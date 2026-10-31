"""CLI: python -m durak_bot"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from playok_driver.browser import BrowserConfig, PLAYOK_DURAK_URL, launch_browser
from playok_driver.loop import BotLoop, LoopConfig
from playok_driver.parser import find_game_page, parse_page


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="durak_bot",
        description="PlayOK podkidnoy Durak bot (headed Playwright).",
    )
    p.add_argument(
        "--profile",
        type=Path,
        default=_repo_root() / "browser_profile",
        help="Persistent Chromium user-data dir (login once; gitignored).",
    )
    p.add_argument(
        "--url",
        default=PLAYOK_DURAK_URL,
        help="Start URL (default PlayOK Durak).",
    )
    p.add_argument(
        "--logs",
        type=Path,
        default=_repo_root() / "logs",
        help="Decision log directory (gitignored).",
    )
    p.add_argument(
        "--probe",
        action="store_true",
        help="Open browser, parse once, print mapping status, exit.",
    )
    p.add_argument(
        "--no-guest",
        action="store_true",
        help="Do not auto-call gstart guest client; leave landing page for manual login.",
    )
    p.add_argument(
        "--poll",
        type=float,
        default=1.0,
        help="Loop poll interval seconds.",
    )
    p.add_argument(
        "--max-parse-failures",
        type=int,
        default=5,
        help="Pause after this many consecutive parse failures.",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("durak_bot")

    cfg = BrowserConfig(
        user_data_dir=args.profile,
        headless=False,
        start_url=args.url,
        open_guest_client=not args.no_guest,
    )
    log.info("Launching headed browser with profile %s", cfg.user_data_dir)
    log.info(
        "If you need a full account: log in manually in this window once "
        "(persistent profile). Never put passwords in the repo or CLI."
    )
    log.info("Join a Durak table and sit yourself; the bot only plays once seated.")
    log.info(
        "Card state is read from patched dk.js (__durakBoard); canvas is display-only. "
        "Plays go through select+opcode 92 (DOM Take/Pass preferred when visible)."
    )

    pw = context = page = None
    try:
        pw, context, page = launch_browser(cfg)
        page = find_game_page(context) or page
        if args.probe:
            page.wait_for_timeout(1500)
            hook = page.evaluate(
                """() => ({
                  hasBoard: !!window.__durakBoard,
                  hasTab: !!window.__durakTab,
                  hasGetState: typeof window.__durakGetState === 'function',
                  patchNotes: window.__durakPatchNotes || null,
                  wsCount: (window.__durakMessages || []).length
                })"""
            )
            notes = getattr(context, "_durak_patch_notes", [])
            parsed = parse_page(page)
            print("=== PlayOK probe ===")
            print(f"url: {page.url}")
            print(f"dk_hook: {hook}")
            print(f"patch_notes: {notes}")
            print(f"parse_ok: {parsed.parse_ok}")
            print(f"state_source: {parsed.state_source}")
            print(f"in_game_shell: {parsed.in_game_shell}")
            print(f"board_active: {parsed.board_active} seat={parsed.our_seat}")
            print(f"seats: {parsed.seat_labels}")
            print(f"hand ({len(parsed.hand)}): {[str(c) for c in parsed.hand]}")
            print(
                f"table attacks: {[str(c) for c in parsed.table_attacks]} "
                f"defenses: {[str(c) if c else '-' for c in parsed.table_defenses]}"
            )
            print(f"trump: {parsed.trump} card={parsed.trump_card}")
            print(f"stock_size: {parsed.stock_size}")
            print(
                f"buttons take/pass/done: "
                f"{parsed.can_take}/{parsed.can_pass}/{parsed.can_done}"
            )
            print(f"matched_selectors: {parsed.matched_selectors}")
            print(f"errors: {parsed.parse_errors}")
            print("--- text sample ---")
            sample = parsed.raw_text_sample[:1500]
            print(sample.encode("ascii", "replace").decode("ascii"))
            print("Browser left open 15s for manual join/sit (re-probe state)...")
            page.wait_for_timeout(15_000)
            parsed2 = parse_page(page)
            print(
                f"after wait: source={parsed2.state_source} "
                f"hand={[str(c) for c in parsed2.hand]} "
                f"trump={parsed2.trump} active={parsed2.board_active}"
            )
            return 0 if (parsed.parse_ok or parsed.in_game_shell or hook.get("hasGetState")) else 2

        loop = BotLoop(
            page,
            LoopConfig(
                poll_interval_s=args.poll,
                decision_log_dir=args.logs,
                max_parse_failures=args.max_parse_failures,
            ),
        )
        log.info("Starting closed loop. Ctrl+C to quit.")
        loop.run_forever()
        return 0
    except KeyboardInterrupt:
        log.info("Interrupted — exiting.")
        return 0
    finally:
        if context is not None:
            context.close()
        if pw is not None:
            pw.stop()


if __name__ == "__main__":
    raise SystemExit(main())
