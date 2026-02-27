import test from "node:test";
import assert from "node:assert/strict";

import {
  getDashboardChannelSelection,
  initDashboardChannelInput,
  renderDashboardChannelSelection,
} from "../features/channel-control/view.js";
import { createChannelControlController } from "../features/channel-control/controller.js";
import {
  getChannelContextSnapshot,
  getObservabilitySnapshot,
} from "../features/observability/api.js";
import {
  renderChannelContextSnapshot,
  renderObservabilitySnapshot,
} from "../features/observability/view.js";
import { createObservabilityController } from "../features/observability/controller.js";
import { createControlPlaneController } from "../features/control-plane/controller.js";

class MockClassList {
  constructor(element) {
    this.element = element;
  }

  add(...tokens) {
    const next = new Set(this._read());
    tokens.filter(Boolean).forEach((token) => next.add(token));
    this.element.className = Array.from(next).join(" ").trim();
  }

  remove(...tokens) {
    const removing = new Set(tokens.filter(Boolean));
    this.element.className = this._read()
      .filter((token) => !removing.has(token))
      .join(" ")
      .trim();
  }

  contains(token) {
    return this._read().includes(token);
  }

  _read() {
    return String(this.element.className || "")
      .split(/\s+/)
      .map((token) => token.trim())
      .filter(Boolean);
  }
}

class MockElement {
  constructor(tagName = "div", ownerDocument = null) {
    this.tagName = String(tagName || "div").toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.style = {};
    this.value = "";
    this.textContent = "";
    this.innerHTML = "";
    this.disabled = false;
    this.placeholder = "";
    this.checked = false;
    this.className = "";
    this.classList = new MockClassList(this);
  }

  appendChild(child) {
    this.children.push(child);
    child.parentNode = this;
    return child;
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  dispatchEvent(event) {
    const safeEvent = event || {};
    safeEvent.target = safeEvent.target || this;
    safeEvent.currentTarget = this;
    safeEvent.preventDefault = safeEvent.preventDefault || (() => {});
    const handlers = this.listeners.get(safeEvent.type) || [];
    handlers.forEach((handler) => handler(safeEvent));
    return true;
  }

  click() {
    this.dispatchEvent({ type: "click" });
  }

  querySelectorAll() {
    return [];
  }
}

class MockDocument {
  constructor() {
    this.elements = new Map();
  }

  createElement(tagName) {
    return new MockElement(tagName, this);
  }

  getElementById(id) {
    return this.elements.get(id) || null;
  }

  registerElement(id, element = null) {
    const target = element || new MockElement("div", this);
    target.id = id;
    target.ownerDocument = this;
    this.elements.set(id, target);
    return target;
  }
}

class MockStorage {
  constructor(initialState = {}) {
    this.store = new Map(Object.entries(initialState));
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    this.store.set(key, String(value));
  }

  removeItem(key) {
    this.store.delete(key);
  }
}

function installBrowserEnv(initialStorage = {}) {
  const document = new MockDocument();
  const localStorage = new MockStorage(initialStorage);
  const windowObject = {
    localStorage,
    location: { origin: "http://localhost:8000" },
    BYTE_CONFIG: {},
    setTimeout,
    clearTimeout,
  };

  globalThis.document = document;
  globalThis.window = windowObject;
  globalThis.localStorage = localStorage;
  return { document, localStorage, window: windowObject };
}

function createChannelControlElements(document) {
  return {
    adminToken: document.registerElement(
      "adminTokenInput",
      new MockElement("input", document),
    ),
    channelInput: document.registerElement(
      "channelLoginInput",
      new MockElement("input", document),
    ),
    joinBtn: document.registerElement(
      "btnJoinChannel",
      new MockElement("button", document),
    ),
    syncBtn: document.registerElement(
      "btnSyncChannels",
      new MockElement("button", document),
    ),
    cardList: document.registerElement(
      "connectedChannelsList",
      new MockElement("ul", document),
    ),
    feedback: document.registerElement(
      "channelFeedbackMsg",
      new MockElement("p", document),
    ),
    modeChip: document.registerElement(
      "channelControlModeChip",
      new MockElement("span", document),
    ),
    modeReason: document.registerElement(
      "channelControlModeReason",
      new MockElement("p", document),
    ),
    dashboardChannelInput: document.registerElement(
      "dashboardChannelInput",
      new MockElement("input", document),
    ),
    dashboardChannelBtn: document.registerElement(
      "btnApplyDashboardChannel",
      new MockElement("button", document),
    ),
    dashboardChannelChip: document.registerElement(
      "dashboardChannelChip",
      new MockElement("span", document),
    ),
    dashboardChannelHint: document.registerElement(
      "dashboardChannelHint",
      new MockElement("p", document),
    ),
  };
}

function createObservabilityElements(document) {
  return {
    connectionState: document.registerElement(
      "connectionState",
      new MockElement("span", document),
    ),
    lastUpdate: document.registerElement(
      "lastUpdate",
      new MockElement("p", document),
    ),
    ctxSelectedChannelChip: document.registerElement(
      "ctxSelectedChannelChip",
      new MockElement("span", document),
    ),
    ctxPersistedStatusChip: document.registerElement(
      "ctxPersistedStatusChip",
      new MockElement("span", document),
    ),
    ctxRuntimeStatusChip: document.registerElement(
      "ctxRuntimeStatusChip",
      new MockElement("span", document),
    ),
    ctxPersistedGame: document.registerElement(
      "ctxPersistedGame",
      new MockElement("dd", document),
    ),
    ctxPersistedVibe: document.registerElement(
      "ctxPersistedVibe",
      new MockElement("dd", document),
    ),
    ctxPersistedLastEvent: document.registerElement(
      "ctxPersistedLastEvent",
      new MockElement("dd", document),
    ),
    ctxPersistedStyle: document.registerElement(
      "ctxPersistedStyle",
      new MockElement("dd", document),
    ),
    ctxPersistedReply: document.registerElement(
      "ctxPersistedReply",
      new MockElement("dd", document),
    ),
    ctxPersistedUpdatedAt: document.registerElement(
      "ctxPersistedUpdatedAt",
      new MockElement("dd", document),
    ),
    ctxPersistedHint: document.registerElement(
      "ctxPersistedHint",
      new MockElement("p", document),
    ),
    persistedHistoryItems: document.registerElement(
      "persistedHistoryItems",
      new MockElement("ul", document),
    ),
    contextItems: document.registerElement(
      "contextItems",
      new MockElement("ul", document),
    ),
    eventsList: document.registerElement(
      "eventsList",
      new MockElement("ul", document),
    ),
    sentimentProgressBar: document.registerElement(
      "sentimentProgressBar",
      new MockElement("div", document),
    ),
  };
}

test("channel focus input normalizes and persists dashboard selection", () => {
  const { document, localStorage } = installBrowserEnv({
    byte_dashboard_focus_channel: "old_channel",
  });
  const els = createChannelControlElements(document);
  const applied = [];

  initDashboardChannelInput(els, (channelId) => {
    applied.push(channelId);
  });

  assert.equal(els.dashboardChannelInput.value, "old_channel");
  assert.equal(els.dashboardChannelChip.textContent, "old_channel");

  els.dashboardChannelInput.value = " Canal_A ";
  els.dashboardChannelBtn.click();

  assert.deepEqual(applied, ["canal_a"]);
  assert.equal(els.dashboardChannelChip.textContent, "canal_a");
  assert.equal(
    els.dashboardChannelHint.textContent,
    "Observability, contexto e histórico persistido seguem #canal_a.",
  );
  assert.equal(localStorage.getItem("byte_dashboard_focus_channel"), "canal_a");
  assert.equal(getDashboardChannelSelection(els), "canal_a");
});

test("channel control controller propagates focused channel sync failures to feedback", async () => {
  const { document } = installBrowserEnv();
  const els = createChannelControlElements(document);
  const controller = createChannelControlController({
    ctrlEls: els,
    applyRuntimeCapabilities() {},
    getErrorMessage(error, fallback) {
      return error?.message || fallback;
    },
    onDashboardChannelChange: async () => {
      throw new Error("sync falhou");
    },
  });

  controller.bindChannelControlEvents();
  els.dashboardChannelInput.value = "Canal_B";
  els.dashboardChannelBtn.click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(controller.getSelectedDashboardChannel(), "canal_b");
  assert.match(els.feedback.textContent, /sync falhou/);
  assert.match(els.feedback.className, /event-level-error/);
});

test("observability api resolves channel-scoped endpoints", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      async json() {
        return { ok: true };
      },
    };
  };

  await getObservabilitySnapshot(" Canal_A ");
  await getChannelContextSnapshot("Canal_B");

  assert.equal(
    calls[0].url,
    "http://localhost:8000/api/observability?channel=canal_a",
  );
  assert.equal(
    calls[1].url,
    "http://localhost:8000/api/channel-context?channel=canal_b",
  );
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[1].options.method, "GET");
});

test("observability views render focused channel and persisted context state", () => {
  const { document } = installBrowserEnv();
  const els = createObservabilityElements(document);

  renderObservabilitySnapshot(
    {
      selected_channel: "canal_a",
      context: {
        channel_id: "canal_a",
        stream_vibe: "Calm",
        last_event: "Boss fight",
      },
      timestamp: "2026-02-27T14:00:00Z",
      sentiment: {
        positive: 3,
        negative: 1,
      },
    },
    els,
  );

  renderChannelContextSnapshot(
    {
      channel: {
        channel_id: "canal_a",
        runtime_loaded: true,
        has_persisted_state: true,
        has_persisted_history: true,
        persisted_state: {
          current_game: "Celeste",
          stream_vibe: "Focused",
          last_event: "PB",
          style_profile: "Fast",
          last_reply: "gg",
          updated_at: "2026-02-27T13:59:00Z",
        },
        persisted_recent_history: ["viewer: oi", "byte: salve"],
      },
    },
    els,
  );

  assert.equal(els.ctxSelectedChannelChip.textContent, "canal_a");
  assert.equal(els.ctxPersistedStatusChip.textContent, "PERSISTED READY");
  assert.equal(els.ctxRuntimeStatusChip.textContent, "RUNTIME HOT");
  assert.equal(els.ctxPersistedGame.textContent, "Celeste");
  assert.equal(els.ctxPersistedHint.className, "panel-hint event-level-info");
  assert.deepEqual(
    els.persistedHistoryItems.children.map((item) => item.textContent),
    ["viewer: oi", "byte: salve"],
  );
});

test("observability controller fetches both snapshots for the selected channel", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const obsEls = createObservabilityElements(document);
  const urls = [];

  globalThis.fetch = async (url) => {
    urls.push(url);
    if (String(url).includes("/api/channel-context")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            channel: {
              channel_id: "canal_z",
              runtime_loaded: false,
              has_persisted_state: false,
              has_persisted_history: false,
              persisted_recent_history: [],
            },
          };
        },
      };
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          ok: true,
          selected_channel: "canal_z",
          context: { channel_id: "canal_z" },
        };
      },
    };
  };

  const controller = createObservabilityController({
    obsEls,
    ctrlEls: null,
    cpEls: null,
    autEls: null,
  });

  controller.setSelectedChannel(" Canal_Z ");
  await controller.fetchAndRenderObservability();

  assert.deepEqual(urls, [
    "http://localhost:8000/api/observability?channel=canal_z",
    "http://localhost:8000/api/channel-context?channel=canal_z",
  ]);
  assert.equal(obsEls.connectionState.textContent, "Synced");
  assert.equal(obsEls.ctxSelectedChannelChip.textContent, "canal_z");
  assert.equal(obsEls.ctxRuntimeStatusChip.textContent, "RUNTIME LAZY");
});

test("control plane controller mirrors the focused channel into channel tuning", () => {
  installBrowserEnv();
  const cpEls = {
    channelIdInput: new MockElement("input"),
  };
  const controller = createControlPlaneController({
    cpEls,
    autEls: null,
    applyRuntimeCapabilities() {},
    getErrorMessage(_error, fallback) {
      return fallback;
    },
  });

  controller.setSelectedChannel(" Canal_Teste ");

  assert.equal(cpEls.channelIdInput.value, "canal_teste");
});
