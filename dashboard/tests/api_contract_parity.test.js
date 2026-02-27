import test from "node:test";
import assert from "node:assert/strict";

import { sendChannelAction } from "../features/channel-control/api.js";
import {
  getControlPlaneState,
  getChannelConfig,
  getAgentNotes,
  resumeAgent,
  suspendAgent,
  updateAgentNotes,
  updateChannelConfig,
  updateControlPlaneConfig,
} from "../features/control-plane/api.js";
import {
  getActionQueue,
  decideActionQueueItem,
} from "../features/action-queue/api.js";
import { triggerAutonomyTick } from "../features/autonomy/api.js";
import { fetchClipJobs } from "../features/clips/api.js";
import { fetchHudMessages } from "../features/hud/api.js";
import {
  getChannelContextSnapshot,
  getObservabilityHistorySnapshot,
  getPostStreamReportSnapshot,
  getSemanticMemorySnapshot,
  getObservabilitySnapshot,
  getSentimentScoresSnapshot,
  upsertSemanticMemoryEntry,
} from "../features/observability/api.js";

const TOKEN_KEY = "byte_dashboard_admin_token";

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

function installApiEnv({ token = "" } = {}) {
  const localStorage = new MockStorage(
    token ? { [TOKEN_KEY]: token } : undefined,
  );
  const calls = [];

  globalThis.window = {
    localStorage,
    location: { origin: "http://localhost:8000" },
    BYTE_CONFIG: {},
    setTimeout,
    clearTimeout,
  };
  globalThis.document = {
    getElementById: () => null,
  };
  globalThis.localStorage = localStorage;
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: options || {} });
    return {
      ok: true,
      status: 200,
      async json() {
        return { ok: true };
      },
    };
  };

  return calls;
}

function findCall(calls, path, method) {
  return calls.find(
    (call) =>
      call.url.includes(path) &&
      String(call.options?.method || "GET").toUpperCase() === method,
  );
}

test("control-plane and channel directives APIs keep backend contract", async () => {
  const calls = installApiEnv();

  await getControlPlaneState();
  await updateControlPlaneConfig({ autonomy_enabled: true });
  await getChannelConfig("Canal_A");
  await updateChannelConfig({ channel_id: "canal_a", temperature: 0.77 });
  await getAgentNotes("Canal_A");
  await updateAgentNotes({ channel_id: "canal_a", notes: "anotacao" });
  await suspendAgent({ reason: "panic_button" });
  await resumeAgent({ reason: "manual_dashboard" });

  assert.ok(findCall(calls, "/api/control-plane", "GET"));
  const updateControlPlaneCall = findCall(calls, "/api/control-plane", "PUT");
  assert.ok(updateControlPlaneCall);
  assert.deepEqual(JSON.parse(String(updateControlPlaneCall.options.body)), {
    autonomy_enabled: true,
  });

  assert.ok(findCall(calls, "/api/channel-config?channel=canal_a", "GET"));
  const updateConfigCall = findCall(calls, "/api/channel-config", "PUT");
  assert.ok(updateConfigCall);
  assert.equal(
    JSON.parse(String(updateConfigCall.options.body)).channel_id,
    "canal_a",
  );

  assert.ok(findCall(calls, "/api/agent-notes?channel=canal_a", "GET"));
  const updateNotesCall = findCall(calls, "/api/agent-notes", "PUT");
  assert.ok(updateNotesCall);
  assert.equal(
    JSON.parse(String(updateNotesCall.options.body)).notes,
    "anotacao",
  );

  assert.ok(findCall(calls, "/api/agent/suspend", "POST"));
  assert.ok(findCall(calls, "/api/agent/resume", "POST"));
});

test("operational runtime APIs keep backend contract", async () => {
  const calls = installApiEnv();

  await sendChannelAction("join", "canal_b");
  await triggerAutonomyTick({ force: false, reason: "manual_test" });
  await getActionQueue({ status: "pending", limit: 7 });
  await decideActionQueueItem("action 123", "APPROVE", "ok");
  await fetchClipJobs();
  await fetchHudMessages(12.5);
  await getObservabilitySnapshot("Canal_Z");
  await getChannelContextSnapshot("Canal_Z");
  await getObservabilityHistorySnapshot("Canal_Z", 10000, 12, 4);
  await getSentimentScoresSnapshot("Canal_Z");
  await getPostStreamReportSnapshot("Canal_Z", 10000, true);
  await getSemanticMemorySnapshot("Canal_Z", 10000, "lore", 6, 50);
  await upsertSemanticMemoryEntry({
    channel_id: "canal_z",
    content: "Priorizar lore sem spoiler",
    memory_type: "instruction",
    tags: "lore,moderation",
  });

  const channelControlCall = findCall(calls, "/api/channel-control", "POST");
  assert.ok(channelControlCall);
  assert.deepEqual(JSON.parse(String(channelControlCall.options.body)), {
    action: "join",
    channel: "canal_b",
  });

  const autonomyTickCall = findCall(calls, "/api/autonomy/tick", "POST");
  assert.ok(autonomyTickCall);
  assert.deepEqual(JSON.parse(String(autonomyTickCall.options.body)), {
    force: false,
    reason: "manual_test",
  });

  assert.ok(findCall(calls, "/api/action-queue?status=pending&limit=7", "GET"));
  const decisionCall = findCall(
    calls,
    "/api/action-queue/action%20123/decision",
    "POST",
  );
  assert.ok(decisionCall);
  assert.deepEqual(JSON.parse(String(decisionCall.options.body)), {
    decision: "approve",
    note: "ok",
  });

  assert.ok(findCall(calls, "/api/clip-jobs", "GET"));
  assert.ok(findCall(calls, "/api/hud/messages?since=12.5", "GET"));
  assert.ok(findCall(calls, "/api/observability?channel=canal_z", "GET"));
  assert.ok(findCall(calls, "/api/channel-context?channel=canal_z", "GET"));
  assert.ok(
    findCall(
      calls,
      "/api/observability/history?channel=canal_z&limit=12&compare_limit=4",
      "GET",
    ),
  );
  assert.ok(findCall(calls, "/api/sentiment/scores?channel=canal_z", "GET"));
  assert.ok(
    findCall(
      calls,
      "/api/observability/post-stream-report?channel=canal_z&generate=1",
      "GET",
    ),
  );
  assert.ok(
    findCall(
      calls,
      "/api/semantic-memory?channel=canal_z&query=lore&limit=6&search_limit=50",
      "GET",
    ),
  );
  const semanticUpsertCall = findCall(calls, "/api/semantic-memory", "PUT");
  assert.ok(semanticUpsertCall);
  assert.equal(
    JSON.parse(String(semanticUpsertCall.options.body)).memory_type,
    "instruction",
  );
});
