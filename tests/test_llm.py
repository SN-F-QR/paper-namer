from lib.extractor import PaperMeta
from lib.errors import LLMError
from lib.llm import (
    LLMConfig,
    extract_metadata_from_text,
    generate_chinese_metadata,
)


def test_extract_metadata_unavailable_fallback(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    def _raise(*args, **kwargs):
        raise LLMError("connection refused")

    monkeypatch.setattr("lib.llm._ollama_chat_json", _raise)

    meta = extract_metadata_from_text(
        "title abstract content",
        fallback_title="2602.22186v1",
        config=config,
    )
    assert meta["source"] == "fallback"
    assert meta["title"] == "2602.22186v1"
    assert meta["abstract"] == ""
    assert meta["year"] == "未知"


def test_extract_metadata_json_retry_then_fallback(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    responses = iter(["{bad-json", '{"unexpected": "shape"}'])
    calls = {"count": 0}

    def _mock_chat(*args, **kwargs):
        calls["count"] += 1
        return next(responses)

    monkeypatch.setattr("lib.llm._ollama_chat_json", _mock_chat)

    meta = extract_metadata_from_text(
        "title abstract content",
        fallback_title="Fallback Title",
        config=config,
        strict=False,
    )

    assert calls["count"] == 2
    assert meta["source"] == "fallback"
    assert meta["title"] == "Fallback Title"


def test_extract_metadata_success(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    monkeypatch.setattr(
        "lib.llm._ollama_chat_json",
        lambda *args, **kwargs: (
            '{"title":"A Good Paper","abstract":"A short abstract","venue":"CHI","year":"2024"}'
        ),
    )

    meta = extract_metadata_from_text(
        "content",
        fallback_title="Fallback",
        config=config,
        strict=True,
    )

    assert meta["source"] == "llm"
    assert meta["title"] == "A Good Paper"
    assert meta["abstract"] == "A short abstract"
    assert meta["year"] == "CHI24"


def test_extract_metadata_maps_full_venue_name_to_abbr(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
        venue_aliases=(("user interface software and technology", "UIST"),),
    )

    monkeypatch.setattr(
        "lib.llm._ollama_chat_json",
        lambda *args, **kwargs: (
            '{"title":"A Good Paper","abstract":"A short abstract","venue":"ACM Symposium on User Interface Software and Technology","year":"2019"}'
        ),
    )

    meta = extract_metadata_from_text(
        "content",
        fallback_title="Fallback",
        config=config,
        strict=True,
    )

    assert meta["source"] == "llm"
    assert meta["year"] == "UIST19"


def test_extract_metadata_accepts_lowercase_venue_abbr(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    monkeypatch.setattr(
        "lib.llm._ollama_chat_json",
        lambda *args, **kwargs: (
            '{"title":"A Good Paper","abstract":"A short abstract","venue":"chi","year":"2024"}'
        ),
    )

    meta = extract_metadata_from_text(
        "content",
        fallback_title="Fallback",
        config=config,
        strict=True,
    )

    assert meta["source"] == "llm"
    assert meta["year"] == "CHI24"


def test_extract_metadata_missing_venue_uses_unk_prefix(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    monkeypatch.setattr(
        "lib.llm._ollama_chat_json",
        lambda *args, **kwargs: (
            '{"title":"A Good Paper","abstract":"A short abstract","year":"2024"}'
        ),
    )

    meta = extract_metadata_from_text(
        "content",
        fallback_title="Fallback",
        config=config,
        strict=True,
    )

    assert meta["source"] == "llm"
    assert meta["year"] == "UNK24"


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
        "source": "llm",
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
        "source": "llm",
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
