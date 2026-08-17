# SPEC — Retomada de quest e conversão em janela

> **Status:** `done`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** `memoria-autoridade-quests-verificaveis` (`done`)

## 1. Contexto & Objetivo

O pedido de tarefa ocorreu no turno 131, a quest nasceu no 132 e a métrica marcou
0% de conversão. O perfil fez uma investigação, saiu do alvo e nunca retomou.

## 2. Requisitos

- **R1** — Perfil normal prioriza quest ativa: navega por hops válidos até o alvo.
- **R2** — No alvo, emite duas investigações textualmente distintas.
- **R3** — Conversão pedido→quest aceita criação em janela D+0..D+3 e conta cada
  pedido no máximo uma vez.
- **R4** — Telemetria e oráculo agregado usam o mesmo cálculo.

### Fora de escopo

Alterar o schema LLM de propostas ou recompensas.

## 3. Design técnico

Helpers determinísticos em `playtest/profiles.py`; métrica pura compartilhada em
`playtest/metrics.py`, consumida por runner e telemetry.

## 4. Plano passo a passo

1. Testar navegação, ações distintas e janela D+1.
2. Implementar política e métrica pura.
3. Validar uma criação/conclusão no longrun mock.

## 5. Critérios de aceite

- [x] Quest ativa não é abandonada pelo ciclo normal.
- [x] D+1 conta como conversão.
- [x] Quest conclui e recompensa uma vez.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Aceite MockLLM `20260816-113051-596798`: quatro pedidos, quatro conversões
(100%), 16 quests criadas, 15 progredidas/concluídas/recompensadas. O smoke real
de NPC confirmou structured output e persistência, sem alterar o schema.

## 8. Resultado

O perfil usa BFS e emite duas investigações distintas no alvo. Runner e summary
consomem `playtest.metrics.quest_request_conversion_count`, com pareamento
unitário entre pedido e criação na janela D+0..D+3.

## 7. Riscos & compatibilidade

Mudança apenas no harness/telemetria; não controla decisões de jogadores reais.
