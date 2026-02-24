// dashboard/features/shared/api.js
import { getStorageItem } from "./dom.js";
export const TIMEOUT_DEFAULT_MS = 12000;

/**
 * Wrapper de Fetch padronizado que já captura erro Http como throwable real
 * e controla abort/timeout.
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
            // Fallback para caso remoto mas fora do space (improvável neste setup)
            finalUrl = `https://juancs-dev-twitch-byte-bot.hf.space/${routePath}`;
        }
    }
    
    // Anexa o token na Query String como fallback (Proxy do HF bloqueia headers as vezes)
    if (activeToken) {
        const separator = finalUrl.includes("?") ? "&" : "?";
        finalUrl = `${finalUrl}${separator}auth=${encodeURIComponent(activeToken)}`;
    }

    try {
        const response = await fetch(finalUrl, fetchOptions);
        let payload = {};

        // Tratativa resiliente para corpo vazio/nao-json mas com sucesso HTTP
        try {
            payload = await response.json();
        } catch (_err) {
            payload = { ok: response.ok, rawFallback: true };
        }

        // A API atual sempre retorna "ok: boolean". Validar contra a resposta
        const isPayloadOk = typeof payload === "object" && payload !== null && payload.ok !== false;

        if (!response.ok || !isPayloadOk) {
            const serverMessage = payload?.message || payload?.error || `HTTP ${response.status}`;
            const err = new Error(serverMessage);
            err.status = response.status;
            err.payload = payload;

            // Alerta visual de falta de permissão se for 403
            if (response.status === 403) {
                console.warn("Acesso Negado (403). Verifique seu Admin Token.");
                const feedback = document.getElementById("channelFeedbackMsg");
                if (feedback) {
                    feedback.textContent = "Erro 403: Token de Admin inválido ou ausente em 'Optional Auth'.";
                    feedback.className = "panel-hint event-level-error";
                }
                const tokenInput = document.getElementById("adminTokenInput");
                if (tokenInput) {
                    tokenInput.style.border = "2px solid var(--danger)";
                    tokenInput.placeholder = "INSIRA O TOKEN AQUI";
                }
            }

            throw err;
        }

        return payload;
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error(`Timeout apos ${timeoutMs / 1000}s. A rede falhou ou o bot travou.`);
        }
        throw error;
    } finally {
        clearTimeout(timeoutId);
    }
}
