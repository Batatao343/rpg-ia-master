# SPEC-405 · revisão (Sonnet) · APPROVED

Escopo: `git diff main...HEAD` (30 arquivos). Testes focados: 9 arquivos (memory_provenance, conflict_summary_lifecycle,
grounding_boundaries, bug_memoria_resiliencia, spec378_text_fold, latency_timeline, narrative_evidence,
npc_identity_grounding, playtest_observability_hardening) verdes com -n 2. `ruff check` e `ruff format --check`
limpos nos 25 .py do diff; `import playtest.telemetry, observability.latency, api` sem ciclo.

## Etapa 4 (archivist)
- `rag.add_memory_to_session` (rag.py:1462) aceita `metadatas` keyword-only. Único backend real; não há adapter alternativo.
- `playtest/runner.py:661` `_write_session` já aceita `metadatas`; o stub de 2 args não existe mais no caminho do archivist.
- Grep em tests/playtest/evals/scripts/services/routes: todos os stubs do archivist aceitam `**kwargs`
  (lambdas e `_add(*_a, **_k)`); `world_simulator` chama com 2 args direto no `rag` real (ok).
- Tratamento de exceção e logs (`rag_persist_failed`) idênticos; só saiu o ramo de `inspect.signature`.
- Stubs alterados só ganharam `**_kwargs`; nenhuma asserção mudou. Dois testes novos cobrem o envio de `metadatas` e a falha do RAG.
- `inspect` continua usado (D1, `add_npc_memory`), sem import órfão.

## Etapas 2-3 (poda)
Reconferi grep em todo o repo (py/ts/yaml/json/md, sem .venv/node_modules): `CalendarDate`, `utc_now`, `run_with_context`,
`reload_config`, `_error_code_of`, `ARMADURAS`, `ESCUDOS`, `_MEMORIAL_DETAIL`, `_soul_for_quest`, `has_curated_art`,
`_debug_scores`, `CrimeCandidate`/`PrisonerRef`/`LawReceipt`, `seed_from_proposal`, `seed_ids`, `deed_event_types`,
`search_intent`: zero usos restantes (nem string/getattr). `ARMADURAS` aparece só em doc narrativo de exploração.
`services/error_codes.py:14` `_CODE_RE` intacto. `datetime` ainda é usado em `auth_sessions`. Sem import com efeito colateral removido (ruff limpo, imports só de typing/TypedDict).

## Etapa 5 (fold)
`services/text.py::fold`: NFKD, remove combinantes, `casefold` ou `lower`, `strip`/`collapse` opcionais.
- `plot_threads._fold` = `fold(text, collapse=True)`: idêntico ao corpo antigo (casefold + split/join).
- `world_utils._fold_txt` = `fold(s, case="lower")`: idêntico (lower, sem strip/colapso, `str(s or "")`).
- Oráculo `tests/test_spec378_text_fold.py` ganhou os dois legados em `SITES` com os mesmos kwargs.

## Etapa 6
`playtest.telemetry._percentile` agora é alias de `observability.latency.percentile` (corpo idêntico, nearest-rank);
teste de identidade novo. Sem ciclo; `observability/latency.py` só importa stdlib. Custo de import desprezível.

## Escopo e qualidade
Nenhuma função nova > 60 linhas; sem mudança fora da spec; sem `evals/` tocado; sem except largo novo.

## Achados
- P0: nenhum. P1: nenhum.
- P2-1 (informativo): `docs/descricao_projeto/fontes/exploracao/explore_02_mecanica.md:478` cita `ARMADURAS`; doc histórico, não precisa mudar.

Veredito: APPROVED
