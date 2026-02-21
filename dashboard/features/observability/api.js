// dashboard/features/observability/api.js
import { fetchWithTimeout } from "../shared/api.js";

const OBSERVABILITY_ENDPOINT = "/api/observability";

/**
 * Coleta os dados em /api/observability disparando o erro para a view em caso de falha.
 */
export async function getObservabilitySnapshot(timeoutMs = 10000) {
    return await fetchWithTimeout(OBSERVABILITY_ENDPOINT, { method: "GET" }, timeoutMs);
}
