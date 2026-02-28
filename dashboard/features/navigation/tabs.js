const DASHBOARD_TAB_STORAGE_KEY = "byte_dashboard_active_tab";

function readStoredTabId(storage) {
  if (!storage || typeof storage.getItem !== "function") {
    return "";
  }
  try {
    return String(storage.getItem(DASHBOARD_TAB_STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

function persistTabId(storage, tabId) {
  if (!storage || typeof storage.setItem !== "function") {
    return;
  }
  try {
    storage.setItem(DASHBOARD_TAB_STORAGE_KEY, tabId);
  } catch {
    // no-op: storage pode estar indisponivel em ambientes restritos.
  }
}

function getDocumentFromRef(documentRef) {
  if (documentRef) {
    return documentRef;
  }
  if (typeof document !== "undefined") {
    return document;
  }
  return null;
}

function getStorageFromRef(storageRef) {
  if (storageRef) {
    return storageRef;
  }
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage;
  }
  if (typeof localStorage !== "undefined") {
    return localStorage;
  }
  return null;
}

function collectDashboardTabs(doc) {
  const tabs = Array.from(doc.querySelectorAll("[data-dashboard-tab]"));
  const panels = Array.from(doc.querySelectorAll("[data-dashboard-tab-panel]"));
  const panelByTabId = new Map(
    panels.map((panel) => [
      String(panel.dataset.dashboardTabPanel || ""),
      panel,
    ]),
  );
  return { tabs, panelByTabId };
}

function clampIndex(index, size) {
  if (size <= 0) return 0;
  if (index < 0) return size - 1;
  if (index >= size) return 0;
  return index;
}

export function initDashboardTabs({ documentRef, storageRef } = {}) {
  const doc = getDocumentFromRef(documentRef);
  if (!doc || typeof doc.querySelectorAll !== "function") {
    return null;
  }

  const { tabs, panelByTabId } = collectDashboardTabs(doc);
  if (!tabs.length || !panelByTabId.size) {
    return null;
  }

  const storage = getStorageFromRef(storageRef);
  let activeTabId = "";

  function resolveTargetTabId(candidateTabId) {
    const target = String(candidateTabId || "").trim();
    const hasTab = tabs.some(
      (tab) => String(tab.dataset.dashboardTab || "") === target,
    );
    if (target && hasTab && panelByTabId.has(target)) {
      return target;
    }
    return String(tabs[0].dataset.dashboardTab || "").trim();
  }

  function activateTab(tabId, { persist = true, focus = false } = {}) {
    const resolvedTabId = resolveTargetTabId(tabId);
    activeTabId = resolvedTabId;

    tabs.forEach((tab) => {
      const currentTabId = String(tab.dataset.dashboardTab || "");
      const isActive = currentTabId === resolvedTabId;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
      tab.tabIndex = isActive ? 0 : -1;
      if (isActive && focus && typeof tab.focus === "function") {
        tab.focus();
      }
    });

    panelByTabId.forEach((panel, panelTabId) => {
      const isActive = panelTabId === resolvedTabId;
      panel.classList.toggle("is-active", isActive);
      panel.hidden = !isActive;
    });

    if (persist) {
      persistTabId(storage, resolvedTabId);
    }
    return resolvedTabId;
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      activateTab(tab.dataset.dashboardTab);
    });

    tab.addEventListener("keydown", (event) => {
      const key = String(event.key || "");
      let targetIndex = index;
      if (key === "ArrowRight") {
        targetIndex = clampIndex(index + 1, tabs.length);
      } else if (key === "ArrowLeft") {
        targetIndex = clampIndex(index - 1, tabs.length);
      } else if (key === "Home") {
        targetIndex = 0;
      } else if (key === "End") {
        targetIndex = tabs.length - 1;
      } else {
        return;
      }
      event.preventDefault();
      activateTab(tabs[targetIndex].dataset.dashboardTab, { focus: true });
    });
  });

  const selectedInMarkup = tabs.find(
    (tab) => tab.getAttribute("aria-selected") === "true",
  );
  const storedTabId = readStoredTabId(storage);
  const initialTabId = storedTabId
    ? resolveTargetTabId(storedTabId)
    : resolveTargetTabId(selectedInMarkup?.dataset?.dashboardTab);
  activateTab(initialTabId, { persist: false });

  return {
    activateTab,
    getActiveTab() {
      return activeTabId;
    },
  };
}
