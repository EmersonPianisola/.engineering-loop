---
title: "Blueprint — Real-Time Chat (Spec 5.1)"
work_item: "spec-5-1-real-time-chat.md"
---

# Blueprint: Real-Time Chat

## Existing Code (Validated)

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `src/lib/chat.js` | 359 | conformant | All operations per spec implemented |
| `src/pages/ChatRoom.jsx` | 533 | conformant | All UI patterns per spec implemented |
| `src/pages/ChatRoom.css` | 4 | GAP | Only basic layout — missing bubble, typing, input styles |
| `src/lib/offline-queue.js` | — | conformant | Offline queuing pre-existing |
| `src/lib/use-chat-rate-limit.js` | 25 | conformant | Rate limiting pre-existing |

## Tasks

### Task 1: Expand ChatRoom.css (CRITICAL GAP)
**File:** `src/pages/ChatRoom.css`

Expand from 4 lines to full BEM stylesheet covering:
- `.chat-bubble--own` — rust background (`var(--color-primary)`), white text, right-aligned, border-radius
- `.chat-bubble--other` — dark card (`var(--color-card)`), text, left-aligned, border-radius
- `.chat-bubble--system` — centered, smaller font, muted color, italic
- `.typing-indicator` — 3 animated dots with opacity pulse
- `.chat-room__input-area` — fixed bottom, textarea + send button
- `.chat-room__unread-badge` — floating badge
- `.chat-room__offline-banner` — offline indicator
- `.chat-room__cancelled-badge` — cancelled state badge
- `.chat-room__dialog` — cancel match dialog overlay
- `.chat-room__load-older` — pagination button
- Responsive adjustments

### Task 2: Create Unit Tests
**File:** `src/__tests__/chat.test.js`

Test suite covering:
- `sendMessage()` — writes correct doc, rejects empty, truncates >2000, handles offline
- `listenToMessages()` — real-time streaming, error fallback
- `markMessagesRead()` — batch updates, skip own messages
- `sendTypingStatus()` — writes typing doc
- `listenToTyping()` — filters by 3s TTL
- `uploadImage()` — validates type, validates size, returns URL
- `getMessages()` — pagination, missing index fallback
- `formatMessagePreview()` — truncation, image type
- `formatRelativeTime()` — seconds/min/hours/days

### Execution Order

1. Task 1: Expand CSS (no dependencies)
2. Task 2: Create tests (depends on chat.js being stable — it is)

## Interface Contracts

All interfaces already defined in existing `chat.js` exports. No changes needed.
