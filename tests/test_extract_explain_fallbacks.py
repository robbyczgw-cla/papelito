"""Focused regressions for safe model fallbacks in extraction and explanation."""

from __future__ import annotations

import logging

from papelito import explain as E
from papelito import extract as X


def test_heuristic_sender_is_none_without_an_institution_header():
    result = X.extract(
        "Der Ausflug findet am Mittwoch, den 09.09.2026, statt.\n"
        "Bitte geben Sie bis Montag 8 Euro mit.",
        "2026-09-03",
    )

    assert result["sender"] is None


def test_heuristic_sender_keeps_a_clear_institution_header():
    result = X.extract(
        "Kindergarten Sonnenblume\n"
        "Der Ausflug findet am Mittwoch, den 09.09.2026, statt.",
        "2026-09-03",
    )

    assert result["sender"] == "Kindergarten Sonnenblume"


def test_english_card_translates_known_outing_title_without_changing_source():
    source = "Der Ausflug findet am Mittwoch, den 09.09.2026, statt."
    card = E.explain_in("en", {
        "id": "outing",
        "title": "Ausflug in den Tiergarten",
        "event_date": "2026-09-09",
        "actions": [{
            "id": "attend",
            "kind": "attend",
            "action": "Ausflug in den Tiergarten",
            "deadline_iso": "2026-09-09",
            "source_line": source,
            "status": "active",
            "confidence": 0.99,
        }],
    })

    assert card["title"] == "Outing to the zoo"
    assert card["header"].startswith("Outing to the zoo")
    assert card["rows"][0]["what"] == "Outing to the zoo"
    assert card["rows"][0]["do"] == "Go: \u201cOuting to the zoo\u201d"
    assert card["rows"][0]["source_line"] == source


def test_extract_model_failure_log_excludes_exception_detail(monkeypatch, caplog):
    class ProviderFailure(Exception):
        status_code = 503

    def fail(*_args):
        raise ProviderFailure("private provider detail")

    monkeypatch.setattr(X, "_model_extract", fail)
    with caplog.at_level(logging.WARNING, logger=X.__name__):
        result = X.extract("Ausflug am 09.09.2026.", "2026-09-03", model=object())

    assert result["extractor"] == "heuristic"
    assert "extract_model_error error_class=ProviderFailure status_code=503" in caplog.text
    assert "private provider detail" not in caplog.text


def test_extract_invalid_json_log_excludes_model_output(caplog):
    with caplog.at_level(logging.WARNING, logger=X.__name__):
        assert X._parse_json("private model output without JSON") is None

    assert "extract_model_invalid_json reason=no_object" in caplog.text
    assert "private model output" not in caplog.text


def test_explain_model_failure_log_excludes_exception_detail(monkeypatch, caplog):
    import strands

    class ProviderFailure(Exception):
        status_code = 429

    class FailingAgent:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _payload):
            raise ProviderFailure("private provider detail")

    monkeypatch.setattr(strands, "Agent", FailingAgent)
    with caplog.at_level(logging.WARNING, logger=E.__name__):
        translated = E.translate_actions(
            [{"action": "Ausflug", "source_line": "Ausflug"}],
            "en",
            object(),
            "Ausflug",
        )

    assert translated == {}
    assert "explain_model_error error_class=ProviderFailure status_code=429" in caplog.text
    assert "private provider detail" not in caplog.text


def test_explain_invalid_json_log_excludes_model_output(monkeypatch, caplog):
    import strands

    class InvalidAgent:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _payload):
            return "private model output without JSON"

    monkeypatch.setattr(strands, "Agent", InvalidAgent)
    with caplog.at_level(logging.WARNING, logger=E.__name__):
        translated = E.translate_actions(
            [{"action": "Ausflug", "source_line": "Ausflug"}],
            "en",
            object(),
            "Ausflug",
        )

    assert translated == {}
    assert "explain_model_invalid_json reason=no_object" in caplog.text
    assert "private model output" not in caplog.text
