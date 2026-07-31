from dataclasses import dataclass
from typing import Protocol

import requests

from research_platform import config
from research_platform.clustering.label_schemas import CLUSTER_LABEL_TOOL_SCHEMA

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class LLMProviderError(Exception):
    pass


class LLMMissingApiKeyError(LLMProviderError):
    """Raised before any network call when the provider's API key is not
    configured -- same fail-fast discipline as OpenAlexMissingApiKeyError."""


class LLMTimeoutError(LLMProviderError):
    """Retryable."""


class LLMTransientError(LLMProviderError):
    """Retryable -- 5xx / connection error."""


class LLMRateLimitError(LLMProviderError):
    """Retryable, with an optional provider-supplied retry_after hint."""

    def __init__(self, message: str, retry_after: str | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMResponseError(LLMProviderError):
    """NOT retried -- a permanent failure (bad request, auth, malformed/
    missing tool-call response shape)."""


@dataclass(frozen=True)
class ModelCapability:
    """Per-(provider, model) sampling policy -- deliberately not a global
    constant. Haiku 4.5 gets an explicit low temperature; Sonnet 5 gets no
    temperature/top_p/top_k override at all (set_temperature=False means
    the adapter omits the parameter entirely, using the provider's
    default).

    thinking_param carries the EXACT `thinking` request value to send, or
    None to omit the parameter entirely. Verified 2026-07-30 against
    Anthropic's official per-model thinking-configuration table
    (platform.claude.com/docs/en/build-with-claude/thinking-troubleshooting):
    Claude Haiku 4.5 supports only legacy "extended" thinking and defaults
    to OFF, so omitting the parameter (thinking_param=None) is correct and
    sufficient. Claude Sonnet 5 supports only "adaptive" thinking and
    defaults to ON -- omitting the parameter would leave thinking enabled,
    so it must be explicitly set to {"type": "disabled"} (which Sonnet 5
    accepts, per the same table) to actually satisfy "disable thinking for
    Sonnet 5"."""

    provider: str
    model: str
    set_temperature: bool
    temperature: float | None
    thinking_param: dict | None
    max_output_tokens: int


MODEL_CAPABILITIES: dict[tuple[str, str], ModelCapability] = {
    ("anthropic", "claude-haiku-4-5-20251001"): ModelCapability(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        set_temperature=True,
        temperature=0.0,
        thinking_param=None,  # extended thinking defaults to Off on Haiku 4.5; omission is correct
        max_output_tokens=1024,
    ),
    ("anthropic", "claude-sonnet-5"): ModelCapability(
        provider="anthropic",
        model="claude-sonnet-5",
        set_temperature=False,
        temperature=None,
        thinking_param={"type": "disabled"},  # adaptive thinking defaults to On; must be explicit
        max_output_tokens=1024,
    ),
}


def get_model_capability(provider: str, model: str) -> ModelCapability:
    key = (provider, model)
    if key not in MODEL_CAPABILITIES:
        raise ValueError(
            f"no ModelCapability registered for provider={provider!r} model={model!r}; "
            f"known: {sorted(MODEL_CAPABILITIES.keys())}"
        )
    return MODEL_CAPABILITIES[key]


class LLMProvider(Protocol):
    def generate(
        self, system_prompt: str, user_prompt: str, model: str, capability: ModelCapability, timeout: float
    ) -> dict:
        """Returns the parsed structured-output dict (already JSON-decoded
        by the provider's structured-output mechanism, e.g. Anthropic's
        forced tool call) -- not a raw string. Raises an LLMProviderError
        subclass on any failure."""
        ...


class AnthropicAdapter:
    """Uses Anthropic's forced tool-call mechanism for structured output --
    the model can only respond via the cluster_label tool (tool_choice
    forces it), which is the reliable way to get strict schema-conforming
    JSON from Claude models (there is no native response_format=json_schema
    parameter the way some other providers offer)."""

    def generate(
        self, system_prompt: str, user_prompt: str, model: str, capability: ModelCapability, timeout: float
    ) -> dict:
        if not config.ANTHROPIC_API_KEY:
            raise LLMMissingApiKeyError(
                "ANTHROPIC_API_KEY is not configured. Set it in .env before running cluster "
                "labeling -- unauthenticated execution is refused, not attempted."
            )

        payload = {
            "model": model,
            "max_tokens": capability.max_output_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": [CLUSTER_LABEL_TOOL_SCHEMA],
            "tool_choice": {"type": "tool", "name": "cluster_label"},
        }
        if capability.set_temperature:
            payload["temperature"] = capability.temperature
        if capability.thinking_param is not None:
            payload["thinking"] = capability.thinking_param

        try:
            response = self._post(payload, timeout=timeout)
        except requests.Timeout as exc:
            raise LLMTimeoutError(f"Anthropic request timed out after {timeout}s") from exc
        except requests.ConnectionError as exc:
            raise LLMTransientError(f"connection error calling Anthropic: {exc}") from exc

        if response.status_code == 200:
            return self._extract_tool_input(response.json())

        if response.status_code == 429:
            raise LLMRateLimitError(
                f"Anthropic rate limit (429): {response.text[:300]!r}",
                retry_after=response.headers.get("retry-after"),
            )
        if response.status_code in (500, 502, 503, 529):
            raise LLMTransientError(f"Anthropic server error {response.status_code}: {response.text[:300]!r}")

        # Any other 4xx: permanent. response.text is the server's own
        # response body only -- never our request payload -- so the key
        # cannot leak into this message.
        raise LLMResponseError(f"Anthropic returned HTTP {response.status_code}: {response.text[:300]!r}")

    def _post(self, payload: dict, timeout: float) -> requests.Response:
        return requests.post(
            ANTHROPIC_API_URL,
            json=payload,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            timeout=timeout,
        )

    def _extract_tool_input(self, response_body: dict) -> dict:
        for block in response_body.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "cluster_label":
                return block.get("input", {})
        raise LLMResponseError("Anthropic response contained no cluster_label tool_use block")


_ADAPTERS: dict[str, LLMProvider] = {"anthropic": AnthropicAdapter()}


def get_provider_adapter(provider: str) -> LLMProvider:
    if provider not in _ADAPTERS:
        raise ValueError(f"unknown LLM provider: {provider!r}; known: {sorted(_ADAPTERS.keys())}")
    return _ADAPTERS[provider]
