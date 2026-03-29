from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from ollama import ChatResponse, Client
from pydantic import BaseModel

from .errors import LLMError
from .extractor import PaperMeta


LOGGER = logging.getLogger("paper_organizer.llm")


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    translate_model: str
    summary_model: str
    ollama_host: str
    metadata_model: str | None = None
    request_timeout: int = 60
    debug: bool = False


class ExtractedMetadata(BaseModel):
    title: str
    abstract: str
    year: str


class TranslatedTitle(BaseModel):
    title_zh: str


class TranslatedSummary(BaseModel):
    summary: str


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _get_nested_string(payload: dict[str, Any], path: tuple[str, ...]) -> str:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    if not isinstance(current, str):
        return ""
    return current.strip()


def _extract_first_string(
    payload: dict[str, Any], paths: tuple[tuple[str, ...], ...]
) -> str:
    for path in paths:
        value = _get_nested_string(payload, path)
        if value:
            return value
    return ""


def _truncate_for_filename(title: str, max_len: int = 50) -> str:
    clean = " ".join((title or "untitled").split())
    return clean[:max_len].strip() or "untitled"


def _normalize_year(year_text: str) -> str:
    matched = re.search(r"(19|20)\d{2}", year_text or "")
    if not matched:
        return "未知"
    return matched.group(0)


def _ollama_chat_json(
    host: str,
    model: str,
    prompt: str,
    timeout_seconds: int,
    *,
    response_schema: dict[str, Any] | Literal["", "json"] | None = "json",
    debug: bool = False,
) -> str:
    client = Client(host=host, timeout=timeout_seconds)
    if debug:
        LOGGER.info(
            "[LLM][request] "
            f"host={host} model={model} timeout={timeout_seconds}s "
            f"prompt={prompt}",
        )
    try:
        response: ChatResponse = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=response_schema,
            think=False,
            options={"temperature": 0},
        )
    except Exception as exc:
        raise LLMError(f"Ollama unavailable: {exc}") from exc

    content = response.message.content or "{}"
    if debug:
        LOGGER.info("[LLM][response] model=%s content=%s", model, content)
    return content


def _normalize_json_text(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise LLMError("LLM returned empty JSON response")

    candidates = [text]

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidates.append("\n".join(lines).strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidate = text[start : end + 1].strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    raise LLMError("LLM returned invalid JSON payload")


def _parse_metadata(content: str) -> tuple[str, str, str]:
    try:
        data = ExtractedMetadata.model_validate_json(_normalize_json_text(content))
        title = data.title.strip()
        abstract = data.abstract.strip()
        year = _normalize_year(data.year.strip())
    except Exception:
        try:
            payload = json.loads(_normalize_json_text(content))
        except Exception as exc:
            raise LLMError("LLM returned invalid JSON for metadata") from exc

        title = _extract_first_string(
            payload,
            (
                ("title",),
                ("properties", "title", "title"),
            ),
        )
        abstract = _extract_first_string(
            payload,
            (
                ("abstract",),
                ("properties", "abstract", "title"),
            ),
        )
        year = _normalize_year(
            _extract_first_string(
                payload,
                (
                    ("year",),
                    ("properties", "year", "title"),
                ),
            )
        )

    if not title:
        raise LLMError("title missing from metadata response")

    return title, abstract, year


def extract_metadata_from_text(
    raw_text: str,
    *,
    fallback_title: str,
    config: LLMConfig,
    logger: logging.Logger | None = None,
    strict: bool = False,
) -> PaperMeta:
    safe_fallback_title = _truncate_for_filename(fallback_title)
    fallback_meta: PaperMeta = {
        "title": safe_fallback_title,
        "abstract": "",
        "year": "未知",
        "source": "fallback",
    }

    if not config.enabled:
        return fallback_meta

    text_for_prompt = " ".join((raw_text or "").split())[:9000]
    if not text_for_prompt:
        if strict:
            raise LLMError("Empty PDF text for metadata extraction")
        return fallback_meta

    metadata_schema = ExtractedMetadata.model_json_schema()
    prompt = (
        "从给定论文正文片段中提取结构化元信息。\n"
        "要求：year 仅输出4位年份（找不到写'未知'）；title 保留原文语言；abstract 尽量提取摘要正文。\n"
        "只输出一个合法 JSON 对象，不要使用 Markdown 代码块，不要输出任何额外文本。\n"
        f"JSON Schema: {json.dumps(metadata_schema, ensure_ascii=False)}\n\n"
        f"正文片段（来自PDF前几页）：{text_for_prompt}"
    )

    model_name = config.metadata_model or config.summary_model
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            content = _ollama_chat_json(
                config.ollama_host,
                model_name,
                prompt,
                timeout_seconds=config.request_timeout,
                response_schema=metadata_schema,
                debug=config.debug,
            )
            title, abstract, year = _parse_metadata(content)
            return {
                "title": title,
                "abstract": abstract,
                "year": year,
                "source": "llm",
            }
        except Exception as exc:
            last_error = exc
            if attempt == 0 and logger:
                logger.warning("Metadata extraction retry: %s", exc)

    if logger and last_error is not None:
        logger.warning("Metadata extraction fallback: %s", last_error)

    if strict:
        if isinstance(last_error, LLMError):
            raise last_error
        if last_error is not None:
            raise LLMError(f"Metadata extraction failed: {last_error}") from last_error
        raise LLMError("Metadata extraction failed")

    return fallback_meta


def _translate_title(title: str, config: LLMConfig) -> str:
    title_for_prompt = " ".join((title or "").split())[:400]
    title_schema = TranslatedTitle.model_json_schema()
    prompt = (
        "请把下面论文标题翻译成中文。要求：不超过30字，适合作文件名，不含特殊符号。\n"
        "只输出一个合法 JSON 对象，不要使用 Markdown 代码块，不要输出任何额外文本。\n"
        f"JSON Schema: {json.dumps(title_schema, ensure_ascii=False)}\n\n"
        f"原标题：{title_for_prompt}"
    )

    def _request_translation(request_prompt: str) -> str:
        content = _ollama_chat_json(
            config.ollama_host,
            config.translate_model,
            request_prompt,
            timeout_seconds=config.request_timeout,
            response_schema=title_schema,
            debug=config.debug,
        )
        try:
            data = TranslatedTitle.model_validate_json(_normalize_json_text(content))
            translated = data.title_zh.strip()
        except Exception:
            try:
                payload = json.loads(_normalize_json_text(content))
            except Exception as exc:
                raise LLMError("LLM returned invalid JSON for translation") from exc

            translated = _extract_first_string(
                payload,
                (
                    ("title_zh",),
                    ("properties", "title_zh", "title"),
                    ("title",),
                ),
            )

        if not translated:
            raise LLMError("title_zh missing from LLM response")
        return translated

    translated = _request_translation(prompt)
    if _contains_cjk(translated):
        return translated

    retry_prompt = (
        "你上一次输出没有翻译成中文，请重新翻译。\n"
        "要求：title_zh 必须包含至少一个中文汉字；不要原样返回英文标题。\n"
        "只输出一个合法 JSON 对象，不要使用 Markdown 代码块，不要输出任何额外文本。\n"
        f"JSON Schema: {json.dumps(title_schema, ensure_ascii=False)}\n\n"
        f"原标题：{title_for_prompt}"
    )
    translated = _request_translation(retry_prompt)
    if not _contains_cjk(translated):
        raise LLMError("title_zh does not contain Chinese characters")
    return translated


def _summarize(title: str, abstract: str, config: LLMConfig) -> str:
    title_for_prompt = " ".join((title or "").split())[:400]
    abstract_for_prompt = " ".join((abstract or "").split())[:3000]
    summary_schema = TranslatedSummary.model_json_schema()
    prompt = (
        "请根据论文信息输出 2-3 句中文核心贡献总结。\n"
        "只输出一个合法 JSON 对象，不要使用 Markdown 代码块，不要输出任何额外文本。\n"
        f"JSON Schema: {json.dumps(summary_schema, ensure_ascii=False)}\n\n"
        f"标题：{title_for_prompt}\n摘要：{abstract_for_prompt}"
    )
    content = _ollama_chat_json(
        config.ollama_host,
        config.summary_model,
        prompt,
        timeout_seconds=config.request_timeout,
        response_schema=summary_schema,
        debug=config.debug,
    )
    try:
        data = TranslatedSummary.model_validate_json(_normalize_json_text(content))
        summary = data.summary.strip()
    except Exception:
        try:
            payload = json.loads(_normalize_json_text(content))
        except Exception as exc:
            raise LLMError("LLM returned invalid JSON for summary") from exc

        summary = _extract_first_string(
            payload,
            (
                ("summary",),
                ("properties", "summary", "title"),
            ),
        )

    if not summary:
        raise LLMError("summary missing from LLM response")
    return summary


def generate_chinese_metadata(
    meta: PaperMeta,
    *,
    config: LLMConfig,
    add_summary: bool,
    logger: logging.Logger | None = None,
    strict: bool = False,
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
        if strict:
            raise
        return fallback_title, fallback_summary

    if not add_summary or not meta.get("abstract"):
        return zh_title, fallback_summary

    try:
        summary = _summarize(meta["title"], meta["abstract"], config)
    except LLMError as exc:
        if logger:
            logger.warning("Summary fallback: %s", exc)
        if strict:
            raise
        summary = fallback_summary
    return zh_title, summary
