# SPEC — Fix de liveness do manifesto e telemetria de circuit breaker

> **Status:** `done` (2026-08-03 — 1382 offline verdes; manifesto v3 validado)
> **Criada:** 2026-08-03 · **Atualizada:** 2026-08-03
> **Depende de:** `hardening-playtest-watchdog` (`done`)
> **Desbloqueia:** runs reais >6 h e métricas confiáveis sob circuit breaker

---

## 1. Contexto & Objetivo

A revisão pós-entrega encontrou dois bugs no hardening do playtest:

1. `recover_stale_runs()` usa apenas `created_at`. O projeto já teve matriz real
   de 8,4 h; se outra run começar após a sexta hora, ela marca a campanha ainda
   ativa como `aborted`.
2. `_normalize_llm_event()` considera todo outcome diferente de `build_error`
   como request de rede. `circuit_open` não chama provider, mas hoje infla
   `llm_network_requests`, custo por tier/provider e falhas.

O objetivo é distinguir processo vivo de manifesto órfão e decisão de roteamento
pulada de request real, preservando compatibilidade com manifestos v2.

## 2. Requisitos

- **R1** — manifesto v3 grava owner (`pid`, `host`) e `heartbeat_at`.
- **R2** — manifesto antigo não é recuperado se pertence a PID vivo no host
  atual, independentemente da idade.
- **R3** — CLI atualiza heartbeat ao fim de cada turno; heartbeat recente
  preserva também execução em outro host/sem PID verificável.
- **R4** — PID morto + heartbeat antigo continua sendo recuperado como
  `aborted/stale_running_manifest`; manifesto v2 legado mantém esse comportamento.
- **R5** — `circuit_open` normaliza com `network_attempted=false`, como
  `build_error`.
- **R6** — summary separa `llm_skipped`; skips não entram em network requests,
  custo, provider counts nem `llm_failures`, mas permanecem auditáveis em
  `llm_attempts`/outcomes.
- **R7** — startup e turnos usam a mesma semântica.

### Fora de escopo

- Lock distribuído entre hosts ou banco de coordenação.
- Cancelamento forte da thread daemon do watchdog.
- Alterar a política que abre o circuit breaker.

## 3. Design técnico

- `playtest/telemetry.py` — schema v3, `_pid_is_alive`, `touch_run`, liveness por
  owner/heartbeat e agregação `llm_skipped`.
- `playtest/__main__.py` — callback de heartbeat por turno.
- `playtest/runner.py` — normalização fecha outcomes sem rede.
- `tests/test_playtest_watchdog.py` — processo vivo, morto, heartbeat e legado.
- `tests/test_playtest_observability_hardening.py` — custo/rede/skips do circuito.

## 4. Plano passo a passo

### Etapa 1 — liveness

1. **Testes primeiro:** manifesto antigo com PID vivo não é abortado; PID morto
   é; heartbeat recente vence idade de criação; v2 antigo continua recuperável.
2. **Implementação:** owner, heartbeat, `touch_run` e callback da CLI.
3. **Verificação:** suíte watchdog verde.

### Etapa 2 — telemetria do circuito

1. **Testes primeiro:** `circuit_open` normaliza sem rede; summary registra um
   skip, zero network request/custo/falha.
2. **Implementação:** normalização e agregação.
3. **Verificação:** suíte de observabilidade/routing verde.

## 5. Critérios de aceite

- [x] R1–R7 cobertos por testes.
- [x] Run longa ativa não pode ser marcada stale no mesmo host.
- [x] Circuit skip custa US$ 0 e não conta request/falha.
- [x] Manifestos v2 continuam legíveis/recuperáveis.
- [x] `uv run pytest` verde (1382 passed, 1 skipped, 14 deselected).
- [x] Nenhum structured output novo; saves de jogo inalterados.

## 6. Smoke test

1. Criar manifesto com idade >6 h e owner do processo atual; recovery preserva.
2. Trocar owner para PID morto; recovery marca `aborted`.
3. Rodar campanha offline curta via CLI; `heartbeat_at` e owner aparecem e o
   manifesto termina `complete`.

## 7. Riscos & compatibilidade

- `os.kill(pid, 0)` só é usado no mesmo host; PID atual tem fast-path.
- Em storage compartilhado entre hosts, heartbeat é a prova de vida disponível.
- Schema v2 sem owner/heartbeat segue o fallback temporal antigo.

## 8. Evidência de conclusão

- Testes reproduziram os bugs antes do fix: PID vivo era abortado; heartbeat
  recente era ignorado; `circuit_open` contava rede e não havia `llm_skipped`.
- Regressões cobrem PID vivo/morto, host remoto com heartbeat, manifesto v2,
  normalização do circuito e custo/rede/falha agregados.
- Smoke CLI `20260803-130102-999691`: 2/2 offline, manifesto schema v3,
  owner `pid+host`, heartbeat atualizado e status final `complete`.
