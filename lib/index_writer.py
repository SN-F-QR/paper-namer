from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from .errors import IndexWriterError


HEADER = "# Papers Index\n\n"
SECTION_PATTERN = re.compile(
    r"^## (?P<header>[^\n]+)\n\n(?P<body>.*?)(?:\n---\n\n|\Z)",
    re.MULTILINE | re.DOTALL,
)
ID_PATTERN = re.compile(r"^- \*\*ID\*\*:\s*(?P<id>.+?)\s*$", re.MULTILINE)
FILENAME_PATTERN = re.compile(r"^- \*\*文件名\*\*:\s*(?P<name>.+?)\s*$", re.MULTILINE)


def append_index_entry(
    *,
    index_path: Path,
    year: str,
    zh_title: str,
    file_name: str,
    original_title: str,
    source: str,
    summary: str,
    paper_id: str | None = None,
    dry_run: bool,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    id_line = f"- **ID**: {paper_id}\n" if paper_id else ""
    section = (
        f"## {year}_{zh_title}\n\n"
        f"- **原标题**: {original_title}\n"
        f"- **来源**: {source}\n"
        f"{id_line}"
        f"- **文件名**: {file_name}\n"
        f"- **核心贡献**: {summary}\n"
        f"- **处理时间**: {timestamp}\n\n"
        "---\n\n"
    )

    if dry_run:
        return

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        if not index_path.exists():
            index_path.write_text(HEADER, encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(section)
    except OSError as exc:
        raise IndexWriterError(f"Write index failed: {index_path}") from exc


def _section_filename(section_body: str) -> str | None:
    match = FILENAME_PATTERN.search(section_body)
    if not match:
        return None
    return match.group("name").strip()


def _section_id(section_body: str) -> str | None:
    match = ID_PATTERN.search(section_body)
    if not match:
        return None
    return match.group("id").strip()


def remove_index_entries(
    *,
    index_path: Path,
    filenames: list[str],
    paper_ids: list[str] | None = None,
    dry_run: bool,
) -> list[str]:
    target_names = {name.strip() for name in filenames if name.strip()}
    target_ids = {
        paper_id.strip() for paper_id in (paper_ids or []) if paper_id.strip()
    }
    if (not target_names and not target_ids) or not index_path.exists():
        return []

    target_headers = {Path(name).stem for name in target_names}

    try:
        original = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IndexWriterError(f"Read index failed: {index_path}") from exc

    matches = list(SECTION_PATTERN.finditer(original))
    if not matches:
        return []

    prefix = original[: matches[0].start()]
    if not prefix.strip():
        prefix = HEADER

    kept_sections: list[str] = []
    removed_headers: list[str] = []

    for match in matches:
        header = match.group("header").strip()
        body = match.group("body").rstrip()
        section_id = _section_id(body)
        section_file_name = _section_filename(body)

        remove_by_id = section_id is not None and section_id in target_ids
        remove_by_filename = (
            section_file_name is not None and section_file_name in target_names
        )
        remove_by_header = header in target_headers

        if remove_by_id or remove_by_filename or remove_by_header:
            removed_headers.append(header)
            continue

        kept_sections.append(f"## {header}\n\n{body}\n\n---\n\n")

    if not removed_headers:
        return []

    rebuilt = prefix
    if not rebuilt.endswith("\n\n"):
        rebuilt = rebuilt.rstrip("\n") + "\n\n"
    rebuilt += "".join(kept_sections)

    if not dry_run:
        try:
            index_path.write_text(rebuilt, encoding="utf-8")
        except OSError as exc:
            raise IndexWriterError(f"Write index failed: {index_path}") from exc

    return removed_headers
