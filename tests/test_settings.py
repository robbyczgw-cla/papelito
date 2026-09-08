from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_private_photo_directory_can_live_outside_the_checkout(tmp_path, monkeypatch):
    private = tmp_path / "private-photos"
    monkeypatch.setenv("PAPELITO_PRIVATE_PHOTO_DIR", str(private))

    import papelito.store as core_store_module
    import web.pipeline as pipeline_module

    core_store_module = importlib.reload(core_store_module)
    pipeline_module = importlib.reload(pipeline_module)
    assert core_store_module.PRIVATE_PHOTO_ROOT == private
    assert pipeline_module.PHOTO_DIR == private

    monkeypatch.delenv("PAPELITO_PRIVATE_PHOTO_DIR")
    importlib.reload(core_store_module)
    importlib.reload(pipeline_module)


@pytest.fixture
def web_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_DB", str(tmp_path / "cases.db"))
    monkeypatch.setenv("PAPELITO_WATCH_LOG", str(tmp_path / "watchdog-last.json"))
    monkeypatch.setenv("PAPELITO_OUT", str(tmp_path / "out"))
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
    assert len(papers) == 3
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


def test_optional_judge_auth_fails_closed(web_modules, monkeypatch):
    app_module, _ = web_modules
    monkeypatch.setenv("PAPELITO_JUDGE_USERNAME", "judge")
    monkeypatch.setenv("PAPELITO_JUDGE_PASSWORD", "correct-password")
    client = TestClient(app_module.app)

    denied = client.get("/")
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == 'Basic realm="Papelito judges"'
    assert client.get("/", auth=("judge", "wrong-password")).status_code == 401
    assert client.get("/", auth=("judge", "correct-password")).status_code == 200

    monkeypatch.delenv("PAPELITO_JUDGE_PASSWORD")
    assert client.get("/").status_code == 401


def test_judge_mode_requires_credentials_and_protects_assets_and_api(web_modules, monkeypatch):
    app_module, _ = web_modules
    client = TestClient(app_module.app)
    monkeypatch.setenv("PAPELITO_JUDGE_MODE", "1")

    for path in ("/", "/static/app.js", "/manifest.webmanifest", "/sw.js", "/api/cases"):
        assert client.get(path).status_code == 401
    assert client.get("/", headers={"Authorization": "Basic !!!"}).status_code == 401

    monkeypatch.setenv("PAPELITO_JUDGE_USERNAME", "judge")
    monkeypatch.setenv("PAPELITO_JUDGE_PASSWORD", "correct-password")
    assert client.get("/static/app.js", auth=("judge", "correct-password")).status_code == 200
    cases = client.get("/api/cases", auth=("judge", "correct-password"))
    assert cases.status_code == 200
    assert cases.headers["cache-control"] == "no-store"


def test_optional_upload_budget(web_modules, monkeypatch):
    app_module, _ = web_modules
    app_module._UPLOAD_TIMES.clear()
    monkeypatch.setenv("PAPELITO_UPLOADS_PER_HOUR", "2")

    assert app_module._take_upload_slot()
    assert app_module._take_upload_slot()
    assert not app_module._take_upload_slot()

    app_module._UPLOAD_TIMES.clear()
    monkeypatch.setenv("PAPELITO_JUDGE_MODE", "1")
    monkeypatch.setenv("PAPELITO_UPLOADS_PER_HOUR", "invalid")
    assert not app_module._take_upload_slot()
    monkeypatch.setenv("PAPELITO_UPLOADS_PER_HOUR", "0")
    assert not app_module._take_upload_slot()


def test_judge_mode_disables_agentcore(web_modules, monkeypatch):
    app_module, _ = web_modules
    monkeypatch.setenv("PAPELITO_JUDGE_MODE", "1")
    monkeypatch.setenv("PAPELITO_JUDGE_USERNAME", "judge")
    monkeypatch.setenv("PAPELITO_JUDGE_PASSWORD", "correct-password")
    monkeypatch.setattr(app_module.agentcore, "agentcore_enabled", lambda: True)
    client = TestClient(app_module.app)

    status = client.get("/api/demo/agentcore", auth=("judge", "correct-password"))
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    invoked = client.post("/api/demo/agentcore", auth=("judge", "correct-password"))
    assert invoked.status_code == 503
    assert invoked.json()["detail"]["code"] == "no_agentcore"


def test_judge_upload_limit_and_request_size(web_modules, tmp_path, monkeypatch):
    app_module, _ = web_modules
    app_module._UPLOAD_TIMES.clear()
    monkeypatch.setenv("PAPELITO_JUDGE_MODE", "1")
    monkeypatch.setenv("PAPELITO_JUDGE_USERNAME", "judge")
    monkeypatch.setenv("PAPELITO_JUDGE_PASSWORD", "correct-password")
    monkeypatch.setenv("PAPELITO_UPLOADS_PER_HOUR", "1")
    monkeypatch.setattr(app_module.pipeline, "save_photo", lambda _data, _name: tmp_path / "demo.png")
    monkeypatch.setattr(
        app_module.pipeline,
        "new_job",
        lambda _path, _received, _lang: {"job": "test-job", "state": "running", "steps": [], "question": ""},
    )
    client = TestClient(app_module.app)
    auth = ("judge", "correct-password")

    first = client.post("/api/upload", auth=auth, files={"photo": ("demo.png", b"image", "image/png")})
    assert first.status_code == 202
    limited = client.post("/api/upload", auth=auth, files={"photo": ("demo.png", b"image", "image/png")})
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "upload_limit"

    oversized = client.post(
        "/api/upload",
        auth=auth,
        content=b"",
        headers={"content-length": str(app_module.MAX_UPLOAD_REQUEST_BYTES + 1)},
    )
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "too_large"


def test_demo_seed_dates_and_watchdog_transition(web_modules):
    app_module, store_module = web_modules
    client = TestClient(app_module.app)

    response = client.post("/api/demo/seed")
    assert response.status_code == 200
    assert {case["id"] for case in response.json()["cases"]} == {"demo-ausflug", "demo-elternabend"}

    core = store_module.get_store().core
    outing = core.get_case("demo-ausflug")
    assert outing["status"] == "open"
    assert outing["due_line"] is None
    assert outing["event_date"] == "2026-09-11"
    assert [(paper["kind"], paper["received_on"], paper["photo_path"]) for paper in outing["papers"]] == [
        ("original", "2026-09-03", None),
        ("amendment", "2026-09-08", None),
    ]
    actions = {action["id"]: action for action in outing["actions"]}
    assert actions["demo-ausflug-pay"]["deadline_iso"] == "2026-09-07"
    assert actions["demo-ausflug-attend-original"]["deadline_iso"] == "2026-09-09"
    assert actions["demo-ausflug-attend-original"]["status"] == "superseded"
    assert actions["demo-ausflug-attend-amended"]["deadline_iso"] == "2026-09-11"
    assert actions["demo-ausflug-boots"]["deadline_iso"] == "2026-09-11"
    assert actions["demo-ausflug-reply"]["deadline_iso"] == "2026-09-09"

    before = next(case for case in response.json()["cases"] if case["id"] == "demo-ausflug")
    assert before["state"] == "open"
    assert before["reminder"] == ""
    rows = {row["id"]: row for row in before["rows"]}
    assert rows["demo-ausflug-attend-original"]["replaced_by"]["id"] == "demo-ausflug-attend-amended"
    assert [row["id"] for row in rows["demo-ausflug-attend-amended"]["replaces"]] == [
        "demo-ausflug-attend-original"
    ]

    watched = client.post("/api/watch?today=2026-09-05&lang=en")
    assert watched.status_code == 200
    after = core.get_case("demo-ausflug")
    assert after["status"] == "due"
    assert after["due_line"].startswith("In two days: 8 €")
    nagged = watched.json()["away"]["nagged"]
    assert [item["case_id"] for item in nagged] == ["demo-ausflug"]


def test_web_reuses_saved_reader_language_card(web_modules):
    app_module, store_module = web_modules
    core = store_module.get_store().core
    core.save_case({
        "id": "translated-web-card",
        "title": "Ausflug in den Tiergarten",
        "language": "en",
        "papers": [{"received_on": "2026-09-03", "text": "Ausflug"}],
        "actions": [{
            "id": "boots",
            "kind": "bring",
            "action": "Gummistiefel mitbringen",
            "source_line": "Bitte Gummistiefel mitbringen.",
            "status": "active",
            "confidence": 0.99,
        }],
    })
    core.add_artifact("translated-web-card", "card", json.dumps({
        "language": "en",
        "case_id": "translated-web-card",
        "title": "Outing to the zoo",
        "header": "Outing to the zoo",
        "labels": ["what", "do", "by when", "done for you"],
        "rows": [{
            "id": "boots",
            "kind": "bring",
            "what": "bring something",
            "do": "Bring rain boots",
            "deadline_iso": None,
            "done": ["✓ saved to case"],
            "status": "active",
            "superseded_by": None,
            "gate": "ok",
            "question": None,
            "source_line": "Bitte Gummistiefel mitbringen.",
            "confidence": 0.99,
            "amount": None,
        }],
    }))

    case = next(
        item for item in TestClient(app_module.app).get("/api/cases?lang=en").json()["cases"]
        if item["id"] == "translated-web-card"
    )
    assert case["title"] == "Outing to the zoo"
    assert case["rows"][0]["do"] == "Bring rain boots"


def test_web_delete_removes_case_managed_files(web_modules, tmp_path, monkeypatch):
    app_module, store_module = web_modules
    import papelito.store as core_store_module

    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(core_store_module, "PRIVATE_PHOTO_ROOT", private)
    source = private / "source.png"
    crop = private / "source-crop.png"
    source.write_bytes(b"source")
    crop.write_bytes(b"crop")

    case_id = "web-delete"
    core = store_module.get_store().core
    core.save_case({
        "id": case_id,
        "title": "Ausflug",
        "papers": [
            {"received_on": "2026-09-03", "photo_path": str(source), "text": "Original"},
            {"kind": "amendment", "received_on": "2026-09-08", "photo_path": str(crop), "text": "Nachtrag"},
        ],
    })
    output = tmp_path / "out"
    output.mkdir()
    calendar = output / f"{case_id}.ics"
    reply = output / f"{case_id}-antwort.txt"
    calendar.write_text("calendar", encoding="utf-8")
    reply.write_text("reply", encoding="utf-8")

    deleted = TestClient(app_module.app).delete(f"/api/cases/{case_id}")
    assert deleted.status_code == 200
    assert core.get_case(case_id) is None
    assert not source.exists()
    assert not crop.exists()
    assert not calendar.exists()
    assert not reply.exists()


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
