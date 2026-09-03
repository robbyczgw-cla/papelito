from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def web_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "cases.db"))
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        'names:\n'
        '  parent: "Lucía García"\n'
        '  household: "Demo household"\n'
        'children:\n'
        '  - id: mateo\n'
        '    name: "Mateo"\n'
        '    kindergarten: "Kindergarten Sonnenblume"\n'
        'reader_language: "English"\n'
        'reply_signature: "Lucía García"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPELITO_PROFILE", str(profile_path))
    monkeypatch.setenv("PAPELITO_TODAY", "2026-09-03")

    import web.store as store_module
    import web.app as app_module

    store_module = importlib.reload(store_module)
    app_module = importlib.reload(app_module)
    yield app_module, store_module
    if store_module._store is not None:
        core = getattr(store_module._store, "core", None)
        if core is not None:
            core.close()
        store_module._store = None


def test_settings_children_calendar_and_board(web_modules):
    app_module, store_module = web_modules
    client = TestClient(app_module.app)

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    data = settings.json()
    assert {"parent", "household", "language", "signature", "children"} == set(data)
    assert data["language"] == "en"
    assert [child["id"] for child in data["children"]] == ["mateo"]
    data["language"] = "en"
    data["children"].append({"id": "second", "name": "Second Child", "kindergarten": "Hort"})
    saved = client.put("/api/settings", json=data)
    assert saved.status_code == 200
    assert any(child["id"] == "second" for child in saved.json()["children"])

    seeded = client.post("/api/demo/seed")
    assert seeded.status_code == 200
    case_id = seeded.json()["cases"][0]["id"]
    attached = client.patch(f"/api/cases/{case_id}", json={"child_id": "second"})
    assert attached.status_code == 200
    assert attached.json()["case"]["child_id"] == "second"
    assert attached.json()["case"]["child_name"] == "Second Child"

    calendar = client.get("/api/calendar?year=2026&month=9&lang=en")
    assert calendar.status_code == 200
    assert calendar.json()["days"]
    item = calendar.json()["days"][0]["items"][0]
    assert {"case_id", "title", "do", "what", "deadline", "child_id", "child_name", "state"} == set(item)
    assert item["deadline"].startswith("2026-09-")

    board = client.get("/api/board?lang=en")
    assert board.status_code == 200
    papers = board.json()["items"]
    assert len(papers) == 5
    assert papers[0]["received_on"] >= papers[-1]["received_on"]
    assert all({
        "paper_id", "case_id", "title", "kind", "board", "received_on", "photo", "text_preview",
        "child_id", "child_name", "has_reply", "has_calendar", "n_actions",
    } == set(paper) for paper in papers)
    assert any(paper["board"] == "action" and paper["has_reply"] for paper in papers)

    store_module.get_store().save_case({
        "id": "notice-case",
        "title": "Tagesplan",
        "papers": [{"id": "notice-paper", "kind": "original", "received_on": "2026-09-03", "text": "Nur zur Information."}],
        "actions": [],
    })
    notice = next(item for item in client.get("/api/board").json()["items"] if item["paper_id"] == "notice-paper")
    assert notice["board"] == "notice"
    assert notice["n_actions"] == 0


def test_settings_validate_language_and_child_fields(web_modules):
    app_module, _ = web_modules
    client = TestClient(app_module.app)
    current = client.get("/api/settings").json()

    assert client.put("/api/settings", json={**current, "language": "fr"}).status_code == 400
    assert client.put("/api/settings", json={**current, "children": [{"name": "Missing id"}]}).status_code == 400


def test_info_actions_need_no_reply_but_can_have_calendar_deadlines():
    from papelito.agent import needs_calendar, needs_reply

    case = {"actions": [{"kind": "info", "status": "active", "deadline_iso": "2026-09-10"}]}
    assert not needs_reply(case)
    assert needs_calendar(case)


def test_save_profile_filters_secrets(tmp_path):
    from papelito.reply import load_profile, save_profile

    path = Path(tmp_path) / "profile.yaml"
    save_profile({
        "parent": "Lucía García",
        "household": "Casa",
        "language": "en",
        "signature": "Lucía García",
        "children": [{"id": "mateo", "name": "Mateo", "kindergarten": "Hort"}],
        "OPENAI_API_KEY": "do-not-write",
    }, path)
    assert "do-not-write" not in path.read_text(encoding="utf-8")
    assert load_profile(path)["children"] == [{"id": "mateo", "name": "Mateo", "kindergarten": "Hort"}]


def test_store_migrates_existing_cases_table(tmp_path):
    from papelito.store import Store

    path = Path(tmp_path) / "old.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL, sender TEXT, "
        "sender_type TEXT NOT NULL DEFAULT 'kindergarten', event_date TEXT, "
        "status TEXT NOT NULL DEFAULT 'open', language TEXT NOT NULL DEFAULT 'en', "
        "summary TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "due_line TEXT, replied_at TEXT)"
    )
    connection.commit()
    connection.close()

    store = Store(path)
    store.save_case({"id": "case-1", "title": "Notice", "child_id": "mateo"})
    assert store.get_case("case-1")["child_id"] == "mateo"
    assert store.list_cases()[0]["child_id"] == "mateo"
    store.close()
