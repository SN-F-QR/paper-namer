from lib.extractor import PaperMeta
from lib.errors import LLMBackendUnavailableError, LLMError
from lib.llm import (
    LLMConfig,
    _lmstudio_chat_json,
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


def test_extract_metadata_backend_unavailable_raises(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    calls = {"count": 0}

    def _raise_backend(*args, **kwargs):
        calls["count"] += 1
        raise LLMBackendUnavailableError("Ollama unavailable: 404")

    monkeypatch.setattr("lib.llm._ollama_chat_json", _raise_backend)

    try:
        extract_metadata_from_text(
            "title abstract content",
            fallback_title="Fallback Title",
            config=config,
        )
        raise AssertionError("Expected backend unavailable error to be raised")
    except LLMBackendUnavailableError:
        pass

    assert calls["count"] == 2


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


def test_lmstudio_backend_uses_lmstudio_calls(monkeypatch):
    config = LLMConfig(
        enabled=True,
        backend="lmstudio",
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )

    responses = iter(
        [
            '{"title":"A Good Paper","abstract":"A short abstract","venue":"CHI","year":"2024"}',
            '{"title_zh":"LM Studio 中文标题"}',
            '{"summary":"本文总结了 LM Studio 后端的工作流程。"}',
        ]
    )
    calls: list[str] = []

    def _raise_ollama(*args, **kwargs):
        raise AssertionError("Ollama backend should not be used when backend=lmstudio")

    def _mock_lmstudio(*args, **kwargs):
        calls.append(args[0] if args else "")
        return next(responses)

    monkeypatch.setattr("lib.llm._ollama_chat_json", _raise_ollama)
    monkeypatch.setattr("lib.llm._lmstudio_chat_json", _mock_lmstudio)

    meta = extract_metadata_from_text(
        "content",
        fallback_title="Fallback",
        config=config,
        strict=True,
    )

    title, summary = generate_chinese_metadata(
        meta,
        config=config,
        add_summary=True,
        strict=True,
    )

    assert meta["source"] == "llm"
    assert meta["year"] == "CHI24"
    assert title == "LM Studio 中文标题"
    assert summary == "本文总结了 LM Studio 后端的工作流程。"
    assert len(calls) == 3


def test_lmstudio_model_falls_back_to_google_prefixed_name(monkeypatch):
    calls: list[str] = []

    class FakeResponse:
        content = '{"title_zh":"LM Studio 中文标题"}'

    class FakeModel:
        def respond(self, history, **kwargs):
            return FakeResponse()

    def _mock_llm(model_key: str, *args, **kwargs):
        calls.append(model_key)
        if model_key == "gemma-4-e4b":
            raise Exception("Model not found: gemma-4-e4b")
        if model_key == "google/gemma-4-e4b":
            return FakeModel()
        raise AssertionError(f"Unexpected model key: {model_key}")

    monkeypatch.setattr("lib.llm.lms.llm", _mock_llm)

    content = _lmstudio_chat_json(
        "gemma-4-e4b",
        "请翻译标题",
        timeout_seconds=5,
    )

    assert calls == ["gemma-4-e4b", "google/gemma-4-e4b"]
    assert content == '{"title_zh":"LM Studio 中文标题"}'


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


def test_title_translation_prompt_includes_abstract(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )
    meta: PaperMeta = {
        "title": "Authoring Tools for XR Learning",
        "abstract": "We present a system for authoring XR lessons with teacher-in-the-loop design.",
        "year": "2026",
        "source": "llm",
    }

    captured_prompts: list[str] = []

    def _mock_chat(*args, **kwargs):
        prompt = kwargs.get("prompt")
        if not isinstance(prompt, str) and len(args) >= 3 and isinstance(args[2], str):
            prompt = args[2]
        if isinstance(prompt, str):
            captured_prompts.append(prompt)
        return '{"title_zh": "XR学习课程创作工具"}'

    monkeypatch.setattr("lib.llm._ollama_chat_json", _mock_chat)

    title, summary = generate_chinese_metadata(
        meta,
        config=config,
        add_summary=False,
        strict=True,
    )

    assert title == "XR学习课程创作工具"
    assert summary == "未生成摘要"
    assert captured_prompts
    assert "结合摘要" in captured_prompts[0]
    assert "摘要：We present a system for authoring XR lessons" in captured_prompts[0]


def test_generate_chinese_metadata_backend_unavailable_raises(monkeypatch):
    config = LLMConfig(
        enabled=True,
        translate_model="qwen3.5:0.8b",
        summary_model="qwen3.5:9b",
        ollama_host="http://localhost:11434",
    )
    meta: PaperMeta = {
        "title": "A Good Paper",
        "abstract": "Some abstract",
        "year": "CHI24",
        "source": "llm",
    }

    def _raise_backend(*args, **kwargs):
        raise LLMBackendUnavailableError("Ollama unavailable: timeout")

    monkeypatch.setattr("lib.llm._ollama_chat_json", _raise_backend)

    try:
        generate_chinese_metadata(
            meta,
            config=config,
            add_summary=True,
            strict=False,
        )
        raise AssertionError("Expected backend unavailable error to be raised")
    except LLMBackendUnavailableError:
        pass
