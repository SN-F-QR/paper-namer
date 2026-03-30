import json
from pathlib import Path

from lib.renamer import ProcessedStore, rename_pdf, sanitize


def test_sanitize_removes_invalid_chars():
    assert sanitize('A/B:C*D?"E<F>G|') == "ABCDEFG"


def test_rename_conflict_appends_suffix(tmp_path: Path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"aaa")

    conflict = tmp_path / "2024_标题.pdf"
    conflict.write_bytes(b"bbb")

    store = ProcessedStore(tmp_path / ".processed")
    new_path = rename_pdf(
        source,
        year="2024",
        zh_title="标题",
        processed=store,
        dry_run=False,
    )
    assert new_path.name == "2024_标题_2.pdf"
    assert new_path.exists()


def test_idempotent_hash_tracking(tmp_path: Path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"same-content")

    store = ProcessedStore(tmp_path / ".processed")
    new_path = rename_pdf(
        source,
        year="2025",
        zh_title="论文",
        processed=store,
        dry_run=False,
    )

    raw = json.loads((tmp_path / ".processed").read_text(encoding="utf-8"))
    assert len(raw) == 1
    assert list(raw.values())[0] == new_path.name

    existing_hash = list(raw.keys())[0]
    assert store.is_processed(existing_hash)


def test_compute_hash_uses_full_file_content(tmp_path: Path):
    prefix = b"A" * 4096
    file_a = tmp_path / "a.pdf"
    file_b = tmp_path / "b.pdf"
    file_a.write_bytes(prefix + b"tail-a")
    file_b.write_bytes(prefix + b"tail-b")

    store = ProcessedStore(tmp_path / ".processed")
    assert store.compute_hash(file_a) != store.compute_hash(file_b)
