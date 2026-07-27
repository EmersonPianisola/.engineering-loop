---
title: "Consolidated Architecture — Real-Time Chat"
work_item: "spec-5-1-real-time-chat.md"
---

# Consolidated Architecture: Real-Time Chat

## Cross-Artifact Consistency

- Requirements ↔ Cloud: All functional requirements mapped to Firebase services
- Requirements ↔ Solution: All FRs have component assignment
- Cloud ↔ Solution: Data paths consistent (matches/{matchId}/messages)

## Traceability

| FR | Cloud Service | Solution Component | Status |
|----|--------------|-------------------|--------|
| FR-1 | Firestore | ChatRoom.jsx | covered |
| FR-2 | Firestore onSnapshot | listenToMessages() | covered |
| FR-3 | Firestore | sendMessage() | covered |
| FR-4 | Storage + Firestore | uploadImage() | covered |
| FR-5 | Firestore | sendMessage() system type | covered |
| FR-6 | Firestore onSnapshot | listenToTyping() | covered |
| FR-7 | — | ChatRoom scroll logic | covered |
| FR-8 | — | ChatRoom unread badge | covered |
| FR-9 | LocalStorage | offline-queue.js | covered |
| FR-10 | Firestore | ChatRoom disabled state | covered |
| FR-11 | — | use-chat-rate-limit.js | covered |
| FR-12 | Firestore pagination | getMessages() | covered |
| FR-13 | Firestore batch | markMessagesRead() | covered |

## Findings

| Severity | Finding | Action |
|----------|---------|--------|
| medium | ChatRoom.css minimal (4 lines) — missing BEM styles for bubbles, typing indicator, input area | impl.code must expand CSS |
| low | No chat unit tests exist yet | test.unit must create chat.test.js |

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Reuse existing chat.js (359 lines) | Code already implements all required operations |
| Reuse existing ChatRoom.jsx (533 lines) | Code already implements all required UI patterns |
| Expand ChatRoom.css | Critical gap — component relies on class names not defined in CSS |
