"""Read / act on PlayOK in-memory board exposed by the dk.js patch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from durak_engine.cards import Card, Suit

from .card_codec import INDEX_TO_RANK, SUITS, decode_raw, encode_card


@dataclass
class LiveBoardState:
    ok: bool
    error: str = ""
    seat: int = -1
    active: bool = False
    hand: List[Card] = field(default_factory=list)
    opponent_hands: List[List[Card]] = field(default_factory=list)
    table_attacks: List[Card] = field(default_factory=list)
    table_defenses: List[Optional[Card]] = field(default_factory=list)
    trump: Optional[Suit] = None
    trump_card: Optional[Card] = None
    stock_hint: Optional[int] = None
    turn_mode: Optional[int] = None  # tab.gb: 0 play, 1 ?, 2 take UI
    mode_flags: Optional[int] = None  # tab.ec — enables take/pass
    table_id: Optional[int] = None
    raw: dict = field(default_factory=dict)


def _card_from_js(obj: Optional[dict]) -> Optional[Card]:
    if not obj:
        return None
    rank_i = int(obj.get("rank", -1))
    suit_i = int(obj.get("suit", -1))
    rank = INDEX_TO_RANK.get(rank_i)
    if rank is None or suit_i < 0 or suit_i >= len(SUITS):
        return None
    return Card(rank, SUITS[suit_i])


def read_live_state(page: Any) -> LiveBoardState:
    try:
        raw = page.evaluate(
            """() => {
              if (typeof window.__durakGetState === 'function') return window.__durakGetState();
              return { ok: false, error: 'inject missing', hasBoard: !!window.__durakBoard };
            }"""
        )
    except Exception as exc:
        return LiveBoardState(ok=False, error=f"evaluate failed: {exc}")

    if not isinstance(raw, dict):
        return LiveBoardState(ok=False, error="bad state payload")
    if not raw.get("ok"):
        return LiveBoardState(
            ok=False,
            error=str(raw.get("error") or "not ok"),
            raw=raw,
        )

    seat = int(raw.get("seat", -1))
    hands_js = raw.get("hands") or []
    hand: List[Card] = []
    opponents: List[List[Card]] = []
    for p, cards in enumerate(hands_js):
        decoded = []
        for c in cards or []:
            card = _card_from_js(c)
            if card:
                decoded.append(card)
        if p == seat:
            hand = decoded
        else:
            opponents.append(decoded)

    attacks = [_card_from_js(c) for c in (raw.get("tableAttacks") or [])]
    attacks_f = [c for c in attacks if c]
    defenses_raw = raw.get("tableDefenses") or []
    defenses: List[Optional[Card]] = []
    for d in defenses_raw:
        defenses.append(_card_from_js(d) if d else None)
    while len(defenses) < len(attacks_f):
        defenses.append(None)

    trump_card = _card_from_js(raw.get("trumpCard"))
    trump = trump_card.suit if trump_card else None
    if trump is None and raw.get("trumpSuit") is not None:
        try:
            trump = SUITS[int(raw["trumpSuit"])]
        except Exception:
            trump = None

    return LiveBoardState(
        ok=True,
        seat=seat,
        active=bool(raw.get("active")),
        hand=hand,
        opponent_hands=opponents,
        table_attacks=attacks_f,
        table_defenses=defenses,
        trump=trump,
        trump_card=trump_card,
        stock_hint=raw.get("stockHint"),
        turn_mode=raw.get("turnMode"),
        mode_flags=raw.get("modeFlags"),
        table_id=raw.get("tableId"),
        raw=raw,
    )


def js_play_card(page: Any, card: Card) -> dict:
    """Select card in engine memory and commit opcode-92 play."""
    from .card_codec import RANK_TO_INDEX, SUIT_TO_INDEX

    rank_i = RANK_TO_INDEX[card.rank]
    suit_i = SUIT_TO_INDEX[card.suit]
    return page.evaluate(
        """({rank, suit}) => {
          const sel = window.__durakSelectCard(rank, suit);
          if (!sel || !sel.ok) return sel || {ok:false, error:'select failed'};
          return window.__durakCommit(0);
        }""",
        {"rank": rank_i, "suit": suit_i},
    )


def js_commit_take_or_pass(page: Any, *, as_pass: bool = False) -> dict:
    """Legacy opcode-92 fallback (prefer js_click_take / js_click_pass)."""
    mode = 2 if as_pass else 0
    return page.evaluate(
        """(mode) => {
          const G = window.__durakBoard;
          if (G) {
            G.L.length = 0;
            for (let p=0;p<G.P.length;p++) for (let i=0;i<G.P[p].length;i++) G.P[p][i]&=-5;
          }
          return window.__durakCommit(mode);
        }""",
        mode,
    )


def js_click_take(page: Any) -> dict:
    """Click live Take control (tab.zb) so PlayOK's own Rc handler runs."""
    return page.evaluate("() => window.__durakClickTake()")


def js_click_pass(page: Any) -> dict:
    """Click live Pass/OK control (tab.yb / Ad)."""
    return page.evaluate("() => window.__durakClickPass()")


def js_click_card_via_region(page: Any, card: Card) -> dict:
    """Fallback: mouse click at Sa hit-box center for the card in our hand."""
    from .card_codec import RANK_TO_INDEX, SUIT_TO_INDEX

    rank_i = RANK_TO_INDEX[card.rank]
    suit_i = SUIT_TO_INDEX[card.suit]
    info = page.evaluate(
        """({rank, suit}) => {
          const G = window.__durakBoard;
          if (!G) return {ok:false, error:'no board'};
          const seat = G.V.Da;
          let index = -1;
          const want = rank*8+suit;
          for (let i=0;i<G.P[seat].length;i++) {
            if (((G.P[seat][i]&~4)%128) === want) { index = i; break; }
          }
          if (index < 0) return {ok:false, error:'not in hand'};
          return window.__durakClickRegion(seat, index);
        }""",
        {"rank": rank_i, "suit": suit_i},
    )
    if not info or not info.get("ok"):
        return info or {"ok": False, "error": "region lookup failed"}
    page.mouse.click(info["clientX"], info["clientY"])
    return {"ok": True, "method": "mouse", **info}
