import json
from dataclasses import replace

import httpx
import pytest

from app.ai import openrouter


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setattr(
        openrouter, "settings", replace(openrouter.settings, openrouter_api_key="sk-test", openrouter_model="x/y")
    )


def test_extract_sends_parts_and_parses_fenced_json(configured, monkeypatch):
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, payload=json, headers=headers)
        body = {"choices": [{"message": {"content": '```json\n{"document_type": "cupom", "transactions": [{"amount": 10}]}\n```'}}]}
        return httpx.Response(200, json=body)

    monkeypatch.setattr(openrouter.httpx, "post", fake_post)
    data = openrouter.extract([openrouter.image_part(b"img", "image/png")])

    assert data["document_type"] == "cupom"
    assert sent["url"].endswith("/chat/completions")
    assert sent["headers"]["Authorization"] == "Bearer sk-test"
    assert sent["payload"]["model"] == "x/y"
    user_content = sent["payload"]["messages"][1]["content"]
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_extract_reports_http_errors(configured, monkeypatch):
    monkeypatch.setattr(openrouter.httpx, "post", lambda *a, **k: httpx.Response(402, text="no credits"))
    with pytest.raises(openrouter.AIError, match="402"):
        openrouter.extract([openrouter.text_part("oi")])


def test_extract_requires_key():
    with pytest.raises(openrouter.AIError):
        openrouter.extract([openrouter.text_part("oi")])


def test_parse_json_rejects_garbage():
    with pytest.raises(openrouter.AIError):
        openrouter._parse_json("não sei")
    assert openrouter._parse_json(json.dumps({"a": 1})) == {"a": 1, "transactions": []}
