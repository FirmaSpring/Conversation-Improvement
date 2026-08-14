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
        created_at=datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc),
    )

    assert item.path.exists()
    assert item.created_at.startswith("2026-08-14")
    assert library.search(query="自拍", date_from="2026-08-14", date_to="2026-08-14")[0].id == item.id


def test_archive_deduplicates_same_image(tmp_path: Path):
    source = tmp_path / "same.gif"
    source.write_bytes(b"gif")
    library = ImageLibrary(tmp_path / "data")
    first = library.archive(source, tags=["表情包"])
    second = library.archive(source, tags=["开心"])
    assert first.id == second.id
    assert set(second.tags) == {"表情包", "开心"}