# AGENTS.md — paper-organizer

Local automation script that watches `~/Downloads/papers/`, renames messy academic PDFs to
human-readable Chinese titles, and maintains a `_index.md` index file.
Works fully offline via a local Ollama LLM; no external APIs required.

---

## Tech Stack

- **Runtime**: Python 3.11+ managed by [uv](https://github.com/astral-sh/uv)
- **PDF parsing**: [PyMuPDF4LLM](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)
- **LLM**: Ollama (local), called via `ollama` Python client
- **Config**: TOML (`config.toml`)
- **Lint / format**: Ruff

---

## Project Structure

```
paper-organizer/
├── organizer.py        # entry point
├── lib/
│   ├── extractor.py    # PDF text extraction (PyMuPDF, first N pages)
│   ├── llm.py          # Ollama calls: metadata extraction, translation, summary
│   ├── renamer.py      # file renaming + idempotency (.processed)
│   └── index_writer.py # append entries to _index.md
├── config.toml         # user config (paths, models, feature flags)
├── .processed          # JSON hash→filename map; do NOT edit manually
├── tests/
└── logs/organizer.log
```

---

## Commands

```bash
# Install / sync dependencies
uv sync

# Run on inbox directory
uv run python organizer.py

# Dry run (print actions, no renaming)
uv run python organizer.py --dry-run

# Debug a single file
uv run python organizer.py --file ~/Downloads/papers/some.pdf

# Tests
uv run pytest tests/ -v

# Lint + format (run before every commit)
uv run ruff check .
uv run ruff format .
```

---

## Architecture

```
PDF → extractor.py (PyMuPDF4LLM, first N pages)
    → llm.py       (extract metadata → translate title → summarize)
    → renamer.py   (idempotent rename: {year}_{zh_title}.pdf)
    → index_writer (append to _index.md)
```

**Key decisions:**

- Extract raw text from first 3 pages and pass to LLM — no DOI lookup, no CrossRef API
- LLM does three separate calls: (1) extract metadata, (2) translate title, (3) summarize
- When Ollama is unreachable, fall back to largest-font text block as title; no translation
- Idempotency via MD5 of first 4 KB; processed hashes stored in `.processed` (JSON)

**Example Snippets**

```python
# pymupdf4llm
md = pymupdf4llm.to_markdown("input.pdf")

#ollama
from ollama import chat
from pydantic import BaseModel

class Country(BaseModel):
  name: str
  capital: str
  languages: list[str]

response = chat(
  model='gpt-oss',
  messages=[{'role': 'user', 'content': 'Tell me about Canada.'}],
  format=Country.model_json_schema(),
)

country = Country.model_validate_json(response.message.content)
print(country)
```

---

## Code Style

- All public functions must have full type annotations
- Use `pathlib.Path` for all file paths — no string concatenation
- Use `logging` module — no bare `print()`
- All config values read from `config.toml` at runtime — no hardcoded paths or model names
- `lib/` modules raise exceptions; only `organizer.py` catches and logs them
- One task per LLM call — do not combine translation + summarization in a single prompt
- All LLM calls use `format="json"` and expect a structured JSON response

---

## Testing

Tests live in `tests/`. Mock external I/O (Ollama HTTP, file system writes) — no real PDFs or network calls in CI.

Required coverage:

- `test_extractor.py` — normal PDF, single-page PDF, low text density warning
- `test_llm.py` — Ollama unreachable fallback, JSON parse failure retry + fallback
- `test_renamer.py` — `sanitize()`, rename collision (`_2`, `_3`), idempotency skip

---

## Boundaries

- ✅ **Always**: run `ruff check . && ruff format .` before finishing; keep single-file failures non-fatal
- ⚠️ **Ask first**: adding new dependencies; changing `.processed` file schema; changing `config.toml` field names
- 🚫 **Never**: add network calls outside Ollama; add OCR libraries; use `# noqa` / `# type: ignore` to silence lint; overwrite existing renamed files (collision → suffix, not overwrite); hardcode `~/Downloads/papers` or model names
