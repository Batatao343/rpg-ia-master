# SPEC-288 — playtest-causa-morte-especie

> **Status:** `done` (autorização do dono de 19/10 para tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Origem:** achado da SPEC-285 (35 de 120 mortes na main com causa = texto de gancho)
> **EXECUTOR_MODEL:** `Sonnet` · **REVIEW_REQUIRED:** `false`

## 1. Contexto & Objetivo
O relatório do playtest (seção Mortes) mostrava como causa "criatura ligada a: Corvane reativou uma
câmara…" em vez da espécie. Causa-raiz é de PRODUTO: `world_utils.check_encounter` (ramo
`looming_threat`) devolvia `hint="criatura ligada a: <ameaça>"` sem `enemy_id`; o spawn não casava o
bestiário e criava um inimigo CUJO NOME era o texto do gancho. Esse nome vazava para a narração, para
`player_downed.payload.killer`, para `continuity.death_history[].cause` (crônica/API) e para o playtest.
Além disso, mortes não-combate (armadilha) gravam `payload.cause` e o playtest lia só `killer` → `None`.

## 2. Requisitos
- **R1** — Encontro `looming_threat` resolve uma criatura canônica do bestiário (`enemy_id`, `hint` = nome da
  espécie); o texto da ameaça fica em `flavor`. Sem criatura elegível, o hint nunca carrega o texto do gancho.
- **R2** — `player_downed.payload` ganha `killer_id` (id do bestiário) e `killer` passa a ser a espécie canônica
  (`species_label_for`, sem sufixo de instância).
- **R3** — `death_cause` do playtest = `killer` → `cause` (categoria ambiental, ex. "armadilha") → `"desconhecida"`;
  nunca o texto do gancho. O runner grava também `killer_id` em `deaths_log`.
- **R4** — Seção Mortes do report mostra a causa canônica.

### Fora de escopo
Mortes por clima/DoT sem payload próprio (hoje só combate e armadilha emitem `player_downed`).

## 3. Design técnico
- `world_utils.check_encounter`: ramo threat usa `pick_encounter_enemy`.
- `agents/combat.py`: helper `_killer_identity(active)`.
- `playtest/runner.py`: causa canônica + `killer_id`.
- Testes: `tests/test_spec288_causa_morte.py`.

## 4. Plano
Testes primeiro, implementação, depois run `combate --turns 200 --seed 21` conferindo o summary.

## 5. Critérios de aceite
- [x] testes novos verdes
- [x] `playtest run --profile combate --turns 200 --seed 21`: nenhuma causa começa com "criatura ligada a"
- [x] suíte completa (exit)
- [x] Saves antigos continuam carregando (campos aditivos)

## 6. Smoke real
Não aplicável: sem structured output novo; caminho determinístico (bestiário Python).

## 7. Riscos
Encontro de ameaça agora tem espécie determinística (antes: scanner/LLM inventava pelo texto). Payload aditivo.
