# SPEC — Estado pós-fuga e origem causal

> **Status:** `done`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** `origem-combate-por-cena` (`done`), `chase-progresso-e-fuga`

## 1. Contexto & Objetivo

Após escapar no turno 24, `Descanso...` foi roteado de volta ao combat agent e
marcado como `player_provoked`. A cena transitória e a classificação livre não
podem transformar descanso/viagem em provocação.

## 2. Requisitos

- **R1** — Fuga bem-sucedida limpa inimigos, target, chase, instance e origem.
- **R2** — Descanso/viagem explícitos fora de combate têm rota STORY determinística.
- **R3** — Só verbo hostil explícito recebe `player_provoked`; reação contextual
  não hostil usa `regional_danger`.
- **R4** — Próximo turno após fuga não reabre os mesmos inimigos.

### Fora de escopo

Impedir encontros sistêmicos legítimos disparados pelo storyteller.

## 3. Design técnico

Sanitização em `_apply_flee_travel`; override léxico fechado no router antes do
structured output e classificador causal Python para a rota COMBAT.

## 4. Plano passo a passo

1. Testar limpeza, descanso e ataque explícito.
2. Implementar sem novo invoke LLM.
3. Smoke dirigido pós-fuga.

## 5. Critérios de aceite

- [x] Descanso pós-fuga não reabre combate antigo.
- [x] Ataque explícito continua provocação.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Executado em 2026-08-16 com LLM real: ataque explícito →
`combat_agent/player_provoked`; investigação cautelosa e descanso →
`storyteller`, sem origem de combate. Nenhum MockLLM foi usado.

## 8. Resultado

Fuga bem-sucedida conserva somente o recibo mecânico do turno e remove
inimigos, target, chase, instance, cena e origem. Descanso/viagem explícitos são
fechados em STORY antes do classificador; a origem COMBAT depende de verbo hostil.

## 7. Riscos & compatibilidade

Overrides reconhecem apenas verbos fechados; texto ambíguo continua com LLM.
