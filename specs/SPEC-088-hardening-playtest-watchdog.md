# SPEC — Hardening do playtest real: watchdog e circuit breaker

> **Status:** `done` (2026-08-03 — watchdog exercitado e 3 runs reais fechadas)
> **Criada:** 2026-08-03 · **Atualizada:** 2026-08-03
> **Depende de:** `hardening-playtest-observabilidade` (`done`)
> **Desbloqueia:** runs reais longas com término e relatório confiáveis

---

## 1. Contexto & Objetivo

A run real `20260803-014405-602783` ficou com manifesto `running`, zero campanha
persistida e sem relatório. Timeouts por cliente já existem, mas uma cadeia com
vários nós/providers ainda pode prender startup ou turno por vários minutos; um
erro permanente também é repetido a cada chamada.

O objetivo é impor um teto de parede ao startup e a cada turno do harness,
encerrar manifestos como `aborted` e evitar retentar na mesma campanha um
provider que já respondeu com falha permanente.

## 2. Requisitos

- **R1** — watchdog configurável cobre startup e cada `_run_turn` em run real;
  offline continua síncrono por padrão.
- **R2** — timeout gera erro estruturado, `aborted_reason` e interrompe a
  campanha, sem produzir falso `complete`.
- **R3** — CLI expõe `--turn-timeout` (default seguro para `--real`).
- **R4** — manifesto aceita status `aborted`; interrupção pelo teclado também
  fecha o manifesto.
- **R5** — `begin_run` recupera manifestos `running` comprovadamente antigos,
  marcando-os `aborted` sem tocar runs recentes.
- **R6** — falhas permanentes de provider (autenticação/pagamento/modelo
  inexistente) abrem circuit breaker até o início da próxima campanha.
- **R7** — tentativa pulada pelo circuito aparece na telemetria.

### Fora de escopo

- Cancelar cooperativamente uma biblioteca HTTP que ignorou seu próprio timeout.
- Watchdog na API de produção; esta spec cobre o harness real.
- Roteamento adaptativo por custo/latência.

## 3. Design técnico

- `playtest/runner.py` — thread daemon isolada por operação monitorada,
  `PlaytestTimeoutError` e aborto imediato da campanha.
- `playtest/__main__.py` — flag e status final `aborted`.
- `playtest/telemetry.py` — recuperação de manifestos stale e status explícito.
- `llm_setup.py` — circuito process-local por `(provider, model)`, reset público
  no começo da campanha e outcome `circuit_open`.
- Testes em `tests/test_playtest_watchdog.py` e `tests/test_routing.py`.

## 4. Plano passo a passo

### Etapa 1 — watchdog e manifesto

1. **Testes primeiro:** timeout retorna no teto, aborta a campanha; manifesto
   abortado nunca é completo; stale é recuperado e run recente não é tocada.
2. **Implementação:** runner, CLI e telemetry.
3. **Verificação:** testes focados.

### Etapa 2 — circuit breaker

1. **Testes primeiro:** 402 abre circuito; próxima chamada pula o provider e
   registra `circuit_open`; reset permite nova tentativa.
2. **Implementação:** classificação fechada de falha permanente.
3. **Verificação:** suíte de routing.

## 5. Critérios de aceite

- [x] R1–R7 cobertos por testes.
- [x] Run artificialmente travada termina como `aborted` dentro do teto.
- [x] Run real curta termina ou aborta com manifesto fechado.
- [x] `uv run pytest` verde (1377 passed, 1 skipped, 14 deselected).
- [x] Nenhum structured output novo.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Rodar 3 turnos com `--real --turn-timeout 120`.
2. Confirmar `complete` em sucesso ou `aborted` em timeout — nunca `running`.
3. Gerar relatório/transcrito quando completo.

## 7. Riscos & compatibilidade

- A thread vencida é daemon e a campanha é encerrada imediatamente; não se inicia
  outro perfil no mesmo processo depois de timeout.
- Circuit breaker só reconhece assinaturas fechadas de erro permanente.
- Zero requests adicionais; tende a reduzir custo em falhas permanentes.

## 8. Evidência de conclusão

- `tests/test_playtest_watchdog.py` prova teto de parede, startup abortado,
  manifesto `aborted` e recuperação stale; `tests/test_routing.py` prova
  `402 → circuit_open → reset`.
- A run órfã `20260803-014405-602783` foi recuperada de `running` para
  `aborted`, motivo `stale_running_manifest`.
- Runs reais `20260803-114646-799077`, `20260803-114339-651827` e
  `20260803-114423-833666` encerraram `complete` sob `--turn-timeout 120`.
