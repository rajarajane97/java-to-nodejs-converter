from __future__ import annotations

"""Configuration utilities for Java2NodeAI.

Loads defaults, merges optional YAML/JSON config files, and applies environment
variable overrides. This layered approach enables secure secret handling and
portable defaults while allowing per-environment customization without code
changes.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


@dataclass
class ReaderConfig:
    """File reader settings.

    - exclude_globs: allow pruning large or irrelevant directories/files to
      improve performance and avoid sending secrets to LLMs.
    - max_file_size_kb: safety limit to skip giant files (e.g., bundled assets).
    - categorization_rules: simple heuristics to label common layers.
    """
    exclude_globs: List[str] = field(default_factory=lambda: [
        "**/build/**",
        "**/out/**",
        "**/target/**",
        "**/.mvn/**",
        "**/.idea/**",
        "**/.git/**",
        "**/*.min.js",
        "**/*.map",
        "**/*.class",
        "**/*.jar",
        "**/*.war",
        "**/*.ear",
        "**/*.zip",
        "**/*.bin",
    ])
    max_file_size_kb: int = 512
    categorization_rules: List[str] = field(default_factory=lambda: [
        "Controller",
        "Service",
        "Repository",
        "DAO",
        "Model",
        "Util",
        "Config",
        "Filter",
        "Interceptor",
    ])


@dataclass
class LLMConfig:
    """LLM provider configuration.

    Provider can be "local" (no network, echo fallback), "openai", or
    "anthropic". Token budgets are configurable to manage costs and latency.
    """
    provider: str = "local"  # local|openai|anthropic|google
    model: str = "gpt-4o-mini"
    max_input_tokens: int = 12000
    max_output_tokens: int = 1500
    temperature: float = 0.1


@dataclass
class LoggingConfig:
    """Logging level configuration."""
    level: str = "INFO"
    file_path: str = "Output/Reports/app.log"


@dataclass
class AppConfig:
    """Aggregated application configuration tree."""
    reader: ReaderConfig = field(default_factory=ReaderConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _load_from_path(path: Path) -> Dict[str, object]:
    """Load config from the given path as YAML or JSON.

    Rationale: We don't want to force a single format. Try YAML first (more
    ergonomic for comments), then JSON as a fallback.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"} and yaml is not None:
        return dict(yaml.safe_load(text) or {})
    if path.suffix.lower() == ".json":
        return json.loads(text)
    # Try YAML first if available
    if yaml is not None:
        try:
            return dict(yaml.safe_load(text) or {})
        except Exception:
            pass
    # Fallback JSON
    try:
        return json.loads(text)
    except Exception:
        return {}


def _merge_dict(base: Dict[str, object], override: Dict[str, object]) -> Dict[str, object]:
    """Deep-merge two dicts with override precedence.

    Only recurses into nested dicts; lists and scalars are replaced.
    """
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge_dict(result[k], v)  # type: ignore[index]
        else:
            result[k] = v
    return result


def load_config(config_path: Optional[Union[str, Path]] = None, override_llm: Optional[str] = None) -> AppConfig:
    """Load application config with optional path and provider override.

    Precedence (lowest to highest):
      1) built-in defaults
      2) discovered config file (yaml/json)
      3) environment variables
      4) CLI override for provider
    """
    # Load from default discovery locations
    discovered: List[Path] = []
    if config_path:
        discovered.append(Path(config_path))
    else:
        for candidate in [
            Path("config.yaml"),
            Path("config.yml"),
            Path("config.json"),
            Path("ai2node.config.yaml"),
        ]:
            if candidate.exists():
                discovered.append(candidate)
                break

    # Start with defaults
    data: Dict[str, object] = {}
    for path in discovered:
        data = _merge_dict(data, _load_from_path(path))

    # Env overrides for secrets/provider
    env_provider = os.getenv("AI2NODE_LLM_PROVIDER")
    env_model = os.getenv("AI2NODE_LLM_MODEL")
    env_max_in = os.getenv("AI2NODE_LLM_MAX_INPUT_TOKENS")
    env_max_out = os.getenv("AI2NODE_LLM_MAX_OUTPUT_TOKENS")
    env_temp = os.getenv("AI2NODE_LLM_TEMPERATURE")
    env_log_level = os.getenv("AI2NODE_LOG_LEVEL")
    env_log_file = os.getenv("AI2NODE_LOG_FILE")

    if env_provider or env_model or env_max_in or env_max_out or env_temp:
        llm_overrides: Dict[str, object] = {}
        if env_provider:
            llm_overrides["provider"] = env_provider
        if env_model:
            llm_overrides["model"] = env_model
        if env_max_in:
            llm_overrides["max_input_tokens"] = int(env_max_in)
        if env_max_out:
            llm_overrides["max_output_tokens"] = int(env_max_out)
        if env_temp:
            llm_overrides["temperature"] = float(env_temp)
        data = _merge_dict(data, {"llm": llm_overrides})

    if env_log_level or env_log_file:
        log_over = {}
        if env_log_level:
            log_over["level"] = env_log_level
        if env_log_file:
            log_over["file_path"] = env_log_file
        data = _merge_dict(data, {"logging": log_over})

    # Explicit CLI override has highest precedence
    if override_llm:
        data = _merge_dict(data, {"llm": {"provider": override_llm}})

    # Construct dataclasses
    reader_cfg = ReaderConfig(**dict(data.get("reader", {})))  # type: ignore[arg-type]
    llm_cfg = LLMConfig(**dict(data.get("llm", {})))  # type: ignore[arg-type]
    logging_cfg = LoggingConfig(**dict(data.get("logging", {})))  # type: ignore[arg-type]

    return AppConfig(reader=reader_cfg, llm=llm_cfg, logging=logging_cfg)
