# SPEC — Letalidade de early-game, 2ª passada (combate/explorador morrem nível 1–3)

> **Status:** `approved` (Etapa 1 = a rodada de playtest com o agente corrigido, EM CURSO; tuning pós-dado)
> **Criada:** 2026-07-20 · **Atualizada:** 2026-07-20
> **Depende de:** [balanceamento-early-game](balanceamento-early-game.md) `done` (1ª passada — "O Saque" + tuning spawn nível 1) ·
> [playtest-agente-curioso-entropia](playtest-agente-curioso-entropia.md) `done` (dado LIMPO de letalidade — sem o viés do agente que nunca cura/usa habilidade)
> **Desbloqueia:** confiança pra avançar tiers 5+ das classes (números base sãos)
>
> **Nota (2026-07-20):** sem código novo até o dado existir — a instrumentação já
> está pronta (summary tem `first_death_turn`/`death_location`/`death_cause`/
> `avg_hp_pct_after_combat` da spec balanceamento-early-game; o agente curioso da
> spec A remove o viés suicida). A **Etapa 1 (baseline)** é a rodada de playtest
> real desta sessão. O **tuning (Etapa 2)** só acontece DEPOIS, decidido com o
> usuário à luz dos achados ("depois do playtest decidimos o que atacar").

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
nem usam habilidade (ver [playtest-agente-curioso-entropia](playtest-agente-curioso-entropia.md)).
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

### Etapa 1 — Baseline com agente corrigido (sem tocar em número)

1. **Pré-requisito:** [playtest-agente-curioso-entropia](playtest-agente-curioso-entropia.md)
   `done` (o agente cura/usa habilidade).
2. Rodar harness (R1); tabular `first_death_turn` × classe × perfil ×
   `death_cause`/`death_location`.
3. **Decisão de gate:** se a sobrevivência já for aceitável (R2), fechar a spec
   como "era viés do harness" — documentar e parar. Senão, fixar os pisos de R2 a
   partir dessa baseline e seguir.

### Etapa 2 — Tuning cirúrgico (só o que o dado condenar)

1. **Testes** (`tests/test_fase0.py` / `test_mvp.py` / novo
   `tests/test_letalidade_early.py`): fixar o comportamento esperado do knob
   ajustado — ex.: `test_encontro_forcado_nivel1_nao_e_letal_2_rodadas`
   (encontro força 2 vs personagem HP cheio nível 1 → não morre em 2 rodadas);
   `test_apex_ainda_letal_subnivel` (regressão: apex não suavizado).
2. **Implementação:** ajustar SÓ os knobs condenados (R3); racional em comentário.
3. **Verificação:** `uv run pytest` verde.

### Etapa 3 — Regressão comparativa

1. Rodada mock pós-tuning, mesmas seeds, `report --baseline`.
2. Critérios R2 verdes; anexar diff de sobrevivência aqui.

## 5. Critérios de aceite

- [ ] Baseline com agente corrigido registrada (run_id + tabela morte×zona×causa)
- [ ] Decisão de gate documentada (era viés do harness? ou tuning real?)
- [ ] Se tuning: critérios R2 (a–c) verdes na rodada pós-ajuste, mesmas seeds
- [ ] Zonas apex inalteradas (teste de regressão)
- [ ] Cada knob mexido tem racional (constante → valor, baseline → alvo)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Saves antigos continuam carregando (stats de inimigo/mapa mudam runtime;
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
