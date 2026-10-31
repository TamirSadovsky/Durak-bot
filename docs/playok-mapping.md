# PlayOK Durak — state mapping

Target: [https://www.playok.com/en/durak/](https://www.playok.com/en/durak/)  
Client: `/j/dk.js` via `gstart('dk', 0)`.

## Chosen method (v1.1): patched `dk.js` in-memory board

PlayOK paints the felt on **`canvas.noth`** (no DOM card nodes).  
The bot **does not OCR**. Instead Playwright **route-patches** `/j/dk.js` so that when a table view constructs the board it runs:

```js
window.__durakTab = this;
window.__durakBoard = this.G;
```

Helpers in `playok_driver/inject.js` then expose:

| API | Role |
|-----|------|
| `__durakGetState()` | Hand, table (`Ja`/`nc`), trump (`Qc`), seat (`V.Da`), hit-boxes (`Sa`) |
| `__durakSelectCard(rank,suit)` | Select a card in our hand (selection bit `\|4`) |
| `__durakCommit(mode)` | Send WebSocket JSON opcode **92** play / pass |
| `__durakClickRegion(seat,i)` | CSS hit-box center for mouse fallback |

`observe` (`parse_page`) merges this into `ParsedTable` with `state_source="dk_js"`.  
Card plays prefer **select + commit**; Take/Pass prefer visible `button.minw`, else opcode 92.

### Card codec

```text
code = rankIndex * 8 + suitIndex   // bit2 = selected; + 128*seat in P[]
rankIndex: 6..14 → 6,7,8,9,10,J,Q,K,A   (td[] in dk.js)
suitIndex: 0♥ 1♦ 2♣ 3♠
```

Implemented in `playok_driver/card_codec.py`.

### WebSocket

Messages are text JSON: `{"i":[ints...],"s":[strings...]}`.  
A WS hook logs traffic to `window.__durakMessages` (debug only).  
Inbound board updates use sub-opcodes on the table controller (`Ve`): 10 trump, 11 `Ja`, 12 `nc`, 13 hands, 14 turn mode.  
Outbound plays: `[92, tableId, 8, 0, ...cardCodes, timestamp]`.

## Auth / workflow

- Persistent `browser_profile/` (gitignored). **No passwords in repo/CLI.**
- Default: guest `gstart('dk',0)` (same as GUEST button).
- User **joins and sits manually** (optional helpers: `>>`, `button.butsit`).

## DOM still used

| Element | Selector |
|---------|----------|
| Join | `button:has-text(">>")` |
| Seats | `button.butsit` |
| Take / Pass / OK | `button.minw` with those labels |

## Take / Pass after a finished hand

PlayOK keeps **multiple** `button.minw` nodes across bouts; `.first` can hit a stale hidden Take.  
The bot now:

1. Clicks live `window.__durakTab.zb` (Take) / `.yb` (Pass) so the real `Rc` handler runs
2. Falls back to the **last** visible enabled `button.minw`
3. Treats uncovered table + our turn as **defense** even if Pass is also visible

Restart `python -m durak_bot` after pulling so `inject.js` reloads.

## Limits / gaps

1. Board exists only **after a table view is created** (patched `dk.js` must load in that window). If patch needle drifts after a PlayOK deploy, `dk_patch.py` needs a new anchor.
2. Stock size is not clearly exposed as a simple integer in the probed fields (`sc` is not treated as stock).
3. Multi-player throw-in beyond 2p is only as complete as the engine bridge.
4. Ban risk remains; human jitter is not stealth.
5. OCR path not implemented (unnecessary while the JS board hook works).

## Live verification (this machine)

```text
Date: 2026-10-31
Method: dk.js route patch + __durakGetState
Landing → gstart Durak window: canvas.noth present, lobby seats DOM
Patch notes: board create needle applied
Guest sit: Take/Pass/OK exist as button.minw (hidden until turn)
Hand while awaiting opponents: empty until deal (expected)
Codec/unit tests: encode/decode + patch idempotency
```

Re-check anytime:

```powershell
python -m durak_bot --probe
```
