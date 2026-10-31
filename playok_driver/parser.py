"""Parse PlayOK Durak DOM into a structured snapshot.

PlayOK Durak (dk.js) renders the **table/hand on a full-size canvas**
(`canvas.noth`). Take / Pass / OK are real DOM `button.minw` controls that
appear when it is your turn. Lobby seats use `button.butsit`.

See docs/playok-mapping.md for discovery notes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set

from durak_engine.cards import Card, Suit


@dataclass
class ParsedTable:
    hand: List[Card] = field(default_factory=list)
    table_attacks: List[Card] = field(default_factory=list)
    table_defenses: List[Optional[Card]] = field(default_factory=list)
    trump: Optional[Suit] = None
    trump_card: Optional[Card] = None
    stock_size: Optional[int] = None
    our_turn: bool = False
    can_take: bool = False
    can_pass: bool = False
    can_done: bool = False
    defender_taking: bool = False
    seat_labels: List[str] = field(default_factory=list)
    raw_text_sample: str = ""
    parse_ok: bool = False
    parse_errors: List[str] = field(default_factory=list)
    matched_selectors: List[str] = field(default_factory=list)
    canvas_only_cards: bool = False
    in_game_shell: bool = False


# Lobby / shell
SEAT_SELECTORS = ["button.butsit", "button.butsys.butsit"]
JOIN_TABLE_SELECTORS = ['button:has-text(">>")']

# Candidate card DOM selectors (usually empty — cards are canvas-drawn)
HAND_SELECTORS = [
    "[data-hand] .card",
    ".hand .card",
    "#hand .card",
    ".mycards .card",
    ".cards-hand img",
    "[class*='hand'] [class*='card']",
]
TABLE_SELECTORS = [
    ".table .card",
    "#table .card",
    ".battlefield .card",
    "[class*='table'] [class*='card']",
]

# Confirmed in dk.js / live probe: button.minw with localized labels
BUTTON_TAKE = [
    "button.minw:has-text('take')",
    "button.minw:has-text('Take')",
    "button.minw:has-text('Взять')",
    "text=take",
    "text=Take",
    "text=Взять",
]
BUTTON_PASS = [
    "button.minw:has-text('pass')",
    "button.minw:has-text('Pass')",
    "button.minw:has-text('Пас')",
    "text=pass",
    "text=Pass",
    "text=Пас",
]
BUTTON_DONE = [
    "button.minw:has-text('ok')",
    "button.minw:has-text('OK')",
    "button.minw:has-text('Done')",
    "text=ok",
    "text=OK",
    "text=Done",
]
TRUMP_SELECTORS = [".trump", "#trump", "[class*='trump']"]

_CARD_RE = re.compile(
    r"\b([6-9]|10|[TJQKA])\s*([HDCS♥♦♣♠])\b",
    re.IGNORECASE,
)
_CARD_ALT_RE = re.compile(
    r"\b([HDCS])([6-9]|10|[TJQKA])\b",
    re.IGNORECASE,
)

SUIT_WORDS = {
    "HEARTS": Suit.HEARTS,
    "DIAMONDS": Suit.DIAMONDS,
    "CLUBS": Suit.CLUBS,
    "SPADES": Suit.SPADES,
    "H": Suit.HEARTS,
    "D": Suit.DIAMONDS,
    "C": Suit.CLUBS,
    "S": Suit.SPADES,
    "♥": Suit.HEARTS,
    "♦": Suit.DIAMONDS,
    "♣": Suit.CLUBS,
    "♠": Suit.SPADES,
}


def parse_card_token(token: str) -> Optional[Card]:
    token = token.strip()
    try:
        return Card.parse(token)
    except ValueError:
        pass
    m = _CARD_RE.search(token)
    if m:
        try:
            return Card.parse(m.group(1) + m.group(2))
        except ValueError:
            return None
    m = _CARD_ALT_RE.search(token)
    if m:
        try:
            return Card.parse(m.group(2) + m.group(1))
        except ValueError:
            return None
    return None


def _attrs_card(el: Any) -> Optional[Card]:
    for attr in ("data-card", "data-code", "alt", "title", "aria-label", "src"):
        try:
            val = el.get_attribute(attr)
        except Exception:
            val = None
        if not val:
            continue
        for part in re.split(r"[/_.\-?\s]+", val):
            c = parse_card_token(part)
            if c:
                return c
        c = parse_card_token(val)
        if c:
            return c
    try:
        text = (el.inner_text() or "").strip()
    except Exception:
        text = ""
    return parse_card_token(text) if text else None


def _query_cards(page: Any, selectors: List[str], matched: List[str]) -> List[Card]:
    cards: List[Card] = []
    for sel in selectors:
        try:
            locs = page.locator(sel)
            n = locs.count()
        except Exception:
            continue
        if n <= 0:
            continue
        matched.append(sel)
        for i in range(n):
            el = locs.nth(i)
            c = _attrs_card(el)
            if c and c not in cards:
                cards.append(c)
        if cards:
            break
    return cards


def _button_enabled_visible(page: Any, selectors: List[str], matched: List[str]) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() < 0:
                continue
            if loc.is_visible() and not loc.is_disabled():
                matched.append(sel)
                return True
        except Exception:
            continue
    return False


def find_game_page(context: Any) -> Any:
    """Prefer the Durak game popup created by gstart('dk', 0)."""
    pages = list(context.pages)
    for p in reversed(pages):
        try:
            title = (p.title() or "").lower()
            if title == "durak" or "playok.com" in (p.url or ""):
                if p.locator("canvas.noth").count() or p.locator("button.butsit").count():
                    return p
        except Exception:
            continue
    return pages[-1] if pages else None


def parse_page(page: Any) -> ParsedTable:
    """Best-effort DOM parse of lobby / in-game shell."""
    result = ParsedTable()
    matched: List[str] = []

    try:
        body_text = page.locator("body").inner_text(timeout=2000)
    except Exception as exc:
        result.parse_errors.append(f"body text failed: {exc}")
        body_text = ""
    result.raw_text_sample = body_text[:2000]
    low = body_text.lower()

    if "log in" in low or "password" in low:
        if "awaiting opponent" not in low and "table #" not in low:
            result.parse_errors.append(
                "Possible login/landing wall — use persistent profile and log in "
                "or open guest via gstart; do not automate passwords."
            )

    try:
        canvas_n = page.locator("canvas").count()
        canvas_noth = page.locator("canvas.noth").count()
    except Exception:
        canvas_n = canvas_noth = 0

    try:
        seats = page.locator("button.butsit")
        for i in range(min(seats.count(), 8)):
            result.seat_labels.append((seats.nth(i).inner_text() or "").strip())
        if result.seat_labels:
            matched.append("button.butsit")
            result.in_game_shell = True
    except Exception:
        pass

    if canvas_noth or "table #" in low or result.seat_labels:
        result.in_game_shell = True

    result.hand = _query_cards(page, HAND_SELECTORS, matched)
    table_cards = _query_cards(page, TABLE_SELECTORS, matched)
    for i, c in enumerate(table_cards):
        if i % 2 == 0:
            result.table_attacks.append(c)
        else:
            result.table_defenses.append(c)
    while len(result.table_defenses) < len(result.table_attacks):
        result.table_defenses.append(None)

    trump_m = re.search(
        r"trump[:\s]+([HDCS♥♦♣♠]|hearts|diamonds|clubs|spades)",
        body_text,
        re.IGNORECASE,
    )
    if trump_m:
        result.trump = SUIT_WORDS.get(trump_m.group(1).upper())

    for sel in TRUMP_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                matched.append(sel)
                c = _attrs_card(loc)
                if c:
                    result.trump_card = c
                    result.trump = c.suit
                break
        except Exception:
            continue

    stock_m = re.search(
        r"\b(?:stock|deck)\s*[:#]?\s*(\d{1,2})\b",
        body_text,
        re.IGNORECASE,
    )
    if stock_m:
        result.stock_size = int(stock_m.group(1))

    # Prefer confirmed minw controls; avoid bare text=ok false positives in lobby chrome
    result.can_take = _button_enabled_visible(
        page, [s for s in BUTTON_TAKE if "minw" in s], matched
    ) or _button_enabled_visible(page, BUTTON_TAKE, matched)
    result.can_pass = _button_enabled_visible(
        page, [s for s in BUTTON_PASS if "minw" in s], matched
    ) or _button_enabled_visible(page, BUTTON_PASS, matched)
    result.can_done = _button_enabled_visible(
        page, [s for s in BUTTON_DONE if "minw" in s], matched
    )
    result.our_turn = result.can_take or result.can_pass or result.can_done
    result.matched_selectors = matched

    if canvas_n and not result.hand:
        result.canvas_only_cards = True
        result.parse_errors.append(
            f"Found {canvas_n} canvas element(s) (PlayOK uses canvas.noth for the "
            "felt). Hand/table cards are not in the DOM — card identity requires "
            "canvas OCR, coordinate maps, or a JS hook into dk.js state."
        )

    if result.hand:
        result.parse_ok = True
        if result.trump is None:
            result.parse_errors.append("Hand found but trump not parsed.")
    elif result.our_turn and result.in_game_shell:
        # Can act on take/pass without card parse (e.g. only PASS available)
        result.parse_ok = False
        result.parse_errors.append(
            "Take/Pass/OK visible but hand cards not readable from DOM."
        )
    elif result.in_game_shell:
        result.parse_errors.append(
            "In PlayOK game shell (lobby/table) but no DOM hand — sit and wait "
            "for a deal; card moves still need canvas mapping."
        )
    else:
        result.parse_errors.append(
            "Not in game shell. Open Durak via guest/login (gstart), join a table, sit."
        )

    return result


def cards_mentioned_in_text(text: str) -> Set[Card]:
    found: Set[Card] = set()
    for m in _CARD_RE.finditer(text):
        c = parse_card_token(m.group(1) + m.group(2))
        if c:
            found.add(c)
    return found
