"""Game state for podkidnoy Durak."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Set

from .cards import Card, Suit


class Phase(Enum):
    ATTACK = auto()  # primary attacker must lead (or continue after empty)
    DEFENSE = auto()  # defender must cover or take
    THROW_IN = auto()  # attackers may throw in / pass
    DRAW = auto()  # internal: refill hands (applied automatically)
    ROUND_END = auto()
    GAME_OVER = auto()


@dataclass
class TablePair:
    attack: Card
    defense: Optional[Card] = None

    @property
    def covered(self) -> bool:
        return self.defense is not None


@dataclass
class PlayerState:
    hand: List[Card] = field(default_factory=list)
    finished: bool = False  # out of cards after stock empty

    def copy(self) -> "PlayerState":
        return PlayerState(hand=list(self.hand), finished=self.finished)


@dataclass
class GameState:
    """Complete podkidnoy Durak state (N players, typically 2–6)."""

    players: List[PlayerState]
    trump: Suit
    trump_card: Optional[Card]  # face-up under stock (None if stock depleted and consumed)
    stock: List[Card]
    discard: List[Card] = field(default_factory=list)
    table: List[TablePair] = field(default_factory=list)
    attacker_index: int = 0
    defender_index: int = 1
    phase: Phase = Phase.ATTACK
    # Whose turn within THROW_IN / ATTACK continuation
    active_player: int = 0
    # Players who have passed this throw-in round (reset when new attack card lands)
    passed: Set[int] = field(default_factory=set)
    # Max attack cards this bout (min(6, defender hand at bout start))
    max_attacks: int = 6
    defender_taking: bool = False
    winner_order: List[int] = field(default_factory=list)  # order finished
    fool: Optional[int] = None

    @property
    def num_players(self) -> int:
        return len(self.players)

    @property
    def stock_size(self) -> int:
        return len(self.stock)

    @property
    def uncovered(self) -> List[TablePair]:
        return [p for p in self.table if not p.covered]

    @property
    def ranks_on_table(self) -> Set:
        ranks = set()
        for pair in self.table:
            ranks.add(pair.attack.rank)
            if pair.defense is not None:
                ranks.add(pair.defense.rank)
        return ranks

    def copy(self) -> "GameState":
        return GameState(
            players=[p.copy() for p in self.players],
            trump=self.trump,
            trump_card=self.trump_card,
            stock=list(self.stock),
            discard=list(self.discard),
            table=[
                TablePair(attack=p.attack, defense=p.defense) for p in self.table
            ],
            attacker_index=self.attacker_index,
            defender_index=self.defender_index,
            phase=self.phase,
            active_player=self.active_player,
            passed=set(self.passed),
            max_attacks=self.max_attacks,
            defender_taking=self.defender_taking,
            winner_order=list(self.winner_order),
            fool=self.fool,
        )
