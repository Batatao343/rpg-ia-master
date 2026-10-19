# Auditoria de bugs funcionais — Área 05: Memória / RAG / contexto / arquivista / crônica

Data: 2026-10-15 · Prefixo: `BUG-05-nn` · Somente leitura + scripts offline (MockLLM/embeddings fake).

**Arquivos cobertos (lidos por inteiro):** `rag.py`, `services/context_builder.py`, `services/context_sources.py`,
`services/memory_provenance.py`, `services/memory_intents.py`, `services/memory_retry.py`, `services/memory_summary.py`,
`agents/archivist.py`, `agents/librarian.py`, `services/chronicle.py`, `services/chronicle_repository.py`,
`services/chronicle_search.py`, `services/chronicle_compression.py`, `workers/chronicle_jobs.py`, `workers/embedding_jobs.py`,
`infrastructure/pgvector_memory.py`, `services/secret_signatures.py`, `services/narrative_evidence.py`,
`services/codex_loader.py`; trechos de `agents/npc.py` (escrita de memória), `agents/campaign_manager.py` (abertura de capítulo),
`services/event_processor.py`, `services/graph_resolver.py`, `services/world_validators.py`, `infrastructure/runtime.py` (embedder).

**NÃO cobertos:** `services/turn_effects.py` / `infrastructure/postgres_turns.py` (commit de memória hospedada, só leitura parcial),
`services/checkpoints.py` (restore × FAISS), `services/discovery.py`, testes de integração Postgres (sem Docker).

**Contagem:** crítica 0 · alta 3 · média 7 · baixa 6 (+ descartados no fim).

Scripts de reprodução (scratchpad): `r1.py` (freeze), `r3.py` (KeyError), `r4.py` (budget), `r5.py` (resumo vazio),
`r6.py` (controlador), `r7.py` (segredo), `r8.py` (ollama pin).

---

### BUG-05-01 — Resumo narrativo congela para sempre enquanto a escrita RAG falha (archivist retorna cedo)
- **Severidade:** alta
- **Categoria:** estado-inconsistente
- **Local:** `agents/archivist.py:313-329` (retry de `pending_memory_facts`), `agents/archivist.py:411-428` (retry de NPC), `agents/archivist.py:196-197`/`:912` (`archive_due = bool(pending)`)
- **Evidência:**
  ```python
  if pending_memory_facts:
      retry_records, ... = _validate_candidates(...)
      if retry_records and not _persist_memory_records(game_id, retry_records):
          return {**event_updates, "archive_due": True, "memory_facts": memory_facts,
                  "pending_memory_facts": retry_records, ..., "rag_persistence_error": "..."}
  ```
  Enquanto `add_memory_to_session` devolver `False`, TODO turno cai neste `return` ANTES do LLM, do `narrative_summary`, da crônica
  e do `archivist_last_run`. `_should_archive` fica True (há `pending_memory_facts`), então nunca sai do laço.
  O ledger `memory_facts` também só recebe fatos APÓS o write físico — o comentário "ledger dá continuidade se o índice estiver
  indisponível" (`context_builder.py:514`) nunca se cumpre: com o índice fora, o ledger fica vazio.
- **Reprodução:** `r1.py` — `add_memory_to_session` stubado para `False` (equivale a "sem provider de embeddings", p.ex. só DeepSeek sem Jina/OpenAI/Google, ou índice corrompido), 3 turnos de archivist:
  ```
  10 llm_calls 1 summary= Resumo do turno 1. pending= 1 ledger= 0 due= True
  11 llm_calls 1 summary= Resumo do turno 1. pending= 1 ledger= 0 due= True
  12 llm_calls 1 summary= Resumo do turno 1. pending= 1 ledger= 0 due= True
  ```
  Esperado: `narrative_summary` avançar a cada turno (a falha de RAG não deveria bloquear a memória de curto prazo). Observado: 1ª chamada ao LLM, depois congelado.
- **Impacto:** em qualquer setup sem embeddings (zero-config/DeepSeek-only, Jina fora do ar, `_save_index` interrompido deixando `index.faiss`/`index.pkl` inconsistentes, ver BUG-05-03) o narrador perde a memória de curto prazo após o 1º turno de falha; o jogo "esquece" tudo que aconteceu depois. Amplificado por BUG-05-03.
- **Correção sugerida:** no retry falho, NÃO retornar cedo: seguir o fluxo normal (resumo/crônica) mantendo `pending_memory_facts`; ou aplicar backoff (`archive_due` só a cada N turnos) e commitar no ledger mesmo sem write vetorial (ledger é fonte primária; índice é derivado).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_memory_provenance.py::test_archivist_falha_atomica_deixa_fato_pendente_e_retry_nao_duplica` (cobre 1 falha + 1 sucesso; não cobre falha persistente nem o resumo).

### BUG-05-02 — Chaves de `SECRET_SIGNATURES` ≠ IDs de entidade: `secret_revealed` legítimo nunca "libera" o segredo (narração e memória continuam censuradas)
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `services/memory_provenance.py:154-179` (`accepted_secret_ids`/`find_strict_unrevealed`), `services/secret_signatures.py:16-34`, `services/world_validators.py:41-52`
- **Evidência:** `find_strict_unrevealed` só desarma `secret_id` ∈ {`target_id`, `payload.secret_id`, `payload.id`} de eventos `secret_revealed`. As chaves são `pacto_valerius`, `rede_carmesim`, `arauto_identidade`, `rei_subterraneo`. Mas o validador exige `target_id` = entidade REAL do grafo (`mon_rei_subterraneo`, `mon_rede_carmesim`, `npc_...`); `pacto_valerius` e `arauto_identidade` nem existem em `entities.json`. O teste existente usa `target_id="pacto_valerius"` (ID que o validador rejeitaria) — por isso passa.
- **Reprodução:** `r7.py`:
  ```
  entity pacto_valerius: False | mon_rei_subterraneo: True
  evento aceito: secret_revealed target=mon_rei_subterraneo
  strict: rei_subterraneo            # ainda "não revelado"
  NarrativeCheck(text='', rejections=[{'reason': 'unrevealed_secret', ...}])
  ```
  Esperado: após o reveal aceito, a frase "…medo do verme-primordial das raízes do mundo" passa. Observado: removida.
- **Impacto:** depois que o jogador de fato descobre o segredo, `guard_current_messages` (archivist) apaga as frases da narração (a mensagem inteira vira "Você observa a cena e pondera seu próximo passo." se só havia essa frase), `validate_memory_fact` recusa o fato (`unrevealed_secret:*`, nunca vira ledger/RAG) e `build_context_pack` descarta memórias. Para `pacto_valerius`/`arauto_identidade` NUNCA há como desarmar por evento aceito. O arco de revelação fica inconsistente com o `event_log`.
- **Correção sugerida:** mapa explícito `secret_id → {entity_ids}` (ou campo `secret_id` no payload preenchido por Python a partir do edge hidden) e usar a união no `accepted_secret_ids`; alinhar o teste ao ID real.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_memory_provenance.py::test_segredo_exige_secret_revealed_aceito_para_o_mesmo_id` (usa ID inválido no grafo).

### BUG-05-03 — `RPG_EMBEDDINGS=<provider>` (override) grava índice pinado, mas a leitura exige disponibilidade pela cadeia → índice "DESATIVADO" a partir da 2ª escrita
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `rag.py:416-430` (`_provider_available`), `rag.py:519-540` (`_embeddings_for_index`), `rag.py:433-443` (`_resolve_provider`)
- **Evidência:** `_resolve_provider` aceita o override sem checar disponibilidade e `get_embeddings_for` constrói o provider (ollama sem host explícito, jina via `JINA_AUTH_TOKEN` que `_build_jina` aceita). Mas ao reabrir um índice pinado, `_embeddings_for_index` chama `_provider_available(provider)`, que exige `OLLAMA_HOST` (ollama) / `JINA_API_KEY` (jina; ignora `JINA_AUTH_TOKEN`). O comentário (l.425) diz que o override "é tratado antes desta função" — não é, na reabertura.
- **Reprodução:** `r8.py` (`RPG_EMBEDDINGS=ollama`, sem `OLLAMA_HOST`, builders fake):
  ```
  write1: True
  Índice '...\g1' pinado no provider 'ollama', indisponível agora — índice DESATIVADO.
  write2: False
  query : ''
  ```
- **Impacto:** o modo "100% local" (Ollama) documentado em CLAUDE.md quebra no 2º fato de cada sessão: memória nunca mais é gravada/consultada e, via BUG-05-01, o resumo congela. Mesmo efeito para `RPG_EMBEDDINGS=jina` só com `JINA_AUTH_TOKEN`.
- **Correção sugerida:** em `_embeddings_for_index`, se `RPG_EMBEDDINGS` == provider pinado, pular `_provider_available` e usar `get_embeddings_for`; unificar o alias `JINA_AUTH_TOKEN` em `_provider_available`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum (a suíte de `test_embeddings_provider.py` seta sempre as keys).

### BUG-05-04 — Resumo narrativo vira `""` quando todas as frases são rejeitadas pelo `validate_narrative` (perde o resumo anterior)
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `agents/archivist.py:213-216` (`archive_node`: `result['narrative_summary'] = check.text`), `services/narrative_evidence.py:109`
- **Evidência:** os sanitizadores internos do `_archive_node` caem para `current_summary` (`grounded_summary or current_summary`), mas a validação pós-hoc do wrapper sobrescreve com `check.text`, que é `''` se toda frase foi rejeitada (segredo, posse, região, NPC). Não há fallback ao resumo anterior.
- **Reprodução:** `r5.py` — resumo anterior "Ana chegou a Brekmar…"; LLM devolve resumo de 1 frase com assinatura de segredo não revelado → `narrative_summary` salvo = `''`. No turno seguinte o prompt usa "A aventura segue." (memória de curto prazo zerada).
- **Impacto:** perda total do resumo (não só da frase ofensiva) sempre que o resumo tem 1 frase ofensiva única — comum com LLMs que escrevem resumo de 1–2 frases.
- **Correção sugerida:** `result['narrative_summary'] = check.text or compact_summary(state.get('narrative_summary')) or 'A aventura segue.'`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-05-05 — "Quem controla {local} agora" nunca é emitido em produção (nome × ID) e, se "consertado" ingenuamente, vazaria controlador oculto
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `services/context_builder.py:204` e `:223` (`current_loc = world["current_location"]`), `:440` / `build_context_pack`; `services/graph_resolver.py:127` (`include_hidden=True` por default)
- **Evidência:** `world["current_location"]` é o NOME (`world_utils.py:163`: `dest["name"]`), mas `get_current_controller(current_loc, …)` e `location_summaries.get(current_loc)` comparam com ID. Além disso `get_current_controller` usa `include_hidden=True` (verdade do mundo) sem relação com `purpose`.
- **Reprodução:** `r6.py`:
  ```
  'Brekmar'           -> []                                     # produção (nome)
  'brekmar'           -> ['Quem controla Brekmar agora: O Poder de Kahen.']
  'Montanhas Afiadas' -> []
  'montanhas_afiadas' -> ['Quem controla As Montanhas Afiadas agora: O Rei Subterrâneo.']   # edge visibility=hidden
  ```
- **Impacto:** (1) o fato de maior impacto (impact=1.0) do bloco `current_state` some do prompt; o narrador inventa quem governa o local (mudanças de controle só aparecem se houver evento recente no `event_log`). (2) Latente: usar `current_location_id` sem trocar para `include_hidden=False` (≠ planning) passaria a injetar o controlador oculto "O Rei Subterrâneo" (`e_rei_sub_controla_montanhas`) no narrador.
- **Correção sugerida:** resolver `loc_id = world.current_location_id` para consultas de grafo/summaries (nome só para scoring) e passar `include_hidden=(purpose=="planning")`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum (`grep "Quem controla" tests` vazio).

### BUG-05-06 — `search_chronicle` levanta `KeyError` (HTTP 500) quando um candidato semântico não existe mais na crônica carregada
- **Severidade:** média
- **Categoria:** exceção-engolida / contrato-api
- **Local:** `services/chronicle_search.py:80-81` (`documents[document_id]`), chamado por `api.py:3702`; origem do digest em `services/chronicle_repository.py:142-157` (`overlay` só reanexa digest com `source_hash` idêntico)
- **Evidência:** `overlay` só anexa `chapter["digest"]` se `chapter_source_hash(chapter)` bate; no capítulo ABERTO, basta 1 entrada nova após a compressão para o digest "sumir" do estado, mas o documento `{chapter_id}:digest` continua no pgvector. O ramo hospedado devolve esse candidato semântico e `documents[...]` não tem a chave. `api.py` só captura `ValueError`.
- **Reprodução:** `r3.py` — 21 entradas, candidato semântico `"{cid}:digest"` (ou id de entrada removida):
  ```
  EXC KeyError '76895c1ff6c5511d9c8fdf5e0a2239ba:digest'
  EXC KeyError 'entry-removido'
  ```
- **Impacto:** busca da crônica retorna 500 em campanhas hospedadas assim que o capítulo atual ganha entradas após uma compressão (ou após restore/rewrite da crônica).
- **Correção sugerida:** `if document_id not in documents: continue` (e filtrar por `chapter_id` ∈ capítulos atuais).
- **Confiança:** confirmado por execução (função pura); caminho hospedado provável (sem Postgres local).
- **Testes existentes relacionados:** nenhum cobre semântico stale.

### BUG-05-07 — Orçamento do context pack: memória RELEVANTE (RAG) e fatos recentes são descartados antes de fatos antigos
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `services/context_builder.py:344-367` (score da memória = `1.0 - index*0.0001`), `:512-533` (ordem de inserção), `:289` (`_assemble`, guloso por score)
- **Evidência:** `memory_parts` = [resumo, `ledger[-20:]` em ordem CRONOLÓGICA, RAG de sessão, RAG de NPC]. O score decresce com o índice, então sob pressão de cota (10% + carry) sobrevivem resumo e os fatos MAIS ANTIGOS dos 20; os mais novos e o resultado semanticamente relevante (último) caem.
- **Reprodução:** `r4.py`, `token_budget=1500`, 20 fatos no ledger + 1 trecho RAG relevante:
  ```
  RELEVANTE in memory_block: False
  fatos presentes: ['00','01','02','03','04','05','06','07']   # 08..19 descartados
  ```
  (com 3500 tokens e mundo vazio tudo cabe, por causa do carry; em jogo real o carry é consumido por current_state/relations.)
- **Impacto:** o narrador perde o que acabou de acontecer e a lembrança pertinente à pergunta, mantendo trivia antiga.
- **Correção sugerida:** ordenar candidatos por relevância ao query + recência (mais novo primeiro), RAG recuperado antes do ledger cronológico.
- **Confiança:** confirmado por execução (orçamento reduzido); provável no orçamento default.
- **Testes existentes relacionados:** nenhum cobre prioridade intra-seção da memória.

### BUG-05-08 — `FallbackLLM` no fallback de texto do archivist grava a mensagem de erro como `narrative_summary`
- **Severidade:** média
- **Categoria:** guard-fallback
- **Local:** `agents/archivist.py:75-91` (`_extract_summary_plain`), `:702-748`
- **Evidência:** `FallbackLLM.with_structured_output()` devolve `self`; `.invoke()` devolve `AIMessage(content=error_message)`. O ramo "não é MemoryUpdate" chama `_extract_summary_plain(llm…)` → `llm.invoke` → o texto do erro vira o resumo (nenhum filtro de `is_fallback`). (Com `RoutedLLM` esgotado o conteúdo é `""` e o resumo antigo é preservado — o bug é específico do `FallbackLLM`, usado com `RPG_NO_MOCK=1`.)
- **Reprodução:** `r2.py` com `FallbackLLM("Erro: nenhum provedor de LLM configurado.")` e resumo anterior válido → `SUMMARY -> Erro: nenhum provedor de LLM configurado.`
- **Impacto:** o resumo real é substituído e o texto do erro passa a ser contexto de todos os agentes (e vai a `/game/state`).
- **Correção sugerida:** `if getattr(llm, "is_fallback", False): return ""` em `_extract_summary_plain`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-05-09 — Memória hospedada (pgvector): fatos recuperados perdem rótulo de proveniência
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `rag.py:738-742`, `:804`, `:837`, `:865`, `:921-924` (perfil ≠ legacy usa `document.text` cru) vs `rag.py:686-728` (legacy usa `_format_memory_documents`)
- **Evidência:** no perfil legacy, a memória passa por `_format_memory_documents` (rótulo `[CONFIRMADO|…]`, `k` efetivo 2, dedupe por texto). No hospedado, `"\n---\n".join(document.text)` (k=6) ignora `metadata.memory_provenance/confidence`; `build_context_pack` então rotula o blob inteiro como `[NÃO VERIFICADO | legacy_unverified]` (`context_builder.py:502-503`) — inclusive `canonical_event` e `npc_claim`.
- **Reprodução:** por leitura (sem Postgres local); contraste direto entre os dois ramos de `query_session_memory`.
- **Impacto:** divergência entre perfis: no hospedado o narrador trata tudo recuperado como não verificado e recebe até 6 fatos contra 2 (consome cota).
- **Correção sugerida:** reaproveitar `_format_memory_documents` com os `MemoryDocument` (têm `.metadata`).
- **Confiança:** provável
- **Testes existentes relacionados:** nenhum para o ramo hospedado.

### BUG-05-10 — pgvector: perfil de embedding fixo `local-1024` não identifica provider/modelo; gemini (3072d) falha em silêncio
- **Severidade:** média
- **Categoria:** regra-divergente (regressão do princípio da SPEC-039 "nunca misturar vetores")
- **Local:** `infrastructure/pgvector_memory.py:27`, `infrastructure/runtime.py:418-428`, `workers/run_worker.py:85-98`, `rag.py:746-759`
- **Evidência:** `embed_query`/`query` aceitam QUALQUER provider resolvido por `rag.get_embeddings()` que devolva 1024 dims (Jina v3, OpenAI com `dimensions=1024`, Ollama bge-m3) e gravam na mesma coluna com `embedding_profile_id="local-1024"`. API e worker resolvem o provider cada um pelo seu próprio ambiente; se divergirem (ou a chave mudar), vetores de espaços diferentes coexistem e a similaridade vira ruído, sem erro. Com só `GOOGLE_API_KEY` (gemini-embedding-001 = 3072d) todo job `embed_memory` levanta `ValueError` (5 tentativas) e `prepare_shared_query_vector` devolve `vector=None` com `provider` ≠ None, fazendo `_default_readers` retornar `""` para lore e sessão (contexto vazio sem log além de um warning).
- **Reprodução:** hipótese por leitura (requer Postgres + 2 providers).
- **Impacto:** recuperação semântica degradada/ruidosa sem sinal; contexto vazio no cenário gemini-only.
- **Correção sugerida:** gravar `provider/model` no `embedding_profile_id` (ex.: `jina-v3-1024`) e filtrar a consulta por ele; recusar provider de dimensão ≠ 1024 na inicialização.
- **Confiança:** hipótese
- **Testes existentes relacionados:** nenhum.

### BUG-05-11 — `revealed_corpus` lê `projection["facts"]` (chave inexistente); reveal por ID não desarma assinatura
- **Severidade:** baixa
- **Categoria:** outro (código morto / chave errada)
- **Local:** `services/secret_signatures.py:60`
- **Evidência:** a projeção grava `revealed_facts` (`event_processor.py:76`, `state.py:405`); `revealed_corpus` lê `"facts"` → ramo (2) é código morto. Só `str(event.payload)` funciona e só se o texto do payload contiver literalmente a frase-assinatura; `target_id` (ex. `mon_rei_subterraneo`) nunca casa com as frases. Além disso o item (3) (`narrative_summary`) permite que um vazamento já escrito no resumo desarme a assinatura para sempre (circular).
- **Reprodução:** leitura + `r7.py` (`legacy: ('rei_subterraneo', 'verme-primordial…')` mesmo com evento aceito sem frase no payload).
- **Impacto:** `sanitize_beat` e invariante `knowledge.secret_leak` seguem tratando segredo revelado como vazamento (falso positivo; beat trocado por rumor).
- **Correção sugerida:** ler `revealed_facts[*].fact` e usar o mesmo mapa ID↔segredo do BUG-05-02.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** `playtest` invariantes (não cobrem a chave).

### BUG-05-12 — `commit_memory_facts` duplica o fato e perde o original quando o ledger já tem 2 linhas com o mesmo texto
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `services/memory_provenance.py:497-515`
- **Evidência:** `normalize_memory_facts` deduplica por `memory_id` (inclui `source_turn`), `commit_memory_facts` por texto: `order` repete a chave e `by_text` mantém só a última linha.
- **Reprodução:** ledger com `inference` "A ponte caiu." turno 3 e turno 9 → `commit_memory_facts(ledger, [])` devolve `[turno 9, turno 9]`.
- **Impacto:** só alcançável com ledger legado/importado; duplica itens no contexto.
- **Correção sugerida:** `order` deve ser deduplicado (`dict.fromkeys`).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `test_commit_idempotente_promove_mesmo_texto_uma_vez` (não cobre ledger prévio duplicado).

### BUG-05-13 — Falhas de consulta RAG engolidas sem log (contexto vazio silencioso)
- **Severidade:** baixa
- **Categoria:** exceção-engolida
- **Local:** `rag.py:822-823`, `:850-851`, `:878-879`, `:1295-1296`; `services/context_sources.py:122-126` (`status="degraded"` nunca logado nem consultado por `build_context_pack`)
- **Evidência:** `except Exception: return ""` em `query_global_by_vector/query_session_by_vector/query_npc_by_vector/query_npc_memory`; índice corrompido, mismatch de dimensão (modelo trocado dentro do mesmo provider — `embeddings_meta.model` nunca é comparado em `_embeddings_for_index`) ou `index.pkl` desalinhado (`_save_index` não é atômico: `save_local` + meta separado) produzem lore/memória vazia sem warning. O texto legado `_query_rag_impl` ainda usa `print` em vez de logger.
- **Reprodução:** por leitura.
- **Impacto:** diagnóstico impossível ("o narrador esqueceu tudo") e agrava BUG-05-01.
- **Correção sugerida:** `_LOG.warning(..., exc_info)` em todos e métrica por `source` degradada; escrita atômica do índice (dir temporário + rename).
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum.

### BUG-05-14 — `validate_narrative` colapsa quebras de parágrafo quando rejeita uma frase
- **Severidade:** baixa
- **Categoria:** round-trip
- **Local:** `services/narrative_evidence.py:99-110`
- **Evidência:** divide por `(?<=[.!?])\s+|\n+` e, havendo rejeição, junta tudo com `' '`: parágrafos/diálogos em linhas separadas viram um bloco único (o texto sem rejeição é preservado).
- **Reprodução:** por leitura.
- **Impacto:** cosmético na narração/crônica após qualquer rejeição.
- **Correção sugerida:** preservar o separador original ao reconstruir.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum.

### BUG-05-15 — `npc_data['memory']` cresce sem limite no save (só as 3 últimas são usadas)
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `agents/npc.py:557` (uso em `:478` `[-3:]`)
- **Evidência:** `npc_data['memory'].append(fato)` a cada interação (~400-500 chars) sem teto; o ledger global já é capado em 500 mas esta lista não.
- **Impacto:** inchaço do save/JSON de NPC em campanhas longas.
- **Correção sugerida:** manter `[-20:]`.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum.

### BUG-05-16 — Alias `JINA_AUTH_TOKEN` inconsistente entre `_build_jina` e `_provider_available`
- **Severidade:** baixa
- **Categoria:** regra-divergente
- **Local:** `rag.py:361` vs `:419-420`
- **Evidência:** o builder aceita `JINA_AUTH_TOKEN`, a resolução da cadeia/pin não. Com só o token: Jina nunca é escolhido e um índice pinado em Jina fica "DESATIVADO" (ver BUG-05-03).
- **Correção sugerida:** helper único `_jina_key()`.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum.

---

## Descartados / falsos positivos / já cobertos
- **NPC onisciente via ledger global** (`npc.py:614-619` espelha fala do jogador ao NPC A no ledger usado no contexto do NPC B): coberto por **SPEC-215**.
- **`known_secrets` nunca escrito / codex mostra nomes ocultos:** coberto por **SPEC-206** (BUG-05-02/-11 são distintos: ID de segredo × ID de entidade).
- **Arquivista síncrono/assíncrono e cadeia L1/L2/L3:** SPEC-213/214.
- **SPEC-114 (npc_claim espelhado sem 2º write):** conferido em `npc.py:612-629`; sem regressão (commit só após `rag_ok`).
- **Isolamento por sessão FAISS / pgvector:** `_safe_storage_component` + `_contained_storage_path` corretos (hash para IDs inseguros, containment verificado); `PgVectorMemoryStore._filters` filtra `owner_id`+`game_id` (+`npc_id`) em todos os escopos privados; `ChronicleRepository.semantic_candidates` idem. Sem bug.
- **Visibilidade:** `vis_rank(None)=public`, desconhecido=`secret` (fail-closed); `query_faiss_evidence` usa `or "public"` (vazio→public) enquanto `_query_rag_impl` usa `vis_rank("")`=secret — divergência só com frontmatter vazio, que o lint barra. `codex_body` bloqueia `hidden/secret`. Todos os callsites de `query_rag` usam default `public`.
- **`compact_summary`:** preserva o FIM (recente), idempotente, ≤1200 chars; nenhum agente usa `narrative_summary` cru (só `context_builder` e API/HUD).
- **Dedupe por replay (`memory_retry`, `commit_memory_facts` por texto):** idempotente no caminho normal; retry parcial pode duplicar vetor (write físico OK + meta falha) mas `_format_memory_documents` deduplica na leitura.
- **Chunks `hidden` cortados no meio no budget:** `_assemble` nunca divide fato; lore é um único bloco `public`.
- **Librarian (`agents/librarian.py`):** o pré-filtro por substring ("Grum" ⊂ "npc_grumaldo") só gera candidatos; a decisão é do LLM com `existing_id in existing_ids` validado e `except Exception` cobrindo `AIMessage` do `FallbackLLM`. Não é bug de código (qualidade de prompt).
- **Crônica — capítulo duplicado ao mudar `arc_title`:** `open_chapter` é no-op para o mesmo título; `append_entry`/`open_chapter` são puros. `enqueue_due` repetido é idempotente (`on conflict do nothing`), só custo de DB por capítulo fechado por turno.
- **Compressão apaga raw:** não — `digest` é derivado e marcos protegidos são copiados (`_protected_milestones`).
