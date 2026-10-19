# SPEC-285 — Letalidade pós-232/275/283: medir → decidir → ajustar

> **Status:** `approved` (aprovada sob a autorização do dono de 19/10 para tudo que não exige ação externa dele; a meta da §2 é decisão do coordenador sob essa autorização)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** SPEC-232 ("letalidade sobe — rebalancear"), SPEC-275 (quebra de impasse) e SPEC-283 §8 (medição 0,564 → 0,598 no playtest; 0,707 → 0,730 na arena)
> **Depende de:** SPEC-232, SPEC-275, SPEC-283 e SPEC-286 (`done`)
> **Desbloqueia:** retomada do tuning de classe (SPEC-049) sobre uma baseline limpa
> **EXECUTOR_MODEL:** `Opus` · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (toca o motor de conflito e os dados do bestiário)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Três specs recentes mudaram a letalidade sem rebalanceamento:

- **SPEC-232** fez buffs, passivas, DoT e Reações valerem de verdade, nos dois lados;
- **SPEC-275** acabou com o impasse: inimigos que ficavam inertes passaram a atacar;
- **SPEC-283** fez a IA inimiga usar Cartas de suporte (+2,3 pp na arena).

A SPEC-283 deixou um pendente: a proteção que o **jogador** põe num aliado expira
antes de qualquer ataque inimigo. O +1 de duração só valia para o lado inimigo.

Esta spec segue o modelo "medir → decidir" da SPEC-056:

1. mede com a arena e com o playtest mock;
2. fixa uma meta ancorada no histórico;
3. só mexe nos knobs que o dado condenar.

Os ajustes são determinísticos e mínimos (princípio "mecânica é Python"). Dados de
bestiário e de Carta mudam só pelo gerador oficial
(`scripts/migrate_bestiary_v4.py`).

## 2. Meta de letalidade (decisão)

O histórico do projeto tem **uma** régua aceita, a da SPEC-056:

- **R2a:** a mediana do 1º turno de queda do perfil `combate` é ≥ 20. Foi aceita
  com 23.
- **R2b:** o herói de nível 1–2, com Vitalidade cheia e fora de zona apex, tem a
  primeira janela de ação.

Não existe número aceito para "morte por combate". A âncora natural seria o estado
anterior às três specs, mas a medição mostrou que ele não serve como alvo:

| commit | playtest morte/combate (12 seeds) | observação |
|---|---|---|
| pré-232 (`afe9894`) | 0,764 | condições e passivas inertes nos dois lados; 6 de 12 campanhas presas |
| pós-232, pré-275 (`bda75fb`) | 0,468 | artificialmente baixo: 982 turnos `combat.no_progress` (inimigo inerte) |
| `main` (`866907d`) | **0,588** | — |

Por isso a meta é composta. É decisão do coordenador sob a autorização do dono.

- **M1** — No playtest `combate` (200 turnos, mock, seeds 21–32), a taxa de morte
  por combate iniciado fica **≤ 0,564**.
  - É o nível pré-283 que a própria SPEC-283 mediu. A meta cancela o aumento da
    283 e parte do da 275.
  - O aumento legítimo da 275 (inimigo que antes travava agora age) fica aceito.
- **M2** — A R2a da SPEC-056 continua valendo: mediana da 1ª queda ≥ 20. Vale nas
  seeds 21–32 e na matriz original da SPEC-056 (5 classes × `combate` × seeds
  42/43 × 50 turnos).
- **M3** — A R2b da SPEC-056 continua valendo
  (`test_heroi_cheio_early_game_reage_antes_da_emboscada`).
- **M4** — Na arena early-game (níveis 1–3, onde a SPEC-056 calibrou):
  - o encontro de Lacaio com o bot "razoável" tem taxa de morte ≤ 0,40;
  - nenhuma célula da arena piora mais de 1,5 pp.
- **M5** — Zero `combat.no_progress` em `combate --turns 200`. A parity de Cartas
  (testes existentes) fica verde.

## 3. Requisitos

- **R1 — Instrumento de medição.** `docs/spec285/arena_lethality.py` mede a morte
  por combate, offline e com seed.
  - Recorte: nível (1/3/5/8) × categoria (Lacaio/Padrão/Elite/Chefe) × 5 classes ×
    criaturas da categoria × seeds.
  - O herói sai da esteira do playtest (`_build_initial_state`): criação,
    `grant_xp`, escolhas e Cartas preparadas.
  - O encontro é o "piso" de uma espécie, como o `fill_encounter` monta até
    `encounter_budget//2`.
  - A proteção de early-game é a mesma do jogo.
  - Há dois bots: `basico` (o da arena da SPEC-283) e `cartas` ("razoável").
  - Também conta `early_deaths` (morte em ≤ 2 rodadas).
- **R2 — Medir antes de mexer.** Baseline de `main` na arena e no playtest (seeds
  21–32), mais âncoras pré-232, pré-275 e pré-283 (§2 e §8).
- **R3 — Proteção simétrica (pendente da SPEC-283).** A Carta defensiva
  (`protecao`/`buff_defesa`) que o lado do jogador põe em **outro** aliado, que
  ainda vai agir na rodada, ganha +1 turno, como a do inimigo
  (`_extend_ally_defense`). Quando o alvo é o próprio ator, nada muda.
- **R4 — O controle tático nega um turno só.**
  - O problema: o `control` (stun) dos perfis táticos (Místico/conjurador) usava
    `duration: 2`. Como o controle é observado antes do tick, cada controle negava
    **dois** turnos.
  - O efeito: com o cooldown de 2 rodadas, um único conjurador prendia o alvo em
    atordoamento contínuo. Na arena, uma luta chegou a 17 turnos perdidos. Das
    mortes de nível 1 contra Lacaio, 38 % tinham ≥ 3 turnos perdidos.
  - O ajuste: passa a `duration: 1`, que é o "controla um turno" descrito no teste
    da conflito-08. Vale para os dois lados.
- **R5 — Nenhuma Carta de inimigo mata sozinha um herói padrão cheio.**
  - A regra: o dano total de uma Carta (acerto + DoT completo) fica < 18, a
    Vitalidade de um herói com Corpo 3.
  - A única violação é `bst_toque_gelido` (5 + 5×3 = 20). Ela ignora armadura (é
    DoT) e está em 15 criaturas, inclusive o Lacaio Zumbi Blindado, a 2ª maior
    causa de morte no playtest.
  - O ajuste: passa a `dano_base 3` (3 + 9 = 12). Fica abaixo do `bst_golpe_mestre`
    (14), que é exclusivo de Elite/Chefe e custa 3.
  - A mudança é feita no gerador e travada por teste.
- **R6 — Provar a meta.** Tabelas de antes e depois (§8). Suíte completa verde.

### Fora de escopo

- **Escala de encontro no nível 5+.** A Vitalidade do herói é fixa (6 × Corpo),
  mas o orçamento do encontro cresce com o nível. No nível 5–8, grupos de 3 a 5
  Lacaios matam mais que um Chefe (§8). É uma decisão de design de progressão e
  fica para follow-up.
- **Mortes em ≤ 2 rodadas no nível 1.** Vêm de críticos de Cartas de 8–10 em
  heróis de 14–18 de Vitalidade, sobretudo no Sangromante. A R2b continua valendo:
  o herói sempre age primeiro. Fica como diagnóstico.
- **Rótulo da causa de morte.** O playtest registra o `combat_target` de um gancho
  ("criatura ligada a: Corvane…") em vez da espécie. São 35 das 120 mortes de
  `main`, e a espécie real era o Sapo-Boi Ácido. É cosmético e fica para outra
  spec.
- Economia de Entropia e knobs `[BALANCEAR]` de classe (SPEC-049).

## 4. Design técnico

- `services/conflict_orchestrator.py`
  - `_resolve_tactical_action`, ramo `control`: `duration` passa de 2 para 1 (R4).
  - `_resolve_actor_turn`: quando o ator está fora do lado inimigo, usa
    `acao.kind == "card"` e mira alguém do mesmo lado, cada `cards_used` vira um
    evento para `_extend_ally_defense` (R3). A própria função filtra o tipo
    defensivo, o alvo diferente do ator e o alvo que já agiu.
- `scripts/migrate_bestiary_v4.py`: `bst_toque_gelido` passa a
  `{"kind": "dot", "dano_base": 3, "duracao": 3}`. Regenerado, o diff em
  `data/cards/bestiario.json` é de 1 linha. O gerador é idempotente no resto.
- `docs/spec285/arena_lethality.py` (novo): o instrumento do R1. Roda também em
  commits antigos, com fallbacks locais de `template_by_id` e `_instances`.
- Sem schema novo e sem bump de save. Condições já ativas em saves carregam como
  estão.

## 5. Plano (executado)

1. **Medição:** arena em 4 commits; playtest de `main` e das âncoras.
2. **Testes** (`tests/test_spec285_lethality.py`):
   - `test_player_protection_on_ally_survives_ally_turn_this_round` (R3, vermelho
     antes da correção);
   - `test_player_protection_on_self_unchanged`;
   - `test_tactical_control_denies_exactly_one_target_turn` (R4, vermelho antes:
     3 turnos perdidos para 2 controles);
   - `test_no_enemy_card_kills_standard_hero_alone` e
     `test_toque_gelido_rebalanced_from_generator` (R5, vermelhos em `main`);
   - em `test_tactical_archetypes_runtime`, o teste do Místico passou a assertar
     que o controle nega o turno e depois expira.
3. **Implementação** e nova medição (§8).

## 6. Critérios de aceite

- [x] M1: playtest morte/combate 0,588 → **0,532** (≤ 0,564)
- [x] M2: mediana da 1ª queda 28,5 → 35 (seeds 21–32); matriz SPEC-056 22 → 24
  (≥ 20)
- [x] M3: R2b verde (`tests/test_letalidade_early.py`)
- [x] M4: arena com bot `cartas`, Lacaio no nível 1 = 0,207 e no nível 3 = 0,360
  (≤ 0,40). Nenhuma célula piora mais de 1,5 pp: a pior variação é +1,0 pp (Padrão
  nível 5, bot `cartas`), dentro do ruído.
- [x] M5: 0 `combat.no_progress` em 12 × 200 turnos; parity de Cartas e lint de
  conteúdo verdes
- [ ] Revisão independente Opus ([handoff](../handoffs/SPEC-285-review.md))
- [ ] `uv run pytest` verde (suíte completa)
- [x] Saves antigos continuam carregando (sem schema novo)

## 7. Smoke real

É opcional pelo brief e não foi executado. As mudanças são números e regras
determinísticas, sem prompt nem structured output novo, e a prosa do combate não
muda.

## 8. Evidência

Medição de 2026-10-19, com MockLLM, offline.

- **Arena:** 2.250 lutas por célula (10 seeds × criaturas da categoria × 5 classes).
- **Playtest:** perfil `combate`, Devoto do Abismo, 200 turnos, seeds 21–32.

**Arena por commit.** Taxa de morte por combate, bot `cartas`, por nível e
categoria:

| célula | pré-232 | pré-275 | pré-283 | `main` | final |
|---|---|---|---|---|---|
| L1 · lacaio | 0,361 | 0,253 | 0,283 | 0,274 | **0,207** |
| L1 · padrão | 0,470 | 0,385 | 0,522 | 0,472 | 0,458 |
| L1 · elite | 0,672 | 0,541 | 0,616 | 0,612 | 0,560 |
| L1 · chefe | 0,600 | 0,545 | 0,551 | 0,537 | 0,448 |
| L3 · lacaio ×2 | 0,567 | 0,374 | 0,423 | 0,426 | **0,360** |
| L3 · padrão | 0,270 | 0,225 | 0,325 | 0,317 | 0,297 |
| L3 · elite | 0,569 | 0,373 | 0,460 | 0,465 | 0,423 |
| L3 · chefe | 0,488 | 0,351 | 0,343 | 0,332 | 0,246 |
| L5 · lacaio ×3 | 0,802 | 0,531 | 0,619 | 0,608 | 0,575 |
| L5 · padrão ×2 | 0,627 | 0,462 | 0,623 | 0,630 | 0,640 |
| L5 · elite ×2 | 0,861 | 0,652 | 0,762 | 0,771 | 0,740 |
| L8 · lacaio ×5 | 0,802 | 0,549 | 0,635 | 0,633 | 0,607 |
| L8 · padrão ×3 | 0,740 | 0,467 | 0,742 | 0,728 | 0,722 |
| L8 · elite ×2 | 0,844 | 0,586 | 0,714 | 0,711 | 0,675 |

O bot `basico` segue o mesmo padrão. A tabela completa (32 células, com
`early_deaths`) está em [docs/spec285/README.md](../docs/spec285/README.md).

**Playtest `combate`, 200 turnos, seeds 21–32.** São 12 campanhas, nenhuma presa
depois da SPEC-286.

| medição | `main` 866907d | R3+R4 | final (R3+R4+R5) |
|---|---|---|---|
| mortes/combates iniciados | 120/204 = **0,588** | 120/204 = 0,588 | 99/186 = **0,532** |
| mediana do 1º turno de queda | 28,5 | 28,5 | **35** |
| `combat.no_progress` | 0 | 0 | 0 |

R3 e R4 não aparecem no perfil `combate`: é o Devoto solo, e nas regiões visitadas
não há conjurador nem aliado. Quem move o playtest é o R5. O Toque Gélido está nas
criaturas do Pântano, onde estão 4 das 5 maiores causas de morte.

**Matriz SPEC-056** (5 classes × `combate` × seeds 42/43 × 50 turnos):

- mediana da 1ª queda: `main` 22 → final **24**;
- mortes/combates: 17/41 = 0,415 → 13/36 = 0,361.

**Preexistente, fora de escopo.** A violação `summary.lifecycle` (`error`) aparece
em 1–2 turnos de uma campanha por rodada de medição. Está em `main` na seed 32 e
no final na seed 29, porque a campanha diverge. Não tem relação com letalidade.
