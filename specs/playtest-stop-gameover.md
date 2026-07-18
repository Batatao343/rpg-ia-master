# SPEC — Harness para no game_over + telemetria de rota fiel

> **Status:** `approved` (2026-07-17 — ordem de dev: **2/8**)
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** Fase 5 (`done`)
> **Desbloqueia:** métricas confiáveis p/ qualquer tuning futuro

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achados A+I de `docs/playtest-longrun-2026-07-14.md`):
`combate` morreu no turno 13 e `explorador` no 47, mas o runner seguiu até 100 —
**140/300 turnos** repetindo o memorial verbatim (o grafo termina em `START →
__end__` com `game_over`, main.py:54). Isso polui TODAS as métricas: p50 de
latência caiu pra 1–4ms, `routes` e custo médio ficam sem sentido.

Segundo problema: `rec.route` lê `state.get("next")` DEPOIS do invoke completo
(runner.py:285/312). O nó de combate consome/sobrescreve `next` → turnos de
combate registram rota vazia (`combate` registrou só `storyteller: 6` num run
de 100 turnos de perfil de combate).

## 2. Requisitos

- **R1** — `run_campaign` encerra a campanha no turno em que `game_over` fica
  `True`, com `aborted_reason="player_death (turno N)"`; nenhum turno é
  executado depois.
- **R2** — `turns_completed` do summary reflete só turnos realmente jogados.
- **R3** — a rota registrada por turno é a DECISÃO do router (ou
  `combat_agent` quando o lock de combate está ativo), nunca vazia num turno
  vivo; capturada no momento da decisão, não do estado final.
- **R4** — summary ganha `routes` completo (todo turno vivo conta exatamente 1
  rota) e o report exibe morte como linha própria (turno + local + causa).
- **R5** — invariantes/telemetria não rodam em turnos pós-morte (não existem
  mais, por R1).

### Fora de escopo

- Mudar o gate do grafo (main.py:54) — está correto; o problema é só o runner.
- Reviver/continuar campanha pós-memorial.

## 3. Design técnico

- **`playtest/runner.py`** — no loop de turnos: após `app.invoke`, se
  `state.get("game_over")` → grava o turno final, seta `aborted_reason` e
  `break`. Rota: registrar via callback/inspeção do dict parcial devolvido pelo
  `dm_router` (o runner já intercepta `new_state` em modo streaming — capturar
  `next` na PRIMEIRA aparição do turno, não na última) e, se
  `state["combat"]["active"]` na entrada do turno, registrar `combat_agent`.
- **`playtest/telemetry.py`** — `deaths`/`first_death_turn` já existem; somar
  `death_location`/`death_cause` (do event_log `player_died`, se disponível).
- **`playtest/report.py`** — render: linha de morte por campanha; p50/p95 agora
  naturalmente limpos (sem turnos de 1ms).

## 4. Plano passo a passo

### Etapa 1 — stop no game_over
1. **Testes** (`tests/test_playtest_harness.py`): `test_runner_para_no_game_over`
   asserta que com um estado que vira `game_over` no turno 3 (MockLLM +
   monkeypatch de `death_outcome`→"died"), `turns_completed == 3`,
   `aborted_reason` menciona morte e `len(history) == 3`.
2. **Implementação:** break no loop do runner.
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — rota fiel
1. **Testes:** `test_rota_registrada_em_turno_de_combate` — campanha mock com
   combate ativo asserta `route == "combat_agent"` no registro do turno;
   `test_rota_nunca_vazia_em_turno_vivo`.
2. **Implementação:** captura da decisão do router + fallback `combat_agent`.
3. **Verificação:** suíte verde; `python -m playtest run --profile combate
   --turns 10` (mock) mostra `rota_top=combat_agent`.

## 5. Critérios de aceite

- [ ] R1–R5 com testes
- [ ] Rodar os 12 perfis mock 50 turnos: nenhum summary com rota vazia em turno vivo
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Saves antigos continuam carregando (não toca persistência)

## 6. Smoke test com LLM real

1. `uv run python -m playtest run --profile combate --turns 30 --real
   --max-requests 0 --max-cost 0.10` — se morrer, run PARA na morte;
   summary sem turnos de 1ms; `routes` com `combat_agent` contado.

## 7. Riscos & compatibilidade

- Compat: só `playtest/` — zero impacto no jogo/API.
- MockLLM: perfis mock raramente morrem; testes forçam morte via monkeypatch.
- Comparação com baselines antigos: `turns_completed` muda de semântica
  (documentar no report que runs pré-spec contavam turnos mortos).
