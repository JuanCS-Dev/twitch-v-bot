function getRootElement(documentRef) {
  if (!documentRef) return null;
  return documentRef.documentElement || null;
}

function toPixelValue(value) {
  if (!Number.isFinite(value)) {
    return "0px";
  }
  const safeValue = Math.max(0, Math.ceil(value));
  return `${safeValue}px`;
}

function readElementHeight(element) {
  if (!element) return 0;
  if (typeof element.getBoundingClientRect === "function") {
    const rect = element.getBoundingClientRect();
    if (rect && Number.isFinite(rect.height)) {
      return rect.height;
    }
  }
  const offsetHeight = Number(element.offsetHeight || 0);
  return Number.isFinite(offsetHeight) ? offsetHeight : 0;
}

export function initDashboardStickyOffset({
  documentRef = typeof document !== "undefined" ? document : null,
  windowRef = typeof window !== "undefined" ? window : null,
  resizeObserverFactory = typeof ResizeObserver !== "undefined"
    ? (callback) => new ResizeObserver(callback)
    : null,
} = {}) {
  const topbar = documentRef?.querySelector?.(".topbar");
  const tabsShell = documentRef?.querySelector?.(".dashboard-tabs-shell");
  const root = getRootElement(documentRef);

  if (!topbar || !tabsShell || !root?.style?.setProperty) {
    return () => {};
  }

  const applyOffset = () => {
    const topbarHeight = readElementHeight(topbar);
    root.style.setProperty(
      "--dashboard-tabs-sticky-top",
      toPixelValue(topbarHeight),
    );
  };

  applyOffset();

  const onResize = () => {
    applyOffset();
  };

  if (windowRef?.addEventListener) {
    windowRef.addEventListener("resize", onResize);
    windowRef.addEventListener("orientationchange", onResize);
  }

  let observer = null;
  if (typeof resizeObserverFactory === "function") {
    observer = resizeObserverFactory(() => {
      applyOffset();
    });
    observer?.observe?.(topbar);
  }

  return () => {
    if (windowRef?.removeEventListener) {
      windowRef.removeEventListener("resize", onResize);
      windowRef.removeEventListener("orientationchange", onResize);
    }
    observer?.disconnect?.();
  };
}
