"""Unit tests for podkidnoy Durak rules engine."""

from __future__ import annotations

import pytest

from durak_engine import (
    Action,
    ActionType,
    Card,
    IllegalMoveError,
    Rank,
    Suit,
    apply_action,
    beats,
    legal_actions,
    new_game,
)
from durak_engine.cards import deck_36
from durak_engine.state import GameState, Phase, PlayerState, TablePair


def test_deck_has_36_unique_cards():
    d = deck_36()
    assert len(d) == 36
    assert len(set(d)) == 36


def test_beats_same_suit_higher():
    assert beats(Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.HEARTS), Suit.SPADES)
    assert not beats(
        Card(Rank.KING, Suit.HEARTS), Card(Rank.ACE, Suit.HEARTS), Suit.SPADES
    )


def test_beats_trump_over_non_trump():
    assert beats(Card(Rank.SIX, Suit.SPADES), Card(Rank.ACE, Suit.HEARTS), Suit.SPADES)
    assert not beats(
        Card(Rank.ACE, Suit.HEARTS), Card(Rank.SIX, Suit.SPADES), Suit.SPADES
    )


def test_new_game_deals_six():
    g = new_game(2, seed=1)
    assert all(len(p.hand) == 6 for p in g.players)
    assert g.trump_card is not None
    assert g.trump == g.trump_card.suit
    assert g.stock_size == 36 - 12
    assert g.phase == Phase.ATTACK


def test_illegal_defend_rejected():
    our = PlayerState(hand=[Card(Rank.SEVEN, Suit.HEARTS)])
    opp = PlayerState(hand=[Card(Rank.ACE, Suit.CLUBS)])
    state = GameState(
        players=[opp, our],
        trump=Suit.SPADES,
        trump_card=Card(Rank.SIX, Suit.SPADES),
        stock=[],
        table=[TablePair(attack=Card(Rank.ACE, Suit.CLUBS))],
        attacker_index=0,
        defender_index=1,
        phase=Phase.DEFENSE,
        active_player=1,
        max_attacks=6,
    )
    with pytest.raises(IllegalMoveError):
        apply_action(
            state,
            Action(
                ActionType.DEFEND,
                card=Card(Rank.SEVEN, Suit.HEARTS),
                target_index=0,
            ),
        )


def test_legal_defend_with_trump():
    our = PlayerState(hand=[Card(Rank.SIX, Suit.SPADES)])
    opp = PlayerState(hand=[])
    state = GameState(
        players=[opp, our],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[],
        table=[TablePair(attack=Card(Rank.ACE, Suit.CLUBS))],
        attacker_index=0,
        defender_index=1,
        phase=Phase.DEFENSE,
        active_player=1,
        max_attacks=1,
    )
    acts = legal_actions(state)
    assert any(a.type == ActionType.TAKE for a in acts)
    assert any(
        a.type == ActionType.DEFEND and a.card == Card(Rank.SIX, Suit.SPADES)
        for a in acts
    )
    nxt = apply_action(
        state,
        Action(
            ActionType.DEFEND,
            card=Card(Rank.SIX, Suit.SPADES),
            target_index=0,
        ),
    )
    assert nxt.table[0].covered
    assert nxt.phase == Phase.THROW_IN


def test_attack_then_take_collector():
    attacker = PlayerState(
        hand=[Card(Rank.SIX, Suit.HEARTS), Card(Rank.SIX, Suit.DIAMONDS)]
    )
    # Defender needs >1 card at bout start so max_attacks allows a throw-in.
    defender = PlayerState(
        hand=[Card(Rank.EIGHT, Suit.CLUBS), Card(Rank.NINE, Suit.DIAMONDS)]
    )
    state = GameState(
        players=[attacker, defender],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[Card(Rank.NINE, Suit.CLUBS)] * 4,
        table=[],
        attacker_index=0,
        defender_index=1,
        phase=Phase.ATTACK,
        active_player=0,
        max_attacks=6,
    )
    state = apply_action(
        state, Action(ActionType.ATTACK, Card(Rank.SIX, Suit.HEARTS))
    )
    assert state.phase == Phase.DEFENSE
    state = apply_action(state, Action(ActionType.TAKE))
    assert state.defender_taking
    assert state.phase == Phase.THROW_IN
    # Attacker throws matching rank then passes → defender picks up
    state = apply_action(
        state, Action(ActionType.THROW_IN, Card(Rank.SIX, Suit.DIAMONDS))
    )
    state = apply_action(state, Action(ActionType.PASS))
    assert not state.table
    assert Card(Rank.SIX, Suit.HEARTS) in state.players[1].hand
    assert Card(Rank.SIX, Suit.DIAMONDS) in state.players[1].hand


def test_successful_defense_discards_and_roles_swap():
    attacker = PlayerState(hand=[Card(Rank.SIX, Suit.HEARTS)])
    defender = PlayerState(hand=[Card(Rank.SEVEN, Suit.HEARTS)])
    state = GameState(
        players=[attacker, defender],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[],
        table=[],
        attacker_index=0,
        defender_index=1,
        phase=Phase.ATTACK,
        active_player=0,
        max_attacks=1,
    )
    state = apply_action(
        state, Action(ActionType.ATTACK, Card(Rank.SIX, Suit.HEARTS))
    )
    state = apply_action(
        state,
        Action(
            ActionType.DEFEND,
            card=Card(Rank.SEVEN, Suit.HEARTS),
            target_index=0,
        ),
    )
    # Throw-in: attacker passes → bout ends successfully
    state = apply_action(state, Action(ActionType.PASS))
    assert Card(Rank.SIX, Suit.HEARTS) in state.discard
    assert Card(Rank.SEVEN, Suit.HEARTS) in state.discard
    assert state.attacker_index == 1
    assert state.defender_index == 0


def test_throw_in_rejects_wrong_rank():
    attacker = PlayerState(hand=[Card(Rank.NINE, Suit.CLUBS)])
    defender = PlayerState(hand=[])
    state = GameState(
        players=[attacker, defender],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[],
        table=[
            TablePair(
                attack=Card(Rank.SIX, Suit.HEARTS),
                defense=Card(Rank.SEVEN, Suit.HEARTS),
            )
        ],
        attacker_index=0,
        defender_index=1,
        phase=Phase.THROW_IN,
        active_player=0,
        max_attacks=6,
        defender_taking=True,
    )
    with pytest.raises(IllegalMoveError):
        apply_action(
            state, Action(ActionType.THROW_IN, Card(Rank.NINE, Suit.CLUBS))
        )


def test_max_six_attacks():
    attacker = PlayerState(
        hand=[Card(Rank(r), Suit.HEARTS) for r in range(6, 12)]  # 6..11
    )
    # After first attack of 6H, ranks on table grow; use same ranks via defenses
    # Simpler: set table already at 6 attacks and ensure no more throw-ins
    defender = PlayerState(hand=[Card(Rank.ACE, Suit.CLUBS)])
    table = [
        TablePair(attack=Card(Rank.SIX, Suit.CLUBS), defense=Card(Rank.SEVEN, Suit.CLUBS)),
        TablePair(attack=Card(Rank.SIX, Suit.DIAMONDS), defense=Card(Rank.EIGHT, Suit.CLUBS)),
        TablePair(attack=Card(Rank.SIX, Suit.SPADES), defense=Card(Rank.NINE, Suit.CLUBS)),
        TablePair(attack=Card(Rank.SEVEN, Suit.DIAMONDS), defense=Card(Rank.TEN, Suit.CLUBS)),
        TablePair(attack=Card(Rank.SEVEN, Suit.SPADES), defense=Card(Rank.JACK, Suit.CLUBS)),
        TablePair(attack=Card(Rank.EIGHT, Suit.DIAMONDS), defense=Card(Rank.QUEEN, Suit.CLUBS)),
    ]
    state = GameState(
        players=[attacker, defender],
        trump=Suit.HEARTS,
        trump_card=None,
        stock=[],
        table=table,
        attacker_index=0,
        defender_index=1,
        phase=Phase.THROW_IN,
        active_player=0,
        max_attacks=6,
    )
    acts = legal_actions(state)
    assert all(a.type != ActionType.THROW_IN for a in acts)
    assert any(a.type == ActionType.PASS for a in acts)


def test_fool_is_last_with_cards():
    p0 = PlayerState(hand=[], finished=True)
    p1 = PlayerState(hand=[Card(Rank.ACE, Suit.HEARTS)], finished=False)
    state = GameState(
        players=[p0, p1],
        trump=Suit.SPADES,
        trump_card=None,
        stock=[],
        table=[],
        attacker_index=1,
        defender_index=0,
        phase=Phase.ATTACK,
        active_player=1,
        winner_order=[0],
    )
    # Attack with last card then... simpler: empty stock, one player has cards, no table
    from durak_engine.rules import _check_game_over

    _check_game_over(state)
    assert state.phase == Phase.GAME_OVER
    assert state.fool == 1
