"""Papelito — the mobile page.

Upload a photo, read the case list (what / do / by when / done for you),
mark a case done, delete it. Nothing is ever sent from here: the human copies
the reply, opens the calendar file, taps done.

Run it:

    uv run uvicorn web.app:app --reload --host 0.0.0.0 --port 8000

Environment:
    PAPELITO_TODAY=2026-09-10   fake clock, for the watchdog demo
    PAPELITO_DB=...             SQLite file for the fallback store
    PAPELITO_PROFILE=...        household profile (else ./profile.yaml)

Language: every list endpoint takes ``?lang=en|de``. The web and CLI default
to English. The German reply and the calendar file are
always German, they go to the institution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from papelito.reply import load_profile, save_profile
from web import agentcore, artifacts, pipeline
from web.store import (
    ASK,
    DEFAULT_LANG,
    NO_DATE,
    backend_name,
    format_date,
    get_store,
    lang_code,
    parse_date,
    sort_key,
    state_of,
    today,
)

STATIC = Path(__file__).resolve().parent / "static"
MAX_PHOTO_BYTES = 12 * 1024 * 1024

app = FastAPI(title="Papelito", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

UI = {
    "overdue": {"en": "Did you send the reply?", "de": "Hast du die Antwort geschickt?"},
    "today": {"en": "Today", "de": "Heute"},
    "tomorrow": {"en": "Tomorrow", "de": "Morgen"},
    "in_days": {"en": "In {n} days", "de": "In {n} Tagen"},
    "unsure": {"en": "?", "de": "?"},
}

# API errors carry a code the page translates, and an English message for curl.
ERRORS = {
    "not_found": (404, "Case not found"),
    "empty_photo": (400, "The photo arrived empty"),
    "too_large": (413, "The photo is too large"),
    "bad_format": (400, "Unsupported photo format"),
    "bad_answer": (400, "Answer must be si or no"),
    "bad_settings": (400, "Invalid settings"),
    "bad_calendar": (400, "Invalid calendar month"),
    "no_photo": (404, "No photo for this case"),
    "no_job": (404, "Unknown upload"),
    "no_agentcore": (503, "AgentCore is not configured"),
    "agentcore_failed": (502, "AgentCore did not answer"),
}


def _error(code: str, message: str | None = None) -> HTTPException:
    status, default = ERRORS[code]
    return HTTPException(status_code=status, detail={"code": code, "message": message or default})


def _lang(value: str | None) -> str:
    return lang_code(value, DEFAULT_LANG)


def household_name() -> str:
    """The household name from the loaded profile."""
    return str(load_profile().get("household") or "")


def _case_child(case: dict[str, Any]) -> tuple[str, str]:
    child_id = str(case.get("child_id") or "").strip()
    child_name = str(case.get("child_name") or "").strip()
    if child_id:
        profile = load_profile()
        child = next(
            (item for item in profile.get("children", [])
             if isinstance(item, dict) and str(item.get("id") or "") == child_id),
            None,
        )
        if child:
            child_name = str(child.get("name") or "").strip()
    return child_id, child_name


# ---------------------------------------------------------------- view model

def _reminder_line(case: dict, state: str, days_left: int | None, lang: str) -> str:
    """The line on a due card. The watchdog's wording wins if it wrote one in this language."""
    if state == "overdue":
        return UI["overdue"][lang]
    if state != "due":
        return ""
    if case.get("reminder"):
        return str(case["reminder"])
    row = next((r for r in case.get("rows", []) if r["status"] == "active" and r["deadline"]), None)
    if not row:
        return ""
    tail = row["do"] or row["what"]
    if row.get("amount") and row["amount"] not in tail:
        tail = f"{tail}, {row['amount']}"
    n = days_left or 0
    when = UI["today"][lang] if n == 0 else UI["tomorrow"][lang] if n == 1 else UI["in_days"][lang].format(n=n)
    return f"{when}: {tail}".strip(": ")


def _when(row: dict, row_date, lang: str) -> str:
    if row_date:
        return format_date(row_date, lang)
    return UI["unsure"][lang] if row["gate"] == "ask" else NO_DATE[lang]


def view(case: dict, lang: str = DEFAULT_LANG) -> dict:
    ref = today()
    state = state_of(case, ref)
    deadline = parse_date(case.get("deadline"))
    days_left = (deadline - ref).days if deadline else None
    child_id, child_name = _case_child(case)

    rows = []
    for row in case.get("rows", []):
        row_date = parse_date(row.get("deadline"))
        rows.append({
            "id": row.get("id") or "",
            # kind and status let the board tell a notice from a paper that asks for something.
            "kind": row.get("kind") or "",
            "status": row.get("status") or "active",
            "what": row["what"],
            "do": row["do"],
            "when": _when(row, row_date, lang),
            "days_left": (row_date - ref).days if row_date else None,
            "done": row["done"],
            "superseded": row["status"] == "superseded",
            "superseded_by": row.get("superseded_by") or "",
            # Amendment, both directions: the old line knows its replacement, the new line what it replaced.
            "replaced_by": {**row["replaced_by"], "when": format_date(row["replaced_by"]["deadline"], lang)}
            if row.get("replaced_by") else None,
            "replaces": [{**old, "when": format_date(old["deadline"], lang)} for old in row.get("replaces") or []],
            "source_line": row["source_line"],
            "question": (row["question"] or ASK[lang]) if row["gate"] == "ask" else "",
        })

    ask = "" if case.get("answered") else next((r["question"] for r in rows if r["question"]), "")
    return {
        "id": case["id"],
        "child_id": child_id,
        "child_name": child_name,
        "lang": lang,
        "state": state,
        "title": case.get("what") or "",
        "sender": case.get("sender") or "",
        "labels": case.get("labels") or [],
        "rows": rows,
        "deadline": case.get("deadline") or "",
        "days_left": days_left,
        "reminder": _reminder_line(case, state, days_left, lang),
        "question": ask,
        "has_photo": bool(case.get("photo")),
        "received_label": format_date(case.get("received_on"), lang),
        "paper_count": int(case.get("paper_count") or 1),
        "amended_label": format_date(case.get("amended_on"), lang) if case.get("amended_on") else "",
        "has_reply": bool(case.get("reply_de")),
    }


def _photo_path(case: dict, crop: bool = False) -> Path | None:
    """Resolve a stored photo path, but only inside photos/private."""
    raw = case.get("source_crop") if crop else case.get("photo")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = pipeline.REPO_ROOT / path
    path = path.resolve()
    if pipeline.PHOTO_DIR.resolve() not in path.parents:
        return None
    return path


def _case_or_404(case_id: str, lang: str = DEFAULT_LANG) -> dict:
    case = get_store().get(case_id, lang)
    if not case:
        raise _error("not_found")
    return case


# --------------------------------------------------------------------- pages

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    # Served from the root so its scope covers the whole page.
    return FileResponse(STATIC / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/api/cases")
def api_cases(include_done: bool = False, lang: str | None = Query(default=None)) -> JSONResponse:
    ui = _lang(lang)
    store = get_store()
    cases = store.list_all(ui) if include_done else store.list_open(ui)
    cases.sort(key=sort_key)
    views = [view(case, ui) for case in cases]
    return JSONResponse({
        "today": today().isoformat(),
        "today_label": format_date(today(), ui),
        "lang": ui,
        "household": household_name(),
        "backend": backend_name(),
        "reader": pipeline.reader_connected(),
        "due_count": sum(1 for v in views if v["state"] in ("due", "overdue")),
        "away": _away_view(),
        "agentcore": agentcore.agentcore_enabled(),
        "cases": views,
    })


def _away_view() -> dict:
    """Last watchdog run: what happened while the phone was face down."""
    try:
        from papelito.watch import read_last_run
    except Exception:
        return {"ran_at": None, "today": None, "checked": 0, "nagged": []}
    data = read_last_run() or {}
    nagged = data.get("nagged") if isinstance(data.get("nagged"), list) else []
    return {
        "ran_at": data.get("ran_at"),
        "today": data.get("today"),
        "checked": int(data.get("checked") or 0),
        "nagged": [
            {"case_id": str(item.get("case_id") or ""), "kind": str(item.get("kind") or ""),
             "text": str(item.get("text") or "")}
            for item in nagged if isinstance(item, dict)
        ],
    }


@app.post("/api/watch")
def api_watch(today: str | None = Query(default=None), lang: str | None = Query(default=None)) -> JSONResponse:
    """Run the watchdog once (same as `papelito watch`). Fake clock: ?today=YYYY-MM-DD.

    Writes the same ``data/watchdog-last.json`` the CLI writes, so the
    while-you-were-away panel updates.
    """
    ui = _lang(lang)
    from papelito.watch import load_store, run_watch

    run_watch(load_store(), today=today, language=ui, notify=False)
    return api_cases(include_done=False, lang=lang)


def _job_view(job: dict, lang: str) -> dict:
    out = pipeline.public(job)
    out["case"] = view(job["case"], lang) if job.get("case") else None
    if job["state"] == "done" and job.get("case") and not job.get("saved"):
        # The fallback reader files the photo unread; the case must still land in the list.
        case_id = get_store().save_case(job["case"])
        job["saved"] = True
        out["case"] = view(_case_or_404(case_id, lang), lang)
    return out


@app.post("/api/upload")
async def api_upload(photo: UploadFile = File(...), received_on: str = Form(""),
                     lang: str | None = Query(default=None), wait: bool = Query(default=False)) -> JSONResponse:
    """Start reading a photo. Returns a job the page polls; ``?wait=true`` blocks until it is done."""
    ui = _lang(lang)
    data = await photo.read()
    if not data:
        raise _error("empty_photo")
    if len(data) > MAX_PHOTO_BYTES:
        raise _error("too_large")
    try:
        path = pipeline.save_photo(data, photo.filename or "")
    except ValueError as exc:
        raise _error("bad_format", str(exc)) from exc
    if not wait:
        return JSONResponse(pipeline.new_job(path, received_on, ui), status_code=202)
    # Synchronous path for curl and the selftest. Reading a note is a model call; keep it off the loop.
    job_id = pipeline.new_job(path, received_on, ui)["job"]
    job = await run_in_threadpool(_wait_for, job_id)
    out = _job_view(job, ui)
    return JSONResponse(out, status_code=201 if out["case"] else 200)


def _wait_for(job_id: str) -> dict:
    import time

    while True:
        job = pipeline.get_job(job_id)
        if job is None or job["state"] == "done":
            return job or {"id": job_id, "state": "done", "steps": [], "case": None, "question": "", "saved": False}
        time.sleep(0.15)


@app.get("/api/upload/{job_id}")
def api_upload_status(job_id: str, lang: str | None = Query(default=None)) -> JSONResponse:
    job = pipeline.get_job(job_id)
    if job is None:
        raise _error("no_job")
    return JSONResponse(_job_view(job, _lang(lang)))


@app.post("/api/cases/{case_id}/done")
def api_done(case_id: str) -> JSONResponse:
    _case_or_404(case_id)
    get_store().mark_replied(case_id)
    return JSONResponse({"ok": True, "id": case_id, "state": "replied"})


@app.delete("/api/cases/{case_id}")
def api_delete(case_id: str) -> JSONResponse:
    """Really deletes: the case row and the photo on disk. No archive behind this."""
    case = _case_or_404(case_id)
    get_store().delete_case(case_id)
    removed = 0
    for crop in (False, True):
        path = _photo_path(case, crop)
        if path and path.is_file():
            path.unlink()
            removed += 1
    return JSONResponse({"ok": True, "id": case_id, "photos_deleted": removed})


@app.post("/api/cases/{case_id}/answer")
def api_answer(case_id: str, answer: str = Form(...), lang: str | None = Query(default=None)) -> JSONResponse:
    """The confidence gate: the human confirms the reading, or asks for a re-read."""
    ui = _lang(lang)
    _case_or_404(case_id, ui)
    if answer not in ("yes", "no"):
        raise _error("bad_answer")
    get_store().record_answer(case_id, answer, ui)
    return JSONResponse({"case": view(_case_or_404(case_id, ui), ui)})


@app.get("/api/cases/{case_id}/reply.txt")
def api_reply(case_id: str) -> PlainTextResponse:
    return PlainTextResponse(artifacts.reply_for(_case_or_404(case_id)))


@app.get("/api/cases/{case_id}/calendar.ics")
def api_ics(case_id: str) -> Response:
    case = _case_or_404(case_id)
    name = quote(f"papelito-{case_id[:8]}.ics")
    return Response(
        artifacts.ics_for(case),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/api/cases/{case_id}/photo")
def api_photo(case_id: str, crop: bool = False) -> FileResponse:
    path = _photo_path(_case_or_404(case_id), crop)
    if not path or not path.is_file():
        raise _error("no_photo")
    return FileResponse(path)


# ---------------------------------------------------------------------- demo

@app.post("/api/demo/seed")
def api_seed(lang: str | None = Query(default=None)) -> JSONResponse:
    """Fills the list with invented Kindergarten paper, for looking at the page."""
    from web import demo

    store = get_store()
    for case in demo.seed_cases():
        store.delete_case(case["id"])  # so re-seeding does not stack up actions
        store.save_case(case)
    return api_cases(include_done=True, lang=lang)


@app.get("/api/demo/agentcore")
def api_agentcore_status() -> JSONResponse:
    """Whether the seed-text sidecar is wired. The PWA hides the button when not."""
    return JSONResponse({
        "enabled": agentcore.agentcore_enabled(),
        "region": agentcore.REGION,
    })


@app.post("/api/demo/agentcore")
def api_agentcore(lang: str | None = Query(default=None)) -> JSONResponse:
    """Extract + explain of the seed Ausflug text on AgentCore Runtime.

    Does not write a case, does not send, does not upload a photo. Seed text only.
    """
    if not agentcore.agentcore_enabled():
        raise _error("no_agentcore")
    ui = _lang(lang)
    try:
        body = agentcore.invoke_runtime(agentcore.seed_payload(ui))
    except Exception as exc:
        raise _error("agentcore_failed", str(exc)[:200]) from exc
    return JSONResponse(body)


@app.post("/api/demo/due/{case_id}")
def api_demo_due(case_id: str, reminder: str = Form(""), lang: str | None = Query(default=None)) -> JSONResponse:
    """What the watchdog does: the case turns due and carries its reminder line."""
    ui = _lang(lang)
    _case_or_404(case_id, ui)
    get_store().mark_due(case_id, reminder)
    return JSONResponse({"case": view(_case_or_404(case_id, ui), ui)})


# ------------------------------------------------- settings, children, month

SETTINGS_FIELDS = ("parent", "household", "language", "signature")


def _settings_view(profile: dict[str, Any]) -> dict[str, Any]:
    children = []
    for child in profile.get("children") or []:
        if not isinstance(child, dict):
            continue
        children.append({
            "id": str(child.get("id") or ""),
            "name": str(child.get("name") or ""),
            "kindergarten": str(child.get("kindergarten") or ""),
        })
    return {
        "parent": str(profile.get("parent_name") or ""),
        "household": str(profile.get("household") or ""),
        "language": lang_code(profile.get("language"), DEFAULT_LANG),
        "signature": str(profile.get("signature") or ""),
        "children": children,
    }


def _setting_text(payload: dict[str, Any], key: str, current: Any) -> str:
    value = payload[key] if key in payload else current
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _error("bad_settings", f"{key} must be a string")
    return value.strip()


def _settings_children(payload: dict[str, Any], current: list[dict[str, Any]]) -> list[dict[str, str]]:
    values = payload["children"] if "children" in payload else current
    if not isinstance(values, list):
        raise _error("bad_settings", "children must be a list")
    children: list[dict[str, str]] = []
    seen: set[str] = set()
    for child in values:
        if not isinstance(child, dict):
            raise _error("bad_settings", "Each child must be an object")
        child_id = child.get("id")
        name = child.get("name")
        if not isinstance(child_id, str) or not child_id.strip():
            raise _error("bad_settings", "Each child needs an id")
        if not isinstance(name, str) or not name.strip():
            raise _error("bad_settings", "Each child needs a name")
        child_id = child_id.strip()
        if child_id in seen:
            raise _error("bad_settings", "Child ids must be unique")
        seen.add(child_id)
        kindergarten = child.get("kindergarten") or ""
        if not isinstance(kindergarten, str):
            raise _error("bad_settings", "kindergarten must be a string")
        children.append({"id": child_id, "name": name.strip(), "kindergarten": kindergarten.strip()})
    return children


@app.get("/api/settings")
def api_settings() -> JSONResponse:
    return JSONResponse(_settings_view(load_profile()))


@app.put("/api/settings")
def api_settings_put(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    current = load_profile()
    language = payload.get("language", current.get("language") or DEFAULT_LANG)
    if not isinstance(language, str) or language not in ("en", "de"):
        raise _error("bad_settings", "language must be en or de")
    data = dict(current)
    data.update({
        "parent_name": _setting_text(payload, "parent", current.get("parent_name")),
        "household": _setting_text(payload, "household", current.get("household")),
        "language": language,
        "signature": _setting_text(payload, "signature", current.get("signature")),
        "children": _settings_children(payload, current.get("children") or []),
    })
    save_profile(data)
    return JSONResponse(_settings_view(load_profile()))


@app.patch("/api/cases/{case_id}")
def api_patch_case(case_id: str, payload: dict[str, Any] = Body(...),
                   lang: str | None = Query(default=None)) -> JSONResponse:
    """Attach a case to a profile child, or clear its assignment."""
    ui = _lang(lang)
    _case_or_404(case_id, ui)
    if "child_id" not in payload or not isinstance(payload["child_id"], str):
        raise _error("bad_settings", "child_id must be a string")
    child_id = payload["child_id"].strip()
    profile = load_profile()
    valid_ids = {str(child.get("id") or "") for child in profile.get("children") or [] if isinstance(child, dict)}
    if child_id and child_id not in valid_ids:
        raise _error("not_found", "Unknown child")
    if not get_store().set_child_id(case_id, child_id or None):
        raise _error("not_found")
    return JSONResponse({"case": view(_case_or_404(case_id, ui), ui)})


@app.get("/api/calendar")
def api_calendar(year: int | None = Query(default=None), month: int | None = Query(default=None),
                 lang: str | None = Query(default=None)) -> JSONResponse:
    """Build a month from active action deadlines already stored on cases."""
    ui = _lang(lang)
    reference = today()
    year = reference.year if year is None else year
    month = reference.month if month is None else month
    if year < 1 or not 1 <= month <= 12:
        raise _error("bad_calendar", "year must be positive and month must be 1..12")
    days: dict[str, list[dict[str, Any]]] = {}
    for case in get_store().list_all(ui):
        if case.get("status") not in ("open", "due", "replied"):
            continue
        card = view(case, ui)
        for row in case.get("rows") or []:
            if row.get("status") != "active":
                continue
            stamp = parse_date(row.get("deadline"))
            if not stamp or stamp.year != year or stamp.month != month:
                continue
            days.setdefault(stamp.isoformat(), []).append({
                "case_id": card["id"],
                "title": card["title"],
                "do": row.get("do") or "",
                "what": row.get("what") or "",
                "deadline": stamp.isoformat(),
                "child_id": card["child_id"],
                "child_name": card["child_name"],
                "state": card["state"],
            })
    for items in days.values():
        items.sort(key=lambda item: (item["title"], item["case_id"], item["do"]))
    return JSONResponse({
        "year": year,
        "month": month,
        "days": [{"date": key, "items": days[key]} for key in sorted(days)],
    })


def _raw_case(case: dict[str, Any]) -> dict[str, Any]:
    raw = case.get("_raw")
    return raw if isinstance(raw, dict) else case


def _paper_actions(raw: dict[str, Any], paper: dict[str, Any], paper_count: int) -> list[dict[str, Any]]:
    paper_id = str(paper.get("id") or "")
    actions = [
        {**a, "status": a.get("status") or "active"}
        for a in raw.get("actions") or []
        if isinstance(a, dict)
    ]
    linked = [a for a in actions if str(a.get("paper_id") or "") == paper_id]
    if not linked and paper_count == 1:
        linked = [a for a in actions if not a.get("paper_id") or str(a.get("paper_id")) == paper_id]
    return linked


@app.get("/api/board")
def api_board(lang: str | None = Query(default=None)) -> JSONResponse:
    """List the papers already attached to cases, newest first."""
    ui = _lang(lang)
    try:
        from papelito.agent import needs_calendar, needs_reply
    except Exception:
        needs_reply = lambda case: any(
            a.get("status") in ("active", "pending") and a.get("kind") in ("reply", "pay")
            for a in case.get("actions") or []
        )
        needs_calendar = lambda case: any(
            a.get("status") == "active" and a.get("deadline_iso")
            for a in case.get("actions") or []
        )

    entries: list[tuple[str, str, dict[str, Any]]] = []
    for case in get_store().list_all(ui):
        raw = _raw_case(case)
        papers = [p for p in raw.get("papers") or [] if isinstance(p, dict)]
        for index, paper in enumerate(papers):
            actions = _paper_actions(raw, paper, len(papers))
            action_case = {"actions": actions}
            has_reply = bool(needs_reply(action_case))
            has_calendar = bool(needs_calendar(action_case))
            text = " ".join(str(paper.get("text") or "").split())
            if len(text) > 180:
                text = text[:177].rstrip() + "..."
            received_on = str(paper.get("received_on") or "")
            entry = {
                "paper_id": str(paper.get("id") or ""),
                "case_id": str(case.get("id") or ""),
                "title": str(raw.get("title") or raw.get("what") or case.get("what") or "Kindergarten"),
                "kind": str(paper.get("kind") or "original"),
                "board": "action" if has_reply or has_calendar else "notice",
                "received_on": received_on,
                "photo": str(paper.get("photo_path") or ""),
                "text_preview": text,
                "child_id": str(case.get("child_id") or ""),
                "child_name": str(case.get("child_name") or ""),
                "has_reply": has_reply,
                "has_calendar": has_calendar,
                "n_actions": len(actions),
            }
            entries.append((received_on, str(paper.get("created_at") or ""), {"_index": index, **entry}))
    entries.sort(key=lambda item: (item[0], item[1], item[2]["_index"]), reverse=True)
    return JSONResponse({"items": [{key: value for key, value in item.items() if key != "_index"}
                                    for _, _, item in entries]})
