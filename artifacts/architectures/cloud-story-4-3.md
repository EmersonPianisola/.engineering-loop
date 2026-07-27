# Cloud Architecture — Story 4.3: Location Update & Match Recalculation

## Summary

**No cloud architecture changes are required for this story.**

Story 4.3 is a client-side feature addition that reuses all existing Firebase infrastructure without modification.

## Cloud Services Used (Unchanged)

| Service | Usage | Change? |
|---------|-------|---------|
| **Firebase Auth** | Session validation via `useAuth()` context | No |
| **Firestore** | `updateDoc` on `users/{uid}` (state, city, updatedAt) | No |
| **Cloud Storage** | Not used by this story | N/A |
| **Firebase Functions** | Not used in MVP | N/A |
| **Firebase Analytics** | Not used in MVP | N/A |

## Firestore Operations

### Write Operations

| Operation | Path | Fields | Trigger |
|-----------|------|--------|---------|
| Profile update | `users/{uid}` | `state`, `city`, `updatedAt` | User clicks "Salvar" on ProfilePage |

This is the **same write path** as the existing profile save flow. No new documents, subcollections, or indexes are needed.

### Read Operations (for Recalculation)

The recalculation step uses the **same data fetch patterns** as the initial match computation:

| Data Source | Collection | Query | Existing? |
|-------------|------------|-------|-----------|
| Active listings | `listings` | `where("status", "==", "active")` | Yes (`fetchActiveListings`) |
| Desire profiles | `users/{uid}/desire-profile/profile` | `getDoc` | Yes (`getDesireProfile`) |
| User vehicles | `users/{uid}/vehicles` | Filter by `userId` | Yes (existing pattern) |

No new Firestore queries, indexes, or security rules.

## Security Rules

**No changes required.** The existing granular rules for `users/{userId}` cover this operation:

```
match /users/{userId} {
  allow update: if request.auth != null
               && request.auth.uid == userId;
}
```

The `updateProfile` call updates `state` and `city` on the authenticated user's own document — fully compliant with existing rules.

## Indexes

**No new indexes required.** All queries used by the recalculation flow reuse existing query patterns:
- `listings` collection: `where("status", "==", "active")` — single-field index (already defined per `cloud-firebase-architecture.md` Gap 1)

## Offline Behavior

Profile updates require network connectivity (per existing architecture limitation #3 in `cloud-firebase-architecture.md`). If the user is offline:
1. `updateProfile` will fail with a network error
2. Error displayed: "Falha ao salvar localizacao."
3. Recalculation not attempted
4. User remains in edit mode (per Journey 5)

This is consistent with the existing offline behavior documented in the cloud architecture.

## Reference

- Full cloud architecture: `_bmad-output/implementation-artifacts/architectures/cloud-firebase-architecture.md`
- Existing Firestore operations: `_bmad-output/implementation-artifacts/architectures/solution-firebase-integration.md` (Auth Service section)
