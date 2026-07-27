---
title: "BDD Journey — Real-Time Chat (Spec 5.1)"
work_item: "_bmad-output/implementation-artifacts/spec-5-1-real-time-chat.md"
generated: "2026-07-21"
---

# BDD Journey: Real-Time Chat

## Journey 1: Open Accepted Match Chat

### Actor
- Primary: User with an accepted match
- Secondary: Matched partner

### Pre-conditions
- User has an accepted match (status = 'accepted')
- Match document exists in Firestore

### Happy Path
```gherkin
Feature: Open Chat Room
  Scenario: User opens accepted match with no messages
    Given I have an accepted match with another user
    When I open the chat room
    Then I see the system message "Troca aceita! Comencem a conversar."
    And the message input field is active

  Scenario: User opens accepted match with existing messages
    Given I have an accepted match with message history
    When I open the chat room
    Then I see the message history displayed
    And the message input field is active
```

### Edge Cases
```gherkin
  Scenario: User opens non-accepted match chat
    Given I have a match that is not accepted
    When I try to open the chat room
    Then I am redirected to the match list
    And I see "Apenas trocas aceitas permitem conversacao."

  Scenario: User opens cancelled match chat
    Given I have a cancelled match
    When I open the chat room
    Then I see the chat history in read-only mode
    And the input field is disabled
    And I see the "Cancelada" badge
```

### Post-conditions
- Chat room rendered with messages or welcome system message
- Typing listener active

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Open accepted match with no messages | e2e | high |
| Open accepted match with history | e2e | high |
| Open non-accepted match | unit | medium |
| Open cancelled match | e2e | high |

---

## Journey 2: Send Text Message

### Actor
- Primary: User in active chat

### Pre-conditions
- Chat room open, match status 'accepted'
- User is online

### Happy Path
```gherkin
Feature: Send Text Message
  Scenario: User sends valid text message
    Given I am in an active chat room
    When I type a message and tap send
    Then the message appears instantly in the chat
    And the message is persisted to Firestore
    And my input field is cleared

  Scenario: Other user sends message in real-time
    Given I am viewing an active chat
    When the other user sends a message
    Then the message appears in real-time
```

### Edge Cases
```gherkin
  Scenario: User sends empty message
    Given I am in an active chat room
    When I tap send without typing anything
    Then the message is not sent
    And the input remains focused

  Scenario: User sends very long message
    Given I am in an active chat room
    When I type a message over 2000 characters and send
    Then the message is truncated to 2000 characters
    And I see a warning "Mensagem limitada a 2000 caracteres"

  Scenario: Firestore write fails
    Given I am in an active chat room
    When I send a message and Firestore returns an error
    Then the optimistic message is removed
    And I see "Falha ao enviar mensagem. Tente novamente."
```

### Post-conditions
- Message visible in chat and stored in Firestore

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Send valid text message | e2e | high |
| Real-time message from other user | e2e | high |
| Empty message blocked | unit | high |
| Long message truncated | unit | high |
| Firestore write failure | unit | medium |

---

## Journey 3: Typing Indicator

### Actor
- Primary: User typing in chat
- Secondary: User observing typing indicator

### Pre-conditions
- Both users in active chat room

### Happy Path
```gherkin
Feature: Typing Indicator
  Scenario: Other user is typing
    Given I am viewing an active chat
    When the other user starts typing
    Then I see the animated typing indicator

  Scenario: Other user stops typing
    Given the other user was typing
    When the other user stops typing for 3 seconds
    Then the typing indicator is hidden
```

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Typing indicator shown | e2e | medium |
| Typing indicator expires | unit | medium |

---

## Journey 4: Scroll Behavior

### Actor
- Primary: User viewing chat

### Happy Path
```gherkin
Feature: Auto-Scroll
  Scenario: User at bottom, new message arrives
    Given I am scrolled to the bottom of the chat
    When a new message arrives
    Then the view auto-scrolls to show the new message

  Scenario: User scrolled up, new message arrives
    Given I am scrolled up in the chat
    When a new message arrives
    Then my scroll position is preserved
    And an unread badge appears with message count

  Scenario: User scrolls to bottom to dismiss badge
    Given an unread badge is visible
    When I scroll to the bottom
    Then the unread badge disappears
```

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Auto-scroll at bottom | e2e | medium |
| Preserve scroll + badge | e2e | medium |
| Dismiss unread badge | e2e | low |

---

## Journey 5: Image Upload

### Actor
- Primary: User sending image

### Pre-conditions
- Chat room open, match accepted

### Happy Path
```gherkin
Feature: Image Upload
  Scenario: User sends image
    Given I am in an active chat room
    When I select and send an image
    Then the image is uploaded to Firebase Storage
    And the image appears as a message in the chat

  Scenario: Image upload fails
    Given I am in an active chat room
    When I select an image and upload fails
    Then I see "Falha ao enviar imagem. Tente novamente."
```

### Edge Cases
```gherkin
  Scenario: Unsupported image type
    Given I am in an active chat room
    When I try to upload a non-image file
    Then I see an appropriate error

  Scenario: Image too large
    Given I am in an active chat room
    When I try to upload an image over 5MB
    Then I see an appropriate error
```

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Send image | e2e | high |
| Upload failure | unit | medium |
| File type validation | unit | medium |
| File size validation | unit | medium |

---

## Journey 6: Offline Mode

### Actor
- Primary: User going offline

### Happy Path
```gherkin
Feature: Offline Messaging
  Scenario: User goes offline
    Given I am in an active chat
    When I lose network connection
    Then I see an offline indicator

  Scenario: User sends message while offline
    Given I am offline in an active chat
    When I type and send a message
    Then the message is queued locally
    And the message is sent when I reconnect
```

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Offline indicator | e2e | medium |
| Queue + send on reconnect | unit | high |

---

## Journey 7: Match Cancellation in Chat

### Actor
- Primary: User cancelling match from chat

### Happy Path
```gherkin
Feature: Cancel Match from Chat
  Scenario: Match cancelled by other party
    Given I am in an active chat
    When the other party cancels the match
    Then I see a system message about cancellation
    And the input is disabled
```

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Cancellation system message | e2e | high |
| Disabled input on cancellation | e2e | high |

---

## Journey 8: Chat Styling

### Actor
- Primary: User viewing chat

### Happy Path
```gherkin
Feature: Chat Visual Design
  Scenario: User message bubble styling
    Given I am viewing the chat
    Then my messages have rust background with white text and are right-aligned

  Scenario: Other user message bubble styling
    Given I am viewing the chat
    Then the other user's messages have dark card background and are left-aligned

  Scenario: System message styling
    Given a system message is displayed
    Then it is centered with smaller font and muted color
```

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| User bubble styling | e2e | medium |
| Other bubble styling | e2e | medium |
| System message styling | e2e | low |

---

## Coverage Summary

| Category | Scenarios | E2E | Unit | Integration |
|----------|-----------|-----|------|-------------|
| Open Chat | 4 | 3 | 1 | 0 |
| Send Text | 5 | 2 | 3 | 0 |
| Typing | 2 | 1 | 1 | 0 |
| Scroll | 3 | 3 | 0 | 0 |
| Images | 4 | 1 | 3 | 0 |
| Offline | 2 | 1 | 1 | 0 |
| Cancellation | 2 | 2 | 0 | 0 |
| Styling | 3 | 3 | 0 | 0 |
| **Total** | **25** | **16** | **9** | **0** |
