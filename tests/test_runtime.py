"""Sidecar extract + explain. No AWS, no photos, no SQLite write."""

from __future__ import annotations

from papelito.runtime import DEFAULT_TEXT, extract_and_explain


def test_rejects_non_string_prompt():
    out = extract_and_explain({"prompt": ["not", "a", "string"], "use_model": False})
    assert out["error"] == "prompt must be a string"


def test_seed_ausflug_heuristic():
    out = extract_and_explain(
        {
            "prompt": "extract_and_explain",
            "text": DEFAULT_TEXT,
            "received_on": "2026-09-01",
            "language": "en",
            "use_model": False,
        },
    )
    result = out["result"]
    assert result["runtime"] == "agentcore"
    assert "Ausflug" in result["title"] or "Tiergarten" in result["title"]
    assert result["actions"]
    assert result["event_date"] == "2026-09-09"
    by_kind = {action["kind"]: action for action in result["actions"]}
    assert by_kind["attend"]["deadline_iso"] == "2026-09-09"
    assert by_kind["pay"]["deadline_iso"] == "2026-09-07"
    assert by_kind["pay"]["amount"] == 8.0
    blob = " ".join(
        str(a.get("source_line") or "") + " " + str(a.get("action") or "")
        for a in result["actions"]
    )
    assert "8" in blob
    card = result["card"]
    assert card["language"] == "en"
    assert len(card["labels"]) == 4
    assert card["text"]
    assert "Wed 9 Sep 2026" in card["text"]
    assert "Mon 7 Sep 2026" in card["text"]
    assert all(row["done"] == [] for row in card["rows"])
    assert ".ics" not in card["text"]
    assert "reminder 2 days" not in card["text"]


def test_requested_model_cannot_silently_become_heuristics(monkeypatch):
    monkeypatch.setattr("papelito.runtime._text_model", lambda: None)
    assert extract_and_explain({"prompt": "extract_and_explain"}) == {"error": "model_unavailable"}


def test_model_extraction_failure_is_explicit(monkeypatch):
    monkeypatch.setattr("papelito.runtime.extract", lambda *args: {"extractor": "heuristic"})
    assert extract_and_explain({"prompt": "extract_and_explain"}, model=object()) == {
        "error": "model_extraction_failed"
    }


def test_does_not_need_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "should-not-be-created.db"))
    extract_and_explain(
        {"prompt": "extract_and_explain", "text": DEFAULT_TEXT, "received_on": "2026-09-01", "use_model": False},
    )
    assert not (tmp_path / "should-not-be-created.db").exists()
