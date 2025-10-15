from __future__ import annotations

"""LLM provider abstraction.

This layer decouples the application from specific LLM SDKs. It enables:
- Local echo provider for offline/dev runs - This will be selected if no provider is configured or is set to none 
- Locally running LLMs via OpenAI-compatible API (e.g., LM Studio, Ollama)
- Cloud providers (Gemini/OpenAI/Anthropic) when keys are supplied
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


class LocalRunLLMProvider(LLMProvider):
    def __init__(self, cfg: LLMConfig) -> None:
        super().__init__(cfg)
        self.api_endpoint = os.getenv("LOCAL_LLM_API_ENDPOINT", "http://localhost:1234")
        self.model_name = os.getenv("LOCAL_LLM_MODEL_NAME", "qwen2.5-coder-7b-instruct")
        self.api_key = os.getenv("LOCAL_LLM_API_KEY","lm-studio")
        try:
            import openai  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("openai python library not installed, required for LocalRunLLMProvider") from exc
        
        openai.api_key = self.api_key

        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI(api_key=self.api_key, base_url=self.api_endpoint)
        except Exception:
            # Fall back to using the openai module directly
            self._client = openai

    def complete(self, prompt: str) -> LLMResponse:
        """Call the locally running LLM via the OpenAI Python client.
        """
        if not getattr(self, "_client", None):
            raise RuntimeError("OpenAI client is not initialized for LocalRunLLMProvider")

        model = self.model_name or self.cfg.model
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_output_tokens,
        )

        if not resp or not getattr(resp, 'choices', None) or len(resp.choices) == 0:
            self._logger.error("LLM(local-run) call failed: received empty or malformed response for model=%s endpoint=%s", model, self.api_endpoint)
            # Return a failure response
            return LLMResponse(text="", input_tokens=len(prompt), output_tokens=0)
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        in_tokens = getattr(usage, "prompt_tokens", len(prompt)) if usage else len(prompt)
        out_tokens = getattr(usage, "completion_tokens", len(text)) if usage else len(text)
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self._logger.info(
            "LLM(local-run) call: endpoint=%s model=%s prompt_tokens=%s completion_tokens=%s",
            self.api_endpoint,
            model,
            in_tokens,
            out_tokens,
        )
        return LLMResponse(text=text, input_tokens=in_tokens, output_tokens=out_tokens)


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
    
class GeminiProvider(LLMProvider):
    def __init__(self, cfg: LLMConfig) -> None:
        super().__init__(cfg)
        try:
            #from google.generativeai import generativeai as gemini  # type: ignore
            import google.generativeai as gemini
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("google-generativeai not installed") from exc
        gemini.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self._model = gemini.GenerativeModel(self.cfg.model)

    def complete(self, prompt: str) -> LLMResponse:  # pragma: no cover - requires network
        """Call Gemini text generation with conservative defaults."""
        resp = self._model.generate_content(
            prompt,
            generation_config={
                "temperature": self.cfg.temperature,
                "max_output_tokens": self.cfg.max_output_tokens,
            }
        )
        text = resp.text if hasattr(resp, "text") else str(resp)
        # Gemini API does not provide token usage directly; fallback to lengths
        in_tokens = len(prompt)
        out_tokens = len(text)
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self._logger.info(
            "LLM(gemini) call: model=%s prompt_tokens=%s completion_tokens=%s",
            self.cfg.model,
            in_tokens,
            out_tokens,
        )
        return LLMResponse(text=text, input_tokens=in_tokens, output_tokens=out_tokens)

def build_provider(cfg: LLMConfig) -> LLMProvider:
    """Factory for LLMProvider instances from configuration."""
    provider = cfg.provider.lower()
    if provider == "local":
        return LocalRunLLMProvider(cfg)
    if provider == "openai":
        return OpenAIProvider(cfg)
    if provider == "anthropic":
        return AnthropicProvider(cfg)
    if provider == "gemini":
        return GeminiProvider(cfg)
    return LocalEchoProvider(cfg)


