import { getObservabilitySnapshot } from "./api.js";
import {
    renderObservabilitySnapshot,
    setConnectionState,
} from "./view.js";
import { applyChannelControlCapability } from "../channel-control/view.js";
import { renderControlPlaneCapabilities } from "../control-plane/view.js";
import { renderAutonomyRuntime } from "../autonomy/view.js";

const OBSERVABILITY_INTERVAL_MS = 10000;
const OBSERVABILITY_TIMEOUT_MS = 8000;

export function createObservabilityController({
    obsEls,
    ctrlEls,
    cpEls,
    autEls,
}) {
    let isPolling = false;
    let timerId = 0;

    function applyRuntimeCapabilities(capabilities = {}, mode = "") {
        if (ctrlEls) {
            applyChannelControlCapability(ctrlEls, capabilities?.channel_control || {});
        }
        if (cpEls) {
            renderControlPlaneCapabilities(cpEls, capabilities || {}, mode || "");
        }
    }

    async function fetchAndRenderObservability() {
        if (!obsEls || isPolling) return;
        isPolling = true;
        setConnectionState("pending", obsEls);
        try {
            const data = await getObservabilitySnapshot(OBSERVABILITY_TIMEOUT_MS);
            renderObservabilitySnapshot(data, obsEls);
            setConnectionState("ok", obsEls);
            applyRuntimeCapabilities(data?.capabilities || {}, data?.bot?.mode || "");
            renderAutonomyRuntime(data?.autonomy || {}, autEls);
        } catch (error) {
            console.error("Dashboard observability refresh error", error);
            setConnectionState("error", obsEls);
        } finally {
            isPolling = false;
        }
    }

    function scheduleObservabilityPolling() {
        if (timerId) {
            window.clearTimeout(timerId);
        }
        timerId = window.setTimeout(async () => {
            await fetchAndRenderObservability();
            scheduleObservabilityPolling();
        }, OBSERVABILITY_INTERVAL_MS);
    }

    return {
        applyRuntimeCapabilities,
        fetchAndRenderObservability,
        scheduleObservabilityPolling,
    };
}
