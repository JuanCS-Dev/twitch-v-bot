// dashboard/features/observability/api.js
import { fetchWithTimeout } from "../shared/api.js";

const OBSERVABILITY_ENDPOINT = "./api/observability";
const CHANNEL_CONTEXT_ENDPOINT = "./api/channel-context";
const OBSERVABILITY_HISTORY_ENDPOINT = "./api/observability/history";

function normalizeChannelId(channelId) {
  return (
    String(channelId || "")
      .trim()
      .toLowerCase() || "default"
  );
}

function buildChannelQuery(channelId, extraParams = {}) {
  const params = new URLSearchParams({
    channel: normalizeChannelId(channelId),
  });
  Object.entries(extraParams || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(String(key), String(value));
  });
  return `?${params.toString()}`;
}

/**
 * Coleta os dados em /api/observability disparando o erro para a view em caso de falha.
 */
export async function getObservabilitySnapshot(channelId, timeoutMs = 10000) {
  return await fetchWithTimeout(
    `${OBSERVABILITY_ENDPOINT}${buildChannelQuery(channelId)}`,
    { method: "GET" },
    timeoutMs,
  );
}

export async function getChannelContextSnapshot(channelId, timeoutMs = 10000) {
  return await fetchWithTimeout(
    `${CHANNEL_CONTEXT_ENDPOINT}${buildChannelQuery(channelId)}`,
    { method: "GET" },
    timeoutMs,
  );
}

export async function getObservabilityHistorySnapshot(
  channelId,
  timeoutMs = 10000,
  limit = 24,
  compareLimit = 6,
) {
  return await fetchWithTimeout(
    `${OBSERVABILITY_HISTORY_ENDPOINT}${buildChannelQuery(channelId, {
      limit,
      compare_limit: compareLimit,
    })}`,
    { method: "GET" },
    timeoutMs,
  );
}
