# SPEC — Janela de recuperação pós-Saque

> **Status:** `done` (2026-07-18 — 835 offline verdes; harness mock 3 seeds 0
> violações de recuperação, sobrevivência muito além do baseline 1-4t; smoke §6
> real: poção + beat + narração de recuperação. Ordem de dev: **4/8**)
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** balanceamento-early-game (`done`), combate-lifecycle (ideal)
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achado B): "O Saque" dispara certo, mas o estado
pós-queda é uma **espiral de morte**: acorda com 25% HP, 0 ouro, só a arma
básica — e nos DOIS perfis que caíram (`combate` t12→morte t13; `explorador`
t43→morte t47) a 2ª queda fatal veio em 2–4 turnos. A 2ª queda matar é por
design (decisão da sessão 15); o problema é que o jogo não oferece NENHUM
caminho de recuperação: sem cura, sem ouro pra estalagem, sem gancho narrativo
de "se reergue primeiro".

Objetivo: manter a dureza do Saque, mas dar ao jogador (humano ou perfil) uma
chance REAL e mecânica de se reerguer — sem LLM decidindo números.

## 2. Requisitos

- **R1** — `apply_downed` (combat_mechanics.py:1145) passa a deixar o jogador
  com **1 consumível de cura básico** no inventário (id canônico de poção menor
  de `data/`; "quem te saqueou não se importou com uma poção rachada").
- **R2** — Pós-downed, o mundo entra em **carência de 1 dia de jogo**
  (`world["downed_grace_until"] = world_clock atual + 1 dia`): encontros
  aleatórios do storyteller NÃO disparam no local seguro durante a carência
  (viajar para zona de perigo cancela a carência — escolha do jogador segue
  valendo, e a 2ª queda deliberada continua matando).
- **R3** — `campaign_manager` injeta **beat de recuperação** determinístico no
  topo do plano após downed (`needs_replan=True` já existe): texto fixo
  parametrizado ("Recupere forças em {local_seguro} antes de voltar à estrada"),
  status `pending` — o LLM não escreve esse beat.
- **R4** — A narração do turno de despertar menciona explicitamente as opções
  de recuperação (descansar / poção) — instrução no prompt do storyteller
  condicionada a `player.active_conditions` conter `downed_recente` (condição
  nova setada por `apply_downed`, removida no 1º descanso ou após 1 dia).
- **R5** — Invariante 5.2: `downed.no_recovery_path` (`warning`) se o estado
  pós-downed não tiver nem poção nem carência ativa.

### Fora de escopo

- Mudar as regras do Saque em si (perda de ouro/itens/únicos fica).
- Reduzir a letalidade da 2ª queda (por design).
- Perfis de playtest "mais espertos" (comportamento burro é feature do harness).

## 3. Design técnico

- **`combat_mechanics.py`** — `apply_downed`: adicionar poção ao inventário
  (`{id, qty:1}`), setar `downed_grace_until` no world e condição
  `downed_recente`; retorno inalterado (tupla existente).
- **`agents/storyteller.py`** — gate de encontro: consultar
  `downed_grace_until` vs `world_clock` antes de sortear encontro; prompt ganha
  cláusula condicional de R4.
- **`agents/campaign_manager.py`** — se `downed_recente` na 1ª execução após
  a queda: prefixa o beat determinístico (R3) antes do plano do LLM.
- **`world_utils.py`** — descanso remove `downed_recente`.
- **`playtest/invariants.py`** — check R5.
- **`state.py`** — documentar `downed_grace_until` (WorldState) — default
  ausente = sem carência (saves antigos ok).

## 4. Plano passo a passo

### Etapa 1 — poção + condição + carência (mecânica pura)
1. **Testes** (`tests/test_balance_early.py`, ampliar):
   `test_apply_downed_deixa_pocao`; `test_apply_downed_seta_carencia_e_condicao`;
   `test_descanso_remove_downed_recente`.
2. **Implementação:** `apply_downed` + `world_utils`.
3. `uv run pytest` verde.

### Etapa 2 — carência bloqueia encontro; beat de recuperação
1. **Testes:** `test_encontro_nao_dispara_na_carencia` (RNG forçado);
   `test_viajar_para_perigo_cancela_carencia`;
   `test_beat_de_recuperacao_e_prefixado_pos_downed` (mock).
2. **Implementação:** storyteller + campaign_manager.
3. `uv run pytest` verde.

### Etapa 3 — invariante + narração
1. **Testes:** `test_invariante_no_recovery_path`.
2. **Implementação:** invariants + cláusula de prompt (R4).
3. Playtest mock: `combate` 50 turnos — morte definitiva ainda possível, mas
   `first_death_turn` da 2ª queda > turno_downed + 2 na média dos seeds.

## 5. Critérios de aceite

- [x] R1–R5 com testes (`tests/test_pos_saque.py`, 13 casos)
- [x] Perfil `combate` mock 50 turnos × 3 seeds: sobrevivência bem além do
  baseline (seed1 morreu no t26, seed2 no t46 após 1 downed; 0 violações
  `downed.no_recovery_path`)
- [x] `uv run pytest` verde (suíte completa offline) — **835 passed**
- [x] Saves antigos continuam carregando (campos novos com default ausente)
- [x] Smoke §6 real — despertar pós-Saque: poção `pocao_cura` no inventário,
  beat `Recupere forças em {local}` no plano, narração cita descansar/poção

## 6. Smoke test com LLM real

1. Forçar downed num run real curto; conferir: poção no inventário, narração
   do despertar menciona recuperação, beat de recuperação no plano.
2. Descansar → condição some; viajar pra perigo → carência cancela.

## 7. Riscos & compatibilidade

- Saves antigos: sem os campos novos, comportamento idêntico ao atual.
- MockLLM: tudo mecânico exceto a cláusula de prompt (R4 é testada via
  presença da instrução no prompt, não via output do mock).
- Risco de design: carência pode "amaciar" demais o early game — knob é 1 dia
  e só no local seguro; medir com harness antes/depois (métrica
  `downed_count`/`first_death_turn` já existe).
