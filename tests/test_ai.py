"""Unit tests for phased heuristic AI and seen-card memory."""

from __future__ import annotations

from durak_ai import HeuristicPolicy, SeenCards, card_value, game_phase
from durak_ai.policy import GamePhase
from durak_engine import Action, ActionType, Card, Rank, Suit
from durak_engine.cards import deck_36
from durak_engine.state import GameState, Phase, PlayerState, TablePair


def test_phases_by_stock():
    assert game_phase(24) == GamePhase.EARLY
    assert game_phase(13) == GamePhase.EARLY
    assert game_phase(12) == GamePhase.MID
    assert game_phase(1) == GamePhase.MID
    assert game_phase(0) == GamePhase.ENDGAME


def test_card_value_trump_bonus():
    assert card_value(Card(Rank.SIX, Suit.HEARTS), Suit.SPADES) == 6
    assert card_value(Card(Rank.SIX, Suit.SPADES), Suit.SPADES) == 6 + 20


def test_take_vs_trump_save():
    """Cheapest cover is high trump vs low non-trump attack while stock>0 → TAKE."""
    defender = PlayerState(
        hand=[
            Card(Rank.ACE, Suit.SPADES),  # only cover: high trump
            Card(Rank.KING, Suit.HEARTS),
        ]
    )
    attacker = PlayerState(hand=[Card(Rank.NINE, Suit.CLUBS)])
    state = GameState(
        players=[attacker, defender],
        trump=Suit.SPADES,
        trump_card=Card(Rank.SIX, Suit.SPADES),
        stock=[Card(Rank.SEVEN, Suit.CLUBS)] * 10,
        table=[TablePair(attack=Card(Rank.SIX, Suit.CLUBS))],
        attacker_index=0,
        defender_index=1,
        phase=Phase.DEFENSE,
        active_player=1,
        max_attacks=6,
    )
    policy = HeuristicPolicy(our_index=1)
    action = policy.choose(state)
    assert action.type == ActionType.TAKE


def test_defend_cheap_non_trump_when_available():
    defender = PlayerState(
        hand=[
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.ACE, Suit.SPADES),
        ]
    )
    attacker = PlayerState(hand=[])
    state = GameState(
        players=[attacker, defender],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[Card(Rank.SEVEN, Suit.HEARTS)] * 8,
        table=[TablePair(attack=Card(Rank.SIX, Suit.CLUBS))],
        attacker_index=0,
        defender_index=1,
        phase=Phase.DEFENSE,
        active_player=1,
        max_attacks=6,
    )
    action = HeuristicPolicy(our_index=1).choose(state)
    assert action.type == ActionType.DEFEND
    assert action.card == Card(Rank.EIGHT, Suit.CLUBS)


def test_attack_prefers_lowest_non_trump():
    us = PlayerState(
        hand=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.NINE, Suit.HEARTS),
            Card(Rank.SIX, Suit.CLUBS),
        ]
    )
    them = PlayerState(hand=[Card(Rank.KING, Suit.CLUBS)])
    state = GameState(
        players=[us, them],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[Card(Rank.SEVEN, Suit.DIAMONDS)] * 14,
        table=[],
        attacker_index=0,
        defender_index=1,
        phase=Phase.ATTACK,
        active_player=0,
        max_attacks=6,
    )
    action = HeuristicPolicy(our_index=0).choose(state)
    assert action.type == ActionType.ATTACK
    assert action.card == Card(Rank.SIX, Suit.CLUBS)


def test_attack_prefers_pair_for_shedding():
    us = PlayerState(
        hand=[
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.CLUBS),
            Card(Rank.SIX, Suit.DIAMONDS),
        ]
    )
    them = PlayerState(hand=[Card(Rank.KING, Suit.CLUBS)])
    state = GameState(
        players=[us, them],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[Card(Rank.EIGHT, Suit.DIAMONDS)] * 14,
        table=[],
        attacker_index=0,
        defender_index=1,
        phase=Phase.ATTACK,
        active_player=0,
        max_attacks=6,
    )
    action = HeuristicPolicy(our_index=0).choose(state)
    assert action.type == ActionType.ATTACK
    assert action.card is not None
    assert action.card.rank == Rank.SEVEN


def test_endgame_unbeatable_lead():
    """With stock empty and inferred opponent hand, lead a card they cannot beat."""
    # Opponent holds 7C (beats our 6C) but cannot beat Ace of trump.
    us = PlayerState(
        hand=[
            Card(Rank.SIX, Suit.CLUBS),
            Card(Rank.ACE, Suit.SPADES),
        ]
    )
    them = PlayerState(hand=[Card(Rank.SEVEN, Suit.CLUBS)])
    # Build memory: everything else seen/discarded so inference is exact
    memory = SeenCards(stock_size=0, known_trump=Suit.SPADES)
    our_and_opp = set(us.hand) | set(them.hand)
    for c in deck_36():
        if c not in our_and_opp:
            memory.discard.add(c)
            memory.seen_plays.add(c)

    state = GameState(
        players=[us, them],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[],
        table=[],
        attacker_index=0,
        defender_index=1,
        phase=Phase.ATTACK,
        active_player=0,
        max_attacks=6,
    )
    policy = HeuristicPolicy(our_index=0, memory=memory)
    action = policy.choose(state)
    assert action.type == ActionType.ATTACK
    assert action.card == Card(Rank.ACE, Suit.SPADES)


def test_throw_in_dumps_when_defender_taking():
    us = PlayerState(
        hand=[
            Card(Rank.SIX, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.SPADES),
        ]
    )
    them = PlayerState(hand=[Card(Rank.KING, Suit.CLUBS)])
    state = GameState(
        players=[us, them],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[Card(Rank.EIGHT, Suit.CLUBS)] * 5,
        table=[TablePair(attack=Card(Rank.SIX, Suit.HEARTS))],
        attacker_index=0,
        defender_index=1,
        phase=Phase.THROW_IN,
        active_player=0,
        max_attacks=6,
        defender_taking=True,
    )
    action = HeuristicPolicy(our_index=0).choose(state)
    assert action.type == ActionType.THROW_IN
    assert action.card == Card(Rank.SIX, Suit.DIAMONDS)
