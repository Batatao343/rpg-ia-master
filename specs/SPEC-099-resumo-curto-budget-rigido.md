# SPEC — Resumo curto e budget rígido de memória

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `context-builder` e archivist (`done`)
> **Desbloqueia:** sessões longas com contexto previsível

---

## 1. Contexto & Objetivo

Em 40 turnos reais o `narrative_summary` cresceu para milhares de tokens. O
context builder descartou o bloco por exceder a quota, mas o storyteller usou o
resumo bruto como fallback, anulando o orçamento. Isso aumenta latência/custo e
faz o contexto recente desaparecer ou escapar do limite dependendo do nó.

## 2. Requisitos

- **R1** — `narrative_summary` deve ter limite determinístico de 1.200 caracteres, preservando preferencialmente o trecho mais recente.
- **R2** — Saves antigos devem ser compactados na carga e toda saída do archivist deve ser compactada antes de persistir.
- **R3** — Memórias devem ser particionadas em fatos que caibam individualmente na quota, em vez de um bloco indivisível.
- **R4** — Nenhum agente pode contornar o `ContextPack` usando o resumo bruto quando `memory_block` estiver vazio.
- **R5** — O harness deve emitir erro se o limite for violado.

### Fora de escopo

Trocar o modelo de sumarização ou adicionar uma nova chamada de LLM.

## 3. Design técnico

- **Novo `services/memory_summary.py`** — constante e compactação pura/sentence-aware.
- **`agents/archivist.py`, `persistence.py`** — aplicar compactação nas fronteiras.
- **`services/context_builder.py`** — granularizar fatos de memória.
- **`agents/storyteller.py`** — retirar bypass.
- **`playtest/invariants.py`** — limite auditável.
- **`tests/test_resumo_budget_rigido.py`** — limites, save legado, seleção e bypass.

## 4. Plano passo a passo

1. **Testes:** provar limite, preferência por recência e migração na carga.
2. **Implementação:** utilitário puro e aplicação nas fronteiras.
3. **Testes:** provar que um fato pequeno sobrevive ao lado de um resumo grande e que o storyteller não injeta o bruto.
4. **Implementação:** granularização e remoção do fallback.

## 5. Critérios de aceite

- [x] Nenhum estado carregado/salvo excede 1.200 caracteres de resumo.
- [x] Memória selecionada respeita o budget.
- [x] Storyteller nunca injeta resumo bruto fora do pack.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum structured output/LLM novo.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Jogar 5 turnos com resumo legado longo.
2. Confirmar limite, contexto recente e ausência de aumento de requests.

Smoke real `20260812-172526-505951`: 5/5 turnos, memória/RAG ativos, zero
violação de limite e nenhuma chamada nova introduzida pela compactação.

## 7. Riscos & compatibilidade

Resumo legado perde detalhes antigos por design; fatos duráveis permanecem no ledger/RAG.
