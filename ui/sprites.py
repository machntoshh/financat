"""Sprite do mascote, exatamente como desenhado no Aseprite (Sprite-0002.aseprite, 16x16).

Legenda: 'o' contorno preto | 'b' corpo azul-bebê | 'w' brilho branco |
         'e' olhos verde-limão | '.' transparente.
FRAME_CLOSED é o mesmo desenho com os olhos fechados (piscar e comemoração).
"""

SPRITE_SIZE = 16

FRAME_OPEN = (
    "................",
    "................",
    "...oo.....oo....",
    "...obo...obo....",
    "...obbooobbo....",
    "...owbbbbbwo....",
    "...obbebebbo....",
    "...obbbobbbo....",
    "..obbbobobbbo...",
    ".oobbbbbbbbboo..",
    ".obbbbwbwbbbbo..",
    ".obwbbwwwbbwbo..",
    "..oobbooobboo...",
    "....oo...oo.....",
    "................",
    "................",
)

FRAME_CLOSED = (
    "................",
    "................",
    "...oo.....oo....",
    "...obo...obo....",
    "...obbooobbo....",
    "...owbbbbbwo....",
    "...obbobobbo....",
    "...obbbobbbo....",
    "..obbbobobbbo...",
    ".oobbbbbbbbboo..",
    ".obbbbwbwbbbbo..",
    ".obwbbwwwbbwbo..",
    "..oobbooobboo...",
    "....oo...oo.....",
    "................",
    "................",
)

assert len(FRAME_OPEN) == SPRITE_SIZE and len(FRAME_CLOSED) == SPRITE_SIZE
assert all(len(r) == SPRITE_SIZE for r in FRAME_OPEN + FRAME_CLOSED)
