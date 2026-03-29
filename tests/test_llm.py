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


def test_llm_fenced_json_response_is_parsed(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )
    meta: PaperMeta = {
        "title": "Codesigning Ripplet: an LLM-Assisted Assessment Authoring",
        "abstract": "This paper introduces an LLM-assisted authoring workflow.",
        "year": "2026",
        "source": "crossref",
    }

    responses = iter(
        [
            '```json\n{"title_zh": "LLM辅助评测创作"}\n```',
            '```json\n{"summary": "本文提出一种LLM辅助评测设计流程。"}\n```',
        ]
    )

    def _mock_chat(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr("lib.llm._ollama_chat_json", _mock_chat)

    title, summary = generate_chinese_metadata(
        meta,
        config=config,
        add_summary=True,
        strict=True,
    )

    assert title == "LLM辅助评测创作"
    assert summary == "本文提出一种LLM辅助评测设计流程。"


def test_llm_retry_when_first_title_is_not_chinese(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )
    meta: PaperMeta = {
        "title": "Codesigning Ripplet: an LLM-Assisted Assessment Authoring",
        "abstract": "",
        "year": "2026",
        "source": "pymupdf",
    }

    responses = iter(
        [
            '{"title_zh": "Codesigning Ripplet"}',
            '{"title_zh": "LLM辅助评测协同设计"}',
        ]
    )

    def _mock_chat(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr("lib.llm._ollama_chat_json", _mock_chat)

    title, summary = generate_chinese_metadata(
        meta,
        config=config,
        add_summary=False,
        strict=True,
    )

    assert title == "LLM辅助评测协同设计"
    assert summary == "未生成摘要"
