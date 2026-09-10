"""Photo intake for the web page.

The reading itself belongs to the core agent (``papelito/agent.py``). This
module hands the photo over when that module exists, and otherwise files an
unread case so the photo is never lost. Either way the page gets a case dict.

An upload runs as a *job* in a thread. ``process_photo`` reports each tool as
it returns (``on_step``), the job keeps that list, and the page polls it to
fill the fourth column while the work happens. A step is marked done only
after the tool came back; the one after it is marked running because the
agent calls its tools in a fixed order. Nothing is ticked that did not run.
"""

from __future__ import annotations

import inspect
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from web.store import DEFAULT_LANG, DEFAULT_STEP_KEYS, REPO_ROOT, lang_code, normalize, today

PHOTO_DIR = Path(os.environ.get("PAPELITO_PRIVATE_PHOTO_DIR", "")).expanduser() \
    if os.environ.get("PAPELITO_PRIVATE_PHOTO_DIR", "").strip() \
    else REPO_ROOT / "photos" / "private"
# Accepted by the file input; anything else is rejected before it is written.
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}

# The agent's fixed tool order for a new photo (papelito.agent.process_photo).
STEP_ORDER = ["check_photo", "read_note", "extract_actions", "match_case", "save_case",
              "write_ics", "draft_reply", "explain_in"]

MSG = {
    "no_reader": {
        "en": "The reader is not connected yet. The photo is kept to be read later.",
        "de": "Der Leser ist noch nicht angeschlossen. Das Foto bleibt gespeichert.",
    },
    "failed": {
        "en": "The photo could not be read ({err}). Take it again?",
        "de": "Das Foto konnte nicht gelesen werden ({err}). Noch einmal fotografieren?",
    },
    "nothing": {
        "en": "Nothing could be read on the photo. Take it again?",
        "de": "Auf dem Foto war nichts zu lesen. Noch einmal fotografieren?",
    },
    "unreadable": {
        "en": "Photo not readable: {hint}. Take it again?",
        "de": "Foto nicht lesbar: {hint}. Noch einmal fotografieren?",
    },
    "new_note": {"en": "New note", "de": "Neues Papier"},
    "unread": {"en": "Not read yet", "de": "Noch nicht gelesen"},
}


def _msg(key: str, lang: str, **kw: Any) -> str:
    return MSG[key][lang_code(lang)].format(**kw)


def save_photo(data: bytes, filename: str) -> Path:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"unsupported format: {suffix or filename!r}")
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    path = PHOTO_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{suffix}"
    path.write_bytes(data)
    return path


def discard_photo(path: str | os.PathLike[str]) -> bool:
    """Delete one app-managed upload without following a final symlink."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    try:
        root = PHOTO_DIR.expanduser().resolve()
        candidate = candidate.parent.resolve() / candidate.name
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False
    if candidate == root or not (candidate.is_file() or candidate.is_symlink()):
        return False
    # A reader can save a case and then fail while creating its artifacts.
    # Preserve references from every case, including closed cases. If we
    # cannot check ownership, retaining the file is safer than deleting it.
    try:
        from papelito.store import case_photo_paths
        from web.store import get_store

        for case in get_store().list_all():
            paths = case_photo_paths(case, root) | case_photo_paths(case.get("_raw") or {}, root)
            if candidate in paths or candidate.resolve() in paths:
                return False
    except Exception:
        return False
    try:
        candidate.unlink()
    except OSError:
        return False
    return True


def _core_reader():
    """papelito.agent's photo entry point, or None while it is being built."""
    try:
        from papelito import agent  # type: ignore
    except Exception:
        return None
    for name in ("process_photo", "read_photo", "add_photo", "run"):
        fn = getattr(agent, name, None)
        if callable(fn):
            return fn
    return None


def reader_connected() -> bool:
    return _core_reader() is not None


def _unread(photo: Path, received: str, question: str, lang: str) -> dict:
    """No reader yet: keep the photo, file it unread, ask rather than guess."""
    return normalize({
        "id": str(uuid.uuid4()),
        "what": _msg("new_note", lang),
        "do": _msg("unread", lang),
        "sender": "",
        "photo": str(photo),
        "received_on": received,
        "status": "open",
        "confidence": 0.0,
        "question": question,
        "steps": [{"key": k, "state": "pending"} for k in DEFAULT_STEP_KEYS],
    }, lang)


def analyse(photo: Path, received_on: str = "", lang: str = DEFAULT_LANG,
            on_step: Callable[[str, dict], None] | None = None) -> dict:
    """Hand the photo to the agent.

    Returns ``{"case": dict | None, "saved": bool, "question": str}``.
    ``papelito.agent.process_photo`` saves the case itself and returns it; an
    unreadable photo comes back as a question and no case, which is the point:
    the agent asks instead of inventing a deadline.
    """
    lang = lang_code(lang)
    received = received_on or today().isoformat()
    reader = _core_reader()
    if reader is None:
        return {"case": _unread(photo, received, _msg("no_reader", lang), lang), "saved": False, "question": ""}

    kwargs: dict[str, Any] = {}
    try:
        if on_step is not None and "on_step" in inspect.signature(reader).parameters:
            kwargs["on_step"] = on_step
    except (TypeError, ValueError):
        pass
    try:
        result = reader(str(photo), received, **kwargs)
    except Exception as exc:  # a bad photo must never cost the photo
        return {"case": None, "saved": False, "question": _msg("failed", lang, err=type(exc).__name__)}

    if not result:
        return {"case": None, "saved": False, "question": _msg("nothing", lang)}
    if not result.get("id") or result.get("status") == "unread":
        hint = result.get("hint")
        question = _msg("unreadable", lang, hint=hint) if hint else (
            result.get("question") or _msg("nothing", lang))
        return {"case": None, "saved": False, "question": question}

    if result.get("duplicate"):
        discard_photo(photo)
    case = normalize(result, lang)
    case["photo"] = case.get("photo") or str(photo)
    return {"case": case, "saved": True, "question": ""}


# ---------------------------------------------------------------------- jobs

JOB_TTL_SECONDS = 15 * 60
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _fresh_steps() -> list[dict]:
    return [{"tool": t, "state": "pending", "detail": {}} for t in STEP_ORDER]


def new_job(photo: Path, received_on: str, lang: str) -> dict:
    """Start reading ``photo`` in a thread; returns the job as the page first sees it."""
    _prune()
    job = {
        "id": uuid.uuid4().hex[:12],
        "created": time.time(),
        "state": "running",
        "lang": lang_code(lang),
        "photo": str(photo),
        "steps": _fresh_steps() if reader_connected() else [],
        "case": None,
        "saved": False,
        "question": "",
        "error": "",
    }
    if job["steps"]:
        job["steps"][0]["state"] = "running"
    with _lock:
        _jobs[job["id"]] = job
    threading.Thread(target=_run, args=(job, received_on), daemon=True, name=f"papelito-job-{job['id']}").start()
    return public(job)


def _run(job: dict, received_on: str) -> None:
    def on_step(tool: str, info: dict) -> None:
        with _lock:
            steps = job["steps"]
            idx = next((i for i, s in enumerate(steps) if s["tool"] == tool), None)
            if idx is None:
                steps.append({"tool": tool, "state": "done", "detail": info})
                return
            ok = info.get("ok", True)
            steps[idx]["state"] = "done" if ok else "failed"
            steps[idx]["detail"] = {k: v for k, v in info.items() if v is not None}
            # Steps before this one ran too (the agent's order is fixed); the next one starts now.
            for s in steps[:idx]:
                if s["state"] in ("pending", "running"):
                    s["state"] = "done"
            if ok and idx + 1 < len(steps):
                steps[idx + 1]["state"] = "running"

    try:
        outcome = analyse(Path(job["photo"]), received_on, job["lang"], on_step)
    except Exception as exc:  # pragma: no cover - analyse already guards, belt and braces
        outcome = {"case": None, "saved": False, "question": _msg("failed", job["lang"], err=type(exc).__name__)}
    if outcome["case"] is None:
        # There is no case through which the user could later delete this upload.
        discard_photo(job["photo"])
    with _lock:
        job["case"] = outcome["case"]
        job["saved"] = outcome["saved"]
        job["question"] = outcome["question"]
        for s in job["steps"]:
            if s["state"] == "running":
                s["state"] = "failed" if outcome["question"] else "done"
            elif s["state"] == "pending" and not outcome["question"] and outcome["case"] is not None:
                # Nothing reported for it, but the case exists: do not claim it ran.
                s["state"] = "skipped"
            elif s["state"] == "pending":
                s["state"] = "skipped"
        job["state"] = "done"


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job, steps=[dict(s) for s in job["steps"]]) if job else None


def mark_saved(job_id: str) -> None:
    """Persist the saved flag on the live job, not only on a response copy."""
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["saved"] = True


def public(job: dict) -> dict:
    """What the page gets: no paths, no raw case."""
    return {
        "job": job["id"],
        "state": job["state"],
        "steps": [{"tool": s["tool"], "state": s["state"], "detail": s.get("detail") or {}} for s in job["steps"]],
        "question": job["question"],
    }


def _prune() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    discarded: list[str] = []
    with _lock:
        for jid in [j for j, job in _jobs.items() if job["created"] < cutoff and job["state"] == "done"]:
            job = _jobs[jid]
            if not job.get("saved"):
                discarded.append(job["photo"])
            del _jobs[jid]
    for photo in discarded:
        discard_photo(photo)
