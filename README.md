# PlayOK Durak Bot

Local **Python 3 + Playwright** bot for [PlayOK Durak](https://www.playok.com/en/durak/).  
Rules: classic **podkidnoy (throw-in)** Durak. AI: **phased heuristics + seen-card memory** (not MCTS).

You start the bot on your PC, log in once in a persistent browser profile, **join a table yourself**, and the bot plays once seated.

> **Ban risk:** automating a real-money/skill site can get accounts restricted. You accept that risk. Timing jitter is not stealth.

## Packages

| Package | Role |
|---------|------|
| `durak_engine` | Cards, `GameState`, legal moves, apply |
| `durak_ai` | `SeenCards` + phased policy |
| `playok_driver` | Headed Playwright observe / click loop |
| `durak_bot` | CLI: `python -m durak_bot` |

Docs: [docs/strategy.md](docs/strategy.md), [docs/playok-mapping.md](docs/playok-mapping.md).

## Install (Windows)

```powershell
cd path\to\Durak-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
playwright install chromium
```

## First login (no passwords in git)

```powershell
python -m durak_bot --probe
```

1. A **headed** Chromium window opens with user data in `browser_profile/` (gitignored).
2. By default the bot opens the Durak client the same way **GUEST** does (`gstart`) — no password automation. For a real account, log in **manually once** in that profile (`--no-guest` on the landing page if you prefer).
3. Do **not** put passwords in `.env` commits, chat, or the repo.
4. Join a Durak table yourself and sit down.
5. Read `docs/playok-mapping.md`. Cards are **painted** on `canvas.noth`, but the bot reads them from a **patched `dk.js` board** (`window.__durakBoard`) and plays via select + WebSocket opcode 92 (DOM Take/Pass when visible).

## Run the bot

```powershell
python -m durak_bot
```

- Observe → legal actions → AI → click (with jitter).
- Parse / click failures pause the loop; see `logs/decisions.jsonl` (gitignored).
- `Ctrl+C` to quit.

Useful flags: `--profile`, `--logs`, `--poll`, `--max-parse-failures`, `-v`.

## Tests

```powershell
pytest -q
```

## Security

- `.gitignore` covers `.env`, `browser_profile/`, `logs/`, `screenshots/`.
- Never commit credentials or copy passwords from chat history into code.
