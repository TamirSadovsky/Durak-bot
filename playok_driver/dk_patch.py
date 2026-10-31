"""Patch PlayOK /j/dk.js so the live board/tab are exposed on window."""

from __future__ import annotations

# Unique anchors from current dk.js (PlayOK Durak client).
BOARD_CREATE_NEEDLE = "this.G=new b,this.G.sa(this)"
BOARD_CREATE_PATCH = (
    "this.G=new b,this.G.sa(this),"
    "window.__durakTab=this,window.__durakBoard=this.G,"
    "(this.G.xc&&(this.G.xc.__durakBoard=this.G))"
)

# Keep canvas reference even if create order differs slightly.
CANVAS_NEEDLE = 'this.xc=y(this.u,"canvas",{className:"noth"'
CANVAS_PATCH_PREFIX = (
    'this.xc=y(this.u,"canvas",{className:"noth"'
)


def patch_dk_js(source: str) -> tuple[str, list[str]]:
    """Return (patched_source, notes). Idempotent if already patched."""
    notes: list[str] = []
    out = source

    if "window.__durakBoard=this.G" in out:
        notes.append("board expose already present")
    elif BOARD_CREATE_NEEDLE in out:
        out = out.replace(BOARD_CREATE_NEEDLE, BOARD_CREATE_PATCH, 1)
        notes.append("patched board create → window.__durakBoard/__durakTab")
    else:
        notes.append("WARN: board create needle not found — state hook may fail")

    if "this.G.xc.__durakBoard" in out or "xc.__durakBoard=this" in out:
        notes.append("canvas board link ok/skip")
    elif CANVAS_NEEDLE in out and "window.__durakBoard=this.G" in out:
        # Board patch already sets xc.__durakBoard after sa(); optional extra not required.
        notes.append("canvas created inside Q.sa; board patch covers xc link")
    else:
        notes.append("canvas needle note: relying on board patch only")

    return out, notes
