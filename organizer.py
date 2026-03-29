from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import tomllib

from lib.errors import OrganizerError
from lib.extractor import extract_metadata
from lib.index_writer import append_index_entry
from lib.llm import LLMConfig, generate_chinese_metadata
from lib.renamer import ProcessedStore, rename_pdf


def _expand(path_value: str) -> Path:
    return Path(path_value).expanduser().resolve()


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("rb") as f:
        return tomllib.load(f)


def setup_logger(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("paper_organizer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rename papers and build index")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no write")
    parser.add_argument("--file", help="Process a single PDF path")
    return parser


def process_one_pdf(
    pdf_path: Path,
    *,
    logger: logging.Logger,
    processed: ProcessedStore,
    crossref_timeout: int,
    llm_config: LLMConfig,
    add_summary: bool,
    write_index: bool,
    dry_run: bool,
) -> None:
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        logger.warning("Skip non-pdf or missing path: %s", pdf_path)
        return

    content_hash = processed.compute_hash(pdf_path)
    if processed.is_processed(content_hash):
        logger.info("Skip already processed: %s", pdf_path.name)
        return

    try:
        meta = extract_metadata(
            pdf_path, crossref_timeout=crossref_timeout, logger=logger
        )
        zh_title, summary = generate_chinese_metadata(
            meta,
            config=llm_config,
            add_summary=add_summary,
            logger=logger,
        )

        if meta["source"] == "pymupdf" and "[ocr]" not in zh_title.lower():
            zh_title = f"{zh_title}[ocr]"

        new_path = rename_pdf(
            pdf_path,
            year=meta["year"],
            zh_title=zh_title,
            processed=processed,
            dry_run=dry_run,
        )

        if write_index:
            append_index_entry(
                index_path=pdf_path.parent / "_index.md",
                year=meta["year"],
                zh_title=zh_title,
                original_title=meta["title"],
                source=meta["source"],
                summary=summary,
                dry_run=dry_run,
            )

        logger.info("Processed: %s -> %s", pdf_path.name, new_path.name)
    except OrganizerError as exc:
        logger.warning("Failed processing %s: %s", pdf_path.name, exc)
    except Exception as exc:  # defensive catch to protect batch processing
        logger.warning("Unexpected error on %s: %s", pdf_path.name, exc)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)

    paths = config.get("paths", {})
    behavior = config.get("behavior", {})
    llm = config.get("llm", {})

    inbox_dir = _expand(paths.get("inbox_dir", "~/papers"))
    log_file = _expand(paths.get("log_file", "~/papers/organizer.log"))
    dry_run = bool(args.dry_run or behavior.get("dry_run", False))
    crossref_timeout = int(behavior.get("crossref_timeout", 5))
    write_index = bool(behavior.get("write_index", True))
    add_summary = bool(behavior.get("add_summary", True))

    logger = setup_logger(log_file)
    logger.info("Start paper-organizer, dry_run=%s", dry_run)

    llm_config = LLMConfig(
        enabled=bool(llm.get("enabled", True)),
        translate_model=str(llm.get("translate_model", "qwen3.5:0.8b")),
        summary_model=str(llm.get("summary_model", "qwen3.5:9b")),
        ollama_host=str(llm.get("ollama_host", "http://localhost:11434")),
    )

    processed_path = config_path.parent / ".processed"
    processed = ProcessedStore(processed_path)

    if args.file:
        pdf_files = [Path(args.file).expanduser().resolve()]
    else:
        pdf_files = sorted(inbox_dir.glob("*.pdf"))

    for pdf_path in pdf_files:
        process_one_pdf(
            pdf_path,
            logger=logger,
            processed=processed,
            crossref_timeout=crossref_timeout,
            llm_config=llm_config,
            add_summary=add_summary,
            write_index=write_index,
            dry_run=dry_run,
        )

    logger.info("Done. total=%d", len(pdf_files))


if __name__ == "__main__":
    main()
