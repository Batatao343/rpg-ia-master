# SPEC — Progresso observável e teto de fuga

> **Status:** `done`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** `telemetria-rollback-abort` (`done`)

## 1. Contexto & Objetivo

Uma perseguição variou de track por onze tentativas, escapou, mas disparou
`combat.no_progress`. O fingerprint ignora chase e a duração não tem teto.

## 2. Requisitos

- **R1** — Fingerprint inclui track/flags mecânicas da perseguição.
- **R2** — Mudança de track zera streak de no-progress.
- **R3** — Após no máximo seis tentativas consecutivas, perseguidores perdem o
  rastro e a fuga termina deterministicamente quando há destino válido.
- **R4** — Estado de tentativas é local ao conflito e não vaza à próxima cena.

### Fora de escopo

Alterar dano, dificuldade de testes ou comportamento de perfis agressivos.

## 3. Design técnico

`combat.flee_attempts` conta tentativas; `agents/combat.py` aplica o teto Python.
`playtest/invariants.py` inclui chase no fingerprint.

## 4. Plano passo a passo

1. Testar fingerprint e teto em `tests/test_longrun_remediation_v4.py`.
2. Implementar contador/escape e limpeza no fim.
3. Rodar longrun mock normal.

## 5. Critérios de aceite

- [x] Chase real não gera falso `combat.no_progress`.
- [x] Fuga termina em até seis tentativas consecutivas.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Aceite MockLLM `20260816-113051-596798`: 20 decisões de fuga, sete conflitos
encerrados e zero `combat.no_progress`/violação. A mecânica permanece sem
invoke LLM; o smoke real dirigido validou a borda do router.

## 8. Resultado

O fingerprint inclui o snapshot fechado do chase. `flee_attempts` é reiniciado
por ação não-fuga e removido junto com a cena; a sexta tentativa com destino
adjacente válido encerra a perseguição deterministicamente.

## 7. Riscos & compatibilidade

Saves sem `flee_attempts` assumem zero; mecânica permanece determinística.
