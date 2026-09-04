"""Selection rules of tools/wp_collect.py (fake filenames only)."""

import wp_collect


def build(tmp_path, names):
    """Create uploads/2024/05/<names> and return the scan groups."""
    month = tmp_path / "2024" / "05"
    month.mkdir(parents=True)
    for name in names:
        (month / name).write_bytes(b"x" * len(name))
    return wp_collect.scan(tmp_path, 2014, 2026)[0]


def best(groups):
    return {stem: min(c, key=wp_collect.Candidate.rank).path.name
            for (_, stem), c in groups.items()}


def test_unsuffixed_original_wins_over_thumbnails(tmp_path):
    groups = build(tmp_path, ["photo.jpg", "photo-150x150.jpg", "photo-1024x768.jpg"])
    assert best(groups) == {"photo": "photo.jpg"}


def test_largest_variant_when_no_original(tmp_path):
    groups = build(tmp_path, ["photo-150x150.jpg", "photo-1024x768.jpg", "photo-300x200.jpg"])
    assert best(groups) == {"photo": "photo-1024x768.jpg"}


def test_scaled_beats_thumbnails_but_loses_to_original(tmp_path):
    groups = build(tmp_path, ["a-scaled.jpg", "a-150x150.jpg"])
    assert best(groups) == {"a": "a-scaled.jpg"}
    groups = build(tmp_path / "second", ["b.jpg", "b-scaled.jpg", "b-150x150.jpg"])
    assert best(groups) == {"b": "b.jpg"}


def test_only_the_trailing_size_suffix_is_stripped(tmp_path):
    """`128T-300x150-1.png` is an original whose *name* contains a size."""
    groups = build(tmp_path, ["128T-300x150-1.png", "128T-300x150-1-150x150.png"])
    assert best(groups) == {"128T-300x150-1": "128T-300x150-1.png"}


def test_plugin_conversions_lose_to_the_source_format(tmp_path):
    groups = build(tmp_path, ["shot.png", "shot.webp", "shot.avif"])
    assert best(groups) == {"shot": "shot.png"}


def test_backups_and_non_images_are_ignored(tmp_path):
    groups = build(tmp_path, ["doc.pdf", "clip.mp4", "photo.bak.jpg", "photo.jpg"])
    assert best(groups) == {"photo": "photo.jpg"}


def test_same_name_in_two_months_is_two_uploads(tmp_path):
    (tmp_path / "2024" / "05").mkdir(parents=True)
    (tmp_path / "2024" / "06").mkdir(parents=True)
    (tmp_path / "2024" / "05" / "x.jpg").write_bytes(b"a")
    (tmp_path / "2024" / "06" / "x.jpg").write_bytes(b"b")
    groups = wp_collect.scan(tmp_path, 2014, 2026)[0]
    assert sorted(groups) == [("2024-05", "x"), ("2024-06", "x")]


def test_years_outside_the_range_are_skipped(tmp_path):
    build(tmp_path, ["photo.jpg"])
    assert wp_collect.scan(tmp_path, 2025, 2026)[0] == {}


def test_layout_keeps_the_original_filename(tmp_path):
    """Same name in two months must survive verbatim, in its own folder."""
    src, dest = tmp_path / "up", tmp_path / "out"
    for month in ("05", "06"):
        (src / "2024" / month).mkdir(parents=True)
        (src / "2024" / month / "NGM.png").write_bytes(month.encode())
        (src / "2024" / month / "NGM-150x150.png").write_bytes(b"thumb")
    assert wp_collect.main(["--source", str(src), "--dest", str(dest)]) == 0
    assert sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*.png")) == [
        "2024-05/NGM.png", "2024-06/NGM.png"]


def test_dedupe_is_opt_in(tmp_path):
    src, dest = tmp_path / "up", tmp_path / "out"
    for month in ("05", "06"):
        (src / "2024" / month).mkdir(parents=True)
        (src / "2024" / month / "same.png").write_bytes(b"identical")
    assert wp_collect.main(["--source", str(src), "--dest", str(dest)]) == 0
    assert len(list(dest.rglob("*.png"))) == 2
    assert wp_collect.main(["--source", str(src), "--dest", str(dest / "d"),
                            "--dedupe"]) == 0
    assert len(list((dest / "d").rglob("*.png"))) == 1


def test_fit_name_only_touches_names_that_break_the_path_limit(tmp_path):
    assert wp_collect.fit_name(tmp_path, "short.jpg") == "short.jpg"
    long = "L" * 200 + ".jpg"
    fitted = wp_collect.fit_name(tmp_path, long)
    assert fitted != long and fitted.endswith(".jpg")
    assert len(str(tmp_path / fitted)) <= 255
