import { fetchWithTimeout } from "../shared/api.js";

export async function fetchClipJobs() {
    const res = await fetchWithTimeout("./api/clip-jobs", { method: "GET" });
    return res;
}
