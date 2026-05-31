"""Provider-neutral chat-completion client for an OpenAI-compatible endpoint.

Configured entirely from env so the same code targets any OpenAI-compatible
deployment — swapping providers is purely an env change, no code edits, and no
vendor name appears anywhere:

  LLM_API_BASE     base URL (trailing slash optional)
  LLM_API_KEY      credential
  LLM_MODEL        model / deployment name
  LLM_API_VERSION  optional. When set, the request uses the versioned
                   `/openai/deployments/{model}/chat/completions?api-version=…`
                   path with the key in an `api-key` header. When empty, the
                   plain `{base}/chat/completions` path with an
                   `Authorization: Bearer …` header is used.

Reasoning models spend completion tokens on hidden reasoning before emitting an
answer, so `max_completion_tokens` must be generous or the visible content
comes back empty (finish_reason=length). Defaults here are sized for small
structured-JSON replies with reasoning headroom.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import requests


log = logging.getLogger(__name__)


class LLMConfigError(RuntimeError):
    """Raised when required LLM_* env configuration is missing."""


class LLMError(RuntimeError):
    """Raised when the endpoint returns an error or an unusable response."""


def _parse_json(content: str) -> dict:
    """Best-effort JSON extraction from a model reply.

    Tolerates models that wrap the object in ```json fences or surrounding
    prose by falling back to the outermost {...} span.
    """
    if not content or not content.strip():
        raise LLMError("empty content from LLM")
    text = content.strip()
    # Strip a leading ```json / ``` fence if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise LLMError(f"could not parse JSON from LLM reply: {content[:200]!r}")


class LLMClient:
    """Minimal chat-completions client over an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base: str | None = None,
        key: str | None = None,
        model: str | None = None,
        api_version: str | None = None,
        timeout: int = 120,
    ):
        self.base = (base if base is not None else os.environ.get("LLM_API_BASE", "")).rstrip("/")
        self.key = key if key is not None else os.environ.get("LLM_API_KEY", "")
        self.model = model if model is not None else os.environ.get("LLM_MODEL", "")
        self.api_version = (
            api_version if api_version is not None else os.environ.get("LLM_API_VERSION", "")
        )
        self.timeout = timeout
        missing = [
            name
            for name, val in (
                ("LLM_API_BASE", self.base),
                ("LLM_API_KEY", self.key),
                ("LLM_MODEL", self.model),
            )
            if not val
        ]
        if missing:
            raise LLMConfigError(f"missing required LLM config: {', '.join(missing)}")
        self._session = requests.Session()

    def _endpoint(self) -> tuple[str, dict]:
        if self.api_version:
            url = (
                f"{self.base}/openai/deployments/{self.model}"
                f"/chat/completions?api-version={self.api_version}"
            )
            headers = {"api-key": self.key, "Content-Type": "application/json"}
        else:
            url = f"{self.base}/chat/completions"
            headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        return url, headers

    def chat(
        self,
        messages: list[dict],
        *,
        max_completion_tokens: int = 4096,
        temperature: float | None = None,
        response_format: dict | None = None,
        retries: int = 3,
    ) -> str:
        """POST a chat completion; return the assistant message content.

        `temperature` is omitted when None (some reasoning models reject any
        value other than the default). Retries network errors, 429s and 5xx
        with backoff; raises LLMError on a non-retryable failure.
        """
        url, headers = self._endpoint()
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_completion_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if response_format is not None:
            payload["response_format"] = response_format

        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self._session.post(url, headers=headers, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("LLM HTTP error (attempt %d): %s", attempt + 1, exc)
                time.sleep(1 + attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("LLM HTTP %d (attempt %d) — backing off", resp.status_code, attempt + 1)
                time.sleep(2 + attempt * 2)
                continue
            if not resp.ok:
                raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise LLMError(f"LLM returned no choices: {str(data)[:300]}")
            message = choices[0].get("message") or {}
            content = message.get("content") or ""
            finish = choices[0].get("finish_reason")
            if not content and finish == "length":
                raise LLMError(
                    "LLM returned empty content (finish_reason=length) — "
                    "raise max_completion_tokens"
                )
            return content
        raise LLMError(f"LLM request failed after {retries} attempts: {last_exc}")

    def chat_json(
        self,
        messages: list[dict],
        *,
        max_completion_tokens: int = 4096,
        retries: int = 3,
    ) -> dict:
        """chat() that requests and parses a JSON object.

        Sends response_format=json_object; if the endpoint rejects that param
        (HTTP 400), retries once without it and relies on _parse_json to pull
        the object out of the reply.
        """
        try:
            content = self.chat(
                messages,
                max_completion_tokens=max_completion_tokens,
                response_format={"type": "json_object"},
                retries=retries,
            )
        except LLMError as exc:
            if "HTTP 400" not in str(exc):
                raise
            log.warning("LLM rejected response_format=json_object — retrying without it")
            content = self.chat(
                messages, max_completion_tokens=max_completion_tokens, retries=retries
            )
        return _parse_json(content)
