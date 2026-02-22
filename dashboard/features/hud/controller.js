import { fetchHudMessages } from "./api.js";
import { renderHudMessages } from "./view.js";

const HUD_POLL_INTERVAL_MS = 3000;

export function createHudController({ hudEls }) {
    let lastTs = 0;
    let timerId = 0;
    let ttsEnabled = false;

    function speakMessage(text) {
        if (!ttsEnabled || !window.speechSynthesis) return;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "pt-BR";
        utterance.rate = 1.1;
        window.speechSynthesis.speak(utterance);
    }

    async function fetchAndRender() {
        try {
            const data = await fetchHudMessages(lastTs);
            if (data.ok && Array.isArray(data.messages)) {
                renderHudMessages(data.messages, hudEls);
                // TTS for new messages
                if (data.messages.length > 0) {
                    const newest = data.messages[data.messages.length - 1];
                    const newestTs = newest.ts || 0;
                    if (newestTs > lastTs && lastTs > 0) {
                        speakMessage(newest.text);
                    }
                    lastTs = Math.max(lastTs, newestTs);
                }
            }
        } catch (error) {
            console.error("HUD polling error:", error);
        }
    }

    function schedulePolling() {
        if (timerId) window.clearTimeout(timerId);
        timerId = window.setTimeout(async () => {
            await fetchAndRender();
            schedulePolling();
        }, document.hidden ? HUD_POLL_INTERVAL_MS * 5 : HUD_POLL_INTERVAL_MS);
    }

    function bindEvents() {
        if (hudEls.ttsToggle) {
            hudEls.ttsToggle.addEventListener("change", (e) => {
                ttsEnabled = e.target.checked;
            });
        }
    }

    return {
        startPolling: () => {
            fetchAndRender();
            schedulePolling();
        },
        bindEvents,
    };
}
