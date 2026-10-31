"""Click / commit actions on PlayOK with human-like timing jitter."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, List

from durak_engine.actions import Action, ActionType
from durak_engine.cards import Card

from .js_state import js_click_card_via_region, js_commit_take_or_pass, js_play_card
from .parser import (
    BUTTON_DONE,
    BUTTON_PASS,
    BUTTON_TAKE,
    HAND_SELECTORS,
    JOIN_TABLE_SELECTORS,
    SEAT_SELECTORS,
    _attrs_card,
)

logger = logging.getLogger("durak_bot.actuator")


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
    """DOM card nodes (rare) → dk.js select+commit → canvas region click."""
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

    _jitter_sleep(0.08, 0.25)
    try:
        result = js_play_card(page, card)
        if result and result.get("ok"):
            logger.debug("Played %s via dk.js commit: %s", card, result)
            return True
        logger.debug("dk.js play failed for %s: %s", card, result)
    except Exception as exc:
        logger.debug("dk.js play exception: %s", exc)

    try:
        result = js_click_card_via_region(page, card)
        if result and result.get("ok"):
            _jitter_sleep(0.1, 0.3)
            # After selecting via click, commit play
            commit = page.evaluate("() => window.__durakCommit(0)")
            return bool(commit and commit.get("ok"))
    except Exception as exc:
        logger.debug("region click failed: %s", exc)

    return False


def perform_action(page: Any, action: Action) -> bool:
    """Execute a chosen Action in the browser. Returns False on failure."""
    if action.type in (ActionType.ATTACK, ActionType.DEFEND, ActionType.THROW_IN):
        if action.card is None:
            return False
        return click_card_in_hand(page, action.card)

    if action.type == ActionType.TAKE:
        if _click_first_visible(page, BUTTON_TAKE):
            return True
        try:
            # Durak take uses Rc with empty selection (mode 0)
            r = js_commit_take_or_pass(page, as_pass=False)
            return bool(r and r.get("ok"))
        except Exception:
            return False

    if action.type == ActionType.PASS:
        if _click_first_visible(page, BUTTON_PASS):
            return True
        if _click_first_visible(page, BUTTON_DONE):
            return True
        try:
            r = js_commit_take_or_pass(page, as_pass=True)
            return bool(r and r.get("ok"))
        except Exception:
            return False

    if action.type == ActionType.DONE:
        if _click_first_visible(page, BUTTON_DONE):
            return True
        try:
            r = js_commit_take_or_pass(page, as_pass=True)
            return bool(r and r.get("ok"))
        except Exception:
            return False

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
