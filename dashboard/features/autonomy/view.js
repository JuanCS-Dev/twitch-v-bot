import { formatNumber, setText } from "../shared/dom.js";

export function getAutonomyElements() {
    return {
        enabledState: document.getElementById("autEnabledState"),
        loopState: document.getElementById("autLoopState"),
        lastHeartbeat: document.getElementById("autLastHeartbeat"),
        lastTick: document.getElementById("autLastTick"),
        lastGoal: document.getElementById("autLastGoal"),
        lastRisk: document.getElementById("autLastRisk"),
        lastBlockReason: document.getElementById("autLastBlockReason"),
        ticksTotal: document.getElementById("autTicksTotal"),
        goalRunsTotal: document.getElementById("autGoalRunsTotal"),
        budgetBlockedTotal: document.getElementById("autBudgetBlockedTotal"),
        dispatchFailuresTotal: document.getElementById("autDispatchFailuresTotal"),
        autoChatSentTotal: document.getElementById("autAutoChatSentTotal"),
        budgetUsage10m: document.getElementById("autBudgetUsage10m"),
        budgetUsage60m: document.getElementById("autBudgetUsage60m"),
        budgetUsageDaily: document.getElementById("autBudgetUsageDaily"),
        queuePending: document.getElementById("autQueuePending"),
        queueApproved: document.getElementById("autQueueApproved"),
        queueRejected: document.getElementById("autQueueRejected"),
        queueIgnored: document.getElementById("autQueueIgnored"),
        tickReasonInput: document.getElementById("autTickReasonInput"),
        tickBtn: document.getElementById("autRunTickBtn"),
        feedback: document.getElementById("autTickFeedbackMsg"),
    };
}

export function setAutonomyBusy(els, busy) {
    const disabled = Boolean(busy);
    if (els?.tickBtn) els.tickBtn.disabled = disabled;
    if (els?.tickReasonInput) els.tickReasonInput.disabled = disabled;
}

export function showAutonomyFeedback(els, message, type = "info") {
    if (!els?.feedback) return;
    setText(els.feedback, message);
    els.feedback.className = `panel-hint event-level-${type === "ok" ? "info" : type}`;
}

function formatBudget(currentValue, limitValue) {
    return `${formatNumber(currentValue)} / ${formatNumber(limitValue)}`;
}

export function renderAutonomyRuntime(runtimePayload, els) {
    const runtime = runtimePayload && typeof runtimePayload === "object" ? runtimePayload : {};
    const budget = runtime.budget_usage || {};
    const queue = runtime.queue || {};

    setText(els?.enabledState, runtime.enabled ? "ON" : "OFF");
    setText(els?.loopState, runtime.loop_running ? "running" : "idle");
    setText(els?.lastHeartbeat, runtime.last_heartbeat_at || "-");
    setText(els?.lastTick, runtime.last_tick_at || "-");
    setText(els?.lastGoal, runtime.last_goal_id || "-");
    setText(els?.lastRisk, runtime.last_goal_risk || "-");
    setText(els?.lastBlockReason, runtime.autonomy_last_block_reason || "-");

    setText(els?.ticksTotal, formatNumber(runtime.autonomy_ticks_total));
    setText(els?.goalRunsTotal, formatNumber(runtime.autonomy_goal_runs_total));
    setText(els?.budgetBlockedTotal, formatNumber(runtime.autonomy_budget_blocked_total));
    setText(els?.dispatchFailuresTotal, formatNumber(runtime.autonomy_dispatch_failures_total));
    setText(els?.autoChatSentTotal, formatNumber(runtime.autonomy_auto_chat_sent_total));

    setText(
        els?.budgetUsage10m,
        formatBudget(budget.messages_10m || 0, budget.limit_10m || 0)
    );
    setText(
        els?.budgetUsage60m,
        formatBudget(budget.messages_60m || 0, budget.limit_60m || 0)
    );
    setText(
        els?.budgetUsageDaily,
        formatBudget(budget.messages_daily || 0, budget.limit_daily || 0)
    );

    setText(els?.queuePending, formatNumber(queue.pending));
    setText(els?.queueApproved, formatNumber(queue.approved));
    setText(els?.queueRejected, formatNumber(queue.rejected));
    setText(els?.queueIgnored, formatNumber(queue.ignored));
}
