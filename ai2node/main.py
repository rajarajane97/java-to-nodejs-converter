"""
Main CLI entrypoint for Java2NodeAI.

This module orchestrates the high-level pipeline:
- Read and categorize Java files
- Extract structured knowledge (syntax-driven and LLM-enriched)
- Convert sample Controller/Service/DAO into Node.js (Express) scaffolds
- Generate TXT/HTML reports including performance and token usage metrics

"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from ai2node.utils.config import AppConfig, load_config
from ai2node.utils.logging import get_logger
from ai2node.reader.java_reader import JavaCodebaseReader, JavaFileInfo
from ai2node.extractor.pipeline import extract_metadata, save_knowledge
from ai2node.converter.convert import convert_to_express
from ai2node.reporting.generator import generate_reports, TokenUsage
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if present

def _resolve_path(path_str: str) -> Path:
    """Resolve a user-supplied path safely.

    Rationale: We want consistent absolute paths and early error reporting when
    paths do not exist. This avoids downstream failures with less helpful tracebacks.
    """
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    return path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Note: The CLI exposes only the parameters most likely needed by users.
    Advanced configuration belongs in config files and environment variables.
    """
    parser = argparse.ArgumentParser(
        prog="ai2node",
        description=(
            "AI-assisted analyzer to extract knowledge from a Java codebase and convert selected parts to Node.js"
        ),
    )

    parser.add_argument(
        "codebase",
        type=str,
        help="Path to the root of the Java codebase to analyze",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to config file (YAML/JSON). If omitted, defaults are used.",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default=None,
        choices=["local", "openai", "anthropic", "gemini"],
        help="Override configured LLM provider.",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=None,
        help="Additional glob patterns to exclude (space-separated)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path("Output").resolve()),
        help="Output directory (defaults to ./Output)",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        default=None,
        help="Optional max single file size in KB to read",
    )
    parser.add_argument(
        "--categories",
        type=str,
        nargs="*",
        default=None,
        help="Override detection categories (Controller/Service/DAO/etc.)",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Program entrypoint.

    Returns 0 on success. The function is split for testability and to avoid
    side effects during import time.
    """
    args = parse_args(argv)

    config: AppConfig = load_config(args.config, override_llm=args.llm_provider)
    logger = get_logger(config.logging.level, config.logging.file_path)

    codebase_root = _resolve_path(args.codebase)
    output_root = Path(args.out).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    reader = JavaCodebaseReader(
        root_dir=codebase_root,
        exclude_globs=(args.exclude or []) + config.reader.exclude_globs,
        max_file_size_kb=args.max_file_size_kb or config.reader.max_file_size_kb,
        categorization_rules=config.reader.categorization_rules if args.categories is None else args.categories,
    )

    logger.info("Scanning Java codebase: %s", str(codebase_root))
    java_files: List[JavaFileInfo] = reader.scan()
    logger.info("Discovered %d Java files after filtering", len(java_files))

    knowledge_dir = output_root / "Knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filelist_out = knowledge_dir / "files.json"
    with filelist_out.open("w", encoding="utf-8") as f:
        json.dump([finfo.to_dict() for finfo in java_files], f, indent=2)
    logger.info("Saved file inventory: %s", str(filelist_out))

    # Knowledge extraction with optional LLM enrichment
    # LLM provider is created based on configuration; local provider is token-free.
    provider = None
    try:
        from ai2node.llm.provider import build_provider as _build
        provider = _build(config.llm)
    except Exception:
        logger.warning("LLM provider setup failed; proceeding without LLM support")
        provider = None
    logger.info("Using LLM provider: %s", str(provider))
    knowledge = extract_metadata(java_files, config=config, provider=provider)
    knowledge_out = knowledge_dir / "knowledge.json"
    save_knowledge(knowledge, knowledge_out)
    logger.info("Saved knowledge JSON: %s", str(knowledge_out))

    # Conversion (Express)
    converted_dir = Path(args.out).resolve() / "Converted"
    results = convert_to_express(
        java_files,
        templates_dir=Path(__file__).with_name("converter") / "templates" / "express",
        out_dir=converted_dir,
    )

    # Reporting
    reports_dir = Path(args.out).resolve() / "Reports"
    # Collect token usage if provider was used
    if 'provider' in locals() and provider is not None:
        token_usage = TokenUsage(input_tokens=getattr(provider, 'total_input_tokens', 0), output_tokens=getattr(provider, 'total_output_tokens', 0))
    else:
        token_usage = TokenUsage(input_tokens=0, output_tokens=0)
    total_ms = sum(r.elapsed_ms for r in results)
    generate_reports(
        results=results,
        total_ms=total_ms,
        token_usage=token_usage,
        template_dir=Path(__file__).with_name("reporting") / "templates",
        out_dir=reports_dir,
        knowledge=knowledge,
    )
    logger.info("Reports generated at: %s", str(reports_dir))

    return 0


if __name__ == "__main__":
    sys.exit(main())


