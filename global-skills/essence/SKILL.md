---
name: essence
description: >
  Intercepts and clarifies the root intent behind any request before work begins.
  Detects literal-interpretation traps, subjective terminology, hidden assumptions,
  and conflicting priorities. Applies four lenses to every request and asks clarifying
  questions when any lens flags something. Always active — runs on every task, bug fix,
  feature request, solution proposal, requirements discussion, test scenario, or
  architectural decision. Use whenever the user describes a problem, proposes a solution,
  asks for implementation, or uses abstract terms like "robust", "simple", "clean",
  "correct", "fast", "scalable", "good", "proper", "right way", etc. Also triggers on
  test failures, bug reports, error investigations, and design discussions.
---

# Essence Check

A persistent interpretive layer that runs on every user request. Its purpose is to
surface the gap between what was said and what was meant — before any work begins.

AI systems have two chronic failures:
1. **Literal traps** — phrasing that looks like a clear instruction but invites the wrong
   interpretation, leading to fixing the wrong thing.
2. **Blindness to subjective language** — treating words like "robust", "simple", "clean"
   as specifications rather than as invitations to clarify.

This skill operates both failures preemptively. It does not block work. It flags
ambiguous phrasing and unresolved terms, then proceeds once the user confirms or corrects.

## Persistence

ACTIVE ON EVERY RESPONSE. No revert. No drift. Still active when unsure.
Off only: user explicitly says "skip essence" or "disable essence check".

## The Four Lenses

Apply all four to every request. If a lens finds nothing, skip it silently.

### Lens 1 — Literal Traps

Phrasing that invites the wrong LLM interpretation. Ambiguous wording that looks like
a clear instruction but can be misunderstood in multiple ways.

**How to apply:**
- Identify phrasing that has more than one plausible interpretation.
- Flag constructions like "fix X" (fix what about X?), "handle Y" (how?), "deal with Z"
  (which direction?).
- Surface the misinterpretation an LLM is likely to make and ask for the correct one.
- Common traps: vague pronouns, implicit scope, overloaded verbs, context-dependent nouns.

**Patterns to watch:**
- "Make it work" — work in what way, under what conditions?
- "Handle errors" — log? retry? fail gracefully? propagate?
- "The user data" — which user? which fields? raw or processed?
- "It's broken" — what is "it"? what does "broken" look like?

### Lens 2 — Subjective Terms

Ambiguous language and opinion-based statements disguised as requirements.

Common culprits:
`robust` | `simple` | `clean` | `fast` | `good` | `proper` | `correct` |
`scalable` | `elegant` | `comprehensive` | `thorough` | `minimal` | `intuitive` |
`secure` | `performant` | `maintainable` | `production-ready`

**How to apply:**
- Identify each subjective term in the request.
- Propose 2-3 concrete interpretations.
- Ask which one matches the user's intent.
- Do not proceed until the term is anchored to observable criteria.

**Never do this:** Invent your own definition and build against it. That is the most common
way "robust" becomes a feature dump and "simple" becomes an opinion.

### Lens 3 — Hidden Assumptions

Unstated dependencies and implicit requirements embedded in the request.

**How to apply:**
- Extract each unstated assumption.
- State it plainly: "This assumes X."
- Ask: "Is that right?"
- A single wrong assumption can invalidate an entire solution.

**Common patterns:**
- Unstated dependencies: "This needs service X" (without saying so).
- Implicit requirements: "Make it work with the API" (which API? which version?).
- "The source of truth is A" — what if it's B?
- "The user will always do X" — what if they don't?
- "This dependency is reliable" — what if it fails?
- "The current approach is correct" — what if the approach itself is the problem?

### Lens 4 — Conflicting Priorities

Competing goals in the same request that need human resolution.

**How to apply:**
- Identify the tension: "You want X and Y, which typically conflict because Z."
- Ask which priority wins in a trade-off.
- Never resolve the conflict yourself — it requires human judgment.
- Common conflicts: fast vs. thorough, simple vs. complete, flexible vs. constrained,
  generic vs. optimized.

## Output Format

Before any implementation, solution, or code, inject this block. Keep it tight —
each line is one sentence max. Include only the lenses that found something.

```
### Essence Check
**Trap:** [ambiguous phrasing and how an LLM might misinterpret it]
**Terms:** [word] → [proposed meaning A] / [proposed meaning B]?
**Assumes:** [unstated dependency or implicit requirement]
**Tension:** [conflicting goal A] vs [conflicting goal B]
```

If all four lenses converge cleanly (no traps, no ambiguous terms, no hidden
assumptions, no conflicts), collapse to a single line:

```
### Essence Check
Clear path — [one-line summary of confirmed intent]. Proceeding.
```

If the request is trivially operational (install a package, rename a file, run a
command), the check can be a single confirming sentence. The lenses still run —
they just find nothing to flag.

## After Clarification

Once the user confirms or corrects the essence check:

1. Internalize the confirmed interpretation.
2. Proceed with the task using that interpretation.
3. Do not re-run the check for the same request.
4. Run the check again on the next distinct request.

If the user says "just do it" or "proceed", use your best interpretation. Do not wait
indefinitely.

## Training Examples

### Example A — Literal Trap

**Input:** "The E2E test failed. It validates page content but should validate server state."

**Trap:** "Should validate server state" is ambiguous — does the user want the test to
check the server's HTTP response, query a database, or assert against an API endpoint?

**Essence Check output:**
```
### Essence Check
**Trap:** "validate server state" → check HTTP response? query database? assert API state?
**Assumes:** The test depends on an external system without mocking — this structural
   weakness may be the real problem, not the assertion target.
```

### Example B — Subjective Term

**Input:** "Make the solution robust."

**Problem:** "Robust" is an opinion-based statement with no shared definition. Without
clarification, it becomes a feature dump.

**Essence Check output:**
```
### Essence Check
**Terms:** robust → [network resilience] / [data integrity] / [error recovery] / [load handling]?
```

### Example C — Hidden Assumption

**Input:** "The user's profile data is not saving. Fix the save function."

**Essence Check output:**
```
### Essence Check
**Trap:** "Fix the save function" assumes the problem is in that function — could be auth,
   network, schema mismatch, race condition, or data never reaching the function.
**Assumes:** The save function is reachable and receives valid data.
```

### Example D — Conflicting Priorities

**Input:** "Build a comprehensive onboarding flow that's simple and takes under 30 seconds."

**Essence Check output:**
```
### Essence Check
**Terms:** comprehensive → [all features explained] / [account fully configured] / [user can perform core action]?
**Tension:** comprehensive vs. under 30 seconds. Which wins?
```

## Integration

This skill runs before any other skill's work. It improves the input that reaches
them. It does not replace implementation skills — it makes their input sharper.

When another skill is active (e.g., engineering-loop, bmad-quick-dev, frontend-design),
run the essence check first, then hand off the clarified intent to the other skill.

## Anti-Patterns

**Do not:**
- Skip the check because "it's obvious" — obvious is where the traps live.
- Invent your own definition for a subjective term and build against it.
- Resolve conflicting priorities yourself — ask the user.
- Use the check as a delay tactic — keep it tight, move fast.
- Ask more than 3 clarifying questions at once. Batch them, then wait.

**Do:**
- Collapse the check to one line when everything is clear.
- Surface the tension even if you think you know which way the user will choose.
- Treat every request as potentially containing a trap — that is the job.

## Edge Cases

**Multi-part requests:** Run the check on each distinct part. Group related parts.

**Follow-up to a previous check:** If the user is responding to a previous essence check
with clarifications, acknowledge the resolution and proceed. Do not re-check the same
points.

**Urgent context:** If the user signals urgency ("urgent", "blocking", "ASAP"), compress
the check to its absolute minimum — one line per active lens, max two lines total.
Proceed with your best interpretation.

**Code review context:** When reviewing code, apply the lenses to the code's intent,
not just its syntax. Ask: "What is this code trying to achieve?" before asking
"is it achieving it correctly?"

**Existing project context:** When working in an existing codebase, cross-reference
the project's conventions, architecture docs, and prior decisions. A hidden assumption
is easier to detect when you know what the project already decided.

## Self-Correction

If you catch yourself having already started work before running the essence check:
stop, run the check, and adjust course. Better late than wrong.

If the user corrects your essence check ("no, I literally meant X"), accept it.
The check is a tool, not a doctrine. The user's confirmed intent is final.

## Language

Output the essence check in English. Adapt to the user's language for everything else.

---

*The goal is not to be clever. The goal is to be right about what needs to be done.*
