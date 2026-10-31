"""Card types for 36-card Durak."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List


class Suit(str, Enum):
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Rank(int, Enum):
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self) -> str:  # pragma: no cover - trivial
        names = {
            6: "6",
            7: "7",
            8: "8",
            9: "9",
            10: "T",
            11: "J",
            12: "Q",
            13: "K",
            14: "A",
        }
        return names[int(self.value)]


RANK_SYMBOLS = {
    "6": Rank.SIX,
    "7": Rank.SEVEN,
    "8": Rank.EIGHT,
    "9": Rank.NINE,
    "10": Rank.TEN,
    "T": Rank.TEN,
    "J": Rank.JACK,
    "Q": Rank.QUEEN,
    "K": Rank.KING,
    "A": Rank.ACE,
}

SUIT_SYMBOLS = {
    "H": Suit.HEARTS,
    "D": Suit.DIAMONDS,
    "C": Suit.CLUBS,
    "S": Suit.SPADES,
    "♥": Suit.HEARTS,
    "♦": Suit.DIAMONDS,
    "♣": Suit.CLUBS,
    "♠": Suit.SPADES,
}


@dataclass(frozen=True, order=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    @property
    def short(self) -> str:
        return str(self)

    def is_trump(self, trump: Suit) -> bool:
        return self.suit == trump

    @classmethod
    def parse(cls, text: str) -> "Card":
        text = text.strip().upper().replace("10", "T")
        if len(text) < 2:
            raise ValueError(f"Cannot parse card: {text!r}")
        rank_s, suit_s = text[:-1], text[-1]
        if rank_s not in RANK_SYMBOLS or suit_s not in SUIT_SYMBOLS:
            raise ValueError(f"Cannot parse card: {text!r}")
        return cls(RANK_SYMBOLS[rank_s], SUIT_SYMBOLS[suit_s])


def deck_36() -> List[Card]:
    return [Card(rank, suit) for suit in Suit for rank in Rank]


def cards_from(texts: Iterable[str]) -> List[Card]:
    return [Card.parse(t) for t in texts]
