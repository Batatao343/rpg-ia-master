# SPEC — Feedback de recompensas ancorado no ledger

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `loot-exploracao` e grounding boundaries (`done`)
> **Desbloqueia:** feedback confiável de exploração e economia

---

## 1. Contexto & Objetivo

O motor concedeu ouro de exploração e o LLM o repetiu em `items_gained`. O
resolver tentou tratar “15 de ouro” como item inexistente, removeu a frase e
acrescentou que nada foi obtido, contradizendo o ledger mecânico.

## 2. Requisitos

- **R1** — Variações de ouro/moedas em `items_gained` não devem passar pelo resolver de itens.
- **R2** — O delta real de ouro/inventário deve produzir confirmação mecânica determinística.
- **R3** — Rejeições de outros claims não podem negar recompensas confirmadas pelo ledger.
- **R4** — O invariante deve detectar narração negativa quando ouro ou inventário aumentou no turno.
- **R5** — Valores continuam vindo apenas do Python; texto do LLM nunca concede economia.

### Fora de escopo

Redesenho visual de toast/HUD ou mudanças na tabela de recompensas.

## 3. Design técnico

- **`agents/storyteller.py`** — snapshots econômicos, classificação monetária e confirmação pelo delta.
- **`playtest/invariants.py`** — contradição recompensa/narração.
- **`tests/test_feedback_ledger_recompensas.py`** — ouro duplicado pelo LLM, item inválido concomitante e invariante.

## 4. Plano passo a passo

1. **Testes:** reproduzir a descoberta que concede ouro e recebe claim monetário.
2. **Implementação:** filtrar claim e renderizar delta mecânico.
3. **Testes/implementação:** cobrir contradição narrativa no harness.

## 5. Critérios de aceite

- [x] Ouro de exploração não é resolvido como item.
- [x] A mensagem final confirma o delta canônico.
- [x] Nenhuma frase afirma “nada obtido” quando o ledger cresceu.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Structured output existente mantém seu guard.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Explorar até obter ouro.
2. Comparar texto final, `player.gold` e `items_gained` retornado pelo provider.

Smoke real `20260812-172526-505951`: exploração/loot elevou ouro a 67 com
feedback coerente, zero `narrative.reward_contradiction`.

## 7. Riscos & compatibilidade

Pode haver uma linha curta redundante se o LLM já mencionar o ganho; ela é deliberada e canônica.
