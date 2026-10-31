"""Headed Playwright browser with persistent user-data dir (login once)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

PLAYOK_DURAK_URL = "https://www.playok.com/en/durak/"


@dataclass
class BrowserConfig:
    user_data_dir: Path
    headless: bool = False
    slow_mo_ms: int = 50
    start_url: str = PLAYOK_DURAK_URL
    channel: Optional[str] = None  # e.g. "chrome"
    open_guest_client: bool = True


def launch_browser(config: BrowserConfig) -> Tuple[Any, Any, Any]:
    """
    Launch persistent Chromium context.

    Returns (playwright, context, page) where page is the Durak client if
    guest open succeeded, otherwise the landing page.
    """
    from playwright.sync_api import sync_playwright

    config.user_data_dir.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    launch_kwargs = {
        "user_data_dir": str(config.user_data_dir),
        "headless": config.headless,
        "slow_mo": config.slow_mo_ms,
        "viewport": {"width": 1280, "height": 900},
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    if config.channel:
        launch_kwargs["channel"] = config.channel

    context = pw.chromium.launch_persistent_context(**launch_kwargs)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(config.start_url, wait_until="domcontentloaded")

    if config.open_guest_client:
        page = _try_open_durak_client(context, page)

    return pw, context, page


def _try_open_durak_client(context: Any, page: Any) -> Any:
    """
    Open the Durak multiplayer client the same way the GUEST button does:
    cookie kguest=1 + gstart('dk', 0). Does not submit passwords.
    If the user is already logged in via persistent profile, gstart still works.
    """
    try:
        page.wait_for_timeout(1500)
        with context.expect_page(timeout=8000) as pi:
            page.evaluate(
                """() => {
                  try { document.cookie = 'kguest=1;path=/'; } catch (e) {}
                  if (typeof gstart === 'function') { gstart('dk', 0); }
                }"""
            )
        game = pi.value
        game.wait_for_load_state("domcontentloaded")
        game.wait_for_timeout(2000)
        return game
    except Exception:
        # Login wall / gstart missing — leave landing page for manual login.
        return page
