# SPEC — Memória NPC no ledger após sucesso direto

> **Status:** `done`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** `memoria-autoridade-quests-verificaveis` (`done`)

## 1. Contexto & Objetivo

O longrun real gravou dois `npc_claim` com sucesso no índice Jina, mas o ledger
global terminou apenas com inferências. O espelhamento atual cobre somente retry:
o sucesso direto no `npc_actor` nunca chega a `memory_facts`.

## 2. Requisitos

- **R1** — Write NPC bem-sucedido adiciona o mesmo record ao ledger global como
  `npc_claim/reported` no próprio turno.
- **R2** — Write falho continua exclusivamente na fila transacional existente.
- **R3** — Merge é idempotente e registra promoção quando substitui inferência.
- **R4** — Nenhum segundo write vetorial global é criado.

### Fora de escopo

Promover relatos a verdade confirmada ou alterar conteúdo do diálogo.

## 3. Design técnico

`agents/npc.py` reutiliza `commit_memory_facts` após `add_npc_memory=True` e
retorna `memory_facts`/`memory_promotions`; o archivist mantém o retry atual.

## 4. Plano passo a passo

1. Testar sucesso direto, falha, idempotência e promoção.
2. Implementar o merge no ator NPC sem write adicional.
3. Rodar suíte e smoke real com conversa NPC.

## 5. Critérios de aceite

- [x] `npc_claim` aparece no ledger no mesmo turno.
- [x] Falha permanece pendente sem autoridade falsa.
- [x] `uv run pytest` verde.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

Executado em 2026-08-16 com LLM/Jina reais: `+1 fatos`, fila vazia, sem erro de
persistência e ledger `[('npc_claim', 'reported')]` no mesmo retorno.

## 8. Resultado

`agents/npc.py` reutiliza o record e faz apenas o merge local após o sucesso do
write privado. Regressões cobrem sucesso, falha, backlog, idempotência e
promoção de `inference` para `reported`.

## 7. Riscos & compatibilidade

Sem schema novo; o ledger já persiste os campos usados.
