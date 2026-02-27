import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";
const CONTROL_PLANE_ENDPOINT = "./api/control-plane";
const CHANNEL_CONFIG_ENDPOINT = "./api/channel-config";
const AGENT_SUSPEND_ENDPOINT = "./api/agent/suspend";
const AGENT_RESUME_ENDPOINT = "./api/agent/resume";
const REQUEST_TIMEOUT_MS = 12000;

function authHeaders() {
    const headers = {};
    const token = getStorageItem(TOKEN_KEY);
    if (token) {
        headers["X-Byte-Admin-Token"] = token;
    }
    return headers;
}

export async function getControlPlaneState(timeoutMs = REQUEST_TIMEOUT_MS) {
    return await fetchWithTimeout(
        CONTROL_PLANE_ENDPOINT,
        { method: "GET", headers: authHeaders() },
        timeoutMs
    );
}

export async function updateControlPlaneConfig(payload, timeoutMs = REQUEST_TIMEOUT_MS) {
    return await fetchWithTimeout(
        CONTROL_PLANE_ENDPOINT,
        { method: "PUT", headers: authHeaders(), body: JSON.stringify(payload || {}) },
        timeoutMs
    );
}

export async function getChannelConfig(channelId, timeoutMs = REQUEST_TIMEOUT_MS) {
    const safeChannelId = encodeURIComponent(String(channelId || "").trim().toLowerCase());
    return await fetchWithTimeout(
        `${CHANNEL_CONFIG_ENDPOINT}?channel=${safeChannelId}`,
        { method: "GET", headers: authHeaders() },
        timeoutMs
    );
}

export async function updateChannelConfig(payload, timeoutMs = REQUEST_TIMEOUT_MS) {
    return await fetchWithTimeout(
        CHANNEL_CONFIG_ENDPOINT,
        { method: "PUT", headers: authHeaders(), body: JSON.stringify(payload || {}) },
        timeoutMs
    );
}

export async function suspendAgent(payload = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    return await fetchWithTimeout(
        AGENT_SUSPEND_ENDPOINT,
        { method: "POST", headers: authHeaders(), body: JSON.stringify(payload || {}) },
        timeoutMs
    );
}

export async function resumeAgent(payload = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    return await fetchWithTimeout(
        AGENT_RESUME_ENDPOINT,
        { method: "POST", headers: authHeaders(), body: JSON.stringify(payload || {}) },
        timeoutMs
    );
}
