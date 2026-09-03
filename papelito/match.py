"""match_case: the amendment reconciler.

A follow-up note about the same Kindergarten event ("moved to Friday, bring
rain boots, confirm by tomorrow") must land in the *same* case. Old actions
of the same kind are marked superseded, the new ones become active, and the
artifacts (calendar, reply, card) are marked stale so the agent regenerates
them. Nothing is deleted: the struck-through items stay visible.

Decision: a deterministic score (sender, event words, event date, amendment
markers, recency). Above ``EXISTING`` the case matches; below ``NEW`` it is a
new case; in between the text model is asked to pick, if one is available.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from papelito.store import Store

EXISTING = 0.6
NEW = 0.35
MAX_AGE_DAYS = 90

AMENDMENT_MARKERS = (
    "verschoben", "verschiebt", "neuer termin", "neuen termin", "statt ", "anstatt", "änderung", "aenderung",
    "geändert", "geaendert", "leider", "doch ", "nun ", "erinnerung", "nochmals", "wie angekündigt",
    "wie bereits", "korrektur", "entfällt", "abgesagt", "findet nicht statt", "nachtrag", "update",
    "zusätzlich", "zusaetzlich", "ergänzung", "bitte nicht vergessen", "wetterbedingt",
)
EVENT_WORDS = (
    "elternabend", "ausflug", "wandertag", "laternenfest", "martinsfest", "sommerfest", "fasching",
    "faschingsfest", "abschlussfest", "fest", "feier", "schließtag", "schliesstag", "geschlossen", "fortbildung",
    "fotograf", "zahnarzt", "impfung", "elternsprechtag", "eingewöhnung", "meldezettel", "anmeldung",
    "abmeldung", "elternbeitrag", "essensgeld", "ferienbetreuung", "theater", "bibliothek", "schwimmen",
    "turnen", "waldtag", "spielplatz", "museum", "zoo", "bauernhof", "nikolaus", "weihnachtsfeier",
)
_STOP = set("und oder der die das den dem des ein eine einen einem eines mit für von bis am um im in an auf zu bei sie ihr ihre ihren wir uns unser unsere bitte liebe lieber eltern kinder kind team kindergarten gruppe uhr euro sehr geehrte geehrter freundlichen grüßen gruessen".split())


def _norm_sender(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"kindergarten|hort|volksschule|schule|gemeinde|magistrat|stadt|praxis|dr\.?", " ", s)
    return " ".join(re.findall(r"[a-zäöüß]{3,}", s))


def _tokens(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-zäöüß]{4,}", (text or "").lower()) if w not in _STOP}


def _event_words(text: str | None) -> set[str]:
    low = (text or "").lower()
    return {w for w in EVENT_WORDS if w in low}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _days_between(a: str | None, b: str | None) -> int | None:
    try:
        return abs((date.fromisoformat(str(a)[:10]) - date.fromisoformat(str(b)[:10])).days)
    except (TypeError, ValueError):
        return None


def score_case(case: dict[str, Any], new: dict[str, Any]) -> tuple[float, list[str]]:
    """How likely ``new`` (a freshly read paper) belongs to ``case``. Returns (0..1, reasons)."""
    reasons: list[str] = []
    score = 0.0
    last_paper = max((p.get("received_on") or "" for p in case.get("papers", [])), default=case.get("created_at", ""))
    age = _days_between(last_paper, new.get("received_on"))
    if age is not None and age > MAX_AGE_DAYS:
        return 0.0, ["too_old"]

    case_text = " ".join([case.get("title") or ""] + [p.get("text") or "" for p in case.get("papers", [])]
                         + [a.get("action") or "" for a in case.get("actions", [])])
    new_text = " ".join([new.get("title") or "", new.get("text") or ""]
                        + [a.get("action") or "" for a in new.get("actions", [])])

    cs, ns = _norm_sender(case.get("sender")), _norm_sender(new.get("sender"))
    if cs and ns and (cs == ns or cs in ns or ns in cs):
        score += 0.3
        reasons.append("same_sender")
    elif not cs or not ns:
        if (case.get("sender_type") or "kindergarten") == (new.get("sender_type") or "kindergarten"):
            score += 0.1
            reasons.append("same_sender_type")
    elif (case.get("sender_type") or "") != (new.get("sender_type") or ""):
        score -= 0.2
        reasons.append("different_sender_type")

    ew = _jaccard(_event_words(case_text), _event_words(new_text))
    if ew > 0:
        score += 0.3 * min(1.0, ew * 2)
        reasons.append("same_event_words")
    tw = _jaccard(_tokens(case_text), _tokens(new_text))
    score += 0.2 * min(1.0, tw * 4)
    if tw >= 0.1:
        reasons.append("shared_words")

    case_dates = {a.get("deadline_iso") for a in case.get("actions", []) if a.get("deadline_iso")}
    if case.get("event_date"):
        case_dates.add(case["event_date"])
    new_dates = {a.get("deadline_iso") for a in new.get("actions", []) if a.get("deadline_iso")}
    if new.get("event_date"):
        new_dates.add(new["event_date"])
    if case_dates and new_dates:
        gaps = [d for d in (_days_between(x, y) for x in case_dates for y in new_dates) if d is not None]
        if gaps and min(gaps) == 0:
            score += 0.25
            reasons.append("same_date")
        elif gaps and min(gaps) <= 14:
            score += 0.12
            reasons.append("date_within_2_weeks")

    if any(m in (new.get("text") or "").lower() for m in AMENDMENT_MARKERS) and score > 0.15:
        score += 0.15
        reasons.append("amendment_wording")
    if age is not None and age <= 45:
        score += 0.05
    return max(0.0, min(1.0, round(score, 3))), reasons


def _ask_model(candidates: list[tuple[dict, float, list[str]]], new: dict[str, Any], model: Any) -> str | None:
    from strands import Agent

    summary = [{
        "case_id": c["id"], "title": c.get("title"), "sender": c.get("sender"), "event_date": c.get("event_date"),
        "actions": [a["action"] for a in c.get("actions", []) if a.get("status") == "active"][:6],
        "score": s,
    } for c, s, _ in candidates]
    prompt = (
        "A parent photographed a new note. Decide whether it is a follow-up (amendment) to one of the open cases "
        "or a new, unrelated event. Answer with JSON only: {\"case_id\": id or null}.\n\n"
        f"Open cases: {json.dumps(summary, ensure_ascii=False)}\n\nNew note (received {new.get('received_on')}):\n{new.get('text')}"
    )
    agent = Agent(model=model, callback_handler=None, name="papelito-match",
                  system_prompt="You reconcile Kindergarten paperwork. Same event = same case, even if dates moved.")
    raw = str(agent(prompt))
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        cid = json.loads(m.group(0)).get("case_id")
    except json.JSONDecodeError:
        return None
    return cid if cid in {c["id"] for c, _, _ in candidates} else None


def match_case(store: Store, new: dict[str, Any], model: Any = None) -> dict[str, Any]:
    """Existing case id or None (= new case), with the scoring trail.

    ``new`` = the extraction dict from ``extract.extract`` plus ``text``.
    """
    candidates = []
    for case in store.list_open():
        s, reasons = score_case(case, new)
        if s > 0:
            candidates.append((case, s, reasons))
    candidates.sort(key=lambda t: -t[1])
    trail = [{"case_id": c["id"], "title": c.get("title"), "score": s, "reasons": r} for c, s, r in candidates[:5]]
    if not candidates:
        return {"case_id": None, "decision": "new", "score": 0.0, "candidates": trail}
    best, score, reasons = candidates[0]
    if score >= EXISTING:
        return {"case_id": best["id"], "decision": "existing", "score": score, "reasons": reasons, "candidates": trail}
    if score >= NEW and model is not None:
        try:
            picked = _ask_model(candidates[:3], new, model)
        except Exception:
            picked = None
        if picked:
            return {"case_id": picked, "decision": "existing", "score": score, "reasons": reasons + ["model_confirmed"],
                    "candidates": trail}
    return {"case_id": None, "decision": "new", "score": score, "reasons": reasons, "candidates": trail}


def enrich_from_case(case: dict[str, Any], extraction: dict[str, Any]) -> list[str]:
    """A follow-up refers to things the case already knows. Fill them in instead of asking.

    "Das Geld bitte bis morgen abgeben" inherits the 8 € from the case's pay action;
    "Regenstiefel mitgeben" without a date takes the event date. Returns the notes applied.
    """
    from papelito.extract import gate_for

    notes: list[str] = []
    active = [a for a in case.get("actions", []) if a.get("status") == "active"]
    old_pay = next((a for a in active if a.get("kind") == "pay" and a.get("amount") is not None), None)
    event_date = extraction.get("event_date") or case.get("event_date")
    for a in extraction.get("actions", []):
        flags = a.setdefault("flags", [])
        if a.get("kind") == "pay" and a.get("amount") is None and old_pay:
            a["amount"] = old_pay["amount"]
            a["flags"] = [f for f in flags if f != "amount_missing"] + ["amount_from_case"]
            a["confidence"] = max(a.get("confidence", 0.5), min(0.85, float(old_pay.get("confidence", 0.8))))
            notes.append(f"pay: amount {old_pay['amount']:g} € inherited from {old_pay['id']}")
        if a.get("kind") == "bring" and not a.get("deadline_iso") and event_date:
            a["deadline_iso"] = event_date
            a["flags"] = flags + ["date_from_event"]
            a["confidence"] = min(a.get("confidence", 0.75), 0.75)
            notes.append(f"bring: deadline {event_date} taken from the event date")
        if a.get("gate") != "drop" or not notes:
            a["gate"] = gate_for(float(a.get("confidence", 0.0)))
            a["question"] = _question(a["flags"]) if a["gate"] == "ask" else None
    return notes


def _question(flags: list[str]) -> str:
    from papelito.extract import question_code

    return question_code([f for f in flags if not f.endswith("_from_case") and not f.endswith("_from_event")])


# --------------------------------------------------------------- amendment
def _same_item(a: dict, b: dict) -> bool:
    """Two bring/info actions talk about the same thing?"""
    return _jaccard(_tokens(a.get("action")), _tokens(b.get("action"))) >= 0.34 or \
        _jaccard(_tokens(a.get("source_line")), _tokens(b.get("source_line"))) >= 0.5


def plan_amendment(old_actions: list[dict], new_actions: list[dict]) -> dict[str, list]:
    """Which old (active) actions the new ones replace. Pure, no store access.

    Returns {"supersede": [(old, new)], "add": [new], "keep": [old]}.
    """
    active = [a for a in old_actions if a.get("status", "active") == "active"]
    supersede: list[tuple[dict, dict]] = []
    taken: set[str] = set()
    cancelled = any(n.get("kind") == "cancel" for n in new_actions)
    for n in new_actions:
        for o in active:
            if o.get("id") in taken:
                continue
            same_kind = o.get("kind") == n.get("kind")
            if n.get("kind") == "cancel":
                supersede.append((o, n))
                taken.add(o.get("id"))
            elif same_kind and n["kind"] in ("reply", "pay", "attend", "closed"):
                supersede.append((o, n))
                taken.add(o.get("id"))
                break
            elif same_kind and n["kind"] in ("bring", "info") and _same_item(o, n):
                supersede.append((o, n))
                taken.add(o.get("id"))
                break
    keep = [o for o in active if o.get("id") not in taken and not cancelled]
    return {"supersede": supersede, "add": list(new_actions), "keep": keep}


def apply_amendment(store: Store, case_id: str, paper: dict[str, Any], new_actions: list[dict[str, Any]],
                    meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach a follow-up paper to ``case_id`` and reconcile its actions.

    Returns {"case_id", "added": [...], "superseded": [...], "kept": [...], "stale_artifacts": [...]}.
    """
    case = store.get_case(case_id)
    if case is None:
        raise KeyError(case_id)
    paper = dict(paper, kind=paper.get("kind") or "amendment")
    paper_id = store.add_paper(case_id, paper)
    plan = plan_amendment(case["actions"], new_actions)
    to_add = [dict(a, paper_id=paper_id, status="active") for a in plan["add"]]
    added_ids = store.add_actions(case_id, to_add)
    for a, aid in zip(to_add, added_ids):
        a["id"] = aid
    superseded = []
    for old, new in plan["supersede"]:
        new_id = next((a["id"] for a in to_add if a is new or (a["action"] == new["action"] and a["source_line"] == new["source_line"])), None)
        store.supersede_actions([old["id"]], new_id)
        superseded.append(dict(old, status="superseded", superseded_by=new_id))
    stale = store.supersede_artifacts(case_id)
    update: dict[str, Any] = {"id": case_id}
    meta = meta or {}
    new_event = next((a["deadline_iso"] for a in to_add if a["kind"] == "attend" and a.get("deadline_iso")), None)
    if new_event:
        update["event_date"] = new_event
    if meta.get("title") and (case.get("title") in (None, "", "Kindergarten")):
        update["title"] = meta["title"]
    if case.get("status") in ("replied", "closed") and any(a["kind"] in ("reply", "pay", "attend", "bring") for a in to_add):
        update["status"] = "open"  # the old reply no longer answers the new note
    store.save_case(update)
    store.log_event(case_id, "amendment", {"paper_id": paper_id, "added": len(to_add), "superseded": len(superseded)})
    return {"case_id": case_id, "paper_id": paper_id, "added": to_add, "superseded": superseded,
            "kept": plan["keep"], "stale_artifacts": stale}
