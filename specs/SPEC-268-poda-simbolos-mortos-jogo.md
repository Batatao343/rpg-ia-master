# SPEC-268 — Apagar símbolos mortos do motor de jogo

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Um scan por AST + contagem de tokens em todo o repo (código, testes, evals, scripts,
JSON/YAML/TOML/SQL/MD fora de `docs/`/`specs/`) encontrou símbolos de topo do lado jogo
**sem nenhuma referência fora da própria definição**, nem em testes. Cada um foi
reconfirmado com `git grep -w <nome>`; os únicos outros hits estão em docs/specs históricas.

| Símbolo | Local | Linhas | Nota |
|---|---|---|---|
| `last_safe_location` | `world_utils.py:766` (+ `_SAFE_LOC_TAGS` e `_APEX_TAG` se ficarem órfãos) | ~23 | resto do "O Saque", aposentado na sessão 23 |
| `make_armor`, `make_shield` | `gamedata.py:225,235` | ~14 | |
| `cards_at_patamar` | `services/cards.py:184` | 7 | |
| `FactionIntel` | `state.py:271` | 6 | TypedDict sem uso |
| `last_stand_roll` | `services/death_flow.py:112` | 4 | |
| `abyss_signature` | `services/abyss_events.py:176` | 2 | |
| `pending_projections` | `services/projections.py:250` | 3 | |
| `XP_BY_TIER` | `progression.py:22` | 1 | |
| `ENCOUNTER_COOLDOWN_TURNS` | `services/npc_layers.py:150` | 1 | |
| `PURSUIT_POLICIES`, `TIPOS`, `RESISTENCIAS` | `services/tactical_profile.py:154,20,21` | 3 | |
| `_write_checkpoint_if_due` | `api.py:3846` | ~13 | helper privado sem chamador |
| `save_custom_artifact` | `gamedata.py:54` | ~23 | só `tests/test_runtime_cache.py:97` chama; o loot não grava mais item custom. Apagar junto a assert do teste, mantendo o teste do overlay de runtime por outro caminho |

Total estimado: **~100 linhas**.

## 2. Requisitos

- **R1** — Antes de apagar cada símbolo, rodar de novo
  `git grep -nw <nome> -- ':!docs' ':!specs' ':!handoffs' ':!proximas-specs' ':!project_index/repo_graph.json'`
  e conferir que só a definição aparece. Procurar também uso dinâmico: `getattr(`, `__all__`, strings.
- **R2** — Apagar o símbolo; apagar imports/constantes privadas que só ele usava.
- **R3** — Não mexer em nada listado em "não podar" no relatório.

### Fora de escopo

Funções usadas só por testes (SPEC-272); infraestrutura (SPEC-269).

## 3–4. Design e plano

Uma remoção por commit lógico (ou um commit só, com o diff revisável). `uv run ruff check .`
detecta import órfão.

## 5. Critérios de aceite

- [ ] R1 registrado no PR (saída do grep)
- [ ] `uv run ruff check .` e `uv run pytest` verdes
- [ ] `uv run python -m playtest run --all --turns 3` sem erro/violação (MockLLM)
- [ ] Project Index regenerado em checkout limpo

## 6. Smoke

Nenhum smoke LLM (código morto não roda).

## 7. Riscos & compatibilidade

Risco **baixo**. Sem efeito em save/schema. Rollback: `git revert`.
