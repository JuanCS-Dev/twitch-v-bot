import { sendChannelAction } from "./api.js";
import {
  getDashboardChannelSelection,
  initTokenInput,
  initDashboardChannelInput,
  renderDashboardChannelSelection,
  renderConnectedChannels,
  setChannelBusy,
  showChannelFeedback,
} from "./view.js";

export function createChannelControlController({
  ctrlEls,
  applyRuntimeCapabilities,
  getErrorMessage,
  onDashboardChannelChange,
}) {
  let activeChannelsState = [];

  function applyDashboardChannel(channelId) {
    if (!ctrlEls) return "default";
    const safeChannel = renderDashboardChannelSelection(ctrlEls, channelId);
    if (typeof onDashboardChannelChange === "function") {
      Promise.resolve(onDashboardChannelChange(safeChannel)).catch((error) => {
        console.error("Dashboard channel sync error", error);
        showChannelFeedback(
          ctrlEls,
          `Error: ${getErrorMessage(error, "Failed to sync dashboard channel.")}`,
          "error",
        );
      });
    }
    return safeChannel;
  }

  async function handleChannelAction(actionType, channelLogin = "") {
    if (!ctrlEls) return;
    setChannelBusy(ctrlEls, true);
    showChannelFeedback(ctrlEls, `Processing ${actionType}...`, "warn");

    try {
      const response = await sendChannelAction(actionType, channelLogin);
      if (Array.isArray(response?.channels)) {
        activeChannelsState = response.channels;
        renderConnectedChannels(ctrlEls, activeChannelsState, (channel) =>
          handleChannelAction("part", channel),
        );
      }
      if (response?.mode) {
        applyRuntimeCapabilities(
          {
            channel_control: {
              enabled: response.mode === "irc",
              reason: response.message || "",
              supported_actions:
                response.mode === "irc" ? ["list", "join", "part"] : [],
            },
          },
          response.mode,
        );
      }
      showChannelFeedback(
        ctrlEls,
        response?.message || "Action completed.",
        "ok",
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
              reason: getErrorMessage(
                error,
                "Mode does not support join/part.",
              ),
              supported_actions: [],
            },
          },
          error?.payload?.mode || "",
        );
        showChannelFeedback(
          ctrlEls,
          getErrorMessage(error, "Unsupported mode."),
          "warn",
        );
        return;
      }
      showChannelFeedback(
        ctrlEls,
        `Error: ${getErrorMessage(error, "Channel control failed.")}`,
        "error",
      );
    } finally {
      setChannelBusy(ctrlEls, false);
    }
  }

  function bindChannelControlEvents() {
    if (!ctrlEls) return;
    initTokenInput(ctrlEls);
    initDashboardChannelInput(ctrlEls, (channelId) => {
      applyDashboardChannel(channelId);
    });

    if (ctrlEls.syncBtn) {
      ctrlEls.syncBtn.addEventListener("click", () => {
        if (ctrlEls.adminToken) {
          localStorage.setItem(
            "byte_dashboard_admin_token",
            ctrlEls.adminToken.value.trim(),
          );
        }
        handleChannelAction("list");
      });
    }

    if (ctrlEls.joinBtn) {
      ctrlEls.joinBtn.addEventListener("click", () => {
        if (ctrlEls.adminToken) {
          localStorage.setItem(
            "byte_dashboard_admin_token",
            ctrlEls.adminToken.value.trim(),
          );
        }
        const channelLogin = (ctrlEls.channelInput?.value || "").trim();
        if (!channelLogin) {
          showChannelFeedback(
            ctrlEls,
            "Enter the channel login before connecting.",
            "error",
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
    getSelectedDashboardChannel() {
      return getDashboardChannelSelection(ctrlEls);
    },
    handleChannelAction,
    setSelectedDashboardChannel(channelId) {
      return applyDashboardChannel(channelId);
    },
  };
}
