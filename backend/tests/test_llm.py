import httpx

from app.services import assistant, llm


def test_without_key_keeps_rule_text(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    session = assistant.create_session()
    message = assistant.post_message(session["id"], "Montre le ruissellement à Yaoundé", {})
    assert message["source"] == "rules"
    assert message["actions"]


def test_gemini_rewrites_text_and_keeps_actions(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen["url"] = url
        seen["key"] = headers["x-goog-api-key"]
        seen["prompt"] = json["contents"][-1]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Selon les données GLDAS de la visualisation, réponse."}]}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    session = assistant.create_session()
    message = assistant.post_message(session["id"], "Montre le ruissellement à Yaoundé", {"locale": "fr"})
    assert message["source"] == "gemini"
    assert message["text"].startswith("Selon les données GLDAS")
    assert message["actions"]
    assert seen["key"] == "test-key"
    assert "Mann-Kendall" in seen["prompt"]


def test_gemini_error_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def failing(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(llm.httpx, "post", failing)
    session = assistant.create_session()
    message = assistant.post_message(session["id"], "Montre le ruissellement à Yaoundé", {})
    assert message["source"] == "rules"
