# SPEC-313 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (subagente spec-reviewer, independente do executor) · **Data:** 2026-10-25 · **Commit revisado:** `1665daf3` (branch `spec-313`, base `ab3950e2`)

## Escopo

`git diff ab3950e2...spec-313` (33 arquivos): `services/lore_quests.py` (novo), extensões em
`services/world_quests.py`, `services/quest_log.py`, `services/event_processor.py`,
`services/world_validators.py`, `services/npc_world.py`, `services/structured_outputs.py`,
`state.py`, `agents/npc.py`, `agents/combat.py`, `agents/storyteller.py`,
`agents/turn_finalizer.py`, `world_utils.py`, `mock_llm.py`, `playtest/invariants.py`,
`playtest/scenarios.py`, `data/world/{lore_quests,world_quests,pressures}.json`,
`observability/events.py`, os 8 `tests/test_spec313_*.py` e a spec (inclusive §8.2). Lido também
o contrato da SPEC-312 em `services/rumors.py` (`investigable`, `truth_of`, `mark_resolved`,
`_cap_ledger`). Ficaram fora: o smoke real §6, a medição de letalidade SPEC-285 e a suíte completa
(são do coordenador).

O que confere:
- **Verdade do rumor:** só `lore_quests.resolve_rumor_outcome` lê `truth_of`, e só no apply do
  `quest_completed` (`event_processor.py:571-583`). O único writer de `resolution` é
  `rumors.mark_resolved`. `investigable` devolve rumor falso e verdadeiro do mesmo jeito.
  `_source_state` (`world_quests.py:924-929`) só olha a instância e a `resolution`, e as duas
  não dependem de `truth`. O status público junta `failed` e `expired`. O título no
  `event_log`/crônica é genérico, o derivado sai com `world_source_id` vazio e o `<DESFECHO_DE_QUEST>`
  não carrega o gist do rumor. O teste `rumor.became_fact` passa no caminho do desmentido.
- **Valores da LLM:** `kind`/`anchor_id` só valem se estiverem no menu daquele turno
  (`validate_anchor`). Item, quantidade, destino, ouro e prazo vêm do JSON curado ou de uma
  regra. O `reward_hint` da LLM é descartado. O texto passa por `safe_llm_text`. O downgrade usa
  `register_proposed_quests`, que só copia campos da lista branca, então `kind`/`anchor_id` não
  vazam para a quest comum.
- **Mecânica em Python:** `has_completion_proof` e `sync_action_progress` bloqueiam a conclusão
  por texto de caça, entrega e escolta. A entrega tira o item uma vez, no mesmo apply do ouro.
  O validador recusa a entrega sem o material. A escolta é sincronizada no `turn_finalizer` e é
  solta quando a quest deixa de estar ativa.
- **305:** `_active_world` e `check_world_quests` excluem os tipos de lore. A troca
  `break`→`continue` não deixa criar quest de crise acima do teto (os contadores não descem).
- **Compatibilidade:** os campos são opcionais e o round-trip legado tem teste
  (`test_legacy_quest_and_npc_sim_roundtrip`). O guard de FallbackLLM tem teste. A flag
  `off|shadow|on` depende de `RPG_WORLD_QUESTS`. O mock R34 propõe a partir do menu.
- Nenhuma mudança em `evals/`. Não há segredo em log: os logs `lore_quest.*` levam só
  kind/reason/channel.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/combat.py:1630` | **A caça nunca conclui em jogo real.** `sync_hunt_progress` recebe `e.get("bestiary_id")` dos inimigos mortos, mas os dicts de inimigo em runtime não têm essa chave. Eles carregam `id = "{bestiary_id}_{N}"` e `archetype_id` (`agents/combat.py:205-216`). A chave `bestiary_id` só existe no `EncounterParticipant` do manifesto (`services/encounter_manifest.py:324`). A lista fica `["", ...]`, a evidência `hunt_kill` não é gravada e `cacar_criatura` sempre falha no prazo. Os testes de `test_spec313_hunt.py` só chamam `sync_hunt_progress` com ids prontos. Nenhum passa pelo `_combat_node`. | Usar `services.discovery.normalize_bestiary_id(e)` (ou `e.get("archetype_id")` com fallback para ele). Acrescentar um teste de integração: inimigo instanciado por `_instances` (id `x_1`), vitória no `_combat_node` (ou no trecho extraído) e `hunt_kill` gravado. |
| P1-2 | P1 | `observability/events.py` (arquivo inteiro) | O catálogo foi regenerado sem `ruff format`: 676 linhas de churn (aspas simples, entradas longas em uma linha), e `ruff format --check observability/events.py` falha. O CI roda `uv run ruff format --check .` (`.github/workflows/validate.yml:62`), então quebra no pouso. O conteúdo está certo: a única chave nova é `lore_quests.fallback`, nenhuma foi removida ou alterada. | `ruff format observability/events.py` (o diff fica em +1 linha). Opcional: o `gen_event_catalog.py` passar a formatar a saída. |
| P2-1 | P2 | `services/npc_world.py:350-352` | `presence` devolve o local do jogador para qualquer escolta não pausada, antes de `escort_sync` (que roda no fim do turno) decidir se pausa. No turno em que o jogador vai no sentido contrário, o escoltado aparece em cena no local novo e some no turno seguinte. Isso viola R22 ("nunca em dois lugares / sem teleporte") pelo lado do narrador. | Em `presence`, usar `escort_eval(state, esc)`: `paused_at` dele, ou `at` quando pausa. Teste: desvio → o NPC não aparece `in_scene` no local novo nesse mesmo turno. |
| P2-2 | P2 | `playtest/invariants.py:2200-2205` | O relaxamento de `quest.world_unheard` aceita qualquer `event_id` que comece com `npc:` em quest de lore. É uma tautologia, porque o próprio código sempre grava `npc:<ref>:<turno>`. O invariante deixou de provar R12 ("só nasce se o NPC estava `in_scene`"). | Validar que `<ref>` está em `npcs`/`npc_sim` e que a quest tem `origin_name` igual a esse NPC (ou registrar o turno em que ele estava em cena). Pelo menos conferir a forma do id e o ref conhecido. |
| P2-3 | P2 | `services/lore_quests.py:254-342` | O menu não olha `cap_reached`. Com 2 quests de lore ativas, o bloco continua no prompt, o NPC oferece a tarefa na fala e a proposta é descartada (`cap`): uma promessa narrativa sem quest. O cooldown de origem já esconde o menu; falta fazer o mesmo com o teto. | `if cap_reached(state): return "", []` no começo de `anchor_menu` (em `shadow`, logar e sair). |
| P2-4 | P2 | `services/lore_quests.py:273-288` | As caças do menu não são filtradas pelo porte do perigo da região. Com `hunt_pressure` empatado em 1.0, a ordem é alfabética e pode cair numa elite que nunca sai no sorteio local (R26 só puxa a âncora "se couber no porte"). A quest fica impossível e falha no prazo, sem custo para ninguém, mas o jogador não entende por quê. A letalidade em si é segura, porque o porte continua decidindo. | Filtrar ou ordenar as candidatas pelo que `pick_encounter_enemy` aceita no perigo típico da região. Ou registrar como `[BALANCEAR]` e medir no playtest da Etapa 8. |
| P2-5 | P2 | `services/world_quests.py:786` | No `_offer`, uma quest de lore criada também faz `active_world += 1`. Na mesma rodada ela ocupa uma vaga do teto de 3 da 305, embora `_active_world` a exclua. O efeito só dura uma rodada, mas contradiz R18 (teto separado). | Incrementar `active_world` só quando `seed.kind not in lq.LORE_KINDS`. |
| P2-6 | P2 | `services/world_quests.py:916-923`, `services/npc_world.py:1494` | Escoltado morto por outra via: a quest fica `active` até o prazo e então expira em silêncio. Até lá, `escort_sync` continua "acompanhando" o NPC morto. `in_scene` provavelmente filtra o morto, mas o `pos` dele segue o jogador. | Em `escort_sync`, soltar a escolta quando `entry.get("dead")`, ou expirar a quest de imediato quando `_source_state == ok_end` para `escoltar`. |
| P2-7 | P2 | `data/world/world_quests.json:242-243` | As descrições `testemunho`/`cartaz` de `recolher_mortos` nomeiam "Guilda dos Corvos" sem checar se o jogador conhece a fação. Isso fere o princípio de não-onisciência que R8/R25 aplicam ao texto (se `guilda_corvos` é fação do grafo, `unknown_faction_names` a marcaria). | Tirar o nome ("quem conhece os ofícios funerários sabe…") ou usar `{faccao}` via `_faction_label`. |
| P2-8 | P2 | `specs/SPEC-315-rumores-adotados-pelo-motor.md:244-272` | Mudança fora do escopo numa spec de outro dono: um bloco de código Python foi reformatado (provavelmente `ruff format` em markdown). Agora tem `materialization: (\n    dict  # ...\n)`, que é Python inválido como anotação de doc. | Reverter o hunk da SPEC-315. |
| P2-9 | P2 | `state.py:534` | Comentário do `outcome` lista `"boato"`, mas o vocabulário real é `confirmado`/`desmentido`/`inconclusivo` (§8.2). | Corrigir o comentário. |
| P2-10 | P2 | `services/quest_log.py:399-404` (comportamento da 305 herdado) | `investigar_rumor`/`recolher_mortos` concluídas pelo LLM precisam de `location_reached` mais **uma** evidência qualquer (`npc_interaction` conta). R19 pede "2 evidências distintas do `action_vocab`". Na prática a 305 também chega a 2 via `completion_ready`, mas uma conversa com a origem, já no local, basta para a prova 223. | Documentar como herdado da 305, ou exigir `completion_ready` para os dois tipos de lore não mecânicos. |

## Correções aplicadas

(nenhuma; revisão só de leitura. Preencher após o executor corrigir P1-1/P1-2.)

## Pendências

- Coordenador: suíte completa 1×, playtest `--all --turns 50`, letalidade SPEC-285 M1/M2/M5
  (seeds 21-32 × 200, `combate`, `RPG_LORE_QUESTS=on`). A medição só vale **depois** de P1-1,
  porque antes dele nenhuma caça conclui e a pressão de caça não aparece.
- Smoke real §6: o passo 1 (caça) teria falhado em "combate na região com a âncora → concluída"
  por causa de P1-1.
- D8: o dono revisa `delivery_routes` antes de ligar `on` no staging. D9: staging em `shadow`
  até o smoke.
- Desvio §8.2 R11 (rumores do menu = rumores percebidos pelo jogador na região do NPC, não os
  que o NPC conhece): aceito para v1. O template `npc` ("{origem} jura que é assim") atribui o
  rumor ao NPC; vale reavaliar na 315.

## Comandos rodados

```text
git diff ab3950e2...spec-313 --stat → 33 arquivos, +4211/-465
bash scripts/dev/py.sh <comparação de chaves EVENTS main×branch> → só adiciona lore_quests.fallback
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec313_*.py tests/test_spec305_{events,lifecycle,perception,review,sources,surfaces}.py tests/test_spec304_{agenda,perils,review}.py tests/test_spec312_{review,proposed}.py tests/test_log_event_registry.py → 222 passed, exit 0
uv run --no-sync ruff format --check <arquivos alterados> → observability/events.py would be reformatted (1 arquivo)
uv run --no-sync ruff check <arquivos .py alterados> → All checks passed
```
