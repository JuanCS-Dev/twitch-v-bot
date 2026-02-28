import assert from "node:assert/strict";
import test from "node:test";

import { initDashboardTabs } from "../features/navigation/tabs.js";

const TAB_STORAGE_KEY = "byte_dashboard_active_tab";

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

  contains(token) {
    return this.tokens.has(token);
  }
}

class MockElement {
  constructor({ tabId = "", panelId = "" } = {}) {
    this.dataset = {};
    if (tabId) {
      this.dataset.dashboardTab = tabId;
    }
    if (panelId) {
      this.dataset.dashboardTabPanel = panelId;
    }
    this.classList = new MockClassList();
    this.listeners = new Map();
    this.attributes = new Map();
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
  constructor(tabs = [], panels = []) {
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
  constructor(seed = {}) {
    this.store = new Map(Object.entries(seed));
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    this.store.set(key, String(value));
  }
}

class MockLocation {
  constructor({ pathname = "/dashboard", search = "", hash = "" } = {}) {
    this.pathname = pathname;
    this.search = search;
    this.hash = hash;
  }
}

class MockHistory {
  constructor(locationRef) {
    this.locationRef = locationRef;
    this.calls = [];
  }

  replaceState(_state, _title, relativeUrl) {
    this.calls.push(String(relativeUrl));
    const nextUrl = String(relativeUrl || "");
    const [pathWithQuery, hash = ""] = nextUrl.split("#", 2);
    const queryIndex = pathWithQuery.indexOf("?");
    this.locationRef.pathname =
      queryIndex >= 0 ? pathWithQuery.slice(0, queryIndex) : pathWithQuery;
    this.locationRef.search =
      queryIndex >= 0 ? pathWithQuery.slice(queryIndex) : "";
    this.locationRef.hash = hash ? `#${hash}` : "";
  }
}

function createTab(id, selected = false) {
  const el = new MockElement({ tabId: id });
  if (selected) {
    el.setAttribute("aria-selected", "true");
    el.classList.add("is-active");
    el.tabIndex = 0;
  } else {
    el.setAttribute("aria-selected", "false");
  }
  return el;
}

function createPanel(id, hidden = true) {
  const el = new MockElement({ panelId: id });
  el.hidden = hidden;
  return el;
}

test("dashboard tabs initialize with first tab active by default", () => {
  const operationTab = createTab("operation", true);
  const analyticsTab = createTab("analytics");
  const operationPanel = createPanel("operation", false);
  const analyticsPanel = createPanel("analytics", true);
  const doc = new MockDocument(
    [operationTab, analyticsTab],
    [operationPanel, analyticsPanel],
  );

  const tabs = initDashboardTabs({
    documentRef: doc,
    storageRef: new MockStorage(),
  });

  assert.ok(tabs);
  assert.equal(tabs.getActiveTab(), "operation");
  assert.equal(operationTab.getAttribute("aria-selected"), "true");
  assert.equal(analyticsTab.getAttribute("aria-selected"), "false");
  assert.equal(operationPanel.hidden, false);
  assert.equal(analyticsPanel.hidden, true);
});

test("dashboard tabs restore persisted tab id from localStorage", () => {
  const operationTab = createTab("operation", true);
  const analyticsTab = createTab("analytics");
  const operationPanel = createPanel("operation", false);
  const analyticsPanel = createPanel("analytics", true);
  const storage = new MockStorage({ [TAB_STORAGE_KEY]: "analytics" });
  const doc = new MockDocument(
    [operationTab, analyticsTab],
    [operationPanel, analyticsPanel],
  );

  const tabs = initDashboardTabs({ documentRef: doc, storageRef: storage });

  assert.ok(tabs);
  assert.equal(tabs.getActiveTab(), "analytics");
  assert.equal(operationPanel.hidden, true);
  assert.equal(analyticsPanel.hidden, false);
  assert.equal(operationTab.getAttribute("aria-selected"), "false");
  assert.equal(analyticsTab.getAttribute("aria-selected"), "true");
});

test("dashboard tabs click updates active panel and persists tab id", () => {
  const operationTab = createTab("operation", true);
  const intelligenceTab = createTab("intelligence");
  const operationPanel = createPanel("operation", false);
  const intelligencePanel = createPanel("intelligence", true);
  const storage = new MockStorage();
  const doc = new MockDocument(
    [operationTab, intelligenceTab],
    [operationPanel, intelligencePanel],
  );

  const tabs = initDashboardTabs({ documentRef: doc, storageRef: storage });
  intelligenceTab.dispatchEvent({ type: "click" });

  assert.ok(tabs);
  assert.equal(tabs.getActiveTab(), "intelligence");
  assert.equal(operationPanel.hidden, true);
  assert.equal(intelligencePanel.hidden, false);
  assert.equal(storage.getItem(TAB_STORAGE_KEY), "intelligence");
});

test("dashboard tabs keyboard navigation wraps and focuses target tab", () => {
  const operationTab = createTab("operation", true);
  const analyticsTab = createTab("analytics");
  const configTab = createTab("config");
  const operationPanel = createPanel("operation", false);
  const analyticsPanel = createPanel("analytics", true);
  const configPanel = createPanel("config", true);
  const doc = new MockDocument(
    [operationTab, analyticsTab, configTab],
    [operationPanel, analyticsPanel, configPanel],
  );

  const tabs = initDashboardTabs({
    documentRef: doc,
    storageRef: new MockStorage(),
  });
  let prevented = false;
  operationTab.dispatchEvent({
    type: "keydown",
    key: "ArrowLeft",
    preventDefault() {
      prevented = true;
    },
  });

  assert.ok(tabs);
  assert.equal(prevented, true);
  assert.equal(tabs.getActiveTab(), "config");
  assert.equal(configPanel.hidden, false);
  assert.equal(configTab.focused, true);
});

test("dashboard tabs prioritize URL tab query over localStorage", () => {
  const operationTab = createTab("operation", true);
  const analyticsTab = createTab("analytics");
  const configTab = createTab("config");
  const operationPanel = createPanel("operation", false);
  const analyticsPanel = createPanel("analytics", true);
  const configPanel = createPanel("config", true);
  const storage = new MockStorage({ [TAB_STORAGE_KEY]: "analytics" });
  const location = new MockLocation({ search: "?tab=config" });
  const history = new MockHistory(location);

  const tabs = initDashboardTabs({
    documentRef: new MockDocument(
      [operationTab, analyticsTab, configTab],
      [operationPanel, analyticsPanel, configPanel],
    ),
    storageRef: storage,
    locationRef: location,
    historyRef: history,
  });

  assert.ok(tabs);
  assert.equal(tabs.getActiveTab(), "config");
  assert.equal(configPanel.hidden, false);
  assert.equal(analyticsPanel.hidden, true);
  assert.equal(history.calls.length, 0);
});

test("dashboard tabs sync active tab into URL query without losing existing params", () => {
  const operationTab = createTab("operation", true);
  const intelligenceTab = createTab("intelligence");
  const operationPanel = createPanel("operation", false);
  const intelligencePanel = createPanel("intelligence", true);
  const location = new MockLocation({ search: "?channel=canal_a" });
  const history = new MockHistory(location);

  const tabs = initDashboardTabs({
    documentRef: new MockDocument(
      [operationTab, intelligenceTab],
      [operationPanel, intelligencePanel],
    ),
    storageRef: new MockStorage(),
    locationRef: location,
    historyRef: history,
  });
  intelligenceTab.dispatchEvent({ type: "click" });

  assert.ok(tabs);
  assert.equal(tabs.getActiveTab(), "intelligence");
  assert.equal(history.calls.length, 2);
  assert.match(history.calls[0], /\?channel=canal_a&tab=operation/);
  assert.match(history.calls[1], /\?channel=canal_a&tab=intelligence/);
  assert.match(location.search, /channel=canal_a/);
  assert.match(location.search, /tab=intelligence/);
});
