"""Podkidnoy Durak rules engine."""

from .cards import Card, Rank, Suit, deck_36
from .actions import Action, ActionType
from .state import GameState, PlayerState, TablePair
from .rules import (
    beats,
    legal_actions,
    apply_action,
    new_game,
    IllegalMoveError,
)

__all__ = [
    "Card",
    "Rank",
    "Suit",
    "deck_36",
    "Action",
    "ActionType",
    "GameState",
    "PlayerState",
    "TablePair",
    "beats",
    "legal_actions",
    "apply_action",
    "new_game",
    "IllegalMoveError",
]
