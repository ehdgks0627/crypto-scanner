import json
import subprocess
from pathlib import Path

import pytest

from risk_engine.llm import LlmConfig, LlmProviderUnavailable, call_qualitative_risk_llm, load_llm_config


def test_llm_provider_posts_openai_compatible_chat_request(monkeypatch):
    prompt = {"system": "system prompt", "user": "user prompt"}
    calls = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": "{\"summary\":\"ok\"}"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        calls["timeout"] = timeout
        calls["body"] = json.loads(request.data.decode())
        calls["auth"] = request.headers["Authorization"]
        return FakeResponse()

    monkeypatch.setattr("risk_engine.llm.urlopen", fake_urlopen)

    completion = call_qualitative_risk_llm(
        prompt,
        LlmConfig(
            provider="openai-compatible",
            model="test-model",
            api_key="secret-token",
            base_url="https://llm.example/v1/",
            timeout_seconds=7,
        ),
    )

    assert calls["url"] == "https://llm.example/v1/chat/completions"
    assert calls["timeout"] == 7
    assert calls["auth"] == "Bearer secret-token"
    assert calls["body"]["model"] == "test-model"
    assert calls["body"]["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]
    assert calls["body"]["response_format"] == {"type": "json_object"}
    assert completion.content == "{\"summary\":\"ok\"}"
    assert completion.usage == {"prompt_tokens": 10, "completion_tokens": 3}


def test_llm_provider_requires_explicit_external_configuration():
    with pytest.raises(LlmProviderUnavailable):
        call_qualitative_risk_llm(
            {"system": "system", "user": "user"},
            LlmConfig(
                provider="mock-rulebook",
                model="",
                api_key="",
                base_url="https://llm.example/v1",
                timeout_seconds=1,
            ),
        )


def test_llm_provider_calls_codex_cli_and_reads_last_message(monkeypatch):
    prompt = {"system": "system prompt", "user": "user prompt"}
    calls = {}

    def fake_run(command, input, text, capture_output, timeout, env, check):
        calls["command"] = command
        calls["input"] = input
        calls["text"] = text
        calls["capture_output"] = capture_output
        calls["timeout"] = timeout
        calls["env"] = env
        calls["check"] = check
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("{\"summary\":\"codex\"}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="progress", stderr="")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("risk_engine.llm.subprocess.run", fake_run)

    completion = call_qualitative_risk_llm(
        prompt,
        LlmConfig(
            provider="codex-cli",
            model="gpt-test",
            api_key="cli-token",
            base_url="",
            timeout_seconds=11,
            cli_command="/usr/local/bin/codex",
            cli_reasoning_effort="low",
            cli_extra_args=("--config", "reasoning_effort=\"low\""),
        ),
    )

    assert calls["command"][:2] == ["/usr/local/bin/codex", "exec"]
    assert "--ephemeral" in calls["command"]
    assert "--skip-git-repo-check" in calls["command"]
    assert "--sandbox" in calls["command"]
    assert "read-only" in calls["command"]
    assert calls["command"][-1] == "-"
    assert calls["command"][calls["command"].index("--model") + 1] == "gpt-test"
    assert ["--config", "reasoning_effort=\"low\""] in [
        calls["command"][index : index + 2]
        for index in range(len(calls["command"]) - 1)
    ]
    assert calls["command"][-3:-1] == ["--config", "reasoning_effort=\"low\""]
    assert "system prompt" in calls["input"]
    assert "user prompt" in calls["input"]
    assert "Return the final answer as one JSON object only" in calls["input"]
    assert calls["timeout"] == 11
    assert calls["env"]["OPENAI_API_KEY"] == "cli-token"
    assert calls["check"] is False
    assert completion.provider == "codex-cli"
    assert completion.model == "gpt-test"
    assert completion.content == "{\"summary\":\"codex\"}"
    assert completion.usage["cli_command"] == "/usr/local/bin/codex"


def test_llm_config_loads_codex_cli_options():
    config = load_llm_config(
        {
            "QUALITATIVE_LLM_PROVIDER": "codex-cli",
            "QUALITATIVE_LLM_MODEL": "gpt-test",
            "QUALITATIVE_CODEX_COMMAND": "/opt/bin/codex",
            "QUALITATIVE_CODEX_REASONING_EFFORT": "low",
            "QUALITATIVE_CODEX_EXTRA_ARGS": "--profile demo --config reasoning_effort=\"low\"",
        }
    )

    assert config.provider == "codex-cli"
    assert config.model == "gpt-test"
    assert config.cli_command == "/opt/bin/codex"
    assert config.cli_reasoning_effort == "low"
    assert config.cli_extra_args == ("--profile", "demo", "--config", "reasoning_effort=low")
