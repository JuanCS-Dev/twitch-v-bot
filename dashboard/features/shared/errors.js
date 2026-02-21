export function getErrorMessage(error, fallbackMessage) {
    const payload = error && typeof error.payload === "object" ? error.payload : {};
    const fromPayload = payload?.message || payload?.error;
    if (String(fromPayload || "").trim()) {
        return String(fromPayload);
    }
    if (String(error?.message || "").trim()) {
        return String(error.message);
    }
    return fallbackMessage;
}

