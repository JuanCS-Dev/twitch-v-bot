import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function countMatches(text, pattern) {
  return (text.match(pattern) || []).length;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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
        `<details class="advanced-settings">[\\s\\S]*?<summary>\\s*${summaryLabel.replace(
          /[.*+?^${}()|[\]\\]/g,
          "\\$&",
        )}\\s*<\\/summary>[\\s\\S]*?<\\/details>`,
      ),
    )?.[0] || ""
  );
}

test("phase-11 control plane exposes governance sections with progressive disclosure", () => {
  const controlPlaneHtml = readText("../partials/control_plane.html");

  const orderedLabels = [
    "Operational Control",
    "Channel Directives",
    "Identity + Agent Notes",
    "Goals Scheduler",
    "Advanced Budget, Cooldowns and Webhooks",
  ];
  let cursor = -1;
  orderedLabels.forEach((label) => {
    const index = indexOfLabel(controlPlaneHtml, label);
    assert.ok(index > cursor, `${label} must keep deterministic hierarchy`);
    cursor = index;
  });

  assert.equal(
    countMatches(controlPlaneHtml, /<details class="advanced-settings">/g),
    2,
    "phase-11 should keep exactly two disclosure blocks in control plane",
  );

  [
    "cpOperationalControlSection",
    "cpChannelDirectivesSection",
    "cpGoalsSchedulerSection",
  ].forEach((id) => {
    assert.match(controlPlaneHtml, new RegExp(`id="${id}"`));
  });
});

test("phase-11 control plane keeps ID contracts in the expected governance blocks", () => {
  const controlPlaneHtml = readText("../partials/control_plane.html");
  const operationalSection = extractSectionById(
    controlPlaneHtml,
    "cpOperationalControlSection",
  );
  const directivesSection = extractSectionById(
    controlPlaneHtml,
    "cpChannelDirectivesSection",
  );
  const goalsSection = extractSectionById(
    controlPlaneHtml,
    "cpGoalsSchedulerSection",
  );
  const identityDetails = extractAdvancedDetailsBySummary(
    controlPlaneHtml,
    "Identity + Agent Notes",
  );
  const advancedDetails = extractAdvancedDetailsBySummary(
    controlPlaneHtml,
    "Advanced Budget, Cooldowns and Webhooks",
  );

  [
    "cpAgentStatusChip",
    "cpAgentStatusHint",
    "cpSuspendBtn",
    "cpResumeBtn",
  ].forEach((id) => {
    assert.ok(
      operationalSection.includes(`id="${id}"`),
      `${id} must stay in operational control section`,
    );
  });

  [
    "cpChannelConfigStatusChip",
    "cpLoadChannelConfigBtn",
    "cpSaveChannelConfigBtn",
    "cpChannelConfigHint",
    "cpChannelConfigId",
    "cpChannelTemperature",
    "cpChannelTopP",
    "cpChannelAgentPaused",
  ].forEach((id) => {
    assert.ok(
      directivesSection.includes(`id="${id}"`),
      `${id} must stay in channel directives section`,
    );
  });

  [
    "cpChannelIdentityStatusChip",
    "cpAgentNotesStatusChip",
    "cpChannelIdentityHint",
    "cpAgentNotesHint",
    "cpChannelPersonaName",
    "cpChannelTone",
    "cpChannelEmoteVocab",
    "cpChannelLore",
    "cpAgentNotes",
  ].forEach((id) => {
    assert.ok(
      identityDetails.includes(`id="${id}"`),
      `${id} must stay in identity and notes disclosure`,
    );
  });

  [
    "cpAutonomyEnabled",
    "cpHeartbeatInterval",
    "cpMinCooldown",
    "cpActionIgnoreAfter",
    "cpBudget10m",
    "cpBudget60m",
    "cpBudgetDaily",
    "cpWebhookUrl",
    "cpWebhookSecret",
    "cpWebhookActive",
    "cpWebhookTestBtn",
  ].forEach((id) => {
    assert.ok(
      advancedDetails.includes(`id="${id}"`),
      `${id} must stay in advanced budget/cooldown/webhook disclosure`,
    );
  });

  [
    "cpGoalsList",
    "cpAddGoalBtn",
    "cpSaveBtn",
    "cpReloadBtn",
    "cpFeedbackMsg",
  ].forEach((id) => {
    assert.equal(
      countMatches(controlPlaneHtml, new RegExp(`id="${id}"`, "g")),
      1,
      `${id} must remain unique after control plane refactor`,
    );
  });

  assert.ok(goalsSection.includes('id="cpGoalsList"'));
});
