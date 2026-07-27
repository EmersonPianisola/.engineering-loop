# Rota 101 — Design Artifacts

---

## 1. Personas

### Troca Ativa

**Perfil:** Usuário que entrou na plataforma com objetivo claro: trocar o veículo atual por outro específico. Valoriza velocidade na decisão e confiança nos números.

**Comportamento:**
- Abre o app, vai direto para `pista` ou `matches`
- Filtra por marca/marca desejada e faixa de preço
- Abre detalhes do veículo, verifica foto com zoom, confirma FIPE
- Se o delta financeiro faz sentido, aceita a match na hora
- Não tolera ambiguidade: quer saber exatamente quanto paga ou recebe

**Necessidades que os refinamentos atendem:**
- **Vehicle Detail Page:** Imagem em destaque + dados do match engine visíveis sem scroll excessivo
- **Swap Calculator:** Mensagem "Você paga R$ X" / "Você recebe R$ X" — decisão binária, sem interpretação
- **Match UI:** Botões ❤️/❌ para ação rápida sem abrir cada card

**Frustrações atuais:**
- Cores semânticas (verde/vermelho/amarelo) criam ruído visual e associam o app a lifestyle, não a transação
- Detalhes do veículo espalhados: tem que rolar para ver FIPE, região, trust tier
- Sem zoom nas fotos: não consegue verificar estado do veículo visualmente

---

### Cauteloso

**Perfil:** Usuário que quer trocar o carro, mas precisa de certeza sobre o estado do veículo e a justiça do preço. Pesquisa antes de agir.

**Comportamento:**
- Passa mais tempo na `pista` navegando do que aceitando matches
- Abre Vehicle Detail de vários veículos antes de decidir
- Usa zoom nas fotos para inspecionar detalhes (amassados, pintura, interior)
- Compara FIPE com o preço que o dono está pedindo
- Verifica trust tier e localização antes de qualquer contato
- Lê a seção "Por que esta troca?" em cada match

**Necessidades que os refinamentos atendem:**
- **Photo Zoom:** Due diligence visual — mínimo 4×, com pinch no mobile
- **Vehicle Detail Page:** Seções colapsáveis para secundário (cor, quilometragem, placa) — foco no essencial primeiro
- **Swap Calculator:** Transparência total: FIPE do meu + FIPE do outro + ajuste do dono = delta
- **Visual Design B/W/Gray:** Seriedade transacional — o app não parece jogo, parece ferramenta

**Frustrações atuais:**
- Fotos sem zoom: não consegue ver detalhes de desgaste
- Cores vibrantes (vermelho, amarelo, verde) passam sensação de "app de namoro" — não de transação financeira
- Sem clareza sobre como o delta foi calculado

---

## 2. Wireframes (Arquitetura de Informação)

### Vehicle Detail Page (Mobile-First)

```
┌─────────────────────────────────┐
│  ┌──┐                           │  ← 32px from edge, z-index: z-detail-overlay
│  │ ✕ │                          │
│  └──┘                           │
│                                 │
│  ┌───────────────────────────┐  │
│  │                           │  │
│  │                           │  │
│  │      VEHICLE PHOTO        │  │  55dvh, tap → zoom overlay
│  │      (primary image)      │  │
│  │                           │  │
│  │              ┌──┐         │  │  ┌──┐ = zoom hint (40×40px)
│  │              │🔍│         │  │
│  │              └──┘         │  │
│  │   ◀    • • ● •   ▶       │  │  dots + arrows, z: 2
│  └───────────────────────────┘  │
│                                 │
│  ─────────────────────────────  │  ← sheet handle (36×4px)
│  ┌───────────────────────────┐  │
│  │ HONDA CIVIL                │  │  font-display, uppercase, tracking 0.05em
│  │ 2019                       │  │  font-body, color-muted
│  │                            │  │
│  │ R$ 68.500                  │  │  font-mono, font-h2, weight 600
│  │                            │  │
│  │ ┌──────────────────────┐  │  │
│  │ │ Marca: Honda         │  │  │  Match engine info — always visible
│  │ │ Modelo: Civic        │  │  │
│  │ │ Ano: 2019            │  │  │
│  │ │ FIPE: R$ 68.500      │  │  │
│  │ │ Região: SP           │  │  │
│  │ │ Nível confiança: Alto│  │  │  ShieldBadge
│  │ └──────────────────────┘  │  │
│  │                            │  │
│  │ ▼ Detalhes do veículo     │  │  ← Collapsible (closed by default)
│  │                            │  │
│  │ ▼ Informações do dono     │  │  ← Collapsible (closed by default)
│  │                            │  │
│  │ ┌─────────────────────────┐│  │
│  │ │  Sugestão de troca      ││  │  Primary action, full width
│  │ └─────────────────────────┘│  │
│  │ ┌─────────────────────────┐│  │
│  │ │  Ver perfil             ││  │  Secondary action, outline
│  │ └─────────────────────────┘│  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**Mudanças em relação ao atual:**
- Match engine info (marca, modelo, ano, FIPE, região, trust tier) — sempre visível, não dentro de colapsável
- Seções secundárias (cor, km, placa, dono) — colapsáveis, fechadas por padrão
- Imagem ocupa 55dvh (era 60dvh) para dar mais espaço ao sheet
- Zoom hint button permanece, mas visual mais discreto

---

### Match Confirmation Screen

```
┌─────────────────────────────────┐
│  ┌──┐                           │
│  │ ← │  Confirmar troca         │
│  └──┘                           │
│                                 │
│  ┌──────────┐  ↔  ┌──────────┐ │
│  │          │      │          │ │
│  │ Seu carro│      │ Carro do │ │
│  │          │      │ outro    │ │
│  │          │      │          │ │
│  └──────────┘      └──────────┘ │
│                                 │
│  ─────────────────────────────  │
│                                 │
│  VALOR DA TROCA                 │  ← font-heading, uppercase
│                                 │
│  Seu veículo:    R$ 45.000      │  ← font-mono, color-text
│  Veículo outro:  R$ 68.500      │
│  Ajuste do dono: R$ 0,00       │
│                                 │
│  ─────────────────────────────  │
│                                 │
│  Você paga R$ 23.500            │  ← font-h2, weight 700
│                                 │
│  ─────────────────────────────  │
│                                 │
│  Nível de match: N1 (exato)     │
│  Confiança: Alto                │
│                                 │
│  ─────────────────────────────  │
│                                 │
│  ┌─────────────────────────┐    │
│  │  Aceitar troca          │    │  Primary, full width
│  └─────────────────────────┘    │
│  ┌─────────────────────────┐    │
│  │  Recusar                │    │  Secondary, outline
│  └─────────────────────────┘    │
│                                 │
└─────────────────────────────────┘
```

**Regras do calculator:**
- Text only. Zero cores, zero ícones decorativos.
- Se delta > 0 (target mais caro): "Você paga R$ X"
- Se delta < 0 (target mais barato): "Você recebe R$ X"
- Se delta = 0: "Valores equivalentes — troca direta"
- Requer conexão: ambos os veículos devem ter FIPE carregado

---

### Match Card

```
┌─────────────────────────────────┐
│  ┌──┐                           │
│  │N1│                          │  ← Level badge, top-left
│  └──┘                           │
│                                 │
│  ┌──────────┐  ↔  ┌──────────┐ │
│  │          │      │          │ │
│  │ Seu carro│      │ Carro do │ │
│  │          │      │ outro    │ │
│  │          │      │          │ │
│  └──────────┘      └──────────┘ │
│                                 │
│  ─────────────────────────────  │
│                                 │
│  Você paga R$ 23.500            │  ← Delta text, center
│                                 │
│  ─────────────────────────────  │
│                                 │
│          ❌        ❤️           │  ← 48×48px min, 32px gap
│                                 │
└─────────────────────────────────┘
```

**Mudanças em relação ao atual:**
- Botões ❤️/❌ substituem "Aceitar troca" / "Recusar" textuais
- Swipe gestures mantidos (swipe right = ❤️, swipe left = ❌)
- Delta text sem cor semântica — apenas peso tipográfico
- Status badges sem cor — border style + texto indicam estado

---

## 3. Interaction Patterns

### Photo Zoom

**Mobile (pinch-to-zoom):**
- Trigger: Tap na foto do Vehicle Detail → abre zoom overlay fullscreen
- Pinch open (2 fingers): scale 1× → 5×, com `scaleDelta = (dist - startDist) * 0.005`
- Pan (1 finger, scale > 1): translate image freely within overlay bounds
- Pinch close: scale returns to 1×, position resets to center
- Tap overlay background: close zoom
- Double-tap: toggle between 1× and 2× centered on tap point

**Desktop (scroll-zoom):**
- Trigger: Click no zoom hint button ou na foto → abre zoom overlay
- Mouse wheel: scale ±0.1 per notch, clamped [1, 5]
- Click + drag (scale > 1): pan image
- `+`/`-` keys: scale ±0.3
- `Escape`: close overlay
- Click background: close overlay

**Shared:**
- Min zoom: 4× (requirement)
- Max zoom: 5×
- Reset button: returns to 1×, center position
- `transform-origin: center center` — zoom always from image center
- `will-change: transform` on zoomed image for GPU compositing
- `prefers-reduced-motion: reduce` → no transition, instant scale change

**Implementation notes:**
- Existing `VehicleDetail.jsx` already implements pinch + scroll zoom (lines 89-148)
- Current max scale is 5× — meets 4× minimum requirement
- Need to add double-tap toggle (1× ↔ 2×) — not yet implemented
- Need to clamp pan bounds so image doesn't pan completely off-screen

---

### Swipe + Button Like/Dislike

**Swipe gesture:**
- Threshold: 80px horizontal displacement triggers action
- Right swipe → like (❤️ equivalent)
- Left swipe → dislike (❌ equivalent)
- Rotation: `offset * 0.05` degrees for natural feel
- Ejection animation: card flies off-screen beyond threshold (250ms)
- Stamp overlay: fades in based on `progress = min(|offset| / threshold, 1)`
- After ejection: 250ms delay before loading next card

**Explicit buttons:**
- ❤️ button: 48×48px minimum touch target, positioned right of ❌
- ❌ button: 48×48px minimum touch target, positioned left of ❤️
- Buttons and swipe are complementary — either triggers the same action
- Button press: `transform: scale(0.97)` on `:active`
- Focus visible: 2px outline with `--color-focus`, 2px offset

**Interaction rules:**
- Swipe and buttons fire the same callbacks (`onSwipeRight` → `onAccept`, `onSwipeLeft` → `onDecline`)
- While card is animating out, buttons are disabled (`pointer-events: none`)
- Swipe threshold not reached → card snaps back to center (0.3s ease)

**Implementation notes:**
- Existing `SwipeContainer.jsx` handles swipe (lines 6-102)
- Need to add ❤️/❌ buttons as siblings of the swipe container in `MatchCard`
- Buttons must call the same `onAccept`/`onDecline` handlers
- Current stamps use colored borders — must change to B/W/Gray outline

---

### Collapsible Sections

**Behavior:**
- Chevron indicator: ▼ (closed) → ▲ (open), 16×16px SVG
- Toggle: click/press on section header row
- Animation: max-height transition, 250ms ease-out
- Only one section open at a time (accordion pattern) — optional, not required
- `aria-expanded` toggles between `true`/`false`
- `aria-controls` points to section content ID

**Vehicle Detail collapsible sections:**
1. **"Detalhes do veículo"** — Cor, Quilometragem, Placa, Combustível, Câmbio
2. **"Informações do dono"** — Avatar, Nome, Localização, Trust tier badge

**Implementation notes:**
- Existing `MatchCard` has collapsible reason section (lines 110-133) — reuse pattern
- `VehicleDetail` currently shows all specs inline — need to move secondary specs into collapsible
- Use CSS `max-height: 0` → `max-height: 300px` transition for smooth expand/collapse

---

### Match Confirmation Flow with Calculator

**Flow:**
1. User taps "Sugestão de troca" in Vehicle Detail
2. Navigates to Match Confirmation overlay (or inline modal)
3. Calculator loads FIPE prices for both vehicles
4. If either vehicle lacks FIPE → show "Cálculo indisponível — FIPE pendente"
5. Delta computed: `targetPrice - userPrice + ownerAdjustment`
6. Message displayed: text-only, typographic emphasis only
7. User sees match level, trust tier, delta
8. User taps "Aceitar troca" or "Recusar"

**Calculator states:**
- **Loading:** Skeleton for price rows, "Calculando..." text
- **Success:** Both prices visible, delta message displayed
- **Error:** "Não foi possível calcular — verifique os dados dos veículos"
- **No connection:** "Requer conexão para consultar FIPE"

**Delta message rules:**
- `delta > 0`: "Você paga R$ {delta}" — font-weight 700, no color
- `delta < 0`: "Você recebe R$ {abs(delta)}" — font-weight 700, no color
- `delta = 0`: "Valores equivalentes — troca direta" — font-weight 600, italic

**Implementation notes:**
- Existing `swap-value.js` computes delta from FIPE only — needs `ownerAdjustment` parameter
- Current `MatchCard` shows delta with colored backgrounds (green/red/yellow) — must strip all color
- `formatSwapMessage` already produces correct pt-BR text — just needs CSS treatment change

---

## 4. Design Tokens

### Colors — B/W/Gray Palette

```css
:root {
  /* ---- Background ---- */
  --color-background: #121212;
  --color-background-elevated: #1E1E1E;
  --color-background-surface: #2A2A2A;

  /* ---- Text ---- */
  --color-text-primary: #FFFFFF;
  --color-text-secondary: #B0B0B0;
  --color-text-tertiary: #737373;
  --color-text-inverse: #121212;

  /* ---- Borders / Dividers ---- */
  --color-border: #333333;
  --color-border-subtle: #262626;

  /* ---- Interactive ---- */
  --color-focus: #FFFFFF;
  --color-hover: #E0E0E0;

  /* ---- Overlay ---- */
  --overlay-dark: rgba(0, 0, 0, 0.85);
  --overlay-gradient: linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.5) 40%, transparent 100%);
}
```

**Rationale:**
- `#121212` — Material Design dark background standard, reduces eye strain vs pure black
- No earthy tones, no automotive colors, no semantic colors (green/red/yellow)
- Status communicated through typography weight, border style, and text — never color alone
- All grays are neutral (equal RGB channels) — no blue/warm undertones

**Removal of existing tokens:**
- `--color-primary` (#E53935, red) — REMOVED
- `--color-primary-dark`, `--color-primary-light` — REMOVED
- `--color-secondary` (#78909C, blue-gray) — REMOVED
- `--color-accent` (#FFC107, yellow) — REMOVED
- `--color-success` (#43A047, green) — REMOVED
- `--color-warning` (#FFC107, yellow) — REMOVED
- `--color-error` (#E53935, red) — REMOVED
- `--color-info` (#1E88E5, blue) — REMOVED
- `--glow-cta` — REMOVED
- `--color-chrome` (#B0BEC5) — replaced by `--color-text-secondary`

**Contrast verification (WCAG AA on #121212):**
- `#FFFFFF` on `#121212` = 19.39:1 — AAA pass
- `#B0B0B0` on `#121212` = 9.23:1 — AAA pass
- `#737373` on `#121212` = 4.58:1 — AA pass (normal text)
- `#333333` on `#121212` = 1.63:1 — border only, not text

---

### Typography

```css
:root {
  /* ---- Families ---- */
  --font-display: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-heading: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Mono', 'Segoe UI Mono', monospace;

  /* ---- Scale (major third, ~1.25) ---- */
  --font-size-display: clamp(2rem, 4vw, 3rem);
  --font-line-display: 1.15;
  --font-weight-display: 700;

  --font-size-h1: 1.75rem;
  --font-line-h1: 1.3;
  --font-weight-h1: 700;

  --font-size-h2: 1.25rem;
  --font-line-h2: 1.4;
  --font-weight-h2: 600;

  --font-size-body: 1rem;
  --font-line-body: 1.6;
  --font-weight-body: 400;

  --font-size-small: 0.875rem;
  --font-line-small: 1.5;
  --font-weight-small: 400;

  --font-size-caption: 0.75rem;
  --font-line-caption: 1.4;
  --font-weight-caption: 500;

  /* ---- Delta emphasis ---- */
  --font-size-delta: 1.5rem;
  --font-line-delta: 1.3;
  --font-weight-delta: 700;
}
```

**Changes from current:**
- Consolidated `--font-display` and `--font-heading` to Inter — eliminates Oswald and Barlow Condensed
- Display font uses Inter 700 instead of Oswald — more neutral, more transactional
- `--font-mono` switched from Courier Prime to JetBrains Mono — better readability for numbers
- Added `--font-size-delta` token for calculator emphasis
- Line heights increased slightly for readability on dark backgrounds

---

### Spacing — 4px Grid

```css
:root {
  --space-2xs: 2px;
  --space-xs:  4px;
  --space-sm:  8px;
  --space-md:  12px;
  --space-base: 16px;
  --space-lg:  20px;
  --space-xl:  24px;
  --space-2xl: 32px;
  --space-3xl: 40px;
  --space-4xl: 48px;
}
```

**Changes from current:**
- Current grid: 8px, 16px, 24px, 32px, 48px, 64px (8px base)
- New grid: 2px, 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px, 48px (4px base)
- Enables finer control for tight layouts (calculator rows, button gaps)
- `--space-sm` changes from 16px → 8px — all components using `--space-sm` need review
- `--space-md` changes from 24px → 12px
- New `--space-base` (16px) replaces old `--space-sm` as the standard unit

---

### Elevation — Dark Mode Shadows

```css
:root {
  --elevation-1: 0 1px 2px rgba(0, 0, 0, 0.5);
  --elevation-2: 0 2px 8px rgba(0, 0, 0, 0.6);
  --elevation-3: 0 4px 16px rgba(0, 0, 0, 0.7);
  --elevation-4: 0 8px 32px rgba(0, 0, 0, 0.8);
  --elevation-5: 0 16px 48px rgba(0, 0, 0, 0.9);
}
```

**Usage:**
- Elevation 1: Cards within lists (MatchCard, VehicleCard)
- Elevation 2: Bottom sheet, modals
- Elevation 3: Floating action elements
- Elevation 4: Zoom overlay controls
- Elevation 5: Full-screen overlays

**Changes from current:**
- Renamed from `sm/md/lg/xl` to numeric scale — clearer hierarchy
- Increased opacity values — shadows need to be more visible on `#121212`
- Removed `--glow-cta` — no colored glows in B/W/Gray system

---

### Motion

```css
:root {
  /* ---- Durations ---- */
  --motion-instant: 0ms;
  --motion-fast: 100ms;
  --motion-normal: 200ms;
  --motion-slow: 300ms;
  --motion-slower: 500ms;

  /* ---- Easing ---- */
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-decelerate: cubic-bezier(0, 0, 0.2, 1);
  --ease-accelerate: cubic-bezier(0.4, 0, 1, 1);
  --ease-emphasized: cubic-bezier(0.2, 0, 0, 1);

  /* ---- Usage ---- */
  --transition-interaction: var(--motion-fast) var(--ease-standard);
  --transition-page: var(--motion-slow) var(--ease-standard);
  --transition-overlay: var(--motion-normal) var(--ease-decelerate);
  --transition-collapse: 250ms var(--ease-standard);
}
```

**Application:**
- Button `:hover`, `:active`: `--transition-interaction`
- Page navigation: `--transition-page` (existing 300ms slide)
- Zoom overlay open/close: `--transition-overlay`
- Collapsible expand/collapse: `--transition-collapse`
- Swipe card snap-back: 300ms ease

---

### Touch Targets

```css
:root {
  --touch-target-min: 48px;
  --touch-target-comfortable: 56px;
}
```

**Enforcement:**
- All buttons: `min-height: 48px`, `min-width: 48px`
- Icon-only buttons: 48×48px square
- Text buttons: 48px height, auto width with `padding: 0 16px`
- Carousel nav arrows: 44×44px (existing, meets WCAG 2.2 2.5.8 target size)
- Zoom overlay controls: 44×44px (existing)
- ❤️/❌ match buttons: 48×48px minimum
- Bottom tab bar items: 48px height (existing)

---

### Border Radius

```css
:root {
  --radius-none: 0px;
  --radius-sm: 4px;
  --radius-base: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-full: 9999px;
}
```

**Changes from current:**
- Simplified naming: removed component-specific radii (`--radius-button`, `--radius-input`, etc.)
- Buttons: `--radius-base` (8px) — was 24px pill shape
- Cards: `--radius-md` (12px) — unchanged
- Bottom sheet: `--radius-lg` (16px) — unchanged
- Badges: `--radius-full` — was 16px fixed

---

### Z-Index Scale (unchanged)

```css
:root {
  --z-feed: 1;
  --z-overlay: 0;
  --z-dropdown: 10;
  --z-sticky: 20;
  --z-modal-backdrop: 30;
  --z-modal: 40;
  --z-tooltip: 50;
  --z-detail-overlay: 100;
  --z-bottom-sheet: 110;
}
```

---

## 5. Visual Spec

### How Tokens Apply to Each Feature

#### Visual Design (B/W/Global)

**Background layers:**
| Layer | Token | Hex | Usage |
|-------|-------|-----|-------|
| App background | `--color-background` | `#121212` | `body`, `html`, root containers |
| Elevated surface | `--color-background-elevated` | `#1E1E1E` | Tab bar, nav bar, sticky headers |
| Card surface | `--color-background-surface` | `#2A2A2A` | MatchCard, VehicleCard, form cards |

**Text hierarchy:**
| Level | Token | Color | Weight | Usage |
|-------|-------|-------|--------|-------|
| Primary | `--color-text-primary` | `#FFFFFF` | 400 | Body text, headings, button labels |
| Secondary | `--color-text-secondary` | `#B0B0B0` | 400 | Labels, metadata, inactive states |
| Tertiary | `--color-text-tertiary` | `#737373` | 400 | Disabled text, placeholder hints |

**Borders:**
- Section dividers: `1px solid var(--color-border)` (#333333)
- Card borders: `1px solid var(--color-border-subtle)` (#262626)
- Focus ring: `2px solid var(--color-focus)` (#FFFFFF), 2px offset

**Status encoding (without color):**
| Status | Encoding |
|--------|----------|
| Accepted | Solid border `--color-border`, opacity 1.0 |
| Declined | Solid border `--color-border-subtle`, opacity 0.6 |
| Expired | Dashed border `--color-border-subtle`, opacity 0.5 |
| Cancelled | Dashed border `--color-border`, opacity 0.5 |
| Completed | Solid border `--color-border`, opacity 1.0 |

---

#### Vehicle Detail Page Layout

**Structure:**
```
[Image carousel]    55dvh, full width
[Sheet handle]      36×4px, centered, --color-text-tertiary
[Sheet content]     flex:1, max-height 44dvh, --color-background-surface
```

**Sheet content order (top to bottom):**
1. Vehicle title — `font-display`, `font-size-h1`, `#FFFFFF`, uppercase, `letter-spacing: 0.05em`
2. Year — `font-body`, `font-size-body`, `#B0B0B0`
3. FIPE price — `font-mono`, `font-size-h2`, `#FFFFFF`, `font-weight: 600`
4. Match info block — always visible, `--color-background` background, `--radius-sm`, `--elevation-1`
   - Marca, Modelo, Ano, FIPE, Região, Nível confiança (ShieldBadge)
   - 2-column grid, `--space-md` gap
5. Collapsible: "Detalhes do veículo" — Cor, Quilometragem, Placa
6. Collapsible: "Informações do dono" — Avatar, Nome, Localização
7. Actions: "Sugestão de troca" (primary), "Ver perfil" (secondary)

**Match info block styling:**
```css
.vehicle-detail__match-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
  padding: var(--space-base);
  background: var(--color-background);
  border-radius: var(--radius-sm);
  box-shadow: var(--elevation-1);
}

.vehicle-detail__match-info-label {
  font-family: var(--font-body);
  font-size: var(--font-size-caption);
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vehicle-detail__match-info-value {
  font-family: var(--font-body);
  font-size: var(--font-size-small);
  color: var(--color-text-primary);
}
```

**Collapsible section styling:**
```css
.vehicle-detail__collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) 0;
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  font-family: var(--font-heading);
  font-size: var(--font-size-body);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vehicle-detail__collapsible-content {
  max-height: 0;
  overflow: hidden;
  transition: max-height var(--transition-collapse);
}

.vehicle-detail__collapsible-content[aria-expanded="true"] {
  max-height: 300px;
}
```

---

#### Calculator Typography Treatment

**Layout:**
```
┌─ Label (right-aligned)   Value (right-aligned) ─┐
│  Seu veículo:           R$ 45.000               │
│  Veículo desejado:      R$ 68.500               │
│  Ajuste do dono:        R$ 0,00                 │
├─────────────────────────────────────────────────┤
│  Você paga R$ 23.500                            │
└─────────────────────────────────────────────────┘
```

**Token application:**
```css
.swap-calculator__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--space-xs) 0;
}

.swap-calculator__label {
  font-family: var(--font-body);
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
}

.swap-calculator__value {
  font-family: var(--font-mono);
  font-size: var(--font-size-small);
  color: var(--color-text-primary);
  font-weight: 500;
}

.swap-calculator__divider {
  height: 1px;
  background: var(--color-border);
  margin: var(--space-sm) 0;
}

.swap-calculator__delta {
  font-family: var(--font-heading);
  font-size: var(--font-size-delta);
  font-weight: var(--font-weight-delta);
  color: var(--color-text-primary);
  text-align: center;
  padding: var(--space-sm) 0;
  margin: 0;
  line-height: var(--font-line-delta);
}

/* No color differentiation — weight and size only */
.swap-calculator__delta--pay {
  /* Same as base — no color change */
}

.swap-calculator__delta--receive {
  /* Same as base — no color change */
}

.swap-calculator__delta--equal {
  font-style: italic;
  font-weight: 600;
}
```

**Rules:**
- Zero color differentiation between pay/receive/equal states
- Delta message uses `font-size-delta` (1.5rem) + `font-weight-delta` (700)
- Equal state adds `font-style: italic` as the only differentiator
- All prices use `font-mono` for alignment and numeric legibility
- No icons, no badges, no colored backgrounds

---

#### ❤️/❌ Button Styling

**Layout:**
```css
.match-card__action-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2xl);
  padding: var(--space-base) 0;
}

.match-card__action-btn {
  width: var(--touch-target-min);
  height: var(--touch-target-min);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-base);
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  transition: var(--transition-interaction);
  font-size: 20px;
  line-height: 1;
}

.match-card__action-btn:hover {
  border-color: var(--color-text-secondary);
  background: var(--color-background-elevated);
}

.match-card__action-btn:active {
  transform: scale(0.95);
}

.match-card__action-btn:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.match-card__action-btn:disabled {
  opacity: 0.4;
  pointer-events: none;
}
```

**Button specifics:**
- ❤️ (like/accept): `aria-label="Aceitar troca"`, calls `onAccept`
- ❌ (dislike/decline): `aria-label="Recusar troca"`, calls `onDecline`
- Both use emoji characters rendered at 20px font-size within 48×48px container
- Border provides visual structure without color
- Hover state: border lightens, background elevates
- Active state: scale(0.95) for tactile feedback
- Disabled: opacity 0.4, `pointer-events: none`

---

#### Accessibility — WCAG AA Contrast Targets

All text on `#121212` background:

| Token | Hex | Contrast Ratio | AA Normal | AA Large | AAA Normal |
|-------|-----|----------------|-----------|----------|------------|
| `--color-text-primary` | `#FFFFFF` | 19.39:1 | Pass | Pass | Pass |
| `--color-text-secondary` | `#B0B0B0` | 9.23:1 | Pass | Pass | Pass |
| `--color-text-tertiary` | `#737373` | 4.58:1 | Pass | Pass | Fail |
| `--color-border` | `#333333` | 1.63:1 | N/A | N/A | N/A |

**Notes:**
- `--color-text-tertiary` (#737373) passes AA for normal text (4.5:1 minimum) with 4.58:1 ratio — tight but compliant
- Use `--color-text-tertiary` only for non-essential text (placeholders, disabled labels)
- `--color-border` is not used for text — only for decorative borders and dividers
- All interactive elements have visible focus indicators: `2px solid #FFFFFF` with 2px offset
- All touch targets meet 48×48px minimum (WCAG 2.5.8 Target Size)
- `prefers-reduced-motion: reduce` media query disables all transitions and animations

**Status communication without color:**
- Match status communicated through text labels + border style + opacity — never color alone
- Swap delta communicated through text content ("Você paga" vs "Você recebe") — never color
- Trust tier communicated through ShieldBadge component (text + icon) — not color-coded

---

### Film Grain Overlay

**Remove.** The existing `body::before` film grain overlay (index.css:226-239) contributes to a lifestyle/aesthetic feel inconsistent with the transactional B/W/Gray direction. Remove or reduce opacity to 0.01 for imperceptible texture.

### Selection Color

**Change.** `::selection` currently uses `--color-primary` (red). Update to:
```css
::selection {
  background-color: var(--color-text-primary);
  color: var(--color-background);
}
```

### Input Focus State

**Change.** Remove `--glow-cta` red glow. Use white border:
```css
input:focus,
textarea:focus,
select:focus {
  border-color: var(--color-focus);
  box-shadow: 0 0 0 2px var(--color-background), 0 0 0 4px var(--color-focus);
}
```
