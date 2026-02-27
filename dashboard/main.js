import { getObservabilityElements } from "./features/observability/view.js";
import { getChannelControlElements } from "./features/channel-control/view.js";
import { getControlPlaneElements } from "./features/control-plane/view.js";
import { getAutonomyElements } from "./features/autonomy/view.js";
import { getActionQueueElements } from "./features/action-queue/view.js";
import { getClipsElements } from "./features/clips/view.js";
import { getHudElements } from "./features/hud/view.js";
import { getErrorMessage } from "./features/shared/errors.js";
import { createObservabilityController } from "./features/observability/controller.js";
import { createChannelControlController } from "./features/channel-control/controller.js";
import { createControlPlaneController } from "./features/control-plane/controller.js";
import { createAutonomyController } from "./features/autonomy/controller.js";
import { createActionQueueController } from "./features/action-queue/controller.js";
import { createClipsController } from "./features/clips/controller.js";
import { createHudController } from "./features/hud/controller.js";

async function bootstrapDashboard() {
  const obsEls = getObservabilityElements();
  const ctrlEls = getChannelControlElements();
  const cpEls = getControlPlaneElements();
  const autEls = getAutonomyElements();
  const aqEls = getActionQueueElements();
  const clipsEls = getClipsElements();
  const hudEls = getHudElements();

  const observabilityController = createObservabilityController({
    obsEls,
    ctrlEls,
    cpEls,
    autEls,
  });
  let controlPlaneController;
  let actionQueueController;
  async function syncDashboardChannel(
    channelId,
    { refreshObservability = true } = {},
  ) {
    observabilityController.setSelectedChannel(channelId);
    if (controlPlaneController) {
      controlPlaneController.setSelectedChannel(channelId);
    }
    if (actionQueueController) {
      actionQueueController.setSelectedChannel(channelId);
    }

    const jobs = [];
    if (refreshObservability) {
      jobs.push(observabilityController.fetchAndRenderObservability());
    }
    if (controlPlaneController) {
      jobs.push(controlPlaneController.loadChannelConfig(false));
    }
    if (actionQueueController) {
      jobs.push(actionQueueController.refreshActionQueue({ showFeedback: false }));
    }
    if (jobs.length) {
      await Promise.all(jobs);
    }
  }
  actionQueueController = createActionQueueController({
    aqEls,
    fetchAndRenderObservability:
      observabilityController.fetchAndRenderObservability,
    getErrorMessage,
  });
  const autonomyController = createAutonomyController({
    autEls,
    refreshActionQueue: actionQueueController.refreshActionQueue,
    getErrorMessage,
  });
  const channelControlController = createChannelControlController({
    ctrlEls,
    applyRuntimeCapabilities: observabilityController.applyRuntimeCapabilities,
    getErrorMessage,
    onDashboardChannelChange: async (channelId) => {
      await syncDashboardChannel(channelId);
    },
  });
  controlPlaneController = createControlPlaneController({
    cpEls,
    autEls,
    applyRuntimeCapabilities: observabilityController.applyRuntimeCapabilities,
    getErrorMessage,
  });
  const clipsController = createClipsController({
    els: clipsEls,
  });
  const hudController = createHudController({
    hudEls,
  });

  channelControlController.bindChannelControlEvents();
  observabilityController.bindObservabilityEvents();
  controlPlaneController.bindControlPlaneEvents();
  autonomyController.bindAutonomyEvents();
  actionQueueController.bindActionQueueEvents();
  hudController.bindEvents();

  try {
    const initialChannel =
      channelControlController.getSelectedDashboardChannel();
    await syncDashboardChannel(initialChannel, { refreshObservability: false });
    await controlPlaneController.loadControlPlaneState(false);
    await channelControlController.handleChannelAction("list");
    await Promise.all([
      observabilityController.fetchAndRenderObservability(),
      actionQueueController.refreshActionQueue({ showFeedback: false }),
    ]);
  } catch (err) {
    if (err.status === 403) {
      console.warn(
        "Bootstrap: Acesso negado. Aguardando input do Admin Token.",
      );
    } else {
      console.error("Erro durante o carregamento inicial:", err);
    }
  }

  observabilityController.scheduleObservabilityPolling();
  actionQueueController.scheduleActionQueuePolling();
  clipsController.startPolling();
  hudController.startPolling();
}

bootstrapDashboard().catch((err) =>
  console.error("Fatal error during bot dashboard bootstrap:", err),
);
