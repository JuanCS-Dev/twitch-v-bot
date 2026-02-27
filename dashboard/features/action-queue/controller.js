import {
    decideActionQueueItem,
    getActionQueue,
    getOpsPlaybooks,
    triggerOpsPlaybook,
} from "./api.js";
import {
    getActionQueueQuery,
    getOpsPlaybookTriggerPayload,
    renderActionQueuePayload,
    renderOpsPlaybooksPayload,
    setActionQueueBusy,
    showActionQueueFeedback,
    showOpsPlaybooksFeedback,
} from "./view.js";

const ACTION_QUEUE_INTERVAL_MS = 12000;

export function createActionQueueController({
    aqEls,
    fetchAndRenderObservability,
    getErrorMessage,
}) {
    let isPolling = false;
    let timerId = 0;
    let selectedChannel = "default";

    async function refreshActionQueue({ showFeedback = true } = {}) {
        if (!aqEls || isPolling) return;
        isPolling = true;
        setActionQueueBusy(aqEls, true);
        if (showFeedback) {
            showActionQueueFeedback(aqEls, "Carregando fila de risco...", "warn");
            showOpsPlaybooksFeedback(aqEls, "Carregando playbooks operacionais...", "warn");
        }
        try {
            const query = getActionQueueQuery(aqEls);
            const [queueResult, opsResult] = await Promise.allSettled([
                getActionQueue(query),
                getOpsPlaybooks(selectedChannel),
            ]);

            if (queueResult.status === "fulfilled") {
                renderActionQueuePayload(queueResult.value, aqEls, decideQueueItem);
                if (showFeedback) {
                    showActionQueueFeedback(
                        aqEls,
                        `Fila atualizada (${queueResult.value?.summary?.total || 0} itens).`,
                        "ok"
                    );
                }
            } else {
                throw queueResult.reason;
            }

            if (opsResult.status === "fulfilled") {
                renderOpsPlaybooksPayload(opsResult.value, aqEls);
                if (showFeedback) {
                    const awaitingCount = opsResult.value?.summary?.awaiting_decision || 0;
                    showOpsPlaybooksFeedback(
                        aqEls,
                        `Playbooks atualizados (${awaitingCount} aguardando decisao).`,
                        "ok"
                    );
                }
            } else {
                showOpsPlaybooksFeedback(
                    aqEls,
                    `Erro: ${getErrorMessage(
                        opsResult.reason,
                        "Falha ao carregar playbooks operacionais."
                    )}`,
                    "error"
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

    async function triggerSelectedPlaybook() {
        if (!aqEls) return;
        const triggerPayload = getOpsPlaybookTriggerPayload(aqEls, selectedChannel);
        if (!triggerPayload.playbookId) {
            showOpsPlaybooksFeedback(aqEls, "Selecione um playbook para disparar.", "warn");
            return;
        }

        setActionQueueBusy(aqEls, true);
        showOpsPlaybooksFeedback(
            aqEls,
            `Disparando playbook ${triggerPayload.playbookId}...`,
            "warn"
        );
        try {
            const payload = await triggerOpsPlaybook(triggerPayload);
            renderOpsPlaybooksPayload(payload, aqEls);
            showOpsPlaybooksFeedback(aqEls, "Playbook disparado com sucesso.", "ok");
            await Promise.all([
                refreshActionQueue({ showFeedback: false }),
                fetchAndRenderObservability(),
            ]);
        } catch (error) {
            console.error("Ops playbook trigger error", error);
            showOpsPlaybooksFeedback(
                aqEls,
                `Erro: ${getErrorMessage(error, "Falha ao disparar playbook.")}`,
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
        if (aqEls.opsRefreshBtn) {
            aqEls.opsRefreshBtn.addEventListener("click", () => {
                refreshActionQueue({ showFeedback: true });
            });
        }
        if (aqEls.opsTriggerBtn) {
            aqEls.opsTriggerBtn.addEventListener("click", () => {
                triggerSelectedPlaybook();
            });
        }
    }

    return {
        bindActionQueueEvents,
        refreshActionQueue,
        scheduleActionQueuePolling,
        setSelectedChannel(channelId) {
            selectedChannel =
                String(channelId || "")
                    .trim()
                    .toLowerCase() || "default";
        },
    };
}
