// dashboard/features/shared/api.js
import { getStorageItem } from "./dom.js";
export const TIMEOUT_DEFAULT_MS = 12000;

/**
 * Standard fetch wrapper that throws HTTP errors
 * and handles abort/timeout.
 */
export async function fetchWithTimeout(url, options = {}, timeoutMs = TIMEOUT_DEFAULT_MS) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    let headers = {
        "Content-Type": "application/json",
        ...options.headers,
    };

    const tokenInput = document.getElementById("adminTokenInput");
    let domToken = tokenInput ? tokenInput.value.trim() : "";
    let localToken = getStorageItem("byte_dashboard_admin_token");
    let serverToken = window.BYTE_CONFIG?.adminToken || "";
    let activeToken = domToken || localToken || serverToken;

    if (activeToken) {
        headers["X-Byte-Admin-Token"] = activeToken;
    }

    const fetchOptions = {
        ...options,
        signal: controller.signal,
        cache: "no-store",
        headers,
    };

    // HF Spaces Subdomain Resolver for Private Iframes
    let finalUrl = url;
    if (url.startsWith("./api/") || url.startsWith("/api/")) {
        const routePath = url.replace(/^\.\//, "/").replace(/^\/api\//, "api/");
        const currentOrigin = window.location.origin;
        if (currentOrigin.includes(".hf.space") || currentOrigin.includes("localhost") || currentOrigin.includes("127.0.0.1")) {
            finalUrl = `${currentOrigin}/${routePath}`;
        } else {
            // Fallback for remote context outside Space (unlikely in this setup)
            finalUrl = `https://juancs-dev-twitch-byte-bot.hf.space/${routePath}`;
        }
    }

    // Attach token in query string as fallback (HF proxy may block headers).
    if (activeToken) {
        const separator = finalUrl.includes("?") ? "&" : "?";
        finalUrl = `${finalUrl}${separator}auth=${encodeURIComponent(activeToken)}`;
    }

    try {
        const response = await fetch(finalUrl, fetchOptions);
        let payload = {};

        // Resilient path for empty/non-JSON body with successful HTTP status.
        try {
            payload = await response.json();
        } catch (_err) {
            payload = { ok: response.ok, rawFallback: true };
        }

        // API contract always includes "ok: boolean".
        const isPayloadOk = typeof payload === "object" && payload !== null && payload.ok !== false;

        if (!response.ok || !isPayloadOk) {
            const serverMessage = payload?.message || payload?.error || `HTTP ${response.status}`;
            const err = new Error(serverMessage);
            err.status = response.status;
            err.payload = payload;

            // Visual warning for missing/invalid permission on 403.
            if (response.status === 403) {
                console.warn("Access denied (403). Check your admin token.");
                const feedback = document.getElementById("channelFeedbackMsg");
                if (feedback) {
                    feedback.textContent = "Error 403: Admin token is invalid or missing in 'Optional Auth'.";
                    feedback.className = "panel-hint event-level-error";
                }
                const tokenInput = document.getElementById("adminTokenInput");
                if (tokenInput) {
                    tokenInput.style.border = "2px solid var(--danger)";
                    tokenInput.placeholder = "ENTER TOKEN HERE";
                }
            }

            throw err;
        }

        return payload;
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error(`Timeout after ${timeoutMs / 1000}s. Network failed or bot is unresponsive.`);
        }
        throw error;
    } finally {
        clearTimeout(timeoutId);
    }
}
