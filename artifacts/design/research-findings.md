---
name: research-findings
stage: design.user-research
run_id: "eng-20250726-000000"
---

# Research Findings: Rota 101 Refinements

## Insights-Chave

### 1. Paleta B/W/Gray = Ferramenta transacional, não lifestyle
O usuário rejeita tons terrosos porque associam a plataforma a algo "quente/lifestyle". Preto + branco + cinza transmite seriedade — é uma ferramenta para decisões de alto valor (troca de veículos), não um app de estilo de vida.

### 2. Calculadora = Facilitador de confiança, não conveniência
A necessidade de cálculo automático não é sobre praticidade — é sobre confiança na transação. O usuário quer saber o delta ANTES de confirmar, porque a incerteza financeira é a maior barreira para fechar um swap P2P.

### 3. Zoom em fotos = Due diligence visual
O zoom não é um "nice-to-have" — é due diligence. Em swap P2P, o usuário precisa inspecionar o veículo visualmente como faria presencialmente. Sem zoom, a confiança na transação diminui.

### 4. Botões explícitos = Controle e previsibilidade
O swipe sozinho gera ações acidentais. Botões ❤️/❌ dão ao usuário o controle de confirmar a intenção. Isso é especialmente importante em mobile, onde gestos podem ser imprecisos.

### 5. Detail page focada = Reduzir fricção de decisão
O usuário identificou que "clicar e navegar sobre o mesmo veículo cansa rápido". A info do match engine (marca, modelo, ano, preço, região, trust) precisa estar visível imediatamente — o foco é a imagem do veículo.

## Dores Identificadas

| # | Dor | Severidade | Feature que resolve |
|---|-----|------------|---------------------|
| D1 | Paleta atual não transmite seriedade automotiva | Medium | Visual Design |
| D2 | Fotos sem zoom impedem inspeção visual | High | Vehicle Detail |
| D3 | Incerteza financeira no swap | Critical | Swap Calculator |
| D4 | Swipe acidental causa frustração | Medium | Match UI |
| D5 | Navegação excessiva no mesmo veículo | High | Detail Page |
| D6 | Negociação sem referência de valor | High | Swap Calculator |

## Suposições

| # | Suposição | Risco | Validação |
|---|-----------|-------|-----------|
| A1 | Usuários preferem B/W/Gray a paletas coloridas | Medium | A/B test posterior |
| A2 | Zoom 4× é suficiente para inspeção | Low | Teste de usabilidade |
| A3 | FIPE + ajuste é modelo de preço aceitável | Medium | Feedback pós-lançamento |
| A4 | Botões + swipe não sobrecarregam a UI | Low | Teste A/B |
| A5 | Delta pré-confirmação não viésa o swipe | Medium | Métrica de conversão |
| A6 | Info do match engine é suficiente no primeiro nível | Low | Heatmap de scroll |
| A7 | Offline não é crítico para calculadora | Low | Analytics de uso |

## Contexto Competitivo

### Apps de Swap no Brasil
- **AutoTroca**: Foco em troca direta, sem calculadora de delta
- **Trokify**: Interface simples, sem zoom em fotos
- **OLX Trocas**: Sem engine de match, negociação manual

### Padrões de UI
- **Tinder-like swipe**: Padrão consolidado para decisão binária rápida
- **Botões + swipe**: Usado por Tinder, Bumble — reduz ações acidentais
- **Photo zoom**: Padrão em apps imobiliários (Zap, VivaReal) — due diligence visual

### Diferencial Rota 101
- Calculadora de delta automática: **único no mercado brasileiro**
- Match engine bidirecional: **diferencial técnico**
- Trust score integrado: **confiança P2P**

## Lacunas de Pesquisa

1. **Demografia de usuários** — Idade, renda, frequência de uso não mapeadas
2. **Taxa de conversão match → swap** — Métrica não medida
3. **Preferência de interação** — Swipe vs. botão: qual preferem?
4. **Tolerância a delta** — Quanto R$ de diferença o usuário aceita?
5. **Qualidade de fotos** — Resolução atual das imagens no Firebase Storage
6. **Uso offline** — Frequência de uso sem conexão
7. **Tempo de decisão** — Quanto tempo o usuário gasta por card?

## Síntese

Os 4 pontos de feedback convergem em uma necessidade central: **confiança transacional em decisões de alto valor P2P**. Cada feature (paleta séria, zoom para inspeção, calculadora de delta, controle de interação) contribui para reduzir a incerteza que o usuário sente ao trocar um veículo com um estranho.
