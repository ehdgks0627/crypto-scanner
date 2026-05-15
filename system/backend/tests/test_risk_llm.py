import json

import pytest

from risk_engine.llm import LlmConfig, LlmProviderUnavailable, call_qualitative_risk_llm


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
