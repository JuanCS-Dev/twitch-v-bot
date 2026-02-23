import { asArray, setText } from "../shared/dom.js";

const SUPPORTED_RISKS = ["auto_chat", "suggest_streamer", "moderation_action"];

function readInt(input, fallbackValue, minValue, maxValue) {
    const parsed = Number.parseInt(String(input?.value || ""), 10);
    if (!Number.isFinite(parsed)) {
        return fallbackValue;
    }
    return Math.max(minValue, Math.min(maxValue, parsed));
}

function normalizeGoalId(rawValue, fallbackIndex) {
    const lowered = String(rawValue || "").trim().toLowerCase();
    const normalized = lowered.replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    return normalized || `goal_${fallbackIndex + 1}`;
}

function buildRiskSelect(currentRisk) {
    const select = document.createElement("select");
    select.className = "form-control";
    select.dataset.goalField = "risk";
    SUPPORTED_RISKS.forEach((riskName) => {
        const option = document.createElement("option");
        option.value = riskName;
        option.textContent = riskName;
        if (riskName === currentRisk) {
            option.selected = true;
        }
        select.appendChild(option);
    });
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

function createGoalCard(goal = {}, index = 0) {
    const card = document.createElement("li");
    card.className = "card";
    card.dataset.goalItem = "1";
    card.style.listStyle = "none";

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
    firstRow.appendChild(createGoalField("Ativo", enabledInput, { minWidth: "80px" }));

    const idInput = document.createElement("input");
    idInput.type = "text";
    idInput.className = "form-control";
    idInput.value = String(goal.id || "");
    idInput.dataset.goalField = "id";
    firstRow.appendChild(createGoalField("ID", idInput, { minWidth: "170px" }));

    const riskSelect = buildRiskSelect(String(goal.risk || "suggest_streamer"));
    firstRow.appendChild(createGoalField("Risco", riskSelect, { minWidth: "190px" }));

    const intervalInput = document.createElement("input");
    intervalInput.type = "number";
    intervalInput.className = "form-control";
    intervalInput.min = "60";
    intervalInput.max = "86400";
    intervalInput.step = "1";
    intervalInput.value = String(goal.interval_seconds || 600);
    intervalInput.dataset.goalField = "interval_seconds";
    firstRow.appendChild(createGoalField("Intervalo (s)", intervalInput, { minWidth: "140px" }));
    card.appendChild(firstRow);

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

    return card;
}

function parseGoalFromCard(card, index) {
    const getField = (fieldName) => card.querySelector(`[data-goal-field="${fieldName}"]`);
    const riskRaw = String(getField("risk")?.value || "").trim().toLowerCase();
    const safeRisk = SUPPORTED_RISKS.includes(riskRaw) ? riskRaw : "suggest_streamer";
    const safeName = String(getField("name")?.value || "").trim() || `Goal ${index + 1}`;
    const safePrompt = String(getField("prompt")?.value || "").trim() || `Objetivo ${index + 1}.`;

    return {
        id: normalizeGoalId(getField("id")?.value, index),
        name: safeName,
        prompt: safePrompt,
        risk: safeRisk,
        interval_seconds: readInt(getField("interval_seconds"), 600, 60, 86400),
        enabled: Boolean(getField("enabled")?.checked),
    };
}

function refreshGoalTitles(goalList) {
    const cards = asArray(Array.from(goalList?.querySelectorAll("[data-goal-item='1']") || []));
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

export function getControlPlaneElements() {
    return {
        modeChip: document.getElementById("cpModeChip"),
        capabilitiesLine: document.getElementById("cpCapabilitiesLine"),
        responseContract: document.getElementById("cpResponseContract"),
        feedback: document.getElementById("cpFeedbackMsg"),
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
    ];
    inputElements.forEach((element) => {
        if (element) element.disabled = disabled;
    });

    if (els?.goalsList) {
        const controls = els.goalsList.querySelectorAll("input, textarea, select, button");
        controls.forEach((element) => {
            element.disabled = disabled;
        });
        els.goalsList.style.opacity = disabled ? "0.6" : "1";
    }
}

export function renderControlPlaneCapabilities(els, capabilities = {}, mode = "") {
    const channelCapability = capabilities?.channel_control || {};
    const autonomyCapability = capabilities?.autonomy || {};
    const riskCapability = capabilities?.risk_actions || {};

    if (els?.modeChip) {
        els.modeChip.classList.remove("ok", "warn", "pending", "error");
        const safeMode = String(mode || "").trim().toLowerCase() || "eventsub";
        setText(els.modeChip, safeMode.toUpperCase());
        els.modeChip.classList.add(safeMode === "irc" ? "ok" : "warn");
    }

    setText(
        els?.capabilitiesLine,
        `Channel control: ${channelCapability?.enabled ? "on" : "off"} | Autonomia: ${autonomyCapability?.enabled ? "on" : "off"} | Risco: ${riskCapability?.enabled ? "on" : "off"}`
    );

    const responseContract = capabilities?.response_contract || {};
    const maxMessages = Number(responseContract.max_messages || 1);
    const maxLines = Number(responseContract.max_lines || 4);
    setText(els?.responseContract, `Contrato ativo: ${maxMessages} mensagem / ${maxLines} linhas.`);
}

export function renderControlPlaneState(payload, els) {
    const safePayload = payload && typeof payload === "object" ? payload : {};
    const config = safePayload.config || {};

    if (els?.autonomyEnabled) els.autonomyEnabled.checked = Boolean(config.autonomy_enabled);
    if (els?.heartbeatInterval) els.heartbeatInterval.value = String(config.heartbeat_interval_seconds ?? 60);
    if (els?.minCooldown) els.minCooldown.value = String(config.min_cooldown_seconds ?? 90);
    if (els?.budget10m) els.budget10m.value = String(config.budget_messages_10m ?? 2);
    if (els?.budget60m) els.budget60m.value = String(config.budget_messages_60m ?? 8);
    if (els?.budgetDaily) els.budgetDaily.value = String(config.budget_messages_daily ?? 30);
    if (els?.actionIgnoreAfter) els.actionIgnoreAfter.value = String(config.action_ignore_after_seconds ?? 900);

    clearGoalList(els?.goalsList);
    asArray(config.goals).forEach((goal, index) => {
        appendGoalCard(els, goal, index);
    });
    if (!asArray(config.goals).length) {
        appendGoalCard(els, {}, 0);
    }

    renderControlPlaneCapabilities(els, safePayload.capabilities || {}, safePayload.mode || "");
}

export function appendGoalCard(els, goal = {}, index = 0) {
    if (!els?.goalsList) return;
    const card = createGoalCard(goal, index);
    const removeButton = card.querySelector("[data-goal-remove='1']");
    if (removeButton) {
        removeButton.addEventListener("click", () => {
            const cardCount = els.goalsList.querySelectorAll("[data-goal-item='1']").length;
            if (cardCount <= 1) {
                showControlPlaneFeedback(els, "Mantenha pelo menos 1 goal configurado.", "warn");
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
    const goalsCards = asArray(Array.from(els?.goalsList?.querySelectorAll("[data-goal-item='1']") || []));
    const goals = goalsCards.map((card, index) => parseGoalFromCard(card, index));

    return {
        autonomy_enabled: Boolean(els?.autonomyEnabled?.checked),
        heartbeat_interval_seconds: readInt(els?.heartbeatInterval, 60, 15, 3600),
        min_cooldown_seconds: readInt(els?.minCooldown, 90, 15, 3600),
        budget_messages_10m: readInt(els?.budget10m, 2, 0, 100),
        budget_messages_60m: readInt(els?.budget60m, 8, 0, 600),
        budget_messages_daily: readInt(els?.budgetDaily, 30, 0, 5000),
        action_ignore_after_seconds: readInt(els?.actionIgnoreAfter, 900, 60, 86400),
        goals,
    };
}
