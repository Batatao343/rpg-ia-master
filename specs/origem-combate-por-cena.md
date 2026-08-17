# SPEC — Origem causal por cena de combate

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `ritmo-social-origem-combates` (`done`)

## 1. Contexto & objetivo

`combat.origin` antigo vencia o hint da cena nova; descansos e viagens apareciam
como provocação do jogador. A causa deve ser materializada novamente a cada start.

## 2. Requisitos

- **R1** — Hint válido da cena nova sempre vence origem histórica.
- **R2** — Descanso interrompido é `regional_danger`; viagem é
  `travel_encounter`; ação de ataque é `player_provoked`.
- **R3** — Origem permanece estável somente durante a mesma cena.
- **R4** — Telemetria conta a origem apenas em `combat_started`.

## 3. Design, plano e aceite

Testes do classificador e integrações storyteller/combat; sem novo invoke LLM.

- [x] Três causas cobertas.
- [x] Origem anterior não contamina cena nova.
- [x] `uv run pytest` verde.

## 4. Evidência

O longrun 200t registrou origens distintas (`player_provoked=12`,
`travel_encounter=2`); os testes cobrem também descanso como `regional_danger`.
