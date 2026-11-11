# SPEC-406 — evidência

## Etapa 0 (11/11) — linha de base e R0

Base: `3082b857` (SPEC-405 já pousada). `ruff check --isolated --select F401,F811,F841 api.py`: **109 diagnósticos, todos F401** (nenhum F811/F841; o `import re` agora é usado e a cópia de `_CODE_RE` saiu com a 405).

Classificação por varredura AST de `tests/ playtest/ evals/ scripts/ services/ routes/ agents/ infrastructure/ observability/` e `*.py` da raiz (`api.<nome>` com alias de `import api [as x]`, `from api import <nome>`, `f(api, "<nome>")` como `getattr`/`monkeypatch.setattr`/`patch.object`, string `"api.<nome>"`), mais `git grep -w` em `*.sh *.yaml *.yml *.toml *.json *.cfg` (acertos só por palavra comum como `json`/`queue`/`gamedata` em arquivo de dados/lock não contam; nenhum aponta para `api`). `F841` nos vizinhos (`api_presenters.py`, `routes/turn.py`; D3, fora de escopo): **2** no total, hoje.

Divergência do §3 da spec (a tabela prevalece): **20 nomes lidos de fora**, não 18: os 18 previstos mais `_inventory_block` (`tests/test_fase43.py:306`) e `_enforce_owner_budget` (9 leituras, `tests/test_abuse_policy.py`, `tests/test_spec197_daily_cap.py`). O `gamedata` (módulo) é um dos 20 e vira `import gamedata` nos 3 testes (D2). Os outros 19 viram `X as X` (D1). Mortos: 89 (a spec previa 89 de 109; com as 2 leituras extras, 89 mortos e 20 leituras = 109). Classe `efeito` decidida por `modules.json` nas Etapas 3-5 (ver abaixo).

| linha | regra | nome local | diagnóstico | classe | evidência |
|---|---|---|---|---|---|
| 9 | F401 | `contextvars` | contextvars | morto | sem acerto em AST/grep |
| 10 | F401 | `hashlib` | hashlib | morto | sem acerto em AST/grep |
| 11 | F401 | `json` | json | morto | sem acerto em AST/grep |
| 12 | F401 | `logging` | logging | morto | sem acerto em AST/grep |
| 14 | F401 | `queue` | queue | morto | sem acerto em AST/grep |
| 17 | F401 | `threading` | threading | morto | sem acerto em AST/grep |
| 20 | F401 | `Counter` | collections.Counter | morto | sem acerto em AST/grep |
| 21 | F401 | `contextmanager` | contextlib.contextmanager | morto | sem acerto em AST/grep |
| 21 | F401 | `nullcontext` | contextlib.nullcontext | morto | sem acerto em AST/grep |
| 22 | F401 | `deepcopy` | copy.deepcopy | morto | sem acerto em AST/grep |
| 23 | F401 | `Annotated` | typing.Annotated | morto | sem acerto em AST/grep |
| 23 | F401 | `Dict` | typing.Dict | morto | sem acerto em AST/grep |
| 23 | F401 | `List` | typing.List | morto | sem acerto em AST/grep |
| 23 | F401 | `Literal` | typing.Literal | morto | sem acerto em AST/grep |
| 23 | F401 | `Optional` | typing.Optional | morto | sem acerto em AST/grep |
| 24 | F401 | `Callable` | collections.abc.Callable | morto | sem acerto em AST/grep |
| 24 | F401 | `Iterator` | collections.abc.Iterator | morto | sem acerto em AST/grep |
| 26 | F401 | `HTTPException` | fastapi.HTTPException | morto | sem acerto em AST/grep |
| 26 | F401 | `Response` | fastapi.Response | morto | sem acerto em AST/grep |
| 29 | F401 | `StreamingResponse` | fastapi.responses.StreamingResponse | morto | sem acerto em AST/grep |
| 31 | F401 | `AIMessage` | langchain_core.messages.AIMessage | morto | sem acerto em AST/grep |
| 31 | F401 | `HumanMessage` | langchain_core.messages.HumanMessage | morto | sem acerto em AST/grep |
| 31 | F401 | `SystemMessage` | langchain_core.messages.SystemMessage | morto | sem acerto em AST/grep |
| 32 | F401 | `BaseModel` | pydantic.BaseModel | morto | sem acerto em AST/grep |
| 32 | F401 | `ConfigDict` | pydantic.ConfigDict | morto | sem acerto em AST/grep |
| 32 | F401 | `Field` | pydantic.Field | morto | sem acerto em AST/grep |
| 32 | F401 | `field_validator` | pydantic.field_validator | morto | sem acerto em AST/grep |
| 36 | F401 | `log_fallback` | observability.telemetry.log_fallback | morto | sem acerto em AST/grep |
| 42 | F401 | `gamedata` | gamedata | leitura | 7 leituras (ex.: tests/test_combat_simulator.py:35 attr) |
| 43 | F401 | `persistence_module` | persistence | morto | sem acerto em AST/grep |
| 44 | F401 | `progression` | progression | morto | sem acerto em AST/grep |
| 45 | F401 | `create_player_character` | character_creator.create_player_character | morto | sem acerto em AST/grep |
| 46 | F401 | `CLASSES` | gamedata.CLASSES | morto | sem acerto em AST/grep |
| 46 | F401 | `load_json_data` | gamedata.load_json_data | leitura | 1 leituras (ex.: tests/test_hardening_persistencia_sse.py:250 attr) |
| 46 | F401 | `seed_factions` | gamedata.seed_factions | morto | sem acerto em AST/grep |
| 61 | F401 | `is_hardened` | infrastructure.runtime.is_hardened | morto | sem acerto em AST/grep |
| 64 | F401 | `is_simulated` | llm_setup.is_simulated | morto | sem acerto em AST/grep |
| 71 | F401 | `_serialize_messages` | persistence._serialize_messages | morto | sem acerto em AST/grep |
| 72 | F401 | `save_path` | persistence.save_path | morto | sem acerto em AST/grep |
| 74 | F401 | `combat_flags` | services.combat_flags | morto | sem acerto em AST/grep |
| 75 | F401 | `retry_once` | services.checkout_retry.retry_once | morto | sem acerto em AST/grep |
| 76 | F401 | `portrait_offer` | services.portrait_offer | morto | sem acerto em AST/grep |
| 77 | F401 | `log_offer_omitted` | services.portrait_offer_log.log_offer_omitted | morto | sem acerto em AST/grep |
| 78 | F401 | `_enemy_intent` | services.enemy_intent | morto | sem acerto em AST/grep |
| 79 | F401 | `_npc_world` | services.npc_world | morto | sem acerto em AST/grep |
| 80 | F401 | `quest_log` | services.quest_log | morto | sem acerto em AST/grep |
| 81 | F401 | `sv` | services.state_views | morto | sem acerto em AST/grep |
| 82 | F401 | `default_chapter_title` | services.chronicle.default_chapter_title | morto | sem acerto em AST/grep |
| 83 | F401 | `player_codex` | services.discovery.player_codex | morto | sem acerto em AST/grep |
| 84 | F401 | `api_error` | services.error_codes.api_error | morto | sem acerto em AST/grep |
| 86 | F401 | `StartScenarioIn` | services.prologue.StartScenarioIn | morto | sem acerto em AST/grep |
| 87 | F401 | `build_start_scenario_ctx` | services.prologue.build_start_scenario_ctx | morto | sem acerto em AST/grep |
| 88 | F401 | `scenario_to_state_seed` | services.prologue.scenario_to_state_seed | morto | sem acerto em AST/grep |
| 90 | F401 | `origin_fragment` | services.prompt_guard.origin_fragment | morto | sem acerto em AST/grep |
| 91 | F401 | `operation_cost` | services.usage_metering.operation_cost | morto | sem acerto em AST/grep |
| 93 | F401 | `creation_visuals` | services.visual_catalog.creation_visuals | morto | sem acerto em AST/grep |
| 94 | F401 | `resolve_turn_visual_state` | services.visual_catalog.resolve_turn_visual_state | morto | sem acerto em AST/grep |
| 95 | F401 | `visual_response` | services.visual_catalog.visual_response | morto | sem acerto em AST/grep |
| 97 | F401 | `faction_tier` | services.reputation.faction_tier | morto | sem acerto em AST/grep |
| 98 | F401 | `starting_world` | world_utils.starting_world | morto | sem acerto em AST/grep |
| 100 | F401 | `ActionRequest` | api_models.ActionRequest | leitura | 18 leituras (ex.: tests/test_streaming.py:554 attr) |
| 101 | F401 | `ArtBriefRequest` | api_models.ArtBriefRequest | morto | sem acerto em AST/grep |
| 102 | F401 | `ArtConfirmRequest` | api_models.ArtConfirmRequest | leitura | 4 leituras (ex.: tests/test_image_quotes_local.py:514 attr) |
| 103 | F401 | `ArtQualityRequest` | api_models.ArtQualityRequest | leitura | 1 leituras (ex.: tests/test_spec352_creature_quote_api.py:169 attr) |
| 104 | F401 | `ArtQuoteRequest` | api_models.ArtQuoteRequest | leitura | 8 leituras (ex.: tests/test_spec352_creature_quote_api.py:40 attr) |
| 105 | F401 | `ChronicleSearchRequest` | api_models.ChronicleSearchRequest | morto | sem acerto em AST/grep |
| 106 | F401 | `CombatSimulatorRequest` | api_models.CombatSimulatorRequest | leitura | 6 leituras (ex.: tests/test_spec290_chefe_sobrevivencia.py:129 attr) |
| 107 | F401 | `CreateCharacterRequest` | api_models.CreateCharacterRequest | leitura | 2 leituras (ex.: tests/test_bug_api_pending_erros.py:136 attr) |
| 108 | F401 | `EquipRequest` | api_models.EquipRequest | morto | sem acerto em AST/grep |
| 109 | F401 | `EspolioRequest` | api_models.EspolioRequest | morto | sem acerto em AST/grep |
| 110 | F401 | `ForjaRequest` | api_models.ForjaRequest | morto | sem acerto em AST/grep |
| 111 | F401 | `GameResponse` | api_models.GameResponse | leitura | 3 leituras (ex.: tests/test_api_attempt_telemetry.py:79 attr) |
| 112 | F401 | `LevelUpRequest` | api_models.LevelUpRequest | morto | sem acerto em AST/grep |
| 113 | F401 | `LojaCartasRequest` | api_models.LojaCartasRequest | morto | sem acerto em AST/grep |
| 114 | F401 | `PrepareCardsRequest` | api_models.PrepareCardsRequest | morto | sem acerto em AST/grep |
| 121 | F401 | `_CLIENT_LATENCY_PATH` | api_core._CLIENT_LATENCY_PATH | morto | sem acerto em AST/grep |
| 122 | F401 | `_NOT_A_FAILURE` | api_core._NOT_A_FAILURE | morto | sem acerto em AST/grep |
| 123 | F401 | `_account_reader` | api_core._account_reader | morto | sem acerto em AST/grep |
| 124 | F401 | `_begin_state_mutation` | api_core._begin_state_mutation | leitura | 5 leituras (ex.: tests/test_spec235_reclaim_local.py:227 attr) |
| 125 | F401 | `_bind_corr` | api_core._bind_corr | morto | sem acerto em AST/grep |
| 126 | F401 | `_captured_usage` | api_core._captured_usage | morto | sem acerto em AST/grep |
| 128 | F401 | `_client_latency_enabled` | api_core._client_latency_enabled | morto | sem acerto em AST/grep |
| 129 | F401 | `_commit_state_mutation` | api_core._commit_state_mutation | morto | sem acerto em AST/grep |
| 131 | F401 | `_embedding_attempt_events` | api_core._embedding_attempt_events | morto | sem acerto em AST/grep |
| 132 | F401 | `_embedding_telemetry_hook` | api_core._embedding_telemetry_hook | morto | sem acerto em AST/grep |
| 133 | F401 | `_enforce_owner_budget` | api_core._enforce_owner_budget | leitura | 9 leituras (ex.: tests/test_spec197_daily_cap.py:268 attr) |
| 134 | F401 | `_enqueue_turn_art` | api_core._enqueue_turn_art | morto | sem acerto em AST/grep |
| 136 | F401 | `_fail_operation` | api_core._fail_operation | morto | sem acerto em AST/grep |
| 138 | F401 | `_llm_log_fields` | api_core._llm_log_fields | leitura | 4 leituras (ex.: tests/test_api_attempt_telemetry.py:48 attr) |
| 141 | F401 | `_meter_auxiliary_operation` | api_core._meter_auxiliary_operation | leitura | 1 leituras (ex.: tests/test_api_attempt_telemetry.py:199 attr) |
| 143 | F401 | `_op_rejected` | api_core._op_rejected | morto | sem acerto em AST/grep |
| 144 | F401 | `_op_replayed` | api_core._op_replayed | morto | sem acerto em AST/grep |
| 145 | F401 | `_prologue_owner` | api_core._prologue_owner | morto | sem acerto em AST/grep |
| 146 | F401 | `_reject_archived` | api_core._reject_archived | morto | sem acerto em AST/grep |
| 147 | F401 | `_reject_memorial` | api_core._reject_memorial | morto | sem acerto em AST/grep |
| 148 | F401 | `_release_failed` | api_core._release_failed | leitura | 1 leituras (ex.: tests/test_fallback_logging.py:97 attr) |
| 149 | F401 | `_turn_logger` | api_core._turn_logger | leitura | 1 leituras (ex.: tests/test_streaming.py:226 attr) |
| 150 | F401 | `_usage_attempts` | api_core._usage_attempts | morto | sem acerto em AST/grep |
| 151 | F401 | `_validated_receipt` | api_core._validated_receipt | morto | sem acerto em AST/grep |
| 154 | F401 | `api_presenters` | api_presenters | morto | sem acerto em AST/grep |
| 156 | F401 | `_card_reward_blocks` | api_presenters._card_reward_blocks | morto | sem acerto em AST/grep |
| 157 | F401 | `_cards_block` | api_presenters._cards_block | leitura | 2 leituras (ex.: tests/test_spec353_misc.py:66 attr) |
| 158 | F401 | `_inventory_block` | api_presenters._inventory_block | leitura | 1 leituras (ex.: tests/test_fase43.py:306 attr) |
| 159 | F401 | `_levelup_block` | api_presenters._levelup_block | morto | sem acerto em AST/grep |
| 160 | F401 | `_portrait_manifest_ctx` | api_presenters._portrait_manifest_ctx | morto | sem acerto em AST/grep |
| 161 | F401 | `_prepared_slots` | api_presenters._prepared_slots | leitura | 2 leituras (ex.: tests/test_spec353_misc.py:68 attr) |
| 162 | F401 | `_public_art_refs` | api_presenters._public_art_refs | leitura | 1 leituras (ex.: tests/test_image_quotes.py:143 attr) |
| 163 | F401 | `_simulation_manifest` | api_presenters._simulation_manifest | morto | sem acerto em AST/grep |
| 164 | F401 | `format_response` | api_presenters.format_response | leitura | 34 leituras (ex.: tests/test_spec293_rotulo_faccao.py:244 attr) |

## Oráculo A (base `3082b857`, 11/11)
- `api_surface_dump` (legacy + hosted): 6 arquivos por perfil, capturados fora do repo.
- `patch_liveness`: ver contagem no hand-back; mutação `LIVENESS_MUTATE=1` capturada. Falha conhecida e alheia na base: `tests/test_spec352_creature_portraits.py::test_view_offer_present_when_eligible` (rate card vencido).
- `evals run` (13 suítes do eval-gates, `--seed 7`) `passed: true`; `playtest run --all --turns 10 --seed 0` (17 perfis; assinatura = linhas `turnos= erros= violações=`).
- Lista dos testes do `patch_liveness`: arquivos `tests/` do `docs/spec381/patch_inventory.json` (151).

## Etapa 1 — R1
- `tests/test_api_surface.py` verde na base (2 passed). Mutação: apagar `format_response` do import de `api.py` reprova `test_api_attributes_read_by_consumers_exist` (lista `evals/core/adapters.py:1194`, `playtest/invariants.py:2177` e testes); revertido.

## Execução (11/11) - resultado
- Commits: E0/E1 `9f0d1427`; E2 `09770c4f`; E3 `b95af30d`; E4 `a7f72603`; E5 `0c1c4dc3`; baseline `8467f9ba`; fechamento (spec, README, size_budget) no commit seguinte.
- Contagem (109 F401): **91 imports removidos** (27 stdlib/terceiros, 32 engine/serviços incluindo o módulo `gamedata`, 31 `api_models`/`api_core`/`api_presenters`, mais `load_json_data`), **18 viraram reexport `X as X`**, **0 ficaram por efeito colateral** (`modules.json` byte-igual em todos os lotes; só `import main  # noqa: F401` segue). `gamedata` e `load_json_data` não viraram reexport: 3 testes passaram a ler `gamedata.*` (D2).
- `api.py`: 1069 -> 984 linhas (-85).
- Oráculo: `api_surface_dump` legacy+hosted byte-igual a cada lote e no fechamento (B2..B5, B); `patch_liveness` A = B (387 chaves, 280 `True`, iguais; `-n 0`); mutação `LIVENESS_MUTATE=1` A = B (24 testes, 19 `failed`, iguais); `evals run` (13 suítes, `--seed 7`) A x B `compare` `passed: true`, `regressions: []`; `playtest run --all --turns 10 --seed 0`: 16 linhas por perfil iguais (só o run id muda).
- `uvicorn api:app` (porta 18406): `smoke_api.sh` SMOKE OK; `tests/test_boot_policy.py` (inclui `importlib.reload(api)`) verde.
- Gate: com `import hashlib` descartável o `ruff check api.py` reprova `F401`; revertido. `ruff check --isolated --select F401,F811,F841 api.py` -> All checks passed. `F841` nos vizinhos (D3, fora de escopo): **2** (`api_presenters.py:1167 climax`, `routes/turn.py:1468 exc`).
- Testes: Etapa 2 `68`+`58` passed; Etapa 3 `287` passed/24 skipped; Etapa 4 `424`/25 skipped; Etapa 5 `633`/27 skipped; `test_size_budget.py` 4 passed.
