import {
  getAgentNotes,
  getChannelConfig,
  getControlPlaneState,
  resumeAgent,
  suspendAgent,
  updateAgentNotes,
  updateChannelConfig,
  updateControlPlaneConfig,
  getWebhooks,
  updateWebhook,
  testWebhook,
} from "./api.js";
import {
  appendGoalCard,
  collectAgentNotesPayload,
  collectChannelConfigPayload,
  collectControlPlanePayload,
  renderAgentNotes,
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
      showControlPlaneFeedback(cpEls, "Loading control plane...", "warn");
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
        showControlPlaneFeedback(cpEls, "Control plane synced.", "ok");
      }
    } catch (error) {
      console.error("Control plane load error", error);
      showControlPlaneFeedback(
        cpEls,
        `Error: ${getErrorMessage(error, "Failed to load control plane.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function loadChannelConfig(showFeedback = false) {
    if (!cpEls) return;
    const rawChannelId = String(cpEls?.channelIdInput?.value || "")
      .trim()
      .toLowerCase();
    if (!rawChannelId) {
      showControlPlaneFeedback(
        cpEls,
        "Provide a channel to load directives.",
        "warn",
      );
      return;
    }
    const payload = collectChannelConfigPayload(cpEls);
    setControlPlaneBusy(cpEls, true);
    if (showFeedback) {
      showControlPlaneFeedback(
        cpEls,
        "Loading channel operational directives...",
        "warn",
      );
    }
    try {
      const [response, notesResponse, webhooksResponse] = await Promise.all([
        getChannelConfig(payload.channel_id),
        getAgentNotes(payload.channel_id),
        getWebhooks(payload.channel_id).catch(() => null),
      ]);
      renderChannelConfig(response?.channel || {}, cpEls);
      renderAgentNotes(notesResponse?.note || {}, cpEls);

      const whList = webhooksResponse?.webhooks || [];
      if (whList.length > 0) {
        const wh = whList[0];
        if (cpEls.cpWebhookUrl) cpEls.cpWebhookUrl.value = wh.url || "";
        if (cpEls.cpWebhookSecret)
          cpEls.cpWebhookSecret.value = wh.secret || "";
        if (cpEls.cpWebhookActive)
          cpEls.cpWebhookActive.checked = Boolean(wh.is_active);
      } else {
        if (cpEls.cpWebhookUrl) cpEls.cpWebhookUrl.value = "";
        if (cpEls.cpWebhookSecret) cpEls.cpWebhookSecret.value = "";
        if (cpEls.cpWebhookActive) cpEls.cpWebhookActive.checked = true;
      }

      if (showFeedback) {
        showControlPlaneFeedback(cpEls, "Operational directives synced.", "ok");
      }
    } catch (error) {
      console.error("Channel config load error", error);
      showControlPlaneFeedback(
        cpEls,
        `Error: ${getErrorMessage(error, "Failed to load channel directives.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function saveControlPlaneState() {
    if (!cpEls) return;
    setControlPlaneBusy(cpEls, true);
    showControlPlaneFeedback(cpEls, "Saving configuration...", "warn");
    try {
      const payload = collectControlPlanePayload(cpEls);
      const updated = await updateControlPlaneConfig(payload);
      renderControlPlaneState(updated, cpEls);
      renderAutonomyRuntime(updated?.autonomy || {}, autEls);
      applyRuntimeCapabilities(
        updated?.capabilities || {},
        updated?.mode || "",
      );
      showControlPlaneFeedback(
        cpEls,
        "Configuration saved successfully.",
        "ok",
      );
    } catch (error) {
      console.error("Control plane save error", error);
      showControlPlaneFeedback(
        cpEls,
        `Error: ${getErrorMessage(error, "Failed to save configuration.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function saveChannelConfigState() {
    if (!cpEls) return;
    setControlPlaneBusy(cpEls, true);
    showControlPlaneFeedback(
      cpEls,
      "Applying operational directives...",
      "warn",
    );
    try {
      const payload = collectChannelConfigPayload(cpEls);
      const notesPayload = collectAgentNotesPayload(cpEls);

      const promises = [
        updateChannelConfig(payload),
        updateAgentNotes(notesPayload),
      ];

      const url = String(cpEls.cpWebhookUrl?.value || "").trim();
      if (url) {
        promises.push(
          updateWebhook({
            channel_id: payload.channel_id,
            url: url,
            secret: String(cpEls.cpWebhookSecret?.value || "").trim(),
            event_types: [], // empty list means all events
            is_active: Boolean(cpEls.cpWebhookActive?.checked),
          }),
        );
      }

      const [updated, updatedNotes] = await Promise.all(promises);
      renderChannelConfig(updated?.channel || {}, cpEls);
      renderAgentNotes(updatedNotes?.note || {}, cpEls);
      showControlPlaneFeedback(
        cpEls,
        "Operational directives saved successfully.",
        "ok",
      );
    } catch (error) {
      console.error("Channel config save error", error);
      showControlPlaneFeedback(
        cpEls,
        `Error: ${getErrorMessage(error, "Failed to save channel directives.")}`,
        "error",
      );
    } finally {
      setControlPlaneBusy(cpEls, false);
    }
  }

  async function triggerTestWebhook() {
    if (!cpEls) return;
    const payload = collectChannelConfigPayload(cpEls);
    setControlPlaneBusy(cpEls, true);
    showControlPlaneFeedback(cpEls, "Triggering test webhook...", "warn");
    try {
      await testWebhook({ channel_id: payload.channel_id });
      showControlPlaneFeedback(
        cpEls,
        "Test webhook queued successfully.",
        "ok",
      );
    } catch (error) {
      console.error("Webhook test error", error);
      showControlPlaneFeedback(
        cpEls,
        `Error: ${getErrorMessage(error, "Failed to trigger webhook.")}`,
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
        nextSuspended ? "Agent suspended." : "Agent resumed.",
        "ok",
      );
    } catch (error) {
      console.error("Control plane suspend/resume error", error);
      showControlPlaneFeedback(
        cpEls,
        `Error: ${getErrorMessage(error, "Failed to update agent state.")}`,
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
        showControlPlaneFeedback(cpEls, "Goal added. Adjust and save.", "info");
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
    if (cpEls.cpWebhookTestBtn) {
      cpEls.cpWebhookTestBtn.addEventListener("click", () => {
        triggerTestWebhook();
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
