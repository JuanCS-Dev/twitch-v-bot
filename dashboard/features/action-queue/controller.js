import {
    decideActionQueueItem,
    getActionQueue,
} from "./api.js";
import {
    getActionQueueQuery,
    renderActionQueuePayload,
    setActionQueueBusy,
    showActionQueueFeedback,
} from "./view.js";

const ACTION_QUEUE_INTERVAL_MS = 12000;

export function createActionQueueController({
    aqEls,
    fetchAndRenderObservability,
    getErrorMessage,
}) {
    let isPolling = false;
    let timerId = 0;

    async function refreshActionQueue({ showFeedback = true } = {}) {
        if (!aqEls || isPolling) return;
        isPolling = true;
        setActionQueueBusy(aqEls, true);
        if (showFeedback) {
            showActionQueueFeedback(aqEls, "Carregando fila de risco...", "warn");
        }
        try {
            const query = getActionQueueQuery(aqEls);
            const payload = await getActionQueue(query);
            renderActionQueuePayload(payload, aqEls, decideQueueItem);
            if (showFeedback) {
                showActionQueueFeedback(
                    aqEls,
                    `Fila atualizada (${payload?.summary?.total || 0} itens).`,
                    "ok"
                );
            }
        } catch (error) {
            console.error("Action queue refresh error", error);
            showActionQueueFeedback(
                aqEls,
                `Erro: ${getErrorMessage(error, "Falha ao carregar fila.")}`,
                "error"
            );
        } finally {
            isPolling = false;
            setActionQueueBusy(aqEls, false);
        }
    }

    function scheduleActionQueuePolling() {
        if (timerId) {
            window.clearTimeout(timerId);
        }
        timerId = window.setTimeout(async () => {
            await refreshActionQueue({ showFeedback: false });
            scheduleActionQueuePolling();
        }, ACTION_QUEUE_INTERVAL_MS);
    }

    async function decideQueueItem(actionId, decision, note = "") {
        if (!aqEls) return;
        setActionQueueBusy(aqEls, true);
        showActionQueueFeedback(
            aqEls,
            `Aplicando decisao ${decision} em ${actionId}...`,
            "warn"
        );
        try {
            await decideActionQueueItem(actionId, decision, note);
            showActionQueueFeedback(aqEls, "Decisao registrada.", "ok");
            await Promise.all([
                refreshActionQueue({ showFeedback: false }),
                fetchAndRenderObservability(),
            ]);
        } catch (error) {
            console.error("Action queue decision error", error);
            showActionQueueFeedback(
                aqEls,
                `Erro: ${getErrorMessage(error, "Falha ao registrar decisao.")}`,
                "error"
            );
        } finally {
            setActionQueueBusy(aqEls, false);
        }
    }

    function bindActionQueueEvents() {
        if (!aqEls) return;
        if (aqEls.refreshBtn) {
            aqEls.refreshBtn.addEventListener("click", () => {
                refreshActionQueue({ showFeedback: true });
            });
        }
        if (aqEls.statusFilter) {
            aqEls.statusFilter.addEventListener("change", () => {
                refreshActionQueue({ showFeedback: true });
            });
        }
        if (aqEls.limitInput) {
            aqEls.limitInput.addEventListener("change", () => {
                refreshActionQueue({ showFeedback: true });
            });
        }
    }

    return {
        bindActionQueueEvents,
        refreshActionQueue,
        scheduleActionQueuePolling,
    };
}

