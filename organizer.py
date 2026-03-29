from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import tomllib

from lib.errors import OrganizerError
from lib.extractor import extract_pdf_text
from lib.index_writer import append_index_entry
from lib.llm import LLMConfig, extract_metadata_from_text, generate_chinese_metadata
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
    extract_pages: int,
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
        extracted = extract_pdf_text(
            pdf_path,
            max_pages=extract_pages,
            logger=logger,
        )
        meta = extract_metadata_from_text(
            extracted["text"],
            fallback_title=extracted["fallback_title"],
            config=llm_config,
            logger=logger,
        )

        if meta["source"] == "fallback":
            zh_title = meta["title"]
            summary = "未生成摘要"
        else:
            zh_title, summary = generate_chinese_metadata(
                meta,
                config=llm_config,
                add_summary=add_summary,
                logger=logger,
            )

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

    inbox_raw = paths.get("inbox_dir")
    log_file_raw = paths.get("log_file")
    if not inbox_raw or not log_file_raw:
        raise OrganizerError(
            "Missing required config: paths.inbox_dir and paths.log_file"
        )

    translate_model_raw = llm.get("translate_model")
    summary_model_raw = llm.get("summary_model")
    if not translate_model_raw or not summary_model_raw:
        raise OrganizerError(
            "Missing required config: llm.translate_model and llm.summary_model"
        )

    metadata_model_raw = llm.get("metadata_model")

    inbox_dir = _expand(str(inbox_raw))
    log_file = _expand(str(log_file_raw))
    dry_run = bool(args.dry_run or behavior.get("dry_run", False))
    extract_pages = int(behavior.get("extract_pages", 3))
    write_index = bool(behavior.get("write_index", True))
    add_summary = bool(behavior.get("add_summary", True))

    logger = setup_logger(log_file)
    logger.info("Start paper-organizer, dry_run=%s", dry_run)

    llm_config = LLMConfig(
        enabled=bool(llm.get("enabled", True)),
        translate_model=str(translate_model_raw),
        summary_model=str(summary_model_raw),
        ollama_host=str(llm.get("ollama_host", "http://localhost:11434")),
        metadata_model=str(metadata_model_raw or summary_model_raw),
        request_timeout=int(llm.get("request_timeout", 60)),
        debug=bool(llm.get("debug", False)),
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
            extract_pages=extract_pages,
            llm_config=llm_config,
            add_summary=add_summary,
            write_index=write_index,
            dry_run=dry_run,
        )

    logger.info("Done. total=%d", len(pdf_files))


if __name__ == "__main__":
    main()
