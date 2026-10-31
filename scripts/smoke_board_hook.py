"""Headed smoke: open guest Durak, join, sit, print __durakBoard state (no passwords)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playok_driver.actuator import join_first_table, sit_first_open_seat
from playok_driver.browser import BrowserConfig, launch_browser
from playok_driver.js_state import read_live_state
from playok_driver.parser import find_game_page, parse_page


def main() -> int:
    out = ROOT / "logs"
    out.mkdir(exist_ok=True)
    pw = context = page = None
    try:
        pw, context, page = launch_browser(
            BrowserConfig(
                user_data_dir=ROOT / "browser_profile",
                headless=False,
                slow_mo_ms=0,
            )
        )
        page = find_game_page(context) or page
        page.wait_for_timeout(2000)
        notes = getattr(context, "_durak_patch_notes", [])
        join_first_table(page)
        page.wait_for_timeout(2000)
        sit_first_open_seat(page)
        page.wait_for_timeout(4000)

        hook = page.evaluate(
            """() => ({
              hasBoard: !!window.__durakBoard,
              hasTab: !!window.__durakTab,
              P: window.__durakBoard ? window.__durakBoard.P.map(h => h.length) : null,
              Ja: window.__durakBoard ? window.__durakBoard.Ja.length : null,
              Qc: window.__durakBoard ? window.__durakBoard.Qc : null,
              Da: window.__durakBoard && window.__durakBoard.V ? window.__durakBoard.V.Da : null,
              active: window.__durakBoard ? window.__durakBoard.active : null
            })"""
        )
        live = read_live_state(page)
        parsed = parse_page(page)
        report = {
            "patch_notes": notes,
            "hook": hook,
            "live_ok": live.ok,
            "live_error": live.error,
            "seat": live.seat,
            "hand": [str(c) for c in live.hand],
            "table": [str(c) for c in live.table_attacks],
            "trump": str(live.trump) if live.trump else None,
            "trump_card": str(live.trump_card) if live.trump_card else None,
            "parse_ok": parsed.parse_ok,
            "state_source": parsed.state_source,
        }
        (out / "smoke_board_hook.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        # Success if board object is hooked (hand may be empty while waiting)
        return 0 if hook.get("hasBoard") else 2
    finally:
        if context is not None:
            context.close()
        if pw is not None:
            pw.stop()


if __name__ == "__main__":
    raise SystemExit(main())
