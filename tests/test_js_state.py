"""Offline tests for JS board state mapping (no live PlayOK)."""

from __future__ import annotations

from durak_engine.cards import Card, Rank, Suit
from playok_driver.js_state import read_live_state
from playok_driver.parser import ParsedTable, _merge_dk_js_state


class _FakePage:
    def __init__(self, payload: dict):
        self._payload = payload

    def evaluate(self, *_a, **_k):
        return self._payload


def test_read_live_state_decodes_hand_and_trump():
    # 6♥=48, A♠=115, table 7♦=57
    page = _FakePage(
        {
            "ok": True,
            "seat": 0,
            "active": True,
            "hands": [
                [{"rank": 6, "suit": 0, "raw": 48}, {"rank": 14, "suit": 3, "raw": 115}],
                [{"rank": 9, "suit": 2, "raw": 74}],
            ],
            "tableAttacks": [{"rank": 7, "suit": 1, "raw": 57}],
            "tableDefenses": [None],
            "trumpCard": {"rank": 10, "suit": 3, "raw": 83},
            "trumpSuit": 3,
        }
    )
    live = read_live_state(page)
    assert live.ok
    assert live.hand == [
        Card(Rank.SIX, Suit.HEARTS),
        Card(Rank.ACE, Suit.SPADES),
    ]
    assert live.table_attacks == [Card(Rank.SEVEN, Suit.DIAMONDS)]
    assert live.trump == Suit.SPADES
    assert live.trump_card == Card(Rank.TEN, Suit.SPADES)


def test_merge_sets_parse_fields():
    page = _FakePage(
        {
            "ok": True,
            "seat": 1,
            "active": True,
            "hands": [[], [{"rank": 11, "suit": 0, "raw": 88}]],
            "tableAttacks": [],
            "tableDefenses": [],
            "trumpCard": {"rank": 6, "suit": 2, "raw": 50},
        }
    )
    result = ParsedTable()
    _merge_dk_js_state(page, result)
    assert result.state_source == "dk_js"
    assert result.our_seat == 1
    assert result.hand == [Card(Rank.JACK, Suit.HEARTS)]
    assert result.trump == Suit.CLUBS
