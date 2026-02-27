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
  getObservabilityHistorySnapshot,
  getObservabilitySnapshot,
} from "../features/observability/api.js";
import {
  renderChannelContextSnapshot,
  renderObservabilityHistorySnapshot,
  renderObservabilitySnapshot,
} from "../features/observability/view.js";
import { createObservabilityController } from "../features/observability/controller.js";
import { createControlPlaneController } from "../features/control-plane/controller.js";
import {
  getControlPlaneElements,
  renderAgentNotes,
} from "../features/control-plane/view.js";
import { createHudController } from "../features/hud/controller.js";

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
    rollupStateChip: document.registerElement(
      "rollupStateChip",
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
    ctxPersistedNotes: document.registerElement(
      "ctxPersistedNotes",
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
    persistedTimelineHint: document.registerElement(
      "persistedTimelineHint",
      new MockElement("p", document),
    ),
    persistedChannelTimelineBody: document.registerElement(
      "persistedChannelTimelineBody",
      new MockElement("tbody", document),
    ),
    persistedChannelComparisonBody: document.registerElement(
      "persistedChannelComparisonBody",
      new MockElement("tbody", document),
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

function createControlPlaneElements(document) {
  return {
    feedback: document.registerElement(
      "cpFeedbackMsg",
      new MockElement("p", document),
    ),
    channelStatusChip: document.registerElement(
      "cpChannelConfigStatusChip",
      new MockElement("span", document),
    ),
    channelHint: document.registerElement(
      "cpChannelConfigHint",
      new MockElement("p", document),
    ),
    channelIdInput: document.registerElement(
      "cpChannelConfigId",
      new MockElement("input", document),
    ),
    channelTemperatureInput: document.registerElement(
      "cpChannelTemperature",
      new MockElement("input", document),
    ),
    channelTopPInput: document.registerElement(
      "cpChannelTopP",
      new MockElement("input", document),
    ),
    channelAgentPausedInput: document.registerElement(
      "cpChannelAgentPaused",
      new MockElement("input", document),
    ),
    agentNotesStatusChip: document.registerElement(
      "cpAgentNotesStatusChip",
      new MockElement("span", document),
    ),
    agentNotesInput: document.registerElement(
      "cpAgentNotes",
      new MockElement("textarea", document),
    ),
    agentNotesHint: document.registerElement(
      "cpAgentNotesHint",
      new MockElement("p", document),
    ),
    loadChannelConfigBtn: document.registerElement(
      "cpLoadChannelConfigBtn",
      new MockElement("button", document),
    ),
    saveChannelConfigBtn: document.registerElement(
      "cpSaveChannelConfigBtn",
      new MockElement("button", document),
    ),
    goalsList: document.registerElement(
      "cpGoalsList",
      new MockElement("ul", document),
    ),
    suspendBtn: document.registerElement(
      "cpSuspendBtn",
      new MockElement("button", document),
    ),
    resumeBtn: document.registerElement(
      "cpResumeBtn",
      new MockElement("button", document),
    ),
    currentSuspendedState: false,
  };
}

function createHudElements(document) {
  return {
    messagesList: document.registerElement(
      "hudMessagesList",
      new MockElement("ul", document),
    ),
    messageCount: document.registerElement(
      "hudMessageCount",
      new MockElement("span", document),
    ),
    ttsToggle: document.registerElement(
      "hudTtsToggle",
      new MockElement("input", document),
    ),
    overlayLink: document.registerElement(
      "hudOverlayLink",
      new MockElement("a", document),
    ),
    overlayUrl: document.registerElement(
      "hudOverlayUrl",
      new MockElement("code", document),
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
  await getObservabilityHistorySnapshot("Canal_C", 10000, 12, 4);

  assert.equal(
    calls[0].url,
    "http://localhost:8000/api/observability?channel=canal_a",
  );
  assert.equal(
    calls[1].url,
    "http://localhost:8000/api/channel-context?channel=canal_b",
  );
  assert.equal(
    calls[2].url,
    "http://localhost:8000/api/observability/history?channel=canal_c&limit=12&compare_limit=4",
  );
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[1].options.method, "GET");
  assert.equal(calls[2].options.method, "GET");
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
      persistence: {
        enabled: true,
        restored: true,
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
        persisted_agent_notes: {
          notes: "Priorize o contexto do streamer.",
        },
        persisted_recent_history: ["viewer: oi", "byte: salve"],
      },
    },
    els,
  );

  renderObservabilityHistorySnapshot(
    {
      selected_channel: "canal_a",
      timeline: [
        {
          channel_id: "canal_a",
          captured_at: "2026-02-27T13:58:00Z",
          metrics: {
            chat_messages_total: 30,
            byte_triggers_total: 6,
            replies_total: 5,
            errors_total: 1,
          },
          chatters: {
            active_60m: 4,
          },
        },
      ],
      comparison: [
        {
          channel_id: "canal_a",
          captured_at: "2026-02-27T13:58:00Z",
          metrics: {
            chat_messages_total: 30,
            byte_triggers_total: 6,
            replies_total: 5,
          },
          chatters: {
            active_60m: 4,
          },
          agent_outcomes: {
            ignored_rate_60m: 10.5,
          },
        },
        {
          channel_id: "canal_b",
          captured_at: "2026-02-27T13:57:00Z",
          metrics: {
            chat_messages_total: 22,
            byte_triggers_total: 3,
            replies_total: 2,
          },
          chatters: {
            active_60m: 3,
          },
          agent_outcomes: {
            ignored_rate_60m: 4.2,
          },
        },
      ],
    },
    els,
  );

  assert.equal(els.ctxSelectedChannelChip.textContent, "canal_a");
  assert.equal(els.rollupStateChip.textContent, "Rollup Restored");
  assert.equal(els.ctxPersistedStatusChip.textContent, "PERSISTED READY");
  assert.equal(els.ctxRuntimeStatusChip.textContent, "RUNTIME HOT");
  assert.equal(els.ctxPersistedGame.textContent, "Celeste");
  assert.equal(
    els.ctxPersistedNotes.textContent,
    "Priorize o contexto do streamer.",
  );
  assert.equal(els.ctxPersistedHint.className, "panel-hint event-level-info");
  assert.deepEqual(
    els.persistedHistoryItems.children.map((item) => item.textContent),
    ["viewer: oi", "byte: salve"],
  );
  assert.equal(els.persistedTimelineHint.className, "panel-hint event-level-info");
  assert.equal(els.persistedChannelTimelineBody.children.length, 1);
  assert.equal(
    els.persistedChannelTimelineBody.children[0].children[1].textContent,
    "30",
  );
  assert.equal(els.persistedChannelComparisonBody.children.length, 2);
  assert.equal(
    els.persistedChannelComparisonBody.children[0].children[0].textContent,
    "canal_a (focused)",
  );
});

test("observability controller fetches observability, context and history for the selected channel", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const obsEls = createObservabilityElements(document);
  const urls = [];

  globalThis.fetch = async (url) => {
    urls.push(url);
    if (String(url).includes("/api/observability/history")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            selected_channel: "canal_z",
            timeline: [
              {
                channel_id: "canal_z",
                captured_at: "2026-02-27T13:40:00Z",
                metrics: { chat_messages_total: 12 },
                chatters: { active_60m: 2 },
              },
            ],
            comparison: [],
          };
        },
      };
    }
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
    "http://localhost:8000/api/observability/history?channel=canal_z&limit=24&compare_limit=6",
  ]);
  assert.equal(obsEls.connectionState.textContent, "Synced");
  assert.equal(obsEls.ctxSelectedChannelChip.textContent, "canal_z");
  assert.equal(obsEls.ctxRuntimeStatusChip.textContent, "RUNTIME LAZY");
  assert.equal(obsEls.persistedChannelTimelineBody.children.length, 1);
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

test("control plane controller warns when loading directives without a channel", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const cpEls = createControlPlaneElements(document);
  cpEls.channelIdInput = null;

  const controller = createControlPlaneController({
    cpEls,
    autEls: null,
    applyRuntimeCapabilities() {},
    getErrorMessage(error, fallback) {
      return error?.message || fallback;
    },
  });

  await controller.loadChannelConfig(true);

  assert.match(cpEls.feedback.textContent, /carregar directives/i);
});

test("control plane controller loads channel directives including agent notes", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const cpEls = createControlPlaneElements(document);
  cpEls.channelIdInput.value = "Canal_A";

  globalThis.fetch = async (url) => {
    if (String(url).includes("/api/agent-notes")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            note: {
              channel_id: "canal_a",
              notes: "Priorize o host.",
              has_notes: true,
              updated_at: "2026-02-27T19:00:00Z",
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
          channel: {
            channel_id: "canal_a",
            temperature: 0.22,
            top_p: 0.73,
            agent_paused: true,
            has_override: true,
            updated_at: "2026-02-27T19:00:00Z",
          },
        };
      },
    };
  };

  const controller = createControlPlaneController({
    cpEls,
    autEls: null,
    applyRuntimeCapabilities() {},
    getErrorMessage(error, fallback) {
      return error?.message || fallback;
    },
  });

  await controller.loadChannelConfig(true);

  assert.equal(cpEls.channelTemperatureInput.value, "0.22");
  assert.equal(cpEls.channelTopPInput.value, "0.73");
  assert.equal(cpEls.channelAgentPausedInput.checked, true);
  assert.equal(cpEls.channelStatusChip.textContent, "CHANNEL PAUSED");
  assert.equal(cpEls.agentNotesInput.value, "Priorize o host.");
  assert.equal(cpEls.agentNotesStatusChip.textContent, "NOTES ACTIVE");
  assert.match(cpEls.feedback.textContent, /sincronizados/i);
});

test("control plane controller surfaces directive load errors", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const cpEls = createControlPlaneElements(document);
  cpEls.channelIdInput.value = "Canal_C";

  globalThis.fetch = async () => {
    throw new Error("falha remota");
  };

  const controller = createControlPlaneController({
    cpEls,
    autEls: null,
    applyRuntimeCapabilities() {},
    getErrorMessage(error, fallback) {
      return error?.message || fallback;
    },
  });

  await controller.loadChannelConfig(true);

  assert.match(cpEls.feedback.textContent, /falha remota/i);
  assert.equal(cpEls.feedback.className, "panel-hint event-level-error");
});

test("control plane controller saves channel directives including agent notes", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const cpEls = createControlPlaneElements(document);
  cpEls.channelIdInput.value = "Canal_B";
  cpEls.channelTemperatureInput.value = "0.35";
  cpEls.channelTopPInput.value = "0.81";
  cpEls.channelAgentPausedInput.checked = true;
  cpEls.agentNotesInput.value = "Evite insistir em dica repetida.";
  const calls = [];

  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), options });
    if (String(url).includes("/api/agent-notes")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            note: {
              channel_id: "canal_b",
              notes: "Evite insistir em dica repetida.",
              has_notes: true,
              updated_at: "2026-02-27T19:05:00Z",
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
          channel: {
            channel_id: "canal_b",
            temperature: 0.35,
            top_p: 0.81,
            agent_paused: true,
            has_override: true,
            updated_at: "2026-02-27T19:05:00Z",
          },
        };
      },
    };
  };

  const controller = createControlPlaneController({
    cpEls,
    autEls: null,
    applyRuntimeCapabilities() {},
    getErrorMessage(error, fallback) {
      return error?.message || fallback;
    },
  });

  controller.bindControlPlaneEvents();
  cpEls.saveChannelConfigBtn.click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(calls.length, 2);
  assert.ok(calls.some((call) => call.url.includes("/api/channel-config")));
  assert.ok(calls.some((call) => call.url.includes("/api/agent-notes")));
  const channelConfigCall = calls.find((call) =>
    call.url.includes("/api/channel-config"),
  );
  assert.equal(
    JSON.parse(String(channelConfigCall?.options?.body || "{}")).agent_paused,
    true,
  );
  assert.equal(cpEls.agentNotesStatusChip.textContent, "NOTES ACTIVE");
  assert.match(cpEls.feedback.textContent, /salvos com sucesso/i);
});

test("control plane controller surfaces directive save errors", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const cpEls = createControlPlaneElements(document);
  cpEls.channelIdInput.value = "Canal_D";
  cpEls.agentNotesInput.value = "Segura a ironia.";

  globalThis.fetch = async (url) => {
    if (String(url).includes("/api/agent-notes")) {
      throw new Error("save notes failed");
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          ok: true,
          channel: {
            channel_id: "canal_d",
            temperature: null,
            top_p: null,
            agent_paused: false,
            has_override: false,
            updated_at: "2026-02-27T19:10:00Z",
          },
        };
      },
    };
  };

  const controller = createControlPlaneController({
    cpEls,
    autEls: null,
    applyRuntimeCapabilities() {},
    getErrorMessage(error, fallback) {
      return error?.message || fallback;
    },
  });

  controller.bindControlPlaneEvents();
  cpEls.saveChannelConfigBtn.click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(cpEls.feedback.textContent, /save notes failed/i);
  assert.equal(cpEls.feedback.className, "panel-hint event-level-error");
});

test("control plane view renders cleared agent notes state", () => {
  const { document } = installBrowserEnv();
  const cpEls = createControlPlaneElements(document);

  renderAgentNotes(
    {
      channel_id: "Canal_E",
      notes: "",
      has_notes: false,
      updated_at: "",
    },
    cpEls,
  );

  assert.equal(cpEls.agentNotesInput.value, "");
  assert.equal(cpEls.agentNotesStatusChip.textContent, "NOTES CLEAR");
  assert.match(
    cpEls.agentNotesHint.textContent,
    /sem notes operacionais persistidas/i,
  );
});

test("control plane view reads agent note elements from the dashboard DOM", () => {
  const { document } = installBrowserEnv();
  document.registerElement("cpPanel", new MockElement("section", document));
  document.registerElement("cpModeChip", new MockElement("span", document));
  document.registerElement(
    "cpAgentStatusChip",
    new MockElement("span", document),
  );
  document.registerElement("cpAgentStatusHint", new MockElement("p", document));
  document.registerElement(
    "cpCapabilitiesLine",
    new MockElement("p", document),
  );
  document.registerElement(
    "cpResponseContract",
    new MockElement("p", document),
  );
  document.registerElement("cpFeedbackMsg", new MockElement("p", document));
  document.registerElement(
    "cpChannelConfigStatusChip",
    new MockElement("span", document),
  );
  document.registerElement(
    "cpChannelConfigHint",
    new MockElement("p", document),
  );
  document.registerElement(
    "cpChannelConfigId",
    new MockElement("input", document),
  );
  document.registerElement(
    "cpChannelTemperature",
    new MockElement("input", document),
  );
  document.registerElement("cpChannelTopP", new MockElement("input", document));
  document.registerElement(
    "cpChannelAgentPaused",
    new MockElement("input", document),
  );
  document.registerElement(
    "cpAgentNotesStatusChip",
    new MockElement("span", document),
  );
  document.registerElement(
    "cpAgentNotes",
    new MockElement("textarea", document),
  );
  document.registerElement("cpAgentNotesHint", new MockElement("p", document));
  document.registerElement(
    "cpLoadChannelConfigBtn",
    new MockElement("button", document),
  );
  document.registerElement(
    "cpSaveChannelConfigBtn",
    new MockElement("button", document),
  );
  document.registerElement(
    "cpAutonomyEnabled",
    new MockElement("input", document),
  );
  document.registerElement(
    "cpHeartbeatInterval",
    new MockElement("input", document),
  );
  document.registerElement("cpMinCooldown", new MockElement("input", document));
  document.registerElement("cpBudget10m", new MockElement("input", document));
  document.registerElement("cpBudget60m", new MockElement("input", document));
  document.registerElement("cpBudgetDaily", new MockElement("input", document));
  document.registerElement(
    "cpActionIgnoreAfter",
    new MockElement("input", document),
  );
  document.registerElement("cpGoalsList", new MockElement("ul", document));
  document.registerElement("cpAddGoalBtn", new MockElement("button", document));
  document.registerElement("cpSaveBtn", new MockElement("button", document));
  document.registerElement("cpReloadBtn", new MockElement("button", document));
  document.registerElement("cpSuspendBtn", new MockElement("button", document));
  document.registerElement("cpResumeBtn", new MockElement("button", document));

  const els = getControlPlaneElements();

  assert.equal(els.agentNotesInput?.id, "cpAgentNotes");
  assert.equal(els.agentNotesStatusChip?.id, "cpAgentNotesStatusChip");
  assert.equal(els.agentNotesHint?.id, "cpAgentNotesHint");
  assert.equal(els.channelAgentPausedInput?.id, "cpChannelAgentPaused");
});

test("hud controller syncs overlay url with the active admin token", () => {
  const { document, localStorage, window } = installBrowserEnv({
    byte_dashboard_admin_token: "local-token",
  });
  const tokenInput = document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const hudEls = createHudElements(document);
  const controller = createHudController({ hudEls });

  controller.bindEvents();

  assert.equal(
    hudEls.overlayLink.href,
    "http://localhost:8000/dashboard/hud?auth=local-token",
  );
  assert.equal(
    hudEls.overlayUrl.textContent,
    "http://localhost:8000/dashboard/hud?auth=local-token",
  );

  window.BYTE_CONFIG.adminToken = "server-token";
  tokenInput.value = "dom-token";
  tokenInput.dispatchEvent({ type: "input" });

  assert.equal(
    hudEls.overlayLink.href,
    "http://localhost:8000/dashboard/hud?auth=dom-token",
  );

  tokenInput.value = "";
  localStorage.removeItem("byte_dashboard_admin_token");
  tokenInput.dispatchEvent({ type: "change" });

  assert.equal(
    hudEls.overlayLink.href,
    "http://localhost:8000/dashboard/hud?auth=server-token",
  );
});
