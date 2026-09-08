"""The append-only resume journal (phase07).

The journal is the source of truth for a scan, so these tests care most about
what happens when a run dies mid-write: a torn line must cost one image, never
the run.
"""

from __future__ import annotations

import json

from logoscanner import config, journal
from logoscanner.journal import JOURNAL_NAME, Journal, JournalEntry


def _entry(path="a/one.png", **kwargs) -> JournalEntry:
    fields = dict(sha256="ab" * 32, dhash="0f1e2d3c4b5a6978", band="review",
                  confidence=0.62, bbox=(4, 5, 60, 30), method="ocr")
    fields.update(kwargs)
    return JournalEntry(path=path, **fields)


def test_entry_round_trips_through_json():
    entry = _entry()
    back = JournalEntry.from_json(entry.to_json())
    assert back.path == entry.path
    assert back.bbox == (4, 5, 60, 30)
    assert back.band == "review" and back.confidence == 0.62
    assert back.method == "ocr" and back.sha256 == entry.sha256
    assert back.image_hash == int("0f1e2d3c4b5a6978", 16)


def test_entry_survives_a_missing_box_and_missing_optional_fields():
    line = json.dumps({"path": "x.png", "band": "negative"})
    back = JournalEntry.from_json(line)
    assert back.bbox is None and back.confidence == 0.0
    assert back.duplicate_of == "" and back.error == ""
    assert back.image_hash is None


def test_torn_and_empty_lines_are_dropped_not_raised():
    assert JournalEntry.from_json('{"path": "half-writ') is None
    assert JournalEntry.from_json("") is None
    assert JournalEntry.from_json("   \n") is None
    assert JournalEntry.from_json("[1, 2, 3]") is None  # valid JSON, not an entry
    assert JournalEntry.from_json('{"band": "positive"}') is None  # no path


def test_entry_renders_the_csv_row():
    row = _entry(band=config.BAND_POSITIVE, confidence=0.9).to_row()
    assert row.filename == "a/one.png"
    assert row.contains_logo is True and row.band == "positive"
    assert (row.x, row.y, row.w, row.h) == (4, 5, 60, 30)

    negative = _entry(band=config.BAND_NEGATIVE, bbox=None).to_row()
    assert negative.contains_logo is False
    assert (negative.x, negative.y, negative.w, negative.h) == (None,) * 4


def test_from_decision_takes_the_band_box_and_method():
    from logoscanner.decision import Decision

    decision = Decision(confidence=0.87654, band="positive", method="ocr+emb",
                        bbox=(1, 2, 3, 4), detail="", results=())
    entry = JournalEntry.from_decision("b.png", decision, sha="ff", image_hash=255)
    assert entry.band == "positive" and entry.method == "ocr+emb"
    assert entry.confidence == 0.8765  # rounded for a readable journal
    assert entry.bbox == (1, 2, 3, 4) and entry.dhash.endswith("ff")


def test_copy_of_carries_the_verdict_and_names_the_original():
    original = _entry("first.png", band="positive", confidence=0.9)
    copy = journal.copy_of(original, "second.png", sha="cd", image_hash=7)
    assert copy.path == "second.png" and copy.duplicate_of == "first.png"
    assert (copy.band, copy.confidence, copy.bbox) == ("positive", 0.9, (4, 5, 60, 30))
    assert copy.sha256 == "cd"


def test_a_copy_of_a_copy_points_at_the_first_original():
    original = _entry("first.png")
    second = journal.copy_of(original, "second.png")
    third = journal.copy_of(second, "third.png")
    assert third.duplicate_of == "first.png"


def test_error_entry_is_negative_and_carries_the_reason():
    entry = journal.error_entry("bad.png", "decode failed", sha="ab")
    assert entry.band == config.BAND_NEGATIVE and entry.error == "decode failed"
    assert entry.to_row().error == "decode failed"


def test_appending_flushes_every_entry_immediately(tmp_path):
    path = tmp_path / JOURNAL_NAME
    with Journal(path) as log:
        log.append(_entry("one.png"))
        # Readable from another handle before the writer closes: that is what
        # makes a killed run recoverable.
        assert len(journal.load(path)) == 1
        log.append(_entry("two.png"))
    assert sorted(journal.load(path)) == ["one.png", "two.png"]


def test_load_skips_a_torn_final_line(tmp_path):
    path = tmp_path / JOURNAL_NAME
    with Journal(path) as log:
        log.append(_entry("one.png"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"path": "two.png", "band": "posi')  # power cut

    loaded = journal.load(path)
    assert list(loaded) == ["one.png"]


def test_load_of_a_missing_journal_is_empty(tmp_path):
    assert journal.load(tmp_path / "never-written.jsonl") == {}


def test_the_last_line_for_a_path_wins(tmp_path):
    path = tmp_path / JOURNAL_NAME
    with Journal(path) as log:
        log.append(_entry("one.png", band="negative"))
        log.append(_entry("one.png", band="positive"))
    assert journal.load(path)["one.png"].band == "positive"


def test_rows_are_sorted_by_path(tmp_path):
    entries = [_entry("b.png"), _entry("a.png"), _entry("c/d.png")]
    assert [row.filename for row in journal.rows(entries)] == ["a.png", "b.png", "c/d.png"]


def test_reset_removes_the_journal_and_tolerates_a_missing_one(tmp_path):
    path = tmp_path / JOURNAL_NAME
    with Journal(path) as log:
        log.append(_entry())
    journal.reset(path)
    assert not path.exists()
    journal.reset(path)  # no error the second time
