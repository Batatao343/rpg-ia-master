# SPEC — Identidade e correlação na aquisição paralela de contexto

> **Status:** `done`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** Nenhuma
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

ThreadPoolExecutor não propaga ContextVars automaticamente. Reprodução com principal_scope: leitura sequencial ok; paralela Unauthorized. A mesma fronteira afeta correlação de telemetria.

## 2. Requisitos

- **R1** — Cada fonte executa com cópia própria do contexto da chamada (principal e correlação), inclusive fachada async.
- **R2** — Duas campanhas/usuários concorrentes nunca compartilham principal; contexto alterado por um leitor não contamina outro nem chamador.
- **R3** — Ausência de principal continua falhando fechado; não inferir usuário global para mascarar Unauthorized.
- **R4** — Preservar limite global, paralelismo, embedding único, ordem lore/session/npc e status de degradação.
- **R5** — Cobrir leitores reais de rag com adapter em memória, além de callbacks artificiais.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

services/context_sources.py: contextvars.copy_context() por tarefa; nunca executar o mesmo Context concorrentemente. Isolar também leitores sequenciais para R2. Assinaturas e schema ContextSourceResult inalterados. tests/test_context_identity.py usa Principal de infrastructure/contracts.py e principal_scope. Não modificar políticas de autorização ou instalar provider.

## 4. Plano passo a passo

1. Regressão com max_workers=1/3 e acquire_context_sources_async.
2. Testar dois usuários simultâneos com barreira, leituras session/npc reais com MemoryStore falso e tentativa de modificar ContextVar em leitor.
3. Implementar propagação e validar testes existentes de limites/latência.
4. Smoke local autenticado com dois usuários no Postgres quando stack disponível.

## 5. Critérios de aceite

- [x] Testes offline de R1–R5 verdes.
- [x] Suite completa preservada.
- [x] Smoke autenticado local confirma isolamento e memória recuperada.

## 6. Smoke test com LLM real / integração aplicável

Não há mudança LLM. Gate real é integração local de identidade → RAG privado, sem API paga; não exige matriz B. Falta de stack não autoriza declarar esse gate feito.

## 7. Riscos & compatibilidade

Cópia de ContextVars é rasa: valores mutáveis compartilhados precisam semântica explícita (telemetria agregada), mas principal não deve ser mutado. Não trocar para async nativo.

## Execução — 23/09

`copy_context().run` isolado por leitor tanto no caminho sequencial quanto no executor paralelo; fachada async herda a correção. **7 casos novos** em `tests/test_context_identity.py`: leitores reais de RAG com MemoryStore falso, identidade/correlação, dois usuários concorrentes, mutação de contexto e ausência de principal. Suíte completa: **1743 passed, 18 skipped, 14 deselected**; suíte focada conjunta: **57 passed**.

Pendente: integração autenticada local com Postgres. Não foi executada nem substituída pelo adapter falso; spec permanece in-progress.

## Execução — 26/09 (prevalece sobre as pendências históricas)

Gate Postgres local executado: tests/test_context_identity_local.py, três modos (serial/paralelo/async), leitores reais de rag para sessão/NPC, dois usuários e isolamento de campanha. Três casos passaram, além dos sete offline e da suíte completa. O bloqueio de infraestrutura de 23/09 foi resolvido; nenhum provider pago.
