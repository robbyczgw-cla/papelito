"""papelito CLI.

    papelito add photo.jpg --received 2026-09-03 [--lang en] [--text note.txt] [--direct] [--yes]
    papelito list | show CASE | card CASE | reply CASE | done CASE | delete CASE | watch

``add`` prints the card as four columns: what / do / by when / done-for-you.
The fourth column fills with checkmarks as the tools run. A low-confidence
date or amount shows the source crop and asks one question; unanswered, the
item gets no artifact.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from papelito import agent as A
from papelito import explain as E
from papelito.reply import load_profile
from papelito.store import Store, get_store

TTY = sys.stdout.isatty()
ARTIFACT_TOOLS = ("save_case", "explain_in", "write_ics", "draft_reply")


# --------------------------------------------------------------- progress
class LiveCard:
    """Renders the card and, on a terminal, redraws it in place as artifacts appear."""

    def __init__(self, store: Store, lang: str, color: bool):
        self.store, self.lang, self.color = store, lang, color
        self.case_id: str | None = None
        self.done: dict[str, bool] = {}
        self._lines = 0

    def card(self) -> str | None:
        if not self.case_id:
            return None
        case = self.store.get_case(self.case_id)
        if not case:
            return None
        done = {a["kind"]: True for a in case["artifacts"] if a["status"] == "active"}
        done.update(self.done)
        done["saved"] = True
        done["reminder"] = done.get("ics", False)
        card = E.explain_in(self.lang, case, model=None, done=done, questions=False)
        return E.render_card(card, color=self.color)

    def redraw(self) -> None:
        """Live card: only on a terminal. Piped output gets the progress lines and one final card."""
        if not TTY:
            return
        text = self.card()
        if text is None:
            return
        if self._lines:
            sys.stdout.write(f"\x1b[{self._lines}F\x1b[J")
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
        self._lines = text.count("\n") + 1


class ToolTrace:
    """Strands hook provider: prints each tool as it fires and updates the live card."""

    def __init__(self, live: LiveCard | None, quiet: bool = False):
        self.live, self.quiet = live, quiet
        self._t0: dict[str, float] = {}
        self.seen: list[str] = []

    def register_hooks(self, registry, **kwargs) -> None:
        from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent

        registry.add_callback(BeforeToolCallEvent, self.before)
        registry.add_callback(AfterToolCallEvent, self.after)

    def before(self, event) -> None:
        self._t0[event.tool_use["toolUseId"]] = time.time()

    def after(self, event) -> None:
        name = event.tool_use["name"]
        dt = time.time() - self._t0.pop(event.tool_use["toolUseId"], time.time())
        payload = _tool_json(event.result)
        err = payload.get("error") if isinstance(payload, dict) else None
        ok = event.result.get("status") == "success" and not err
        self.seen.append(name)
        if not self.quiet:
            mark = "✓" if ok else "✗"
            line = f"  {mark} {name:<16}{dt:5.1f}s" + (f"  {err}" if err else "")
            if self.live and self.live._lines:
                sys.stdout.write(f"\x1b[{self.live._lines}F\x1b[J{line}\n")
                self.live._lines = 0
            else:
                print(line)
        if self.live and name in ARTIFACT_TOOLS and ok:
            if name == "save_case":
                cid = payload.get("case_id")
                if cid:
                    self.live.case_id = cid
            elif name == "write_ics":
                self.live.done["ics"] = True
            elif name == "draft_reply":
                self.live.done["reply"] = True
            self.live.redraw()


def _tool_json(result: dict) -> dict:
    import json

    for c in result.get("content", []):
        if "json" in c:
            return c["json"]
        if "text" in c:
            try:
                return json.loads(c["text"])
            except ValueError:
                continue
    return {}


def _direct(trace: ToolTrace, live: LiveCard | None, tool, **kwargs) -> dict:
    """Call a tool without the model loop (same @tool functions), keeping the trace output identical."""
    t0 = time.time()
    out = tool(**kwargs)
    ok = isinstance(out, dict) and "error" not in out
    trace.seen.append(tool.tool_name)
    if not trace.quiet:
        line = f"  {'✓' if ok else '✗'} {tool.tool_name:<16}{time.time() - t0:5.1f}s"
        if live and live._lines:
            sys.stdout.write(f"\x1b[{live._lines}F\x1b[J{line}\n")
            live._lines = 0
        else:
            print(line)
    if live and ok and tool.tool_name in ARTIFACT_TOOLS:
        if tool.tool_name == "save_case":
            live.case_id = out.get("case_id")
        elif tool.tool_name == "write_ics":
            live.done["ics"] = True
        elif tool.tool_name == "draft_reply":
            live.done["reply"] = True
        live.redraw()
    return out


# -------------------------------------------------------------- questions
def _crop(photo: str | None, line: str) -> str | None:
    if not photo:
        return None
    try:
        from papelito import photo as _photo  # type: ignore
    except ImportError:
        return None
    for fn in ("crop_line", "crop", "crop_for_line"):
        f = getattr(_photo, fn, None)
        if f:
            try:
                out = f(photo, line)
                return str(out) if out else None
            except Exception:
                return None
    return None


def _parse_date(s: str, received_on: str) -> str | None:
    s = s.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    from papelito.extract import resolve_date

    return resolve_date(s, received_on)


def ask_questions(sess: dict[str, Any], lang: str, assume_no: bool) -> None:
    """Confidence gate: one question per unclear item, with the crop. Unanswered → no artifact."""
    ext = sess["extraction"]
    for a in ext["actions"]:
        if a["gate"] != "ask":
            continue
        q = E.QUESTIONS[E._lang(lang)][a.get("question") or "line"]
        crop = _crop(sess.get("photo_path"), a["source_line"])
        print()
        print(f"  ? {q}")
        print(f"    „{a['source_line']}“" + (f"  [crop: {crop}]" if crop else ""))
        if assume_no or not sys.stdin.isatty():
            print("    → " + {"en": "no answer: no artifact for this line",
                             "de": "keine Antwort: kein Artefakt für diese Zeile"}[E._lang(lang)])
            a["gate"] = "drop"
            continue
        ans = input("    > ").strip()
        if not ans:
            a["gate"] = "drop"
            continue
        if a["question"] == "date":
            iso = _parse_date(ans, ext["received_on"])
            if not iso:
                a["gate"] = "drop"
                continue
            a["deadline_iso"] = iso
        elif a["question"] == "amount":
            m = re.search(r"\d+(?:[.,]\d{1,2})?", ans)
            if not m:
                a["gate"] = "drop"
                continue
            a["amount"] = float(m.group(0).replace(",", "."))
        else:
            a["action"] = ans
        a["confidence"] = 1.0
        a["confirmed"] = True
        a["gate"] = "ok"
        a["question"] = None


# ------------------------------------------------------------------- add
def cmd_add(args: argparse.Namespace) -> int:
    store = Store(args.db) if args.db else get_store()
    profile = load_profile(args.profile)
    lang = args.lang or profile.get("language") or "en"
    A.SESSION.clear()
    A.configure(store=store, profile=profile, use_models=not args.no_model)
    vision, text_model = A._models()
    use_agent = not args.direct and text_model is not None
    received = args.received or date.today().isoformat()
    color = TTY and not args.no_color
    live = LiveCard(store, lang, color)
    trace = ToolTrace(live, quiet=args.quiet)
    agent = A.build_agent(hooks=[trace], callback_handler=None) if use_agent else None
    photo = args.photo
    print(f"papelito · {photo} · {received} · {lang}" + ("" if use_agent else " · direct"))

    # Phase 1: check, read, extract.
    pid: str | None = None
    if args.text:
        text = Path(args.text).read_text(encoding="utf-8")
        pid = A.register_paper(text, received, photo_path=photo if photo and Path(photo).exists() else None)["paper_id"]
        if agent:
            agent(f"The note at {photo} (received {received}) was already transcribed as paper_id {pid}. "
                  f"Call extract_actions('{pid}', '{received}') and then stop and report needs_confirmation.")
    else:
        if not Path(photo).exists():
            print(f"no such photo: {photo}", file=sys.stderr)
            return 2
        if vision is None:
            print("no vision model configured; pass --text note.txt or set ZEN_API_KEY", file=sys.stderr)
            return 2
        if agent:
            before = set(A.SESSION)
            agent(f"New photo: {photo}, received {received}, reader language {lang}. "
                  "Do steps 1-3 (check_photo, read_note, extract_actions), then stop and report the paper_id and needs_confirmation.")
            new = [k for k in A.SESSION if k not in before]
            pid = new[-1] if new else None
        else:
            chk = _direct(trace, live, A.check_photo, image_path=photo)
            if not chk.get("ok", True) and not args.force:
                print(f"photo not usable: {chk.get('hint')} (use --force to read anyway)")
                return 3
            pid = _direct(trace, live, A.read_note, image_path=photo, received_on=received).get("paper_id")
    if not pid or pid not in A.SESSION:
        print("could not read the note", file=sys.stderr)
        return 3
    sess = A.SESSION[pid]
    if "extraction" not in sess:
        _direct(trace, live, A.extract_actions, text=pid, received_on=received)
    if "extraction" not in sess:
        print("could not extract actions", file=sys.stderr)
        return 3

    # Reconcile first (deterministic, fast): a follow-up inherits what the case already knows,
    # so the confidence gate asks only what the paper really leaves open.
    _direct(trace, live, A.match_case, paper_id=pid)

    # Confidence gate.
    ask_questions(sess, lang, assume_no=args.yes)

    # Phase 2: match, save, card, ics, reply.
    if agent:
        agent(f"Continue with paper_id {pid}: match_case, save_case, explain_in('{lang}', case_id). "
              "write_ics only if there is a deadline. draft_reply only if the paper asks for a reply or money. "
              f"Then answer in {lang} in at most three short sentences.")
    if "case_id" not in sess:
        m = sess.get("match") or _direct(trace, live, A.match_case, paper_id=pid)
        _direct(trace, live, A.save_case, paper_id=pid, case_id=m.get("case_id") or "")
    cid = sess.get("case_id")
    if not cid:
        print("case not saved", file=sys.stderr)
        return 3
    have = {a["kind"] for a in store.get_case(cid)["artifacts"] if a["status"] == "active"}
    c = store.get_case(cid)
    if "ics" not in have and A.needs_calendar(c):
        _direct(trace, live, A.write_ics, case_id=cid)
    if "reply" not in have and A.needs_reply(c):
        _direct(trace, live, A.draft_reply, case_id=cid)
    if "card" not in have:
        _direct(trace, live, A.explain_in, language=lang, case_id=cid)

    # Final card and where the artifacts are.
    live.case_id = cid
    have = {a["kind"] for a in store.get_case(cid)["artifacts"] if a["status"] == "active"}
    live.done.update({"ics": "ics" in have, "reply": "reply" in have})
    if TTY and live._lines:
        sys.stdout.write(f"\x1b[{live._lines}F\x1b[J")
        live._lines = 0
    print()
    if sess.get("diff"):
        d = sess["diff"]
        print({"en": f"Existing case {cid}: amendment applied, {len(d['superseded'])} item(s) replaced.",
               "de": f"Bestehender Akt {cid}: Nachtrag angewendet, {len(d['superseded'])} Punkt(e) ersetzt."}[E._lang(lang)])
    else:
        print({"en": f"New case {cid}.", "de": f"Neuer Akt {cid}."}[E._lang(lang)])
    print(live.card() or "")
    print()
    out = A.out_dir()
    print(f"  .ics    {out / (cid + '.ics')}")
    print(f"  reply   {out / (cid + '-antwort.txt')}   (draft, not sent)")
    if agent is not None:
        last = agent.messages[-1] if agent.messages else None
        if last and last.get("role") == "assistant":
            said = " ".join(c.get("text", "") for c in last.get("content", []) if "text" in c).strip()
            if said:
                print()
                print("  " + said)
    return 0


# ------------------------------------------------------------ other cmds
def _store_for(args: argparse.Namespace) -> Store:
    return Store(args.db) if args.db else get_store()


def cmd_list(args: argparse.Namespace) -> int:
    store = _store_for(args)
    cases = store.list_cases(None if args.all else ("open", "due"))
    if not cases:
        print("no open cases")
        return 0
    for c in cases:
        active = [a for a in c["actions"] if a["status"] == "active"]
        nxt = min((a["deadline_iso"] for a in active if a["deadline_iso"]), default="-")
        flag = {"due": "!!", "open": "  ", "replied": "ok", "closed": "--"}[c["status"]]
        print(f"{flag} {c['id']}  {nxt}  {c['title']}  ({c['status']}, {len(active)} actions, {len(c['papers'])} papers)")
        if c.get("due_line"):
            print(f"      {c['due_line']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    import json

    c = _store_for(args).get_case(args.case)
    if not c:
        print("no such case", file=sys.stderr)
        return 1
    print(json.dumps(c, ensure_ascii=False, indent=2))
    return 0


def cmd_card(args: argparse.Namespace) -> int:
    store = _store_for(args)
    c = store.get_case(args.case)
    if not c:
        print("no such case", file=sys.stderr)
        return 1
    done = {a["kind"]: True for a in c["artifacts"] if a["status"] == "active"}
    done["saved"] = True
    done["reminder"] = done.get("ics", False)
    lang = args.lang or c.get("language") or "en"
    print(E.render_card(E.explain_in(lang, c, done=done), color=TTY and not args.no_color))
    return 0


def cmd_reply(args: argparse.Namespace) -> int:
    c = _store_for(args).get_case(args.case)
    if not c:
        print("no such case", file=sys.stderr)
        return 1
    active = [a for a in c["artifacts"] if a["kind"] == "reply" and a["status"] == "active"]
    if active:
        print(active[-1]["content"])
    else:
        from papelito.reply import draft_reply

        print(draft_reply(c, load_profile(args.profile)))
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    ok = _store_for(args).mark_replied(args.case)
    print("replied" if ok else "no such case")
    return 0 if ok else 1


def cmd_delete(args: argparse.Namespace) -> int:
    ok = _store_for(args).delete_case(args.case)
    print("deleted" if ok else "no such case")
    return 0 if ok else 1


def cmd_watch(args: argparse.Namespace) -> int:
    try:
        from papelito import watch as _watch  # type: ignore
    except ImportError:
        print("watchdog module not available", file=sys.stderr)
        return 1
    fn = getattr(_watch, "main", None) or getattr(_watch, "run", None)
    rest = list(args.rest or [])
    return int(fn(rest) or 0) if fn else 1


# ------------------------------------------------------------------ main
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", help="SQLite file (default $PAPELITO_DB or data/papelito.db)")
    common.add_argument("--profile", help="profile.yaml path")
    p = argparse.ArgumentParser(prog="papelito", description="Reads the paper in the schoolbag and does the work.",
                                parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="photograph → case, card, .ics, German reply", parents=[common])
    a.add_argument("photo")
    a.add_argument("--received", help="date the note was received (YYYY-MM-DD, default today)")
    a.add_argument("--lang", help="reader language: en (default), de")
    a.add_argument("--text", help="use this transcription instead of the vision model")
    a.add_argument("--direct", action="store_true", help="call the tools in fixed order, no model loop")
    a.add_argument("--no-model", action="store_true", help="no model at all: heuristic extraction (needs --text)")
    a.add_argument("--yes", action="store_true", help="never ask; unclear items get no artifact")
    a.add_argument("--force", action="store_true", help="read even if check_photo complains")
    a.add_argument("--quiet", action="store_true")
    a.add_argument("--no-color", action="store_true")
    a.set_defaults(fn=cmd_add)

    ls = sub.add_parser("list", help="open and due cases", parents=[common])
    ls.add_argument("--all", action="store_true")
    ls.set_defaults(fn=cmd_list)
    for name, fn in (("show", cmd_show), ("reply", cmd_reply), ("done", cmd_done), ("delete", cmd_delete)):
        s = sub.add_parser(name, parents=[common])
        s.add_argument("case")
        s.set_defaults(fn=fn)
    c = sub.add_parser("card", help="print the card for a case", parents=[common])
    c.add_argument("case")
    c.add_argument("--lang")
    c.add_argument("--no-color", action="store_true")
    c.set_defaults(fn=cmd_card)
    w = sub.add_parser("watch", help="run the watchdog once (papelito.watch)", parents=[common])
    w.add_argument("rest", nargs=argparse.REMAINDER)
    w.set_defaults(fn=cmd_watch)
    return p


def main(argv: list[str] | None = None) -> int:
    import logging

    logging.basicConfig(level=logging.ERROR)
    logging.getLogger("strands").setLevel(logging.ERROR)  # the gateway echoes reasoning blocks; Strands warns per turn
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
