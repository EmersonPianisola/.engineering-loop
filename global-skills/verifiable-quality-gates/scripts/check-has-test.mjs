#!/usr/bin/env node
/**
 * check-has-test — the COVERAGE gate (reference implementation).
 *
 * Proves that every automated check has a committed test that actually EXECS it. Pairs with
 * verify-check-discrimination.mjs (the mutation gate, which proves those tests DISCRIMINATE).
 *
 * Dependency-free (Node built-ins only) and vendor-neutral: it does not assume a particular test
 * runner. It credits a check when some test file both (a) references the check's file name and
 * (b) contains an exec indicator (it spawns a child process). That heuristic is intentionally
 * simple; a production version may prefer an AST pass that confirms the check's path is passed to
 * the exec call from a local binding (fewer false credits). See SKILL.md.
 *
 * Config (JSON; path via argv[2] or ./verifiable-gates.config.json):
 *   {
 *     "checksDir":    "scripts/ci",              // where the checks live
 *     "checkPattern": "^check-.*\\.(mjs|js)$",   // which files there are checks (basename regex)
 *     "testsDir":     "test/checks",             // where the check-tests live (searched recursively)
 *     "testPattern":  "\\.(test|spec)\\.(mjs|js|ts|tsx)$",
 *     "allowlist":    "scripts/ci/check-test-allowlist.json"  // shrink-only list of pre-existing untested checks
 *   }
 *
 * Exit 0 = every non-allowlisted check has a crediting test. Non-zero = missing input (fail closed)
 * or one or more untested checks.
 */
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, resolve, basename } from "node:path";

function die(msg) {
  console.error(`[check-has-test] FAIL — ${msg}`);
  process.exit(1);
}

// --- config (fail closed on anything missing) --------------------------------
const configPath = resolve(process.argv[2] ?? "verifiable-gates.config.json");
if (!existsSync(configPath)) die(`config not found: ${configPath}`);
let cfg;
try {
  cfg = JSON.parse(readFileSync(configPath, "utf8"));
} catch (e) {
  die(`config is not valid JSON (${e.message})`);
}
for (const k of ["checksDir", "checkPattern", "testsDir", "testPattern", "allowlist"]) {
  if (!cfg[k]) die(`config is missing "${k}"`);
}

const checksDir = resolve(cfg.checksDir);
const testsDir = resolve(cfg.testsDir);
if (!existsSync(checksDir)) die(`checksDir does not exist: ${checksDir}`);
if (!existsSync(testsDir)) die(`testsDir does not exist: ${testsDir}`);

const checkRe = new RegExp(cfg.checkPattern);
const testRe = new RegExp(cfg.testPattern);

let allowlist;
try {
  allowlist = new Set(JSON.parse(readFileSync(resolve(cfg.allowlist), "utf8")));
} catch (e) {
  die(`allowlist not found or invalid JSON at ${cfg.allowlist} (${e.message})`);
}

// --- enumerate checks --------------------------------------------------------
const checks = readdirSync(checksDir).filter((f) => checkRe.test(f));
if (checks.length === 0) die(`no checks matched ${cfg.checkPattern} in ${checksDir} (zero-scan)`);

// --- read every test file, collect exec-credited check names -----------------
function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (testRe.test(name)) out.push(p);
  }
  return out;
}
const testFiles = walk(testsDir);
const EXEC = /\b(execFileSync|execSync|spawnSync|execFile|spawn|exec)\s*\(/;

const credited = new Set();
for (const tf of testFiles) {
  const src = readFileSync(tf, "utf8");
  if (!EXEC.test(src)) continue; // a test that spawns nothing cannot exec a check
  for (const c of checks) if (src.includes(c)) credited.add(c);
}

// --- verdict -----------------------------------------------------------------
const required = checks.filter((c) => !allowlist.has(c));
const untested = required.filter((c) => !credited.has(c));

if (untested.length) {
  console.error(
    `[check-has-test] FAIL — ${untested.length} check(s) have no committed test that execs them:`
  );
  for (const c of untested) console.error(`  • ${c}`);
  console.error(
    `\nAdd a test that spawns the real check and asserts its exit code (see check-test-patterns.md),\n` +
      `or — only for a pre-existing check — add it to ${cfg.allowlist} (shrink-only; burn it down).`
  );
  process.exit(1);
}

// Report stale allowlist entries (a check on the list that now HAS a test, or no longer exists).
const stale = [...allowlist].filter((c) => credited.has(c) || !checks.includes(c));
console.log(
  `[check-has-test] OK — ${checks.length} checks scanned, ${required.length} required, ` +
    `${credited.size} credited by a committed exec-test, ${allowlist.size} on the shrink-only allowlist.`
);
if (stale.length) {
  console.log(
    `  note: ${stale.length} allowlist entry(ies) can be REMOVED (now tested, or the check is gone): ${stale.join(", ")}`
  );
}
process.exit(0);
