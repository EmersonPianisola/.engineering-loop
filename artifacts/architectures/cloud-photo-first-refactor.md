---
name: Cloud Architecture — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# Cloud Architecture: Photo-First Refactor

## Impact Assessment

**No changes to cloud infrastructure.** This is a frontend-only refactor.

## Existing Infrastructure (Unchanged)

| Service | Purpose | Status |
|---------|---------|--------|
| Firebase Auth | OAuth (Google/Facebook) | Unchanged |
| Firestore | Listings, matches, profiles, chat | Unchanged |
| Firebase Storage | Vehicle photos | Unchanged |
| AWS S3 | Static assets, backups | Unchanged |
| CloudFront | CDN for PWA | Unchanged |

## Image Delivery Considerations

### Current
- Photos stored in Firebase Storage
- Direct URL access from client
- No CDN optimization for images

### Recommendation (Future, not in scope)
- Firebase Storage + CloudFront for image delivery
- Image resizing/thumbnail generation
- Lazy loading with progressive JPEG

**Out of scope for this refactor.** Current image delivery is sufficient for MVP.
