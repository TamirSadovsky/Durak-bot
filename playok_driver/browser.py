"""Headed Playwright browser with persistent user-data dir (login once)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from .dk_patch import patch_dk_js

PLAYOK_DURAK_URL = "https://www.playok.com/en/durak/"
_INJECT_JS = (Path(__file__).resolve().parent / "inject.js").read_text(encoding="utf-8")


@dataclass
class BrowserConfig:
    user_data_dir: Path
    headless: bool = False
    slow_mo_ms: int = 50
    start_url: str = PLAYOK_DURAK_URL
    channel: Optional[str] = None  # e.g. "chrome"
    open_guest_client: bool = True
    patch_dk_js: bool = True


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
    _install_hooks(context, patch=config.patch_dk_js)

    page = context.pages[0] if context.pages else context.new_page()
    page.goto(config.start_url, wait_until="domcontentloaded")

    if config.open_guest_client:
        page = _try_open_durak_client(context, page)

    _ensure_inject(page)
    return pw, context, page


def _install_hooks(context: Any, *, patch: bool) -> None:
    """Route-patch dk.js and add init scripts for helpers + WS logging."""
    context.add_init_script(_ws_hook_js())
    context.add_init_script(_INJECT_JS)

    if not patch:
        return

    def handle_dk(route: Any, request: Any) -> None:
        try:
            response = route.fetch()
            body = response.text()
            patched, notes = patch_dk_js(body)
            route.fulfill(
                status=response.status,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("content-encoding", "content-length")
                },
                body=patched,
            )
            # Stash notes on context for probe
            prev = getattr(context, "_durak_patch_notes", [])
            context._durak_patch_notes = list(prev) + notes  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - network
            try:
                route.continue_()
            except Exception:
                pass
            context._durak_patch_notes = [f"patch failed: {exc}"]  # type: ignore[attr-defined]

    context.route("**/j/dk.js*", handle_dk)


def _ws_hook_js() -> str:
    return r"""
(() => {
  if (window.__durakWSHooked) return;
  window.__durakWSHooked = true;
  window.__durakMessages = [];
  const Orig = window.WebSocket;
  function Wrap(url, protocols) {
    const ws = protocols !== undefined ? new Orig(url, protocols) : new Orig(url);
    window.__durakLastWS = ws;
    const push = (dir, data) => {
      try {
        const entry = { t: Date.now(), dir, data: typeof data === 'string' ? data : '[binary]' };
        window.__durakMessages.push(entry);
        if (window.__durakMessages.length > 400) window.__durakMessages.shift();
      } catch (e) {}
    };
    ws.addEventListener('message', (ev) => push('in', ev.data));
    const raw = ws.send.bind(ws);
    ws.send = function(data) { push('out', data); return raw(data); };
    return ws;
  }
  Wrap.prototype = Orig.prototype;
  Wrap.CONNECTING = Orig.CONNECTING;
  Wrap.OPEN = Orig.OPEN;
  Wrap.CLOSING = Orig.CLOSING;
  Wrap.CLOSED = Orig.CLOSED;
  window.WebSocket = Wrap;
})();
"""


def _ensure_inject(page: Any) -> None:
    try:
        page.evaluate(_INJECT_JS)
    except Exception:
        pass


def _try_open_durak_client(context: Any, page: Any) -> Any:
    """
    Open the Durak multiplayer client the same way the GUEST button does:
    cookie kguest=1 + gstart('dk', 0). Does not submit passwords.
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
        game.wait_for_timeout(2500)
        _ensure_inject(game)
        return game
    except Exception:
        return page
