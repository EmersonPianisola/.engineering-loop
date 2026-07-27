---
name: Architecture Review — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# Architecture Review: Photo-First Refactor

## Review Findings

### Critical: 0
### Major: 1
### Minor: 2

### Finding M-1: BrowseListings Deprecation Risk
**Severity:** Major
**Description:** BrowseListings pode ser usado por rotas existentes ou links diretos.
**Recommendation:** Redirecionar rota BrowseListings → HomePage (PistaFeed) ao invés de remover silenciosamente.

### Finding Mi-1: MatchCard Dependency
**Severity:** Minor
**Description:** MatchCard usa VehicleCard internamente. Refatoração do VehicleCard pode quebrar MatchCard.
**Recommendation:** Testar MatchCard explicitamente após refatoração. Considerar prop `variant` no VehicleCard para suportar ambos os contextos.

### Finding Mi-2: Swipe Gesture Conflicts
**Severity:** Minor
**Description:** Swipe horizontal no VehicleDetail carousel pode conflitar com swipe vertical do feed.
**Recommendation:** VehicleDetail é full-screen overlay — sem conflito. Confirmar que swipe do feed não propaga quando detail está aberto.

## Consolidated Architecture

**Approved with modifications:**
- Adicionar redirect BrowseListings → HomePage
- Adicionar prop `variant` ao VehicleCard (feed | match)
- Manter swipe isolado por contexto (feed vs detail)

**Architecture: APPROVED** ✓
