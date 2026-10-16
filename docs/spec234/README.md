# SPEC-234 - evidencia

Mudancas: arquivista nao congela com indice vetorial fora (ledger primario, `vector_status`, retry a cada 3 turnos);
resumo nunca vazio/erro; segredos liberados por ID de entidade real (`data/secret_entities.json` + lint);
`RPG_EMBEDDINGS`/`JINA_AUTH_TOKEN`/`OLLAMA_HOST` respeitados na reabertura; verificacao de modelo na meta;
`_save_index` atomico; controlador do local por ID sem vazar `hidden`; ordem de orcamento resumo > RAG > ledger recente;
`search_chronicle` ignora candidato stale; rotulos de proveniencia no pgvector; invariante `memory.summary_frozen`.

Testes: `tests/test_bug_memoria_resiliencia.py` (12), +3 em `tests/test_embeddings_provider.py`; 5 testes de
`test_conflict_summary_lifecycle.py` e 1 de `test_memory_provenance.py` atualizados ao novo contrato.
Suite completa offline verde; playtest offline (embeddings desligados) explorador/normal/quester x 40 turnos:
0 erros, 0 violacoes (runs 20261016-015624-665565, -015627-997279, -015631-773437). Eval memory_context
(tests/test_eval_memory_context.py) verde, `evals/` intocado.

R9 (perfil por provider/modelo/dim, recusa dim!=1024, migrate_legacy_profile) e metrica rpg_rag_degraded_total implementados. Validado em Postgres local (infra_local) e evals CI verdes.

## Revisão e smoke real (2026-10-16, coordenador)

- Revisão Sol independente: APPROVED_WITH_FOLLOWUPS; corrigidos perfil de embedding divergente entre staging de turno e
  consulta (`configured_profile_id`), filtro `embedding_profile_id` na busca vetorial e liberação de segredo por id vindo
  do LLM (só `target_id` validado). `infra_local` em Supabase local: 5 + 18 passed.
- Coordenador: métrica `rpg_rag_degraded_total` também em índice desativado (`index_disabled`) e falha de escrita de
  sessão (`session_write`); fatos pendentes só reabrem o arquivista na janela de retry (sem SMART por turno, §7).
- Smoke real (DeepSeek, API legacy): sem `JINA_API_KEY`, 3 turnos → resumo avança (834→1058→1024 chars), ledger 4→9→15
  fatos `pending`, métrica `session_write`=3. Com só `JINA_AUTH_TOKEN` + `RPG_EMBEDDINGS=jina`: memória gravada
  (índice de NPC criado). Reveal por evento (§6.2) coberto offline.
- Deploy hosted: rodar `scripts/migrate_embedding_profile.py` junto do deploy (documentos `local-1024` saem da busca
  semântica até migrar). Follow-up conhecido: `npc_o_arauto_da_nevoa` sem edge hidden/secret (fail-closed).
