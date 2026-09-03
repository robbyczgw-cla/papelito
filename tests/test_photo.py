"""Synthetic checks for papelito.photo.check_photo. No network, no LLM."""

from __future__ import annotations

import ast
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from papelito.photo import PhotoCheck, check_photo

REPO = Path(__file__).resolve().parents[1]
PHOTO_PY = REPO / "papelito" / "photo.py"


def _font(size: int) -> ImageFont.ImageFont:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _synthetic_note(
    size: tuple[int, int] = (600, 420),
    bg: tuple[int, int, int] = (246, 242, 230),
    ink: tuple[int, int, int] = (30, 30, 30),
    margin: int = 40,
) -> Image.Image:
    """High-contrast Kindergarten-note stand-in (cream paper, dark lines)."""
    width, height = size
    im = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(im)
    body = _font(22)
    title = _font(28)
    lines = (
        "Kindergarten Sonnenblume",
        "Liebe Eltern,",
        "am Mittwoch, 17.09.2026 findet um 18:30 Uhr",
        "unser Elternabend statt.",
        "Bitte geben Sie bis Freitag, 12.09.2026 bekannt,",
        "ob Sie teilnehmen.",
    )
    draw.text((margin, 24), lines[0], font=title, fill=ink)
    y = 80
    for line in lines[1:]:
        draw.text((margin, y), line, font=body, fill=ink)
        y += 48
    # Bars so the blur metric does not depend on a TrueType face.
    draw.rectangle((margin, y + 10, width - margin, y + 18), fill=ink)
    draw.rectangle((margin, y + 28, width - margin - 80, y + 36), fill=ink)
    return im


class TestCheckPhoto(unittest.TestCase):
    def test_sharp_high_contrast_note_ok(self) -> None:
        result = check_photo(_synthetic_note())
        self.assertIsInstance(result, PhotoCheck)
        self.assertTrue(result.ok)
        self.assertEqual(result.reasons, ())

    def test_heavily_blurred_not_ok_blur(self) -> None:
        blurred = _synthetic_note().filter(ImageFilter.GaussianBlur(radius=8))
        result = check_photo(blurred)
        self.assertFalse(result.ok)
        self.assertIn("blur", result.reasons)

    def test_near_white_washed_glare_or_exposure(self) -> None:
        washed = Image.new("RGB", (400, 300), (250, 250, 250))
        result = check_photo(washed)
        self.assertFalse(result.ok)
        self.assertTrue(
            "glare" in result.reasons or "exposure" in result.reasons,
            f"expected glare or exposure, got {result.reasons}",
        )

    def test_clipped_text_reason(self) -> None:
        im = Image.new("RGB", (400, 300), (246, 242, 230))
        draw = ImageDraw.Draw(im)
        font = _font(24)
        for y in range(0, 280, 28):
            draw.text((0, y), "Elternabend 17.09.2026 bitte Rueckmeldung", font=font, fill=(20, 20, 20))
        result = check_photo(im)
        self.assertFalse(result.ok)
        self.assertIn("clipped-text", result.reasons)

    def test_too_dark_exposure(self) -> None:
        dark = Image.new("RGB", (400, 300), (18, 16, 14))
        result = check_photo(dark)
        self.assertFalse(result.ok)
        self.assertIn("exposure", result.reasons)

    def test_flash_glare_hotspot(self) -> None:
        im = _synthetic_note()
        ImageDraw.Draw(im).ellipse((180, 80, 420, 280), fill=(255, 255, 255))
        result = check_photo(im)
        self.assertFalse(result.ok)
        self.assertIn("glare", result.reasons)

    def test_thumb_on_border_clipped_text(self) -> None:
        im = _synthetic_note()
        ImageDraw.Draw(im).ellipse((150, 300, 450, 500), fill=(50, 30, 25))
        result = check_photo(im)
        # A blob on one edge is a thumb. Still fail if that edge is mostly ink.
        self.assertFalse(result.ok)
        self.assertIn("clipped-text", result.reasons)

    def test_sign_above_the_slip_is_ok(self) -> None:
        """Kitchen wall: a header at the top of the frame, the slip fully in view."""
        im = Image.new("RGB", (600, 800), (230, 228, 222))
        ImageDraw.Draw(im).text((40, 4), "WICHTIG", font=_font(48), fill=(200, 30, 30))
        note = _synthetic_note((520, 380))
        im.paste(note, (40, 220))
        result = check_photo(im)
        self.assertTrue(result.ok, result.reasons)

    def test_note_on_table_ok_with_recrop(self) -> None:
        canvas = Image.new("RGB", (800, 600), (40, 38, 36))
        note = _synthetic_note((480, 340))
        canvas.paste(note, (160, 130))
        result = check_photo(canvas)
        self.assertTrue(result.ok, result.reasons)
        self.assertIsNotNone(result.recrop)
        left, top, right, bottom = result.recrop  # type: ignore[misc]
        # Padded around the pasted note at (160,130,640,470).
        self.assertLess(left, 160)
        self.assertLess(top, 130)
        self.assertGreater(right, 640)
        self.assertGreater(bottom, 470)
        self.assertLess(right - left, 800)
        self.assertLess(bottom - top, 600)

    def test_accepts_path_and_bytes(self) -> None:
        note = _synthetic_note()
        buf = io.BytesIO()
        note.save(buf, format="PNG")
        png = buf.getvalue()
        from_bytes = check_photo(png)
        self.assertTrue(from_bytes.ok, from_bytes.reasons)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.png"
            path.write_bytes(png)
            from_path = check_photo(path)
            from_str = check_photo(str(path))
        self.assertTrue(from_path.ok)
        self.assertTrue(from_str.ok)
        self.assertEqual(from_bytes.to_dict()["ok"], True)

    def test_module_has_no_network_or_llm_imports(self) -> None:
        tree = ast.parse(PHOTO_PY.read_text(encoding="utf-8"))
        banned = {
            "openai",
            "anthropic",
            "strands",
            "httpx",
            "requests",
            "urllib",
            "aiohttp",
            "httplib",
            "socket",
        }
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in banned:
                        found.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in banned:
                    found.add(node.module)
        self.assertFalse(found, f"photo.py must not import {found}")


if __name__ == "__main__":
    unittest.main()
