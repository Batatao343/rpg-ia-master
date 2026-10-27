# SPEC-327 — Cartas #00: Visão — o conflito de Valoria como jogo de cartas estratégico

> **Status:** `approved` (dono, 2026-10-27)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Tipo:** épico / guarda-chuva (sem código próprio; define princípios, ordem e decisões do dono)
> **Depende de:** Conflito v2 (SPEC-062–077) e SPEC-325, todas `done`
> **Desbloqueia:** SPEC-328 a SPEC-336
> **Pesquisa:** [docs/cartas/pesquisa-design-cartas-2026-10-27.md](../docs/cartas/pesquisa-design-cartas-2026-10-27.md)
> **REVIEW_MODEL:** `Astra`/`Sol` (checkpoint conceitual) + dono

---

## 1. Contexto & Objetivo

O dono quer que **a LLM monte o cenário e a batalha seja jogada como um jogo de cartas** — estratégico, claro, com muitas cartas individuais, tudo na lore de Valoria, mantendo o esqueleto atual.

**O que já está bom (fica):** mecânica 100 % Python; 2d10 + Virtude; Vitalidade/Ferimentos; Entropia/Carga/Abismo como tentação; 5 Posturas com gatilho próprio de Entropia (caldeira do Arcanista, autodano do Sangromante…); zonas/engajamento; Reações; preparação de cena pela LLM (SPEC-072); IA inimiga por perfil tático; conhecimento de bestiário.

**O que impede de "soar como jogo de cartas" (diagnóstico, HEAD `a8361681`):**
1. **Não há baralho**: 4–7 cartas preparadas fixas, as mesmas toda rodada, limitadas por frequência → é lista de magias, não mão. Uma ação principal por rodada.
2. **Decisão no escuro**: o inimigo decide na resolução; o jogador não vê o que vem.
3. **Cartas de um efeito só**: 308 cartas, 31 `kind`s, sem gatilho/condição/combo; 35 sem descrição, 80 com descrição genérica.
4. **Inimigos iguais**: 124 criaturas dividem 40 cartas; 21 predadores com a mesma.
5. **Cena passiva**: objetivos em texto livre, sem relógio, sem ambiente que age.
6. **Sem progressão entre níveis**: carta nova só no level-up; consequências (Ferimento/cicatriz) não aparecem no jogo de cartas.
7. **Leitura difícil**: resultado mecânico misturado à prosa; sem preview da chance do 2d10.

## 2. Princípios (da pesquisa)

- **P1 A decisão é a carta, não o dado.** O 2d10 modula; a escolha é *qual carta, em que ordem, guardar ou gastar* (Griftlands trocou dado por cartas porque o dado era "menos divertido").
- **P2 Quanto mais aleatório o resolvedor, mais informação antes de decidir** → Presságio + preview exato.
- **P3 Orçamento que não cobre tudo** → Fôlego 3, mão 5, descarte da sobra.
- **P4 O Abismo empresta, cobra depois** → Entropia como custo de tentação previsível (nunca autodano aleatório).
- **P5 Identidade por roda das Posturas** (o que cada uma faz / às vezes / nunca) e **raridade = complexidade**.
- **P6 Toda carta tem um momento** em que é a melhor jogada — escrito junto com a carta.
- **P7 Vocabulário pequeno e fechado** (14 palavras-chave na v1, ≤ 2 novas por onda) com tooltip.
- **P8 A LLM escolhe de catálogos e narra; as cartas decidem** (modelo Hand of Fate). Zero número inventado pela LLM; zero chamada LLM a mais por carta.
- **P9 Consequência vira carta** (Ferimento = status; cicatriz = maldição; Carga alta = Sussurro do Abismo).
- **P10 Todo conflito termina** (Relógio do Abismo) e **é medido** (taxa de uso/vitória por carta).

## 3. Mapa das specs e ordem

| Ordem | Spec | O quê | Precisa de |
|---|---|---|---|
| 1 | **SPEC-329** Presságio | intenção inimiga visível (funciona até no modo atual) | — |
| 2 | **SPEC-330** Gramática | efeitos compostos + 14 palavras-chave + texto gerado + orçamento | (grupo B após 328) |
| 3 | **SPEC-328** Baralho/Mão/Fôlego | o coração da mudança | — |
| 4 | **SPEC-334** Front | mão, pips, presságio, preview, log | 328, 329, 330 |
| 5 | **SPEC-331** Cena-tabuleiro | Cartas de Cena, objetivo com regra, Relógio | 330 |
| 6 | **SPEC-336** Esteira | draft → lint → sim → curadoria → métricas | 330 |
| 7 | **SPEC-335** Expansão onda 1 | +180 de Postura, +40 neutras, reparo das 308 | 330, 336 |
| 8 | **SPEC-332** Inimigos | baralhos por família/facção, padrão, chefes com fases | 329, 330, 336 |
| 9 | **SPEC-333** Espólio/Forja | 1 de 3 pós-luta, esquecer/afiar, Ferimento/cicatriz como carta | 328, 330, 335 |

Paralelizável: 329 ∥ 330(A) ∥ 336(lint); depois 328; conteúdo (335/332) corre em lotes junto com 331/333.

Volume ao fim da onda 1: ~308 + 15 básicas + 180 Postura + 40 neutras + ~180 inimigo + 24 cena + ~10 status ≈ **750 cartas**; com a esteira (SPEC-336 R8) ~+80/mês.

Flags: `RPG_CARD_DECK`, `RPG_ENEMY_INTENT` (`off|shadow|on`), padrão `off`; `on` no staging só com o front (SPEC-334) pronto e arena verde.

## 4. Decisões do dono

**Fechadas em 27/10:** o dono aprovou o épico ("boa, continue e execute") com as
recomendações abaixo como padrão: D1 sim (atrás de flag), D2 Fôlego 3 / mão 5,
D3 Pacto 2:1 teto 2, D4 nomes propostos, D5 roda como na tabela, D6 rodada 5,
D7 sim (recusa = 15 de ouro), D8 amostra de 20 % + 1 onda/mês, D9 ordem
Arcanista → Sangromante → Devoto → Corruptor → Médico. Tudo nasce `off`; nomes e
números podem mudar sem nova spec (dados, não código).

- **D1** Aceita trocar "preparadas fixas" por **baralho com compra** (SPEC-328)? É a mudança que mais muda a sensação. *Recomendo: sim, atrás de flag.*
- **D2** Recurso por rodada se chama **Fôlego**, 3 por rodada, mão 5? *(calibrável na arena)*
- **D3** **Pacto do Abismo**: pagar Fôlego faltante com 2 Entropia, máx. 2 por rodada?
- **D4** Nomes das 14 palavras-chave (SPEC-330 R5/R6): Rachadura, Torpor, Sangria, Vigília, Marca do Abismo, Interromper, Sacrifício, Chamado, Exaurir, Guardar, Eco, Ressoar, Fardo, Vazão. `exposto` vira Rachadura?
- **D5** Roda das Posturas (tabela na SPEC-335) — aprovar/ajustar o "Nunca" de cada uma.
- **D6** Relógio do Abismo a partir da rodada 5 (SPEC-331 R7)?
- **D7** Espólio "1 de 3" a cada vitória, recusa paga ouro (SPEC-333 R1)?
- **D8** Revisão de voz: o dono lê todas as cartas novas ou amostra de 20 %? Cadência de 1 onda/mês?
- **D9** Ordem das Posturas na expansão (SPEC-335 lotes 1–5).

## 5. Fora de escopo deste épico (ideias registradas da pesquisa, para depois)

- Conflito **social** com o mesmo motor de cartas (argumentos persistentes + compostura, Griftlands) — candidato a épico próprio.
- **Saco do caos da Entropia** (faixas de Entropia sujam/ajudam o 2d10, Arkham LCG) e **ruptura Aflição/Virtude** no máximo de Entropia (Darkest Dungeon) — avaliar depois do Fôlego estabilizar.
- Arte por carta.

## 6. Como saber que deu certo (métricas do épico)

- Playtest/staging: ≥ 2 cartas jogadas por rodada em média; ≥ 60 % das rodadas com escolha entre ≥ 3 jogadas válidas.
- Uso de cartas defensivas/controle sobe após o Presságio (log de `card_played` por `kind`).
- Nenhuma carta com uso > 60 % quando na mão; < 10 % de cartas "em branco" por onda.
- Duração p95 do conflito ≤ 10 rodadas; 1 request e 1 narração por rodada (latência não piora).
