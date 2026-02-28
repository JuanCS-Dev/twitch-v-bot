import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function assertPartialMapping(indexHtml, id, url) {
  const escapedUrl = url.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`id:\\s*"${id}"[\\s\\S]*?url:\\s*"${escapedUrl}"`);
  assert.ok(
    pattern.test(indexHtml),
    `Expected partial mapping ${id} -> ${url}`,
  );
}

test("dashboard operation/config panels include the expected containers", () => {
  const indexHtml = readText("../index.html");
  const operationPanel =
    indexHtml.match(
      /id="dashboardTabOperationPanel"[\s\S]*?<\/section>/,
    )?.[0] || "";
  const configPanel =
    indexHtml.match(/id="dashboardTabConfigPanel"[\s\S]*?<\/section>/)?.[0] ||
    "";

  assert.ok(operationPanel.includes('id="metricsHealthContainer"'));
  assert.ok(operationPanel.includes('id="riskQueueContainer"'));
  assert.ok(operationPanel.includes('id="autonomyRuntimeContainer"'));
  assert.ok(operationPanel.includes('id="operationEventsContainer"'));

  assert.ok(configPanel.includes('id="controlPlaneContainer"'));
});

test("dashboard partial loader maps new phase-2 containers correctly", () => {
  const indexHtml = readText("../index.html");

  assertPartialMapping(
    indexHtml,
    "controlPlaneContainer",
    "/dashboard/partials/control_plane.html",
  );
  assertPartialMapping(
    indexHtml,
    "autonomyRuntimeContainer",
    "/dashboard/partials/autonomy_runtime.html",
  );
  assertPartialMapping(
    indexHtml,
    "operationEventsContainer",
    "/dashboard/partials/operational_events.html",
  );
  assertPartialMapping(
    indexHtml,
    "analyticsLogsContainer",
    "/dashboard/partials/analytics_logs.html",
  );
});

test("phase-2 partial split keeps IDs in the right files", () => {
  const controlPlaneHtml = readText("../partials/control_plane.html");
  const autonomyRuntimeHtml = readText("../partials/autonomy_runtime.html");
  const analyticsLogsHtml = readText("../partials/analytics_logs.html");
  const operationalEventsHtml = readText("../partials/operational_events.html");

  assert.ok(controlPlaneHtml.includes('id="cpPanel"'));
  assert.ok(!controlPlaneHtml.includes('id="autRunTickBtn"'));

  assert.ok(autonomyRuntimeHtml.includes('id="autRunTickBtn"'));
  assert.ok(autonomyRuntimeHtml.includes('id="autBudgetPctText"'));

  assert.ok(!analyticsLogsHtml.includes('id="eventsList"'));
  assert.ok(analyticsLogsHtml.includes('id="timelineBody"'));

  assert.ok(operationalEventsHtml.includes('id="eventsList"'));
});
