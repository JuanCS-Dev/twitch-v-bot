// dashboard/features/observability/view.js
import { setText, formatNumber, formatPercent, asArray, createCellRow } from "../shared/dom.js";

function formatUsd(value) {
    const amount = Number(value || 0);
    return `$${amount.toFixed(4)}`;
}

export function getObservabilityElements() {
    return {
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
        oEstimatedCostTotal: document.getElementById("oEstimatedCostTotal")
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
    const rows = safeRoutes.length > 0 ? safeRoutes.slice(0, 12) : [{ route: "-", count: 0 }];
    rows.forEach((item) => {
        targetBody.appendChild(createCellRow([item.route, formatNumber(item.count)]));
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
            ])
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
        targetBody.appendChild(createCellRow([item.author || "-", formatNumber(item[valueKey])]));
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
        li.textContent = "Nenhum contexto temporario estipulado hoje.";
        targetBody.appendChild(li);
        return;
    }

    entries.forEach(([key, value]) => {
        const li = document.createElement("li");
        li.textContent = `${key}: ${value}`;
        targetBody.appendChild(li);
    });
}

function renderEvents(events, targetBody) {
    if (!targetBody) return;
    targetBody.innerHTML = "";
    const safeEvents = asArray(events);
    const rows = safeEvents.length > 0 ? safeEvents.slice(0, 16) : [{ ts: "-", level: "INFO", event: "startup", message: "No data stream yet" }];

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

export function renderObservabilitySnapshot(data, els) {
    const safeData = data && typeof data === "object" ? data : {};
    const bot = safeData.bot || {};
    const metrics = safeData.metrics || {};
    const chatters = safeData.chatters || {};
    const analytics = safeData.chat_analytics || {};
    const sourceCounts = analytics.source_counts_60m || {};
    const leaderboards = safeData.leaderboards || {};
    const context = safeData.context || {};
    const outcomes = safeData.agent_outcomes || {};

    setText(els.botIdentity, `${bot.brand || "Byte"} v${bot.version || "-"}`);
    setText(els.mChatMessages, formatNumber(metrics.chat_messages_total));
    setText(els.mByteTriggers, formatNumber(metrics.byte_triggers_total));
    setText(els.mInteractions, formatNumber(metrics.interactions_total));
    setText(els.mReplies, formatNumber(metrics.replies_total));
    setText(els.mActiveChatters, formatNumber(chatters.active_10m));
    setText(els.mActiveChatters60m, formatNumber(chatters.active_60m));
    setText(els.mUniqueChatters, formatNumber(chatters.unique_total));
    setText(els.mErrors, formatNumber(metrics.errors_total));
    setText(els.mAvgLatency, `${Number(metrics.avg_latency_ms || 0).toFixed(1)} ms`);
    setText(els.mP95Latency, `${Number(metrics.p95_latency_ms || 0).toFixed(1)} ms`);

    setText(els.aMessages10m, formatNumber(analytics.messages_10m));
    setText(els.aMessages60m, formatNumber(analytics.messages_60m));
    setText(els.aMpm10m, Number(analytics.messages_per_minute_10m || 0).toFixed(2));
    setText(els.aMpm60m, Number(analytics.messages_per_minute_60m || 0).toFixed(2));
    setText(els.aAvgLen10m, Number(analytics.avg_message_length_10m || 0).toFixed(1));
    setText(els.aAvgLen60m, Number(analytics.avg_message_length_60m || 0).toFixed(1));
    setText(els.aCommands60m, formatNumber(analytics.prefixed_commands_60m));
    setText(els.aCommandRatio60m, formatPercent(analytics.prefixed_command_ratio_60m));
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
    setText(els.healthTokenRefreshes, formatNumber(metrics.token_refreshes_total));
    const fallbacksTotal = Number(metrics.quality_fallback_total || 0) + Number(metrics.quality_retry_total || 0);
    setText(els.healthFallbackOrRetry, formatNumber(fallbacksTotal));

    // Agent Outcomes
    setText(els.oUsefulEngagementRate, formatPercent(outcomes.useful_engagement_rate_60m));
    setText(els.oIgnoredRate, formatPercent(outcomes.ignored_rate_60m));
    setText(els.oCorrectionRate, formatPercent(outcomes.correction_rate_60m));
    setText(els.oCorrectionTriggerRate, formatPercent(outcomes.correction_trigger_rate_60m));
    setText(els.oTokenInput60m, formatNumber(outcomes.token_input_60m));
    setText(els.oTokenOutput60m, formatNumber(outcomes.token_output_60m));
    setText(els.oEstimatedCost60m, formatUsd(outcomes.estimated_cost_usd_60m));
    setText(els.oEstimatedCostTotal, formatUsd(outcomes.estimated_cost_usd_total));

    // Context Data
    setText(els.ctxMode, bot.mode || "-");
    setText(els.ctxUptime, `${formatNumber(bot.uptime_minutes || 0)} min`);
    setText(els.ctxVibe, context.stream_vibe || "-");
    setText(els.ctxLastEvent, context.last_event || "-");
    setText(els.ctxActiveContexts, formatNumber(context.active_contexts || 0));
    setText(els.ctxUniqueChatters, formatNumber(chatters.unique_total || 0));
    setText(els.ctxLastPrompt, context.last_prompt || "-");
    setText(els.ctxLastReply, context.last_reply || "-");

    renderRoutes(safeData.routes || [], els.routesBody);
    renderTimeline(safeData.timeline || [], els.timelineBody);
    renderLeaderboard(els.topChatters60mBody, leaderboards.top_chatters_60m, "messages");
    renderLeaderboard(els.topTriggers60mBody, leaderboards.top_trigger_users_60m, "triggers");
    renderLeaderboard(els.topChattersTotalBody, leaderboards.top_chatters_total, "messages");
    renderContextItems(context.items || {}, els.contextItems);
    renderEvents(safeData.recent_events || [], els.eventsList);

    const snapshotTime = typeof safeData.timestamp === "string" ? new Date(safeData.timestamp) : null;
    if (snapshotTime && !Number.isNaN(snapshotTime.getTime())) {
        setText(els.lastUpdate, `Atualizado as: ${snapshotTime.toLocaleTimeString()}`);
        return;
    }
    setText(els.lastUpdate, `Atualizado as: ${new Date().toLocaleTimeString()}`);
}
