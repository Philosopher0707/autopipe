"""I12: LLM clients never mutate process-global SDK state; timeouts stay transport-only.

Regression guards for the OpenAI global-key leak vector (NORTH_STAR I12,
SOURCE-DERIVED llm/client.py) and for `timeout` leaking into JSON request
bodies of the requests-based providers.
"""

from typing import Any, Dict, Optional


class _FakeMessage:
    content = "hi"


class _FakeChatResponse:
    class _Choice:
        message = _FakeMessage()

    choices = [_Choice()]


def test_openai_chat_never_touches_module_global(monkeypatch):
    import pytest

    # openai is an opt-in extra (autopipe[openai]); skip on a clean install.
    openai = pytest.importorskip("openai")

    from autopipe.llm.client import OpenAIClient

    monkeypatch.setattr(openai, "api_key", "sentinel", raising=False)

    seen: Dict[str, Any] = {}

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            seen.update(kwargs)
            return _FakeChatResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeSDKClient:
        chat = _FakeChat()

    # Cover both the instance-scoped path (openai.OpenAI) and the legacy
    # module-level path so the test stays red until the mutation is gone.
    monkeypatch.setattr(openai, "OpenAI", lambda **_: _FakeSDKClient(), raising=False)
    monkeypatch.setattr(openai, "chat", _FakeChat(), raising=False)

    client = OpenAIClient(api_key="sk-test-key", model="gpt-4o")
    out = client.chat([{"role": "user", "content": "hi"}])

    assert out == "hi"
    assert seen["model"] == "gpt-4o"
    assert openai.api_key == "sentinel", "chat() must not mutate openai.api_key globally"


class _FakeHTTPResponse:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Dict[str, Any]:
        return self._payload


def _stub_requests(monkeypatch, module_path: str) -> Dict[str, Any]:
    captured: Dict[str, Any] = {}

    def fake_get(*args, **kwargs):
        return _FakeHTTPResponse({"data": []})

    def fake_post(url, headers=None, json=None, timeout: Optional[float] = None):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return _FakeHTTPResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(f"{module_path}.requests.get", fake_get)
    monkeypatch.setattr(f"{module_path}.requests.post", fake_post)
    return captured


def test_ollama_timeout_is_transport_only(monkeypatch):
    from autopipe.llm.client import OllamaClient

    captured = _stub_requests(monkeypatch, "autopipe.llm.client")
    client = OllamaClient(api_key="k", model="m", base_url="http://example.invalid/v1")

    out = client.chat([{"role": "user", "content": "hi"}], timeout=7)

    assert out == "ok"
    assert captured["timeout"] == 7, "timeout must reach requests as the transport timeout"
    assert "timeout" not in captured["json"], "timeout must not be sent in the JSON body"


def test_openrouter_timeout_is_transport_only(monkeypatch):
    from autopipe.llm.client import OpenRouterClient

    captured = _stub_requests(monkeypatch, "autopipe.llm.client")
    client = OpenRouterClient(api_key="k", model="m")

    out = client.chat([{"role": "user", "content": "hi"}], timeout=9)

    assert out == "ok"
    assert captured["timeout"] == 9
    assert "timeout" not in captured["json"]
