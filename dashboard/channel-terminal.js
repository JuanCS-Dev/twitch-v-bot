const CHANNEL_CONTROL_ENDPOINT = "/api/channel-control";
const CHANNEL_CONTROL_TIMEOUT_MS = 12000;
const TERMINAL_TOKEN_STORAGE_KEY = "byte_dashboard_admin_token";

const terminalElements = {
  tokenInput: document.getElementById("terminalAdminToken"),
  commandInput: document.getElementById("terminalCommandInput"),
  runButton: document.getElementById("terminalRunButton"),
  listButton: document.getElementById("terminalListButton"),
  output: document.getElementById("terminalOutput"),
};

let terminalBusy = false;

function getStoredAdminToken() {
  try {
    return String(window.localStorage.getItem(TERMINAL_TOKEN_STORAGE_KEY) || "").trim();
  } catch (_error) {
    return "";
  }
}

function persistAdminToken(value) {
  try {
    const safeValue = String(value || "");
    if (safeValue.trim()) {
      window.localStorage.setItem(TERMINAL_TOKEN_STORAGE_KEY, safeValue);
    } else {
      window.localStorage.removeItem(TERMINAL_TOKEN_STORAGE_KEY);
    }
  } catch (_error) {
    // localStorage can be blocked; ignore and continue.
  }
}

function setTerminalBusy(isBusy) {
  terminalBusy = isBusy;
  if (terminalElements.tokenInput) {
    terminalElements.tokenInput.disabled = isBusy;
  }
  if (terminalElements.commandInput) {
    terminalElements.commandInput.disabled = isBusy;
  }
  if (terminalElements.runButton) {
    terminalElements.runButton.disabled = isBusy;
    terminalElements.runButton.textContent = isBusy ? "Running..." : "Run";
  }
  if (terminalElements.listButton) {
    terminalElements.listButton.disabled = isBusy;
  }
}

function formatChannels(channels) {
  if (!Array.isArray(channels) || channels.length === 0) {
    return "none";
  }
  return channels.map((channel) => `#${channel}`).join(", ");
}

function printTerminal(lines, isError = false) {
  if (!terminalElements.output) {
    return;
  }
  const timestamp = new Date().toLocaleTimeString();
  const body = Array.isArray(lines) ? lines.join("\n") : String(lines);
  terminalElements.output.dataset.state = isError ? "error" : "ok";
  terminalElements.output.textContent = `[${timestamp}] ${body}`;
}

async function runTerminalCommand(commandText) {
  if (terminalBusy) {
    return;
  }
  const token = String(terminalElements.tokenInput?.value || "").trim();
  const command = String(commandText || "").trim();

  if (!command) {
    printTerminal(["Command is required. Use: list | join <channel> | part <channel>."], true);
    return;
  }

  setTerminalBusy(true);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CHANNEL_CONTROL_TIMEOUT_MS);
  const outputLines = [`> ${command}`];

  try {
    const headers = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["X-Byte-Admin-Token"] = token;
    }

    const response = await fetch(CHANNEL_CONTROL_ENDPOINT, {
      method: "POST",
      cache: "no-store",
      signal: controller.signal,
      headers,
      body: JSON.stringify({ command }),
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }
    const safePayload = payload && typeof payload === "object" ? payload : {};

    if (typeof safePayload.message === "string" && safePayload.message.trim()) {
      outputLines.push(safePayload.message.trim());
    }
    if (safePayload.channels !== undefined) {
      outputLines.push(`Channels: ${formatChannels(safePayload.channels)}`);
    }

    const isPayloadOk = safePayload.ok !== false;
    if (!response.ok || !isPayloadOk) {
      if (response.status === 403 && !token) {
        outputLines.push("Forbidden: use browser login (Basic Auth) or fill Admin Token.");
      }
      outputLines.push(`HTTP ${response.status}`);
      printTerminal(outputLines, true);
      return;
    }

    printTerminal(outputLines, false);
    if (typeof window.byteRefreshSnapshot === "function") {
      window.byteRefreshSnapshot();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    printTerminal([...outputLines, `Request failed: ${message}`], true);
  } finally {
    clearTimeout(timeoutId);
    setTerminalBusy(false);
  }
}

function bindTerminalEvents() {
  if (!terminalElements.commandInput || !terminalElements.runButton || !terminalElements.listButton) {
    return;
  }

  if (terminalElements.tokenInput) {
    terminalElements.tokenInput.value = getStoredAdminToken();
    terminalElements.tokenInput.addEventListener("change", () => {
      persistAdminToken(terminalElements.tokenInput?.value || "");
    });
    terminalElements.tokenInput.addEventListener("blur", () => {
      persistAdminToken(terminalElements.tokenInput?.value || "");
    });
  }

  terminalElements.runButton.addEventListener("click", () => {
    runTerminalCommand(String(terminalElements.commandInput?.value || ""));
  });

  terminalElements.listButton.addEventListener("click", () => {
    if (terminalElements.commandInput) {
      terminalElements.commandInput.value = "list";
    }
    runTerminalCommand("list");
  });

  terminalElements.commandInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    runTerminalCommand(String(terminalElements.commandInput?.value || ""));
  });
}

bindTerminalEvents();
