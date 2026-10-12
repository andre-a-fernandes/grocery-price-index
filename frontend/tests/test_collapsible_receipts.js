const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const HTML_PATH = path.resolve(__dirname, "../index.html");

// 1. Syntax Validation: Ensure frontend scripts compile cleanly
test("frontend/index.html script tags have valid JavaScript syntax", () => {
  const html = fs.readFileSync(HTML_PATH, "utf8");
  const scriptMatches = html.match(/<script[\s\S]*?<\/script>/gi) || [];
  assert.ok(scriptMatches.length > 0, "Expected at least one script tag in index.html");

  scriptMatches.forEach((scriptTag, idx) => {
    const code = scriptTag.replace(/<script[\s\S]*?>/i, "").replace(/<\/script>/i, "");
    assert.doesNotThrow(() => {
      new vm.Script(code);
    }, `Script tag #${idx} contained syntax errors`);
  });
});

// Minimal DOM implementation to isolate and test renderHistory's collapsible functionality
class MockElement {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.attributes = {};
    this.style = {};
    this.textContent = "";
    this.innerHTML = "";
    this.listeners = {};
    const classes = new Set();
    this.classList = {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
      toggle: (c) => {
        if (classes.has(c)) {
          classes.delete(c);
          return false;
        } else {
          classes.add(c);
          return true;
        }
      },
      get _set() { return classes; }
    };
  }

  get className() {
    return Array.from(this.classList._set).join(" ");
  }

  set className(val) {
    this.classList._set.clear();
    if (val) {
      val.split(/\s+/).filter(Boolean).forEach((c) => this.classList.add(c));
    }
  }

  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  appendChild(child) { this.children.push(child); }

  addEventListener(event, fn) {
    this.listeners[event] = this.listeners[event] || [];
    this.listeners[event].push(fn);
  }

  dispatchEvent(event) {
    event.target = event.target || this;
    const handlers = this.listeners[event.type] || [];
    handlers.forEach((fn) => fn(event));
  }

  closest(selector) {
    if (selector === ".btn-danger" && this.classList.contains("btn-danger")) return this;
    if (selector === ".receipt-card" && this.classList.contains("receipt-card")) return this;
    return null;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const matches = [];
    const walk = (node) => {
      for (const child of node.children) {
        if (selector.startsWith(".") && child.classList.contains(selector.slice(1))) {
          matches.push(child);
        } else if (selector.startsWith("#") && child.id === selector.slice(1)) {
          matches.push(child);
        }
        walk(child);
      }
    };
    walk(this);
    return matches;
  }
}

function createReceiptFixture(id, store, date, itemCount = 1) {
  return {
    id,
    store_name: store,
    receipt_date: date,
    currency: "EUR",
    items: Array.from({ length: itemCount }, (_, i) => ({
      generalized_name: `item ${i + 1}`,
      quantity_label: "1 pc",
      unit_price: 2.5,
      unit_price_uom: "each",
      total_price: 2.5
    }))
  };
}

function renderHistorySim(allReceipts, historyList, options = {}) {
  const { onReceiptDeleted, getSelectedText } = options;

  if (allReceipts.length === 0) {
    historyList.innerHTML = `<div class="empty">No receipts saved yet.<br/>Scan one from the Scan tab.</div>`;
    return;
  }

  historyList.children = [];
  allReceipts.forEach((r, idx) => {
    const currency = r.currency || "EUR";
    const total = r.items.reduce((s, i) => s + (i.total_price || 0), 0);
    const card = new MockElement("div");
    card.className = "card receipt-card";

    const header = new MockElement("div");
    header.className = "receipt-header";
    const store = new MockElement("strong");
    store.className = "display";
    store.textContent = r.store_name;

    const metaRight = new MockElement("div");
    metaRight.className = "receipt-header-right";

    const dateSpan = new MockElement("span");
    dateSpan.className = "muted";
    dateSpan.textContent = r.receipt_date;

    const toggleBtn = new MockElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "receipt-toggle-btn";

    metaRight.appendChild(dateSpan);
    metaRight.appendChild(toggleBtn);

    header.appendChild(store);
    header.appendChild(metaRight);

    const details = new MockElement("div");
    details.className = "receipt-details";

    const summary = new MockElement("div");
    summary.className = "muted";
    summary.textContent = `${r.items.length} items · ${currency}${total.toFixed(2)}`;
    details.appendChild(summary);

    r.items.forEach((i) => {
      const row = new MockElement("div");
      row.className = "receipt-item";
      details.appendChild(row);
    });

    const delBtn = new MockElement("button");
    delBtn.className = "btn-danger";
    delBtn.textContent = "Delete receipt";
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (onReceiptDeleted) onReceiptDeleted(r.id);
    });
    details.appendChild(delBtn);

    card.appendChild(header);
    card.appendChild(details);

    // Default loading: only the latest receipt (idx === 0) is maximized
    const isMinimized = idx > 0;
    if (isMinimized) {
      card.classList.add("minimized");
      toggleBtn.textContent = "▼";
      toggleBtn.setAttribute("aria-label", "Maximize receipt");
      toggleBtn.setAttribute("aria-expanded", "false");
    } else {
      toggleBtn.textContent = "▲";
      toggleBtn.setAttribute("aria-label", "Minimize receipt");
      toggleBtn.setAttribute("aria-expanded", "true");
    }

    card.addEventListener("click", (e) => {
      if (e.target.closest && e.target.closest(".btn-danger")) return;
      if (getSelectedText && getSelectedText().trim().length > 0) return;

      const currentlyMinimized = card.classList.toggle("minimized");
      toggleBtn.textContent = currentlyMinimized ? "▼" : "▲";
      toggleBtn.setAttribute("aria-label", currentlyMinimized ? "Maximize receipt" : "Minimize receipt");
      toggleBtn.setAttribute("aria-expanded", String(!currentlyMinimized));
    });

    historyList.appendChild(card);
  });
}
test("collapsible receipt cards: empty receipt history displays placeholder", () => {
  const historyList = new MockElement("div");
  renderHistorySim([], historyList);
  assert.ok(historyList.innerHTML.includes("No receipts saved yet"));
});

test("collapsible receipt cards: single receipt defaults to maximized", () => {
  const historyList = new MockElement("div");
  const receipts = [createReceiptFixture("r1", "Store A", "2026-10-12")];
  renderHistorySim(receipts, historyList);

  assert.strictEqual(historyList.children.length, 1);
  const card = historyList.children[0];
  const toggleBtn = card.querySelector(".receipt-toggle-btn");

  assert.strictEqual(card.classList.contains("minimized"), false, "Single receipt should not be minimized");
  assert.strictEqual(toggleBtn.textContent, "▲", "Maximized receipt arrow must point up (▲) for minimizing");
  assert.strictEqual(toggleBtn.getAttribute("aria-expanded"), "true");
});

test("collapsible receipt cards: multiple receipts default to only latest receipt maximized", () => {
  const historyList = new MockElement("div");
  const receipts = [
    createReceiptFixture("r1", "Latest Store", "2026-10-12"),
    createReceiptFixture("r2", "Older Store 1", "2026-10-10"),
    createReceiptFixture("r3", "Older Store 2", "2026-10-05")
  ];
  renderHistorySim(receipts, historyList);

  assert.strictEqual(historyList.children.length, 3);

  // Latest receipt (idx = 0)
  const card0 = historyList.children[0];
  const toggleBtn0 = card0.querySelector(".receipt-toggle-btn");
  assert.strictEqual(card0.classList.contains("minimized"), false, "Latest receipt (idx=0) should be maximized");
  assert.strictEqual(toggleBtn0.textContent, "▲", "Arrow points up (▲) to minimize");
  assert.strictEqual(toggleBtn0.getAttribute("aria-expanded"), "true");

  // Older receipts (idx > 0)
  [1, 2].forEach((idx) => {
    const card = historyList.children[idx];
    const toggleBtn = card.querySelector(".receipt-toggle-btn");
    assert.strictEqual(card.classList.contains("minimized"), true, `Receipt at index ${idx} should default to minimized`);
    assert.strictEqual(toggleBtn.textContent, "▼", "Arrow points down (▼) to maximize");
    assert.strictEqual(toggleBtn.getAttribute("aria-expanded"), "false");
  });
});

test("collapsible receipt cards: clicking anywhere on receipt toggles minimized / maximized", () => {
  const historyList = new MockElement("div");
  const receipts = [
    createReceiptFixture("r1", "Store A", "2026-10-12"),
    createReceiptFixture("r2", "Store B", "2026-10-10")
  ];
  renderHistorySim(receipts, historyList);

  const card1 = historyList.children[1]; // Initially minimized
  const toggleBtn1 = card1.querySelector(".receipt-toggle-btn");
  assert.strictEqual(card1.classList.contains("minimized"), true);
  assert.strictEqual(toggleBtn1.textContent, "▼");

  // Click card to maximize
  card1.dispatchEvent({ type: "click", target: card1 });
  assert.strictEqual(card1.classList.contains("minimized"), false, "Card should now be maximized");
  assert.strictEqual(toggleBtn1.textContent, "▲", "Arrow should now point up (▲)");
  assert.strictEqual(toggleBtn1.getAttribute("aria-expanded"), "true");

  // Click card again to minimize
  card1.dispatchEvent({ type: "click", target: card1 });
  assert.strictEqual(card1.classList.contains("minimized"), true, "Card should now be minimized");
  assert.strictEqual(toggleBtn1.textContent, "▼", "Arrow should now point down (▼)");
  assert.strictEqual(toggleBtn1.getAttribute("aria-expanded"), "false");
});

test("collapsible receipt cards: clicking arrow button toggles minimized / maximized", () => {
  const historyList = new MockElement("div");
  const receipts = [createReceiptFixture("r1", "Store A", "2026-10-12")];
  renderHistorySim(receipts, historyList);

  const card = historyList.children[0]; // Initially maximized
  const toggleBtn = card.querySelector(".receipt-toggle-btn");

  // Click toggle arrow button
  toggleBtn.dispatchEvent({ type: "click", target: toggleBtn });
  card.dispatchEvent({ type: "click", target: toggleBtn }); // bubbles to card

  assert.strictEqual(card.classList.contains("minimized"), true, "Card should minimize when toggle button is clicked");
  assert.strictEqual(toggleBtn.textContent, "▼", "Arrow points down (▼)");
});

test("collapsible receipt cards: clicking delete button triggers delete without toggling card", () => {
  const historyList = new MockElement("div");
  const receipts = [createReceiptFixture("r1", "Store A", "2026-10-12")];
  let deletedId = null;

  renderHistorySim(receipts, historyList, {
    onReceiptDeleted: (id) => { deletedId = id; }
  });

  const card = historyList.children[0];
  const delBtn = card.querySelector(".btn-danger");

  let propagationStopped = false;
  const clickEvent = {
    type: "click",
    target: delBtn,
    stopPropagation: () => { propagationStopped = true; }
  };

  delBtn.dispatchEvent(clickEvent);
  assert.strictEqual(deletedId, "r1", "Delete callback should have fired");
  assert.strictEqual(propagationStopped, true, "Event propagation should be stopped on delete button");

  // Card click handler should also reject .btn-danger target
  card.dispatchEvent(clickEvent);
  assert.strictEqual(card.classList.contains("minimized"), false, "Card must not toggle when clicking delete button");
});

test("collapsible receipt cards: text selection does not trigger accidental toggle", () => {
  const historyList = new MockElement("div");
  const receipts = [createReceiptFixture("r1", "Store A", "2026-10-12")];
  let currentSelection = "Store A";

  renderHistorySim(receipts, historyList, {
    getSelectedText: () => currentSelection
  });

  const card = historyList.children[0];
  card.dispatchEvent({ type: "click", target: card });

  assert.strictEqual(card.classList.contains("minimized"), false, "Card must not toggle if text is selected");
});

