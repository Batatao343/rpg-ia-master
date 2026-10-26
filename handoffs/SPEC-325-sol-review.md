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
