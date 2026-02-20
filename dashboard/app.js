const API_ENDPOINT = "/api/observability";
const FETCH_TIMEOUT_MS = 10000;

const elements = {
  refreshButton: document.getElementById("refreshButton"),
  botIdentity: document.getElementById("botIdentity"),
  connectionState: document.getElementById("connectionState"),
  lastUpdate: document.getElementById("lastUpdate"),
  mChatMessages: document.getElementById("mChatMessages"),
  mByteTriggers: document.getElementById("mByteTriggers"),
  mInteractions: document.getElementById("mInteractions"),
  mReplies: document.getElementById("mReplies"),
  mActiveChatters: document.getElementById("mActiveChatters"),
  mActiveChatters60m: document.getElementById("mActiveChatters60m"),
  mUniqueChatters: document.getElementById("mUniqueChatters"),
  mErrors: document.getElementById("mErrors"),
  mAvgLatency: document.getElementById("mAvgLatency"),
  mP95Latency: document.getElementById("mP95Latency"),
  aMessages10m: document.getElementById("aMessages10m"),
  aMessages60m: document.getElementById("aMessages60m"),
  aMpm10m: document.getElementById("aMpm10m"),
  aMpm60m: document.getElementById("aMpm60m"),
  aAvgLen10m: document.getElementById("aAvgLen10m"),
  aAvgLen60m: document.getElementById("aAvgLen60m"),
  aCommands60m: document.getElementById("aCommands60m"),
  aCommandRatio60m: document.getElementById("aCommandRatio60m"),
  aUrls60m: document.getElementById("aUrls60m"),
  aUrlRatio60m: document.getElementById("aUrlRatio60m"),
  aSourceIrc60m: document.getElementById("aSourceIrc60m"),
  aSourceEventsub60m: document.getElementById("aSourceEventsub60m"),
  aSourceUnknown60m: document.getElementById("aSourceUnknown60m"),
  aByteTriggers10m: document.getElementById("aByteTriggers10m"),
  aByteTriggers60m: document.getElementById("aByteTriggers60m"),
  ctxMode: document.getElementById("ctxMode"),
  ctxUptime: document.getElementById("ctxUptime"),
  ctxVibe: document.getElementById("ctxVibe"),
  ctxLastEvent: document.getElementById("ctxLastEvent"),
  ctxActiveContexts: document.getElementById("ctxActiveContexts"),
  ctxUniqueChatters: document.getElementById("ctxUniqueChatters"),
  ctxLastPrompt: document.getElementById("ctxLastPrompt"),
  ctxLastReply: document.getElementById("ctxLastReply"),
  routesBody: document.getElementById("routesBody"),
  timelineBody: document.getElementById("timelineBody"),
  topChatters60mBody: document.getElementById("topChatters60mBody"),
  topTriggers60mBody: document.getElementById("topTriggers60mBody"),
  topChattersTotalBody: document.getElementById("topChattersTotalBody"),
  contextItems: document.getElementById("contextItems"),
  eventsList: document.getElementById("eventsList"),
};

let isRefreshing = false;

function setConnectionState(mode) {
  elements.connectionState.classList.remove("chip-ok", "chip-warn", "chip-bad");
  if (mode === "ok") {
    elements.connectionState.textContent = "Connected";
    elements.connectionState.classList.add("chip-ok");
    return;
  }
  if (mode === "error") {
    elements.connectionState.textContent = "Disconnected";
    elements.connectionState.classList.add("chip-bad");
    return;
  }
  elements.connectionState.textContent = "Connecting";
  elements.connectionState.classList.add("chip-warn");
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function setText(element, text) {
  if (element) {
    element.textContent = text;
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function setRefreshButtonState(refreshing) {
  if (!elements.refreshButton) {
    return;
  }
  elements.refreshButton.disabled = refreshing;
  elements.refreshButton.textContent = refreshing ? "Refreshing..." : "Refresh";
}

function createCellRow(values) {
  const row = document.createElement("tr");
  values.forEach((value) => {
    const cell = document.createElement("td");
    cell.textContent = String(value);
    row.appendChild(cell);
  });
  return row;
}

function renderRoutes(routes) {
  if (!elements.routesBody) {
    return;
  }
  elements.routesBody.innerHTML = "";
  const safeRoutes = asArray(routes);
  const rows = safeRoutes.length > 0 ? safeRoutes.slice(0, 12) : [{ route: "-", count: 0 }];
  rows.forEach((item) => {
    elements.routesBody.appendChild(createCellRow([item.route, formatNumber(item.count)]));
  });
}

function renderTimeline(timeline) {
  if (!elements.timelineBody) {
    return;
  }
  elements.timelineBody.innerHTML = "";
  const rows = asArray(timeline).slice(-12);
  if (!rows.length) {
    elements.timelineBody.appendChild(createCellRow(["-", 0, 0, 0, 0, 0]));
    return;
  }

  rows.forEach((item) => {
    elements.timelineBody.appendChild(
      createCellRow([
        item.label,
        formatNumber(item.chat_messages),
        formatNumber(item.byte_triggers),
        formatNumber(item.replies_sent),
        formatNumber(item.llm_requests),
        formatNumber(item.errors),
      ])
    );
  });
}

function renderLeaderboard(targetBody, rows, valueKey) {
  if (!targetBody) {
    return;
  }
  targetBody.innerHTML = "";
  const safeRows = asArray(rows);
  if (!safeRows.length) {
    targetBody.appendChild(createCellRow(["-", 0]));
    return;
  }
  safeRows.slice(0, 8).forEach((item) => {
    targetBody.appendChild(createCellRow([item.author || "-", formatNumber(item[valueKey])]));
  });
}

function renderContextItems(items) {
  if (!elements.contextItems) {
    return;
  }
  elements.contextItems.innerHTML = "";
  const entries = Object.entries(items || {});
  if (!entries.length) {
    const li = document.createElement("li");
    li.textContent = "No active context items.";
    elements.contextItems.appendChild(li);
    return;
  }

  entries.forEach(([key, value]) => {
    const li = document.createElement("li");
    li.textContent = `${key}: ${value}`;
    elements.contextItems.appendChild(li);
  });
}

function renderEvents(events) {
  if (!elements.eventsList) {
    return;
  }
  elements.eventsList.innerHTML = "";
  const safeEvents = asArray(events);
  const rows = safeEvents.length > 0 ? safeEvents.slice(0, 16) : [{ ts: "-", level: "INFO", event: "startup", message: "No events yet." }];

  rows.forEach((eventItem) => {
    const li = document.createElement("li");

    const meta = document.createElement("div");
    meta.className = "event-meta";

    const ts = document.createElement("span");
    ts.textContent = eventItem.ts || "-";

    const level = document.createElement("span");
    const safeLevel = String(eventItem.level || "INFO").toLowerCase();
    level.className = `event-level-${safeLevel.startsWith("err") ? "error" : safeLevel.startsWith("warn") ? "warn" : "info"}`;
    level.textContent = String(eventItem.level || "INFO");

    const name = document.createElement("span");
    name.textContent = String(eventItem.event || "event");

    meta.appendChild(ts);
    meta.appendChild(level);
    meta.appendChild(name);

    const msg = document.createElement("div");
    msg.textContent = String(eventItem.message || "");

    li.appendChild(meta);
    li.appendChild(msg);
    elements.eventsList.appendChild(li);
  });
}

function renderSnapshot(data) {
  const safeData = data && typeof data === "object" ? data : {};
  const bot = safeData.bot || {};
  const metrics = safeData.metrics || {};
  const chatters = safeData.chatters || {};
  const analytics = safeData.chat_analytics || {};
  const sourceCounts = analytics.source_counts_60m || {};
  const leaderboards = safeData.leaderboards || {};
  const context = safeData.context || {};

  setText(elements.botIdentity, `${bot.brand || "Byte"} v${bot.version || "-"}`);
  setText(elements.mChatMessages, formatNumber(metrics.chat_messages_total));
  setText(elements.mByteTriggers, formatNumber(metrics.byte_triggers_total));
  setText(elements.mInteractions, formatNumber(metrics.interactions_total));
  setText(elements.mReplies, formatNumber(metrics.replies_total));
  setText(elements.mActiveChatters, formatNumber(chatters.active_10m));
  setText(elements.mActiveChatters60m, formatNumber(chatters.active_60m));
  setText(elements.mUniqueChatters, formatNumber(chatters.unique_total));
  setText(elements.mErrors, formatNumber(metrics.errors_total));
  setText(elements.mAvgLatency, `${Number(metrics.avg_latency_ms || 0).toFixed(1)} ms`);
  setText(elements.mP95Latency, `${Number(metrics.p95_latency_ms || 0).toFixed(1)} ms`);

  setText(elements.aMessages10m, formatNumber(analytics.messages_10m));
  setText(elements.aMessages60m, formatNumber(analytics.messages_60m));
  setText(elements.aMpm10m, Number(analytics.messages_per_minute_10m || 0).toFixed(2));
  setText(elements.aMpm60m, Number(analytics.messages_per_minute_60m || 0).toFixed(2));
  setText(elements.aAvgLen10m, Number(analytics.avg_message_length_10m || 0).toFixed(1));
  setText(elements.aAvgLen60m, Number(analytics.avg_message_length_60m || 0).toFixed(1));
  setText(elements.aCommands60m, formatNumber(analytics.prefixed_commands_60m));
  setText(elements.aCommandRatio60m, formatPercent(analytics.prefixed_command_ratio_60m));
  setText(elements.aUrls60m, formatNumber(analytics.url_messages_60m));
  setText(elements.aUrlRatio60m, formatPercent(analytics.url_ratio_60m));
  setText(elements.aSourceIrc60m, formatNumber(sourceCounts.irc));
  setText(elements.aSourceEventsub60m, formatNumber(sourceCounts.eventsub));
  setText(elements.aSourceUnknown60m, formatNumber(sourceCounts.unknown));
  setText(elements.aByteTriggers10m, formatNumber(analytics.byte_triggers_10m));
  setText(elements.aByteTriggers60m, formatNumber(analytics.byte_triggers_60m));

  setText(elements.ctxMode, bot.mode || "-");
  setText(elements.ctxUptime, `${formatNumber(bot.uptime_minutes || 0)} min`);
  setText(elements.ctxVibe, context.stream_vibe || "-");
  setText(elements.ctxLastEvent, context.last_event || "-");
  setText(elements.ctxActiveContexts, formatNumber(context.active_contexts || 0));
  setText(elements.ctxUniqueChatters, formatNumber(chatters.unique_total || 0));
  setText(elements.ctxLastPrompt, context.last_prompt || "-");
  setText(elements.ctxLastReply, context.last_reply || "-");

  renderRoutes(safeData.routes || []);
  renderTimeline(safeData.timeline || []);
  renderLeaderboard(elements.topChatters60mBody, leaderboards.top_chatters_60m, "messages");
  renderLeaderboard(elements.topTriggers60mBody, leaderboards.top_trigger_users_60m, "triggers");
  renderLeaderboard(elements.topChattersTotalBody, leaderboards.top_chatters_total, "messages");
  renderContextItems(context.items || {});
  renderEvents(safeData.recent_events || []);

  const snapshotTime = typeof safeData.timestamp === "string" ? new Date(safeData.timestamp) : null;
  if (snapshotTime && !Number.isNaN(snapshotTime.getTime())) {
    setText(elements.lastUpdate, `Last update: ${snapshotTime.toLocaleTimeString()}`);
    return;
  }
  setText(elements.lastUpdate, `Last update: ${new Date().toLocaleTimeString()}`);
}

async function refreshSnapshot() {
  if (isRefreshing) {
    return;
  }
  isRefreshing = true;
  setRefreshButtonState(true);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const response = await fetch(API_ENDPOINT, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    renderSnapshot(payload);
    setConnectionState("ok");
  } catch (error) {
    console.error("Dashboard refresh failed:", error);
    setConnectionState("error");
    setText(elements.lastUpdate, `Last update: error (${new Date().toLocaleTimeString()})`);
  } finally {
    clearTimeout(timeoutId);
    isRefreshing = false;
    setRefreshButtonState(false);
  }
}

setConnectionState("connecting");
setRefreshButtonState(false);
refreshSnapshot();
window.byteRefreshSnapshot = refreshSnapshot;
if (elements.refreshButton) {
  elements.refreshButton.addEventListener("click", () => {
    refreshSnapshot();
  });
}
