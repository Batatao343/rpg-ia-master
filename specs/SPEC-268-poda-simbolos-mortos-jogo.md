# SPEC-268 — Apagar símbolos mortos do motor de jogo

> **Status:** `done` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (`_APEX_TAG` fica; `save_custom_artifact` opcional; ver §8)
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
| `last_safe_location` | `world_utils.py:766` (+ `_SAFE_LOC_TAGS`; **`_APEX_TAG` fica**: `world_utils.py:573,799` usam) | ~23 | resto do "O Saque", aposentado na sessão 23 |
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
| `save_custom_artifact` *(opcional, revisão)* | `gamedata.py:54` | ~23 | só `tests/test_runtime_cache.py:97` chama; é o único escritor do overlay `custom_artifact` (SPEC-051). Apagar remove `test_custom_artifact_no_overlay` inteiro; o overlay genérico segue coberto pelo teste de NPC (`:85-92`). Se o dono preferir manter o gancho para loot custom futuro, sai da lista |

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

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

Verificado com `git grep -nw` (fora de docs/specs/handoffs/proximas-specs/índice): cada símbolo da tabela
só aparece na definição, exceto os abaixo. Sem uso dinâmico: os únicos `getattr(` sobre módulo em produção
são `playtest/latency_llm.py:185` (`get_llm`) e `playtest/runner.py:631` (lista explícita); nenhum `make_*`
montado em string. `_write_checkpoint_if_due` está superado pelos caminhos de checkpoint em
`api.py:3454/3522/3786` (sem perda de funcionalidade).

Achados:
1. `_APEX_TAG` **não fica órfão**: `world_utils.py:573,799` usam (e `services/cards.py` tem cópia própria).
   A tabela agora diz para mantê-lo.
2. `save_custom_artifact` é o único escritor do overlay `custom_artifact` da SPEC-051; virou item opcional.
