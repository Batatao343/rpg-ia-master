# SPEC-332 — Cartas #05: Baralhos de inimigo por família e facção (com padrão de intenção)

> **Status:** `approved` (dono, 2026-10-27)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-329 (presságio), SPEC-330 (gramática), SPEC-283 (IA usa cartas de suporte)
> **Desbloqueia:** SPEC-335 (volume de conteúdo inimigo)
> **EXECUTOR_MODEL:** `Terra` (motor) + autoria por lotes · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] `data/bestiary.json` tem 124 criaturas em 10 `arquetipo`s, mas o pool de cartas de inimigo é **um só** (`data/cards/bestiario.json`, 40 cartas). 55 criaturas têm **1** carta; os 21 `predador` usam a mesma `bst_bote_certeiro`; os 15 `morto_vivo_implacavel` a mesma `bst_toque_gelido`. Resultado: lutar contra um lobo e contra um ladrão de esgoto parece igual.

[F] As facções do lore (`lore_nova/factions.txt`: Legião de Ferro, Mão Sombria, Filhos da Chama Azul, Guilda dos Corvos, Encapuzados da Fornalha, Clãs de Combate, Renegados do Ermo, Osshari de Brekmar, Bandos Orc das Saídas Baixas, Druidas do Ciclo Cinzento…) já aparecem em `bestiary.json` (`faction`), mas sem mecânica própria.

[R] Inimigo memorável = **identidade mecânica + padrão de intenção legível** (Slay the Spire: cada inimigo tem um ciclo reconhecível; o jogador aprende e planeja). Com o Presságio (SPEC-329), padrão vira conhecimento que o jogador ganha jogando — e casa com `bestiary_knowledge`.

## 2. Requisitos

- **R1** — **Baralhos de família** `data/cards/inimigos/<familia>.json`: 8–12 cartas cada, para as 10 famílias de `arquetipo` + 1 família "abissal". Mantém as 40 atuais como base comum.
- **R2** — **Baralhos de facção** `data/cards/inimigos/faccao_<id>.json`: 6–8 cartas cada, para as 10 facções com criaturas no bestiário. Identidade (proposta [D?]):
  - *Legião de Ferro* — formação: Vigília compartilhada entre aliados adjacentes; "Muralha de Escudos" (Torpor em quem ataca o da frente).
  - *Mão Sombria* — Marca + Esconder; golpe dobrado em alvo Marcado; some da cena se em desvantagem.
  - *Filhos da Chama Azul* — fanatismo: ganham dano ao perder Vitalidade; Sangria azul que gera Entropia no alvo.
  - *Encapuzados da Fornalha / Cultistas da Destilação* — inserem **Fardos** ("Fumo de Destilação") no baralho do jogador.
  - *Renegados do Ermo* — emboscada: primeira rodada sempre com vantagem; fogem com o saque.
  - *Osshari de Brekmar / piratas* — empurrão e zona: jogam o alvo para a zona alagada.
  - *Druidas do Ciclo Cinzento* — cura cíclica + Enraizado; invocam Carta de Cena (SPEC-331).
  - (demais conforme lore; o executor lê o trecho da facção por Grep, nunca o arquivo inteiro)
- **R3** — Criatura monta baralho de conflito = `cartas` próprias (assinatura) + 3–5 da família + 0–3 da facção, determinístico por `id` + seed.
- **R4** — **Padrão de intenção**: `tactical_profile` ganha `padrao: list[str]` opcional (ex.: `["ataque","ataque","reforco_proprio"]`) e `assinatura: {carta, a_cada_n}` — a carta-assinatura é **telegrafada 1 rodada antes** ("a Legionária finca o estandarte…"). Gatilhos do perfil (vida baixa, alvo vulnerável) continuam com precedência.
- **R5** — **Elites e chefes** (`BOSS` 11, `Elite` 54): chefes têm **fases** (`fases: [{ate_vitalidade_pct, baralho_extra, padrao}]`) — troca de fase narrada e presságio novo.
- **R6** — Conhecimento: após 1 conflito com a família, o jogador vê o `padrao` como "costuma: ataque, ataque, reforço" no painel (SPEC-334). Reaproveita `bestiary_knowledge` (nível conhecido/estudado).
- **R7** — Toda carta nova passa no validador + orçamento de poder (SPEC-330 R9) com faixa própria de inimigo.

### Fora de escopo
Novas criaturas (só cartas e padrões para as 124 existentes). Inimigos com mão/Fôlego (o inimigo continua escolhendo por perfil; o baralho é o repertório).

## 3. Design técnico
- **Novo** `services/enemy_decks.py`: `build_enemy_deck(creature, seed) -> list[str]`, `next_intent(creature, round, scene_state) -> str` (padrão + gatilhos).
- **Alterado** `services/tactical_profile.py` (`padrao`, `assinatura`, `fases`), `conflict_orchestrator._enemy_offensive_card/_enemy_support_card` passam a escolher dentro do baralho montado.
- **Novo** `data/cards/inimigos/*.json` (~11 × 10 + 10 × 7 ≈ **180 cartas**).

## 4. Plano (TDD)
1. Motor: `tests/test_enemy_decks.py` — montagem determinística; padrão respeitado; gatilho do perfil tem precedência; assinatura telegrafada.
2. Fases de chefe: `tests/test_boss_phases.py`.
3. Conteúdo em 3 lotes (famílias → facções → chefes), cada lote validado + arena por família (taxa de vitória do jogador por família entre 45–85 % no nível-alvo).

## 5. Critérios de aceite
- [ ] Nenhuma carta de inimigo usada por > 15 criaturas
- [ ] Cada família e facção com ≥ 1 carta que **nenhuma outra** tem
- [ ] Arena por família dentro da faixa; `uv run pytest` verde

## 6. Smoke real
1. Lutar contra a Legião de Ferro: presságio de assinatura 1 rodada antes. 2. Segundo encontro com a família: padrão visível. 3. Chefe muda de fase com narração.

## 7. Riscos
- Volume de autoria: usar a esteira da SPEC-336 (rascunho por LLM + validador + curadoria).
- Dificuldade sobe sem querer: arena por família obrigatória antes de `on`.
