// dashboard/features/observability/api.js
import { fetchWithTimeout } from "../shared/api.js";

const OBSERVABILITY_ENDPOINT = "./api/observability";
const CHANNEL_CONTEXT_ENDPOINT = "./api/channel-context";
const OBSERVABILITY_HISTORY_ENDPOINT = "./api/observability/history";
const SENTIMENT_SCORES_ENDPOINT = "./api/sentiment/scores";
const POST_STREAM_REPORT_ENDPOINT = "./api/observability/post-stream-report";
const SEMANTIC_MEMORY_ENDPOINT = "./api/semantic-memory";

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

export async function getSentimentScoresSnapshot(channelId, timeoutMs = 10000) {
  return await fetchWithTimeout(
    `${SENTIMENT_SCORES_ENDPOINT}${buildChannelQuery(channelId)}`,
    { method: "GET" },
    timeoutMs,
  );
}

export async function getPostStreamReportSnapshot(
  channelId,
  timeoutMs = 10000,
  generate = false,
) {
  return await fetchWithTimeout(
    `${POST_STREAM_REPORT_ENDPOINT}${buildChannelQuery(channelId, {
      generate: generate ? 1 : undefined,
    })}`,
    { method: "GET" },
    timeoutMs,
  );
}

export async function getSemanticMemorySnapshot(
  channelId,
  timeoutMs = 10000,
  query = "",
  limit = 8,
  searchLimit = 60,
) {
  return await fetchWithTimeout(
    `${SEMANTIC_MEMORY_ENDPOINT}${buildChannelQuery(channelId, {
      query: query || undefined,
      limit,
      search_limit: searchLimit,
    })}`,
    { method: "GET" },
    timeoutMs,
  );
}

export async function upsertSemanticMemoryEntry(
  payload,
  timeoutMs = 10000,
) {
  return await fetchWithTimeout(
    SEMANTIC_MEMORY_ENDPOINT,
    {
      method: "PUT",
      body: JSON.stringify(payload || {}),
    },
    timeoutMs,
  );
}
