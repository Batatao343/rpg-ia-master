# SPEC — Telemetria de rollback, conflito e run abortado

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `observabilidade-latencia-nos`, `continuidade-memoria-morte`

## 1. Contexto & objetivo

Mortes misturam índice da ação e turno canônico; eventos restaurados zeram
`downed_count`; conflitos repetidos inflam encerramentos. Um prefixo abortado é
reportado como JSONL estruturalmente inválido e sua linha final perde rota/timing.

## 2. Requisitos

- **R1** — Cada morte expõe `session_action`, `canonical_turn` e `timeline_epoch`.
- **R2** — Contagens derivam de `death_history`, que não retrocede.
- **R3** — cobertura agrega conflitos únicos por `conflict_id + epoch` e separa
  replay/rollback.
- **R4** — timeout usa rota `timeout`, preserva nós/timings parciais.
- **R5** — run abortado aceita prefixo sequencial válido; incompletude fica no
  status, sem erros JSONL redundantes.

## 3. Plano e aceite

Testes de summary/manifest/watchdog, depois runner/telemetry/report.

- [x] Três relógios inequívocos.
- [x] Prefixo abortado estruturalmente válido.
- [x] `uv run pytest` verde.

## 4. Evidência

O longrun 200t terminou com `session_action=200`, turno canônico 114 e seis
epochs; seis mortes permaneceram no ledger. Contrato dedicado cobre JSONL
abortado com rota `timeout` e timings parciais.
