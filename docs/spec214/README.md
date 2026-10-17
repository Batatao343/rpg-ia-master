# SPEC-214 — Memória hierárquica (L1/L2/L3): evidência de execução

**Data:** 2026-10-17 · **Status da spec:** `in-progress` · **Decisão de rollout (R13):** `off` (não promovido).

Entrada: Gate R1 `GO` com provider real ([gate-real-2026-10-17.md](gate-real-2026-10-17.md):
context p50/p95 = 414/762 ms, 3,94 % do TTLT). O gate offline anterior foi `NO_GO` ([gate.md](gate.md)).
Teto teórico de ganho: ~4 % do TTLT.

## O que mudou

* `services/scene_snapshot.py` — `SceneSnapshot` L1 puro (sem I/O/LLM/embedding): local, presentes,
  interlocutor + relação, ameaças, combate, eventos recentes da cena (ids), ids revelados (nunca texto),
  objetivo **público** (`services/objectives.public_objective`, sem beats), relógio, clima/luz.
  `snapshot_key` = sha256 de `KEY_FIELDS` (game_id, epoch, local, interlocutor, combate ativo/rodada,
  quests ativas, checkpoint, mortes, `death_pending`, versão de memória, hash do revelado). Sem `turn_count`.
* `services/context_cache.py` — LRU por processo e por jogo (`RPG_SCENE_CACHE_MAX_GAMES`, default 64),
  lock; slot `(purpose, npc_id)`. Entrada descartada (nunca atualizada) a cada mudança de chave, com causa:
  `location|interlocutor|quest|combat|checkpoint_restore|death|secret_revealed|memory`; e ainda
  `turn_replay`/`rollback` (`note_turn_start`, chamado em `api._run_turn_collected`), `new_topic` (R7,
  termos da query fora da cena sem interseção com o conteúdo/consulta cacheados), `secret_filter`
  (R9: `find_strict_unrevealed` na escrita **e** na leitura) e `schema`. Memória nova só invalida slots que
  guardaram sessão/NPC (slot só de lore sobrevive, R3). Aquisição degradada (embedding falhou) não é cacheada.
* `services/context_builder.py` — `build_context_pack` (assinatura e callsites intactos) despacha por
  `RPG_SCENE_CACHE=off|shadow|l1_only|on` (default `off`; valor inválido ⇒ `off` + fallback `bad_flag`).
  `off` = caminho anterior byte a byte (golden do HEAD `8823bb0`). `on`: L1 renderizado na seção `scene`
  + fatos dinâmicos/resumo/ledger sempre recomputados + fontes RAG do cache (hit L2, sem embedding) ou
  aquisição atual (L3). `ContextBudget.layer_quota` (P2 default, escalado: L1 600 / L2 1900 / L3 1000 de 3500).
  Exceção/sem `game_id` ⇒ builder atual + `rpg_context_cache_fallback_total{reason}` (R10).
  `shadow` entrega o pack atual e loga `rpg.context_cache` `context_shadow` (contagens de evidence ids e
  tokens, sem texto/id).
* Telemetria aditiva em `rpg.turn` (R12): `context_cache`, `context_cache_calls`, `context_cache_mode`,
  `context_layers_tokens {l1,l2,l3}`, `context_invalidation_reason`, `context_embed_calls`. Métricas
  `rpg_context_cache_total{status}` e `rpg_context_cache_fallback_total{reason}`.
* Harness SPEC-200: `--embed-ms` injeta latência fixa por embedding de contexto (embedding simulado com
  sucesso, leitura offline vazia); `scene_cache` (informativo) e `embed_ms` (comparável) no fingerprint;
  `scene_cache` nos records; resumo por jornada ganha `context_embed_calls_mean` e `context_cache_calls`;
  `compare` mostra a fase `context`.
* Nenhum campo novo no save; `SCHEMA_VERSION` segue 8. Nenhum `with_structured_output` novo.

## A/B offline pareado (três braços)

`scripts/latency_baseline.py run --journeys all --reps 30 --seed 214 --mode virtual --embed-ms 400`,
mesmas jornadas/seed, `RPG_SCENE_CACHE` = `off` / `l1_only` / `on`. `--embed-ms 400` ≈ context p50 real
(414 ms). 330 turnos medidos por run (`latency_runs` fora do repo; sha256 de `summary.json` abaixo).

| perfil | braço | context p50/p95 | turn_total p50/p95 | embeddings/turno | cache (chamadas) | summary sha256 |
|---|---|---|---|---|---|---|
| typical | off | 400 / 800 | 6622 / 8023 | 0,930 | off 307 | `074d2cdad26429bf…` |
| typical | l1_only | 400 / 800 | 6622 / 8023 | 0,930 | hit_l1 37, miss 270 | `29b01cfc41ade8fb…` |
| typical | on | 400 / 800 | 6542 / 8023 | 0,888 | hit_l2 14, miss 293 | `765460515f33c480…` |
| slow-tail | off | 400 / 800 | 6849 / 17727 | 0,930 | off 307 | `9bf906d714488747…` |
| slow-tail | l1_only | 400 / 800 | 6849 / 17727 | 0,930 | hit_l1 37, miss 270 | `c265fc85eb913cd5…` |
| slow-tail | on | 400 / 800 | 6804 / 17727 | 0,888 | hit_l2 14, miss 293 | `82a38304cd9f47f1…` |

* Só J2 (combate) teve hits (14/97 chamadas): o slot `combat_narration` guarda só lore e sobrevive a
  memória nova. J1/J3/J5/J6: 0 hits — a cada turno o arquivista grava memória (invalida sessão/NPC) ou
  muda local/quest/checkpoint. Causas no braço `on` typical (por turno): memory 129, new_topic 30,
  location 30, checkpoint_restore 30, combat 23, quest 21, nenhuma 67.
* Ganho `on` vs `off` (typical): context p50 **0 %**, turn_total p50 **−1,2 %**, embeddings/turno **−4,5 %**.
  Tokens médios por turno no `on`: L1 46, L2 951, L3 0 (offline o RAG volta vazio).
* Paridade `off`: `spec214-pre-head-typical` (código do HEAD, sem flag) e `spec214-post-typical-off-e0`
  (este código, `off`, `--embed-ms 0`) têm o mesmo overall (total p50/p95 6204/7846).

## Regra de promoção (R13, P3 default) — não atendida

| condição | exigido | medido | ok? |
|---|---|---|---|
| (i) p50(context) | −30 % | 0 % | não |
| (i) p50(turn_total) | −5 % | −1,2 % | não |
| (i) alternativa: custo de embedding/turno | −30 % | −4,5 % | não |
| (ii) régua SPEC-170 com `on` | sem regressão | igual a `off` (ver abaixo) | sim* |
| (iii) dataset de invalidação | 100 % | não autorado (handoff) | pendente |
| (iv) smoke playtest offline | 0 `error` | 0 | sim |

**Decisão: `RPG_SCENE_CACHE` permanece `off`** (shadow disponível para medir em staging). Leitura honesta: com
a chave conservadora exigida por R3/R5, a memória escrita quase todo turno invalida o L2 de story/NPC; o
hit fica restrito a slots só de lore. Afrouxar a chave (ex.: não invalidar por memória) trocaria correção
por latência — fora do escopo e contra R3.

\* A régua SPEC-170 (`memory_context.jsonl`) passa idêntica com `off` e `on` (Recall@1/3/5 0,583/1/1, MRR
0,833, context R@5 1,0, leak 0, budget 0; run `spec214-on`, json sha256 `4e48f02bcb4cbaba…`), mas o adapter
`context_grounding` chama `assemble_pack` direto e **não exercita a flag**: é só não-regressão do montador.

## Smoke / invariantes

* `uv run --frozen python -m playtest run --all --turns 3`: 14 perfis × 3 turnos com `off` e com `on` —
  0 erros, 0 violações (err/warn) nos dois.
* 200 turnos offline, perfil `normal`, seed 214, `RPG_SCENE_CACHE=on` (script de oráculo em scratchpad:
  embrulha `get_l2/put_l2` e, a cada hit, recomputa a chave do estado **atual** e confere
  local/combate/morte contra a entrada servida): 200/200 turnos, 0 erros, 0 violações, **0 hits obsoletos**;
  194 chamadas, 2 hits L2, 192 misses (memory 87, combat 50, location 33, new_topic 11, quest 6,
  checkpoint_restore 2). O número de chamadas varia entre execuções do playtest mock (74–194 observados);
  o resultado (≈1 % de hit, 0 obsoleto) se repetiu.

## Testes

* Novos: `tests/test_scene_snapshot.py` (22), `tests/test_context_cache.py` (19),
  `tests/test_context_layers_ab.py` (18), golden `tests/fixtures/spec214_context_pack_off.json` + `tests/spec214_cases.py`.
* Suíte completa (`pytest -q -p no:warnings --ignore=tests/test_project_index.py`): **3685 passed, 227 skipped**, exit 0.
* Ruff verde nos arquivos tocados.

## Limites / o que falta

* Dataset de invalidação (EVAL_AUTHORING_REQUIRED) → [handoff](../../handoffs/SPEC-214-eval-authoring.md).
* Revisão independente Astra (`REVIEW_REQUIRED`) não feita.
* Smoke real (P4 default: não executar). A injeção `--embed-ms` modela só a latência do embedding/buscas;
  não mede qualidade do lore reaproveitado num hit.
* Cache por processo: em serverless/multi-instância os hits seriam ainda mais raros (correção preservada).

## Checklist de manutenção da chave (risco de snapshot obsoleto)

Ao adicionar campo canônico que mude o que pode entrar no contexto: avaliar contra
`scene_snapshot._key_parts`/`KEY_FIELDS`, mapear a causa em `context_cache._REASON_BY_FIELD` e acrescentar a
mutação em `test_key_changes_on_each_invalidation_field`.
