from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_COMPATIBLE_PROVIDERS = {"openai", "openai-compatible", "openai_compatible"}
CODEX_CLI_PROVIDERS = {"codex", "codex-cli", "codex_cli"}
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
    cli_command: str = "codex"
    cli_extra_args: tuple[str, ...] = ()


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
    cli_command = _env_first(env, "QUALITATIVE_CODEX_COMMAND", "CODEX_CLI_COMMAND", default="codex")
    cli_extra_args = _env_args(env, "QUALITATIVE_CODEX_EXTRA_ARGS", "CODEX_CLI_EXTRA_ARGS")
    return LlmConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        json_mode=json_mode,
        cli_command=cli_command,
        cli_extra_args=cli_extra_args,
    )


def call_qualitative_risk_llm(prompt: Mapping[str, Any], config: LlmConfig | None = None) -> LlmCompletion:
    resolved = config or load_llm_config()
    if resolved.provider in DISABLED_PROVIDERS:
        raise LlmProviderUnavailable("qualitative LLM provider is disabled")
    if resolved.provider in CODEX_CLI_PROVIDERS:
        return _call_codex_cli(prompt, resolved)
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


def _call_codex_cli(prompt: Mapping[str, Any], config: LlmConfig) -> LlmCompletion:
    command = _codex_exec_command(config)
    request_text = _codex_prompt_text(prompt)
    with tempfile.TemporaryDirectory(prefix="qualitative-codex-") as tmp_dir:
        output_path = Path(tmp_dir) / "last-message.txt"
        run_command = [
            *command,
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-last-message",
            str(output_path),
        ]
        if config.model:
            run_command.extend(["--model", config.model])
        run_command.extend(config.cli_extra_args)
        run_command.append("-")
        try:
            completed = subprocess.run(
                run_command,
                input=request_text,
                text=True,
                capture_output=True,
                timeout=config.timeout_seconds,
                env=_codex_env(config),
                check=False,
            )
        except FileNotFoundError as exc:
            raise LlmProviderUnavailable(f"Codex CLI command not found: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise LlmProviderError(f"Codex CLI timed out after {config.timeout_seconds:g}s") from exc

        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "unknown Codex CLI error").strip()
            raise LlmProviderError(f"Codex CLI exited with {completed.returncode}: {error[:500]}")

        content = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else completed.stdout.strip()
        if not content:
            raise LlmProviderError("Codex CLI returned an empty message")
        usage = {
            "cli_command": command[0],
            "exit_code": completed.returncode,
            "stdout_bytes": len((completed.stdout or "").encode()),
            "stderr_bytes": len((completed.stderr or "").encode()),
        }
        return LlmCompletion(provider=config.provider, model=config.model, content=content, usage=usage)


def _codex_exec_command(config: LlmConfig) -> list[str]:
    try:
        command = shlex.split(config.cli_command)
    except ValueError as exc:
        raise LlmProviderUnavailable("QUALITATIVE_CODEX_COMMAND is not a valid shell command") from exc
    if not command:
        raise LlmProviderUnavailable("QUALITATIVE_CODEX_COMMAND must not be empty")
    return command


def _codex_prompt_text(prompt: Mapping[str, Any]) -> str:
    return (
        f"{prompt['system']}\n\n"
        f"{prompt['user']}\n\n"
        "Return the final answer as one JSON object only. "
        "Do not include Markdown fences, explanations, or code changes."
    )


def _codex_env(config: LlmConfig) -> dict[str, str]:
    env = os.environ.copy()
    if config.api_key and not env.get("OPENAI_API_KEY"):
        env["OPENAI_API_KEY"] = config.api_key
    env.setdefault("NO_COLOR", "1")
    return env


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


def _env_args(env: Mapping[str, str], *names: str) -> tuple[str, ...]:
    value = _env_first(env, *names)
    if not value:
        return ()
    try:
        return tuple(shlex.split(value))
    except ValueError as exc:
        raise LlmProviderUnavailable(f"{names[0]} must be valid shell-style arguments") from exc
