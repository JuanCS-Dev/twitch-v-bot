import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";
const ACTION_QUEUE_ENDPOINT = "./api/action-queue";
const OPS_PLAYBOOKS_ENDPOINT = "./api/ops-playbooks";
const OPS_PLAYBOOKS_TRIGGER_ENDPOINT = "./api/ops-playbooks/trigger";
const REQUEST_TIMEOUT_MS = 12000;

function authHeaders() {
    const headers = {};
    const token = getStorageItem(TOKEN_KEY);
    if (token) {
        headers["X-Byte-Admin-Token"] = token;
    }
    return headers;
}

function normalizeChannelId(channelId) {
    return (
        String(channelId || "")
            .trim()
            .toLowerCase() || "default"
    );
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

export async function getOpsPlaybooks(channelId = "default", timeoutMs = REQUEST_TIMEOUT_MS) {
    const params = new URLSearchParams({
        channel: normalizeChannelId(channelId),
    });
    return await fetchWithTimeout(
        `${OPS_PLAYBOOKS_ENDPOINT}?${params.toString()}`,
        { method: "GET", headers: authHeaders() },
        timeoutMs
    );
}

export async function triggerOpsPlaybook(
    { playbookId = "", channelId = "default", reason = "manual_dashboard", force = false } = {},
    timeoutMs = REQUEST_TIMEOUT_MS
) {
    return await fetchWithTimeout(
        OPS_PLAYBOOKS_TRIGGER_ENDPOINT,
        {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                playbook_id: String(playbookId || "").trim().toLowerCase(),
                channel_id: normalizeChannelId(channelId),
                reason: String(reason || "manual_dashboard").trim(),
                force: Boolean(force),
            }),
        },
        timeoutMs
    );
}
