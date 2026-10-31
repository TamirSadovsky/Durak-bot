"""Legal action types for Durak."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .cards import Card


class ActionType(Enum):
    ATTACK = auto()
    DEFEND = auto()
    THROW_IN = auto()
    TAKE = auto()
    PASS = auto()  # attacker / thrower declines more throw-ins
    DONE = auto()  # defender finished; table clears (alias for round end after full defense)


@dataclass(frozen=True)
class Action:
    type: ActionType
    card: Optional[Card] = None
    # For DEFEND: which attack card on the table this covers (by index into open attacks)
    target_index: Optional[int] = None

    def __str__(self) -> str:
        if self.card is not None:
            extra = f"@{self.target_index}" if self.target_index is not None else ""
            return f"{self.type.name}:{self.card}{extra}"
        return self.type.name
