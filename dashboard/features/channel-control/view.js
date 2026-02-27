// dashboard/features/channel-control/view.js
import {
  setText,
  getStorageItem,
  setStorageItem,
  asArray,
} from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";
const DASHBOARD_CHANNEL_KEY = "byte_dashboard_focus_channel";

function normalizeDashboardChannelId(value) {
  return (
    String(value || "")
      .trim()
      .toLowerCase() || "default"
  );
}

export function getChannelControlElements() {
  return {
    adminToken: document.getElementById("adminTokenInput"),
    channelInput: document.getElementById("channelLoginInput"),
    joinBtn: document.getElementById("btnJoinChannel"),
    syncBtn: document.getElementById("btnSyncChannels"),
    cardList: document.getElementById("connectedChannelsList"),
    feedback: document.getElementById("channelFeedbackMsg"),
    modeChip: document.getElementById("channelControlModeChip"),
    modeReason: document.getElementById("channelControlModeReason"),
    dashboardChannelInput: document.getElementById("dashboardChannelInput"),
    dashboardChannelBtn: document.getElementById("btnApplyDashboardChannel"),
    dashboardChannelChip: document.getElementById("dashboardChannelChip"),
    dashboardChannelHint: document.getElementById("dashboardChannelHint"),
  };
}

function isJoinAllowed(els) {
  return String(els?.joinBtn?.dataset?.joinAllowed || "1") !== "0";
}

function isChannelBusy(els) {
  return String(els?.syncBtn?.dataset?.busy || "0") === "1";
}

/**
 * Prepara o input de token com o ultimo salvo.
 */
export function initTokenInput(els) {
  if (!els.adminToken) return;
  els.adminToken.value = getStorageItem(TOKEN_KEY);

  const saveAction = () => setStorageItem(TOKEN_KEY, els.adminToken.value);
  els.adminToken.addEventListener("change", saveAction);
  els.adminToken.addEventListener("blur", saveAction);
}

export function initDashboardChannelInput(els, onApply) {
  const safeChannel = getStorageItem(DASHBOARD_CHANNEL_KEY) || "default";
  renderDashboardChannelSelection(els, safeChannel);

  const applySelection = () => {
    const nextChannel = normalizeDashboardChannelId(
      els?.dashboardChannelInput?.value,
    );
    renderDashboardChannelSelection(els, nextChannel);
    if (typeof onApply === "function") {
      onApply(nextChannel);
    }
  };

  if (els?.dashboardChannelBtn) {
    els.dashboardChannelBtn.addEventListener("click", applySelection);
  }
  if (els?.dashboardChannelInput) {
    els.dashboardChannelInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      applySelection();
    });
  }
}

/**
 * Bloqueia os inputs durante operacao transacional.
 */
export function setChannelBusy(els, busy) {
  const activeBusy = Boolean(busy);
  if (els.syncBtn) {
    els.syncBtn.dataset.busy = activeBusy ? "1" : "0";
  }

  if (els.adminToken) els.adminToken.disabled = activeBusy;
  const joinAllowed = isJoinAllowed(els);
  if (els.channelInput) els.channelInput.disabled = activeBusy || !joinAllowed;
  if (els.joinBtn) els.joinBtn.disabled = activeBusy || !joinAllowed;
  if (els.syncBtn) els.syncBtn.disabled = activeBusy;

  if (activeBusy && els.cardList) {
    els.cardList.style.opacity = "0.5";
  } else if (els.cardList) {
    els.cardList.style.opacity = "1";
  }
}

/**
 * Exibe feedback de alerta do fluxo (ok, warn, error)
 */
export function showChannelFeedback(els, message, type = "info") {
  if (!els.feedback) return;
  setText(els.feedback, message);
  els.feedback.className = `panel-hint event-level-${type === "ok" ? "info" : type}`;
}

export function renderDashboardChannelSelection(els, channelId) {
  const safeChannel = normalizeDashboardChannelId(channelId);
  if (els?.dashboardChannelInput) {
    els.dashboardChannelInput.value = safeChannel;
  }
  if (els?.dashboardChannelChip) {
    els.dashboardChannelChip.classList.remove("ok", "warn", "error", "pending");
    setText(els.dashboardChannelChip, safeChannel);
    els.dashboardChannelChip.classList.add("ok");
  }
  if (els?.dashboardChannelHint) {
    setText(
      els.dashboardChannelHint,
      `Observability, contexto e histórico persistido seguem #${safeChannel}.`,
    );
  }
  setStorageItem(DASHBOARD_CHANNEL_KEY, safeChannel);
  return safeChannel;
}

export function applyChannelControlCapability(els, capability = {}) {
  const enabled = Boolean(capability?.enabled);
  const reason = String(capability?.reason || "").trim();

  if (els.joinBtn) {
    els.joinBtn.dataset.joinAllowed = enabled ? "1" : "0";
  }

  if (els.modeChip) {
    els.modeChip.classList.remove("ok", "warn", "error", "pending");
    if (enabled) {
      setText(els.modeChip, "IRC runtime");
      els.modeChip.classList.add("ok");
    } else {
      setText(els.modeChip, "EventSub");
      els.modeChip.classList.add("warn");
    }
  }

  if (els.modeReason) {
    setText(
      els.modeReason,
      reason ||
        (enabled
          ? "Channel manager em modo completo."
          : "Join/part desabilitados neste modo."),
    );
  }

  if (!enabled) {
    showChannelFeedback(
      els,
      "Join/part desabilitados: este runtime nao opera canais dinamicos fora de IRC.",
      "warn",
    );
  }
  setChannelBusy(els, isChannelBusy(els));
}

/**
 * Desenha os channel chips iterativos conforme a API list retornou.
 */
export function renderConnectedChannels(els, channels, partActionCallback) {
  if (!els.cardList) return;
  els.cardList.innerHTML = "";

  const safes = asArray(channels);
  const joinAllowed = isJoinAllowed(els);
  if (safes.length === 0) {
    const li = document.createElement("li");
    li.style.fontStyle = "italic";
    li.style.color = "var(--text-muted)";
    li.textContent = joinAllowed
      ? "Nenhum canal ativo. O bot esta ocioso."
      : "Modo EventSub ativo: runtime sem canais IRC para listar.";
    els.cardList.appendChild(li);
    return;
  }

  safes.forEach((channel) => {
    const chip = document.createElement("div");
    chip.className = "chip ok";
    chip.style.display = "flex";
    chip.style.gap = "var(--spacing-2)";
    chip.style.alignItems = "center";

    const label = document.createElement("span");
    label.textContent = `#${channel}`;

    chip.appendChild(label);
    if (joinAllowed) {
      const partBtn = document.createElement("button");
      partBtn.textContent = "Sair";
      partBtn.className = "btn btn-danger btn-sm";
      partBtn.title = `Desconectar de #${channel}`;
      partBtn.addEventListener("click", () => {
        partActionCallback(channel);
      });
      chip.appendChild(partBtn);
    }
    els.cardList.appendChild(chip);
  });
}

export function getDashboardChannelSelection(els) {
  return normalizeDashboardChannelId(
    els?.dashboardChannelInput?.value || getStorageItem(DASHBOARD_CHANNEL_KEY),
  );
}
