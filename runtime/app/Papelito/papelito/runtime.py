"""On-demand extract + explain for AgentCore Runtime.

Seed text only. No photos, no SQLite, no MCP, no save_case, no send.
The household watchdog stays on systemd; this is the sidecar judges can invoke.
"""

from __future__ import annotations

from typing import Any

from papelito.explain import explain_in
from papelito.extract import extract

DEFAULT_TEXT = (
    "Der Ausflug in den Tiergarten findet am Mittwoch statt. "
    "Bitte geben Sie Ihrem Kind bis Montag 8,- Euro in einem beschrifteten Kuvert mit."
)
DEFAULT_RECEIVED_ON = "2026-09-01"
DEFAULT_LANGUAGE = "en"


def _text_model() -> Any | None:
    try:
        from papelito.models import text_model

        return text_model()
    except Exception:
        return None


def extract_and_explain(payload: dict[str, Any], model: Any | None = None) -> dict[str, Any]:
    """Run Papelito extract then explain on note text. Never writes a case file."""
    if not isinstance(payload, dict):
        return {"error": "payload must be a JSON object"}
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return {"error": "prompt must be a string"}

    text = payload.get("text") or DEFAULT_TEXT
    if not isinstance(text, str) or not text.strip():
        return {"error": "text must be a non-empty string"}
    received_on = payload.get("received_on") or DEFAULT_RECEIVED_ON
    if not isinstance(received_on, str):
        return {"error": "received_on must be a string"}
    language = payload.get("language") or DEFAULT_LANGUAGE
    if not isinstance(language, str):
        return {"error": "language must be a string"}

    if model is None and payload.get("use_model", True):
        model = _text_model()

    extracted = extract(text.strip(), received_on, model)
    case = {
        "title": extracted.get("title") or "Kindergarten",
        "sender": extracted.get("sender"),
        "sender_type": extracted.get("sender_type"),
        "event_date": extracted.get("event_date"),
        "actions": extracted.get("actions") or [],
        "language": language,
    }
    card = explain_in(language, case, model=model, questions=True)
    return {
        "result": {
            "title": case["title"],
            "sender": case.get("sender"),
            "sender_type": case.get("sender_type"),
            "event_date": case.get("event_date"),
            "actions": case["actions"],
            "extractor": extracted.get("extractor"),
            "card": {
                "language": card.get("language"),
                "header": card.get("header"),
                "labels": card.get("labels"),
                "text": card.get("text"),
                "rows": card.get("rows"),
            },
            "runtime": "agentcore",
        }
    }
