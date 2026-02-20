import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const distRoot = new URL("../dist", import.meta.url);
const sourceRoot = new URL("../src", import.meta.url);

const JS_GZIP_BUDGET = 350 * 1024;
const CSS_GZIP_BUDGET = 80 * 1024;

function fail(message) {
  console.error(`[check:pa] FAIL: ${message}`);
  process.exit(1);
}

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

const distDir = distRoot.pathname;
const srcDir = sourceRoot.pathname;

const distFiles = walk(distDir);
const jsFiles = distFiles.filter((f) => f.endsWith(".js"));
const cssFiles = distFiles.filter((f) => f.endsWith(".css"));

const totalJsGzip = jsFiles.reduce((sum, f) => sum + gzipSync(readFileSync(f)).length, 0);
const totalCssGzip = cssFiles.reduce((sum, f) => sum + gzipSync(readFileSync(f)).length, 0);

if (totalJsGzip > JS_GZIP_BUDGET) {
  fail(`JS gzip size budget exceeded: ${totalJsGzip} > ${JS_GZIP_BUDGET}`);
}
if (totalCssGzip > CSS_GZIP_BUDGET) {
  fail(`CSS gzip size budget exceeded: ${totalCssGzip} > ${CSS_GZIP_BUDGET}`);
}

const appTsx = readFileSync(join(srcDir, "App.tsx"), "utf8");
if (!appTsx.includes("ToastProvider")) {
  fail("a11y baseline check failed: ToastProvider missing (aria-live regression risk)");
}

const pages = ["DashboardPage.tsx", "RunJobPage.tsx", "ResultsPage.tsx"];
for (const page of pages) {
  const content = readFileSync(join(srcDir, "pages", page), "utf8");
  if (!content.includes("<h3>") && !content.includes("<h4>")) {
    fail(`a11y baseline check failed: heading missing in ${page}`);
  }
}

console.log("[check:pa] PASS");
console.log(`[check:pa] gzip(js)=${totalJsGzip} bytes, gzip(css)=${totalCssGzip} bytes`);
