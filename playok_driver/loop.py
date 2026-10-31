"""Observe → legal actions → AI → click closed loop."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from durak_ai.memory import SeenCards
from durak_ai.policy import HeuristicPolicy
from durak_engine.actions import Action, ActionType
from durak_engine.rules import legal_actions

from .actuator import perform_action
from .parser import ParsedTable, parse_page
from .state_bridge import parsed_to_state

logger = logging.getLogger("durak_bot.loop")


@dataclass
class LoopConfig:
    poll_interval_s: float = 1.0
    decision_log_dir: Path = Path("logs")
    pause_on_parse_fail: bool = True
    max_parse_failures: int = 5
    our_index: int = 0


class BotLoop:
    def __init__(
        self,
        page: Any,
        config: Optional[LoopConfig] = None,
        policy: Optional[HeuristicPolicy] = None,
    ) -> None:
        self.page = page
        self.config = config or LoopConfig()
        self.memory = SeenCards()
        self.policy = policy or HeuristicPolicy(
            our_index=self.config.our_index, memory=self.memory
        )
        self.config.decision_log_dir.mkdir(parents=True, exist_ok=True)
        self._fail_streak = 0
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run_forever(self) -> None:
        logger.info("Bot loop started — join a table manually, then sit and wait.")
        while not self._stop:
            self.tick()
            time.sleep(self.config.poll_interval_s)

    def tick(self) -> Optional[Action]:
        parsed = parse_page(self.page)
        if not parsed.parse_ok:
            self._fail_streak += 1
            self._log_decision(
                {
                    "event": "parse_fail",
                    "errors": parsed.parse_errors,
                    "matched": parsed.matched_selectors,
                    "sample": parsed.raw_text_sample[:500],
                }
            )
            logger.warning(
                "Parse failure (%s/%s): %s",
                self._fail_streak,
                self.config.max_parse_failures,
                "; ".join(parsed.parse_errors),
            )
            if (
                self.config.pause_on_parse_fail
                and self._fail_streak >= self.config.max_parse_failures
            ):
                logger.error("Too many parse failures — pausing bot loop.")
                self._stop = True
            return None

        self._fail_streak = 0
        if not parsed.our_turn and not parsed.can_take and not parsed.can_pass:
            return None

        state = parsed_to_state(parsed, our_index=self.config.our_index)
        self.memory.observe_state(state, self.config.our_index)

        # Restrict legal actions to what UI suggests when possible
        actions = legal_actions(state)
        actions = _filter_by_ui(actions, parsed)
        if not actions:
            self._log_decision({"event": "no_legal", "phase": state.phase.name})
            return None

        action = self.policy.choose(state)
        # If policy picked something not in filtered list, fall back
        if action not in actions and not _action_match(action, actions):
            action = actions[0]

        ok = perform_action(self.page, action)
        self._log_decision(
            {
                "event": "act",
                "action": str(action),
                "ok": ok,
                "hand": [str(c) for c in parsed.hand],
                "trump": str(parsed.trump) if parsed.trump else None,
                "stock": parsed.stock_size,
            }
        )
        if not ok:
            logger.error("Click failed for %s — pausing.", action)
            if self.config.pause_on_parse_fail:
                self._stop = True
        return action

    def _log_decision(self, payload: dict) -> None:
        payload = {
            **payload,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        path = self.config.decision_log_dir / "decisions.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _filter_by_ui(actions, parsed: ParsedTable):
    out = []
    for a in actions:
        if a.type == ActionType.TAKE and not parsed.can_take:
            continue
        if a.type == ActionType.PASS and not (parsed.can_pass or parsed.can_done):
            continue
        if a.type == ActionType.DONE and not parsed.can_done:
            continue
        out.append(a)
    return out or actions


def _action_match(action: Action, actions) -> bool:
    for a in actions:
        if (
            a.type == action.type
            and a.card == action.card
            and a.target_index == action.target_index
        ):
            return True
    return False
