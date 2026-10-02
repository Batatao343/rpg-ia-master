# SPEC — Checkpoint seguro fora de combate

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `continuidade-memoria-morte` (`done`)

## 1. Contexto & objetivo

O longrun 200t restaurou dez vezes o mesmo checkpoint capturado dentro de um
conflito letal. Esta spec garante que nenhum slot novo contenha combate ativo e
saneia slots legados antes do retorno ao jogo.

## 2. Requisitos

- **R1** — `should_checkpoint` é falso durante combate ativo.
- **R2** — `snapshot`, `maybe_write` e `save_checkpoint` recusam estado ativo.
- **R3** — checkpoint legado ativo é restaurado fora do combate, sem inimigos,
  com jogador consciente/vivo e Vitalidade mínima 1.
- **R4** — histórico e três relógios continuam preservados.

## 3. Design e plano

Testes primeiro em `tests/test_longrun_remediation_v3.py`; guardas em
`services/checkpoints.py` e `persistence.py`; smoke de morte/restore no harness.

## 4. Aceite

- [x] Nenhum checkpoint novo ativo.
- [x] Slot legado não reabre conflito.
- [x] Longrun não repete o mesmo conflito após morte.
- [x] `uv run pytest` verde.

## 5. LLM real e riscos

Não exige LLM. O saneamento preserva progresso e só encerra a cena transitória.

## 6. Evidência

Longrun `20260813-085903-974550`: 200/200, seis mortes em seis epochs e zero
replay de conflito. Restore sempre retomou fora da cena letal.
