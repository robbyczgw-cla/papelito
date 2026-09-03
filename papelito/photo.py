"""Pre-vision photo quality gate: blur, glare/exposure, clipped text.

Dependencies: Pillow (see pyproject.toml). Stdlib + Pillow only; no numpy.
This module does not import an LLM client and does not open a network connection.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat

# Analysis is done on a downsampled grayscale copy so thresholds stay
# roughly scale-invariant for phone photos (2-12 Mpx) and tiny synthetics.
_ANALYZE_MAX_SIDE = 512

# 3x3 Laplacian. offset=128 keeps the signed response in 0–255 so Pillow
# does not clip negatives; variance is taken on the interior to skip the
# 1px convolution border.
_LAPLACIAN = ImageFilter.Kernel(
    (3, 3),
    (0, 1, 0, 1, -4, 1, 0, 1, 0),
    scale=1,
    offset=128,
)

# Interior Laplacian variance below this, with enough contrast to be
# content rather than a flat wash, counts as blur. Sharp synthetic notes
# land in the hundreds; GaussianBlur(radius=8) lands near 1.
_BLUR_VAR_MIN = 50.0
_CONTRAST_FOR_BLUR = 10.0

_DARK_MEAN = 40.0
_BRIGHT_MEAN = 238.0
_BRIGHT_STD_MAX = 16.0
_SAT_LEVEL = 250
_SAT_FRAC = 0.08

# Clipped text: letter strokes at the frame (gradient) or a dark blob
# covering a border (thumb). Smooth table around an inset note is not ink.
_CLIP_GRAD = 2.5
_CLIP_INK_FRAC = 0.10

# Suggest a recrop only when the bright paper island is clearly smaller
# than the frame (note sitting on a table).
_PAPER_AREA_MAX = 0.85

ImageLike = str | Path | bytes | bytearray | Image.Image


@dataclass(frozen=True)
class PhotoCheck:
    """Result of the pre-vision quality gate.

    recrop is a PIL box (left, top, right, bottom) in original pixels,
    right/bottom exclusive, or None when the frame is already tight.
    """

    ok: bool
    reasons: tuple[str, ...]
    recrop: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "recrop": list(self.recrop) if self.recrop is not None else None,
        }


def check_photo(image: ImageLike) -> PhotoCheck:
    """Return whether a kitchen-light phone photo is worth a vision call.

    reasons values, when present: ``blur``, ``glare``, ``exposure``,
    ``clipped-text``. ``ok`` is True only when the list is empty.
    """
    rgb = _as_rgb(image)
    orig_w, orig_h = rgb.size
    gray = _analysis_gray(rgb)

    stat = ImageStat.Stat(gray)
    mean = float(stat.mean[0])
    std = float(stat.stddev[0])
    sat_frac = _saturated_fraction(gray)
    lap_var = _laplacian_variance(gray)
    grad_max, ink_max = _border_metrics(gray)

    reasons: list[str] = []
    too_dark = mean <= _DARK_MEAN
    washed = mean >= _BRIGHT_MEAN and std <= _BRIGHT_STD_MAX
    if too_dark or washed:
        reasons.append("exposure")
    if sat_frac >= _SAT_FRAC:
        reasons.append("glare")
    if lap_var < _BLUR_VAR_MIN and std >= _CONTRAST_FOR_BLUR:
        reasons.append("blur")
    # One hot border is usually a sign above the slip or a magnet, not
    # missing words. Fail only when two or more edges look cut off.
    n_clip = _clipped_border_count(gray)
    if n_clip >= 2 or (n_clip == 1 and ink_max >= 0.35):
        reasons.append("clipped-text")

    recrop = _paper_recrop(gray, orig_w, orig_h)
    return PhotoCheck(ok=not reasons, reasons=tuple(reasons), recrop=recrop)


def _as_rgb(image: ImageLike) -> Image.Image:
    if isinstance(image, Image.Image):
        rgb = image.convert("RGB")
    elif isinstance(image, (bytes, bytearray)):
        with Image.open(io.BytesIO(image)) as im:
            rgb = im.convert("RGB")
    else:
        with Image.open(Path(image)) as im:
            rgb = im.convert("RGB")
    transposed = ImageOps.exif_transpose(rgb)
    return transposed if transposed is not None else rgb


def _analysis_gray(rgb: Image.Image) -> Image.Image:
    gray = rgb.convert("L")
    if max(gray.size) > _ANALYZE_MAX_SIDE:
        gray = gray.copy()
        gray.thumbnail((_ANALYZE_MAX_SIDE, _ANALYZE_MAX_SIDE), Image.Resampling.BILINEAR)
    return gray


def _laplacian_variance(gray: Image.Image) -> float:
    response = gray.filter(_LAPLACIAN)
    width, height = response.size
    pad = 2 if min(width, height) > 8 else 0
    if pad:
        response = response.crop((pad, pad, width - pad, height - pad))
    return float(ImageStat.Stat(response).var[0])


def _saturated_fraction(gray: Image.Image) -> float:
    hist = gray.histogram()
    total = gray.size[0] * gray.size[1]
    if total <= 0:
        return 0.0
    return sum(hist[_SAT_LEVEL:]) / total


def _border_width(gray: Image.Image) -> int:
    return max(4, min(gray.size) // 50)


def _border_strips(gray: Image.Image) -> tuple[tuple[float, float], ...]:
    """(gradient, ink fraction) for left, right, top, bottom strips."""
    pixels = gray.load()
    width, height = gray.size
    border = _border_width(gray)
    stat = ImageStat.Stat(gray)
    mean = float(stat.mean[0])
    std = float(stat.stddev[0])
    # No lower clamp: a dark table around an inset note must not count as ink.
    ink_thr = min(90.0, mean - 0.8 * std)

    def _strip(xs: range, ys: range, axis: str) -> tuple[float, float]:
        energy = 0
        dark = 0
        count = 0
        for y in ys:
            for x in xs:
                count += 1
                value = pixels[x, y]
                if value < ink_thr:
                    dark += 1
                if axis == "h" and x + 1 < width:
                    energy += abs(value - pixels[x + 1, y])
                elif axis == "v" and y + 1 < height:
                    energy += abs(value - pixels[x, y + 1])
        if count == 0:
            return 0.0, 0.0
        return energy / count, dark / count

    return (
        _strip(range(0, border), range(height), "h"),
        _strip(range(width - border, width), range(height), "h"),
        _strip(range(width), range(0, border), "v"),
        _strip(range(width), range(height - border, height), "v"),
    )


def _border_metrics(gray: Image.Image) -> tuple[float, float]:
    """Return (max border gradient, max border ink fraction)."""
    strips = _border_strips(gray)
    return max(s[0] for s in strips), max(s[1] for s in strips)


def _clipped_border_count(gray: Image.Image) -> int:
    """How many frame edges look like cut-off ink."""
    return sum(1 for g, ink in _border_strips(gray) if g >= _CLIP_GRAD or ink >= _CLIP_INK_FRAC)


def _paper_recrop(
    gray: Image.Image, orig_w: int, orig_h: int
) -> tuple[int, int, int, int] | None:
    stat = ImageStat.Stat(gray)
    std = float(stat.stddev[0])
    if std < 8.0:
        return None
    thr = float(stat.mean[0]) + 0.15 * std
    mask = gray.point(lambda p, t=thr: 255 if p >= t else 0)
    box = mask.getbbox()
    if box is None:
        return None
    gw, gh = gray.size
    sx = orig_w / gw
    sy = orig_h / gh
    pad = max(8, round(0.03 * max(orig_w, orig_h)))
    left = max(0, round(box[0] * sx) - pad)
    top = max(0, round(box[1] * sy) - pad)
    right = min(orig_w, round(box[2] * sx) + pad)
    bottom = min(orig_h, round(box[3] * sy) + pad)
    area = (right - left) * (bottom - top)
    if area <= 0 or area >= _PAPER_AREA_MAX * orig_w * orig_h:
        return None
    if right - left < 32 or bottom - top < 32:
        return None
    return (left, top, right, bottom)
