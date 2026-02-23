import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";
const CONTROL_PLANE_ENDPOINT = "./api/control-plane";
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
