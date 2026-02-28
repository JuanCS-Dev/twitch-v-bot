// dashboard/features/observability/view.js
import {
  setText,
  formatNumber,
  formatPercent,
  asArray,
  createCellRow,
} from "../shared/dom.js";

function formatUsd(value) {
  const amount = Number(value || 0);
  return `$${amount.toFixed(4)}`;
}

function normalizeStreamHealthBand(band) {
  const normalized = String(band || "")
    .trim()
    .toLowerCase();
  if (normalized === "excellent") return "excellent";
  if (normalized === "stable") return "stable";
  if (normalized === "watch") return "watch";
  return "critical";
}

function formatStreamHealthBandLabel(band) {
  const normalized = normalizeStreamHealthBand(band);
  if (normalized === "excellent") return "Excellent";
  if (normalized === "stable") return "Stable";
  if (normalized === "watch") return "Watch";
  return "Critical";
}

function formatStreamHealthScore(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "0";
  const clamped = Math.max(0, Math.min(100, parsed));
  return String(Math.round(clamped));
}

function ignoredRateChipTone(value) {
  const rate = Number(value);
  if (!Number.isFinite(rate)) return "pending";
  if (rate >= 30) return "error";
  if (rate >= 15) return "warn";
  return "ok";
}

function buildAnalyticsQuickInsightHint(
  channelId,
  streamHealthBand,
  ignoredRate,
  errorsTotal,
) {
  const normalizedBand = normalizeStreamHealthBand(streamHealthBand);
  const rate = Number(ignoredRate || 0);
  const errors = Number(errorsTotal || 0);

  if (normalizedBand === "critical" || rate >= 30 || errors > 0) {
    return {
      text: `Attention required in #${channelId}: health pressure or operational errors detected.`,
      className: "panel-hint event-level-warn",
    };
  }

  if (normalizedBand === "watch" || rate >= 15) {
    return {
      text: `Monitor #${channelId}: engagement pressure is rising and may require tactical adjustment.`,
      className: "panel-hint event-level-info",
    };
  }

  return {
    text: `#${channelId} is stable. Runtime context, realtime timeline and persisted history are ready for deeper analysis.`,
    className: "panel-hint",
  };
}

function formatStreamHealthCell(source) {
  const streamHealth = source?.stream_health || {};
  return `${formatStreamHealthScore(streamHealth.score)} (${formatStreamHealthBandLabel(streamHealth.band)})`;
}

function normalizeCoachingRiskBand(band) {
  const normalized = String(band || "")
    .trim()
    .toLowerCase();
  if (normalized === "critical") return "critical";
  if (normalized === "high") return "high";
  if (normalized === "watch") return "watch";
  return "low";
}

function formatCoachingRiskBandLabel(band) {
  const normalized = normalizeCoachingRiskBand(band);
  if (normalized === "critical") return "Critical";
  if (normalized === "high") return "High";
  if (normalized === "watch") return "Watch";
  return "Low";
}

function coachingRiskChipClass(band) {
  const normalized = normalizeCoachingRiskBand(band);
  if (normalized === "critical") return "error";
  if (normalized === "high") return "warn";
  if (normalized === "watch") return "pending";
  return "ok";
}

function formatCoachingRiskScore(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "0";
  const clamped = Math.max(0, Math.min(100, parsed));
  return String(Math.round(clamped));
}

function setStatusChip(chipEl, label, tone) {
  if (!chipEl) return;
  chipEl.classList.remove("ok", "warn", "error", "pending");
  setText(chipEl, label);
  chipEl.classList.add(tone || "pending");
}

function normalizeSemanticEngine(engine) {
  const normalized = String(engine || "")
    .trim()
    .toLowerCase();
  if (normalized === "pgvector") return "pgvector";
  if (normalized === "fallback") return "fallback";
  return "none";
}

function formatSemanticEngineLabel(engine) {
  const normalized = normalizeSemanticEngine(engine);
  if (normalized === "pgvector") return "PGVECTOR";
  if (normalized === "fallback") return "DETERMINISTIC";
  return "IDLE";
}

function semanticEngineChipTone(engine) {
  const normalized = normalizeSemanticEngine(engine);
  if (normalized === "pgvector") return "ok";
  if (normalized === "fallback") return "warn";
  return "pending";
}

function formatSemanticThreshold(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "-1.00";
  return parsed.toFixed(2);
}

function streamHealthSummaryChipTone(band) {
  const normalized = normalizeStreamHealthBand(band);
  if (normalized === "excellent" || normalized === "stable") return "ok";
  if (normalized === "watch") return "warn";
  return "error";
}

export function getObservabilityElements() {
  return {
    botIdentity: document.getElementById("botIdentity"),
    connectionState: document.getElementById("connectionState"),
    rollupStateChip: document.getElementById("rollupStateChip"),
    summaryFocusedChannel: document.getElementById("summaryFocusedChannel"),
    summaryRuntimeStatusChip: document.getElementById(
      "summaryRuntimeStatusChip",
    ),
    summaryPersistenceStatusChip: document.getElementById(
      "summaryPersistenceStatusChip",
    ),
    summaryStreamHealthScore: document.getElementById(
      "summaryStreamHealthScore",
    ),
    summaryStreamHealthBandChip: document.getElementById(
      "summaryStreamHealthBandChip",
    ),
    summaryQueuePendingCount: document.getElementById(
      "summaryQueuePendingCount",
    ),
    summaryQueuePendingChip: document.getElementById("summaryQueuePendingChip"),
    summaryAutonomyState: document.getElementById("summaryAutonomyState"),
    summaryAutonomyBudget: document.getElementById("summaryAutonomyBudget"),
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

    // Agent Health Counters (Novos)
    healthAuthFailures: document.getElementById("healthAuthFailures"),
    healthTotalChecks: document.getElementById("healthTotalChecks"),
    healthTokenRefreshes: document.getElementById("healthTokenRefreshes"),
    healthFallbackOrRetry: document.getElementById("healthFallbackOrRetry"),

    // Agent Outcomes (60m + total)
    oUsefulEngagementRate: document.getElementById("oUsefulEngagementRate"),
    oIgnoredRate: document.getElementById("oIgnoredRate"),
    oCorrectionRate: document.getElementById("oCorrectionRate"),
    oCorrectionTriggerRate: document.getElementById("oCorrectionTriggerRate"),
    oTokenInput60m: document.getElementById("oTokenInput60m"),
    oTokenOutput60m: document.getElementById("oTokenOutput60m"),
    oEstimatedCost60m: document.getElementById("oEstimatedCost60m"),
    oEstimatedCostTotal: document.getElementById("oEstimatedCostTotal"),

    // Sentiment & Vision (Fases 6-8)
    mVisionFrames: document.getElementById("mVisionFrames"),
    mSentimentVibe: document.getElementById("mSentimentVibe"),
    mSentimentAvg: document.getElementById("mSentimentAvg"),
    mStreamHealthScore: document.getElementById("mStreamHealthScore"),
    mStreamHealthBand: document.getElementById("mStreamHealthBand"),
    ctxSentimentVibe: document.getElementById("ctxSentimentVibe"),
    ctxSentimentAvg: document.getElementById("ctxSentimentAvg"),
    ctxStreamHealthScore: document.getElementById("ctxStreamHealthScore"),
    ctxStreamHealthBand: document.getElementById("ctxStreamHealthBand"),
    ctxVisionFrames: document.getElementById("ctxVisionFrames"),
    ctxVisionLast: document.getElementById("ctxVisionLast"),
    ctxSelectedChannelChip: document.getElementById("ctxSelectedChannelChip"),
    ctxPersistedStatusChip: document.getElementById("ctxPersistedStatusChip"),
    ctxRuntimeStatusChip: document.getElementById("ctxRuntimeStatusChip"),
    analyticsQuickInsightHint: document.getElementById(
      "analyticsQuickInsightHint",
    ),
    analyticsQuickFocusedChannel: document.getElementById(
      "analyticsQuickFocusedChannel",
    ),
    analyticsQuickRuntimeChip: document.getElementById(
      "analyticsQuickRuntimeChip",
    ),
    analyticsQuickPersistenceChip: document.getElementById(
      "analyticsQuickPersistenceChip",
    ),
    analyticsQuickHealthScore: document.getElementById(
      "analyticsQuickHealthScore",
    ),
    analyticsQuickHealthBandChip: document.getElementById(
      "analyticsQuickHealthBandChip",
    ),
    analyticsQuickIgnoredRate: document.getElementById(
      "analyticsQuickIgnoredRate",
    ),
    analyticsQuickMessagesPerMinute: document.getElementById(
      "analyticsQuickMessagesPerMinute",
    ),
    analyticsQuickTriggerRate: document.getElementById(
      "analyticsQuickTriggerRate",
    ),
    analyticsQuickCost60m: document.getElementById("analyticsQuickCost60m"),
    analyticsQuickErrors: document.getElementById("analyticsQuickErrors"),
    ctxPersistedGame: document.getElementById("ctxPersistedGame"),
    ctxPersistedVibe: document.getElementById("ctxPersistedVibe"),
    ctxPersistedLastEvent: document.getElementById("ctxPersistedLastEvent"),
    ctxPersistedStyle: document.getElementById("ctxPersistedStyle"),
    ctxPersistedReply: document.getElementById("ctxPersistedReply"),
    ctxPersistedNotes: document.getElementById("ctxPersistedNotes"),
    ctxPersistedUpdatedAt: document.getElementById("ctxPersistedUpdatedAt"),
    ctxPersistedHint: document.getElementById("ctxPersistedHint"),
    persistedHistoryItems: document.getElementById("persistedHistoryItems"),
    persistedTimelineHint: document.getElementById("persistedTimelineHint"),
    persistedChannelTimelineBody: document.getElementById(
      "persistedChannelTimelineBody",
    ),
    persistedChannelComparisonBody: document.getElementById(
      "persistedChannelComparisonBody",
    ),

    // Intelligence Overview Panel
    intVisionStatus: document.getElementById("intVisionStatus"),
    intVisionFramesTotal: document.getElementById("intVisionFramesTotal"),
    intVisionLastAnalysis: document.getElementById("intVisionLastAnalysis"),
    intSentimentVibe: document.getElementById("intSentimentVibe"),
    intSentimentAvg: document.getElementById("intSentimentAvg"),
    intSentimentCount: document.getElementById("intSentimentCount"),
    intSentimentPositive: document.getElementById("intSentimentPositive"),
    intSentimentNegative: document.getElementById("intSentimentNegative"),
    intStreamHealthScore: document.getElementById("intStreamHealthScore"),
    intStreamHealthBand: document.getElementById("intStreamHealthBand"),
    intCoachingRiskChip: document.getElementById("intCoachingRiskChip"),
    intCoachingHudStatus: document.getElementById("intCoachingHudStatus"),
    intCoachingRiskScore: document.getElementById("intCoachingRiskScore"),
    intCoachingLastEmission: document.getElementById("intCoachingLastEmission"),
    intCoachingHint: document.getElementById("intCoachingHint"),
    intCoachingAlerts: document.getElementById("intCoachingAlerts"),
    sentimentProgressBar: document.getElementById("sentimentProgressBar"),
    intPostStreamStatusChip: document.getElementById("intPostStreamStatusChip"),
    intPostStreamGeneratedAt: document.getElementById(
      "intPostStreamGeneratedAt",
    ),
    intPostStreamTrigger: document.getElementById("intPostStreamTrigger"),
    intPostStreamSummary: document.getElementById("intPostStreamSummary"),
    intPostStreamRecommendations: document.getElementById(
      "intPostStreamRecommendations",
    ),
    intPostStreamGenerateBtn: document.getElementById(
      "intPostStreamGenerateBtn",
    ),
    intSemanticMemoryStatusHint: document.getElementById(
      "intSemanticMemoryStatusHint",
    ),
    intSemanticMemoryEngineChip: document.getElementById(
      "intSemanticMemoryEngineChip",
    ),
    intSemanticMemoryEngineHint: document.getElementById(
      "intSemanticMemoryEngineHint",
    ),
    intSemanticMemoryQueryInput: document.getElementById(
      "intSemanticMemoryQueryInput",
    ),
    intSemanticMemoryMinSimilarityInput: document.getElementById(
      "intSemanticMemoryMinSimilarityInput",
    ),
    intSemanticMemoryForceFallbackToggle: document.getElementById(
      "intSemanticMemoryForceFallbackToggle",
    ),
    intSemanticMemorySearchBtn: document.getElementById(
      "intSemanticMemorySearchBtn",
    ),
    intSemanticMemoryTypeInput: document.getElementById(
      "intSemanticMemoryTypeInput",
    ),
    intSemanticMemoryTagsInput: document.getElementById(
      "intSemanticMemoryTagsInput",
    ),
    intSemanticMemoryContentInput: document.getElementById(
      "intSemanticMemoryContentInput",
    ),
    intSemanticMemorySaveBtn: document.getElementById(
      "intSemanticMemorySaveBtn",
    ),
    intSemanticMemoryMatches: document.getElementById(
      "intSemanticMemoryMatches",
    ),
    intSemanticMemoryEntries: document.getElementById(
      "intSemanticMemoryEntries",
    ),

    // Revenue Conversions
    intRevenueEventType: document.getElementById("intRevenueEventType"),
    intRevenueViewerLogin: document.getElementById("intRevenueViewerLogin"),
    intRevenueValue: document.getElementById("intRevenueValue"),
    intRevenueSimulateBtn: document.getElementById("intRevenueSimulateBtn"),
    intRevenueConversions: document.getElementById("intRevenueConversions"),
  };
}

export function setConnectionState(mode, elements) {
  const el = elements.connectionState;
  if (!el) return;
  el.classList.remove("ok", "warn", "error", "pending");
  if (mode === "ok") {
    el.textContent = "Synced";
    el.classList.add("ok");
    return;
  }
  if (mode === "error") {
    el.textContent = "Offline";
    el.classList.add("error");
    return;
  }
  el.textContent = "Polling...";
  el.classList.add("warn");
}

function renderRoutes(routes, targetBody) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeRoutes = asArray(routes);
  const rows =
    safeRoutes.length > 0
      ? safeRoutes.slice(0, 12)
      : [{ route: "-", count: 0 }];
  rows.forEach((item) => {
    targetBody.appendChild(
      createCellRow([item.route, formatNumber(item.count)]),
    );
  });
}

function renderTimeline(timeline, targetBody) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const rows = asArray(timeline).slice(-12);
  if (!rows.length) {
    targetBody.appendChild(createCellRow(["-", 0, 0, 0, 0, 0]));
    return;
  }
  rows.forEach((item) => {
    targetBody.appendChild(
      createCellRow([
        item.label,
        formatNumber(item.chat_messages),
        formatNumber(item.byte_triggers),
        formatNumber(item.replies_sent),
        formatNumber(item.llm_requests),
        formatNumber(item.errors),
      ]),
    );
  });
}

function renderLeaderboard(targetBody, rows, valueKey) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeRows = asArray(rows);
  if (!safeRows.length) {
    targetBody.appendChild(createCellRow(["-", 0]));
    return;
  }
  safeRows.slice(0, 8).forEach((item) => {
    targetBody.appendChild(
      createCellRow([item.author || "-", formatNumber(item[valueKey])]),
    );
  });
}

function renderContextItems(items, targetBody) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const entries = Object.entries(items || {});
  if (!entries.length) {
    const li = document.createElement("li");
    li.style.fontStyle = "italic";
    li.style.color = "var(--text-muted)";
    li.textContent = "No temporary context defined today.";
    targetBody.appendChild(li);
    return;
  }

  entries.forEach(([key, value]) => {
    const li = document.createElement("li");
    li.textContent = `${key}: ${value}`;
    targetBody.appendChild(li);
  });
}

function renderStringList(items, targetBody, emptyMessage) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeItems = asArray(items);
  if (!safeItems.length) {
    const li = document.createElement("li");
    li.style.fontStyle = "italic";
    li.style.color = "var(--text-muted)";
    li.textContent = emptyMessage;
    targetBody.appendChild(li);
    return;
  }

  safeItems.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = String(item || "-");
    targetBody.appendChild(li);
  });
}

function renderCoachingAlerts(alerts, targetBody) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeAlerts = asArray(alerts);
  if (!safeAlerts.length) {
    const li = document.createElement("li");
    li.style.fontStyle = "italic";
    li.style.color = "var(--text-muted)";
    li.textContent = "No tactical alerts right now.";
    targetBody.appendChild(li);
    return;
  }

  safeAlerts.slice(0, 4).forEach((item) => {
    const li = document.createElement("li");
    const severity = String(item?.severity || "info")
      .trim()
      .toLowerCase();
    const severityLabel =
      severity === "critical"
        ? "CRITICAL"
        : severity === "warn"
          ? "WARN"
          : "INFO";
    const title =
      String(item?.title || "Tactical signal").trim() || "Tactical signal";
    const message = String(item?.message || "").trim();
    const tactic = String(item?.tactic || "").trim();
    li.textContent = `[${severityLabel}] ${title}: ${message}${tactic ? ` | Action: ${tactic}` : ""}`;
    targetBody.appendChild(li);
  });
}

function formatPostStreamTrigger(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (!normalized) return "-";
  return normalized.replaceAll("_", " ");
}

function formatSemanticMemoryTags(tags) {
  const safeTags = asArray(tags)
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  if (!safeTags.length) return "-";
  return safeTags.map((value) => `#${value}`).join(" ");
}

function renderSemanticMemoryRows(
  rows,
  targetBody,
  emptyMessage,
  withSimilarity = false,
) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeRows = asArray(rows);
  if (!safeRows.length) {
    const li = document.createElement("li");
    li.style.fontStyle = "italic";
    li.style.color = "var(--text-muted)";
    li.textContent = emptyMessage;
    targetBody.appendChild(li);
    return;
  }

  safeRows.slice(0, 8).forEach((item) => {
    const li = document.createElement("li");
    const type =
      String(item?.memory_type || "fact")
        .trim()
        .toLowerCase() || "fact";
    const content = String(item?.content || "-").trim() || "-";
    const tags = formatSemanticMemoryTags(item?.tags);
    const similarity = Number(item?.similarity || 0);
    const score = withSimilarity ? ` | sim ${similarity.toFixed(3)}` : "";
    li.textContent = `[${type}] ${content} | ${tags}${score}`;
    targetBody.appendChild(li);
  });
}

function renderPersistedTimelineRows(rows, targetBody) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeRows = asArray(rows);
  if (!safeRows.length) {
    targetBody.appendChild(createCellRow(["-", 0, 0, 0, 0, 0, "0 (Critical)"]));
    return;
  }
  safeRows.slice(0, 16).forEach((item) => {
    const metrics = item?.metrics || {};
    const chatters = item?.chatters || {};
    targetBody.appendChild(
      createCellRow([
        String(item?.captured_at || "-"),
        formatNumber(metrics.chat_messages_total),
        formatNumber(metrics.byte_triggers_total),
        formatNumber(metrics.replies_total),
        formatNumber(chatters.active_60m),
        formatNumber(metrics.errors_total),
        formatStreamHealthCell(item),
      ]),
    );
  });
}

function renderPersistedComparisonRows(rows, targetBody, selectedChannel) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeRows = asArray(rows);
  if (!safeRows.length) {
    targetBody.appendChild(
      createCellRow(["-", 0, 0, 0, 0, "0.0%", "0 (Critical)", "-"]),
    );
    return;
  }
  safeRows.slice(0, 12).forEach((item) => {
    const channelId =
      String(item?.channel_id || "-")
        .trim()
        .toLowerCase() || "-";
    const metrics = item?.metrics || {};
    const chatters = item?.chatters || {};
    const outcomes = item?.agent_outcomes || {};
    const channelLabel =
      selectedChannel && channelId === selectedChannel
        ? `${channelId} (focused)`
        : channelId;
    targetBody.appendChild(
      createCellRow([
        channelLabel,
        formatNumber(metrics.chat_messages_total),
        formatNumber(metrics.byte_triggers_total),
        formatNumber(metrics.replies_total),
        formatNumber(chatters.active_60m),
        formatPercent(outcomes.ignored_rate_60m),
        formatStreamHealthCell(item),
        String(item?.captured_at || "-"),
      ]),
    );
  });
}

function renderEvents(events, targetBody) {
  if (!targetBody) return;
  targetBody.innerHTML = "";
  const safeEvents = asArray(events);
  const rows =
    safeEvents.length > 0
      ? safeEvents.slice(0, 16)
      : [
          {
            ts: "-",
            level: "INFO",
            event: "startup",
            message: "No data stream yet",
          },
        ];

  rows.forEach((eventItem) => {
    const li = document.createElement("li");

    const meta = document.createElement("div");
    meta.className = "event-meta";

    const ts = document.createElement("span");
    ts.textContent = eventItem.ts || "-";

    const level = document.createElement("span");
    const safeLevel = String(eventItem.level || "INFO").toLowerCase();
    level.className = `event-level-${safeLevel.startsWith("err") ? "error" : safeLevel.startsWith("warn") ? "warn" : "info"}`;
    level.textContent = String(eventItem.level || "INFO").toUpperCase();

    const name = document.createElement("span");
    name.textContent = String(eventItem.event || "event");

    meta.appendChild(ts);
    meta.appendChild(level);
    meta.appendChild(name);

    const msg = document.createElement("div");
    msg.textContent = String(eventItem.message || "");

    li.appendChild(meta);
    li.appendChild(msg);
    targetBody.appendChild(li);
  });
}

export function renderObservabilitySnapshot(
  data,
  els,
  sentimentPayload = null,
) {
  const safeData = data && typeof data === "object" ? data : {};
  const bot = safeData.bot || {};
  const metrics = safeData.metrics || {};
  const chatters = safeData.chatters || {};
  const analytics = safeData.chat_analytics || {};
  const sourceCounts = analytics.source_counts_60m || {};
  const leaderboards = safeData.leaderboards || {};
  const context = safeData.context || {};
  const outcomes = safeData.agent_outcomes || {};
  const persistence = safeData.persistence || {};
  const safeSentimentPayload =
    sentimentPayload && typeof sentimentPayload === "object"
      ? sentimentPayload
      : {};
  const sentimentFromScores = safeSentimentPayload.sentiment || {};
  const streamHealthFromScores = safeSentimentPayload.stream_health || {};
  const sentiment =
    Object.keys(sentimentFromScores).length > 0
      ? sentimentFromScores
      : safeData.sentiment || {};
  const streamHealth =
    Object.keys(streamHealthFromScores).length > 0
      ? streamHealthFromScores
      : safeData.stream_health || {};
  const coaching = safeData.coaching || {};

  setText(els.botIdentity, `${bot.brand || "Byte"} v${bot.version || "-"}`);
  setText(els.mChatMessages, formatNumber(metrics.chat_messages_total));
  setText(els.mByteTriggers, formatNumber(metrics.byte_triggers_total));
  setText(els.mInteractions, formatNumber(metrics.interactions_total));
  setText(els.mReplies, formatNumber(metrics.replies_total));
  setText(els.mActiveChatters, formatNumber(chatters.active_10m));
  setText(els.mActiveChatters60m, formatNumber(chatters.active_60m));
  setText(els.mUniqueChatters, formatNumber(chatters.unique_total));
  setText(els.mErrors, formatNumber(metrics.errors_total));
  setText(
    els.mAvgLatency,
    `${Number(metrics.avg_latency_ms || 0).toFixed(1)} ms`,
  );
  setText(
    els.mP95Latency,
    `${Number(metrics.p95_latency_ms || 0).toFixed(1)} ms`,
  );

  setText(els.aMessages10m, formatNumber(analytics.messages_10m));
  setText(els.aMessages60m, formatNumber(analytics.messages_60m));
  setText(
    els.aMpm10m,
    Number(analytics.messages_per_minute_10m || 0).toFixed(2),
  );
  setText(
    els.aMpm60m,
    Number(analytics.messages_per_minute_60m || 0).toFixed(2),
  );
  setText(
    els.aAvgLen10m,
    Number(analytics.avg_message_length_10m || 0).toFixed(1),
  );
  setText(
    els.aAvgLen60m,
    Number(analytics.avg_message_length_60m || 0).toFixed(1),
  );
  setText(els.aCommands60m, formatNumber(analytics.prefixed_commands_60m));
  setText(
    els.aCommandRatio60m,
    formatPercent(analytics.prefixed_command_ratio_60m),
  );
  setText(els.aUrls60m, formatNumber(analytics.url_messages_60m));
  setText(els.aUrlRatio60m, formatPercent(analytics.url_ratio_60m));
  setText(els.aSourceIrc60m, formatNumber(sourceCounts.irc));
  setText(els.aSourceEventsub60m, formatNumber(sourceCounts.eventsub));
  setText(els.aSourceUnknown60m, formatNumber(sourceCounts.unknown));
  setText(els.aByteTriggers10m, formatNumber(analytics.byte_triggers_10m));
  setText(els.aByteTriggers60m, formatNumber(analytics.byte_triggers_60m));

  // Health Data (canonical source: metrics)
  setText(els.healthAuthFailures, formatNumber(metrics.auth_failures_total));
  setText(els.healthTotalChecks, formatNumber(metrics.quality_checks_total));
  setText(
    els.healthTokenRefreshes,
    formatNumber(metrics.token_refreshes_total),
  );
  const fallbacksTotal =
    Number(metrics.quality_fallback_total || 0) +
    Number(metrics.quality_retry_total || 0);
  setText(els.healthFallbackOrRetry, formatNumber(fallbacksTotal));

  // Agent Outcomes
  setText(
    els.oUsefulEngagementRate,
    formatPercent(outcomes.useful_engagement_rate_60m),
  );
  setText(els.oIgnoredRate, formatPercent(outcomes.ignored_rate_60m));
  setText(els.oCorrectionRate, formatPercent(outcomes.correction_rate_60m));
  setText(
    els.oCorrectionTriggerRate,
    formatPercent(outcomes.correction_trigger_rate_60m),
  );
  setText(els.oTokenInput60m, formatNumber(outcomes.token_input_60m));
  setText(els.oTokenOutput60m, formatNumber(outcomes.token_output_60m));
  setText(els.oEstimatedCost60m, formatUsd(outcomes.estimated_cost_usd_60m));
  setText(
    els.oEstimatedCostTotal,
    formatUsd(outcomes.estimated_cost_usd_total),
  );

  // Context Data
  setText(els.ctxMode, bot.mode || "-");
  setText(els.ctxUptime, `${formatNumber(bot.uptime_minutes || 0)} min`);
  setText(els.ctxVibe, context.stream_vibe || "-");
  setText(els.ctxLastEvent, context.last_event || "-");
  setText(els.ctxActiveContexts, formatNumber(context.active_contexts || 0));
  setText(els.ctxUniqueChatters, formatNumber(chatters.unique_total || 0));
  setText(els.ctxLastPrompt, context.last_prompt || "-");
  setText(els.ctxLastReply, context.last_reply || "-");
  const focusedChannel =
    String(context.channel_id || safeData.selected_channel || "default")
      .trim()
      .toLowerCase() || "default";
  const streamHealthScoreLabel = `${formatStreamHealthScore(streamHealth.score)}/100`;
  const persistenceLabel =
    persistence.enabled && persistence.restored
      ? "PERSISTENCE READY"
      : persistence.enabled
        ? "PERSISTENCE LIVE"
        : "PERSISTENCE OFF";
  const persistenceTone =
    persistence.enabled && persistence.restored
      ? "ok"
      : persistence.enabled
        ? "warn"
        : "pending";
  const runtimeSnapshotLabel = String(bot.mode || "").trim()
    ? "RUNTIME ACTIVE"
    : "RUNTIME IDLE";
  const runtimeSnapshotTone = String(bot.mode || "").trim() ? "ok" : "pending";
  const messages60m = Number(analytics.messages_60m || 0);
  const triggerRate60m =
    messages60m > 0
      ? (Number(analytics.byte_triggers_60m || 0) / messages60m) * 100
      : 0;

  setText(els.summaryFocusedChannel, focusedChannel);
  setText(els.analyticsQuickFocusedChannel, focusedChannel);
  if (els.ctxSelectedChannelChip) {
    els.ctxSelectedChannelChip.classList.remove(
      "ok",
      "warn",
      "error",
      "pending",
    );
    setText(els.ctxSelectedChannelChip, focusedChannel);
    els.ctxSelectedChannelChip.classList.add("ok");
  }

  setStatusChip(
    els.analyticsQuickRuntimeChip,
    runtimeSnapshotLabel,
    runtimeSnapshotTone,
  );
  setStatusChip(
    els.analyticsQuickPersistenceChip,
    persistenceLabel,
    persistenceTone,
  );
  setText(els.analyticsQuickHealthScore, streamHealthScoreLabel);
  setStatusChip(
    els.analyticsQuickHealthBandChip,
    formatStreamHealthBandLabel(streamHealth.band).toUpperCase(),
    streamHealthSummaryChipTone(streamHealth.band),
  );
  setStatusChip(
    els.analyticsQuickIgnoredRate,
    `IGNORED ${formatPercent(outcomes.ignored_rate_60m)}`,
    ignoredRateChipTone(outcomes.ignored_rate_60m),
  );
  setText(
    els.analyticsQuickMessagesPerMinute,
    `${Number(analytics.messages_per_minute_10m || 0).toFixed(2)} / ${Number(analytics.messages_per_minute_60m || 0).toFixed(2)} mpm`,
  );
  setText(
    els.analyticsQuickTriggerRate,
    `${formatPercent(triggerRate60m)} trigger rate (60m)`,
  );
  setText(
    els.analyticsQuickCost60m,
    formatUsd(outcomes.estimated_cost_usd_60m),
  );
  setText(
    els.analyticsQuickErrors,
    `${formatNumber(metrics.errors_total)} errors`,
  );

  if (els.analyticsQuickInsightHint) {
    const quickHint = buildAnalyticsQuickInsightHint(
      focusedChannel,
      streamHealth.band,
      outcomes.ignored_rate_60m,
      metrics.errors_total,
    );
    setText(els.analyticsQuickInsightHint, quickHint.text);
    els.analyticsQuickInsightHint.className = quickHint.className;
  }

  if (els.summaryPersistenceStatusChip) {
    setStatusChip(
      els.summaryPersistenceStatusChip,
      persistenceLabel,
      persistenceTone,
    );
  }
  if (els.rollupStateChip) {
    els.rollupStateChip.classList.remove("ok", "warn", "error", "pending");
    if (persistence.enabled && persistence.restored) {
      setText(els.rollupStateChip, "Rollup Restored");
      els.rollupStateChip.classList.add("ok");
    } else if (persistence.enabled) {
      setText(els.rollupStateChip, "Rollup Live");
      els.rollupStateChip.classList.add("warn");
    } else {
      setText(els.rollupStateChip, "Volatile Only");
      els.rollupStateChip.classList.add("pending");
    }
  }

  renderRoutes(safeData.routes || [], els.routesBody);
  renderTimeline(safeData.timeline || [], els.timelineBody);
  renderLeaderboard(
    els.topChatters60mBody,
    leaderboards.top_chatters_60m,
    "messages",
  );
  renderLeaderboard(
    els.topTriggers60mBody,
    leaderboards.top_trigger_users_60m,
    "triggers",
  );
  renderLeaderboard(
    els.topChattersTotalBody,
    leaderboards.top_chatters_total,
    "messages",
  );
  renderContextItems(context.items || {}, els.contextItems);
  renderEvents(safeData.recent_events || [], els.eventsList);

  // Sentiment & Vision (Fases 6-8)
  const vision = safeData.vision || {};
  setText(els.mVisionFrames, formatNumber(vision.frame_count));
  setText(els.mSentimentVibe, sentiment.vibe || "Chill");
  setText(els.mSentimentAvg, Number(sentiment.avg || 0).toFixed(2));
  setText(els.mStreamHealthScore, formatStreamHealthScore(streamHealth.score));
  setText(
    els.mStreamHealthBand,
    formatStreamHealthBandLabel(streamHealth.band),
  );
  setText(els.summaryStreamHealthScore, streamHealthScoreLabel);
  setStatusChip(
    els.summaryStreamHealthBandChip,
    formatStreamHealthBandLabel(streamHealth.band).toUpperCase(),
    streamHealthSummaryChipTone(streamHealth.band),
  );
  setText(els.ctxSentimentVibe, sentiment.vibe || "-");
  setText(els.ctxSentimentAvg, Number(sentiment.avg || 0).toFixed(2));
  setText(els.ctxStreamHealthScore, streamHealthScoreLabel);
  setText(
    els.ctxStreamHealthBand,
    formatStreamHealthBandLabel(streamHealth.band),
  );
  setText(els.ctxVisionFrames, formatNumber(vision.frame_count));
  setText(els.ctxVisionLast, vision.last_analysis || "-");

  // Intelligence Overview Panel
  setText(els.intVisionStatus, vision.frame_count > 0 ? "Active" : "Idle");
  setText(els.intVisionFramesTotal, formatNumber(vision.frame_count));
  setText(els.intVisionLastAnalysis, vision.last_analysis || "-");
  setText(els.intSentimentVibe, sentiment.vibe || "Chill");
  setText(els.intSentimentAvg, Number(sentiment.avg || 0).toFixed(2));
  setText(els.intSentimentCount, formatNumber(sentiment.count));
  setText(els.intSentimentPositive, formatNumber(sentiment.positive));
  setText(els.intSentimentNegative, formatNumber(sentiment.negative));
  setText(
    els.intStreamHealthScore,
    `${formatStreamHealthScore(streamHealth.score)}/100`,
  );
  setText(
    els.intStreamHealthBand,
    formatStreamHealthBandLabel(streamHealth.band),
  );
  const coachingBand = normalizeCoachingRiskBand(coaching.risk_band);
  const coachingRiskScore = formatCoachingRiskScore(coaching.risk_score);
  const coachingHud = coaching.hud || {};

  if (els.intCoachingRiskChip) {
    els.intCoachingRiskChip.classList.remove("ok", "warn", "error", "pending");
    setText(
      els.intCoachingRiskChip,
      `CHURN ${formatCoachingRiskBandLabel(coachingBand).toUpperCase()}`,
    );
    els.intCoachingRiskChip.classList.add(coachingRiskChipClass(coachingBand));
  }
  setText(els.intCoachingRiskScore, `${coachingRiskScore}/100`);
  setText(els.intCoachingLastEmission, coachingHud.last_emitted_at || "-");
  if (els.intCoachingHudStatus) {
    if (coachingHud.emitted) {
      setText(els.intCoachingHudStatus, "HUD push emitted in this update.");
      els.intCoachingHudStatus.className = "panel-hint event-level-info";
    } else if (coachingHud.suppressed) {
      setText(
        els.intCoachingHudStatus,
        "HUD in anti-noise cooldown to prevent spam.",
      );
      els.intCoachingHudStatus.className = "panel-hint event-level-warn";
    } else {
      setText(els.intCoachingHudStatus, "HUD idle");
      els.intCoachingHudStatus.className = "panel-hint";
    }
  }
  if (els.intCoachingHint) {
    if (coachingBand === "critical" || coachingBand === "high") {
      setText(
        els.intCoachingHint,
        "High churn risk detected. Prioritize immediate tactical action.",
      );
      els.intCoachingHint.className = "panel-hint event-level-warn";
    } else if (coachingBand === "watch") {
      setText(
        els.intCoachingHint,
        "Engagement fluctuation detected. Adjust pace and validate chat response.",
      );
      els.intCoachingHint.className = "panel-hint event-level-info";
    } else {
      setText(
        els.intCoachingHint,
        "No churn signals at the moment. Tactical coach remains live.",
      );
      els.intCoachingHint.className = "panel-hint";
    }
  }
  renderCoachingAlerts(coaching.alerts || [], els.intCoachingAlerts);

  if (els.sentimentProgressBar) {
    const totalSentiments =
      (sentiment.positive || 0) + (sentiment.negative || 0);
    let ratio = 50; // default 50%
    if (totalSentiments > 0) {
      ratio = Math.round(((sentiment.positive || 0) / totalSentiments) * 100);
    }
    els.sentimentProgressBar.style.width = `${ratio}%`;
  }

  const snapshotTime =
    typeof safeData.timestamp === "string"
      ? new Date(safeData.timestamp)
      : null;
  if (snapshotTime && !Number.isNaN(snapshotTime.getTime())) {
    setText(els.lastUpdate, `Updated at: ${snapshotTime.toLocaleTimeString()}`);
    return;
  }
  setText(els.lastUpdate, `Updated at: ${new Date().toLocaleTimeString()}`);
}

export function renderObservabilityHistorySnapshot(payload, els) {
  if (!els) return;
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const selectedChannel =
    String(safePayload.selected_channel || "default")
      .trim()
      .toLowerCase() || "default";
  const timeline = asArray(safePayload.timeline);
  const comparison = asArray(safePayload.comparison);

  renderPersistedTimelineRows(timeline, els.persistedChannelTimelineBody);
  renderPersistedComparisonRows(
    comparison,
    els.persistedChannelComparisonBody,
    selectedChannel,
  );

  if (els.persistedTimelineHint) {
    if (timeline.length > 0) {
      setText(
        els.persistedTimelineHint,
        `Persisted timeline for #${selectedChannel} loaded with multi-channel comparison in the same operational layout.`,
      );
      els.persistedTimelineHint.className = "panel-hint event-level-info";
    } else {
      setText(
        els.persistedTimelineHint,
        `No persisted timeline for #${selectedChannel} yet. Historical snapshots will appear here when activity is available.`,
      );
      els.persistedTimelineHint.className = "panel-hint event-level-warn";
    }
  }
}

export function renderChannelContextSnapshot(payload, els) {
  if (!els) return;
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const channel = safePayload.channel || {};
  const persistedState = channel.persisted_state || {};
  const persistedAgentNotes = channel.persisted_agent_notes || {};
  const channelId =
    String(channel.channel_id || "default")
      .trim()
      .toLowerCase() || "default";
  const runtimeLoaded = Boolean(channel.runtime_loaded);
  const hasPersistedState = Boolean(channel.has_persisted_state);
  const hasPersistedHistory = Boolean(channel.has_persisted_history);
  const persistedReady = hasPersistedState || hasPersistedHistory;
  const persistedLabel = persistedReady ? "PERSISTED READY" : "NO SNAPSHOT";
  const runtimeLabel = runtimeLoaded ? "RUNTIME HOT" : "RUNTIME LAZY";

  setText(els.summaryFocusedChannel, channelId);
  setText(els.analyticsQuickFocusedChannel, channelId);

  if (els.ctxSelectedChannelChip) {
    setStatusChip(els.ctxSelectedChannelChip, channelId, "ok");
  }

  setStatusChip(
    els.ctxPersistedStatusChip,
    persistedLabel,
    persistedReady ? "ok" : "warn",
  );
  setStatusChip(
    els.summaryPersistenceStatusChip,
    persistedLabel,
    persistedReady ? "ok" : "warn",
  );
  setStatusChip(
    els.analyticsQuickPersistenceChip,
    persistedLabel,
    persistedReady ? "ok" : "warn",
  );

  setStatusChip(
    els.ctxRuntimeStatusChip,
    runtimeLabel,
    runtimeLoaded ? "ok" : "pending",
  );
  setStatusChip(
    els.summaryRuntimeStatusChip,
    runtimeLabel,
    runtimeLoaded ? "ok" : "pending",
  );
  setStatusChip(
    els.analyticsQuickRuntimeChip,
    runtimeLabel,
    runtimeLoaded ? "ok" : "pending",
  );

  setText(els.ctxPersistedGame, persistedState.current_game || "-");
  setText(els.ctxPersistedVibe, persistedState.stream_vibe || "-");
  setText(els.ctxPersistedLastEvent, persistedState.last_event || "-");
  setText(els.ctxPersistedStyle, persistedState.style_profile || "-");
  setText(els.ctxPersistedReply, persistedState.last_reply || "-");
  setText(els.ctxPersistedNotes, persistedAgentNotes.notes || "-");
  setText(els.ctxPersistedUpdatedAt, persistedState.updated_at || "-");

  if (els.ctxPersistedHint) {
    if (hasPersistedState || hasPersistedHistory) {
      setText(
        els.ctxPersistedHint,
        `Persisted state for #${channelId} loaded from Supabase for operational inspection.`,
      );
      els.ctxPersistedHint.className = "panel-hint event-level-info";
    } else {
      setText(
        els.ctxPersistedHint,
        `No persisted snapshot for #${channelId}. Runtime may be operating in memory only.`,
      );
      els.ctxPersistedHint.className = "panel-hint event-level-warn";
    }
  }

  if (els.analyticsQuickInsightHint && (!runtimeLoaded || !persistedReady)) {
    setText(
      els.analyticsQuickInsightHint,
      `#${channelId} is running with partial persisted context. Validate runtime/timeline before tactical actions.`,
    );
    els.analyticsQuickInsightHint.className = "panel-hint event-level-warn";
  }

  renderStringList(
    channel.persisted_recent_history || [],
    els.persistedHistoryItems,
    "No persisted history available for this channel.",
  );
}

export function renderPostStreamReportSnapshot(payload, els) {
  if (!els) return;
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const report =
    safePayload.report && typeof safePayload.report === "object"
      ? safePayload.report
      : {};
  const hasReport = Boolean(
    safePayload.has_report && Object.keys(report).length > 0,
  );

  if (els.intPostStreamStatusChip) {
    els.intPostStreamStatusChip.classList.remove(
      "ok",
      "warn",
      "error",
      "pending",
    );
    if (hasReport) {
      setText(
        els.intPostStreamStatusChip,
        safePayload.generated ? "REPORT UPDATED" : "REPORT READY",
      );
      els.intPostStreamStatusChip.classList.add("ok");
    } else {
      setText(els.intPostStreamStatusChip, "NO REPORT");
      els.intPostStreamStatusChip.classList.add("warn");
    }
  }

  setText(
    els.intPostStreamGeneratedAt,
    hasReport ? report.generated_at || "-" : "-",
  );
  setText(
    els.intPostStreamTrigger,
    hasReport ? formatPostStreamTrigger(report.trigger) : "-",
  );
  setText(
    els.intPostStreamSummary,
    hasReport
      ? String(report.narrative || "Summary unavailable for this session.")
      : "No post-stream report for this channel. Generate manually to register the session summary.",
  );
  renderStringList(
    hasReport ? report.recommendations || [] : [],
    els.intPostStreamRecommendations,
    "No recommendations recorded.",
  );
}

export function renderSemanticMemorySnapshot(payload, els) {
  if (!els) return;
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const diagnostics =
    safePayload.search_diagnostics &&
    typeof safePayload.search_diagnostics === "object"
      ? safePayload.search_diagnostics
      : {};
  const settings =
    safePayload.search_settings &&
    typeof safePayload.search_settings === "object"
      ? safePayload.search_settings
      : {};
  const selectedChannel =
    String(safePayload.selected_channel || "default")
      .trim()
      .toLowerCase() || "default";
  const query = String(safePayload.query || "").trim();
  const hasEntries = Boolean(safePayload.has_entries);
  const hasMatches = Boolean(safePayload.has_matches);
  const entries = asArray(safePayload.entries);
  const matches = asArray(safePayload.matches);
  const semanticEngine = normalizeSemanticEngine(diagnostics.engine);
  const minSimilarity = formatSemanticThreshold(
    diagnostics.min_similarity ?? settings.default_min_similarity,
  );
  const forceFallback = Boolean(diagnostics.force_fallback);
  const candidateCount = Number(diagnostics.candidate_count || 0);
  const resultCount = Number(diagnostics.result_count || 0);

  if (els.intSemanticMemoryEngineChip) {
    setStatusChip(
      els.intSemanticMemoryEngineChip,
      `ENGINE ${formatSemanticEngineLabel(semanticEngine)}`,
      semanticEngineChipTone(semanticEngine),
    );
  }

  if (els.intSemanticMemoryEngineHint) {
    const modeLabel = forceFallback
      ? "manual deterministic fallback"
      : "auto engine";
    setText(
      els.intSemanticMemoryEngineHint,
      `Search mode: ${modeLabel}. Threshold >= ${minSimilarity}. Candidates: ${candidateCount}, results: ${resultCount}.`,
    );
    els.intSemanticMemoryEngineHint.className =
      semanticEngine === "pgvector"
        ? "panel-hint event-level-info"
        : "panel-hint";
  }

  if (
    els.intSemanticMemoryMinSimilarityInput &&
    (typeof document === "undefined" ||
      document.activeElement !== els.intSemanticMemoryMinSimilarityInput)
  ) {
    const normalizedInputValue = String(
      diagnostics.min_similarity ?? settings.default_min_similarity ?? "",
    );
    els.intSemanticMemoryMinSimilarityInput.value = normalizedInputValue;
  }
  if (els.intSemanticMemoryForceFallbackToggle) {
    els.intSemanticMemoryForceFallbackToggle.checked = forceFallback;
  }

  if (els.intSemanticMemoryStatusHint) {
    if (!hasEntries) {
      setText(
        els.intSemanticMemoryStatusHint,
        `No semantic memory registered for #${selectedChannel} yet.`,
      );
      els.intSemanticMemoryStatusHint.className = "panel-hint event-level-warn";
    } else if (query && hasMatches) {
      setText(
        els.intSemanticMemoryStatusHint,
        `Semantic search active in #${selectedChannel} for "${query}".`,
      );
      els.intSemanticMemoryStatusHint.className = "panel-hint event-level-info";
    } else if (query && !hasMatches) {
      setText(
        els.intSemanticMemoryStatusHint,
        `No matches for "${query}" in #${selectedChannel}.`,
      );
      els.intSemanticMemoryStatusHint.className = "panel-hint event-level-warn";
    } else {
      setText(
        els.intSemanticMemoryStatusHint,
        `Semantic memory for #${selectedChannel} loaded in the current panel.`,
      );
      els.intSemanticMemoryStatusHint.className = "panel-hint event-level-info";
    }
  }

  renderSemanticMemoryRows(
    matches,
    els.intSemanticMemoryMatches,
    "No semantic matches.",
    true,
  );
  renderSemanticMemoryRows(
    entries,
    els.intSemanticMemoryEntries,
    "No persisted memory for this channel.",
    false,
  );
}

export function renderRevenueConversionsSnapshot(payload, els) {
  if (!els || !els.intRevenueConversions) return;
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const conversions = asArray(safePayload.conversions);
  const targetBody = els.intRevenueConversions;

  targetBody.innerHTML = "";
  if (!conversions.length) {
    const li = document.createElement("li");
    li.style.fontStyle = "italic";
    li.style.color = "var(--text-muted)";
    li.textContent = "No recent conversions for this channel.";
    targetBody.appendChild(li);
    return;
  }

  conversions.forEach((item) => {
    const li = document.createElement("li");
    const eventType = String(item?.event_type || "-").toUpperCase();
    const login = item?.viewer_login || "-";
    const val = Number(item?.revenue_value || 0);
    const attr = item?.attributed_action_type || "";
    const badge = attr ? `[Attr: ${attr}] ` : "";
    const money = val > 0 ? ` $${val.toFixed(2)}` : "";

    li.textContent = `${badge}${eventType} from ${login}${money}`;
    targetBody.appendChild(li);
  });
}
