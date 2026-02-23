// dashboard/features/channel-control/api.js
import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const CHANNEL_CONTROL_ENDPOINT = "./api/channel-control";
const ACTION_TIMEOUT_MS = 12000;
const TOKEN_KEY = "byte_dashboard_admin_token";

/**
 * Dispara uma ação (join, part, list) para a bot bridge em conformidade com AS-IS.
 */
export async function sendChannelAction(action, channelLogin = "") {
    const token = getStorageItem(TOKEN_KEY);
    const headers = {};
    if (token) {
        headers["X-Byte-Admin-Token"] = token;
    }

    const payload = {
        action,
        channel: channelLogin
    };

    return await fetchWithTimeout(
        CHANNEL_CONTROL_ENDPOINT,
        { method: "POST", headers, body: JSON.stringify(payload) },
        ACTION_TIMEOUT_MS
    );
}
