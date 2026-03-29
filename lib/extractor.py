from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, TypedDict, cast

from .errors import ExtractorError


class ExtractedPDF(TypedDict):
    text: str
    fallback_title: str
    source: str


class PaperMeta(TypedDict):
    title: str
    abstract: str
    year: str
    source: str


def _extract_largest_font_title(text_dict: dict[str, Any]) -> str:
    spans: list[tuple[float, str]] = []
    blocks = text_dict.get("blocks", [])
    if not isinstance(blocks, list):
        blocks = []

    for block in blocks:
        if not isinstance(block, dict):
            continue
        lines = block.get("lines", [])
        if not isinstance(lines, list):
            continue

        for line in lines:
            if not isinstance(line, dict):
                continue
            span_items = line.get("spans", [])
            if not isinstance(span_items, list):
                continue

            for span in span_items:
                if not isinstance(span, dict):
                    continue
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                try:
                    size = float(span.get("size", 0.0))
                except (TypeError, ValueError):
                    size = 0.0
                spans.append((size, text))

    if not spans:
        return ""

    spans.sort(key=lambda item: item[0], reverse=True)

    title = ""
    for _, text in spans:
        lower_text = text.lower()
        # 跳过常见的非标题特征：DOI/arXiv前缀、URL链接、ISSN
        if re.match(
            r"^(?:doi\s*[:/]|arxiv\s*[:/]|10\.\d{4,}/|issn\s*[:/]|https?://|www\.)",
            lower_text,
        ):
            continue
        # 跳过常见的期刊顶部标签
        if lower_text in {"research article", "review article", "article", "letter"}:
            continue
        # 跳过太短的独立数字（如纯页码集合、年份、编号）
        if len(text) < 5 and text.isdigit():
            continue

        title = text
        break

    return title or spans[0][1]


def extract_pdf_text(
    pdf_path: Path,
    *,
    max_pages: int = 3,
    logger: logging.Logger | None = None,
) -> ExtractedPDF:
    if max_pages <= 0:
        raise ExtractorError("max_pages must be positive")

    try:
        import fitz
        import pymupdf4llm
    except Exception as exc:
        raise ExtractorError(f"PDF extraction dependencies unavailable: {exc}") from exc

    try:
        with fitz.open(pdf_path) as doc:
            if len(doc) == 0:
                raise ExtractorError("PDF has no pages")

            page_count = min(len(doc), max_pages)
            page_numbers = list(range(page_count))
            markdown = pymupdf4llm.to_markdown(
                doc,
                pages=page_numbers,
                ignore_images=True,
                show_progress=False,
            )
            raw_text_dict = doc[0].get_text("dict")
    except ExtractorError:
        raise
    except Exception as exc:
        raise ExtractorError(f"PyMuPDF parse failed: {exc}") from exc

    if not isinstance(raw_text_dict, dict):
        raise ExtractorError("PyMuPDF returned unexpected text structure")

    fallback_title = _extract_largest_font_title(cast(dict[str, Any], raw_text_dict))
    if not fallback_title:
        fallback_title = pdf_path.stem

    text = str(markdown or "").strip()
    text_density = len(re.sub(r"\s+", "", text))
    if text_density < 30 and logger:
        logger.warning("Low text density for %s, consider OCR upstream.", pdf_path.name)

    return {
        "text": text,
        "fallback_title": fallback_title,
        "source": "pymupdf4llm",
    }
