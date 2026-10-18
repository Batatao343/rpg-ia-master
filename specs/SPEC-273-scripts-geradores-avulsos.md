# SPEC-273 — Aposentar geradores de uso único e unir os leitores de .env dos scripts

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

- `scripts/gen_world_living_npcs.py` (186 linhas, último commit 2026-08-11) escreveu os
  36 NPCs da conflito-17, hoje curados em `data/codex` e no grafo.
- `scripts/gen_tiers_5_plus.py` (148 linhas, 2026-08-20) gerou as 80 Cartas tardias em `data/cards`.

Nenhum dos dois tem teste, CI, guia ou referência em CLAUDE/AGENTS; o único hit é uma
lista em `docs/descricao_projeto/fontes/exploracao/explore_06_qualidade.md`.
Diferente deles, `gen_classes_v2.py`, `gen_cards_v4.py`, `migrate_lore_nova.py`,
`migrate_bestiary_v4.py` e `import_visual_assets.py` são fonte documentada ou têm teste: ficam.

Também há dois leitores de `.env` escritos à mão: `_dotenv()` em
`scripts/release/checklist.py:340` e `load_env()` em `scripts/staging/s192.py:26`.
O projeto já depende de `python-dotenv`.

## 2. Requisitos

- **R1** — Confirmar que os dados gerados não são regerados por esses scripts: rodar cada
  um em diretório temporário (sem gravar no repo) **ou** checar se o docstring diz que é a
  fonte de verdade. Se algum for fonte de verdade, ele fica e vai para `docs/guias/AUTORIA.md`.
- **R2** — Os que não forem fonte: `git rm`.
- **R3** — Trocar os dois leitores por `dotenv.dotenv_values(path)` mantendo o comportamento
  (precedência env > arquivo, se existir hoje) e os testes de `tests/test_spec192_staging_scripts.py`.

### Fora de escopo

`scripts/staging/*` de runbook (incident_drill, security_wave_smoke, voice_smoke…): são
ferramentas de operação citadas por runbooks da SPEC-197. Avaliar à parte com quem opera.

## 5. Critérios de aceite

- [ ] `uv run pytest` verde (inclui os testes de scripts de staging)
- [ ] `uv run python scripts/validate_content.py` sem erro
- [ ] `uv run python scripts/release/checklist.py --help` e `s192.py --help` funcionam

## 7. Riscos & compatibilidade

Risco **baixo**: perder a receita de geração. O histórico git guarda o script. Rollback: `git revert`.
