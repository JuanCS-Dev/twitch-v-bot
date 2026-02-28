import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function extractPanel(indexHtml, panelId) {
  return (
    indexHtml.match(new RegExp(`id="${panelId}"[\\s\\S]*?<\\/section>`))?.[0] ||
    ""
  );
}

test("phase-3 summary strip and tab intros are present in dashboard shell", () => {
  const indexHtml = readText("../index.html");

  assert.ok(indexHtml.includes('id="globalSummaryStrip"'));
  assert.ok(indexHtml.includes('id="summaryFocusedChannel"'));
  assert.ok(indexHtml.includes('id="summaryRuntimeStatusChip"'));
  assert.ok(indexHtml.includes('id="summaryPersistenceStatusChip"'));
  assert.ok(indexHtml.includes('id="summaryStreamHealthScore"'));
  assert.ok(indexHtml.includes('id="summaryStreamHealthBandChip"'));
  assert.ok(indexHtml.includes('id="summaryQueuePendingCount"'));
  assert.ok(indexHtml.includes('id="summaryQueuePendingChip"'));
  assert.ok(indexHtml.includes('id="summaryAutonomyState"'));
  assert.ok(indexHtml.includes('id="summaryAutonomyBudget"'));

  const operationPanel = extractPanel(indexHtml, "dashboardTabOperationPanel");
  const intelligencePanel = extractPanel(
    indexHtml,
    "dashboardTabIntelligencePanel",
  );
  const clipsPanel = extractPanel(indexHtml, "dashboardTabClipsPanel");
  const analyticsPanel = extractPanel(indexHtml, "dashboardTabAnalyticsPanel");
  const configPanel = extractPanel(indexHtml, "dashboardTabConfigPanel");

  assert.match(operationPanel, /class="dashboard-tab-intro"/);
  assert.match(intelligencePanel, /class="dashboard-tab-intro"/);
  assert.match(clipsPanel, /class="dashboard-tab-intro"/);
  assert.match(analyticsPanel, /class="dashboard-tab-intro"/);
  assert.match(configPanel, /class="dashboard-tab-intro"/);
});

test("phase-3 moves secondary telemetry into advanced disclosure blocks", () => {
  const metricsHtml = readText("../partials/metrics_health.html");
  const analyticsHtml = readText("../partials/analytics_logs.html");

  assert.match(metricsHtml, /<details class="advanced-settings">/);
  assert.match(metricsHtml, /id="agentHealthCards"/);
  assert.match(metricsHtml, /id="agentOutcomeCards"/);

  assert.match(analyticsHtml, /<details class="advanced-settings">/);
  assert.match(
    analyticsHtml,
    /Expanded Context: Persisted State, History and Multi-Channel Comparison/,
  );
  assert.match(analyticsHtml, /id="ctxPersistedGame"/);
  assert.match(analyticsHtml, /id="persistedChannelTimelineBody"/);
  assert.match(analyticsHtml, /id="persistedChannelComparisonBody"/);
});
