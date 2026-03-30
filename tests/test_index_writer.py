from pathlib import Path

from lib.index_writer import HEADER, append_index_entry, remove_index_entries


def test_remove_index_entries_by_filename(tmp_path: Path):
    index_path = tmp_path / "_index.md"

    append_index_entry(
        index_path=index_path,
        year="CHI24",
        zh_title="第一篇",
        file_name="CHI24_第一篇.pdf",
        original_title="Paper One",
        source="llm",
        summary="摘要一",
        dry_run=False,
    )
    append_index_entry(
        index_path=index_path,
        year="CHI25",
        zh_title="第二篇",
        file_name="CHI25_第二篇.pdf",
        original_title="Paper Two",
        source="llm",
        summary="摘要二",
        dry_run=False,
    )

    removed = remove_index_entries(
        index_path=index_path,
        filenames=["CHI24_第一篇.pdf"],
        dry_run=False,
    )

    text = index_path.read_text(encoding="utf-8")
    assert removed == ["CHI24_第一篇"]
    assert "CHI24_第一篇" not in text
    assert "CHI25_第二篇" in text


def test_remove_index_entries_falls_back_to_legacy_header_match(tmp_path: Path):
    index_path = tmp_path / "_index.md"
    legacy = (
        HEADER
        + "## CHI24_老条目\n\n"
        + "- **原标题**: Legacy Paper\n"
        + "- **来源**: llm\n"
        + "- **核心贡献**: legacy summary\n"
        + "- **处理时间**: 2026-03-29T00:00:00\n\n"
        + "---\n\n"
    )
    index_path.write_text(legacy, encoding="utf-8")

    removed = remove_index_entries(
        index_path=index_path,
        filenames=["CHI24_老条目.pdf"],
        dry_run=False,
    )

    text = index_path.read_text(encoding="utf-8")
    assert removed == ["CHI24_老条目"]
    assert "CHI24_老条目" not in text


def test_remove_index_entries_dry_run_does_not_modify_file(tmp_path: Path):
    index_path = tmp_path / "_index.md"

    append_index_entry(
        index_path=index_path,
        year="CHI24",
        zh_title="保留测试",
        file_name="CHI24_保留测试.pdf",
        original_title="Paper",
        source="llm",
        summary="摘要",
        dry_run=False,
    )

    before = index_path.read_text(encoding="utf-8")
    removed = remove_index_entries(
        index_path=index_path,
        filenames=["CHI24_保留测试.pdf"],
        dry_run=True,
    )
    after = index_path.read_text(encoding="utf-8")

    assert removed == ["CHI24_保留测试"]
    assert before == after
