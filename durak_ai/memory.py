"""Track seen/discarded cards and opponent take piles for inference."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from durak_engine.cards import Card, Suit, deck_36
from durak_engine.state import GameState


@dataclass
class SeenCards:
    """Running memory of cards that left unknown hands."""

    discard: Set[Card] = field(default_factory=set)
    seen_plays: Set[Card] = field(default_factory=set)
    # Cards each opponent picked up when they took (known contents)
    opponent_took: Dict[int, Set[Card]] = field(default_factory=dict)
    known_trump: Optional[Suit] = None
    stock_size: int = 0

    def observe_state(self, state: GameState, our_index: int) -> None:
        self.known_trump = state.trump
        self.stock_size = state.stock_size
        for c in state.discard:
            self.discard.add(c)
            self.seen_plays.add(c)
        for pair in state.table:
            self.seen_plays.add(pair.attack)
            if pair.defense is not None:
                self.seen_plays.add(pair.defense)
        # Our hand is known but not "opponent unseen"
        _ = our_index

    def record_take(self, player_index: int, cards: Iterable[Card]) -> None:
        bucket = self.opponent_took.setdefault(player_index, set())
        for c in cards:
            bucket.add(c)
            self.seen_plays.add(c)

    def record_discard(self, cards: Iterable[Card]) -> None:
        for c in cards:
            self.discard.add(c)
            self.seen_plays.add(c)

    def all_seen(self) -> Set[Card]:
        return set(self.seen_plays) | set(self.discard)

    def unseen_cards(
        self,
        our_hand: Iterable[Card],
        exclude_table: Optional[Iterable[Card]] = None,
    ) -> List[Card]:
        """Cards that could still be in opponent hands or stock."""
        known = self.all_seen() | set(our_hand)
        if exclude_table:
            known |= set(exclude_table)
        return [c for c in deck_36() if c not in known]

    def inferred_opponent_hands_when_stock_empty(
        self,
        state: GameState,
        our_index: int,
    ) -> Dict[int, Set[Card]]:
        """
        When stock is empty, remaining unseen cards are distributed among
        opponents. If a single opponent remains with cards, their hand is exact.
        """
        result: Dict[int, Set[Card]] = {}
        if state.stock_size > 0:
            return result

        table_cards = []
        for p in state.table:
            table_cards.append(p.attack)
            if p.defense is not None:
                table_cards.append(p.defense)

        unseen = set(
            self.unseen_cards(state.players[our_index].hand, exclude_table=table_cards)
        )
        # Remove cards we already know opponents took that are still in their hands
        # (approx: took pile minus later discards — we treat took as still held if unseen)
        opponents = [
            i
            for i in range(state.num_players)
            if i != our_index and not state.players[i].finished
        ]
        if len(opponents) == 1:
            opp = opponents[0]
            # Exact: unseen must be their hand (plus any known took still held)
            held = set(unseen)
            took = self.opponent_took.get(opp, set())
            held |= {c for c in took if c not in self.discard and c not in table_cards}
            # Size check: trim not needed if tracking is consistent
            result[opp] = held
        else:
            for opp in opponents:
                took = self.opponent_took.get(opp, set())
                result[opp] = {
                    c for c in took if c not in self.discard and c not in table_cards
                }
        return result

    def copy(self) -> "SeenCards":
        return SeenCards(
            discard=set(self.discard),
            seen_plays=set(self.seen_plays),
            opponent_took={k: set(v) for k, v in self.opponent_took.items()},
            known_trump=self.known_trump,
            stock_size=self.stock_size,
        )
