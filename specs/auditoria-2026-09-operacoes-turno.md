# SPEC — Operações idempotentes e execução unificada do turno

> **Status:** `done`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** Nenhuma para replay; efeitos transacionais integram na spec própria
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

Recibos retornam antes da validação de identidade do pedido; retry de morte é rejeitado antes da consulta. Claims adquiridos antes de precondições podem ficar presos. POST e SSE duplicam a orquestração.

## 2. Requisitos

- **R1** — Replay valida owner, game_id, kind e hash; divergência retorna 409 e nunca devolve recibo de outra operação/campanha. Replay válido retorna resposta original.
- **R2** — Consulta de replay precede precondições mutáveis (death_pending, memorial). Falhas após claim sempre liberam via fencing, incluindo HTTPException.
- **R3** — Único executor Python compartilha preparação, grafo, apresentação e commit entre POST/SSE; transporte apenas entrega eventos.
- **R4** — Desconectar SSE não duplica turno. Conflito não vira retry de efeito novo; operation_id é estável.
- **R5** — Mutação de equip/levelup/death/art respeita ownership, lifecycle e campanha arquivada; mudanças de regra de equip em combate precisam decisão explícita.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

Estender receipt(principal, operation_id, *, game_id, kind, request_hash) no port/adapters ou criar lookup_validated com os mesmos campos. Validar metadados persistidos sem usar base_version atual para recusar replay concluído. Novo services/turn_execution.py coordena execução, com hooks de progresso e contextmanager de claim. Mover fatias de api.py sem alterar endpoints/schemas existentes. Compatibilidade legacy: ledger limitado permanece, com limitações documentadas.

## 4. Plano passo a passo

1. tests/test_operation_replay_boundaries.py: replay válido/divergente, usuário/campanha, morte após conclusão e liberação em toda exceção.
2. Contratos idênticos POST/SSE, incluindo desconexão e duas requisições simultâneas.
3. Extrair executor somente após paridade; sem big-bang.
4. Smoke Postgres local com conflito/versionamento real.

## 5. Critérios de aceite

- [x] R1–R5 e paridade de transportes cobertos.
- [x] Suite completa e smoke local transacional verdes.
- [x] Nenhum replay dispara LLM nem efeitos externos.

## 6. Smoke test com LLM real / integração aplicável

MockLLM basta para o gate transacional; executar API+Postgres reais locais. Não consome provider e não depende da matriz B.

## 7. Riscos & compatibilidade

Não invalidar recibos antigos silenciosamente; quando metadados insuficientes, erro explícito. Não reduzir isolamento para destravar retries.

## Execução — 26/09 (prevalece sobre as pendências históricas)

Executor compartilhado POST/SSE, validação de recibo por owner/game/kind/hash, replay antes das precondições mutáveis e limpeza de claim via operation_scope. Gate autenticado confirmou SSE→replay POST sem nova entrada no histórico e 409 para payload divergente. Migração 20260926132501 inclui art no domínio de operações; aplicada somente local. Ainda falta a matriz curta completa de morte/equip/levelup, desconexão durante commit e concorrência na API. Legacy mantém ledger limitado, sem garantia de recibo histórico completo.

Continuação: matriz HTTP real local de death/equip/levelup passou, com replay
após alteração de precondições e liberação do claim rejeitado. Encontrou e
corrigiu perda de archived/archived_reason na serialização; arquivamento agora
também interrompe o grafo antes de qualquer nó. Regressões curtas adicionadas.
Browser passou com confirmação perdida após commit e retomada sem duplicação.
Corrida simultânea pela API passou: uma mutação confirma e a concorrente recebe
409, com incremento único de versão. Isso fecha a lacuna antes pendente.
