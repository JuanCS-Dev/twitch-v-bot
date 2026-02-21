// dashboard/features/shared/api.js

export const TIMEOUT_DEFAULT_MS = 12000;

/**
 * Wrapper de Fetch padronizado que já captura erro Http como throwable real
 * e controla abort/timeout.
 */
export async function fetchWithTimeout(url, options = {}, timeoutMs = TIMEOUT_DEFAULT_MS) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const fetchOptions = {
        ...options,
        signal: controller.signal,
        cache: "no-store",
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    };

    try {
        const response = await fetch(url, fetchOptions);
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
