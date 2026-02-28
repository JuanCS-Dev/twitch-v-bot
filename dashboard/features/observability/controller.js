import {
  getChannelContextSnapshot,
  getObservabilityHistorySnapshot,
  getPostStreamReportSnapshot,
  getSemanticMemorySnapshot,
  getObservabilitySnapshot,
  getSentimentScoresSnapshot,
  upsertSemanticMemoryEntry,
  getRevenueConversionsSnapshot,
  postRevenueConversion,
} from "./api.js";
import {
  renderChannelContextSnapshot,
  renderObservabilityHistorySnapshot,
  renderPostStreamReportSnapshot,
  renderSemanticMemorySnapshot,
  renderObservabilitySnapshot,
  setConnectionState,
  renderRevenueConversionsSnapshot,
} from "./view.js";
import { applyChannelControlCapability } from "../channel-control/view.js";
import { renderControlPlaneCapabilities } from "../control-plane/view.js";
import { renderAutonomyRuntime } from "../autonomy/view.js";

const OBSERVABILITY_INTERVAL_MS = 10000;
const OBSERVABILITY_TIMEOUT_MS = 8000;
const OBSERVABILITY_HISTORY_LIMIT = 24;
const OBSERVABILITY_COMPARE_LIMIT = 6;
const SEMANTIC_MEMORY_LIMIT = 8;
const SEMANTIC_MEMORY_SEARCH_LIMIT = 60;

function normalizeSemanticMinSimilarity(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return "";
  const clamped = Math.max(-1, Math.min(1, parsed));
  return String(Number(clamped.toFixed(3)));
}

export function createObservabilityController({
  obsEls,
  ctrlEls,
  cpEls,
  autEls,
}) {
  let isPolling = false;
  let timerId = 0;
  let selectedChannel = "default";
  let semanticMemoryQuery = "";
  let semanticMemoryMinSimilarity = "";
  let semanticMemoryForceFallback = false;

  function syncSemanticMemorySearchTuning() {
    if (!obsEls) return;
    semanticMemoryMinSimilarity = normalizeSemanticMinSimilarity(
      obsEls.intSemanticMemoryMinSimilarityInput?.value,
    );
    semanticMemoryForceFallback = Boolean(
      obsEls.intSemanticMemoryForceFallbackToggle?.checked,
    );
  }

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
    syncSemanticMemorySearchTuning();
    isPolling = true;
    setConnectionState("pending", obsEls);
    try {
      const sentimentPromise = getSentimentScoresSnapshot(
        selectedChannel,
        OBSERVABILITY_TIMEOUT_MS,
      ).catch((_error) => null);

      const [
        data,
        channelData,
        historyData,
        sentimentData,
        postStreamData,
        semanticMemoryData,
        revenueData,
      ] = await Promise.all([
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
        getSemanticMemorySnapshot(
          selectedChannel,
          OBSERVABILITY_TIMEOUT_MS,
          semanticMemoryQuery,
          SEMANTIC_MEMORY_LIMIT,
          SEMANTIC_MEMORY_SEARCH_LIMIT,
          semanticMemoryMinSimilarity,
          semanticMemoryForceFallback,
        ).catch((_error) => null),
        getRevenueConversionsSnapshot(
          selectedChannel,
          OBSERVABILITY_TIMEOUT_MS,
        ).catch((_error) => null),
      ]);
      renderObservabilitySnapshot(data, obsEls, sentimentData);
      renderChannelContextSnapshot(channelData, obsEls);
      renderObservabilityHistorySnapshot(historyData, obsEls);
      renderPostStreamReportSnapshot(postStreamData, obsEls);
      renderSemanticMemorySnapshot(semanticMemoryData, obsEls);
      renderRevenueConversionsSnapshot(revenueData, obsEls);
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

  async function refreshSemanticMemory(query = "") {
    if (!obsEls) return null;
    syncSemanticMemorySearchTuning();
    semanticMemoryQuery = String(query || "").trim();
    try {
      const payload = await getSemanticMemorySnapshot(
        selectedChannel,
        OBSERVABILITY_TIMEOUT_MS,
        semanticMemoryQuery,
        SEMANTIC_MEMORY_LIMIT,
        SEMANTIC_MEMORY_SEARCH_LIMIT,
        semanticMemoryMinSimilarity,
        semanticMemoryForceFallback,
      );
      renderSemanticMemorySnapshot(payload, obsEls);
      return payload;
    } catch (error) {
      console.error("Dashboard semantic memory refresh error", error);
      return null;
    }
  }

  async function saveSemanticMemoryEntry() {
    if (!obsEls) return null;
    const content = String(
      obsEls.intSemanticMemoryContentInput?.value || "",
    ).trim();
    if (!content) return null;
    if (obsEls.intSemanticMemorySaveBtn) {
      obsEls.intSemanticMemorySaveBtn.disabled = true;
    }
    try {
      await upsertSemanticMemoryEntry(
        {
          channel_id: selectedChannel,
          content,
          memory_type: String(
            obsEls.intSemanticMemoryTypeInput?.value || "fact",
          )
            .trim()
            .toLowerCase(),
          tags: String(obsEls.intSemanticMemoryTagsInput?.value || ""),
        },
        OBSERVABILITY_TIMEOUT_MS,
      );
      if (obsEls.intSemanticMemoryContentInput) {
        obsEls.intSemanticMemoryContentInput.value = "";
      }
      syncSemanticMemorySearchTuning();
      const queryFromInput = String(
        obsEls.intSemanticMemoryQueryInput?.value || "",
      ).trim();
      await refreshSemanticMemory(queryFromInput);
      return true;
    } catch (error) {
      console.error("Dashboard semantic memory save error", error);
      return null;
    } finally {
      if (obsEls.intSemanticMemorySaveBtn) {
        obsEls.intSemanticMemorySaveBtn.disabled = false;
      }
    }
  }

  async function simulateRevenueConversion() {
    if (!obsEls || !obsEls.intRevenueSimulateBtn) return null;
    const btn = obsEls.intRevenueSimulateBtn;
    const eventType = obsEls.intRevenueEventType?.value || "sub";
    const viewerLogin = String(
      obsEls.intRevenueViewerLogin?.value || "simulated_viewer",
    ).trim();
    const rawValue = obsEls.intRevenueValue?.value || "0";
    const revenueValue = Number(rawValue) || 0.0;

    btn.disabled = true;
    try {
      await postRevenueConversion(
        {
          channel_id: selectedChannel,
          event_type: eventType,
          viewer_login: viewerLogin,
          revenue_value: revenueValue,
        },
        OBSERVABILITY_TIMEOUT_MS,
      );

      if (obsEls.intRevenueViewerLogin) obsEls.intRevenueViewerLogin.value = "";
      if (obsEls.intRevenueValue) obsEls.intRevenueValue.value = "";

      const payload = await getRevenueConversionsSnapshot(
        selectedChannel,
        OBSERVABILITY_TIMEOUT_MS,
      );
      renderRevenueConversionsSnapshot(payload, obsEls);
      return true;
    } catch (error) {
      console.error("Dashboard revenue simulation error", error);
      return null;
    } finally {
      btn.disabled = false;
    }
  }

  function bindObservabilityEvents() {
    if (!obsEls) return;
    if (obsEls.intPostStreamGenerateBtn) {
      obsEls.intPostStreamGenerateBtn.addEventListener(
        "click",
        async (event) => {
          event.preventDefault();
          await generatePostStreamReport();
        },
      );
    }
    if (obsEls.intSemanticMemorySearchBtn) {
      obsEls.intSemanticMemorySearchBtn.addEventListener(
        "click",
        async (event) => {
          event.preventDefault();
          syncSemanticMemorySearchTuning();
          const query = String(
            obsEls.intSemanticMemoryQueryInput?.value || "",
          ).trim();
          await refreshSemanticMemory(query);
        },
      );
    }
    if (obsEls.intSemanticMemorySaveBtn) {
      obsEls.intSemanticMemorySaveBtn.addEventListener(
        "click",
        async (event) => {
          event.preventDefault();
          await saveSemanticMemoryEntry();
        },
      );
    }
    if (obsEls.intSemanticMemoryMinSimilarityInput) {
      obsEls.intSemanticMemoryMinSimilarityInput.addEventListener(
        "change",
        async () => {
          syncSemanticMemorySearchTuning();
          const query = String(
            obsEls.intSemanticMemoryQueryInput?.value || "",
          ).trim();
          await refreshSemanticMemory(query);
        },
      );
    }
    if (obsEls.intSemanticMemoryForceFallbackToggle) {
      obsEls.intSemanticMemoryForceFallbackToggle.addEventListener(
        "change",
        async () => {
          syncSemanticMemorySearchTuning();
          const query = String(
            obsEls.intSemanticMemoryQueryInput?.value || "",
          ).trim();
          await refreshSemanticMemory(query);
        },
      );
    }
    if (obsEls.intRevenueSimulateBtn) {
      obsEls.intRevenueSimulateBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        await simulateRevenueConversion();
      });
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
    generatePostStreamReport,
    refreshSemanticMemory,
    saveSemanticMemoryEntry,
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
