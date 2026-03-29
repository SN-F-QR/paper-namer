from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .errors import ExtractorError


class PaperMeta(TypedDict):
    title: str
    abstract: str
    year: str
    source: str


def _clean_abstract(raw: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", raw or "")
    squashed = re.sub(r"\s+", " ", no_tags).strip()
    return html.unescape(squashed)


def _extract_doi_with_pdf2doi(pdf_path: Path) -> str | None:
    try:
        from pdf2doi import pdf2doi
    except ModuleNotFoundError:
        return None
    except ImportError as exc:
        raise ExtractorError(f"pdf2doi import failed: {exc}") from exc

    try:
        result = pdf2doi(str(pdf_path))
    except Exception as exc:
        raise ExtractorError(f"pdf2doi parse failed: {exc}") from exc

    if isinstance(result, dict):
        doi = result.get("identifier") or result.get("doi")
        if isinstance(doi, str) and doi.strip():
            return doi.strip()
    return None


def _meta_from_crossref(doi: str, timeout: int) -> PaperMeta:
    url = f"https://api.crossref.org/works/{doi}"
    try:
        with urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ExtractorError(f"CrossRef request failed: {exc}") from exc

    message = payload.get("message", {})
    titles = message.get("title") or []
    title = titles[0].strip() if titles else ""

    abstract = _clean_abstract(message.get("abstract", ""))
    year = "未知"
    issued = message.get("issued", {}).get("date-parts", [])
    if issued and issued[0]:
        year = str(issued[0][0])

    if not title:
        raise ExtractorError("CrossRef response missing title")

    return {
        "title": title,
        "abstract": abstract,
        "year": year,
        "source": "crossref",
    }


def _meta_from_pymupdf(
    pdf_path: Path, logger: logging.Logger | None = None
) -> PaperMeta:
    try:
        import fitz
    except Exception as exc:
        raise ExtractorError("PyMuPDF unavailable") from exc

    try:
        with fitz.open(pdf_path) as doc:
            if len(doc) == 0:
                raise ExtractorError("PDF has no pages")
            page = doc[0]
            raw_text_dict = page.get_text("dict")
    except Exception as exc:
        raise ExtractorError(f"PyMuPDF parse failed: {exc}") from exc

    if not isinstance(raw_text_dict, dict):
        raise ExtractorError("PyMuPDF returned unexpected text structure")

    text_dict = cast(dict[str, Any], raw_text_dict)

    spans: list[tuple[float, str]] = []
    all_text_parts: list[str] = []
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
                all_text_parts.append(text)

    if not spans:
        raise ExtractorError("No text spans detected")

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

    if not title:
        title = spans[0][1]

    text_density = len(" ".join(all_text_parts))
    if text_density < 30 and logger:
        logger.warning("Low text density for %s, consider OCR upstream.", pdf_path.name)

    return {
        "title": title,
        "abstract": "",
        "year": "未知",
        "source": "pymupdf",
    }


def extract_metadata(
    pdf_path: Path,
    *,
    crossref_timeout: int = 5,
    logger: logging.Logger | None = None,
) -> PaperMeta:
    doi: str | None = None
    try:
        doi = _extract_doi_with_pdf2doi(pdf_path)
    except ExtractorError as exc:
        if logger:
            logger.warning(
                "DOI extraction failed for %s, fallback to PyMuPDF: %s",
                pdf_path.name,
                exc,
            )

    if doi:
        try:
            return _meta_from_crossref(doi, timeout=crossref_timeout)
        except ExtractorError as exc:
            if logger:
                logger.warning(
                    "CrossRef failed for %s, fallback to PyMuPDF: %s",
                    pdf_path.name,
                    exc,
                )

    return _meta_from_pymupdf(pdf_path, logger=logger)
