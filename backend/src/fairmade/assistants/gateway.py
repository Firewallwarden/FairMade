"""Small local-only transport boundary; never auto-download or use cloud inference."""

import json
import os
from typing import Protocol

import httpx
from fastapi import Request

from fairmade.auth import api_error

MODEL = "qwen3:8b"
URL = "http://127.0.0.1:11434/api/chat"
MAX_RESPONSE_BYTES = 65536


class Gateway(Protocol):
    def complete(self, messages: list[dict], schema: dict) -> dict: ...


def unavailable():
    return api_error(503, "ASSISTANT_UNAVAILABLE", "Local assistant is unavailable; retry later.")


class OllamaGateway:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def complete(self, messages: list[dict], schema: dict) -> dict:
        body = {
            "model": MODEL,
            "messages": messages,
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "5m",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1200},
        }
        try:
            # Disable environment proxies and redirects: private evidence stays on loopback.
            with (
                httpx.Client(
                    transport=self.transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(60, connect=2),
                ) as client,
                client.stream("POST", URL, json=body) as response,
            ):
                if response.status_code != 200:
                    raise unavailable()
                chunks = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise api_error(
                            502, "ASSISTANT_INVALID_RESPONSE", "Invalid model response."
                        )
            payload = json.loads(chunks)
            if (
                payload.get("model") != MODEL
                or payload.get("done") is not True
                or payload.get("done_reason") != "stop"
                or payload.get("message", {}).get("role") != "assistant"
            ):
                raise ValueError("Incomplete or unexpected model response")
            content = payload["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Expected JSON object")
            return result
        except (httpx.HTTPError, OSError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError, AttributeError):
            raise api_error(502, "ASSISTANT_INVALID_RESPONSE", "Invalid model response.") from None


def get_gateway(request: Request) -> Gateway:
    override = getattr(request.app.state, "assistant_gateway", None)
    if override is not None:
        return override
    if os.environ.get("FAIRMADE_ASSISTANTS_ENABLED", "false") != "true":
        raise unavailable()
    return OllamaGateway()
