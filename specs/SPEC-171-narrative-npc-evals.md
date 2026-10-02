# SPEC-171 — Narrative e NPC Evals deterministic-first

> **Status:** `done`
> **Depende de:** SPEC-170 `done`
> **Modelo executor mínimo:** Sol High
> **Revisão obrigatória:** **Astra**

## Objetivo

Usar estado/evidência canônica para bloquear contradições e manter judges subjetivos fora do caminho crítico até calibração.

## Blocking determinístico

- falsa morte;
- posse falsa;
- localização contraditória;
- identidade NPC;
- secret leak;
- reward/outcome contradiction;
- lifecycle/action incompatível;
- entidades fora da cena quando detectável pelo estado.

## Judge inicialmente não-blocking

- persona;
- fluidez;
- agência subjetiva;
- repetição semântica.

## Promoção de judge

Exige corpus humano rotulado, agreement, known-good/known-bad, position-swap, model/version pinned e Astra review específica.

## Aceite

- [x] hard claims usam estado canônico;
- [x] zero judge substituindo check determinístico;
- [x] Astra aprova fronteira blocking/non-blocking.

## Execução — 2026-09-29

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Corpus público versionado com 27 casos e quatro operações reais: guard de
  narrativa, presença de NPC na cena, elegibilidade de ação e lifecycle de
  conflito. Cobre morte, posse, localização/região, identidade, segredo,
  reward/outcome, lifecycle, ação incompatível e entidade fora da cena.
- O evaluator compara decisão, reason e, nos 15 casos de prosa, o texto
  sanitizado fixture-authored. Fragmentos proibidos independentes distinguem
  claim vazado de substituição neutra ou supressão excessiva.
- Smoke final `spec171-narrative-npc-smoke-v3`: 27/27 casos verdes,
  `narrative_claim_accuracy=1.0`, `narrative_hard_contradictions=0` e
  `npc_identity_errors=0`; provider/model ausentes.
- `npc_persona_score` permanece `blocking: false`, sem calibração e sem execução;
  nenhum judge substitui contrato determinístico.
- Revisão independente Astra aprovada em `SPEC-171-ASTRA-20260930-01`, após
  corrigir observabilidade da saída sanitizada e a semântica do contador.
- Gate final: 1.878 passed, 35 skipped, 15 deselected. Project Index fresco:
  5.420 nodes/13.866 edges.
- Limite: os contratos cobrem claims delimitados do corpus público; não provam
  fact-check semântico geral nem qualidade de geração LLM.
