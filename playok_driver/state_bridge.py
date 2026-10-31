"""Map ParsedTable → GameState suitable for AI (hero-centric 2p approximation)."""

from __future__ import annotations

from typing import Optional

from durak_engine.cards import Suit
from durak_engine.state import GameState, Phase, PlayerState, TablePair

from .parser import ParsedTable


def parsed_to_state(
    parsed: ParsedTable,
    *,
    our_index: int = 0,
    opponent_hand_size: int = 6,
    we_are_defender: Optional[bool] = None,
) -> GameState:
    """
    Build a minimal GameState from DOM snapshot.

    Opponent cards are unknown; we place face-down placeholders as empty hand
    with `opponent_hand_size` tracked only loosely (empty list — AI uses memory).
    """
    trump = parsed.trump or Suit.HEARTS
    our = PlayerState(hand=list(parsed.hand))
    opp = PlayerState(hand=[])  # unknown
    # Keep empty placeholders so hand-size heuristics that read len(hand) use
    # opponent_hand_size via a synthetic pad only when needed:
    # For throw-in dump threshold we pass defender_taking / buttons instead.

    table = []
    for i, atk in enumerate(parsed.table_attacks):
        defense = None
        if i < len(parsed.table_defenses):
            defense = parsed.table_defenses[i]
        table.append(TablePair(attack=atk, defense=defense))

    uncovered = any(not p.covered for p in table)
    if we_are_defender is None:
        # Take is shown during defend even when Pass is also visible (often disabled).
        # Do NOT require `not can_pass` — that broke defender detection after hand 1.
        we_are_defender = bool(
            parsed.can_take
            or parsed.defender_taking
            or (uncovered and (parsed.board_active or parsed.can_take or parsed.our_turn))
            or (uncovered and parsed.state_source == "dk_js" and parsed.board_active)
        )
        # Uncovered attack on table while it is our interaction window → defending
        if uncovered and (parsed.board_active or parsed.our_turn or parsed.can_take):
            we_are_defender = True

    if we_are_defender:
        attacker_index, defender_index = 1, 0
        phase = Phase.DEFENSE if uncovered else Phase.THROW_IN
        active = 0
    elif table and all(p.covered for p in table):
        attacker_index, defender_index = 0, 1
        phase = Phase.THROW_IN
        active = 0
    elif table:
        attacker_index, defender_index = 0, 1
        phase = Phase.ATTACK
        active = 0
    else:
        attacker_index, defender_index = 0, 1
        phase = Phase.ATTACK
        active = 0

    stock = []
    # Represent stock size with dummy unknown cards for phase only
    n = parsed.stock_size if parsed.stock_size is not None else 12
    # Use unique dummy? Engine only needs len(stock) — use empty and override via copy trick
    # We'll set stock to n copies of trump_card if known else leave mid default via Fake:
    from durak_engine.cards import Card, Rank

    dummy = parsed.trump_card or Card(Rank.SIX, trump)
    # Don't pollute card identity: stock cards are not used for identity in AI phase
    # Use distinct placeholders by not adding real deck cards — AI reads stock_size via len
    # Creating n references of same card is OK for len only if we never draw in live loop.
    stock = [dummy] * max(0, n)

    # Fake opponent hand size for dump heuristics when we attack
    if not we_are_defender:
        opp.hand = [dummy] * max(0, opponent_hand_size)

    state = GameState(
        players=[our, opp],
        trump=trump,
        trump_card=parsed.trump_card,
        stock=stock,
        table=table,
        attacker_index=attacker_index,
        defender_index=defender_index,
        phase=phase,
        active_player=active,
        defender_taking=parsed.defender_taking,
        max_attacks=6,
    )
    return state
