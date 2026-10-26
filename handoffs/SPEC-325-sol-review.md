# SPEC-325 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / Sol · **Data:** 2026-10-26 · **Commit revisado:** `e09703d8`

## Escopo

Fase A (R8 resistência revelada, R9 golpe não-letal) na branch `spec-325`, `git diff main...spec-325`
(24 arquivos): `agents/combat.py`, `services/{combat_flags,combat_intents,conflict_damage,conflict_orchestrator,conflict_turn,death_flow,encounter_manifest,companion_tags}.py`,
`api.py`, `playtest/invariants.py`, `scripts/staging/vercel_env.py`, `web/src/{types.ts,workspace/tabs/CombateTab.tsx}`,
`data/companion_choice_tags.json`, registro de eventos e testes `tests/test_spec325_*`. Fases B–D estão fora.
Gate R17 (arena/matriz/D5) não rodado, como a spec declara (§8.1, coordenador).

O que está correto:
- **Desfecho com `incapacitado`.** `_encounter_outcome` dá `victory`. `_alive`/`_targetable`/listas da API excluem o
  incapacitado, então ele não age nem volta a ser alvo, e o combate termina por `combat_should_end`. XP sai 1× por
  `xp_awarded`, com o mesmo valor do abate (D2). Não gera `npc_killed` nem `record_kills` (desvio 4). O manifesto
  ganha o status e o `EventKind` `incapacitated`.
- **Flag `off`.** O único escritor de `incapacitated=True` é `apply_nonlethal_finish`, e `resistance_hit` só entra em
  `atk` quando a flag não está `off`. As mudanças incondicionais (`_encounter_outcome`, guarda de `_check_terminal`,
  `_targetable`) ficam inertes, e os testes de regressão de combate passam com as duas flags em `off`.
- **Flag `shadow`.** Não muda estado: `params["nao_letal"]` e `attacks` não são persistidos, e o shadow só emite
  `_log_event`.
- **Regra de ouro (R8).** A resistência só é revelada pelo golpe do herói ou de um aliado, depois de agir. A API
  devolve o rótulo pt-BR. O teste confere que uma imunidade que não agiu não aparece na API nem nos logs do
  narrador. O perfil hosted não persiste o overlay.
- **Chip "Sem matar".** Só aparece com `nonlethal_available`, que existe só com a flag `on`.
- **`vercel_env`.** As 8 flags estão em `OPTIONAL_FLAGS` e em `WORLD_FLAGS`; `staging_flags.json` não foi tocado.
- **Invariante.** `check_conflict_capabilities` está registrada em `CHECKS`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/conflict_orchestrator.py:1194-1199`, `:1616`; `services/conflict_turn.py:689` | **D2 quebrado para Elite/Chefe/Nomeado.** O golpe não-letal que enche o último Crítico dispara a Última Ação e o Estado Terminal (sem `_mark_down`). Na estabilização do fim da rodada, inimigo sem aliado capaz morre (`res["dead"]` → `deaths` → `npc_killed`). O `_mark_down` só alcança quem **sobreviveu** ao terminal e leva dano novo (`last_stand_resolved`), o que quase nunca acontece. Sondagem pelo `combat_node` real, `RPG_COMBAT_NONLETHAL=on`, "derrubo o capitão sem matar": `nomeado` → `morto` + `npc_killed`; `elite` → `morto` + `npc_killed`; só `padrao`/`lacaio` ficam `incapacitado`. Para o jogador, "NPC nomeado sobrevive" não vale justamente para os NPCs nomeados. | Quando `_nonlethal_mode(...) == "on"` e o alvo é inimigo full-flow que entrou em `last_stand_pending`/`estado_terminal` neste golpe, marcar `target["nonlethal_pending_by"]=actor_id` em `:1487`. A Última Ação ainda resolve. Na resolução terminal (`:1616`), se o alvo tem essa marca e é do lado inimigo, chamar `apply_nonlethal_finish` + status `incapacitado` + `out["incapacitated"]` em vez de `morto`/`deaths`. Em `shadow`, só logar. Teste pelo `combat_node` com `categoria` `nomeado` e `elite` (sem `last_stand_resolved` pré-setado) afirmando `incapacitado`, nenhum `npc_killed` e `victory`. |
| P1-2 | P1 | `tests/test_spec325_nonlethal.py:97-106`, `:122-127` | **Testes de D2 não provam o que dizem.** `test_no_npc_killed_event_and_named_npc_survives` usa um `lacaio`, não um nomeado, e a última asserção confere `state["npcs"]` de entrada, que o nó nunca altera, então passaria sempre. `test_elite_nonlethal_after_last_stand` só exercita `_check_terminal` com `last_stand_resolved=True` pré-setado e não passa pelo fluxo real (R7). Foi por isso que o P1-1 passou. | Junto com o P1-1: teste pelo nó com `categoria="nomeado"` e asserção sobre `pending_world_events` e o `final_status` do `combat.result`. Remover a asserção vazia sobre `state["npcs"]`. |
| P2-1 | P2 (antes de `on`) | `agents/combat.py:1700-1716`; `services/quest_log.py:508-532` | **Caça SPEC-313 × não-letal.** `sync_hunt_progress` recebe só `dead`. Se o jogador nocauteia a criatura-âncora de `cacar_criatura`, o combate termina em `victory`, a criatura sai da cena e a quest não recebe `hunt_kill`. Ela fica aberta até o prazo e falha com consequência (SPEC-305), uma armadilha para quem declarou "sem matar". Hoje o P1-1 mascara isso quando a âncora é elite. | Decidir e testar: (a) âncora incapacitada conta como `hunt_kill` (subjugada), passando `dead + downed` com `_normalize_bestiary_id`; ou (b) recusar o não-letal contra a âncora de caça ativa, com log. A opção (a) é a mais coerente com D2. |
| P2-2 | P2 | `services/law.py:456-459`, `:61-65` | **Lei SPEC-299: o gate lexical de `homicidio` aceita "sem matar".** `supports("homicidio", "Sem matar.")` é verdadeiro porque o léxico casa `matar`. A frase do chip e qualquer declaração "sem matar" dão suporte lexical a uma alegação `crime_claims` de homicídio pelo LLM, embora não haja morte. O caminho do motor (`:677-690`) é coerente: dá `agressao` e só vira `homicidio` com `npc_killed`. | Em `supports`, para `homicidio`, devolver `False` quando `death_flow.nonlethal_declared(player_text)`. Teste: "derrubo o guarda sem matar" não sustenta `homicidio` e sustenta `agressao`. |
| P2-3 | P2 | `services/death_flow.py:385-410` | **`NONLETHAL_RE`, sondagem pt-BR.** Falsos negativos: "não mate"/"não o mate", "poupe"/"poupe-o", "deixo-o vivo" (exige espaço antes de `-o`), "quero ele vivo", "capturo vivo", "não fujo e nocauteio o guarda" (a janela de negação de 2 palavras pega o "não" de outra oração). Falsos positivos: "poupo fôlego e ataco", "poupar energia, ataco com tudo", "estou em desacordo", "poupar é fraqueza" e "não quero golpe não letal, mato" (o atalho `startswith("nao")` ignora a negação externa). O dano é baixo: o falso positivo só poupa o inimigo, e só com a flag `on`. | Exigir objeto pessoal após `poup*` (`poup(?:o|ar|e)\s+(?:-?o|-?a|ele|ela|o\s+\w+|a\s+\w+)`), aceitar `poupe`, `-o vivo` e `mat[ea]\b` negado ("não mate"); cortar a janela de negação em conjunção/vírgula (`e`, `mas`, `,`). Adicionar esses casos a `tests/test_spec325_intents.py`. |
| P2-4 | P2 | `tests/test_spec325_nonlethal.py:130-136`; `tests/test_spec325_resist.py:130-136` | **O teste de shadow compara pouco.** Compara `combat`/`player`/eventos/mensagem, mas `_narrate` está stubado, então a prosa não prova nada, e `quests`, `npcs`, `bestiary_knowledge` e o retorno inteiro ficam de fora. Além disso, a suíte roda no default `shadow`, não em `off`, então a parte de R3 que pede regressões com tudo em `off` não é exercitada. | Comparar `out` inteiro (off × shadow) menos campos não determinísticos, capturar os argumentos de `_narrate` nos dois modos e comparar. Um teste parametrizado de regressão (p.ex. `test_spec272_conflito_ligado`) com as 8 flags em `off`. |
| P2-5 | P2 | `web/src/combatOutcome.ts:14-17`; `web/src/types.ts:371` | O painel de desfecho não tem rótulo para `incapacitado` (mostra a chave crua), e a união `status` do manifesto no TS não inclui o valor. | `incapacitado: "desacordado"` em `STATUS_LABELS` e `"incapacitado"` na união. |
| P2-6 | P2 | `services/dossiers.py:316` | O dossiê do bestiário (legacy) mostra o formato cru `igneo:imune`; só `_combat_block` usa `resistance_label`. | Aplicar `combat_flags.resistance_label` no dossiê. |
| P2-7 | P2 | `web/src/workspace/tabs/CombateTab.tsx:229-235` | O tooltip diz "O próximo golpe…", mas o toggle é persistente: não volta após o envio e continua anexando "Sem matar." se a flag sair de `on`. | Resetar `spare` após `onAction` (ou ajustar o texto) e ignorar `spare` quando `!nonlethal_available`. |
| P2-8 | P2 | `services/companion_tags.py:126-133`; spec §Histórico | A tag `poupou_inimigo` sai de `final_status=="incapacitado"` com outcome `victory`, não do desfecho `incapacitated_enemy` que a R9 descreve. Funciona, mas não está entre os desvios registrados. | Registrar como desvio 5 na spec. |

Sem P0. Não há valor do LLM sem validação nem structured output novo: a declaração é regex, sem campo novo no
`PlayerMove`. Não há segredo em log. Nada mudou em `evals/`. O writer persistente novo (`revealed_resistances` no
inimigo e no overlay legacy) usa o caminho existente do `bestiary_knowledge` e o formato é validado pelo invariante.

## Correções aplicadas

(nenhuma ainda — executor)

## Pendências

- P1-1 e P1-2: obrigatórios antes de pousar (ou, no mínimo, antes de qualquer flag da Fase A ir a `on`). Executor Terra, nesta spec.
- P2-1 e P2-2: obrigatórios antes de `RPG_COMBAT_NONLETHAL=on` (gate R17/D6), nesta spec.
- P2-3 a P2-8: podem entrar com o P1 ou na Etapa 8.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -n 2 tests/test_spec325_{flags,intents,nonlethal,resist}.py tests/test_spec192_vercel_env.py tests/test_log_event_registry.py → 94 passed (exit 0)
bash scripts/dev/py.sh -m pytest -n 2 -q tests/test_death_flow.py tests/test_spec272_conflito_ligado.py tests/test_encounter_manifest.py tests/test_spec300_tags.py tests/test_spec313_hunt.py tests/test_spec299_confrontation.py tests/test_spec299_crime_claims.py tests/test_perfil_normal_invariantes.py → exit 0
RPG_COMBAT_REVEAL_RESIST=off RPG_COMBAT_NONLETHAL=off pytest -n 2 tests/test_spec272_conflito_ligado.py tests/test_death_flow.py tests/test_encounter_manifest.py → 33 passed
sondagem temporária (arquivo removido) combat_node, NONLETHAL=on, "sem matar": nomeado→morto+npc_killed; elite→morto+npc_killed; padrao→incapacitado
sondagem NONLETHAL_RE com 30 frases pt-BR → ver P2-3
cd web && npm test → 178 pass; tsc --noEmit → exit 0
```

---

## Fase B

> **Veredito (Fase B):** `CHANGES_REQUIRED`
> **Revisor:** Opus / Sol · **Data:** 2026-10-26 · **Commit revisado:** `afa074f2` (`git diff main...spec-325`)

### Escopo

R10–R13 (abordagem, ataque na fuga, abandono, sacrifício), desvios 6–11 e §8.2 da spec. Arquivos: `agents/combat.py`,
`services/{chase,combat_intents,companion_soul,companion_tags,conflict_orchestrator,npc_world}.py`, `state.py`,
`api.py`, `observability/events.py`, `data/companion_choice_tags.json`, `web/src/{types.ts,workspace/tabs/CombateTab.tsx}`
e os testes novos. O gate de letalidade §8.2 ficou fora (é do coordenador).

Conferido e correto:
- Destino selado em `party[i].pending_fate`, companheiro inativo com `waiting_at`, consumido só em
  `companion_soul.apply_turn` 7b via `apply_companion_fate` (SPEC-304). O telegrama `source="abandono"` é gravado no
  1º turno após o selo; o destino sai só com `day - pday >= TELEGRAPH_MIN_DAYS`. Companheiro rechamado = resgate.
- Sem destino duplo: o selo é excluído de `companions_exposed` (`companion_soul.py:985`) e do perigo do `npc_world`
  (`npc_world.py:885`).
- Regra de ouro: o payload de `companion_abandoned` leva só `name/location_id/day`. O `event_id` é o hash da seed,
  não a seed. O narrador recebe "X ficou para trás". `/game/state` não expõe `pending_fate` (teste com dump). A
  `chase_view` só ganha `approach`/`abandon_candidates`/`sacrifice_offer` com a flag `on`.
- D3: `can_volunteer_sacrifice(soul)` exige aprovação >= `LOYAL_AT` e `coragem >= 1`, ou o traço. A oferta sai uma
  vez por perseguição e expira na rodada seguinte. Recusar não toca a alma.
- R10: a abordagem vale só na rodada (é removida do estado com `on`). Em `shadow`/`off` fica Agilidade, e o consumo
  do RNG é idêntico (`ally_rolls` mantém a ordem e o número de `luck_roll`).
- R11: à distância continua; corpo a corpo em `pressionado` limpa `combat_meta["chase"]`; em `afastado`/`quase_livre`
  é recusado via `run_round(refusal=)`, que segue o caminho do item recusado e devolve `combat.round`.
- `shadow` não escreve nada: `last_luck`, `sacrifice_offer` e `approach` não são persistidos; os testes off×shadow
  comparam `combat/party/player/enemies/event_log`.
- Catálogo 16→17 (`abandonou_companheiro`) é legítimo. O teste `vercel_env` garante as 8 flags em
  `WORLD_FLAGS`/`OPTIONAL_FLAGS`. Nada mudou em `evals/`. Não há structured output novo nem valor do LLM: tudo é regex
  fechada ou seed. Nenhum segredo vai a log.
- Round-trip save/load com o selo (sondagem temporária, perfil legacy): `pending_fate`, `chase.abandoned` e
  `last_luck` sobrevivem intactos.

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| B-P1-1 | P1 | `services/companion_soul.py:897`; `agents/combat.py:2008` (viagem só com `flee_dest_id`); chips em `web/src/workspace/tabs/CombateTab.tsx` (sem destino) | **Abandono e sacrifício se anulam no fluxo principal.** Uma fuga sem destino (o caso do chip e de "Aceito o sacrifício.") deixa o herói no mesmo `current_location_id`. No mesmo turno, `turn_finalizer → apply_turn` vê `here == location and not combat_active` e trata isso como resgate: o selo é cancelado sem dano. Sondagem pelo `combat_node` real com `RPG_CHASE_ABANDON=on`: aceito o sacrifício → `combat.phase=ended`, local `montanhas_afiadas` → após `apply_turn`, `pending_fate=None`. O mesmo vale para o abandono quando a fuga termina sem destino. O R13 ("o companheiro segue o mesmo caminho selado") e o custo do R12 só aparecem se a fuga tiver destino. Os testes não pegam isso porque `_after` (`tests/test_spec325_abandon.py:158-172`) troca o local para `nova_arcadia` à mão. | Exigir que o herói **tenha saído** antes de valer o resgate. Opção (a): gravar `pf["left"]=True` na 1ª vez que `apply_turn` vê `here != location`, e resgatar só com `left` e `here == location`. Se o herói nunca sair, o destino precisa poder sair após >= 1 dia, mas o gate da 304 recusa `here == waiting_at`; a regra precisa ser decidida e documentada. Opção (b): fuga com selo e sem destino move o herói para um nó adjacente (o mesmo caminho do `_apply_flee_travel`). Escolher uma, registrar como desvio e adicionar um teste ponta a ponta `combat_node` (aceite/abandono + fuga) → `apply_turn` **sem** editar o local à mão. |
| B-P2-1 | P2 | `services/companion_soul.py:871` (`if live:`) | O consumo e o resgate só rodam com `RPG_COMPANION_SOUL=on`. Com a alma em `off`/`shadow` e `RPG_CHASE_ABANDON=on`, o selo nunca é consumido nem cancelado. O companheiro fica para sempre fora de `abandon_candidates`, do sacrifício e do perigo (todos filtram `pending_fate`), mesmo depois de rechamado. | Tratar `chase_abandon` como `off` quando a alma não estiver `on` (em `_chase_party_choices`/`_publish_sacrifice_offer`/API), ou mover o resgate (active/no local) para fora do `if live`. Teste com a alma `off`. |
| B-P2-2 | P2 | `tests/test_spec325_abandon.py` | Falta um teste versionado de round-trip save/load com o selo (`pending_fate`, `chase.last_luck/abandoned/sacrifice_offer`), como exige a regra de writer persistente. A sondagem passou no legacy. | Teste `save_game_state` → `load_game_state()` no meio do selo, e depois `apply_turn` aplicando o destino no estado carregado. |
| B-P2-3 | P2 | `services/npc_world.py:885` | A exclusão do perigo off-screen para companheiro selado não tem teste. Só `companions_exposed` é testado (`test_peril_pipeline_skips_sealed_companion`). | Teste do `day_hook` com o companheiro selado: nenhum perigo aberto para ele. |
| B-P2-4 | P2 | `agents/combat.py:1548-1552` | O ataque corpo a corpo recusado (R11) não é uma tentativa de fuga, então zera `flee_attempts`. Uma rodada recusada, que não gasta nada, reinicia o teto de tentativas consecutivas (`MAX_CONSECUTIVE_FLEE_ATTEMPTS`). Não há laço infinito (a recusa depende do jogador), mas a fuga com destino fica mais longa. | Na recusa, preservar `flee_attempts` (salvar antes e restaurar junto com `combat.round`). |
| B-P2-5 | P2 | `services/chase.py:390`; `agents/npc.py:934` | `seal_fate` grava o **id** do local em `waiting_at`, e a fala "Está esperando em {waiting}" mostra o id cru (`montanhas_afiadas`). A convenção já é mista (`npc_world.resolve_location_ref` aceita os dois; `law._party_wait` também grava id). | Na mensagem do `npc.py`, resolver o id para o nome de exibição. Também pode ser follow-up geral. |
| B-P2-6 | P2 (nota) | `agents/combat.py:_chase_party_choices` | O sacrifício aceito não gera evento nem tag para os outros companheiros, e a spec R13 não pede. Se o dono esperava efeito na alma/reputação ao aceitar (o pedido da revisão citava isso), falta definir. | Decisão do dono; nada a mudar até lá. |

Sem P0.

### Pendências

- B-P1-1: obrigatório antes de pousar a Fase B (ou, no mínimo, antes de `RPG_CHASE_ABANDON=on`). Executor Terra, nesta spec.
- B-P2-1 a B-P2-3: antes de `RPG_CHASE_ABANDON=on`.
- B-P2-4 e B-P2-5: podem entrar com o P1 ou na Etapa 8. B-P2-6: decisão do dono.

### Comandos rodados

```text
RAM livre 2,2 GB → testes em série (sem -n)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec325_{abandon,chase_choices,chase_intents,flags,intents,nonlethal,resist}.py tests/test_spec300_{values,tags}.py tests/test_spec304_{fate,perils,review}.py tests/test_spec192_vercel_env.py tests/test_conflito_fuga.py tests/test_fuga_progressiva_persistente.py tests/test_conflito16_frontend.py → 289 passed (exit 0)
sondagem temporária (scratchpad, fora do repo): sacrifício aceito → apply_turn no mesmo local → pending_fate=None (B-P1-1); abandono com combate ativo → selo mantido
sondagem temporária: save_game_state/load_game_state com selo → pending_fate/last_luck/abandoned idênticos
cd web && npm test → 194 pass, 0 fail
```

---

## Fase C

> **Veredito (Fase C):** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / Sol · **Data:** 2026-10-26 · **Commit revisado:** `d84c5d8d` (`git diff main...spec-325`)

### Escopo

R14 (objetos de cena) e R15 (ordem a companheiro), desvios 12–16 e §8.3. Arquivos: `agents/combat.py`
(`_object_declaration`, `_guard_object_step`, `_companion_orders`, `PlayerMoveObject`), `services/combat_intents.py`
(`object_step`, `companion_order`), `services/companion_orders.py`, `services/conflict_turn.py`
(`_search_discovers_object`), `api.py` (`scene.objects`, `companion_orders`), `observability/events.py`,
`web/src/{types.ts,workspace/tabs/CombateTab.tsx}` e testes `tests/test_spec325_{objects,orders,intents_scene}.py`.
O gate §8.3 ficou fora (é do coordenador).

Conferido e correto:
- **Regra de ouro.** `visible_objects` devolve só `label`/`cost`/usos, e o secreto só aparece depois de descoberto.
  O prompt do CLASSIFY lista `id=nome [rótulos]`, sem `effect`. A recusa ("Não dá para usar '<rótulo>' assim
  agora…") não descreve o efeito. O log de uso sai só depois do uso. Há teste para "efeito não usado não chega
  ao narrador nem à API".
- **Casamento nome + interação.** Exige o nome canônico inteiro (com checagem de negação no nome) e o rótulo,
  inteiro ou pelo radical. Só aceita objetos visíveis, então o secreto não descoberto não pode ser declarado. O
  `object_id`/`interaction` vindos do LLM são validados contra `visible_objects` (`_valid_object_use`); se forem
  inválidos, viram ataque básico. O guard `isinstance(res, PlayerMove)` cobre a subclasse.
- **Ofensivo contra os seus.** `_effect_is_offensive` cobre `damage` e condição nociva. O alvo vem de
  `params.target` (fixo no objeto). A recusa passa pelo `run_round(refusal=)` e não gasta a rodada.
- **`procurar`.** O estado "alguém escondido de mim" é lido **antes** de `cs.search`, que o limpa (desvio 16). Revela
  o 1º secreto da zona do ator (ou sem zona). Em `shadow` só loga e em `off` não faz nada. O log de `procurar` em
  `off` continua igual.
- **Ordens (D9).** Tabela fixa sobre `values` da alma (`honra`/`compaixao`/`coragem` >= 2). Somada ao perfil,
  passa pelo `tp.validate_companion_order` existente, com `leverage = approval >= LOYAL_AT` (70). Recusa,
  `loses_command` ou falta de alvo válido viram só uma linha de log, sem declaração, e o aliado age pelo perfil. A
  declaração do jogador não muda (`test_player_action_unchanged_on_refusal`).
- **Shadow/off.** Em `shadow`, os quatro pontos só emitem `_log_event`. Em `off`, o prompt e o schema do CLASSIFY
  continuam byte a byte iguais (`move_model = PlayerMove`, `object_rule = ""`). As regressões de combate passam
  com C/D em `off`.
- **Chips web.** Aparecem só quando a API traz `scene.objects`/`companion_orders`, e os dois saem só com
  `combat_flags.active(...)` (= `on`). O texto do chip ("<rótulo> <nome>." / "<nome>, <verbo>.") é reconhecido
  pelo parser local.

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| C-P2-1 | P2 | `agents/combat.py:1873` + desvio 15 | O texto da ordem também vai ao CLASSIFY do jogador. Com o LLM real, "Bran, recue." ou "Bran, cure." pode virar `move afastar` ou cura **do herói**, e não o ataque básico que o desvio 15 supõe. O MockLLM esconde isso. | Com a ordem aceita em `on`, retirar a oração da ordem do texto antes do parser. Se sobrar só ela, usar ataque básico ou `pass` sem CLASSIFY. Smoke real (§6) com "X, recue.". |
| C-P2-2 | P2 | `web/src/workspace/tabs/CombateTab.tsx:42` | Falta o chip `curar`: o R15 lista atacar/proteger/recuar/curar. | Adicionar `["curar","Curar"]`, se possível só para quem tem perfil de suporte, ou registrar como desvio. |
| C-P2-3 | P2 | `services/combat_intents.py:125` | Com rótulo de 5 letras ("puxar", "subir"), o radical fica em 4 letras ("puxa") e não casa "puxo"/"subo". | `stem = fl[:max(3, len(fl)-2)]` para rótulos de 5 letras, com teste. |
| C-P2-4 | P2 | `agents/combat.py:1225` | `"object"` entrou no conjunto do `_canonical_player_action` sem depender da flag. Em `off`, uma declaração `object` do harness passa a ser relatada como `object`, e não `pass`. É mais correto, mas não é "off byte a byte" (desvio 14). | Registrar no desvio 14, ou condicionar à flag. |
| C-P2-5 | P2 | `services/companion_orders.py:17` | A linha `coragem >= 2 → abandonar_posto` vai além do exemplo da spec e transforma "recuar" em recusa para companheiros corajosos. É razoável, mas não está registrado. | Registrar na spec (D9). |
| C-P2-6 | P2 | `web/` | Não há teste web (unitário) para os chips de objeto e de ordem nem para a nota de reforço. | Um teste de render com e sem os campos. |

Sem P0/P1. Nada de `evals/` alterado. Nenhum segredo vai a log (os payloads levam só `verb`/`action`).

---

## Fase D

> **Veredito (Fase D):** `CHANGES_REQUIRED` (não bloqueia o pouso em `shadow`, mas bloqueia `RPG_COMBAT_REINFORCEMENTS=on`;
> o gate R17 (a) **não** detecta o defeito, então ele precisa ser corrigido antes da medição)
> **Revisor:** Opus / Sol · **Data:** 2026-10-26 · **Commit revisado:** `56ee5985`

### Escopo

R16 (reforço de `lider_matilha`), desvios 17–20 e §8.4. Arquivos: `services/reinforcements.py`, `agents/combat.py`
(`_plan_reinforcements`, `_advance_reinforcements`), `services/encounter_manifest.py` (`add_joined`, `_base_id`),
`api.py` (`reinforcement_warning`), `docs/spec285/arena_lethality.py` (célula `lider_matilha`) e
`tests/test_spec325_reinforcements.py`.

### Por que o reforço BAIXA a morte do herói (prioridade)

Mecanismo confirmado por sondagem (arena real, `basico`, 4 líderes × 5 classes × 10 seeds, MockLLM):

1. **A cópia rebaixada continua líder.** `services/reinforcements.py:89-93`: sem Lacaio da mesma facção (é o caso
   dos 4 líderes do pool), a cópia muda só `categoria`/`type` e mantém `arquetipo="lider_matilha"` e o
   `tactical_profile` do líder (sondagem: prioridades `['flee','support','support']`). O reforço é um **segundo
   líder de matilha**.
2. **Líder com par troca ataque por apoio.** `services/tactical_profile.py:231-235`: `lider_matilha = {matilha_quebrada:
   flee, alvo_vulneravel: support, sempre: support}`. Sozinho, o `support` não tem alvo
   (`_ally_available_target=None`) e cai para ataque (`services/conflict_orchestrator.py:529-538`), então o líder
   solo ataca 100 % das vezes. Com o reforço em cena, os dois passam a conceder `attack_advantage` um ao outro
   (`conflict_orchestrator.py:1315-1327`) em vez de atacar. Contagem de declarações no L5: líder solo, 998/998
   ataque ou Carta; líder com par, 388/620 (63 %) `tactic:support`; reforço com par, 445/620 (72 %) `support`.
3. **Morto o líder, o reforço foge e a luta vira vitória.** `conflict_orchestrator.py:436`: `pack_broken`
   (o único par morto) faz a cópia fugir. Em 57 de 120 lutas ON no L5, o fim foi "líder morto + reforço `fugiu`",
   com `win`.
4. **Timeout não conta como morte.** Os +2 a +11 timeouts/200 (cópia do `mon_auroque_ruinas`, que herda
   `bst_mimetismo_morto`/esconder e a fuga) entram como não-morte na arena (`arena_lethality.py:229`). Isso explica
   só uma parte pequena do Δ.

Não é erro de contagem, de troca de alvo pelo líder a 50 % nem de reset de inimigo: o id, o orçamento e o fim de
luta estão coerentes. **É defeito de design (desvio 20) que inverte o propósito do R16**, e dois defeitos se anulam:

| Nível | OFF | ON (como está) | ON com a cópia em perfil `equilibrado` (sondagem) |
|---|---|---|---|
| L3 | 0,570 | 0,485 (−8,5 pp) | **0,880 (+31 pp)** |
| L5 | 0,565 | 0,440 (−12,5 pp) | **0,860 (+29,5 pp)** |
| L8 | 0,450 | 0,340 (−11 pp) | **0,810 (+36 pp)** |

Com a IA do reforço consertada, a letalidade explode, porque a cópia leva a **ficha inteira do Elite** (desvio 20)
e o orçamento a cobra como **Lacaio** (`reinforcements.py:105-108`: `eb.tier_cost(template)` depois de rebaixar a
`categoria`). Na prática entra um segundo Elite pelo preço de um Lacaio. O resultado negativo atual esconde esse
estouro, e o gate "≤ +3 pp" passa só porque o reforço não luta.

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| D-P1-1 | P1 | `services/reinforcements.py:89-93` | A cópia rebaixada herda `arquetipo`/`tactical_profile` de `lider_matilha`: cria um laço de apoio mútuo e foge quando o líder morre (mecanismo acima). O reforço deixa o herói **mais seguro**. | Na cópia: `arquetipo` de combate (p.ex. `equilibrado`, ou o arquétipo de Lacaio da espécie) e `tactical_profile = _profile_for_archetype(...)`. Tirar das `cartas` as de comando/esconder do líder (`bst_uivo_comando`, `bst_mimetismo_morto`). Teste: a cópia não é `is_leader` e declara `attack` quando está com o líder. |
| D-P1-2 | P1 | `services/reinforcements.py:89-93`, `:105-108`; spec desvio 20 | A ficha do Elite é cobrada como Lacaio no orçamento. Com o D-P1-1 corrigido, o Δ medido fica entre +29 e +36 pp, contra o teto de +3 pp. | Uma de duas: (a) rebaixar a **ficha** de verdade (gerar Lacaio categórico da mesma espécie/facção via o gerador do bestiário, com Vitalidade/virtudes de Lacaio); (b) cobrar o custo da ficha real (Elite), o que quase nunca cabe. A (a) segue o espírito do R16 ("1 Lacaio"). É mudança do desvio 20: **decisão do autor da spec/dono**. Remedir a célula `lider_matilha` depois. |
| D-P2-1 | P2 | `services/discovery.py:50-58` | `normalize_bestiary_id` não reconhece `<base>_r<N>`: `_\d+$` não remove `_r1` e o slug do nome "(reforço)" não casa. Sondagem: `normalize_bestiary_id(reforço) == ''`, então `record_kills` não conta a morte (bestiário `defeated`) e `sync_hunt_progress` (SPEC-313, `agents/combat.py:2195`) nunca vê o reforço. O `_base_id` do manifesto foi atualizado, mas este não. | Em `normalize_bestiary_id`: tentar `enemy["archetype_id"]` antes, e/ou `re.sub(r"_r?\d+$", ...)`. Teste: o reforço morto conta `defeated+1` na espécie. Se a caça deve ou não aceitar a cópia como âncora é decisão; pelo menos documentar. |
| D-P2-2 | P2 | `services/reinforcements.py:113-116` | Líder com nome único (`mon_capita_corda` "Capitã da Corda Molhada", `enemy_bandido_capitao`) gera uma segunda "Capitã… (reforço)". Para o narrador, é uma duplicata de uma personagem nomeada. | Junto com o D-P1-2(a): nome genérico do Lacaio da espécie/facção, nunca o nome do líder. |
| D-P2-3 | P2 | `tests/test_spec325_reinforcements.py` | Falta round-trip `save_game_state` → `load_game_state` no meio do reforço (entre aviso e chegada: `combat.reinforcement`, `next_by_template`, `scene.reinforcement_triggers[*].participants`), como exige a regra de writer persistente. Só há o caso de save antigo. | Teste: avisa, salva, carrega, roda a rodada seguinte → chega `_r1` uma vez. |
| D-P2-4 | P2 | `services/reinforcements.py:29-34` | `acts()` não olha `estado_terminal`/`last_stand_pending`. Um líder em Estado Terminal com `status="ativo"` ainda "age" e o reforço chega. O R16 manda cancelar se o líder "cair". | Incluir `estado_terminal` (e `incapacitado`) na condição de cancelamento, com teste. |
| D-P2-5 | P2 | `tests/test_spec325_reinforcements.py:118-143` | `test_unique_instance_id_and_xp` confere `xp >= xp_before`, que passa mesmo sem XP. | Conferir `xp > xp_before`, ou o valor exato de `xp_awarded`. |
| D-P2-6 | P2 | `docs/spec285/arena_lethality.py:229` | Na célula `lider_matilha`, `timeout` conta como não-morte, e é justo onde a Fase D o aumenta. | No gate §8.4, relatar `death+timeout` ou exigir Δtimeout ≈ 0 na célula. |

**Fidelidade da célula da arena (item 6):** é fiel ao nó. Usa o mesmo `rf.plan_triggers` antes do `cs.freeze`, o
mesmo `rf.advance(..., mode="on")` no fim da rodada só se a luta não acabou nem o herói morreu (o nó também
exclui `is_simulation`/`hero_fled`), e o mesmo orçamento `encounter_budget(nível, danger, 0)` que define o grupo. As
diferenças são que a arena não chama `_mirror_vitals`/`_sync_enemy_knowledge`/`add_joined` (inertes para a
letalidade), e que o `spawn → template_by_id` consome o `random` global só no ON (é ruído, não viés). As células
atuais seguem intactas (`reinforce and cat == LEADER_CELL`, e a categoria fica fora do default).

**Ids/manifesto (item 3):** `_r<N>` vem de `combat_meta["next_by_template"]` e é distinto de `<base>_<n>`. O
`encounter_manifest._base_id` (`_r?\d+$`) não colide com nenhum id do bestiário (grep: 0 ids `_r<N>`). O
`_canonical_enemy_id` (`agents/combat.py:101`) não remove `_r1`, então a cópia nunca gera `npc_killed` do NPC
nomeado (correto). O que falta está no D-P2-1.

**Shadow/off (item 4):** em `shadow`, `_plan_reinforcements` retorna antes de `add_reinforcement_trigger`, e
`rf.advance` só loga `would_warn`, sem `combat_meta.reinforcement` (desvio 19). Em `off` nada roda. A API publica
`reinforcement_warning` só com `on` e entre o aviso e a chegada ou o cancelamento. Sem P0. Nada em `evals/`. Nenhum
valor do LLM. Nenhum segredo vai a log.

### Pendências

- D-P1-1 e D-P1-2: obrigatórios antes de `RPG_COMBAT_REINFORCEMENTS=on` e antes de rodar o gate §8.4. O D-P1-2
  pede decisão sobre o desvio 20 (ficha de Lacaio de verdade ou custo de Elite). Depois disso, remedir a célula
  `lider_matilha`. Com a correção mínima, o esperado é que o Δ fique positivo e maior que 3 pp.
- D-P2-1 a D-P2-4: antes do `on`. D-P2-5 e D-P2-6: na Etapa 8.
- Fase C: C-P2-1 antes de `RPG_COMPANION_ORDERS=on` (smoke real). O resto pode ir na Etapa 8.

### Comandos rodados (Fases C+D)

```text
RAM livre 2,4–2,7 GB → testes em série (sem -n)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec325_{objects,orders,intents_scene,reinforcements}.py tests/test_encounter_manifest.py tests/test_log_event_registry.py → 97 passed (exit 0)
RPG_COMBAT_OBJECTS=off RPG_COMPANION_ORDERS=off RPG_COMBAT_REINFORCEMENTS=off pytest -q tests/test_spec272_conflito_ligado.py tests/test_spec313_hunt.py tests/test_conflito_fuga.py tests/test_spec325_flags.py → exit 0
sondagem (scratchpad, fora do repo): arena fight() lider_matilha L3/L5/L8 basico, 10 seeds, contagem de declarações por ator solo×par e desfecho final (líder/reforço)
sondagem: mesma arena com a cópia em perfil `equilibrado` → +31/+29,5/+36 pp (tabela acima)
sondagem: normalize_bestiary_id/record_kills no reforço `enemy_soldado_legiao_ferro_r1` → '' / {}
web: não rodado (sem mudança de teste web; RAM baixa)
```
