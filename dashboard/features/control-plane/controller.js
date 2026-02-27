import {
  getChannelConfig,
  getControlPlaneState,
  resumeAgent,
  suspendAgent,
  updateChannelConfig,
  updateControlPlaneConfig,
} from "./api.js";
import {
  appendGoalCard,
  collectChannelConfigPayload,
  collectControlPlanePayload,
  renderChannelConfig,
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
      applyRuntimeCapabilities(
        payload?.capabilities || {},
        payload?.mode || "",
      );
      if (showFeedback) {
        showControlPlaneFeedback(cpEls, "Control plane sincronizado.", "ok");
      }
    } catch (error) {
      console.error("Control plane load error", error);
      showControlPlaneFeedback(
        cpEls,
        `Erro: ${getErrorMessage(error, "Falha ao carregar control plane.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function loadChannelConfig(showFeedback = false) {
    if (!cpEls) return;
    const payload = collectChannelConfigPayload(cpEls);
    if (!payload.channel_id) {
      showControlPlaneFeedback(
        cpEls,
        "Informe um canal para carregar tuning.",
        "warn",
      );
      return;
    }
    setControlPlaneBusy(cpEls, true);
    if (showFeedback) {
      showControlPlaneFeedback(cpEls, "Carregando channel tuning...", "warn");
    }
    try {
      const response = await getChannelConfig(payload.channel_id);
      renderChannelConfig(response?.channel || {}, cpEls);
      if (showFeedback) {
        showControlPlaneFeedback(cpEls, "Channel tuning sincronizado.", "ok");
      }
    } catch (error) {
      console.error("Channel config load error", error);
      showControlPlaneFeedback(
        cpEls,
        `Erro: ${getErrorMessage(error, "Falha ao carregar channel tuning.")}`,
        "error",
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
      applyRuntimeCapabilities(
        updated?.capabilities || {},
        updated?.mode || "",
      );
      showControlPlaneFeedback(cpEls, "Configuracao salva com sucesso.", "ok");
    } catch (error) {
      console.error("Control plane save error", error);
      showControlPlaneFeedback(
        cpEls,
        `Erro: ${getErrorMessage(error, "Falha ao salvar configuracao.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function saveChannelConfigState() {
    if (!cpEls) return;
    setControlPlaneBusy(cpEls, true);
    showControlPlaneFeedback(cpEls, "Aplicando channel tuning...", "warn");
    try {
      const payload = collectChannelConfigPayload(cpEls);
      const updated = await updateChannelConfig(payload);
      renderChannelConfig(updated?.channel || {}, cpEls);
      showControlPlaneFeedback(
        cpEls,
        "Channel tuning salvo com sucesso.",
        "ok",
      );
    } catch (error) {
      console.error("Channel config save error", error);
      showControlPlaneFeedback(
        cpEls,
        `Erro: ${getErrorMessage(error, "Falha ao salvar channel tuning.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function updateAgentSuspension(nextSuspended) {
    if (!cpEls) return;
    const actionLabel = nextSuspended ? "Suspending" : "Resuming";
    setControlPlaneBusy(cpEls, true);
    showControlPlaneFeedback(cpEls, `${actionLabel} agent...`, "warn");
    try {
      const payload = nextSuspended
        ? await suspendAgent({ reason: "manual_dashboard_suspend" })
        : await resumeAgent({ reason: "manual_dashboard_resume" });
      renderControlPlaneState(payload, cpEls);
      renderAutonomyRuntime(payload?.autonomy || {}, autEls);
      applyRuntimeCapabilities(
        payload?.capabilities || {},
        payload?.mode || "",
      );
      showControlPlaneFeedback(
        cpEls,
        nextSuspended ? "Agente suspenso." : "Agente retomado.",
        "ok",
      );
    } catch (error) {
      console.error("Control plane suspend/resume error", error);
      showControlPlaneFeedback(
        cpEls,
        `Erro: ${getErrorMessage(error, "Falha ao atualizar estado do agente.")}`,
        "error",
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
        showControlPlaneFeedback(
          cpEls,
          "Goal adicionada. Ajuste e salve.",
          "info",
        );
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
    if (cpEls.loadChannelConfigBtn) {
      cpEls.loadChannelConfigBtn.addEventListener("click", () => {
        loadChannelConfig(true);
      });
    }
    if (cpEls.saveChannelConfigBtn) {
      cpEls.saveChannelConfigBtn.addEventListener("click", () => {
        saveChannelConfigState();
      });
    }
    if (cpEls.suspendBtn) {
      cpEls.suspendBtn.addEventListener("click", () => {
        updateAgentSuspension(true);
      });
    }
    if (cpEls.resumeBtn) {
      cpEls.resumeBtn.addEventListener("click", () => {
        updateAgentSuspension(false);
      });
    }
  }

  return {
    bindControlPlaneEvents,
    loadControlPlaneState,
    loadChannelConfig,
    setSelectedChannel(channelId) {
      if (!cpEls?.channelIdInput) return;
      cpEls.channelIdInput.value =
        String(channelId || "")
          .trim()
          .toLowerCase() || "default";
    },
  };
}
