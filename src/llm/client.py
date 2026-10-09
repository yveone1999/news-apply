"""OpenAI 兼容接口适配层：超时、有限重试、错误记录、密钥脱敏。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


class LLMError(Exception):
    """LLM 调用失败（已重试耗尽或不可重试错误）。"""

    def __init__(self, message: str, status_code: int | None = None):
        # 不携带任何请求头/密钥信息
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LLMConfig:
    base_url: str
    api_key: str = ""
    model: str = ""
    timeout_seconds: float = 120.0
    max_retries: int = 3
    extra: dict = field(default_factory=dict)


_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMClient:
    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(config.timeout_seconds),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def list_models(self) -> list[str]:
        resp = self._request("GET", "/models")
        data = resp.json()
        return [m.get("id", "") for m in data.get("data", [])]

    def chat(self, messages: list[dict], max_tokens: int | None = None, temperature: float | None = None) -> str:
        payload: dict = {"model": self.config.model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        resp = self._request("POST", "/chat/completions", json=payload)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError("模型返回结构异常，无法解析 choices") from exc

    def ping(self) -> dict:
        """连接测试：返回 {ok, model, latency_ms, sample}。失败抛 LLMError。"""
        started = time.monotonic()
        sample = self.chat([{"role": "user", "content": "回复两个字：连通"}], max_tokens=20)
        return {
            "ok": True,
            "model": self.config.model,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "sample": sample[:200],
        }

    def _request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        last_err: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                resp = self._client.request(method, path, json=json)
                if resp.status_code in _RETRYABLE_STATUS and attempt < self.config.max_retries - 1:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                if resp.status_code >= 400:
                    raise LLMError(f"模型接口返回 HTTP {resp.status_code}", status_code=resp.status_code)
                return resp
            except httpx.TimeoutException as exc:
                last_err = exc
                if attempt < self.config.max_retries - 1:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise LLMError(f"模型接口超时（>{self.config.timeout_seconds}s，重试 {self.config.max_retries} 次）") from exc
            except httpx.HTTPError as exc:
                last_err = exc
                if attempt < self.config.max_retries - 1:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise LLMError(f"模型接口网络错误: {type(exc).__name__}") from exc
        raise LLMError(f"模型接口调用失败（重试耗尽）: {type(last_err).__name__ if last_err else 'unknown'}")
