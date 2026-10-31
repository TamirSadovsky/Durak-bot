"""Defender detection from parsed UI (regression: take+pass both visible)."""

from durak_engine.cards import Card, Rank, Suit
from durak_engine.state import Phase
from playok_driver.parser import ParsedTable
from playok_driver.state_bridge import parsed_to_state


def test_defender_when_take_and_pass_both_visible():
    """Screenshot case: uncoverd 10C, take+pass shown — must be DEFENSE not ATTACK."""
    parsed = ParsedTable(
        hand=[
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.ACE, Suit.SPADES),
        ],
        table_attacks=[Card(Rank.TEN, Suit.CLUBS)],
        table_defenses=[None],
        trump=Suit.HEARTS,
        trump_card=Card(Rank.TEN, Suit.HEARTS),
        can_take=True,
        can_pass=True,  # visible (often disabled) — previously broke detection
        our_turn=True,
        board_active=True,
        state_source="dk_js",
        parse_ok=True,
    )
    state = parsed_to_state(parsed, our_index=0)
    assert state.defender_index == 0
    assert state.phase == Phase.DEFENSE


def test_uncovered_table_implies_defense():
    parsed = ParsedTable(
        hand=[Card(Rank.SIX, Suit.SPADES)],
        table_attacks=[Card(Rank.NINE, Suit.DIAMONDS)],
        table_defenses=[None],
        trump=Suit.HEARTS,
        board_active=True,
        our_turn=True,
        state_source="dk_js",
    )
    state = parsed_to_state(parsed)
    assert state.phase == Phase.DEFENSE
    assert state.defender_index == 0
