# PlayOK Durak — DOM / state mapping

Target: [https://www.playok.com/en/durak/](https://www.playok.com/en/durak/)  
Client script: `/j/dk.js` (opens via `gstart('dk', 0)`).

## Auth model

- **No passwords in repo, env commits, or CLI args.**
- Browser uses a **persistent user-data dir** (`browser_profile/`, gitignored).
- Landing page GUEST button runs: `document.cookie='kguest=1;path=/'; gstart('dk',0);`
- The bot calls the same **without** reading any password. Logged-in sessions reuse the persistent profile cookies.
- User still **joins a table and sits manually** (helpers exist but are optional).

## Probe commands

```powershell
python -m durak_bot --probe
python scripts\probe_playok.py
```

## Confirmed (headed probe on Windows, 2026-10-31)

| Element | Status | How |
|---------|--------|-----|
| Landing page | DOM | Title `PlayOK - Play Durak Online Free` |
| Guest / login entry | DOM | `gstart('dk',0)` opens second window titled `Durak` |
| Lobby table list | DOM | Rows with `>>` join buttons |
| Seats | DOM | `button.butsit` (`#1`…`#n`) |
| Game felt / cards | **Canvas** | Single `canvas.noth` covering the table — **no DOM card nodes** |
| Take / Pass / OK | DOM (when dealt / your turn) | `button.minw` labels `take` / `pass` / `ok` (hidden until relevant) |
| Trump / stock / hand ranks | Not in accessible DOM text while seated waiting | Encoded inside `dk.js` / drawn on canvas (`Gc=["hearts","diamonds","clubs","spades"]`) |
| WebSocket | Present in `dk.js` | `WebSocket(c+"://"+host+":"+port+"/ws/")` — protocol not hooked in v1 |

### What works today

- Open headed Chromium with persistent profile.
- Auto-open Durak client as guest (or reuse login cookies).
- Detect game shell (canvas + seats).
- Click **Take / Pass / OK** when those `button.minw` controls are visible & enabled.
- Engine + AI closed loop offline with unit tests.

### Gaps (block full auto-play of card clicks)

1. **Hand and table cards are canvas-only** — `parse_page` cannot list `Card` objects from DOM while playing. Loop pauses on parse failure by design.
2. Closing the gap (pick one for v2): canvas OCR, recorded click-regions by hand index, or reverse-engineer `dk.js` in-memory state / WS messages.
3. Auto-join / multi-table farming remains out of scope.

### Selectors (code)

Defined in `playok_driver/parser.py`:

- Join: `button:has-text(">>")`
- Sit: `button.butsit`
- Take / Pass / OK: `button.minw:has-text('take'|'pass'|'ok')`
- Cards: candidate CSS list (expected empty on live PlayOK)

## Failure behavior

Repeated parse failures → bot **pauses**; decisions append to `logs/decisions.jsonl` (gitignored).

## Probe log (this machine)

```text
Date: 2026-10-31
Landing parse_ok: false (expected — no hand on marketing page)
After gstart: Durak window, canvas.noth=1, lobby tables visible
After join+sit: seat occupied, take/pass/ok present in DOM but not visible until turn
Card DOM nodes: none
Login wall: guest path works without password automation
```
