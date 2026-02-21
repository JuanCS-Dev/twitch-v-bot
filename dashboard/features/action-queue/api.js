import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";
const ACTION_QUEUE_ENDPOINT = "/api/action-queue";
const REQUEST_TIMEOUT_MS = 12000;

function authHeaders() {
    const headers = {};
    const token = getStorageItem(TOKEN_KEY);
    if (token) {
        headers["X-Byte-Admin-Token"] = token;
    }
    return headers;
}

export async function getActionQueue({ status = "", limit = 80 } = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    const params = new URLSearchParams();
    if (String(status || "").trim()) {
        params.set("status", String(status).trim());
    }
    params.set("limit", String(limit || 80));

    const endpoint = `${ACTION_QUEUE_ENDPOINT}?${params.toString()}`;
    return await fetchWithTimeout(endpoint, { method: "GET", headers: authHeaders() }, timeoutMs);
}

export async function decideActionQueueItem(actionId, decision, note = "", timeoutMs = REQUEST_TIMEOUT_MS) {
    const safeActionId = encodeURIComponent(String(actionId || "").trim());
    return await fetchWithTimeout(
        `${ACTION_QUEUE_ENDPOINT}/${safeActionId}/decision`,
        {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                decision: String(decision || "").trim().toLowerCase(),
                note: String(note || "").trim(),
            }),
        },
        timeoutMs
    );
}
