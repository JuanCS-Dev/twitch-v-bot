import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { initDashboardTabs } from "../features/navigation/tabs.js";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function countMatches(text, pattern) {
  return (text.match(pattern) || []).length;
}

function extractPanel(indexHtml, panelId) {
  return (
    indexHtml.match(new RegExp(`id="${panelId}"[\\s\\S]*?<\\/section>`))?.[0] ||
    ""
  );
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
  constructor({ tabId = "", panelId = "" } = {}) {
    this.dataset = {};
    if (tabId) this.dataset.dashboardTab = tabId;
    if (panelId) this.dataset.dashboardTabPanel = panelId;
    this.classList = new MockClassList();
    this.attributes = new Map();
    this.listeners = new Map();
    this.children = [];
    this.tabIndex = -1;
    this.hidden = false;
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

  appendChild(child) {
    this.children.push(child);
    return child;
  }
}

class MockDocument {
  constructor(tabs, panels) {
    this.tabs = tabs;
    this.panels = panels;
  }

  querySelectorAll(selector) {
    if (selector === "[data-dashboard-tab]") return this.tabs;
    if (selector === "[data-dashboard-tab-panel]") return this.panels;
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
  tab.setAttribute("aria-selected", selected ? "true" : "false");
  tab.tabIndex = selected ? 0 : -1;
  return tab;
}

function createPanel(id, hidden = true) {
  const panel = new MockElement({ panelId: id });
  panel.hidden = hidden;
  return panel;
}

test("tab panels preserve expected containers and id uniqueness in index shell", () => {
  const indexHtml = readText("../index.html");

  const operationPanel = extractPanel(indexHtml, "dashboardTabOperationPanel");
  const intelligencePanel = extractPanel(
    indexHtml,
    "dashboardTabIntelligencePanel",
  );
  const clipsPanel = extractPanel(indexHtml, "dashboardTabClipsPanel");
  const analyticsPanel = extractPanel(indexHtml, "dashboardTabAnalyticsPanel");
  const configPanel = extractPanel(indexHtml, "dashboardTabConfigPanel");

  assert.ok(operationPanel.includes('id="metricsHealthContainer"'));
  assert.ok(operationPanel.includes('id="riskQueueContainer"'));
  assert.ok(operationPanel.includes('id="autonomyRuntimeContainer"'));
  assert.ok(operationPanel.includes('id="operationEventsContainer"'));
  assert.ok(intelligencePanel.includes('id="intelligencePanelContainer"'));
  assert.ok(clipsPanel.includes('id="clipsSectionContainer"'));
  assert.ok(analyticsPanel.includes('id="analyticsLogsContainer"'));
  assert.ok(configPanel.includes('id="controlPlaneContainer"'));

  const uniqueIds = [
    "metricsHealthContainer",
    "riskQueueContainer",
    "autonomyRuntimeContainer",
    "operationEventsContainer",
    "intelligencePanelContainer",
    "clipsSectionContainer",
    "analyticsLogsContainer",
    "controlPlaneContainer",
  ];
  uniqueIds.forEach((id) => {
    assert.equal(
      countMatches(indexHtml, new RegExp(`id="${id}"`, "g")),
      1,
      `${id} must remain unique in dashboard shell`,
    );
  });
});

test("tab switch toggles visibility only and keeps panel node contents", () => {
  const operationTab = createTab("operation", true);
  const analyticsTab = createTab("analytics");
  const operationPanel = createPanel("operation", false);
  const analyticsPanel = createPanel("analytics", true);
  const operationNode = { id: "metricsHealthContainer" };
  const analyticsNode = { id: "analyticsLogsContainer" };
  operationPanel.appendChild(operationNode);
  analyticsPanel.appendChild(analyticsNode);

  const tabs = initDashboardTabs({
    documentRef: new MockDocument(
      [operationTab, analyticsTab],
      [operationPanel, analyticsPanel],
    ),
    storageRef: new MockStorage(),
  });
  assert.ok(tabs);

  analyticsTab.dispatchEvent({ type: "click" });
  assert.equal(operationPanel.hidden, true);
  assert.equal(analyticsPanel.hidden, false);
  assert.equal(operationPanel.children[0], operationNode);
  assert.equal(analyticsPanel.children[0], analyticsNode);

  operationTab.dispatchEvent({ type: "click" });
  assert.equal(operationPanel.hidden, false);
  assert.equal(analyticsPanel.hidden, true);
  assert.equal(operationPanel.children[0], operationNode);
  assert.equal(analyticsPanel.children[0], analyticsNode);
});
