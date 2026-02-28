import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { initDashboardTabs } from "../features/navigation/tabs.js";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

class MockClassList {
  constructor() {
    this.tokens = new Set();
  }

  add(...tokens) {
    tokens.filter(Boolean).forEach((token) => this.tokens.add(token));
  }

  remove(...tokens) {
    tokens.filter(Boolean).forEach((token) => this.tokens.delete(token));
  }

  toggle(token, force) {
    if (force === true) {
      this.tokens.add(token);
      return true;
    }
    if (force === false) {
      this.tokens.delete(token);
      return false;
    }
    if (this.tokens.has(token)) {
      this.tokens.delete(token);
      return false;
    }
    this.tokens.add(token);
    return true;
  }
}

class MockElement {
  constructor({ tabId = "", panelTabId = "" } = {}) {
    this.dataset = {};
    if (tabId) this.dataset.dashboardTab = tabId;
    if (panelTabId) this.dataset.dashboardTabPanel = panelTabId;
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new MockClassList();
    this.tabIndex = -1;
    this.hidden = false;
    this.focused = false;
  }

  setAttribute(name, value) {
    this.attributes.set(String(name), String(value));
  }

  getAttribute(name) {
    return this.attributes.get(String(name)) || null;
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  dispatchEvent(event) {
    const handlers = this.listeners.get(String(event?.type || "")) || [];
    handlers.forEach((handler) => handler(event));
  }

  focus() {
    this.focused = true;
  }
}

class MockDocument {
  constructor(tabs, panels) {
    this.tabs = tabs;
    this.panels = panels;
  }

  querySelectorAll(selector) {
    if (selector === "[data-dashboard-tab]") {
      return this.tabs;
    }
    if (selector === "[data-dashboard-tab-panel]") {
      return this.panels;
    }
    return [];
  }
}

class MockStorage {
  getItem() {
    return null;
  }

  setItem() {
    // no-op
  }
}

function createTab(id, selected = false) {
  const tab = new MockElement({ tabId: id });
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", selected ? "true" : "false");
  tab.tabIndex = selected ? 0 : -1;
  return tab;
}

function createPanel(tabId, hidden = true) {
  const panel = new MockElement({ panelTabId: tabId });
  panel.setAttribute("role", "tabpanel");
  panel.hidden = hidden;
  return panel;
}

test("tab markup keeps aria wiring in index shell", () => {
  const indexHtml = readText("../index.html");
  const tabPairs = [
    ["dashboardTabOperationBtn", "dashboardTabOperationPanel"],
    ["dashboardTabIntelligenceBtn", "dashboardTabIntelligencePanel"],
    ["dashboardTabClipsBtn", "dashboardTabClipsPanel"],
    ["dashboardTabAnalyticsBtn", "dashboardTabAnalyticsPanel"],
    ["dashboardTabConfigBtn", "dashboardTabConfigPanel"],
  ];

  tabPairs.forEach(([buttonId, panelId]) => {
    const buttonBlock =
      indexHtml.match(
        new RegExp(`<button[\\s\\S]*?id="${buttonId}"[\\s\\S]*?<\\/button>`),
      )?.[0] || "";
    const panelBlock =
      indexHtml.match(
        new RegExp(`<section[\\s\\S]*?id="${panelId}"[\\s\\S]*?<\\/section>`),
      )?.[0] || "";

    assert.match(buttonBlock, /role="tab"/);
    assert.match(buttonBlock, new RegExp(`aria-controls="${panelId}"`));
    assert.match(panelBlock, /role="tabpanel"/);
    assert.match(panelBlock, new RegExp(`aria-labelledby="${buttonId}"`));
  });
});

test("tab navigation keeps aria-selected, aria-hidden and keyboard semantics", () => {
  const operationTab = createTab("operation", true);
  const analyticsTab = createTab("analytics");
  const configTab = createTab("config");
  const operationPanel = createPanel("operation", false);
  const analyticsPanel = createPanel("analytics", true);
  const configPanel = createPanel("config", true);
  const tabs = initDashboardTabs({
    documentRef: new MockDocument(
      [operationTab, analyticsTab, configTab],
      [operationPanel, analyticsPanel, configPanel],
    ),
    storageRef: new MockStorage(),
  });

  assert.ok(tabs);
  assert.equal(operationTab.getAttribute("aria-selected"), "true");
  assert.equal(analyticsTab.getAttribute("aria-selected"), "false");
  assert.equal(operationPanel.getAttribute("aria-hidden"), "false");
  assert.equal(analyticsPanel.getAttribute("aria-hidden"), "true");

  let prevented = false;
  operationTab.dispatchEvent({
    type: "keydown",
    key: "ArrowRight",
    preventDefault() {
      prevented = true;
    },
  });
  assert.equal(prevented, true);
  assert.equal(tabs.getActiveTab(), "analytics");
  assert.equal(analyticsTab.getAttribute("aria-selected"), "true");
  assert.equal(analyticsPanel.hidden, false);
  assert.equal(analyticsPanel.getAttribute("aria-hidden"), "false");
  assert.equal(operationPanel.hidden, true);
  assert.equal(operationPanel.getAttribute("aria-hidden"), "true");

  analyticsTab.dispatchEvent({
    type: "keydown",
    key: "End",
    preventDefault() {},
  });
  assert.equal(tabs.getActiveTab(), "config");
  assert.equal(configTab.focused, true);

  configTab.dispatchEvent({
    type: "keydown",
    key: "Home",
    preventDefault() {},
  });
  assert.equal(tabs.getActiveTab(), "operation");
});

test("tab initialization is idempotent for the same document", () => {
  const doc = new MockDocument(
    [createTab("operation", true)],
    [createPanel("operation", false)],
  );
  const storage = new MockStorage();
  const first = initDashboardTabs({ documentRef: doc, storageRef: storage });
  const second = initDashboardTabs({ documentRef: doc, storageRef: storage });

  assert.ok(first);
  assert.equal(first, second);
});
