from datetime import datetime, timezone
from pathlib import Path

from conversation_improvement.library import ImageLibrary


def test_archive_and_search_by_tags_and_date(tmp_path: Path):
    source = tmp_path / "selfie.png"
    source.write_bytes(b"image")
    library = ImageLibrary(tmp_path / "data")
    item = library.archive(
        source,
        prompt="窗边自拍",
        tags=["自拍", "窗边", "开心"],
        label="窗边-开心",
        event_date="2026-08-14",
        created_at=datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc),
    )

    assert item.path.exists()
    assert item.created_at.startswith("2026-08-14")
    assert item.label == "窗边-开心"
    assert item.event_date == "2026-08-14"
    assert "窗边-开心" in item.path.name
    assert library.search(query="自拍", date_from="2026-08-14", date_to="2026-08-14")[0].id == item.id


def test_archive_deduplicates_same_image(tmp_path: Path):
    source = tmp_path / "same.gif"
    source.write_bytes(b"gif")
    library = ImageLibrary(tmp_path / "data")
    first = library.archive(source, tags=["表情包"])
    second = library.archive(source, tags=["开心"])
    assert first.id == second.id
    assert {"表情包", "开心", "自动生成图片"}.issubset(set(second.tags))


def test_archive_adds_label_and_default_event_date(tmp_path: Path):
    source = tmp_path / "reaction.png"
    source.write_bytes(b"reaction")
    library = ImageLibrary(tmp_path / "data")
    item = library.archive(source, label="拥抱-开心", created_at=datetime(2026, 8, 15, tzinfo=timezone.utc))

    assert item.label == "拥抱-开心"
    assert item.event_date == "2026-08-15"
    assert "拥抱-开心" in item.path.name
    assert library.search(query="拥抱-开心")[0].id == item.id


def test_search_matches_archived_filename_title(tmp_path: Path):
    source = tmp_path / "reaction.png"
    source.write_bytes(b"reaction")
    library = ImageLibrary(tmp_path / "data")
    item = library.archive(source, label="慌张", tags=[], created_at=datetime(2026, 8, 15, tzinfo=timezone.utc))
    rows = library._load()
    rows[0].update(label="", tags=[], prompt="")
    library._save(rows)

    assert library.search(query="慌张")[0].id == item.id


def test_archive_infers_readable_label_when_host_omits_one(tmp_path: Path):
    source = tmp_path / "reaction.png"
    source.write_bytes(b"reaction")
    item = ImageLibrary(tmp_path / "data").archive(source, tags=["hug", "happy"])

    assert item.label == "拥抱-开心"
    assert "拥抱-开心" in item.path.name


def test_repair_missing_labels_renames_legacy_files(tmp_path: Path):
    source = tmp_path / "legacy.png"
    source.write_bytes(b"legacy")
    library = ImageLibrary(tmp_path / "data")
    item = library.archive(source, label="拥抱")
    rows = library._load()
    rows[0]["label"] = ""
    rows[0]["tags"] = ["blush", "cute"]
    old_path = item.path.with_name("2026-08-15_legacy.png")
    item.path.replace(old_path)
    rows[0]["path"] = str(old_path)
    library._save(rows)

    assert library.repair_missing_labels() == 1
    repaired = library.search(query="脸红害羞")[0]
    assert repaired.path.is_file()
    assert "脸红害羞" in repaired.path.name