"""Generate `tests/assets/dummy_logo.png` — a fake brand mark for tests.

Deliberately not the real logo: a coloured hexagon plus the word ACME, safe to
commit to a public repo. RGBA so the synthetic generator can alpha-composite it.

The mark carries deliberate *internal* detail — an off-centre eye, a slash, bars,
a chevron, a wordmark and a tagline. Flat silhouettes are useless for the SIFT
signal (phase03): almost all of their keypoints sit on the outline, whose
descriptors change with whatever background the logo is pasted on, and a
six-fold-symmetric shape makes Lowe's ratio test discard the few that remain.
Real logos have that kind of interior structure; the fake needs it too, or the
synthetic tests cannot exercise the signal at all. See D-018.

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

WIDTH, HEIGHT = 720, 240
SYMBOL_BGR = (40, 120, 240)   # orange-ish
TEXT_BGR = (90, 40, 20)       # dark navy
ACCENT_BGR = (60, 190, 120)   # green
PAPER_BGR = (250, 250, 250)   # near-white, for punched-out detail
TEXT = "ACME"
TAGLINE = "WIDGET WORKS"


def make_logo() -> np.ndarray:
    """Return the logo as an RGBA (BGRA) uint8 array on a transparent ground."""
    bgr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    alpha = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)

    # Symbol: filled hexagon, left of the wordmark.
    centre = (118, HEIGHT // 2)
    radius = 96
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

    # Interior detail — opaque, so these descriptors are the same whatever the
    # logo is pasted onto, and asymmetric, so the ratio test can tell them apart.
    cv2.circle(bgr, (centre[0] + 12, centre[1] - 12), 34, PAPER_BGR, -1)
    cv2.circle(bgr, (centre[0] + 12, centre[1] - 12), 14, ACCENT_BGR, -1)
    cv2.line(
        bgr, (centre[0] - 58, centre[1] + 52), (centre[0] + 58, centre[1] - 58),
        ACCENT_BGR, 10,
    )
    cv2.rectangle(
        bgr, (centre[0] + 26, centre[1] + 30), (centre[0] + 62, centre[1] + 56),
        PAPER_BGR, -1,
    )
    for i in range(4):
        cv2.line(
            bgr, (centre[0] - 62, centre[1] - 40 + i * 12),
            (centre[0] - 20, centre[1] - 40 + i * 12), PAPER_BGR, 4,
        )
    cv2.circle(bgr, (centre[0] - 40, centre[1] + 40), 12, PAPER_BGR, -1)
    cv2.circle(bgr, (centre[0] + 56, centre[1] - 56), 9, PAPER_BGR, -1)
    chevron = np.array(
        [
            [centre[0] - 30, centre[1] - 70],
            [centre[0] + 4, centre[1] - 52],
            [centre[0] - 26, centre[1] - 34],
        ],
        dtype=np.int32,
    )
    cv2.polylines(bgr, [chevron], False, PAPER_BGR, 5)
    cv2.circle(bgr, centre, radius - 4, ACCENT_BGR, 3)

    # Wordmark and tagline.
    font = cv2.FONT_HERSHEY_DUPLEX
    cv2.putText(bgr, TEXT, (250, 132), font, 2.9, TEXT_BGR, 7, cv2.LINE_AA)
    cv2.putText(alpha, TEXT, (250, 132), font, 2.9, 255, 7, cv2.LINE_AA)
    cv2.putText(bgr, TAGLINE, (252, 186), font, 1.0, TEXT_BGR, 3, cv2.LINE_AA)
    cv2.putText(alpha, TAGLINE, (252, 186), font, 1.0, 255, 3, cv2.LINE_AA)

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
