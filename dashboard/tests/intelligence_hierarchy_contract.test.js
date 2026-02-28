import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function countMatches(text, pattern) {
  return (text.match(pattern) || []).length;
}

function extractSectionById(html, id) {
  return (
    html.match(
      new RegExp(`<section[^>]*id="${id}"[\\s\\S]*?<\\/section>`),
    )?.[0] || ""
  );
}

test("phase-10 intelligence panel keeps explicit operational hierarchy", () => {
  const intelligenceHtml = readText("../partials/intelligence_panel.html");

  const headingsInOrder = [
    "Tactical Coaching",
    "Post-Stream Report",
    "Semantic Memory",
    "Revenue Attribution",
  ];
  let cursor = -1;
  headingsInOrder.forEach((heading) => {
    const index = intelligenceHtml.indexOf(`>${heading}<`);
    assert.ok(index > cursor, `${heading} must keep deterministic hierarchy`);
    cursor = index;
  });

  assert.equal(
    countMatches(intelligenceHtml, /<hr\b/gi),
    0,
    "phase-10 should remove repeated hr separators in intelligence panel",
  );

  [
    "intCoachingRiskChip",
    "intPostStreamGenerateBtn",
    "intSemanticMemorySearchBtn",
    "intSemanticMemorySaveBtn",
    "intRevenueSimulateBtn",
  ].forEach((id) => {
    assert.equal(
      countMatches(intelligenceHtml, new RegExp(`id="${id}"`, "g")),
      1,
      `${id} must remain unique after hierarchy refactor`,
    );
  });
});

test("phase-10 moves non-live flows into progressive disclosure", () => {
  const intelligenceHtml = readText("../partials/intelligence_panel.html");
  const tacticalSection = extractSectionById(
    intelligenceHtml,
    "intelligenceTacticalCoachingBlock",
  );
  const detailsBlock =
    intelligenceHtml.match(
      /<details class="advanced-settings">[\s\S]*?<\/details>/,
    )?.[0] || "";

  assert.match(
    intelligenceHtml,
    /<summary>\s*Post-Live Intelligence Tools\s*<\/summary>/,
  );
  assert.ok(
    tacticalSection.includes('id="intCoachingRiskChip"'),
    "live coaching controls must stay visible in primary tactical block",
  );
  assert.ok(
    tacticalSection.includes('id="intCoachingAlerts"'),
    "tactical alerts must stay visible in primary tactical block",
  );

  [
    "intPostStreamGenerateBtn",
    "intSemanticMemorySearchBtn",
    "intSemanticMemorySaveBtn",
    "intRevenueSimulateBtn",
  ].forEach((id) => {
    assert.ok(
      detailsBlock.includes(`id="${id}"`),
      `${id} must be rendered inside progressive disclosure`,
    );
  });
});
