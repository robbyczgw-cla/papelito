"""On-demand extract + explain for AgentCore Runtime.

The PWA demo route sends fixed, invented note text. The Runtime accepts note
text in its payload, then extracts and explains it without photos, SQLite, MCP,
save_case or send. The household watchdog stays on systemd.
"""

from __future__ import annotations

from typing import Any
import logging
import time

from papelito.explain import explain_in, render_card
from papelito.extract import extract

DEFAULT_TEXT = (
    "Der Ausflug in den Tiergarten findet am Mittwoch, den 09.09.2026, statt.\n"
    "Bitte geben Sie Ihrem Kind bis Montag, den 07.09.2026, 8,- Euro in einem beschrifteten Kuvert mit."
)
DEFAULT_RECEIVED_ON = "2026-09-01"
DEFAULT_LANGUAGE = "en"
_log = logging.getLogger(__name__)
_log.setLevel(logging.INFO)
if not _log.handlers:
    _log.addHandler(logging.StreamHandler())


def _text_model() -> Any | None:
    try:
        from papelito.models import text_model

        return text_model()
    except Exception as exc:
        reason = {
            "AgentCore workload token is unavailable": "missing_workload_identity",
            "AWS region is unavailable": "missing_region",
            "AgentCore Identity returned no API key": "empty_credential",
        }.get(str(exc), "other")
        _log.warning("runtime_model_unavailable error_class=%s reason=%s", type(exc).__name__, reason)
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

    require_model = bool(payload.get("use_model", True))
    if model is None and require_model:
        started = time.monotonic()
        _log.info("runtime_phase=model_init event=start")
        model = _text_model()
        _log.info("runtime_phase=model_init event=end seconds=%.3f available=%s", time.monotonic() - started, model is not None)
    if require_model and model is None:
        return {"error": "model_unavailable"}

    started = time.monotonic()
    _log.info("runtime_phase=extract event=start")
    extracted = extract(text.strip(), received_on, model)
    _log.info("runtime_phase=extract event=end seconds=%.3f extractor=%s", time.monotonic() - started, extracted.get("extractor"))
    if require_model and extracted.get("extractor") != "model":
        return {"error": "model_extraction_failed"}
    case = {
        "title": extracted.get("title") or "Kindergarten",
        "sender": extracted.get("sender"),
        "sender_type": extracted.get("sender_type"),
        "event_date": extracted.get("event_date"),
        "actions": extracted.get("actions") or [],
        "language": language,
    }
    started = time.monotonic()
    _log.info("runtime_phase=explain event=start")
    card = explain_in(language, case, model=model, questions=True)
    # This sidecar never saves files, schedules reminders, or stores a case.
    # Do not show the full application's pending artifact checklist here.
    for row in card["rows"]:
        row["done"] = []
    card["text"] = render_card(card)
    _log.info("runtime_phase=explain event=end seconds=%.3f", time.monotonic() - started)
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
