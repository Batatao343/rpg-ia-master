# SPEC — Bloquear fuga e exploração com Vitalidade zero

> **Status:** `done`
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

- [x] A1 levou Vitalidade a 0 duas vezes em combate; ambas seguiram para
  morte/restore, nunca viagem viva a 0.
- [x] Estado vivo fora de combate a 0 gera invariante `error`.
- [x] Suíte completa verde.
