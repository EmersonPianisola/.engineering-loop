#!/usr/bin/env node
/**
 * verify-check-discrimination — the MUTATION gate (reference implementation).
 *
 * For each check that is expected to have a test, replace the check with a no-op that always
 * passes, run that check's test(s), and REQUIRE them to FAIL. A test that still passes against a
 * do-nothing check asserts nothing about detection — it is vacuous — and this gate blocks the
 * merge. Pairs with check-has-test.mjs (the coverage gate). See references/mutation-gate.md.
 *
 * Dependency-free (Node built-ins) and vendor-neutral. It shells out to a configurable test
 * command so it works with any runner that accepts file paths and exits non-zero on failure.
 * The reference no-op stub assumes Node checks (see NOOP); adapt it if your checks are in another
 * language.
 *
 * Config (JSON; path via argv[2] or ./verifiable-gates.config.json) — same keys as
 * check-has-test.mjs, plus:
 *   "testCommand": ["node", "--test"]   // test file paths are appended to this argv
 *
 * Exit 0 = every check's test fails when its check is a no-op (all discriminate).
 * Non-zero = a vacuous test was found, or a fail-closed condition (missing input, unmapped check,
 * runner could not start).
 *
 * SAFETY: this mutates check files on disk. It restores every one in a `finally`. In CI this runs
 * on an ephemeral checkout; if a local run is hard-killed mid-mutation, restore with your VCS
 * (e.g. re-checkout the checks directory).
 */
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

function die(msg) {
  console.error(`[verify-check-discrimination] FAIL — ${msg}`);
  process.exit(1);
}

const NOOP = "#!/usr/bin/env node\n// temporarily stubbed by the discrimination gate\nprocess.exit(0);\n";

// --- config (fail closed) ----------------------------------------------------
const configPath = resolve(process.argv[2] ?? "verifiable-gates.config.json");
if (!existsSync(configPath)) die(`config not found: ${configPath}`);
let cfg;
try {
  cfg = JSON.parse(readFileSync(configPath, "utf8"));
} catch (e) {
  die(`config is not valid JSON (${e.message})`);
}
for (const k of ["checksDir", "checkPattern", "testsDir", "testPattern", "allowlist", "testCommand"]) {
  if (!cfg[k]) die(`config is missing "${k}"`);
}
if (!Array.isArray(cfg.testCommand) || cfg.testCommand.length === 0) {
  die(`"testCommand" must be a non-empty argv array, e.g. ["node","--test"]`);
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

// --- enumerate + map checks to their crediting test files --------------------
const checks = readdirSync(checksDir).filter((f) => checkRe.test(f));
const required = checks.filter((c) => !allowlist.has(c));
if (required.length === 0) {
  console.log("[verify-check-discrimination] OK — no non-allowlisted checks to mutate (nothing to do).");
  process.exit(0);
}

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (testRe.test(name)) out.push(p);
  }
  return out;
}
const EXEC = /\b(execFileSync|execSync|spawnSync|execFile|spawn|exec)\s*\(/;
const testFiles = walk(testsDir).filter((tf) => EXEC.test(readFileSync(tf, "utf8")));

const mapped = new Map(); // check basename -> [test file paths]
for (const c of required) {
  const files = testFiles.filter((tf) => readFileSync(tf, "utf8").includes(c));
  if (files.length === 0) die(`required check has no test mapped to it: ${c} (coverage gate should have caught this)`);
  mapped.set(c, files);
}

// --- mutate one check at a time; its test(s) MUST fail -----------------------
const backups = new Map(); // path -> original source
const vacuous = [];
try {
  for (const c of required) {
    const checkPath = join(checksDir, c);
    if (!backups.has(checkPath)) backups.set(checkPath, readFileSync(checkPath, "utf8"));

    writeFileSync(checkPath, NOOP); // neutralize the check
    const files = mapped.get(c);
    const res = spawnSync(cfg.testCommand[0], [...cfg.testCommand.slice(1), ...files], {
      stdio: "pipe",
      encoding: "utf8",
    });
    writeFileSync(checkPath, backups.get(checkPath)); // restore immediately so later runs see the real others

    if (res.error) die(`could not launch test runner "${cfg.testCommand.join(" ")}": ${res.error.message}`);
    if (res.status === 0) vacuous.push(c); // tests PASSED against a no-op → vacuous
  }
} finally {
  // Defensive sweep: restore anything a mid-loop crash left stubbed.
  for (const [p, src] of backups) {
    try {
      if (readFileSync(p, "utf8") === NOOP) writeFileSync(p, src);
    } catch {
      /* best effort; VCS is the backstop */
    }
  }
}

// --- verdict -----------------------------------------------------------------
if (vacuous.length) {
  console.error(
    `[verify-check-discrimination] FAIL — ${vacuous.length} check(s) have a VACUOUS test ` +
      `(it still passes when the check is a no-op):`
  );
  for (const c of vacuous) console.error(`  • ${c}`);
  console.error(
    `\nEach listed test asserts nothing tied to its check's detection, so a broken check would ship\n` +
      `green. Add a fixture that reproduces the real violation and asserts a non-zero exit ` +
      `(see check-test-patterns.md).`
  );
  process.exit(1);
}

console.log(
  `[verify-check-discrimination] OK — ${required.length} check(s) mutated; ` +
    `each FAILS when its check is a no-op (all genuinely discriminate).`
);
process.exit(0);
