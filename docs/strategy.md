# Durak bot strategy (v1)

Phased heuristics plus seen-card memory. Not MCTS.

## Card value

```text
card_value = rank + (trump ? 20 : 0)
```

Ranks are 6–14 (Ace). Trumps are expensive so the bot prefers non-trump junk early.

## Phases

| Stock size | Phase    | Focus                                      |
|------------|----------|--------------------------------------------|
| `> 12`     | early    | Shed lowest non-trumps; save trumps        |
| `1–12`     | mid      | Count discards; take vs expensive defense  |
| `0`        | endgame  | Infer opponent hand; lead unbeatable cards |

## Attack

- Prefer lowest non-trump; if only trumps remain, lowest trump.
- Prefer opening a rank you hold as a pair/triple (shedding / throw-in setup).
- On continued attack, pass when the cheapest legal add is high for the phase (early: value≥10; mid: trump or value≥12).
- Endgame: if inferred defender hand cannot beat a lead, play that lead.

## Defend

- Among legal covers, pick minimum `card_value`.
- **Take vs trump-save:** if cheapest cover is a high trump (Jack+) against a low non-trump attack (≤8) and stock > 0 → `TAKE`.
- **Multi-trump cost:** if greedy trump cost to cover the whole table exceeds threshold → `TAKE`.

## Throw-in

- If defender is taking, or defender hand size ≤ 3 → dump legal junk (lowest non-trumps, else lowest legal).
- Otherwise throw lowest matching non-trumps that are not your sole card of that suit (keep suit covers).
- Pass when remaining adds are too expensive for the phase; endgame may continue with unbeatable adds.

## Memory (`SeenCards`)

Tracks:

- Discard / all seen plays
- Known trump and stock size
- Cards an opponent picked up on take

When stock is empty and a single opponent remains, unseen cards are treated as that opponent’s hand for unbeatable-lead detection.

## Out of scope (v1)

- MCTS / ISMCTS
- Full multi-player coalition throw-in modeling beyond legal rules
- Learning from logged PlayOK games
