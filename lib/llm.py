from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from ollama import ChatResponse, Client
from pydantic import BaseModel

from .errors import LLMBackendUnavailableError, LLMError
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
    venue_aliases: tuple[tuple[str, str], ...] = field(default_factory=tuple)


class ExtractedMetadata(BaseModel):
    title: str
    abstract: str
    venue: str
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


def _to_one_line(text: str, *, max_len: int = 600) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3]}..."


YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
VENUE_STOPWORDS = {
    "a",
    "an",
    "and",
    "annual",
    "conference",
    "for",
    "in",
    "international",
    "journal",
    "of",
    "on",
    "proceedings",
    "symposium",
    "the",
    "transactions",
    "workshop",
}


def _normalize_year(year_text: str) -> str:
    matched = YEAR_PATTERN.search(year_text or "")
    if not matched:
        return ""
    return matched.group(0)


def _normalize_venue_abbr(
    venue_text: str,
    venue_aliases: tuple[tuple[str, str], ...],
) -> str:
    compact = " ".join((venue_text or "").split())
    if not compact:
        return ""

    # Handle direct acronym responses like "chi" / "uist" first.
    compact_token = re.sub(r"[^A-Za-z0-9]", "", compact)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,9}", compact_token):
        candidate = re.sub(r"(?:19|20)\d{2}$|\d{2}$", "", compact_token.upper())
        if len(candidate) >= 2 and not candidate.isdigit():
            return candidate

    lowered = compact.lower()
    for alias, abbr in venue_aliases:
        if alias in lowered:
            return abbr

    bracketed = re.search(r"\(([A-Za-z][A-Za-z0-9]{1,9})\)", compact)
    if bracketed:
        candidate = re.sub(r"[^A-Za-z0-9]", "", bracketed.group(1)).upper()
        candidate = re.sub(r"(?:19|20)\d{2}$|\d{2}$", "", candidate)
        if len(candidate) >= 2:
            return candidate

    token_pattern = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
    for token in token_pattern.findall(compact):
        candidate = re.sub(r"(?:19|20)\d{2}$|\d{2}$", "", token.upper())
        if len(candidate) >= 2 and not candidate.isdigit():
            return candidate

    words = re.findall(r"[A-Za-z]+", compact)
    if not words:
        return ""

    meaningful = [word for word in words if word.lower() not in VENUE_STOPWORDS]
    selected = meaningful or words
    initials = "".join(word[0].upper() for word in selected[:5])
    if len(initials) < 2:
        return selected[0][:4].upper()
    return initials[:8]


def _build_venue_year_tag(
    venue_text: str,
    year_text: str,
    venue_aliases: tuple[tuple[str, str], ...],
) -> str:
    year_full = _normalize_year(year_text) or _normalize_year(venue_text)
    venue_abbr = _normalize_venue_abbr(venue_text, venue_aliases)

    if not venue_abbr and not year_full:
        return "未知"
    if not venue_abbr:
        venue_abbr = "UNK"
    if not year_full:
        return f"{venue_abbr}XX"
    return f"{venue_abbr}{year_full[-2:]}"


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
            "[LLM][request] host=%s model=%s timeout=%ss prompt=%s",
            host,
            model,
            timeout_seconds,
            _to_one_line(prompt),
        )
    try:
        response: ChatResponse = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=response_schema,
            think=False,
            options={"temperature": 0.2, "num_ctx": 8192},
        )
    except Exception as exc:
        raise LLMBackendUnavailableError(f"Ollama unavailable: {exc}") from exc

    content = response.message.content or "{}"
    if debug:
        LOGGER.info(
            "[LLM][response] model=%s chars=%d content=%s",
            model,
            len(content),
            _to_one_line(content),
        )
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


def _parse_metadata(
    content: str,
    venue_aliases: tuple[tuple[str, str], ...],
) -> tuple[str, str, str]:
    try:
        data = ExtractedMetadata.model_validate_json(_normalize_json_text(content))
        title = data.title.strip()
        abstract = data.abstract.strip()
        venue_year = _build_venue_year_tag(
            data.venue.strip(),
            data.year.strip(),
            venue_aliases,
        )
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
        venue_text = _extract_first_string(
            payload,
            (
                ("venue",),
                ("venue_abbr",),
                ("conference",),
                ("journal",),
                ("publication",),
                ("properties", "venue", "title"),
                ("properties", "venue_abbr", "title"),
                ("properties", "conference", "title"),
                ("properties", "journal", "title"),
            ),
        )
        year_text = _extract_first_string(
            payload,
            (
                ("year",),
                ("properties", "year", "title"),
            ),
        )
        venue_year = _build_venue_year_tag(venue_text, year_text, venue_aliases)

    if not title:
        raise LLMError("title missing from metadata response")

    return title, abstract, venue_year


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
        "要求：venue 输出会议或期刊缩写（如 CHI、UIST、ISMAR、VR，未知填 UNK）；"
        "year 输出4位年份（未知填'未知'）；title 保留原文语言；abstract 尽量提取摘要正文。\n"
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
            title, abstract, year = _parse_metadata(content, config.venue_aliases)
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

    if isinstance(last_error, LLMBackendUnavailableError):
        raise last_error

    if strict:
        if isinstance(last_error, LLMError):
            raise last_error
        if last_error is not None:
            raise LLMError(f"Metadata extraction failed: {last_error}") from last_error
        raise LLMError("Metadata extraction failed")

    return fallback_meta


def _translate_title(title: str, abstract: str, config: LLMConfig) -> str:
    title_for_prompt = " ".join((title or "").split())[:400]
    abstract_for_prompt = " ".join((abstract or "").split())[:3000]
    title_schema = TranslatedTitle.model_json_schema()
    prompt = (
        "请把下面论文标题翻译成中文。请严格遵守以下要求：\n"
        "1. 简明扼要，不超过30字，必须适合作文件名。\n"
        "2. 去除冒号、问号、斜杠等不合法或不建议用作文件名的特殊符号（可用空格或连字符 '-' 替代）。\n"
        "3. 保留框架名、专有名词或缩写（如 AgentAR、LLM 等）以增强辨识度，不要强行翻译。\n"
        "4. 必须结合摘要理解术语语义与词性（如 Authoring 常作动词“创作/构建/编写”，不要生硬翻译为“作者”）。\n"
        "5. 若标题存在歧义，以摘要中的研究任务、方法与对象为准。\n\n"
        "【参考示例】\n"
        "原标题：AgentAR: A Framework for Authoring Augmented Reality Experiences\n"
        "翻译为：AgentAR 创作增强现实体验的框架\n\n"
        "原标题：Do Large Language Models Understand Graph Topology?\n"
        "翻译为：大语言模型是否理解图拓扑\n\n"
        "原标题：Direct Preference Optimization: Your Language Model is Secretly a Reward Model\n"
        "翻译为：DPO 直接偏好优化 你的语言模型暗中是个奖励模型\n\n"
        "只输出一个合法的 JSON 对象，不要使用 Markdown 代码块，不要输出任何额外文本。\n"
        f"JSON Schema: {json.dumps(title_schema, ensure_ascii=False)}\n\n"
        f"原标题：{title_for_prompt}\n"
        f"摘要：{abstract_for_prompt}"
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
        "并且请结合摘要语境来消歧，不要仅做字面直译。\n"
        "只输出一个合法 JSON 对象，不要使用 Markdown 代码块，不要输出任何额外文本。\n"
        f"JSON Schema: {json.dumps(title_schema, ensure_ascii=False)}\n\n"
        f"原标题：{title_for_prompt}\n"
        f"摘要：{abstract_for_prompt}"
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
        zh_title = _translate_title(meta["title"], meta.get("abstract", ""), config)
    except LLMBackendUnavailableError:
        raise
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
    except LLMBackendUnavailableError:
        raise
    except LLMError as exc:
        if logger:
            logger.warning("Summary fallback: %s", exc)
        if strict:
            raise
        summary = fallback_summary
    return zh_title, summary
