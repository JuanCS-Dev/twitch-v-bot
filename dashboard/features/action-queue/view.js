import { asArray, formatNumber, setText } from "../shared/dom.js";

function chipClassByStatus(status) {
    const safeStatus = String(status || "").trim().toLowerCase();
    if (safeStatus === "approved") return "ok";
    if (safeStatus === "rejected") return "error";
    if (safeStatus === "ignored") return "pending";
    return "warn";
}

function chipClassByRisk(risk) {
    const safeRisk = String(risk || "").trim().toLowerCase();
    if (safeRisk === "moderation_action") return "error";
    if (safeRisk === "auto_chat") return "pending";
    return "warn";
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
    noteInput.placeholder = "Nota opcional de auditoria (ex: aprovado para teste).";
    controls.appendChild(noteInput);

    const buttonRow = document.createElement("div");
    buttonRow.style.display = "flex";
    buttonRow.style.gap = "var(--spacing-2)";

    const approveBtn = document.createElement("button");
    approveBtn.type = "button";
    approveBtn.className = "btn btn-primary";
    approveBtn.textContent = "Approve";
    approveBtn.addEventListener("click", () => onDecision(item.id, "approve", noteInput.value));
    buttonRow.appendChild(approveBtn);

    const rejectBtn = document.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "btn btn-danger";
    rejectBtn.textContent = "Reject";
    rejectBtn.addEventListener("click", () => onDecision(item.id, "reject", noteInput.value));
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
    title.textContent = String(item.title || "Acao sem titulo");
    topRow.appendChild(title);
    topRow.appendChild(buildChip(String(item.risk || "unknown"), chipClassByRisk(item.risk)));
    topRow.appendChild(buildChip(String(item.status || "pending"), chipClassByStatus(item.status)));
    card.appendChild(topRow);

    const body = document.createElement("div");
    body.textContent = String(item.body || "-");
    card.appendChild(body);

    const meta = document.createElement("div");
    meta.className = "event-meta";
    meta.textContent = `id=${item.id || "-"} | created=${item.created_at || "-"} | updated=${item.updated_at || "-"}`;
    card.appendChild(meta);

    if (String(item.status || "").trim().toLowerCase() === "pending") {
        card.appendChild(buildPendingActions(item, onDecision));
    } else if (item.decision_note) {
        const note = document.createElement("div");
        note.className = "panel-hint";
        note.textContent = `Nota: ${item.decision_note}`;
        card.appendChild(note);
    }

    return card;
}

export function getActionQueueElements() {
    return {
        panel: document.getElementById("aqPanel"),
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
}

export function showActionQueueFeedback(els, message, type = "info") {
    if (!els?.feedback) return;
    setText(els.feedback, message);
    els.feedback.className = `panel-hint event-level-${type === "ok" ? "info" : type}`;
}

export function getActionQueueQuery(els) {
    const status = String(els?.statusFilter?.value || "").trim().toLowerCase();
    const limitRaw = Number.parseInt(String(els?.limitInput?.value || "80"), 10);
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(300, limitRaw)) : 80;
    if (els?.limitInput) {
        els.limitInput.value = String(limit);
    }
    return { status, limit };
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
        emptyItem.textContent = "Fila sem itens para o filtro atual.";
        els.list.appendChild(emptyItem);
        return;
    }

    items.forEach((item) => {
        els.list.appendChild(buildActionItem(item, onDecision));
    });
}
