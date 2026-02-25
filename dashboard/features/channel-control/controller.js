import { sendChannelAction } from "./api.js";
import {
    initTokenInput,
    renderConnectedChannels,
    setChannelBusy,
    showChannelFeedback,
} from "./view.js";

export function createChannelControlController({
    ctrlEls,
    applyRuntimeCapabilities,
    getErrorMessage,
}) {
    let activeChannelsState = [];

    async function handleChannelAction(actionType, channelLogin = "") {
        if (!ctrlEls) return;
        setChannelBusy(ctrlEls, true);
        showChannelFeedback(ctrlEls, `Processando ${actionType}...`, "warn");

        try {
            const response = await sendChannelAction(actionType, channelLogin);
            if (Array.isArray(response?.channels)) {
                activeChannelsState = response.channels;
                renderConnectedChannels(ctrlEls, activeChannelsState, (channel) =>
                    handleChannelAction("part", channel)
                );
            }
            if (response?.mode) {
                applyRuntimeCapabilities(
                    {
                        channel_control: {
                            enabled: response.mode === "irc",
                            reason: response.message || "",
                            supported_actions: response.mode === "irc" ? ["list", "join", "part"] : [],
                        },
                    },
                    response.mode
                );
            }
            showChannelFeedback(
                ctrlEls,
                response?.message || "Acao concluida.",
                "ok"
            );
            if (ctrlEls.channelInput) {
                ctrlEls.channelInput.value = "";
            }
        } catch (error) {
            console.error("Channel action error", error);
            if (error?.payload?.error === "unsupported_mode") {
                applyRuntimeCapabilities(
                    {
                        channel_control: {
                            enabled: false,
                            reason: getErrorMessage(error, "Modo sem suporte para join/part."),
                            supported_actions: [],
                        },
                    },
                    error?.payload?.mode || ""
                );
                showChannelFeedback(ctrlEls, getErrorMessage(error, "Modo nao suportado."), "warn");
                return;
            }
            showChannelFeedback(
                ctrlEls,
                `Erro: ${getErrorMessage(error, "Falha no channel control.")}`,
                "error"
            );
        } finally {
            setChannelBusy(ctrlEls, false);
        }
    }

    function bindChannelControlEvents() {
        if (!ctrlEls) return;
        initTokenInput(ctrlEls);

        if (ctrlEls.syncBtn) {
            ctrlEls.syncBtn.addEventListener("click", () => {
                if (ctrlEls.adminToken) {
                    localStorage.setItem("byte_dashboard_admin_token", ctrlEls.adminToken.value.trim());
                }
                handleChannelAction("list");
            });
        }

        if (ctrlEls.joinBtn) {
            ctrlEls.joinBtn.addEventListener("click", () => {
                if (ctrlEls.adminToken) {
                    localStorage.setItem("byte_dashboard_admin_token", ctrlEls.adminToken.value.trim());
                }
                const channelLogin = (ctrlEls.channelInput?.value || "").trim();
                if (!channelLogin) {
                    showChannelFeedback(
                        ctrlEls,
                        "Digite o login do canal antes de conectar.",
                        "error"
                    );
                    return;
                }
                handleChannelAction("join", channelLogin);
            });
        }

        if (ctrlEls.channelInput) {
            ctrlEls.channelInput.addEventListener("keydown", (event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                if (ctrlEls.joinBtn) {
                    ctrlEls.joinBtn.click();
                }
            });
        }
    }

    return {
        bindChannelControlEvents,
        handleChannelAction,
    };
}
