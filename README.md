# Paper Renamer

An offline tool to organize and rename academic PDFs: uses a local Ollama LLM to extract metadata, generate Chinese titles and summaries, rename files, and update an index.

## Features

- Monitor and process `.pdf` files in a directory
- Extract text from the first N pages of a PDF (default: 3)
- Use a local Ollama model to extract year/title and other metadata
- Translate English titles to Chinese and generate summaries
- Rename files to `YEAR_ChineseTitle.pdf` (auto-suffix on collisions)
- Append entries to `_index.md` and use `.processed` to avoid reprocessing

## Quick Start

1. Requirements: Python 3.11+, `uv`, and a local Ollama service.
2. Install dependencies:

```bash
uv sync
```

3. Edit `config.toml` as needed (paths, models, behavior flags).
4. Dry run (no writes):

```bash
uv run python organizer.py --dry-run
```

5. Run for real:

```bash
uv run python organizer.py
```

## Common Commands

```bash
# Process a single PDF
uv run python organizer.py --file ~/Downloads/papers/example.pdf

# Run tests
uv run pytest tests/ -v

# Lint and format
uv run ruff check .
uv run ruff format .
```
