# SPEC-185 — handoff de executor Terra High

`MODEL_HANDOFF_REQUIRED: Terra High` identificado em 2026-10-09. A spec
aprovada exige executor Terra High e revisão Sol High independente; Terra não
está disponível nesta sessão. Após pergunta específica sobre usar subagente
Sol High executor e outro Sol High revisor na SPEC-185, o usuário respondeu
"continue". Esta instrução foi interpretada como autorização para essa
substituição nesta spec. O custo de modelo fica acima do tier planejado.

Dependência SPEC-184: `done`, implementação `8b2134c`, fechamento `cd27f79`,
draft PR #20. A wallet fornece views de saldo/histórico por owner, sem ativar
cobrança comercial. A SPEC-185 deve implementar APIs read-only owner-scoped,
dashboard de conta e custo por mensagem derivado de `app.turns`/operation/usage,
sem escrever valor financeiro no `GameState` ou `presentation_history`.

Source confirmado: `api.py` possui `/game/history` por volta de 1601,
`web/src/components/StoryLog.tsx` desenha mensagens, e
`infrastructure/wallet.py` é o writer da conta. Consultar os trechos reais
antes de editar. Os gates incluem histórico paginado sem N+1, timeline epoch,
degradação quando read-model financeiro falha, isolamento A/B e 390/1440.

Hipótese cross-file para verificar: `services/presentation_history.py` grava
`id`, `turn` e `epoch`, mas não `operation_id`; `app.turns.sequence` é versão de
storage, não necessariamente `world.turn_count`. Assim, associar custo por
`turn` ou pela posição da mensagem pode atribuir valor à fala errada após
restore. `record_history` é chamado em `api.py` antes do commit. Uma opção mais
direta é gravar em `app.turns` o `presentation_entry_id` do narrador, extraído
do estado logo após `record_history`, na mesma transação de `commit_game` junto
de `operation_id` e `timeline_epoch`. O read-model faz batch pelos IDs da página
de histórico. Assim, custo/Estilhas permanecem fora do `GameState`. Saves antigos
sem vínculo devem degradar para custo ausente. Confirmar no source e nos testes.

Nenhuma implementação da SPEC-185 começou neste handoff.

## Desfecho

A hipótese foi confirmada no source: `app.turns.sequence` é versão de storage,
enquanto `record_history` produz o ID estável da entrada narrativa. A
implementação gravou `presentation_entry_id` em `app.turns` no commit da
operação e fez enriquecimento por lote da página, conferindo owner e epoch de
cada entrada. O usuário autorizou a substituição de Terra High por Sol High;
outro Sol High aprovou a revisão independente
(`SPEC-185-SOL-20261009T215654Z`). Evidência: `docs/spec185/README.md`.

O ciclo comercial `reserve → execute → settle → release` das jogadas normais
continua pendente para outra spec. Esta entrega expõe custo técnico e débito
liquidado como dados distintos, sem ativar cobrança.
