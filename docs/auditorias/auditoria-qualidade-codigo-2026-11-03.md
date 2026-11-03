# Auditoria de qualidade do código — 2026-11-03

**Para quem:** o dono do projeto, sem exigir leitura de código.
**Pergunta respondida:** o projeto está bom de construir em cima? Onde dá para cortar, fundir e simplificar? Como estão testes e evals?
**Método:** 6 auditorias paralelas somente leitura (estilo `ponytail-audit`: caça a over-engineering, não a bugs), uma por área. Nada foi executado nem editado. Cada achado tem evidência `arquivo:linha` no anexo. Dois achados de risco foram reconferidos à mão pelo coordenador (marcados ✔).

---

## 1. Veredito em 8 linhas

1. **Dá para construir em cima.** Não é "uma bola de coisa": código morto é raro (dos 183 módulos de `services/`, só 1 não tem chamador; dos 127 tipos do front, 0 sem uso; todas as 211 flags são lidas; todas as deps do `pyproject` são importadas).
2. **O problema não é volume inútil, é concentração.** Quatro arquivos fazem tudo: `api.py` (7.940 linhas, 12 responsabilidades), `agents/storyteller.py` (um nó de 1.548 linhas), `agents/combat.py` (um nó de 1.012 linhas) e `web/src/App.tsx` (1.137 linhas, 20 estados, 19 refs, callbacks descendo 5 níveis). Toda feature nova toca esses arquivos.
3. **Pequenos helpers foram copiados em vez de extraídos.** Cerca de 60 cópias de "tirar acento e baixar caixa" (`_fold`), 25 cópias do leitor de flag `off/shadow/on`, ~40 leitores de JSON com cache caseiro, ~30 guards de structured output iguais, 19 montagens do mesmo evento de telemetria em `llm_setup.py`. **Algumas cópias já divergem** e isso é risco de bug real, não só estética (ver §3).
4. **Flags demais.** 211 flags, 45 `release`; 12 já estão `on` por padrão e carregam o ramo `off` morto. Aposentar flags é provavelmente o maior corte do repo, mas depende de decisão sua.
5. **Testes são acima da média** (7.145 testes, 18.657 asserts, 1 `assert True`, zero `MagicMock`). O custo está na organização: 43 % dos arquivos são "por spec", com 127 construtores de estado e 128 fakes de LLM próprios.
6. **Cobertura real não existe como número** (sem `pytest-cov`). Pelo proxy de imports, só 2 módulos pequenos não têm teste. O risco está dentro dos arquivos gigantes, que o proxy não enxerga.
7. **Evals são sólidos e determinísticos, mas pararam em 19/10**: não cobrem cartas nem bestiário, não comparam com baseline no CI, e a governança (lock de hashes, 3.456 linhas de plano para 281 casos) pesa mais que o valor que entregam hoje.
8. **O repositório está inchado por arquivo gerado**: `project_index/repo_graph.json` (25 MB) foi commitado 492 vezes → pack git de 319 MB. Mais 1 GB+ de lixo local em `.tmp/` sincronizado pelo OneDrive.

**Saldo total estimado: cerca de −17.000 linhas (−9.000 código, −5.000 testes Python, −1.000 e2e, −2.000 scripts), −1 dep, −60 MB versionados, −1 GB local.** Sobre ~340 K linhas no total é ~5 %. O ganho maior não está nas linhas, está nos *splits* (que não cortam linhas, mas tornam cada feature nova mais barata).

---

## 2. Números levantados

| Medida | Valor |
|---|---|
| Código Python não-teste | 178.917 linhas |
| Testes Python | 148.937 linhas em 696 arquivos, 7.145 testes |
| Front (`web/src`) | 14.569 linhas · e2e 9.240 linhas, 297 testes |
| Rotas HTTP em `api.py` | 66 rotas + 7 handlers + 2 middlewares, num só arquivo |
| Flags em `config/flags.yaml` | 211 (45 release, 86 ops, 53 config, 27 dev, 4 kill) |
| Specs | 376 |
| Scripts | 131; 17 órfãos (4.243 linhas) |
| Evals | 11 datasets, 281 casos, 8 evaluators, 100 % determinístico; sem commit desde 19/10 |
| Git | pack 319 MB; `repo_graph.json` 25 MB × 492 commits |
| Worktrees vivos | 21 (10 `bst-*` de bestiário + specs 359/367/368/370–374) |

---

## 3. Riscos de bug encontrados de passagem (fora do escopo, mas vale saber)

Não são over-engineering; apareceram enquanto se caçava duplicação. Cada um merece correção pequena.

| # | Risco | Evidência | Correção |
|---|---|---|---|
| R1 ✔ | **Guia de cartas manda rodar `gen_cards_v4.py`, que apaga curadoria.** O gerador não conhece `momento`/`raridade`/`apex` (0 ocorrências no script; 31 `"momento"` só em `arcanista.json`) e grava por cima de `data/cards/*.json`. Quem seguir `docs/design/CARTAS.md:105` perde as ondas do SPEC-335 sem nenhum teste falhar. | `scripts/gen_cards_v4.py:2518`, `docs/design/CARTAS.md:4-6,105-106` | Apagar o gerador (2.553 linhas) e declarar `data/cards/` como fonte. Mesmo caso: `gen_classes_v2.py` (1.623 linhas; `docs/design/CLASSES.md:132` já manda não rodar). |
| R2 ✔ | **`law.daily_tick` nunca foi ligado.** SPEC-302 deveria registrar a poda de `wanted`; `world_engine` registra só calendar/npc_world/fauna/rumors. `law_state.wanted` cresce no save. | `services/law.py:1719`, `services/world_engine.py:735-738` | `register_day_hook("law", …)` ou apagar a função. |
| R3 | **`custo_folego` existe em duas versões que divergem** (jogo vs lint/simulador). Arena e lint podem avaliar uma carta com custo diferente do que ela tem em jogo. | `services/cards.py:442` vs `services/card_effects.py:1595` | Uma só. |
| R4 | **`_alive` tem 3 semânticas; `_side_of` devolve `"heroes"` num lugar e `"hero"` noutro.** | `card_effects.py:296` vs `conflict_orchestrator.py:164`; `card_effects.py:391` vs `conflict_turn.py:291` | Unificar com nomes explícitos (`can_be_targeted` / `in_fight`). |
| R5 | **Duas regras para esconder facção secreta** — nome pode ser mascarado na tela de combate e aparecer no texto do NPC. | `faction_display.py:33` vs `faction_gate.py:59` | Fundir `faction_gate`+`faction_display`. |
| R6 | **As ~60 cópias de `_fold` não são iguais** (`ascii ignore` vs `combining`, com/sem `strip`, `casefold` vs `lower`, `_` vs espaço). A mesma entidade pode casar num módulo e falhar em outro. | `combat_mechanics.py:467`, `world_utils.py:81`, `lore_quests.py:76`, `reputation.py:74`, `card_effects.py:151`… | Um `services/text.fold()`; migrar com teste de equivalência por módulo. |
| R7 | **Front sem contrato com o backend.** `types.ts` espelha DTOs à mão; backend expõe 18 campos `dict[str, Any]`; e2e roda contra um backend falso também à mão. Campo renomeado passa na suíte e quebra em staging. | `web/src/types.ts:1`, `api.py:2089`, `web/e2e/fixtures.ts` | Tipar os Pydantic primeiro; depois `openapi-typescript` no build. |
| R8 | **Imports locais em `api.py`** (417, 135 de `infrastructure`) podem ser de propósito (cold start da Vercel, ciclos). | `api.py` | Medir antes de subir para o topo. |

---

## 4. Achados por área (rankeados por corte)

Formato: `tag · o que cortar → substituição [onde] (~linhas)`. Tags: `split` dividir arquivo · `delete` apagar · `shrink` mesma lógica em menos linhas · `merge` fundir módulos · `yagni` abstração sem uso · `native` plataforma já faz.

### 4.1 Raiz (`api.py`, `llm_setup.py`, `rag.py`, `persistence.py`…) — net ≈ −1.300 (−1.800 com CLI)

1. `split` **`api.py` em ~12 módulos `APIRouter`** (já há `include_router` em `api.py:303`): boot/CSP/middlewares (~1.130) · auth/conta (~640, 14 rotas) · DTOs → `api_models.py` (~300) · montagem de resposta (`_combat_block` 254 linhas, `_world_block`, `_cards_block`) → `api_presenters.py` (~1.350) · health/metrics (~510) · leitura (mapa, state, codex, history) (~260) · billing (~480) · arte/prólogo (~540) · jogo novo + pipeline do turno (~1.700) · SSE (~430) · equip/cartas/levelup (~330) · saves/crônica (~200). Saldo 0; ganho é legibilidade.
2. `delete` **`game_engine.py`** (CLI, 477 linhas): segundo cliente que refaz criação/turno/morte fora da API; defasado em cartas/flags/cobrança; 1 teste. → web, ou CLI fino que chama a API. **Decisão sua** (AGENTS.md o lista como comando).
3. `shrink` **`llm_setup.py`**: `LLMAttemptEvent(...)` montado à mão 19× (~−200) + preparação de candidato duplicada entre `invoke`/`stream`/`_stream_attempt` (~−120). → `_attempt()` e `_prepare_candidate()`.
4. `delete` **reforços de combate** (`RPG_COMBAT_REINFORCEMENTS`): "abandonados pelo dono" no registro de staging, default `off`. `services/reinforcements.py` (224) + ganchos em `api.py:3269`, `combat_flags.py:26`, `vercel_env.py`, `world_utils.py:1318`, `state.py:99` + teste 325. (~−260)
5. `shrink` **`rag.py`**: `add_memory_to_session` ≈ `add_npc_memory` (150 linhas cada; diferem em scope/npc_id/prefixo) → `_add_memory(scope, …)` (~−130); idem `query_session_by_vector`/`query_npc_by_vector` (~−30).
6. `shrink` **`persistence.py`**: `_state_to_save_data` e `_raw_to_state` são listas espelhadas de 80+ campos → tabela única `CAMPO → (default, limite, normalizador)` usada nos dois sentidos (~−120). Exige teste de round-trip.
7. `shrink` **checagem de perfil runtime** copiada 32× (`rag.py` ×9, `persistence.py` ×8) embora `api.py:308` já tenha `_database_profile()` → `is_database_profile()` (~−30; ~−300 se FAISS/JSON virar adapter de `runtime.memory_store`).
8. `native` **"carregar save ou 404"** copiado 15× em `api.py` → `_load_or_404()` ou `Depends` (~−30).
9. `delete` aliases de rota sem uso no web (`/game/{id}/art/player/confirm`, `/auth/logout`) — confirmar com app Android antes; métrica `DEPRECATED rpg_sse_first_event_seconds`; formato antigo de mensagem em `_deserialize_messages`; mapa buscado duas vezes (`/game/map` e `/data/map`). (~−80)

### 4.2 Agentes + combate/cartas — net ≈ −540 (−1.000 após cartas `on` definitivo)

1. `split` **`storyteller_node`** (1.548 linhas, `agents/storyteller.py:1173-2720`) → `time_passage.py` (~330) · `context.py` (~280) · `apply_update.py` (~450) · nó orquestrador (~250).
2. `split` **`_combat_node`** (1.012 linhas, `agents/combat.py:2206-3218`) → `start.py` / `round.py` / `finish.py`; `_run_round` (483 linhas, `conflict_orchestrator.py:2517-3000`) em pré-rodada / laço / fim.
3. `shrink` **~30 guards `isinstance(res, Model)`** com try/except/log/fallback cada → `llm_setup.invoke_structured(llm, schema, msgs, *, node) -> Model | None` (~−150). `librarian.py:89` faz o teste invertido.
4. `delete` **funções sem chamador de produção** (só testes): `combat_mechanics.tick_conditions` (111, substituída pelo orquestrador), `cards.set_deck` (60, recurso nunca ligado), `conflict_scene.set_postura`/`consume_postura_on_attack`/`clear_sustained_postura`/`alert_party`, `card_effects.resolve_card`, menores. (~−200)
5. `delete` (condicional) **caminho de combate sem tabuleiro** quando `RPG_CARD_DECK=on` for definitivo: `_parse_turn_declaration` (209), `_narrate` por rodada (104), ramos `if not board_on`, modo `shadow` de `card_piles`. (~−450). **Hoje ainda necessário**: default `off` e playtest usa.
6. `shrink` `_fold` ×6 no escopo, leitor de flag tri-state ×4, `_infer_tier_from_name` que sempre devolve FAST, `_pool_enabled` idêntico em 2 arquivos, `_last_human_text` ×3, fallbacks `try/except ImportError` para módulos do próprio repo. (~−120)
7. **Mantido:** `combat_mechanics.py` está quase todo vivo (orquestrador chama `cm.*`); `ROUTES` multi-provider se justifica.

### 4.3 `services/` (183 módulos) — net ≈ −1.300

Saudável: cada módulo é dono declarado de um campo; famílias `npc_*`, `faction_*`, `quests/rumors/plots`, `creature_*` se chamam em vez de se copiar — **não fundir**.

1. `delete` **ramos `shadow`/`off` de 12 flags `release` já `on`** (`RPG_WORLD_ENGINE`, `_WORLD_QUESTS`, `_RUMORS`, `_LORE_QUESTS`, `_CALENDAR`, `_NPC_SELF`, `_COMPANION_SOUL`, `_CONTEXT_PREFETCH`, `_OPENING_THREAD`, `_NPC_TWO_PHASE`, `_REPLAN_AFTER`, `_COMPANION_ROMANCE`). 50 referências a `shadow` só em 9 módulos. (~−300 + testes). **Decisão sua.**
2. `shrink` **~30 cópias de `_fold`** → `services/text.fold()` (~−150). Ver R6.
3. `shrink` **25 funções `mode()`/`enabled()`** repetindo `os.getenv().strip().lower()` e encadeando dependências à mão → `flags.mode("RPG_X", requires=…)` lendo `config/flags.yaml` (que hoje só `scripts/flag_registry.py` lê) (~−120).
4. `shrink` **leitura de JSON com cache à mão**: 17 `_load*`, 26 `json.loads(read_text)`, 47 `lru_cache`, 19 `reload()`. Já existe `services/file_cache.py` (SPEC-317) usado por só 2 módulos → `file_cache.load_json(path)` para todos (~−150).
5. `delete` funções sem referência alguma (`law.daily_tick` — ver R2; `npc_world.escort_stop`; `world_engine.region_pressure`; `faction_relations.faction_relation`/`relation_label`) e ~55 usadas só em testes. (~−250)
6. `merge` `faction_gate`+`faction_display` → `faction_visibility.py` (~−130; ver R5) · `embedding/image/speech_pricing` → `pricing_cards.py` (~−70) · 5 formas de "problema achado" (`Finding`×2, `Issue`, `ValidationResult`, `list[str]`) → um `Issue(level, code, message, path)` (~−40).
7. `delete`/`move` `gameplay_oracles.py` (0 chamadores, 47 linhas); inlinar `social_direction`, `art_similarity`, `prologue_token`, `intent_guard` (1 chamador cada); `creature_gen_eval` → `scripts/bestiario/`; `google_play_fake` → `dev/`.

### 4.4 Infra, scripts, CI, repositório — net ≈ −7.000 linhas, −60 MB versionados, −1 GB local

1. `native` **tirar `project_index/repo_graph.json` do git** (25 MB × 492 commits = o pack de 319 MB). Gerar sob demanda, ignorar, adaptar `project_index check` no CI e `wt.sh`/`reindex.sh`.
2. `delete` **`.tmp/`** (120 entradas de set/out; `spec176-clone` com `.git`+`.venv`+`node_modules`, dentro do OneDrive). Já ignorado pelo git; deixa buscas lentas, dá "Permission denied" e viola `BRIEF_SUBAGENTE`. Também pastas vazias `frontend/` e `de/` na raiz.
3. `delete` **`gen_cards_v4.py`** (2.553) e **`gen_classes_v2.py`** (1.623) — ver R1. `migrate_bestiary_v4.py` (1.354) precisa análise (importado por teste 287).
4. `delete` **17 scripts órfãos de evidência de spec** já executada (~2.000 linhas): `spec222_art_purge`, `spec236_daily_cap`, `spec279_usage_survives_delete`, `security_wave_smoke`, `browser_voice_smoke`, `stt_fallback_smoke`, `jev_primary_measure`, `smoke/spec351_opening`, `smoke_local_profile`, `migrate_embedding_profile`, `bestiario/arena_todas.sh`… **Manter** os citados em runbooks (`incident_drill`, `finops_margin_sim`, `vercel_bundle_check`, `restore_local`, `retire_creature_portrait`).
5. `yagni` **perfis `portable` e `hosted` (S3 + OIDC)**: linhas de config idênticas (`runtime.py:225-226`); nenhum deploy usa (staging = `hosted-supabase`, SPEC-104 em espera). Estacionar `s3_blob.py` (69), `oidc_identity.py` (207), ramos em `runtime.py`/`cloud_doctor.py`, extra `boto3`. (~−350 + 5 testes). **Decisão sua.**
6. `shrink` **CI repetido**: `eval-gates.yml:98-102` roda 9 `test_eval_*` que `validate.yml` já roda; `npm ci && test && build` roda 3× por PR; `npm audit` duplicado. (~3–5 min de CI por PR)
7. `delete` **mídia em `docs/`** (51 MB, 1.123 arquivos): vídeo de divulgação (mp3 6 MB, mp4, 74 arquivos = 15 MB) e capturas PNG/WEBM de evidência (~22 MB). → fora do repo ou Git LFS.
8. `shrink` dois leitores de `.env` idênticos (`release/checklist.py:519`, `staging/s192.py:26`) → `staging/common.py`; `infrastructure/ports.py` (Protocol com 1 implementação).
9. **Sem corte**: `observability/`, migrations Supabase, `handoffs/`, todas as 104 vars do `.env.example`, todas as deps.

### 4.5 Front `web/` — net ≈ −1.000 (−1.600 com item 3), −1 dep possível

Saudável: 0 tipos mortos, 2 classes CSS mortas em 619, `http.ts`/`api.ts` não se duplicam, devDeps todas em uso.

1. `delete` **4 specs e2e que só tiram prints** (`deck-342-prints`, `spec347-prints`, `spec354-prints`, `diagnostics/spec201-capture`; opt-in, 1–8 expects cada). (~−600)
2. `shrink` **19 e2e de combate nomeados por spec** (1.664 linhas) → 3 arquivos por feature (tabuleiro, Livro, retrato) com laço de viewport. (~−400)
3. `yagni` **governança de efeitos**: `design/effects.registry.ts` sem importador no app; `effects.spec.ts` 673 linhas/26 testes com projeto Playwright próprio → 1 teste de kill switch + 1 de reduced-motion. (~−500) **Decisão sua.**
4. `shrink` **`App.tsx`** → hooks `useAuthSession` (`:130-305`), `useImageQuote` (`:378-445`), `useTurn` (`:498-760`, stream/retry — maior risco de regressão), `useSaves` (`:769-850`); App fica ~300 linhas.
5. `shrink` **prop-drilling 5 níveis** (`onEquip`, `onPrepareCards`, `onCardReward`, `onGeneratePortrait`) → `GameActionsContext` (~−60).
6. `split` **`Hud.tsx`** (577 linhas, 7 abas, nenhum HUD) → 1 arquivo por aba.
7. `delete` wrappers de 2–4 linhas (`workspace/tabs/BestiarioTab`, `PersonagemTab`); `WebStripeAdapter`/`selectPurchaseAdapter` (só teste usa); 2 classes CSS. (~−40)
8. `native` `motion` usado em 5 arquivos, quase só fade → CSS `@starting-style`/View Transitions. Prioridade baixa.
9. **Mantido** até decisão da SPEC-198: Capacitor, `purchases/androidPlay.ts`.

### 4.6 Testes, evals, playtest — net ≈ −5.000 linhas de teste

**Qualidade:** boa. Destaque `tests/test_mecanica_orfa.py:935` (exige teste de efeito para toda mecânica declarada). Goldens legítimos (330/358/360). `conftest.py` enxuto, 0 fixtures mortas.

**Problemas:**
1. **Organização por spec**: 299 de 696 arquivos (57 K linhas, 38 %) têm `specNNN` no nome; `conflict_orchestrator` é testado por 65 arquivos de épocas diferentes; não existe "o teste do combate". Uma spec (325) tem 13 arquivos.
2. **127 arquivos definem construtor de estado próprio** (`_state` ×81, `_player` ×32…) e **94 definem fake de LLM próprio** (128 definições) → `tests/factories.py` + `tests/fakes/scripted_llm.py` (~−3.000).
3. **~29 testes leem código-fonte e checam substring** (`getsource`, posição de strings em `App.tsx`) — quebram em refatoração e não provam comportamento. (~−800)
4. **Splits de §4.1/4.2 quebram monkeypatch**: ~151 patches em `api.*`, 85 `persistence`, 55 `rag`, 50 `llm_setup`, ~196 em storyteller/combat. Saída: reexports no módulo antigo durante a transição.

**Cobertura:** sem `pytest-cov`. Proxy por import: 8 módulos sem import em teste, 6 aparecem por string; só `services/file_cache.py` e `services/art_similarity.py` sem teste próprio; 67 módulos com 1–2 testes (ex.: `game_engine.py`, `error_codes.py`, `postgres_shared_pool.py`, `oidc_identity.py`). Chute honesto: 70–85 % de linhas no núcleo, bem menos em infra/workers. Precisa de número real.

**Evals:** 281 casos, 11 datasets, 8 evaluators, 100 % determinístico, roda no CI. Mas: (a) sem commit desde 19/10; épico de cartas (327–368) e bestiário (349–361) **sem caso de eval**; (b) CI **não compara com baseline** (única baseline de 17/10); (c) nenhuma medida recorrente de qualidade com LLM real; (d) governança (lock de hashes, 16 caminhos protegidos, `eval-protected.yml`, 4 schemas, plano de 3.456 linhas, política de tiers Luna/Terra/Sol/Astra que não bate com os subagentes usados) é pesada para 1 dev e 281 casos. Na prática viraram uma segunda suíte pytest em JSONL.

**Playtest:** 53 checks (47 registrados); `check_roundtrip`/`check_reproducibility` são helpers de teste dentro de módulo de produção; **16 perfis, não 14** (corrigir AGENTS.md).

---

## 5. Proposta de specs (para você autorizar)

Ordenadas por **valor ÷ risco**. Cada linha vira uma spec `draft` quando você aprovar. Marque as que quer.

| # | Spec proposta | Área | Corte | Risco | Depende de você? |
|---|---|---|---|---|---|
| A | **Higiene do repositório**: `repo_graph.json` fora do git + gerar sob demanda; apagar `.tmp/`, `frontend/`, `de/`; mídia de `docs/` para fora/LFS; CI sem jobs repetidos | infra | −60 MB, −1 GB local, −3–5 min CI | baixo | não |
| B | **Geradores-armadilha e scripts órfãos**: apagar `gen_cards_v4.py`, `gen_classes_v2.py`, 17 scripts de evidência; `data/cards` e `data/classes.json` viram fonte; corrigir `CARTAS.md`/`CLASSES.md` | scripts | −6.000 | baixo | não |
| C | **Bugs de passagem**: ligar/apagar `law.daily_tick`; unificar `custo_folego`, `_alive`, `_side_of`; fundir `faction_gate`+`faction_display` | serviços | −200 | médio (muda comportamento nas bordas; teste de caracterização) | não |
| D | **Helpers comuns**: `text.fold()`, `flags.mode()` lendo `flags.yaml`, `file_cache.load_json()` em todos, `invoke_structured()` para guards, `_load_or_404()`, `is_database_profile()`, `_attempt()`/`_prepare_candidate()` em `llm_setup`, `_add_memory` em `rag`, tabela de campos em `persistence` | raiz + serviços + agentes | −1.500 | médio (R6: `_fold` diverge; round-trip de save) | não |
| E | **Fatiar `api.py`** em routers por domínio + `api_models.py` + `api_presenters.py`, com reexports para os 151 monkeypatches | raiz | 0 linhas, legibilidade | médio (testes acoplados; imports locais/cold start — medir) | não |
| F | **Fatiar `storyteller_node` e `_combat_node`/`_run_round`** com reexports para os ~196 patches | agentes | 0 linhas, legibilidade | médio | não |
| G | **Front**: hooks `useTurn`/`useAuthSession`/`useSaves`/`useImageQuote`, `GameActionsContext`, `Hud.tsx` por aba, e2e por feature, apagar specs de prints e wrappers | web | −1.000 | médio (stream/retry em `App.tsx:498-760`) | não |
| H | **Testes**: `tests/factories.py` + `tests/fakes/scripted_llm.py`; migrar os 127 construtores e 128 fakes aos poucos; trocar/apagar os ~29 testes de substring de código; regra "teste novo vai no arquivo do módulo"; consolidar 325/297/363/364 | testes | −5.000 | baixo–médio | não |
| I | **Cobertura real**: `pytest-cov` + `--cov-branch` num job semanal (sem gate); relatório por módulo | testes | 0 | baixo | não |
| J | **Evals vivos**: `evals compare --baseline` no CI com baseline regenerada no pouso; suíte `cards_combat` (~20 casos dos goldens 330/358); `llm_playtest` semanal com 5 turnos nos 4 perfis vitais como métrica; afrouxar governança (lock só de `evals/core`, apagar política de tiers) | evals | ~0 | baixo (governança é decisão sua) | parcial |
| K | **Aposentar flags `release` já `on`** (12) e apagar o ramo `off`; decidir as 11 `shadow`; reforços de combate (`RPG_COMBAT_REINFORCEMENTS`) fora | flags | −600+ | baixo | **sim** (quais flags) |
| L | **Estacionar perfis `portable`/`hosted` (S3+OIDC)** e `boto3` até a SPEC-104 voltar | infra | −350, −1 dep | baixo | **sim** |
| M | **Apagar CLI `game_engine.py`** ou reduzir a cliente fino da API | raiz | −470 | baixo | **sim** |
| N | **Caminho de combate sem tabuleiro** fora, após cartas `on` definitivo em staging | agentes | −450 | médio | **sim** (depende do smoke §6) |
| O | **Contrato front↔back**: tipar os 18 `dict[str, Any]` do `GameResponse` em Pydantic; depois `openapi-typescript` no build | api + web | 0 | médio | não |

**Ordem sugerida de execução:** A → B → C → I → D → H → E → F → G → J → O; K/L/M/N quando você decidir. A, B, C, I são rápidas e independentes; D antes de E/F porque os splits ficam menores depois dos helpers; H junto com qualquer split (os reexports são temporários).

**O que NÃO proponho mudar:** famílias de `services/` (npc, facções, quests, criaturas); `combat_mechanics.py` (vivo); `ROUTES` multi-provider; `observability/`; migrations; `http.ts`/`api.ts`; Capacitor/Android; bloco de pagamentos (YAGNI por calendário, mas pedido em spec).

---

## 6. Plano de execução da onda (SPEC-375 a SPEC-385)

Dono autorizou em 03/11 transformar o relatório em specs, "sendo bem crítico para não quebrar nada" e
lembrando que **outras sessões trabalham em paralelo**. As regras abaixo valem para as 11 specs; cada
spec cita a regra pelo código (W1…W8).

### 6.1 Mapeamento letra → spec

| Letra do §5 | Spec | Observação |
|---|---|---|
| A | SPEC-375 higiene do repo (índice, CI, lixo local) | sem mídia (ver 6.4); `.tmp/` tem dumps de staging (revisão) |
| B + parte de D/§4 "sem chamador" | SPEC-376 fonte de cartas/classes + poda morta | exclusões da SPEC-272 obrigatórias |
| C | SPEC-377 divergências (lei, fôlego, `_alive`, facção) | **muda comportamento de propósito** |
| D | SPEC-378 helpers comuns | só cópias **equivalentes**; sem `file_cache`, sem tabela de `persistence` |
| H + I | SPEC-379 testes: fábricas, fake de LLM, cobertura | sem renomear em massa |
| J | SPEC-380 evals vivos | `EVAL_AUTHORING_REQUIRED` |
| E | SPEC-381 `api.py` em routers | oráculo = OpenAPI byte-igual |
| F | SPEC-382 nós grandes dos agentes | extrair **no mesmo arquivo** (preserva monkeypatch) |
| G | SPEC-383 front: hooks, contexto, Hud, e2e | depois da 379 (testes que leem `App.tsx`) |
| K + L + M + N | SPEC-384 poda por decisão do dono | cada item é um D seu |
| O | SPEC-385 contrato front↔back | opcional, baixa prioridade |

### 6.2 Regras da onda

- **W1 — Trava de arquivos (anti-conflito com outras sessões).** *(Revisada após as revisões
  independentes de 03/11: a versão só-branches não via sessões que commitam direto na `main` e travava
  para sempre por branches mortas.)* Antes de **cada etapa**, o executor junta três fontes e cruza com os
  arquivos da etapa; interseção não vazia ⇒ a etapa **espera** (não começa e não "resolve no rebase"):
  1. **Branches vivas:** branches com commit à frente da `main` **e** com commit nos últimos 7 dias
     (branches paradas, ex.: `spec-214`, `spec-349-pre-sync`, `feat/*` antigas, ficam fora e são listadas
     para o dono arquivar);
  2. **Mudanças não commitadas** em todos os worktrees, **inclusive o checkout principal**
     (`git -C <wt> status --porcelain` para cada linha de `git worktree list`);
  3. **Specs `in-progress` que trabalham direto na `main`** (sem branch): arquivos citados na §3 da spec
     e arquivos dos commits recentes delas (`git log --since=2.days --name-only main`).
  ```bash
  { for b in $(git for-each-ref --format='%(refname:short)' refs/heads | grep -vE '^(main|backup/)'); do
      [ "$(git rev-list --count main..$b)" -gt 0 ] && [ -n "$(git log -1 --since=7.days --format=%h $b)" ]         && git diff --name-only main...$b
    done
    git worktree list --porcelain | sed -n 's/^worktree //p' | while read -r wt; do
      git -C "$wt" status --porcelain | cut -c4-
    done
    git log --since=2.days --name-only --format= main
  } | sort -u > /tmp/travados.txt
  comm -12 /tmp/travados.txt <(sort -u etapa_arquivos.txt)   # tem que sair vazio
  ```
  A fonte 3 é conservadora de propósito (trava por arquivo tocado recentemente na `main`); o executor pode
  liberar um arquivo se a spec que o tocou estiver `done` e a sessão dela ociosa (`ListAgents`).
- **W2 — Oráculo de equivalência** (toda etapa marcada "refatoração pura"). Antes e depois:
  1. `uv run pytest` completo verde (coordenador, 1×, no pouso);
  2. `uv run python -m evals run` nas 12 suítes do `eval-gates.yml` com `--seed 7` → saída A (antes) e B
     (depois); `uv run python -m evals compare --current B --baseline A` **sem nenhuma diferença**;
  3. `uv run python -m playtest run --all --turns 10 --seed 0`: mesma contagem de violações por perfil e
     mesmo desfecho (vivo/morto/turnos). Não é byte-a-byte: a campanha tem caches globais de conteúdo
     gerado ([playtest/invariants.py:1763](../../playtest/invariants.py#L1763));
  4. quando tocar a API: dump de `app.openapi()` e da lista `(path, methods, name)` de `app.routes`
     **byte-iguais**.
- **W3 — Refatoração pura não muda asserção.** Só pode mudar em teste: alvo de `monkeypatch`/import.
  Se algum teste precisar de asserção nova, a etapa **não é pura**: para, registra e reporta.
- **W4 — Um commit por mudança mecânica**, revertível sozinho (`git revert <sha>`).
- **W5 — Caminhos protegidos de eval** (`evals/protected-paths.txt`) só na SPEC-380, por um agente que
  não toca produto, com publicação via `/eval-publish`.
- **W6 — Uma spec de refatoração em voo por vez** desta onda (elas se cruzam entre si), no máximo
  1 executor + 1 revisor simultâneos (RAM; regra do dono de 24/10). RAM livre < 3 GB ⇒ enfileira.
- **W7 — Revisão independente obrigatória** (`spec-reviewer`, Opus) em todas; o revisor roda o W2 de novo
  por conta própria em pelo menos 1 item.
- **W8 — Nada de reescrever histórico git** (force-push quebra os 21 worktrees e as outras sessões).

### 6.3 Ordem e travas conhecidas em 03/11

| Ordem | Spec | Pode começar quando | Arquivos quentes hoje (branch) |
|---|---|---|---|
| 1 | 375 | 368 pousada (tem commit em `project_index/`) | `project_index/` (368) |
| 2 | 376 | já (etapas de cartas esperam 368) | `services/cards.py`, `card_effects.py` (368) |
| 3 | 377 | itens de lei/facção já; fôlego/`_alive` após 368 | idem |
| 4 | 379 | já | — |
| 5 | 378 | após 376/377; etapas de `combat.py`/`loot.py`/`persistence.py` após 367/368/371 | `agents/combat.py` (371), `agents/loot.py` (367), `persistence.py` (368) |
| 6 | 381 | 367 e 368 pousadas e nenhuma branch tocando `api.py` | `api.py` (367, 368) |
| 7 | 382 | storyteller já; combate após 371 | `agents/combat.py` (371) |
| 8 | 383 | 379 R6 pousada; 367/368/371 pousadas | `App.tsx` (367), `types.ts` (368, 371) |
| — | 380 | 370 e 374 pousadas (tocam `protected-paths.txt`) | `evals/protected-paths.txt` (370, 374) |
| — | 384 | por decisão sua, item a item | `config/flags.yaml` (371) |
| — | 385 | após 381 e 383; opcional | — |

### 6.4 Itens do §4 que **saíram** depois da verificação crítica

| Item | Por que saiu |
|---|---|
| Apagar `set_postura`, `consume_postura_on_attack`, `clear_sustained_postura`, `alert_party`, `suggested_virtue_cards` | Você decidiu **manter** na SPEC-272 (tabela "(c) manter"). Não reabrir. |
| Apagar `services/gameplay_oracles.py` | Contrato nominal da SPEC-212, testado por paridade (auditoria 18/10, "Não podar"). |
| Mover `services/creature_gen_eval.py` | SPEC-374 está editando agora; é código de eval. |
| Apagar `currentPurchaseAdapter`/`WebStripeAdapter` | Gancho da SPEC-198 (revisão de 18/10). |
| Mídia de `docs/` (mp3/mp4/png) | SPEC-266 já tirou o que dava; o resto é insumo do projeto Remotion ou evidência linkada. E o histórico guarda tudo mesmo (W8). |
| Leitores de `.env` duplicados | Já usam `python-dotenv`; ganho de ~5 linhas (SPEC-273 §R3). |
| Subir os 417 imports locais de `api.py` | Podem ser de propósito (cold start de 19–59 s na Vercel, ciclos). |
| Migrar tudo para `services/file_cache.py` | 19 seams `reload()`/`cache_clear` usados pela suíte; semântica mtime ≠ `lru_cache`. |
| Tabela única de campos em `persistence.py` | Mexe no round-trip de save para ganhar ~120 linhas; as listas espelhadas são explícitas e legíveis. |
| Trocar `motion` por CSS | Dep funciona; reescrever animação custa mais que a dep. |
| Renomear os 299 arquivos `test_specNNN_*` | Churn enorme, conflito com toda branch aberta, perde `git blame`. Só regra daqui pra frente. |
| Fundir jobs de `npm ci/build` entre workflows | Compartilhar artefato entre workflows é mais complexo que os 3 min economizados. |

### 6.5 Correções feitas pelos autores das specs (verificação no código)

A escrita das specs reverificou cada achado. O que mudou em relação aos §3–§5:

- **Scripts "órfãos":** 4 dos 11 estão vivos (`spec222_art_purge` citado em `docs/spec364/smoke-final.md:98`;
  `spec351_opening` com medição pendente da 366; `migrate_embedding_profile` é o único caminho da migração da
  SPEC-234 no deploy; `arena_todas.sh` ainda é usado). A SPEC-376 recomenda apagar só 3.
- **`/auth/logout` não é alias:** é a rota canônica (SPEC-220) e o bundle Android a chama. Fica. Só
  `/art/player/confirm` sai (SPEC-384 D8).
- **Reforços:** metade dos "ganchos" é outra mecânica (o fugitivo que volta com reforços) e fica (SPEC-384 D3).
- **Lei:** `daily_tick` não ligado **muda o jogo** (depois de suborno, caçador chega sem aviso), não só o save (SPEC-377).
- **`_side_of` "hero"/"heroes":** não é bug, cada módulo só compara consigo. Bug candidato novo: inimigo rendido
  continua alvo de Carta (SPEC-377 D3).
- **Facção:** duas políticas de propósito (SPEC-293 × SPEC-314), não regra duplicada; recomendação é não fundir (SPEC-377 D4).
- **Fôlego:** a arena já usa a regra do jogo; a divergência só afeta lint/relatório (SPEC-377 D2).
- **Helpers:** 38 folds (32 candidatos), ~29 leitores de flag, 19 sites de structured output (5–9 migráveis);
  `RPG_RUNTIME_PROFILE=""` tem respostas diferentes em 4 arquivos. Saldo real da 378: −330 a −500 linhas.
- **`api.py`:** 65 rotas, 8 handlers, 5 middlewares; ~140 patches sobre 34 nomes; 11 testes leem o texto/AST
  do arquivo; o e2e do web **não** bate na API real (backend falso), então não serve de oráculo (SPEC-381).
- **Nós grandes:** 210 patches nos testes confirmam extrair no mesmo arquivo (SPEC-382).
- **Testes:** não existe construtor canônico do estado inicial (montado inline em `api._create_game` e copiado,
  já divergente em 13 campos, em `playtest/runner.py`); a 379 **acrescenta** +300 a +650 linhas.
- **Evals:** `compare` já falha em regressão (não precisa mexer em `evals/core` para R1); baseline local é de 30/09
  e inútil; 15 caminhos protegidos.
- **Contrato:** 16 campos `Any` (não 18) no `GameResponse`; recomendação é a opção barata (snapshot de forma).

**Saldo revisado da onda:** bem menor que o −17.000 do §1. Código de produto ≈ −2.000 a −3.000 linhas
(375 a 384, sem contar flags de D1 ainda não medidas); testes crescem no curto prazo. O ganho principal é
estrutural: `api.py`, nós de agente e `App.tsx` em pedaços com dono, e helpers únicos onde eram equivalentes.

### 6.6 Revisão independente das specs (03/11, noite)

Onze revisores Opus que não escreveram as specs refizeram as buscas com terminal, rodaram sondas só de
leitura e testes focados. Pareceres em `handoffs/SPEC-NNN-independent-review.md`; cada spec tem uma seção
"Resposta à revisão" mapeando achado → mudança. Todos os P0/P1 foram aplicados.

| Spec | Veredito | P0 que a revisão pegou (já corrigido na spec) |
|---|---|---|
| 375 | seguro com mudanças | `.tmp/` tem dumps do banco de staging e insumos de experimentos congelados; `--theirs` da skill re-rastreia o índice; corrida da fixture com `-n auto` |
| 376 | seguro com mudanças | `env.sh` troca o `RPG_ROOT` → medir os geradores regravaria `data/` no checkout principal; medir a **cadeia** de geradores |
| 377 | seguro com mudanças | bugs da lei e do rendido **confirmados**; storyteller sobrescreve `law_state`; `lote-v2` usa a regra do lint (vira eval authoring) |
| 378 | seguro com mudanças | `invoke_structured` chamava `_log_event` inexistente (guard de FallbackLLM viraria crash); teste de empacotamento Vercel conta literal |
| 379 | seguro com mudanças | paridade com `/game/new` falharia (calendário deriva do `game_id`) |
| 380 | seguro com mudanças | baseline de 688 KB barrada pelo hook de 500 KB; fonte dos `expected` fechada |
| 381 | seguro com mudanças | `include_router` deixa rotas opacas → métrica `route_label` e 3 testes passariam vazios; montar com `routes.extend` |
| 382 | seguro com mudanças | guard da 363 compara o orquestrador com a `main` (D6 do dono); `getsource` de uma linha |
| 383 | seguro com mudanças | lint `react-hooks/refs` reprovaria o desenho; Context com ref recusaria clique rápido |
| 384 | seguro com mudanças | fórmula mudaria o modo do calendário com o motor em `shadow`; staging real é `cc31a6c1` |
| 385 | **adiada** | forma MockLLM instável sem seed; duplicaria a 381; nenhum bug de contrato real até hoje |

Lições que viraram regra: a W1 (§6.2) agora vê commits diretos na `main` e mudanças não commitadas e
ignora branches paradas; nome de parecer de spec é `-independent-review.md` (`tests/test_handoff_names.py`).
Para arquivar (dono): branches paradas `spec-214`, `spec-349-pre-sync`.

---

## Anexo — o que não foi verificado

- Nada foi executado: nenhum corte foi validado contra a suíte.
- Chamadas dinâmicas (`getattr`, string em YAML/JSON) não foram descartadas para as funções "sem chamador".
- Contagens de linhas por corte são estimativas por referência, não medidas ramo a ramo.
- Coverage real, tempo atual da suíte, tamanho de `.tmp/` (o `du` não terminou), peso real do `motion` no bundle, uso dos aliases de rota pelo app Android, painéis Grafana que leem a métrica `DEPRECATED`.
- Se `migrate_bestiary_v4.py` também sobrescreve o bestiário novo do SPEC-349.

Relatórios completos das 6 auditorias ficam no transcrito desta sessão; os achados acima são a consolidação com evidência `arquivo:linha` preservada.
