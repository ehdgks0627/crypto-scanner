from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_COMPATIBLE_PROVIDERS = {"openai", "openai-compatible", "openai_compatible"}
DISABLED_PROVIDERS = {"", "disabled", "off", "none", "mock", "mock-rulebook", "heuristic"}


class LlmProviderUnavailable(RuntimeError):
    pass


class LlmProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float
    json_mode: bool = True


@dataclass(frozen=True)
class LlmCompletion:
    provider: str
    model: str
    content: str
    usage: Mapping[str, Any]


def load_llm_config(environ: Mapping[str, str] | None = None) -> LlmConfig:
    env = environ or os.environ
    provider = _env_first(env, "QUALITATIVE_LLM_PROVIDER", "LLM_PROVIDER", default="mock-rulebook").lower()
    model = _env_first(env, "QUALITATIVE_LLM_MODEL", "LLM_MODEL", "OPENAI_MODEL")
    api_key = _env_first(env, "QUALITATIVE_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
    base_url = _env_first(
        env,
        "QUALITATIVE_LLM_BASE_URL",
        "LLM_API_BASE_URL",
        "OPENAI_BASE_URL",
        default="https://api.openai.com/v1",
    )
    timeout_seconds = _env_float(env, "QUALITATIVE_LLM_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS", default=30.0)
    json_mode = _env_bool(env, "QUALITATIVE_LLM_JSON_MODE", default=True)
    return LlmConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        json_mode=json_mode,
    )


def call_qualitative_risk_llm(prompt: Mapping[str, Any], config: LlmConfig | None = None) -> LlmCompletion:
    resolved = config or load_llm_config()
    if resolved.provider in DISABLED_PROVIDERS:
        raise LlmProviderUnavailable("qualitative LLM provider is disabled")
    if resolved.provider not in OPENAI_COMPATIBLE_PROVIDERS:
        raise LlmProviderUnavailable(f"unsupported qualitative LLM provider: {resolved.provider}")
    if not resolved.model:
        raise LlmProviderUnavailable("QUALITATIVE_LLM_MODEL or LLM_MODEL must be set")
    if not resolved.api_key:
        raise LlmProviderUnavailable("QUALITATIVE_LLM_API_KEY, LLM_API_KEY, or OPENAI_API_KEY must be set")
    return _call_openai_compatible_chat(prompt, resolved)


def _call_openai_compatible_chat(prompt: Mapping[str, Any], config: LlmConfig) -> LlmCompletion:
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": str(prompt["system"])},
            {"role": "user", "content": str(prompt["user"])},
        ],
        "temperature": 0,
    }
    if config.json_mode:
        body["response_format"] = {"type": "json_object"}
    response = _post_json(
        f"{config.base_url.rstrip('/')}/chat/completions",
        body,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError("LLM provider response did not include choices[0].message.content") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmProviderError("LLM provider returned an empty message")
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return LlmCompletion(provider=config.provider, model=config.model, content=content, usage=usage)


def _post_json(url: str, body: Mapping[str, Any], *, api_key: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode()
    except HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        raise LlmProviderError(f"LLM provider returned HTTP {exc.code}: {error_body[:500]}") from exc
    except (TimeoutError, URLError) as exc:
        raise LlmProviderError(f"LLM provider request failed: {exc}") from exc
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise LlmProviderError("LLM provider response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise LlmProviderError("LLM provider response must be a JSON object")
    return data


def _env_first(env: Mapping[str, str], *names: str, default: str = "") -> str:
    for name in names:
        value = env.get(name)
        if value:
            return value.strip()
    return default


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(env: Mapping[str, str], *names: str, default: float) -> float:
    value = _env_first(env, *names)
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise LlmProviderUnavailable(f"{names[0]} must be numeric") from exc
