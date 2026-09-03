"""Generate `tests/assets/dummy_logo.png` — a fake brand mark for tests.

Deliberately not the real logo: a coloured hexagon plus the word ACME, safe to
commit to a public repo. RGBA so the synthetic generator can alpha-composite it.

Usage:
    python tools/make_dummy_logo.py [--out tests/assets/dummy_logo.png]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np

DEFAULT_OUT = Path("tests/assets/dummy_logo.png")

WIDTH, HEIGHT = 360, 120
SYMBOL_BGR = (40, 120, 240)   # orange-ish
TEXT_BGR = (90, 40, 20)       # dark navy
TEXT = "ACME"


def make_logo() -> np.ndarray:
    """Return the logo as an RGBA (BGRA) uint8 array on a transparent ground."""
    bgr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    alpha = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)

    # Symbol: filled hexagon with a punched-out centre, left of the wordmark.
    centre = (60, HEIGHT // 2)
    radius = 44
    hexagon = np.array(
        [
            [
                int(centre[0] + radius * math.cos(math.radians(60 * i - 30))),
                int(centre[1] + radius * math.sin(math.radians(60 * i - 30))),
            ]
            for i in range(6)
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(bgr, [hexagon], SYMBOL_BGR)
    cv2.fillPoly(alpha, [hexagon], 255)
    cv2.circle(bgr, centre, 16, (255, 255, 255), -1)
    cv2.circle(alpha, centre, 16, 0, -1)

    # Wordmark.
    font = cv2.FONT_HERSHEY_DUPLEX
    scale, thickness = 1.9, 4
    (text_w, text_h), _ = cv2.getTextSize(TEXT, font, scale, thickness)
    origin = (120, (HEIGHT + text_h) // 2)
    cv2.putText(bgr, TEXT, origin, font, scale, TEXT_BGR, thickness, cv2.LINE_AA)
    cv2.putText(alpha, TEXT, origin, font, scale, 255, thickness, cv2.LINE_AA)

    return np.dstack([bgr, alpha])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output PNG path")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    logo = make_logo()
    # imencode + tofile: imwrite cannot handle non-ASCII paths on Windows.
    ok, buf = cv2.imencode(".png", logo)
    if not ok:
        print("error: PNG encoding failed")
        return 1
    buf.tofile(str(out))
    print(f"wrote {out} ({logo.shape[1]}x{logo.shape[0]}, RGBA)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
