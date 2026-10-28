# SPEC-352 — Retrato de inimigo pago pelo jogador, com registro compartilhado

> **Status:** `approved` (o dono decidiu em 27/10 e deu autonomia até 08:30 de 28/10; decisões em §8)
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Depende de:** **SPEC-347 pousada na `main`** (bloqueante: o núcleo determinístico `services/creature_art.py`, o `retrato` na view, o catálogo `creature`/`creature_family`, `scripts/import_bestiary_art.py`, a flag `RPG_CREATURE_ART` e o `PortraitOffer` sem fiação do `TargetChip` só existem na branch `spec-347`). SPEC-326 (`done`, fluxo pago de arte: cotação, reserva, débito, worker). SPEC-297 (pool compartilhado, regra de HOLD). SPEC-222 (exclusão de conta). SPEC-340 (registro de flags).
> **Desbloqueia:** retrato de inimigo gerado de verdade no tabuleiro; spec futura de provedor aberto com LoRA de Valoria (D-347-J).
> **Origem:** transferida da SPEC-347 (R13.4, R13.6, a parte de cobrança de R13.10 e a fiação do botão), por decisão do coordenador em 28/10 (`specs/SPEC-347-cartas-smoke-layout.md` §9, branch `spec-347`).
> **EXECUTOR_MODEL:** `Sol` (writer persistente compartilhado + carteira + worker) · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`

---

## 1. Contexto & Objetivo

A SPEC-347 entregou o retrato do inimigo **sem geração**. Hoje o tabuleiro mostra a arte curada do bestiário (quando existe) ou o ícone da família, e o campo `gerar` vem sempre `null`. O dono quer que o jogador possa **pagar, se quiser**, para gerar o retrato de um inimigo que ainda não tem imagem. A imagem fica num **registro compartilhado**: no inimigo genérico, ela vale para o tipo e todos os jogadores a veem de graça; no inimigo importante, vale só para aquele indivíduo.

O dinheiro passa pelo mesmo caminho da arte dinâmica da SPEC-326: cotação, reserva na carteira, débito liquidado e a mesma política de falha. Muda pouco: um tipo novo, `monster`, e uma chave que vem do servidor. A parte nova e arriscada é o **writer persistente compartilhado** (`app.creature_portraits`). Ele garante uma cobrança só por chave, mesmo com dois jogadores confirmando ao mesmo tempo. Também guarda a imagem fora do escopo do dono, para ela sobreviver quando quem pagou apaga o jogo ou a conta.

Princípios: *mecânica é Python* (chave, preço e visibilidade são determinísticos; não há LLM novo) e *a arte curada vence* (com arte curada do bestiário, não há oferta e ela tem prioridade na exibição). Toda geração passa pela porta `ImageGenerator` (`infrastructure/ports.py:27`), para trocar de provedor depois.

### O que existe hoje (evidência; arquivos da branch `spec-347`, que é a base desta spec)

- **F1 — A chave e a resolução já existem e são determinísticas.** `is_important`/`portrait_key`/`portrait_for` em `services/creature_art.py:81-204`. `portrait_for` só oferece `gerar` com `mode()=="on"`, `quote_price` conhecido e sem arte própria nem `pending` (`:194-195`). O registro é um `Protocol` com um único `get` (`:53-54`), e só existe o `EmptyRegistry` (`:57-61`).
- **F2 — A view nunca passa `registry` nem `quote_price`.** `api.py:2796-2816` (`_enemy_portrait`) chama `portrait_for` sem os dois. Por isso `gerar` é sempre `null` e o botão fica oculto (SPEC-347 §9).
- **F3 — Bug latente de forma das variantes.** `_registry_src` lê `variants["thumbnail"]["url"]` (`creature_art.py:150-151`). O pipeline da 326, porém, gera as variantes `full` e `thumb` (`services/asset_pipeline.py:15`) e grava **object keys**, não URLs (`workers/dynamic_art_jobs.py:196-236`). Um registro real nunca acharia a imagem.
- **F4 — A cotação aceita só três tipos.** `ArtQuoteRequest.image_type: Literal["player","npc","scene"]` (`api.py:1935-1939`). Fora de `player`, ela exige uma oferta salva em `state["art_offers"]` (`api.py:4697-4710`). O inimigo não tem oferta.
- **F5 — Constraints do banco recusam o tipo novo.** `art_generations.trigger_kind in ('player_portrait','npc_first_appearance','arc_epic_moment')` e `subject_type in ('player','npc','scene')` (`supabase/migrations/20260819002404_blob_assets_chronicle.sql:66,68`). `image_quotes.image_type in ('player','npc','scene')` (`20261012160000_image_quotes.sql:19`). `assets.asset_kind` já aceita `monster` (`20260819002404…:6`), e `object_key` também (`asset_pipeline.py:45-52`).
- **F6 — Preço:** o perfil vem de `RPG_IMAGE_PRICE_PROFILE_SCENE` quando `subject_type=="scene"` e, nos outros casos, de `RPG_IMAGE_PRICE_PROFILE_PORTRAIT` (`services/image_quotes.py:62-72`). O teto é `quote_attempt_ceiling(max_provider_usd, version)` (`:84-86`). A cotação vale 5 min e é imutável (`:103`; trigger `image_quotes_immutable`, `20261012160000…:35-36`). O front mostra "Custo máximo: N Estilhas" (`web/src/components/ImageQuoteDialog.tsx:20-32`).
- **F7 — Confirmação e débito:** `POST /game/{id}/art/confirm` (`api.py:4731-4822`). Ela faz `_guard_image_effect`, roda `reserve_request` no estado e adia `repository.confirm` para dentro do commit (`:4790-4800`). O `_confirm` trava a cotação (`for update`), reserva na carteira, cria `art_generations` e enfileira `generate_dynamic_art` (`image_quotes.py:150-230`). O débito é liquidado em `DynamicArtRepository.complete` (`services/dynamic_art.py:275-311`).
- **F8 — Política de falha da 326 (não é "estorno sempre").** Falha **antes** do ticket libera a reserva (`release_pre_effect`). Depois de o provedor ser chamado, a reserva fica `uncertain` para conciliação (`image_quotes.py:331-375`, `hold_or_release`). Um job adiado além do TTL libera a reserva e fica com `failed/deferred_timeout` (`:291-329`).
- **F9 — Unicidade atual é por jogo.** `unique(game_id,timeline_epoch,trigger_kind,trigger_instance_id,profile_version)` (`20260819002404…:83`). Não existe nada que impeça dois jogos de pagar pela mesma chave `tipo:`.
- **F10 — O blob privado não serve como registro compartilhado.** A chave é `users/{owner}/games/{game}/…` (`asset_pipeline.py:55-58`). `SupabaseBlobStore.put` recusa chave fora de `users/{owner}/` (`infrastructure/supabase_blob.py:64-67`). O trigger de storage recusa, no bucket `rpg-dynamic`, objeto que não começa com `users/` (`20261013173632_account_lifecycle.sql:97-100`). A exclusão de conta apaga tudo sob `users/{owner}/` (`infrastructure/account_lifecycle.py:530-539`). Conclusão: sem cópia para fora do escopo do dono, o retrato some quando quem pagou apaga a conta.
- **F11 — O worker instancia o provedor direto:** `OpenAIImageGenerator(...)` em `workers/run_worker.py:87-89`. O job em si recebe `generator: ImageGenerator` (`workers/dynamic_art_jobs.py:152-163`). A porta é `infrastructure/ports.py:27-28`.
- **F12 — Não há brief de criatura.** `services/art_brief.py` tem `build_player_art_brief` (`:133`), `build_npc_art_brief` (`:201-239`) e `build_epic_art_brief` (`:253-300`). Este último referencia `player:approved_portrait` (`:295`). Nenhum deles serve para um retrato de criatura sem herói.
- **F13 — Já existe um padrão de tabela compartilhada.** `app.shared_pool` (`supabase/migrations/20261024100000_shared_pool.sql`) não é por dono, guarda `origin_owner_id`/`origin_game_id`, tem RLS de leitura "promovida ou minha", `rpg_api` sem `update` e imutabilidade de linha promovida (`:72-94`). A exclusão de conta desvincula as linhas promovidas e apaga as outras (`account_lifecycle.py:545-550`; `PostgresSharedPoolStore.erase_owner`).
- **F14 — O front já tem a oferta, mas sem fiação.** `PortraitOffer` com confirmação inline (`web/src/combat/TargetChip.tsx:38-58`), `onGenerate?` em `TargetChip`/`Arena` (`TargetChip.tsx:61-68,106`; `Arena.tsx:65-116`). A `CombateTab` não passa `onGenerate` (SPEC-347 §9). O cliente de cotação aceita `ImageQuote["type"]` = `player|npc|scene` (`web/src/api.ts:410-432`). O fluxo de arte do `App.tsx` é `openImageQuote` → `ImageQuoteDialog` → `confirmImageQuote` (`web/src/App.tsx:371-402`).
- **F15 — A geração paga já funciona em qualquer perfil com banco.** `_image_finance` exige `_database_profile()` (= perfil ≠ `legacy`, `api.py:303-304`) e `RPG_DYNAMIC_ART_ENABLED` (`api.py:4622-4636`). A SPEC-347 R13.4 escrevia "legacy/local não geram". O código, porém, deixa o perfil `local` (Postgres do Supabase local) rodar o fluxo pago, e os testes de dinheiro dependem dele (`tests/test_image_quotes_local.py:30-49`, `RPG_TEST_DATABASE_URL`).
- **F16 — A avaliação de qualidade muda o status da geração** para `rejected_quality` (`dynamic_art.py:126-142`; `POST /game/{id}/art/{generation_id}/quality`, `api.py:4905`).

## 2. Requisitos

Notação: `[F#]` remete à evidência acima. "Perfil com banco" = `local` ou `hosted` (`_database_profile()`). Tudo fica atrás de `RPG_CREATURE_ART=on` **e** `RPG_DYNAMIC_ART_ENABLED`. Com qualquer uma das duas desligada, o comportamento é idêntico ao da `main` pós-347.

### Registro de retratos (writer persistente novo)

- **R1 — Tabela `app.creature_portraits`** (migration nova; uma linha por `portrait_key`):
  - colunas: `portrait_key text primary key` (1–200 chars); `scope text check in ('tipo','unico','npc')`; `status text check in ('pending','ready','failed','retired')`; `generation_id uuid` (sem FK: a geração é privada e pode sumir com a conta); `visibility text check in ('shared','pool','game')`; `pool_entry_id text null`; `origin_owner_id uuid null`; `origin_game_id uuid null`; `store text check in ('shared','private') null`; `object_keys jsonb not null default '{}'` (`{"full": key, "thumb": key}`); `sha256 jsonb not null default '{}'`; `error_code text null`; `created_at`, `updated_at`, `version int`.
  - invariantes no banco: (a) `status='ready'` ⇒ `object_keys ? 'thumb'` e `store is not null`; (b) uma linha viva sem dono só existe com `status in ('ready','retired')` (padrão de `shared_pool_owner_required`, [F13]); (c) uma linha `ready` é imutável em `portrait_key/scope/visibility/object_keys/sha256` (trigger `guard_creature_portrait_immutable`). As exceções são a troca `store` `private`→`shared`, que reescreve `object_keys` uma única vez, e a transição para `retired`.
  - RLS forçada; `revoke all` de `public/anon/authenticated`. `rpg_api` só tem `select`, com a policy `status in ('ready','pending') and (visibility='shared' or origin_game_id in (jogos do owner corrente))`. Quem escreve é só `rpg_admin`/`rpg_runtime` (`select app.grant_runtime_access()`, como em `20261024100000_shared_pool.sql:139`).
  - trigger `account_write_fence` com `guard_deleted_account_write_origin` (reaproveitar a função de `20261024100000_shared_pool.sql:98-114`).
- **R2 — Canonical owner único: `services/creature_portraits.py`** (`PostgresPortraitRegistry`). Nenhum outro módulo faz `insert/update/delete` em `app.creature_portraits` (teste de grep, R15). Transições permitidas:
  - nenhuma linha → `pending` (só `claim`, dentro da transação de confirmação, R6);
  - `failed`/`retired` → `pending` (só `claim`);
  - `pending` → `ready` (só `mark_ready`, pelo worker, na mesma transação de `DynamicArtRepository.complete`);
  - `pending` → `failed` (só `mark_failed`, pelos caminhos de falha da 326, R8);
  - `ready` → `retired` (só a ferramenta de operador, R13).
  - Esse registro de ownership é entregue ao coordenador no hand-back. O subagente não edita `project_index/`.
- **R3 — Status efetivo:** uma linha `pending` cuja geração está em `failed*`, `refused`, `superseded` ou não existe mais conta como `failed` para cotação e `claim`. A conferência é feita por join com `app.art_generations` em `system_scope`. Assim uma geração morta nunca trava a chave para sempre.
- **R4 — Visibilidade efetiva (R13.5 da 347), calculada na leitura:**
  - `visibility='shared'`: genérico de criatura do bestiário (`tipo:{bestiary_id}`, `tipo:gen:*`) e `npc:{entity_id}`. Para `npc:`, a view só mostra se o NPC for `known_by_player` no jogo que lê (como `services/art_triggers.py`/`visual_catalog._eligible_npcs`, `services/visual_catalog.py:117-125`).
  - `visibility='pool'`: `tipo:bst:{entry}` e `unico:bst:{entry}:*`. Fica visível a todos só quando `app.shared_pool.status='promoted'` para `pool_entry_id`; nos outros casos, só ao `origin_game_id`. Com `rejected`/`vetoed`, nunca aparece a outro jogo.
  - `visibility='game'`: `unico:{game_id}:*`. Só para o `origin_game_id`.
  - Um jogo que não vê a linha recebe o mesmo resultado de "sem linha". O `claim`, porém, continua respeitando a unicidade, e a chave `unico:{game}` não colide entre jogos por construção.

### Cotação e confirmação (`image_type="monster"`)

- **R5 — Cotação** `POST /game/{id}/art/quote` com `{"image_type": "monster", "enemy_id": "<id da instância>"}`:
  - `ArtQuoteRequest` ganha `enemy_id: str | None` (1–128 chars). `image_type` aceita `"monster"`. Com `monster`, `offer_id` e `reformulation` dão 422.
  - Com `RPG_CREATURE_ART != on`: 404 `creature_art_disabled`.
  - O inimigo precisa estar no conflito atual, vivo e visível na view (`_combat_block`). Se não estiver: 422 `enemy_not_in_conflict`.
  - O servidor recalcula `portrait_key` com o mesmo `_enemy_portrait`/`portrait_key` da view [F1] e nunca aceita a chave do cliente (com `extra="forbid"`, um campo `portrait_key` no corpo dá 422).
  - Com arte curada que já resolve a chave (genérico: `creature` da criatura; importante `npc:`: `visual_for("npc", …)`): 409 `creature_portrait_curated`. A arte curada tem prioridade (D-352-6).
  - Com status efetivo (R3) `pending`/`ready` visível ao jogo: 409 `creature_portrait_exists`, **sem** gravar cotação.
  - Nos outros casos, cria `ArtGenerationRequest("creature_portrait", portrait_key, "monster", portrait_key, None, request_key)` e um brief novo, `build_creature_art_brief` (R9). Usa o mesmo `repository.issue` [F7] com o perfil de preço de retrato (`RPG_IMAGE_PRICE_PROFILE_PORTRAIT`, [F6]: `monster` não é `scene`) e o mesmo `_guard_image_effect` (kill switch `IMAGE` → 503; preço vencido → 503).
  - A resposta é a de `public_quote` com `type: "monster"`. Nenhum campo novo expõe a chave, o dono de origem ou o brief.
- **R6 — Confirmação** pelo mesmo `POST /game/{id}/art/confirm` [F7]. Para `quote.image_type == "monster"`:
  - Antes de `_begin_state_mutation`, a API refaz a checagem rápida de R5. Se a chave já ficou `pending`/`ready`, responde 409 `creature_portrait_in_progress` sem reserva.
  - Dentro de `ImageQuoteRepository._confirm`, **antes** de `wallet.reserve`, chama `PostgresPortraitRegistry.claim(connection, portrait_key, scope, visibility, pool_entry_id, origin_owner_id, origin_game_id, generation_id)`. Ele faz `insert … on conflict (portrait_key) do update set status='pending', … where <status efetivo é failed/retired> returning *`. Sem linha devolvida, levanta `CreaturePortraitTaken` (subclasse de `Conflict`): a transação inteira é revertida, sem reserva e sem débito, e a API responde 409 `creature_portrait_in_progress`. A cotação imutável apenas expira.
  - A confirmação continua idempotente pela `quote_id`. Um replay com geração existente devolve o `prior` como hoje (`api.py:4749-4762`).
  - `reserve_request` (`services/art_triggers.py:52-105`) aceita `creature_portrait` sem orçamento de arco. Ele não entra em `NPC_LIMIT_PER_ARC` nem no épico, e o dedupe do ledger vale por `(trigger_kind, portrait_key, None)` no jogo.
- **R7 — Concorrência:** duas confirmações simultâneas de dois donos diferentes na mesma chave `tipo:` produzem **exatamente 1** reserva e 1 job. A outra recebe 409 `creature_portrait_in_progress`, e o saldo dela não muda. A chave primária é o árbitro: não há lock em Python.
- **R8 — Fim da geração:**
  - **Sucesso:** o worker grava as variantes privadas (como hoje) e depois copia `full`/`thumb` para o store compartilhado (R10). `DynamicArtRepository.complete` chama `mark_ready` na mesma transação, com `store='shared'` e as chaves compartilhadas.
  - Se a cópia compartilhada falhar, a geração **não** falha (o jogador já pagou): `mark_ready` grava `store='private'` com as chaves privadas e enfileira o job idempotente `copy_creature_portrait`, que promove para `shared` depois.
  - **Falha:** `hold_or_release`, `release_if_deferred_too_long` e `fail(…, retryable=False)` chamam `mark_failed` na mesma transação. O dinheiro segue **exatamente** a política da 326 [F8]: falha antes do ticket libera a reserva; falha depois do ticket deixa `uncertain` para conciliação. Isso fica escrito na copy (R12), sem prometer "estorno" automático.
- **R9 — Brief de criatura** `build_creature_art_brief(enemy, *, important: bool, npc: dict | None) -> ArtBrief` em `services/art_brief.py`:
  - usa o estilo global de Valoria (`profile["global_style"]`) e um formato novo, `formats.creature_portrait` (retrato quadrado/vertical do mesmo `size` do perfil de retrato, para casar com o `image_price_profiles.size`, [F6]), em `data/dynamic_art_profiles.json`;
  - `reference_asset_ids = []` (nunca `player:approved_portrait`, [F12]);
  - **genérico:** só o nome do bestiário e a `description` do bestiário (`data/bestiary.json` por `normalize_bestiary_id`, ou o documento do pool quando `tipo:bst:`), com `sanitize_visual_text` e limite de 300;
  - **importante:** também o nome e a `description`/`appearance` do indivíduo (instância ou NPC via `build_npc_art_brief`, [F12]), sem `secret`/`hidden` (`exclusions += "no secret unrevealed traits"`);
  - **nunca** texto livre do jogador (teste: um `input_text` do turno não aparece em `render_image_prompt`).
- **R10 — Store compartilhado:**
  - `InfrastructureRuntime` ganha `shared_blob_store: BlobStore | None` (`infrastructure/runtime.py:673-679`):
    - `supabase` → `SupabaseBlobStore(bucket="rpg-shared-art", shared=True)`, que aceita **só** chaves `shared/creatures/…` e não faz checagem de dono;
    - `file` → `FileBlobStore(root/"shared")`;
    - `s3` → mesmo bucket, prefixo `shared/`.
  - A chave vem de `asset_pipeline.shared_object_key(portrait_key, asset_id, variant, sha256)` → `shared/creatures/{safe_entity_id(hash12(portrait_key))}/{asset_id}.{variant}.{sha12}.webp`. A chave do bucket usa um **hash** da `portrait_key`, para não expor o `game_id` de `unico:{game}`.
  - Migration: bucket privado `rpg-shared-art` (padrão de `20260820113242_dynamic_storage_bucket_rls.sql:4`), só `service_role`, sem policy para clientes.
- **R11 — View:** `_enemy_portrait` (`api.py:2796-2816`) passa a receber:
  - `registry`: `PostgresPortraitRegistry` no perfil com banco, `EmptyRegistry` no `legacy`, com uma leitura em lote por resposta (`get_many(keys, game_id)`, uma query por turno, nunca uma por inimigo);
  - `quote_price`: preço de exibição em **Estilhas inteiras** (teto da cotação arredondado para cima, a mesma conta de `shards()` do front), lido por `ImageQuoteRepository.peek_ceiling("monster")` **sem** inserir cotação e cacheado por processo por 60 s. Sem perfil de preço válido, fica `None` e `gerar` não aparece.
  - `_registry_src` é corrigido [F3]: lê `object_keys["thumb"]` e devolve uma **URL assinada** (`signed_url(key, 3600)` no store da linha), com cache por processo de até 50 min por object key. A view nunca expõe a object key crua.
  - Com o perfil `legacy`, ou sem `RPG_DYNAMIC_ART_ENABLED`, `gerar` fica sempre `null` (a 347 continua igual).
- **R12 — Front (fiação):**
  - `CombateTab` passa `onGenerate` para a `Arena` só quando o modo é `on` e o jogo não está `busy` (`genDisabled` já existe, [F14]).
  - "Gerar" na confirmação inline (`PortraitOffer`) → `requestImageQuote(gameId, "monster", false, undefined, enemyId)`.
    - Se `shards(quote.credits_milli) <= retrato.gerar.preco_estilhas`, chama `confirmPlayerArt` direto: a confirmação inline já foi o consentimento do jogador, com o preço mostrado, sem segundo modal.
    - Se a cotação vier **maior** (o câmbio mudou), abre o `ImageQuoteDialog` existente com o preço real e o aviso de compartilhamento. Nunca debita acima do que o jogador viu.
  - `api.ts`: `ImageQuote["type"]` inclui `"monster"`, e `requestImageQuote` aceita `enemyId?` (só enviado com `monster`).
  - Respostas: sucesso → banner "Retrato encomendado. O saldo foi reservado." + atualização do saldo (como `App.tsx:396-398`). 409 `creature_portrait_in_progress`/`exists` → banner informativo "Outro jogador já está gerando este retrato. Ele aparece em breve, sem custo." (copy da 347 §8) e nada é cobrado. 402 → "Estilhas insuficientes." 503 → "Geração de imagem indisponível agora."
  - O retrato passa de `gerando` a `pronto` na próxima resposta de turno (a view relê o registro). Não há polling novo.
  - Copy da confirmação (da 347 §8; acrescentar a linha de risco): genérico "Gerar o retrato de {nome} por até {preço} Estilhas? A imagem fica no bestiário e outros jogadores a verão."; importante "… A imagem é só deste {nome}.". Em ambos, abaixo, a linha pequena "Se a geração falhar antes de começar, o saldo é liberado."
- **R13 — Retirada pelo operador:** `scripts/retire_creature_portrait.py <portrait_key> --reason "<texto>"` (só `rpg_admin`) passa `ready` → `retired`. Também apaga os objetos compartilhados e libera a chave para nova cotação. Ele existe para moderar uma imagem compartilhada ruim ou inadequada. Não há UI.
- **R14 — Ciclo de vida:**
  - **Exclusão de conta** (`account_lifecycle.py:540-550`): `PostgresPortraitRegistry.erase_owner(db, owner)`.
    - Linhas `visibility='game'` do dono: apagadas, com os objetos compartilhados.
    - Linhas `pending` do dono: `failed`.
    - Linhas `ready` `shared`/`pool` promovidas: `origin_owner_id=null, origin_game_id=null` (desvínculo, como D3 do pool).
    - Linhas `ready` com `store='private'` (cópia ainda não feita): `failed`, porque os blobs privados vão ser apagados.
  - **Exportação de conta** (`account_lifecycle.py:396-400`): inclui as linhas com `origin_owner_id = owner` (só chave, escopo, status e datas; sem object keys).
  - **Apagar um jogo:** as linhas `visibility='game'` daquele `origin_game_id` são apagadas no mesmo caminho que hoje apaga os dados do jogo no perfil com banco. As outras ficam.
- **R15 — Avaliação de qualidade:** `POST /game/{id}/art/{generation_id}/quality` com uma geração `monster` dá 422 `quality_not_applicable`. O retrato compartilhado não pode ser derrubado por um jogador; a moderação é R13 [F16].
- **R16 — Provedor trocável (D-347-J):** `services/creature_portraits.py`, `services/creature_art.py` e o brief não importam `infrastructure.openai_images` (teste de import). O ramo `monster` do worker usa o `generator: ImageGenerator` que já é injetado [F11]. Trocar o provedor do worker (`run_worker.py:87-89`) fica para a spec do LoRA.

### Fora de escopo

- Treinar ou integrar um modelo aberto/LoRA, ou fazer uma fábrica de provedores configurável (só a porta, R16).
- Geração automática de retrato de inimigo, ou oferta fora do tabuleiro de combate (bestiário, codex, crônica).
- Retrato do jogador e dos aliados no tabuleiro; reformulação de retrato de inimigo; mais de uma variante artística por chave.
- Perfil `legacy` gerando imagem (continua com catálogo e marcador).
- UI de moderação; reembolso manual; mudar a política de falha da 326.
- Gerar as imagens do bestiário (projeto paralelo do dono; entram por `scripts/import_bestiary_art.py`, da 347).
- Campo de missão no inimigo (D-347-I segue valendo).
- Mudar preço, perfil de preço ou rate card. A cotação usa o perfil de retrato vigente.

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `supabase/migrations/2026102812xxxx_creature_portraits.sql` | R1, R10: tabela, triggers, RLS, constraints ampliadas (`trigger_kind += 'creature_portrait'`, `subject_type += 'monster'`, `image_quotes.image_type += 'monster'`), bucket `rpg-shared-art`, `job kind` do `copy_creature_portrait` se `app.jobs` restringir o kind. Idempotente. Timestamp maior que a última migration na `main` no momento do pouso. |
| `services/creature_portraits.py` | Canonical owner (R2): `PostgresPortraitRegistry` (`get`, `get_many`, `claim`, `mark_ready`, `mark_failed`, `promote_store`, `retire`, `erase_owner`, `delete_game`), `effective_status`, `effective_visible`, `visibility_for(key)`, `CreaturePortraitTaken`. |
| `scripts/retire_creature_portrait.py` | R13. |
| `tests/test_spec352_creature_portraits.py` | Unidade e contrato offline (registro fake em memória com a mesma semântica). |
| `tests/test_spec352_creature_portraits_db.py` | Postgres real (`RPG_TEST_DATABASE_URL`, padrão de `tests/test_image_quotes_local.py:30-49`): round-trip, RLS, concorrência, falha, ciclo de vida. |
| `tests/test_spec352_creature_quote_api.py` | API: cotação/confirmação `monster` com o banco de teste. |
| `web/e2e/spec352-retrato-pago.spec.ts` | Playwright 390/1440 com fixture de rede. |

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `api.py` | `ArtQuoteRequest` (`:1935`): `image_type` + `"monster"`, `enemy_id`; ramo `monster` em `create_image_quote` (`:4665-4728`) e checagem rápida em `confirm_player_art` (`:4731-4822`); 409/422 novos; `_enemy_portrait` (`:2796`) com `registry` + `quote_price`; recusa de `quality` para `monster` (`:4905`). |
| `services/creature_art.py` | `_registry_src` lê `object_keys.thumb` e devolve URL via callback `sign(store, key)` injetado (sem importar runtime); `PortraitRegistry` ganha `get_many`. A ordem de `portrait_for` não muda. |
| `services/image_quotes.py` | `_confirm`: `claim` antes de `wallet.reserve` quando `quote["image_type"]=="monster"`; `hold_or_release`/`release_if_deferred_too_long` → `mark_failed`; `peek_ceiling(image_type)` só de leitura. |
| `services/dynamic_art.py` | `complete` → `mark_ready` para `subject_type=='monster'`; `fail(retryable=False)` → `mark_failed`. |
| `services/art_triggers.py` | `reserve_request` aceita `creature_portrait` sem orçamento de arco. |
| `services/art_brief.py` | `build_creature_art_brief` (R9). |
| `data/dynamic_art_profiles.json` | `formats.creature_portrait` + `creature_composition` (curado; sem mudar `profile_version` dos outros formatos). |
| `services/asset_pipeline.py` | `shared_object_key(...)`. |
| `workers/dynamic_art_jobs.py` | Ramo `monster`: depois das variantes privadas, copia para `shared_blob_store`; devolve `shared_variants` ou `shared_copy_failed`. |
| `workers/run_worker.py` | Passa `runtime.shared_blob_store`; handler `copy_creature_portrait` (idempotente). |
| `infrastructure/runtime.py`, `infrastructure/supabase_blob.py`, `infrastructure/local_adapters.py` | `shared_blob_store` (R10); `SupabaseBlobStore(shared=True)` aceita só `shared/creatures/`. |
| `infrastructure/account_lifecycle.py` | Exportação e `erase_owner` (R14). |
| caminho de exclusão de jogo no perfil com banco | `delete_game(origin_game_id)` (R14). O executor localiza o caminho por `Grep "delete from app.games"`. |
| `web/src/api.ts`, `web/src/combat/CombateTab.tsx`, `web/src/combat/TargetChip.tsx`, `web/src/App.tsx` | R12. |

### Schemas e assinaturas

```python
# services/creature_portraits.py
PortraitStatus = Literal["pending", "ready", "failed", "retired"]
PortraitVisibility = Literal["shared", "pool", "game"]

class CreaturePortraitTaken(Conflict): ...

def visibility_for(portrait_key: str) -> PortraitVisibility:
    # "tipo:bst:"/"unico:bst:" -> "pool"; "unico:" (outros) -> "game"; "tipo:"/"npc:" -> "shared"

class PostgresPortraitRegistry:
    def __init__(self, pool) -> None: ...
    def get(self, portrait_key: str) -> dict | None: ...                       # Protocol da 347
    def get_many(self, keys: Sequence[str], *, game_id: str) -> dict[str, dict]: ...  # já filtrado por R3/R4
    def claim(self, connection, *, portrait_key: str, scope: str, pool_entry_id: str | None,
              origin_owner_id: UUID, origin_game_id: UUID, generation_id: UUID) -> dict: ...  # raises CreaturePortraitTaken
    def mark_ready(self, connection, *, generation_id: UUID, store: Literal["shared","private"],
                   object_keys: dict[str, str], sha256: dict[str, str]) -> None: ...
    def mark_failed(self, connection, *, generation_id: UUID, error_code: str) -> None: ...
    def promote_store(self, *, portrait_key: str, object_keys: dict[str, str]) -> bool: ...
    def retire(self, *, portrait_key: str, reason: str) -> list[str]: ...      # devolve object keys a apagar
    @staticmethod
    def erase_owner(db, owner: UUID) -> list[str]: ...
    @staticmethod
    def delete_game(db, game_id: UUID) -> list[str]: ...

# services/image_quotes.py
def peek_ceiling(self, image_type: str) -> int | None: ...   # credits_milli; None sem perfil válido

# services/asset_pipeline.py
def shared_object_key(*, portrait_key: str, asset_id: UUID, variant: str, sha256: str) -> str: ...

# api.py
class ArtQuoteRequest(BaseModel):
    model_config = {"extra": "forbid"}
    image_type: Literal["player", "npc", "scene", "monster"] = "player"
    offer_id: uuid.UUID | None = None
    reformulation: bool = False
    enemy_id: str | None = Field(default=None, min_length=1, max_length=128)
```

```ts
// web/src/api.ts
export interface ImageQuote { /* … */ type: "player" | "npc" | "scene" | "monster"; }
export const requestImageQuote = (gameId: string, imageType: ImageQuote["type"] = "player",
  reformulation = false, offerId?: string, enemyId?: string) => /* body inclui enemy_id só com monster */;
```

### Formatos (exemplo com IDs reais)

Linha de `app.creature_portraits` depois de um Goblin genérico pago:

```json
{"portrait_key": "tipo:enemy_goblin", "scope": "tipo", "status": "ready", "visibility": "shared",
 "pool_entry_id": null, "origin_owner_id": "…", "origin_game_id": "…", "store": "shared",
 "object_keys": {"full": "shared/creatures/3f9a1c0b7d2e/…full.ab12cd34ef56.webp",
                 "thumb": "shared/creatures/3f9a1c0b7d2e/…thumb.0011aabbccdd.webp"},
 "generation_id": "…", "error_code": null}
```

`retrato` na view de outro jogo (outro dono), sem `gerar`:

```json
{"estado": "pronto", "src": "https://…/storage/v1/object/sign/rpg-shared-art/shared/creatures/…?token=…",
 "familia": "covarde_oportunista", "icone": "exit", "alt": "Retrato de Goblin", "proprio": false, "gerar": null}
```

Erros públicos novos: `creature_art_disabled` (404), `enemy_not_in_conflict` (422), `creature_portrait_curated` (409), `creature_portrait_exists` (409), `creature_portrait_in_progress` (409), `quality_not_applicable` (422).

## 4. Plano passo a passo

Subagente: só os testes do escopo, `-n 2` no máximo. Os testes `_db` exigem `RPG_TEST_DATABASE_URL` (Supabase local, porta 55322). Sem a URL eles fazem `skip`, e isso **não** vale como verde para esta spec (critério de aceite).

### Etapa 0 — base e ownership

1. Confirmar que a SPEC-347 está na `main`. Se não estiver, parar e devolver `BLOQUEADO: 347`.
2. Escrever a entrada de ownership proposta (`app.creature_portraits` → `services/creature_portraits.py`; invariantes R1/R2; readers `api.py`, `services/creature_art.py`; writers indiretos `services/image_quotes.py`, `services/dynamic_art.py`, `infrastructure/account_lifecycle.py`, `scripts/retire_creature_portrait.py`, todos via o owner). Ela vai no hand-back para o coordenador integrar em `project_index/state_ownership.yaml`.

### Etapa 1 — chave/variantes e visibilidade (offline)

1. **Testes** (`tests/test_spec352_creature_portraits.py`):
   - `test_visibility_for_keys`: `tipo:enemy_goblin`→shared, `tipo:gen:bandido`→shared, `tipo:bst:abc12345`→pool, `unico:bst:abc12345:grishnak`→pool, `unico:<gid>:goblin:grishnak`→game, `npc:npc_xyz`→shared;
   - `test_registry_src_reads_thumb_key` (regressão F3): linha `ready` com `object_keys.thumb` → `src` = URL do callback `sign`, nunca a key crua;
   - `test_effective_status_dead_generation`: `pending` + geração `failed` → `failed`;
   - `test_visible_pool_hold_only_origin`, `test_visible_pool_promoted_all`, `test_visible_pool_rejected_never_other`, `test_visible_unico_game_only_origin`, `test_npc_requires_known_by_player`;
   - `test_curated_beats_registry`: arte `creature` curada + linha `ready` → `src` curada e `gerar` null.
2. **Implementação:** `visibility_for`, `effective_*`, registro fake; correção de `_registry_src` com callback `sign`.

### Etapa 2 — migration e registro real

1. **Testes** (`tests/test_spec352_creature_portraits_db.py`):
   - `test_migration_idempotent` (aplicar 2×);
   - `test_roundtrip` (claim → get → mark_ready → get_many);
   - `test_ready_immutable` (update de `object_keys` em `ready` com `store='shared'` → erro);
   - `test_rpg_api_cannot_write` (insert/update como `rpg_api` → erro de RLS/grant);
   - `test_rpg_api_reads_shared_and_own_game_only`;
   - `test_claim_conflict_raises_taken`;
   - `test_claim_after_failed_ok`;
   - `test_constraints_accept_monster` (insert em `image_quotes`/`art_generations` com `monster`/`creature_portrait`);
   - `test_account_fence_blocks_deleted_owner`.
2. **Implementação:** migration + `PostgresPortraitRegistry`.

### Etapa 3 — cotação e confirmação

1. **Testes** (`tests/test_spec352_creature_quote_api.py`, banco de teste + `FakeImageGenerator`, `tests/fakes/fake_image_generator.py`):
   - `test_quote_recomputes_key_server_side` (corpo com `portrait_key` → 422; a chave gravada no `trigger` é a da view);
   - `test_quote_flag_off_404`;
   - `test_quote_enemy_not_in_conflict_422`;
   - `test_quote_curated_409`;
   - `test_quote_existing_pending_409_no_quote_row`;
   - `test_quote_kill_switch_503_no_row`;
   - `test_confirm_reserves_once_and_enqueues`;
   - `test_concurrent_confirms_one_debit`: duas threads, dois donos, dois `quote_id`, mesma chave `tipo:enemy_goblin` → 1 `wallet_reservations`, 1 job, a outra resposta é 409 `creature_portrait_in_progress`, saldo do segundo dono intacto;
   - `test_confirm_replay_idempotent`;
   - `test_important_keys_independent`: Grishnak pago não muda Ugruk nem o tipo;
   - `test_monster_brief_has_no_player_text_nor_player_ref`;
   - `test_reserve_request_creature_no_arc_budget`.
2. **Implementação:** R5, R6, R9; `reserve_request`; `peek_ceiling`.

### Etapa 4 — worker, falha e cópia compartilhada

1. **Testes** (mesmo arquivo `_db`):
   - `test_job_ready_marks_shared_and_settles` (`store='shared'`, débito liquidado, objetos em `shared/creatures/`);
   - `test_shared_copy_failure_keeps_generation_ready_private` + `test_copy_job_promotes_store`;
   - `test_pre_dispatch_failure_releases_and_marks_failed`;
   - `test_post_dispatch_failure_uncertain_and_marks_failed`;
   - `test_deferred_timeout_marks_failed`;
   - `test_failed_allows_new_quote`;
   - `test_second_game_sees_ready_without_offer_or_debit`.
2. **Implementação:** R8, R10; handler `copy_creature_portrait`.

### Etapa 5 — view, ciclo de vida, qualidade, retirada

1. **Testes:**
   - `test_view_offer_present_when_eligible` (`gerar.preco_estilhas` = `ceil(peek_ceiling/1000)`);
   - `test_view_one_registry_query_per_turn` (contador no fake);
   - `test_view_legacy_never_offers`;
   - `test_view_no_raw_object_key`;
   - `test_erase_owner_unlinks_shared_deletes_game_rows`;
   - `test_erase_owner_private_store_becomes_failed`;
   - `test_export_lists_origin_rows_without_keys`;
   - `test_delete_game_removes_game_rows_only`;
   - `test_quality_monster_422`;
   - `test_retire_frees_key_and_deletes_objects`;
   - `test_only_owner_module_writes` (grep: nenhum `insert into app.creature_portraits|update app.creature_portraits|delete from app.creature_portraits` fora de `services/creature_portraits.py` e da migration);
   - `test_no_provider_import` (R16).
2. **Implementação:** R11, R13, R14, R15.

### Etapa 6 — front

1. **Testes:**
   - `node --test` (SSR) de `TargetChip`/`PortraitOffer`: "Gerar" chama `onGenerate(enemyId)` uma vez e "Agora não" não chama;
   - fluxo de `CombateTab` com `api` fake: cotação ≤ preço mostrado → confirma direto; cotação > preço → abre `ImageQuoteDialog` e não confirma; 409 → banner "Outro jogador…" e nenhum `confirm`;
   - Playwright `web/e2e/spec352-retrato-pago.spec.ts` a 390 e 1440, com fixture de rede: botão "Gerar retrato (N Estilhas)" ≥ 43,5 px; confirmação inline; requests `quote` e depois `confirm` conferidos; "Agora não" sem request; 409 sem `confirm`; depois do turno seguinte com `estado: "pronto"`, aparece a `<img>`. `--workers=1`.
2. **Implementação:** R12.

### Etapa 7 — verificação

`bash scripts/dev/py.sh -m pytest tests/test_spec352_*.py tests/test_spec347_creature_art.py tests/test_image_quotes_local.py -q -n 2` com `RPG_TEST_DATABASE_URL`. A suíte completa é do coordenador, no pouso.

## 5. Critérios de aceite

- [ ] SPEC-347 pousada antes do início (Etapa 0). (branch empilhada em `spec-347`; rebase na `main` é do coordenador)
- [ ] Ownership de `app.creature_portraits` entregue no hand-back e integrado pelo coordenador em `project_index/state_ownership.yaml` no pouso.
- [x] Migration idempotente; `rpg_api` sem escrita; linha `ready` imutável; fence de conta excluída (testes `_db` **executados**, não `skip`).
- [x] Nenhuma geração sem cotação confirmada (teste); chave calculada só no servidor (teste).
- [x] Concorrência: duas confirmações na mesma chave → 1 débito, 1 job, 409 para a outra, saldo intacto (teste `_db` executado).
- [x] Política de falha da 326 preservada (pré-ticket libera; pós-ticket `uncertain`) e a chave volta a aceitar cotação (testes).
- [x] Imagem copiada para `shared/creatures/` fora de `users/{owner}/`; quando a cópia falha, a geração fica pronta e o job de cópia promove depois (testes).
- [x] Outro jogo vê `pronto` sem `gerar` e sem débito; HOLD, rejeitada e `unico:{game}` não vazam (testes).
- [x] Arte curada vence e corta a oferta (teste).
- [x] Exclusão de conta, exportação e exclusão de jogo tratam o registro (testes).
- [x] Bug F3 corrigido com teste de regressão.
- [x] Sem import de provider nos módulos novos (teste); worker usa a porta `ImageGenerator`.
- [x] Front: confirmação única com o preço mostrado; cotação maior abre o diálogo; 409 sem cobrança (SSR + Playwright 390/1440).
- [x] `RPG_CREATURE_ART` (já em `config/flags.yaml`, 347) com `spec: SPEC-352` acrescentado à nota; gate de flags verde.
- [ ] `uv run pytest` verde (suíte completa offline, no pouso, pelo coordenador).
- [x] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo; teste de import garante que não há `get_llm` em `creature_portraits.py`).
- [ ] Saves antigos continuam carregando (o estado só ganha linhas novas no `art_generation_ledger`, com o formato de hoje).
- [ ] Smoke real de §6 executado no staging, com evidência em `docs/spec352/smoke-AAAA-MM-DD.md`.

## 6. Smoke test real (staging; custo real de imagem)

Pré-requisitos: staging com a migration aplicada pelo coordenador, `RPG_CREATURE_ART=on`, `RPG_DYNAMIC_ART_ENABLED=1`, perfil de preço de retrato válido e duas contas de teste com Estilhas. Teto: **3 gerações** no total.

1. Conta A, combate com um Goblin genérico sem arte curada: o chip mostra o marcador + "Gerar retrato (N Estilhas)". "Agora não" → nenhum request de cotação (DevTools) e saldo igual.
2. "Gerar" → `quote` (200, `type: "monster"`) → `confirm` (200, `pending`). O saldo mostra a reserva. Em até ~2 min, o próximo turno mostra `pronto` nos chips de todos os Goblins da cena. O débito fica liquidado ≤ teto (`/account`).
3. Conta B, outro jogo, combate com Goblin: `pronto` direto, sem botão, saldo de B igual. A URL da imagem aponta para `rpg-shared-art`.
4. Conta A, inimigo importante (chefe ou nome próprio): a oferta diz "só deste {nome}". Gerar → a arte própria aparece só nele. Na conta B, o mesmo nome noutro jogo **não** mostra essa arte.
5. Concorrência manual: A e B abrem a confirmação da mesma criatura nova, e A confirma primeiro. B recebe "Outro jogador já está gerando…", sem reserva (saldo de B igual).
6. Registrar: requests/respostas (sem tokens), custo do provedor, latência até `pronto`, prints a 390 e 1440.

## 7. Riscos & compatibilidade

- **Saves:** nenhum campo novo no `GameState`. O `art_generation_ledger` ganha linhas `creature_portrait` com o formato atual. Um save antigo carrega igual.
- **Perfil `legacy`:** sem mudança (`EmptyRegistry`, `gerar` null).
- **Dinheiro:** a chave primária é o árbitro da concorrência, e `claim` roda **antes** da reserva, na mesma transação. Falhar no `claim` reverte tudo. O débito fica limitado ao teto da cotação (326). O preço exibido pode divergir da cotação por câmbio; nesse caso o diálogo da 326 reaparece (R12).
- **Chave travada:** uma geração morta é tratada pelo status efetivo (R3), e a geração `uncertain` vira `failed` no registro. Existe um risco residual de gerar duas imagens para a mesma chave se uma geração `uncertain` acabar tendo sucesso no provedor. A segunda é aceita como custo; a linha `ready` não é sobrescrita.
- **Privacidade:** a chave do bucket usa hash da `portrait_key` (não expõe `game_id`). O brief não leva texto do jogador. O desvínculo na exclusão de conta segue D3 do pool. Uma imagem compartilhada inadequada sai pela retirada do operador (R13).
- **Latência:** uma query de registro por turno, preço cacheado 60 s, URL assinada cacheada ~50 min. Não há LLM novo.
- **MockLLM/FallbackLLM:** não se aplica (sem `get_llm`). Os testes usam `FakeImageGenerator`.
- **Conflito com specs em voo:** `api.py` e `services/image_quotes.py` são quentes. Rebase no pouso. A 347 precisa ter pousado (Etapa 0).
- **Desvio da 347:** a 347 R13.4 dizia "legacy/local não geram". Esta spec deixa o perfil `local` gerar, porque o fluxo da 326 já roda nele e os testes de dinheiro dependem dele (D-352-7).

## 8. Decisões

**Do dono (27/10, transferidas da SPEC-347 D-347-B/D/G/J):**

- **D-352-1 — Opcional e pago pelo jogador.** "Gerar retrato (X Estilhas)?" com confirmação. Nada é gerado sem pedido; não há gatilho automático.
- **D-352-2 — Mesmo dinheiro da 326.** Cotação, reserva, débito e a política de falha da arte dinâmica, com o tipo novo `monster`.
- **D-352-3 — Registro compartilhado.** No genérico, a imagem vai para a chave do tipo e todos reaproveitam. No importante, vai para a chave própria.
- **D-352-4 — Uma cobrança por chave**, mesmo com concorrência.
- **D-352-5 — Provedor atrás de `ImageGenerator`.** O dono quer um LoRA open source depois; aqui é só a porta (R16).
- **D-352-6 — Arte curada do bestiário tem prioridade.** Na exibição, a curada vence o registro. Com curada, não há oferta (409 na cotação).

**Do autor da spec (técnicas, dentro da autonomia; o dono pode reverter):**

- **D-352-7 — Perfil `local` também gera** (qualquer perfil com banco), em vez de "só hosted" [F15]. Motivo: é o mesmo código da 326, e os testes de dinheiro precisam de Postgres real.
- **D-352-8 — Confirmação única.** O "Gerar" inline já é o consentimento quando a cotação real ≤ preço mostrado. Se a cotação vier maior, cai no diálogo da 326. A copy diz "até N Estilhas", porque o débito é limitado ao teto e pode sair menor.
- **D-352-9 — Cópia para bucket privado novo `rpg-shared-art`**, servido por URL assinada [F10]. Um bucket público seria mais barato em latência, mas exporia `unico:{game}` sem controle.
- **D-352-10 — Falha da geração libera a chave.** Ela não fica bloqueada, e outro jogador pode pagar de novo. O dinheiro de quem falhou segue a 326 (sem promessa de estorno automático depois de o provedor ser chamado).
- **D-352-11 — Sem avaliação de qualidade por jogador para `monster`.** A moderação é do operador (R13), para um jogador não derrubar a arte que outros veem.

**O que o dono ainda precisa decidir:** nada bloqueia a implementação. Antes do smoke de §6, o coordenador precisa aplicar a migration no staging e confirmar com o dono o teto de 3 gerações reais.

## 9. Implementação — decisões e desvios (executor, 28/10, dono em autonomia)

Branch `spec-352` sobre `spec-347`. Status segue `approved` (revisão independente pendente).

- **D-352-12 — `trigger_instance_id` leva a tentativa** (`{portrait_key}|{request_key}`; `subject_id` = a chave). Motivo: a unicidade
  `art_generations(game,epoch,trigger_kind,trigger_instance_id,profile_version)` [F9] impediria o MESMO jogo de recotar depois de uma
  falha (D-352-10). O árbitro da cobrança única é só `creature_portraits` (PK), não o ledger; o dedupe do ledger vira por tentativa.
- **D-352-13 — `erase_owner` APAGA** as linhas `pending`/`failed`/`ready+private` do dono (em vez de marcar `failed`): o CHECK
  `creature_portraits_owner_required` (R1b) proíbe linha viva sem dono, e o blob privado some junto. Efeito igual (chave livre).
  As `ready` compartilhadas são desvinculadas; as `visibility='game'` apagadas (objetos compartilhados saem por job).
- **D-352-14 — dois jobs novos**: `copy_creature_portrait` (R8, idempotente; enfileirado só quando a cópia falhou) e `purge_shared_art`
  (R14: objetos compartilhados das linhas `game` ao apagar jogo/conta; a exclusão de conta apaga direto via `shared_blobs`, best-effort).
- **Desvio da 347 (tests):** `tests/test_spec347_creature_art.py` mudou a forma das linhas do registro de teste para
  `object_keys.thumb` + `Reg.sign` (correção do bug F3; a forma `variants.thumbnail.url` nunca existiu num registro real).
- `PortraitRegistry` (Protocol) ganhou `sign` opcional; `portrait_for(..., sign=)`. Sem `sign`, linha `ready` não dá `src`.
- `RPG_CREATURE_ART` em `config/flags.yaml`: só a nota cita a SPEC-352 (o campo `spec:` segue `SPEC-347`, é escalar).
- `_public_art_refs` (resposta de `/art/confirm`) NÃO lista `monster` (a chave `unico:{game}` não vai ao cliente).
- Preço exibido = `ceil(teto/1000)` Estilhas inteiras; o front só confirma direto se `BigInt(credits_milli) <= preço*1000`.
- Não feito aqui: smoke real §6 (staging, custo real) e prints a 390/1440 (a asserção de tamanho mínimo do botão está no e2e).
- Local: a migration foi aplicada ao Postgres local (55322) para os testes `_db`; o teste `test_account_lifecycle_worker_local.py` já
  falhava ali por `DuplicateTable` (reaplica migrations já presentes) — pré-existente, fora do escopo.
