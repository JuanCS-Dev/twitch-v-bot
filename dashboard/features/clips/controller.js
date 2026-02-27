import { fetchClipJobs, fetchVisionStatus, postVisionIngest } from "./api.js";
import { renderClipCard, renderVisionStatus } from "./view.js";

// Polling adaptativo usando Page Visibility API
class AdaptivePoller {
    constructor(fn, intervalMs = 2000) {
        this.fn = fn;
        this.baseInterval = intervalMs;
        this.timer = null;
        this.isRunning = false;

        document.addEventListener("visibilitychange", () => {
            if (this.isRunning) {
                this.restart(); // Reinicia com novo intervalo baseado na visibilidade
            }
        });
    }

    start() {
        if (this.isRunning) return;
        this.isRunning = true;
        this.tick();
    }

    stop() {
        this.isRunning = false;
        if (this.timer) clearTimeout(this.timer);
    }

    restart() {
        if (this.timer) clearTimeout(this.timer);
        this.tick();
    }

    async tick() {
        if (!this.isRunning) return;

        await this.fn();

        const isHidden = document.hidden;
        const nextInterval = isHidden ? this.baseInterval * 5 : this.baseInterval;

        this.timer = setTimeout(() => this.tick(), nextInterval);
    }
}

export function createClipsController({ els }) {
    const render = (jobs) => {
        if (!els.container) return;

        if (jobs.length === 0) {
            els.container.innerHTML = '<div class="empty-state">Nenhum job de clip recente.</div>';
            return;
        }

        const html = jobs.map(renderClipCard).join("");
        // Simple DOM diffing could be added here for optimization,
        // but innerHTML is fast enough for < 50 items.
        // We check if content changed to avoid text selection loss if user is selecting text.
        if (els.container.innerHTML !== html) {
            els.container.innerHTML = html;
        }

        // Hide skeleton if visible
        if (els.loadingSkeleton) {
            els.loadingSkeleton.style.display = "none";
        }
    };

    const fetchAndRender = async () => {
        try {
            const [clipData, visionData] = await Promise.all([
                fetchClipJobs().catch(() => null),
                fetchVisionStatus().catch(() => null)
            ]);

            if (clipData?.ok && Array.isArray(clipData.items)) {
                render(clipData.items);
            }
            if (visionData?.ok) {
                renderVisionStatus(visionData, els);
            }
        } catch (error) {
            console.error("Erro no polling de clips:", error);
        }
    };

    const handleVisionIngest = async () => {
        if (!els.visionIngestInput || !els.visionIngestInput.files.length) {
            if (els.visionFeedback) els.visionFeedback.textContent = "Selecione uma imagem primeiro.";
            return;
        }

        const file = els.visionIngestInput.files[0];
        if (els.visionIngestBtn) els.visionIngestBtn.disabled = true;
        if (els.visionFeedback) els.visionFeedback.textContent = "Enviando frame...";

        try {
            const result = await postVisionIngest(file);
            if (result && result.ok) {
                els.visionFeedback.textContent = "Frame analisado com sucesso.";
                els.visionFeedback.className = "panel-hint event-level-info";
                els.visionIngestInput.value = ""; // clear
                await fetchAndRender();
            } else {
                els.visionFeedback.textContent = `Erro: ${result?.reason || 'Falha no envio'}`;
                els.visionFeedback.className = "panel-hint event-level-warn";
            }
        } catch (error) {
            els.visionFeedback.textContent = "Erro na comunicacao com o servidor.";
            els.visionFeedback.className = "panel-hint event-level-error";
        } finally {
            if (els.visionIngestBtn) els.visionIngestBtn.disabled = false;
        }
    };

    if (els.visionIngestBtn) {
        els.visionIngestBtn.addEventListener("click", handleVisionIngest);
    }

    const poller = new AdaptivePoller(fetchAndRender, 2000);

    return {
        startPolling: () => poller.start(),
        stopPolling: () => poller.stop(),
        manualRefresh: fetchAndRender
    };
}
