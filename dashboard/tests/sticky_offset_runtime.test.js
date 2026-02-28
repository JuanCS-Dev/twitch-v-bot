import assert from "node:assert/strict";
import test from "node:test";

import { initDashboardStickyOffset } from "../features/navigation/sticky-offset.js";

class MockStyle {
  constructor() {
    this.values = new Map();
  }

  setProperty(name, value) {
    this.values.set(String(name), String(value));
  }

  getPropertyValue(name) {
    return this.values.get(String(name)) || "";
  }
}

class MockWindow {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  removeEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    this.listeners.set(
      type,
      handlers.filter((candidate) => candidate !== handler),
    );
  }

  dispatchEvent(type) {
    const handlers = this.listeners.get(type) || [];
    handlers.forEach((handler) => handler({ type }));
  }
}

class MockTopbar {
  constructor(height) {
    this.height = height;
  }

  getBoundingClientRect() {
    return { height: this.height };
  }
}

class MockDocument {
  constructor({ topbar = null, tabsShell = null, rootStyle = null } = {}) {
    this.topbar = topbar;
    this.tabsShell = tabsShell;
    this.documentElement = {
      style: rootStyle || new MockStyle(),
    };
  }

  querySelector(selector) {
    if (selector === ".topbar") {
      return this.topbar;
    }
    if (selector === ".dashboard-tabs-shell") {
      return this.tabsShell;
    }
    return null;
  }
}

test("sticky offset tracks topbar height through resize events", () => {
  const topbar = new MockTopbar(88.2);
  const tabsShell = {};
  const rootStyle = new MockStyle();
  const windowRef = new MockWindow();
  const documentRef = new MockDocument({ topbar, tabsShell, rootStyle });

  const cleanup = initDashboardStickyOffset({ documentRef, windowRef });
  assert.equal(
    rootStyle.getPropertyValue("--dashboard-tabs-sticky-top"),
    "89px",
  );

  topbar.height = 131.1;
  windowRef.dispatchEvent("resize");
  assert.equal(
    rootStyle.getPropertyValue("--dashboard-tabs-sticky-top"),
    "132px",
  );

  cleanup();
  assert.equal((windowRef.listeners.get("resize") || []).length, 0);
  assert.equal((windowRef.listeners.get("orientationchange") || []).length, 0);
});

test("sticky offset updates via ResizeObserver callback when available", () => {
  const topbar = new MockTopbar(64);
  const tabsShell = {};
  const rootStyle = new MockStyle();
  const documentRef = new MockDocument({ topbar, tabsShell, rootStyle });
  let observerCallback = null;
  let disconnectCalls = 0;
  let observedTarget = null;

  const cleanup = initDashboardStickyOffset({
    documentRef,
    windowRef: null,
    resizeObserverFactory(callback) {
      observerCallback = callback;
      return {
        observe(target) {
          observedTarget = target;
        },
        disconnect() {
          disconnectCalls += 1;
        },
      };
    },
  });

  assert.equal(observedTarget, topbar);
  assert.equal(
    rootStyle.getPropertyValue("--dashboard-tabs-sticky-top"),
    "64px",
  );

  topbar.height = 99;
  observerCallback?.();
  assert.equal(
    rootStyle.getPropertyValue("--dashboard-tabs-sticky-top"),
    "99px",
  );

  cleanup();
  assert.equal(disconnectCalls, 1);
});
