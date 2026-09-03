"""SQLite case file for Papelito.

One Kindergarten event is one *case*. A case collects several papers (the
original note and its amendments), the actions they demand, and the artifacts
the agent produced (calendar file, German reply, reader-language card).

Case states, shared with the watchdog and the web app:

    open     saved, at least one active action, reply not yet sent
    due      watchdog found a deadline within 2 days and no reply; reminder logged
    replied  the human marked the reply as sent (``papelito done <case>``)
    closed   deadline passed and the "did you send it?" question was answered

Action states: ``active`` (artifact-worthy), ``pending`` (confidence gate: one
question open, no artifact yet), ``superseded`` (replaced by an amendment),
``done``, ``dropped`` (unreadable, human gave no answer).

``delete_case`` really deletes: rows go, ``secure_delete`` zeroes the freed
pages, and the file is vacuumed.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

OPEN_STATES = ("open", "due")
ALL_STATES = ("open", "due", "replied", "closed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    sender       TEXT,
    sender_type  TEXT NOT NULL DEFAULT 'kindergarten',
    event_date   TEXT,
    status       TEXT NOT NULL DEFAULT 'open',
    language     TEXT NOT NULL DEFAULT 'en',
    child_id     TEXT,
    summary      TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    due_line     TEXT,
    replied_at   TEXT
);
CREATE TABLE IF NOT EXISTS papers (
    id           TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL DEFAULT 'original',
    received_on  TEXT NOT NULL,
    photo_path   TEXT,
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    paper_id      TEXT REFERENCES papers(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL,
    action        TEXT NOT NULL,
    deadline_iso  TEXT,
    amount        REAL,
    source_line   TEXT NOT NULL,
    confidence    REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    superseded_by TEXT,
    question      TEXT,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    id         TEXT PRIMARY KEY,
    case_id    TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,
    content    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id    TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    at         TEXT NOT NULL,
    kind       TEXT NOT NULL,
    detail     TEXT
);
CREATE INDEX IF NOT EXISTS actions_case ON actions(case_id, status);
CREATE INDEX IF NOT EXISTS cases_status ON cases(status);
"""


def default_db_path() -> Path:
    env = os.environ.get("PAPELITO_DB")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / "data" / "papelito.db"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _child_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _language(value: Any) -> str:
    code = str(value or "en").strip().lower()[:2]
    return "de" if code == "de" else "en"


class Store:
    """Thin wrapper over one SQLite file. Every method opens a short transaction."""

    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA secure_delete = ON")
        self._conn.executescript(SCHEMA)
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(cases)")}
        if "child_id" not in columns:
            self._conn.execute("ALTER TABLE cases ADD COLUMN child_id TEXT")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ----------------------------------------------------------------- cases
    def save_case(self, case: dict[str, Any]) -> str:
        """Insert a new case or update an existing one.

        ``case`` keys: id (optional), title, sender, sender_type, event_date,
        language, child_id, summary, papers[], actions[], artifacts[].
        Nested papers/actions/artifacts without an id are appended.
        Returns the case id.
        """
        now = _now()
        case_id = case.get("id") or _new_id("case")
        with self._tx() as c:
            row = c.execute("SELECT id FROM cases WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO cases (id, title, sender, sender_type, event_date, status, language,"
                    " child_id, summary, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        case_id,
                        case.get("title") or "Kindergarten",
                        case.get("sender"),
                        case.get("sender_type") or "kindergarten",
                        case.get("event_date"),
                        case.get("status") or "open",
                        _language(case.get("language")),
                        _child_value(case.get("child_id")),
                        case.get("summary"),
                        now,
                        now,
                    ),
                )
            else:
                sets, vals = [], []
                for k in ("title", "sender", "sender_type", "event_date", "language", "summary", "status"):
                    if case.get(k) is not None:
                        sets.append(f"{k} = ?")
                        vals.append(case[k])
                if "child_id" in case:
                    sets.append("child_id = ?")
                    vals.append(_child_value(case["child_id"]))
                sets.append("updated_at = ?")
                vals.append(now)
                vals.append(case_id)
                c.execute(f"UPDATE cases SET {', '.join(sets)} WHERE id = ?", vals)
            for paper in case.get("papers", []):
                self._insert_paper(c, case_id, paper, now)
            for action in case.get("actions", []):
                self._insert_action(c, case_id, action, now)
            for art in case.get("artifacts", []):
                self._insert_artifact(c, case_id, art, now)
        return case_id

    def _insert_paper(self, c: sqlite3.Connection, case_id: str, paper: dict, now: str) -> str:
        pid = paper.get("id") or _new_id("paper")
        if c.execute("SELECT 1 FROM papers WHERE id = ?", (pid,)).fetchone():
            return pid
        c.execute(
            "INSERT INTO papers (id, case_id, kind, received_on, photo_path, text, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (pid, case_id, paper.get("kind", "original"), paper["received_on"],
             paper.get("photo_path"), paper.get("text", ""), now),
        )
        return pid

    def _insert_action(self, c: sqlite3.Connection, case_id: str, a: dict, now: str) -> str:
        aid = a.get("id") or _new_id("act")
        if c.execute("SELECT 1 FROM actions WHERE id = ?", (aid,)).fetchone():
            return aid
        c.execute(
            "INSERT INTO actions (id, case_id, paper_id, kind, action, deadline_iso, amount, source_line,"
            " confidence, status, superseded_by, question, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, case_id, a.get("paper_id"), a.get("kind", "info"), a["action"], a.get("deadline_iso"),
             a.get("amount"), a.get("source_line", ""), float(a.get("confidence", 1.0)),
             a.get("status", "active"), a.get("superseded_by"), a.get("question"), now),
        )
        return aid

    def _insert_artifact(self, c: sqlite3.Connection, case_id: str, art: dict, now: str) -> str:
        aid = art.get("id") or _new_id("art")
        # A new artifact of a kind supersedes the active one of the same kind.
        c.execute(
            "UPDATE artifacts SET status = 'superseded' WHERE case_id = ? AND kind = ? AND status = 'active'",
            (case_id, art["kind"]),
        )
        c.execute(
            "INSERT INTO artifacts (id, case_id, kind, content, status, created_at) VALUES (?,?,?,?,?,?)",
            (aid, case_id, art["kind"], art["content"], "active", now),
        )
        return aid

    def add_paper(self, case_id: str, paper: dict) -> str:
        with self._tx() as c:
            pid = self._insert_paper(c, case_id, paper, _now())
            c.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (_now(), case_id))
        return pid

    def add_actions(self, case_id: str, actions: list[dict]) -> list[str]:
        ids = []
        with self._tx() as c:
            for a in actions:
                ids.append(self._insert_action(c, case_id, a, _now()))
            c.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (_now(), case_id))
        return ids

    def set_child_id(self, case_id: str, child_id: str | None) -> bool:
        """Attach a case to a child, or clear its child assignment."""
        value = _child_value(child_id)
        with self._tx() as c:
            cur = c.execute(
                "UPDATE cases SET child_id = ?, updated_at = ? WHERE id = ?",
                (value, _now(), case_id),
            )
        return cur.rowcount > 0

    def add_artifact(self, case_id: str, kind: str, content: str) -> str:
        with self._tx() as c:
            return self._insert_artifact(c, case_id, {"kind": kind, "content": content}, _now())

    def supersede_actions(self, action_ids: list[str], by: str | None) -> None:
        if not action_ids:
            return
        with self._tx() as c:
            c.executemany(
                "UPDATE actions SET status = 'superseded', superseded_by = ? WHERE id = ?",
                [(by, aid) for aid in action_ids],
            )

    def confirm_action(self, action_id: str, deadline_iso: str | None = None, amount: float | None = None,
                       action: str | None = None) -> bool:
        """Human answered the one question: the pending action becomes active with confidence 1.0."""
        sets, vals = ["status = 'active'", "confidence = 1.0", "question = NULL"], []
        if deadline_iso:
            sets.append("deadline_iso = ?")
            vals.append(deadline_iso)
        if amount is not None:
            sets.append("amount = ?")
            vals.append(amount)
        if action:
            sets.append("action = ?")
            vals.append(action)
        vals.append(action_id)
        with self._tx() as c:
            cur = c.execute(f"UPDATE actions SET {', '.join(sets)} WHERE id = ?", vals)
            if cur.rowcount:
                row = c.execute("SELECT case_id FROM actions WHERE id = ?", (action_id,)).fetchone()
                c.execute("UPDATE artifacts SET status = 'superseded' WHERE case_id = ? AND status = 'active'", (row["case_id"],))
                c.execute("INSERT INTO events (case_id, at, kind, detail) VALUES (?,?,?,?)",
                          (row["case_id"], _now(), "confirmed", action_id))
        return cur.rowcount > 0

    def drop_action(self, action_id: str) -> bool:
        """No answer: the item stays visible as unreadable and never becomes an artifact."""
        with self._tx() as c:
            cur = c.execute("UPDATE actions SET status = 'dropped', question = NULL WHERE id = ?", (action_id,))
        return cur.rowcount > 0

    def supersede_artifacts(self, case_id: str) -> list[str]:
        """Mark every active artifact stale (after an amendment). Returns their kinds."""
        with self._tx() as c:
            kinds = [r["kind"] for r in c.execute(
                "SELECT kind FROM artifacts WHERE case_id = ? AND status = 'active'", (case_id,))]
            c.execute("UPDATE artifacts SET status = 'superseded' WHERE case_id = ? AND status = 'active'", (case_id,))
        return kinds

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        c = self._conn
        row = c.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        case = dict(row)
        case["papers"] = [dict(r) for r in c.execute(
            "SELECT * FROM papers WHERE case_id = ? ORDER BY received_on, created_at", (case_id,))]
        case["actions"] = [dict(r) for r in c.execute(
            "SELECT * FROM actions WHERE case_id = ? ORDER BY created_at, id", (case_id,))]
        case["artifacts"] = [dict(r) for r in c.execute(
            "SELECT * FROM artifacts WHERE case_id = ? ORDER BY created_at", (case_id,))]
        case["events"] = [dict(r) for r in c.execute(
            "SELECT * FROM events WHERE case_id = ? ORDER BY id", (case_id,))]
        return case

    def list_cases(self, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        c = self._conn
        if statuses:
            q = f"SELECT id FROM cases WHERE status IN ({','.join('?' * len(statuses))})"
            rows = c.execute(q + " ORDER BY updated_at DESC", statuses).fetchall()
        else:
            rows = c.execute("SELECT id FROM cases ORDER BY updated_at DESC").fetchall()
        cases = [self.get_case(r["id"]) for r in rows]
        return [x for x in cases if x is not None]

    def list_open(self) -> list[dict[str, Any]]:
        """Cases the watchdog must look at: open or due, with their active actions."""
        cases = self.list_cases(OPEN_STATES)

        def next_deadline(case: dict) -> str:
            ds = [a["deadline_iso"] for a in case["actions"] if a["status"] == "active" and a["deadline_iso"]]
            return min(ds) if ds else "9999-12-31"

        cases.sort(key=lambda k: (k["status"] != "due", next_deadline(k)))
        return cases

    def set_status(self, case_id: str, status: str, detail: str | None = None) -> None:
        if status not in ALL_STATES:
            raise ValueError(f"unknown status {status!r}")
        with self._tx() as c:
            c.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", (status, _now(), case_id))
            c.execute("INSERT INTO events (case_id, at, kind, detail) VALUES (?,?,?,?)",
                      (case_id, _now(), f"status:{status}", detail))

    def mark_due(self, case_id: str, reminder_text: str) -> None:
        """Watchdog: deadline within 2 days, not replied. Stores the reader-language line."""
        with self._tx() as c:
            c.execute("UPDATE cases SET status = 'due', due_line = ?, updated_at = ? WHERE id = ?",
                      (reminder_text, _now(), case_id))
            c.execute("INSERT INTO events (case_id, at, kind, detail) VALUES (?,?,?,?)",
                      (case_id, _now(), "reminder", reminder_text))

    def mark_replied(self, case_id: str) -> bool:
        with self._tx() as c:
            cur = c.execute(
                "UPDATE cases SET status = 'replied', replied_at = ?, updated_at = ?, due_line = NULL WHERE id = ?",
                (_now(), _now(), case_id))
            if cur.rowcount == 0:
                return False
            c.execute("UPDATE actions SET status = 'done' WHERE case_id = ? AND status = 'active'", (case_id,))
            c.execute("INSERT INTO events (case_id, at, kind, detail) VALUES (?,?,?,?)",
                      (case_id, _now(), "replied", None))
        return True

    def close_case(self, case_id: str, detail: str | None = None) -> None:
        self.set_status(case_id, "closed", detail)

    def log_event(self, case_id: str, kind: str, detail: Any = None) -> None:
        if detail is not None and not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        with self._tx() as c:
            c.execute("INSERT INTO events (case_id, at, kind, detail) VALUES (?,?,?,?)",
                      (case_id, _now(), kind, detail))

    def delete_case(self, case_id: str) -> bool:
        """Remove the case and everything attached to it. Nothing is kept, not even a tombstone."""
        with self._tx() as c:
            cur = c.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            deleted = cur.rowcount > 0
        if deleted and str(self.path) != ":memory:":
            self._conn.execute("VACUUM")
        return deleted

    def find_paper_by_text(self, text: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM papers WHERE text = ?", (text,)).fetchone()
        return dict(row) if row else None


_default_store: Store | None = None


def get_store(path: str | os.PathLike | None = None) -> Store:
    """Process-wide store. Tests pass an explicit path (or ':memory:')."""
    global _default_store
    if path is not None:
        return Store(path)
    if _default_store is None:
        _default_store = Store()
    return _default_store


def reset_default_store() -> None:
    global _default_store
    if _default_store is not None:
        _default_store.close()
    _default_store = None
