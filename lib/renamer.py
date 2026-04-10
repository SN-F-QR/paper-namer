from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TypedDict

from .errors import RenamerError


INVALID_CHARS = re.compile(r"[\\/*?:\"<>|]")
HASH_CHUNK_SIZE = 1024 * 1024


class StaleProcessedEntry(TypedDict):
    content_hash: str
    filename: str


def sanitize(title: str, max_len: int = 60) -> str:
    cleaned = INVALID_CHARS.sub("", (title or "untitled")).strip()
    compact = re.sub(r"\s+", " ", cleaned)
    clipped = compact[:max_len].strip()
    return clipped or "untitled"


class ProcessedStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache = self._load()

    def _load(self) -> dict[str, str]:
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RenamerError(
                f"Invalid processed file JSON: {self.file_path}"
            ) from exc

    def _save(self) -> None:
        self.file_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def compute_hash(self, pdf_path: Path) -> str:
        sha256 = hashlib.sha256()
        try:
            with pdf_path.open("rb") as f:
                while chunk := f.read(HASH_CHUNK_SIZE):
                    sha256.update(chunk)
        except OSError as exc:
            raise RenamerError(f"Cannot read file for hash: {pdf_path}") from exc
        return f"sha256:{sha256.hexdigest()}"

    def is_processed(self, content_hash: str) -> bool:
        return content_hash in self._cache

    def cleanup_stale_entries(
        self, directory: Path, *, dry_run: bool
    ) -> list[StaleProcessedEntry]:
        stale_hashes: list[str] = []
        stale_entries: list[StaleProcessedEntry] = []

        for stored_hash, filename in self._cache.items():
            tracked_path = directory / filename
            if not tracked_path.exists():
                stale_hashes.append(stored_hash)
                stale_entries.append(
                    {"content_hash": stored_hash, "filename": filename}
                )
                continue

            current_hash = self.compute_hash(tracked_path)
            if current_hash != stored_hash:
                stale_hashes.append(stored_hash)
                stale_entries.append(
                    {"content_hash": stored_hash, "filename": filename}
                )

        if stale_hashes and not dry_run:
            for stale_hash in stale_hashes:
                self._cache.pop(stale_hash, None)
            self._save()

        # Preserve order while removing duplicate stale hashes.
        unique_entries: list[StaleProcessedEntry] = []
        seen_hashes: set[str] = set()
        for entry in stale_entries:
            entry_hash = entry["content_hash"]
            if entry_hash in seen_hashes:
                continue
            unique_entries.append(entry)
            seen_hashes.add(entry_hash)

        return unique_entries

    def mark_processed(self, content_hash: str, new_filename: str) -> None:
        self._cache[content_hash] = new_filename
        self._save()


def _resolve_conflict(target_path: Path) -> Path:
    if not target_path.exists():
        return target_path

    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def rename_pdf(
    pdf_path: Path,
    *,
    year: str,
    zh_title: str,
    processed: ProcessedStore,
    dry_run: bool,
) -> Path:
    if not pdf_path.exists():
        raise RenamerError(f"File not found: {pdf_path}")

    safe_year = year if year else "未知"
    safe_title = sanitize(zh_title)
    target_name = f"{safe_year}_{safe_title}.pdf"
    target_path = _resolve_conflict(pdf_path.parent / target_name)

    content_hash = processed.compute_hash(pdf_path)
    if dry_run:
        return target_path

    try:
        pdf_path.rename(target_path)
    except OSError as exc:
        raise RenamerError(f"Rename failed: {pdf_path} -> {target_path}") from exc

    processed.mark_processed(content_hash, target_path.name)
    return target_path
