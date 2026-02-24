import { fetchWithTimeout } from "../shared/api.js";

export async function fetchHudMessages(since = 0) {
    const res = await fetchWithTimeout(`./api/hud/messages?since=${since}`, { method: "GET" });
    return res;
}
