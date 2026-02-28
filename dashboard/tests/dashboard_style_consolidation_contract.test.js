import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("phase-13 keeps stylesheet links valid and local in dashboard shell", () => {
  const indexHtml = readText("../index.html");
  const hrefMatches = [
    ...indexHtml.matchAll(/<link\s+rel="stylesheet"\s+href="([^"]+)"/g),
  ];
  const hrefs = hrefMatches.map((match) => match[1]);

  const expectedHrefs = [
    "/dashboard/styles/tokens.css",
    "/dashboard/styles/base.css",
    "/dashboard/styles/layout.css",
    "/dashboard/styles/components.css",
    "/dashboard/styles/clips.css",
  ];

  assert.deepEqual(hrefs, expectedHrefs);

  hrefs.forEach((href) => {
    const localRelativePath = href.replace("/dashboard/", "../");
    const absolutePath = new URL(localRelativePath, import.meta.url);
    assert.ok(existsSync(absolutePath), `Missing stylesheet target: ${href}`);
  });
});

test("phase-13 removes inline styles from dashboard shell and partials", () => {
  const indexHtml = readText("../index.html");
  assert.doesNotMatch(indexHtml, /\sstyle\s*=/i);

  const partialDir = new URL("../partials/", import.meta.url);
  const partialFiles = readdirSync(partialDir).filter((file) =>
    file.endsWith(".html"),
  );
  partialFiles.forEach((partialFile) => {
    const partialContent = readText(`../partials/${partialFile}`);
    assert.doesNotMatch(
      partialContent,
      /\sstyle\s*=/i,
      `Inline style found in ${partialFile}`,
    );
  });
});

test("phase-13 utility classes used by migrated markup are defined in components css", () => {
  const componentsCss = readText("../styles/components.css");
  const requiredClassSelectors = [
    ".form-row-center",
    ".form-row-between",
    ".form-row-wrap",
    ".section-surface",
    ".section-divider-top",
    ".events-scroll-560",
    ".events-scroll-500",
    ".events-scroll-200",
    ".events-list-chips",
    ".panel-header-row",
    ".code-block-scroll-120",
    ".autonomy-budget-visual",
    ".autonomy-budget-ring",
    ".sentiment-track",
    ".sentiment-progress",
    ".toggle-switch-mt-14",
    ".fatal-error-screen",
  ];

  requiredClassSelectors.forEach((selector) => {
    assert.match(
      componentsCss,
      new RegExp(escapeRegex(selector)),
      `Missing CSS selector ${selector}`,
    );
  });
});
