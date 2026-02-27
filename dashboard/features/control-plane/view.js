import { asArray, setText } from "../shared/dom.js";

const SUPPORTED_RISKS = [
  "auto_chat",
  "suggest_streamer",
  "moderation_action",
  "clip_candidate",
];
const SUPPORTED_GOAL_KPIS = [
  "auto_chat_sent",
  "action_queued",
  "clip_candidate_queued",
];
const SUPPORTED_COMPARISONS = ["gte", "lte", "eq"];

function defaultKpiForRisk(risk) {
  if (risk === "auto_chat") return "auto_chat_sent";
  if (risk === "clip_candidate") return "clip_candidate_queued";
  return "action_queued";
}

function normalizeGoalComparison(rawValue) {
  const comparison = String(rawValue || "")
    .trim()
    .toLowerCase();
  if (SUPPORTED_COMPARISONS.includes(comparison)) {
    return comparison;
  }
  return "gte";
}

function readInt(input, fallbackValue, minValue, maxValue) {
  const parsed = Number.parseInt(String(input?.value || ""), 10);
  if (!Number.isFinite(parsed)) {
    return fallbackValue;
  }
  return Math.max(minValue, Math.min(maxValue, parsed));
}

function readOptionalFloat(input, minValue, maxValue) {
  const rawValue = String(input?.value || "").trim();
  if (!rawValue) {
    return null;
  }
  const parsed = Number.parseFloat(rawValue);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  const safeValue = Math.max(minValue, Math.min(maxValue, parsed));
  return Number(safeValue.toFixed(4));
}

function readFloat(input, fallbackValue, minValue, maxValue) {
  const parsed = Number.parseFloat(String(input?.value || "").trim());
  if (!Number.isFinite(parsed)) {
    return fallbackValue;
  }
  const safeValue = Math.max(minValue, Math.min(maxValue, parsed));
  return Number(safeValue.toFixed(4));
}

function normalizeGoalId(rawValue, fallbackIndex) {
  const lowered = String(rawValue || "")
    .trim()
    .toLowerCase();
  const normalized = lowered
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized || `goal_${fallbackIndex + 1}`;
}

function buildOptionSelect(values, currentValue) {
  const select = document.createElement("select");
  select.className = "form-control";
  values.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === currentValue) {
      option.selected = true;
    }
    select.appendChild(option);
  });
  return select;
}

function buildRiskSelect(currentRisk) {
  const select = buildOptionSelect(SUPPORTED_RISKS, currentRisk);
  select.dataset.goalField = "risk";
  return select;
}

function buildKpiSelect(currentKpi) {
  const select = buildOptionSelect(SUPPORTED_GOAL_KPIS, currentKpi);
  select.dataset.goalField = "kpi_name";
  return select;
}

function buildComparisonSelect(currentComparison) {
  const select = buildOptionSelect(SUPPORTED_COMPARISONS, currentComparison);
  select.dataset.goalField = "comparison";
  return select;
}

function createGoalField(labelText, fieldElement, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = "form-group";
  if (options.minWidth) {
    wrapper.style.minWidth = options.minWidth;
  }

  const label = document.createElement("label");
  label.textContent = labelText;
  wrapper.appendChild(label);
  wrapper.appendChild(fieldElement);
  return wrapper;
}

function formatGoalMetricValue(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "0";
  if (Number.isInteger(parsed)) return String(parsed);
  return String(Number(parsed.toFixed(4)));
}

function formatGoalSessionResult(sessionResult = {}) {
  const result =
    sessionResult && typeof sessionResult === "object" ? sessionResult : {};
  const evaluatedAt = String(result.evaluated_at || "").trim();
  if (!evaluatedAt) {
    return "Ultima avaliacao: sem execucao registrada.";
  }
  const comparison = normalizeGoalComparison(result.comparison);
  const comparisonLabel =
    comparison === "lte" ? "<=" : comparison === "eq" ? "=" : ">=";
  const met = Boolean(result.met);
  const outcome = String(result.outcome || "n/a").trim() || "n/a";
  return (
    `Ultima avaliacao: ${met ? "MET" : "MISS"} | ` +
    `${formatGoalMetricValue(result.observed_value)} ` +
    `${comparisonLabel} ${formatGoalMetricValue(result.target_value)} | ` +
    `outcome: ${outcome} | ${evaluatedAt}`
  );
}

function createGoalCard(goal = {}, index = 0) {
  const card = document.createElement("li");
  card.className = "card";
  card.dataset.goalItem = "1";
  card.style.listStyle = "none";
  const goalRiskRaw = String(goal.risk || "")
    .trim()
    .toLowerCase();
  const safeRisk = SUPPORTED_RISKS.includes(goalRiskRaw)
    ? goalRiskRaw
    : "suggest_streamer";

  const headerRow = document.createElement("div");
  headerRow.style.display = "flex";
  headerRow.style.alignItems = "center";
  headerRow.style.justifyContent = "space-between";
  headerRow.style.gap = "var(--spacing-2)";
  headerRow.style.marginBottom = "var(--spacing-3)";

  const title = document.createElement("strong");
  title.textContent = `Goal #${index + 1}`;
  headerRow.appendChild(title);

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-danger";
  removeBtn.style.padding = "0.2rem 0.6rem";
  removeBtn.style.fontSize = "0.75rem";
  removeBtn.textContent = "Remover";
  removeBtn.dataset.goalRemove = "1";
  headerRow.appendChild(removeBtn);
  card.appendChild(headerRow);

  const firstRow = document.createElement("div");
  firstRow.className = "form-row";
  firstRow.style.flexWrap = "wrap";

  const enabledInput = document.createElement("input");
  enabledInput.type = "checkbox";
  enabledInput.checked = Boolean(goal.enabled);
  enabledInput.dataset.goalField = "enabled";
  enabledInput.style.width = "18px";
  enabledInput.style.height = "18px";
  firstRow.appendChild(
    createGoalField("Ativo", enabledInput, { minWidth: "80px" }),
  );

  const idInput = document.createElement("input");
  idInput.type = "text";
  idInput.className = "form-control";
  idInput.value = String(goal.id || "");
  idInput.dataset.goalField = "id";
  firstRow.appendChild(createGoalField("ID", idInput, { minWidth: "170px" }));

  const riskSelect = buildRiskSelect(safeRisk);
  firstRow.appendChild(
    createGoalField("Risco", riskSelect, { minWidth: "190px" }),
  );

  const intervalInput = document.createElement("input");
  intervalInput.type = "number";
  intervalInput.className = "form-control";
  intervalInput.min = "60";
  intervalInput.max = "86400";
  intervalInput.step = "1";
  intervalInput.value = String(goal.interval_seconds || 600);
  intervalInput.dataset.goalField = "interval_seconds";
  firstRow.appendChild(
    createGoalField("Intervalo (s)", intervalInput, { minWidth: "140px" }),
  );
  card.appendChild(firstRow);

  const secondRow = document.createElement("div");
  secondRow.className = "form-row";
  secondRow.style.flexWrap = "wrap";
  secondRow.style.marginTop = "var(--spacing-2)";

  const goalKpiNameRaw = String(goal.kpi_name || "")
    .trim()
    .toLowerCase();
  const safeKpiName = SUPPORTED_GOAL_KPIS.includes(goalKpiNameRaw)
    ? goalKpiNameRaw
    : defaultKpiForRisk(safeRisk);
  const kpiSelect = buildKpiSelect(safeKpiName);
  secondRow.appendChild(createGoalField("KPI", kpiSelect, { minWidth: "190px" }));

  const targetInput = document.createElement("input");
  targetInput.type = "number";
  targetInput.className = "form-control";
  targetInput.min = "0";
  targetInput.max = "10000";
  targetInput.step = "0.1";
  targetInput.value = String(goal.target_value ?? 1);
  targetInput.dataset.goalField = "target_value";
  secondRow.appendChild(
    createGoalField("Target", targetInput, { minWidth: "120px" }),
  );

  const comparisonSelect = buildComparisonSelect(
    normalizeGoalComparison(goal.comparison),
  );
  secondRow.appendChild(
    createGoalField("Comparacao", comparisonSelect, { minWidth: "120px" }),
  );

  const windowInput = document.createElement("input");
  windowInput.type = "number";
  windowInput.className = "form-control";
  windowInput.min = "1";
  windowInput.max = "1440";
  windowInput.step = "1";
  windowInput.value = String(goal.window_minutes ?? 60);
  windowInput.dataset.goalField = "window_minutes";
  secondRow.appendChild(
    createGoalField("Janela (min)", windowInput, { minWidth: "140px" }),
  );
  card.appendChild(secondRow);

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "form-control";
  nameInput.value = String(goal.name || "");
  nameInput.dataset.goalField = "name";
  card.appendChild(createGoalField("Nome", nameInput));

  const promptInput = document.createElement("textarea");
  promptInput.className = "form-control";
  promptInput.rows = 3;
  promptInput.value = String(goal.prompt || "");
  promptInput.dataset.goalField = "prompt";
  card.appendChild(createGoalField("Prompt", promptInput));

  const sessionResultHint = document.createElement("p");
  sessionResultHint.className = "panel-hint";
  sessionResultHint.style.margin = "var(--spacing-2) 0 0 0";
  sessionResultHint.textContent = formatGoalSessionResult(goal.session_result);
  card.appendChild(sessionResultHint);

  return card;
}

function parseGoalFromCard(card, index) {
  const getField = (fieldName) =>
    card.querySelector(`[data-goal-field="${fieldName}"]`);
  const riskRaw = String(getField("risk")?.value || "")
    .trim()
    .toLowerCase();
  const safeRisk = SUPPORTED_RISKS.includes(riskRaw)
    ? riskRaw
    : "suggest_streamer";
  const kpiRaw = String(getField("kpi_name")?.value || "")
    .trim()
    .toLowerCase();
  const safeKpi = SUPPORTED_GOAL_KPIS.includes(kpiRaw)
    ? kpiRaw
    : defaultKpiForRisk(safeRisk);
  const safeName =
    String(getField("name")?.value || "").trim() || `Goal ${index + 1}`;
  const safePrompt =
    String(getField("prompt")?.value || "").trim() || `Objetivo ${index + 1}.`;

  return {
    id: normalizeGoalId(getField("id")?.value, index),
    name: safeName,
    prompt: safePrompt,
    risk: safeRisk,
    interval_seconds: readInt(getField("interval_seconds"), 600, 60, 86400),
    enabled: Boolean(getField("enabled")?.checked),
    kpi_name: safeKpi,
    target_value: readFloat(getField("target_value"), 1, 0, 10000),
    window_minutes: readInt(getField("window_minutes"), 60, 1, 1440),
    comparison: normalizeGoalComparison(getField("comparison")?.value),
  };
}

function refreshGoalTitles(goalList) {
  const cards = asArray(
    Array.from(goalList?.querySelectorAll("[data-goal-item='1']") || []),
  );
  cards.forEach((card, index) => {
    const title = card.querySelector("strong");
    if (title) {
      title.textContent = `Goal #${index + 1}`;
    }
  });
}

function clearGoalList(goalList) {
  if (!goalList) return;
  goalList.innerHTML = "";
}

function renderAgentSuspension(els, autonomy = {}, config = {}) {
  const suspended = Boolean(autonomy.suspended ?? config.agent_suspended);
  const reason = String(autonomy.suspend_reason || "").trim();

  els.currentSuspendedState = suspended;

  if (els?.panel) {
    if (suspended) {
      els.panel.classList.add("attention-required");
    } else {
      els.panel.classList.remove("attention-required");
    }
  }

  if (els?.agentStatusChip) {
    els.agentStatusChip.classList.remove("ok", "warn", "pending", "error");
    setText(els.agentStatusChip, suspended ? "SUSPENDED" : "RUNNING");
    els.agentStatusChip.classList.add(suspended ? "error" : "ok");
  }

  if (els?.agentStatusHint) {
    if (suspended) {
      const since = autonomy.suspended_at
        ? ` desde ${autonomy.suspended_at}`
        : "";
      setText(
        els.agentStatusHint,
        `Motivo: ${reason || "manual_dashboard"}${since}.`,
      );
    } else {
      const resumedAt = String(autonomy.last_resumed_at || "").trim();
      const resumeReason = String(autonomy.last_resume_reason || "").trim();
      if (resumedAt) {
        setText(
          els.agentStatusHint,
          `Ultima retomada: ${resumeReason || "manual_dashboard"} em ${resumedAt}.`,
        );
      } else {
        setText(els.agentStatusHint, "Agente operacional.");
      }
    }
  }
}

export function renderChannelConfig(channelPayload, els) {
  const channel =
    channelPayload && typeof channelPayload === "object" ? channelPayload : {};
  const channelId =
    String(channel.channel_id || "default")
      .trim()
      .toLowerCase() || "default";
  const hasOverride = Boolean(channel.has_override);
  const agentPaused = Boolean(channel.agent_paused);

  if (els?.channelIdInput) {
    els.channelIdInput.value = channelId;
  }
  if (els?.channelTemperatureInput) {
    els.channelTemperatureInput.value =
      channel.temperature === null || channel.temperature === undefined
        ? ""
        : String(channel.temperature);
  }
  if (els?.channelTopPInput) {
    els.channelTopPInput.value =
      channel.top_p === null || channel.top_p === undefined
        ? ""
        : String(channel.top_p);
  }
  if (els?.channelAgentPausedInput) {
    els.channelAgentPausedInput.checked = agentPaused;
  }
  if (els?.channelStatusChip) {
    els.channelStatusChip.classList.remove("ok", "warn", "pending", "error");
    setText(
      els.channelStatusChip,
      agentPaused
        ? "CHANNEL PAUSED"
        : hasOverride
          ? "OVERRIDE ACTIVE"
          : "MODEL DEFAULT",
    );
    els.channelStatusChip.classList.add(
      agentPaused ? "warn" : hasOverride ? "ok" : "pending",
    );
  }
  if (els?.channelHint) {
    const temperatureLabel =
      channel.temperature === null || channel.temperature === undefined
        ? "auto"
        : channel.temperature;
    const topPLabel =
      channel.top_p === null || channel.top_p === undefined
        ? "auto"
        : channel.top_p;
    const pauseLabel = agentPaused ? "on" : "off";
    const updatedAt = String(channel.updated_at || "").trim();
    const updatedSuffix = updatedAt ? ` | atualizado: ${updatedAt}` : "";
    setText(
      els.channelHint,
      `Canal ${channelId} | pause: ${pauseLabel} | temperature: ${temperatureLabel} | top_p: ${topPLabel}${updatedSuffix}`,
    );
  }
}

export function renderAgentNotes(notePayload, els) {
  const note =
    notePayload && typeof notePayload === "object" ? notePayload : {};
  const channelId =
    String(note.channel_id || "default")
      .trim()
      .toLowerCase() || "default";
  const notes = String(note.notes || "");
  const hasNotes = Boolean(note.has_notes);

  if (els?.agentNotesInput) {
    els.agentNotesInput.value = notes;
  }
  if (els?.agentNotesStatusChip) {
    els.agentNotesStatusChip.classList.remove("ok", "warn", "pending", "error");
    setText(
      els.agentNotesStatusChip,
      hasNotes ? "NOTES ACTIVE" : "NOTES CLEAR",
    );
    els.agentNotesStatusChip.classList.add(hasNotes ? "ok" : "pending");
  }
  if (els?.agentNotesHint) {
    const updatedAt = String(note.updated_at || "").trim();
    const updatedSuffix = updatedAt ? ` | atualizado: ${updatedAt}` : "";
    setText(
      els.agentNotesHint,
      hasNotes
        ? `Canal ${channelId} | notes operacionais ativas${updatedSuffix}`
        : `Canal ${channelId} | sem notes operacionais persistidas${updatedSuffix}`,
    );
  }
}

export function getControlPlaneElements() {
  return {
    panel: document.getElementById("cpPanel"),
    modeChip: document.getElementById("cpModeChip"),
    agentStatusChip: document.getElementById("cpAgentStatusChip"),
    agentStatusHint: document.getElementById("cpAgentStatusHint"),
    capabilitiesLine: document.getElementById("cpCapabilitiesLine"),
    responseContract: document.getElementById("cpResponseContract"),
    feedback: document.getElementById("cpFeedbackMsg"),
    channelStatusChip: document.getElementById("cpChannelConfigStatusChip"),
    channelHint: document.getElementById("cpChannelConfigHint"),
    channelIdInput: document.getElementById("cpChannelConfigId"),
    channelTemperatureInput: document.getElementById("cpChannelTemperature"),
    channelTopPInput: document.getElementById("cpChannelTopP"),
    channelAgentPausedInput: document.getElementById("cpChannelAgentPaused"),
    agentNotesStatusChip: document.getElementById("cpAgentNotesStatusChip"),
    agentNotesInput: document.getElementById("cpAgentNotes"),
    agentNotesHint: document.getElementById("cpAgentNotesHint"),
    loadChannelConfigBtn: document.getElementById("cpLoadChannelConfigBtn"),
    saveChannelConfigBtn: document.getElementById("cpSaveChannelConfigBtn"),
    autonomyEnabled: document.getElementById("cpAutonomyEnabled"),
    heartbeatInterval: document.getElementById("cpHeartbeatInterval"),
    minCooldown: document.getElementById("cpMinCooldown"),
    budget10m: document.getElementById("cpBudget10m"),
    budget60m: document.getElementById("cpBudget60m"),
    budgetDaily: document.getElementById("cpBudgetDaily"),
    actionIgnoreAfter: document.getElementById("cpActionIgnoreAfter"),
    goalsList: document.getElementById("cpGoalsList"),
    addGoalBtn: document.getElementById("cpAddGoalBtn"),
    saveBtn: document.getElementById("cpSaveBtn"),
    reloadBtn: document.getElementById("cpReloadBtn"),
    suspendBtn: document.getElementById("cpSuspendBtn"),
    resumeBtn: document.getElementById("cpResumeBtn"),
    currentSuspendedState: false,
  };
}

export function showControlPlaneFeedback(els, message, type = "info") {
  if (!els?.feedback) return;
  setText(els.feedback, message);
  els.feedback.className = `panel-hint event-level-${type === "ok" ? "info" : type}`;
}

export function setControlPlaneBusy(els, busy) {
  const disabled = Boolean(busy);
  const inputElements = [
    els?.autonomyEnabled,
    els?.heartbeatInterval,
    els?.minCooldown,
    els?.budget10m,
    els?.budget60m,
    els?.budgetDaily,
    els?.actionIgnoreAfter,
    els?.addGoalBtn,
    els?.saveBtn,
    els?.reloadBtn,
    els?.channelIdInput,
    els?.channelTemperatureInput,
    els?.channelTopPInput,
    els?.channelAgentPausedInput,
    els?.agentNotesInput,
    els?.loadChannelConfigBtn,
    els?.saveChannelConfigBtn,
  ];
  inputElements.forEach((element) => {
    if (element) element.disabled = disabled;
  });

  if (els?.suspendBtn) {
    els.suspendBtn.disabled = disabled || Boolean(els.currentSuspendedState);
  }
  if (els?.resumeBtn) {
    els.resumeBtn.disabled = disabled || !Boolean(els.currentSuspendedState);
  }

  if (els?.goalsList) {
    const controls = els.goalsList.querySelectorAll(
      "input, textarea, select, button",
    );
    controls.forEach((element) => {
      element.disabled = disabled;
    });
    els.goalsList.style.opacity = disabled ? "0.6" : "1";
  }
}

export function renderControlPlaneCapabilities(
  els,
  capabilities = {},
  mode = "",
) {
  const channelCapability = capabilities?.channel_control || {};
  const autonomyCapability = capabilities?.autonomy || {};
  const riskCapability = capabilities?.risk_actions || {};

  if (els?.modeChip) {
    els.modeChip.classList.remove("ok", "warn", "pending", "error");
    const safeMode =
      String(mode || "")
        .trim()
        .toLowerCase() || "eventsub";
    setText(els.modeChip, safeMode.toUpperCase());
    els.modeChip.classList.add(safeMode === "irc" ? "ok" : "warn");
  }

  setText(
    els?.capabilitiesLine,
    `Channel control: ${channelCapability?.enabled ? "on" : "off"} | Autonomia: ${autonomyCapability?.enabled ? "on" : "off"} | Panic: ${autonomyCapability?.suspended ? "suspended" : "ready"} | Risco: ${riskCapability?.enabled ? "on" : "off"}`,
  );

  const responseContract = capabilities?.response_contract || {};
  const maxMessages = Number(responseContract.max_messages || 1);
  const maxLines = Number(responseContract.max_lines || 4);
  setText(
    els?.responseContract,
    `Contrato ativo: ${maxMessages} mensagem / ${maxLines} linhas.`,
  );
}

export function renderControlPlaneState(payload, els) {
  const safePayload = payload && typeof payload === "object" ? payload : {};
  const config = safePayload.config || {};
  const autonomy = safePayload.autonomy || {};

  if (els?.autonomyEnabled)
    els.autonomyEnabled.checked = Boolean(config.autonomy_enabled);
  if (els?.heartbeatInterval)
    els.heartbeatInterval.value = String(
      config.heartbeat_interval_seconds ?? 60,
    );
  if (els?.minCooldown)
    els.minCooldown.value = String(config.min_cooldown_seconds ?? 90);
  if (els?.budget10m)
    els.budget10m.value = String(config.budget_messages_10m ?? 2);
  if (els?.budget60m)
    els.budget60m.value = String(config.budget_messages_60m ?? 8);
  if (els?.budgetDaily)
    els.budgetDaily.value = String(config.budget_messages_daily ?? 30);
  if (els?.actionIgnoreAfter)
    els.actionIgnoreAfter.value = String(
      config.action_ignore_after_seconds ?? 900,
    );

  clearGoalList(els?.goalsList);
  asArray(config.goals).forEach((goal, index) => {
    appendGoalCard(els, goal, index);
  });
  if (!asArray(config.goals).length) {
    appendGoalCard(els, {}, 0);
  }

  renderControlPlaneCapabilities(
    els,
    safePayload.capabilities || {},
    safePayload.mode || "",
  );
  renderAgentSuspension(els, autonomy, config);
}

export function appendGoalCard(els, goal = {}, index = 0) {
  if (!els?.goalsList) return;
  const card = createGoalCard(goal, index);
  const removeButton = card.querySelector("[data-goal-remove='1']");
  if (removeButton) {
    removeButton.addEventListener("click", () => {
      const cardCount = els.goalsList.querySelectorAll(
        "[data-goal-item='1']",
      ).length;
      if (cardCount <= 1) {
        showControlPlaneFeedback(
          els,
          "Mantenha pelo menos 1 goal configurado.",
          "warn",
        );
        return;
      }
      card.remove();
      refreshGoalTitles(els.goalsList);
    });
  }
  els.goalsList.appendChild(card);
  refreshGoalTitles(els.goalsList);
}

export function collectControlPlanePayload(els) {
  const goalsCards = asArray(
    Array.from(els?.goalsList?.querySelectorAll("[data-goal-item='1']") || []),
  );
  const goals = goalsCards.map((card, index) => parseGoalFromCard(card, index));

  return {
    autonomy_enabled: Boolean(els?.autonomyEnabled?.checked),
    heartbeat_interval_seconds: readInt(els?.heartbeatInterval, 60, 15, 3600),
    min_cooldown_seconds: readInt(els?.minCooldown, 90, 15, 3600),
    budget_messages_10m: readInt(els?.budget10m, 2, 0, 100),
    budget_messages_60m: readInt(els?.budget60m, 8, 0, 600),
    budget_messages_daily: readInt(els?.budgetDaily, 30, 0, 5000),
    action_ignore_after_seconds: readInt(
      els?.actionIgnoreAfter,
      900,
      60,
      86400,
    ),
    goals,
  };
}

export function collectChannelConfigPayload(els) {
  const safeChannelId =
    String(els?.channelIdInput?.value || "")
      .trim()
      .toLowerCase() || "default";
  return {
    channel_id: safeChannelId,
    temperature: readOptionalFloat(els?.channelTemperatureInput, 0, 2),
    top_p: readOptionalFloat(els?.channelTopPInput, 0, 1),
    agent_paused: Boolean(els?.channelAgentPausedInput?.checked),
  };
}

export function collectAgentNotesPayload(els) {
  const safeChannelId =
    String(els?.channelIdInput?.value || "")
      .trim()
      .toLowerCase() || "default";
  return {
    channel_id: safeChannelId,
    notes: String(els?.agentNotesInput?.value || ""),
  };
}
