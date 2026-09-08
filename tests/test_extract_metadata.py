"""Top-level event metadata must come from verified action evidence."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]


def _extract_modules():
    root_module = importlib.import_module("papelito.extract")
    vendored_path = REPO / "runtime" / "app" / "Papelito" / "papelito" / "extract.py"
    spec = importlib.util.spec_from_file_location("papelito_vendored_extract_metadata_test", vendored_path)
    assert spec and spec.loader
    vendored = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendored)
    return root_module, vendored


@pytest.mark.parametrize("module", _extract_modules())
def test_event_date_follows_verified_attend_deadline(module):
    attend_source = "Der Ausflug in den Tiergarten findet am Mittwoch statt."
    payment_source = "Bitte geben Sie Ihrem Kind bis Montag 8,- Euro in einem beschrifteten Kuvert mit."
    text = f"{attend_source} {payment_source}"
    raw = {
        "title": "Ausflug",
        "event_date": "2026-09-07",
        "actions": [
            {
                "kind": "attend",
                "action": "Am Ausflug teilnehmen",
                "deadline_phrase": "",
                "deadline_iso": None,
                "source_line": attend_source,
                "confidence": 0.95,
            },
            {
                "kind": "bring",
                "action": "8 Euro mitgeben",
                "deadline_phrase": "bis Montag",
                "deadline_iso": "2026-09-07",
                "amount_eur": 8.0,
                "source_line": payment_source,
                "confidence": 0.95,
            },
        ],
    }

    result = module._verify(raw, text, module._to_date("2026-09-01"), True)

    assert result["actions"][0]["deadline_iso"] == "2026-09-02"
    assert result["event_date"] == "2026-09-02"
    assert result["actions"][0]["source_line"] == attend_source
    assert result["actions"][1]["kind"] == "pay"
    assert result["actions"][1]["deadline_iso"] == "2026-09-07"
    assert result["actions"][1]["amount"] == 8.0
    assert module.find_amount(payment_source) == 8.0


@pytest.mark.parametrize("module", _extract_modules())
def test_ungrounded_raw_event_date_is_dropped_without_attend(module):
    raw = {"title": "Ausflug", "event_date": "2026-09-07", "actions": []}

    result = module._verify(raw, "Der Ausflug findet statt.", module._to_date("2026-09-01"), True)

    assert result["event_date"] is None
    assert result["actions"] == []


@pytest.mark.parametrize("module", _extract_modules())
def test_grounded_raw_event_date_still_adds_attend(module):
    text = "Der Ausflug findet am Mittwoch statt."
    raw = {"title": "Ausflug", "event_date": "2026-09-02", "actions": []}

    result = module._verify(raw, text, module._to_date("2026-09-01"), True)

    assert result["event_date"] == "2026-09-02"
    assert result["actions"][0]["kind"] == "attend"
    assert result["actions"][0]["deadline_iso"] == "2026-09-02"


@pytest.mark.parametrize("module", _extract_modules())
def test_deadline_phrase_not_present_in_source_cannot_validate_model_date(module):
    source = "Bitte an Fr. Huber abgeben."
    raw = {
        "actions": [{
            "kind": "reply",
            "action": "Bei Fr. Huber abgeben",
            "deadline_phrase": "12.09.2026",
            "deadline_iso": "2026-09-12",
            "source_line": source,
            "confidence": 0.96,
        }],
    }

    action = module._verify(raw, source, module._to_date("2026-09-01"), True)["actions"][0]

    assert action["deadline_iso"] is None
    assert "date_unverified" in action["flags"]
    assert action["gate"] == "ask"
