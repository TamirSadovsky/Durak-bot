"""Create GitHub PR via API using git credentials / GITHUB_TOKEN."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "TamirSadovsky/Durak-bot"
HEAD = "cursor/feat-playok-durak-bot-3e75"
BASE = "main"

BODY = """## Summary
- Podkidnoy Durak rules engine (`durak_engine`) with illegal-move rejection tests
- Seen-card memory + phased heuristic AI (`durak_ai`) including take-vs-trump-save and endgame unbeatable-lead tests
- Headed Playwright driver (`playok_driver`) with persistent profile, guest `gstart`, observe→AI→click loop
- Docs: `docs/strategy.md`, `docs/playok-mapping.md`; README handoff

## PlayOK mapping
- Lobby/seats/Take/Pass/OK are DOM (`button.butsit`, `button.minw`)
- **Cards are canvas-only** (`canvas.noth`) — full card auto-play blocked until OCR/JS hook; loop pauses on parse fail

## Test plan
- [x] `pytest -q` → 20 passed
- [x] `python -m durak_bot --probe` reaches Durak client shell
- [ ] User: log in once (optional), join table, sit, run bot

## Security
- No credentials committed; `browser_profile/`, `.env`, logs gitignored
"""


def token_from_gh() -> str | None:
    try:
        out = subprocess.check_output(
            ["gh", "auth", "token"], stderr=subprocess.DEVNULL, text=True
        )
        return out.strip() or None
    except Exception:
        return None


def token_from_env() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def token_from_git_credential() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        data = {}
        for line in proc.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k] = v
        return data.get("password")
    except Exception:
        return None


def main() -> int:
    token = token_from_env() or token_from_gh() or token_from_git_credential()
    if not token:
        print("No GitHub token available", file=sys.stderr)
        return 1

    payload = {
        "title": "PlayOK Durak bot: engine, phased AI, Playwright driver",
        "head": HEAD,
        "base": BASE,
        "body": BODY,
    }
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "durak-bot-scaffold",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(err, file=sys.stderr)
        # If PR already exists, try to find it
        if e.code == 422 and "already exists" in err.lower():
            pass
        return 1

    url = data.get("html_url")
    print(url)
    Path("logs").mkdir(exist_ok=True)
    Path("logs/pr_url.txt").write_text(url or "", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
