# SPEC-234 — Memória/RAG: arquivista resiliente a falha de índice, segredos por ID de entidade, pin de embeddings com override e contexto

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-039 embeddings-provider, SPEC-085 hardening-memoria-proveniencia, SPEC-037 beats-visibilidade-ptbr e SPEC-005 fase-2.8-context-builder `done` são corrigidas. Corrige o hot path ANTES de SPEC-213/214 reprojetarem a arquitetura (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-206, SPEC-212, SPEC-213, SPEC-214 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-05-01..05-16 (`achados/05-memoria-rag-contexto.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — toca visibilidade de segredos (R3) e o ledger de proveniência
> **EVAL_AUTHORING_REQUIRED:** `true` — o corpus memory/context (SPEC-170) deve ganhar casos "índice indisponível" e "segredo revelado por ID real" (autoria separada; implementador não edita o dataset)

---

## 1. Contexto & Objetivo

Reproduções executadas pelo orquestrador (`r1.py`, `r7.py`, `r8.py` da área 05) no HEAD `d6af933`:

- [F] **Resumo congela quando o índice falha** — `agents/archivist.py:313-329`: com `pending_memory_facts` e
  `_persist_memory_records` falhando, o nó retorna ANTES do LLM/resumo/crônica/`archivist_last_run`; `_should_archive`
  (`:183-197`) é `True` enquanto houver pendentes → loop. Repro: 3 turnos → `summary = "Resumo do turno 1"`, `ledger 0`,
  `llm_calls 1`. O ledger só recebe fatos após o write físico (contradiz o comentário "ledger dá continuidade" em
  `context_builder.py:514`). Cenários reais: zero-config/DeepSeek-only sem embeddings, Jina fora do ar, índice corrompido.
- [F] **Chaves de segredo ≠ IDs de entidade** — `services/secret_signatures.SECRET_SIGNATURES` usa `pacto_valerius`,
  `rede_carmesim`, `arauto_identidade`, `rei_subterraneo`; `memory_provenance.accepted_secret_ids` (`:154-168`) coleta
  `target_id`/`payload.secret_id` de `secret_revealed`; o validador (`world_validators._v_secret_revealed`) exige entidade
  REAL (`mon_rei_subterraneo`, `mon_rede_carmesim`); `pacto_valerius`/`arauto_identidade` não existem em `entities.json`
  (só `npc_o_arauto_da_nevoa`). Repro: reveal aceito de `mon_rei_subterraneo` → `find_strict_unrevealed` ainda
  `rei_subterraneo` → `validate_narrative` apaga a frase (`text=''`), fato recusado, contexto censurado. O teste existente
  usa `target_id="pacto_valerius"` (que o validador rejeitaria).
- [F] **Override de embeddings desativa o índice na reabertura** — `rag._resolve_provider` (`:433-443`) aceita
  `RPG_EMBEDDINGS=<p>` sem checar disponibilidade (escrita OK e pin gravado); `_embeddings_for_index` (`:519-540`) exige
  `_provider_available(p)` (ollama → `OLLAMA_HOST`; jina → só `JINA_API_KEY`, ignora `JINA_AUTH_TOKEN` que `_build_jina`
  aceita). Repro: `write1 True`, "índice DESATIVADO", `write2 False`, `query ''`. O modo 100% local documentado quebra
  no 2º fato; via o 1º bug, o resumo congela.
- [F] Médias (leitura/execução do subagente): resumo salvo como `""` quando o `validate_narrative` do wrapper rejeita
  todas as frases (`archivist.py:213-216`); `FallbackLLM` grava a mensagem de erro como resumo (`_extract_summary_plain`,
  `:75-91`); "Quem controla X" nunca emitido porque `context_builder.py:204,223` consulta por NOME e o grafo por ID — e
  o conserto ingênuo vazaria o controlador `hidden` (`get_current_controller(include_hidden=True)`); `search_chronicle`
  `KeyError` (500) para candidato semântico stale (`chronicle_search.py:80-81`); orçamento do context pack descarta
  fatos recentes e RAG relevante antes de fatos antigos (`context_builder.py:344-367,512-533`); pgvector perde rótulos
  de proveniência (`rag.py:738-924` vs `_format_memory_documents`); `embedding_profile_id="local-1024"` não identifica
  provider/modelo (`pgvector_memory.py:27`).
- [F] Baixas: `revealed_corpus` lê `projection["facts"]` (chave é `revealed_facts`, `secret_signatures.py:60`);
  `commit_memory_facts` duplica com ledger legado repetido; exceções de consulta RAG engolidas sem log (`rag.py:822-879,
  1295`); `validate_narrative` colapsa parágrafos; `npc_data["memory"]` sem teto; alias `JINA_AUTH_TOKEN` inconsistente.

Objetivo: o ledger `memory_facts` é a fonte primária (índice vetorial é derivado e pode faltar); o resumo de curto
prazo nunca congela nem é substituído por vazio/erro; segredos são identificados por ID de entidade do grafo; o
pin de embeddings respeita o override; contexto prioriza relevância+recência e nunca vaza `hidden`.

## 2. Requisitos

- **R1** — [R] `archive_node`: falha de `_persist_memory_records` NÃO retorna cedo — commita os registros validados no
  ledger `memory_facts` com `vector_status="pending"`, mantém `pending_vector_writes` para retry com backoff
  (tentar no máximo 1× a cada 3 turnos), e segue para resumo/crônica/`archivist_last_run`. Teste de reprodução: 3 turnos
  com índice falhando → `llm_calls 3`, resumo avança, `ledger 3`, `pending_vector_writes 3`.
- **R2** — [R] `context_builder` lê o ledger (inclusive `vector_status="pending"`) como memória de curto prazo mesmo com
  índice indisponível; `context_sources` registra `status="degraded"` com log `WARNING` (R10). Teste: índice fora →
  bloco de memória contém os fatos do ledger.
- **R3** — [R] Mapa explícito `SECRET_ENTITY_IDS: dict[str, set[str]]` (`rei_subterraneo → {mon_rei_subterraneo}`,
  `rede_carmesim → {mon_rede_carmesim}`, `arauto_identidade → {npc_o_arauto_da_nevoa}`, `pacto_valerius → {npc_valerius,
  …}` — IDs reais verificados em `entities.json`; lint de conteúdo falha se um ID não existir). `accepted_secret_ids`
  devolve a união `{secret_id} ∪ entity_ids` para cada `secret_revealed` aceito; `revealed_corpus` lê
  `projection["revealed_facts"]`. Teste de reprodução: reveal aceito de `mon_rei_subterraneo` → frase do verme passa,
  fato aceito, contexto inclui. Teste existente corrigido para usar ID real.
- **R4** — [R] `_embeddings_for_index`: se `RPG_EMBEDDINGS` == provider pinado, usa `get_embeddings_for(provider)` sem
  `_provider_available`; `_provider_available("jina")` aceita `JINA_AUTH_TOKEN` via helper único `_jina_key()`;
  `_provider_available("ollama")` aceita `OLLAMA_HOST` OU override. Teste de reprodução: `write1 True, write2 True,
  query != ''`.
- **R5** — [R] Resumo nunca vazio/erro: `narrative_summary = check.text or compact_summary(anterior) or "A aventura
  segue."`; `_extract_summary_plain` devolve `""` quando `getattr(llm, "is_fallback", False)` ou o conteúdo começa com
  prefixo de erro conhecido (`RoutedLLM`/`FallbackLLM`). Testes: `r5.py` e `r2.py` da área 05 → resumo anterior preservado.
- **R6** — [R] `build_context_pack` consulta grafo/`location_summaries` por `world.current_location_id` e passa
  `include_hidden=(purpose == "planning")`; nome só para scoring. Teste: `Montanhas Afiadas` com edge `hidden` →
  narrador NÃO recebe "O Rei Subterrâneo"; planner recebe.
- **R7** — [R] `search_chronicle`: candidato ausente em `documents` é ignorado (`continue`) e filtrado por capítulos
  atuais; nunca `KeyError`. Teste: candidato `"{cid}:digest"` stale → resultado sem exceção.
- **R8** — [R] Ordem do bloco de memória sob orçamento: (1) resumo, (2) RAG relevante (sessão/NPC), (3) ledger do
  mais NOVO para o mais antigo. Teste de reprodução: `token_budget=1500` → `RELEVANTE in memory_block == True`, fatos
  presentes = os mais recentes.
- **R9** — [R] Perfil hospedado (pgvector): resultados passam por `_format_memory_documents` (rótulos de proveniência,
  k efetivo, dedupe) — paridade com legacy; `embedding_profile_id = f"{provider}-{model}-{dim}"` e consulta filtra por
  ele; provider com dimensão ≠ 1024 recusado na inicialização com erro claro. Teste: documento gravado com perfil A não
  é retornado por consulta com perfil B.
- **R10** — [R] Toda consulta RAG com exceção loga `WARNING` com `exc_info` e incrementa métrica `rpg.rag.degraded{source}`;
  `_save_index` escreve em diretório temporário + rename (atômico); `embeddings_meta.model` comparado na reabertura
  (modelo diferente → índice desativado com mensagem, não vetor misto).
- **R11** — [R] `commit_memory_facts` deduplica `order` (`dict.fromkeys`); `validate_narrative` preserva separadores
  originais; `npc_data["memory"]` capado em `[-20:]`.

### Fora de escopo

- Arquivista assíncrono/projeções (SPEC-213), L1/L2/L3 (SPEC-214), conhecimento por NPC (SPEC-215), taxonomia visível
  (SPEC-206) — esta spec entrega o mapa de IDs que a 206 consome.
- Troca de provider de embeddings ou re-index do Codex.

## 3. Design técnico

### Arquivos alterados

- `agents/archivist.py:75-91,183-197,213-216,313-329,411-428` — R1, R5.
- `services/memory_provenance.py:154-179,497-515` — `vector_status`, R3, R11.
- `services/secret_signatures.py:16-34,60` — `SECRET_ENTITY_IDS`, `revealed_facts` (R3); `services/content_validator.py`
  — lint dos IDs.
- `rag.py:361,416-443,519-540,738-924,822-879` — R4, R9, R10.
- `services/context_builder.py:204,223,344-367,512-533` + `context_sources.py:122-126` — R2, R6, R8.
- `services/chronicle_search.py:80-81` — R7. `infrastructure/pgvector_memory.py:27`, `infrastructure/runtime.py:418-428`,
  `workers/run_worker.py:85-98` — perfil de embedding (R9).
- `agents/npc.py:557` — teto (R11). `services/narrative_evidence.py:99-110` — separadores (R11).

### Schemas

```python
class MemoryFact(TypedDict, total=False):
    memory_id: str; text: str; provenance: str; confidence: float; source_turn: int
    vector_status: Literal["written", "pending", "failed"]      # novo, default "written" para legado
SECRET_ENTITY_IDS: dict[str, frozenset[str]]
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_memoria_resiliencia.py`: `test_archivist_continues_when_index_fails` (R1), `test_context_uses_ledger_when_
index_down` (R2), `test_secret_revealed_by_entity_id_unlocks` (R3), `test_embeddings_override_reopens_pinned_index` (R4),
`test_summary_never_empty_or_error` (R5), `test_controller_by_id_without_hidden_leak` (R6), `test_search_chronicle_stale_
candidate` (R7), `test_memory_budget_prefers_recent_and_relevant` (R8).
### Etapa 1 — R1, R2, R5 (arquivista/ledger)
### Etapa 2 — R3 + lint (segredos por ID) — revisão `Sol` obrigatória nesta etapa
### Etapa 3 — R4, R10 (rag.py) · R6, R7, R8 (contexto/crônica) · R9 (hospedado) · R11
### Etapa 4 — regressão `uv run pytest` + playtest offline 3 perfis × 40 turnos com `_offline_embeddings` desligado
(índice indisponível de propósito): resumo avança todo turno (invariante nova `memory.summary_frozen`, error).

## 5. Critérios de aceite

- [ ] 8 testes vermelhos → verdes; `tests/test_memory_provenance.py` (teste de segredo corrigido para ID real),
      `test_embeddings_provider.py`, `test_archivist_facts.py`, `test_fase28.py`, `test_beats_visibilidade.py`,
      `test_chronicle_search*.py` verdes ou diff justificado.
- [ ] `uv run pytest` verde; playtest offline com índice indisponível sem `memory.summary_frozen`.
- [ ] Saves antigos carregam (`vector_status` default).
- [ ] Guard de FallbackLLM mantido no archivist (R5 reforça).

## 6. Smoke test com LLM real

1. Sem `JINA_API_KEY` (só DeepSeek): 3 turnos → resumo avança; `rag.degraded` no log; ao repor a key, pendentes gravados.
2. Revelar o segredo do Rei Subterrâneo por evento aceito → narração seguinte cita o verme sem censura.
3. `RPG_EMBEDDINGS=jina` com `JINA_AUTH_TOKEN` apenas → memória grava e consulta em 2 turnos seguidos.

## 7. Riscos & compatibilidade

- R3 muda o que o narrador pode dizer após reveal (correto) — invariante `knowledge.secret_leak` do playtest passa a usar
  o mesmo mapa (ajustar `playtest/invariants.py`).
- R1 aumenta chamadas ao LLM do arquivista em cenário de índice fora (antes 1 total; agora 1/turno elegível) — é o
  comportamento esperado; custo coberto pela cadência `_ARCHIVE_EVERY`.
- R9 exige migração do `embedding_profile_id` em `app.memory_documents` (hospedado): migration idempotente que renomeia
  `local-1024` → perfil do provider configurado, documentada no README.

## 8. Pontos de decisão do dono

- **D-A (`pacto_valerius` entidade-alvo):** mapear para `npc_valerius` (se existir) ou criar entidade `sec_pacto_valerius`
  no grafo com edge `hidden`; default: mapear para as entidades existentes envolvidas e documentar.
- **D-B (backoff do retry vetorial):** 3 turnos (default) ou exponencial.

## 9. Evidência requerida

- `uv run pytest` completo; testes antes/depois; run_id do playtest com índice indisponível.
- `docs/<spec>/README.md` com `r1.py`/`r7.py`/`r8.py` transcritos, lista `SECRET_ENTITY_IDS` validada pelo lint e revisão `Sol`.
- **Handoff de eval (EVAL_AUTHORING_REQUIRED):** casos para o corpus SPEC-170 — "store com índice indisponível →
  retrieve pelo ledger" e "secret_revealed por ID real → generation sem censura" — autoria separada, relock de hash.
