#!/usr/bin/env bash
# new_adr.sh — scaffold the next-numbered ADR in a repo's decision log.
#
# Usage:
#   scripts/new_adr.sh "use postgres for billing"            # MADR (default)
#   scripts/new_adr.sh -f nygard "adopt trunk based dev"     # Nygard lightweight
#   scripts/new_adr.sh -d docs/decisions "title"             # force a log directory
#
# Behavior:
#   - Detects the ADR log directory (or uses -d), creating docs/adr/ if none exists.
#   - Computes the next zero-padded 4-digit id as max(existing ids)+1.
#   - Writes NNNN-kebab-title.md seeded from the chosen template.
#   - Prints the path of the created file.
#
# The template bodies are embedded so the script is self-contained once copied
# into a repo. Fill in every {…} placeholder before committing.

set -euo pipefail

FORMAT="madr"
DIR=""

while getopts "f:d:h" opt; do
  case "$opt" in
    f) FORMAT="$OPTARG" ;;
    d) DIR="$OPTARG" ;;
    h) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

if [ $# -lt 1 ]; then
  echo "error: provide a decision title, e.g. new_adr.sh \"use postgres for billing\"" >&2
  exit 2
fi
TITLE_RAW="$*"

# --- locate the log directory -------------------------------------------------
detect_dir() {
  if [ -n "$DIR" ]; then echo "$DIR"; return; fi
  if [ -f .adr-dir ]; then head -n1 .adr-dir | tr -d '[:space:]'; return; fi
  for c in docs/adr docs/decisions doc/adr adr architecture/decisions docs/architecture/decisions; do
    if [ -d "$c" ]; then echo "$c"; return; fi
  done
  # look for an existing NNNN-*.md anywhere and reuse its directory
  local found
  found=$(find . -type f -regextype posix-extended -regex '.*/[0-9]{3,4}-[^/]+\.md' 2>/dev/null | head -n1 || true)
  if [ -n "$found" ]; then dirname "$found"; return; fi
  echo "docs/adr"  # default; will be created
}

LOG_DIR="$(detect_dir)"
mkdir -p "$LOG_DIR"

# --- compute next id ----------------------------------------------------------
highest=0
while IFS= read -r f; do
  base="$(basename "$f")"
  num="${base%%-*}"
  if [[ "$num" =~ ^[0-9]+$ ]]; then
    n=$((10#$num))
    (( n > highest )) && highest=$n
  fi
done < <(find "$LOG_DIR" -maxdepth 1 -type f -name '[0-9]*-*.md' 2>/dev/null || true)

next=$((highest + 1))
ID="$(printf '%04d' "$next")"

# --- slug ---------------------------------------------------------------------
SLUG="$(echo "$TITLE_RAW" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
FILE="$LOG_DIR/${ID}-${SLUG}.md"

if [ -e "$FILE" ]; then
  echo "error: $FILE already exists" >&2
  exit 1
fi

TODAY="$(date +%Y-%m-%d)"
# Title Case for the human-readable heading
HEADING="$(echo "$TITLE_RAW" | awk '{for(i=1;i<=NF;i++){$i=toupper(substr($i,1,1)) substr($i,2)}}1')"

# --- write the template -------------------------------------------------------
if [ "$FORMAT" = "nygard" ]; then
  cat > "$FILE" <<EOF
# ${ID}. ${HEADING}

Date: ${TODAY}

## Status

Accepted

## Context

{What is the issue that motivates this decision? State the forces at play as facts.}

## Decision

We will {state the decision in active voice}.

## Consequences

{What becomes easier and what becomes harder. Include good, bad, and neutral outcomes.}
EOF
else
  cat > "$FILE" <<EOF
---
status: "accepted"
date: ${TODAY}
decision-makers: {who decided}
consulted:
informed:
---

# ${HEADING}

## Context and Problem Statement

{Two or three sentences of context and the problem. Name the components affected and
the constraints that bound the choice (scale, latency, team skills, deadlines).}

## Decision Drivers

* {driver 1}
* {driver 2}

## Considered Options

* {option 1}
* {option 2}

## Decision Outcome

Chosen option: "{option 1}", because {justification tied to a driver}.

### Consequences

* Good, because {positive consequence}
* Bad, because {cost you are accepting}

### Confirmation

{How will you confirm the code stays true to this decision? A test, lint rule, or review.}

## Pros and Cons of the Options

### {option 1}

* Good, because {argument}
* Bad, because {argument}

### {option 2}

* Good, because {argument}
* Bad, because {argument}

## More Information

{Related ADRs, links, revisit conditions.}
EOF
fi

echo "$FILE"
