import json

import httpx
import pytest
from fastapi import HTTPException

from fairmade.assistants.gateway import MODEL, OllamaGateway


def response(content=None, **changes):
    result = {
        "model": MODEL,
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(content or {"paragraphs": []})},
    }
    return {**result, **changes}


def test_local_transport_has_fixed_model_no_tools_redirects_or_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://external.invalid")
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=response({"paragraphs": [{"text": "Synthetic"}]}))

    result = OllamaGateway(httpx.MockTransport(handle)).complete(
        [{"role": "system", "content": "Synthetic system"}], {"type": "object"}
    )
    assert result["paragraphs"][0]["text"] == "Synthetic"
    request = seen[0]
    assert str(request.url) == "http://127.0.0.1:11434/api/chat"
    body = json.loads(request.content)
    assert body["model"] == MODEL and body["think"] is False and body["stream"] is False
    assert body["options"]["num_predict"] == 1200 and "tools" not in body


@pytest.mark.parametrize("status", [301, 404, 429, 500])
def test_provider_http_errors_are_safe_and_do_not_follow_redirects(status):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(
            status, headers={"Location": "https://external.invalid"}, text="PRIVATE_PROVIDER_ERROR"
        )

    with pytest.raises(HTTPException) as exc:
        OllamaGateway(httpx.MockTransport(handle)).complete([], {})
    assert exc.value.status_code == 503 and "PRIVATE" not in str(exc.value.detail)
    assert len(seen) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"done": False},
        {"done_reason": "length"},
        {"model": "qwen3:8b-cloud"},
        {"message": {"role": "tool", "content": "{}"}},
        {"message": {"role": "assistant", "content": "PRIVATE_INVALID_JSON"}},
        {"message": {"role": "assistant", "content": "[]"}},
        {"message": None},
    ],
)
def test_invalid_or_truncated_model_results_fail_closed(payload):
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=response(**payload)))
    with pytest.raises(HTTPException) as exc:
        OllamaGateway(transport).complete([], {})
    assert exc.value.status_code == 502 and "PRIVATE" not in str(exc.value.detail)


def test_provider_timeout_is_safe():
    def timeout(request):
        raise httpx.ReadTimeout("PRIVATE_TIMEOUT", request=request)

    with pytest.raises(HTTPException) as exc:
        OllamaGateway(httpx.MockTransport(timeout)).complete([], {})
    assert exc.value.status_code == 503 and "PRIVATE" not in str(exc.value.detail)


def test_oversized_provider_response_is_bounded():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 65537))
    with pytest.raises(HTTPException) as exc:
        OllamaGateway(transport).complete([], {})
    assert exc.value.status_code == 502
