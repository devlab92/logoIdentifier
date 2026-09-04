"""Generate a synthetic labeled dataset for tests and pre-real-data benchmarks.

Backgrounds are procedural (solid / gradient / noise / shapes / text); positives
get `tests/assets/dummy_logo.png` pasted at a random scale, position, small
rotation and opacity. With `--with-text`, a share of the positives also carry
the first `BRAND_TERMS` entry rendered as readable text (varied font, size and
plaque colour) so the OCR signal can be exercised without company images.
Output layout mirrors `data/labeled/`:

    <out>/positive/pos_0001.png
    <out>/negative/neg_0001.png

Usage:
    python tools/make_synthetic.py --out .tmp_synth --count 50 --positive-ratio 0.5
    python tools/make_synthetic.py --out .tmp_synth --count 20 --with-text
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from logoscanner.config import BRAND_TERMS  # noqa: E402  (needs the path above)

DEFAULT_LOGO = Path("tests/assets/dummy_logo.png")
BRAND_FONTS = (
    cv2.FONT_HERSHEY_SIMPLEX,
    cv2.FONT_HERSHEY_DUPLEX,
    cv2.FONT_HERSHEY_TRIPLEX,
    cv2.FONT_HERSHEY_COMPLEX,
)
BACKGROUND_KINDS = ("solid", "gradient", "noise", "shapes", "text")
_WORDS = ("REPORT", "SUMMARY", "DATA", "FIGURE", "NOTES", "DRAFT", "TOTAL", "INDEX")


def _solid(rng, h, w):
    colour = rng.integers(0, 256, size=3)
    return np.full((h, w, 3), colour, dtype=np.uint8)


def _gradient(rng, h, w):
    start = rng.integers(0, 256, size=3).astype(np.float32)
    end = rng.integers(0, 256, size=3).astype(np.float32)
    ramp = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :, None]
    row = start[None, None, :] * (1 - ramp) + end[None, None, :] * ramp
    return np.repeat(row, h, axis=0).astype(np.uint8)


def _noise(rng, h, w):
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def _shapes(rng, h, w):
    image = _solid(rng, h, w)
    for _ in range(int(rng.integers(4, 12))):
        colour = tuple(int(c) for c in rng.integers(0, 256, size=3))
        if rng.random() < 0.5:
            p1 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
            p2 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
            cv2.rectangle(image, p1, p2, colour, -1)
        else:
            centre = (int(rng.integers(0, w)), int(rng.integers(0, h)))
            cv2.circle(image, centre, int(rng.integers(10, max(11, h // 4))), colour, -1)
    return image


def _text(rng, h, w):
    image = _solid(rng, h, w)
    for _ in range(int(rng.integers(3, 9))):
        word = _WORDS[int(rng.integers(0, len(_WORDS)))]
        origin = (int(rng.integers(0, max(1, w - 100))), int(rng.integers(20, h)))
        colour = tuple(int(c) for c in rng.integers(0, 256, size=3))
        cv2.putText(
            image, word, origin, cv2.FONT_HERSHEY_SIMPLEX,
            float(rng.uniform(0.6, 1.8)), colour, int(rng.integers(1, 4)), cv2.LINE_AA,
        )
    return image


_BACKGROUND_FUNCS = {
    "solid": _solid,
    "gradient": _gradient,
    "noise": _noise,
    "shapes": _shapes,
    "text": _text,
}


def make_background(rng, height: int, width: int) -> np.ndarray:
    kind = BACKGROUND_KINDS[int(rng.integers(0, len(BACKGROUND_KINDS)))]
    return _BACKGROUND_FUNCS[kind](rng, height, width)


def _rotate_rgba(logo: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate an RGBA patch about its centre, expanding the canvas to fit."""
    h, w = logo.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w, new_h = int(h * sin + w * cos), int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - w / 2
    matrix[1, 2] += new_h / 2 - h / 2
    return cv2.warpAffine(
        logo, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
    )


def paste_logo(rng, background: np.ndarray, logo: np.ndarray) -> np.ndarray:
    """Alpha-composite `logo` (BGRA) onto a copy of `background` at random pose."""
    bg_h, bg_w = background.shape[:2]
    scale = float(rng.uniform(0.3, 1.5))
    # Keep the mark inside the frame even at the largest scale.
    fit = min(1.0, (bg_w * 0.9) / (logo.shape[1] * scale), (bg_h * 0.9) / (logo.shape[0] * scale))
    scale *= fit
    resized = cv2.resize(
        logo, (max(1, int(logo.shape[1] * scale)), max(1, int(logo.shape[0] * scale))),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
    )
    patch = _rotate_rgba(resized, float(rng.uniform(-10, 10)))

    p_h, p_w = patch.shape[:2]
    x = int(rng.integers(0, max(1, bg_w - p_w + 1)))
    y = int(rng.integers(0, max(1, bg_h - p_h + 1)))
    p_h, p_w = min(p_h, bg_h - y), min(p_w, bg_w - x)
    patch = patch[:p_h, :p_w]

    opacity = float(rng.uniform(0.6, 1.0))
    alpha = (patch[:, :, 3:4].astype(np.float32) / 255.0) * opacity
    region = background[y : y + p_h, x : x + p_w].astype(np.float32)
    blended = patch[:, :, :3].astype(np.float32) * alpha + region * (1 - alpha)

    out = background.copy()
    out[y : y + p_h, x : x + p_w] = blended.astype(np.uint8)
    return out


def draw_brand_text(rng, image: np.ndarray, term: str | None = None) -> np.ndarray:
    """Stamp the brand term onto a contrasting plaque so OCR can read it.

    The plaque (light box, dark glyphs, or the inverse) stands in for the flat,
    high-contrast lockups the real logo appears in; without it, text landing on
    procedural noise is unreadable and the synthetic set would test nothing.
    """
    term = (term or (BRAND_TERMS[0] if BRAND_TERMS else "BRAND")).strip()
    height, width = image.shape[:2]
    font = BRAND_FONTS[int(rng.integers(0, len(BRAND_FONTS)))]
    thickness = int(rng.integers(2, 4))

    scale = float(rng.uniform(0.8, 2.4))
    (text_w, text_h), baseline = cv2.getTextSize(term, font, scale, thickness)
    # Shrink until the plaque fits, so small canvases still get legible text.
    while (text_w + 24 > width or text_h + baseline + 24 > height) and scale > 0.4:
        scale *= 0.8
        (text_w, text_h), baseline = cv2.getTextSize(term, font, scale, thickness)

    pad = max(6, int(text_h * 0.35))
    box_w, box_h = text_w + 2 * pad, text_h + baseline + 2 * pad
    x = int(rng.integers(0, max(1, width - box_w + 1)))
    y = int(rng.integers(0, max(1, height - box_h + 1)))

    dark = bool(rng.random() < 0.5)
    plate = tuple(int(c) for c in rng.integers(0, 46, size=3)) if dark else tuple(
        int(c) for c in rng.integers(210, 256, size=3)
    )
    ink = (235, 235, 235) if dark else (20, 20, 20)

    out = image.copy()
    cv2.rectangle(out, (x, y), (x + box_w, y + box_h), plate, -1)
    cv2.putText(
        out, term, (x + pad, y + pad + text_h), font, scale, ink, thickness, cv2.LINE_AA
    )
    return out


def _write(image: np.ndarray, path: Path) -> None:
    ok, buf = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"failed to encode {path}")
    buf.tofile(str(path))


def generate(
    out_dir: str | Path,
    count: int,
    positive_ratio: float = 0.5,
    logo_path: str | Path = DEFAULT_LOGO,
    size: tuple[int, int] = (600, 800),
    seed: int | None = None,
    text_ratio: float = 0.0,
) -> dict[str, int]:
    """Write `count` images split by `positive_ratio`. Returns per-class counts.

    `text_ratio` is the share of positives that additionally carry the brand
    name as readable text (0 = none, 1 = all).
    """
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    pos_dir, neg_dir = out_dir / "positive", out_dir / "negative"
    pos_dir.mkdir(parents=True, exist_ok=True)
    neg_dir.mkdir(parents=True, exist_ok=True)

    n_positive = int(round(count * positive_ratio))
    n_negative = count - n_positive

    logo = None
    if n_positive:
        logo_path = Path(logo_path)
        if not logo_path.is_file():
            raise FileNotFoundError(
                f"{logo_path} missing — run `python tools/make_dummy_logo.py` first"
            )
        buf = np.fromfile(str(logo_path), dtype=np.uint8)
        logo = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        if logo is None or logo.shape[2] != 4:
            raise ValueError(f"{logo_path} is not a readable RGBA image")

    height, width = size
    n_text = int(round(n_positive * max(0.0, min(1.0, text_ratio))))
    for index in range(n_positive):
        image = paste_logo(rng, make_background(rng, height, width), logo)
        if index < n_text:
            image = draw_brand_text(rng, image)
        _write(image, pos_dir / f"pos_{index + 1:04d}.png")
    for index in range(n_negative):
        _write(make_background(rng, height, width), neg_dir / f"neg_{index + 1:04d}.png")

    return {"positive": n_positive, "negative": n_negative}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="output folder")
    parser.add_argument("--count", type=int, default=50, help="total images")
    parser.add_argument("--positive-ratio", type=float, default=0.5, help="0..1")
    parser.add_argument("--logo", default=str(DEFAULT_LOGO), help="RGBA logo to paste")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--with-text",
        dest="text_ratio",
        type=float,
        nargs="?",
        const=0.6,
        default=0.0,
        help="share of positives that also carry the brand name as text (bare flag: 0.6)",
    )
    args = parser.parse_args(argv)

    if not 0.0 <= args.positive_ratio <= 1.0:
        print("error: --positive-ratio must be between 0 and 1")
        return 2

    counts = generate(
        args.out, args.count, args.positive_ratio, args.logo,
        size=(args.height, args.width), seed=args.seed, text_ratio=args.text_ratio,
    )
    print(f"wrote {counts['positive']} positive + {counts['negative']} negative -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
