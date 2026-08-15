from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ImageItem:
    id: str
    path: Path
    created_at: str
    prompt: str
    tags: tuple[str, ...]
    label: str
    event_date: str
    source: str


class ImageLibrary:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.media_dir = self.root / "media"
        self.index_path = self.root / "index.json"
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def _save(self, rows: list[dict]) -> None:
        temp = self.index_path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.index_path)

    @staticmethod
    def _from_row(row: dict) -> ImageItem:
        return ImageItem(
            id=row["id"], path=Path(row["path"]), created_at=row["created_at"],
            prompt=row.get("prompt", ""), tags=tuple(row.get("tags", [])),
            label=row.get("label", ""),
            event_date=row.get("event_date", str(row.get("created_at", ""))[:10]),
            source=row.get("source", "unknown"),
        )

    @staticmethod
    def _clean_label(label: str) -> str:
        clean = " ".join(str(label).strip().split())
        clean = clean.replace("/", "-").replace("\\", "-").replace(":", "-")
        return clean[:64] or "untitled"

    def archive(
        self,
        source_path: Path,
        *,
        prompt: str = "",
        tags: Iterable[str] = (),
        label: str = "",
        event_date: str = "",
        source: str = "generated",
        created_at: datetime | None = None,
    ) -> ImageItem:
        source_path = Path(source_path).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        clean_label = self._clean_label(label)
        clean_tags = sorted({str(tag).strip() for tag in tags if str(tag).strip()} | {clean_label})
        timestamp = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        clean_event_date = event_date.strip() or f"{timestamp:%Y-%m-%d}"
        clean_tags = sorted(set(clean_tags) | {f"date:{clean_event_date}"})
        rows = self._load()
        for row in rows:
            if row.get("id") == digest:
                row["tags"] = sorted(set(row.get("tags", [])) | set(clean_tags))
                if not row.get("label") or row.get("label") == "untitled":
                    row["label"] = clean_label
                row.setdefault("event_date", clean_event_date)
                if prompt and not row.get("prompt"):
                    row["prompt"] = prompt
                self._save(rows)
                return self._from_row(row)
        suffix = source_path.suffix.lower() or ".bin"
        destination = self.media_dir / f"{timestamp:%Y-%m-%d}_{clean_label}_{digest[:12]}{suffix}"
        shutil.copy2(source_path, destination)
        row = {
            "id": digest,
            "path": str(destination),
            "created_at": timestamp.isoformat(),
            "prompt": prompt,
            "tags": clean_tags,
            "label": clean_label,
            "event_date": clean_event_date,
            "source": source,
        }
        rows.append(row)
        self._save(rows)
        return self._from_row(row)

    def search(self, query: str = "", date_from: str = "", date_to: str = "", limit: int = 10) -> list[ImageItem]:
        terms = [part.casefold() for part in query.split() if part]
        matches: list[ImageItem] = []
        for row in reversed(self._load()):
            created = str(row.get("created_at", ""))[:10]
            if date_from and created < date_from:
                continue
            if date_to and created > date_to:
                continue
            filename_title = Path(str(row.get("path", ""))).stem
            haystack = " ".join([
                filename_title,
                row.get("label", ""),
                row.get("prompt", ""),
                *row.get("tags", []),
            ]).casefold()
            if terms and not all(term in haystack for term in terms):
                continue
            matches.append(self._from_row(row))
            if len(matches) >= max(1, min(limit, 50)):
                break
        return matches