import { fetchHudMessages } from "./api.js";
import { renderHudMessages } from "./view.js";
import { getStorageItem } from "../shared/dom.js";

const HUD_POLL_INTERVAL_MS = 3000;

export function createHudController({ hudEls }) {
  let lastTs = 0;
  let timerId = 0;
  let ttsEnabled = false;

  function resolveAdminToken() {
    const tokenInput = document.getElementById("adminTokenInput");
    const domToken = tokenInput ? tokenInput.value.trim() : "";
    const localToken = getStorageItem("byte_dashboard_admin_token");
    const serverToken = window.BYTE_CONFIG?.adminToken || "";
    return domToken || localToken || serverToken;
  }

  function syncOverlayAccess() {
    const overlayUrl = new URL("/dashboard/hud", window.location.origin);
    const token = resolveAdminToken();
    if (token) {
      overlayUrl.searchParams.set("auth", token);
    }
    if (hudEls.overlayLink) {
      hudEls.overlayLink.href = overlayUrl.toString();
    }
    if (hudEls.overlayUrl) {
      hudEls.overlayUrl.textContent = overlayUrl.toString();
    }
  }

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
    timerId = window.setTimeout(
      async () => {
        await fetchAndRender();
        schedulePolling();
      },
      document.hidden ? HUD_POLL_INTERVAL_MS * 5 : HUD_POLL_INTERVAL_MS,
    );
  }

  function bindEvents() {
    syncOverlayAccess();

    if (hudEls.ttsToggle) {
      hudEls.ttsToggle.addEventListener("change", (e) => {
        ttsEnabled = e.target.checked;
      });
    }

    const tokenInput = document.getElementById("adminTokenInput");
    if (tokenInput) {
      tokenInput.addEventListener("input", syncOverlayAccess);
      tokenInput.addEventListener("change", syncOverlayAccess);
    }
  }

  return {
    startPolling: () => {
      syncOverlayAccess();
      fetchAndRender();
      schedulePolling();
    },
    bindEvents,
  };
}
