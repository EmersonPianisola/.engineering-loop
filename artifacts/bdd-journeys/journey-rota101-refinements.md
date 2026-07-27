---
name: bdd-journey-rota101-refinements
version: 1.0.0
type: bdd-journey
work_item: "Rota 101 — Refinamentos de UI e Funcionalidades"
run_id: "eng-20250726-000000"
---

# BDD Journey: Rota 101 Refinements

## Journey 1: Visual Design — Troca de Paleta B/W/Gray

### Actor
- Primary: Usuário logado (qualquer perfil)
- System: App renderiza componentes com novos design tokens

### Pre-conditions
- Usuário está logado
- App está carregado com design tokens atualizados

### Happy Path

**Scenario: Usuário visualiza paleta B/W/Gray na tela principal**
```gherkin
@e2e @visual @mobile
Given o usuário está na aba "Pista"
When o app renderiza a interface
Then o fundo principal é preto (#121212) ou próximo
And o texto padrão é branco (#FFFFFF) ou próximo
And os acentos de UI usam tons de cinza
And nenhum componente usa tons terrosos/marrom
```

**Scenario: Paleta consistente em todas as abas**
```gherkin
@e2e @visual
Given o usuário está logado
When o usuário navega entre as abas "Pista", "Veículos", "Matches", "Conversa" e "Perfil"
Then cada aba usa a mesma paleta B/W/Gray
And não há tons terrosos em nenhuma aba
```

### Alternative Paths

**Scenario: Imagens de usuário mantêm cores originais**
```gherkin
@e2e @edge-case
Given o app usa paleta B/W/Gray nos componentes de UI
When o usuário visualiza fotos de veículos enviadas por outros usuários
Then as fotos mantêm suas cores originais
And apenas os elementos de overlay (botões, labels) usam a paleta B/W/Gray
```

### Edge Cases

**Scenario: Toast e notificações seguem paleta**
```gherkin
@e2e @edge-case
Given o app usa paleta B/W/Gray
When um toast ou notificação aparece
Then o toast usa fundo preto/cinza escuro com texto branco
And não usa cores terrosas
```

**Scenario: Modais e overlays seguem paleta**
```gherkin
@e2e @edge-case
Given o app usa paleta B/W/Gray
When um modal ou overlay é aberto
Then o backdrop é semi-transparente escuro
And o conteúdo do modal usa fundo preto/cinza com texto branco
```

### Post-conditions
- Todos os design tokens atualizados para B/W/Gray
- Zero tons terrosos em componentes de UI

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Paleta na tela principal | e2e/visual | high |
| Consistência entre abas | e2e/visual | high |
| Imagens mantêm cores | e2e | medium |
| Toast/notificação | e2e | medium |
| Modais/overlays | e2e | medium |

---

## Journey 2: Vehicle Detail Page — Página de Detalhes do Veículo

### Actor
- Primary: Usuário logado navegando veículos
- Secondary: Dono do veículo listado

### Pre-conditions
- Usuário está logado
- Existem veículos listados na plataforma
- Usuário está na aba "Pista" ou "Veículos"

### Happy Path

**Scenario: Usuário abre página de detalhes ao tocar no card**
```gherkin
@e2e @mobile
Given o usuário está na aba "Pista" vendo cards de veículos
When o usuário toca em um card de veículo
Then o app navega para a página de detalhes do veículo
And a imagem principal do veículo é exibida em destaque
And as informações do match engine são visíveis: marca, modelo, ano, preço FIPE, região e trust tier
```

**Scenario: Informações prioritárias visíveis sem scroll**
```gherkin
@e2e @mobile
Given o usuário está na página de detalhes de um veículo
When a página é carregada
Then a imagem do veículo ocupa a maior área visível
And marca, modelo, ano e preço FIPE são visíveis sem scroll
And região e trust tier são visíveis sem scroll
And detalhes secundários (km, combustível, câmbio) estão em seção colapsável
```

**Scenario: Zoom em foto do veículo (mobile)**
```gherkin
@e2e @mobile
Given o usuário está na página de detalhes vendo a galeria de fotos
When o usuário faz pinch-to-zoom em uma foto
Then a foto amplia até 4× da dimensão original
And o zoom é suave e responsivo
And o usuário pode navegar pela imagem ampliada com arraste
```

**Scenario: Zoom em foto do veículo (desktop)**
```gherkin
@e2e @desktop
Given o usuário está na página de detalhes vendo a galeria de fotos
When o usuário faz scroll do mouse sobre uma foto
Then a foto amplia até 4× da dimensão original
And o usuário pode navegar pela imagem ampliada movendo o cursor
```

**Scenario: Seção colapsável de detalhes secundários**
```gherkin
@e2e @mobile
Given o usuário está na página de detalhes
When o usuário toca na seção de detalhes secundários
Then a seção expande mostrando km, combustível, câmbio e outros detalhes
And o usuário pode colapsar a seção tocando novamente
```

### Alternative Paths

**Scenario: Veículo sem fotos**
```gherkin
@e2e @edge-case
Given existe um veículo listado sem fotos
When o usuário abre a página de detalhes
Then um placeholder é exibido no lugar da galeria
And as informações do veículo (marca, modelo, ano, preço) ainda são visíveis
```

**Scenario: Imagem quebrada na galeria**
```gherkin
@e2e @edge-case
Given a página de detalhes tem galeria de fotos
When uma imagem da galeria falha ao carregar
Then um placeholder é exibido no lugar da imagem quebrada
And as demais imagens da galeria continuam acessíveis
```

**Scenario: Trust score indisponível**
```gherkin
@e2e @edge-case
Given o usuário está na página de detalhes
When o trust score do dono não está disponível
Then um placeholder "Não calculado" ou equivalente é exibido
And o resto da página renderiza normalmente
```

### Post-conditions
- Usuário pode analisar veículo em detalhes
- Informações do match engine visíveis de forma prioritária

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Navegação para detalhes | e2e | high |
| Info prioritária visível | e2e/visual | high |
| Zoom mobile (pinch) | e2e/mobile | high |
| Zoom desktop (scroll) | e2e/desktop | high |
| Seção colapsável | e2e | medium |
| Sem fotos | e2e | medium |
| Imagem quebrada | e2e | medium |
| Trust score nulo | e2e | low |

---

## Journey 3: Swap Value Calculator — Calculadora de Diferença de Swap

### Actor
- Primary: Usuário logado recebendo match
- Secondary: Outro usuário (match)
- System: Calculadora de delta FIPE

### Pre-conditions
- Usuário está logado
- Ocorreu um match bidirecional entre dois usuários
- Ambos os veículos têm preço FIPE registrado no Firestore
- Usuário está online

### Happy Path

**Scenario: Delta exibido no fluxo de match (pré-confirmação)**
```gherkin
@e2e @mobile
Given o usuário recebeu um match com outro usuário
When o usuário visualiza a tela de confirmação do match
Then o app exibe o valor FIPE do veículo do usuário
And o app exibe o valor FIPE do veículo do match
And o app exibe o delta calculado com ajuste do dono
And o app exibe "Você paga R$ X" se o veículo do match vale mais
Or o app exibe "Você recebe R$ X" se o veículo do match vale menos
```

**Scenario: Delta zero — veículos de mesmo valor**
```gherkin
@e2e @edge-case
Given o usuário recebeu um match
When os dois veículos têm o mesmo valor FIPE (com ajuste)
Then o app exibe "Valores equivalentes — sem diferença a pagar"
And não exibe "Você paga" nem "Você recebe"
```

**Scenario: Cálculo com ajuste do dono**
```gherkin
@e2e @integration
Given o veículo do usuário tem FIPE de R$ 50.000 e ajuste de +10%
And o veículo do match tem FIPE de R$ 55.000 e ajuste de 0%
When o delta é calculado
Then o valor ajustado do usuário é R$ 55.000
And o delta é R$ 0 (valores equivalentes)
```

### Alternative Paths

**Scenario: Usuário offline — calculadora indisponível**
```gherkin
@e2e @edge-case
Given o usuário recebeu um match
When o usuário está sem conexão com internet
Then o app exibe mensagem "Sem conexão — calculadora indisponível"
And o usuário ainda pode ver informações básicas do match
```

**Scenario: Veículo sem preço FIPE**
```gherkin
@e2e @edge-case
Given o usuário recebeu um match
When um dos veículos não tem preço FIPE registrado
Then o app exibe "Valor FIPE indisponível" para esse veículo
And o delta não é calculado
And o usuário pode prosseguir com o match sem o delta
```

**Scenario: Dono não definiu ajuste percentual**
```gherkin
@e2e @edge-case
Given o usuário recebeu um match
When o dono do veículo não definiu ajuste percentual
Then o app usa o valor FIPE puro (ajuste = 0%)
And o cálculo prossegue normalmente
```

### Post-conditions
- Usuário conhece o delta financeiro antes de confirmar match
- Delta calculado com transparência (FIPE + ajuste)

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Delta no fluxo de match | e2e | high |
| Delta zero | e2e | high |
| Cálculo com ajuste | unit/integration | high |
| Offline | e2e | high |
| Sem preço FIPE | e2e | medium |
| Sem ajuste do dono | unit | medium |
| Fórmula de cálculo | unit | high |

---

## Journey 4: Match UI — Botões de Like/Dislike

### Actor
- Primary: Usuário logado na aba "Pista"
- System: Motor de match, Firestore

### Pre-conditions
- Usuário está logado
- Usuário está na aba "Pista" vendo cards de veículos
- Existem veículos disponíveis para match

### Happy Path

**Scenario: Usuário dá like com botão ❤️**
```gherkin
@e2e @mobile
Given o usuário está vendo um card de veículo na aba "Pista"
When o usuário toca no botão ❤️ abaixo do card
Then o like é registrado
And o card sai da pilha com animação de like
And o próximo card aparece
And o like é salvo no Firestore
```

**Scenario: Usuário dá dislike com botão ❌**
```gherkin
@e2e @mobile
Given o usuário está vendo um card de veículo na aba "Pista"
When o usuário toca no botão ❌ abaixo do card
Then o dislike é registrado
And o card sai da pilha com animação de dislike
And o próximo card aparece
And o dislike é salvo no Firestore
```

**Scenario: Swipe right = like (comportamento mantido)**
```gherkin
@e2e @mobile
Given o usuário está vendo um card de veículo
When o usuário faz swipe para a direita no card
Then o like é registrado (mesmo comportamento do botão ❤️)
And o card sai com animação de swipe
```

**Scenario: Swipe left = dislike (comportamento mantido)**
```gherkin
@e2e @mobile
Given o usuário está vendo um card de veículo
When o usuário faz swipe para a esquerda no card
Then o dislike é registrado (mesmo comportamento do botão ❌)
And o card sai com animação de swipe
```

### Alternative Paths

**Scenario: Botão e swipe simultâneos**
```gherkin
@e2e @edge-case
Given o usuário está vendo um card
When o usuário toca no botão ❤️ enquanto faz swipe
Then apenas uma ação é registrada (não duplica)
And o card sai da pilha uma vez
```

**Scenario: Sem mais cards na pilha**
```gherkin
@e2e @edge-case
Given o usuário esgotou todos os cards disponíveis
When o usuário tenta interagir com a pilha
Then uma tela "Sem mais veículos" é exibida
And os botões ❤️/❌ ficam desabilitados
```

**Scenario: Like/dislike sem conexão**
```gherkin
@e2e @edge-case
Given o usuário está sem conexão
When o usuário toca em ❤️ ou ❌
Then a ação é enfileirada offline (offline-queue)
And é sincronizada quando a conexão retorna
```

### Edge Cases

**Scenario: Botões acessíveis (touch target)**
```gherkin
@e2e @accessibility
Given os botões ❤️ e ❌ estão visíveis
When medido o tamanho do touch target
Then cada botão tem mínimo 48×48px
And há espaço mínimo entre os botões
```

**Scenario: Botões visíveis em todas as orientações**
```gherkin
@e2e @mobile
Given o usuário está na aba "Pista"
When o usuário rotaciona o dispositivo (portrait ↔ landscape)
Then os botões ❤️/❌ permanecem visíveis e acessíveis
```

### Post-conditions
- Like/dislike registrado no Firestore
- Card removido da pilha
- Próximo card exibido

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| Like com botão | e2e | high |
| Dislike com botão | e2e | high |
| Swipe right = like | e2e | high |
| Swipe left = dislike | e2e | high |
| Ação simultânea | e2e | medium |
| Sem cards | e2e | medium |
| Offline queue | e2e/integration | medium |
| Touch target | e2e/accessibility | high |
| Orientação | e2e | low |

---

## Summary

| Journey | Scenarios | E2E | Unit | Integration |
|---------|-----------|-----|------|-------------|
| Visual Design | 5 | 5 | 0 | 0 |
| Vehicle Detail | 8 | 7 | 0 | 1 |
| Swap Calculator | 6 | 4 | 2 | 1 |
| Match UI | 9 | 8 | 0 | 1 |
| **Total** | **28** | **24** | **2** | **3** |
