# SPEC-291 — e2e-divisor-split-flake

> **Status:** `done` (autorização do dono de 19/10 para tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** CI eval-gates do commit b90436c: F17 (`critical-journeys.spec.ts:337`) e
> `workspace-shell.spec.ts:166` falharam com o divisor em 50 após o arrasto; o push seguinte passou.
> **EXECUTOR_MODEL:** `Sonnet` · **REVIEW_REQUIRED:** `false` (teste e2e)

## 1. Contexto & Objetivo

Após o arrasto do divisor (`mouse.down` → `mouse.move` ×6 → `mouse.up`) os testes liam
`aria-valuenow` uma única vez, sem espera. O componente (`Workspace.tsx`) calcula o ratio em
`pointermove` de janela com `getBoundingClientRect` ao vivo (sem ref desatualizada, estado
inicial síncrono do `localStorage`); `pointermove` é evento contínuo e o React pode adiar o
render para depois do `mouse.up` sob CPU carregada (suíte inteira em CI). Resultado: leitura
do valor antigo (50). Não há corrida no app; o defeito é de leitura não determinística no teste.
Rodar o teste isolado passa (10/10), por isso só aparecia na suíte cheia.

## 2. Requisitos

- **R1** — Os dois testes esperam o ratio estabilizar com `expect.poll` antes de ler o valor
  arrastado; sem `sleep`. Os asserts de faixa permanecem iguais.
- **R2** — Nenhum arquivo protegido (`evals/protected-paths.txt`) alterado; app inalterado.

## 5. Critérios de aceite

- [x] `critical-journeys.spec.ts` F17 e `workspace-shell.spec.ts` divisor: 10× cada, 0 falhas
- [x] Suíte Python offline verde (exit 0)
