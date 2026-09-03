"""Static Austrian Kindergarten / family-paper glossary.

``glossary_at(term)`` looks up cited entries. Kita is not the Austrian
Kindergarten word. MA is a Vienna Magistratsabteilung; Gemeinde is the
municipality. Meldezettel is the real Austrian registration form.
"""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_UMLAUT = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "à": "a",
        "è": "e",
        "ò": "o",
        "ñ": "n",
    }
)

_DATA_ENV = "PAPELITO_GLOSSARY"


def _data_path() -> Path:
    override = os.environ.get(_DATA_ENV)
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "glossary.yaml"


def _fold(text: str) -> str:
    lowered = text.strip().lower().translate(_UMLAUT)
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _fold(text)).strip()


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _fold(text))


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            ins = prev[j] + 1
            delete = curr[j - 1] + 1
            sub = prev[j - 1] + (ca != cb)
            curr.append(min(ins, delete, sub))
        prev = curr
    return prev[-1]


def _max_edit(length: int) -> int:
    if length <= 3:
        return 0
    if length <= 6:
        return 1
    return 2


@lru_cache(maxsize=1)
def _load_entries() -> tuple[dict[str, Any], ...]:
    path = _data_path()
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    raw = payload.get("terms") if isinstance(payload, dict) else None
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"glossary file has no terms: {path}")
    entries: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("term"):
            continue
        citations = []
        for cite in item.get("citations") or []:
            if not isinstance(cite, dict):
                continue
            name = str(cite.get("name") or "").strip()
            url = str(cite.get("url") or "").strip()
            if name:
                citations.append({"name": name, "url": url})
        aliases = [
            str(alias).strip()
            for alias in (item.get("aliases") or [])
            if str(alias).strip()
        ]
        entries.append(
            {
                "term": str(item["term"]).strip(),
                "aliases": aliases,
                "en": str(item.get("en") or "").strip(),
                "explanation": " ".join(str(item.get("explanation") or "").split()),
                "see_also": [
                    str(rel).strip()
                    for rel in (item.get("see_also") or [])
                    if str(rel).strip()
                ],
                "citations": citations,
            }
        )
    return tuple(entries)


def _score(query: str, entry: dict[str, Any]) -> tuple[float, str]:
    q_tokens = _tokens(query)
    q_compact = _compact(query)
    if not q_compact:
        return 0.0, "none"

    term_tokens = _tokens(entry["term"])
    term_compact = _compact(entry["term"])
    if q_tokens == term_tokens or q_compact == term_compact:
        return 1.0, "exact"

    alias_tokens = {_tokens(alias) for alias in entry["aliases"]}
    alias_compact = {_compact(alias) for alias in entry["aliases"]}
    if q_tokens in alias_tokens or q_compact in alias_compact:
        return 0.98, "alias"

    best = 0.0
    how = "none"
    names = [entry["term"], *entry["aliases"]]
    for name in names:
        n_tokens = _tokens(name)
        n_compact = _compact(name)
        if not n_compact:
            continue
        if q_compact == n_compact:
            return 0.96, "alias"
        if len(q_compact) >= 5 and (
            q_compact in n_compact or n_compact in q_compact
        ):
            ratio = min(len(q_compact), len(n_compact)) / max(
                len(q_compact), len(n_compact)
            )
            score = 0.72 + 0.18 * ratio
            if score > best:
                best, how = score, "partial"
        if len(q_tokens) >= 5 and q_tokens in n_tokens:
            if 0.85 > best:
                best, how = 0.85, "partial"
        limit = _max_edit(min(len(q_compact), len(n_compact)))
        if limit and abs(len(q_compact) - len(n_compact)) <= limit:
            dist = _levenshtein(q_compact, n_compact)
            if dist <= limit:
                score = 0.9 - 0.12 * dist
                if score > best:
                    best, how = score, "fuzzy"
    return best, how


def _format_entry(
    query: str,
    entry: dict[str, Any],
    *,
    match: str,
    score: float,
) -> dict[str, Any]:
    return {
        "query": query,
        "found": True,
        "term": entry["term"],
        "en": entry["en"],
        "explanation": entry["explanation"],
        "see_also": list(entry["see_also"]),
        "citations": [dict(cite) for cite in entry["citations"]],
        "match": match,
        "score": round(score, 3),
    }


def _unknown(query: str, suggestions: list[str]) -> dict[str, Any]:
    hint = ", ".join(suggestions) if suggestions else "none"
    return {
        "query": query,
        "found": False,
        "term": None,
        "en": None,
        "explanation": (
            "unverified: no glossary entry for this term. "
            f"Suggestions: {hint}."
        ),
        "see_also": [],
        "citations": [],
        "match": "none",
        "score": 0.0,
        "suggestions": suggestions,
    }


def glossary_at(term: str) -> dict[str, Any]:
    """Look up an Austrian Kindergarten / family-paper term.

    Matches umlauts (Rückmeldung / Rueckmeldung) and common misspellings
    (Kindergarden, Schliesstage). Returns citations when the entry has them.
    Unknown terms come back as found=False with explanation starting
    ``unverified``.
    """
    query = "" if term is None else str(term).strip()
    if not query:
        return _unknown(query, [])

    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for entry in _load_entries():
        score, how = _score(query, entry)
        if score > 0:
            ranked.append((score, how, entry))
    ranked.sort(key=lambda row: (-row[0], row[2]["term"]))

    if ranked and ranked[0][0] >= 0.72:
        score, how, entry = ranked[0]
        return _format_entry(query, entry, match=how, score=score)

    suggestions = [row[2]["term"] for row in ranked[:5]]
    if not suggestions:
        compact = _compact(query)
        for entry in _load_entries():
            if compact and compact[:4] in _compact(entry["term"]):
                suggestions.append(entry["term"])
            if len(suggestions) >= 5:
                break
    return _unknown(query, suggestions)


def list_terms() -> list[str]:
    """Canonical terms in file order."""
    return [entry["term"] for entry in _load_entries()]
