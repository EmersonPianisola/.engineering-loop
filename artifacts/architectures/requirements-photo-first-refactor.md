---
name: Requirements — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# Requirements: Photo-First Refactor

## Functional Requirements

### FR-1: VehicleCard Photo-First
- Card exibe foto full-bleed com aspect-ratio 4:5
- Overlays sobre foto: gradiente inferior, título, FIPE pill, ShieldBadge, avatar dono
- Sem seção de conteúdo separada abaixo da imagem
- Placeholder gradiente quando sem foto
- Acessibilidade: role=button, keyboard nav, aria-label

### FR-2: HomePage → Pista Feed
- HomePage exibe feed vertical infinito de VehicleCards
- Swipe right = propor match, swipe left = pular
- Header com logo + botão explore (filtros)
- Pull-to-refresh
- Skeleton loading com shimmer

### FR-3: VehicleDetail Bottom Sheet
- Carousel de fotos: 60% altura da tela
- Bottom sheet: 40% altura, scrollável
- Sheet contém: título, ano, FIPE, specs grid, owner card, CTA
- Swipe horizontal no carousel

### FR-4: Profile Gallery
- Grid 3-colunas de fotos dos veículos do usuário
- Aspect-ratio 1:1 por item
- Tap para navegar ao vehicle detail

### FR-5: Design Tokens Update
- --aspect-ratio-card: 4/5
- --radius-card: 12px
- --radius-button: 24px (pill)
- --radius-bottom-sheet: 16px
- --color-on-photo: #FFFFFF
- --elevation-xl: bottom sheet/modal
- --overlay-gradient: linear gradient inferior

## Non-Functional Requirements

### NFR-1: Performance
- LCP (Largest Contentful Paint) < 2.5s no feed
- Image lazy loading com placeholder
- Skeleton loading < 300ms após mount

### NFR-2: Responsividade
- Mobile: feed 1-coluna, full-bleed cards
- Tablet: feed 1-coluna (preservar swipe)
- Desktop: feed centralizado max-width 480px

### NFR-3: Acessibilidade
- WCAG 2.1 AA
- Keyboard navigation em todos os cards
- Reduced motion: disable swipe animation, shimmer static
- Screen reader: aria-label com brand + model + year

### NFR-4: Compatibilidade
- Manter API do VehicleCard (props: vehicle, onClick)
- Manter compatibilidade com MatchCard (usa VehicleCard)
- Firebase Storage: sem mudanças

## Volumetry
- Componentes afetados: 6 (VehicleCard, HomePage, BrowseListings, VehicleDetail, ProfilePage, tokens.css)
- Linhas de código estimadas: ~800 linhas (refatoração)
- Testes: 14 BDD scenarios

## Security
- Sem mudanças de segurança — refactor UI apenas
- Manter LGPD compliance existente
