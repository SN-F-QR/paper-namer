from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .errors import IndexWriterError


HEADER = "# Papers Index\n\n"


def append_index_entry(
    *,
    index_path: Path,
    year: str,
    zh_title: str,
    original_title: str,
    source: str,
    summary: str,
    dry_run: bool,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    section = (
        f"## {year}_{zh_title}\n\n"
        f"- **原标题**: {original_title}\n"
        f"- **来源**: {source}\n"
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
