# SPEC-332 — Cartas #05: Baralhos de inimigo por família e facção (com padrão de intenção)

> **Status:** `in-progress` (Entrega 1 — motor + 11 famílias — pousada `off` em 27/10; Entrega 2 — 10 facções, fases dos 12 chefes, curadoria de `bst_bote_certeiro`, F-1, calibragem — na branch `spec-332`, aguardando revisão; falta só o front da SPEC-334 antes de `on`)
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
- [x] Nenhuma carta de inimigo usada por > 15 criaturas (novas: sim, seeds 0-11 testadas; `bst_bote_certeiro` (21) curada só em `on`; 1 seed em ~60 ainda passa de 15 por variância da assinatura `rasgo_aberto`)
- [~] Cada família e facção com ≥ 1 carta que **nenhuma outra** tem (11 famílias e 10 facções; 4 facções do bestiário ainda sem baralho: tribos_devoradores_sol, bandos_nomades, colmeia_hospedeiros, mercadores_escravos_pradaria — SPEC-336)
- [~] Arena por família dentro da faixa (medida; 2 células-família fora, `off` já fora em vários nichos); pytest do escopo verde

### Entrega 1 (27/10, branch spec-332) e desvios

- **Feito:** motor `services/enemy_decks.py` atrás de `RPG_ENEMY_DECKS=off|shadow|on` (default `off`, byte-idêntico);
  R1 (11 famílias x 8 cartas, `data/cards/inimigos/<familia>.json`, origem `cartas-332`, classe `Inimigo`,
  `_decks.json` com `padrao` + 2 `assinaturas` por família); R3 (próprias + 3-5 família + 0-3 facção por hash de
  `id`+seed, aplicado em `ensure_combat_sheet`); R4 (`padrao`/`assinatura` em `tactical_profile` ou default da família;
  gatilho do perfil que não é `sempre` tem precedência; perfil de apoio/flanco só recebe a assinatura; assinatura
  com `desvio` por criatura e nunca antes da rodada 2; `prenuncio` no Presságio da 329 = 1 rodada antes, campo
  `prenuncio` em `pressagios_publicos`); R5 motor de fases (`fases` no perfil: `baralho_extra`, `padrao`,
  `assinatura`, `narracao`; troca narrada em `out.logs`, invalida o presságio congelado); R6 `costuma:` no painel
  público quando `revealed_cards` existe (mesmo `bestiary_knowledge`).
- **Desvio R7:** não criei faixa de orçamento própria de inimigo; as cartas são `patamar: inicial` e passam na
  faixa `comum` existente (teste `test_new_enemy_cards_pass_vocabulary_budget_and_voice`).
- **Desvio critério 1:** "nenhuma carta usada por > 15 criaturas" vale para as cartas NOVAS (`inf_*`, testado). As
  legadas `bst_bote_certeiro` (21) e `bst_toque_gelido` (15) continuam nas criaturas do `bestiary.json` (mexer lá
  mudaria o `off`): curadoria do bestiário = próximo lote.
- **Desvio fora de escopo:** nenhuma carta/fase chama reforço (descartado pelo dono na 325 D; teste cobre).
- **Pendente (próximo lote):** R2 facções (`faccao_<id>.json`: o pool já é lido de `data/cards/inimigos/faccao_*.json`
  e `faccoes` em `_decks.json` está vazio), `fases` autoradas nos 11 chefes/54 elites, `abissal` sem criatura no
  bestiário, calibragem de `lider_matilha`/`bruto` (arena: `docs/spec332/arena-results-2026-10-27.md`) antes de `on`.

### Correções da revisão Sol (27/10)

- **P2-1/P2-2:** `apply_phases` roda também no FIM de `_run_round` (antes do forecast seguinte); a assinatura de uma
  fase nova só cai depois de uma rodada telegrafada (`fase_rnd`); com `RPG_ENEMY_INTENT` != `on` o `prenuncio` vai
  ao log narrado no fim da rodada. **P2-3:** `_deck332_shadow` (shadow) separado de `_deck332` (on); ficha
  reconstruída já montada não soma de novo; round-trip testado. **P2-4:** `deck_seed` = crc32(game_id|turno|alvo)
  gravado no spawn (`agents/combat._instances`); limite de 15 testado com ids `<base>_1`. **P2-5:** o helper do golden
  filtra pelas chaves do golden. **P2-8:** perfil `sempre`→`control` também é preservado (só a assinatura sobrepõe).
- **Follow-up P2-6:** `known_pattern` usa `revealed_cards` (por arquétipo, acende ao 1º uso de carta), não um contador
  de conflitos por família; ligar ao `bestiary_knowledge` na SPEC-334. **Follow-up P2-7:** `prenuncio`/`costuma` ainda
  não são renderizados em `web/` — front na SPEC-334 antes de `on`.

### Entrega 2 (27/10, branch spec-332) e desvios

- **R2:** 10 `data/cards/inimigos/faccao_<id>.json` x 6 cartas (`inf_fac_<id>_*`, subclasse = facção): legiao_ferro,
  mao_sombria, filhos_chama_azul, cultistas_destilacao, renegados_ermo, osshari_brekmar, druidas_renegados,
  bandos_orc_saidas_baixas, clas_combate, grupos_piratas_rivais (as 4 restantes do bestiário — tribos_devoradores_sol,
  bandos_nomades, colmeia_hospedeiros, mercadores_escravos_pradaria — ficam para a esteira da 336). Toda carta é
  exclusiva da facção; nomes conferidos contra as cartas de jogador.
- **Desvio R2:** só usam o vocabulário/efeitos já existentes (sem Fardos no baralho do jogador, sem Vigília
  compartilhada, sem Carta de Cena): "Fumo de Destilação" é um DoT, "Muralha de Escudos" uma proteção. Mecânicas novas
  entram quando a 330/331 as expuserem ao inimigo.
- **R5 fases:** `fases` dos 12 chefes em `_decks.json` (por id do bestiário/`archetype_id`; o `bestiary.json` não muda,
  logo `off` idêntico): fase 60 % (carta de apoio + padrão) e 40 % (acima do `muito_ferido` de 35 %, para o chefe solo usar a assinatura antes de fugir) (carta-assinatura própria `inf_chefe_*` em
  `chefes.json`, `a_cada_n: 2`, telegrafada). `chefes.json` não é pool de família (`_pools` só lê `FAMILIAS`).
- **Curadoria:** `legadas_compartilhadas: [bst_bote_certeiro]` — em `on`, metade das criaturas (hash id+seed) troca a
  carta por um ataque da família (`_curate_shared`). `bst_toque_gelido` (15) já cumpre "não mais que 15".
- **F-1:** a heurística de "ficha já montada" agora exige ≥ 3 cartas dos pools (o marcador `_deck332` continua decidindo).
- **Arena (amostra maior, 200 combates/célula):** [resultados](../docs/spec332/arena-results-2026-10-27.md), com o delta
  `on` - `off` por célula. `bruto` estava OK (o -18 era ruído); `lider_matilha` calibrada (mordida do alfa 8 -> 5,
  uivo 2 -> 1): L3 +3,5 / L5 -7 pp. Alvo usado: 45-85 % (decisão do coordenador); nichos fora da faixa já estavam fora no `off`.
- **Correções da revisão Sol (lote 2):** P1-1 fases 60/40 + `prenuncio` não promete com vitalidade <= 35 % ou ferimento
  grave/crítico; P1-2 a IA de suporte escolhe `cura` (si <= 70 % ou aliado ferido) e há teste de que todo efeito `inf_*`
  é alcançável; P1-3 renomeadas "Poeira do Cais" e "Corda no Passo" e o teste de nomes cobre todo o catálogo; P2: a
  troca do `bote_certeiro` entra na cota da família (sem cartas a mais) e `predador` ganhou 4 cartas (pool 12); narração
  de fase com `{nome}`, própria por chefe e uma por fase cruzada; `_pools` loga arquivo órfão.
- **P1-4 (re-revisão):** `plan()` e `prenuncio` usam o mesmo `_badly_wounded` (vida <= 35 % ou ferimento grave/crítico):
  muito ferido não joga nem anuncia a assinatura; teste do bestiário inteiro (30 % e 60 %).
- **Follow-up P2-7:** assinatura já anunciada e jogada mesmo após cair abaixo de 35 % (promessa com precedência sobre
  `plano_falhou`/`muito_ferido`) não foi feita: exige guardar a promessa no estado e mexer na precedência do perfil no
  orquestrador; fica para a SPEC-334/336 antes de `on`.
- **Pendente:** front de `prenuncio`/`costuma` (SPEC-334); conteúdo das 4 facções restantes e chefes nomeados (336);
  decisão do dono sobre o alvo da arena (nichos fracos: morto_vivo, guardiao, apex L5).

## 6. Smoke real
1. Lutar contra a Legião de Ferro: presságio de assinatura 1 rodada antes. 2. Segundo encontro com a família: padrão visível. 3. Chefe muda de fase com narração.

## 7. Riscos
- Volume de autoria: usar a esteira da SPEC-336 (rascunho por LLM + validador + curadoria).
- Dificuldade sobe sem querer: arena por família obrigatória antes de `on`.
