"""Case store for the Papelito web app.

The core owns ``papelito/store.py``. This module is a thin adapter over it:

* if ``papelito.store`` is importable, the page reads and writes the real case
  file through its ``Store`` class;
* otherwise an equivalent SQLite store here keeps the page usable on its own.

The interface either backend offers::

    list_open(lang)              -> list[dict]   not replied, due ones included
    list_all(lang)               -> list[dict]   including replied and closed
    get(case_id, lang)           -> dict | None
    save_case(case)              -> str          returns the case id
    mark_replied(case_id)        -> bool
    mark_due(case_id, reminder)  -> bool         watchdog: the case turns "due"
    record_answer(case_id, ans)  -> bool         confidence gate, human answer
    set_child_id(case_id, child_id) -> bool      assign or clear a child
    delete_case(case_id)         -> bool         really deletes the row

``normalize`` flattens either shape into what the page renders: a case with one
row per action, each row carrying what / do / by when / done for you, in the
UI language is English by default.

Fake clock: set ``PAPELITO_TODAY=2026-09-10`` to move "today" (gate 3, video).
Database path: ``PAPELITO_DB`` (both backends read it).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

DUE_WINDOW_DAYS = 2

REPO_ROOT = Path(__file__).resolve().parent.parent
# PAPELITO_DB is the case file both the CLI and this page use. Without it the
# core store picks its own XDG default; the fallback store below keeps its own
# file, whose schema must never land in the core's.
DB_PATH = Path(os.environ.get("PAPELITO_DB") or REPO_ROOT / "data" / "papelito-web.db")

LANGS = ("en", "de")
DEFAULT_LANG = "en"

# Same tables as papelito.explain, kept here so the page works without the core.
LABELS = {
    "en": ("what", "do", "by when", "done for you"),
    "de": ("was", "tun", "bis wann", "erledigt"),
}
# The states papelito.store accepts. Never write anything else into the case file.
CORE_STATES = ("open", "due", "replied", "closed")

# The fourth column of the fallback (flat) case: one line per tool, ticked as it runs.
DEFAULT_STEP_KEYS = ("read", "dates", "calendar", "reply")
STEP_LABELS = {
    "en": {"read": "read", "dates": "dates", "calendar": "calendar", "reply": "reply"},
    "de": {"read": "gelesen", "dates": "Fristen", "calendar": "Kalender", "reply": "Antwort"},
}

# papelito.explain writes for a terminal card; a 390 px column needs it shorter.
SHORT_DONE = {
    "en": {"calendar (.ics)": "calendar", "German reply drafted": "German reply",
           "reminder 2 days before": "reminder", "saved to case": "saved",
           "case updated": "updated", "unreadable, no artifact": "unreadable"},
    "de": {"Kalender (.ics)": "Kalender", "Antwort (DE) entworfen": "Antwort",
           "Erinnerung 2 Tage vorher": "Erinnerung", "im Akt gespeichert": "gespeichert",
           "Akt aktualisiert": "aktualisiert", "unleserlich, kein Artefakt": "unleserlich"},
}
# The mark on a row that replaced an older line (the amendment reconciler ran).
UPDATED_MARK = {"en": "updated from a later note", "de": "aus späterer Mitteilung aktualisiert",
                }

MONTHS_SHORT = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "de": ["Jän", "Feb", "März", "Apr", "Mai", "Juni", "Juli", "Aug", "Sep", "Okt", "Nov", "Dez"],
}
WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
}
NO_DATE = {"en": "no date", "de": "kein Datum"}

GATE_THRESHOLD = 0.7
# The card asks instead of guessing. The store keeps the confidence, not the gate.
ASK = {
    "en": "This line was not read with confidence. Does it say what the card says?",
    "de": "Diese Zeile wurde nicht sicher gelesen. Steht dort, was die Karte sagt?",
}
REREAD = {"en": "Marked to re-read the photo.", "de": "Zum erneuten Lesen des Fotos vorgemerkt."}


def lang_code(value: Any, default: str = DEFAULT_LANG) -> str:
    """Normalise an English or German language label to a supported code."""
    v = str(value or "").strip().lower()
    v = {"english": "en", "german": "de", "deutsch": "de"}.get(v, v[:2])
    return v if v in LANGS else default


def today() -> date:
    """Today, or the fake clock in PAPELITO_TODAY."""
    stamp = os.environ.get("PAPELITO_TODAY")
    if stamp:
        try:
            return date.fromisoformat(stamp.strip()[:10])
        except ValueError:
            pass
    return date.today()


def parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def format_date(value: Any, lang: str = DEFAULT_LANG) -> str:
    """Short kitchen-table date: 'Fri 4 Sep' / 'Fr 4. Sep' / 'vie 4 sep.'."""
    day = parse_date(value)
    if not day:
        return ""
    lang = lang_code(lang)
    wd, mon = WEEKDAYS[lang][day.weekday()], MONTHS_SHORT[lang][day.month - 1]
    if lang == "de":
        return f"{wd} {day.day}. {mon}"
    return f"{wd} {day.day} {mon}"


def _amount_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):g} €"
    except (TypeError, ValueError):
        return str(value)


# ------------------------------------------------------------- normalisation

def _mark(text: str, lang: str) -> dict:
    """'✓ calendar (.ics)' -> {'label': 'calendar', 'state': 'done'}."""
    body = text.strip()
    state = "pending"
    for prefix, name in (("✓", "done"), ("·", "pending"), ("?", "blocked")):
        if body.startswith(prefix):
            state, body = name, body[len(prefix):].strip()
            break
    short = SHORT_DONE[lang].get(body)
    if short is None:  # the core may answer in another language than asked; keep it readable
        for table in SHORT_DONE.values():
            short = table.get(body)
            if short:
                break
    return {"label": short or body, "state": state}


def _gate(row: dict) -> str:
    if row.get("gate") in ("ask", "drop"):
        return row["gate"]
    return "ask" if float(row.get("confidence") or 1.0) < GATE_THRESHOLD else "ok"


def _child_fields(raw: dict) -> tuple[str, str]:
    child_id = str(raw.get("child_id") or "").strip()
    child_name = str(raw.get("child_name") or "").strip()
    if not child_id:
        return "", child_name
    try:
        from papelito.reply import load_profile  # type: ignore

        profile = load_profile()
    except Exception:
        profile = {}
    child = next(
        (item for item in profile.get("children", [])
         if isinstance(item, dict) and str(item.get("id") or "") == child_id),
        None,
    )
    if child:
        child_name = str(child.get("name") or "").strip()
    return child_id, child_name


def _child_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _explain(case: dict, lang: str) -> dict | None:
    """The reader-language card from the core. Deterministic, no model call."""
    try:
        from papelito import explain  # type: ignore
    except Exception:
        return None
    done = {a["kind"]: True for a in case.get("artifacts", []) if a.get("status") == "active"}
    done["saved"] = True
    has_deadline = any(a.get("deadline_iso") for a in case.get("actions", []))
    done["reminder"] = has_deadline and case.get("status") in ("open", "due")
    try:
        return explain.explain_in(lang, case, None, done)
    except Exception:
        return None


def _core_reminder(case: dict, lang: str) -> str:
    """The watchdog's wording, in the UI language, for cases it has not reached yet."""
    try:
        from papelito import explain  # type: ignore

        return explain.reminder_line(case, lang, today()) or ""
    except Exception:
        return ""


def _core_rows(case: dict, lang: str) -> list[dict]:
    """One row per action: what / do / by when / done for you."""
    card = _explain(case, lang)
    if card:
        return [
            {
                "id": row.get("id") or "",
                "kind": row.get("kind") or "",
                "what": row.get("what") or "",
                "do": row.get("do") or "",
                "deadline": row.get("deadline_iso") or "",
                "done": [_mark(m, lang) for m in row.get("done") or []],
                "status": row.get("status") or "active",
                "superseded_by": row.get("superseded_by") or "",
                "gate": _gate(row),
                "question": row.get("question") or "",
                "source_line": row.get("source_line") or "",
                "confidence": float(row.get("confidence") or 1.0),
                "amount": _amount_text(row.get("amount")),
            }
            for row in card.get("rows", [])
        ]
    # papelito.explain missing: the German action wording is still true.
    return [
        {
            "id": a.get("id") or "",
            "kind": a.get("kind") or "",
            "what": a.get("kind") or "",
            "do": a.get("action") or "",
            "deadline": a.get("deadline_iso") or "",
            "done": [],
            "status": a.get("status") or "active",
            "superseded_by": a.get("superseded_by") or "",
            "gate": _gate(a),
            "question": "",
            "source_line": a.get("source_line") or "",
            "confidence": float(a.get("confidence") or 1.0),
            "amount": _amount_text(a.get("amount")),
        }
        for a in case.get("actions", [])
    ]


def _link_amendments(rows: list[dict], lang: str) -> None:
    """Pair each superseded row with the row that replaced it, both ways.

    The core's ``_ordered`` puts the old row right after its replacement, but the
    ``superseded_by`` id is the reliable link. A row that replaced something gets
    an extra done-mark: the amendment reconciler really ran for it.
    """
    by_id = {r["id"]: r for r in rows if r["id"]}
    for row in rows:
        if row["status"] != "superseded":
            continue
        new = by_id.get(row["superseded_by"])
        if new is None or new is row:
            continue
        row["replaced_by"] = {"id": new["id"], "deadline": new["deadline"], "do": new["do"]}
        new.setdefault("replaces", []).append({"id": row["id"], "deadline": row["deadline"], "do": row["do"]})
        if new["status"] == "active" and all(m["label"] != UPDATED_MARK[lang] for m in new["done"]):
            new["done"].append({"label": UPDATED_MARK[lang], "state": "done"})


def _from_core(raw: dict, lang: str) -> dict:
    """A case as papelito.store keeps it: cases + papers + actions + artifacts."""
    rows = _core_rows(raw, lang)
    _link_amendments(rows, lang)
    active = [r for r in rows if r["status"] == "active" and r["deadline"]]
    papers = raw.get("papers") or []
    artifacts = [a for a in raw.get("artifacts", []) if a.get("status") == "active"]
    reply = next((a["content"] for a in artifacts if a.get("kind") == "reply"), "")
    answered = any(e.get("kind") == "ui:answer" for e in raw.get("events", []))
    amendments = [p for i, p in enumerate(papers) if i > 0 or p.get("kind") == "amendment"]
    case_lang = lang_code(raw.get("language"), "en")
    child_id, child_name = _child_fields(raw)
    # The watchdog wrote its line in the profile language. Another UI language gets a fresh one.
    reminder = (raw.get("due_line") or "") if case_lang == lang else ""
    return {
        "id": str(raw.get("id")),
        "child_id": child_id,
        "child_name": child_name,
        "status": (raw.get("status") or "open").lower(),
        "sender": raw.get("sender") or "",
        "what": raw.get("title") or "Kindergarten",
        "rows": rows,
        "labels": list(LABELS[lang]),
        "lang": lang,
        "deadline": min((r["deadline"] for r in active), default=""),
        "reminder": reminder or _core_reminder(raw, lang),
        "reply_de": reply,
        "photo": (papers[-1].get("photo_path") if papers else "") or "",
        "received_on": (papers[0].get("received_on") if papers else "") or "",
        "paper_count": len(papers),
        "amended_on": (amendments[-1].get("received_on") if amendments else "") or "",
        "answered": answered,
        "created_at": raw.get("created_at") or "",
        # The untouched core case, for papelito.ics and papelito.reply.
        "_raw": raw,
    }


def _steps(value: Any, lang: str) -> list[dict]:
    default = [{"label": STEP_LABELS[lang][k], "state": "pending"} for k in DEFAULT_STEP_KEYS]
    if not value:
        return default
    steps = []
    for item in value:
        if isinstance(item, str):
            steps.append(_mark(item, lang) if item[:1] in "✓·?" else {"label": item, "state": "done"})
        elif isinstance(item, dict):
            key = item.get("key") or ""
            steps.append({
                "label": STEP_LABELS[lang].get(key) or item.get("label") or key,
                "state": item.get("state") or ("done" if item.get("done") else "pending"),
            })
    return steps or default


def _from_flat(raw: dict, lang: str) -> dict:
    """A case as this module's own SQLite store keeps it: one row, flat fields."""
    case = dict(raw)
    case["id"] = str(raw.get("id") or raw.get("case_id") or uuid.uuid4())
    case["status"] = (raw.get("status") or "open").lower()
    if raw.get("replied_at"):
        case["status"] = "replied"
    case["labels"] = list(LABELS[lang])
    case["lang"] = lang
    case["child_id"], case["child_name"] = _child_fields(raw)
    case["created_at"] = raw.get("created_at") or datetime.now().isoformat(timespec="seconds")
    case["rows"] = [
        {
            "id": f"{case['id']}-a1",
            "kind": "",
            "what": raw.get("what") or {"en": "Unread note", "de": "Ungelesenes Papier"}[lang],
            "do": raw.get("do") or "",
            "deadline": raw.get("deadline") or "",
            "done": _steps(raw.get("steps"), lang),
            "status": "active",
            "superseded_by": "",
            "gate": _gate(raw),
            "question": raw.get("question") or "",
            "source_line": raw.get("source_line") or "",
            "confidence": float(raw.get("confidence") or 1.0),
            "amount": raw.get("amount") or "",
        }
    ]
    for n, old in enumerate(raw.get("amended") or [], start=2):
        case["rows"].append({
            "id": f"{case['id']}-a{n}", "kind": "",
            "what": "", "do": old.get("label") if isinstance(old, dict) else str(old),
            "deadline": old.get("deadline", "") if isinstance(old, dict) else "",
            "done": [], "status": "superseded", "superseded_by": f"{case['id']}-a1", "gate": "ok",
            "question": "", "source_line": old.get("reason", "") if isinstance(old, dict) else "",
            "confidence": 1.0, "amount": "",
        })
    _link_amendments(case["rows"], lang)
    case_lang = lang_code(raw.get("language"), "en")
    case["reminder"] = (raw.get("due_line") or "") if case_lang == lang else ""
    case["paper_count"] = 1 + len(raw.get("amended") or [])
    case["amended_on"] = raw.get("amended_on") or ""
    case["answered"] = bool(raw.get("human_answer")) or any(
        e.get("kind") == "ui:answer" for e in raw.get("events") or []
    )
    return case


def normalize(raw: dict, lang: str = DEFAULT_LANG) -> dict:
    """Either store's case dict, in the shape the page renders, in ``lang``."""
    lang = lang_code(lang)
    if "actions" in raw or "papers" in raw:
        return _from_core(raw, lang)
    return _from_flat(raw, lang)


def state_of(case: dict, ref: date | None = None) -> str:
    """open | due | overdue | replied. The watchdog sets status='due'."""
    if case.get("status") in ("replied", "closed"):
        return "replied"
    ref = ref or today()
    deadline = parse_date(case.get("deadline"))
    if deadline:
        if deadline < ref:
            return "overdue"
        if (deadline - ref).days <= DUE_WINDOW_DAYS:
            return "due"
    if case.get("status") == "due":
        return "due"
    return "open"


def sort_key(case: dict, ref: date | None = None):
    """Due cases first, then by deadline; replied sink to the bottom."""
    ref = ref or today()
    rank = {"overdue": 0, "due": 1, "open": 2, "replied": 3}[state_of(case, ref)]
    deadline = parse_date(case.get("deadline"))
    return (rank, deadline or date.max, case.get("created_at") or "")


class SqliteStore:
    """Standalone store, used when papelito.store is not importable.

    Cases are kept as given and normalised on the way out, so a case written in
    the core's shape survives the round trip unchanged.
    """

    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS cases ("
                " id TEXT PRIMARY KEY,"
                " status TEXT NOT NULL DEFAULT 'open',"
                " deadline TEXT,"
                " created_at TEXT NOT NULL,"
                " payload TEXT NOT NULL)"
            )

    def _db(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def _raw(self, where: str = "", args: tuple = ()) -> list[dict]:
        with self._db() as db:
            rows = db.execute(f"SELECT payload FROM cases {where}", args).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def list_all(self, lang: str = DEFAULT_LANG) -> list[dict]:
        return [normalize(raw, lang) for raw in self._raw()]

    def list_open(self, lang: str = DEFAULT_LANG) -> list[dict]:
        return [normalize(raw, lang) for raw in self._raw("WHERE status NOT IN ('replied', 'closed')")]

    def get(self, case_id: str, lang: str = DEFAULT_LANG) -> dict | None:
        raw = self._raw("WHERE id = ?", (case_id,))
        return normalize(raw[0], lang) if raw else None

    def save_case(self, case: dict) -> str:
        card = normalize(case)
        raw = {k: v for k, v in case.items() if not k.startswith("_")}
        raw["id"] = card["id"]
        with self._db() as db:
            db.execute(
                "INSERT INTO cases (id, status, deadline, created_at, payload)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET"
                " status=excluded.status, deadline=excluded.deadline, payload=excluded.payload",
                (
                    card["id"],
                    card["status"],
                    card.get("deadline") or None,
                    card["created_at"] or datetime.now().isoformat(timespec="seconds"),
                    json.dumps(raw, ensure_ascii=False),
                ),
            )
        return card["id"]

    def _patch(self, case_id: str, **fields) -> bool:
        raw = self._raw("WHERE id = ?", (case_id,))
        if not raw:
            return False
        self.save_case({**raw[0], **fields})
        return True

    def mark_replied(self, case_id: str) -> bool:
        return self._patch(
            case_id, status="replied", replied_at=datetime.now().isoformat(timespec="seconds")
        )

    def mark_due(self, case_id: str, reminder: str = "") -> bool:
        fields: dict[str, Any] = {"status": "due"}
        if reminder:
            fields["due_line"] = reminder
        return self._patch(case_id, **fields)

    def record_answer(self, case_id: str, answer: str, lang: str = DEFAULT_LANG) -> bool:
        raw = self._raw("WHERE id = ?", (case_id,))
        if not raw:
            return False
        events = list(raw[0].get("events") or [])
        events.append({"kind": "ui:answer", "detail": answer})
        return self._patch(case_id, events=events, human_answer=answer,
                           question="" if answer == "yes" else REREAD[lang_code(lang)])

    def delete_case(self, case_id: str) -> bool:
        """Really deletes: the row is gone, not flagged."""
        with self._db() as db:
            return db.execute("DELETE FROM cases WHERE id = ?", (case_id,)).rowcount > 0

    def set_child_id(self, case_id: str, child_id: str | None) -> bool:
        raw = self._raw("WHERE id = ?", (case_id,))
        if not raw:
            return False
        raw[0]["child_id"] = _child_value(child_id)
        self.save_case(raw[0])
        return True


def _euros(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"[-+]?[0-9]+(?:[.,][0-9]+)?", str(value))
    return float(match.group().replace(",", ".")) if match else None


def to_core(case: dict) -> dict:
    """This module's flat case, in the shape papelito.store.save_case expects.

    Nested ids are derived from the case id, so saving twice does not duplicate
    the paper or the actions.
    """
    if "actions" in case or "papers" in case:
        return case
    cid = case.get("id") or str(uuid.uuid4())
    row_kind = "pay" if case.get("amount") else "reply" if case.get("deadline") else "info"
    actions = [{
        "id": f"{cid}-a1",
        "kind": row_kind,
        "action": case.get("do") or case.get("what") or "Papelito",
        "deadline_iso": case.get("deadline") or None,
        "amount": _euros(case.get("amount")),
        "source_line": case.get("source_line") or "",
        "confidence": float(case.get("confidence") or 1.0),
    }]
    for n, old in enumerate(case.get("amended") or [], start=2):
        label = old.get("label") if isinstance(old, dict) else str(old)
        actions.append({
            "id": f"{cid}-a{n}", "kind": "info", "action": label,
            "source_line": case.get("source_line") or "", "confidence": 1.0,
            "status": "superseded", "superseded_by": f"{cid}-a1",
        })
    status = case.get("status")
    core = {
        "id": cid,
        "title": case.get("what") or "Papelito",
        "sender": case.get("sender") or None,
        "child_id": _child_value(case.get("child_id")),
        "status": status if status in CORE_STATES else "open",
        "language": lang_code(case.get("language"), "en"),
        "summary": case.get("do") or None,
        "papers": [{
            "id": f"{cid}-p1",
            "received_on": case.get("received_on") or today().isoformat(),
            "photo_path": case.get("photo") or None,
            "text": case.get("source_line") or "",
        }],
        "actions": actions,
    }
    if case.get("reply_de"):
        core["artifacts"] = [{"kind": "reply", "content": case["reply_de"]}]
    return core


class CoreStore:
    """The real case file: papelito.store.Store."""

    def __init__(self, core_store):
        self.core = core_store

    def list_all(self, lang: str = DEFAULT_LANG) -> list[dict]:
        return [normalize(row, lang) for row in self.core.list_cases()]

    def list_open(self, lang: str = DEFAULT_LANG) -> list[dict]:
        return [normalize(row, lang) for row in self.core.list_open()]

    def get(self, case_id: str, lang: str = DEFAULT_LANG) -> dict | None:
        row = self.core.get_case(case_id)
        return normalize(row, lang) if row else None

    def save_case(self, case: dict) -> str:
        core_case = to_core(case)
        case_id = str(self.core.save_case(core_case))
        if core_case.get("status") == "due":
            self.core.mark_due(case_id, case.get("reminder") or case.get("due_line") or "")
        return case_id

    def mark_replied(self, case_id: str) -> bool:
        return bool(self.core.mark_replied(case_id))

    def mark_due(self, case_id: str, reminder: str = "") -> bool:
        self.core.mark_due(case_id, reminder)
        return True

    def record_answer(self, case_id: str, answer: str, lang: str = DEFAULT_LANG) -> bool:
        """Kept as a case event, so the agent's trace shows who confirmed what."""
        self.core.log_event(case_id, "ui:answer", answer)
        return True

    def delete_case(self, case_id: str) -> bool:
        return bool(self.core.delete_case(case_id))

    def set_child_id(self, case_id: str, child_id: str | None) -> bool:
        return bool(self.core.set_child_id(case_id, child_id))


_store = None


def get_store():
    """The core case file when papelito.store is there, this module's own until then."""
    global _store
    if _store is None:
        _store = None if os.environ.get("PAPELITO_WEB_STORE", "auto") == "auto" else False
        if _store is None:
            try:
                from papelito.store import get_store as core_get_store  # type: ignore

                _store = CoreStore(core_get_store(str(DB_PATH) if os.environ.get("PAPELITO_DB") else None))
            except Exception:
                _store = None
        if not isinstance(_store, CoreStore):
            _store = SqliteStore()
    return _store


def backend_name() -> str:
    return "papelito.store" if isinstance(get_store(), CoreStore) else "web sqlite"
