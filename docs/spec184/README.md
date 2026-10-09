# SPEC-184 — Wallet ledger e reservas

Implementação em `infrastructure/wallet.py` e migration
`20261008170000_wallet_ledger.sql`. A unidade é `shard_milli` inteiro; o saldo
comercial pertence à conta e não entra no `GameState`.

## Contrato contábil

| Evento | disponível | reservado |
|---|---:|---:|
| compra | +p | 0 |
| reserva | −r | +r |
| liquidação | 0 | −s |
| liberação | +u | −u |
| refund/reversal | −p | 0 |
| ajuste administrativo | ±a | 0 |

Portanto `compras + ajustes líquidos − liquidações − refunds − reversals =
disponível + reservado`. O banco exige ambos os saldos não negativos, confere
os dois caches contra a soma do ledger em trigger diferida e confere o saldo
reservado contra todas as reservas abertas. Entries e tickets de tentativa são
append-only. O lock da conta serializa movimentos; chaves únicas vinculam
payment externo, referência de operação e eventos de usage.

## Fronteiras de efeito pago

1. Backend valida versão de pricing fresca, owner de `operation_id` e saldo;
   grava reserva e transferência em uma transação.
2. Cada tentativa de provider precisa de ticket persistido **antes** do envio.
   O pior custo publicado é convertido pela versão autorizada e somado aos
   tickets anteriores. Fallback e retry usam novo ticket. Provider sem limite
   verificável ou teto insuficiente bloqueia o envio.
3. `settle_usage` lê usage exato persistido, verifica owner, operation, contagem
   e provider/model de todos os tickets, impede uso do mesmo evento em duas
   liquidações e grava `settle + release` do restante numa transação.
4. Queda sem ticket permite liberação automática. Com ticket, `recover` muda
   para `uncertain` e conserva a reserva, inclusive se a operação falhou.
   Usage exato persistido pode liquidar após novo fence. Ausência de cobrança
   exige reconciliação manual com ator e prova do provider.

O registro de usage usado para liquidar recebe snapshot financeiro imutável;
isso preserva a auditoria de uma liquidação mesmo se os eventos operacionais
originais forem apagados. FX e rate card devem estar frescos na autorização.
A liquidação posterior usa a versão imutável já autorizada.

## Fronteira de ativação

`wallet_spend_scope` e o parâmetro opcional `spend_scope` da operação já ligam
o teto ao `RoutedLLM.invoke/stream`. Nenhuma rota de produção entra nesse scope
ou credita compra nesta spec. Stripe, Google Play, voz e imagem exigem seus
contratos de confirmação, tickets e reconciliação nas specs seguintes antes de
ativar cobrança. `credit_verified_purchase` só é chamável no backend e exige
confirmação externa; não há endpoint de compra. DeepSeek com preço
`conservative_peak` não autoriza settlement exato e permanece em reconciliação.

## Gates

- `tests/test_wallet_local.py`: Postgres local, concorrência, replay,
  conservação, crash e RLS/roles.
- `tests/test_wallet_spend_guard.py`: bloqueio antes da rede em invoke,
  fallback e stream.
- Teste focado local: **17 passed** (Postgres + guard). Cobre duas reservas
  concorrentes, lease/fence no reclaim, evento de usage único entre reservas,
  corrida settle/recover e sequência determinística de 24 transferências com
  reconstrução do saldo a partir do ledger. Ruff dos arquivos alterados passou.
- `supabase/tests/valoria_rls_test.sql` passou **14/14** no Postgres local após
  aplicar as views `public.wallet_*_view` com `security_barrier=true`, revogar
  `USAGE app` de `authenticated` e limitar grants das views a `SELECT` para
  `authenticated`. Teste de feature verifica esses privilégios e opções das
  views. Nenhuma migration foi aplicada em produção.
- Suíte completa final: **2.093 passed, 13 skipped, 15 deselected**, zero falha
  ou erro (JUnit: 2.106 tests). No Windows, o gate precisou de `--basetemp`
  ASCII para FAISS/arte e `safe.directory` Git apenas no ambiente do processo
  por diferença de owner do sandbox; nenhum source de eval foi alterado.
- Parecer Astra High independente: **APPROVED**
  ([registro](../../handoffs/SPEC-184-ASTRA-independent-review.md), run
  `SPEC-184-ASTRA-20261009-final2`). A SPEC-184 está `done`.
