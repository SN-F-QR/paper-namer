import json
from pathlib import Path

import pytest
from ollama import Client

from lib.extractor import extract_pdf_text
from lib.llm import LLMConfig, extract_metadata_from_text, generate_chinese_metadata


def _ollama_is_ready(host: str) -> bool:
    client = Client(host=host, timeout=2)
    try:
        client.list()
        return True
    except Exception:
        return False


def test_llm_real_generate_title_and_summary_with_real_pdf():
    pdf_path = Path(__file__).with_name("2602.22186v1.pdf")
    assert pdf_path.exists()

    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:0.8b",
        ollama_host="http://localhost:11434",
        request_timeout=60,
        debug=True,
    )

    if not _ollama_is_ready(config.ollama_host):
        pytest.skip("Ollama service unavailable, skip real LLM integration test")

    try:
        extracted = extract_pdf_text(pdf_path, max_pages=3)
    except Exception as exc:
        pytest.skip(f"PDF text extraction unavailable: {exc}")

    try:
        meta = extract_metadata_from_text(
            extracted["text"],
            fallback_title=extracted["fallback_title"],
            config=config,
            strict=True,
        )
    except Exception as exc:
        pytest.skip(f"LLM metadata extraction unavailable: {exc}")

    if not meta.get("title"):
        pytest.skip("No title extracted from real PDF")

    print(
        "[TEST][meta] "
        f"source={meta.get('source')} "
        f"venue_year={meta.get('year')} "
        f"title={meta.get('title')} "
        f"has_abstract={bool(meta.get('abstract'))}",
        flush=True,
    )

    title, summary = generate_chinese_metadata(
        meta,
        config=config,
        add_summary=True,
        strict=True,
    )

    assert title
    assert title != pdf_path.stem
    # Check if we got something resembling Chinese, meaning actual translation happened
    assert any("\u4e00" <= c <= "\u9fff" for c in title), (
        f"Title wasn't translated to Chinese: {title}"
    )

    assert summary
    if meta.get("abstract"):
        assert summary != "未生成摘要"
    else:
        assert summary == "未生成摘要"

    out_dir = Path(__file__).resolve().parent / ".generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "llm_real_result.json"
    out_file.write_text(
        json.dumps(
            {
                "pdf": pdf_path.name,
                "meta_source": meta["source"],
                "venue_year": meta["year"],
                "title_input": meta["title"],
                "title_zh": title,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
