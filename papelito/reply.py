"""draft_reply: the finished German reply, Sie-form, register by sender type.

Kindergarten, Hort and Elternverein get a warm but formal note; Gemeinde,
Magistrat and other offices get letter form with a subject line; a doctor's
practice gets a short confirmation. One line per required answer. Names
come from the household profile, never from the note. Nothing is sent.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_PROFILE: dict[str, Any] = {
    "parent_name": "Erziehungsberechtigte/r",
    "household": "",
    "child_name": "unser Kind",
    "children": [],
    "child_birthdate": None,
    "kindergarten": None,
    "group": None,
    "address": None,
    "language": "en",
    "signature": None,
    "answers": {"attend": True, "persons": 1},
}


def load_profile(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """profile.yaml (real, ignored by git) or profile.example.yaml or defaults. Tolerant to key names."""
    root = Path(__file__).resolve().parent.parent
    candidates = [path, os.environ.get("PAPELITO_PROFILE"), "profile.yaml", root / "profile.yaml",
                  "profile.example.yaml", root / "profile.example.yaml"]
    data: dict[str, Any] = {}
    for c in candidates:
        if c and Path(c).exists():
            data = _read_yaml(Path(c))
            break
    if not isinstance(data, dict):
        data = {}
    # profile.example.yaml nests names: {parent, household}; flatten.
    name_values = data.get("names")
    if isinstance(name_values, dict):
        for k, v in name_values.items():
            data.setdefault(k, v)
    prof = dict(DEFAULT_PROFILE)
    prof["children"] = []
    prof["answers"] = dict(DEFAULT_PROFILE["answers"])
    alias = {
        "parent_name": ("parent_name", "parent", "name", "reader_name", "mother", "father"),
        "child_name": ("child_name", "child", "kid"),
        "child_birthdate": ("child_birthdate", "birthdate", "child_dob"),
        "kindergarten": ("kindergarten", "institution", "kita_name"),
        "group": ("group", "gruppe", "child_group"),
        "address": ("address", "address_line", "adresse"),
        "language": ("language", "reader_language", "lang"),
        "signature": ("signature", "reply_signature", "sign"),
    }
    for key, aliases in alias.items():
        for n in aliases:
            v = data.get(n)
            if isinstance(v, dict) and key in ("child_name", "parent_name"):
                v = v.get("name")
            if v is not None and v != "":
                prof[key] = v
                break
    prof["household"] = str(data.get("household") or data.get("family") or "")
    prof["children"] = _normalise_children(data)
    if prof["children"]:
        first = prof["children"][0]
        prof["child_name"] = first["name"]
        if not prof.get("kindergarten") and first.get("kindergarten"):
            prof["kindergarten"] = first["kindergarten"]
    if isinstance(data.get("answers"), dict):
        prof["answers"] = {**DEFAULT_PROFILE["answers"], **data["answers"]}
    prof["language"] = _lang_code(prof.get("language"))
    return prof


def save_profile(data: dict[str, Any], path: str | os.PathLike | None = None) -> Path:
    """Write the non-secret household profile to ``profile.yaml``."""
    if not isinstance(data, dict):
        raise TypeError("profile data must be a mapping")
    target = Path(path or os.environ.get("PAPELITO_PROFILE") or "profile.yaml").expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_dump_profile(_profile_document(data)), encoding="utf-8")
    return target


def _normalise_children(data: dict[str, Any]) -> list[dict[str, str]]:
    raw_children = data.get("children")
    if isinstance(raw_children, list):
        entries: list[Any] = raw_children
    else:
        legacy = data.get("child_name")
        if legacy is None:
            legacy = data.get("child")
        if legacy is None:
            legacy = data.get("kid")
        entries = [legacy] if legacy is not None else []

    fallback_kindergarten = data.get("kindergarten") or data.get("institution") or data.get("kita_name") or ""
    children: list[dict[str, str]] = []
    used: set[str] = set()
    for index, entry in enumerate(entries):
        if isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("child_name") or "").strip()
            kindergarten = str(entry.get("kindergarten") or fallback_kindergarten or "").strip()
            child_id = str(entry.get("id") or "").strip()
        else:
            name = str(entry or "").strip()
            kindergarten = str(fallback_kindergarten).strip()
            child_id = ""
        if not name:
            continue
        base_id = child_id or _child_slug(name) or f"child-{index + 1}"
        child_id = base_id
        suffix = 2
        while child_id in used:
            child_id = f"{base_id}-{suffix}"
            suffix += 1
        used.add(child_id)
        children.append({"id": child_id, "name": name, "kindergarten": kindergarten})
    return children


def _child_slug(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def _profile_document(data: dict[str, Any]) -> dict[str, Any]:
    names = data.get("names") if isinstance(data.get("names"), dict) else {}
    parent = data.get("parent") or data.get("parent_name") or names.get("parent") or ""
    household = data.get("household") or data.get("family") or names.get("household") or ""
    language = _lang_code(data.get("language") or data.get("reader_language") or "en")
    signature = data.get("signature") or data.get("reply_signature") or ""
    document: dict[str, Any] = {
        "names": {"parent": str(parent).strip(), "household": str(household).strip()},
        "children": _normalise_children(data),
        "reader_language": {"en": "English", "de": "German"}[language],
        "reply_signature": str(signature).strip(),
    }
    for output_key, input_keys in {
        "address_line": ("address_line", "address"),
        "group": ("group", "gruppe", "child_group"),
        "child_birthdate": ("child_birthdate", "birthdate", "child_dob"),
    }.items():
        value = next((data.get(key) for key in input_keys if data.get(key) not in (None, "")), None)
        if value is not None:
            document[output_key] = str(value)
    answers = data.get("answers")
    if isinstance(answers, dict):
        safe_answers: dict[str, Any] = {}
        if isinstance(answers.get("attend"), bool):
            safe_answers["attend"] = answers["attend"]
        if isinstance(answers.get("persons"), int) and not isinstance(answers["persons"], bool):
            safe_answers["persons"] = answers["persons"]
        if safe_answers and safe_answers != {"attend": True, "persons": 1}:
            document["answers"] = safe_answers
    return document


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _dump_profile(document: dict[str, Any]) -> str:
    lines = [
        "names:",
        f"  parent: {_yaml_scalar(document['names']['parent'])}",
        f"  household: {_yaml_scalar(document['names']['household'])}",
        "children:",
    ]
    children = document.get("children") or []
    if children:
        for child in children:
            lines.extend([
                f"  - id: {_yaml_scalar(child['id'])}",
                f"    name: {_yaml_scalar(child['name'])}",
                f"    kindergarten: {_yaml_scalar(child.get('kindergarten') or '')}",
            ])
    else:
        lines[-1] = "children: []"
    lines.extend([
        f"reader_language: {_yaml_scalar(document['reader_language'])}",
        f"reply_signature: {_yaml_scalar(document['reply_signature'])}",
    ])
    for key in ("address_line", "group", "child_birthdate"):
        if key in document:
            lines.append(f"{key}: {_yaml_scalar(document[key])}")
    if document.get("answers"):
        lines.append("answers:")
        for key, value in document["answers"].items():
            lines.append(f"  {key}: {_yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _lang_code(value: Any) -> str:
    v = str(value or "en").strip().lower()
    return "de" if v in {"de", "de-at", "german", "deutsch"} else "en"


def _read_yaml(path: Path) -> dict[str, Any]:
    """PyYAML when installed; otherwise a small reader for profile YAML."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    except Exception:
        return {}
    out: dict[str, Any] = {}
    parent: str | None = None
    list_item: dict[str, Any] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if indent == 0:
            key, _, val = stripped.partition(":")
            val = _yaml_value(val.strip())
            if val == "":
                parent = key
                out[key] = [] if key == "children" else {}
            else:
                parent = None
                out[key] = val
            list_item = None
        elif parent and stripped.startswith("-") and isinstance(out.get(parent), list):
            item: dict[str, Any] = {}
            out[parent].append(item)
            list_item = item
            key, _, val = stripped[1:].strip().partition(":")
            list_item[key] = _yaml_value(val.strip())
        elif parent and list_item is not None and isinstance(out.get(parent), list):
            key, _, val = stripped.partition(":")
            list_item[key] = _yaml_value(val.strip())
        elif parent and isinstance(out.get(parent), dict):
            key, _, val = stripped.partition(":")
            out[parent][key] = _yaml_value(val.strip())
    return out


def _yaml_value(value: str) -> Any:
    if value in ("", "null", "~"):
        return None if value else ""
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in ("true", "false"):
        return value == "true"
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def _de_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    wd = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][d.weekday()]
    return f"{wd}, {d.day:02d}.{d.month:02d}.{d.year}"


def _amount(a: float | None) -> str:
    return "" if a is None else (f"{a:.2f}".replace(".", ",").replace(",00", "") + " €")


def salutation(case: dict[str, Any], profile: dict[str, Any]) -> tuple[str, str, str]:
    """(register, salutation line, closing line)."""
    st = (case.get("sender_type") or "kindergarten").lower()
    contact = case.get("contact")
    if contact and re.match(r"(Frau|Herr) ", contact):
        greet = f"Sehr geehrte {contact}," if contact.startswith("Frau") else f"Sehr geehrter {contact},"
    else:
        greet = None
    if st in ("kindergarten", "hort", "elternverein"):
        name = case.get("sender") or profile.get("kindergarten")
        where = {"kindergarten": "Kindergarten-Team", "hort": "Hort-Team", "elternverein": "Elternverein"}[st]
        return "warm", greet or (f"Liebes {where}" + (f" des {name}" if name and st != "elternverein" else "") + ","), "Mit freundlichen Grüßen"
    if st in ("gemeinde", "amt"):
        return "amt", greet or "Sehr geehrte Damen und Herren,", "Mit freundlichen Grüßen"
    if st == "arzt":
        return "arzt", greet or "Sehr geehrtes Praxisteam,", "Mit freundlichen Grüßen"
    if st == "schule":
        return "schule", greet or "Sehr geehrtes Lehrerteam,", "Mit freundlichen Grüßen"
    return "amt", greet or "Sehr geehrte Damen und Herren,", "Mit freundlichen Grüßen"


def _answer_lines(case: dict[str, Any], profile: dict[str, Any], answers: dict[str, Any]) -> list[str]:
    child = profile.get("child_name") or "unser Kind"
    title = case.get("title") or "Termin"
    active = [a for a in case.get("actions", []) if a.get("status", "active") == "active" and a.get("gate", "ok") == "ok"]
    attend = next((a for a in active if a["kind"] == "attend"), None)
    lines: list[str] = []
    for a in active:
        k = a["kind"]
        ans = answers.get(a.get("id") or "", {}) if isinstance(answers.get(a.get("id") or ""), dict) else {}
        will_attend = ans.get("attend", answers.get("attend", True))
        persons = ans.get("persons", answers.get("persons", 1))
        when = _de_date((attend or {}).get("deadline_iso") or a.get("deadline_iso"))
        if k == "reply":
            if will_attend:
                who = f"{persons} Person" if persons == 1 else f"{persons} Personen"
                lines.append(f"Hiermit bestätige ich unsere Teilnahme am {title}" + (f" am {when}" if when else "") + f" ({who}).")
            else:
                lines.append(f"Leider können wir am {title}" + (f" am {when}" if when else "") + " nicht teilnehmen.")
        elif k == "pay":
            lines.append(f"Den Betrag von {_amount(a.get('amount'))} geben wir {child}" + (f" bis {_de_date(a.get('deadline_iso'))}" if a.get("deadline_iso") else "") + " in bar mit.")
        elif k == "bring":
            item = (a.get("action") or "").strip().rstrip(".")
            item = re.sub(r"^(bitte\s+)?", "", item, flags=re.I)
            lines.append(f"{item[:1].upper()}{item[1:]} bringen wir mit." if item else "")
        elif k == "closed" and a.get("deadline_iso"):
            lines.append(f"Den Schließtag am {_de_date(a['deadline_iso'])} haben wir vorgemerkt.")
        elif k == "attend" and not any(x["kind"] == "reply" for x in active):
            lines.append(f"Wir haben den Termin am {when} vorgemerkt" + (" und nehmen teil." if will_attend else ", können aber leider nicht teilnehmen."))
    return [ln for ln in lines if ln]


def draft_reply(case: dict[str, Any], profile: dict[str, Any] | None = None, answers: dict[str, Any] | None = None,
                model: Any = None) -> str:
    """German reply text. ``answers`` overrides profile defaults (attend, persons, per-action dicts)."""
    profile = profile or load_profile()
    answers = {**(profile.get("answers") or {}), **(answers or {})}
    register, greet, close = salutation(case, profile)
    child = profile.get("child_name") or "unser Kind"
    group = profile.get("group")
    parent = profile.get("parent_name") or ""
    sig = profile.get("signature") or parent
    body = _answer_lines(case, profile, answers)
    if not body:
        body = [f"vielen Dank für Ihre Information zum {case.get('title') or 'Termin'}; wir haben sie zur Kenntnis genommen."]
    parts: list[str] = []
    if register == "amt":
        ref = f"Betreff: {case.get('title') or 'Ihr Schreiben'}"
        if profile.get("child_birthdate"):
            ref += f" – {child}, geb. {_de_date(str(profile['child_birthdate']))}"
        parts += [ref, ""]
    parts.append(greet)
    parts.append("")
    if register == "warm":
        intro = f"vielen Dank für Ihre Nachricht" + (f" zum {case['title']}" if case.get("title") else "") + "."
        parts.append(intro)
    elif register == "arzt":
        parts.append(f"vielen Dank für Ihre Nachricht bezüglich {child}.")
    else:
        parts.append(f"vielen Dank für Ihr Schreiben" + (f" vom {_de_date(case['papers'][-1]['received_on'])}" if case.get("papers") else "") + ".")
    parts += body
    parts.append("")
    parts.append(close)
    parts.append(sig)
    if register == "warm" and child != "unser Kind":
        parts.append(f"(Eltern von {child}" + (f", Gruppe {group}" if group else "") + ")")
    if register == "amt" and profile.get("address"):
        parts.append(str(profile["address"]))
    text = "\n".join(parts)
    if model is not None:
        polished = _polish(text, model)
        if polished:
            return polished
    return text


def _polish(text: str, model: Any) -> str | None:
    """Optional fluency pass. Rejects the result if any number, name or the Sie-form went missing."""
    from strands import Agent

    agent = Agent(model=model, callback_handler=None, name="papelito-reply",
                  system_prompt="Korrigiere Grammatik und Fluss dieses deutschen Antwortschreibens. Sie-Form beibehalten. "
                                "Keine neuen Fakten, keine Zahlen, Daten, Beträge oder Namen ändern oder weglassen. "
                                "Gib nur den fertigen Text zurück.")
    try:
        out = str(agent(text)).strip()
    except Exception:
        return None
    if set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", out)):
        return None
    if re.search(r"\b(du|dein|deine|euch|euer)\b", out, re.I):
        return None
    caps = {w for w in re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]{2,}\b", text)}
    if len(caps - set(re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]{2,}\b", out))) > 2:
        return None
    return out
