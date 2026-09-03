/* Papelito. One list, four columns, four taps. Nothing is ever sent from here. */

const ASKED_KEY = "papelito.notice.asked";
const NOTIFIED_KEY = "papelito.notified";
const LANG_KEY = "papelito.lang";
const JOB_KEY = "papelito.job";
const POLL_MS = 20000;
const JOB_POLL_MS = 700;
const LANGS = ["en", "de"];
const VIEWS = ["cases", "board", "calendar", "settings"];

/* ---------------------------------------------------------------- language */

const T = {
  en: {
    today: "today {d}",
    notice_q: "Shall Papelito tell you two days before each date?",
    notice_yes: "Turn on reminders",
    notice_no: "Not now",
    empty_lead: "Nothing pending. Photograph a note from the Kindergarten and it becomes a case with four columns:",
    empty_cols: [
      ["what", "the kind of paper: money, appointment, reply requested, closed day"],
      ["do", "the one thing you have to do, in your language"],
      ["by when", "the date, with the German sentence it came from behind it"],
      ["done for you", "what Papelito already did: calendar entry, German reply, reminder two days before"],
    ],
    empty_note: "A second note about the same event updates the case instead of opening a new one. Nothing is sent without you.",
    show_done: "Show done", hide_done: "Hide done",
    shoot: "Photograph", upload: "Upload photo",
    received: "received {d}",
    papers: "{n} papers, updated {d}",
    yes: "Yes, correct", no: "No",
    view_original: "view the original", hide_original: "hide the original",
    no_source: "No original sentence saved.",
    copy: "Copy reply", calendar: "Calendar", done: "Done", done_checked: "Done ✓", delete: "Delete",
    ac_run: "Run on AgentCore",
    ac_wait: "First click may take about 15 seconds",
    ac_badge: "This card was produced on AgentCore Runtime",
    ac_fail: "AgentCore did not answer",
    reading: "Reading the note…", reading_title: "Reading your note",
    working: "the tools run, one after the other", tools_live: "live",
    live_note: "Each tick appears when that tool has returned. Nothing is ticked ahead of time.",
    saved: "Case saved", amended: "Case updated from this note: {n} line(s) replaced",
    copied: "Reply copied. Paste it into your mail or message and send it yourself. Papelito never sends.",
    marked_done: "Marked as done", deleted: "Deleted. Really gone, no archive.", thanks: "Thanks, noted.",
    confirm_delete: "Delete this case? It is really deleted, together with the photo. No undo.",
    failed: "Something failed",
    ago: "{n} d. ago", today_short: "today", tomorrow_short: "tomorrow", in_days: "in {n} d.",
    was: "was {d}", now: "now {d}", replaced: "replaced by a later note", updated: "updated from a later note",
    steps: {
      check_photo: "photo ok", read_note: "read", extract_actions: "dates", match_case: "case",
      save_case: "saved", write_ics: "calendar", draft_reply: "German reply", explain_in: "card",
    },
    step_detail: { amendment: "existing case, amended", new: "new case", failed: "failed", skipped: "not run" },
    errors: {
      not_found: "Case not found", empty_photo: "The photo arrived empty", too_large: "The photo is too large",
      bad_format: "Unsupported photo format", bad_answer: "Invalid answer", no_photo: "No photo", no_job: "Upload not found",
      bad_settings: "Those settings are not valid", bad_calendar: "That month does not exist",
      no_agentcore: "AgentCore is not configured", agentcore_failed: "AgentCore did not answer",
    },
    notification_title: "Papelito",
    away_kicker: "While you were away",
    away_never: "Papelito has not checked the open cases yet. The daily timer does that with the phone face down.",
    away_quiet: "Papelito looked at {n} open case(s). Nothing new to nag about.",
    away_nagged: "Papelito looked at {n} open case(s) and left {k} reminder(s).",
    away_run: "Check now",
    away_ran: "Last check {d}",

    nav_cases: "Cases", nav_board: "Board", nav_calendar: "Calendar", nav_settings: "Settings",

    for_child: "for", child_none: "not assigned", child_all: "All",
    child_saved: "This paper is {n}'s", child_cleared: "Name taken off this paper",

    board_title: "The board",
    board_lead: "Every paper that came in. A notice hangs quietly, a paper that asks for something carries its date.",
    board_empty: "No paper on the board yet. Photograph one.",
    board_notice: "notice", board_action: "to do",
    board_no_text: "No German text saved.",

    cal_today: "Today",
    cal_key_due: "due or overdue", cal_key_open: "later",
    cal_pick_day: "Tap a day to see what is on it.",
    cal_day_empty: "Nothing on this day.",
    cal_offline: "The month is not there yet. The list and the calendar file still work.",
    cal_months: ["January", "February", "March", "April", "May", "June",
                 "July", "August", "September", "October", "November", "December"],
    cal_months_short: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    cal_week: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],

    settings_title: "Settings",
    s_household: "Household", s_parent: "Your name",
    s_signature: "Signature under the German reply",
    s_signature_hint: "It goes under the draft you copy. Papelito never sends.",
    s_language: "Language", s_children: "Children",
    s_no_children: "No child yet. Add one and you can say which paper belongs to whom.",
    s_child_name: "Name", s_kg: "Kindergarten",
    s_add: "Add", s_remove: "Remove", s_save: "Save", s_saved: "Saved",
    s_confirm_remove: "Remove {n}? The papers stay, they only lose the name.",
    s_need_name: "A child needs a name.",
    s_privacy: "This stays on your own server. Nothing here is sent anywhere.",
    s_offline: "Settings could not be saved.",
  },
  de: {
    today: "heute {d}",
    notice_q: "Soll Papelito dich zwei Tage vor jedem Termin erinnern?",
    notice_yes: "Erinnerungen einschalten",
    notice_no: "Jetzt nicht",
    empty_lead: "Nichts offen. Fotografiere ein Papier vom Kindergarten, daraus wird ein Akt mit vier Spalten:",
    empty_cols: [
      ["was", "die Art des Papiers: Geld, Termin, Rückmeldung, Schließtag"],
      ["tun", "das eine, das du tun musst, in deiner Sprache"],
      ["bis wann", "die Frist, dahinter der deutsche Satz, aus dem sie stammt"],
      ["erledigt", "was Papelito schon gemacht hat: Kalendereintrag, deutsche Antwort, Erinnerung zwei Tage vorher"],
    ],
    empty_note: "Eine zweite Mitteilung zum selben Ereignis aktualisiert den Akt statt einen neuen anzulegen. Ohne dich wird nichts verschickt.",
    show_done: "Erledigte zeigen", hide_done: "Erledigte ausblenden",
    shoot: "Fotografieren", upload: "Foto hochladen",
    received: "erhalten {d}",
    papers: "{n} Papiere, aktualisiert {d}",
    yes: "Ja, stimmt", no: "Nein",
    view_original: "Original zeigen", hide_original: "Original ausblenden",
    no_source: "Kein Originalsatz gespeichert.",
    copy: "Antwort kopieren", calendar: "Kalender", done: "Erledigt", done_checked: "Erledigt ✓", delete: "Löschen",
    ac_run: "Auf AgentCore ausführen",
    ac_wait: "Der erste Klick kann etwa 15 Sekunden dauern",
    ac_badge: "Diese Karte kam von AgentCore Runtime",
    ac_fail: "AgentCore hat nicht geantwortet",
    reading: "Papier wird gelesen…", reading_title: "Dein Papier wird gelesen",
    working: "die Werkzeuge laufen nacheinander", tools_live: "live",
    live_note: "Jeder Haken erscheint, wenn das Werkzeug fertig ist. Nichts wird vorab abgehakt.",
    saved: "Akt gespeichert", amended: "Akt aus dieser Mitteilung aktualisiert: {n} Zeile(n) ersetzt",
    copied: "Antwort kopiert. Füge sie in Mail oder Nachricht ein und schick sie selbst. Papelito sendet nie.",
    marked_done: "Als erledigt markiert", deleted: "Gelöscht. Wirklich weg, kein Archiv.", thanks: "Danke, notiert.",
    confirm_delete: "Diesen Akt löschen? Er wird wirklich gelöscht, samt Foto. Kein Zurück.",
    failed: "Etwas ist schiefgegangen",
    ago: "vor {n} T.", today_short: "heute", tomorrow_short: "morgen", in_days: "in {n} T.",
    was: "war {d}", now: "neu {d}", replaced: "durch spätere Mitteilung ersetzt", updated: "aus späterer Mitteilung aktualisiert",
    steps: {
      check_photo: "Foto ok", read_note: "gelesen", extract_actions: "Fristen", match_case: "Akt",
      save_case: "gespeichert", write_ics: "Kalender", draft_reply: "Antwort (DE)", explain_in: "Karte",
    },
    step_detail: { amendment: "bestehender Akt, ergänzt", new: "neuer Akt", failed: "fehlgeschlagen", skipped: "nicht gelaufen" },
    errors: {
      not_found: "Akt nicht gefunden", empty_photo: "Das Foto kam leer an", too_large: "Das Foto ist zu groß",
      bad_format: "Fotoformat nicht unterstützt", bad_answer: "Ungültige Antwort", no_photo: "Kein Foto", no_job: "Upload nicht gefunden",
      bad_settings: "Diese Einstellungen gehen nicht", bad_calendar: "Diesen Monat gibt es nicht",
      no_agentcore: "AgentCore ist nicht eingerichtet", agentcore_failed: "AgentCore hat nicht geantwortet",
    },
    notification_title: "Papelito",
    away_kicker: "Während du weg warst",
    away_never: "Papelito hat die offenen Akte noch nicht geprüft. Das macht der tägliche Timer, auch wenn das Telefon auf dem Tisch liegt.",
    away_quiet: "Papelito hat {n} offene Akte angesehen. Nichts zum Erinnern.",
    away_nagged: "Papelito hat {n} offene Akte angesehen und {k} Erinnerung(en) hinterlassen.",
    away_run: "Jetzt prüfen",
    away_ran: "Letzte Prüfung {d}",

    nav_cases: "Akten", nav_board: "Pinnwand", nav_calendar: "Kalender", nav_settings: "Einstellungen",

    for_child: "für", child_none: "nicht zugeordnet", child_all: "Alle",
    child_saved: "Dieses Papier gehört zu {n}", child_cleared: "Name vom Papier entfernt",

    board_title: "Die Pinnwand",
    board_lead: "Jedes Papier, das hereinkam. Eine Mitteilung hängt still, ein Papier mit Frist zeigt sein Datum.",
    board_empty: "Noch kein Papier an der Pinnwand. Fotografiere eines.",
    board_notice: "Mitteilung", board_action: "zu tun",
    board_no_text: "Kein deutscher Text gespeichert.",

    cal_today: "Heute",
    cal_key_due: "fällig oder überfällig", cal_key_open: "später",
    cal_pick_day: "Tippe einen Tag an, dann siehst du, was ansteht.",
    cal_day_empty: "An diesem Tag nichts.",
    cal_offline: "Der Monat ist noch nicht da. Liste und Kalenderdatei gehen trotzdem.",
    cal_months: ["Jänner", "Februar", "März", "April", "Mai", "Juni",
                 "Juli", "August", "September", "Oktober", "November", "Dezember"],
    cal_months_short: ["Jän", "Feb", "März", "Apr", "Mai", "Juni", "Juli", "Aug", "Sep", "Okt", "Nov", "Dez"],
    cal_week: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],

    settings_title: "Einstellungen",
    s_household: "Haushalt", s_parent: "Dein Name",
    s_signature: "Unterschrift unter der deutschen Antwort",
    s_signature_hint: "Steht unter dem Entwurf, den du kopierst. Papelito verschickt nie.",
    s_language: "Sprache", s_children: "Kinder",
    s_no_children: "Noch kein Kind. Lege eines an, dann kannst du sagen, wem ein Papier gehört.",
    s_child_name: "Name", s_kg: "Kindergarten",
    s_add: "Hinzufügen", s_remove: "Entfernen", s_save: "Speichern", s_saved: "Gespeichert",
    s_confirm_remove: "{n} entfernen? Die Papiere bleiben, nur der Name geht weg.",
    s_need_name: "Ein Kind braucht einen Namen.",
    s_privacy: "Bleibt auf deinem eigenen Server. Von hier geht nichts weg.",
    s_offline: "Einstellungen konnten nicht gespeichert werden.",
  },
};

const storedLang = localStorage.getItem(LANG_KEY);
let lang = LANGS.includes(storedLang) ? storedLang : "en";
let langIsChosen = LANGS.includes(storedLang);

function t(key, vars = {}) {
  const raw = (T[lang] && T[lang][key]) ?? T.en[key] ?? key;
  return typeof raw === "string" ? raw.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? "")) : raw;
}

function applyLanguage() {
  document.documentElement.lang = lang;
  if (langIsChosen) localStorage.setItem(LANG_KEY, lang);
  for (const el of document.querySelectorAll("[data-t]")) el.textContent = t(el.dataset.t);
  for (const btn of document.querySelectorAll("[data-lang]")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.lang === lang));
  }
  document.getElementById("toggle-done").textContent = includeDone ? t("hide_done") : t("show_done");
  document.getElementById("child-name").placeholder = t("s_child_name");
  document.getElementById("child-kg").placeholder = t("s_kg");
  const cols = document.getElementById("empty-columns");
  cols.replaceChildren(...t("empty_cols").map(([name, what]) => {
    const li = document.createElement("li");
    const b = document.createElement("b");
    b.textContent = name;
    li.append(b, ` ${what}`);
    return li;
  }));
  renderChips();
  renderChildList();
}

/* -------------------------------------------------------------------- state */

const listEl = document.getElementById("list");
const emptyEl = document.getElementById("empty");
const todayEl = document.getElementById("today");
const householdEl = document.getElementById("household");
const toastEl = document.getElementById("toast");
const noticeEl = document.getElementById("notice");
const chipsEl = document.getElementById("chips");
const boardEl = document.getElementById("board");
const boardEmptyEl = document.getElementById("board-empty");
const tpl = document.getElementById("slip-tpl");
const liveTpl = document.getElementById("live-tpl");
const pinTpl = document.getElementById("pin-tpl");

let includeDone = false;
let notified = new Set(load(NOTIFIED_KEY, []));
let lastData = null;
let liveJob = null; /* {job, steps, state} while a photo is being read */

let view = viewFromHash();
let settings = { parent: "", household: "", language: "en", signature: "", children: [] };
let childFilter = ""; /* "" = every child, otherwise a child id */
let boardPapers = [];
let calMonth = null; /* {year, month} */
let calDays = new Map(); /* iso date -> items */
let calLoaded = false;
let calPick = "";

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}

function toast(text, ms = 2600) {
  toastEl.textContent = text;
  toastEl.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { toastEl.hidden = true; }, ms);
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = t("failed");
    try {
      const body = await res.json();
      const d = body.detail;
      if (d && typeof d === "object") detail = t("errors")[d.code] || d.message || detail;
      else if (typeof d === "string") detail = d;
    } catch { /* keep default */ }
    throw new Error(detail);
  }
  return res;
}

async function json(path, options) {
  return (await api(path, options)).json();
}

function withLang(path) {
  return `${path}${path.includes("?") ? "&" : "?"}lang=${lang}`;
}

function cell(tag, cls, text) {
  const el = document.createElement(tag);
  el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
}

/* ------------------------------------------------------------ paper shapes */

/* A row still standing: not struck through by a later note. */
function liveRows(c) {
  return (c.rows || []).filter((r) => r.status !== "superseded" && !r.superseded);
}

function dated(row) {
  return row.days_left !== null && row.days_left !== undefined;
}

/* write_ics only has something to write when a standing row carries a date. */
function hasIcs(c) {
  return liveRows(c).some(dated);
}

/* A notice tells you something. A paper asks you for something, by a date. */
function isNotice(c) {
  const active = (c.rows || []).filter((r) => (r.status || "active") === "active");
  return !active.some((r) => dated(r) && r.kind && r.kind !== "info");
}

/* The German sentences the reading came from, as they stand on the paper. */
function previewOf(c) {
  const lines = (c.rows || []).map((r) => r.source_line).filter(Boolean);
  return [...new Set(lines)].slice(0, 3).join(" ");
}

/* The nearest date still ahead of you on this paper. */
function nextDue(c) {
  const rows = liveRows(c).filter(dated);
  if (!rows.length) return null;
  return rows.reduce((a, b) => (a.days_left <= b.days_left ? a : b));
}

/* One paper, as it hangs on the board. /api/board lists the papers, the case
   list carries the dates and the state, so a pin is built from both. */
function pinOf(item, c) {
  const from = c || {};
  const caseId = item.case_id || from.id || "";
  const due = nextDue(from);
  /* The board endpoint calls any paper with a date an action. A Tagesablauf or
     a Terminausblick only tells you something, so the rows have the last word. */
  const notice = c ? isNotice(c) : item.board === "notice";
  return {
    id: caseId,
    key: item.paper_id || caseId,
    title: item.title || from.title || "",
    received: item.received_on ? dayLabel(item.received_on) : (from.received_label || ""),
    sender: from.sender || "",
    child_id: item.child_id || from.child_id || "",
    child_name: item.child_name || from.child_name || "",
    photo: (item.photo || from.has_photo) && caseId ? `/api/cases/${caseId}/photo` : "",
    preview: item.text_preview || previewOf(from),
    kind: notice ? "notice" : "action",
    state: from.state || "open",
    when: due ? due.when : "",
    days_left: due ? due.days_left : null,
  };
}

function leftLabel(days) {
  if (days === null || days === undefined) return "";
  if (days < 0) return t("ago", { n: Math.abs(days) });
  if (days === 0) return t("today_short");
  if (days === 1) return t("tomorrow_short");
  return t("in_days", { n: days });
}

/* ------------------------------------------------------------------- cards */

function stepItem(mark) {
  const li = cell("li", "", mark.label);
  li.dataset.state = mark.state;
  if (mark.tool) {
    const code = document.createElement("code");
    code.textContent = mark.tool;
    li.append(" ", code);
  }
  if (mark.note) li.append(cell("small", "note", mark.note));
  return li;
}

/* The four columns, one row per action, laid out as one grid so they stay aligned. */
function buildTable(labels, rows) {
  const table = document.createDocumentFragment();
  for (const label of labels) table.append(cell("span", "lbl", label));

  rows.forEach((row, i) => {
    const sep = i > 0 ? " sep" : "";
    const off = row.superseded ? " off" : "";
    const what = cell("div", `cell${sep}${off}`, row.what);
    if (row.superseded) what.setAttribute("aria-label", `${t("replaced")}: ${row.what}`);
    table.append(what);
    table.append(cell("div", `cell${sep}${off}`, row.do));

    const when = cell("div", `cell when${sep}${off}`, row.when);
    if (row.days_left !== null && row.days_left !== undefined && !row.superseded) {
      when.append(cell("small", "left", leftLabel(row.days_left)));
    }
    /* The amendment, visible on both lines: the old date says what replaced it, the new one what it replaced. */
    if (row.superseded && row.replaced_by) {
      when.append(cell("small", "amend", `${t("now", { d: row.replaced_by.when || "" })}`.trim()));
    } else if (row.replaces && row.replaces.length) {
      for (const old of row.replaces) {
        if (old.when && old.when !== row.when) when.append(cell("small", "amend", t("was", { d: old.when })));
      }
    }
    table.append(when);

    const steps = cell("ul", `cell steps${sep}${off}`);
    if (row.superseded) {
      steps.append(stepItem({ label: t("replaced"), state: "off" }));
    }
    for (const mark of row.done) steps.append(stepItem(mark));
    table.append(steps);
  });
  return table;
}

function option(value, label) {
  const opt = document.createElement("option");
  opt.value = value;
  opt.textContent = label;
  return opt;
}

function buildSlip(c) {
  const node = tpl.content.firstElementChild.cloneNode(true);
  const f = (name) => node.querySelector(`[data-f="${name}"]`);
  node.dataset.state = c.state;
  node.dataset.id = c.id;
  node.dataset.kind = isNotice(c) ? "notice" : "action";
  for (const el of node.querySelectorAll("[data-t]")) el.textContent = t(el.dataset.t);

  f("sender").textContent = c.sender || "Papelito";
  f("received").textContent = c.received_label ? t("received", { d: c.received_label }) : "";
  f("title").textContent = c.title;
  if (c.paper_count > 1) {
    f("papers").textContent = t("papers", { n: c.paper_count, d: c.amended_label || "" }).replace(/,\s*$/, "");
    f("papers").hidden = false;
    node.classList.add("amended");
  }

  /* Whose paper is this. Only asked once there is a child to name. */
  if (settings.children.length) {
    const pick = f("child");
    const select = pick.querySelector("select");
    select.replaceChildren(option("", t("child_none")), ...settings.children.map((k) => option(k.id, k.name)));
    select.value = c.child_id || "";
    pick.hidden = false;
  }

  f("table").append(buildTable(c.labels, c.rows));

  const reminder = f("reminder");
  if (c.reminder && c.state !== "replied") {
    reminder.textContent = c.reminder;
    reminder.hidden = false;
  }

  if (c.question) {
    f("question").textContent = c.question;
    f("ask").hidden = false;
  }

  /* Every deadline keeps its German source sentence; the photo sits behind it. */
  const sources = c.rows.map((r) => r.source_line).filter(Boolean);
  const expand = node.querySelector('[data-act="expand"]');
  if (sources.length || c.has_photo) {
    const list = f("sources");
    for (const line of sources.length ? sources : [t("no_source")]) {
      list.append(cell("li", "", line));
    }
    if (c.has_photo) f("crop").dataset.src = `/api/cases/${c.id}/photo`;
  } else {
    expand.hidden = true;
  }

  /* A notice has no German reply to copy and no date to put in a calendar. */
  node.querySelector('[data-act="copy"]').hidden = !c.has_reply;
  const ics = node.querySelector('[data-act="ics"]');
  if (hasIcs(c)) ics.href = `/api/cases/${c.id}/calendar.ics`;
  else ics.hidden = true;

  const done = node.querySelector('[data-act="done"]');
  if (c.state === "replied") {
    done.textContent = t("done_checked");
    done.disabled = true;
  }

  const ac = node.querySelector('[data-act="agentcore"]');
  if (ac) ac.hidden = !(lastData && lastData.agentcore && c.id === "demo-ausflug");
  return node;
}

/* The slip that fills up while the agent works: one row, fourth column = the tools. */
function buildLive(job) {
  const node = liveTpl.content.firstElementChild.cloneNode(true);
  const f = (name) => node.querySelector(`[data-f="${name}"]`);
  node.dataset.job = job.job;
  for (const el of node.querySelectorAll("[data-t]")) el.textContent = t(el.dataset.t);
  f("title").textContent = t("reading_title");
  f("tools").textContent = t("tools_live");
  const labels = (lastData && lastData.cases[0] && lastData.cases[0].labels) || labelsFor(lang);
  const marks = job.steps.map((s) => {
    const detail = s.detail || {};
    let note = "";
    if (s.tool === "match_case" && s.state === "done" && detail.result) note = t("step_detail")[detail.result] || "";
    if (s.tool === "extract_actions" && s.state === "done" && detail.actions !== undefined) note = `${detail.actions}`;
    if (s.tool === "write_ics" && s.state === "done" && detail.events !== undefined) note = `${detail.events}`;
    if (s.state === "failed") note = t("step_detail").failed;
    if (s.state === "skipped") note = t("step_detail").skipped;
    return { label: t("steps")[s.tool] || s.tool, state: s.state, tool: s.tool, note };
  });
  const row = { what: "", do: t("working"), when: "…", days_left: null, done: marks, superseded: false };
  f("table").append(buildTable(labels, [row]));
  return node;
}

function labelsFor(code) {
  return { en: ["what", "do", "by when", "done for you"], de: ["was", "tun", "bis wann", "erledigt"] }[code];
}

/* ------------------------------------------------------------ child filter */

function keeps(paper) {
  return !childFilter || paper.child_id === childFilter;
}

function renderChips() {
  const many = settings.children.length > 1;
  chipsEl.hidden = !many || (view !== "cases" && view !== "board");
  if (!many) {
    childFilter = "";
    return;
  }
  const make = (id, label) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.dataset.child = id;
    b.textContent = label;
    b.setAttribute("aria-pressed", String(childFilter === id));
    return b;
  };
  chipsEl.replaceChildren(make("", t("child_all")), ...settings.children.map((k) => make(k.id, k.name)));
}

document.getElementById("away-run").addEventListener("click", async () => {
  const button = document.getElementById("away-run");
  button.disabled = true;
  try {
    render(await json(withLang("/api/watch"), { method: "POST" }));
  } catch (err) {
    toast(err.message);
  } finally {
    button.disabled = false;
  }
});

document.getElementById("away-list").addEventListener("click", (event) => {
  const a = event.target.closest("a[data-case]");
  if (!a) return;
  event.preventDefault();
  showView("cases");
});

chipsEl.addEventListener("click", (event) => {
  const chip = event.target.closest("[data-child]");
  if (!chip) return;
  childFilter = chip.dataset.child;
  renderChips();
  render(lastData);
  renderBoard();
});

/* ------------------------------------------------------------- cases view */

function render(data) {
  if (!data) return;
  lastData = data;
  todayEl.textContent = t("today", { d: data.today_label || data.today });
  householdEl.textContent = settings.household || data.household || "";
  householdEl.hidden = !householdEl.textContent;
  renderAway(data.away);
  const cases = data.cases.filter(keeps);
  const nodes = cases.map(buildSlip);
  if (liveJob && liveJob.state !== "done") nodes.unshift(buildLive(liveJob));
  listEl.replaceChildren(...nodes);
  emptyEl.hidden = cases.length > 0 || Boolean(liveJob);
  document.title = data.due_count ? `(${data.due_count}) Papelito` : "Papelito";
  announce(data.cases);
}

function renderAway(away) {
  const box = document.getElementById("away");
  const kicker = document.getElementById("away-kicker");
  const body = document.getElementById("away-body");
  const list = document.getElementById("away-list");
  if (!box || !kicker || !body || !list) return;
  box.hidden = false;
  kicker.textContent = t("away_kicker");
  const nagged = (away && away.nagged) || [];
  const checked = (away && away.checked) || 0;
  if (!away || !away.ran_at) {
    body.textContent = t("away_never");
    list.replaceChildren();
    return;
  }
  const when = away.ran_at.replace("T", " ").slice(0, 16);
  if (nagged.length === 0) {
    body.textContent = `${t("away_quiet", { n: checked })} ${t("away_ran", { d: when })}`;
    list.replaceChildren();
    return;
  }
  body.textContent = `${t("away_nagged", { n: checked, k: nagged.length })} ${t("away_ran", { d: when })}`;
  list.replaceChildren(...nagged.map((item) => {
    const li = document.createElement("li");
    if (item.case_id) {
      const a = document.createElement("a");
      a.href = `#cases`;
      a.dataset.case = item.case_id;
      a.textContent = item.text || item.case_id;
      li.append(a);
    } else {
      li.textContent = item.text || "";
    }
    return li;
  }));
}

async function refresh() {
  try {
    render(await json(withLang(`/api/cases?include_done=${includeDone}`)));
  } catch (err) {
    toast(err.message);
  }
}

/* -------------------------------------------------------------- board view */

/* The board endpoint if it is there, otherwise one pin per case from the list. */
async function loadBoard() {
  let cases = [];
  try {
    cases = (await json(withLang("/api/cases?include_done=true"))).cases;
  } catch (err) {
    toast(err.message);
  }
  const byCase = new Map(cases.map((c) => [c.id, c]));

  let papers = null;
  try {
    const res = await fetch(withLang("/api/board"));
    if (res.ok) {
      const body = await res.json();
      const items = Array.isArray(body) ? body : body.items || body.papers || body.cases || [];
      papers = items.map((item) => pinOf(item, byCase.get(item.case_id)));
    }
  } catch { /* no board endpoint: the cases below say the same thing */ }

  boardPapers = papers || cases.map((c) => pinOf({}, c));
  renderBoard();
}

function buildPin(p) {
  const node = pinTpl.content.firstElementChild.cloneNode(true);
  const f = (name) => node.querySelector(`[data-f="${name}"]`);
  node.dataset.id = p.id;
  node.dataset.kind = p.kind;
  node.dataset.state = p.state;

  if (p.photo) {
    const img = f("photo");
    img.addEventListener("error", () => { img.hidden = true; });
    img.src = p.photo;
    img.hidden = false;
  }
  f("child").textContent = p.child_name || "";
  f("received").textContent = p.received || p.sender || "";
  f("title").textContent = p.title;
  f("preview").textContent = p.preview || t("board_no_text");
  const tag = p.kind === "notice" ? t("board_notice") : t("board_action");
  f("tag").textContent = p.state === "replied" ? t("done") : tag;

  /* Only a paper that asks for something wears a date. */
  if (p.kind === "action" && p.when) {
    const due = f("due");
    due.textContent = p.when;
    due.append(cell("small", "left", leftLabel(p.days_left)));
    due.hidden = false;
  }
  return node;
}

function renderBoard() {
  const papers = boardPapers.filter(keeps);
  boardEl.replaceChildren(...papers.map(buildPin));
  boardEmptyEl.hidden = papers.length > 0;
}

boardEl.addEventListener("click", (event) => {
  const pin = event.target.closest(".pin");
  if (pin) openCase(pin.dataset.id);
});

boardEl.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const pin = event.target.closest(".pin");
  if (!pin) return;
  event.preventDefault();
  openCase(pin.dataset.id);
});

/* From the board or the month, back to the case itself. */
async function openCase(id) {
  childFilter = "";
  goTo("cases");
  await refresh();
  if (!listEl.querySelector(`.slip[data-id="${id}"]`) && !includeDone) {
    includeDone = true;
    applyLanguage();
    await refresh();
  }
  const node = listEl.querySelector(`.slip[data-id="${id}"]`);
  if (!node) return;
  node.classList.add("fresh");
  node.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ----------------------------------------------------------- calendar view */

const calGrid = document.getElementById("cal-grid");
const calWeek = document.getElementById("cal-week");
const calTitle = document.getElementById("cal-title");
const calDayEl = document.getElementById("cal-day");

function iso(year, month, day) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function dayLabel(stamp) {
  const [y, m, d] = stamp.split("-").map(Number);
  const dow = (new Date(y, m - 1, d).getDay() + 6) % 7;
  return `${t("cal_week")[dow]} ${d} ${t("cal_months_short")[m - 1]}`;
}

/* The loudest thing on a day decides its colour. */
const CAL_RANK = { overdue: 4, due: 3, open: 2, replied: 1, off: 0 };

function worst(items) {
  return items.reduce((a, i) => (CAL_RANK[i.state] > CAL_RANK[a] ? i.state : a), "off");
}

async function loadMonth() {
  const { year, month } = calMonth;
  calDays = new Map();
  calLoaded = false;
  try {
    const res = await fetch(withLang(`/api/calendar?year=${year}&month=${month}`));
    if (res.ok) {
      const body = await res.json();
      const days = Array.isArray(body.days) ? body.days : [];
      for (const day of days) {
        const stamp = day.date || day.day || "";
        const items = (day.items || []).map((i) => ({
          case_id: i.case_id || i.id || "",
          title: i.title || "",
          do: i.do || i.what || "",
          child_name: i.child_name || "",
          state: CAL_RANK[i.state] === undefined ? "open" : i.state,
        }));
        if (stamp && items.length) calDays.set(stamp, items);
      }
      calLoaded = true;
    }
  } catch { /* the month stays empty */ }
  renderCalendar();
}

function renderCalendar() {
  const { year, month } = calMonth;
  calTitle.textContent = `${t("cal_months")[month - 1]} ${year}`;
  calWeek.replaceChildren(...t("cal_week").map((d) => cell("span", "wd", d)));

  const first = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const length = new Date(year, month, 0).getDate();
  const nodes = [];
  for (let i = 0; i < first; i += 1) nodes.push(cell("span", "cal-pad"));

  const now = (lastData && lastData.today) || "";
  for (let day = 1; day <= length; day += 1) {
    const stamp = iso(year, month, day);
    const items = calDays.get(stamp) || [];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cal-cell";
    button.dataset.date = stamp;
    if (stamp === now) button.dataset.today = "1";
    if (stamp === calPick) button.setAttribute("aria-pressed", "true");
    button.append(cell("span", "num", String(day)));
    if (items.length) {
      button.dataset.state = worst(items);
      const dots = cell("span", "dots");
      for (const item of items.slice(0, 3)) {
        const dot = cell("span", "dot");
        dot.dataset.state = item.state;
        dots.append(dot);
      }
      dots.setAttribute("aria-label", `${items.length}`);
      button.append(dots);
    }
    nodes.push(button);
  }
  calGrid.replaceChildren(...nodes);
  renderCalDay();
}

function renderCalDay() {
  const parts = [];
  if (!calLoaded) parts.push(cell("p", "view-empty", t("cal_offline")));

  if (!calPick || !calPick.startsWith(`${calMonth.year}-${String(calMonth.month).padStart(2, "0")}`)) {
    parts.push(cell("p", "view-empty", t("cal_pick_day")));
    calDayEl.replaceChildren(...parts);
    return;
  }

  parts.push(cell("h3", "cal-day-title", dayLabel(calPick)));
  const items = calDays.get(calPick) || [];
  if (!items.length) {
    parts.push(cell("p", "view-empty", t("cal_day_empty")));
    calDayEl.replaceChildren(...parts);
    return;
  }
  const list = cell("ul", "cal-items");
  for (const item of items) {
    const li = document.createElement("li");
    li.dataset.state = item.state;
    li.dataset.id = item.case_id;
    li.append(cell("b", "cal-do", item.do));
    const meta = [item.title, item.child_name].filter(Boolean).join(" · ");
    if (meta) li.append(cell("span", "cal-meta", meta));
    list.append(li);
  }
  parts.push(list);
  calDayEl.replaceChildren(...parts);
}

function stepMonth(by) {
  const d = new Date(calMonth.year, calMonth.month - 1 + by, 1);
  calMonth = { year: d.getFullYear(), month: d.getMonth() + 1 };
  loadMonth();
}

document.getElementById("cal-prev").addEventListener("click", () => stepMonth(-1));
document.getElementById("cal-next").addEventListener("click", () => stepMonth(1));
document.getElementById("cal-today").addEventListener("click", () => {
  const now = (lastData && lastData.today) || new Date().toISOString().slice(0, 10);
  const [year, month] = now.split("-").map(Number);
  calPick = now;
  calMonth = { year, month };
  loadMonth();
});

calGrid.addEventListener("click", (event) => {
  const button = event.target.closest(".cal-cell");
  if (!button) return;
  calPick = button.dataset.date === calPick ? "" : button.dataset.date;
  renderCalendar();
});

calDayEl.addEventListener("click", (event) => {
  const item = event.target.closest("li[data-id]");
  if (item && item.dataset.id) openCase(item.dataset.id);
});

/* ----------------------------------------------------------- settings view */

const form = document.getElementById("settings-form");
const childListEl = document.getElementById("child-list");
const noChildrenEl = document.getElementById("no-children");
const nameInput = document.getElementById("child-name");
const kgInput = document.getElementById("child-kg");

function normalizeSettings(data) {
  return {
    parent: String(data.parent || ""),
    household: String(data.household || ""),
    language: LANGS.includes(data.language) ? data.language : "en",
    signature: String(data.signature || ""),
    children: (data.children || [])
      .filter((k) => k && k.name)
      .map((k) => ({ id: String(k.id || k.name), name: String(k.name), kindergarten: String(k.kindergarten || "") })),
  };
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) settings = normalizeSettings(await res.json());
  } catch { /* the page runs without settings */ }
  /* The household picked a language; a language chosen on this phone still wins. */
  if (!langIsChosen && settings.language !== lang) {
    lang = settings.language;
    applyLanguage();
  }
  fillSettings();
  renderChips();
}

function fillSettings() {
  document.getElementById("s-household").value = settings.household;
  document.getElementById("s-parent").value = settings.parent;
  document.getElementById("s-signature").value = settings.signature;
  renderChildList();
}

function renderChildList() {
  noChildrenEl.hidden = settings.children.length > 0;
  childListEl.replaceChildren(...settings.children.map((k) => {
    const li = document.createElement("li");
    const who = cell("span", "child-who");
    who.append(cell("b", "", k.name));
    if (k.kindergarten) who.append(cell("small", "", k.kindergarten));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost child-remove";
    remove.dataset.child = k.id;
    remove.textContent = t("s_remove");
    li.append(who, remove);
    return li;
  }));
}

function formValues() {
  return {
    household: document.getElementById("s-household").value.trim(),
    parent: document.getElementById("s-parent").value.trim(),
    signature: document.getElementById("s-signature").value.trim(),
    language: lang,
    children: settings.children,
  };
}

async function saveSettings(payload) {
  const body = payload || formValues();
  try {
    const saved = await json("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    settings = normalizeSettings(saved);
  } catch (err) {
    toast(err.message === t("failed") ? t("s_offline") : err.message);
    return false;
  }
  fillSettings();
  renderChips();
  householdEl.textContent = settings.household;
  householdEl.hidden = !settings.household;
  await refresh();
  return true;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.getElementById("settings-save");
  button.disabled = true;
  if (await saveSettings()) toast(t("s_saved"));
  button.disabled = false;
});

document.getElementById("child-add").addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) {
    toast(t("s_need_name"));
    nameInput.focus();
    return;
  }
  const child = { id: `k${Date.now().toString(36)}`, name, kindergarten: kgInput.value.trim() };
  const payload = formValues();
  payload.children = [...settings.children, child];
  if (await saveSettings(payload)) {
    nameInput.value = "";
    kgInput.value = "";
    toast(t("s_saved"));
  }
});

childListEl.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-child]");
  if (!button) return;
  const child = settings.children.find((k) => k.id === button.dataset.child);
  if (!child || !confirm(t("s_confirm_remove", { n: child.name }))) return;
  const payload = formValues();
  payload.children = settings.children.filter((k) => k.id !== child.id);
  if (await saveSettings(payload)) toast(t("s_saved"));
});

/* ------------------------------------------------------------------ views */

function viewFromHash() {
  const name = location.hash.replace("#", "");
  return VIEWS.includes(name) ? name : "cases";
}

function goTo(name) {
  if (location.hash !== `#${name}`) location.hash = name;
  else showView(name);
}

function showView(name) {
  view = VIEWS.includes(name) ? name : "cases";
  document.body.dataset.view = view;
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.id !== `view-${view}`;
  }
  for (const tab of document.querySelectorAll("#tabs [data-view]")) {
    const on = tab.dataset.view === view;
    tab.setAttribute("aria-current", on ? "page" : "false");
  }
  renderChips();
  if (view === "board") loadBoard();
  if (view === "calendar") {
    if (!calMonth) {
      const now = (lastData && lastData.today) || new Date().toISOString().slice(0, 10);
      const [year, month] = now.split("-").map(Number);
      calMonth = { year, month };
    }
    loadMonth();
  }
  window.scrollTo({ top: 0 });
}

document.getElementById("tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-view]");
  if (tab) goTo(tab.dataset.view);
});

window.addEventListener("hashchange", () => showView(viewFromHash()));

/* --------------------------------------------------------------- reminders */

function askOnce() {
  if (!("Notification" in window)) return;
  if (localStorage.getItem(ASKED_KEY)) return;
  if (Notification.permission !== "default") {
    localStorage.setItem(ASKED_KEY, "1");
    return;
  }
  noticeEl.hidden = false;
}

function closeNotice() {
  localStorage.setItem(ASKED_KEY, "1");
  noticeEl.hidden = true;
}

document.getElementById("notice-yes").addEventListener("click", async () => {
  try { await Notification.requestPermission(); } catch { /* user said no */ }
  closeNotice();
  refresh();
});
document.getElementById("notice-no").addEventListener("click", closeNotice);

/* One browser notification per case that turns due, and no repeats. */
function announce(cases) {
  const live = new Set(cases.map((c) => c.id));
  notified = new Set([...notified].filter((id) => live.has(id)));

  if (!("Notification" in window) || Notification.permission !== "granted") {
    localStorage.setItem(NOTIFIED_KEY, JSON.stringify([...notified]));
    return;
  }
  for (const c of cases) {
    const due = c.state === "due" || c.state === "overdue";
    if (!due || !c.reminder || notified.has(c.id)) continue;
    new Notification(t("notification_title"), { body: c.reminder, tag: c.id, lang, icon: "/static/icon-192.png" });
    notified.add(c.id);
  }
  localStorage.setItem(NOTIFIED_KEY, JSON.stringify([...notified]));
}

/* ------------------------------------------------------------------ upload */

const shootEl = document.getElementById("shoot");
const cameraInput = document.getElementById("photo-camera");
const fileInput = document.getElementById("photo-file");

function showLive(job) {
  liveJob = job;
  const existing = listEl.querySelector(".slip.live");
  const fresh = buildLive(job);
  if (existing) existing.replaceWith(fresh);
  else listEl.prepend(fresh);
  emptyEl.hidden = true;
}

async function uploadPhoto(input) {
  const file = input.files[0];
  if (!file) return;
  const body = new FormData();
  body.append("photo", file);
  shootEl.dataset.busy = "1";
  goTo("cases");
  toast(t("reading"));
  try {
    const res = await api(withLang("/api/upload"), { method: "POST", body });
    const job = await res.json();
    sessionStorage.setItem(JOB_KEY, job.job);
    showLive(job);
    await followJob(job.job);
  } catch (err) {
    toast(err.message);
  } finally {
    input.value = "";
    shootEl.dataset.busy = "0";
  }
}

async function followJob(jobId) {
  for (;;) {
    let job;
    try {
      job = await json(withLang(`/api/upload/${jobId}`));
    } catch (err) {
      sessionStorage.removeItem(JOB_KEY);
      liveJob = null;
      toast(err.message);
      await refresh();
      return;
    }
    if (job.state !== "done") {
      showLive(job);
      await new Promise((r) => setTimeout(r, JOB_POLL_MS));
      continue;
    }
    /* Leave the finished ticks on screen for a moment, then let the real card take over. */
    showLive(job);
    await new Promise((r) => setTimeout(r, job.question ? 400 : 900));
    sessionStorage.removeItem(JOB_KEY);
    liveJob = null;
    if (job.question) {
      /* Unreadable photo: the agent asks instead of inventing a deadline. */
      toast(job.question, 7000);
    } else {
      const amended = job.steps.find((s) => s.tool === "match_case" && s.detail && s.detail.result === "amendment");
      const superseded = job.steps.find((s) => s.tool === "save_case");
      const n = superseded && superseded.detail && Array.isArray(superseded.detail.superseded)
        ? superseded.detail.superseded.length : 0;
      toast(amended ? t("amended", { n }) : t("saved"), amended ? 5000 : undefined);
    }
    await refresh();
    if (job.case) {
      const node = listEl.querySelector(`.slip[data-id="${job.case.id}"]`);
      if (node) {
        node.classList.add("fresh");
        node.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
    return;
  }
}

cameraInput.addEventListener("change", () => uploadPhoto(cameraInput));
fileInput.addEventListener("change", () => uploadPhoto(fileInput));

/* ----------------------------------------------------------------- actions */

listEl.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-act]");
  if (!button || button.tagName === "SELECT") return;
  const slip = button.closest(".slip");
  const id = slip.dataset.id;
  const act = button.dataset.act;

  if (act === "expand") {
    const detail = slip.querySelector('[data-f="detail"]');
    detail.hidden = !detail.hidden;
    button.textContent = detail.hidden ? t("view_original") : t("hide_original");
    const img = slip.querySelector('[data-f="crop"]');
    if (!detail.hidden && img.dataset.src && !img.src) {
      img.src = img.dataset.src;
      img.hidden = false;
    }
    return;
  }

  if (act === "copy") {
    try {
      const text = await (await api(`/api/cases/${id}/reply.txt`)).text();
      await copy(text);
      toast(t("copied"), 5000);
    } catch (err) {
      toast(err.message);
    }
    return;
  }

  if (act === "done") {
    await act_on(button, `/api/cases/${id}/done`, "POST", t("marked_done"));
    return;
  }

  if (act === "delete") {
    if (!confirm(t("confirm_delete"))) return;
    await act_on(button, `/api/cases/${id}`, "DELETE", t("deleted"));
    return;
  }

  if (act === "yes" || act === "no") {
    const body = new FormData();
    body.append("answer", act);
    await act_on(button, withLang(`/api/cases/${id}/answer`), "POST", t("thanks"), body);
    return;
  }

  if (act === "agentcore") {
    toast(t("ac_wait"), 8000);
    button.disabled = true;
    try {
      const body = await json(withLang("/api/demo/agentcore"), { method: "POST" });
      const panel = slip.querySelector('[data-f="ac"]');
      const badge = slip.querySelector('[data-f="ac-badge"]');
      const card = slip.querySelector('[data-f="ac-card"]');
      const result = body.result || body;
      badge.textContent = t("ac_badge");
      card.textContent = (result.card && result.card.text) || JSON.stringify(result, null, 2);
      panel.hidden = false;
      toast(t("ac_badge"), 5000);
    } catch (err) {
      toast(err.message || t("ac_fail"));
    }
    button.disabled = false;
  }
});

/* Which child a paper belongs to. One PATCH, no other field touched. */
listEl.addEventListener("change", async (event) => {
  const select = event.target.closest('select[data-act="child"]');
  if (!select) return;
  const id = select.closest(".slip").dataset.id;
  const childId = select.value;
  select.disabled = true;
  try {
    await api(`/api/cases/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ child_id: childId }),
    });
    const child = settings.children.find((k) => k.id === childId);
    toast(child ? t("child_saved", { n: child.name }) : t("child_cleared"));
  } catch (err) {
    toast(err.message);
  }
  await refresh();
});

async function act_on(button, path, method, message, body) {
  button.disabled = true;
  try {
    await api(path, { method, body });
    toast(message);
    await refresh();
  } catch (err) {
    toast(err.message);
    button.disabled = false;
  }
}

async function copy(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const box = document.createElement("textarea");
  box.value = text;
  box.setAttribute("readonly", "");
  box.style.position = "fixed";
  box.style.opacity = "0";
  document.body.append(box);
  box.select();
  document.execCommand("copy");
  box.remove();
}

document.getElementById("toggle-done").addEventListener("click", () => {
  includeDone = !includeDone;
  applyLanguage();
  refresh();
});

/* The header and the settings page set the same language. */
function pickLanguage(event) {
  const button = event.target.closest("[data-lang]");
  if (!button || button.dataset.lang === lang) return;
  lang = button.dataset.lang;
  langIsChosen = true;
  applyLanguage();
  refresh();
  if (view === "board") loadBoard();
  if (view === "calendar") loadMonth();
}

document.getElementById("lang").addEventListener("click", pickLanguage);
document.getElementById("s-lang").addEventListener("click", pickLanguage);

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});

/* ------------------------------------------------------------------- start */

applyLanguage();
askOnce();
showView(view);
loadSettings().then(refresh).then(() => {
  /* A reload in the middle of an upload: pick the job up again. */
  const pending = sessionStorage.getItem(JOB_KEY);
  if (pending) followJob(pending);
});
setInterval(() => { if (!document.hidden) refresh(); }, POLL_MS);

if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js").catch(() => { /* the page works without it */ });
}
