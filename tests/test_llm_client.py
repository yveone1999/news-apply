import httpx
import pytest

from src.llm.client import LLMClient, LLMConfig, LLMError

KEY = "sk-secret-value-123"


def make_client(handler, **cfg):
    transport = httpx.MockTransport(handler)
    config = LLMConfig(base_url="http://mock/v1", api_key=KEY, model="test-model",
                       timeout_seconds=5, max_retries=cfg.pop("max_retries", 2), **cfg)
    return LLMClient(config, transport=transport)


def chat_response():
    return httpx.Response(200, json={"choices": [{"message": {"content": "连通"}}]})


def test_chat_success():
    client = make_client(lambda req: chat_response())
    assert client.chat([{"role": "user", "content": "hi"}]) == "连通"


def test_chat_retries_then_success():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return chat_response()

    client = make_client(handler)
    assert client.chat([{"role": "user", "content": "hi"}]) == "连通"
    assert calls["n"] == 2


def test_chat_permanent_failure_no_secret_leak():
    client = make_client(lambda req: httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(LLMError) as excinfo:
        client.chat([{"role": "user", "content": "hi"}])
    assert KEY not in str(excinfo.value)


def test_ping_returns_sample():
    client = make_client(lambda req: chat_response())
    result = client.ping()
    assert result["ok"] is True and result["sample"] == "连通" and result["model"] == "test-model"
