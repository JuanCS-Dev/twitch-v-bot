// dashboard/features/observability/api.js
import { fetchWithTimeout } from "../shared/api.js";

const OBSERVABILITY_ENDPOINT = "./api/observability";
const CHANNEL_CONTEXT_ENDPOINT = "./api/channel-context";

function buildChannelQuery(channelId) {
  const safeChannel = encodeURIComponent(
    String(channelId || "")
      .trim()
      .toLowerCase() || "default",
  );
  return `?channel=${safeChannel}`;
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
