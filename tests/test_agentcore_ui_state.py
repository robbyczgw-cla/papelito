"""Behavioral regression for AgentCore state surviving card re-renders."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_agentcore_run_survives_refresh_and_stays_language_specific():
    harness = r'''
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

class FakeElement {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.children = [];
    this.handlers = {};
    this.style = {};
    this.className = "";
    this.classList = { add() {}, remove() {}, toggle() {} };
    this.selectors = new Map();
    this.parentCard = null;
  }
  addEventListener(type, callback) { this.handlers[type] = callback; }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  replaceWith() {}
  setAttribute() {}
  scrollIntoView() {}
  querySelector(selector) {
    if (!this.selectors.has(selector)) {
      const element = new FakeElement(selector.includes("select") ? "select" : "div");
      element.parentCard = this.parentCard || this;
      if (selector === '[data-f="ac"]') element.hidden = true;
      const action = selector.match(/data-act="([^"]+)"/);
      if (action) {
        element.tagName = "BUTTON";
        element.dataset.act = action[1];
      }
      this.selectors.set(selector, element);
    }
    return this.selectors.get(selector);
  }
  querySelectorAll() { return []; }
  closest(selector) {
    if (selector === "[data-act]" && this.dataset.act) return this;
    if (selector === ".slip") return this.parentCard;
    return null;
  }
}

function makeCard() {
  const card = new FakeElement("article");
  card.className = "slip";
  card.parentCard = card;
  return card;
}

const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, new FakeElement());
  return elements.get(id);
}
const list = element("list");
const template = element("slip-tpl");
template.content = { firstElementChild: { cloneNode: () => makeCard() } };
for (const id of ["live-tpl", "pin-tpl"]) {
  element(id).content = { firstElementChild: { cloneNode: () => new FakeElement() } };
}

const storage = () => ({
  values: new Map(),
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; },
  setItem(key, value) { this.values.set(key, String(value)); },
  removeItem(key) { this.values.delete(key); },
});
const document = {
  body: new FakeElement("body"),
  documentElement: new FakeElement("html"),
  hidden: false,
  title: "",
  getElementById: element,
  querySelectorAll: () => [],
  createElement: (tag) => new FakeElement(tag),
  createDocumentFragment: () => new FakeElement("fragment"),
  addEventListener() {},
  execCommand() { return true; },
};
const window = { addEventListener() {}, scrollTo() {}, isSecureContext: false };
const context = vm.createContext({
  assert,
  clearTimeout() {},
  confirm: () => true,
  console,
  document,
  fetch: async () => ({ ok: false }),
  FormData: class { append() {} },
  location: { hash: "" },
  localStorage: storage(),
  navigator: {},
  sessionStorage: storage(),
  setTimeout: () => 1,
  window,
});

const source = fs.readFileSync(process.argv[2], "utf8");
const withoutStartup = source.split("/* ------------------------------------------------------------------- start */")[0];
const checks = String.raw`
(async () => {
  const demo = {
    id: "demo-ausflug", state: "open", sender: "Kindergarten Sonnenblume",
    title: "Outing", received_label: "", paper_count: 1, amended_label: "",
    child_id: "", labels: ["what", "do", "by when", "done for you"], rows: [],
    reminder: "", question: "", has_photo: false, has_reply: false,
  };
  const data = { agentcore: true, cases: [demo], today: "2026-09-05", due_count: 0, away: null };
  const buttonOf = () => listEl.children[0].querySelector('[data-act="agentcore"]');
  const panelOf = () => listEl.children[0].querySelector('[data-f="ac"]');
  const cardText = () => listEl.children[0].querySelector('[data-f="ac-card"]').textContent;
  const badgeText = () => listEl.children[0].querySelector('[data-f="ac-badge"]').textContent;

  render(data);
  let resolveEnglish;
  json = () => new Promise((resolve) => { resolveEnglish = resolve; });
  const englishRun = listEl.handlers.click({ target: buttonOf() });
  await Promise.resolve();
  assert.strictEqual(agentcoreRuns.get("demo-ausflug:en").pending, true);

  render(data); // the 20-second refresh replaces the original button and card
  assert.strictEqual(buttonOf().disabled, true);
  resolveEnglish({ result: { card: { text: "English runtime card" } } });
  await englishRun;
  assert.strictEqual(cardText(), "English runtime card");
  assert.strictEqual(badgeText(), T.en.ac_badge);
  assert.strictEqual(panelOf().hidden, false);

  lang = "de";
  render(data);
  assert.strictEqual(buttonOf().disabled, false);
  assert.strictEqual(panelOf().hidden, true);
  let resolveGerman;
  json = () => new Promise((resolve) => { resolveGerman = resolve; });
  const germanRun = listEl.handlers.click({ target: buttonOf() });
  await Promise.resolve();
  render(data);
  assert.strictEqual(buttonOf().disabled, true);
  resolveGerman({ result: { card: { text: "Deutsche Runtime-Karte" } } });
  await germanRun;
  assert.strictEqual(cardText(), "Deutsche Runtime-Karte");
  assert.strictEqual(badgeText(), T.de.ac_badge);

  lang = "en";
  render(data);
  assert.strictEqual(cardText(), "English runtime card");
  assert.strictEqual(badgeText(), T.en.ac_badge);
})()
`;

vm.runInContext(withoutStartup + checks, context).then(
  () => process.exit(0),
  (error) => { console.error(error.stack || error); process.exit(1); },
);
'''
    completed = subprocess.run(
        ["node", "-", str(REPO / "web" / "static" / "app.js")],
        input=harness,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
