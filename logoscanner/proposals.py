"""Candidate regions to compare against the logo, cut out of one image.

Why this stage exists: an embedding of a whole 1600x900 photo is dominated by
whatever fills the frame - a rack, a person, a slide background. A logo
occupying 2% of the pixels barely moves that vector, so a whole-image cosine
against the logo variants is close to noise. Cropping first restores the
signal: one of these boxes contains mostly logo, and *that* crop embeds close
to the template.

Sources, in the priority order the budget is spent in:

1. **OCR line boxes** - the strongest hint available. A stylised wordmark that
   fuzzy-matches no brand term is still *text* to the detector: on the labeled
   set the ZPE wordmark came back as a two-character garble at 0.54 confidence.
   The characters are wrong, the box is right.
2. **SIFT's projected quad** - when keypoints verified a homography that the
   signal's own threshold then rejected, the location is still worth a look.
3. **MSER stable regions** - a mark on a flat background is the blob detector's
   home ground, and it needs neither text nor keypoints.
4. **Tiles + the full frame** - a coarse 3x3 grid, always included, so an image
   where every other source came up empty still gets looked at.

Everything is padded, area-filtered and merged, because near-duplicate crops
cost embedding time and buy nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from logoscanner import config
from logoscanner.signals import BBox

# Lower sorts first when the region budget is spent.
SOURCE_PRIORITY = {"text": 0, "sift": 1, "mser": 2, "tile": 3, "full": 4}


@dataclass(frozen=True)
class Region:
    """One candidate box and where the idea came from."""

    bbox: BBox  # x, y, w, h in pixels of the image passed to `propose`
    source: str

    @property
    def area(self) -> int:
        return max(0, self.bbox[2]) * max(0, self.bbox[3])


def clip_box(bbox: BBox, shape) -> BBox | None:
    """Clamp a box to the image; None if nothing survives."""
    height, width = shape[:2]
    x, y, w, h = (int(round(v)) for v in bbox)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + max(0, w)), min(height, y + max(0, h))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1 - x0, y1 - y0


def pad_box(bbox: BBox, shape, frac: float | None = None) -> BBox | None:
    """Grow a box by `frac` of its own size, clipped to the image.

    A text box is drawn tight around the glyphs, so the symbol beside the words
    - the part that actually distinguishes this brand - falls outside it.
    """
    frac = config.PROPOSAL_PAD_FRAC if frac is None else frac
    x, y, w, h = bbox
    dx, dy = w * frac, h * frac
    return clip_box((x - dx, y - dy, w + 2 * dx, h + 2 * dy), shape)


def area_ok(bbox: BBox, shape) -> bool:
    """Is this box in the size range where a logo could plausibly live?"""
    height, width = shape[:2]
    image_area = float(height * width)
    if image_area <= 0:
        return False
    area = float(max(0, bbox[2]) * max(0, bbox[3]))
    return (
        config.PROPOSAL_MIN_AREA_FRAC * image_area
        <= area
        <= config.PROPOSAL_MAX_AREA_FRAC * image_area
    )


def iou(a: BBox, b: BBox) -> float:
    """Intersection over union of two boxes."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    overlap = float((x1 - x0) * (y1 - y0))
    union = float(aw * ah + bw * bh) - overlap
    return overlap / union if union > 0 else 0.0


def union_box(a: BBox, b: BBox) -> BBox:
    """Smallest box containing both."""
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1 = max(a[0] + a[2], b[0] + b[2])
    y1 = max(a[1] + a[3], b[1] + b[3])
    return x0, y0, x1 - x0, y1 - y0


def merge_overlapping(regions, threshold: float | None = None) -> list[Region]:
    """Fold regions overlapping by more than `threshold` into their union.

    The survivor keeps the higher-priority source, so a text box absorbing a
    stray MSER blob is still reported as a text proposal.
    """
    threshold = config.PROPOSAL_MERGE_IOU if threshold is None else threshold
    merged: list[Region] = []
    for region in sorted(
        regions, key=lambda r: (SOURCE_PRIORITY.get(r.source, 9), -r.area)
    ):
        for index, kept in enumerate(merged):
            if iou(region.bbox, kept.bbox) > threshold:
                merged[index] = Region(union_box(kept.bbox, region.bbox), kept.source)
                break
        else:
            merged.append(region)
    return merged


def tile_regions(shape, grid: int | None = None) -> list[Region]:
    """The coarse fallback: an NxN grid of overlapping tiles, plus the frame.

    Tiles overlap by half a cell so a logo straddling a cell boundary is still
    whole inside some tile.
    """
    grid = config.PROPOSAL_TILE_GRID if grid is None else grid
    height, width = shape[:2]
    regions = [Region((0, 0, width, height), "full")]
    if grid < 1 or width < 2 or height < 2:
        return regions
    step_x, step_y = width / (grid + 1), height / (grid + 1)
    tile_w, tile_h = width / grid, height / grid
    for row in range(grid + 1):
        for col in range(grid + 1):
            box = clip_box((col * step_x, row * step_y, tile_w, tile_h), shape)
            if box:
                regions.append(Region(box, "tile"))
    return regions


def group_boxes(boxes, shape) -> list[BBox]:
    """Cluster character-sized blobs into whole-mark boxes.

    MSER answers with one blob per *stroke group* - on a wordmark that means one
    box per letter, and a crop of the letter "A" tells the embedding model
    nothing. Neighbouring blobs are therefore painted into a mask, dilated
    sideways by roughly one character width, and read back as connected
    components, which glues a word (and a symbol sitting beside it) into a
    single region. The individual blobs are kept as well: a lone symbol mark is
    already whole, and merging drops the duplicates later.
    """
    boxes = [tuple(int(v) for v in box) for box in boxes]
    if not boxes:
        return []
    height, width = shape[:2]
    heights = sorted(box[3] for box in boxes)
    median_h = max(1, heights[len(heights) // 2])
    mask = np.zeros((height, width), dtype=np.uint8)
    for x, y, w, h in boxes:
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    # Wide, short kernel: join letters across the gaps, not paragraphs down.
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(3, int(median_h * 1.2)), max(1, int(median_h * 0.4)))
    )
    joined = cv2.dilate(mask, kernel)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(joined, 8)
    grouped = []
    for index in range(1, count):
        x, y, w, h, _area = stats[index]
        grouped.append((int(x), int(y), int(w), int(h)))
    return grouped + boxes


def mser_regions(image: np.ndarray) -> list[Region]:
    """MSER blobs, area-filtered. Never raises - it is one source among many.

    The input is forced to 3-channel BGR on purpose: OpenCV 5.0's
    `MSER.detectRegions` returns an *empty* result for a single-channel array
    instead of raising, so handing it a grayscale image silently disables this
    whole proposal source (D-025).
    """
    if image.ndim == 2:
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    else:
        bgr = image
    height, width = bgr.shape[:2]
    max_area = int(config.PROPOSAL_MSER_MAX_AREA_FRAC * height * width)
    try:
        detector = cv2.MSER_create(
            delta=config.PROPOSAL_MSER_DELTA,
            min_area=config.PROPOSAL_MSER_MIN_AREA,
            max_area=max(config.PROPOSAL_MSER_MIN_AREA + 1, max_area),
        )
        _points, boxes = detector.detectRegions(bgr)
    except Exception:  # OpenCV build differences must not kill the scan
        return []
    return [Region(box, "mser") for box in group_boxes(boxes, bgr.shape)]


def text_regions(image: np.ndarray) -> list[Region]:
    """Every OCR line box, brand-matching or not (see the module docstring).

    Imported lazily so `proposals` stays usable - and testable - without the
    OCR engine loaded.
    """
    try:
        from logoscanner.ocr import read_text

        return [Region(bbox, "text") for _text, _conf, bbox in read_text(image)]
    except Exception:
        return []


def propose(
    image: np.ndarray,
    extra: tuple = (),
    max_regions: int | None = None,
    use_text: bool = True,
    use_mser: bool = True,
) -> list[Region]:
    """Candidate regions for `image`, best-guess first and budget-capped.

    `extra` accepts `(bbox, source)` pairs or `Region`s - that is how a caller
    feeds in a box another signal already computed. The tile fallback and the
    full frame are always kept, so the budget only rations the smarter sources.
    """
    max_regions = config.PROPOSAL_MAX_REGIONS if max_regions is None else max_regions
    shape = image.shape

    hinted: list[Region] = []
    for item in extra:
        hinted.append(
            item if isinstance(item, Region) else Region(tuple(item[0]), item[1])
        )
    if use_text:
        hinted.extend(text_regions(image))
    if use_mser:
        hinted.extend(mser_regions(image))

    padded: list[Region] = []
    for region in hinted:
        box = pad_box(region.bbox, shape)
        if box and area_ok(box, shape):
            padded.append(Region(box, region.source))

    fallback = tile_regions(shape)
    budget = max(0, max_regions - len(fallback))
    kept = merge_overlapping(padded)[:budget]
    return merge_overlapping(kept + fallback)
