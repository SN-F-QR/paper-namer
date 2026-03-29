import io
import json
from pathlib import Path

from lib import extractor


class _FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_extract_metadata_doi_crossref(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    monkeypatch.setattr(
        extractor, "_extract_doi_with_pdf2doi", lambda _: "10.1000/test"
    )

    payload = {
        "message": {
            "title": ["A Good Paper"],
            "abstract": "<jats:p>Important finding.</jats:p>",
            "issued": {"date-parts": [[2024, 1, 1]]},
        }
    }

    monkeypatch.setattr(
        extractor, "urlopen", lambda *args, **kwargs: _FakeResponse(payload)
    )

    meta = extractor.extract_metadata(pdf, crossref_timeout=1)
    assert meta["source"] == "crossref"
    assert meta["title"] == "A Good Paper"
    assert meta["abstract"] == "Important finding."
    assert meta["year"] == "2024"


def test_extract_metadata_pymupdf_fallback(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    monkeypatch.setattr(extractor, "_extract_doi_with_pdf2doi", lambda _: None)

    class _FakePage:
        def get_text(self, mode: str):
            assert mode == "dict"
            return {
                "blocks": [
                    {
                        "lines": [
                            {
                                "spans": [
                                    {"size": 20, "text": "Largest Title"},
                                    {"size": 10, "text": "small text"},
                                ]
                            }
                        ]
                    }
                ]
            }

    class _FakeDoc:
        def __len__(self):
            return 1

        def __getitem__(self, idx: int):
            assert idx == 0
            return _FakePage()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeFitz:
        @staticmethod
        def open(path):
            assert path == pdf
            return _FakeDoc()

    monkeypatch.setitem(__import__("sys").modules, "fitz", _FakeFitz)

    meta = extractor.extract_metadata(pdf)
    assert meta["source"] == "pymupdf"
    assert meta["title"] == "Largest Title"
    assert meta["year"] == "未知"
