import { triggerAutonomyTick } from "./api.js";
import {
    renderAutonomyRuntime,
    setAutonomyBusy,
    showAutonomyFeedback,
} from "./view.js";

export function createAutonomyController({
    autEls,
    refreshActionQueue,
    getErrorMessage,
}) {
    async function runManualAutonomyTick() {
        if (!autEls) return;
        setAutonomyBusy(autEls, true);
        const reasonInput = String(autEls.tickReasonInput?.value || "").trim();
        const reason = reasonInput || "manual_dashboard";
        showAutonomyFeedback(autEls, "Running 1 tick...", "warn");
        try {
            const payload = await triggerAutonomyTick({ force: true, reason });
            renderAutonomyRuntime(payload?.runtime || {}, autEls);
            const processedCount = Array.isArray(payload?.processed)
                ? payload.processed.length
                : Number(payload?.due_goals || 0);
            showAutonomyFeedback(
                autEls,
                `Tick completed. Goals processed: ${processedCount}.`,
                "ok"
            );
            await refreshActionQueue({ showFeedback: false });
        } catch (error) {
            console.error("Autonomy manual tick error", error);
            showAutonomyFeedback(
                autEls,
                `Error: ${getErrorMessage(error, "Failed to run tick.")}`,
                "error"
            );
        } finally {
            setAutonomyBusy(autEls, false);
        }
    }

    function bindAutonomyEvents() {
        if (!autEls?.tickBtn) return;
        autEls.tickBtn.addEventListener("click", () => {
            runManualAutonomyTick();
        });
    }

    return {
        bindAutonomyEvents,
    };
}
