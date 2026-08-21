# SPEC — Continuação segura de matriz interrompida

> **Status:** `in-progress`
> **Criada/Atualizada:** 2026-08-21
> **Origem:** matriz A `20260820-200416-642340`, interrompida no par 5
> **Depende de:** `matriz-longrun-multiperfil-niveis`, `playtest-matrix-single-flight`

## 1. Contexto & objetivo

A matriz A concluiu quatro pares e perdeu uma conexão no quinto. Reiniciar os
800 turnos válidos gastaria quota sem acrescentar evidência. O harness deve
permitir continuação explícita a partir de um índice da matriz fixa, criando
manifesto próprio e preservando perfil, classe, nível e seed.

## 2. Requisitos

- **R1:** `matrix-suite --start-index N` seleciona os pares `N..10`.
- **R2:** default `1` mantém a execução integral atual.
- **R3:** manifesto lista apenas os pares esperados na continuação.
- **R4:** preflight, fail-closed, lock, tetos e ordem não mudam.
- **R5:** índice fora de `1..10` é rejeitado na CLI.
- **R6:** a matriz B formal continua usando `--start-index 1`.

### Fora de escopo

- Mesclar ou sobrescrever artefatos da tentativa anterior.
- Retomar dentro de campanha parcial; o par 5 reinicia no turno 1.
- Corrigir gameplay antes de completar a coleta A.

## 3. Design técnico

- `playtest/matrix.py`: seleção imutável da cauda pelo índice canônico.
- `playtest/__main__.py`: flag e manifesto da continuação.
- Testes cobrem seleção, manifesto e primeiro perfil executado.

## 4. Plano passo a passo

1. Escrever regressões para seleção 5..10 e manifesto.
2. Implementar flag sem alterar a matriz canônica.
3. Rodar suíte completa, atualizar handoff e iniciar A do par 5.

## 5. Critérios de aceite

- [x] Continuação seleciona exatamente os pares 5..10.
- [x] Par 5 reinicia com comerciante/Corruptor/nível 9/seed 6204.
- [x] Os quatro summaries anteriores permanecem intocados.
- [x] Suíte completa verde (1610 testes).

## 6. Smoke real

O novo manifesto deve declarar seis campanhas e começar por `matrix_05_6204`.

## 7. Riscos & compatibilidade

A evidência A ficará em dois run IDs e será agregada por `index/seed`. Nenhum
estado, agente ou mecânica do jogo muda.
