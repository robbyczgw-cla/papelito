"""extract_actions: turn the text of a note into actions with evidence.

Every action carries the German source line it came from and a confidence.
The model proposes; deterministic checks (date resolution, amount regex,
source-line lookup) verify and may lower the confidence. Gate:

    confidence >= ASK_BELOW   -> artifact is created
    DROP_BELOW <= c < ASK     -> show the source line, ask one question, no guess
    c < DROP_BELOW            -> no artifact, listed as unreadable

Works without a model too (regex heuristics), which is the test path and the
fallback when no key is configured.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from datetime import date, timedelta
from typing import Any

_LOG = logging.getLogger(__name__)

ASK_BELOW = 0.75
DROP_BELOW = 0.4

KINDS = ("reply", "pay", "bring", "attend", "closed", "cancel", "info")
SENDER_TYPES = ("kindergarten", "hort", "schule", "gemeinde", "amt", "arzt", "elternverein", "other")

# ----------------------------------------------------------------- dates
try:  # owned by another agent; use it when present
    from papelito import dates as _dates  # type: ignore
except Exception:  # pragma: no cover - depends on sibling module
    _dates = None

_WEEKDAYS = {
    "montag": 0, "mo": 0, "dienstag": 1, "di": 1, "mittwoch": 2, "mi": 2, "donnerstag": 3, "do": 3,
    "freitag": 4, "fr": 4, "samstag": 5, "sa": 5, "sonntag": 6, "so": 6,
}
_MONTHS = {
    "jänner": 1, "januar": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3, "april": 4, "apr": 4,
    "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
}
_RE_NUMERIC = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{2,4}))?(?!\d)")
_RE_LONG = re.compile(r"\b(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\.?(?:\s+(\d{4}))?")
_RE_DAYS = re.compile(r"(?:innerhalb|binnen)\s+(?:von\s+)?(\d{1,2})\s+tag|in\s+(\d{1,2})\s+tagen")
_RE_WEEKS = re.compile(r"(?:innerhalb|binnen)\s+(?:von\s+)?(\d{1,2})\s+woche|in\s+(\d{1,2})\s+wochen")


def _to_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _local_resolve(phrase: str, received_on: date) -> str | None:
    """Deterministic German date phrase → ISO date. No LLM. Returns None when unsure."""
    raw_phrase = phrase.strip()
    p = raw_phrase.lower()
    m = _RE_NUMERIC.search(p)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if y is None:
            year = received_on.year
            try:
                cand = date(year, mo, d)
            except ValueError:
                return None
            if cand < received_on - timedelta(days=30):
                cand = date(year + 1, mo, d)
            return cand.isoformat()
        yi = int(y)
        if yi < 100:
            yi += 2000
        try:
            return date(yi, mo, d).isoformat()
        except ValueError:
            return None
    m = _RE_LONG.search(p)
    if m and m.group(2) in _MONTHS:
        d, mo = int(m.group(1)), _MONTHS[m.group(2)]
        year = int(m.group(3)) if m.group(3) else received_on.year
        try:
            cand = date(year, mo, d)
        except ValueError:
            return None
        if not m.group(3) and cand < received_on - timedelta(days=30):
            cand = date(year + 1, mo, d)
        return cand.isoformat()
    if "übermorgen" in p or "uebermorgen" in p:
        return (received_on + timedelta(days=2)).isoformat()
    if "morgen" in p:
        return (received_on + timedelta(days=1)).isoformat()
    if "heute" in p:
        return received_on.isoformat()
    m = _RE_DAYS.search(p)
    if m:
        n = int(m.group(1) or m.group(2))
        return (received_on + timedelta(days=n)).isoformat()
    m = _RE_WEEKS.search(p)
    if m:
        n = int(m.group(1) or m.group(2))
        return (received_on + timedelta(weeks=n)).isoformat()
    if "ende der woche" in p or "wochenende" in p:
        delta = (4 - received_on.weekday()) % 7
        return (received_on + timedelta(days=delta)).isoformat()
    if "ende des monats" in p or "monatsende" in p:
        nxt = (received_on.replace(day=28) + timedelta(days=4)).replace(day=1)
        return (nxt - timedelta(days=1)).isoformat()
    if "nächste woche" in p or "naechste woche" in p:
        return (received_on + timedelta(days=(7 - received_on.weekday()) % 7 or 7)).isoformat()
    for word in re.findall(r"[a-zäöü]+", p):
        if word in _WEEKDAYS:
            # ``Fr. Huber`` is the common honorific Frau, not Friday.
            if word == "fr" and re.search(r"\bFr\.\s+[A-ZÄÖÜ]", raw_phrase):
                continue
            target = _WEEKDAYS[word]
            delta = (target - received_on.weekday()) % 7
            if delta == 0 and ("nächst" in p or "naechst" in p or "kommend" in p):
                delta = 7
            return (received_on + timedelta(days=delta)).isoformat()
    return None


def resolve_date(phrase: str | None, received_on: str | date) -> str | None:
    """ISO date for a German phrase, relative to the day the note was received."""
    if not phrase:
        return None
    rec = _to_date(received_on)
    if _dates is not None and hasattr(_dates, "resolve_dates"):
        try:
            out = _dates.resolve_dates(phrase, rec.isoformat())
            if hasattr(out, "iso") and not isinstance(out, (str, dict, list, tuple)):
                out = out.iso if (getattr(out, "miss", None) is None) else None
            if isinstance(out, dict):
                out = out.get("iso") or out.get("date")
            if isinstance(out, (list, tuple)):
                out = out[0] if out else None
            if out:
                return str(out)[:10]
        except Exception:
            pass
    return _local_resolve(phrase, rec)


def weekday_conflict(phrase: str | None, iso: str | None) -> bool:
    """True when the phrase names a weekday that does not match the numeric date (paper typo or misread)."""
    if not phrase or not iso:
        return False
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return False
    names = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonntag": 6}
    for w, n in names.items():
        if re.search(rf"\b{w}\b", phrase.lower()) and _RE_NUMERIC.search(phrase):
            return n != d.weekday()
    return False


# ---------------------------------------------------------------- amounts
_RE_AMOUNT = re.compile(
    r"(?:€\s?(\d{1,4}(?:[.,](?:\d{1,2}|-))?))|(?:(\d{1,4}(?:[.,](?:\d{1,2}|-))?)\s?(?:€|euro|eur\b))",
    re.IGNORECASE,
)


def find_amount(text: str) -> float | None:
    m = _RE_AMOUNT.search(text or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    raw = re.sub(r"[.,]-$", "", raw)
    return float(raw.replace(",", "."))


# ------------------------------------------------------------ source lines
def note_lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _neighbours(line: str, text: str) -> list[str]:
    """The line before and after ``line`` in the note (a sentence often wraps over two printed lines)."""
    lines = note_lines(text)
    out = []
    for i, ln in enumerate(lines):
        if ln == line or line.endswith(ln) or line.startswith(ln):
            if i > 0:
                out.append(lines[i - 1])
            if i + 1 < len(lines):
                out.append(lines[i + 1])
            break
    return out


def _extend_source(line: str, text: str, predicate) -> str | None:
    """Join the neighbouring line when it carries the evidence (date/amount) the model quoted."""
    lines = note_lines(text)
    for i, ln in enumerate(lines):
        if ln == line:
            if i + 1 < len(lines) and predicate(lines[i + 1]):
                return f"{ln} {lines[i + 1]}"
            if i > 0 and predicate(lines[i - 1]):
                return f"{lines[i - 1]} {ln}"
    return None


def best_source_line(claimed: str, text: str) -> tuple[str, float]:
    """Find the note line closest to what the model quoted. Returns (line, similarity)."""
    lines = note_lines(text)
    if not lines:
        return claimed, 0.0
    if not claimed:
        return lines[0], 0.0
    exact = claimed.strip()
    c = exact.lower()
    for ln in lines:
        start = ln.lower().find(c) if c else -1
        if start >= 0:
            return ln[start:start + len(exact)], 1.0
    # Model may have joined two lines; try pairs.
    pairs = [f"{a} {b}" for a, b in zip(lines, lines[1:])]
    best, best_r = lines[0], 0.0
    for cand in lines + pairs:
        r = difflib.SequenceMatcher(None, c, cand.lower()).ratio()
        if r > best_r:
            best, best_r = cand, r
    return best, best_r


def paper_id_for(text: str) -> str:
    return "paper_" + hashlib.sha1((text or "").strip().encode("utf-8")).hexdigest()[:10]


# --------------------------------------------------------------- heuristic
_EVENT_WORDS = (
    "elternabend", "ausflug", "wandertag", "laternenfest", "martinsfest", "sommerfest", "fasching", "fest",
    "feier", "fotograf", "elternsprechtag", "eingewöhnung", "theater", "besuch", "abschlussfest",
)

_SENDER_HEADER = re.compile(
    r"^(?:kindergarten|kindergruppe|hort|volksschule|schule|gemeinde|"
    r"magistrat(?:sabteilung)?|ma\s*\d+|bezirksamt|elternverein|ordination|praxis|dr\.)\b",
    re.IGNORECASE,
)
_SENDER_SENTENCE_WORDS = re.compile(
    r"\b(?:am|bis|findet|geschlossen|bleibt|wegen|bitte|ist|sind|war|wird|werden|"
    r"liebe|unser|unsere|wir)\b",
    re.IGNORECASE,
)


def _heuristic_sender(lines: list[str]) -> str | None:
    """Return a clear institution header, never an arbitrary first sentence."""
    if not lines:
        return None
    candidate = lines[0].strip()
    if len(candidate.split()) > 8 or candidate.endswith((".", "!", "?")):
        return None
    if _SENDER_SENTENCE_WORDS.search(candidate):
        return None
    return candidate if _SENDER_HEADER.match(candidate) else None


def _heuristic_extract(text: str, received_on: date) -> dict[str, Any]:
    lines = note_lines(text)
    low = text.lower()
    actions: list[dict[str, Any]] = []
    title = None
    event_date = None
    for word in _EVENT_WORDS:
        if word in low:
            title = word.capitalize()
            break
    sender = _heuristic_sender(lines)
    sender_type = "kindergarten"
    for st, keys in (("gemeinde", ("gemeinde", "magistrat", "ma ", "bezirksamt", "meldezettel")),
                     ("arzt", ("praxis", "dr.", "ordination", "arzt", "ärztin", "impf")),
                     ("hort", ("hort",)), ("schule", ("volksschule", "schule")),
                     ("elternverein", ("elternverein",))):
        if any(k in low for k in keys) and "kindergarten" not in low:
            sender_type = st
            break
    for i, ln in enumerate(lines):
        ll = ln.lower()
        ctx = " ".join(lines[max(0, i - 1): i + 2]).lower()
        iso = resolve_date(ln, received_on)
        amount = find_amount(ln)
        if "geschlossen" in ll or "schließtag" in ll or "schliesstag" in ll:
            src, when = ln, iso
            if not when:  # the date often sits on the neighbouring line
                for near in lines[max(0, i - 1): i + 2]:
                    when = resolve_date(near, received_on)
                    if when:
                        src = near
                        break
            actions.append(dict(kind="closed", action="Kindergarten geschlossen", deadline_iso=when,
                                amount=None, source_line=src, confidence=0.8 if when else 0.5))
            continue
        if "abgesagt" in ll or "entfällt" in ll or "findet nicht statt" in ll:
            actions.append(dict(kind="cancel", action="Termin abgesagt", deadline_iso=None, amount=None,
                                source_line=ln, confidence=0.8))
            continue
        if re.search(r"\bbis\b", ll) and (iso or "morgen" in ll) and any(k in ctx for k in ("rückmeld", "bekannt", "bescheid", "anmeld", "abgeben", "zurück", "unterschr", "bestätig")):
            actions.append(dict(kind="reply", action="Rückmeldung abgeben", deadline_iso=iso, amount=None,
                                source_line=ln, confidence=0.8 if iso else 0.5))
            continue
        if amount is not None:
            when = iso or resolve_date(ctx, received_on)
            actions.append(dict(kind="pay", action=f"{amount:g} € mitgeben", deadline_iso=when, amount=amount,
                                source_line=ln, confidence=0.8 if when else 0.6))
            continue
        if any(k in ll for k in ("mitbringen", "mitnehmen", "mitgeben", "mitzubringen", "brauchen die kinder")) or \
                re.search(r"\b(bringen|nehmen|geben)\b.*\bmit\b", ll):
            item = re.sub(r"(?i)\b(bitte|bringen|nehmen|geben|sie|ihr\w*|dem|den|das|kind\w*|mit|zu|am|bis|noch|auch)\b", " ", ln)
            item = re.sub(r"\s+", " ", item).strip(" .,:;!")
            actions.append(dict(kind="bring", action=item or ln.rstrip("."), deadline_iso=iso, amount=None,
                                source_line=ln, confidence=0.75))
            continue
        if iso and any(w in ctx for w in _EVENT_WORDS):
            actions.append(dict(kind="attend", action=(title or "Termin"), deadline_iso=iso, amount=None,
                                source_line=ln, confidence=0.8))
            event_date = event_date or iso
    return {"title": title or "Kindergarten", "sender": sender, "sender_type": sender_type,
            "event_date": event_date, "actions": actions}


# ------------------------------------------------------------------- model
_SYSTEM = """You extract actions from a German note that a Kindergarten, Hort, school, Gemeinde/Magistrat, doctor or Elternverein in Austria sent to parents.
Return ONLY a JSON object, no prose:
{"title": short German event title, "sender": institution name or null, "sender_type": one of %s,
 "event_date": "YYYY-MM-DD" or null,
 "actions": [{"kind": one of %s, "action": short German imperative, "deadline_phrase": exact words from the note that state the date or deadline (or ""),
              "deadline_iso": "YYYY-MM-DD" or null, "amount_eur": number or null, "source_line": the exact line of the note this comes from,
              "confidence": 0.0-1.0}]}
Rules: one action per thing the parent must do or know (reply, pay, bring, attend, closed, cancel, info). Always add one "attend" action for the event itself (Elternabend, Ausflug, Fest, Termin) with the event date, even when attendance is implicit. Quote source_line verbatim from the note (join two printed lines with a space when the sentence wraps).
Never invent a date or an amount; if the note does not state it, leave null and lower confidence. The note was received on %s.""" % (
    list(SENDER_TYPES), list(KINDS), "%s")


def _parse_json(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        _LOG.warning("extract_model_invalid_json reason=no_object")
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        _LOG.warning("extract_model_invalid_json reason=json_decode")
        return None
    if not isinstance(parsed, dict):
        _LOG.warning("extract_model_invalid_json reason=wrong_shape")
        return None
    return parsed


def _numeric_status_code(exc: Exception) -> int | None:
    """Read a provider status without rendering the exception or response."""
    sources: tuple[Any, ...] = (exc, getattr(exc, "response", None))
    for source in sources:
        if source is None:
            continue
        try:
            value = getattr(source, "status_code", None)
        except Exception:
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.isdecimal():
            return int(value)
    return None


def _log_model_error(exc: Exception) -> None:
    status_code = _numeric_status_code(exc)
    if status_code is None:
        _LOG.warning("extract_model_error error_class=%s", type(exc).__name__)
    else:
        _LOG.warning(
            "extract_model_error error_class=%s status_code=%d",
            type(exc).__name__,
            status_code,
        )


def _model_extract(text: str, received_on: date, model: Any) -> dict[str, Any] | None:
    from strands import Agent

    agent = Agent(
        model=model,
        system_prompt=_SYSTEM % received_on.isoformat(),
        callback_handler=None,
        name="papelito-extract",
        retry_strategy=None,
    )
    result = agent(f"Note received {received_on.isoformat()}:\n\n{text}")
    return _parse_json(str(result))


# ----------------------------------------------------------------- verify
def _verify(raw: dict[str, Any], text: str, received_on: date, from_model: bool) -> dict[str, Any]:
    out_actions: list[dict[str, Any]] = []
    for a in raw.get("actions", []) or []:
        kind = a.get("kind") if a.get("kind") in KINDS else "info"
        conf = float(a.get("confidence", 0.7) or 0.7)
        conf = max(0.0, min(1.0, conf))
        flags: list[str] = []
        line, sim = best_source_line(str(a.get("source_line") or ""), text)
        if sim < 0.6:
            conf = min(conf, 0.5)
            flags.append("source_line_not_found")
        if kind == "bring" and find_amount(line) is not None:
            kind = "pay"
            flags.append("kind_normalized_from_money")
        claimed_phrase = str(a.get("deadline_phrase") or "").strip()
        phrase = claimed_phrase if claimed_phrase and claimed_phrase.casefold() in line.casefold() else line
        dated_kind = kind in ("reply", "pay", "attend", "closed")
        det = resolve_date(phrase, received_on) or (resolve_date(line, received_on) if dated_kind else None)
        if not det and dated_kind:  # date on the neighbouring printed line: quote both lines as the source
            ext = _extend_source(line, text, lambda ln: resolve_date(ln, received_on) is not None)
            if ext:
                line, det = ext, resolve_date(ext, received_on)
        model_iso = a.get("deadline_iso")
        # A model date is only a proposal. Keep it only when the quoted phrase
        # or verified source line resolves deterministically; otherwise the
        # card must show no date instead of laundering a guess through a gate.
        deadline = det
        if det and model_iso and det != model_iso:
            conf = min(conf, 0.6)
            flags.append("date_mismatch")
            deadline = det
        elif not det and model_iso:
            conf = min(conf, 0.65)
            flags.append("date_unverified")
        if deadline and (weekday_conflict(phrase, deadline) or weekday_conflict(line, deadline)):
            conf = min(conf, 0.7)
            flags.append("weekday_mismatch")
        if kind in ("reply", "pay", "attend") and not deadline:
            conf = min(conf, 0.5)
            flags.append("date_missing")
        amount = a.get("amount_eur", a.get("amount"))
        amount = float(amount) if amount not in (None, "") else None
        det_amount = find_amount(line)
        if det_amount is None and (amount is not None or kind == "pay"):
            ext = _extend_source(line, text, lambda ln: find_amount(ln) is not None)
            if ext:
                line, det_amount = ext, find_amount(ext)
        if amount is not None and det_amount is not None and abs(amount - det_amount) > 0.005:
            conf = min(conf, 0.6)
            flags.append("amount_mismatch")
            amount = det_amount
        elif amount is not None and det_amount is None:
            conf = min(conf, 0.65)
            flags.append("amount_unverified")
        elif amount is None and det_amount is not None and kind == "pay":
            amount = det_amount
        if kind == "pay" and amount is None:
            conf = min(conf, 0.5)
            flags.append("amount_missing")
        out_actions.append({
            "kind": kind,
            "action": str(a.get("action") or line).strip(),
            "deadline_iso": deadline,
            "amount": amount,
            "source_line": line,
            "confidence": round(conf, 2),
            "flags": flags,
            "gate": gate_for(conf),
            "question": question_code(flags) if gate_for(conf) == "ask" else None,
        })
    meta_sender_type = raw.get("sender_type") if raw.get("sender_type") in SENDER_TYPES else "kindergarten"
    proposed_event_date = raw.get("event_date")
    if proposed_event_date and not any(a["kind"] == "attend" for a in out_actions):
        # The event itself must land in the calendar even if the model only listed the chores around it.
        src = next((ln for ln in note_lines(text) if resolve_date(ln, received_on) == proposed_event_date), None)
        if src:
            conf = 0.8 if not weekday_conflict(src, proposed_event_date) else 0.7
            out_actions.insert(0, {
                "kind": "attend", "action": str(raw.get("title") or "Termin"), "deadline_iso": proposed_event_date, "amount": None,
                "source_line": src, "confidence": conf, "flags": ["attend_added_from_event_date"],
                "gate": gate_for(conf), "question": "date" if gate_for(conf) == "ask" else None,
            })
    event_date = next(
        (a["deadline_iso"] for a in out_actions if a["kind"] == "attend" and a["deadline_iso"]),
        None,
    )
    return {
        "paper_id": paper_id_for(text),
        "title": (raw.get("title") or "Kindergarten").strip(),
        "sender": raw.get("sender"),
        "sender_type": meta_sender_type,
        "event_date": event_date,
        "received_on": received_on.isoformat(),
        "actions": out_actions,
        "extractor": "model" if from_model else "heuristic",
    }


def gate_for(confidence: float) -> str:
    if confidence >= ASK_BELOW:
        return "ok"
    if confidence >= DROP_BELOW:
        return "ask"
    return "drop"


def question_code(flags: list[str]) -> str:
    for f in flags:
        if f.startswith("date") or f.startswith("weekday"):
            return "date"
        if f.startswith("amount"):
            return "amount"
    return "line"


def extract(text: str, received_on: str | date, model: Any = None) -> dict[str, Any]:
    """Full extraction: meta (title, sender, sender_type, event_date) plus verified actions."""
    rec = _to_date(received_on)
    raw = None
    from_model = False
    if model is not None:
        try:
            raw = _model_extract(text, rec, model)
            from_model = raw is not None
        except Exception as exc:
            _log_model_error(exc)
            raw = None
    if raw is None:
        raw = _heuristic_extract(text, rec)
    return _verify(raw, text, rec, from_model)


def extract_actions(text: str, received_on: str | date, model: Any = None) -> list[dict[str, Any]]:
    """[{action, kind, deadline_iso, amount, source_line, confidence, gate, question}]"""
    return extract(text, received_on, model)["actions"]


def artifact_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only actions that passed the confidence gate (or were confirmed by the human)."""
    return [a for a in actions if a.get("gate") == "ok" or a.get("confirmed")]
