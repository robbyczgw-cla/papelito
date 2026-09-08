"""Core: store, extraction gate, amendment reconciler, card, reply, tools without a model."""

from __future__ import annotations

import sqlite3

import pytest

from papelito import agent as A
from papelito import explain as E
from papelito import extract as X
from papelito import match as M
from papelito.reply import draft_reply
from papelito.store import Store

NOTE = """Kindergarten Sonnenblume
Liebe Eltern,
am Donnerstag, 17.09.2026 findet um 18:30 Uhr
unser Elternabend statt.
Bitte geben Sie bis Samstag, 12.09.2026 bekannt,
ob Sie teilnehmen.
Am 24.09. ist der Kindergarten wegen
Fortbildung geschlossen.
Mit freundlichen Gruessen, das Team"""

FOLLOW_UP = """Kindergarten Sonnenblume
Liebe Eltern,
der Elternabend wird auf Samstag, 19.09.2026 verschoben.
Bitte bringen Sie Hausschuhe mit.
Rückmeldung bitte bis morgen.
Das Team"""

RECEIVED = "2026-09-03"  # a Thursday


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.db")
    yield s
    s.close()


# ------------------------------------------------------------------ dates
@pytest.mark.parametrize("phrase,iso", [
    ("bis Samstag, 12.09.2026", "2026-09-12"),
    ("bis Freitag", "2026-09-04"),
    ("innerhalb von 14 Tagen", "2026-09-17"),
    ("Am 24.09. ist geschlossen", "2026-09-24"),
    ("bis morgen", "2026-09-04"),
    ("17. September 2026", "2026-09-17"),
    ("Ende der Woche", "2026-09-04"),
    ("kein Datum hier", None),
])
def test_local_resolve(phrase, iso):
    assert X._local_resolve(phrase, X._to_date(RECEIVED)) == iso


# ------------------------------------------------------------- extraction
def test_heuristic_extract_keeps_source_and_confidence():
    ext = X.extract(NOTE, RECEIVED)
    by_kind = {a["kind"]: a for a in ext["actions"]}
    assert by_kind["reply"]["deadline_iso"] == "2026-09-12"
    assert by_kind["attend"]["deadline_iso"] == "2026-09-17"
    assert by_kind["closed"]["deadline_iso"] == "2026-09-24"
    for a in ext["actions"]:
        assert a["source_line"] in NOTE
        assert 0 <= a["confidence"] <= 1
        assert a["gate"] in ("ok", "ask", "drop")
    assert ext["event_date"] == "2026-09-17"
    assert ext["sender_type"] == "kindergarten"


def test_verify_lowers_confidence_on_date_mismatch():
    raw = {"actions": [{"kind": "reply", "action": "Rückmeldung", "deadline_phrase": "bis Samstag, 12.09.2026",
                        "deadline_iso": "2026-09-19", "source_line": "Bitte geben Sie bis Samstag, 12.09.2026 bekannt,",
                        "confidence": 0.95}]}
    out = X._verify(raw, NOTE, X._to_date(RECEIVED), True)
    a = out["actions"][0]
    assert a["deadline_iso"] == "2026-09-12"  # deterministic wins
    assert a["confidence"] <= 0.6 and a["gate"] == "ask" and a["question"] == "date"


def test_verify_drops_unknown_source_line():
    raw = {"actions": [{"kind": "pay", "action": "8 € mitgeben", "amount_eur": 8, "deadline_iso": "2026-09-08",
                        "source_line": "dieser Satz steht nicht auf dem Papier", "confidence": 0.9}]}
    a = X._verify(raw, NOTE, X._to_date(RECEIVED), True)["actions"][0]
    assert "source_line_not_found" in a["flags"] and a["gate"] != "ok"


def test_verify_rejects_model_deadline_without_date_evidence():
    text = "Bitte an Fr. Huber abgeben."
    raw = {"actions": [{
        "kind": "info",
        "action": "Bei Fr. Huber abgeben",
        "deadline_phrase": "",
        "deadline_iso": "2026-09-04",
        "source_line": text,
        "confidence": 0.96,
    }]}
    action = X._verify(raw, text, X._to_date("2026-09-01"), True)["actions"][0]
    assert action["deadline_iso"] is None
    assert "date_unverified" in action["flags"]
    assert action["gate"] == "ask"


def test_verify_keeps_model_deadline_backed_by_absolute_source_date():
    text = "Bitte am 04.09.2026 an Fr. Huber abgeben."
    raw = {"actions": [{
        "kind": "info",
        "action": "Bei Fr. Huber abgeben",
        "deadline_phrase": "04.09.2026",
        "deadline_iso": "2026-09-04",
        "source_line": text,
        "confidence": 0.96,
    }]}
    action = X._verify(raw, text, X._to_date("2026-09-01"), True)["actions"][0]
    assert action["deadline_iso"] == "2026-09-04"
    assert "date_unverified" not in action["flags"]
    assert action["gate"] == "ok"


def test_verify_normalizes_money_bring_action_to_pay_and_drafts_reply(tmp_path, monkeypatch):
    text = "Bitte geben Sie Ihrem Kind bis Montag 8 Euro in einem beschrifteten Kuvert mit."
    raw = {"actions": [{
        "kind": "bring",
        "action": "8 Euro in einem Kuvert mitgeben",
        "deadline_phrase": "bis Montag",
        "deadline_iso": "2026-09-07",
        "amount_eur": 8,
        "source_line": text,
        "confidence": 0.96,
    }]}
    action = X._verify(raw, text, X._to_date("2026-09-01"), True)["actions"][0]
    assert action["kind"] == "pay"
    assert action["amount"] == 8.0
    assert action["deadline_iso"] == "2026-09-07"
    assert "kind_normalized_from_money" in action["flags"]
    assert A.needs_reply({"actions": [{**action, "status": "active"}]})

    monkeypatch.setenv("PAPELITO_OUT", str(tmp_path / "out"))
    store = Store(tmp_path / "money.db")
    case_id = store.save_case({
        "title": "Ausflug in den Tiergarten",
        "sender": "Fr. Huber",
        "papers": [{"received_on": "2026-09-01", "text": text}],
        "actions": [{**action, "status": "active"}],
    })
    A.configure(
        store=store,
        profile={"child_name": "Mateo", "parent_name": "Lucía García", "language": "en"},
        use_models=False,
    )
    drafted = A.draft_reply(case_id=case_id)
    assert drafted.get("text")
    assert "skipped" not in drafted
    assert (tmp_path / "out" / f"{case_id}-antwort.txt").is_file()
    store.close()


def test_verify_keeps_non_payment_packing_action_as_bring():
    text = "Bitte geben Sie Ihrem Kind 8 Trinkflaschen mit."
    raw = {"actions": [{
        "kind": "bring",
        "action": "8 Trinkflaschen mitgeben",
        "deadline_phrase": "",
        "deadline_iso": None,
        "amount_eur": None,
        "source_line": text,
        "confidence": 0.96,
    }]}
    action = X._verify(raw, text, X._to_date("2026-09-01"), True)["actions"][0]
    assert action["kind"] == "bring"
    assert action["amount"] is None
    assert "kind_normalized_from_money" not in action["flags"]


def test_weekday_conflict_lowers_confidence():
    note = "Elternabend am Mittwoch, 17.09.2026 um 18:30 Uhr."
    a = X.extract(note, RECEIVED)["actions"][0]
    assert a["deadline_iso"] == "2026-09-17" and "weekday_mismatch" in a["flags"] and a["gate"] == "ask"
    assert X.weekday_conflict("Donnerstag, 17.09.2026", "2026-09-17") is False


def test_amount_regex():
    assert X.find_amount("bitte 8 € in bar") == 8.0
    assert X.find_amount("Kosten: € 12,50") == 12.5
    assert X.find_amount("Ausflug am 17.09.") is None


# ------------------------------------------------------------------ store
def test_store_roundtrip_and_real_delete(store):
    cid = store.save_case({"title": "Elternabend", "sender": "Kindergarten Sonnenblume",
                           "papers": [{"received_on": RECEIVED, "text": NOTE}],
                           "actions": [{"kind": "reply", "action": "Rückmeldung", "deadline_iso": "2026-09-12",
                                        "source_line": "x", "confidence": 0.9}]})
    store.add_artifact(cid, "reply", "Sehr geehrte...")
    assert [c["id"] for c in store.list_open()] == [cid]
    store.mark_due(cid, "Tomorrow: reply")
    assert store.get_case(cid)["status"] == "due"
    assert store.mark_replied(cid)
    assert store.get_case(cid)["status"] == "replied"
    assert store.list_open() == []
    assert store.delete_case(cid)
    assert store.get_case(cid) is None
    con = sqlite3.connect(store.path)
    for table in ("cases", "papers", "actions", "artifacts", "events"):
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert con.execute("PRAGMA secure_delete").fetchone()[0] in (0, 1)  # pragma exists
    assert not store.delete_case(cid)


def test_delete_removes_only_exact_case_owned_files(store, tmp_path, monkeypatch):
    import papelito.store as store_module

    private = tmp_path / "private"
    output = tmp_path / "out"
    private.mkdir()
    output.mkdir()
    monkeypatch.setattr(store_module, "PRIVATE_PHOTO_ROOT", private)
    monkeypatch.setenv("PAPELITO_OUT", str(output))

    original = private / "original.png"
    crop = private / "crop.png"
    shared = private / "shared.png"
    outside = tmp_path / "outside.png"
    for path in (original, crop, shared, outside):
        path.write_bytes(path.name.encode())

    case_id = "case-delete"
    store.save_case({
        "id": case_id,
        "title": "Ausflug",
        "papers": [
            {"received_on": RECEIVED, "photo_path": str(original), "text": "Original"},
            {"received_on": "2026-09-04", "photo_path": str(crop), "text": "Crop"},
            {"received_on": "2026-09-05", "photo_path": str(shared), "text": "Shared"},
            {"received_on": "2026-09-06", "photo_path": str(outside), "text": "Outside"},
        ],
    })
    store.save_case({
        "id": "case-shared",
        "title": "Elternabend",
        "papers": [{"received_on": RECEIVED, "photo_path": str(shared), "text": "Shared"}],
    })

    calendar = output / f"{case_id}.ics"
    reply = output / f"{case_id}-antwort.txt"
    neighbour = output / f"{case_id}-extra.ics"
    for path in (calendar, reply, neighbour):
        path.write_text(path.name, encoding="utf-8")

    assert store.delete_case(case_id)
    assert not original.exists()
    assert not crop.exists()
    assert shared.exists()
    assert outside.exists()
    assert not calendar.exists()
    assert not reply.exists()
    assert neighbour.exists()
    assert store.delete_case("case-shared")
    assert not shared.exists()


def test_cli_delete_removes_exact_outputs(tmp_path, monkeypatch):
    import papelito.store as store_module
    from papelito.cli import main

    private = tmp_path / "private"
    output = tmp_path / "out"
    private.mkdir()
    output.mkdir()
    monkeypatch.setattr(store_module, "PRIVATE_PHOTO_ROOT", private)
    monkeypatch.setenv("PAPELITO_OUT", str(output))

    db = tmp_path / "cli.db"
    case_id = "cli-delete"
    photo = private / "note.png"
    photo.write_bytes(b"note")
    created = Store(db)
    created.save_case({
        "id": case_id,
        "title": "Ausflug",
        "papers": [{"received_on": RECEIVED, "photo_path": str(photo), "text": "Note"}],
    })
    created.close()
    calendar = output / f"{case_id}.ics"
    reply = output / f"{case_id}-antwort.txt"
    calendar.write_text("calendar", encoding="utf-8")
    reply.write_text("reply", encoding="utf-8")

    assert main(["delete", "--db", str(db), case_id]) == 0
    assert not photo.exists()
    assert not calendar.exists()
    assert not reply.exists()


# -------------------------------------------------------------- amendment
def _save_original(store):
    ext = X.extract(NOTE, RECEIVED)
    return store.save_case({"title": ext["title"], "sender": ext["sender"], "sender_type": ext["sender_type"],
                            "event_date": ext["event_date"], "papers": [{"received_on": RECEIVED, "text": NOTE}],
                            "actions": [{k: v for k, v in a.items() if k not in ("flags", "gate", "question")} for a in ext["actions"]]})


def test_follow_up_matches_same_case_and_supersedes(store):
    cid = _save_original(store)
    store.add_artifact(cid, "ics", "BEGIN:VCALENDAR")
    ext2 = X.extract(FOLLOW_UP, "2026-09-08")
    decision = M.match_case(store, {**ext2, "text": FOLLOW_UP})
    assert decision["decision"] == "existing" and decision["case_id"] == cid, decision
    diff = M.apply_amendment(store, cid, {"received_on": "2026-09-08", "text": FOLLOW_UP}, ext2["actions"], meta=ext2)
    kinds_superseded = sorted(a["kind"] for a in diff["superseded"])
    assert kinds_superseded == ["attend", "reply"]
    assert "ics" in diff["stale_artifacts"]
    case = store.get_case(cid)
    active = [a for a in case["actions"] if a["status"] == "active"]
    assert {a["kind"] for a in active} == {"attend", "reply", "bring", "closed"}
    assert next(a for a in active if a["kind"] == "attend")["deadline_iso"] == "2026-09-19"
    assert next(a for a in active if a["kind"] == "reply")["deadline_iso"] == "2026-09-09"
    assert case["event_date"] == "2026-09-19"
    old_attend = next(a for a in case["actions"] if a["kind"] == "attend" and a["status"] == "superseded")
    assert old_attend["superseded_by"] is not None
    assert len(case["papers"]) == 2 and case["papers"][1]["kind"] == "amendment"


def test_unrelated_note_is_new_case(store):
    _save_original(store)
    other = "Zahnarztpraxis Dr. Muster\nKontrolltermin am 02.10.2026 um 9:00 Uhr.\nBitte E-Card mitbringen."
    ext = X.extract(other, "2026-09-08")
    assert M.match_case(store, {**ext, "text": other})["decision"] == "new"


def test_amendment_reopens_replied_case(store):
    cid = _save_original(store)
    store.mark_replied(cid)
    ext2 = X.extract(FOLLOW_UP, "2026-09-08")
    M.apply_amendment(store, cid, {"received_on": "2026-09-08", "text": FOLLOW_UP}, ext2["actions"], meta=ext2)
    assert store.get_case(cid)["status"] == "open"


# ------------------------------------------------------------------- card
def test_card_has_four_columns_source_and_strike(store):
    cid = _save_original(store)
    ext2 = X.extract(FOLLOW_UP, "2026-09-08")
    M.apply_amendment(store, cid, {"received_on": "2026-09-08", "text": FOLLOW_UP}, ext2["actions"], meta=ext2)
    card = E.explain_in("en", store.get_case(cid), done={"ics": True})
    text = card["text"]
    for label in ("what", "do", "by when", "done for you"):
        assert label in text
    assert "~~" in text  # superseded rows struck through
    assert "source: „" in text
    assert "✓ calendar (.ics)" in text and "· German reply drafted" in text
    assert any(r["by_when"].startswith("Sat 19 Sep 2026") for r in card["rows"] if r["status"] == "active")


def test_reminder_line():
    case = {"title": "Ausflug", "sender": "Kindergarten Sonnenblume",
            "actions": [{"kind": "pay", "action": "8 € mitgeben", "amount": 8.0, "deadline_iso": "2026-09-08",
                         "status": "active", "source_line": "x"}]}
    assert E.reminder_line(case, "en", "2026-09-07") == "Tomorrow: Hand in 8 € in cash, Kindergarten Sonnenblume."


# ------------------------------------------------------------------ reply
def test_reply_is_sie_form_by_register(store):
    cid = _save_original(store)
    case = store.get_case(cid)
    prof = {"parent_name": "Lucía García", "child_name": "Mateo", "kindergarten": "Kindergarten Sonnenblume", "answers": {"attend": True}}
    text = draft_reply(case, prof)
    assert text.startswith("Liebes Kindergarten-Team")
    assert "Teilnahme am Elternabend am Donnerstag, 17.09.2026" in text
    assert "Lucía García" in text and "Mateo" in text
    assert not any(w in text.lower().split() for w in ("du", "dein", "euch"))
    case["sender_type"] = "gemeinde"
    amt = draft_reply(case, prof)
    assert amt.startswith("Betreff:") and "Sehr geehrte Damen und Herren," in amt


# --------------------------------------------------- tools without a model
def test_tools_direct_no_model(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_OUT", str(tmp_path / "out"))
    store = Store(tmp_path / "t.db")
    A.SESSION.clear()
    A.configure(store=store, profile={"child_name": "Mateo", "parent_name": "Lucía García", "language": "en"}, use_models=False)
    pid = A.register_paper(NOTE, RECEIVED)["paper_id"]
    ext = A.extract_actions(text=pid, received_on=RECEIVED)
    assert ext["paper_id"] == pid and ext["actions"]
    assert A.match_case(paper_id=pid)["decision"] == "new"
    saved = A.save_case(paper_id=pid)
    cid = saved["case_id"]
    assert saved["result"] == "created"
    ics = A.write_ics(case_id=cid)
    assert ics["events"] == 3 and (tmp_path / "out" / f"{cid}.ics").read_text().count("TRIGGER:-P") == 3
    rep = A.draft_reply(case_id=cid)
    assert "Mateo" in rep["text"]
    card = A.explain_in(language="en", case_id=cid)
    assert "✓ calendar (.ics)" in card["text"]
    # follow-up through the same tools → amendment
    pid2 = A.register_paper(FOLLOW_UP, "2026-09-08")["paper_id"]
    A.extract_actions(text=pid2, received_on="2026-09-08")
    m = A.match_case(paper_id=pid2)
    assert m["case_id"] == cid
    out = A.save_case(paper_id=pid2, case_id=m["case_id"])
    assert out["result"] == "amended" and len(out["superseded"]) == 2
    assert A.list_open()["cases"][0]["case_id"] == cid
    assert A.mark_replied(case_id=cid)["replied"]
    assert A.delete_case(case_id=cid)["deleted"]
    assert A.list_open()["cases"] == []
    assert A.resolve_dates(phrase="bis Freitag", received_on=RECEIVED)["iso"] == "2026-09-04"
    store.close()


# ------------------------------------------------ pending questions, web entry
def test_pending_action_stored_with_question_and_confirmed(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPELITO_OUT", str(tmp_path / "out"))
    store = Store(tmp_path / "t.db")
    A.SESSION.clear()
    A.configure(store=store, profile={"child_name": "Mateo", "parent_name": "Lucía García", "language": "en"}, use_models=False)
    note = "Kindergarten Sonnenblume\nAusflug am Mittwoch, 17.09.2026.\nBitte 8 € bis Freitag mitgeben."
    case = A.process_photo("none.jpg", RECEIVED, text=note)
    assert case and case["id"]
    pending = [a for a in case["actions"] if a["status"] == "pending"]
    assert pending and pending[0]["question"] == "date"  # Mittwoch vs 17.09.2026 (a Thursday)
    card = E.explain_in("en", case)
    row = next(r for r in card["rows"] if r["status"] == "pending")
    assert row["gate"] == "ask" and row["question"].startswith("I could not read the date")
    ics_before = next(a for a in case["artifacts"] if a["kind"] == "ics" and a["status"] == "active")["content"]
    assert ics_before.count("BEGIN:VEVENT") == 1  # only the confident pay action
    assert store.confirm_action(pending[0]["id"], deadline_iso="2026-09-17")
    case = store.get_case(case["id"])
    assert all(a["status"] != "pending" for a in case["actions"])
    assert all(a["status"] == "superseded" for a in case["artifacts"])  # regenerate after the answer
    assert A.write_ics(case_id=case["id"])["events"] == 2
    assert A.compose_reminder(store.get_case(case["id"]), today="2026-09-03", language="en").startswith("Tomorrow: Hand in 8 €")
    store.close()


def test_profile_example_shape(tmp_path):
    from papelito.reply import load_profile

    f = tmp_path / "p.yaml"
    f.write_text('names:\n  parent: "Lucía García"\nchild: "Mateo"\nkindergarten: "Kindergarten Sonnenblume"\n'
                 'address_line: "Demo Street 12, 00000 Demo City"\nreader_language: "English"\nreply_signature: "Lucía García"\n')
    prof = load_profile(f)
    assert prof["parent_name"] == "Lucía García" and prof["child_name"] == "Mateo"
    assert prof["language"] == "en" and prof["signature"] == "Lucía García" and prof["address"].startswith("Demo Street")


def test_follow_up_inherits_amount_and_event_date(store):
    cid = store.save_case({"title": "Ausflug", "sender": "Kindergarten Sonnenblume", "event_date": "2026-09-17",
                           "papers": [{"received_on": RECEIVED, "text": "Ausflug am 17.09.2026. Bitte 8 Euro bis 14.09. mitgeben."}],
                           "actions": [{"kind": "pay", "action": "8 Euro mitgeben", "amount": 8.0, "deadline_iso": "2026-09-14",
                                        "source_line": "Bitte 8 Euro bis 14.09. mitgeben.", "confidence": 0.95}]})
    raw = {"title": "Ausflug", "event_date": "2026-09-18", "actions": [
        {"kind": "pay", "action": "Geld abgeben", "deadline_phrase": "bis morgen", "source_line": "Das Geld bitte bis morgen abgeben.", "confidence": 0.9},
        {"kind": "bring", "action": "Regenstiefel mitgeben", "source_line": "Bitte Regenstiefel mitgeben.", "confidence": 0.9},
    ]}
    text = "Der Ausflug wird auf Freitag, 18.09.2026 verschoben.\nBitte Regenstiefel mitgeben.\nDas Geld bitte bis morgen abgeben."
    ext = X._verify(raw, text, X._to_date("2026-09-08"), True)
    pay = next(a for a in ext["actions"] if a["kind"] == "pay")
    bring = next(a for a in ext["actions"] if a["kind"] == "bring")
    assert pay["gate"] == "ask" and pay["question"] == "amount" and bring["deadline_iso"] is None
    notes = M.enrich_from_case(store.get_case(cid), ext)
    assert len(notes) == 2
    assert pay["amount"] == 8.0 and pay["gate"] == "ok" and pay["question"] is None and pay["deadline_iso"] == "2026-09-09"
    assert bring["deadline_iso"] == "2026-09-18" and bring["gate"] == "ok"


def test_info_do_column_quotes_german_for_non_german_readers():
    action = {
        "kind": "info",
        "action": "Ruhephase von 12:45 – 13:45 Uhr",
        "source_line": "12:45 – 13:45 Uhr: Ruhephase",
        "confidence": 0.9,
    }
    en = E.action_line(action, "en")
    de = E.action_line(action, "de")
    assert en.startswith("“") and en.endswith("”")
    assert de == "Ruhephase von 12:45 – 13:45 Uhr"
    assert "Ruhephase" in en
    translated = E.action_line(action, "en", translated="Rest period from 12:45 to 13:45")
    assert translated == "Rest period from 12:45 to 13:45"


def test_model_translation_covers_reader_title_and_actions(monkeypatch):
    import strands

    class FakeAgent:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _payload):
            return '{"0":"Bring rain boots","__title__":"Outing to the zoo"}'

    monkeypatch.setattr(strands, "Agent", FakeAgent)
    card = E.explain_in("en", {
        "id": "translated-card",
        "title": "Ausflug in den Tiergarten",
        "actions": [{
            "id": "boots",
            "kind": "bring",
            "action": "Gummistiefel mitbringen",
            "source_line": "Bitte Gummistiefel mitbringen.",
            "status": "active",
            "confidence": 0.99,
        }],
    }, model=object())

    assert card["title"] == "Outing to the zoo"
    assert card["rows"][0]["do"] == "Bring: Bring rain boots"
