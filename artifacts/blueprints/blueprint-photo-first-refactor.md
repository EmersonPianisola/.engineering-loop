---
name: Implementation Blueprint — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# Implementation Blueprint: Photo-First Refactor

## Execution Order

| # | File | Action | Depends On |
|---|------|--------|------------|
| 1 | `src/tokens.css` | UPDATE | — |
| 2 | `src/components/VehicleCard.jsx` | REWRITE | #1 |
| 3 | `src/components/VehicleCard.css` | REWRITE | #1 |
| 4 | `src/components/SwipeContainer.jsx` | NEW | — |
| 5 | `src/components/SwipeContainer.css` | NEW | — |
| 6 | `src/pages/HomePage.jsx` | REPLACE | #2, #4 |
| 7 | `src/pages/HomePage.css` | REPLACE | — |
| 8 | `src/pages/VehicleDetail.jsx` | REFACTOR | #1 |
| 9 | `src/pages/VehicleDetail.css` | REFACTOR | #1 |
| 10 | `src/components/VehicleGallery.jsx` | NEW | — |
| 11 | `src/components/VehicleGallery.css` | NEW | — |
| 12 | `src/pages/ProfilePage.jsx` | EXTEND | #10 |
| 13 | `src/pages/ProfilePage.css` | EXTEND | #11 |

## Contracts

### VehicleCard Props
```tsx
interface VehicleCardProps {
  vehicle: {
    id: string;
    brand?: string;
    model?: string;
    year?: number;
    fipePrice?: number;
    region?: string;
    photos?: Array<{ url: string } | string>;
    trustTier?: 'high' | 'medium' | 'low';
    userId?: string;
    ownerName?: string;
  };
  onClick?: () => void;
  variant?: 'feed' | 'match';  // NEW — controls overlay layout
}
```

### SwipeContainer Props
```tsx
interface SwipeContainerProps {
  children: React.ReactNode;
  onSwipeRight?: () => void;
  onSwipeLeft?: () => void;
  threshold?: number;  // px, default 80
}
```

### VehicleGallery Props
```tsx
interface VehicleGalleryProps {
  vehicles: Array<{
    id: string;
    photos?: Array<{ url: string } | string>;
  }>;
  onVehicleClick?: (vehicle: any) => void;
}
```

## CSS Contracts

### tokens.css additions
```css
:root {
  --aspect-ratio-card: 4/5;
  --radius-card: 12px;
  --radius-button: 24px;
  --radius-bottom-sheet: 16px;
  --color-on-photo: #FFFFFF;
  --elevation-xl: 0 20px 40px rgba(0, 0, 0, 0.7);
  --overlay-gradient: linear-gradient(to top, rgba(0, 0, 0, 0.85) 0%, transparent 60%);
  --z-feed: 1;
  --z-detail-overlay: 100;
  --z-bottom-sheet: 110;
}
```

## File Specifications

### 1. tokens.css
- Add new variables listed above
- Update existing: `--radius-card` (8px → 12px), `--radius-button` (4px → 24px)

### 2-3. VehicleCard
- Full rewrite: photo full-bleed 4:5, overlays on photo
- Gradient overlay bottom 40% for text readability
- Owner avatar top-left, ShieldBadge top-right
- Title + year center-bottom, FIPE pill bottom-left
- Support `variant='match'` for MatchCard compatibility

### 4-5. SwipeContainer
- New component: wraps children with touch/mouse swipe detection
- Threshold-based: swipe triggers only after N px movement
- Visual feedback: rotation + opacity during swipe
- Callback: onSwipeRight, onSwipeLeft

### 6-7. HomePage → PistaFeed
- Replace welcome page with infinite feed
- FeedHeader: logo + explore button
- SwipeContainer wrapping VehicleCard
- Pull-to-refresh
- Skeleton loading (4:5 aspect ratio)
- Empty state

### 8-9. VehicleDetail
- Convert to full-screen overlay pattern
- Carousel: 60% viewport height
- Bottom sheet: 40% height, scrollable
- Maintain existing carousel functionality
- Update styling: bottom sheet radius, elevation-xl

### 10-11. VehicleGallery
- New component: 3-column grid
- Each item: 1:1 aspect ratio, vehicle photo
- Click → navigate to vehicle detail

### 12-13. ProfilePage
- Insert VehicleGallery after stats section
- Fetch user's vehicles from existing lib

## Testing Strategy

| Component | Unit | E2E |
|-----------|------|-----|
| tokens.css | ✓ (CSS variable existence) | — |
| VehicleCard | ✓ (render, overlays, accessibility) | ✓ (tap, swipe) |
| SwipeContainer | ✓ (gesture detection, callbacks) | ✓ (swipe feed) |
| PistaFeed | ✓ (loading, empty, populated) | ✓ (feed scroll) |
| VehicleDetail | ✓ (carousel, bottom sheet) | ✓ (tap detail) |
| VehicleGallery | ✓ (grid, click) | ✓ (profile gallery) |
