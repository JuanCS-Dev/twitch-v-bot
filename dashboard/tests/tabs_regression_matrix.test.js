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
    this.attributes = new Map();
    this.listeners = new Map();
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

class MockEventTarget {
  constructor() {
    this.listeners = new Map();
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
}

function createTab(id, selected = false) {
  const el = new MockElement({ tabId: id });
  el.setAttribute("aria-selected", selected ? "true" : "false");
  el.tabIndex = selected ? 0 : -1;
  return el;
}

function createPanel(id, hidden = true) {
  const el = new MockElement({ panelId: id });
  el.hidden = hidden;
  return el;
}

function createHarness({
  tabIds,
  selectedTabId = "",
  storageSeed = {},
  locationSearch = "",
  locationHash = "",
} = {}) {
  const tabs = tabIds.map((tabId) => createTab(tabId, tabId === selectedTabId));
  const panels = tabIds.map((tabId) =>
    createPanel(tabId, tabId !== selectedTabId),
  );
  const location = new MockLocation({
    search: locationSearch,
    hash: locationHash,
  });
  const history = new MockHistory(location);
  const eventTarget = new MockEventTarget();
  const storage = new MockStorage(storageSeed);
  const documentRef = new MockDocument(tabs, panels);
  const api = initDashboardTabs({
    documentRef,
    storageRef: storage,
    locationRef: location,
    historyRef: history,
    eventTargetRef: eventTarget,
  });

  return {
    api,
    tabs,
    panels,
    storage,
    location,
    history,
    eventTarget,
    tabById: new Map(
      tabs.map((tab) => [String(tab.dataset.dashboardTab), tab]),
    ),
  };
}

function assertSingleActiveState({ tabs, panels, activeTabId }) {
  const selectedTabs = tabs.filter(
    (tab) => tab.getAttribute("aria-selected") === "true",
  );
  const visiblePanels = panels.filter((panel) => panel.hidden === false);
  assert.equal(selectedTabs.length, 1);
  assert.equal(visiblePanels.length, 1);
  assert.equal(String(selectedTabs[0].dataset.dashboardTab), activeTabId);
  assert.equal(String(visiblePanels[0].dataset.dashboardTabPanel), activeTabId);

  tabs.forEach((tab) => {
    const tabId = String(tab.dataset.dashboardTab || "");
    const shouldBeActive = tabId === activeTabId;
    assert.equal(
      tab.getAttribute("aria-selected"),
      shouldBeActive ? "true" : "false",
    );
    assert.equal(tab.tabIndex, shouldBeActive ? 0 : -1);
  });

  panels.forEach((panel) => {
    const panelId = String(panel.dataset.dashboardTabPanel || "");
    const shouldBeActive = panelId === activeTabId;
    assert.equal(panel.hidden, !shouldBeActive);
    assert.equal(
      panel.getAttribute("aria-hidden"),
      shouldBeActive ? "false" : "true",
    );
  });
}

function dispatchKeyOnActiveTab(tabs, key) {
  const activeTab =
    tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || null;
  assert.ok(activeTab);
  let prevented = false;
  activeTab.dispatchEvent({
    type: "keydown",
    key,
    preventDefault() {
      prevented = true;
    },
  });
  assert.equal(prevented, true);
}

test("tabs ignore invalid query on bootstrap and fallback to persisted state", () => {
  const harness = createHarness({
    tabIds: ["operation", "analytics", "config"],
    selectedTabId: "operation",
    storageSeed: { [TAB_STORAGE_KEY]: "analytics" },
    locationSearch: "?tab=desconhecida&channel=canal_a",
    locationHash: "#live",
  });

  assert.ok(harness.api);
  assert.equal(harness.api.getActiveTab(), "analytics");
  assertSingleActiveState({
    tabs: harness.tabs,
    panels: harness.panels,
    activeTabId: "analytics",
  });
  assert.equal(harness.history.calls.length, 1);
  assert.match(harness.history.calls[0], /tab=analytics/);
  assert.match(harness.history.calls[0], /channel=canal_a/);
  assert.match(harness.history.calls[0], /#live$/);
});

test("tabs ignore invalid or missing query during popstate", () => {
  const harness = createHarness({
    tabIds: ["operation", "analytics", "config"],
    selectedTabId: "operation",
    locationSearch: "?tab=operation&channel=canal_a",
  });
  assert.ok(harness.api);

  harness.tabById.get("analytics")?.dispatchEvent({ type: "click" });
  assert.equal(harness.api.getActiveTab(), "analytics");
  assert.equal(harness.history.calls.length, 1);

  harness.location.search = "?tab=nao_existe&channel=canal_a";
  harness.eventTarget.dispatchEvent({ type: "popstate" });
  assert.equal(harness.api.getActiveTab(), "analytics");
  assert.equal(harness.storage.getItem(TAB_STORAGE_KEY), "analytics");
  assert.equal(harness.history.calls.length, 1);

  harness.location.search = "?channel=canal_a";
  harness.eventTarget.dispatchEvent({ type: "popstate" });
  assert.equal(harness.api.getActiveTab(), "analytics");
  assert.equal(harness.storage.getItem(TAB_STORAGE_KEY), "analytics");
  assert.equal(harness.history.calls.length, 1);
  assertSingleActiveState({
    tabs: harness.tabs,
    panels: harness.panels,
    activeTabId: "analytics",
  });
});

test("tabs keep invariants in deterministic navigation matrix", () => {
  const harness = createHarness({
    tabIds: ["operation", "intelligence", "clips", "analytics", "config"],
    selectedTabId: "operation",
    locationSearch: "?channel=canal_a&tab=operation",
    locationHash: "#ops",
  });
  assert.ok(harness.api);

  const steps = [
    { type: "click", tabId: "analytics", expected: "analytics" },
    { type: "key", key: "End", expected: "config" },
    { type: "key", key: "ArrowRight", expected: "operation" },
    { type: "key", key: "ArrowRight", expected: "intelligence" },
    {
      type: "popstate",
      search: "?channel=canal_a&tab=clips",
      expected: "clips",
    },
    {
      type: "popstate",
      search: "?channel=canal_a&tab=config",
      expected: "config",
    },
    { type: "key", key: "Home", expected: "operation" },
    { type: "click", tabId: "intelligence", expected: "intelligence" },
  ];

  steps.forEach((step) => {
    if (step.type === "click") {
      harness.tabById.get(step.tabId)?.dispatchEvent({ type: "click" });
    } else if (step.type === "key") {
      dispatchKeyOnActiveTab(harness.tabs, step.key);
    } else if (step.type === "popstate") {
      harness.location.search = step.search;
      harness.eventTarget.dispatchEvent({ type: "popstate" });
    }

    assert.equal(harness.api.getActiveTab(), step.expected);
    assert.equal(harness.storage.getItem(TAB_STORAGE_KEY), step.expected);
    assertSingleActiveState({
      tabs: harness.tabs,
      panels: harness.panels,
      activeTabId: step.expected,
    });
  });

  assert.equal(harness.history.calls.length, 6);
  assert.match(harness.location.search, /tab=intelligence/);
  assert.match(harness.location.search, /channel=canal_a/);
  assert.equal(harness.location.hash, "#ops");
});
