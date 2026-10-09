# SPEC-183 — handoff de executor (`MODEL_HANDOFF_REQUIRED`)

Data: 2026-10-08. Base técnica: `4eee012` (SPEC-182 `done`, PR #18).

> **Atualização:** após receber o aviso de indisponibilidade de Terra High, o
> usuário orientou disparar um subagente equivalente. Um executor Sol High foi
> delegado para a SPEC-183, com revisão Sol High independente por outro agente.
> A substituição foi comunicada ao usuário antes de iniciar a implementação.

## Motivo

A [SPEC-183](../specs/SPEC-183-pricing-estilhas-margin.md) exige executor
**Terra High** e revisor **Sol High** independente, sem substituição silenciosa.
Terra não consta entre os modelos disponíveis nesta sessão. O executor ativo é
Sol High. A dependência SPEC-182 está `done`. O handoff foi necessário antes da
orientação do usuário registrada acima; a execução prossegue com Sol High em
subagente e parecer independente posterior. Nenhum preço comercial final foi
definido.

## Source confirmado

- O motor de uso/custo está em `services/usage_metering.py`, com rate card em
  `data/pricing/rate_card_2026-10-08.json`; `app.usage_events` e o consolidado
  de turno foram entregues na SPEC-182.
- Ainda não há motor de pricing, `pricing_versions`, `purchase_skus` nem wallet.
  Ouro pertence ao `GameState`; Estilhas pertencem à conta e não entram no save.
- A fórmula canônica e os limites estão na SPEC-183 e em
  `docs/rpg-next-jev-golive-plan/02_BILLING_E_MARGIN.md`: `Decimal` e
  `shard_milli` inteiro, floor na concessão, ceil no débito, margem-alvo 5%,
  imposto zero nesta versão, fee fixa+percentual por canal, FX/rate card
  versionados, infra fixa reportada à parte. Não publicar pacotes finais.

## Próximo executor

Após a decisão de modelo, confirmar o owner de qualquer writer persistente no
source e no mapa de ownership seletivo; separar versão imutável de pricing,
configuração de fees/FX e exemplos não comerciais. Implementar funções puras
com `Decimal` antes do storage, vetores financeiros e property tests de
conservação/rounding, calculadora CLI e guard fail-closed para FX/rate card
ausente ou stale. Não modificar golden/expected/evaluator na tarefa de produto.
Rodar a menor suíte determinística, depois `uv run pytest` completo e revisão
Sol High independente antes de marcar `done`.
