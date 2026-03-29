from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path
from typing import TypedDict
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
        from pdf2doi import pdf2doi  # type: ignore
    except Exception:
        return None

    try:
        result = pdf2doi(str(pdf_path))
    except Exception:
        return None

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
        import fitz  # type: ignore
    except Exception as exc:
        raise ExtractorError("PyMuPDF unavailable") from exc

    try:
        with fitz.open(pdf_path) as doc:
            if len(doc) == 0:
                raise ExtractorError("PDF has no pages")
            page = doc[0]
            text_dict = page.get_text("dict")
    except Exception as exc:
        raise ExtractorError(f"PyMuPDF parse failed: {exc}") from exc

    spans: list[tuple[float, str]] = []
    all_text_parts: list[str] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                size = float(span.get("size", 0.0))
                spans.append((size, text))
                all_text_parts.append(text)

    if not spans:
        raise ExtractorError("No text spans detected")

    spans.sort(key=lambda item: item[0], reverse=True)
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
    doi = _extract_doi_with_pdf2doi(pdf_path)
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
