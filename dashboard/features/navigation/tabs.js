const DASHBOARD_TAB_STORAGE_KEY = "byte_dashboard_active_tab";
const DASHBOARD_TAB_QUERY_KEY = "tab";
const initializedTabsByDocument = new WeakMap();

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

function getLocationFromRef(locationRef) {
  if (locationRef) {
    return locationRef;
  }
  if (typeof window !== "undefined" && window.location) {
    return window.location;
  }
  if (typeof location !== "undefined") {
    return location;
  }
  return null;
}

function getHistoryFromRef(historyRef) {
  if (historyRef) {
    return historyRef;
  }
  if (typeof window !== "undefined" && window.history) {
    return window.history;
  }
  if (typeof history !== "undefined") {
    return history;
  }
  return null;
}

function getEventTargetFromRef(eventTargetRef) {
  if (eventTargetRef) {
    return eventTargetRef;
  }
  if (typeof window !== "undefined" && window.addEventListener) {
    return window;
  }
  return null;
}

function readTabIdFromLocation(locationRef) {
  if (!locationRef) {
    return "";
  }
  try {
    const search = String(locationRef.search || "").trim();
    if (!search) {
      return "";
    }
    const params = new URLSearchParams(
      search.startsWith("?") ? search : `?${search}`,
    );
    return String(params.get(DASHBOARD_TAB_QUERY_KEY) || "").trim();
  } catch {
    return "";
  }
}

function persistTabIdInLocation(historyRef, locationRef, tabId) {
  if (
    !historyRef ||
    typeof historyRef.replaceState !== "function" ||
    !locationRef
  ) {
    return;
  }
  try {
    const pathname = String(locationRef.pathname || "/");
    const currentSearch = String(locationRef.search || "");
    const hash = String(locationRef.hash || "");
    const params = new URLSearchParams(
      currentSearch.startsWith("?") ? currentSearch : `?${currentSearch}`,
    );
    if (params.get(DASHBOARD_TAB_QUERY_KEY) === tabId) {
      return;
    }
    params.set(DASHBOARD_TAB_QUERY_KEY, tabId);
    const nextSearch = params.toString();
    historyRef.replaceState(
      null,
      "",
      `${pathname}${nextSearch ? `?${nextSearch}` : ""}${hash}`,
    );
  } catch {
    // no-op: ambientes sem suporte total ao History API.
  }
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

export function initDashboardTabs({
  documentRef,
  storageRef,
  locationRef,
  historyRef,
  eventTargetRef,
} = {}) {
  const doc = getDocumentFromRef(documentRef);
  if (!doc || typeof doc.querySelectorAll !== "function") {
    return null;
  }

  const cached = initializedTabsByDocument.get(doc);
  if (cached) {
    return cached;
  }

  const { tabs, panelByTabId } = collectDashboardTabs(doc);
  if (!tabs.length || !panelByTabId.size) {
    return null;
  }

  const storage = getStorageFromRef(storageRef);
  const location = getLocationFromRef(locationRef);
  const history = getHistoryFromRef(historyRef);
  const eventTarget = getEventTargetFromRef(eventTargetRef);
  let activeTabId = "";

  function isKnownTabId(candidateTabId) {
    const normalizedCandidate = String(candidateTabId || "").trim();
    if (!normalizedCandidate) {
      return false;
    }
    const hasTab = tabs.some(
      (tab) => String(tab.dataset.dashboardTab || "") === normalizedCandidate,
    );
    return hasTab && panelByTabId.has(normalizedCandidate);
  }

  function resolveTargetTabId(candidateTabId) {
    const target = String(candidateTabId || "").trim();
    if (isKnownTabId(target)) {
      return target;
    }
    return String(tabs[0].dataset.dashboardTab || "").trim();
  }

  function activateTab(
    tabId,
    { persist = true, focus = false, syncUrl = true, reveal = true } = {},
  ) {
    const resolvedTabId = resolveTargetTabId(tabId);
    activeTabId = resolvedTabId;
    let activeTabElement = null;

    tabs.forEach((tab) => {
      const currentTabId = String(tab.dataset.dashboardTab || "");
      const isActive = currentTabId === resolvedTabId;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
      tab.tabIndex = isActive ? 0 : -1;
      if (isActive) {
        activeTabElement = tab;
      }
      if (isActive && focus && typeof tab.focus === "function") {
        tab.focus();
      }
    });

    panelByTabId.forEach((panel, panelTabId) => {
      const isActive = panelTabId === resolvedTabId;
      panel.classList.toggle("is-active", isActive);
      panel.hidden = !isActive;
      panel.setAttribute("aria-hidden", isActive ? "false" : "true");
    });

    if (persist) {
      persistTabId(storage, resolvedTabId);
    }
    if (
      reveal &&
      activeTabElement &&
      typeof activeTabElement.scrollIntoView === "function"
    ) {
      try {
        activeTabElement.scrollIntoView({
          block: "nearest",
          inline: "nearest",
        });
      } catch {
        // no-op: fallback para ambientes sem scrollIntoView completo.
      }
    }
    if (syncUrl) {
      persistTabIdInLocation(history, location, resolvedTabId);
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
  const tabFromLocation = readTabIdFromLocation(location);
  const storedTabId = readStoredTabId(storage);
  const selectedTabId = String(
    selectedInMarkup?.dataset?.dashboardTab || "",
  ).trim();
  const initialCandidateTabId =
    (isKnownTabId(tabFromLocation) && tabFromLocation) ||
    (isKnownTabId(storedTabId) && storedTabId) ||
    (isKnownTabId(selectedTabId) && selectedTabId);
  const initialTabId = resolveTargetTabId(initialCandidateTabId);
  activateTab(initialTabId, { persist: false, syncUrl: true });

  if (eventTarget && typeof eventTarget.addEventListener === "function") {
    eventTarget.addEventListener("popstate", () => {
      const nextTabId = readTabIdFromLocation(location);
      if (!isKnownTabId(nextTabId)) {
        return;
      }
      const resolvedTabId = String(nextTabId).trim();
      if (resolvedTabId === activeTabId) {
        return;
      }
      activateTab(resolvedTabId, { persist: true, syncUrl: false });
    });
  }

  const api = {
    activateTab,
    getActiveTab() {
      return activeTabId;
    },
  };
  initializedTabsByDocument.set(doc, api);
  return api;
}
