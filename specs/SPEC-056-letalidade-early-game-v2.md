# SPEC — Letalidade de early-game, 2ª passada (combate/explorador morrem nível 1–3)

> **Status:** `done`
> **Criada:** 2026-07-20 · **Atualizada:** 2026-08-02 (rebase v4 + regressão mock/real concluída)
> **Depende de:** [balanceamento-early-game](SPEC-034-balanceamento-early-game.md) `done` (1ª passada — "O Saque" + tuning spawn nível 1) ·
> [playtest-agente-curioso-entropia](SPEC-059-playtest-agente-curioso-entropia.md) `done` (dado LIMPO de letalidade — sem o viés do agente que nunca cura/usa habilidade)
> **Desbloqueia:** confiança pra avançar tiers 5+ das classes (números base sãos)
> **Interage com:** [checkpoints-morte](SPEC-060-checkpoints-morte.md) (C — modelo de morte/restore substitui a "2ª chance com poção" do Saque)
>
> **Nota (2026-07-20):** Etapa 1 (baseline) FECHADA com o run `20260720-093014`
> (17 campanhas reais, agente curioso ativo). Achado dominante: **letalidade NÃO
> é dano alto — é AUSÊNCIA de recovery.** Combate/explorador perambulam a ~40% HP
> por 5–7 turnos sem curar nada (viagem não cura; descanso em zona de perigo é
> interrompido por encontro), entram em luta a 10–12 HP e morrem. Quester
> sobrevive só porque EVITA combate. Ver Etapa 1 abaixo. O usuário decidiu 4
> alavancas (Etapa 2), todas determinísticas.

---

## 1. Contexto & Objetivo

O playtest longo (`run_id 20260719-160014`, 15 campanhas reais) mostra que a
letalidade de early-game NÃO foi resolvida pela 1ª passada. Perfis de combate
direto morrem cedo:

| perfil | faixa de morte | nível na morte |
|---|---|---|
| combate | t7–t30 | 1–3 |
| explorador | t22–t30 | 1–3 |
| quester | t67–t70 (2 sobreviveram 70) | 3–4 |

O quester sobrevive **~3× mais** porque o ciclo de quest o mantém em loops
relativamente seguros; combate/explorador buscam perigo direto e caem. Mortes
concentradas: **Pântano da Melancolia / Profundezas** (Sapo-Boi Ácido, Zumbi
Blindado, Afogado), **montanhas/farol** (Yeti, Troll de Ponte, Lobo das
Geleiras), **Nova Arcádia / forja** (Vulto da Forja, Capanga da Legião).

A 1ª passada (`balanceamento-early-game`) já introduziu `forced_encounter_danger`
(a FORÇA de um encontro forçado escala com o nível, teto `(lvl+3)//2` — nível 1
= força 2) e "O Saque". Mesmo assim o combate direto no início mata. **Objetivo:
2ª passada com o dado deste run** — decidir, por invariante e não por vibe, se o
early-game é letal por design aceitável (combate direto SEM cura é arriscado, ok)
ou por tuning quebrado (dano por golpe / número de inimigos / gatilho de encontro
alto demais pra HP de nível 1).

**Pré-requisito de método:** parte da letalidade observada é **viés do harness** —
os perfis `combate`/`fujao` buscam o nó de MAIOR perigo todo turno e nunca curam
nem usam habilidade (ver [playtest-agente-curioso-entropia](SPEC-059-playtest-agente-curioso-entropia.md)).
Julgar o tuning com esse agente superestima a letalidade. Esta spec **depende do
agente curioso** para separar "morre porque o jogo é injusto" de "morre porque o
bot joga mal". A 1ª rodada de dado desta spec usa o harness já corrigido.

Princípio: **"Mecânica é Python"** — todo ajuste é constante determinística
(dano/tier/quantidade/gatilho), verificável por invariante do harness.

## 2. Requisitos

- **R1 — Medir com agente corrigido primeiro.** Rodar o harness pós-agente-curioso
  (combate/explorador/fujao × 5 classes × ≥2 seeds × ≥50 turnos, mock + real
  curto) e registrar a nova baseline de sobrevivência ANTES de mexer em número.
  Se a sobrevivência subir para faixa aceitável só com o agente curando/usando
  habilidade, o "bug" era o harness — documentar e fechar sem tuning.
- **R2 — Critério objetivo de letalidade aceitável (vira assert):**
  - a) mediana de turnos-até-1ª-morte de um perfil de combate direto jogando
    "razoável" (cura quando pode, usa habilidade) ≥ um piso a definir na Etapa 1
    a partir da baseline (ex.: ≥ 20 turnos / nível ≥ 3), não t7;
  - b) nenhum encontro de nível 1–2 em zona NÃO-apex mata um personagem em HP
    cheio em ≤2 rodadas sem o jogador ter chance de reagir (fugir/curar/usar
    habilidade);
  - c) 2ª queda deliberada sem recurso segue podendo matar (design de "O Saque"
    preservado — não é regressão).
- **R3 — Ajustes candidatos (só os que o dado condenar):**
  - teto de dano-por-golpe de inimigo comum vs HP de nível 1–2;
  - `encounter_budget` / número de inimigos por encontro forçado em nível 1–2;
  - gatilho de encontro (`check_encounter`: `danger >= 4` embosca; cooldown
    `_ENCOUNTER_COOLDOWN`) — frequência cedo demais;
  - `forced_encounter_danger` — reavaliar o teto `(lvl+3)//2` se o dado mostrar
    que força 2 ainda mata nível 1.
  Cada knob mexido ganha racional na `note`/comentário do código
  (constante → valor, baseline X → Y).
- **R4 — Zonas apex preservadas.** Nada nesta spec suaviza zona `apex`
  (endgame/proibida): sub-nível lá DEVE morrer (é o sinal "você não pertence
  aqui"). O ajuste é só das zonas normais de early-game.
- **R5 — Regressão.** Rodada mock pós-tuning com as MESMAS seeds comparada via
  `report --baseline`; critérios R2 verdes; suíte offline verde (testes que fixam
  stats de inimigo/encontro atualizados junto).

### Fora de escopo

- **Economia de Entropia / balanceamento de classe** — spec de balanceamento +
  agente curioso. Aqui só spawn/encontro/dano de inimigo de early-game.
- **Rebalance global de XP/economia/loot** — fora; só o que trava a
  sobrevivência de nível 1–3.
- **"O mundo não puxa o jogador" / exploração não recompensa** — achados de
  imersão do playtest de 2026-07-14, spec própria se o usuário quiser; não é
  letalidade.
- **Tiers 5+ das classes** — fast-follow, depois de a base estar sã.
- **Comportamento do agente de teste** — é a spec-dependência, não esta.

## 3. Design técnico

**Arquivos candidatos (confirmar pelo dado antes de editar):**

- `world_utils.py`
  - `forced_encounter_danger(loc, danger_real, player_level)` (l.593) — teto de
    força por nível.
  - `check_encounter(...)` (l.607) — gatilho determinístico + `_ENCOUNTER_COOLDOWN`.
  - `pick_encounter_enemy` / `encounter_budget` — criatura e quantidade.
- `combat_mechanics.py` — resolução de dano; teto de dano-por-golpe de inimigo
  comum (se existir; senão o ajuste é nos stats do bestiário).
- `data/bestiary.json` — stats dos inimigos de early-game que concentram morte
  (Sapo-Boi Ácido, Zumbi Blindado, Afogado, Yeti, Troll de Ponte, Lobo das
  Geleiras). Grep por id/nome; NÃO ler o arquivo inteiro.
- `data/world_map.json` — `danger` dos nós de early-game (Pântano/montanhas/forja).
- `data/classes.json` (gerado) — HP base de nível 1 por classe, se o dado mostrar
  que uma classe específica é injustamente frágil (mas cuidado: é território da
  spec de balanceamento; coordenar).

**Fonte de verdade da métrica:** o `summary.json` do harness já traz
`first_death_turn`, `death_location`, `death_cause`, `avg_hp_pct_after_combat`,
`downed_count` (spec balanceamento-early-game R5) — esta spec CONSOME esses
campos, cruzando com `death_location`/`death_cause` para achar o inimigo/zona
culpados. Nenhuma telemetria nova necessária além da que o agente-curioso já
adiciona.

## 4. Plano passo a passo

### Etapa 1 — Baseline com agente corrigido — `done` (run `20260720-093014`)

17 campanhas reais (5 classes × {combate,explorador,quester} + comerciante +
recrutador), agente curioso ativo, **0 erro de motor, $1.74**.

| perfil | sobrevivência | nível na morte | causa dominante |
|---|---|---|---|
| combate (5 classes) | **todas morreram** t19–47 | 2–3 | luta a HP baixo, sem recovery |
| explorador (5 classes) | **todas morreram** t16–31 | 1–3 | one-shot em zona high-danger + sem recovery |
| quester/recrutador/comerciante | vivos t60 | 3–4 (com.=1) | evitam combate |

**Diagnóstico (dos logs `*.jsonl`):** HP fica TRAVADO (ex.: `combate_sangromante`
12/31 do t11→t16; `explorador_arcanista` 12/26 do t8→t14). Viagem não cura;
descanso em zona de perigo dispara `check_encounter` (danger≥4) e vira combate
antes de curar. O jogo hoje só é sobrevivível NÃO lutando → o combate cedo não
tem laço de recuperação. **Gate: é tuning real, não viés do harness.**

### Etapa 2 — Tuning (4 alavancas decididas pelo usuário) — `done`

Todas determinísticas ("mecânica é Python"). Constantes novas ganham racional
`baseline → alvo` no comentário.

**Alavanca 1 — Descanso/viagem recuperam (o laço que falta).**
- `world_utils`: novas constantes `EARLY_GAME_LEVEL = 3`, `RECOVERY_SAFE_DANGER = 3`.
- **Descanso confiável no early-game:** no path de REST do storyteller, se
  `player.level ≤ EARLY_GAME_LEVEL` e zona **não-apex** e `danger_now ≤
  RECOVERY_SAFE_DANGER` → encontro SUPRIMIDO (`enc = None`), o descanso cura.
  (Zona apex ou danger 4+ segue rolando — quem descansa na boca do lobo aceita o
  risco.) Reusa a mesma lógica do `downed_grace` já existente.
- **Cadência de encontro na viagem escala com nível:** `check_encounter` passa a
  respeitar cooldown **maior** no early-game (`_early_cooldown(player_level)`:
  nível ≤3 → cooldown +2 turnos) → menos combate forçado de volta-a-volta,
  espaço pra viajar/curar entre lutas. Não zera perigo — só espaça.

**Alavanca 2 — Mais poções iniciais** (gerador `scripts/gen_classes_v2.py`,
`starting_equipment`): cada classe +1 `pocao_cura` (Devoto/Sangromante/Corruptor/
Arcanista → 2; Médico → 3). Regenera `data/classes.json`.

**Alavanca 3 — Mais Vitalidade em nível baixo** (rebase v4): `base_stats.hp`
deixou de ser fonte de verdade no cutover de Cartas. O gerador agora grava
`base_stats.vitalidade_bonus = 6`; `gamedata.sync_vitality` soma esse bônus à
tabela de Corpo somente para as cinco classes canônicas. Pisos finais: Devoto,
Sangromante e Corruptor **18**; Médico **16**; Arcanista **14**. Saves v5 recebem
o novo teto preservando o dano já sofrido.

**Alavanca 4 — Mais dano em nível baixo** (runtime, `combat_mechanics`): novo
`early_game_damage_bonus(level)` — +2 no dano do golpe do jogador em nível 1–2,
+1 no nível 3, **0 do nível 4+** (some ao crescer). Aplicado só ao ataque do
JOGADOR (inimigo não ganha), no cálculo de dano de `resolve_player_action`.

> **Fora desta spec, vai pra C:** a "2ª chance com poção" do Saque
> (`apply_downed` deixa 1 poção) é substituída pelo modelo de **checkpoint +
> restore** da spec [checkpoints-morte](SPEC-060-checkpoints-morte.md). Aqui só o
> early-game survivability; a mecânica de morte/continue é C.

**Testes** (`tests/test_letalidade_early.py` novo + `test_fase0`/`test_mvp`
ajustados):
- `test_descanso_early_game_zona_segura_nao_dispara_encontro` (nível ≤3, danger ≤3, não-apex → `enc None`).
- `test_descanso_apex_ainda_dispara` (regressão R4).
- `test_early_damage_bonus_soma_no_golpe_do_jogador` + `test_early_damage_bonus_zera_nivel_4`.
- `test_early_damage_bonus_nao_afeta_inimigo`.
- `test_cooldown_encontro_maior_no_early_game`.
- classes: `test_hp_base_pisos_novos`, `test_starting_equipment_pocoes` (contra `classes.json` regenerado).

### Etapa 3 — Regressão comparativa

1. Rodada mock pós-tuning, mesmas seeds; suíte offline verde.
2. **Smoke real:** `combate --class sangromante --real --turns 30` — sobrevive
   além de t19 (baseline), com descanso curando e poção sobrando.
3. Re-run real curto de validação (combate × 2–3 classes) e comparar
   `first_death_turn` com o baseline `20260720-093014`.

## 5. Critérios de aceite

- [x] Baseline com agente corrigido registrada (run_id + tabela morte×zona×causa)
- [x] Decisão de gate documentada (era viés do harness? ou tuning real?)
- [x] Se tuning: critérios R2 (a–c) verdes na rodada pós-ajuste, mesmas seeds
- [x] Zonas apex inalteradas (teste de regressão)
- [x] Cada knob mexido tem racional (constante → valor, baseline → alvo)
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Saves antigos continuam carregando (stats de inimigo/mapa mudam runtime;
      sem migração de schema)

## 6. Smoke test com LLM real

1. `uv run python -m playtest run --profile combate --class devoto_do_abismo
   --real --turns 30 --max-cost 0.05` — o personagem sobrevive além da faixa
   t7–t9 do baseline atual, jogando razoável (cura/habilidade).
2. Um turno de API real entrando numa zona de early-game (Pântano) em nível 1:
   o encontro forçado aparece mas não é one-shot; o jogador tem turno pra reagir.
3. Regressão de "O Saque": forçar 2ª queda sem cura → morte definitiva ainda
   ocorre (design preservado).

## 7. Riscos & compatibilidade

- **Saves antigos:** ajustes vivem em `data/*.json` + constantes de
  `world_utils`/`combat_mechanics`, lidos em runtime. Personagem existente passa
  a usar os números novos ao carregar — desejado, sem migração.
- **MockLLM:** combate mock é raso (só ataque básico) → a letalidade real só se
  mede em `--real` com o agente curioso. Mock serve de regressão relativa.
- **Risco de over-nerf:** suavizar demais mata a tensão do early-game. Mitigar
  com R2c (2ª queda ainda mata) e R4 (apex intacto); alvo é "morte evitável com
  jogo razoável", não "invulnerabilidade".
- **Acoplamento com a spec de balanceamento:** HP base de classe é knob
  compartilhado. Se o dado apontar pra HP de classe, coordenar com
  `balanceamento-classes-pos-playtest` em vez de editar `gen_classes_v2.py` em
  paralelo (conflito de gerador).
- **Quota/custo:** rodadas reais com teto (~$0.05 DeepSeek).

## 8. Registro de execução final — 2026-08-02

**Rebase e correções.** Além das quatro alavancas, o gate revelou três defeitos
do harness/integração que distorciam a métrica: o perfil só descansava depois de
ficar inconsciente, não evacuava interiores cujo primeiro passo tinha o mesmo
perigo e só curava em combate abaixo de 30%. O perfil razoável agora busca
recuperação abaixo de 50%, aceita o primeiro passo de evacuação e cura abaixo de
50% também durante conflito. Fuga estruturada passou a ter precedência sobre o
parser textual do router (interior não é mais reduzido ao nó-pai). Personagem
nível 1–2, cheio e fora de apex recebe a primeira janela de ação; ferido, nível
3+ e apex preservam a iniciativa normal.

**Regressão mock final.** Matriz de 30 campanhas (5 classes × combate/
explorador/fujão × seeds 42/43 × 50 turnos): **1.500 turnos, 0 erros, 0
violações `error`**; mediana da primeira queda do perfil combate = **23** (piso
R2a = 20). Replays focados corrigiram o antigo falso positivo
`action.declaration_matches` de fuga para interiores. Testes determinísticos
cobrem descanso seguro/apex, cooldown, dano inicial, Vitalidade/poções, migração,
primeira reação e memorial após queda (R2b–c/R4).

**Smoke real aceito.** `20260802-175310-716794`, Sangromante/combate/seed 42:
30/30 turnos, primeira queda **t29** (baseline t19), 0 erros, 0 violações,
`mock=false`, 78 tentativas/77 sucessos reais, custo **US$ 0,02198**, gasto de
Entropia 4, habilidade ativa em 42,1% dos turnos de combate e Carga pico 4. Uma
falha de conexão isolada foi absorvida pelo roteamento. Runs diagnósticos
`20260802-173822-641785` (queda t18: descanso em perigo 4) e
`20260802-174601-475598` (queda t14: cura tardia) foram rejeitados e originaram
as correções acima.
