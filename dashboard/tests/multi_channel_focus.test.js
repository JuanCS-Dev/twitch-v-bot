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
  getPostStreamReportSnapshot,
  getSemanticMemorySnapshot,
  getObservabilitySnapshot,
  getSentimentScoresSnapshot,
  upsertSemanticMemoryEntry,
} from "../features/observability/api.js";
import {
  renderChannelContextSnapshot,
  renderObservabilityHistorySnapshot,
  renderPostStreamReportSnapshot,
  renderSemanticMemorySnapshot,
  renderObservabilitySnapshot,
} from "../features/observability/view.js";
import { createObservabilityController } from "../features/observability/controller.js";
import { createControlPlaneController } from "../features/control-plane/controller.js";
import {
  collectChannelConfigPayload,
  collectControlPlanePayload,
  getControlPlaneElements,
  renderChannelConfig,
  renderAgentNotes,
} from "../features/control-plane/view.js";
import { createHudController } from "../features/hud/controller.js";
import { renderHudMessages } from "../features/hud/view.js";

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

function createGoalFieldStub({ value = "", checked = false } = {}) {
  return { value: String(value), checked: Boolean(checked) };
}

function createGoalCardStub(fieldValues = {}) {
  return {
    querySelector(selector) {
      const match = String(selector || "").match(
        /\[data-goal-field="([^"]+)"\]/,
      );
      if (!match) return null;
      const fieldName = match[1];
      return fieldValues[fieldName] || null;
    },
  };
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
    analyticsQuickInsightHint: document.registerElement(
      "analyticsQuickInsightHint",
      new MockElement("p", document),
    ),
    analyticsQuickFocusedChannel: document.registerElement(
      "analyticsQuickFocusedChannel",
      new MockElement("span", document),
    ),
    analyticsQuickRuntimeChip: document.registerElement(
      "analyticsQuickRuntimeChip",
      new MockElement("span", document),
    ),
    analyticsQuickPersistenceChip: document.registerElement(
      "analyticsQuickPersistenceChip",
      new MockElement("span", document),
    ),
    analyticsQuickHealthScore: document.registerElement(
      "analyticsQuickHealthScore",
      new MockElement("span", document),
    ),
    analyticsQuickHealthBandChip: document.registerElement(
      "analyticsQuickHealthBandChip",
      new MockElement("span", document),
    ),
    analyticsQuickIgnoredRate: document.registerElement(
      "analyticsQuickIgnoredRate",
      new MockElement("span", document),
    ),
    analyticsQuickMessagesPerMinute: document.registerElement(
      "analyticsQuickMessagesPerMinute",
      new MockElement("span", document),
    ),
    analyticsQuickTriggerRate: document.registerElement(
      "analyticsQuickTriggerRate",
      new MockElement("span", document),
    ),
    analyticsQuickCost60m: document.registerElement(
      "analyticsQuickCost60m",
      new MockElement("span", document),
    ),
    analyticsQuickErrors: document.registerElement(
      "analyticsQuickErrors",
      new MockElement("span", document),
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
    mStreamHealthScore: document.registerElement(
      "mStreamHealthScore",
      new MockElement("dd", document),
    ),
    mStreamHealthBand: document.registerElement(
      "mStreamHealthBand",
      new MockElement("dd", document),
    ),
    ctxStreamHealthScore: document.registerElement(
      "ctxStreamHealthScore",
      new MockElement("dd", document),
    ),
    ctxStreamHealthBand: document.registerElement(
      "ctxStreamHealthBand",
      new MockElement("dd", document),
    ),
    intStreamHealthScore: document.registerElement(
      "intStreamHealthScore",
      new MockElement("dd", document),
    ),
    intStreamHealthBand: document.registerElement(
      "intStreamHealthBand",
      new MockElement("dd", document),
    ),
    intCoachingRiskChip: document.registerElement(
      "intCoachingRiskChip",
      new MockElement("span", document),
    ),
    intCoachingHudStatus: document.registerElement(
      "intCoachingHudStatus",
      new MockElement("p", document),
    ),
    intCoachingRiskScore: document.registerElement(
      "intCoachingRiskScore",
      new MockElement("dd", document),
    ),
    intCoachingLastEmission: document.registerElement(
      "intCoachingLastEmission",
      new MockElement("dd", document),
    ),
    intCoachingHint: document.registerElement(
      "intCoachingHint",
      new MockElement("p", document),
    ),
    intCoachingAlerts: document.registerElement(
      "intCoachingAlerts",
      new MockElement("ul", document),
    ),
    sentimentProgressBar: document.registerElement(
      "sentimentProgressBar",
      new MockElement("div", document),
    ),
    intPostStreamStatusChip: document.registerElement(
      "intPostStreamStatusChip",
      new MockElement("span", document),
    ),
    intPostStreamGeneratedAt: document.registerElement(
      "intPostStreamGeneratedAt",
      new MockElement("dd", document),
    ),
    intPostStreamTrigger: document.registerElement(
      "intPostStreamTrigger",
      new MockElement("dd", document),
    ),
    intPostStreamSummary: document.registerElement(
      "intPostStreamSummary",
      new MockElement("p", document),
    ),
    intPostStreamRecommendations: document.registerElement(
      "intPostStreamRecommendations",
      new MockElement("ul", document),
    ),
    intPostStreamGenerateBtn: document.registerElement(
      "intPostStreamGenerateBtn",
      new MockElement("button", document),
    ),
    intSemanticMemoryStatusHint: document.registerElement(
      "intSemanticMemoryStatusHint",
      new MockElement("p", document),
    ),
    intSemanticMemoryQueryInput: document.registerElement(
      "intSemanticMemoryQueryInput",
      new MockElement("input", document),
    ),
    intSemanticMemorySearchBtn: document.registerElement(
      "intSemanticMemorySearchBtn",
      new MockElement("button", document),
    ),
    intSemanticMemoryTypeInput: document.registerElement(
      "intSemanticMemoryTypeInput",
      new MockElement("input", document),
    ),
    intSemanticMemoryTagsInput: document.registerElement(
      "intSemanticMemoryTagsInput",
      new MockElement("input", document),
    ),
    intSemanticMemoryContentInput: document.registerElement(
      "intSemanticMemoryContentInput",
      new MockElement("input", document),
    ),
    intSemanticMemorySaveBtn: document.registerElement(
      "intSemanticMemorySaveBtn",
      new MockElement("button", document),
    ),
    intSemanticMemoryMatches: document.registerElement(
      "intSemanticMemoryMatches",
      new MockElement("ul", document),
    ),
    intSemanticMemoryEntries: document.registerElement(
      "intSemanticMemoryEntries",
      new MockElement("ul", document),
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
    channelIdentityStatusChip: document.registerElement(
      "cpChannelIdentityStatusChip",
      new MockElement("span", document),
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
    channelPersonaNameInput: document.registerElement(
      "cpChannelPersonaName",
      new MockElement("input", document),
    ),
    channelToneInput: document.registerElement(
      "cpChannelTone",
      new MockElement("input", document),
    ),
    channelEmoteVocabInput: document.registerElement(
      "cpChannelEmoteVocab",
      new MockElement("input", document),
    ),
    channelLoreInput: document.registerElement(
      "cpChannelLore",
      new MockElement("textarea", document),
    ),
    channelIdentityHint: document.registerElement(
      "cpChannelIdentityHint",
      new MockElement("p", document),
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
    "Observability, context and persisted history now follow #canal_a.",
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
  await getSentimentScoresSnapshot("Canal_D");
  await getPostStreamReportSnapshot("Canal_E", 10000, true);
  await getSemanticMemorySnapshot("Canal_F", 10000, "meta", 7, 40);
  await upsertSemanticMemoryEntry({
    channel_id: "canal_f",
    content: "Viewer prefere lore sem spoiler.",
    memory_type: "preference",
    tags: "lore,spoiler",
  });

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
  assert.equal(
    calls[3].url,
    "http://localhost:8000/api/sentiment/scores?channel=canal_d",
  );
  assert.equal(
    calls[4].url,
    "http://localhost:8000/api/observability/post-stream-report?channel=canal_e&generate=1",
  );
  assert.equal(
    calls[5].url,
    "http://localhost:8000/api/semantic-memory?channel=canal_f&query=meta&limit=7&search_limit=40",
  );
  assert.equal(calls[6].url, "http://localhost:8000/api/semantic-memory");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[1].options.method, "GET");
  assert.equal(calls[2].options.method, "GET");
  assert.equal(calls[3].options.method, "GET");
  assert.equal(calls[4].options.method, "GET");
  assert.equal(calls[5].options.method, "GET");
  assert.equal(calls[6].options.method, "PUT");
  assert.equal(
    JSON.parse(String(calls[6].options.body)).memory_type,
    "preference",
  );
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
      stream_health: {
        score: 40,
        band: "critical",
      },
      coaching: {
        risk_score: 72,
        risk_band: "high",
        has_alerts: true,
        alerts: [
          {
            id: "chat_velocity_drop",
            severity: "critical",
            title: "Queda de ritmo no chat",
            message: "Ritmo em 10m caiu para 0.06 msg/min.",
            tactic: "Dispare CTA curto com resposta em ate 20s.",
          },
        ],
        hud: {
          emitted: true,
          suppressed: false,
          last_emitted_at: "2026-02-27T14:00:10Z",
        },
      },
    },
    els,
    {
      sentiment: {
        vibe: "Hyped",
        avg: 1.6,
        count: 8,
        positive: 6,
        negative: 1,
      },
      stream_health: {
        score: 91,
        band: "excellent",
      },
    },
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
          stream_health: {
            score: 74,
            band: "stable",
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
          stream_health: {
            score: 88,
            band: "excellent",
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
          stream_health: {
            score: 52,
            band: "watch",
          },
        },
      ],
    },
    els,
  );
  renderPostStreamReportSnapshot(
    {
      ok: true,
      selected_channel: "canal_a",
      has_report: true,
      generated: false,
      report: {
        generated_at: "2026-02-27T14:01:00Z",
        trigger: "auto_part_success",
        narrative: "Canal #canal_a encerrou com stream health 88/100.",
        recommendations: [
          "Reduzir backlog pendente da action queue.",
          "Aplicar teto operacional de custo por hora.",
        ],
      },
    },
    els,
  );
  renderSemanticMemorySnapshot(
    {
      ok: true,
      selected_channel: "canal_a",
      query: "lore",
      has_entries: true,
      has_matches: true,
      entries: [
        {
          entry_id: "mem_1",
          memory_type: "fact",
          content: "Streamer joga modo hardcore.",
          tags: ["game", "hardcore"],
        },
      ],
      matches: [
        {
          entry_id: "mem_2",
          memory_type: "preference",
          content: "Evitar spoiler de lore no chat.",
          tags: ["lore", "spoiler"],
          similarity: 0.934,
        },
      ],
    },
    els,
  );

  assert.equal(els.ctxSelectedChannelChip.textContent, "canal_a");
  assert.equal(els.rollupStateChip.textContent, "Rollup Restored");
  assert.equal(els.ctxPersistedStatusChip.textContent, "PERSISTED READY");
  assert.equal(els.ctxRuntimeStatusChip.textContent, "RUNTIME HOT");
  assert.equal(els.analyticsQuickFocusedChannel.textContent, "canal_a");
  assert.equal(els.analyticsQuickRuntimeChip.textContent, "RUNTIME HOT");
  assert.equal(
    els.analyticsQuickPersistenceChip.textContent,
    "PERSISTED READY",
  );
  assert.equal(els.analyticsQuickHealthScore.textContent, "91/100");
  assert.equal(els.analyticsQuickHealthBandChip.textContent, "EXCELLENT");
  assert.equal(els.analyticsQuickIgnoredRate.textContent, "IGNORED 0.0%");
  assert.equal(
    els.analyticsQuickMessagesPerMinute.textContent,
    "0.00 / 0.00 mpm",
  );
  assert.equal(
    els.analyticsQuickTriggerRate.textContent,
    "0.0% trigger rate (60m)",
  );
  assert.equal(els.analyticsQuickCost60m.textContent, "$0.0000");
  assert.equal(els.analyticsQuickErrors.textContent, "0 errors");
  assert.match(els.analyticsQuickInsightHint.textContent, /#canal_a/i);
  assert.equal(els.mStreamHealthScore.textContent, "91");
  assert.equal(els.mStreamHealthBand.textContent, "Excellent");
  assert.equal(els.ctxStreamHealthScore.textContent, "91/100");
  assert.equal(els.ctxStreamHealthBand.textContent, "Excellent");
  assert.equal(els.intStreamHealthScore.textContent, "91/100");
  assert.equal(els.intStreamHealthBand.textContent, "Excellent");
  assert.equal(els.intCoachingRiskChip.textContent, "CHURN HIGH");
  assert.match(els.intCoachingRiskChip.className, /warn/);
  assert.equal(els.intCoachingRiskScore.textContent, "72/100");
  assert.equal(els.intCoachingLastEmission.textContent, "2026-02-27T14:00:10Z");
  assert.match(els.intCoachingHudStatus.textContent, /emitted/i);
  assert.equal(els.intCoachingHint.className, "panel-hint event-level-warn");
  assert.equal(els.intCoachingAlerts.children.length, 1);
  assert.match(els.intCoachingAlerts.children[0].textContent, /\[CRITICAL\]/);
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
  assert.equal(
    els.persistedTimelineHint.className,
    "panel-hint event-level-info",
  );
  assert.equal(els.persistedChannelTimelineBody.children.length, 1);
  assert.equal(
    els.persistedChannelTimelineBody.children[0].children[1].textContent,
    "30",
  );
  assert.equal(
    els.persistedChannelTimelineBody.children[0].children[6].textContent,
    "74 (Stable)",
  );
  assert.equal(els.persistedChannelComparisonBody.children.length, 2);
  assert.equal(
    els.persistedChannelComparisonBody.children[0].children[0].textContent,
    "canal_a (focused)",
  );
  assert.equal(
    els.persistedChannelComparisonBody.children[0].children[6].textContent,
    "88 (Excellent)",
  );
  assert.equal(els.intPostStreamStatusChip.textContent, "REPORT READY");
  assert.equal(
    els.intPostStreamGeneratedAt.textContent,
    "2026-02-27T14:01:00Z",
  );
  assert.equal(els.intPostStreamTrigger.textContent, "auto part success");
  assert.match(els.intPostStreamSummary.textContent, /Canal #canal_a/);
  assert.equal(els.intPostStreamRecommendations.children.length, 2);
  assert.match(
    els.intSemanticMemoryStatusHint.textContent,
    /Semantic search active in #canal_a/i,
  );
  assert.equal(els.intSemanticMemoryMatches.children.length, 1);
  assert.match(
    els.intSemanticMemoryMatches.children[0].textContent,
    /\[preference\]/i,
  );
  assert.match(
    els.intSemanticMemoryEntries.children[0].textContent,
    /hardcore/i,
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
    if (String(url).includes("/api/sentiment/scores")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            sentiment: {
              vibe: "Hyped",
              avg: 1.3,
              count: 10,
              positive: 7,
              negative: 2,
            },
            stream_health: {
              score: 84,
              band: "stable",
            },
          };
        },
      };
    }
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
    if (String(url).includes("/api/observability/post-stream-report")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            selected_channel: "canal_z",
            has_report: true,
            generated: false,
            report: {
              generated_at: "2026-02-27T13:45:00Z",
              trigger: "manual_dashboard",
              narrative: "Resumo pos-live de canal_z",
              recommendations: ["Reforcar CTA no inicio da live."],
            },
          };
        },
      };
    }
    if (String(url).includes("/api/semantic-memory")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            selected_channel: "canal_z",
            query: "",
            has_entries: true,
            has_matches: true,
            entries: [
              {
                entry_id: "mem_a",
                memory_type: "fact",
                content: "Canal z prioriza game indie.",
                tags: ["game", "indie"],
              },
            ],
            matches: [
              {
                entry_id: "mem_a",
                memory_type: "fact",
                content: "Canal z prioriza game indie.",
                tags: ["game", "indie"],
                similarity: 0.87,
              },
            ],
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
    "http://localhost:8000/api/sentiment/scores?channel=canal_z",
    "http://localhost:8000/api/observability?channel=canal_z",
    "http://localhost:8000/api/channel-context?channel=canal_z",
    "http://localhost:8000/api/observability/history?channel=canal_z&limit=24&compare_limit=6",
    "http://localhost:8000/api/observability/post-stream-report?channel=canal_z",
    "http://localhost:8000/api/semantic-memory?channel=canal_z&limit=8&search_limit=60",
    "http://localhost:8000/api/observability/conversions?channel=canal_z&limit=20",
  ]);
  assert.equal(obsEls.connectionState.textContent, "Synced");
  assert.equal(obsEls.ctxSelectedChannelChip.textContent, "canal_z");
  assert.equal(obsEls.ctxRuntimeStatusChip.textContent, "RUNTIME LAZY");
  assert.equal(obsEls.analyticsQuickFocusedChannel.textContent, "canal_z");
  assert.equal(obsEls.analyticsQuickRuntimeChip.textContent, "RUNTIME LAZY");
  assert.equal(obsEls.analyticsQuickPersistenceChip.textContent, "NO SNAPSHOT");
  assert.match(
    obsEls.analyticsQuickInsightHint.textContent,
    /partial persisted/i,
  );
  assert.equal(obsEls.mStreamHealthScore.textContent, "84");
  assert.equal(obsEls.intStreamHealthBand.textContent, "Stable");
  assert.equal(obsEls.persistedChannelTimelineBody.children.length, 1);
  assert.equal(obsEls.intPostStreamStatusChip.textContent, "REPORT READY");
  assert.match(obsEls.intPostStreamSummary.textContent, /canal_z/i);
  assert.match(obsEls.intSemanticMemoryStatusHint.textContent, /loaded/i);
  assert.equal(obsEls.intSemanticMemoryEntries.children.length, 1);
});

test("observability controller triggers manual post-stream generation from intelligence panel", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const obsEls = createObservabilityElements(document);
  const urls = [];

  globalThis.fetch = async (url) => {
    const safeUrl = String(url);
    urls.push(safeUrl);
    if (safeUrl.includes("/api/observability/post-stream-report?")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            selected_channel: "canal_manual",
            has_report: true,
            generated: true,
            report: {
              generated_at: "2026-02-27T20:00:00Z",
              trigger: "manual_dashboard",
              narrative: "Resumo pos-live manual.",
              recommendations: ["Ajustar ritmo inicial da proxima live."],
            },
          };
        },
      };
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return { ok: true };
      },
    };
  };

  const controller = createObservabilityController({
    obsEls,
    ctrlEls: null,
    cpEls: null,
    autEls: null,
  });
  controller.setSelectedChannel("Canal_Manual");
  controller.bindObservabilityEvents();

  obsEls.intPostStreamGenerateBtn.click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.ok(
    urls.includes(
      "http://localhost:8000/api/observability/post-stream-report?channel=canal_manual&generate=1",
    ),
  );
  assert.equal(obsEls.intPostStreamStatusChip.textContent, "REPORT UPDATED");
  assert.equal(obsEls.intPostStreamTrigger.textContent, "manual dashboard");
});

test("observability controller triggers semantic memory search and save in intelligence panel", async () => {
  const { document } = installBrowserEnv();
  document.registerElement(
    "adminTokenInput",
    new MockElement("input", document),
  );
  const obsEls = createObservabilityElements(document);
  const calls = [];

  globalThis.fetch = async (url, options = {}) => {
    const safeUrl = String(url);
    const method = String(options?.method || "GET").toUpperCase();
    calls.push({ url: safeUrl, method, body: options?.body || "" });

    if (safeUrl.includes("/api/semantic-memory") && method === "PUT") {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            entry: {
              channel_id: "canal_mem",
              memory_type: "preference",
              content: "Nao spoiler de lore.",
            },
          };
        },
      };
    }

    if (safeUrl.includes("/api/semantic-memory")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            selected_channel: "canal_mem",
            query: "lore",
            has_entries: true,
            has_matches: true,
            entries: [
              {
                entry_id: "m1",
                memory_type: "preference",
                content: "Nao spoiler de lore.",
                tags: ["lore", "chat"],
              },
            ],
            matches: [
              {
                entry_id: "m1",
                memory_type: "preference",
                content: "Nao spoiler de lore.",
                tags: ["lore", "chat"],
                similarity: 0.941,
              },
            ],
          };
        },
      };
    }

    return {
      ok: true,
      status: 200,
      async json() {
        return { ok: true };
      },
    };
  };

  const controller = createObservabilityController({
    obsEls,
    ctrlEls: null,
    cpEls: null,
    autEls: null,
  });
  controller.setSelectedChannel("Canal_Mem");
  controller.bindObservabilityEvents();

  obsEls.intSemanticMemoryQueryInput.value = "lore";
  obsEls.intSemanticMemorySearchBtn.click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  obsEls.intSemanticMemoryTypeInput.value = "preference";
  obsEls.intSemanticMemoryTagsInput.value = "lore,chat";
  obsEls.intSemanticMemoryContentInput.value = "Nao spoiler de lore.";
  obsEls.intSemanticMemorySaveBtn.click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  const searchCall = calls.find(
    (call) =>
      call.method === "GET" &&
      call.url.includes("/api/semantic-memory?channel=canal_mem&query=lore"),
  );
  assert.ok(searchCall);

  const saveCall = calls.find(
    (call) =>
      call.method === "PUT" && call.url.includes("/api/semantic-memory"),
  );
  assert.ok(saveCall);
  const savePayload = JSON.parse(String(saveCall?.body || "{}"));
  assert.equal(savePayload.channel_id, "canal_mem");
  assert.equal(savePayload.memory_type, "preference");
  assert.equal(savePayload.content, "Nao spoiler de lore.");
  assert.equal(obsEls.intSemanticMemoryContentInput.value, "");
  assert.match(
    obsEls.intSemanticMemoryStatusHint.textContent,
    /semantic search/i,
  );
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

  assert.match(cpEls.feedback.textContent, /load directives/i);
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
  assert.match(cpEls.feedback.textContent, /synced/i);
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
  assert.match(cpEls.feedback.textContent, /saved successfully/i);
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

test("control plane payload includes KPI contract and clip_candidate risk", () => {
  const { document } = installBrowserEnv();
  const cpEls = createControlPlaneElements(document);

  const goalCard = createGoalCardStub({
    enabled: createGoalFieldStub({ checked: true }),
    id: createGoalFieldStub({ value: "Goal Clip" }),
    name: createGoalFieldStub({ value: "Clip Radar" }),
    prompt: createGoalFieldStub({ value: "Detecte momentos clipaveis." }),
    risk: createGoalFieldStub({ value: "clip_candidate" }),
    interval_seconds: createGoalFieldStub({ value: "480" }),
    kpi_name: createGoalFieldStub({ value: "clip_candidate_queued" }),
    target_value: createGoalFieldStub({ value: "2.5" }),
    window_minutes: createGoalFieldStub({ value: "45" }),
    comparison: createGoalFieldStub({ value: "gte" }),
  });
  cpEls.goalsList.querySelectorAll = () => [goalCard];

  const payload = collectControlPlanePayload(cpEls);
  const [goal] = payload.goals;

  assert.equal(goal.id, "goal_clip");
  assert.equal(goal.risk, "clip_candidate");
  assert.equal(goal.kpi_name, "clip_candidate_queued");
  assert.equal(goal.target_value, 2.5);
  assert.equal(goal.window_minutes, 45);
  assert.equal(goal.comparison, "gte");
});

test("control plane payload normalizes invalid KPI contract values", () => {
  const { document } = installBrowserEnv();
  const cpEls = createControlPlaneElements(document);

  const goalCard = createGoalCardStub({
    enabled: createGoalFieldStub({ checked: true }),
    id: createGoalFieldStub({ value: "goal auto" }),
    name: createGoalFieldStub({ value: "Auto Goal" }),
    prompt: createGoalFieldStub({ value: "Atue no chat." }),
    risk: createGoalFieldStub({ value: "auto_chat" }),
    interval_seconds: createGoalFieldStub({ value: "15" }),
    kpi_name: createGoalFieldStub({ value: "unknown_metric" }),
    target_value: createGoalFieldStub({ value: "-10" }),
    window_minutes: createGoalFieldStub({ value: "5000" }),
    comparison: createGoalFieldStub({ value: "invalid" }),
  });
  cpEls.goalsList.querySelectorAll = () => [goalCard];

  const payload = collectControlPlanePayload(cpEls);
  const [goal] = payload.goals;

  assert.equal(goal.risk, "auto_chat");
  assert.equal(goal.kpi_name, "auto_chat_sent");
  assert.equal(goal.target_value, 0);
  assert.equal(goal.window_minutes, 1440);
  assert.equal(goal.interval_seconds, 60);
  assert.equal(goal.comparison, "gte");
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
    /no persisted operational notes/i,
  );
});

test("control plane view renders per-channel identity fields", () => {
  const { document } = installBrowserEnv();
  const cpEls = createControlPlaneElements(document);

  renderChannelConfig(
    {
      channel_id: "canal_id",
      temperature: 0.44,
      top_p: 0.73,
      agent_paused: false,
      has_override: true,
      updated_at: "2026-02-27T19:00:00Z",
      persona_name: "Byte Coach",
      tone: "analitico e objetivo",
      emote_vocab: ["PogChamp", "LUL"],
      lore: "Lore principal do canal.",
      has_identity: true,
      identity_updated_at: "2026-02-27T19:01:00Z",
    },
    cpEls,
  );

  assert.equal(cpEls.channelPersonaNameInput.value, "Byte Coach");
  assert.equal(cpEls.channelToneInput.value, "analitico e objetivo");
  assert.equal(cpEls.channelEmoteVocabInput.value, "PogChamp, LUL");
  assert.equal(cpEls.channelLoreInput.value, "Lore principal do canal.");
  assert.equal(cpEls.channelIdentityStatusChip.textContent, "IDENTITY ACTIVE");
  assert.match(cpEls.channelIdentityHint.textContent, /persona: Byte Coach/i);
});

test("control plane view collects identity payload with token normalization", () => {
  const { document } = installBrowserEnv();
  const cpEls = createControlPlaneElements(document);

  cpEls.channelIdInput.value = " Canal_X ";
  cpEls.channelTemperatureInput.value = "0.55";
  cpEls.channelTopPInput.value = "0.80";
  cpEls.channelAgentPausedInput.checked = true;
  cpEls.channelPersonaNameInput.value = "Byte Coach";
  cpEls.channelToneInput.value = "analitico";
  cpEls.channelEmoteVocabInput.value = "PogChamp, LUL, pogchamp, , Kappa";
  cpEls.channelLoreInput.value = "Lore ativo.";

  const payload = collectChannelConfigPayload(cpEls);

  assert.deepEqual(payload, {
    channel_id: "canal_x",
    temperature: 0.55,
    top_p: 0.8,
    agent_paused: true,
    persona_name: "Byte Coach",
    tone: "analitico",
    emote_vocab: ["PogChamp", "LUL", "Kappa"],
    lore: "Lore ativo.",
  });
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
    "cpChannelIdentityStatusChip",
    new MockElement("span", document),
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
    "cpChannelPersonaName",
    new MockElement("input", document),
  );
  document.registerElement("cpChannelTone", new MockElement("input", document));
  document.registerElement(
    "cpChannelEmoteVocab",
    new MockElement("input", document),
  );
  document.registerElement(
    "cpChannelLore",
    new MockElement("textarea", document),
  );
  document.registerElement(
    "cpChannelIdentityHint",
    new MockElement("p", document),
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
  assert.equal(els.channelPersonaNameInput?.id, "cpChannelPersonaName");
  assert.equal(els.channelToneInput?.id, "cpChannelTone");
  assert.equal(els.channelEmoteVocabInput?.id, "cpChannelEmoteVocab");
  assert.equal(els.channelLoreInput?.id, "cpChannelLore");
  assert.equal(
    els.channelIdentityStatusChip?.id,
    "cpChannelIdentityStatusChip",
  );
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

test("hud view renders coaching source with warn chip", () => {
  const { document } = installBrowserEnv();
  const hudEls = createHudElements(document);

  renderHudMessages(
    [
      {
        ts: 1_770_000_000,
        source: "coaching",
        text: "Ative CTA no proximo bloco.",
      },
    ],
    hudEls,
  );

  assert.equal(hudEls.messageCount.textContent, "1");
  assert.match(hudEls.messagesList.innerHTML, /chip warn/i);
});
