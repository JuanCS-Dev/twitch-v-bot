import assert from "node:assert/strict";
import test from "node:test";

import { renderActionQueuePayload } from "../features/action-queue/view.js";
import { renderAutonomyRuntime } from "../features/autonomy/view.js";
import {
  renderChannelContextSnapshot,
  renderObservabilitySnapshot,
} from "../features/observability/view.js";

class MockClassList {
  constructor(element) {
    this.element = element;
  }

  add(...tokens) {
    const next = new Set(this.#readTokens());
    tokens.filter(Boolean).forEach((token) => next.add(token));
    this.element.className = Array.from(next).join(" ").trim();
  }

  remove(...tokens) {
    const removing = new Set(tokens.filter(Boolean));
    this.element.className = this.#readTokens()
      .filter((token) => !removing.has(token))
      .join(" ")
      .trim();
  }

  #readTokens() {
    return String(this.element.className || "")
      .split(/\s+/)
      .map((token) => token.trim())
      .filter(Boolean);
  }
}

class MockElement {
  constructor(className = "") {
    this.textContent = "";
    this.className = className;
    this.style = {};
    this.classList = new MockClassList(this);
  }
}

function createChip() {
  return new MockElement("chip pending");
}

test("summary strip reflects focused channel, stream health and runtime/persistence", () => {
  const els = {
    summaryFocusedChannel: new MockElement(),
    summaryRuntimeStatusChip: createChip(),
    summaryPersistenceStatusChip: createChip(),
    summaryStreamHealthScore: new MockElement(),
    summaryStreamHealthBandChip: createChip(),
  };

  renderObservabilitySnapshot(
    {
      selected_channel: "Canal_A",
      context: { channel_id: "canal_a" },
      persistence: { enabled: true, restored: true },
      stream_health: { score: 88, band: "stable" },
      sentiment: { positive: 2, negative: 1 },
      timestamp: "2026-02-28T12:00:00Z",
    },
    els,
  );

  renderChannelContextSnapshot(
    {
      channel: {
        channel_id: "canal_a",
        runtime_loaded: true,
        has_persisted_state: true,
        has_persisted_history: false,
      },
    },
    els,
  );

  assert.equal(els.summaryFocusedChannel.textContent, "canal_a");
  assert.equal(els.summaryStreamHealthScore.textContent, "88/100");
  assert.equal(els.summaryStreamHealthBandChip.textContent, "STABLE");
  assert.match(els.summaryStreamHealthBandChip.className, /ok/);
  assert.equal(els.summaryRuntimeStatusChip.textContent, "RUNTIME HOT");
  assert.equal(els.summaryPersistenceStatusChip.textContent, "PERSISTED READY");
});

test("summary strip queue state tracks pending pressure from action queue payload", () => {
  const els = {
    panel: new MockElement(),
    pendingCount: new MockElement(),
    approvedCount: new MockElement(),
    rejectedCount: new MockElement(),
    ignoredCount: new MockElement(),
    totalCount: new MockElement(),
    summaryQueuePendingCount: new MockElement(),
    summaryQueuePendingChip: createChip(),
  };

  renderActionQueuePayload(
    {
      summary: {
        pending: 7,
        approved: 2,
        rejected: 1,
        ignored: 0,
        total: 10,
      },
      items: [],
    },
    els,
    () => {},
  );

  assert.equal(els.summaryQueuePendingCount.textContent, "7");
  assert.equal(els.summaryQueuePendingChip.textContent, "HIGH LOAD");
  assert.match(els.summaryQueuePendingChip.className, /error/);
  assert.match(els.panel.className, /attention-required/);
});

test("summary strip autonomy state and budget are updated from runtime snapshot", () => {
  const previousDocument = globalThis.document;
  globalThis.document = { getElementById: () => null };

  try {
    const els = {
      summaryAutonomyState: new MockElement(),
      summaryAutonomyBudget: new MockElement(),
    };

    renderAutonomyRuntime(
      {
        enabled: true,
        suspended: false,
        loop_running: false,
        budget_usage: {
          messages_10m: 2,
          limit_10m: 20,
          messages_60m: 4,
          limit_60m: 30,
          messages_daily: 10,
          limit_daily: 200,
        },
        queue: { pending: 1, approved: 2, rejected: 0, ignored: 0 },
      },
      els,
    );

    assert.equal(els.summaryAutonomyState.textContent, "ON - idle");
    assert.equal(els.summaryAutonomyBudget.textContent, "Budget 60m: 4/30");
  } finally {
    globalThis.document = previousDocument;
  }
});
