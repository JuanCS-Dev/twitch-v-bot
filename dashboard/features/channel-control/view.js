// dashboard/features/channel-control/view.js
import { setText, getStorageItem, setStorageItem, asArray } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";

export function getChannelControlElements() {
    return {
        adminToken: document.getElementById("adminTokenInput"),
        channelInput: document.getElementById("channelLoginInput"),
        joinBtn: document.getElementById("btnJoinChannel"),
        syncBtn: document.getElementById("btnSyncChannels"),
        cardList: document.getElementById("connectedChannelsList"),
        feedback: document.getElementById("channelFeedbackMsg"),
        modeChip: document.getElementById("channelControlModeChip"),
        modeReason: document.getElementById("channelControlModeReason")
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
            reason || (enabled
                ? "Channel manager em modo completo."
                : "Join/part desabilitados neste modo.")
        );
    }

    if (!enabled) {
        showChannelFeedback(
            els,
            "Join/part desabilitados: este runtime nao opera canais dinamicos fora de IRC.",
            "warn"
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

    safes.forEach(channel => {
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
            partBtn.className = "btn btn-danger";
            partBtn.style.padding = "0.1rem 0.4rem";
            partBtn.style.fontSize = "0.65rem";
            partBtn.title = `Desconectar de #${channel}`;
            partBtn.addEventListener("click", () => {
                partActionCallback(channel);
            });
            chip.appendChild(partBtn);
        }
        els.cardList.appendChild(chip);
    });
}
