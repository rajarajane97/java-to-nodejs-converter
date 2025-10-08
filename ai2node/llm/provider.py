from __future__ import annotations

"""LLM provider abstraction.

This layer decouples the application from specific LLM SDKs. It enables:
- Local echo provider for offline/dev runs
- Cloud providers (OpenAI/Anthropic) when keys are supplied
- Centralized token accounting for reporting and cost control
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional

from ai2node.utils.config import LLMConfig
from ai2node.utils.logging import get_logger


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMProvider:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._logger = get_logger()

    def complete(self, prompt: str) -> LLMResponse:  # pragma: no cover - overridden
        """Synchronous completion interface.

        Implementations should set token counters for accurate reporting. We
        keep the interface minimal to avoid overfitting to any one SDK.
        """
        raise NotImplementedError


class LocalEchoProvider(LLMProvider):
    def complete(self, prompt: str) -> LLMResponse:
        # Lightweight fallback that echoes a trimmed response.
        # Why: Enables deterministic, zero-cost runs during development and in
        # CI where network access/keys are not available.
        output = prompt[: min(len(prompt), self.cfg.max_output_tokens // 2)]
        resp = LLMResponse(text=output, input_tokens=len(prompt), output_tokens=len(output))
        self.total_input_tokens += resp.input_tokens
        self.total_output_tokens += resp.output_tokens
        self._logger.debug(
            "LLM(local) call: model=%s input_chars=%d output_chars=%d",
            self.cfg.model,
            resp.input_tokens,
            resp.output_tokens,
        )
        return resp


class OpenAIProvider(LLMProvider):
    def __init__(self, cfg: LLMConfig) -> None:
        super().__init__(cfg)
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("openai not installed") from exc
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def complete(self, prompt: str) -> LLMResponse:  # pragma: no cover - requires network
        """Call OpenAI chat completions with conservative defaults."""
        resp = self._client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_output_tokens,
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        in_tokens = getattr(usage, "prompt_tokens", len(prompt)) if usage else len(prompt)
        out_tokens = getattr(usage, "completion_tokens", len(text)) if usage else len(text)
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self._logger.info(
            "LLM(openai) call: model=%s prompt_tokens=%s completion_tokens=%s",
            self.cfg.model,
            in_tokens,
            out_tokens,
        )
        return LLMResponse(text=text, input_tokens=in_tokens, output_tokens=out_tokens)


class AnthropicProvider(LLMProvider):
    def __init__(self, cfg: LLMConfig) -> None:
        super().__init__(cfg)
        try:
            import anthropic  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("anthropic not installed") from exc
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def complete(self, prompt: str) -> LLMResponse:  # pragma: no cover - requires network
        """Call Anthropic Messages API with conservative defaults."""
        msg = self._client.messages.create(
            model=self.cfg.model,
            max_tokens=self.cfg.max_output_tokens,
            temperature=self.cfg.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join([blk.text for blk in msg.content if getattr(blk, "text", None)])
        # Anthropics usage fields may vary by SDK; fallback to lengths when missing
        in_tokens = getattr(msg, "input_tokens", len(prompt))
        out_tokens = getattr(msg, "output_tokens", len(text))
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self._logger.info(
            "LLM(anthropic) call: model=%s prompt_tokens=%s completion_tokens=%s",
            self.cfg.model,
            in_tokens,
            out_tokens,
        )
        return LLMResponse(text=text, input_tokens=in_tokens, output_tokens=out_tokens)


def build_provider(cfg: LLMConfig) -> LLMProvider:
    """Factory for LLMProvider instances from configuration."""
    provider = cfg.provider.lower()
    if provider == "local":
        return LocalEchoProvider(cfg)
    if provider == "openai":
        return OpenAIProvider(cfg)
    if provider == "anthropic":
        return AnthropicProvider(cfg)
    return LocalEchoProvider(cfg)


