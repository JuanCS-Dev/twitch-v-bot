import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function indexOfLabel(html, label) {
  const match = html.match(new RegExp(`>\\s*${escapeRegExp(label)}\\s*<`));
  return match?.index ?? -1;
}

function extractSectionById(html, id) {
  return (
    html.match(
      new RegExp(`<section[^>]*id="${id}"[\\s\\S]*?<\\/section>`),
    )?.[0] || ""
  );
}

function extractAdvancedDetailsBySummary(html, summaryLabel) {
  return (
    html.match(
      new RegExp(
        `<details class="advanced-settings">[\\s\\S]*?<summary>\\s*${escapeRegExp(summaryLabel)}\\s*<\\/summary>[\\s\\S]*?<\\/details>`,
      ),
    )?.[0] || ""
  );
}

test("phase-12 analytics keeps decision-first hierarchy with clear domain separation", () => {
  const analyticsHtml = readText("../partials/analytics_logs.html");

  const orderedLabels = [
    "Analytics Decision Brief",
    "Runtime Context",
    "Timeline Logs Realtime (Last 30 min)",
    "Deep Analytics (60m)",
    "Persisted History and Comparison",
  ];
  let cursor = -1;
  orderedLabels.forEach((label) => {
    const index = indexOfLabel(analyticsHtml, label);
    assert.ok(index > cursor, `${label} must keep deterministic hierarchy`);
    cursor = index;
  });

  [
    "analyticsQuickInsightsSection",
    "analyticsRuntimeSection",
    "analyticsDiagnosticsSection",
    "analyticsPersistedSection",
  ].forEach((id) => {
    assert.match(analyticsHtml, new RegExp(`id="${id}"`));
  });

  assert.equal(
    (analyticsHtml.match(/<details class="advanced-settings">/g) || []).length,
    1,
    "phase-12 should keep exactly one persisted disclosure block in analytics",
  );
});

test("phase-12 analytics keeps quick insight and persisted contracts in expected blocks", () => {
  const analyticsHtml = readText("../partials/analytics_logs.html");
  const quickInsightsSection = extractSectionById(
    analyticsHtml,
    "analyticsQuickInsightsSection",
  );
  const runtimeSection = extractSectionById(
    analyticsHtml,
    "analyticsRuntimeSection",
  );
  const persistedDetails = extractAdvancedDetailsBySummary(
    analyticsHtml,
    "Expanded Context: Persisted State, History and Multi-Channel Comparison",
  );

  [
    "analyticsQuickInsightHint",
    "analyticsQuickFocusedChannel",
    "analyticsQuickRuntimeChip",
    "analyticsQuickPersistenceChip",
    "analyticsQuickHealthScore",
    "analyticsQuickHealthBandChip",
    "analyticsQuickIgnoredRate",
    "analyticsQuickMessagesPerMinute",
    "analyticsQuickTriggerRate",
    "analyticsQuickCost60m",
    "analyticsQuickErrors",
  ].forEach((id) => {
    assert.ok(
      quickInsightsSection.includes(`id="${id}"`),
      `${id} must stay in decision brief section`,
    );
  });

  ["ctxMode", "ctxUptime", "ctxLastEvent", "timelineBody"].forEach((id) => {
    assert.ok(
      runtimeSection.includes(`id="${id}"`),
      `${id} must stay in runtime/timeline section`,
    );
  });

  [
    "ctxPersistedGame",
    "ctxPersistedVibe",
    "ctxPersistedHint",
    "persistedHistoryItems",
    "persistedTimelineHint",
    "persistedChannelTimelineBody",
    "persistedChannelComparisonBody",
  ].forEach((id) => {
    assert.ok(
      persistedDetails.includes(`id="${id}"`),
      `${id} must stay in persisted disclosure section`,
    );
  });
});
