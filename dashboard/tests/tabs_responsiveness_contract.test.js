import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

test("tabs shell keeps sticky desktop behavior and touch-safe targets", () => {
  const layoutCss = readText("../styles/layout.css");

  assert.match(
    layoutCss,
    /\.dashboard-tabs-shell\s*\{[\s\S]*position:\s*sticky;[\s\S]*top:\s*var\(--dashboard-tabs-sticky-top,\s*0px\);[\s\S]*\}/,
  );
  assert.match(layoutCss, /\.dashboard-tab-btn\s*\{[\s\S]*min-height:\s*44px;/);
  assert.doesNotMatch(
    layoutCss,
    /\.dashboard-tabs-shell\s*\{[\s\S]*top:\s*86px;/,
  );
});

test("tablet and mobile tab navigation support horizontal scrolling", () => {
  const layoutCss = readText("../styles/layout.css");

  assert.match(
    layoutCss,
    /@media\s*\(max-width:\s*1024px\)\s*\{[\s\S]*\.dashboard-tabs\s*\{[\s\S]*flex-wrap:\s*nowrap;[\s\S]*overflow-x:\s*auto;[\s\S]*\}/,
  );
  assert.match(
    layoutCss,
    /@media\s*\(max-width:\s*1024px\)\s*\{[\s\S]*\.dashboard-tab-btn\s*\{[\s\S]*flex:\s*0 0 auto;[\s\S]*\}/,
  );
  assert.match(
    layoutCss,
    /@media\s*\(max-width:\s*600px\)\s*\{[\s\S]*\.dashboard-tabs-shell\s*\{[\s\S]*top:\s*var\(--dashboard-tabs-sticky-top,\s*0px\);[\s\S]*\}/,
  );
});
