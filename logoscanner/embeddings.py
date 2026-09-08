"""Embedding signal: compare candidate crops against the logo in feature space.

OCR reads text and SIFT matches geometry. Both fail on the same kind of image:
the mark is there, but it is too small, too smooth or too re-drawn to give
either one something to hold. This signal asks a different question - *does
this crop look like the logo?* - using a self-supervised vision transformer
(DINOv2-small) as a fixed feature extractor. Nothing is trained here (D-024);
the model is used exactly as downloaded, and only the cosine distance between
its output vectors carries information.

The pipeline is deliberately dull:

    logo variants -> one embedding each (cached per process)
    image         -> candidate regions (`proposals.propose`)
                  -> one embedding per crop, in a single batch
    score         = max cosine(crop, variant) over all pairs
    bbox          = the region that produced that maximum

Similarities are plain NumPy dot products over L2-normalised vectors - with a
handful of variants and a couple of dozen crops, an index like FAISS would cost
more than it saves (D-004).

Degradation is quiet and total: no torch, no `logo/`, or a model that will not
load means a warning once and 0.0 for every image thereafter, exactly like the
SIFT signal with an empty logo folder. A scan never dies because an optional
dependency is missing.
"""

from __future__ import annotations

import threading
import warnings
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from logoscanner import config
from logoscanner.proposals import Region, propose
from logoscanner.signals import BBox, SignalResult, register

SIGNAL_NAME = "emb"

# DINOv2 was trained with the ImageNet statistics.
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_model_lock = threading.Lock()
_model = None
_model_failed = ""
_template_lock = threading.Lock()
_template_cache: dict[tuple[str, str], "Templates"] = {}


@dataclass(frozen=True)
class Templates:
    """The logo variants as one L2-normalised matrix, plus their names."""

    names: tuple[str, ...]
    vectors: np.ndarray  # (n_variants, dim)

    def __len__(self) -> int:
        return len(self.names)


def load_model():
    """The DINOv2 backbone, loaded once per process. None when unavailable.

    Kept behind a function (and a lazy import) so that neither `torch` nor a
    downloaded checkpoint is needed to import this module, run the other
    signals, or run the fast test suite.
    """
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    with _model_lock:
        if _model is not None or _model_failed:
            return _model
        try:
            import timm
            import torch

            if config.EMB_THREADS > 0:
                torch.set_num_threads(config.EMB_THREADS)
            model = timm.create_model(
                config.EMB_MODEL,
                pretrained=True,
                num_classes=0,
                dynamic_img_size=True,
            )
            model.eval()
            _model = model
        except Exception as exc:  # missing dep, no checkpoint, no network
            _model_failed = f"{type(exc).__name__}: {exc}"
            return None
    return _model


def reset_model() -> None:
    """Forget the loaded model and any load failure (tests)."""
    global _model, _model_failed
    with _model_lock:
        _model = None
        _model_failed = ""


def letterbox(crop: np.ndarray, size: int, fill: int = 255) -> np.ndarray:
    """Resize to `size` x `size` preserving aspect, padding the remainder.

    Squashing matters here: a wordmark is three times wider than it is tall, and
    stretching it to a square makes it look like a different mark to the model.
    """
    height, width = crop.shape[:2]
    if height < 1 or width < 1:
        return np.full((size, size, 3), fill, dtype=np.uint8)
    scale = min(size / width, size / height)
    new_w = max(1, min(size, int(round(width * scale))))
    new_h = max(1, min(size, int(round(height * scale))))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(crop, (new_w, new_h), interpolation=interp)
    canvas = np.full((size, size, 3), fill, dtype=np.uint8)
    top, left = (size - new_h) // 2, (size - new_w) // 2
    canvas[top : top + new_h, left : left + new_w] = resized
    return canvas


def preprocess(crops, size: int | None = None) -> np.ndarray:
    """Stack BGR crops into the NCHW float tensor the model expects."""
    size = config.EMB_INPUT_SIZE if size is None else size
    batch = np.empty((len(crops), size, size, 3), dtype=np.float32)
    for index, crop in enumerate(crops):
        boxed = letterbox(crop, size)
        rgb = cv2.cvtColor(boxed, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        batch[index] = (rgb - IMAGENET_MEAN) / IMAGENET_STD
    return batch.transpose(0, 3, 1, 2)


def embed(crops, size: int | None = None) -> np.ndarray | None:
    """L2-normalised embeddings for BGR crops, or None when the model is out.

    Runs in batches so a 24-region image is a couple of forward passes rather
    than 24.
    """
    if not len(crops):
        return np.zeros((0, 0), dtype=np.float32)
    model = load_model()
    if model is None:
        return None
    import torch

    outputs = []
    with torch.inference_mode():
        for start in range(0, len(crops), config.EMB_BATCH_SIZE):
            chunk = crops[start : start + config.EMB_BATCH_SIZE]
            tensor = torch.from_numpy(preprocess(chunk, size))
            outputs.append(model(tensor).float().numpy())
    vectors = np.concatenate(outputs, axis=0).astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def _variant_views(path: Path) -> list[np.ndarray]:
    """Readable BGR views of one logo file.

    A transparent variant is composited onto **both** white and black: the same
    white wordmark appears on a dark hero image and on a light slide, and the
    background it is flattened onto changes its embedding a lot.
    """
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return []
    if buf.size == 0:
        return []
    image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        return []
    if image.ndim == 2:
        return [cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)]
    if image.shape[2] == 4:
        alpha = (image[:, :, 3:4].astype(np.float32)) / 255.0
        colour = image[:, :, :3].astype(np.float32)
        views = []
        for fill in (255.0, 0.0):
            flat = colour * alpha + fill * (1.0 - alpha)
            views.append(flat.clip(0, 255).astype(np.uint8))
        return views
    return [image]


def build_templates(logo_dir: str | Path) -> Templates:
    """Embed every logo variant in `logo_dir` (both backgrounds where alpha)."""
    logo_dir = Path(logo_dir)
    names: list[str] = []
    views: list[np.ndarray] = []
    if logo_dir.is_dir():
        for path in sorted(logo_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in config.IMAGE_EXTS:
                continue
            for index, view in enumerate(_variant_views(path)):
                names.append(path.name if index == 0 else f"{path.name}#{index}")
                views.append(view)
    if not views:
        return Templates((), np.zeros((0, 0), dtype=np.float32))
    vectors = embed(views)
    if vectors is None:
        return Templates((), np.zeros((0, 0), dtype=np.float32))
    return Templates(tuple(names), vectors)


def get_templates(logo_dir: str | Path) -> Templates:
    """`build_templates`, memoised per (logo dir, model) - embedding costs real time."""
    key = (str(Path(logo_dir).resolve()), config.EMB_MODEL)
    cached = _template_cache.get(key)
    if cached is None:
        with _template_lock:
            cached = _template_cache.get(key)
            if cached is None:
                cached = build_templates(logo_dir)
                _template_cache[key] = cached
    return cached


def clear_cache() -> None:
    """Forget memoised template embeddings (tests, or an edited logo folder)."""
    with _template_lock:
        _template_cache.clear()


def crop_regions(image: np.ndarray, regions) -> tuple[list[np.ndarray], list[Region]]:
    """Cut each region out of the image, dropping any that came back empty."""
    crops, kept = [], []
    for region in regions:
        x, y, w, h = region.bbox
        patch = image[y : y + h, x : x + w]
        if patch.size == 0:
            continue
        if patch.ndim == 3 and patch.shape[2] == 4:
            patch = cv2.cvtColor(patch, cv2.COLOR_BGRA2BGR)
        elif patch.ndim == 2:
            patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
        crops.append(patch)
        kept.append(region)
    return crops, kept


class EmbeddingSignal:
    """Crop-vs-logo similarity in DINOv2 feature space. Model loads on first `run`."""

    name = SIGNAL_NAME

    def __init__(self, logo_dir: str | Path | None = None):
        self.logo_dir = Path(config.LOGO_DIR if logo_dir is None else logo_dir)
        self._warned = False

    def templates(self) -> Templates:
        """Cached template embeddings; warns once when there are none."""
        found = get_templates(self.logo_dir)
        if not len(found) and not self._warned:
            self._warned = True
            reason = _model_failed or f"no usable logo variants in {self.logo_dir}"
            warnings.warn(
                f"{reason}: the {self.name!r} signal will score 0 for every image",
                RuntimeWarning,
                stacklevel=2,
            )
        return found

    def run(self, image: np.ndarray) -> SignalResult:
        templates = self.templates()
        if not len(templates):
            return SignalResult(self.name, 0.0, None, _model_failed or "no logo variants")
        try:
            return self._match(image, templates)
        except Exception as exc:  # never abort a 10k-image scan
            return SignalResult(self.name, 0.0, None, f"error: {type(exc).__name__}: {exc}")

    def _match(self, image: np.ndarray, templates: Templates) -> SignalResult:
        regions = propose(image)
        crops, kept = crop_regions(image, regions)
        if not crops:
            return SignalResult(self.name, 0.0, None, "no candidate regions")
        vectors = embed(crops)
        if vectors is None:
            return SignalResult(self.name, 0.0, None, _model_failed or "model unavailable")

        # (n_crops, n_variants) cosines; both sides are already L2-normalised.
        similarity = vectors @ templates.vectors.T
        flat = int(np.argmax(similarity))
        crop_index, variant_index = divmod(flat, similarity.shape[1])
        best = float(similarity[crop_index, variant_index])
        region = kept[crop_index]
        detail = (
            f"{templates.names[variant_index]} cos={best:.3f} "
            f"via {region.source} ({len(crops)} regions)"
        )
        if best < config.EMB_MIN_SIMILARITY:
            return SignalResult(self.name, 0.0, None, f"below floor: {detail}")
        return SignalResult(self.name, max(0.0, best), _bbox(region.bbox), detail)


def _bbox(bbox: BBox) -> BBox:
    return tuple(int(v) for v in bbox)


@register(SIGNAL_NAME)
def _build() -> EmbeddingSignal:
    return EmbeddingSignal()
