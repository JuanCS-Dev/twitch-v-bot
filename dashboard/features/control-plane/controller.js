import {
    getControlPlaneState,
    updateControlPlaneConfig,
} from "./api.js";
import {
    appendGoalCard,
    collectControlPlanePayload,
    renderControlPlaneState,
    setControlPlaneBusy,
    showControlPlaneFeedback,
} from "./view.js";
import { renderAutonomyRuntime } from "../autonomy/view.js";

export function createControlPlaneController({
    cpEls,
    autEls,
    applyRuntimeCapabilities,
    getErrorMessage,
}) {
    async function loadControlPlaneState(showFeedback = true) {
        if (!cpEls) return;
        setControlPlaneBusy(cpEls, true);
        if (showFeedback) {
            showControlPlaneFeedback(cpEls, "Carregando control plane...", "warn");
        }
        try {
            const payload = await getControlPlaneState();
            renderControlPlaneState(payload, cpEls);
            renderAutonomyRuntime(payload?.autonomy || {}, autEls);
            applyRuntimeCapabilities(payload?.capabilities || {}, payload?.mode || "");
            if (showFeedback) {
                showControlPlaneFeedback(cpEls, "Control plane sincronizado.", "ok");
            }
        } catch (error) {
            console.error("Control plane load error", error);
            showControlPlaneFeedback(
                cpEls,
                `Erro: ${getErrorMessage(error, "Falha ao carregar control plane.")}`,
                "error"
            );
        } finally {
            setControlPlaneBusy(cpEls, false);
        }
    }

    async function saveControlPlaneState() {
        if (!cpEls) return;
        setControlPlaneBusy(cpEls, true);
        showControlPlaneFeedback(cpEls, "Salvando configuracao...", "warn");
        try {
            const payload = collectControlPlanePayload(cpEls);
            const updated = await updateControlPlaneConfig(payload);
            renderControlPlaneState(updated, cpEls);
            renderAutonomyRuntime(updated?.autonomy || {}, autEls);
            applyRuntimeCapabilities(updated?.capabilities || {}, updated?.mode || "");
            showControlPlaneFeedback(cpEls, "Configuracao salva com sucesso.", "ok");
        } catch (error) {
            console.error("Control plane save error", error);
            showControlPlaneFeedback(
                cpEls,
                `Erro: ${getErrorMessage(error, "Falha ao salvar configuracao.")}`,
                "error"
            );
        } finally {
            setControlPlaneBusy(cpEls, false);
        }
    }

    function bindControlPlaneEvents() {
        if (!cpEls) return;
        if (cpEls.addGoalBtn) {
            cpEls.addGoalBtn.addEventListener("click", () => {
                const currentGoalCount = cpEls.goalsList
                    ? cpEls.goalsList.querySelectorAll("[data-goal-item='1']").length
                    : 0;
                appendGoalCard(cpEls, {}, currentGoalCount);
                showControlPlaneFeedback(cpEls, "Goal adicionada. Ajuste e salve.", "info");
            });
        }
        if (cpEls.saveBtn) {
            cpEls.saveBtn.addEventListener("click", () => {
                saveControlPlaneState();
            });
        }
        if (cpEls.reloadBtn) {
            cpEls.reloadBtn.addEventListener("click", () => {
                loadControlPlaneState(true);
            });
        }
    }

    return {
        bindControlPlaneEvents,
        loadControlPlaneState,
    };
}

