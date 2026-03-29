import json
from pathlib import Path

import pytest
from ollama import Client

from lib.extractor import PaperMeta
from lib.llm import LLMConfig, generate_chinese_metadata


def _ollama_is_ready(host: str) -> bool:
    client = Client(host=host)
    try:
        client.list()
        return True
    except Exception:
        return False


def _read_real_pdf_text(pdf_path: Path) -> str:
    fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed, skip integration")
    with fitz.open(pdf_path) as doc:
        if len(doc) == 0:
            return ""
        text = doc[0].get_text("text")
    return " ".join(text.split())


def test_llm_real_generate_title_and_summary_with_real_pdf():
    pdf_path = Path(__file__).with_name("2602.22186v1.pdf")
    assert pdf_path.exists()

    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    if not _ollama_is_ready(config.ollama_host):
        pytest.skip("Ollama service unavailable, skip real LLM integration test")

    page_text = _read_real_pdf_text(pdf_path)
    if not page_text:
        pytest.skip("No extractable text in PDF for integration test")

    meta: PaperMeta = {
        "title": pdf_path.stem,
        "abstract": page_text[:1600],
        "year": "未知",
        "source": "pymupdf",
    }

    title, summary = generate_chinese_metadata(meta, config=config, add_summary=True)

    assert title
    assert title != pdf_path.stem
    assert summary
    assert summary != "未生成摘要"

    out_dir = Path(__file__).resolve().parent / ".generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "llm_real_result.json"
    out_file.write_text(
        json.dumps(
            {
                "pdf": pdf_path.name,
                "title_input": meta["title"],
                "title_zh": title,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
