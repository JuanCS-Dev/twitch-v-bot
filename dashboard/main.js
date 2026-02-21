import { getObservabilityElements } from "./features/observability/view.js";
import { getChannelControlElements } from "./features/channel-control/view.js";
import { getControlPlaneElements } from "./features/control-plane/view.js";
import { getAutonomyElements } from "./features/autonomy/view.js";
import { getActionQueueElements } from "./features/action-queue/view.js";
import { getErrorMessage } from "./features/shared/errors.js";
import { createObservabilityController } from "./features/observability/controller.js";
import { createChannelControlController } from "./features/channel-control/controller.js";
import { createControlPlaneController } from "./features/control-plane/controller.js";
import { createAutonomyController } from "./features/autonomy/controller.js";
import { createActionQueueController } from "./features/action-queue/controller.js";

document.addEventListener("DOMContentLoaded", async () => {
    const obsEls = getObservabilityElements();
    const ctrlEls = getChannelControlElements();
    const cpEls = getControlPlaneElements();
    const autEls = getAutonomyElements();
    const aqEls = getActionQueueElements();

    const observabilityController = createObservabilityController({
        obsEls,
        ctrlEls,
        cpEls,
        autEls,
    });
    const actionQueueController = createActionQueueController({
        aqEls,
        fetchAndRenderObservability: observabilityController.fetchAndRenderObservability,
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
    });
    const controlPlaneController = createControlPlaneController({
        cpEls,
        autEls,
        applyRuntimeCapabilities: observabilityController.applyRuntimeCapabilities,
        getErrorMessage,
    });

    channelControlController.bindChannelControlEvents();
    controlPlaneController.bindControlPlaneEvents();
    autonomyController.bindAutonomyEvents();
    actionQueueController.bindActionQueueEvents();

    await controlPlaneController.loadControlPlaneState(false);
    await channelControlController.handleChannelAction("list");
    await Promise.all([
        observabilityController.fetchAndRenderObservability(),
        actionQueueController.refreshActionQueue({ showFeedback: false }),
    ]);

    observabilityController.scheduleObservabilityPolling();
    actionQueueController.scheduleActionQueuePolling();
});

