"""Tests for PlayOK dk.js card encoding."""

from durak_engine.cards import Card, Rank, Suit
from playok_driver.card_codec import decode_raw, encode_card, strip_flags
from playok_driver.dk_patch import BOARD_CREATE_NEEDLE, patch_dk_js


def test_roundtrip_common_cards():
    for rank in Rank:
        for suit in Suit:
            raw = encode_card(Card(rank, suit), seat=0)
            assert decode_raw(raw) == Card(rank, suit)


def test_seat_offset_and_selection_bit():
    c = Card(Rank.ACE, Suit.SPADES)
    enc = encode_card(c, seat=2, selected=True)
    assert enc == (14 * 8 + 3) + 128 * 2 + 4
    assert strip_flags(enc) == 14 * 8 + 3
    assert decode_raw(enc) == c


def test_empty_pad_is_none():
    assert decode_raw(0) is None
    assert decode_raw(128) is None  # seat-1 pad


def test_dk_patch_injects_board_expose():
    src = f"prelude;{BOARD_CREATE_NEEDLE};epilogue"
    out, notes = patch_dk_js(src)
    assert "window.__durakBoard=this.G" in out
    assert "window.__durakTab=this" in out
    assert any("patched board" in n for n in notes)
    # idempotent
    out2, notes2 = patch_dk_js(out)
    assert out2.count("window.__durakBoard=this.G") == 1
    assert any("already present" in n for n in notes2)
