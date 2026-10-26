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
