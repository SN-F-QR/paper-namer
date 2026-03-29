import sys
from pathlib import Path
from typing import Any

from lib import extractor


class _FakePage:
    def __init__(self, text_dict: dict[str, Any]) -> None:
        self._text_dict = text_dict

    def get_text(self, mode: str) -> dict[str, Any]:
        assert mode == "dict"
        return self._text_dict


class _FakeDoc:
    def __init__(self, page_count: int, first_page_dict: dict[str, Any]) -> None:
        self._page_count = page_count
        self._first_page = _FakePage(first_page_dict)

    def __len__(self) -> int:
        return self._page_count

    def __getitem__(self, idx: int) -> _FakePage:
        assert idx == 0
        return self._first_page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_extract_pdf_text_uses_first_three_pages(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    captured: dict[str, Any] = {}
    first_page_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {"size": 22, "text": "Largest Title"},
                            {"size": 10, "text": "some content"},
                        ]
                    }
                ]
            }
        ]
    }

    class _FakeFitz:
        @staticmethod
        def open(path: Path) -> _FakeDoc:
            assert path == pdf
            return _FakeDoc(page_count=5, first_page_dict=first_page_dict)

    class _FakePyMuPDF4LLM:
        @staticmethod
        def to_markdown(doc: _FakeDoc, *, pages: list[int], **kwargs: Any) -> str:
            captured["doc"] = doc
            captured["pages"] = pages
            return "# Largest Title\n\nAbstract text"

    monkeypatch.setitem(sys.modules, "fitz", _FakeFitz)
    monkeypatch.setitem(sys.modules, "pymupdf4llm", _FakePyMuPDF4LLM)

    extracted = extractor.extract_pdf_text(pdf, max_pages=3)
    assert captured["pages"] == [0, 1, 2]
    assert extracted["source"] == "pymupdf4llm"
    assert extracted["fallback_title"] == "Largest Title"
    assert "Abstract" in extracted["text"]


def test_extract_pdf_text_single_page_pdf(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    captured: dict[str, Any] = {}

    first_page_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {"size": 20, "text": "Single Page Title"},
                        ]
                    }
                ]
            }
        ]
    }

    class _FakeFitz:
        @staticmethod
        def open(path: Path) -> _FakeDoc:
            assert path == pdf
            return _FakeDoc(page_count=1, first_page_dict=first_page_dict)

    class _FakePyMuPDF4LLM:
        @staticmethod
        def to_markdown(doc: _FakeDoc, *, pages: list[int], **kwargs: Any) -> str:
            captured["pages"] = pages
            return "single page text"

    monkeypatch.setitem(sys.modules, "fitz", _FakeFitz)
    monkeypatch.setitem(sys.modules, "pymupdf4llm", _FakePyMuPDF4LLM)

    extracted = extractor.extract_pdf_text(pdf, max_pages=3)
    assert captured["pages"] == [0]
    assert extracted["fallback_title"] == "Single Page Title"


def test_extract_pdf_text_low_density_warning(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    first_page_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {"size": 18, "text": "Recovered Title"},
                        ]
                    }
                ]
            }
        ]
    }

    class _FakeFitz:
        @staticmethod
        def open(path: Path) -> _FakeDoc:
            assert path == pdf
            return _FakeDoc(page_count=2, first_page_dict=first_page_dict)

    class _FakePyMuPDF4LLM:
        @staticmethod
        def to_markdown(doc: _FakeDoc, *, pages: list[int], **kwargs: Any) -> str:
            return "tiny"

    monkeypatch.setitem(sys.modules, "fitz", _FakeFitz)
    monkeypatch.setitem(sys.modules, "pymupdf4llm", _FakePyMuPDF4LLM)

    class _Logger:
        def __init__(self):
            self.calls: list[str] = []

        def warning(self, msg: str, *args: object) -> None:
            self.calls.append(msg % args)

    logger = _Logger()
    extracted = extractor.extract_pdf_text(pdf, logger=logger)

    assert extracted["fallback_title"] == "Recovered Title"
    assert any("Low text density" in msg for msg in logger.calls)
