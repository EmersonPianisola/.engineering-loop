---
title: "Requirements — Real-Time Chat (Spec 5.1)"
work_item: "spec-5-1-real-time-chat.md"
---

# Requirements: Real-Time Chat

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Chat room opens when match is accepted | critical |
| FR-2 | Real-time message streaming via Firestore onSnapshot | critical |
| FR-3 | Text messages (max 2000 chars) | critical |
| FR-4 | Image upload (JPG/PNG/GIF, max 5MB) | high |
| FR-5 | System messages for match events | critical |
| FR-6 | Typing indicator (3s expiry) | medium |
| FR-7 | Auto-scroll to bottom | medium |
| FR-8 | Unread badge when scrolled up | medium |
| FR-9 | Offline message queue (LocalStorage) | high |
| FR-10 | Read-only mode for cancelled matches | high |
| FR-11 | Rate limiting (30 messages/60s per match) | medium |
| FR-12 | Message pagination (load older) | medium |
| FR-13 | Mark messages as read | high |

## Volumetry

- Messages per chat: 0-500 typical, unbounded
- Messages per second: 0.5-2 peak
- Image size: 5MB max
- Typing events: 1-5 per second per user

## Scalability

- Firestore onSnapshot: automatic, no scaling needed
- Storage: Firebase Storage handles image storage
- Offline queue: LocalStorage capped at 100 messages

## Observability

- Firebase error logging via `logFirebaseError()`
- Analytics events: `CHAT_STARTED`
- Error banners for user-facing errors

## Security

- Firestore rules: authenticated users only
- Messages stored in `matches/{matchId}/messages` — accessible only to match participants
- Images stored in `chat/{matchId}/` — authenticated upload only
