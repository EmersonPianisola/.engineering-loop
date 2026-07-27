---
name: BDD Journey — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# BDD Journey: Photo-First Refactor

## Feature: Feed de Descoberta (Pista)

### Scenario: Usuário vê feed de veículos na HomePage
**Tag:** `[unit] [e2e]`

```gherkin
Given o usuário está logado
When ele abre o app
Then ele vê um feed vertical de cards de veículos
And cada card exibe uma foto full-bleed em 4:5
And cada card exibe overlay gradiente na parte inferior
And cada card exibe título do veículo sobre a foto
And cada card exibe preço FIPE em pill sobre a foto
And cada card exibe ShieldBadge no canto superior direito
And cada card exibe avatar do dono no canto superior esquerdo
```

### Scenario: Usuário faz swipe no card do feed
**Tag:** `[e2e]`

```gherkin
Given o usuário está vendo o feed de veículos
When ele desliza um card para a direita
Then o card é marcado como "match proposto"
And o próximo card entra no feed
When ele desliza um card para a esquerda
Then o card é pulado
And o próximo card entra no feed
```

### Scenario: Feed vazio — sem veículos
**Tag:** `[unit] [e2e]`

```gherkin
Given o usuário está logado
When não há veículos compatíveis com seu perfil de desejo
Then ele vê uma mensagem "Nenhum veículo encontrado"
And um botão para ajustar filtros
```

### Scenario: Skeleton loading no feed
**Tag:** `[unit]`

```gherkin
Given o usuário está carregando o feed
Then ele vê skeleton cards com shimmer animation
And os skeletons respeitam aspect-ratio 4:5
```

## Feature: VehicleCard Photo-First

### Scenario: Card exibe foto com overlays
**Tag:** `[unit] [e2e]`

```gherkin
Given um VehicleCard com veículo com foto
Then a foto ocupa 100% do card (full-bleed)
And o aspect-ratio é 4:5
And um gradiente escuro aparece na parte inferior
And o título do veículo aparece sobre o gradiente
And o preço FIPE aparece em pill no canto inferior esquerdo
And o ShieldBadge aparece no canto superior direito
And o avatar do dono aparece no canto superior esquerdo
```

### Scenario: Card sem foto usa placeholder
**Tag:** `[unit]`

```gherkin
Given um VehicleCard com veículo sem foto
Then o card exibe um gradiente placeholder
And mantém o aspect-ratio 4:5
And os overlays permanecem visíveis
```

### Scenario: Card é clicável e acessível
**Tag:** `[unit] [e2e]`

```gherkin
Given um VehicleCard
When o usuário clica no card
Then ele navega para o detail do veículo
When o usuário pressiona Enter ou Space no card
Then ele navega para o detail do veículo
```

## Feature: VehicleDetail Bottom Sheet

### Scenario: Detail exibe carousel + bottom sheet
**Tag:** `[unit] [e2e]`

```gherkin
Given o usuário abriu o detail de um veículo
Then ele vê um carousel de fotos ocupando 60% da tela
And uma bottom sheet com 40% de altura
And a bottom sheet contém: título, ano, FIPE price
And a bottom sheet contém: specs grid (cor, km, placa, região)
And a bottom sheet contém: owner card com avatar e ShieldBadge
And a bottom sheet contém: botão "Sugestão de troca"
```

### Scenario: Carousel de fotos com swipe
**Tag:** `[e2e]`

```gherkin
Given o usuário está no vehicle detail
When ele swipa horizontalmente no carousel
Then a foto muda para a próxima/anterior
And os dots indicam a foto atual
```

### Scenario: Bottom sheet é scrollável
**Tag:** `[unit]`

```gherkin
Given o usuário está no vehicle detail
When o conteúdo da bottom sheet excede a altura disponível
Then a bottom sheet é verticalmente scrollável
And o carousel permanece fixo no topo
```

## Feature: Profile Gallery

### Scenario: Perfil exibe galeria de veículos
**Tag:** `[unit] [e2e]`

```gherkin
Given o usuário está na página de perfil
Then ele vê seus veículos em grid 3-colunas
And cada item da galeria exibe a foto principal do veículo
And cada item usa aspect-ratio 1:1
```

## Feature: Design Tokens Photo-First

### Scenario: Tokens incluem variáveis para layout photo-first
**Tag:** `[unit]`

```gherkin
Given o arquivo tokens.css
Then ele define --aspect-ratio-card como 4/5
Then ele define --overlay-gradient para gradiente inferior
Then ele define --radius-card como 12px
Then ele define --radius-button como 24px (pill)
Then ele define --radius-bottom-sheet como 16px
Then ele define --color-on-photo como #FFFFFF
Then ele define --elevation-xl para bottom sheet e modals
```

## Feature: Navegação Consolidada

### Scenario: HomePage é o feed Pista
**Tag:** `[e2e]`

```gherkin
Given o usuário está logado
When ele abre o app
Then a HomePage exibe o feed Pista (não welcome page)
And o feed inclui header com logo e botão explore
And o bottom tab bar mostra 4 tabs: Pista, Matches, Chat, Perfil
```

### Scenario: Filtros acessíveis via Explore
**Tag:** `[unit] [e2e]`

```gherkin
Given o usuário está no feed Pista
When ele clica no botão explore
Then ele vê filtros visuais (brand, year, price, region)
And filtros aplicados aparecem como pills dismissíveis
```

## Coverage Matrix

| Scenario | unit | integration | e2e |
|----------|------|-------------|-----|
| Feed vertical cards | ✓ | | ✓ |
| Swipe match/skip | | | ✓ |
| Feed vazio | ✓ | | ✓ |
| Skeleton loading | ✓ | | |
| Card full-bleed 4:5 | ✓ | | ✓ |
| Card sem foto | ✓ | | |
| Card acessível | ✓ | | ✓ |
| Detail carousel + sheet | ✓ | | ✓ |
| Carousel swipe | | | ✓ |
| Bottom sheet scroll | ✓ | | |
| Profile gallery 3-col | ✓ | | ✓ |
| Tokens photo-first | ✓ | | |
| HomePage = Pista feed | | | ✓ |
| Filtros Explore | ✓ | | ✓ |

**Total scenarios:** 14
**Unit coverage:** 10/14 (71%)
**E2E coverage:** 10/14 (71%)
**Integration coverage:** 0/14 (0%) — UI refactor, no new API contracts
