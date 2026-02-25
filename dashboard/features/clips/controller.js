import { fetchClipJobs } from "./api.js";
import { renderClipCard } from "./view.js";

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
            const data = await fetchClipJobs();
            if (data.ok && Array.isArray(data.items)) {
                render(data.items);
            }
        } catch (error) {
            console.error("Erro no polling de clips:", error);
        }
    };

    const poller = new AdaptivePoller(fetchAndRender, 2000);

    return {
        startPolling: () => poller.start(),
        stopPolling: () => poller.stop(),
        manualRefresh: fetchAndRender
    };
}
