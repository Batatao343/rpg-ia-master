# SPEC-185 — Conta e atribuição de custo

## Contrato entregue

- `/account/balance`, `/account/purchases`, `/account/usage` e `/account/series`
  exigem sessão e filtram todas as consultas pelo owner verificado. Históricos
  usam cursor `(created_at, id)` e limite de 50. As séries 24h/7d/30d têm
  buckets UTC e zeros preenchidos no servidor, separados em game/image/voice.
- O Account abre sem campanha. Saldo discreto aparece no shell; a tela mostra
  consumo **liquidado** em Estilhas, atividade de usage e histórico de compras
  em seções distintas. O gráfico oferece tabela temporal equivalente para
  leitor de tela e funciona em 390px e 1440px.
- O ID do narrador salvo no `presentation_history` é ligado a `app.turns` no
  commit, junto da operação e epoch. O enriquecimento de `/game/history` consulta
  uma página em lote, sem N+1, e volta ao histórico sem custo se a projeção
  financeira falhar. Um save legado ou prólogo sem esse vínculo não recebe
  custo inferido por posição/turno.
- O StoryLog apresenta, sob hover/focus/tap, custo técnico USD com origem e
  exatidão e, separadamente, débito em Estilhas apenas quando existe
  `wallet_entries.settle`. O custo não entra no `GameState` nem no
  `presentation_history`. Valores em milli-Estilhas atravessam JSON como
  strings decimais para preservar `bigint`.

## Evidência

- Python: `uv run --no-sync --project <repo> python -m pytest -o addopts=
  -m 'not llm_contract and not llm_playtest' -q --disable-warnings
  --basetemp=C:\tmp\rpg_spec185_pytest_summary` — **2.056 passed, 59 skipped,
  15 deselected**; seis warnings. Integrações que exigem banco local ficam
  desabilitadas neste comando e foram verificadas no gate focado abaixo.
- Focados: `tests/test_account_api.py`, `tests/test_account_read_model.py`,
  `tests/test_account_read_model_local.py`, `tests/test_presentation_history.py`:
  **12 passed**. Integração Postgres local com rollback cobre isolamento A/B,
  operação sem settlement, categoria voice sem `usage_operation_id`, bucket UTC
  sob sessão `America/Sao_Paulo` e plano do índice com 501 turnos.
- Browser: `node ./node_modules/@playwright/test/cli.js test
  e2e/account.spec.ts --project=chromium` — **4 passed**, incluindo 390/1440,
  navegação por teclado/tap, fallback clássico, troca de owner com resposta
  atrasada e saldo acima de `2^53` milli-Estilhas.
- `npm.cmd test` — **5 passed**; `tsc -b` e Ruff dos arquivos alterados verdes.
- Revisão Sol High independente: **APPROVED**, run
  `SPEC-185-SOL-20261009T215654Z`, sem bloqueios.

## Limite comercial

Nenhuma rota credita compra ou ativa checkout. As jogadas normais ainda não
executam o ciclo `reserve → execute → settle → release` do plano
`docs/rpg-next-jev-golive-plan/02_BILLING_E_MARGIN.md`; essa integração precisa
de spec futura. Assim, o custo técnico de um turno pode aparecer no StoryLog
enquanto o dashboard informa zero de consumo liquidado. Zero e indisponível
são distintos no DTO.
