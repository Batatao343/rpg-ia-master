# SPEC-389 — revisão sol (review)

> **Veredito:** `APPROVED` (rodada 3; rodadas 1 e 2: `CHANGES_REQUIRED`)
> **Revisor:** Opus / Sol · **Data:** 2026-11-04 · **Commit revisado:** `b4cefa2b`

## Escopo

`git diff main...spec-389` (d6f5aa85, 97b29be2, 308d6d09, b4cefa2b) conferido contra R1–R26 e D-389-1..8 (opção (a)).
Arquivos: `services/portrait_offer.py`, `services/portrait_offer_log.py`, `services/kill_switches.py`,
`services/creature_art.py`, `api.py` (delegação e `_conds`), `scripts/staging/portrait_offer_measure.py`,
`services/quest_log.py`, `agents/npc.py`, `services/round_log.py`, `services/combat_preview.py`, `web/src/{combat/deck.ts,
components/Hud.tsx,types.ts}`, `scripts/cards/draft.py`, `tests/fixtures/spec368_seed.py` e os testes novos.
R6/R7 (correção final de S7-1) ficam fora: dependem da medição no staging. Aqui julguei se a instrumentação basta para decidir.

**O que está correto:**
- **Kill switch (R4):** `MAX_STALE_SECONDS = 60` é constante (não é env), o TTL de 5 s não mudou, `kill_switches.load_failed` vai por `log_event` com `error_class` e `snapshot_age_s`, sem a mensagem da exceção (o teste F1 da 196 continua sem vazar o DSN), e a métrica ficou. Releitura falhando por 30 s mantém o snapshot; por 61 s, as chaves fail-closed caem. O switch se recupera em ≤ 5 s. Testes com relógio falso.
- **Cache de preço (R3):** `None`/0 de `peek_ceiling` grava `at=0.0, value=None`; a exceção continua fora do cache; preço válido fica 60 s.
- **Entrega pela rota NPC (R9):** é determinística. Verbo em 1ª pessoa de uma lista fechada, negação barrando, origem por `origin_name`/`origin_entity_id`, prova (`has_completion_proof`), no máximo 1 quest. `_completion_allowed` replica a regra de `world_validators._quest_proof` (`t == turn` e `turn - t < 3`) e lê o mesmo `event_log`. `pending_world_events` não tem reducer, então sobrescrever com `state + eventos` está certo. O merge com `fm_events` em `npc.py:1552` preserva a entrega.
- **Caminho do storyteller** (a pergunta do coordenador): **não é defeito.** `QUEST_COMPLETION_COOLDOWN` é documentado como "turnos entre conclusões propostas pelo LLM" (`services/world_validators.py:286`), e as fontes do motor (`ENGINE_SOURCES`, `:273-282`) pulam o gate de propósito (SPEC-223). O `sync_action_progress` exige 2 ações distintas no local alcançado, que é prova Python. Então não há pendência de código. Só a redação do §9 precisa mudar (P2-6).
- **R11–R15:** verificados. Conferi pela API (`TestClient`, 6 execuções) que `registro_rodada` traz `pressagio_frustrado` / "Presságio frustrado: Goblin" no `/game/state`. O Voto não mostra "próxima intenção" depois do desvio ou da resistência. A view traz `conditions[].id` com o nome gravado e `name == label`, e o save não muda. A Reação aparece na prosa via `fora_de_turno`. O HUD mostra "· Mão Sombria". Nenhum consumidor do front ou do Python compara `conditions[].name` com id (`TargetChip.tsx:92` e `Hud.tsx:573` usam `label ?? name`), e nenhum teste antigo compara essas estruturas por igualdade: 799 testes de regressão verdes.
- **Seeds:** `4 falha` (`esquiva_penalidade`, `ferimento_espacos` e `last_stand_resolved` são campos reais do motor), `12 hostil` (combate fechado, `HOSTIL_NARRATION` fixa, `FallbackLLM` no router → `hostility_fallback`), `smoke_body` com `ruptura` na jogada e `reaction_card_id` no nível de cima, e `13 reacao` com `guardar` (justificado no §9 item 5). A linha do `promote` sai com `--voz-pendente`.
- **Guardas:** o diff de integridade está vazio (`evals/`, `web/e2e/contracts`, `lint/sim/promote`, golden e equivalência da 330, `staging_flags.json`, `config/flags.yaml`). Tamanho: `api.py` diminuiu, `agents/npc.py` foi de 1605 para 1604 linhas, `conflict_orchestrator.py` não mudou, `round_log.py` tem 927 linhas. Ruff check e format limpos. Nenhum `with_structured_output` novo.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `scripts/staging/portrait_offer_measure.py:176-188` | O passo (1) da R5 não funciona contra o staging. O `admin_kill_switch.py` é chamado **sem** `--dsn-env RPG_STAGING_DB_URL --env-file .env.staging`, ao contrário de `incident_drill.py:31-37`, e cai em `get_runtime().game_store.pool` do perfil local. O resultado é `rc=…` ou o banco errado. Além disso, `splitlines()[-8:]` corta o JSON indentado: com as chaves em ordem alfabética, `image_generation` pode sumir do `list`, e o `audit` não é filtrado por `image_generation` (a R5 pede as 5 últimas linhas **dessa** chave, com hora). Sem a hora do `on`, a hipótese "amostra antes do `on`" não se decide | Passar `--dsn-env RPG_STAGING_DB_URL --env-file .env.staging` (os nomes como constantes, como no `incident_drill`). Fazer `json.loads` da saída: do `list`, guardar só `image_generation`; do `audit`, pedir `--limit 50` e guardar as 5 primeiras linhas com `key == "image_generation"`, só com `key`, `previous_enabled`, `enabled` e `created_at` (sem `actor_id`/`reason`). Falhar (rc≠0) se o snapshot não vier. Teste com `subprocess.run` falso |
| P1-2 | P1 | `scripts/staging/portrait_offer_measure.py:143-152,163-173,214-225` | A R7 ("endpoint e `game_id` de cada lado") não se decide. (a) `game` é sempre `short_hash(args.game_id)` e `endpoint` é a constante `"/game/state"`. O navegador carrega o jogo do `storage_state`, não o do argumento, então a hipótese "jogo diferente" (uma das 3 do §1.1) fica mascarada. O `offer_view` não traz `game_ref` porque `/game/state` não chama `_bind_corr`. (b) O controle positivo tem furo: se o navegador não fizer nenhum `/game/state` (`seen` vazio), a amostra não existe e o script sai 0 com 6/6 da API. Só falha quando a amostra existe sem log | (a) Hashear o `game_id` **real**: `body["game_id"]` da resposta (o `GameResponse` sempre tem), ou o parâmetro de `resp.url`. Gravar `endpoint` como o path de `resp.url`/`resp.request.url`, sem a query. (b) Em `run`, falhar se `len(api) != api_reads` ou `len(browser) != len(widths)`, ou se alguma amostra tiver `status != 200`. Testes: amostra com `game_id` diferente do argumento sai com o hash certo; navegador sem resposta faz o script falhar |
| P2-1 | P2 | `api.py:2947`, `api.py:3142` | `offer_view` sai em **toda** resposta, inclusive fora de combate. O `_combat_block` roda em todo `/game/state` e `/game/action` (`api.py:2315`), e `begin` é chamado mesmo com `alive == []`. Conferi: `_combat_block({"enemies": []})` emite `offered=0, omitted={}`. A R2 diz "cada `_combat_block` com inimigo vivo". O resultado é volume de log e ruído na medição | Abrir o tally só com `alive`, por exemplo `if alive: portrait_offer.begin(...)` no `_combat_block`, ou retornar cedo em `_portrait_registry`. O `finish()` já não emite sem tally. Teste: sem inimigo vivo, 0 `offer_view` |
| P2-2 | P2 | `services/portrait_offer.py:117-119` | `classify` põe `private_other_game` antes de `has_own_art`/`pending`. Como `_registry_src` anexa a razão a cada leitura (a chave própria **e** a do tipo), um inimigo comum com linha `private` de outro jogo no tipo **e** arte curada (`pending=False`, `has_own_art=True`) é contado como `private_other_game`. O mesmo vale para o importante com arte própria. É exatamente a contagem que decide a R6, então um falso positivo leva à correção errada. O teste de catálogo só exercita `classify` com listas montadas à mão, nunca o `portrait_for` real | Ordem: `fallback_enemy` → `has_own_art` → (`pending` com `private_other_game` presente → `private_other_game`; senão `pending`). Teste pelo `portrait_for` real com um registro falso: linha `private` de outro `origin_game_id` no tipo mais criatura curada dá `has_own_art`; só a linha `private` dá `private_other_game` |
| P2-3 | P2 | `services/portrait_offer.py:18` | Helper duplicado: `INSTANCE = uuid4().hex[:6]` repete `observability.boot.INSTANCE_REF`, que o `logging_setup.py:66-68` já põe em **toda** linha como `instance_ref`. A linha sai com dois ids de processo diferentes | `from observability.boot import INSTANCE_REF as INSTANCE` (mantém o campo `instance` da R2 com o mesmo valor de `instance_ref`). Ajustar o teste |
| P2-4 | P2 | `services/portrait_offer.py:96-104` × `api.py:2867-2875` | `art_cause` reimplementa as 3 condições de `_creature_art_live` (flag, perfil e `RPG_DYNAMIC_ART_ENABLED` com o mesmo conjunto de valores). As duas cópias podem divergir, e a causa reportada deixaria de bater com o portão real | `_creature_art_live()` passa a ser `portrait_offer.art_cause(_art.mode() == "on", _database_profile()) is None`, uma fonte só |
| P2-5 | P2 | `tests/test_spec387_seed.py:315-333` | A R18 pede que cada corpo, pelo `TestClient`, "produza o resultado prometido da variante". O teste só afirma o status 200 em 7 de 9 corpos. Conferi à mão que os corpos funcionam (`14 entrega` deixa `q368` `completed`; `2 frustrar` traz `pressagio_frustrado` no `/game/state`), mas o teste não os prende | Asserções por variante: `2 frustrar` → `registro_rodada` com `pressagio_frustrado`; `13 voto` → "muda de alvo" ou "resiste" e sem "próxima intenção"; `4 falha` → objetivo `falhou`; `12 hostil` → combate ativo; `14 entrega` → `q368` `completed`, sem `campaign.replan reason=region_change` (isso fecha também o "1 turno pelo grafo" da R8); `3 eco`/`13 condicao_carta` → o efeito da variante |
| P2-6 | P2 | `tests/test_quest_delivery_npc.py:98-111`; `specs/SPEC-389-cartas-smoke7-oferta-quest.md:421` | (a) A R9 pede que a entrega à origem feche "com recompensa e técnica pelo `event_processor`, como no teste da 387". O teste só confere `status == "completed"`. (b) O §9 item 1 deixa um "follow-up" aberto para o storyteller. Pela análise acima, é desenho da SPEC-223 (o cooldown vale para propostas do LLM), e não pendência: com a política de zero pendência, não pode ficar como follow-up solto | (a) Usar `reward_gold_planned` na quest do teste e afirmar o ouro concedido e a técnica, como no teste equivalente da 387. (b) Reescrever o §9 item 1: "o storyteller não precisa de mudança: fonte do motor fica fora do cooldown por desenho (`world_validators.py:273-286`, SPEC-223); a entrega pela rota NPC aplica o limite por exigência da R9" |
| P2-7 | P2 | `services/kill_switches.py:112-113` | A docstring de `_fail_closed_keys` diz "AND no good snapshot was ever loaded". Com a R4, as chaves também caem quando o snapshot passa de 60 s (`stale`). A docstring de `unreadable` (`:217-219`) também não cita o `stale` | Atualizar as duas docstrings: "ilegível sem snapshot bom, **ou** snapshot bom com mais de `MAX_STALE_SECONDS` (SPEC-389 R4)" |

**A instrumentação basta para decidir a causa?** O lado do servidor basta, com a P2-2 corrigida: causa fechada por inimigo, portão do switch com `switches_stale`/`switches_unreadable`/`env_off`, `price_absent` fora do cache, `switch_age_s`, `price_cached`, `art_live` e o `request_id` da correlação, que é o mesmo do header `X-Request-ID` (`api.py:632,669`). O `offer_view` é o controle positivo. O script de medição **não basta ainda**: sem a P1-1 não há a hora do `on`, e sem a P1-2 não se sabe que jogo cada lado leu. Nada vaza no código de produto: sem id de jogo, DSN ou nome no `offer_view`, e o `load_failed` só leva a classe da exceção. No script, o cookie vem de env e não é impresso. A P1-1 tira `actor_id`/`reason` do JSON gravado.

## Correções aplicadas

P1-1, P1-2, P2-1..P2-7 corrigidos com teste antes do código; ver o commit "fix(cards): SPEC-389 Sol review" e o final do §9 da spec.

## Pendências

Nenhuma aceita como follow-up (política de zero pendência). R6/R7 seguem condicionados à medição do coordenador depois da P1-1/P1-2.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_portrait_offer_causes.py tests/test_quest_delivery_npc.py tests/test_combat_text_smoke7.py tests/test_spec387_seed.py tests/test_size_budget.py tests/test_spec346_board_no_llm.py tests/test_spec196_finops.py → 158 passed, 1 skipped
bash scripts/dev/pt.sh (352 portraits/quote, 353_misc, 354, 355 provocacao/golpe/reacao/router, 363_*, 364_*, 367_*, 368_*, 387_*, 347, 197_daily_cap, 330 review, enemy_intent*, keywords, boot_policy) → 799 passed, 13 skipped
node --test web/tests/spec389-hud-subclass.test.mjs web/tests/spec389-round-frustrado.test.mjs → 2 pass
npx tsc -p web/tsconfig.json --noEmit → rc 0
ruff check / ruff format --check (17 .py do diff) → limpos
scripts/dev/dup_helpers.py --diff main...HEAD → só homônimos genéricos; duplicata real = INSTANCE (P2-3)
git diff main...spec-389 -- evals web/e2e/contracts scripts/cards/{lint,sim,promote}.py tests/spec330_* staging_flags.json config/flags.yaml → vazio
py.sh -c (_combat_block sem inimigos) → 1 offer_view emitido (P2-1)
py.sh -c (TestClient + smoke_body 14 entrega / 2 frustrar ×6) → q368 completed; pressagio_frustrado no /game/state 6/6
```

---

## Rodada 2 (2026-11-04) — commits `0765f494`, `a55af51f`

> **Veredito da rodada 2:** `CHANGES_REQUIRED` (2 P2; política de zero pendência) · **Commit revisado:** `a55af51f`

### Achados da rodada 1, um por um

| ID | Situação | Evidência |
|---|---|---|
| P1-1 | **resolvido** | `switches_snapshot` passa `--dsn-env RPG_STAGING_DB_URL --env-file .env.staging`, lê o JSON inteiro, guarda só `image_generation` e as 5 linhas do `audit` dessa chave (`key`, `previous_enabled`, `enabled`, `created_at`; sem `actor_id`/`reason`), e levanta erro com rc≠0 ou saída inválida. Testes com `run` falso |
| P1-2 | **resolvido** (com o P2-R2-1 abaixo) | `sample_from` faz o hash do `body["game_id"]` real e usa o path real (`urlsplit`). `count_problems` reprova contagem por lado ≠ N e status ≠ 200, e o `main` sai 1 |
| P2-1 | resolvido | `if enemies:` antes de `begin` (`api.py:2944`). Teste `test_no_offer_view_without_alive_enemy` |
| P2-2 | resolvido | Precedência `fallback_enemy` > `has_own_art` > `pending` (vira `private_other_game` se a linha `private` estiver presente). Teste pelo `portrait_for` real |
| P2-3 | resolvido | `INSTANCE = observability.boot.INSTANCE_REF` |
| P2-4 | resolvido | `_creature_art_live` = `art_cause(...) is None` |
| P2-5 | **parcial** | Asserção por variante em 8 de 9 corpos. A `14 entrega` deixou de passar pelo `TestClient` (ver P2-R2-2) |
| P2-6 | resolvido | O teste confere ouro (`QUEST_REWARD_GOLD`), `reward_card` e a técnica `neu1_*`. O §9 item 1 foi reescrito como "por desenho", sem follow-up |
| P2-7 | resolvido | Docstrings de `_fail_closed_keys` e `unreadable` citam o `stale` |

### Pontos pedidos pelo coordenador

- **`game_ref` no `offer_view`:** está OK quanto a vazamento. É `telemetry.pseudonym(game_id)`, um HMAC-SHA256 com `RPG_TELEMETRY_SECRET` truncado em 16 caracteres. É o mesmo esquema do `game_ref` que a correlação já põe nas outras linhas (`telemetry.py:85-87,289-293`): estável por jogo e sem o id cru. O teste afirma que não há `game_id` nos kwargs. Mas o campo não chega à tabela da medição (P2-R2-1).
- **`14 entrega` rodando o `npc_actor` direto:** o desvio do nó se justifica. Sob MockLLM, "Entrego…" vai para STORY, e o roteamento real fica para o smoke §6, passo 2. Ainda assim, a cobertura da R8 ficou **menor que na rodada 1**. A R8 pede explicitamente "rodar 1 turno pelo grafo (MockLLM) não gera `campaign.replan reason=region_change`". Na rodada 1 o `TestClient` rodava esse turno (só não conferia o resultado); agora nada passa pelo grafo com a seed `14 entrega`, e o replan só é coberto pela chamada unitária `_replan_reason`. Conferi à mão na rodada 1: o POST com o corpo da `14 entrega` responde 200 e fecha a `q368` pelo storyteller sob MockLLM. Então dá para ter as duas coberturas sem custo (P2-R2-2).
- **`ruff format --check .`:** 1849 arquivos já formatados. **`ruff check .`:** limpo. **`scripts/dev/size_budget.py`:** rc 0. `api.py` foi de 7973 para 7948 linhas, `agents/npc.py` de 1605 para 1604, e `conflict_orchestrator.py` tem 3049, sem mudança.
- **Regressão nova:** nenhuma no produto. 357 testes do escopo verdes.

### Achados novos

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-R2-1 | P2 | `scripts/staging/portrait_offer_measure.py:73-82` (`join_samples`) | O `offer_view` agora traz `game_ref`, mas `join_samples` copia só `instance/offered/omitted/switch_age_s/price_cached/art_live`. O `summary["games"]` lê `offer_view.get("game_ref")` e sai **sempre `"None"`**. Conferido: `join_samples([...], [{"request_id":"r","game_ref":"abc",...}])` dá `[('api','h','None')]`. O cruzamento servidor × cliente que a correção anuncia (§9 "offer_view ganhou game_ref") não acontece. Nenhum teste cobre `games` | Incluir `"game_ref"` na tupla de chaves de `join_samples`. Teste: um log com `game_ref="abc"` faz `summarize(...)["games"]` conter `"abc"` |
| P2-R2-2 | P2 | `tests/test_spec387_seed.py:325-326,360-379` | A `14 entrega` não passa mais pelo `TestClient`. A R8 (1 turno pelo grafo sem `region_change`) e a R18 (cada corpo pelo `TestClient`) ficam sem cobertura no grafo para essa variante | Manter `_assert_entrega_closes` (rota NPC) e **também** fazer o POST do corpo pelo `TestClient`, numa seed nova. Afirmar status 200, `q368` `completed` (qualquer rota sob mock) e nenhum replan por região: `campaign_plan.location == "Brekmar"` e `current_step` sem voltar a 0, ou nenhum `campaign.replan reason=region_change` no `caplog` |

### Comandos rodados (rodada 2)

```text
git diff cfa1158d..spec-389 → 9 arquivos (+325/−60)
bash scripts/dev/pt.sh (portrait_offer_causes, quest_delivery_npc, combat_text_smoke7, spec387_seed, size_budget, spec346_board_no_llm, spec196_finops, 352×2, 354_portrait, 363/364/367/387 portrait, 347, 197_daily_cap, boot_log) → 357 passed, 4 skipped
ruff format --check . → 1849 files already formatted · ruff check . → All checks passed
bash scripts/dev/py.sh scripts/dev/size_budget.py → rc 0
py.sh -c (join_samples com game_ref no log) → offer_view sem game_ref; games=[('api','h','None')] (P2-R2-1)
```

---

## Rodada 3 (2026-11-04) — commit `0b1893b5`

> **Veredito da rodada 3:** `APPROVED` · **Commit revisado:** `0b1893b5`. R6/R7 seguem condicionados à medição no staging
> (§6 passo 1, coordenador). Isso é critério de aceite da spec, não pendência da revisão de código.

### Achados da rodada 2

| ID | Situação | Evidência |
|---|---|---|
| P2-R2-1 | resolvido | `join_samples` copia `game_ref` (`portrait_offer_measure.py:77`). O teste `test_measure_join_copies_game_ref_to_summary` afirma `("api", "h", "abc123") in summary["games"]` |
| P2-R2-2 | resolvido | `test_entrega_body_through_the_graph_keeps_the_arc` faz o POST do corpo da `14 entrega` pelo `TestClient`, numa seed nova, e confere 200, `campaign_plan.location == "Brekmar"` e que `current_step` não volta. Junto com `_assert_entrega_closes` (nó `npc_actor` com a mesma frase e a mesma seed: `completed` e ouro pago), as partes de R8 e R18 que dá para provar offline estão cobertas |

### Pergunta do coordenador: fechamento aleatório da `14 entrega` pelo grafo

**Julgamento: (a) aceitável. Não é bug de produto.**

- **De onde vem a aleatoriedade:** é desenho do MockLLM, não do motor. O storyteller do mock propõe `quest_completed` com `random.random() < 0.5` para quests marcadas como `prova: ok` (`mock_llm.py:335-361`, "Fase 5: … ~50% das vezes propõe a CONCLUSÃO"). A seed `14 entrega` já tem prova antes da conversa: `location_reached` (turno 1) e `investigation` (turno 2), em `spec368_seed.py:411-413`, e a quest tem `location_id`. Então `has_completion_proof` passa pela regra (a)+(b) da SPEC-223 sem `npc_interaction`, e o validador aceita a proposta. Um LLM real que proponha concluir uma quest provada é um caminho legítimo do produto. Quest provada fechar sem conversa com a origem é o comportamento especificado para quest com local-alvo, e não muda nada da R9.
- **Por que não tornar determinístico:**
  - Fixar `random` no mock (por exemplo, `random.random → 0.99`) só provaria que a quest **não** fecha pelo storyteller. Isso não acrescenta nada.
  - Trocar a frase do corpo por um verbo de conversa mudaria o cenário do smoke §6, que precisa reproduzir a frase do jogador do L3 ("Entrego a prova da caça ao contratante").
  - Que o CLASSIFY real mande essa frase para a rota NPC é decisão de LLM. Isso só se prova no smoke real (§6 passo 2), como o próprio §6 prevê.
- **Determinismo do teste:** o teste é determinístico no que afirma. Status 200, arco preservado e status válido valem nos dois desfechos do mock. Rodei 3 vezes os 10 testes de `smoke_body` e o do grafo: verdes nas 3. O fechamento determinístico pela rota NPC fica provado por `_assert_entrega_closes` e pelos 18 testes de `tests/test_quest_delivery_npc.py`.
- Recomendação ao coordenador para o §6 passo 2: anotar a rota (`speaker.kind`/`reason`) junto com o `quest_completed`. Fechar pelo storyteller com prova continua correto. Se o roteamento real nunca cair em NPC com essa frase, o caminho da R9 fica sem uso real, e esse dado vai para o `docs/spec389/smoke.md`.

### Comandos rodados (rodada 3)

```text
git diff fbdb7f52..spec-389 → 3 arquivos (+34)
bash scripts/dev/pt.sh test_entrega_body_through_the_graph_keeps_the_arc + test_smoke_bodies_parse_and_play (3×) → 10 passed ×3
bash scripts/dev/pt.sh tests/test_portrait_offer_causes.py tests/test_quest_delivery_npc.py tests/test_size_budget.py → 57 passed
ruff format --check (3 arquivos do diff) → already formatted · scripts/dev/size_budget.py → rc 0
```
