"""Offline parser helpers (no browser)."""

from durak_engine.cards import Card, Rank, Suit
from playok_driver.parser import parse_card_token


def test_parse_card_token_variants():
    assert parse_card_token("AH") == Card(Rank.ACE, Suit.HEARTS)
    assert parse_card_token("10S") == Card(Rank.TEN, Suit.SPADES)
    assert parse_card_token("td") == Card(Rank.TEN, Suit.DIAMONDS)
    assert parse_card_token("garbage") is None
