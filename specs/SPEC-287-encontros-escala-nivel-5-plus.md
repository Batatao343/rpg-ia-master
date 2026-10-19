# SPEC-287 — Escala do encontro no nível 5+

> **Status:** `done` (revisão Opus APPROVED_WITH_FOLLOWUPS em 2026-10-19; aprovada sob a autorização do dono de 19/10 para tudo que não exige ação externa dele; a meta da §2 é decisão do coordenador sob essa autorização e o desvio "Chefe no topo" fica para o dono ratificar)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** SPEC-285 §3 "Fora de escopo" e §8 (na arena, grupos de Lacaio nos níveis 5–8 matam mais que um Chefe)
> **Depende de:** SPEC-285 (`done`), SPEC-288 (`done`)
> **Desbloqueia:** retomada do tuning de classe (SPEC-049) nos níveis 5+
> **EXECUTOR_MODEL:** `Opus` · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (toca o orçamento de encontro e os dados do bestiário)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A SPEC-285 mediu, na arena, que nos níveis 5–8 um grupo de Lacaios mata mais que
um Chefe (0,58–0,61 contra 0,25–0,27, bot `cartas`). A pergunta desta spec é onde
o modelo erra, e a correção é feita na causa, com knobs determinísticos mínimos.

**Diagnóstico** (medido com a arena e com sondas de composição fixa, §8):

1. **O herói v4 cresce no ataque, não na defesa.** A Vitalidade é Corpo + bônus
   de classe (18 no Devoto, igual do nível 1 ao 8; `progression.grant_xp`: "Vitalidade
   não escala com nível"). Virtudes sobem +1 nos níveis pares e há uma Carta por
   nível. Esse crescimento corta pela metade a letalidade contra **uma** criatura
   fixa (Chefe 0,45 → 0,25 do nível 1 ao 8), mas quase não muda a de **grupos**
   (3 Lacaios: 0,48 → 0,44).
2. **A ameaça é superlinear no número de corpos.** Cada corpo age uma vez por
   rodada contra a mesma Vitalidade. No nível 5: 1 → 2 → 3 Lacaios = 0,05 → 0,32 →
   0,56, com custo 2 → 4 → 6.
3. **O piso do orçamento conta pontos linearmente.** `fill_encounter` reforça até
   `budget//2`, e o orçamento cresce com o nível e o perigo (`BASE_BY_DANGER + nível`).
   Nos níveis 5–8 o piso vai de 6 a 9 pontos e fecha com 3–5 Lacaios ou 3 Padrões.
   Isso também quebrava a ordem Padrão < Elite nos níveis 7–8 (3 Padrões > 2 Elites).
4. **O Chefe não tem durabilidade de chefe.** A Vitalidade dele sai só da tabela de
   Corpo (máx. 16), menor que a do herói (18). Como age uma vez por rodada, cai em
   2–3 rodadas e fica *mais fácil* com o nível do herói.

As regras consolidadas (§5, §5.1) dizem que o mundo não escala com o protagonista
e que o Nível do Encontro é perigo absoluto. A correção respeita isso: nada passa a
depender do nível da party.

## 2. Meta (decisão)

Nos níveis 5–8 da arena, com os bots `cartas` e `basico`:

- **E1** — A ordem dos encontros com orçamento fica `Lacaio < Padrão < Elite`.
- **E2** — A horda de Lacaio deixa de matar mais que o Chefe: `Lacaio < Chefe`.
- **E3** — O piso de Lacaio fica na faixa do early game: ≤ 0,40 no bot `cartas`,
  como na meta M4 da SPEC-285.
- **E4** — Os níveis 1–4 da arena não mudam (idênticos célula a célula).
- **E5** — As metas M1–M5 da SPEC-285 continuam valendo.

**Desvio do pedido original, com evidência.** O pedido era a cadeia completa
`Lacaio < Padrão < Elite < Chefe` em cada nível. A parte "Chefe acima de Padrão e
Elite" fica fora, por três razões:

- **Já é falsa nos níveis 1–4** (Chefe 0,24–0,45 contra Elite 0,40–0,57), e esses
  níveis não podem piorar (E4/M4).
- **Durabilidade não basta.** Um Chefe com o triplo de Vitalidade (+36) chega a
  0,49 no nível 8, e duas ações por rodada dão 0,42, contra 0,67–0,70 de dois Elites.
  Um corpo só, agindo uma vez por rodada, não alcança um grupo de dois.
- **O design prevê o Chefe absoluto.** Pelas regras §5, uma ameaça fixa fica mais
  fácil para o veterano.

Se o dono quiser o Chefe no topo, isso é decisão de design (séquito por Nível do
Encontro ou economia de ações do Chefe) e fica para outra spec.

## 3. Requisitos

- **R1 — Economia de ações no piso.** `encounter_budget.floor_cost(enemies)` =
  custo linear dos Chefes/Nomeados + (soma dos demais) ×
  `action_economy_multiplier(n)`. O multiplicador é `1 + ACTION_ECONOMY_STEP·(n−1)`,
  com n = corpos não-chefe. `fill_encounter` mede o piso por `floor_cost`.
  `ACTION_ECONOMY_STEP = 1,25` `[BALANCEAR]` é o menor passo que fecha os pisos
  dos níveis 5–8 da arena com até 2 corpos.
- **R2 — Níveis 1–4 intactos por construção.** O piso ≤ 4 dá o mesmo número de
  corpos que a regra linear para qualquer passo ≥ 0: 1 corpo custa o mesmo, e 2
  corpos já alcançam qualquer piso ≤ 4. Isso cobre todo nível 1–4 em perigo 1–2.
  Acima disso o piso só pode ter menos corpos, nunca mais.
- **R3 — O teto não muda.** `clamp_encounter` continua linear. A horda narrada
  pela LLM segue limitada pelo orçamento atual: o risco é visível na narração (§5).
  Só o reforço sistêmico deixa de inflar.
- **R4 — Sobrevivência específica do Chefe (regras §27.3) pelo Nível do Encontro.**
  - O gerador oficial (`scripts/migrate_bestiary_v4.py`) grava
    `vitalidade_por_nivel_encontro` em toda criatura Chefe/Nomeado
    (`SOBREVIVENCIA_POR_NIVEL_ENCONTRO = 12` `[BALANCEAR]`) e remove o campo das
    demais.
  - Em runtime, `agents.bestiary.apply_encounter_survival` soma
    `campo × min(2, max(0, Nível do Encontro − 2))` à Vitalidade máxima (teto de
    2 passos: bônus de evento no Nível do Encontro não multiplica sem limite). Vale
    em `template_by_id` e no cache-hit de `generate_new_enemy`.
  - Chefe/Nomeado nunca sai como reforço aleatório: o sorteio regional
    (`world_utils.pick_encounter_enemy`) e os migrantes (`services.ecology`)
    excluem pela categoria canônica (`encounter_budget.is_boss`), não mais pelo
    texto "BOSS" do `type`. Antes, `enemy_aranha_de_cristal` (Chefe) e
    `enemy_garrick,_o_silenciador` (Nomeado) entravam como reforço sem a
    sobrevivência (achado P2-1 da revisão).
  - Nível do Encontro ≤ 2 não muda nada. Esse é todo o recorte dos níveis 1–4 da
    arena.
  - 12 é o menor valor testado (6/9/10/12) com margem ≥ 3 pp sobre o piso de Lacaio
    em todos os níveis 5–8 e nos dois bots.
- **R5 — Instrumento reproduzível.** A arena semeia o `random` global por luta. Partes
  do motor ainda usam o `random` global, e sem isso a mesma árvore dava resultados
  diferentes entre execuções. A arena também passa a calcular o tamanho do piso com
  `floor_cost` quando ele existe, e cai na regra linear em commits antigos.
- **R6 — Provar.** Tabelas de antes e depois da arena (níveis 1–8, os dois bots), o
  playtest `combate` (seeds 21–32), a matriz SPEC-056 e o playtest com
  `--start-level 5/8`. A suíte completa fica verde.

### Fora de escopo

- O Chefe acima de Padrão e Elite (§2). Fica para decisão de design do dono.
- O teto (`clamp_encounter`) com economia de ações. Mudaria os níveis 1–2 (2 Lacaios
  deixariam de caber no orçamento 4–5) e quebraria regras numéricas que a SPEC-203
  trava em teste.
- Crescimento de Vitalidade por nível. É contrário à regra "Corpo define
  Vitalidade" (decisões fechadas §Vitalidade).
- Níveis 9–20 e economia de Entropia (SPEC-049).
- `combat.no_progress` em `--start-level 5`, seed 24: 2 ocorrências, preexistentes e
  idênticas em `main` (§8). Fica como achado.

## 4. Design técnico

- `encounter_budget.py`: `ACTION_ECONOMY_STEP`, `action_economy_multiplier(bodies)`,
  `floor_cost(enemies)`, `is_boss(entry)`. `fill_encounter` usa `floor_cost` no `spent` inicial e após
  cada reforço. A assinatura pública não muda.
- `world_utils.pick_encounter_enemy` e `services/ecology.migrant_candidates`:
  filtro de Chefe/Nomeado por `is_boss`.
- `agents/bestiary.py`: `ENCOUNTER_SURVIVAL_FROM_LEVEL = 3`, `ENCOUNTER_SURVIVAL_MAX_STEPS = 2`,
  `apply_encounter_survival(data, encounter_level)` e `_ready_v4`. O helper altera
  só a cópia: o bestiário em memória não muda.
- `scripts/migrate_bestiary_v4.py`: `SOBREVIVENCIA_POR_NIVEL_ENCONTRO`, gravado em
  `migrate_creature`. Regenerado, `data/bestiary.json` ganha o campo em 13
  criaturas (12 Chefes + 1 Nomeado). O gerador é idempotente.
- `docs/spec285/arena_lethality.py`: `random.seed` por luta e `group_size` via
  `floor_cost`.
- Sem schema novo nem bump de save. Fichas de inimigo já salvas carregam como estão.

## 5. Plano (executado)

1. Medir a baseline (arena e playtest) e as sondas de composição fixa (§8).
2. Escrever os testes em `tests/test_spec287_encounter_scale.py`:
   - `test_floor_cost_*`: custo de 1 corpo linear; custo superlinear; Chefe linear
     e fora da contagem;
   - `test_levels_1_to_4_floor_unchanged` (96 casos: nível × perigo × aliados ×
     categoria) contra a regra linear (R2);
   - `test_levels_5_to_8_floor_at_most_two_bodies` e
     `test_lacaio_horde_floor_shrinks_at_level_8` (R1);
   - `test_clamp_stays_linear` (R3);
   - `test_generator_sets_survival_only_on_chefe_and_nomeado`,
     `test_template_by_id_survival_scales_from_encounter_level_3` e
     `test_generate_new_enemy_cache_hit_applies_survival`,
     `test_survival_bonus_is_capped` e `test_random_pool_excludes_boss_by_category` (R4).
3. Implementar, regenerar o bestiário pelo gerador e medir de novo (§8).

## 6. Critérios de aceite

- [x] E1: `Lacaio < Padrão < Elite` nos níveis 5–8, nos dois bots (antes, Padrão >
  Elite nos níveis 7–8)
- [x] E2: `Lacaio < Chefe` nos níveis 5–8, nos dois bots, com margem ≥ 3 pp
- [x] E3: piso de Lacaio nos níveis 5–8 com o bot `cartas` entre 0,324 e 0,363
  (antes 0,516–0,607)
- [x] E4: níveis 1–4 idênticos célula a célula, nos dois bots, com o mesmo instrumento
- [x] E5/M1: playtest `combate` 0,541 → 0,497 (≤ 0,564)
- [x] E5/M2: mediana da 1ª queda 35 → 35; matriz SPEC-056 22 → 22 (≥ 20)
- [x] E5/M3: `tests/test_letalidade_early.py` verde
- [x] E5/M4: Lacaio no nível 1 = 0,207 e no nível 3 = 0,366 (≤ 0,40); nenhuma célula
  dos níveis 1–3 muda
- [x] E5/M5: 0 `combat.no_progress` em 12 × 200 turnos; parity de Cartas e lint de
  conteúdo verdes
- [x] Revisão independente Opus ([handoff](../handoffs/SPEC-287-review.md)):
  APPROVED_WITH_FOLLOWUPS, sem P0/P1. P2-1 (Chefe/Nomeado de `type` não-BOSS como
  reforço) e P2-3 (bônus sem teto) corrigidos; P2-5 coberto por prova analítica
  revisada; P2-2 (Chefe gerado pela LLM e laboratório sem o bônus) e P2-4
  (ratificar o desvio da §2) ficam para o dono/follow-up. Depois das correções,
  playtest `combate` 12 seeds e matriz SPEC-056 deram resultado idêntico ao da
  primeira medição.
- [x] `uv run pytest` verde (suíte completa; só falhas de índice stale —
  `specs/index.yaml` e Project Index — regenerados no pouso)
- [x] Saves antigos carregam (sem schema novo)

## 7. Smoke real

Não se aplica: as mudanças são números e regras determinísticas, sem prompt nem
structured output novo. O mesmo critério valeu na SPEC-285.

## 8. Evidência

Medição de 2026-10-19, com MockLLM e offline.

**Sondas de composição fixa** (bot `cartas`, 3 seeds, taxa de morte por combate):

| nível | Lacaio ×1 / ×2 / ×3 / ×5 | Padrão ×1 / ×2 / ×3 | Elite ×1 / ×2 | Chefe |
|---|---|---|---|---|
| 5 | 0,05 / 0,32 / 0,56 / 0,67 | 0,28 / 0,67 / 0,81 | 0,43 / 0,78 | 0,21 |
| 8 | 0,07 / 0,30 / 0,47 / 0,59 | 0,21 / 0,52 / 0,70 | 0,35 / 0,70 | 0,19 |

Sondas do Chefe no nível 8 (4 seeds): +18 Vit = 0,36; +36 Vit = 0,49; duas ações
por rodada = 0,42.

**Arena** (10 seeds, 2.250 lutas por célula de grupo e 650 por célula de Chefe).
Os dois lados usam o mesmo instrumento (R5). A tabela completa, com os dois bots e
`early_deaths`, está em [docs/spec287/README.md](../docs/spec287/README.md).
Recorte do bot `cartas`, níveis 5–8, antes → depois:

| nível | Lacaio | Padrão | Elite | Chefe |
|---|---|---|---|---|
| 5 | ×3 0,582 → ×2 **0,356** | ×2 0,633 → 0,633 | ×2 0,739 → 0,739 | 0,255 → **0,432** |
| 6 | ×3 0,516 → ×2 **0,358** | ×2 0,598 → 0,598 | ×2 0,716 → 0,716 | 0,275 → **0,423** |
| 7 | ×4 0,589 → ×2 **0,363** | ×3 0,755 → ×2 **0,563** | ×2 0,705 → 0,705 | 0,269 → **0,440** |
| 8 | ×5 0,607 → ×2 **0,324** | ×3 0,728 → ×2 **0,555** | ×2 0,674 → 0,674 | 0,246 → **0,423** |

No bot `basico`, níveis 5–8, depois:

- Lacaio: 0,359–0,434
- Padrão: 0,642–0,720
- Elite: 0,726–0,783
- Chefe: 0,517–0,665

**Playtest `combate`** (Devoto, 200 turnos, seeds 21–32, nível final 3–4):

| medição | `main` 3bf6cb3 | `spec-287` |
|---|---|---|
| mortes/combates iniciados | 111/205 = 0,541 | 98/197 = **0,497** |
| mediana do 1º turno de queda | 35 | 35 |
| `combat.no_progress` | 0 | 0 |

**Por que o playtest muda se a arena 1–4 não muda.** No jogo, o herói de nível 3–4
visita regiões de perigo 3–4, onde o piso passa de 4. Ali o piso perde corpos (R2).

- Com o R4 desligado, as seeds afetadas reproduzem o mesmo resultado. Logo, quem
  move o playtest é o R1.
- O playtest de `main` é determinístico: as seeds 22, 23 e 31 repetidas deram o
  mesmo resultado.
- Em seeds divergentes, a violação preexistente `summary.lifecycle` aparece numa
  campanha a mais: seeds 29 (`main`) e 29 + 32 (branch). É o mesmo achado da SPEC-285
  §8 e não tem relação com letalidade.

**Matriz SPEC-056** (5 classes × `combate` × seeds 42/43 × 50 turnos), idêntica nos
dois lados:

- mediana da 1ª queda: 22;
- mortes/combates: 12/36.

**Playtest com `--start-level 5` e `--start-level 8`** (seeds 21–26, 200 turnos):
idêntico nos dois lados.

| nível inicial | mortes/combates | mediana da 1ª queda |
|---|---|---|
| 5 | 45/62 | 29 |
| 8 | 23/43 | 49 |

O perfil `combate` não chega a regiões de perigo 3–4 nesse horizonte. O piso fica
≤ 4 e o Nível do Encontro ≤ 2, então o loop real cai no caso que o R2 preserva.

- A seed 24 com nível inicial 5 tem 2 `combat.no_progress`, iguais em `main`
  (preexistente; §3 fora de escopo).
