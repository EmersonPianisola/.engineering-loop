---
title: "Cloud Architecture — Real-Time Chat"
work_item: "spec-5-1-real-time-chat.md"
---

# Cloud Architecture: Real-Time Chat

## Infrastructure (Firebase — existing)

| Service | Role | Chat-Specific Config |
|---------|------|---------------------|
| Firestore | Message storage | `matches/{matchId}/messages` subcollection |
| Firebase Storage | Image hosting | `chat/{matchId}/{timestamp}-{random}.jpg` |
| Firestore (real-time) | Live streaming | onSnapshot on messages + typing |

## Data Storage

### Messages Collection
- Path: `matches/{matchId}/messages/{docId}`
- Fields: senderId, text, type, timestamp, read, participantIds
- Index: orderBy('timestamp', 'desc') — composite

### Typing Subcollection
- Path: `matches/{matchId}/typing/{userId}`
- Fields: isTyping, updatedAt
- TTL: 3 seconds (client-side check)

## Deployment

- No new services required — all Firebase infrastructure pre-existing
- Firestore rules already permit authenticated reads/writes
- Storage rules permit authenticated uploads

## Cost Estimate

- Firestore reads: ~500/day per active chat user (onSnapshot)
- Firestore writes: ~50/day per active chat user
- Storage uploads: ~10/day per active chat user
- Estimated impact: negligible at MVP scale (<100 MAU)
