# .ff/ — FF Workspace

This directory is the working directory for the FF (Fail Fast) protocol.

## Files

- `state.json` — Current FF session state. Updated after each block completion.
- `lessons.json` — Accumulated lessons from failed or retried tasks. Append-only.
- `README.md` — This file.

## Usage

The FF protocol creates and manages this directory automatically. Do not edit files manually unless debugging a failed session.
