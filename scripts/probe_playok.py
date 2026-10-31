"""One-shot PlayOK discovery (headed). Writes artifacts under logs/ (gitignored)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playok_driver.browser import BrowserConfig, launch_browser
from playok_driver.parser import parse_page


def main() -> int:
    out = ROOT / "logs"
    out.mkdir(exist_ok=True)
    profile = ROOT / "browser_profile"
    pw = context = page = None
    try:
        pw, context, page = launch_browser(
            BrowserConfig(user_data_dir=profile, headless=False, slow_mo_ms=0)
        )
        page.wait_for_timeout(4000)
        # Extra wait for SPA
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(2000)

        html = page.content()
        (out / "playok_probe.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(out / "playok_probe.png"), full_page=True)

        canvas_n = page.locator("canvas").count()
        iframes = page.locator("iframe").count()
        buttons = []
        for b in page.locator("button, a, [role='button']").all()[:80]:
            try:
                t = (b.inner_text() or "").strip()
                if t:
                    buttons.append(t[:80])
            except Exception:
                pass

        parsed = parse_page(page)
        report = {
            "url": page.url,
            "title": page.title(),
            "canvas_count": canvas_n,
            "iframe_count": iframes,
            "button_texts": buttons,
            "parse_ok": parsed.parse_ok,
            "hand": [str(c) for c in parsed.hand],
            "trump": str(parsed.trump) if parsed.trump else None,
            "stock_size": parsed.stock_size,
            "can_take": parsed.can_take,
            "can_pass": parsed.can_pass,
            "can_done": parsed.can_done,
            "matched_selectors": parsed.matched_selectors,
            "errors": parsed.parse_errors,
            "text_sample": parsed.raw_text_sample[:3000],
        }
        (out / "playok_probe.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if parsed.parse_ok else 2
    finally:
        if context is not None:
            context.close()
        if pw is not None:
            pw.stop()


if __name__ == "__main__":
    raise SystemExit(main())
