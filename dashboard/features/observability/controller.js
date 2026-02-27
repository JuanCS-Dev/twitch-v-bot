import {
  getChannelContextSnapshot,
  getObservabilityHistorySnapshot,
  getPostStreamReportSnapshot,
  getObservabilitySnapshot,
  getSentimentScoresSnapshot,
} from "./api.js";
import {
  renderChannelContextSnapshot,
  renderObservabilityHistorySnapshot,
  renderPostStreamReportSnapshot,
  renderObservabilitySnapshot,
  setConnectionState,
} from "./view.js";
import { applyChannelControlCapability } from "../channel-control/view.js";
import { renderControlPlaneCapabilities } from "../control-plane/view.js";
import { renderAutonomyRuntime } from "../autonomy/view.js";

const OBSERVABILITY_INTERVAL_MS = 10000;
const OBSERVABILITY_TIMEOUT_MS = 8000;
const OBSERVABILITY_HISTORY_LIMIT = 24;
const OBSERVABILITY_COMPARE_LIMIT = 6;

export function createObservabilityController({
  obsEls,
  ctrlEls,
  cpEls,
  autEls,
}) {
  let isPolling = false;
  let timerId = 0;
  let selectedChannel = "default";

  function applyRuntimeCapabilities(capabilities = {}, mode = "") {
    if (ctrlEls) {
      applyChannelControlCapability(
        ctrlEls,
        capabilities?.channel_control || {},
      );
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
      const sentimentPromise = getSentimentScoresSnapshot(
        selectedChannel,
        OBSERVABILITY_TIMEOUT_MS,
      ).catch((_error) => null);

      const [data, channelData, historyData, sentimentData, postStreamData] =
        await Promise.all([
          getObservabilitySnapshot(selectedChannel, OBSERVABILITY_TIMEOUT_MS),
          getChannelContextSnapshot(selectedChannel, OBSERVABILITY_TIMEOUT_MS),
          getObservabilityHistorySnapshot(
            selectedChannel,
            OBSERVABILITY_TIMEOUT_MS,
            OBSERVABILITY_HISTORY_LIMIT,
            OBSERVABILITY_COMPARE_LIMIT,
          ),
          sentimentPromise,
          getPostStreamReportSnapshot(
            selectedChannel,
            OBSERVABILITY_TIMEOUT_MS,
          ).catch((_error) => null),
        ]);
      renderObservabilitySnapshot(data, obsEls, sentimentData);
      renderChannelContextSnapshot(channelData, obsEls);
      renderObservabilityHistorySnapshot(historyData, obsEls);
      renderPostStreamReportSnapshot(postStreamData, obsEls);
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

  async function generatePostStreamReport() {
    if (!obsEls) return null;
    if (obsEls.intPostStreamGenerateBtn) {
      obsEls.intPostStreamGenerateBtn.disabled = true;
    }
    try {
      const payload = await getPostStreamReportSnapshot(
        selectedChannel,
        OBSERVABILITY_TIMEOUT_MS,
        true,
      );
      renderPostStreamReportSnapshot(payload, obsEls);
      return payload;
    } catch (error) {
      console.error("Dashboard post-stream report generation error", error);
      return null;
    } finally {
      if (obsEls.intPostStreamGenerateBtn) {
        obsEls.intPostStreamGenerateBtn.disabled = false;
      }
    }
  }

  function bindObservabilityEvents() {
    if (!obsEls?.intPostStreamGenerateBtn) return;
    obsEls.intPostStreamGenerateBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await generatePostStreamReport();
    });
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
    generatePostStreamReport,
    bindObservabilityEvents,
    setSelectedChannel(channelId) {
      selectedChannel =
        String(channelId || "")
          .trim()
          .toLowerCase() || "default";
    },
    scheduleObservabilityPolling,
  };
}
