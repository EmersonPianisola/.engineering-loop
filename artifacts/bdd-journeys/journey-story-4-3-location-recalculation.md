---
story: '4.3'
title: 'Localizacao Update & Match Recalculation'
type: 'bdd-journey-map'
created: '2026-07-21'
status: 'draft'
spec_ref: '_bmad-output/implementation-artifacts/spec-4-3-location-update-match-recalculation.md'
artifacts:
  - 'src/pages/ProfilePage.jsx'
  - 'src/lib/match-engine.js'
  - 'src/__tests__/match-recalculation.test.js'
---

# BDD Journey Map — Story 4.3: Localizacao Update & Match Recalculation

## Visao Geral

O usuario pode atualizar sua localizacao (UF + cidade) na pagina de perfil. Quando a UF muda, o motor de correspondencias re computa as trocas disponiveis. O usuario recebe uma notificacao com o novo numero de matches.

## Atores

| Ator | descricao |
|------|-----------|
| Usuario autenticado | Usuario com perfil criado, possivelmente com perfil de desejo e veiculos publicados |
| Motor de correspondencias | Funcao `computeMatches` em `src/lib/match-engine.js` |
| Firestore | Backend de perfil do usuario e dados de correspondencias |

---

## Journey 1: Atualizar localizacao com mudanca de UF

**Descricao:** Usuario muda o estado (UF) no perfil, salva, e o sistema re computa as correspondencias usando a nova UF como regiao primaria.

**Ator:** Usuario autenticado com perfil de desejo e veiculos publicados.

**Pre-condicoes:**
- Usuario esta logado e na pagina de perfil (`ProfilePage`).
- Perfil de desejo definido (marca, regiao, faixas de preco/ano).
- Pelo menos um veiculo publicado pelo usuario.
- Localizacao atual do perfil: UF = SP.
- Motor de correspondencias funcional (Story 4.1).

**Caminho Feliz (Happy Path):**
1. Usuario clica em "Editar" no perfil.
2. Usuario altera o campo "Estado" de SP para MG.
3. Usuario clica em "Salvar".
4. Sistema salva localizacao no Firestore via `updateProfile`.
5. Sistema detecta mudanca de UF (SP → MG).
6. Sistema chama `computeMatches` com parametro `location: { state: 'MG', city: formData.city }`.
7. Motor de correspondencias usa MG como UF primaria (override de `desire.regions[0]`).
8. Sistema compara novo total de matches com total anterior.
9. Sistema exibe notificacao de resultado.
10. Usuario ve mensagem de atualizacao e link para aba de trocas (se houver mudanca).

**Caminhos Alternativos:**
- A1: Novos matches encontrados → notificacao com contagem e link.
- A2: Menos matches → notificacao genérica com link.
- A3: Sem mudanca → notificacao informando sem alteracao.

**Casos de Borda:**
- Usuario muda UF para estado sem veiculos correspondentes → 0 matches, notificacao "Suas trocas foram atualizadas".
- Usuario muda UF para estado adjacente → Level 2 matches possiveis.

**Pos-condicoes:**
- Perfil do usuario atualizado com nova UF em Firestore.
- Matches re computados com nova UF.
- Notificacao de resultado exibida.

### Gherkin Scenarios

```gherkin
@e2e @journey-1 @happy-path
Cenario: Usuario muda de UF e novos matches sao encontrados
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario tem um perfil de desejo definido
  E que o usuario tem pelo menos um veiculo publicado
  E que o usuario possui 2 matches atuais no estado SP
  Quando o usuario clica em "Editar"
  E muda o estado de "SP" para "MG"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "MG"
  E o motor de correspondencias re computa os matches usando MG como UF primaria
  E o usuario ve a notificacao "3 novas trocas encontradas!"
  E a notificacao contem um link para a aba de trocas
```

```gherkin
@e2e @journey-1 @alternative
Cenario: Usuario muda de UF e perde matches
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario tem um perfil de desejo definido
  E que o usuario tem pelo menos um veiculo publicado
  E que o usuario possui 8 matches atuais no estado SP
  Quando o usuario muda o estado de "SP" para "AC"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "AC"
  E o motor de correspondencias re computa os matches usando AC como UF primaria
  E o usuario ve a notificacao "Suas trocas foram atualizadas"
  E a notificacao contem um link para a aba de trocas
```

```gherkin
@e2e @journey-1 @alternative
Cenario: Usuario muda de UF sem alteracao nos matches
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario tem um perfil de desejo definido
  E que o usuario possui 3 matches atuais no estado SP
  Quando o usuario muda o estado de "SP" para "RJ"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "RJ"
  E o usuario ve a notificacao "Nenhuma alteracao nas suas trocas"
```

```gherkin
@unit @journey-1 @match-engine
Cenario: computeMatches recebe parametro de localizacao e usa nova UF
  Dado que um perfil de desejo com regions ["SP"]
  E listings de veiculos em MG e SP
  E um parametro de localizacao { state: "MG", city: "Belo Horizonte" }
  Quando computeMatches e chamado com o parametro de localizacao
  Entao matches em MG sao retornados como correspondencias
  E listings apenas em SP sem adjacency nao sao retornados
```

```gherkin
@unit @journey-1 @match-engine
Cenario: computeMatches sem parametro de localizacao usa regions do desejo
  Dado que um perfil de desejo com regions ["SP"]
  E listings de veiculos em SP
  Quando computeMatches e chamado sem parametro de localizacao
  Entao matches em SP sao retornados
```

---

## Journey 2: Atualizar apenas cidade, mesmo UF

**Descricao:** Usuario altera apenas a cidade mantendo o mesmo estado. O perfil e atualizado, mas o motor de correspondencias NAO e re computado.

**Ator:** Usuario autenticado com perfil de desejo e veiculos publicados.

**Pre-condicoes:**
- Usuario logado na pagina de perfil.
- UF atual = SP, cidade atual = Sao Paulo.
- Perfil de desejo e veiculos publicados existentes.

**Caminho Feliz:**
1. Usuario clica em "Editar".
2. Usuario altera cidade de "Sao Paulo" para "Campinas" (mesmo UF SP).
3. Usuario clica em "Salvar".
4. Sistema salva localizacao no Firestore.
5. Sistema detecta que UF NAO mudou (SP → SP).
6. Sistema NAO chama `computeMatches`.
7. Sistema exibe confirmacao de localizacao salva.

**Caminhos Alternativos:**
- A1: Usuario limpa o campo cidade → perfil atualizado, sem recalucao.

**Casos de Borda:**
- Cidade vazia apos salvamento → NAO dispara recalucao.
- Cidade com espacos em branco → trim aplicado, sem recalucao.

**Pos-condicoes:**
- Perfil atualizado com nova cidade.
- Matches nao alterados.

### Gherkin Scenarios

```gherkin
@e2e @journey-2 @happy-path
Cenario: Usuario muda apenas a cidade sem alterar UF
  Dado que o usuario esta na pagina de perfil com localizacao SP, Sao Paulo
  E que o usuario tem um perfil de desejo definido
  Quando o usuario clica em "Editar"
  E muda a cidade de "Sao Paulo" para "Campinas"
  E mantem o estado como "SP"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com cidade "Campinas"
  E o motor de correspondencias NAO e re computado
  E nenhuma notificacao de trocas e exibida
```

```gherkin
@e2e @journey-2 @edge-case
Cenario: Usuario limpa o campo cidade
  Dado que o usuario esta na pagina de perfil com localizacao SP, Sao Paulo
  Quando o usuario clica em "Editar"
  E limpa o campo cidade
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com cidade nula ou vazia
  E o motor de correspondencias NAO e re computado
```

```gherkin
@unit @journey-2
Cenario: Logica de deteccao de mudanca de UF identifica UF inalterada
  Dado que a UF anterior e "SP"
  E a UF nova e "SP"
  Quando o sistema verifica se a UF mudou
  Entao o resultado e falso (UF nao mudou)
  E a recalucao de matches nao e disparada
```

---

## Journey 3: Localizacao salva mas sem perfil de desejo

**Descricao:** Usuario altera UF mas nao tem perfil de desejo definido. A localizacao e salva, mas a recalucao de matches e pulada com mensagem informativa.

**Ator:** Usuario autenticado com veiculos publicados, sem perfil de desejo.

**Pre-condicoes:**
- Usuario logado na pagina de perfil.
- Perfil de desejo NAO definido.
- Pelo menos um veiculo publicado.

**Caminho Feliz:**
1. Usuario altera UF de SP para MG.
2. Usuario clica em "Salvar".
3. Sistema salva localizacao no Firestore.
4. Sistema detecta mudanca de UF.
5. Sistema verifica ausencia de perfil de desejo.
6. Sistema NAO chama `computeMatches`.
7. Sistema exibe mensagem: "Defina seu perfil de desejo para recalcular trocas."

**Pos-condicoes:**
- Perfil atualizado com nova UF.
- Matches nao re computados.

### Gherkin Scenarios

```gherkin
@e2e @journey-3 @happy-path
Cenario: Usuario muda UF sem perfil de desejo
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario NAO tem um perfil de desejo definido
  E que o usuario tem pelo menos um veiculo publicado
  Quando o usuario muda o estado de "SP" para "MG"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "MG"
  E a recalucao de matches e pulada
  E o usuario ve a mensagem "Defina seu perfil de desejo para recalcular trocas."
```

```gherkin
@unit @journey-3
Cenario: Verificacao de perfil de desejo retorna falso para perfil nulo
  Dado que o perfil de desejo e nulo
  Quando o sistema verifica a existencia de perfil de desejo antes da recalucao
  Entao a recalucao de matches nao e disparada
```

---

## Journey 4: Localizacao salva mas sem veiculos publicados

**Descricao:** Usuario altera UF mas nao tem veiculos publicados. A localizacao e salva, mas a recalucao de matches e pulada com mensagem.

**Ator:** Usuario autenticado com perfil de desejo, sem veiculos publicados.

**Pre-condicoes:**
- Usuario logado na pagina de perfil.
- Perfil de desejo definido.
- ZERO veiculos publicados pelo usuario.

**Caminho Feliz:**
1. Usuario altera UF de SP para PR.
2. Usuario clica em "Salvar".
3. Sistema salva localizacao no Firestore.
4. Sistema detecta mudanca de UF.
5. Sistema verifica que usuario NAO tem veiculos publicados.
6. Sistema NAO chama `computeMatches`.
7. Sistema exibe mensagem: "Publique um veiculo para recalcular trocas."

**Pos-condicoes:**
- Perfil atualizado com nova UF.
- Matches nao re computados.

### Gherkin Scenarios

```gherkin
@e2e @journey-4 @happy-path
Cenario: Usuario muda UF sem veiculos publicados
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario tem um perfil de desejo definido
  E que o usuario NAO tem veiculos publicados
  Quando o usuario muda o estado de "SP" para "PR"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "PR"
  E a recalucao de matches e pulada
  E o usuario ve a mensagem "Publique um veiculo para recalcular trocas."
```

```gherkin
@unit @journey-4
Cenario: Verificacao de veiculos do usuario retorna falso para lista vazia
  Dado que a lista de veiculos do usuario e vazia
  Quando o sistema verifica a existencia de veiculos antes da recalucao
  Entao a recalucao de matches nao e disparada
```

---

## Journey 5: Falha ao salvar localizacao

**Descricao:** Usuario tenta salvar localizacao, mas ocorre erro no Firestore. Localizacao NAO e atualizada e erro e exibido.

**Ator:** Usuario autenticado.

**Pre-condicoes:**
- Usuario logado na pagina de perfil, em modo de edicao.
- Firestore indisponivel ou erro de rede.

**Caminho Feliz (caminho de erro):**
1. Usuario altera UF e/ou cidade.
2. Usuario clica em "Salvar".
3. Chamada `updateProfile` falha com erro.
4. Sistema NAO atualiza localizacao.
5. Sistema exibe mensagem de erro: "Falha ao salvar localizacao."
6. Usuario permanece em modo de edicao (pode tentar novamente).

**Casos de Borda:**
- Erro de timeout → mesmo tratamento de erro.
- Campo UF vazio ao tentar salvar → validacao inline antes da chamada ao Firestore.

**Pos-condicoes:**
- Perfil NAO alterado.
- Nenhuma recalucao disparada.

### Gherkin Scenarios

```gherkin
@e2e @journey-5 @error
Cenario: Falha ao salvar localizacao no Firestore
  Dado que o usuario esta na pagina de perfil em modo de edicao
  E que o Firestore esta indisponivel
  Quando o usuario muda o estado de "SP" para "MG"
  E clica em "Salvar"
  Entao o perfil do usuario NAO e atualizado
  E o usuario ve a mensagem de erro "Falha ao salvar localizacao."
  E o usuario permanece em modo de edicao
```

```gherkin
@e2e @journey-5 @validation
Cenario: Usuario tenta salvar com estado vazio
  Dado que o usuario esta na pagina de perfil em modo de edicao
  Quando o usuario limpa o campo estado
  E clica em "Salvar"
  Entao o perfil do usuario NAO e atualizado
  E o usuario ve o erro de validacao inline "Selecione um estado valido"
  E nenhuma requisicao ao Firestore e enviada
```

```gherkin
@unit @journey-5
Cenario: Validacao de estado vazio impede salvamento
  Dado que o campo estado esta vazio
  Quando o sistema valida o formulario antes de salvar
  Entao o salvamento e bloqueado
  E a mensagem "Selecione um estado valido" e exibida
```

---

## Journey 6: Falha ao recalcular trocas

**Descricao:** Localizacao salva com sucesso, mas a chamada ao motor de correspondencias falha. Erro e exibido ao usuario.

**Ator:** Usuario autenticado com perfil de desejo e veiculos publicados.

**Pre-condicoes:**
- Usuario logado na pagina de perfil.
- Perfil de desejo definido, veiculos publicados.
- Firestore funcional (salvamento ok).
- Motor de correspondencias falha (erro de dados, timeout, etc.).

**Caminho Feliz (caminho de erro):**
1. Usuario altera UF e salva.
2. `updateProfile` conclui com sucesso.
3. Sistema detecta mudanca de UF, tenta chamar `computeMatches`.
4. `computeMatches` lanca erro.
5. Sistema exibe mensagem: "Falha ao recalcular trocas. Tente novamente."

**Casos de Borda:**
- Dados de outros usuarios inconsistentes → erro capturado.
- Timeout na busca de listings → erro capturado.

**Pos-condicoes:**
- Perfil atualizado com nova UF.
- Matches antigos mantidos (recalucao falhou).

### Gherkin Scenarios

```gherkin
@e2e @journey-6 @error
Cenario: Recalucao de matches falha apos localizacao salva
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario tem um perfil de desejo definido
  E que o usuario tem veiculos publicados
  E que o motor de correspondencias esta falhando
  Quando o usuario muda o estado de "SP" para "MG"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "MG"
  E o usuario ve a mensagem de erro "Falha ao recalcular trocas. Tente novamente."
```

```gherkin
@integration @journey-6
Cenario: computeMatches lanca erro com dados inconsistentes
  Dado que o perfil de desejo e valido
  E que os dados de listings contem entradas corrompidas
  Quando computeMatches e chamado
  Entao uma excecao e lancada
  E o erro e capturado pela camada de apresentacao
```

---

## Journey 7: Recalucao sem mudancas

**Descricao:** Usuario muda UF, recalucao e executada, mas o numero de matches permanece o mesmo. Notificacao informando que nao houve alteracao.

**Ator:** Usuario autenticado com perfil de desejo e veiculos publicados.

**Pre-condicoes:**
- Usuario logado na pagina de perfil.
- Perfil de desejo definido.
- Veiculos publicados.
- Matches atuais = 5.

**Caminho Feliz:**
1. Usuario altera UF e salva.
2. `updateProfile` conclui com sucesso.
3. `computeMatches` re computado com nova UF.
4. Novo total de matches = 5 (igual ao anterior).
5. Sistema exibe notificacao: "Nenhuma alteracao nas suas trocas"

**Pos-condicoes:**
- Perfil atualizado.
- Matches re computados (mesmo resultado).

### Gherkin Scenarios

```gherkin
@e2e @journey-7 @happy-path
Cenario: Recalucao retorna mesmo numero de matches
  Dado que o usuario esta na pagina de perfil com localizacao SP
  E que o usuario tem um perfil de desejo definido
  E que o usuario possui 5 matches atuais
  Quando o usuario muda o estado de "SP" para "PR"
  E clica em "Salvar"
  Entao o perfil do usuario e atualizado com estado "PR"
  E o motor de correspondencias re computa os matches
  E o usuario ve a notificacao "Nenhuma alteracao nas suas trocas"
  E a notificacao NAO contem link para a aba de trocas
```

```gherkin
@unit @journey-7
Cenario: Comparacao de contagem de matches detecta sem mudanca
  Dado que o numero anterior de matches e 5
  E o novo numero de matches e 5
  Quando o sistema compara as contagens
  Entao o tipo de resultado e "unchanged"
  E a mensagem "Nenhuma alteracao nas suas trocas" e gerada
```

---

## Matriz de Casos de Borda

| # | Cenario | Tipo | Prioridade |
|---|---------|------|------------|
| E1 | UF muda, novos matches encontrados | e2e | alta |
| E2 | UF muda, menos matches | e2e | alta |
| E3 | UF muda, mesmo numero de matches | e2e | media |
| E4 | Apenas cidade muda, mesmo UF | e2e | alta |
| E5 | Cidade limpa (vazia) | e2e | media |
| E6 | Sem perfil de desejo | e2e | alta |
| E7 | Sem veiculos publicados | e2e | alta |
| E8 | Falha ao salvar localizacao (Firestore) | e2e | alta |
| E9 | Falha ao recalcular trocas | e2e | alta |
| E10 | Estado vazio — validacao inline | e2e | alta |
| E11 | computeMatches com parametro de localizacao | unit | alta |
| E12 | computeMatches sem parametro de localizacao | unit | media |
| E13 | Deteccao de UF inalterada | unit | media |
| E14 | Verificacao de perfil de desejo nulo | unit | media |
| E15 | Verificacao de lista de veiculos vazia | unit | media |
| E16 | Comparacao de contagem unchanged | unit | media |
| E17 | computeMatches com dados inconsistentes | integration | media |

---

## Tabela de Mapeamento de Testes

| Cenario | Tipo de Teste | Arquivo alvo | Tag Gherkin | Prioridade |
|---------|--------------|--------------|-------------|------------|
| UF muda, novos matches encontrados | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-1 @happy-path` | alta |
| UF muda, menos matches | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-1 @alternative` | alta |
| UF muda, sem alteracao nos matches | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-1 @alternative` | media |
| computeMatches com localizacao | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-1 @match-engine` | alta |
| computeMatches sem localizacao | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-1 @match-engine` | media |
| Apenas cidade muda | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-2 @happy-path` | alta |
| Cidade limpa | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-2 @edge-case` | media |
| Deteccao UF inalterada | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-2` | media |
| Sem perfil de desejo | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-3 @happy-path` | alta |
| Verificacao perfil de desejo nulo | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-3` | media |
| Sem veiculos publicados | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-4 @happy-path` | alta |
| Verificacao lista veiculos vazia | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-4` | media |
| Falha ao salvar localizacao | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-5 @error` | alta |
| Estado vazio — validacao | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-5 @validation` | alta |
| Validacao estado vazio | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-5` | alta |
| Falha ao recalcular trocas | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-6 @error` | alta |
| computeMatches dados inconsistentes | integration | `src/__tests__/match-recalculation.test.js` | `@integration @journey-6` | media |
| Recalucao sem mudancas | e2e | `src/__tests__/match-recalculation.test.js` | `@e2e @journey-7 @happy-path` | media |
| Comparacao unchanged | unit | `src/__tests__/match-recalculation.test.js` | `@unit @journey-7` | media |

---

## Cobertura de Critérios de Aceitacao

| # | Critério de Aceitacao (spec) | Jornada | Cenario Gherkin |
|---|------------------------------|---------|-----------------|
| AC1 | Seção localizacao visivel com campos UF/cidade preenchidos | J1 | (pre-condicao) |
| AC2 | Mudar UF SP→MG atualiza perfil e re computa matches | J1 | "Usuario muda de UF e novos matches sao encontrados" |
| AC3 | Mudar apenas cidade NAO re computa matches | J2 | "Usuario muda apenas a cidade sem alterar UF" |
| AC4 | 3 novos matches → "3 novas trocas encontradas!" com link | J1 | "Usuario muda de UF e novos matches sao encontrados" |
| AC5 | Sem novos matches → "Nenhuma alteracao nas suas trocas" | J1 / J7 | "Usuario muda de UF sem alteracao nos matches" |
| AC6 | Menos matches → "Suas trocas foram atualizadas" com link | J1 | "Usuario muda de UF e perde matches" |
| AC7 | Falha recalucao → "Falha ao recalcular trocas. Tente novamente." | J6 | "Recalucao de matches falha apos localizacao salva" |
| AC8 | Falha salvamento → "Falha ao salvar localizacao." | J5 | "Falha ao salvar localizacao no Firestore" |
| AC9 | Sem perfil de desejo → localizacao salva, recalucao pulada | J3 | "Usuario muda UF sem perfil de desejo" |
| AC10 | Sem veiculos → localizacao salva, recalucao pulada | J4 | "Usuario muda UF sem veiculos publicados" |
| AC11 | Estado vazio → validacao inline | J5 | "Usuario tenta salvar com estado vazio" |
| AC12 | Cores via CSS custom properties | N/A | (verificacao manual) |
| AC13 | Todo texto em Portugues (BR) | Todas | (verificacao manual) |

---

## Referencias

- Spec: `_bmad-output/implementation-artifacts/spec-4-3-location-update-match-recalculation.md`
- Epic: `_bmad-output/implementation-artifacts/epic-4-context.md`
- Match Algorithm Spec: `_bmad-output/implementation-artifacts/spec-4-1-match-algorithm.md`
- ProfilePage: `src/pages/ProfilePage.jsx`
- Match Engine: `src/lib/match-engine.js`
- Brazil States: `src/data/brazil-states.js`
