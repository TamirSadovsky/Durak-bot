"""Click actions on PlayOK with human-like timing jitter."""

from __future__ import annotations

import random
import time
from typing import Any, List

from durak_engine.actions import Action, ActionType
from durak_engine.cards import Card

from .parser import (
    BUTTON_DONE,
    BUTTON_PASS,
    BUTTON_TAKE,
    HAND_SELECTORS,
    JOIN_TABLE_SELECTORS,
    SEAT_SELECTORS,
    _attrs_card,
)


def _jitter_sleep(min_s: float = 0.15, max_s: float = 0.55) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _click_first_visible(page: Any, selectors: List[str], allow_disabled: bool = False) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if not loc.is_visible():
                continue
            if not allow_disabled and loc.is_disabled():
                continue
            _jitter_sleep()
            loc.click()
            return True
        except Exception:
            continue
    return False


def click_card_in_hand(page: Any, card: Card) -> bool:
    for sel in HAND_SELECTORS:
        try:
            locs = page.locator(sel)
            n = locs.count()
        except Exception:
            continue
        for i in range(n):
            el = locs.nth(i)
            parsed = _attrs_card(el)
            if parsed == card:
                _jitter_sleep()
                el.click()
                return True
    return False


def perform_action(page: Any, action: Action) -> bool:
    """Execute a chosen Action in the browser. Returns False on click failure."""
    if action.type in (ActionType.ATTACK, ActionType.DEFEND, ActionType.THROW_IN):
        if action.card is None:
            return False
        # DOM card nodes are usually absent (canvas). Fail closed.
        if click_card_in_hand(page, action.card):
            return True
        return False

    if action.type == ActionType.TAKE:
        return _click_first_visible(page, BUTTON_TAKE)

    if action.type == ActionType.PASS:
        if _click_first_visible(page, BUTTON_PASS):
            return True
        return _click_first_visible(page, BUTTON_DONE)

    if action.type == ActionType.DONE:
        return _click_first_visible(page, BUTTON_DONE)

    return False


def join_first_table(page: Any) -> bool:
    """Optional helper — default workflow is still manual join."""
    return _click_first_visible(page, JOIN_TABLE_SELECTORS)


def sit_first_open_seat(page: Any) -> bool:
    """Optional helper — default workflow is still manual sit."""
    for sel in SEAT_SELECTORS:
        try:
            locs = page.locator(sel)
            for i in range(locs.count()):
                el = locs.nth(i)
                if el.is_visible() and not el.is_disabled():
                    _jitter_sleep()
                    el.click()
                    return True
        except Exception:
            continue
    return False
