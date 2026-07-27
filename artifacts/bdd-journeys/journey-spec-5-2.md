# BDD Journey — Conversation List & History (Spec 5.2)

## Journey 1: View Conversation List

### Actor
Logged-in user with accepted matches.

### Pre-conditions
- User is authenticated via Google or Facebook OAuth.
- User is on the "Conversas" tab.
- ChatRoom (Story 5.1) and Matches service (Story 4.2) are available.

### Happy Path

**Scenario 1.1: User sees conversations sorted by last message**
```gherkin
Given I have 3 accepted matches, each with at least one message
When I open the "Conversas" tab
Then I see 3 conversation items
And conversations are sorted by last message timestamp (newest first)
```

**Scenario 1.2: Accepted matches without messages show placeholder preview**
```gherkin
Given I have 2 accepted matches with no messages exchanged
When I open the "Conversas" tab
Then I see 2 conversation items
And each item displays "Nenhuma mensagem ainda" as the preview text
```

**Scenario 1.3: No accepted matches shows empty state**
```gherkin
Given I have no accepted matches
When I open the "Conversas" tab
Then I see the empty state message "Nenhuma conversa ainda"
And I see a hint prompting me to explore matches
```

### Alternative Paths
**Scenario 1.4: Mixed state — some matches with messages, some without**
```gherkin
Given I have 3 accepted matches
  and 2 matches have messages
  and 1 match has no messages
When I open the "Conversas" tab
Then the 2 matches with messages appear sorted by last message time
And the 1 match without messages appears below with "Nenhuma mensagem ainda"
```

### Edge Cases
- User refreshes the page while on the Conversas tab — list re-queries from Firestore.
- A match transitions from accepted to cancelled while viewing the list — item disappears on next real-time update.

### Post-conditions
- Conversation list is fully rendered and ready for interaction.
- Real-time listeners are subscribed for match and message updates.

### Test Mapping
| Scenario | I/O # | Type | Priority |
|----------|-------|------|----------|
| 1.1 | 1 | Unit + E2E | P0 |
| 1.2 | 2 | Unit + E2E | P0 |
| 1.3 | 3 | Unit + E2E | P0 |
| 1.4 | — | Integration | P1 |

---

## Journey 2: Message Preview Handling

### Actor
User browsing the conversation list.

### Pre-conditions
- User has accepted matches with messages of varying types.
- User is on the Conversas tab.

### Happy Path

**Scenario 2.1: Image message as last message shows "[Foto]"**
```gherkin
Given the last message in match "match-001" is of type "image"
When I view the conversation list
Then the preview for match "match-001" displays "[Foto]"
```

**Scenario 2.2: Long message is truncated**
```gherkin
Given the last message in match "match-002" is a text message exceeding 40 characters
When I view the conversation list
Then the preview for match "match-002" is truncated to 40 characters
And the preview ends with "..."
```

### Alternative Paths

**Scenario 2.3: System message as last — falls back to previous user message**
```gherkin
Given the last message in match "match-003" is of type "system"
  and a prior user-sent message exists in the same match
When I view the conversation list
Then the preview for match "match-003" displays the prior user message text
And the system message is not shown as the preview
```

**Scenario 2.4: System message as last — no prior user message**
```gherkin
Given the last message in match "match-004" is of type "system"
  and no other user-sent messages exist in the match
When I view the conversation list
Then the preview for match "match-004" displays "Conversa iniciada"
```

### Edge Cases
- Last message text is exactly 40 characters — displayed in full, no truncation.
- Message contains only whitespace — preview displays whitespace-trimmed result.
- Multiple system messages at end — skips all until user message or defaults to "Conversa iniciada".

### Post-conditions
- All conversation items render correct preview text for their last message.

### Test Mapping
| Scenario | I/O # | Type | Priority |
|----------|-------|------|----------|
| 2.1 | 6 | Unit | P0 |
| 2.2 | 7 | Unit | P0 |
| 2.3 | 5 | Unit + Integration | P0 |
| 2.4 | 5 | Unit | P1 |

---

## Journey 3: Unread Count Management

### Actor
User managing unread conversations.

### Pre-conditions
- User is on the Conversas tab.
- User has accepted matches with unread messages.

### Happy Path

**Scenario 3.1: Single unread badge displays correctly**
```gherkin
Given I have 5 unread messages in match "match-001"
When I view the conversation list
Then match "match-001" displays a red badge with count "5"
```

**Scenario 3.2: Reading conversation resets unread count**
```gherkin
Given match "match-001" has 5 unread messages
When I tap the conversation for "match-001"
  and the ChatRoom opens
Then the unread badge for "match-001" resets to 0
And the badge is no longer visible
```

### Alternative Paths

**Scenario 3.3: High unread count is capped**
```gherkin
Given I have 127 unread messages in match "match-002"
When I view the conversation list
Then the badge for match "match-002" displays "99+"
```

**Scenario 3.4: Cancelled matches excluded from list**
```gherkin
Given I have 2 accepted matches and 1 cancelled match
When I view the conversation list
Then I see only the 2 accepted matches
And the cancelled match is not visible
```

### Edge Cases
- Unread count is exactly 1 — badge shows "1" (not hidden).
- Unread count transitions 0→1 via real-time listener — badge appears immediately.

### Post-conditions
- Unread badge accurately reflects unread message counts for each match.

### Test Mapping
| Scenario | I/O # | Type | Priority |
|----------|-------|------|----------|
| 3.1 | 10 | Unit + E2E | P0 |
| 3.2 | 9 | Integration + E2E | P0 |
| 3.3 | 11 | Unit | P1 |
| 3.4 | 4 | Unit + E2E | P0 |

---

## Journey 4: Real-time Updates

### Actor
User viewing the conversation list while another user sends a message.

### Pre-conditions
- User is on the Conversas tab with at least one accepted match.
- The other matched user is active and can send messages.

### Happy Path

**Scenario 4.1: New message re-sorts conversation and updates badge**
```gherkin
Given the conversation for match "match-003" is currently 2nd in the list
  and "match-003" has 0 unread messages
When the other user sends a new message to "match-003"
Then the conversation for "match-003" moves to the top of the list
And the badge updates to show "1"
And the preview text updates to the new message content
```

**Scenario 4.2: New message to unseen match adds it to list**
```gherkin
Given I have 0 accepted matches
When another user accepts a swap match with me
  and sends the first message
Then a new conversation item for the match appears in the list
And the item is at the top of the list
And the badge shows "1"
```

### Alternative Paths
**Scenario 4.3: Multiple messages arrive rapidly**
```gherkin
Given "match-001" has 0 unread messages
When the other user sends 3 messages in rapid succession
Then the badge for "match-001" updates to "3"
And the preview reflects the last message sent
And the conversation remains at the top of the list
```

### Edge Cases
- Network briefly drops during real-time update — Firestore reconnects and syncs.
- Message arrives for cancelled match — no update reflected.

### Post-conditions
- Conversation list accurately reflects real-time message state.

### Test Mapping
| Scenario | I/O # | Type | Priority |
|----------|-------|------|----------|
| 4.1 | 8 | Integration + E2E | P0 |
| 4.2 | 8 | Integration + E2E | P0 |
| 4.3 | 8 | Integration | P1 |

---

## Journey 5: Error and Fallback Handling

### Actor
User encountering data errors while viewing the conversation list.

### Pre-conditions
- User is on the Conversas tab.

### Happy Path

**Scenario 5.1: Firestore query failure shows error banner**
```gherkin
Given the Firestore query for matches fails (network error)
When the ConversationList attempts to load
Then I see an ErrorBanner component
And the banner includes a retry button
When I tap the retry button
Then the list re-queries Firestore
And if the query succeeds, the banner disappears and the list renders
```

### Alternative Paths

**Scenario 5.2: Missing target user data uses fallback name**
```gherkin
Given a match exists but the target user's profile data is missing
When I view the conversation list
Then the conversation item displays "Usuario" as the user name
And the rest of the item renders normally (vehicle, preview, timestamp)
```

### Edge Cases
- Vehicle data also missing — shows "Veículo" as fallback label.
- Timestamp missing or null — displays relative time placeholder or hides timestamp.
- Retry button tapped multiple times — only one query in-flight (debounced).

### Post-conditions
- Error state is recoverable. Fallback labels prevent blank or broken UI.

### Test Mapping
| Scenario | I/O # | Type | Priority |
|----------|-------|------|----------|
| 5.1 | 12 | Unit + E2E | P0 |
| 5.2 | 13 | Unit | P1 |

---

## Journey 6: Navigation to Chat Room

### Actor
User tapping a conversation to open the chat.

### Pre-conditions
- User is on the Conversas tab with at least one conversation item visible.
- ChatRoom component (Story 5.1) is mounted and routable.

### Happy Path

**Scenario 6.1: Tapping conversation opens ChatRoom with correct match**
```gherkin
Given the conversation list displays match "match-001"
When I tap the conversation item for "match-001"
Then the ChatRoom page opens
And the ChatRoom loads messages for "match-001"
And the unread count for "match-001" is reset to 0
```

### Alternative Paths
**Scenario 6.2: Back navigation returns to conversation list**
```gherkin
Given I am viewing ChatRoom for "match-001"
When I navigate back
Then I return to the ConversationList
And the list reflects the updated unread counts from my chat session
```

### Edge Cases
- Match cancelled while in ChatRoom — returning to list shows match removed.
- Rapid double-tap — only one navigation occurs (idempotent).

### Post-conditions
- ChatRoom is open and fully functional. Unread counts are consistent.

### Test Mapping
| Scenario | I/O # | Type | Priority |
|----------|-------|------|----------|
| 6.1 | 14 | E2E | P0 |
| 6.2 | 14 | E2E | P1 |
