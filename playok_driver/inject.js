/**
 * Injected helpers for PlayOK Durak (dk.js).
 * Board reference is installed by patching dk.js (see dk_patch.py).
 */
(function () {
  if (window.__durakBotInjected) return;
  window.__durakBotInjected = true;
  window.__durakMessages = window.__durakMessages || [];

  function strip(v) {
    return (v & ~4) % 128;
  }

  function decode(v) {
    var code = strip(v);
    if (!code) return null;
    var rank = Math.floor(code / 8) % 16;
    var suit = code % 4;
    return { rank: rank, suit: suit, raw: code };
  }

  window.__durakGetState = function () {
    var G = window.__durakBoard;
    var tab = window.__durakTab;
    if (!G) {
      return { ok: false, error: "no __durakBoard (dk.js patch missing or game not open)" };
    }
    var seat = G.V && typeof G.V.Da === "number" ? G.V.Da : -1;
    var hands = [];
    for (var p = 0; p < (G.P || []).length; p++) {
      var cards = [];
      for (var i = 0; i < G.P[p].length; i++) {
        var d = decode(G.P[p][i]);
        if (d) cards.push(d);
      }
      hands.push(cards);
    }
    var tableAtk = [];
    var tableDef = [];
    for (var j = 0; j < (G.Ja || []).length; j++) {
      var a = decode(G.Ja[j]);
      if (a) tableAtk.push(a);
    }
    for (var n = 0; n < (G.nc || []).length; n++) {
      var defv = G.nc[n];
      if (defv === -1 || defv === undefined || defv === null) {
        tableDef.push(null);
      } else {
        tableDef.push(decode(defv));
      }
    }
    var trumpCard = null;
    if (typeof G.Qc === "number" && G.Qc >= 0) {
      trumpCard = decode(G.Qc);
    }
    var regions = [];
    if (G.Sa) {
      for (var r = 0; r < G.Sa.length; r++) {
        var s = G.Sa[r];
        regions.push({
          x: s.x,
          y: s.y,
          w: s.w,
          h: s.h,
          seat: s.Vb,
          index: s.Ub,
        });
      }
    }
    return {
      ok: true,
      seat: seat,
      active: !!G.active,
      hands: hands,
      tableAttacks: tableAtk,
      tableDefenses: tableDef,
      trumpCard: trumpCard,
      trumpSuit: trumpCard ? trumpCard.suit : null,
      stockHint: typeof G.sc === "number" ? G.sc : null,
      turnMode: tab && typeof tab.gb === "number" ? tab.gb : null,
      modeFlags: tab && typeof tab.ec === "number" ? tab.ec : null,
      selected: (G.L || []).map(decode).filter(Boolean),
      regions: regions,
      tableId: tab && typeof tab.O === "number" ? tab.O : null,
    };
  };

  function clearSelection(G) {
    G.L.length = 0;
    for (var p = 0; p < G.P.length; p++) {
      for (var i = 0; i < G.P[p].length; i++) {
        G.P[p][i] &= -5;
      }
    }
  }

  window.__durakSelectCard = function (rank, suit) {
    var G = window.__durakBoard;
    if (!G) return { ok: false, error: "no board" };
    var seat = G.V.Da;
    if (seat < 0) return { ok: false, error: "no seat" };
    clearSelection(G);
    var want = (rank * 8 + suit) | 0;
    for (var i = 0; i < G.P[seat].length; i++) {
      var raw = G.P[seat][i] & -5;
      if (strip(raw) === want) {
        G.P[seat][i] = raw | 4;
        G.L.push(G.P[seat][i]);
        try {
          if (typeof G.V.$c === "function") G.V.$c(true, G.L.length);
        } catch (e) {}
        return { ok: true, seat: seat, index: i, raw: strip(raw) };
      }
    }
    return { ok: false, error: "card not in hand", want: want, seat: seat };
  };

  window.__durakCommit = function (mode) {
    // mode: 0 = play selected / take-pass via Rc shape; 2 = pass/ok alternate
    var tab = window.__durakTab;
    var G = window.__durakBoard;
    if (!tab || !G) return { ok: false, error: "no tab/board" };
    var cards = [];
    for (var i = 0; i < G.L.length; i++) cards.push(G.L[i] & -5);
    try {
      if (typeof ld === "function") {
        /* may be minified local — fall through */
      }
    } catch (e) {}
    G.active = false;
    var ts = 0;
    try {
      ts = Math.floor((Date.now() - tab.lb.o) / 100);
    } catch (e2) {
      ts = 0;
    }
    var msg;
    if (mode === 2) {
      msg = [92, tab.O, 8, 2, ts];
    } else {
      msg = [92, tab.O, 8, 0].concat(cards).concat([ts]);
    }
    try {
      tab.send(msg, null);
      clearSelection(G);
      return { ok: true, sent: msg };
    } catch (err) {
      return { ok: false, error: String(err), sent: msg };
    }
  };

  window.__durakClickRegion = function (seat, index) {
    var G = window.__durakBoard;
    if (!G || !G.Sa || !G.u) return { ok: false, error: "no regions" };
    for (var i = 0; i < G.Sa.length; i++) {
      var s = G.Sa[i];
      if (s.Vb === seat && s.Ub === index) {
        var rect = G.u.getBoundingClientRect();
        return {
          ok: true,
          clientX: rect.left + s.x + s.w / 2,
          clientY: rect.top + s.y + s.h / 2,
          local: { x: s.x, y: s.y, w: s.w, h: s.h },
        };
      }
    }
    return { ok: false, error: "region not found", seat: seat, index: index };
  };
})();
