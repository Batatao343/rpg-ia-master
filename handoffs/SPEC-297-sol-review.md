# SPEC-297 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (final, após a 3ª rodada em `6357f9b3`; a 1ª e a 2ª rodadas foram `CHANGES_REQUIRED`)
> **Revisor:** Opus (papel Sol, independente; foco em segurança entre tenants) · **Data:** 2026-10-23 / 2026-10-24 · **Commits revisados:** `3855057` → `6533e258` → `6357f9b3`

## Escopo

Branch `spec-297`, `main...HEAD` (6 commits, 41 arquivos): `services/shared_pool*.py`,
`services/npc_seed.py`, `infrastructure/{shared_pool_store,postgres_shared_pool,runtime,account_lifecycle}.py`,
`supabase/migrations/20261024100000_shared_pool.sql`, `agents/{npc,storyteller,bestiary,combat}.py`,
`gamedata.py`, `persistence.py`, `state.py`, `services/cron_internal.py`, `workers/shared_pool_jobs.py`,
`scripts/pool_{admin,promote}.py`, `observability/events.py`, testes `tests/test_spec297_*.py`.
Fora do escopo: conteúdo das tabelas de semente (D8, revisão do dono), smoke real §6, suíte completa.

**Postgres não verificado.** Não há Postgres local deste repo. O único Supabase local em execução
(`supabase_db_projeto-racha-spec-pack-v1.0`, :54322) é de outro projeto e não foi usado. Os 9
testes `infra_local` de `tests/test_spec297_shared_pool_local.py` foram pulados. A migração e o RLS
foram revisados só por leitura.

### Os 6 pontos pedidos

1. **Flag `off` = comportamento anterior.** Equivalente na prática: npc, bestiário, combate,
   artefato e npc_actor caem no caminho antigo, e `tests/test_npc_catalog_scope.py` não mudou e
   passa. Não é idêntico byte a byte: o system prompt do storyteller ganha uma linha em branco e
   o save ganha `pool_used: []` (P2-1).
2. **Texto do jogador chegando a outro tenant.** Com o pool ligado, a cena sai do prompt de
   geração. Os validadores de schema, PII, injeção, cópia literal, segredos e unicidade estão
   implementados, e o corpus é coberto só pelos marcadores (teste dedicado; `tests/` não vai para
   a Vercel). Os nomes digitados nos caminhos router/npc_actor e no scanner de combate ficam fora
   (`local_only`). **Exceção:** um nome digitado pelo jogador volta como nome do narrador (P1-3).
3. **Promoção fail-closed.** OK: AIMessage, exceção e `None` mantêm `held` (3 tentativas levam a
   `eval_unavailable`), MockLLM nunca promove e `RPG_POOL_ALLOW_MOCK_EVAL` está em
   `FORBIDDEN_IN_HOSTED` (com teste).
4. **Migração.** Por leitura, está correta. O `rpg_api` só tem `select, insert`; o insert exige
   `held|local_only` e `origin_owner_id = app.current_owner_id()`; a leitura é `promoted` ou o
   próprio owner. O trigger de imutabilidade cobre os campos de conteúdo. A cerca de exclusão
   copia o padrão invoker de `guard_deleted_account_write`. `erase_owner` apaga
   held/local_only/rejected e desvincula o resto (D3), e é chamado em `account_lifecycle.finish`.
   Não foi executada (P1-4).
5. **Cron.** OK: `/internal/cron/shared-pool` chama `authorize(request)` e `_run`, como as
   outras rotas, e há teste de segredo. Porém não repassa `usage_sink`/`owner_values` (P1-1).
6. **Estado de A não vaza para B.** OK: `materialize_npc` copia só a `DOCUMENT_ALLOWLIST`, a
   relação nasce de `initial_relationship`, `status` vem da ficha v4 do motor e os traços ocultos
   são sorteados pelo `game_id` de B. O pool não é escrito depois do `submit`. `own_entries` filtra
   por `origin_game_id`. `cast_entries` exclui o próprio jogo, `pool_used` e os nomes já
   conhecidos.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/cron_internal.py:231`, `scripts/pool_promote.py:22` | Em produção o job é chamado como `promote_due_job(store)`, sem `usage_sink` nem `owner_values`. Efeitos: (a) R20 não é cumprido, pois nenhum `usage_events` é gravado e a FinOps (SPEC-236) não vê o custo da avaliação; (b) o validador `pii` de R14 roda sem o e-mail e o nome de exibição do dono de origem. O teste `test_evaluation_emits_usage_events` só prova o hook. | No cron, montar um `usage_sink` que grave `usage_events` sem dono pagante, no padrão do `compress` em `workers/run_worker.py:150-180`, e um `owner_values(entry)` que resolva e-mail e nome de exibição de `entry.origin_owner_id` pela conexão admin. Passar os dois. Adicionar teste da rota com fake que confirme que os dois chegam a `promote_due`. |
| P1-2 | P1 | `observability/events.py` (arquivo inteiro) | O catálogo foi regenerado com aspas simples e `ruff format --check observability/events.py` acusa "1 file would be reformatted". O CI roda `uv run ruff format --check .` (`.github/workflows/validate.yml:62`) e vai quebrar. A regeneração também removeu `ambient.fallback` e `combat_agent.fallback`. `test_log_event_registry` passa, então parecem mortos, mas a remoção é escopo alheio. | `uv run ruff format observability/events.py`. Confirmar que a remoção dos 2 eventos é intencional ou restaurá-los. |
| P1-3 | P1 | `agents/storyteller.py:1232-1236`, `agents/npc.py` (`_submit_generated_npc`) | O nome digitado pelo jogador é lavado pelo narrador. Se o jogador escreve um nome (de pessoa real, por exemplo) e o narrador o devolve em `introduced_npcs`, a entrada nasce `name_origin="narrator"` e fica elegível. `literal_player_text` usa 6-gramas e nunca pega um nome (< 6 tokens), e o `scan_pii` pega e-mail/telefone, não nome próprio. Só o critério LLM `pii` protege, e ele não tem como saber se "Carlos Mendes" é uma pessoa real. É justamente a ameaça que a SPEC-223 R7 cobria. | Em `_with_new_npc` (ou no `submit`), se `fold_name(new_name)` ou um token dele com ≥ 4 letras aparecer nas entradas recentes do jogador já dobradas, rebaixar para `name_origin="player"` (`local_only`). Teste: a entrada "falo com Carlos Mendes" e o narrador introduzindo "Carlos Mendes" devem dar `local_only`. |
| P1-4 | P1 | `supabase/migrations/20261024100000_shared_pool.sql`, `tests/test_spec297_shared_pool_local.py` | Migração, RLS, triggers, lease do `due()` e `erase_owner` nunca rodaram contra Postgres (executor e revisor). É critério de aceite §5 ("RLS: tenant não autopromove… (teste local Postgres)"). | Subir o Supabase local deste repo, aplicar as migrações e rodar `RPG_TEST_DATABASE_URL=… pytest -m infra_local tests/test_spec297_shared_pool_local.py` antes de aplicar no staging. Registrar o resultado aqui. |
| P2-1 | P2 | `agents/storyteller.py:1015`, `persistence.py:665` | Com a flag `off` não é byte a byte: o system prompt ganha `"\n    \n"` e o save ganha `"pool_used": []`. Não muda a mecânica. | Emitir o separador dentro de `cast_block_text` só quando ele não estiver vazio. O `pool_used` no save pode ficar, mas documentar na spec. |
| P2-2 | P2 | `services/shared_pool_validators.py:85-124`, `services/shared_pool.py:731-735` | `_text_fields` ignora campos que não são `str`/`list[str]`. As chaves de `attributes` (texto livre do LLM), `initial_relationship`, `unique` e `stackable` não passam por validação de tipo nem de faixa, e `materialize_npc` copia `attributes` e `initial_relationship` (sem clamp) para o jogo B. | Em `validate_schema`, exigir `attributes ⊆ {str,dex,con,int,wis,cha}` com valores `int` em faixa, `initial_relationship` `int` na faixa do jogo e `unique`/`stackable` `bool`. No `materialize_npc`, fazer clamp de `initial_relationship`. |
| P2-3 | P2 | migração `:55-56`, `services/shared_pool.py:564-572` | A policy de leitura é por linha, então o `rpg_api` lê `origin_owner_id`, `origin_game_id` e `input_shingles` das entradas promovidas de outros tenants. Não chega ao cliente, mas é dado de outro tenant no request. | Na promoção, zerar `input_shingles` (não servem mais). Avaliar uma view ou grant por coluna sem `origin_*`/`input_shingles` para o `rpg_api`. |
| P2-4 | P2 | migração `:9-34`, `services/shared_pool.py:165` | Uma escrita sem principal roda como `rpg_runtime` (policy `runtime_all`, sem RLS) e grava `held`/`local_only` com `origin_owner_id NULL`. Essa linha escapa do `erase_owner` (LGPD) e do teto por dono. Hoje o principal é propagado nas threads, então isto é defesa em profundidade. | Adicionar `check (origin_owner_id is not null or status in ('promoted','vetoed','retired'))`. Em perfil que não seja legacy, `submit` deve recusar `owner is None`. |
| P2-5 | P2 | `services/shared_pool.py:110-126` | `get_store()` cai para o JSON local quando `get_runtime()` falha, inclusive em hosted: um arquivo em `/tmp` sem RLS (fail-open). | Fora do legacy, propagar o erro (fail-closed). |
| P2-6 | P2 | `agents/storyteller.py:1234` | `messages[-3:]` filtrado por `HumanMessage` dá as 3 últimas mensagens, não as 3 últimas entradas do jogador (R9). | Filtrar `HumanMessage` primeiro e depois pegar `[-3:]`. |
| P2-7 | P2 | `services/shared_pool.py:499,531` | O mock só é detectado antes (`is_simulated`/nome do tipo). R17 pede detecção também pela telemetria (`provider == "mock"`). | Não promover se algum item de `attempts` capturado em `evaluate` tiver `provider == "mock"`. |
| P2-8 | P2 | `infrastructure/account_lifecycle.py:58,350` | R31 cita o inventário (`:159`), mas as linhas `shared_pool` do titular não entram no export (acesso LGPD). | Incluir as entradas não promovidas do owner no export, ou registrar em `RETAINED_WITH_REASON`/doc de retenção por que ficam fora. |
| P2-9 | P2 | `tests/test_spec297_shared_pool_local.py:125-139` | `test_skip_locked_two_workers_no_double_eval` usa a mesma conexão/transação nos dois "workers", então prova o lease, não o `skip locked`. | Usar duas conexões, com a primeira transação aberta. |
| P2-10 | P2 | `agents/bestiary.py` (`_pool_bestiary_view`) | Lista até 200 criaturas promovidas sem filtro de região a cada `load_bestiary` (espírito de R33). | Filtrar por região atual ou pôr cache por turno. |

## Re-revisão (delta `3855057..6533e258`)

Conferi os P1 1–4 e os P2 que o executor marcou como feitos, olhando o código e rodando os testes.

| Item | Situação |
|---|---|
| P1-1 | Corrigido na lógica: `promote_due_job(pool=…)` liga o `usage_sink` (`app.operations` com kind `pool_evaluation` + `usage_events` sob o dono de sistema `…0297`) e o `owner_values`. A nova `operations_kind_check` repete exatamente a lista anterior (`20261016121500`) e acrescenta `pool_evaluation`. **Mas o `owner_values` quebra em hosted (R-1).** |
| P1-2 | `observability/events.py` agora passa no `ruff format --check`. Os 2 eventos "removidos" (`ambient.fallback`, `combat_agent.fallback`) vieram da `main` depois do ponto de partida da branch e voltam no rebase; não há emissor na branch. **Um arquivo novo de teste não está formatado (R-2).** |
| P1-3 | Corrigido: `name_typed_by_player` (nome dobrado como substring, ou token ≥ 4 letras, nas 3 últimas entradas do jogador) rebaixa para `player`/`local_only`. A regra é conservadora (`"Ana"` casa com `"banana"`), o que é aceitável: o erro só tira o NPC do pool. Há teste. |
| P1-4 | Corrigido: os 13 testes de `tests/test_spec297_shared_pool_local.py` passam contra o Postgres local :55322. Eles cobrem RLS de insert/update/leitura, trigger de imutabilidade, CHECK de dono, `skip locked` com 2 conexões, `erase_owner`, cerca de exclusão e sink real. A suposição dos testes locais é o superusuário `postgres`, e é daí que vem a R-1. |
| P2-1 | Prompt corrigido: com a flag `off` ou sem elenco, o system prompt é idêntico ao da `main` (o separador agora mora dentro de `cast_block_text`). `pool_used: []` continua entrando no save. |
| P2-2, P2-4…P2-10 | Conferidos e OK: tipos e faixas em `attributes`/`initial_relationship`/`unique`/`stackable`/tags; clamp na materialização; CHECK `shared_pool_owner_required` (o `erase_owner` apaga antes de desvincular, então respeita o CHECK); `submit` e `get_store()` falham fechados fora do legacy (`RPG_RUNTIME_PROFILE`, o mesmo nome que o runtime usa); `HumanMessage` filtrado antes do `[-3:]`; mock bloqueado também pela telemetria; export LGPD com `shared_pool`; bestiário filtrado por região, até 100 entradas. |
| P2-3 | Parcial: `input_shingles` é zerado na promoção. Falta o grant por coluna (ver Pendências). |

### Achados novos

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R-1 | P1 | `workers/shared_pool_jobs.py` (`make_owner_values`) | Faz `select email, raw_user_meta_data from auth.users` pela conexão admin. Em staging e produção a conexão admin é o papel de login `rpg_runtime`, que **não tem acesso ao schema `auth`** (`20261015160000_runtime_login_role.sql:28-30`: o runtime só usa 3 funções SECURITY DEFINER). O lookup levanta `permission denied` e cai no `except` de `promote_due`: toda entrada com dono vira `failed`, o lease renova a cada 15 min e **nada é promovido em hosted**. É fail-closed (sem vazamento e sem custo de LLM, porque roda antes da avaliação), mas a feature fica inerte e o smoke §6 falharia. Os testes locais não pegam isso porque conectam como `postgres`. | Pegar o e-mail com `app.runtime_auth_email(owner)`, que já existe e já está concedida ao runtime. Para o nome de exibição, criar uma função SECURITY DEFINER nova (`app.runtime_auth_display_names(uuid) returns text[]`, `search_path` travado, revoke de public/anon/authenticated/rpg_api) na migração da 297, ou abrir mão do nome e documentar. Teste local: rodar `make_owner_values` com `set local role rpg_runtime`. |
| R-2 | P1 | `tests/test_spec297_generation.py:196` | `ruff format --check` acusa "1 file would be reformatted", e o CI (`ruff format --check .`) quebra. | `uv run ruff format tests/test_spec297_generation.py`. |
| R-3 | P2 | `services/shared_pool.py` (`admin_restore`) + CHECK `shared_pool_owner_required` | Restaurar uma entrada vetada ou aposentada cujo autor excluiu a conta (dono NULL) viola o CHECK e o comando falha. É fail-closed e coerente com o LGPD, mas a CLI devolve só um erro cru. | Na CLI, mensagem clara ("autor excluído; restauração indisponível"), ou permitir `promoted` direto via `restore --promoted`, se o dono quiser. |
| R-4 | P2 | `tests/test_account_lifecycle_financial_local.py:24`, `tests/test_account_lifecycle_worker_local.py` | Esses 5 testes `*_local` reaplicam a migração `account_lifecycle` sem `if not exists` e falham com `DuplicateTable` numa base que já tem as migrações (caso do :55322). Isso existe antes da 297 e os arquivos não foram tocados na branch, mas contradiz "o `infra/security_local` do repo inteiro passa". | Follow-up fora da 297: deixar os fixtures idempotentes (checar `to_regclass` como `install_lifecycle` já faz para `image_quotes`). |

### Pendente: bloqueia ou é follow-up?

- **Grant por coluna ou view sem `origin_*`/`input_shingles` para o `rpg_api`:** **follow-up, não
  bloqueia.** Depois da correção, `input_shingles` vem vazio nas linhas promovidas. O que sobra
  legível de outros tenants é `origin_owner_id`/`origin_game_id` (UUIDs opacos), só dentro do
  processo (nenhum caminho de API ou estado os copia; `materialize_npc` e
  `_pool_creature_template` usam a allowlist), e o RLS de `games` impede usar esses ids.
  Recomendo fechar antes de ligar `on` em produção (não precisa ser antes do `shadow` no
  staging), com uma view `app.shared_pool_public` para o `rpg_api` ou revoke por coluna.
- **`pool_used: []` no save com a flag `off`:** **follow-up/aceito, não bloqueia.** É aditivo,
  o load de saves antigos e novos funciona nas duas direções (`_raw_to_state` usa `.get(..., [])`)
  e a mecânica não muda. Só registrar na spec que `off` é byte a byte no prompt e na mecânica,
  não no formato do save.

## Rodada final (delta `6533e258..6357f9b3`)

- **R-1 — fechado.** `make_owner_values` não lê mais `auth.users` direto; chama
  `app.runtime_auth_email(owner)`, que já existia, e `app.runtime_auth_display_names(owner)`,
  criada nesta rodada. A função nova:
  - é `SECURITY DEFINER`, com dono `postgres` e `search_path=pg_catalog`;
  - devolve **só** um `text[]` com os valores de 5 chaves de nome do `raw_user_meta_data`
    (com ≥ 3 caracteres). Nenhum outro campo de `auth.users` sai dela.
  - Privilégios conferidos no :55322 com `has_function_privilege`: `rpg_runtime` e `rpg_admin` têm
    execute (via `grant_runtime_access`, chamado no fim da migração, depois do `create`);
    `rpg_api`, `anon`, `authenticated` e `public` **não têm** (revoke explícito).
  - O teste local roda o lookup sob `set local role rpg_runtime` e passa.
  - Resta um risco aceito: qualquer código com a conexão de sistema consegue o nome de qualquer
    usuário, mas esse é o mesmo nível de confiança de `runtime_auth_email`.
- **R-2 — fechado.** `ruff format --check` nos 37 `.py` alterados: "37 files already formatted".
- O veredito passa a **`APPROVED_WITH_FOLLOWUPS`**. Os follow-ups estão em Pendências (nenhum é
  P0/P1).

## Correções aplicadas

Aplicadas pelo executor em 2026-10-24: P1-1, P1-2 (`ruff format` em `observability/events.py`; a remoção dos 2 eventos da SPEC-296 se resolve no rebase), P1-3, P1-4 (13 testes Postgres local passam, ver spec), P2-1, P2-2, P2-3 (parcial), P2-4, P2-5, P2-6, P2-7, P2-8, P2-9, P2-10. Detalhe na seção "Correções da revisão Sol" da spec.

## Pendências

- D7 (decisão do dono: criaturas do pool entram no sorteio de encontros depois da calibração)
  ainda não foi implementada. É follow-up com spec própria e gate de letalidade SPEC-285. Dono:
  coordenador.
- D3: cláusula nos termos de uso (texto legal do dono, alinhar com a SPEC-222).
- D8: revisão das tabelas de semente pelo dono antes de `on` no staging.
- Smoke real §6, que só passa depois da R-1.
- Grant por coluna ou view para o `rpg_api` (P2-3, 2ª parte): antes de `on` em produção.
- R-3, R-4 (P2).

## Comandos rodados

```text
git diff main...HEAD --stat → 41 arquivos, +5435/-388
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec297_*.py tests/test_npc_catalog_scope.py tests/test_npc_fallback.py tests/test_npc_camadas.py tests/test_npc_identity_grounding.py tests/test_bug_npc_ciclo_de_vida.py tests/test_conflito_autoria_bestiario.py tests/test_npc_memory.py tests/test_rls_runtime_config.py tests/test_spec192_staging_scripts.py tests/test_review_blockers_npc_preparation.py tests/test_log_event_registry.py → 244 testes: 235 passed, 9 skipped (infra_local sem RPG_TEST_DATABASE_URL), 0 failed
ruff format --check <35 .py alterados> → 1 file would be reformatted (observability/events.py)
EVENTS main vs branch → 206 → 224; removidos: ambient.fallback, combat_agent.fallback
docker ps → só há Supabase local de outro projeto (projeto-racha-spec-pack); não usado
# re-revisão 2026-10-24 (delta 6533e258)
RPG_TEST_DATABASE_URL=…:55322 pytest (sem -n) tests/test_spec297_*.py + npc/bestiário + rls_runtime_config + spec192 + log_event_registry + test_account_lifecycle*.py → 265 testes: 260 passed, 5 failed (só test_account_lifecycle_{financial,worker}_local: DuplicateTable no fixture, já existia antes da 297), 0 skipped; os 13 de test_spec297_shared_pool_local passam
ruff format --check <.py alterados> → 1 file would be reformatted (tests/test_spec297_generation.py)
ruff check <.py alterados> → All checks passed
grep auth.users em migrations/infra → rpg_runtime sem grant em auth (só app.runtime_auth_email/runtime_session_active/runtime_revoke_auth)
operations_kind_check → lista de 20261016121500 + 'pool_evaluation' (nada se perdeu)
# rodada final 2026-10-24 (delta 6357f9b3)
has_function_privilege(app.runtime_auth_display_names) → rpg_api/anon/authenticated/public=False; rpg_runtime/rpg_admin=True; prosecdef=True, search_path=pg_catalog, owner=postgres
RPG_TEST_DATABASE_URL=…:55322 pytest (sem -n) tests/test_spec297_*.py tests/test_npc_catalog_scope.py tests/test_log_event_registry.py tests/test_rls_runtime_config.py → 173 passed, 0 failed, 0 skipped
ruff format --check <37 .py alterados> → 37 files already formatted
```
