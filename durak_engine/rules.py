"""Podkidnoy Durak rules: legal moves and state transitions."""

from __future__ import annotations

import random
from typing import List, Optional

from .actions import Action, ActionType
from .cards import Card, Suit, deck_36
from .state import GameState, Phase, PlayerState, TablePair


class IllegalMoveError(ValueError):
    pass


MAX_ATTACKS_HARD = 6


def beats(defense: Card, attack: Card, trump: Suit) -> bool:
    """True if defense beats attack under trump suit."""
    if defense.suit == attack.suit:
        return int(defense.rank) > int(attack.rank)
    if defense.suit == trump and attack.suit != trump:
        return True
    return False


def new_game(
    num_players: int = 2,
    seed: Optional[int] = None,
    deck: Optional[List[Card]] = None,
) -> GameState:
    if num_players < 2 or num_players > 6:
        raise ValueError("Durak supports 2–6 players")
    rng = random.Random(seed)
    cards = list(deck) if deck is not None else deck_36()
    rng.shuffle(cards)

    players = [PlayerState() for _ in range(num_players)]
    # Deal 6 each
    for _ in range(6):
        for p in players:
            p.hand.append(cards.pop())

    trump_card = cards[0] if cards else None  # bottom of remaining stock face-up
    trump = trump_card.suit if trump_card else Suit.HEARTS
    # Stock is remaining cards; trump_card stays at bottom visually but is last drawn
    stock = cards  # last card in list is drawn last = trump_card if present

    # Lowest trump starts (classic); fallback player 0
    attacker = _lowest_trump_holder(players, trump)
    defender = (attacker + 1) % num_players

    state = GameState(
        players=players,
        trump=trump,
        trump_card=trump_card,
        stock=stock,
        attacker_index=attacker,
        defender_index=defender,
        phase=Phase.ATTACK,
        active_player=attacker,
        max_attacks=MAX_ATTACKS_HARD,
    )
    return state


def _lowest_trump_holder(players: List[PlayerState], trump: Suit) -> int:
    best_i = 0
    best_rank = 99
    found = False
    for i, p in enumerate(players):
        for c in p.hand:
            if c.suit == trump and int(c.rank) < best_rank:
                best_rank = int(c.rank)
                best_i = i
                found = True
    return best_i if found else 0


def legal_actions(state: GameState) -> List[Action]:
    if state.phase == Phase.GAME_OVER:
        return []

    if state.phase == Phase.ATTACK:
        return _legal_attack_open(state)

    if state.phase == Phase.DEFENSE:
        return _legal_defense(state)

    if state.phase == Phase.THROW_IN:
        return _legal_throw_in(state)

    return []


def _bout_attack_cap(state: GameState) -> int:
    defender = state.players[state.defender_index]
    # At bout start we freeze max_attacks; also never exceed defender's remaining
    # capacity for uncovered slots: uncovered + new <= hand size when not taking
    return min(state.max_attacks, MAX_ATTACKS_HARD)


def _legal_attack_open(state: GameState) -> List[Action]:
    """Primary attacker leads the bout (table empty) or continues after covers cleared mid-bout."""
    actions: List[Action] = []
    player = state.players[state.active_player]
    if state.table:
        # Continuing attack with matching ranks only
        ranks = state.ranks_on_table
        for card in player.hand:
            if card.rank in ranks and len(state.table) < _bout_attack_cap(state):
                actions.append(Action(ActionType.ATTACK, card))
        actions.append(Action(ActionType.PASS))
        return actions

    for card in player.hand:
        actions.append(Action(ActionType.ATTACK, card))
    return actions


def _legal_defense(state: GameState) -> List[Action]:
    actions: List[Action] = [Action(ActionType.TAKE)]
    defender = state.players[state.defender_index]
    for idx, pair in enumerate(state.table):
        if pair.covered:
            continue
        for card in defender.hand:
            if beats(card, pair.attack, state.trump):
                actions.append(
                    Action(ActionType.DEFEND, card=card, target_index=idx)
                )
    return actions


def _can_throw_more(state: GameState) -> bool:
    if len(state.table) >= _bout_attack_cap(state):
        return False
    if state.defender_taking:
        # When taking, can throw until cap or attackers pass
        return len(state.table) < _bout_attack_cap(state)
    # Cannot add more uncovered than defender can still cover (hand size)
    uncovered = len(state.uncovered)
    defender_hand = len(state.players[state.defender_index].hand)
    # Each throw adds an uncovered card; defender still needs cards to cover them
    # Standard rule: total attacks <= min(6, defender cards at bout start) already in max_attacks
    return len(state.table) < _bout_attack_cap(state) and (
        uncovered < defender_hand or defender_hand == 0
    )


def _legal_throw_in(state: GameState) -> List[Action]:
    actions: List[Action] = []
    pid = state.active_player
    if pid == state.defender_index:
        return actions

    player = state.players[pid]
    ranks = state.ranks_on_table
    can_add = _can_throw_more(state) and ranks

    if can_add:
        for card in player.hand:
            if card.rank in ranks:
                actions.append(Action(ActionType.THROW_IN, card))

    # Always can pass (done throwing)
    actions.append(Action(ActionType.PASS))

    # If all covered and this is attacker deciding whether to continue — DONE clears
    # Represented as: if table fully covered and everyone may pass → PASS eventually ends bout
    return actions


def apply_action(state: GameState, action: Action) -> GameState:
    """Return a new state after applying action. Raises IllegalMoveError if illegal."""
    legal = legal_actions(state)
    if not _action_in(action, legal):
        raise IllegalMoveError(f"Illegal action {action} in phase {state.phase.name}")

    s = state.copy()

    if action.type == ActionType.ATTACK:
        _do_attack(s, action.card)
    elif action.type == ActionType.DEFEND:
        _do_defend(s, action.card, action.target_index)
    elif action.type == ActionType.THROW_IN:
        _do_throw_in(s, action.card)
    elif action.type == ActionType.TAKE:
        _do_take(s)
    elif action.type == ActionType.PASS:
        _do_pass(s)
    elif action.type == ActionType.DONE:
        _end_bout_success(s)
    else:
        raise IllegalMoveError(f"Unknown action {action}")

    _check_finished_players(s)
    _check_game_over(s)
    return s


def _action_in(action: Action, legal: List[Action]) -> bool:
    for a in legal:
        if a.type != action.type:
            continue
        if a.card != action.card:
            continue
        if a.target_index != action.target_index:
            continue
        return True
    return False


def _remove_from_hand(player: PlayerState, card: Card) -> None:
    for i, c in enumerate(player.hand):
        if c == card:
            del player.hand[i]
            return
    raise IllegalMoveError(f"Card {card} not in hand")


def _do_attack(s: GameState, card: Card) -> None:
    assert card is not None
    player = s.players[s.active_player]
    _remove_from_hand(player, card)
    if not s.table:
        # Freeze bout attack cap at bout start
        def_hand = len(s.players[s.defender_index].hand)
        s.max_attacks = min(MAX_ATTACKS_HARD, max(1, def_hand))
    s.table.append(TablePair(attack=card))
    s.passed.clear()
    s.phase = Phase.DEFENSE
    s.active_player = s.defender_index


def _do_defend(s: GameState, card: Card, target_index: Optional[int]) -> None:
    assert card is not None and target_index is not None
    pair = s.table[target_index]
    if pair.covered:
        raise IllegalMoveError("Target already covered")
    if not beats(card, pair.attack, s.trump):
        raise IllegalMoveError(f"{card} does not beat {pair.attack}")
    _remove_from_hand(s.players[s.defender_index], card)
    pair.defense = card

    if s.uncovered:
        # Still more to cover
        s.phase = Phase.DEFENSE
        s.active_player = s.defender_index
        return

    # All covered → throw-in phase
    s.phase = Phase.THROW_IN
    s.passed.clear()
    s.active_player = _next_thrower(s, start_after=s.defender_index)


def _do_throw_in(s: GameState, card: Card) -> None:
    assert card is not None
    if card.rank not in s.ranks_on_table:
        raise IllegalMoveError("Throw-in rank not on table")
    _remove_from_hand(s.players[s.active_player], card)
    s.table.append(TablePair(attack=card))
    s.passed.clear()

    if s.defender_taking:
        # Stay in throw-in until pass-around or cap
        s.phase = Phase.THROW_IN
        s.active_player = _next_thrower(s, start_after=s.active_player)
    else:
        s.phase = Phase.DEFENSE
        s.active_player = s.defender_index


def _do_take(s: GameState) -> None:
    s.defender_taking = True
    s.phase = Phase.THROW_IN
    s.passed.clear()
    s.active_player = _next_thrower(s, start_after=s.defender_index)


def _do_pass(s: GameState) -> None:
    if s.phase == Phase.ATTACK and s.table:
        # Attacker declines to add more after successful defense cycle mid-continuation
        _end_bout_success(s)
        return

    if s.phase != Phase.THROW_IN:
        raise IllegalMoveError("PASS only in throw-in / continued attack")

    s.passed.add(s.active_player)

    # Everyone eligible to throw has passed?
    if _all_throwers_passed(s):
        if s.defender_taking:
            _end_bout_take(s)
        else:
            _end_bout_success(s)
        return

    s.active_player = _next_thrower(s, start_after=s.active_player)


def _eligible_throwers(s: GameState) -> List[int]:
    out = []
    for i in range(s.num_players):
        if i == s.defender_index:
            continue
        if s.players[i].finished:
            continue
        if not s.players[i].hand and s.stock_size == 0:
            continue
        out.append(i)
    return out


def _all_throwers_passed(s: GameState) -> bool:
    eligible = _eligible_throwers(s)
    if not eligible:
        return True
    return all(i in s.passed for i in eligible)


def _next_thrower(s: GameState, start_after: int) -> int:
    eligible = _eligible_throwers(s)
    if not eligible:
        return s.attacker_index
    # Walk clockwise from start_after
    i = (start_after + 1) % s.num_players
    for _ in range(s.num_players):
        if i in eligible and i not in s.passed:
            return i
        i = (i + 1) % s.num_players
    return eligible[0]


def _end_bout_take(s: GameState) -> None:
    defender = s.players[s.defender_index]
    for pair in s.table:
        defender.hand.append(pair.attack)
        if pair.defense is not None:
            defender.hand.append(pair.defense)
    s.table.clear()
    s.defender_taking = False
    s.passed.clear()
    _draw_up(s, defender_skipped=False)
    # Attacker stays; next defender is the one after current defender
    # Classic: after take, attacker remains, new defender is next after the one who took
    s.attacker_index = s.attacker_index  # unchanged
    s.defender_index = _next_active(s, s.defender_index)
    # If defender index collides with attacker (2p), fine
    if s.defender_index == s.attacker_index:
        s.defender_index = _next_active(s, s.attacker_index)
    s.phase = Phase.ATTACK
    s.active_player = s.attacker_index
    s.max_attacks = MAX_ATTACKS_HARD


def _end_bout_success(s: GameState) -> None:
    for pair in s.table:
        s.discard.append(pair.attack)
        if pair.defense is not None:
            s.discard.append(pair.defense)
    s.table.clear()
    s.defender_taking = False
    s.passed.clear()
    _draw_up(s, defender_skipped=False)
    # Successful defense: defender becomes next attacker
    s.attacker_index = s.defender_index
    s.defender_index = _next_active(s, s.attacker_index)
    s.phase = Phase.ATTACK
    s.active_player = s.attacker_index
    s.max_attacks = MAX_ATTACKS_HARD


def _next_active(s: GameState, after: int) -> int:
    i = (after + 1) % s.num_players
    for _ in range(s.num_players):
        if not s.players[i].finished:
            return i
        i = (i + 1) % s.num_players
    return after


def _draw_up(s: GameState, defender_skipped: bool) -> None:
    """Draw to six: attacker first, then others clockwise, defender last."""
    order = []
    order.append(s.attacker_index)
    i = (s.attacker_index + 1) % s.num_players
    while i != s.defender_index:
        if i != s.attacker_index:
            order.append(i)
        i = (i + 1) % s.num_players
    order.append(s.defender_index)
    # Deduplicate while preserving order
    seen = set()
    draw_order = []
    for pid in order:
        if pid not in seen:
            seen.add(pid)
            draw_order.append(pid)

    for pid in draw_order:
        p = s.players[pid]
        if p.finished:
            continue
        while len(p.hand) < 6 and s.stock:
            p.hand.append(s.stock.pop())
        if not s.stock:
            s.trump_card = None


def _check_finished_players(s: GameState) -> None:
    if s.stock:
        return
    # Nobody leaves mid-bout; empty hands resolve after the table clears.
    if s.table:
        return
    for i, p in enumerate(s.players):
        if not p.finished and not p.hand and i not in s.winner_order:
            p.finished = True
            s.winner_order.append(i)


def _check_game_over(s: GameState) -> None:
    if s.stock:
        return
    active = [i for i, p in enumerate(s.players) if not p.finished and p.hand]
    # Also players with empty hand already finished
    still = [i for i, p in enumerate(s.players) if not p.finished]
    if len(still) <= 1 and not s.table:
        if still:
            s.fool = still[0]
            s.players[still[0]].finished = True
        elif len(s.winner_order) == s.num_players - 1:
            remaining = [i for i in range(s.num_players) if i not in s.winner_order]
            if remaining:
                s.fool = remaining[0]
        s.phase = Phase.GAME_OVER
        return

    if len(active) <= 1 and not s.table:
        if active:
            s.fool = active[0]
        s.phase = Phase.GAME_OVER
