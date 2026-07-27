---
name: Solution Design — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# Solution Design: Photo-First Refactor

## Component Architecture

### Modified Components

#### 1. VehicleCard (Refactor)
```
DEPRECATED structure:
┌─────────────────────┐
│ Image (16:10)       │
│ Region badge (TR)   │
├─────────────────────┤
│ Title               │
│ Year                │
│ Price | ShieldBadge │
└─────────────────────┘

NEW structure:
┌─────────────────────┐
│ Avatar (TL)         │
│ ShieldBadge (TR)    │
│ Photo (4:5)         │
│                     │
│ ┌─────────────────┐ │
│ │ Gradient overlay│ │
│ │ Title + Year    │ │
│ │ FIPE pill (BL)  │ │
│ │ Save icon (BR)  │ │
│ └─────────────────┘ │
└─────────────────────┘
```

**Props API:** Mantida — `{ vehicle, onClick }`
**Break:** `vehicle-card__content` removido. Tudo em overlay sobre foto.

#### 2. HomePage (Replace)
```
DEPRECATED: Welcome page com greeting + desire card + CTA
NEW: PistaFeed — infinite vertical feed de VehicleCards
```

**Component tree:**
```
PistaFeed
├── FeedHeader (logo + explore button)
├── SwipeContainer
│   └── VehicleCard[] (swipe-enabled)
└── PullToRefresh
```

#### 3. BrowseListings (Deprecate / Consolidate)
- **Opção A:** Remover, consolidar na PistaFeed
- **Opção B:** Manter como página de filtros avançados
- **Decisão:** Consolidar na PistaFeed. Filtros acessíveis via Explore button.

#### 4. VehicleDetail (Refactor)
```
DEPRECATED: Nav + carousel (16:10) + info section
NEW: Full-screen overlay com:
┌─────────────────────┐
│ Close button (TL)   │
│ Carousel (60% h)    │
│ Dots indicator      │
├─────────────────────┤
│ Bottom Sheet (40%)  │
│ ┌─────────────────┐ │
│ │ Title + Year    │ │
│ │ FIPE Price      │ │
│ │ Specs Grid      │ │
│ │ Owner Card      │ │
│ │ CTA Buttons     │ │
│ └─────────────────┘ │
└─────────────────────┘
```

#### 5. ProfilePage (Extend)
- Adicionar `VehicleGallery` component
- Grid 3-colunas, aspect-ratio 1:1
- Fotos dos veículos do usuário

#### 6. tokens.css (Update)
```css
--aspect-ratio-card: 4/5;
--radius-card: 12px;
--radius-button: 24px;
--radius-bottom-sheet: 16px;
--color-on-photo: #FFFFFF;
--elevation-xl: 0 20px 40px rgba(0,0,0,0.7);
--overlay-gradient: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
```

## Data Flow (Unchanged)

```
Firestore → listings.js → PistaFeed → VehicleCard[]
                              ↓
                        Swipe → matches.js → Match proposal
                              ↓
                        Tap → VehicleDetail (bottom sheet)
```

## File Changes

| File | Action |
|------|--------|
| `src/tokens.css` | UPDATE |
| `src/components/VehicleCard.jsx` | REWRITE |
| `src/components/VehicleCard.css` | REWRITE |
| `src/pages/HomePage.jsx` | REPLACE → PistaFeed |
| `src/pages/HomePage.css` | REPLACE → PistaFeed |
| `src/pages/BrowseListings.jsx` | DEPRECATE |
| `src/pages/BrowseListings.css` | DEPRECATE |
| `src/pages/VehicleDetail.jsx` | REFACTOR |
| `src/pages/VehicleDetail.css` | REFACTOR |
| `src/pages/ProfilePage.jsx` | EXTEND |
| `src/pages/ProfilePage.css` | EXTEND |
| `src/components/VehicleGallery.jsx` | NEW |
| `src/components/VehicleGallery.css` | NEW |
| `src/components/SwipeContainer.jsx` | NEW |
| `src/components/SwipeContainer.css` | NEW |

## Dependencies
- React 18+ (touch events para swipe)
- Firebase (sem mudanças)
- Sem novas dependências de terceiros
