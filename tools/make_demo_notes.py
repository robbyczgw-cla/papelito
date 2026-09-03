"""Printable demo notes with exact German text. Do not use an image model."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "photos" / "demo"
BG = (246, 242, 230)
INK = (32, 30, 28)
RED = (176, 48, 36)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / name
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def slip(lines: list[tuple[str, bool]], filename: str, size: tuple[int, int] = (900, 720)) -> Path:
    im = Image.new("RGB", size, BG)
    d = ImageDraw.Draw(im)
    y = 48
    for text, bold in lines:
        font = _font(34 if bold else 26, bold=bold)
        d.text((48, y), text, font=font, fill=INK)
        y += 52 if bold else 44
    im = im.rotate(1.2, fillcolor=BG, expand=False)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / filename
    im.save(path, "PNG")
    return path


def main() -> None:
    a = slip(
        [
            ("Kindergarten Sonnenblume", True),
            ("Liebe Eltern,", False),
            ("am Mittwoch, 09.09.2026 findet unser", False),
            ("Ausflug in den Tiergarten statt.", False),
            ("Bitte geben Sie Ihrem Kind bis Montag,", False),
            ("07.09.2026 8 Euro in einem beschrifteten", False),
            ("Kuvert mit, an Fr. Huber.", False),
            ("Mit freundlichen Gruessen, das Team", False),
        ],
        "01-ausflug.png",
    )
    b = slip(
        [
            ("Kindergarten Sonnenblume", True),
            ("Liebe Eltern,", False),
            ("der Ausflug in den Tiergarten wurde auf", False),
            ("Freitag, 11.09.2026 verschoben.", False),
            ("Bitte Gummistiefel mitgeben.", False),
            ("Rueckmeldung bis morgen.", False),
            ("Das Team", False),
        ],
        "02-ausflug-nachtrag.png",
        (900, 620),
    )
    c = slip(
        [
            ("Kindergarten Sonnenblume", True),
            ("Liebe Eltern,", False),
            ("am Mittwoch, 17.09.2026 findet um 18:30 Uhr", False),
            ("unser Elternabend statt.", False),
            ("Bitte geben Sie bis Freitag, 12.09.2026", False),
            ("bekannt, ob Sie teilnehmen.", False),
            ("Am 24.09. ist der Kindergarten wegen", False),
            ("Fortbildung geschlossen.", False),
            ("Mit freundlichen Gruessen, das Team", False),
        ],
        "03-elternabend.png",
        (900, 760),
    )
    for p in (a, b, c):
        print(p)


if __name__ == "__main__":
    main()
