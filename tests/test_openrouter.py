import json

import httpx
import pytest

from financas_core import ai as openrouter


@pytest.fixture()
def client():
    return openrouter.OpenRouterClient(openrouter.AIConfig(api_key="sk-test", model="x/y"))


def test_extract_sends_parts_and_parses_fenced_json(client, monkeypatch):
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, payload=json, headers=headers)
        body = {"choices": [{"message": {"content": '```json\n{"document_type": "cupom", "transactions": [{"amount": 10}]}\n```'}}]}
        return httpx.Response(200, json=body)

    monkeypatch.setattr(openrouter.httpx, "post", fake_post)
    data = client.extract([openrouter.image_part(b"img", "image/png")], owner_documents=frozenset({"123"}))

    assert data["document_type"] == "cupom"
    assert sent["url"].endswith("/chat/completions")
    assert sent["headers"]["Authorization"] == "Bearer sk-test"
    assert sent["payload"]["model"] == "x/y"
    user_content = sent["payload"]["messages"][1]["content"]
    assert "123" in user_content[0]["text"]
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_extract_reports_http_errors(client, monkeypatch):
    monkeypatch.setattr(openrouter.httpx, "post", lambda *a, **k: httpx.Response(402, text="no credits"))
    with pytest.raises(openrouter.AIError, match="402"):
        client.extract([openrouter.text_part("oi")])


def test_extract_requires_key():
    with pytest.raises(openrouter.AIError):
        openrouter.OpenRouterClient(openrouter.AIConfig(api_key=""))


def test_parse_json_rejects_garbage():
    with pytest.raises(openrouter.AIError):
        openrouter._parse_json("não sei")
    assert openrouter._parse_json(json.dumps({"a": 1})) == {"a": 1, "transactions": []}
