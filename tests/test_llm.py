from pathlib import Path

from lib.extractor import PaperMeta
from lib.errors import LLMError
from lib.llm import LLMConfig, generate_chinese_metadata


def test_llm_unavailable_fallback(monkeypatch):
    real_pdf = Path(__file__).with_name("2602.22186v1.pdf")
    assert real_pdf.exists()

    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )
    meta: PaperMeta = {
        "title": real_pdf.stem,
        "abstract": "Some abstract",
        "year": "2024",
        "source": "crossref",
    }

    def _raise(*args, **kwargs):
        raise LLMError("connection refused")

    monkeypatch.setattr("lib.llm._ollama_chat_json", _raise)

    title, summary = generate_chinese_metadata(meta, config=config, add_summary=True)
    assert title == "2602.22186v1"
    assert summary == "未生成摘要"
