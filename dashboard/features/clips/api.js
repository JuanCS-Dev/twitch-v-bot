import { fetchWithTimeout } from "../shared/api.js";
import { getStorageItem } from "../shared/dom.js";

const TOKEN_KEY = "byte_dashboard_admin_token";

function authHeaders() {
  const headers = {};
  const token = getStorageItem(TOKEN_KEY);
  if (token) {
    headers["X-Byte-Admin-Token"] = token;
  }
  return headers;
}

export async function fetchClipJobs() {
    const res = await fetchWithTimeout("./api/clip-jobs", { method: "GET" });
    return res;
}

export async function fetchVisionStatus() {
    return await fetchWithTimeout("./api/vision/status", { method: "GET" });
}

export async function postVisionIngest(fileOrBlob) {
    const headers = authHeaders();
    headers["Content-Type"] = fileOrBlob.type || "image/jpeg";

    return await fetchWithTimeout("./api/vision/ingest", {
        method: "POST",
        headers: headers,
        body: fileOrBlob
    });
}
