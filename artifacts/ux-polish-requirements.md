# Architecture: UX Polish Requirements

## Category 1 — Input Masks & Validation

### UX-01: Currency mask for price fields
- **Location:** DesireProfile (priceMin, priceMax), FipeValuation (manual override), VehicleForm (mileage)
- **Behavior:** As user types digits, format with Brazilian thousand separators (e.g., `50.000`)
- **Storage:** Strip formatting before saving to Firestore (store as integer)
- **Edge cases:** Paste handling, backspace, delete, mobile keyboard input

### UX-02: CPF mask in ProfilePage edit mode
- **Location:** ProfilePage.jsx edit mode
- **Behavior:** Apply same `formatCPF()` used in ProfileSetup
- **Input mode:** `inputmode="numeric"` for mobile numpad

### UX-03: Phone mask in ProfilePage edit mode
- **Location:** ProfilePage.jsx edit mode
- **Behavior:** Apply same `formatPhone()` used in ProfileSetup

### UX-04: On-blur validation
- **Location:** All form fields across all pages
- **Behavior:** On blur, validate field and show inline error
- **Pattern:** Clear error on change, show error on blur if invalid

## Category 2 — User Feedback

### UX-05: Toast notification system
- **New component:** `src/components/Toast.jsx` + `src/components/Toast.jsx`
- **Pattern:** Auto-dismissing (3s), bottom-center, non-dismissible, `data-testid="toast"`
- **Queue:** Support multiple toasts (queue, show one at a time)
- **Accessibility:** `role="status"`, `aria-live="polite"`, screen reader announcement
- **Styling:** Card background, primary border-left, subtle animation (slide up)
- **Integration:** Context provider or global hook in App.jsx

### UX-06: Wire dead buttons
- **HomePage explore icon:** Navigate to BrowseListings
- **HomePage swipe handlers:** Wire `onSwipeRight` to create match, `onSwipeLeft` to skip
- **VehicleCard save heart:** Remove until save feature implemented

### UX-07: Toast for key actions
- Match accept → "Troca aceita!" 
- Match decline → "Proposta recusada"
- ProfileSetup save → "Perfil salvo!"
- ProfilePage edit save → "Alterações salvas"
- Vehicle delete → "Veículo excluído"
- Swap complete → "Troca concluída!"
- Feedback submit → "Obrigado pelo feedback!"

## Category 3 — Intuitive Filters (BrowseListings)

### UX-08: Chip-based filter bar
- **Replace:** Form-style FilterBar with horizontal scrollable chip rows
- **Brand chips:** 4-6 most popular brands + "Mais marcas" → bottom sheet
- **Year chips:** Ranges (e.g., "2020–2026", "2015–2019", "2010–2014", "Anterior")
- **Price chips:** "Qualquer preço", "Até R$ 50 mil", "R$ 50–80 mil", "R$ 80–120 mil", "Acima de R$ 120 mil"
- **Region chips:** 27 UF as small chips, grouped by macro-region
- **Sort chips:** "Relevância", "Preço ↑", "Preço ↓", "Ano ↓"
- **Active filters:** Dismissible pills with ✕ above grid
- **Advanced filters:** Bottom sheet for full form (power users)

### UX-09: Consolidate sort controls
- Remove duplicate sort from FilterBar
- Place sort chips above vehicle grid

## Category 4 — MatchCard Layout

### UX-10: Side-by-side photo layout
- **Mobile:** Two photos side-by-side at ~48% width each with small gap
- **Swap indicator:** Small "⇄" icon between photos (replace dashed divider)
- **Metadata:** Move level badge to top-left overlay pill, status to top-right
- **Reason text:** Hidden behind "ℹ️" tap-to-reveal
- **Gesture separation:** Swipe only on card edges, VehicleCard taps navigate to detail

## Technical Constraints
- No new npm dependencies (no masking library — implement inline)
- Follow existing CSS custom properties (tokens.css)
- No routing library changes (imperative state navigation)
- Portuguese (BR) microcopy
- Dark-mode-first, responsive at 768px
