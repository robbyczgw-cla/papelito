"""explain_in: the card in the reader's language (English by default).

Four columns: what / do / by when / done-for-you. The fourth column is the
product: it lists what the agent already did (calendar file, German reply,
reminder, case saved). Every deadline keeps its German source line.

Templates by action kind are deterministic. A text model may translate the
free German action wording; dates and amounts are checked to survive the
translation, otherwise the German wording is kept.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

LABELS = {
    "en": ("what", "do", "by when", "done for you"),
    "de": ("was", "tun", "bis wann", "erledigt"),
}
_WD = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
}
KIND_WHAT = {
    "en": {"reply": "reply requested", "pay": "money", "bring": "bring something", "attend": "appointment",
           "closed": "Kindergarten closed", "cancel": "cancelled", "info": "information"},
    "de": {"reply": "Rückmeldung", "pay": "Geld", "bring": "Mitbringen", "attend": "Termin",
           "closed": "geschlossen", "cancel": "abgesagt", "info": "Information"},
}
DONE_LABELS = {
    "en": {"ics": "calendar (.ics)", "reply": "German reply drafted", "reminder": "reminder 2 days before",
           "saved": "saved to case", "amended": "case updated"},
    "de": {"ics": "Kalender (.ics)", "reply": "Antwort (DE) entworfen", "reminder": "Erinnerung 2 Tage vorher",
           "saved": "im Akt gespeichert", "amended": "Akt aktualisiert"},
}
QUESTIONS = {
    "en": {"date": "I could not read the date on this line. Which date is it? (dd.mm.yyyy, or Enter if unsure)",
           "amount": "I could not read the amount on this line. How many euros? (or Enter if unsure)",
           "line": "I could not read this line. What does it say? (or Enter if unsure)"},
    "de": {"date": "Das Datum in dieser Zeile ist unleserlich. Welches Datum? (tt.mm.jjjj, oder Enter)",
           "amount": "Der Betrag in dieser Zeile ist unleserlich. Wie viel Euro? (oder Enter)",
           "line": "Diese Zeile ist unleserlich. Was steht dort? (oder Enter)"},
}
UNREADABLE = {"en": "unreadable, no artifact", "de": "unleserlich, kein Artefakt"}


def _lang(language: str | None) -> str:
    lang = (language or "en").lower()[:2]
    return lang if lang in LABELS else "en"


def format_date(iso: str | None, language: str = "en") -> str:
    if not iso:
        return {"en": "no date", "de": "kein Datum"}[_lang(language)]
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    wd = _WD[_lang(language)][d.weekday()]
    return f"{wd} {d.day:02d}.{d.month:02d}.{d.year}" if _lang(language) != "en" else f"{wd} {d.day} {d.strftime('%b')} {d.year}"


def _amount(a: float | None) -> str:
    if a is None:
        return ""
    return f"{a:.2f} €".replace(".00 €", " €").replace(".", ",")


def cite(german: str, language: str, translated: str | None = None) -> str:
    """Reader-language cell for a German sentence.

    A translation wins. Without one, a non-German card quotes the German.
    Raw German never lands unmarked in the do-column.
    """
    lang = _lang(language)
    if translated and translated.strip():
        return translated.strip()
    text = (german or "").strip()
    if not text:
        return ""
    if lang == "de":
        return text
    left, right = "“", "”"
    if text.startswith(left) and text.endswith(right):
        return text
    return f"{left}{text}{right}"


def action_line(action: dict[str, Any], language: str, title: str = "", translated: str | None = None) -> str:
    """The 'do' column for one action."""
    lang = _lang(language)
    kind = action.get("kind", "info")
    amt = _amount(action.get("amount"))
    raw = action.get("action") or action.get("source_line") or ""
    quoted = cite(raw, lang, translated)
    if lang == "en":
        return {
            "reply": f"Reply to the Kindergarten (Rückmeldung){': ' + quoted if translated else ''}",
            "pay": f"Hand in {amt} in cash{' · ' + quoted if translated else ''}",
            "bring": f"Bring: {quoted}",
            "attend": f"Go: {cite(title or raw, lang, translated)}",
            "closed": "Kindergarten closed, arrange care",
            "cancel": f"Cancelled: {quoted}",
            "info": quoted,
        }[kind]
    return {
        "reply": "Rückmeldung abgeben" + (f": {quoted}" if translated else ""),
        "pay": f"{amt} bar mitgeben",
        "bring": f"Mitbringen: {quoted}",
        "attend": f"Hingehen: {title or raw}",
        "closed": "Kindergarten geschlossen, Betreuung organisieren",
        "cancel": f"Abgesagt: {quoted}",
        "info": quoted,
    }[kind]


def translate_actions(actions: list[dict[str, Any]], language: str, model: Any) -> dict[str, str]:
    """Translate the German action wording with the text model; keep digits intact or drop the translation."""
    lang = _lang(language)
    if lang == "de" or model is None or not actions:
        return {}
    from strands import Agent

    items = {str(i): a.get("action") or a.get("source_line") for i, a in enumerate(actions)}
    target = "English"
    agent = Agent(model=model, callback_handler=None, name="papelito-explain",
                  system_prompt=f"Translate short German Kindergarten instructions into {target}. Keep every number, date, "
                                "time, € amount and proper name exactly as written. Keep the words Kindergarten, Hort, "
                                "Elternabend, Ausflug untranslated (add a 2-3 word gloss in parentheses on first use). "
                                "Return ONLY a JSON object mapping the same keys to the translations.")
    try:
        raw = str(agent(json.dumps(items, ensure_ascii=False)))
        m = re.search(r"\{.*\}", raw, re.S)
        out = json.loads(m.group(0)) if m else {}
    except Exception:
        return {}
    ok: dict[str, str] = {}
    for k, v in out.items():
        if k in items and isinstance(v, str) and set(re.findall(r"\d+", items[k])) <= set(re.findall(r"\d+", v)):
            ok[k] = v.strip()
    return ok


def done_marks(action: dict[str, Any], done: dict[str, bool] | None, language: str) -> list[str]:
    """What the agent did for this row: '✓ calendar (.ics)' etc. Pending items get '·'."""
    lang = _lang(language)
    done = done or {}
    labels = DONE_LABELS[lang]
    wanted: list[str] = []
    if action.get("kind") in ("attend", "closed", "pay", "reply", "bring") and action.get("deadline_iso"):
        wanted.append("ics")
    if action.get("kind") == "reply":
        wanted.append("reply")
    if action.get("deadline_iso") and action.get("kind") in ("reply", "pay", "bring", "attend"):
        wanted.append("reminder")
    if not wanted:
        wanted.append("saved")
    return [("✓ " if done.get(k) else "· ") + labels[k] for k in wanted]


def explain_in(language: str, case: dict[str, Any], model: Any = None, done: dict[str, bool] | None = None,
               questions: bool = True) -> dict[str, Any]:
    """Card for ``case`` in ``language``. Returns a dict with rows and a rendered ``text``."""
    lang = _lang(language)
    title = case.get("title") or "Kindergarten"
    actions = case.get("actions", [])
    translated = translate_actions(actions, lang, model)
    rows = []
    for i, a in _ordered(actions):
        status = a.get("status", "active")
        gate = a.get("gate") or {"pending": "ask", "dropped": "drop"}.get(status, "ok")
        conf = float(a.get("confidence", 1.0))
        what = KIND_WHAT[lang].get(a.get("kind", "info"), "")
        if a.get("kind") == "attend":
            what = title
        row = {
            "id": a.get("id"),
            "kind": a.get("kind"),
            "what": what,
            "do": action_line(a, lang, title, translated.get(str(i))),
            "by_when": format_date(a.get("deadline_iso"), lang),
            "deadline_iso": a.get("deadline_iso"),
            "amount": a.get("amount"),
            "source_line": a.get("source_line", ""),
            "confidence": conf,
            "status": status,
            "gate": gate,
            "question": QUESTIONS[lang][a["question"] if a.get("question") in QUESTIONS[lang] else "line"] if (gate == "ask" and questions) else None,
            "done": [] if status == "superseded" or gate != "ok" else done_marks(a, done, lang),
        }
        if gate == "drop":
            row["done"] = [UNREADABLE[lang]]
        elif gate == "ask" and not a.get("confirmed"):
            row["done"] = ["?"]
        rows.append(row)
    sender = case.get("sender")
    header = {
        "en": f"{title}" + (f" · from {sender}" if sender else "") + (f" · {format_date(case.get('event_date'), lang)}" if case.get("event_date") else ""),
        "de": f"{title}" + (f" · von {sender}" if sender else "") + (f" · {format_date(case.get('event_date'), lang)}" if case.get("event_date") else ""),
    }[lang]
    card = {"language": lang, "case_id": case.get("id"), "title": title, "header": header, "labels": LABELS[lang], "rows": rows}
    card["text"] = render_card(card)
    return card


def _ordered(actions: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """Active rows in creation order, each followed by the row it replaced; leftover superseded rows last."""
    indexed = list(enumerate(actions))
    by_id = {a.get("id"): (i, a) for i, a in indexed if a.get("id")}
    out: list[tuple[int, dict[str, Any]]] = []
    placed: set[int] = set()
    for i, a in indexed:
        if a.get("status", "active") == "superseded":
            continue
        out.append((i, a))
        placed.add(i)
        for j, old in indexed:
            if old.get("status") == "superseded" and old.get("superseded_by") and old["superseded_by"] == a.get("id") and j not in placed:
                out.append((j, old))
                placed.add(j)
    out += [(i, a) for i, a in indexed if i not in placed]
    return out


# ------------------------------------------------------------ rendering
_STRIKE = "\x1b[9m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"
_RESET = "\x1b[0m"


def _wrap(s: str, width: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def render_card(card: dict[str, Any], widths: tuple[int, int, int, int] = (18, 34, 18, 28), color: bool = False) -> str:
    """Plain-text four-column card. Superseded rows are struck through (~~ ~~ or ANSI)."""
    labels = card["labels"]
    out = [card.get("header", "")]
    out.append("  ".join(l.ljust(w) for l, w in zip(labels, widths)))
    out.append("  ".join("-" * w for w in widths))
    for r in card["rows"]:
        cells = [r["what"], r["do"], r["by_when"], "\n".join(r["done"])]
        cols = [_wrap(c, w) if "\n" not in c else sum((_wrap(x, w) for x in c.split("\n")), []) for c, w in zip(cells, widths)]
        height = max(len(c) for c in cols)
        for i in range(height):
            line = "  ".join((c[i] if i < len(c) else "").ljust(w) for c, w in zip(cols, widths))
            if r["status"] == "superseded":
                line = f"{_STRIKE}{_DIM}{line}{_RESET}" if color else "~~" + line.rstrip() + "~~"
            out.append(line)
        src = r.get("source_line")
        if src:
            tag = {"en": "source", "de": "Quelle"}[card["language"]]
            conf = f" · {int(r['confidence'] * 100)}%"
            s = f"    {tag}: „{src}“{conf}"
            out.append(f"{_DIM}{s}{_RESET}" if color else s)
        if r.get("question"):
            out.append(f"    ? {r['question']}")
    return "\n".join(out)


def reminder_line(case: dict[str, Any], language: str, today: str | date) -> str | None:
    """One reader-language line for the watchdog."""
    lang = _lang(language)
    today = today if isinstance(today, date) else date.fromisoformat(str(today)[:10])
    active = [a for a in case.get("actions", []) if a.get("status") == "active" and a.get("deadline_iso")]
    if not active:
        return None
    a = min(active, key=lambda x: x["deadline_iso"])
    d = date.fromisoformat(a["deadline_iso"])
    delta = (d - today).days
    when = {
        "en": {0: "Today", 1: "Tomorrow", 2: "Day after tomorrow"}.get(delta, f"In {delta} days" if delta > 0 else f"{-delta} days ago"),
        "de": {0: "Heute", 1: "Morgen", 2: "Übermorgen"}.get(delta, f"In {delta} Tagen" if delta > 0 else f"Vor {-delta} Tagen"),
    }[lang]
    what = action_line(a, lang, case.get("title") or "")
    sender = case.get("sender") or ""
    return f"{when}: {what}" + (f", {sender}" if sender else "") + "."
