from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ollama import ChatResponse, Client

from .errors import LLMError
from .extractor import PaperMeta


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    translate_model: str
    summary_model: str
    ollama_host: str


def _truncate_for_filename(title: str, max_len: int = 50) -> str:
    clean = " ".join((title or "untitled").split())
    return clean[:max_len].strip() or "untitled"


def _ollama_chat_json(host: str, model: str, prompt: str) -> dict[str, Any]:
    client = Client(host=host)
    try:
        response: ChatResponse = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
    except Exception as exc:
        raise LLMError(f"Ollama unavailable: {exc}") from exc

    content = response.message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError("LLM returned non-JSON response") from exc


def _translate_title(title: str, config: LLMConfig) -> str:
    prompt = (
        "请把下面论文标题翻译成中文，返回 JSON："
        '{"title_zh":"..."}。要求：不超过30字，适合作文件名，不含特殊符号。\n\n'
        f"原标题：{title}"
    )
    data = _ollama_chat_json(config.ollama_host, config.translate_model, prompt)
    translated = str(data.get("title_zh", "")).strip()
    if not translated:
        raise LLMError("title_zh missing from LLM response")
    return translated


def _summarize(title: str, abstract: str, config: LLMConfig) -> str:
    prompt = (
        "请根据论文信息输出 2-3 句中文核心贡献总结，返回 JSON："
        '{"summary":"..."}。\n\n'
        f"标题：{title}\n摘要：{abstract}"
    )
    data = _ollama_chat_json(config.ollama_host, config.summary_model, prompt)
    summary = str(data.get("summary", "")).strip()
    if not summary:
        raise LLMError("summary missing from LLM response")
    return summary


def generate_chinese_metadata(
    meta: PaperMeta,
    *,
    config: LLMConfig,
    add_summary: bool,
    logger: logging.Logger | None = None,
) -> tuple[str, str]:
    fallback_title = _truncate_for_filename(meta["title"])
    fallback_summary = "未生成摘要"

    if not config.enabled:
        return fallback_title, fallback_summary

    try:
        zh_title = _translate_title(meta["title"], config)
    except LLMError as exc:
        if logger:
            logger.warning("Title translation fallback: %s", exc)
        return fallback_title, fallback_summary

    if not add_summary or not meta.get("abstract"):
        return zh_title, fallback_summary

    try:
        summary = _summarize(meta["title"], meta["abstract"], config)
    except LLMError as exc:
        if logger:
            logger.warning("Summary fallback: %s", exc)
        summary = fallback_summary
    return zh_title, summary
