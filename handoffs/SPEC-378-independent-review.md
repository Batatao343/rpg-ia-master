# SPEC-378 — revisão independente (spec `draft`, antes de `approved`)

> **Veredito:** `SAFE-WITH-CHANGES` (no vocabulário do template: `CHANGES_REQUIRED` na spec antes de virar `approved`; nenhum achado exige descartar a spec)
> **Revisor:** Opus (spec-reviewer, papel Sol) · **Data:** 2026-11-03 · **Commit revisado:** `main` em `b278f6af` (a spec cita `5fd2e920`; 48+ commits depois, inclusive SPEC-367)

## Escopo

Revisão crítica de `specs/SPEC-378-refactor-helpers-comuns.md` (refatoração pura E1–E6), contra o source da `main`, a auditoria §6/§6.5 e as specs vizinhas 376/377/379/381/382/384. Só leitura: nenhuma edição de spec, código ou teste. Sondas: `git grep`/`git diff`, W1 real, leitura dos sites. A sonda de propriedade de fold e os testes focados **não terminaram**: a RAM livre caiu para 1,1 GB (regra do dono: abaixo de 3 GB não se dispara nada) e matei o meu próprio pytest pela árvore de PID.

## Tabela por etapa

| Etapa | Pura como escrita? | Evidência | O que falta |
|---|---|---|---|
| E4 `_attempt`/`_prepare_candidate` | Sim, se o golden cobrir os ramos reais | `llm_setup.py:1014-1090` (invoke) × `:1201-1250` (stream) × `:1426+` (`_stream_attempt`); 19 `LLMAttemptEvent(` confirmados | `invoke` separa build e `_apply` (`errors` "build:X"/"apply:X", `error="apply:X"`); `stream` usa **um** `try` para os dois (`"build:X"`, `error=X`, a latência inclui o build). `circuit_open` incrementa `attempt_index` no invoke e não no stream; `kill_switch` não emite `LLMAttemptEvent` nem avança o índice; `structured` é calculado por candidato no stream. `_stream_attempt` roda em threads do hedge (`:1663-1730`, `hedge_lost`): o golden R23 não lista hedge e não diz como torná-lo determinístico |
| E5 `_add_memory`/`_query_by_vector` | Sim, se a tabela `_SCOPE` ler globais na hora | `diff` das duas funções (`rag.py:1352-1498` × `:1511-1658`): as diferenças são as do R27 (lista completa) | O R25 só fala de `llm_setup`. Em `rag` a suíte faz `setattr(rag, "SAVES_DIR")` 15×, `get_embeddings` 5×, `_has_faiss_index` 5×, `_embeddings_for_index` 4×, `FAISS`, `_save_index`. Um `_SCOPE` com `SAVES_DIR` capturado no import faz o teste **gravar no `data/saves_memory` real** e mesmo assim passar |
| E2 `env_choice` | Sim para as formas listadas | 23 sites `raw if raw in … else` em `services/` | Já existe o mesmo helper: `services/latency_flags.py:16-18 _choice`. `companion_soul.py:74` usa `os.environ.get` (não `os.getenv`): migrar troca qual monkeypatch o afeta (`tests/test_eval_dossier_leak.py:142` troca o `os.getenv` global) |
| E1 `fold` | **Não** com o corpus proposto | ver P1-1 e P1-2 | A prova por corpus não cobre a ordem `casefold`→NFKD (contraexemplo U+0345/`ᾼ`); `loot` é NFD; `faction_gate._fold_word` levanta com `None` |
| E3 `invoke_structured` | **Não** como codificado em §3.3 | `llm_setup.py` não tem `_log_event` (só `from observability.telemetry import log_event` local em `:243` e `:1807`) | O `except` do helper levantaria `NameError` e derrubaria o guard. O escopo do `try` encolhe (P1-3). Catálogo: o scanner só lê área/evento **posicionais** (`scripts/gen_event_catalog.py:34-36`, `("both", 0, 1)`); `node=`/`event=` por kwarg exige mudar a lógica do `scan()`, não só o dict `WRAPPERS` |
| E6 `is_database_profile` | **Não**: quebra asserção existente | `tests/test_spec192_vercel_packaging.py:81-82` exige `count('RPG_RUNTIME_PROFILE", "legacy"') >= 3` em `persistence.py` e `>= 2` em `rag.py` | Migrar os 9 sites de `rag` e os 8 de `persistence` zera as contagens, e a W3 proíbe mudar o `assert`. A SPEC-379 já planeja remover essa contagem (linha `test_spec192…` da tabela da 379, destino "378"): a 378 precisa depender disso |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | spec §3.3; `llm_setup.py` (sem `_log_event`) | O código do helper chama `_log_event`, que não existe em `llm_setup`. Na 1ª exceção com `node`, o `except` levanta `NameError`: o guard de FallbackLLM vira crash, o contrário do R17 | Escrever o helper com `from observability.telemetry import log_event` **lazy dentro do except** (como em `:243`) e `try/except` em volta do próprio log; teste do R17 com `node` passado e exceção em `invoke` |
| P0-2 | P0 | `tests/test_spec192_vercel_packaging.py:81-82`; spec E6/§3.7 | A E6 em `rag.py`/`persistence.py` reprova uma asserção de contagem textual; pela W3, a etapa não é pura | Pôr a dependência "SPEC-379 com a remoção da contagem de `test_spec192` pousada" nos sub-itens `rag`/`persistence` da E6 (ou manter ≥ 2/≥ 3 literais, o que é pior). Citar o teste no §7 |
| P1-1 | P1 | spec §3.1 (corpus; classes B, C, F) | Equivalência "no corpus" não é equivalência. Os sites que dobram a caixa **antes** do NFKD (`agents/router.py:315`, `bestiary_lint.py:174`, `conflict_summary.py:426`, `encounter_manifest.py:166`, `faction_gate.py:171`, `lore_quests.py:77`) divergem de `fold` em U+0345 (`"ͅ".casefold()=="ι"`, que o NFKD trata como combinante) e em `"ᾼ"` (`"αι"` × `"α"`). O corpus adversarial não tem esses pontos | (a) Acrescentar U+0345, `ᾼ`, `ﾞ` (U+FF9E) e `ŉ` ao corpus. (b) Regra: site com a **mesma sequência de operações** do `fold` migra por construção (o teste é só cinto de segurança); site com outra ordem só migra com um parâmetro `order=` explícito, ou fica. Para `fold_name` (id no pool), exigir identidade estrutural; hoje ela é idêntica (`shared_pool_models.py:135-139`) |
| P1-2 | P1 | spec §3.1 (tabela) | A classe A inclui `agents/loot.py`, que é **NFD** (`:283`) e nunca bate com um `fold` fixo em NFKD (`ﬁ`, `™`, `①`, nbsp). `faction_gate._fold_word` faz `w.casefold()` sem `str()` e levanta com `None`; `mock_llm.py:847` usa `str(s)`. A spec não diz como o teste trata exceção da função antiga | Reclassificar o loot como "fica" (ou H). No teste de propriedade, exceção em `_legacy(x)` conta como divergência (não como erro de coleta) |
| P1-3 | P1 | spec R18 | Os sites embrulham no mesmo `try` coisas fora do `invoke`: `get_llm` (`shared_pool.py:469-473`), `materialize`/`save` (`bestiary.py:677-690`), `_normalize` (`prologue.py:518-522`), `model_copy` (`loot.py:330-337`), `model_dump` (`character_creator.py:363-368`). O helper só cobre `with_structured_output`+`invoke`; migrar sem manter o `try` externo deixa exceções escaparem | Acrescentar ao R18: "o `try` externo do site fica com o mesmo escopo e o mesmo `except`". `services/creature_gen.py:1404` deixa a exceção subir para o `future` (log `creature_gen_*`): não é apto, porque o helper a engoliria |
| P1-4 | P1 | spec R25 (só `llm_setup`) | Falta a regra equivalente para o `rag` (lista na tabela acima) | Estender o R25 à E5: `_SCOPE` guarda funções que leem `SAVES_DIR`/`FAISS`/`_save_index` no momento da chamada; o golden roda com `SAVES_DIR` em `tmp_path` e afirma que nada foi criado fora dele |
| P1-5 | P1 | spec R23/R24 | O golden não lista: erro de `_apply` no stream (texto diferente do invoke), `circuit_open` no stream (o índice não avança) e o hedge (`hedge_lost`, `_log_hedge`, threads) | Acrescentar os 3 desfechos. Para o hedge, fake com `threading.Event` controlando quem vence, comparando o multiconjunto de eventos ordenado por `(attempt_index, outcome)`. `_prepare_candidate` recebe `split_apply: bool` (invoke `True`, stream `False`) e `advance_on_circuit: bool` |
| P1-6 | P1 | spec §3.7 + §4 (W1) | W1 rodada agora: **E5 travada** (`rag.py` ← spec-374; a spec diz "—"). E2: `creature_gen.py` (374), `fauna.py` (370), `enemy_decks`/`enemy_intent` (371). E1: `mock_llm.py` (374), `world_utils.py`/`fauna.py` (370), `bestiary_lint.py` (10 branches `bst-*`, `spec-359`, `spec-349-pre-sync`). E3: `character_creator.py`, `encounter_preparation.py`, `combat.py` (371), `creature_gen.py` (374). E6: `dossiers.py`, `combat.py` (371), `rag.py` (374). **E4 livre.** E a W1 é **cega** a 367/368: as duas commitam direto na `main` (sem branch), então `loot.py`/`persistence.py`/`card_*` não aparecem | Na spec: (1) atualizar §3.7; (2) a trava de 367/368 é por **status da spec** (`done`), não pela W1; (3) branches paradas (`spec-349-pre-sync`, `spec-214`, de 2 semanas) travam para sempre: o coordenador decide se contam |
| P2-1 | P2 | spec R16/§3.2 | `services/latency_flags.py:16 _choice` já é o `env_choice` (com `getenv(name, "")`, mesmo resultado) | Citar e fazer `latency_flags._choice = env_choice` (alias), ou justificar não reusar |
| P2-2 | P2 | spec E2 | `companion_soul.mode` lê `os.environ.get`; o `env_choice` lê `os.getenv` | Deixar `companion_soul` fora, ou golden com `monkeypatch.setattr(os, "getenv", …)` provando o mesmo valor |
| P2-3 | P2 | spec R30/§3.2 | `services/checkpoints.py:188` (`getenv(...,"legacy") == "legacy"`, sem `strip`/`lower`) não está em nenhuma lista; os "23 equivalentes" são 22 fora do `api.py:309` | Listar `checkpoints` como divergente; corrigir a conta |
| P2-4 | P2 | spec §3.3 / testes | `tests/test_structured_output_guards.py` só vê sites com `.with_structured_output`; site migrado sai da rede estática | Teste novo (acréscimo): todo chamador de `invoke_structured` testa `is None`/`isinstance` na mesma função |
| P2-5 | P2 | spec §6 | "Cinco requests no máximo" não cabe: 1 turno de história já chama router, storyteller e archivist/campaign (~4 chamadas) | Teto em turnos (4) e em custo, não em requests |
| P2-6 | P2 | 382 §110; 384 :11/:316 | As specs 382 e 384 chamam o helper de `flags.mode()`; a 378 cria `services/env.env_choice` | Alinhar o nome nas três specs |

## Fatos conferidos

**Certos:** 63 `unicodedata.normalize` em 57 arquivos; 19 `with_structured_output(` em produto; 19 `LLMAttemptEvent(` em `llm_setup`; `test_log_event_registry.py` lê só constantes; o R27 (diferenças das duas funções de memória) está completo; `fold_name` é estruturalmente igual a `fold(collapse=True)`; `infrastructure/runtime.py:488` usa `or "legacy"`; 22 arquivos de teste com `setattr(llm_setup, …)`; `services/text.py`/`services/env.py` não existem e `services/__init__.py` tem 80 bytes (sem custo de import nem ciclo).

**Errados ou desatualizados:**
- Commit base: `5fd2e920` → `b278f6af`, e os números de linha mudaram (loot `256`→`283`, faction_gate `168`→`171` etc.).
- Falta `services/prose_guard.py:521 _fold_gold` (classe A, entrou com a 367): são 39 funções e 33 candidatas.
- O loot é NFD, não "NFKD/NFD".
- A §3.3 usa um `_log_event` que não existe.
- Os "49 `setattr`" são ~60 linhas (14 `_get_cached_client`, 10 `get_llm`, 8 `_build_client`, 7 `_ATTEMPT_TELEMETRY_HOOK`…).
- Os "23 equivalentes" de perfil são 22 + `api`.
- A §3.7 diz que a E5 está livre; ela está travada pela 374.

## Oráculo W2 (pergunta 3)

O W2 não cobre a E4 e cobre pouco a E5 e a E6. `evals/core/runner.py:464-465` força `RPG_FORCE_MOCK=1`, e as 12 suítes do `eval-gates.yml` não chamam `RoutedLLM` nem `add_memory_to_session`/`add_npc_memory` (no `git grep` em `evals/`, só aparecem experimentos fora do gate). `playtest/runner.py:577-582` também força o mock e roda em `legacy`. Logo `RoutedLLM.invoke/stream` **nunca executa** no W2, o perfil com banco nunca roda e a E3 só vê instâncias do MockLLM. O oráculo real são os goldens. Com os acréscimos de P1-1, P1-4, P1-5 e o teste de fallback do helper (P0-1), eles pegam a divergência; sem eles, não pegam.

## Guard de FallbackLLM (pergunta 4)

O contrato (não-instância → `None`; exceção → `None`) está certo e bate com o AGENTS.md. **Mas** o código da §3.3 quebra no ramo de exceção com `node` (P0-1), e a migração pode encolher o `try` (P1-3). Com as duas correções, o helper preserva "AIMessage de erro → None" nos sites aptos (chronicle_compression, prologue, tactical_profile, loot, character_creator; shared_pool e bestiary mantendo o `try` externo). Router, archivist, world_simulator, campaign_manager, encounter_preparation, librarian e creature_gen ficam como estão.

## Choques com decisões e specs

- 377: coerente (a 378 depende dela; os folds de lei e facção só migram depois).
- 379: **dependência faltando** (P0-2: remoção da contagem em `test_spec192`).
- 381: coerente com D5 (a); o §508 da 381 pede exatamente isso.
- 384: coerente (a E2 pula as flags a aposentar); o nome do helper diverge (P2-6).
- 382: espera `invoke_structured`/`text.fold`; funciona se a 378 pousar antes, e a 382 já prevê o caso contrário.
- Decisões do dono: nenhuma contradita (o §6.4 da auditoria é respeitado: sem `file_cache`, sem tabela de `persistence`, sem subir imports de `api.py`).

## Correções aplicadas

Nenhuma: revisão de spec, só leitura.

## Pendências

O executor da Etapa 0 roda a sonda de propriedade com o corpus ampliado de P1-1 (eu preparei um script equivalente, mas não o executei por falta de RAM).

## Comandos rodados

```text
git grep -c "unicodedata.normalize" (produto) → 63 em 57 arquivos
git grep "with_structured_output(" (produto) → 19 sites
grep -c "LLMAttemptEvent(" llm_setup.py → 19
W1 (for-each-ref + diff main...b) → 557 arquivos travados; interseções por etapa em P1-6
git diff main...spec-374 -- rag.py → só reindex_global/parse_args (mas trava o arquivo)
diff add_memory_to_session × add_npc_memory → diferenças = R27
pytest -n 0 test_structured_output_guards/test_spec192/test_log_event_registry → interrompido por mim (RAM 1,1 GB), sem resultado
```
