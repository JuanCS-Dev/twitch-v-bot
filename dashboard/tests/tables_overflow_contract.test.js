import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";

function countMatches(text, matcher) {
  return (text.match(matcher) || []).length;
}

test("table-wrap keeps horizontal overflow contract for dashboard tables", () => {
  const componentsCss = readFileSync(
    new URL("../styles/components.css", import.meta.url),
    "utf8",
  );
  assert.match(
    componentsCss,
    /\.table-wrap\s*\{[\s\S]*overflow-x:\s*auto;[\s\S]*\}/,
  );
});

test("every table in partials is wrapped with table-wrap", () => {
  const partialsDir = new URL("../partials", import.meta.url);
  const partialFileNames = readdirSync(partialsDir)
    .filter((fileName) => fileName.endsWith(".html"))
    .sort();

  partialFileNames.forEach((fileName) => {
    const partialText = readFileSync(
      new URL(`../partials/${fileName}`, import.meta.url),
      "utf8",
    );
    const tableCount = countMatches(partialText, /<table\b/gi);
    if (tableCount === 0) {
      return;
    }
    const wrappedTableCount = countMatches(partialText, /class="table-wrap"/gi);
    assert.equal(
      wrappedTableCount,
      tableCount,
      `${fileName} must wrap each <table> with .table-wrap`,
    );
  });
});
