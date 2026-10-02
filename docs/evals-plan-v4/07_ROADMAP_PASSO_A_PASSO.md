# 07 — Roadmap oficial de execução

Este documento substitui qualquer ordem `000-008` das versões anteriores do pacote.

## SPEC-163 — Normalizar histórico de specs

Criar IDs estáveis 001–162 pela ordem de criação comprovada no Git; `completed_order` separado. Renomear/referenciar automaticamente e gerar `specs/index.yaml`.

## SPEC-164 — Atualizar AGENTS.md

Ensinar spec IDs, eval integrity, project index, state ownership, long-run opt-in e model routing.

## SPEC-165 — Eval Governance

Definir schemas, hashes, protected paths, holdout, compatibility e anti-gaming. **Astra review obrigatório.**

## SPEC-166 — Project Index Core

Criar índice/grafo determinístico, bounded e evidence-backed. Sem mover pastas.

## SPEC-167 — Deterministic Eval Harness

Runner/registry/report comum, reaproveitando `playtest/` e testes.

## SPEC-168 — State/Rules/Persistence Evals

Começar pelo máximo determinístico: state, lifecycle, economy, rewards, persistence, idempotência.

## SPEC-169 — Routing/Action Evals

Route/intent/target com corpus fechado e confusion matrix.

## SPEC-170 — Memory/RAG/Context Evals

Separar store/retrieve/context/generate; Recall@K/MRR/evidence IDs/leak hard gates. **Astra review obrigatório.**

## SPEC-171 — Narrative/NPC Evals

Hard contradictions determinísticas primeiro; judges não-blocking até calibração. **Astra review obrigatório.**

## SPEC-172 — Frontend Evals

Playwright journeys, console/network, responsive, a11y e visual estável.

## SPEC-173 — CI/Gates

PR deterministic gates, private holdout, manual short real-provider, artifacts. Nenhum long-run automático.

## SPEC-174 — Baseline v1

Executar e registrar números. **Nenhuma mudança de produto. Nenhum target inventado. Nenhum long-run.**

## SPEC-175 — A/B do Project Index

Provar se o índice ajuda o coding agent no próprio repo antes de torná-lo obrigatório.

## Depois

A próxima spec recebe o próximo ID somente quando baseline/benchmark apontarem um problema real. Não reservar SPEC-176 antecipadamente.
