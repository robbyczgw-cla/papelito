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
    assert any(a.get("deadline_iso") == "2026-09-07" for a in result["actions"])
    blob = " ".join(
        str(a.get("source_line") or "") + " " + str(a.get("action") or "")
        for a in result["actions"]
    )
    assert "8" in blob
    card = result["card"]
    assert card["language"] == "en"
    assert len(card["labels"]) == 4
    assert card["text"]
    assert "Mon 7 Sep 2026" in card["text"]


def test_does_not_need_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "should-not-be-created.db"))
    extract_and_explain(
        {"prompt": "extract_and_explain", "text": DEFAULT_TEXT, "received_on": "2026-09-01", "use_model": False},
    )
    assert not (tmp_path / "should-not-be-created.db").exists()
