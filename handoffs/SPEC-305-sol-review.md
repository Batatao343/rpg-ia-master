# SPEC-305 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / Sol (subagente independente, não escreveu o código) · **Data:** 2026-10-24 · **Commit revisado:** `956599bd`

## Escopo

Branch `spec-305` (worktree `rpg-spec-305`), `git diff main...HEAD`: 31 arquivos (+3428/−56).
Lidos: `services/world_quests.py` (inteiro), diffs de `quest_log`, `event_processor`,
`world_validators`, `structured_outputs`, `world_director`, `world_engine`, `world_pressures`,
`reputation`, `pressures.json`, `state.py`, `agents/{storyteller,turn_finalizer,combat}.py`,
`api.py`, `playtest/invariants.py`, `web/src/{types.ts,components/QuestsTab.tsx,styles.css}`,
`tests/test_spec305_*.py`. Fora: smoke real §6 e letalidade SPEC-285 medida (pendências do
coordenador já declaradas na §11 da spec); `playtest/report.py`/`telemetry.py` só por leitura rápida.

Confirmado OK:
- **Regra de ouro (1):** `_resolve_channel` só cria quest com item percebido (testemunho/cartaz),
  testemunho direto (estar na estrada fechada) ou `location_heard[local atual]` com a 215 `on`
  (rumor/NPC). Sem percepção, nada nasce (teste `test_unperceived_crisis_creates_no_quest`).
  API usa lista branca (`public_quest_view`): `deadline_day`, `world_source_id`, `heard_via`,
  `origin_faction_id`, `fail_reason`, `world_kind` não saem. Rótulo vago, sem número; prompt
  e `<GANCHO_NOVO>` sem número de dia. `fail_text` dos 9 tipos é neutro.
- **(2)** Só `world_quests.py` monta `world_kind` (teste AST). `quest_failed` exige
  `source ∈ {system, engine}`; `world_quest_relief` sempre rejeitado como proposta. O LLM não
  controla `source` (`ProposedWorldEvent` não tem o campo; storyteller grava `"storyteller"`).
  Validador de `quest_failed` exige quest ativa: duas falhas (órfão + motor) não acontecem.
- **(3)** `relieve` só marca `relieved_day`; `step_crises` não escala aliviada e fecha com
  `intervencao`; teto/cooldown/anúncio do diretor intactos (a crise aliviada continua ocupando a
  vaga até fechar). Puro e determinístico. Falha só emite `quest_failed`; extras por tabela
  (`pressures.json`: `fome +6` em rota; consolidação de ocupação em `apply_event`). D8: uma quest
  por `world_source_id`, qualquer status; quests não são podadas, então não há reoferta.
- **(4)** `combat_won`: 1 por turno, só no alvo, só após `location_reached`, nunca no turno de
  criação, só tipos com `combat_counts`, `not is_simulation`. Conclusão é única (status sai de
  `active`), alívio não dá XP/ouro. Sem farm.
- **(5)** 301: `wq_base` parte de `fm_extra["quests"]`; `register_proposed_quests` recebe
  `wq_quests`; `kind="faccao"` por `mission_kind`. 298: `deed_info` cai em `origin_faction_id`
  sem trocar `origin_npc`. 374 testes de 301/302/fase33/34/proof/305 verdes.
- **(6)** `mode()` só fica `on`/`shadow` com `RPG_WORLD_ENGINE=on`; `off` → `_offer`/
  `sync_deadlines`/`engine_completions` não fazem nada e o storyteller sai cedo;
  `sync_action_progress` não muda para quem não tem quest de mundo.
- **(7)** `npx tsc --noEmit` limpo. Não há teste node que cubra `QuestsTab`.
- **(8)** Combate: o único efeito novo é anexar `combat_won` ao `progress_log` quando já existe
  quest de mundo; nenhum número de combate muda. Letalidade inalterada pelo código.
- Nenhum `with_structured_output` novo; sem segredo em log; logs `world_quest.*` sem ids de crise;
  `evals/` não foi tocado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/quest_log.py:553-570`; `web/src/components/QuestsTab.tsx:4-8` | **Vazamento do desfecho pelo status público.** `public_quest_view` repassa `status` cru. Quest de mundo que falhou mostra "Fracassada" + selo "prazo esgotado"; a que expirou no prazo porque a fonte acabou sozinha (R16, 2º item, **sem** percepção) mostra "Prazo esgotado". O jogador distingue "a crise se resolveu sozinha" de "a crise seguiu/escalou" sem ter percebido nada. A R21 diz explicitamente que o status público dos dois tem que ser o mesmo "para não revelar se a fonte acabou sozinha". O teste `test_failed_and_expired_same_public_label` só confere o `deadline_label`, não o `status`. | Para quest com `world_kind` e status `failed`/`expired`, projetar um status público único (ex.: `"expired"` → "Prazo esgotado") em `public_quest_view`; manter `failed` cru só para quest comum ou de fação. Teste: `failed` e `expired` de mundo dão o mesmo dict público, exceto id/título/descrição. |
| P1-2 | P1 | `agents/storyteller.py:1808-1815` (ordem da fila), `services/world_validators.py:76-82` (`_v_quest_completed`), `agents/storyteller.py:1277` (`_quests_ativas_block(wq_quests)`) | **Conclusão aceita depois do prazo, no turno do vencimento.** No turno em que o dia chega a `deadline_day`, `sync_deadlines` só **enfileira** `quest_failed`; a quest continua `active` em `wq_quests`, aparece no prompt como "urgente · prova: ok" e a fila do archivist processa `pending_llm_events` **antes** de `extra_engine_events`. Um `quest_completed` proposto pelo LLM (prova feita em turnos anteriores; ex.: descansar no alvo até o dia vencer) é aceito primeiro: XP, ouro, feito da 298 e `world_quest_relief`. O `quest_failed` do motor é rejeitado em seguida (a quest já não está ativa). Para crises, a escalada do dia `e` já rodou dentro de `advance_days`; o resultado é quest concluída **e** crise escalada, e o alívio ainda trava as escaladas seguintes. Isso quebra a R11 ("`location_reached` no alvo **antes** do prazo") e a R16. A prova (`_quest_proof`) não olha `deadline_day`. | Duas defesas, as duas determinísticas: (a) em `_v_quest_completed` (ou em `_quest_proof`), rejeitar quest com `world_kind` quando `clock.day >= deadline_day` e `source != "engine"`; (b) no storyteller, tirar do bloco `QUESTS_ATIVAS` as quests que têm `quest_failed` na fila deste turno, ou aplicar `fail_quest` direto em `wq_quests` e manter o evento só como registro. Teste: dia vira para `deadline_day` com prova pronta e o LLM propõe `quest_completed` → `failed`, sem XP e sem `world_quest_relief`. |
| P2-1 | P2 | `playtest/invariants.py:2194` | `quest.world_unheard` aceita, nos canais testemunho/cartaz/mensageiro, qualquer `event_id` presente no `event_log` (`ref in logged`). Todo evento do motor está no log, então o invariante não prova percepção nesses canais (R6). | Exigir `ref in perceived_ids`; deixar `logged` só para o testemunho direto de rota/objeto, ou gravar esses ids também no livro-razão `perceived_ids`. |
| P2-2 | P2 | `services/world_director.py:380-396` | Crise aliviada cuja pressão não cai abaixo de `RECUPERA` (causa diária persistente, como cerco → fome) nunca escala e também nunca fecha: fica aberta, ocupa a vaga da região e mantém o `loc_state`. Isso segue a letra da R13, mas pode congelar a região. | Follow-up: TTL de crise aliviada (ex.: fechar com `intervencao` após N dias) ou medir no playtest `mundo` antes de ligar no staging. |
| P2-3 | P2 | `tests/test_spec305_events.py:105` | Writer persistente novo (campos de `Quest`, `WorldSimState.perceived_ids`, `CrisisRecord.relieved_day`, `location_states[*].liberation_day/consolidated_until_day`) sem round-trip `save_game_state → load_game_state`. Há só o load de save antigo. `persistence` copia esses blocos inteiros, então provavelmente funciona, mas falta a prova. | Teste de round-trip com uma quest de mundo completa + `world_sim` com `relieved_day`/`perceived_ids`. |
| P2-4 | P2 | `services/reputation.py:496` | R14 (feito da 298 via `origin_faction_id`) sem teste. | Teste: conclusão de quest de mundo com `origin_faction_id` de fação do grafo gera o feito `quest_completed`; sem fação, só XP e ouro. |
| P2-5 | P2 | `services/structured_outputs.py:60-63` | `quest_failed`/`world_quest_relief` entram no `EventType` que o LLM vê no schema. Se o LLM propuser um deles, a quarentena atômica descarta o payload livre inteiro da resposta. O padrão é o mesmo de `faction_membership_changed` (301). | Opcional: tirar os tipos engine-only do schema que o LLM recebe, ou registrar a taxa de rejeição `engine_only` no smoke §6. |
| P2-6 | P2 | `agents/turn_finalizer.py:78` | Em `shadow`, `offer_from_heard` não roda, então rumor/NPC nunca gera `world_quest.shadow_offer`. O shadow do staging subconta as ofertas. | Chamar com `mode() in ("on", "shadow")` (o `_offer` já não grava nada em shadow). |

## Correções aplicadas

(nenhuma; aguarda o executor)

## Pendências

- P1-1 e P1-2 bloqueiam o pouso; depois, re-revisão focada nesses dois.
- P2-1..P2-6: podem ir no mesmo commit da correção ou virar follow-up registrado na spec.
- Já declaradas pelo executor: smoke real §6, medição de letalidade SPEC-285 com as duas flags
  `on`, `resgate` dormente até a SPEC-304, `recuperar_objeto` dormente (nenhum emissor grava
  holder de fação).

## Comandos rodados

```text
git diff main...HEAD --stat → 31 files, +3428/-56
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec305_*.py tests/test_spec301_*.py tests/test_spec302_*.py tests/test_fase33.py tests/test_fase34.py tests/test_world_event_proof.py → 374 passed (exit 0)
cd web && npx tsc --noEmit → sem erros
git diff main...HEAD --stat -- evals/ → vazio
```
