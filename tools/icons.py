"""Draw the PWA icons with Pillow. Run once; the PNGs are committed.

    .venv/bin/python tools/icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "web" / "static"
PAPER, SLIP, INK, MUTED, RULE, DUE, DONE = "#f3eee2", "#fffdf7", "#2b2420", "#7d7266", "#e2d8c5", "#b23c17", "#6d7f63"


def draw(size: int, maskable: bool = False) -> Image.Image:
    s = size / 64  # the SVG grid
    scale = 4
    big = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    S = s * scale
    radius = 0 if maskable else 14 * S
    d.rounded_rectangle([0, 0, size * scale, size * scale], radius=radius, fill=PAPER)

    # the slip, slightly tilted like paper on a table
    slip = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    sd = ImageDraw.Draw(slip)
    inset = 6 if maskable else 0  # keep clear of the safe zone when the launcher masks the icon
    x0, y0, w, h = (15 + inset) * S, (12 + inset) * S, (34 - inset * 1.4) * S, (42 - inset * 1.4) * S
    sd.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=3 * S, fill=SLIP, outline=RULE, width=int(1.5 * S))
    sd.rounded_rectangle([x0, y0, x0 + 4 * S, y0 + h], radius=1.5 * S, fill=DUE)
    for i, (lw, col) in enumerate(((20, INK), (16, MUTED), (12, MUTED))):
        ly = y0 + (9 + 8 * i) * S
        sd.rounded_rectangle([x0 + 9 * S, ly, x0 + (9 + lw) * S, ly + 3 * S], radius=1.5 * S, fill=col)
    cy = y0 + h - 7 * S
    sd.line([(x0 + 10 * S, cy), (x0 + 13.5 * S, cy + 3.5 * S), (x0 + 20 * S, cy - 4 * S)],
            fill=DONE, width=int(3 * S), joint="curve")
    slip = slip.rotate(6, resample=Image.BICUBIC, center=(32 * S, 34 * S))
    big.alpha_composite(slip)

    # the due dot: the ping is the product
    r = 6 * S
    cx, cy = (49 - inset) * S, (15 + inset) * S
    d = ImageDraw.Draw(big)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DUE)
    return big.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    draw(192).save(OUT / "icon-192.png")
    draw(512).save(OUT / "icon-512.png")
    draw(180).save(OUT / "icon-180.png")
    draw(512, maskable=True).save(OUT / "icon-512-maskable.png")
    print("icons written to", OUT)
