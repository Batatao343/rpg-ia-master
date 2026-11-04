# SPEC-378 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer, W7) · **Data:** 2026-11-04 · **Commit revisado:** `eca6bae8` (branch `spec-378`, merge-base `e88d0e11`, 47 commits)

## Escopo

Revisei o código pronto da branch `spec-378` (`git diff main...HEAD`, 46 arquivos): E1 (`services/text.fold`, 15 sítios), E2 (`services/env.env_choice`, 15 módulos e o alias `latency_flags._choice`), E4 (`llm_setup._attempt` e `RoutedLLM._prepare_candidate`), E5 (`rag._add_memory`, `_stage_memory` e `_query_by_vector`), E6 (`is_database_profile` em `kill_switches`, `dossiers`, `rag` e `persistence`) e a E3, cancelada pela R21. Ficaram fora a suíte completa, que é do coordenador, o playtest de 10 turnos do W2 (refiz só o `evals compare`) e o smoke real §6.

Verificações W7 pedidas:

1. **W2 refeito (A = `e88d0e11` × B = `eca6bae8`)**: rodei `evals run` nas 12 suítes do `eval-gates.yml` com `--seed 7` (272 casos). `evals compare` deu `passed: true` e `regressions: []`. Comparei campo a campo: `metric_values`, `aggregates`, `case_diagnostics`, `eligible/error/skipped_case_ids` e `hard_failures` são idênticos. Nos `results`, as únicas diferenças são `duration_ms`, `started_at` e `product_sha`.
2. **E1, equivalência estrutural (D1=a / R11a)**: conferi o diff contra a cópia `_legacy_*` do oráculo em 5 classes: A `party._fold`, B `inventory._fold`, C `law._fold`, D `faction_membership._fold` e E `shared_pool_models.fold_name` (id do pool). Em todas, a sequência é `str(x or "")` → NFKD → tira `combining` → caixa → (strip | collapse). Nenhum sítio mudou de classe. As cópias com caixa antes do NFKD, NFD, `str(s)` ou ascii-ignore não estão no diff. Fiz também uma checagem exaustiva fora do corpus: os 15 sítios migrados × todos os code points (U+0000–U+10FFFF, sem surrogates), mais 140 mil variantes com espaço nas pontas e prefixadas: 0 divergências entre o legado, o sítio e `fold(**opts)`. As cópias legadas no teste batem verbatim com o source de `e88d0e11`.
3. **E2**: os 16 leitores do golden `flag_readers.json` (15 módulos) foram gravados no `2da51010`, antes de qualquer migração. Nenhum commit posterior mexe no golden. Cada leitor mantém default, `choices` e fallback: `""`, valor inválido e ausente caem no mesmo default. Os `or ""`/`or "on"` antigos são redundantes com `getenv`, e os `getenv(name, "")` antigos são equivalentes porque todo default é minúsculo e está em `choices`. As dependências encadeadas (R14) continuam no chamador. `latency_flags` não está no golden (P2-2). O total é 16 módulos migrados, não 17: 15 no golden mais o `latency_flags`.
4. **E6**: `is_database_profile()` reproduz literalmente `getenv("RPG_RUNTIME_PROFILE","legacy").strip().lower() != "legacy"`, com `""` → `True`. O teste novo cobre `None`/`""`/`" LEGACY "`. A negação em `kill_switches` (`not is_database_profile()`) preserva o `== "legacy"`. Os divergentes `or "legacy"` (`llm_setup`, `shared_pool:134`, `checkpoints:188`) não foram tocados (D4=a). `api._database_profile` está intocado: `api.py` não aparece no diff (D5=a). A contagem textual de `test_spec192` já tinha saído na base (R30a ok), e o teste está verde.
5. **W3**: nenhum teste existente mudou. `git diff main...HEAD -- tests/` só acrescenta arquivos `test_spec378_*` e fixtures, e regrava `size_budget.json`. `grep '^-.*assert'` sai vazio. Nenhum alvo de monkeypatch precisou mudar.
6. **Lint e tamanho**: `ruff check .` limpo; `ruff_baseline.py --check` diz "current"; `size_budget.py` rc 0. O `persistence.py` cresceu 1 linha (1372 → 1373, o import). **Aceito**: troca 8 expressões por um helper sem custo de cold start (`services.env` é stdlib-only) e está justificado no commit `81c5e703`. `llm_setup` −37 e `rag` −174.

Também conferi:

- **E4**: li os 19 sítios no diff. Cada `_attempt(...)` recebe exatamente os kwargs do `LLMAttemptEvent(...)` antigo, e `grep -c "LLMAttemptEvent("` dá 1. No `_prepare_candidate`, `split_apply` reproduz os rótulos `build:X`/`apply:X` e o `error="apply:X"` do `invoke`, e o `build:X`/`error=X` único do `stream`. Também reproduz o `attempt_index` (avança em circuito/build/apply; o `stream` descarta e usa `idx`) e o kill switch sem evento. Os globais (`_kill_switch_disabled`, `_OPEN_CIRCUITS`, `_cached_for_tier`, `_emit_attempt_telemetry` → hook) são lidos na hora da chamada (R25).
- **E5**: comparei as funções antigas inteiras com as novas. Digest do `document_id`, prefixo, `npc_id` no intent/query só no NPC, `makedirs`, `source` e `_note_degraded` por escopo, e os 4 eventos literais (R6): tudo preservado. Não existe tabela `_SCOPE`: todos os globais são lidos na chamada (R28a).
- **E3 cancelada**: amostrei `npc`, `campaign_manager`, `death_flow` e `narrative_sink`. Todos têm `try` mais largo, `raise` próprio ou devolvem o resultado bruto ao chamador. O "2 aptos < 5" da R21 é plausível. O helper não foi criado, e o `dup_helpers` não acusa `invoke_structured`.
- **Guard de FallbackLLM**: nenhum nó com structured output foi tocado (a E3 foi cancelada). `test_structured_output_guards.py` está verde.
- **Segredo em log**: nenhum log novo, e os eventos estão byte-iguais (`test_log_event_registry` verde). Nenhum writer persistente novo: o `_stage_memory`/FAISS está coberto pelo golden de round-trip dos argumentos, com `document_id`. Nada em `evals/` foi tocado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `tests/test_spec378_llm_attempt_golden.py:87-100` | O golden da E4 cobre 12 desfechos, não a lista do R23. Faltam `invalid_structured` com retry semântico, 429, 400 `tool_use_failed` com regeneração, timeout, `stream_structured`, hedge (`hedge_lost`) e eventos de log. O fixture troca `_apply` por identidade, então o erro em `_apply` (o único ramo com lógica nova, `split_apply`) também não está no golden. Mitigado: li o diff sítio a sítio (kwargs idênticos) e rodei um A×B próprio com erro de `_apply` + circuito em `invoke`/`stream` e 4 candidatos, com eventos, hook legado e retorno byte-idênticos. `test_llm_hedge`, `test_stream_structured` e `test_api_attempt_telemetry` estão verdes | Acrescentar ao golden os cenários de `_apply` que levanta, `with_structured_output` (inválido → válido), 400 `tool_use_failed` e hedge com `threading.Event`, gravados contra `e88d0e11`. Pode ser follow-up: o código já está provado equivalente pela leitura |
| P2-2 | P2 | `services/latency_flags.py:18`; `tests/test_spec378_env_choice.py:21` | O R13 pede que o golden cubra os leitores de `latency_flags._choice` (agora alias de `env_choice`), e os 4 leitores (`RPG_NPC_TWO_PHASE`, `RPG_REPLAN_AFTER`, `RPG_DAY_DIGEST`, `RPG_ARCHIVE_POLICY`) não estão em `READERS`. A semântica mudou de `getenv(name, "")` para `getenv(name, default)`. É equivalente porque todo default é minúsculo e está em `allowed`, mas o golden não prova isso | Acrescentar os 4 leitores ao golden. Gravar com o `_choice` antigo (copiar verbatim no teste) |
| P2-3 | P2 | `rag.py:1390-1453` | `_add_memory` tem 64 linhas, acima do teto de 60 para função nova | Extrair o ramo FAISS (load/create + `_save_index`) para um `_faiss_add_memory(scope, path, texts, metadatas)` |
| P2-4 | P2 | `tests/test_spec378_text_fold.py:68` | O corpus lê só `data/**/*.json`, corta em 400 arquivos e não lê `*.yaml` (§3.1 item 1). Mitigado pela regra estrutural (R11a) e pela minha checagem exaustiva por code point (0 divergências) | Tirar o `[:400]` e incluir `rglob("*.yaml")` (com `yaml.safe_load`) |
| P2-5 | P2 | `tests/test_spec378_rag_memory_golden.py:68` | O R28a pede que o golden afirme que nada foi criado fora de `tmp_path`, e o teste não afirma. Mitigado: o código não captura `SAVES_DIR` (lê o global na chamada) | Snapshot de `data/saves_memory` antes e depois do teste, ou `os.makedirs` monkeypatchado para recusar caminhos fora de `tmp_path` |
| P2-6 | P2 | `inventory.py:36`, `services/reputation.py`, `services/faction_membership.py:124` | Pela letra da R11a, a sequência não é idêntica. O legado faz `strip` → caixa, e `fold` faz caixa → `strip`. É equivalente: provei exaustivamente que nenhum code point sai ou entra em `isspace()` sob `lower`/`casefold` (0 contraexemplos). Nenhum comportamento muda | Registrar no §9 que a ordem `strip`/caixa comuta (prova exaustiva). Nada a mudar no código |

Nenhum P0 ou P1.

## Correções aplicadas

Nenhuma (revisão só leitura; o revisor só edita este arquivo).

## Pendências

- **Smoke real §6** (E4 toca `RoutedLLM.invoke/stream`): pendente, com teto de 4 turnos e US$ 0,10. Fica com o coordenador antes de `done`.
- Suíte completa 1× no `/spec-land` (coordenador).
- P2-1 e P2-2 (golden ampliado): follow-up pequeno da própria 378, de preferência antes do pouso, porque custa pouco.
- P2-3 a P2-6: follow-up ou nota no §9; nenhum bloqueia.
- Os follow-ups já listados no §9 da spec continuam valendo (unificar os folds divergentes, perfil `""`, as duas semânticas de `attempt_index`, build/apply no `stream`).

## Comandos rodados

```text
git diff main...HEAD --stat → 46 arquivos, +4161/−703 (merge-base e88d0e11)
evals run 12 suítes --seed 7 em A (worktree destacado de e88d0e11) e em B (HEAD) → ambos passed:true, 272 casos
evals compare --current B --baseline A → passed:true, regressions:[]; resultados iguais exceto duration_ms/started_at/product_sha
script exaustivo: 15 sítios E1 × ~1,25 M entradas por code point → 0 divergências; comutação strip/caixa → 0 contraexemplos
script A×B: RoutedLLM invoke/stream com erro em _apply + circuito aberto → eventos/hook/retorno byte-idênticos
git diff main...HEAD -- tests/ | grep '^-.*assert' → vazio
pt.sh test_spec378_* + log_event_registry + spec192 + npc_memory + size_budget + structured_output_guards → 61 passed
pt.sh 25 arquivos (attempt_telemetry, llm_hedge, llm_logging, provider_logging, spec196, stream*, persistence*, dossiers, enemy_*, jev_rollout, law, npc_knowledge, scene_cards, shared_pool, calendar, rumor, death_flow, memory_provenance, rag_index_cache, storage_security, latency_timeline) → 370 passed, 15 skipped
ruff check . → All checks passed; ruff_baseline.py --check → current; size_budget.py → rc 0
dup_helpers.py --diff main...HEAD → só `fold` (o helper canônico; fauna_lint/leak_phrases/plot_threads_lint são wrappers ou ficam)
pt.sh tests/test_handoff_names.py -n 0 → 3 passed
worktree A removido (git worktree remove); nenhum processo em background
```
