# Architecture

> Keep this file matching reality. Update on any behavioral change.

## Current state
**phase07 done: the scanner is resumable, deduplicating and crash-proof, and the full collection
has been scanned.**
`python -m logoscanner scan` walks a folder (`io_utils.iter_images`), and for each file:
hashes its bytes, loads it safely (`io_utils.load_image`, downscaled to `config.MAX_SIDE`, decode
failures recorded not raised, AVIF via a Pillow fallback), hashes its pixels, and - if neither hash
has been seen - runs every signal in `config.ENABLED_SIGNALS` through `pipeline.Pipeline` and bands
the result with `decision.decide`. The verdict is appended to `output/.progress.jsonl` and flushed
to disk before the next image starts, and `results.csv` + `summary.json` are rebuilt from that
journal at the end of every run (D-030). A re-run skips whatever the journal already holds, so a
killed or Ctrl-C'd scan resumes where it stopped; `--restart` throws the journal away, which is
what to do after changing a threshold. Per-image failures become rows in `results.csv` and
`errors.csv` instead of ending the run.

`ocr.OcrSignal` reads text with RapidOCR and fuzzy-matches each line against
`config.BRAND_TERMS` (D-013), scoring `fuzz/100 x ocr_confidence` and returning the winning
line's box. `keypoints.SiftSignal` covers the logos OCR cannot read: SIFT descriptors are
computed once per variant in `logo/`, matched with a Lowe ratio test kept one-per-image-location,
and verified by a RANSAC homography whose projected quad must be a believable logo placement
(D-017); score is `min(1, inliers / SIFT_SCORE_NORM)`. An empty or missing `logo/` warns once
and the signal scores 0, so a scan still runs on OCR alone.

`embeddings.EmbeddingSignal` covers what neither of the others can see (D-024). `proposals.propose`
first cuts candidate boxes out of the image - OCR line boxes (a stylised wordmark is still *text*
to the detector even when it reads as gibberish), MSER stable regions grouped from per-letter
blobs into whole marks, any box another signal passes in, and an always-kept 3x3 tile grid plus
the full frame - padded, area-filtered, merged and capped at `PROPOSAL_MAX_REGIONS`. Each crop is
embedded by a **frozen** DINOv2-small (no training, no labels) and scored by cosine similarity
against every `logo/` variant, each of which is embedded on both a white and a black background.
The score is the best crop-vs-variant cosine and the box is that crop. Whole images are never
compared directly: a mark covering 2% of a photo barely moves that photo's global feature vector.
Missing torch, a missing checkpoint or an empty `logo/` all degrade to "warn once, score 0".

`decision.decide` gives each signal its own `(weak, strong)` pair from
`config.SIGNAL_THRESHOLDS`, asks each which band it claims, and takes the best band claimed
(D-021). Calibrated 2026-09-08 over all three signals on the corrected labeled set: OCR
0.75/0.85, SIFT 0.45/0.45, EMB 0.85/0.95. SIFT collapses to a single bar - a homography-verified
match is either convincing or noise, so it flags or stays silent - while OCR and the embedding
signal both keep a real review band. `confidence` is the winner's score normalized onto the shared
scale (weak → 0.50, strong → 0.85) and `method` names every signal that claimed the band.

`python -m logoscanner calibrate --labeled <dir>` re-derives those four numbers and writes them
back into `config.py`; `python -m logoscanner benchmark --labeled <dir> --signals ocr,sift`
reports what each signal could do alone plus a naive-OR row (D-019), appending to
`docs/BENCHMARKS.md`.

Measured on the corrected labeled set (98/160 - two positives turned out to carry no logo at all
and were moved to `negative/`, D-028): precision **0.873**, catch-recall **0.980**, review share
**8.9%** at 0.45 img/s. The gate **PASSED**, both targets met with no relaxation, and the
attainable recall ceiling is 1.0 (D-029). The embedding signal is what cleared it, not the
relabeling: phase04's detector re-scored on the corrected labels still reaches only 0.959. Two
positives are still missed - a screenshot whose wordmark OCR garbles to two characters, and one
product diagram the calibration chose to give up in exchange for precision. **phase06 is therefore
unnecessary and was skipped.**
phase01 baseline was ~42 img/s for walk + decode + resize alone; OCR still dominates the cost, with
the embedding stage adding ~0.33 s/image. On the real collection the scanner holds ~0.44 img/s, an
ETA of ~6h20m for 10,000 images - comfortably inside the 12 h bar phase07 set for reaching for
multiprocessing, which is why `--workers` does not exist. See BENCHMARKS for throughput and the
production-run summary.

### The scan loop (phase07)
```text
for each file under input/:
   sha256(bytes) ─ seen? ──► copy that verdict, decode nothing        ┐
      │ no                                                            │ duplicate_of
   load_image ─ error? ──► error row, keep going                      │
      │                                                               │
   dhash(pixels) ─ within 4 bits of something seen? ──► copy verdict ─┘
      │ no
   signals ──► decision ──► crop + copy into detected/ | review/
      │
   append one JSON line to output/.progress.jsonl  (flush + fsync)
end
rewrite results.csv / summary.json / errors.csv from the journal
```
Both hashes come before the pipeline because both are thousands of times cheaper than a signal
pass: a website export is full of the same picture saved twice, and each copy would otherwise cost
~2 s *and* land in `review/` as another image for the human to judge (D-031). A duplicate borrows
the original's band, confidence, box and method, and gets no crop and no copy of its own - the CSV
still lists it, naming the original in `duplicate_of`.

`output/detected/`, `output/review/` and `output/crops/` mirror the input's folder structure so
same-named files in different folders cannot overwrite each other (D-032). The crop is the padded
match box, and it is the fast path for review: judging a 200x80 mark takes a second where opening
the full photo takes several. Negatives are listed in the CSV only.

## Target pipeline
```text
image ──► OCR signal   (RapidOCR + fuzzy brand-term match)      ─┐
      ──► SIFT signal  (keypoints + Lowe ratio + RANSAC verify) ─┤► rule-based decision ──► positive / review / negative
      ──► EMB signal   (region proposals + frozen DINOv2 cosine)─┘        │
                                                                         ▼
          [skipped] fine-tuned nano detector - phase05 met the gate   results.csv/json, crops/, detected/, review/
```

## Key principles
- Decision engine uses **OR rules**, not weighted averages: one strong signal ⇒ positive; a lone medium signal ⇒ review. Protects recall. Since phase04 the OR runs over the *bands each signal claims*, not over raw scores, because a score means something different in each signal (D-021).
- Every signal owns a `(weak, strong)` threshold pair; `confidence` is the winner's score normalized onto one shared scale (weak → 0.50, strong → 0.85). Monotonic, comparable, **not** a probability.
- Thresholds come from **calibration on the labeled set**, never intuition: `calibrate` grid-searches them and writes them into `config.py`. Bands: positive / review / negative.
- Signals are independent modules returning `SignalResult(score, bbox, method, detail)` so the decision layer stays pluggable.
- CPU-first. Performance work only if measured ETA for 10k images exceeds ~12 h (then: multiprocessing before any GPU runtime).
- Heavy models are used **frozen**, never fine-tuned (D-024): 100 positives is enough to memorise a dataset, not to learn a mark. Every model-backed stage must also degrade to "warn once, score 0" so a missing dependency can never abort a scan.
- Expensive stages are computed once per image and shared: `ocr.read_text` is memoised on a content hash so the embedding stage's region proposals reuse the OCR pass instead of paying for it twice (D-026).

## Calibration flow
```text
data/labeled/{positive,negative}
        │  metrics.score_images  (load once, every signal scores every image)
        ▼
   [ScoredImage(filename, label, {signal: score})]
        │  calibrate.search      (grid over each signal's (weak, strong); band vectors, OR, metrics)
        ▼
   objective: max precision  s.t. catch-recall >= 0.97 and review <= 10%   (relaxed if unreachable, D-022)
        │
        ├─► metrics.evaluate on the winner  ─► output/calibration.json
        ├─► config.SIGNAL_THRESHOLDS block rewritten in place
        └─► gate verdict  ─► output/gate_failures.txt when it fails
```
Scoring is the only expensive step, so it happens once and tens of thousands of threshold
combinations are judged on the stored scores. The winner is re-measured through
`metrics.evaluate` - the same `decision.decide` the scanner runs - so the published numbers can
never drift from the shipped behaviour.

## Data flow & artifacts
`input/` → scanner walk → dedup hashes → per-image signals → decision → one journal line per image
in `output/.progress.jsonl` (the resume point and the source of truth) → `output/results.csv`,
`output/summary.json`, `output/errors.csv` rebuilt from the journal, plus `crops/`, `detected/` and
`review/` for everything flagged.

| artifact | what it holds |
|---|---|
| `.progress.jsonl` | one JSON line per processed image; append-only, fsynced, the resume point |
| `results.csv` | every image: band, confidence, box, method, `duplicate_of`, error |
| `summary.json` | band totals, duplicates, errors, processed/skipped, img/s, 10k ETA |
| `errors.csv` | just the files that failed, so a 10k run's losses are visible at a glance |
| `detected/`, `review/` | copies of the flagged originals, input tree mirrored |
| `crops/` | the padded match box of each flagged image - the fast path for human review |
