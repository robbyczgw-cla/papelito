"""The Strands agent "papelito" and its tools.

Plain ``@tool`` functions over the case file. Tools share the paper they are
working on through a small in-process session keyed by ``paper_id`` (the
hash of the note text), so the model passes ids around instead of copying
note text through every call.

Models: ``deepseek-v4-flash-vision-exp`` for reading (max_tokens >= 2000),
``deepseek-v4-flash`` for everything else, through the Zen OpenAI-compatible
gateway. If ``papelito.models`` (owned by another agent) exists it is used;
otherwise the models are built here from the key in ``~/.pi/agent/auth.json``.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from strands import Agent, tool

from papelito import explain as _explain
from papelito import extract as _extract
from papelito import match as _match
from papelito import reply as _reply
from papelito.store import Store, get_store

ZEN_URL = "https://opencode.ai/zen/go/v1"
VISION_MODEL_ID = "deepseek-v4-flash-vision-exp"
TEXT_MODEL_ID = "deepseek-v4-flash"

SESSION: dict[str, dict[str, Any]] = {}
_CTX: dict[str, Any] = {"store": None, "profile": None, "vision": None, "text": None, "models_loaded": False}


# ------------------------------------------------------------- configuration
def zen_key() -> str | None:
    for env in ("ZEN_API_KEY", "OPENCODE_GO_KEY", "OPENCODE_API_KEY"):
        if os.environ.get(env):
            return os.environ[env]
    auth = Path("~/.pi/agent/auth.json").expanduser()
    if auth.exists():
        try:
            data = json.loads(auth.read_text())
            entry = data.get("opencode-go") or data.get("opencode-go.key")
            if isinstance(entry, dict):
                return entry.get("key")
            if isinstance(entry, str):
                return entry
        except (OSError, json.JSONDecodeError):
            return None
    return None


def load_models() -> tuple[Any, Any]:
    """(vision_model, text_model). Either may be None when no key is configured."""
    try:  # sibling module, if present
        from papelito import models as _models  # type: ignore

        v = getattr(_models, "vision_model", None) or getattr(_models, "VISION", None)
        t = getattr(_models, "text_model", None) or getattr(_models, "TEXT", None)
        v = v() if callable(v) else v
        t = t() if callable(t) else t
        if v is not None and t is not None:
            return v, _fast(t)
    except Exception:
        pass
    key = zen_key()
    if not key:
        return None, None
    from strands.models.openai import OpenAIModel

    vision = OpenAIModel(client_args={"api_key": key, "base_url": ZEN_URL}, model_id=VISION_MODEL_ID,
                         params={"max_tokens": 2500, "temperature": 0})
    text = OpenAIModel(client_args={"api_key": key, "base_url": ZEN_URL}, model_id=TEXT_MODEL_ID,
                       params={"max_tokens": 2000, "temperature": 0.2})
    return vision, _fast(text)


def _fast(text_model: Any) -> Any:
    """Turn off chain-of-thought for the text rounds.

    Measured 2026-09-03 on the same extraction prompt: default 30.8 s / 4.5k output tokens,
    ``reasoning_effort="none"`` 3.3 s / 225 tokens, same JSON. Override with PAPELITO_REASONING=low|medium|high.
    """
    effort = os.environ.get("PAPELITO_REASONING", "none")
    try:
        cfg = text_model.get_config() if hasattr(text_model, "get_config") else {}
        params = dict(cfg.get("params") or {})
        params["reasoning_effort"] = effort
        text_model.update_config(params=params)
    except Exception:
        pass
    return text_model


def configure(store: Store | None = None, profile: dict[str, Any] | None = None, vision: Any = None, text: Any = None,
              use_models: bool = True) -> None:
    if store is not None:
        _CTX["store"] = store
    if profile is not None:
        _CTX["profile"] = profile
    if use_models:
        _CTX["vision"], _CTX["text"] = (vision, text) if (vision or text) else load_models()
    else:
        _CTX["vision"], _CTX["text"] = None, None
    _CTX["models_loaded"] = True


def _store() -> Store:
    if _CTX["store"] is None:
        _CTX["store"] = get_store()
    return _CTX["store"]


def _profile() -> dict[str, Any]:
    if _CTX["profile"] is None:
        _CTX["profile"] = _reply.load_profile()
    return _CTX["profile"]


def _models() -> tuple[Any, Any]:
    if not _CTX["models_loaded"]:
        configure()
    return _CTX["vision"], _CTX["text"]


def out_dir() -> Path:
    p = Path(os.environ.get("PAPELITO_OUT", "~/.local/share/papelito/out")).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------------ tools
@tool
def check_photo(image_path: str) -> dict:
    """Check a note photo for blur, glare and clipped text before spending a vision call.

    Args:
        image_path: Path to the photo (jpg/png).
    """
    try:
        from papelito import photo as _photo  # type: ignore

        if hasattr(_photo, "check_photo"):
            out = _photo.check_photo(image_path)
            if isinstance(out, dict):
                return out
            if hasattr(out, "to_dict"):
                d = dict(out.to_dict())
            else:
                import dataclasses

                d = dataclasses.asdict(out) if dataclasses.is_dataclass(out) else {"ok": bool(out)}
            d.setdefault("hint", "; ".join(d.get("reasons") or []) or "ok")
            return d
    except ImportError:
        pass
    return _local_check_photo(image_path)


def _local_check_photo(image_path: str) -> dict:
    from PIL import Image, ImageFilter, ImageStat

    p = Path(image_path)
    if not p.exists():
        return {"ok": False, "hint": "file not found"}
    im = Image.open(p).convert("L")
    w, h = im.size
    edges = im.filter(ImageFilter.FIND_EDGES)
    blur_score = ImageStat.Stat(edges).stddev[0]
    hist = im.histogram()
    glare = sum(hist[250:]) / (w * h)
    border = 0.03
    dark = 0
    for box in ((0, 0, w, int(h * border)), (0, int(h * (1 - border)), w, h), (0, 0, int(w * border), h), (int(w * (1 - border)), 0, w, h)):
        crop = im.crop(box)
        dark += sum(crop.histogram()[:80]) / max(1, crop.size[0] * crop.size[1])
    clipped = dark / 4 > 0.08
    hints = []
    if blur_score < 6:
        hints.append("blurry: hold still or move closer")
    if glare > 0.12:
        hints.append("glare: tilt away from the light")
    if clipped:
        hints.append("text touches the edge: include the whole note")
    if w < 600 or h < 600:
        hints.append("low resolution")
    return {"ok": not hints, "blur_score": round(blur_score, 1), "glare_fraction": round(glare, 3),
            "edge_clipped": clipped, "width": w, "height": h, "hint": "; ".join(hints) or "ok"}


@tool
def read_note(image_path: str, received_on: str) -> dict:
    """Read a photographed German note with the vision model. Returns paper_id, text and lines.

    Args:
        image_path: Path to the photo.
        received_on: ISO date the note reached the parent (YYYY-MM-DD).
    """
    vision, _ = _models()
    if vision is None:
        return {"error": "no vision model configured (set ZEN_API_KEY or ~/.pi/agent/auth.json)"}
    p = Path(image_path)
    fmt = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp", ".gif": "gif"}.get(p.suffix.lower(), "jpeg")
    data = p.read_bytes()
    reader = Agent(model=vision, callback_handler=None, name="papelito-reader",
                   system_prompt="You transcribe photographed German notes from Austrian Kindergartens, schools, offices and "
                                 "doctors. Output the text exactly as printed, one line per printed line, keep umlauts, dates, "
                                 "times and amounts verbatim. If a word is unreadable write [unleserlich]. No commentary.")
    result = reader([{"text": "Transcribe this note."}, {"image": {"format": fmt, "source": {"bytes": data}}}])
    text = str(result).strip()
    return register_paper(text, received_on, photo_path=str(p))


def register_paper(text: str, received_on: str, photo_path: str | None = None) -> dict:
    """Put a note text into the session (used by read_note and by the CLI --text path)."""
    pid = _extract.paper_id_for(text)
    lines = _extract.note_lines(text)
    SESSION[pid] = {"paper_id": pid, "text": text, "lines": lines, "received_on": received_on, "photo_path": photo_path}
    return {"paper_id": pid, "received_on": received_on, "n_lines": len(lines), "text": text}


@tool
def extract_actions(text: str, received_on: str) -> dict:
    """Extract the actions a note demands: [{action, kind, deadline_iso, amount, source_line, confidence, gate}].

    Args:
        text: The note text, or a paper_id returned by read_note.
        received_on: ISO date the note was received (YYYY-MM-DD).
    """
    if text.startswith("paper_") and text in SESSION:
        text = SESSION[text]["text"]
    _, tm = _models()
    ext = _extract.extract(text, received_on, model=tm)
    pid = ext["paper_id"]
    SESSION.setdefault(pid, {"paper_id": pid, "text": text, "lines": _extract.note_lines(text), "received_on": received_on})
    SESSION[pid]["extraction"] = ext
    needs = [a for a in ext["actions"] if a["gate"] == "ask"]
    return {**ext, "needs_confirmation": len(needs)}


@tool
def resolve_dates(phrase: str, received_on: str) -> dict:
    """Deterministically resolve a German date phrase ("bis Freitag", "innerhalb von 14 Tagen", "17.09.") to ISO.

    Args:
        phrase: The German phrase.
        received_on: ISO date the note was received.
    """
    return {"phrase": phrase, "iso": _extract.resolve_date(phrase, received_on)}


@tool
def match_case(paper_id: str) -> dict:
    """Decide whether an extracted paper is a follow-up to an open case (amendment) or a new case.

    Args:
        paper_id: paper_id from extract_actions.
    """
    sess = SESSION.get(paper_id)
    if not sess or "extraction" not in sess:
        return {"error": f"unknown paper {paper_id}; run extract_actions first"}
    _, tm = _models()
    new = {**sess["extraction"], "text": sess["text"]}
    out = _match.match_case(_store(), new, model=tm)
    sess["match"] = out
    if out.get("case_id"):
        case = _store().get_case(out["case_id"])
        if case:
            out["inherited"] = _match.enrich_from_case(case, sess["extraction"])
    return out


@tool
def save_case(paper_id: str, case_id: str = "") -> dict:
    """Save the paper: create a case, or apply it as an amendment to case_id (old items get superseded).

    Args:
        paper_id: paper_id from extract_actions.
        case_id: Existing case id from match_case, or empty for a new case.
    """
    sess = SESSION.get(paper_id)
    if not sess or "extraction" not in sess:
        return {"error": f"unknown paper {paper_id}; run extract_actions first"}
    store = _store()
    ext = sess["extraction"]
    case_id = case_id or (sess.get("match") or {}).get("case_id") or ""
    keep = [a for a in ext["actions"] if a["gate"] in ("ok", "ask") or a.get("confirmed")]
    actions = []
    for a in keep:
        row = {k: v for k, v in a.items() if k not in ("flags", "gate", "confirmed")}
        row["status"] = "active" if (a["gate"] == "ok" or a.get("confirmed")) else "pending"
        row["question"] = None if row["status"] == "active" else (a.get("question") or "line")
        actions.append(row)
    paper = {"received_on": ext["received_on"], "photo_path": sess.get("photo_path"), "text": sess["text"]}
    if case_id and store.get_case(case_id):
        diff = _match.apply_amendment(store, case_id, paper, actions, meta=ext)
        sess["case_id"] = case_id
        sess["diff"] = diff
        return {"case_id": case_id, "result": "amended", "added": len(diff["added"]),
                "superseded": [a["action"] for a in diff["superseded"]], "kept": len(diff["kept"]),
                "pending": sum(1 for a in actions if a["status"] == "pending")}
    case_id = store.save_case({
        "title": ext["title"], "sender": ext.get("sender"), "sender_type": ext.get("sender_type"),
        "event_date": ext.get("event_date"), "language": _profile().get("language", "en"),
        "papers": [dict(paper, kind="original")], "actions": actions,
    })
    sess["case_id"] = case_id
    sess["diff"] = None
    store.log_event(case_id, "created", {"paper_id": paper_id, "actions": len(actions),
                                          "dropped": len(ext["actions"]) - len(keep)})
    return {"case_id": case_id, "result": "created", "actions": len(actions), "dropped": len(ext["actions"]) - len(keep),
            "pending": sum(1 for a in actions if a["status"] == "pending")}


@tool
def explain_in(language: str, case_id: str) -> dict:
    """Produce the four-column card (what / do / by when / done-for-you) for a case in the reader's language.

    Args:
        language: en or de for the public demo.
        case_id: The case id.
    """
    store = _store()
    case = store.get_case(case_id)
    if case is None:
        return {"error": f"no case {case_id}"}
    _, tm = _models()
    done = {a["kind"]: True for a in case["artifacts"] if a["status"] == "active"}
    done["saved"] = True
    card = _explain.explain_in(language, case, model=tm, done=done)
    # Keep the structured reader card. The PWA can then render the same verified
    # translations without a second model call; older plain-text card artifacts
    # remain readable through the deterministic fallback.
    store.add_artifact(case_id, "card", json.dumps(card, ensure_ascii=False))
    return {"case_id": case_id, "text": card["text"], "rows": len(card["rows"])}


@tool
def write_ics(case_id: str) -> dict:
    """Write the calendar file for a case: one VEVENT per active action with a deadline, alarm 48 h before.

    Args:
        case_id: The case id.
    """
    store = _store()
    case = store.get_case(case_id)
    if case is None:
        return {"error": f"no case {case_id}"}
    if not needs_calendar(case):
        return {"case_id": case_id, "skipped": "no deadline", "events": 0}
    content = None
    try:
        from papelito import ics as _ics  # type: ignore

        fn = getattr(_ics, "write_ics", None)
        if fn:
            out = fn({**case, "actions": [a for a in case["actions"] if a["status"] == "active"]})
            content = out if isinstance(out, str) and out.lstrip().startswith("BEGIN:VCALENDAR") else (Path(out).read_text() if out else None)
    except ImportError:
        pass
    if content is None:
        content = _local_ics(case)
    path = out_dir() / f"{case_id}.ics"
    path.write_text(content, encoding="utf-8")
    store.add_artifact(case_id, "ics", content)
    n = content.count("BEGIN:VEVENT")
    return {"case_id": case_id, "path": str(path), "events": n}


def _local_ics(case: dict) -> str:
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Papelito//EN", "CALSCALE:GREGORIAN"]
    for a in case["actions"]:
        if a["status"] != "active" or not a.get("deadline_iso"):
            continue
        d = date.fromisoformat(a["deadline_iso"][:10])
        nxt = d.toordinal() + 1
        summ = f"{case.get('title') or 'Kindergarten'}: {a['action']}"
        if a.get("amount"):
            summ += f" ({a['amount']:g} €)"
        desc = f"Quelle: {a['source_line']}".replace("\n", " ")
        lines += ["BEGIN:VEVENT", f"UID:{a['id']}@papelito", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{date.fromordinal(nxt).strftime('%Y%m%d')}",
                  f"SUMMARY:{summ}", f"DESCRIPTION:{desc}",
                  "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{summ}", "TRIGGER:-PT48H", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


REPLY_KINDS = ("reply", "pay")


def needs_reply(case: dict[str, Any]) -> bool:
    """A Tagesablauf or Termine-Aushang is information. Only draft when the paper asks for an answer or money."""
    for a in case.get("actions") or []:
        if a.get("status") not in ("active", "pending"):
            continue
        if a.get("kind") in REPLY_KINDS:
            return True
    return False


def needs_calendar(case: dict[str, Any]) -> bool:
    """Write .ics only when an active action has a real deadline."""
    for a in case.get("actions") or []:
        if a.get("status") != "active":
            continue
        if a.get("deadline_iso"):
            return True
    return False


@tool
def draft_reply(case_id: str, attend: bool = True, persons: int = 1) -> dict:
    """Draft the German reply (Sie-form, register by sender type) for a case. Never sent, only stored.

    Args:
        case_id: The case id.
        attend: Whether the family attends (default from the profile).
        persons: How many persons attend.
    """
    store = _store()
    case = store.get_case(case_id)
    if case is None:
        return {"error": f"no case {case_id}"}
    if not needs_reply(case):
        return {"case_id": case_id, "skipped": "info only", "text": ""}
    _, tm = _models()
    text = _reply.draft_reply(case, _profile(), answers={"attend": attend, "persons": persons}, model=tm)
    store.add_artifact(case_id, "reply", text)
    path = out_dir() / f"{case_id}-antwort.txt"
    path.write_text(text, encoding="utf-8")
    return {"case_id": case_id, "path": str(path), "text": text}


@tool
def glossary_at(term: str) -> dict:
    """Austrian family-paper glossary (Kindergarten, Hort, MA, Gemeinde, Meldezettel...). Static, cited.

    Args:
        term: The German term.
    """
    try:
        from papelito import glossary as _glossary  # type: ignore

        fn = getattr(_glossary, "glossary_at", None) or getattr(_glossary, "lookup", None)
        if fn:
            out = fn(term)
            return out if isinstance(out, dict) else {"term": term, "entry": out}
    except ImportError:
        pass
    return {"term": term, "entry": None, "note": "glossary module not available"}


@tool
def lookup_office(name: str) -> dict:
    """Find what/where/phone/URL of an Austrian office. Personal data is stripped before the web lookup.

    Args:
        name: Office name as printed on the paper.
    """
    try:
        from papelito import lookup as _lookup  # type: ignore

        fn = getattr(_lookup, "lookup_office", None)
        if fn:
            out = fn(name)
            return out if isinstance(out, dict) else {"name": name, "result": out}
    except ImportError:
        pass
    return {"name": name, "result": None, "note": "lookup module not available"}


@tool
def mark_replied(case_id: str) -> dict:
    """Mark a case as replied (the human sent the reply). Stops the watchdog reminders.

    Args:
        case_id: The case id.
    """
    return {"case_id": case_id, "replied": _store().mark_replied(case_id)}


@tool
def list_open() -> dict:
    """List open and due cases with their active actions and next deadline."""
    out = []
    for c in _store().list_open():
        active = [a for a in c["actions"] if a["status"] == "active"]
        out.append({"case_id": c["id"], "title": c["title"], "status": c["status"], "sender": c.get("sender"),
                    "next_deadline": min((a["deadline_iso"] for a in active if a["deadline_iso"]), default=None),
                    "actions": [{"action": a["action"], "deadline_iso": a["deadline_iso"], "kind": a["kind"]} for a in active],
                    "due_line": c.get("due_line")})
    return {"cases": out}


@tool
def delete_case(case_id: str) -> dict:
    """Delete a case and everything attached to it. Really deletes (secure_delete + VACUUM).

    Args:
        case_id: The case id.
    """
    return {"case_id": case_id, "deleted": _store().delete_case(case_id)}


# ---------------------------------------------------- entry points for others
def process_photo(photo_path: str, received_on: str, language: str | None = None, text: str | None = None,
                  on_step: Any = None) -> dict | None:
    """Photo (or transcribed ``text``) → saved case dict. The web app calls this; no model loop, fixed tool order.

    Low-confidence items are stored as ``pending`` with their question; the UI answers them
    through ``Store.confirm_action`` / ``Store.drop_action``. Returns None when nothing could be read.

    ``on_step(tool_name, info)`` is called after each tool returns, so a caller can show the
    fourth column filling up while the work happens. It is never called for a tool that did not run.
    """
    store = _store()
    lang = language or _profile().get("language", "en")

    def step(tool_name: str, **info: Any) -> None:
        if on_step is None:
            return
        try:
            on_step(tool_name, info)
        except Exception:  # a progress display must never break the reading
            pass

    if text is None:
        chk = check_photo(image_path=photo_path)
        reasons = list(chk.get("reasons") or [])
        hard = [r for r in reasons if r != "clipped-text"]
        ok = bool(chk.get("ok", True)) or (not hard)
        step("check_photo", ok=ok, hint=chk.get("hint"))
        if not ok:
            return {"id": None, "status": "unread", "photo": photo_path, "received_on": received_on,
                    "question": f"Photo not readable: {chk.get('hint')}. Take it again?",
                    "hint": chk.get("hint"), "check": chk}
        got = read_note(image_path=photo_path, received_on=received_on)
        if "error" in got:
            step("read_note", ok=False, error=got["error"])
            return None
        step("read_note", ok=True, n_lines=got.get("n_lines"))
        pid = got["paper_id"]
    else:
        pid = register_paper(text, received_on, photo_path=photo_path)["paper_id"]
        step("read_note", ok=True, n_lines=None)
    ext = extract_actions(text=pid, received_on=received_on)
    step("extract_actions", ok=True, actions=len(ext.get("actions") or []),
         needs_confirmation=ext.get("needs_confirmation", 0))
    m = match_case(paper_id=pid)
    step("match_case", ok=True, result="amendment" if m.get("case_id") else "new", case_id=m.get("case_id"))
    saved = save_case(paper_id=pid, case_id=m.get("case_id") or "")
    cid = saved.get("case_id")
    step("save_case", ok=bool(cid), result=saved.get("result"), superseded=saved.get("superseded"))
    if not cid:
        return None
    case_now = store.get_case(cid) or {}
    if needs_calendar(case_now):
        ics = write_ics(case_id=cid)
        step("write_ics", ok=True, events=ics.get("events"))
    else:
        step("write_ics", ok=True, events=0, skipped="no deadline")
    if needs_reply(case_now):
        draft_reply(case_id=cid)
        step("draft_reply", ok=True)
    else:
        step("draft_reply", ok=True, skipped="info only")
    explain_in(language=lang, case_id=cid)
    step("explain_in", ok=True, language=lang)
    case = store.get_case(cid)
    case["photo"] = photo_path
    case["match"] = m
    case["amendment"] = SESSION[pid].get("diff")
    return case


def compose_reminder(case: dict, today: str | None = None, language: str | None = None) -> str | None:
    """The watchdog's reader-language line. Deterministic text; the model may rephrase it, digits must survive."""
    import re

    lang = language or case.get("language") or _profile().get("language", "en")
    today = today or date.today().isoformat()
    line = _explain.reminder_line(case, lang, today)
    if not line:
        return None
    _, tm = _models()
    if tm is None:
        return line
    target = {"en": "English", "de": "German"}.get(lang[:2], "English")
    agent = Agent(model=tm, callback_handler=None, name="papelito-remind",
                  system_prompt=f"Rewrite this reminder as one natural {target} sentence a parent reads on the phone. "
                                "Keep every number, date, € amount and name. Keep Kindergarten/Ausflug/Elternabend untranslated. "
                                "Return only the sentence.")
    try:
        out = str(agent(line)).strip()
    except Exception:
        return line
    if out and set(re.findall(r"\d+", line)) <= set(re.findall(r"\d+", out)) and len(out) < 240:
        return out
    return line


TOOLS = [check_photo, read_note, extract_actions, resolve_dates, match_case, save_case, explain_in, write_ics,
         draft_reply, glossary_at, lookup_office, mark_replied, list_open, delete_case]

SYSTEM_PROMPT = """You are papelito, an agent that reads the paper a Kindergarten, Hort, school, Gemeinde/Magistrat, doctor or Elternverein in Austria sends home with a child, and does the work for a parent who does not read German.

For a new photo, call the tools in this order and do not skip one:
1. check_photo(image_path)  – if not ok, say what to re-shoot and stop.
2. read_note(image_path, received_on)  – gives paper_id.
3. extract_actions(paper_id, received_on)  – actions with source lines and confidence.
4. match_case(paper_id)  – existing case (amendment) or new.
5. save_case(paper_id, case_id)  – case_id from step 4 or empty.
6. explain_in(language, case_id)
7. write_ics(case_id) only if an action has a deadline (Termine, Ausflug, Schließtag). Skip for a Tagesablauf with no date.
8. draft_reply(case_id) only if the paper asks for a reply or money (Rückmeldung, Beitrag). Skip for info: daily schedule, Termine-Aushang, general Kindergarten notice.
Never invent a date or an amount: only what the tools return. Never send anything. If extract_actions reports needs_confirmation > 0, say which line is unclear and stop after saving.
Final answer: plain text, no markdown, no headings, at most three short sentences in the reader's language: what the paper is, what to do, by when."""


def build_agent(hooks: list | None = None, callback_handler: Any = None, store: Store | None = None,
                profile: dict[str, Any] | None = None, use_models: bool = True) -> Agent:
    """The papelito agent. ``callback_handler=None`` keeps stdout quiet; hooks get tool events."""
    configure(store=store, profile=profile, use_models=use_models)
    _, text = _models()
    if text is None:
        raise RuntimeError("no text model configured; set ZEN_API_KEY or ~/.pi/agent/auth.json, or use the CLI --direct path")
    return Agent(model=text, tools=TOOLS, system_prompt=SYSTEM_PROMPT, name="papelito",
                 callback_handler=callback_handler, hooks=hooks or [])
