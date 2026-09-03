"""Daily watchdog: nag open cases two days before the deadline.

The web app owns the reminder page. This module owns the due-state
transition: list open cases, compose a reader-language line, mark due,
and after the deadline ask once whether the reply was sent, then close.

Store is duck-typed. If ``papelito.store`` is present it is used; tests
inject an in-memory object with the same methods. ``Store.close()``
closes the SQLite connection. Case close is ``close_case``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

log = logging.getLogger("papelito.watch")

DUE_WINDOW_DAYS = 2
REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_DB = REPO_ROOT / "data" / "papelito.db"
ASK_SENT = {
    "de": "Hast du die Antwort geschickt?",
    "en": "Did you send the reply?",
}
PREFIX = {
    "de": {0: "Heute", 1: "Morgen", 2: "In zwei Tagen"},
    "en": {0: "Today", 1: "Tomorrow", 2: "In two days"},
}

# ---------------------------------------------------------------------------
# Duck-typed field access
# ---------------------------------------------------------------------------


def _field(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    getter = obj.get if isinstance(obj, dict) else lambda n, d=None: getattr(obj, n, d)
    for name in names:
        try:
            value = getter(name)
        except Exception:
            value = None
        if value not in (None, ""):
            return value
    return default


def _case_id(case: Any) -> str:
    return str(_field(case, "id", "case_id") or "")


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _lang_key(language: str | None) -> str:
    s = (language or "en").strip().lower()
    if s in {"de", "german", "deutsch"}:
        return "de"
    if s in {"en", "english"}:
        return "en"
    return "en"


def parse_today(value: str | date | None = None) -> date:
    """CLI ``--today``, else ``PAPELITO_TODAY``, else the real date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = (str(value) if value is not None else os.environ.get("PAPELITO_TODAY") or "").strip()
    if text:
        return date.fromisoformat(text[:10])
    return date.today()


def load_reader_language(profile_path: str | os.PathLike | None = None) -> str:
    candidates: list[Path] = []
    if profile_path:
        candidates.append(Path(profile_path))
    candidates.extend(
        [
            Path("profile.yaml"),
            Path("profile.example.yaml"),
            REPO_ROOT / "profile.yaml",
            REPO_ROOT / "profile.example.yaml",
        ]
    )
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("reader_language:"):
                return stripped.split(":", 1)[1].strip().strip("\"'")
    return "English"


# ---------------------------------------------------------------------------
# Store loading (independent of store.py existing)
# ---------------------------------------------------------------------------


def load_store(path: str | os.PathLike | None = None) -> Any:
    """Return a store with list_open / mark_due / mark_replied.

    Prefers ``papelito.store.get_store``. Falls back to ``web.store`` so the
    timer still marks cases due if the core module has not landed. Tests pass
    their own object and never call this.
    """
    db = path or os.environ.get("PAPELITO_DB") or str(REPO_DB)
    try:
        from papelito.store import get_store  # type: ignore
    except ImportError:
        get_store = None
    if get_store is not None:
        try:
            return get_store(db)
        except TypeError:
            return get_store()
    try:
        from web.store import get_store as web_get_store  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "no case store: papelito.store is missing and no store was injected"
        ) from exc
    return web_get_store()


def _call(store: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    fn = getattr(store, name, None)
    if not callable(fn):
        return None
    return fn(*args, **kwargs)


def _mark_due(store: Any, case_id: str, reminder: str) -> None:
    fn = getattr(store, "mark_due", None)
    if not callable(fn):
        raise AttributeError("store has no mark_due")
    try:
        fn(case_id, reminder)
        return
    except TypeError:
        pass
    try:
        fn(case_id, reminder_text=reminder)
        return
    except TypeError:
        fn(case_id)


def _close_case(store: Any, case_id: str, detail: str | None = None) -> None:
    """Close a *case*. Never call ``store.close()``: that drops the DB connection."""
    fn = getattr(store, "close_case", None)
    if callable(fn):
        try:
            fn(case_id, detail)
            return
        except TypeError:
            fn(case_id)
            return
    fn = getattr(store, "mark_closed", None)
    if callable(fn):
        fn(case_id)
        return
    fn = getattr(store, "set_status", None)
    if callable(fn):
        try:
            fn(case_id, "closed", detail)
        except TypeError:
            fn(case_id, "closed")
        return
    log.warning("store cannot close case %s; next run may ask again", case_id)


def _list_due(store: Any) -> list[Any]:
    fn = getattr(store, "list_due", None)
    if callable(fn):
        return list(fn() or [])
    return [
        case
        for case in (_call(store, "list_open") or [])
        if str(_field(case, "status") or "").lower() == "due"
    ]


def _log_trace(store: Any, case_id: str | None, event: dict[str, Any]) -> None:
    log.info("%s", json.dumps(event, ensure_ascii=False))
    fn = getattr(store, "log_event", None)
    if not callable(fn) or not case_id:
        return
    try:
        fn(case_id, "watch", event)
    except TypeError:
        try:
            fn(case_id, "watch", json.dumps(event, ensure_ascii=False))
        except Exception:
            log.debug("log_event failed", exc_info=True)
    except Exception:
        log.debug("log_event failed", exc_info=True)


# ---------------------------------------------------------------------------
# Case selection
# ---------------------------------------------------------------------------


def _is_replied(case: Any) -> bool:
    status = str(_field(case, "status") or "").lower()
    if status in {"replied", "done"}:
        return True
    if _field(case, "replied") is True:
        return True
    if _field(case, "replied_at"):
        return True
    return False


def _is_closed(case: Any) -> bool:
    status = str(_field(case, "status") or "").lower()
    if status == "closed":
        return True
    if _field(case, "asked_sent") is True:
        return True
    return False


def _active_actions(case: Any) -> list[Any]:
    actions = _field(case, "actions") or []
    if isinstance(actions, dict):
        actions = list(actions.values())
    if not actions:
        deadline = _field(case, "deadline", "deadline_iso", "due_date", "event_date")
        if deadline:
            return [
                {
                    "deadline_iso": deadline,
                    "action": _field(case, "do", "action", "title", "summary") or "",
                    "amount": _field(case, "amount"),
                    "status": "active",
                }
            ]
        return []
    out = []
    for action in actions:
        status = str(_field(action, "status") or "active").lower()
        if status in {"superseded", "done", "replied", "closed"}:
            continue
        out.append(action)
    return out


def _nearest_action(case: Any) -> tuple[date | None, Any | None]:
    nearest: date | None = None
    chosen: Any | None = None
    for action in _active_actions(case):
        deadline = _as_date(_field(action, "deadline_iso", "deadline", "due_date", "date"))
        if deadline is None:
            continue
        if nearest is None or deadline < nearest:
            nearest = deadline
            chosen = action
    if nearest is None:
        nearest = _as_date(_field(case, "deadline", "deadline_iso", "due_date", "event_date"))
    return nearest, chosen


# ---------------------------------------------------------------------------
# Reminder text
# ---------------------------------------------------------------------------


def _amount_text(amount: Any) -> str:
    if amount in (None, ""):
        return ""
    if isinstance(amount, bool):
        return ""
    if isinstance(amount, (int, float)):
        n = int(amount) if float(amount) == int(amount) else amount
        return f"{n} €"
    text = str(amount).strip()
    if not text:
        return ""
    if "€" in text:
        return text
    return f"{text} €"


def _is_cash(action_text: str, amount_text: str) -> bool:
    blob = f"{action_text} {amount_text}".lower()
    return any(w in blob for w in ("€", "euro", "bar", "cash", "bargeld"))


def _detail(case: Any, action: Any | None, lang: str) -> str:
    amount = _amount_text(_field(action, "amount") or _field(case, "amount"))
    title = str(_field(case, "title", "what", "summary") or "").strip()
    sender = str(_field(case, "sender", "contact") or "").strip()
    action_text = str(_field(action, "action", "do") or _field(case, "do", "action") or "").strip()
    cash = _is_cash(action_text, amount)

    if lang == "de":
        if amount and title:
            head = f"{amount} für den {title}"
        else:
            head = amount or action_text or title or "der Kindergartenbrief"
        bits = [head]
        if cash:
            bits.append("bar")
        if sender:
            bits.append(sender)
        return ", ".join(bits)
    if lang == "en":
        if amount and title:
            head = f"{amount} for the {title}"
        else:
            head = amount or action_text or title or "the Kindergarten note"
        bits = [head]
        if cash:
            bits.append("cash")
        if sender:
            bits.append(sender)
        return ", ".join(bits)
    raise ValueError(f"unsupported language: {lang}")


def compose_reminder(
    case: Any,
    today: date,
    language: str | None = None,
    *,
    overdue: bool = False,
) -> str:
    """Reader-language nag. Deterministic so Gate 3 works without a model."""
    lang = _lang_key(language or _field(case, "language", "reader_language") or "en")
    if overdue:
        return ASK_SENT[lang]
    deadline, action = _nearest_action(case)
    if deadline is None:
        return f"{PREFIX[lang][2]}: {_detail(case, None, lang)}."
    days = (deadline - today).days
    days = 0 if days < 0 else min(days, 2)
    return f"{PREFIX[lang][days]}: {_detail(case, action, lang)}."


def _agent_compose(case: Any, today: date, language: str) -> str | None:
    """Hand the case to the Strands agent if it exposes compose_reminder.

    Off unless PAPELITO_WATCH_AGENT=1 so the timer and Gate 3 stay offline.
    """
    flag = os.environ.get("PAPELITO_WATCH_AGENT", "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return None
    try:
        mod = __import__("papelito.agent", fromlist=["*"])
    except ImportError:
        return None
    fn = getattr(mod, "compose_reminder", None) or getattr(mod, "remind", None)
    if not callable(fn):
        return None
    try:
        result = fn(case, today=today.isoformat(), language=language)
    except TypeError:
        try:
            result = fn(case)
        except Exception:
            log.exception("agent compose_reminder failed")
            return None
    except Exception:
        log.exception("agent compose_reminder failed")
        return None
    if isinstance(result, str) and result.strip():
        return result.strip()
    return None


# ---------------------------------------------------------------------------
# Optional outbound nag (never required; replies are never sent)
# ---------------------------------------------------------------------------


def _maybe_notify(text: str) -> None:
    """No outbound send. Reminders stay in SQLite, the web UI, and .ics VALARM."""
    return


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


@dataclass
class Reminder:
    case_id: str
    text: str
    kind: str  # "due" | "ask_sent"


@dataclass
class WatchReport:
    reminders: list[Reminder] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)

    @property
    def texts(self) -> list[str]:
        return [item.text for item in self.reminders]


def run_watch(
    store: Any | None = None,
    today: date | str | None = None,
    language: str | None = None,
    *,
    compose: Callable[..., str] | None = None,
    notify: bool = True,
) -> WatchReport:
    """Scan open cases. Mark due inside the 2-day window. Close after deadline.

    ``today`` is the fake clock for Gate 3 (``--today 2026-09-10``).
    """
    store = store if store is not None else load_store()
    today_d = parse_today(today)
    reader = language or load_reader_language()
    compose_fn = compose or compose_reminder
    report = WatchReport()

    open_cases = list(_call(store, "list_open") or [])
    due_cases = _list_due(store)
    report.traces.append(
        {
            "tool": "list_open",
            "ids": [_case_id(c) for c in open_cases],
            "today": today_d.isoformat(),
        }
    )
    report.traces.append(
        {
            "tool": "list_due",
            "ids": [_case_id(c) for c in due_cases],
        }
    )
    _log_trace(store, None, report.traces[0])
    _log_trace(store, None, report.traces[1])

    for case in open_cases:
        case_id = _case_id(case)
        if not case_id or _is_replied(case) or _is_closed(case):
            continue
        deadline, _action = _nearest_action(case)
        if deadline is None:
            continue
        days = (deadline - today_d).days
        case_lang = _field(case, "language", "reader_language") or reader

        if days < 0:
            try:
                text = compose_fn(case, today_d, case_lang, overdue=True)
            except TypeError:
                text = ASK_SENT[_lang_key(str(case_lang))]
            if not isinstance(text, str) or not text.strip():
                text = ASK_SENT[_lang_key(str(case_lang))]
            _mark_due(store, case_id, text)
            _close_case(store, case_id, text)
            reminder = Reminder(case_id=case_id, text=text, kind="ask_sent")
            report.reminders.append(reminder)
            event = {"tool": "close_case", "case_id": case_id, "reminder": text}
            report.traces.append(event)
            _log_trace(store, case_id, event)
            if notify:
                _maybe_notify(text)
            continue

        if days > DUE_WINDOW_DAYS:
            continue

        try:
            text = compose_fn(case, today_d, case_lang)
        except TypeError:
            text = compose_fn(case, today_d)
        agent_text = None if compose is not None else _agent_compose(case, today_d, str(case_lang))
        if agent_text:
            text = agent_text
        if not isinstance(text, str) or not text.strip():
            text = compose_reminder(case, today_d, str(case_lang))
        _mark_due(store, case_id, text)
        reminder = Reminder(case_id=case_id, text=text, kind="due")
        report.reminders.append(reminder)
        event = {"tool": "mark_due", "case_id": case_id, "reminder": text}
        report.traces.append(event)
        _log_trace(store, case_id, {"tool": "compose_reminder", "case_id": case_id, "reminder": text})
        _log_trace(store, case_id, event)
        if notify:
            _maybe_notify(text)

    write_last_run(report, today_d, checked=len(open_cases))
    return report


def last_run_path() -> Path:
    return Path(os.environ.get("PAPELITO_WATCH_LOG") or REPO_ROOT / "data" / "watchdog-last.json")


def write_last_run(report: WatchReport, today_d: date, checked: int | None = None) -> dict[str, Any]:
    """What the web app shows as 'while you were away'."""
    if checked is None:
        checked = 0
        for event in report.traces:
            if event.get("tool") == "list_open":
                checked = len(event.get("ids") or [])
                break
    payload = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "today": today_d.isoformat(),
        "checked": int(checked),
        "nagged": [
            {"case_id": item.case_id, "kind": item.kind, "text": item.text}
            for item in report.reminders
        ],
    }
    path = last_run_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def read_last_run() -> dict[str, Any] | None:
    path = last_run_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def mark_done(case_id: str, store: Any | None = None) -> bool:
    """``papelito done``: the next watch run sends nothing for this case."""
    store = store if store is not None else load_store()
    result = _call(store, "mark_replied", case_id)
    event = {"tool": "mark_replied", "case_id": case_id}
    _log_trace(store, case_id, event)
    return bool(result) if result is not None else True


# ---------------------------------------------------------------------------
# CLI (systemd runs ``python -m papelito.watch``)
# ---------------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    if argv and argv[0] == "done":
        parser = argparse.ArgumentParser(prog="papelito watch done")
        parser.add_argument("case_id")
        parser.add_argument("--db", default=None, help="SQLite path (PAPELITO_DB)")
        args = parser.parse_args(argv[1:])
        store = load_store(args.db)
        ok = mark_done(args.case_id, store=store)
        if not ok:
            log.error("mark_replied failed for %s", args.case_id)
            return 1
        return 0

    parser = argparse.ArgumentParser(
        prog="papelito watch",
        description="Nag open cases whose deadline is within two days.",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Fake clock YYYY-MM-DD (Gate 3: two days before the deadline)",
    )
    parser.add_argument("--language", default=None, help="Reader language (default: profile)")
    parser.add_argument("--db", default=None, help="SQLite path (PAPELITO_DB)")
    parser.add_argument("--profile", default=None, help="profile.yaml path")
    args = parser.parse_args(argv)

    store = load_store(args.db)
    language = args.language or load_reader_language(args.profile)
    report = run_watch(store, today=args.today, language=language)
    for text in report.texts:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
