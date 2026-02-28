import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const DASHBOARD_ROOT = fileURLToPath(new URL("../", import.meta.url));
const DASHBOARD_TEST_DIR_SEGMENT = `${path.sep}tests${path.sep}`;
const DASHBOARD_ROUTES_FILE = fileURLToPath(
  new URL("../../bot/dashboard_server_routes.py", import.meta.url),
);

function readText(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function resolveDashboardAsset(assetPath) {
  assert.match(
    assetPath,
    /^\/dashboard\//,
    `Asset path must stay under /dashboard: ${assetPath}`,
  );
  return path.join(DASHBOARD_ROOT, assetPath.replace(/^\/dashboard\//, ""));
}

function collectFiles(rootDir, extension, files = []) {
  const entries = readdirSync(rootDir, { withFileTypes: true });
  entries.forEach((entry) => {
    const absolutePath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      collectFiles(absolutePath, extension, files);
      return;
    }
    if (entry.isFile() && absolutePath.endsWith(extension)) {
      files.push(absolutePath);
    }
  });
  return files;
}

function extractModuleSpecifiers(source) {
  const specifiers = [];
  const patterns = [
    /\bimport\s+(?:[^'"]*?\sfrom\s*)?["']([^"']+)["']/g,
    /\bexport\s+(?:\*|\{[^}]*\})\s+from\s+["']([^"']+)["']/g,
    /\bimport\(\s*["']([^"']+)["']\s*\)/g,
  ];

  patterns.forEach((pattern) => {
    for (const match of source.matchAll(pattern)) {
      specifiers.push(match[1]);
    }
  });

  return specifiers;
}

function resolveImportTarget(importerPath, specifier) {
  const baseTarget = path.resolve(path.dirname(importerPath), specifier);
  const candidates = [baseTarget];
  if (!path.extname(baseTarget)) {
    candidates.push(`${baseTarget}.js`);
    candidates.push(`${baseTarget}.mjs`);
    candidates.push(`${baseTarget}.cjs`);
    candidates.push(path.join(baseTarget, "index.js"));
  }
  return candidates.find((candidate) => existsSync(candidate));
}

test("dashboard shell asset references resolve to local files", () => {
  const indexHtml = readText("../index.html");
  const routesSource = readFileSync(DASHBOARD_ROUTES_FILE, "utf8");
  const dynamicDashboardAssets = new Set(["/dashboard/config.js"]);
  const stylesheetHrefs = [
    ...indexHtml.matchAll(/<link\s+rel="stylesheet"\s+href="([^"]+)"/g),
  ].map((match) => match[1]);
  const scriptSrcs = [...indexHtml.matchAll(/<script[^>]+src="([^"]+)"/g)].map(
    (match) => match[1],
  );
  const partialUrls = [...indexHtml.matchAll(/url:\s*"([^"]+\.html)"/g)].map(
    (match) => match[1],
  );
  const runtimeModuleSrcs = [
    ...indexHtml.matchAll(/script\.src\s*=\s*"([^"]+)"/g),
  ].map((match) => match[1]);

  const referencedAssets = [
    ...stylesheetHrefs,
    ...scriptSrcs,
    ...partialUrls,
    ...runtimeModuleSrcs,
  ];
  assert.ok(referencedAssets.length > 0, "No dashboard assets were discovered");

  referencedAssets.forEach((assetPath) => {
    if (dynamicDashboardAssets.has(assetPath)) {
      assert.match(
        routesSource,
        new RegExp(`["']${escapeRegex(assetPath)}["']`),
        `Missing dynamic route for dashboard asset: ${assetPath}`,
      );
      return;
    }

    const absolutePath = resolveDashboardAsset(assetPath);
    assert.ok(
      existsSync(absolutePath),
      `Missing dashboard asset: ${assetPath}`,
    );
  });
});

test("dashboard source js imports resolve without broken local paths", () => {
  const jsFiles = collectFiles(DASHBOARD_ROOT, ".js").filter(
    (filePath) => !filePath.includes(DASHBOARD_TEST_DIR_SEGMENT),
  );
  const missingImports = [];

  jsFiles.forEach((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const localSpecifiers = extractModuleSpecifiers(source).filter(
      (specifier) => specifier.startsWith("./") || specifier.startsWith("../"),
    );

    localSpecifiers.forEach((specifier) => {
      const resolvedTarget = resolveImportTarget(filePath, specifier);
      if (!resolvedTarget) {
        missingImports.push(
          `${path.relative(DASHBOARD_ROOT, filePath)} -> ${specifier}`,
        );
      }
    });
  });

  assert.deepEqual(
    missingImports,
    [],
    `Broken dashboard imports:\n${missingImports.join("\n")}`,
  );
});

test("dashboard css local imports resolve", () => {
  const cssFiles = collectFiles(path.join(DASHBOARD_ROOT, "styles"), ".css");
  const missingImports = [];

  cssFiles.forEach((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const importMatches = source.matchAll(
      /@import\s+(?:url\()?['"]([^'")]+)['"]\)?/g,
    );

    for (const match of importMatches) {
      const importPath = match[1];
      if (/^https?:\/\//.test(importPath)) {
        continue;
      }

      let resolvedTarget = "";
      if (importPath.startsWith("/dashboard/")) {
        resolvedTarget = resolveDashboardAsset(importPath);
      } else if (importPath.startsWith("./") || importPath.startsWith("../")) {
        resolvedTarget = path.resolve(path.dirname(filePath), importPath);
      } else {
        continue;
      }

      if (!existsSync(resolvedTarget)) {
        missingImports.push(
          `${path.relative(DASHBOARD_ROOT, filePath)} -> ${importPath}`,
        );
      }
    }
  });

  assert.deepEqual(
    missingImports,
    [],
    `Broken dashboard css imports:\n${missingImports.join("\n")}`,
  );
});
