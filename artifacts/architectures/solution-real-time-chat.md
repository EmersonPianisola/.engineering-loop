---
title: "Solution Architecture — Real-Time Chat"
work_item: "spec-5-1-real-time-chat.md"
---

# Solution Architecture: Real-Time Chat

## Component Design

### Data Layer (`src/lib/chat.js`)
- Firestore operations for messages, typing, and read receipts
- Firebase Storage integration for images
- Offline queue integration via `offline-queue.js`
- Error handling via `error-handler.js`

### UI Layer (`src/pages/ChatRoom.jsx`)
- ChatRoom: container component with message list, input, typing indicator
- ChatBubble: message rendering (text/image/system)
- TypingIndicator: animated dots component
- Inline cancel match dialog
- Report dialog integration

### Cross-Cutting
- Rate limiting: `use-chat-rate-limit.js` (30 msg/60s)
- Offline support: `offline-queue.js` (LocalStorage queue)
- Auth context: `AuthContext.jsx`
- Analytics: `analytics.js` (CHAT_STARTED event)

## Data Model

```js
// Message document
{
  senderId: string,
  text: string,           // message content or image URL
  type: 'text' | 'image' | 'system',
  timestamp: serverTimestamp(),
  read: boolean,
  participantIds: array,  // optional
}

// Typing document
{
  isTyping: boolean,
  updatedAt: serverTimestamp(),
}
```

## API Contracts

| Function | Input | Output | Error |
|----------|-------|--------|-------|
| sendMessage | matchId, senderId, text, type, participantIds | docRef | 'Mensagem vazia', FirebaseError |
| listenToMessages | matchId, callback, limit | unsubscribe fn | — |
| uploadImage | file, matchId | downloadURL | FirebaseError |
| sendTypingStatus | matchId, userId, isTyping | — | FirebaseError |
| listenToTyping | matchId, callback | unsubscribe fn | — |
| markMessagesRead | matchId, userId | — | FirebaseError |
| getMessages | matchId, limit, beforeTs | {messages, hasMore} | FirebaseError |

## Error Handling

| Error | User Message | Strategy |
|-------|-------------|----------|
| Empty message | Blocked silently | Input validation |
| Long message | Truncated to 2000 | Auto-truncate |
| Firestore write fail | "Falha ao enviar mensagem" | Remove optimistic, show banner |
| Image upload fail | "Falha ao enviar imagem" | Show banner |
| Offline | Queued message | LocalStorage queue, send on reconnect |
| Permission denied | Mapped Firebase error | mapFirebaseError() |
