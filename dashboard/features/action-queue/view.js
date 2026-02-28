import { asArray, formatNumber, setText } from "../shared/dom.js";

function chipClassByStatus(status) {
  const safeStatus = String(status || "")
    .trim()
    .toLowerCase();
  if (safeStatus === "approved") return "ok";
  if (safeStatus === "rejected") return "error";
  if (safeStatus === "ignored") return "pending";
  return "warn";
}

function chipClassByRisk(risk) {
  const safeRisk = String(risk || "")
    .trim()
    .toLowerCase();
  if (safeRisk === "moderation_action") return "error";
  if (safeRisk === "auto_chat") return "pending";
  return "warn";
}

function chipClassByPlaybookState(state) {
  const safeState = String(state || "")
    .trim()
    .toLowerCase();
  if (safeState === "idle") return "ok";
  if (safeState === "cooldown") return "pending";
  if (safeState === "awaiting_decision") return "warn";
  return "warn";
}

function chipClassByPlaybookOutcome(outcome) {
  const safeOutcome = String(outcome || "")
    .trim()
    .toLowerCase();
  if (safeOutcome === "completed") return "ok";
  if (safeOutcome === "aborted") return "error";
  return "pending";
}

function formatPlaybookState(state) {
  const safeState = String(state || "")
    .trim()
    .toLowerCase();
  if (safeState === "awaiting_decision") return "awaiting decision";
  if (safeState === "cooldown") return "cooldown";
  if (safeState === "idle") return "idle";
  return safeState || "-";
}

function formatPlaybookOutcome(outcome) {
  const safeOutcome = String(outcome || "")
    .trim()
    .toLowerCase();
  if (safeOutcome === "never_run") return "never run";
  if (safeOutcome === "completed") return "completed";
  if (safeOutcome === "aborted") return "aborted";
  return safeOutcome || "-";
}

function buildChip(text, tone) {
  const chip = document.createElement("span");
  chip.className = `chip ${tone}`;
  chip.textContent = String(text || "-");
  return chip;
}

function buildPendingActions(item, onDecision) {
  const controls = document.createElement("div");
  controls.style.display = "flex";
  controls.style.flexDirection = "column";
  controls.style.gap = "var(--spacing-2)";
  controls.style.marginTop = "var(--spacing-3)";

  const noteInput = document.createElement("input");
  noteInput.type = "text";
  noteInput.className = "form-control";
  noteInput.placeholder = "Optional audit note (e.g. approved for test).";
  controls.appendChild(noteInput);

  const buttonRow = document.createElement("div");
  buttonRow.style.display = "flex";
  buttonRow.style.gap = "var(--spacing-2)";

  const approveBtn = document.createElement("button");
  approveBtn.type = "button";
  approveBtn.className = "btn btn-primary";
  approveBtn.textContent = "Approve";
  approveBtn.addEventListener("click", () =>
    onDecision(item.id, "approve", noteInput.value),
  );
  buttonRow.appendChild(approveBtn);

  const rejectBtn = document.createElement("button");
  rejectBtn.type = "button";
  rejectBtn.className = "btn btn-danger";
  rejectBtn.textContent = "Reject";
  rejectBtn.addEventListener("click", () =>
    onDecision(item.id, "reject", noteInput.value),
  );
  buttonRow.appendChild(rejectBtn);

  controls.appendChild(buttonRow);
  return controls;
}

function buildActionItem(item, onDecision) {
  const card = document.createElement("li");
  card.style.display = "flex";
  card.style.flexDirection = "column";
  card.style.gap = "var(--spacing-2)";

  const topRow = document.createElement("div");
  topRow.style.display = "flex";
  topRow.style.flexWrap = "wrap";
  topRow.style.gap = "var(--spacing-2)";
  topRow.style.alignItems = "center";

  const title = document.createElement("strong");
  title.textContent = String(item.title || "Untitled action");
  topRow.appendChild(title);
  topRow.appendChild(
    buildChip(String(item.risk || "unknown"), chipClassByRisk(item.risk)),
  );
  topRow.appendChild(
    buildChip(String(item.status || "pending"), chipClassByStatus(item.status)),
  );
  card.appendChild(topRow);

  const body = document.createElement("div");
  body.textContent = String(item.body || "-");
  card.appendChild(body);

  const meta = document.createElement("div");
  meta.className = "event-meta";
  meta.textContent = `id=${item.id || "-"} | created=${item.created_at || "-"} | updated=${item.updated_at || "-"}`;
  card.appendChild(meta);

  if (
    String(item.status || "")
      .trim()
      .toLowerCase() === "pending"
  ) {
    card.appendChild(buildPendingActions(item, onDecision));
  } else if (item.decision_note) {
    const note = document.createElement("div");
    note.className = "panel-hint";
    note.textContent = `Note: ${item.decision_note}`;
    card.appendChild(note);
  }

  return card;
}

function buildPlaybookItem(item) {
  const card = document.createElement("li");
  card.style.display = "flex";
  card.style.flexDirection = "column";
  card.style.gap = "var(--spacing-2)";

  const topRow = document.createElement("div");
  topRow.style.display = "flex";
  topRow.style.flexWrap = "wrap";
  topRow.style.gap = "var(--spacing-2)";
  topRow.style.alignItems = "center";

  const title = document.createElement("strong");
  title.textContent = String(item?.name || item?.id || "Playbook");
  topRow.appendChild(title);
  topRow.appendChild(
    buildChip(
      formatPlaybookState(item?.state),
      chipClassByPlaybookState(item?.state),
    ),
  );
  topRow.appendChild(
    buildChip(
      formatPlaybookOutcome(item?.last_outcome),
      chipClassByPlaybookOutcome(item?.last_outcome),
    ),
  );
  card.appendChild(topRow);

  const description = document.createElement("div");
  description.textContent = String(item?.description || "-");
  card.appendChild(description);

  const step = Number(item?.current_step_number || 0);
  const totalSteps = Number(item?.total_steps || 0);
  const waitingActionId = String(item?.waiting_action_id || "").trim();
  const progress = document.createElement("div");
  progress.className = "panel-hint";
  progress.textContent =
    step > 0 && totalSteps > 0
      ? `Step ${step}/${totalSteps}: ${item?.current_step_title || "-"}`
      : `Total steps: ${formatNumber(totalSteps)}`;
  card.appendChild(progress);

  const meta = document.createElement("div");
  meta.className = "event-meta";
  meta.textContent = `id=${item?.id || "-"} | run=${item?.last_run_id || "-"} | updated=${item?.updated_at || "-"}`;
  card.appendChild(meta);

  const detail = document.createElement("div");
  detail.className = "panel-hint";
  if (waitingActionId) {
    detail.textContent = `Awaiting queue decision for action_id=${waitingActionId}.`;
  } else if (
    String(item?.state || "")
      .trim()
      .toLowerCase() === "cooldown"
  ) {
    detail.textContent = `Cooldown until ${item?.cooldown_until || "-"}.`;
  } else {
    detail.textContent = `Last reason: ${item?.last_outcome_reason || "n/a"}.`;
  }
  card.appendChild(detail);

  return card;
}

export function getActionQueueElements() {
  return {
    panel: document.getElementById("aqPanel"),
    summaryQueuePendingCount: document.getElementById(
      "summaryQueuePendingCount",
    ),
    summaryQueuePendingChip: document.getElementById("summaryQueuePendingChip"),
    statusFilter: document.getElementById("aqStatusFilter"),
    limitInput: document.getElementById("aqLimitInput"),
    refreshBtn: document.getElementById("aqRefreshBtn"),
    feedback: document.getElementById("aqFeedbackMsg"),
    pendingCount: document.getElementById("aqPendingCount"),
    approvedCount: document.getElementById("aqApprovedCount"),
    rejectedCount: document.getElementById("aqRejectedCount"),
    ignoredCount: document.getElementById("aqIgnoredCount"),
    totalCount: document.getElementById("aqTotalCount"),
    list: document.getElementById("aqList"),
    opsUpdatedAt: document.getElementById("aqOpsUpdatedAt"),
    opsIdleCount: document.getElementById("aqOpsIdleCount"),
    opsAwaitingCount: document.getElementById("aqOpsAwaitingCount"),
    opsCooldownCount: document.getElementById("aqOpsCooldownCount"),
    opsCompletedCount: document.getElementById("aqOpsCompletedCount"),
    opsAbortedCount: document.getElementById("aqOpsAbortedCount"),
    opsPlaybookSelect: document.getElementById("aqOpsPlaybookSelect"),
    opsReasonInput: document.getElementById("aqOpsReasonInput"),
    opsForceToggle: document.getElementById("aqOpsForceToggle"),
    opsRefreshBtn: document.getElementById("aqOpsRefreshBtn"),
    opsTriggerBtn: document.getElementById("aqOpsTriggerBtn"),
    opsFeedback: document.getElementById("aqOpsFeedbackMsg"),
    opsList: document.getElementById("aqOpsList"),
  };
}

export function setActionQueueBusy(els, busy) {
  const disabled = Boolean(busy);
  if (els?.statusFilter) els.statusFilter.disabled = disabled;
  if (els?.limitInput) els.limitInput.disabled = disabled;
  if (els?.refreshBtn) els.refreshBtn.disabled = disabled;
  if (els?.list) {
    const actionButtons = els.list.querySelectorAll("button");
    actionButtons.forEach((button) => {
      button.disabled = disabled;
    });
    els.list.style.opacity = disabled ? "0.7" : "1";
  }
  if (els?.opsPlaybookSelect) els.opsPlaybookSelect.disabled = disabled;
  if (els?.opsReasonInput) els.opsReasonInput.disabled = disabled;
  if (els?.opsForceToggle) els.opsForceToggle.disabled = disabled;
  if (els?.opsRefreshBtn) els.opsRefreshBtn.disabled = disabled;
  if (els?.opsTriggerBtn) els.opsTriggerBtn.disabled = disabled;
  if (els?.opsList) {
    els.opsList.style.opacity = disabled ? "0.7" : "1";
  }
}

export function showActionQueueFeedback(els, message, type = "info") {
  if (!els?.feedback) return;
  setText(els.feedback, message);
  els.feedback.className = `panel-hint event-level-${type === "ok" ? "info" : type}`;
}

export function showOpsPlaybooksFeedback(els, message, type = "info") {
  if (!els?.opsFeedback) return;
  setText(els.opsFeedback, message);
  els.opsFeedback.className = `panel-hint event-level-${type === "ok" ? "info" : type}`;
}

export function getActionQueueQuery(els) {
  const status = String(els?.statusFilter?.value || "")
    .trim()
    .toLowerCase();
  const limitRaw = Number.parseInt(String(els?.limitInput?.value || "80"), 10);
  const limit = Number.isFinite(limitRaw)
    ? Math.max(1, Math.min(300, limitRaw))
    : 80;
  if (els?.limitInput) {
    els.limitInput.value = String(limit);
  }
  return { status, limit };
}

function syncOpsPlaybookSelect(playbooks, selectEl) {
  if (!selectEl) return;
  const items = asArray(playbooks).filter((item) => item && item.id);
  const previousValue = String(selectEl.value || "")
    .trim()
    .toLowerCase();
  selectEl.innerHTML = "";
  if (!items.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No playbook";
    selectEl.appendChild(option);
    selectEl.value = "";
    return;
  }

  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.id || "")
      .trim()
      .toLowerCase();
    option.textContent = String(item.name || item.id || "Playbook");
    selectEl.appendChild(option);
  });

  const hasPrevious = items.some(
    (item) =>
      String(item.id || "")
        .trim()
        .toLowerCase() === previousValue,
  );
  selectEl.value = hasPrevious
    ? previousValue
    : String(items[0].id || "")
        .trim()
        .toLowerCase();
}

function renderOpsPlaybookRows(playbooks, targetList) {
  if (!targetList) return;
  targetList.innerHTML = "";
  const items = asArray(playbooks);
  if (!items.length) {
    const emptyItem = document.createElement("li");
    emptyItem.style.fontStyle = "italic";
    emptyItem.style.color = "var(--text-muted)";
    emptyItem.textContent = "No operational playbooks registered.";
    targetList.appendChild(emptyItem);
    return;
  }
  items.forEach((playbook) => {
    targetList.appendChild(buildPlaybookItem(playbook));
  });
}

export function getOpsPlaybookTriggerPayload(els, channelId = "default") {
  const playbookId = String(els?.opsPlaybookSelect?.value || "")
    .trim()
    .toLowerCase();
  const reason =
    String(els?.opsReasonInput?.value || "").trim() || "manual_dashboard";
  const force = Boolean(els?.opsForceToggle?.checked);
  return {
    playbookId,
    channelId:
      String(channelId || "")
        .trim()
        .toLowerCase() || "default",
    reason,
    force,
  };
}

function renderSummaryQueueState(els, pendingCount) {
  const safePending = Number.isFinite(Number(pendingCount))
    ? Number(pendingCount)
    : 0;
  setText(els?.summaryQueuePendingCount, formatNumber(safePending));
  if (!els?.summaryQueuePendingChip) return;
  els.summaryQueuePendingChip.classList.remove(
    "ok",
    "warn",
    "error",
    "pending",
  );
  if (safePending <= 0) {
    setText(els.summaryQueuePendingChip, "CLEAR");
    els.summaryQueuePendingChip.classList.add("ok");
    return;
  }
  if (safePending >= 5) {
    setText(els.summaryQueuePendingChip, "HIGH LOAD");
    els.summaryQueuePendingChip.classList.add("error");
    return;
  }
  setText(els.summaryQueuePendingChip, "REVIEW");
  els.summaryQueuePendingChip.classList.add("warn");
}

export function renderActionQueuePayload(payload, els, onDecision) {
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const summary = safePayload.summary || {};
  const items = asArray(safePayload.items);

  setText(els?.pendingCount, formatNumber(summary.pending));
  setText(els?.approvedCount, formatNumber(summary.approved));
  setText(els?.rejectedCount, formatNumber(summary.rejected));
  setText(els?.ignoredCount, formatNumber(summary.ignored));
  setText(els?.totalCount, formatNumber(summary.total));
  renderSummaryQueueState(els, summary.pending);

  if (els?.panel) {
    if (summary.pending > 0) {
      els.panel.classList.add("attention-required");
    } else {
      els.panel.classList.remove("attention-required");
    }
  }

  if (!els?.list) return;
  els.list.innerHTML = "";
  if (!items.length) {
    const emptyItem = document.createElement("li");
    emptyItem.style.fontStyle = "italic";
    emptyItem.style.color = "var(--text-muted)";
    emptyItem.textContent = "Queue has no items for the current filter.";
    els.list.appendChild(emptyItem);
    return;
  }

  items.forEach((item) => {
    els.list.appendChild(buildActionItem(item, onDecision));
  });
}

export function renderOpsPlaybooksPayload(payload, els) {
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const summary = safePayload.summary || {};
  const playbooks = asArray(safePayload.playbooks);

  setText(els?.opsUpdatedAt, safePayload.updated_at || "-");
  setText(els?.opsIdleCount, formatNumber(summary.idle));
  setText(els?.opsAwaitingCount, formatNumber(summary.awaiting_decision));
  setText(els?.opsCooldownCount, formatNumber(summary.cooldown));
  setText(els?.opsCompletedCount, formatNumber(summary.completed));
  setText(els?.opsAbortedCount, formatNumber(summary.aborted));

  syncOpsPlaybookSelect(playbooks, els?.opsPlaybookSelect);
  renderOpsPlaybookRows(playbooks, els?.opsList);
}
