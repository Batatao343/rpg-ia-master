# SPEC-188 — handoff de implementação para revisão Sol High

Status: `review-complete`. Executor Sol High; revisão Sol High concluída em
contexto independente. Não houve autoaprovação nem substituição silenciosa.
Base: SPEC-187 `done`, commit `ab081be12ea0782c60ce37fe67fa569c06269c38`.
Branch local: `spec-188-paid-image-quotes`. Commit de implementação congelado:
`a82adea3333284003629bd106bf58f1eb1440154`. Não havia push ou PR no
momento da revisão.

## Escopo de revisão

- Quote privado/imutável: owner/campanha/epoch/type/model/brief/teto/pricing/expiry.
- Aceite explícito: booleano literal, nenhum preço/model/owner do cliente.
- Commit único: operação + wallet reserve + geração + queue + save; replay.
- Paths reais: ofertas não tocam wallet/provider; job antigo/local falha fechado;
  `generate_dynamic_art_job` exige admission, e o handler usa dados canônicos.
- Ticket/fence antes da rede; sucesso normal do adapter por tokens documentados
  liquida, usage desconhecido/effect uncertain retém, erro pré-ticket libera.
- Excesso de custo mantém teto de débito e registra anomalia FinOps.
- UI: jogador/NPC/cena mostram resultado e hold após reload; troca de sessão
  cancela estado busy; expiração, 402 e replay só por clique explícito.

Arquivos principais: `services/image_quotes.py`, `services/image_pricing.py`,
`infrastructure/wallet.py`, `services/dynamic_art.py`, `workers/run_worker.py`,
`workers/dynamic_art_jobs.py`, `infrastructure/openai_images.py`, `api.py`,
migration `20261012160000_image_quotes.sql`, componentes/contratos web.
Source proof, sources oficiais e limites: `docs/spec188/README.md`.

## Resultados finais

- Gate focado consolidado: **78 passed**, incluindo **22 Postgres real** em
  rollback e adapter/worker real com HTTP fake → token usage → settlement.
- Python completa final: **2.118 passed, 90 skipped, 15 deselected**, exit 0,
  213,41s; JUnit local em `.tmp/spec188-final.xml`.
- Build e Ruff verdes; E2E da SPEC **7 passed** em 390/1440; browser completo
  **38 passed, 1 skipped**, 3,4m (executados pelo parent Sol).
- Índice de source será regenerado após docs/status para fechar freshness.
- Não houve imagem/LLM live, recarga de saldo de provider, SKU ou preço comercial.

Os quatro achados da revisão preliminar foram corrigidos; nenhum esperado de
evaluator ou dataset de regressão protegido foi editado. Testes antigos do
pipeline fake receberam somente wiring de admission/finance para manter as
mesmas asserções. Uma falha de métricas foi corrigida no produto, preservando
o oracle. Uma falha temporária PermissionDenied de SSE não reproduziu em dez
testes isolados e na suíte final; não foi suprimida nem contada como sucesso.

## Limites a registrar no parecer

- Custo do card técnico Standard deriva de fontes oficiais e inferência
  explicitamente documentada para inputs (Batch50%); sem validação por invoice
  ou geração live. Card válido sete dias, snapshot pinado e hash no quote.
- Unknown/inconsistent usage mantém hold até política/evidência explícita.
- Smoke browser opt-in antigo usa o contrato anterior sem quote; seu expected
  permaneceu intacto e o helper deve migrar antes de reusar aquele smoke.
- Casos Postgres da SPEC usam transações/savepoints e replay sequencial; não há
  novo stress com duas conexões. Locks/unique/fences foram auditados no source.

Registrar `review_model`, `review_effort`, `review_run_id` e decisão em parecer
separado. Só então marcar a SPEC e o índice `done` e liberar SPEC-189.

## Decisão posterior ao congelamento

O revisor Sol High independente aprovou o commit `a82adea` sem achados abertos
no run `SPEC-188-SOL-20261013-INDEPENDENT-01`. O parecer está em
[SPEC-188-SOL-independent-review.md](SPEC-188-SOL-independent-review.md);
SPEC-188 foi promovida a `done` após esse parecer.
