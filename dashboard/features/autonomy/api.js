import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";
const AUTONOMY_TICK_ENDPOINT = "./api/autonomy/tick";
const REQUEST_TIMEOUT_MS = 15000;

function authHeaders() {
    const headers = {};
    const token = getStorageItem(TOKEN_KEY);
    if (token) {
        headers["X-Byte-Admin-Token"] = token;
    }
    return headers;
}

export async function triggerAutonomyTick({ force = true, reason = "manual_dashboard" } = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    return await fetchWithTimeout(
        AUTONOMY_TICK_ENDPOINT,
        {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ force: Boolean(force), reason: String(reason || "manual_dashboard") }),
        },
        timeoutMs
    );
}
