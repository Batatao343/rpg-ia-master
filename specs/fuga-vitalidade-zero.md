# SPEC — Bloquear fuga e exploração com Vitalidade zero

> **Status:** `approved`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A, explorador (17 mortes)

## 1. Problema

O perfil conseguia concluir fuga já com Vitalidade 0. O combate encerrava sem
`death_pending`; depois o personagem viajava/descansava a 0 até outra ameaça
formalizar a morte. Houve ciclos repetidos nas Saídas Baixas.

## 2. Requisitos

- **R1:** protagonista com Vitalidade 0 não inicia/conclui fuga.
- **R2:** a ação vira `pass` e a resolução terminal/estabilização normal do
  conflito decide o estado; nunca sai `combat.active=false` vivo a 0.
- **R3:** invariante `player.zero_vitality_outside_terminal` acusa estado 0 fora
  de combate sem `death_pending/game_over`.
- **R4:** perfil explorador aprende destino/ciclo fatal após restore como antes.

## 3. Aceite

- [ ] Regressão reproduz fuga a 0 e obtém `death_pending`, não viagem.
- [x] Estado vivo fora de combate a 0 gera invariante `error`.
- [x] Suíte completa verde.
