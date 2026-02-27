import { setText, formatNumber } from "../shared/dom.js";

export function getHudElements() {
  return {
    messagesList: document.getElementById("hudMessagesList"),
    messageCount: document.getElementById("hudMessageCount"),
    ttsToggle: document.getElementById("hudTtsToggle"),
    overlayLink: document.getElementById("hudOverlayLink"),
    overlayUrl: document.getElementById("hudOverlayUrl"),
  };
}

function escapeHtml(str) {
  if (!str) return "";
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

export function renderHudMessages(messages, els) {
  if (!els.messagesList) return;
  const safeMessages = Array.isArray(messages) ? messages : [];

  setText(els.messageCount, formatNumber(safeMessages.length));

  if (safeMessages.length === 0) {
    els.messagesList.innerHTML =
      '<li style="font-style:italic; color:var(--text-muted);">Nenhuma sugestão do agente ainda.</li>';
    return;
  }

  const html = safeMessages
    .slice()
    .reverse()
    .map((msg) => {
      const time = new Date(msg.ts * 1000).toLocaleTimeString();
      const source = String(msg.source || "autonomy")
        .trim()
        .toLowerCase();
      const sourceClass =
        source === "vision" ? "pending" : source === "coaching" ? "warn" : "ok";
      return `<li>
                <div class="event-meta">
                    <span>${escapeHtml(time)}</span>
                    <span class="chip ${sourceClass}">${escapeHtml(source)}</span>
                </div>
                <div>${escapeHtml(msg.text)}</div>
            </li>`;
    })
    .join("");

  els.messagesList.innerHTML = html;
}
