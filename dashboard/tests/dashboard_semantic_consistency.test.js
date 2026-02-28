import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("dashboard shell keeps english locale and primary tab labels", () => {
  const indexHtml = readText("../index.html");

  assert.match(indexHtml, /<html lang="en">/i);
  [
    "Operation",
    "Intelligence",
    "Clips & Vision",
    "Analytics",
    "Configuration",
  ].forEach((label) => {
    assert.match(indexHtml, new RegExp(`>\\s*${escapeRegex(label)}\\s*<`));
  });
});

test("operational ui copy uses english while keeping prompt fallback in portuguese", () => {
  const channelControlView = readText("../features/channel-control/view.js");
  const controlPlaneController = readText(
    "../features/control-plane/controller.js",
  );
  const controlPlaneView = readText("../features/control-plane/view.js");

  assert.match(
    channelControlView,
    /Observability, context and persisted history now follow #/,
  );
  assert.doesNotMatch(
    channelControlView,
    /Observability, contexto e histórico persistido seguem #/i,
  );

  assert.match(controlPlaneController, /Control plane synced\./);
  assert.doesNotMatch(controlPlaneController, /sincronizado/i);

  assert.match(controlPlaneView, /since \$\{autonomy\.suspended_at\}/);
  assert.doesNotMatch(controlPlaneView, / desde /);

  // Prompt text can remain localized for national streamer rollout.
  assert.ok(controlPlaneView.includes("`Objetivo ${index + 1}.`"));
});
