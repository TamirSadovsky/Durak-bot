"""Phased heuristic policy for podkidnoy Durak."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set

from durak_engine.actions import Action, ActionType
from durak_engine.cards import Card, Suit
from durak_engine.rules import beats, legal_actions
from durak_engine.state import GameState, Phase

from .memory import SeenCards

TRUMP_BONUS = 20
HIGH_TRUMP_THRESHOLD = 11  # Jack+
MULTI_TRUMP_COST_THRESHOLD = TRUMP_BONUS + 10  # roughly two trumps / high trump


class GamePhase(Enum):
    EARLY = auto()
    MID = auto()
    ENDGAME = auto()


def game_phase(stock_size: int) -> GamePhase:
    if stock_size > 12:
        return GamePhase.EARLY
    if stock_size > 0:
        return GamePhase.MID
    return GamePhase.ENDGAME


def card_value(card: Card, trump: Suit) -> int:
    return int(card.rank) + (TRUMP_BONUS if card.suit == trump else 0)


@dataclass
class HeuristicPolicy:
    our_index: int
    memory: Optional[SeenCards] = None
    # Defend: take if cheapest cover is high trump vs low attack while stock remains
    high_trump_save: bool = True
    multi_trump_take_threshold: int = MULTI_TRUMP_COST_THRESHOLD

    def choose(self, state: GameState) -> Action:
        if self.memory is not None:
            self.memory.observe_state(state, self.our_index)
        actions = legal_actions(state)
        if not actions:
            raise RuntimeError("No legal actions")
        return choose_action(state, actions, self.our_index, self.memory, self)


def choose_action(
    state: GameState,
    actions: List[Action],
    our_index: int,
    memory: Optional[SeenCards] = None,
    policy: Optional[HeuristicPolicy] = None,
) -> Action:
    policy = policy or HeuristicPolicy(our_index=our_index, memory=memory)
    phase = game_phase(state.stock_size)

    by_type: Dict[ActionType, List[Action]] = {}
    for a in actions:
        by_type.setdefault(a.type, []).append(a)

    if state.phase == Phase.DEFENSE and our_index == state.defender_index:
        return _choose_defend(state, by_type, phase, policy)

    if ActionType.ATTACK in by_type and state.phase == Phase.ATTACK:
        return _choose_attack(state, by_type, phase, policy, memory)

    if state.phase == Phase.THROW_IN or (
        ActionType.THROW_IN in by_type or ActionType.PASS in by_type
    ):
        if ActionType.THROW_IN in by_type or ActionType.PASS in by_type:
            return _choose_throw_or_pass(state, by_type, phase, policy, memory)

    # Fallback: lowest-value card action, else first
    return _lowest_card_action(actions, state.trump) or actions[0]


def _lowest_card_action(actions: List[Action], trump: Suit) -> Optional[Action]:
    card_actions = [a for a in actions if a.card is not None]
    if not card_actions:
        return None
    return min(card_actions, key=lambda a: card_value(a.card, trump))  # type: ignore[arg-type]


def _rank_counts(hand: List[Card]) -> Dict:
    counts: Dict = {}
    for c in hand:
        counts[c.rank] = counts.get(c.rank, 0) + 1
    return counts


def _choose_attack(
    state: GameState,
    by_type: Dict[ActionType, List[Action]],
    phase: GamePhase,
    policy: HeuristicPolicy,
    memory: Optional[SeenCards],
) -> Action:
    attacks = by_type.get(ActionType.ATTACK, [])
    passes = by_type.get(ActionType.PASS, [])

    if not attacks:
        return passes[0] if passes else list(by_type.values())[0][0]

    # Endgame: prefer unbeatable leads if we can infer opponent hand
    if phase == GamePhase.ENDGAME and memory is not None and not state.table:
        unbeatable = _unbeatable_leads(state, attacks, policy.our_index, memory)
        if unbeatable:
            return min(unbeatable, key=lambda a: card_value(a.card, state.trump))  # type: ignore

    hand = state.players[policy.our_index].hand
    counts = _rank_counts(hand)

    non_trump = [a for a in attacks if a.card and a.card.suit != state.trump]
    pool = non_trump if non_trump else attacks

    # Prefer pairs/triples for shedding (open that rank)
    paired = [
        a
        for a in pool
        if a.card and counts.get(a.card.rank, 0) >= 2
    ]
    if paired and phase != GamePhase.ENDGAME:
        return min(paired, key=lambda a: card_value(a.card, state.trump))  # type: ignore

    best = min(pool, key=lambda a: card_value(a.card, state.trump))  # type: ignore

    # Pass/done: stop when remaining cards high for phase (continued attack)
    if state.table and passes:
        if _should_stop_attacking(state, best, phase, policy):
            return passes[0]

    return best


def _should_stop_attacking(
    state: GameState,
    best_attack: Action,
    phase: GamePhase,
    policy: HeuristicPolicy,
) -> bool:
    if best_attack.card is None:
        return True
    v = card_value(best_attack.card, state.trump)
    if phase == GamePhase.EARLY and v >= 10:
        return True
    if phase == GamePhase.MID and (
        best_attack.card.suit == state.trump or v >= 12
    ):
        return True
    if phase == GamePhase.ENDGAME:
        return False  # continue if we still have a lead (caller may override)
    return False


def _unbeatable_leads(
    state: GameState,
    attacks: List[Action],
    our_index: int,
    memory: SeenCards,
) -> List[Action]:
    inferred = memory.inferred_opponent_hands_when_stock_empty(state, our_index)
    if state.defender_index not in inferred:
        return []
    opp_hand = inferred[state.defender_index]
    if not opp_hand:
        return []
    out = []
    for a in attacks:
        if a.card is None:
            continue
        if not any(beats(c, a.card, state.trump) for c in opp_hand):
            out.append(a)
    return out


def _choose_defend(
    state: GameState,
    by_type: Dict[ActionType, List[Action]],
    phase: GamePhase,
    policy: HeuristicPolicy,
) -> Action:
    covers = by_type.get(ActionType.DEFEND, [])
    takes = by_type.get(ActionType.TAKE, [])

    if not covers:
        return takes[0]

    # Cheapest cover overall (among all uncovered targets — pick globally cheapest action)
    cheapest = min(covers, key=lambda a: card_value(a.card, state.trump))  # type: ignore
    assert cheapest.card is not None
    assert cheapest.target_index is not None
    attack_card = state.table[cheapest.target_index].attack

    # High trump vs low attack + stock → TAKE
    if (
        policy.high_trump_save
        and takes
        and state.stock_size > 0
        and cheapest.card.suit == state.trump
        and int(cheapest.card.rank) >= HIGH_TRUMP_THRESHOLD
        and int(attack_card.rank) <= 8
        and attack_card.suit != state.trump
    ):
        return takes[0]

    # Multi-trump cost to cover whole table
    if takes and state.stock_size > 0:
        cost = _estimate_full_cover_trump_cost(state, covers)
        if cost >= policy.multi_trump_take_threshold:
            return takes[0]

    return cheapest


def _estimate_full_cover_trump_cost(
    state: GameState, covers: List[Action]
) -> int:
    """Greedy estimate: sum of trump values of cheapest cover per uncovered attack."""
    total = 0
    for idx, pair in enumerate(state.table):
        if pair.covered:
            continue
        options = [a for a in covers if a.target_index == idx and a.card]
        if not options:
            return policy_inf()
        best = min(options, key=lambda a: card_value(a.card, state.trump))  # type: ignore
        if best.card and best.card.suit == state.trump:
            total += card_value(best.card, state.trump)
    return total


def policy_inf() -> int:
    return 10_000


def _choose_throw_or_pass(
    state: GameState,
    by_type: Dict[ActionType, List[Action]],
    phase: GamePhase,
    policy: HeuristicPolicy,
    memory: Optional[SeenCards],
) -> Action:
    throws = by_type.get(ActionType.THROW_IN, [])
    passes = by_type.get(ActionType.PASS, [])
    attacks = by_type.get(ActionType.ATTACK, [])  # continued attack uses ATTACK

    candidates = throws or attacks
    if not candidates:
        return passes[0]

    hand = state.players[policy.our_index].hand
    defender_hand_size = len(state.players[state.defender_index].hand)
    dump = state.defender_taking or defender_hand_size <= 3

    non_trump = [a for a in candidates if a.card and a.card.suit != state.trump]
    pool = non_trump if non_trump else ([] if not dump else candidates)

    if dump:
        pool = non_trump if non_trump else candidates
        if pool:
            return min(pool, key=lambda a: card_value(a.card, state.trump))  # type: ignore
        return passes[0] if passes else candidates[0]

    # Else: lowest matching non-trumps that are not sole suit covers
    safe = []
    for a in non_trump:
        assert a.card is not None
        if _is_sole_suit_cover(a.card, hand, state):
            continue
        safe.append(a)

    if safe:
        best = min(safe, key=lambda a: card_value(a.card, state.trump))  # type: ignore
        if _should_stop_attacking(state, best, phase, policy):
            return passes[0] if passes else best
        return best

    # Endgame: continue if unbeatable
    if phase == GamePhase.ENDGAME and memory is not None and candidates:
        unbeatable = _unbeatable_leads(state, candidates, policy.our_index, memory)
        if unbeatable:
            return min(unbeatable, key=lambda a: card_value(a.card, state.trump))  # type: ignore

    return passes[0] if passes else min(
        candidates, key=lambda a: card_value(a.card, state.trump)  # type: ignore
    )


def _is_sole_suit_cover(card: Card, hand: List[Card], state: GameState) -> bool:
    """True if this card is our only non-trump cover for its suit (keep for defense)."""
    if card.suit == state.trump:
        return True
    same_suit = [c for c in hand if c.suit == card.suit]
    return len(same_suit) <= 1
