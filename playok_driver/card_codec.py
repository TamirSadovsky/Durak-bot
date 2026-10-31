"""PlayOK / dk.js card integer codec.

Encoding (from /j/dk.js draw + trump helpers):
  value = rank_index * 8 + suit_index   (bits 0–1 suit, bit 2 = UI selected flag, bits 3+ rank)
  stored in hand as value + 128 * seat
  rank_index indexes td = ['-', 'Jo', '2'..'9', '10', 'J', 'Q', 'K', 'A']  (Durak uses 6–14)
  suit_index: 0 hearts, 1 diamonds, 2 clubs, 3 spades
"""

from __future__ import annotations

from typing import Optional

from durak_engine.cards import Card, Rank, Suit

TD_RANKS = ["-", "Jo", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = (Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES)

RANK_TO_INDEX = {
    Rank.SIX: 6,
    Rank.SEVEN: 7,
    Rank.EIGHT: 8,
    Rank.NINE: 9,
    Rank.TEN: 10,
    Rank.JACK: 11,
    Rank.QUEEN: 12,
    Rank.KING: 13,
    Rank.ACE: 14,
}
INDEX_TO_RANK = {v: k for k, v in RANK_TO_INDEX.items()}
SUIT_TO_INDEX = {
    Suit.HEARTS: 0,
    Suit.DIAMONDS: 1,
    Suit.CLUBS: 2,
    Suit.SPADES: 3,
}


def strip_flags(value: int) -> int:
    """Clear selection bit and seat offset → 0–127 card code (0 = empty pad)."""
    return (int(value) & ~4) % 128


def decode_raw(value: int) -> Optional[Card]:
    code = strip_flags(value)
    if code == 0:
        return None
    rank_i = (code // 8) % 16
    suit_i = code % 4
    rank = INDEX_TO_RANK.get(rank_i)
    if rank is None or suit_i >= len(SUITS):
        return None
    return Card(rank, SUITS[suit_i])


def encode_card(card: Card, seat: int = 0, selected: bool = False) -> int:
    code = RANK_TO_INDEX[card.rank] * 8 + SUIT_TO_INDEX[card.suit]
    if selected:
        code |= 4
    return code + 128 * seat
