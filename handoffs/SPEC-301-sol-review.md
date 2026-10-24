# SPEC-301 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / papel Sol (revisão independente) · **Data:** 2026-10-24 · **Commit revisado:** `7bfe743d`

## Escopo

Revisei a branch `spec-301` contra o merge-base `e9127c4e` (commits `47fce843..7bfe743d`, 37 arquivos,
+5363/-49). Li o diff de `services/faction_membership.py`, `services/faction_missions.py`,
`services/event_processor.py`, `services/world_engine.py`, `world_utils.py`, `agents/storyteller.py`,
`agents/npc.py`, `services/world_validators.py`, `services/quest_log.py`, `services/economy.py`,
`services/npc_knowledge.py`, `services/chronicle.py`, `services/context_builder.py`, `api.py`,
`persistence.py`, `state.py`, `mock_llm.py`, `playtest/invariants.py` e
`data/faction_membership.json` (o catálogo inteiro). Ficou fora: a UI (`Hud.tsx`/`types.ts`) por
leitura superficial, o perfil `faccionario` (não rodei o playtest) e a interação com 299/300, que já
estão na `main` e não entram neste diff.

Pontos de foco que conferem:
- **LLM só propõe.** `membership_action` passa por `apply_intent` no storyteller e no `npc_actor`. O
  guard usa `isinstance(..., MembershipAction)`, o storyteller ignora o campo em quarentena, e o
  validador rejeita `faction_membership_changed` com `source != "engine"`. O LLM não consegue preencher
  `source`.
- **Regra de ouro.** A pendência `rival_awareness` só é aplicada na chegada à região do rival, num
  local controlado por ele ou quando um NPC do rival ouviu o evento (`RPG_NPC_KNOWLEDGE=on`). Fação
  secreta não propaga (`is_secret_event` em `npc_knowledge`/`context_builder`). `standing_label` vem de
  um enum fechado, e a API e o prompt não mostram mérito, influência nem pendências.
- **Catálogo.** Mercadores de Escravos estão `nao`. Devoradores de Sol estão `condicional`, com
  `origins_allowed: ["deserto_zhur"]`. `MAX_MEMBERSHIPS = 2` conta todos os status abertos, inclusive a
  secreta e o rito pendente. O Kahen limita quem não é Sangromante ao índice 1. O lint dá 0 erros.
- **Contra-jogo.** Influência fica em ±9. `effective_pace` trunca rumo a 0 com piso 0. Com influência 0
  o comportamento é o de antes: `test_fase2`/`27`/`34` e `test_bug_contabilidade_recompensas` passam sem
  edição. No modo `on`, `world_engine` (passo 6) usa `effective_pace` e decai 1 por dia. O
  `advance_factions` legado só roda com `_engine_owns_factions()` falso. `_push_progress` satura em 99.
- **Traição telegrafada.** A 1ª ofensa marca `suspeito` com aviso. A 2ª dentro de 5 dias vira
  `traidor`. `check_expulsion` roda depois das ofensas.
- **Persistência.** O round-trip de `faction_membership`, `influence`, `influence_periods` e dos campos
  novos de `Quest` está coberto, e o save antigo carrega `{}`.
- **Proteções.** Nada em `evals/` nem em `web/e2e`. Nenhum segredo em log.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/faction_missions.py:88-126`, `services/faction_membership.py:993` | **XP/ouro ilimitados com missões de fação.** `offer_mission` não tem cooldown. Quando `fresh` esvazia, cai em `rng.choice(pool)` e repete templates já concluídos. `_ask_mission` não exige local. Um template cujo `location_id` é o local atual (ex.: `legiao_quota_ferro` em `na_anel_ferro`, o QG) já recebe `location_reached` no turno da criação (`storyteller.py:1674`). Simulei 8 missões seguidas no **mesmo dia de jogo**, 5 delas sem sair do QG. Resultado: 250 de ouro, 8 × `XP_PER_QUEST` (200), mais mérito, `progress` e influência a cada ciclo de cerca de 3 turnos, sem o relógio andar. A sabotagem pelo mesmo laço zera o `progress` de um rival a partir de um ponto fixo. A spec (§7) só fecha o farm de ascensão; o de XP e ouro fica aberto. | Limitar a 1 missão por fação por dia de jogo, com um campo `last_mission_day` no `MembershipRecord` (gravado no `offer_mission`) e um motivo de recusa `missao_recente` com texto narrável. Opcionalmente, excluir templates cujo único local é o local atual. Teste: duas chamadas a `ask_mission` no mesmo `world_clock.day` → a 2ª é recusada e o estado não muda. Com o dia seguinte → oferece. Registrar o desvio na spec. |
| P1-2 | P1 | `playtest/invariants.py:2064` | **Falso positivo de nível `error` no modo padrão.** `faction.progress_le_99_outside_tick` marca qualquer fação com `progress >= 100` que não esteja `completed`/`defeated`. Com `RPG_WORLD_ENGINE=on` (default), o tick da 302 leva o `progress` a 100 por conta própria (`world_engine._tick_day`, `min(100, …)`). A ascensão, porém, espera o aviso, `MIN_WARNING_DAYS` e `_try_open`, e uma fação sem região nunca ascende. Ela fica legitimamente em 100 sem `completed`, e o invariante dispara `error` toda vez. Isso quebra o `llm_playtest` e campanhas longas, que exigem 0 `error`. Os 50 turnos do `faccionario` não chegaram a esse estado. | Checar a transição em vez do estado: `prev.progress < 100 <= progress` com o `world_clock.day` inalterado (nenhum tick nesse turno) e o `progress` subindo além do que o pace explica. Alternativa mínima: exigir `progress > 99` só nos turnos sem virada de dia. Teste com um estado de engine `on` em 100 aguardando o aviso → 0 violações. |
| P2-1 | P2 | `agents/storyteller.py:836` | Com o motor `on` (default e staging), `faction_events` fica sempre `[]`, porque só o `advance_factions` legado o preenche. Por isso `ascension_member_note` nunca produz a linha `[FAÇÃO]` de R19 quando a fação do jogador ascende. O ramo `dissolved` funciona, porque compara `defeated`. | Derivar os eventos de ascensão comparando `completed` entre `state["factions"]` e `factions` depois do tick, como já se faz com `_was_defeated`, e passar essa lista para `ascension_member_note`. Teste com o motor `on`. |
| P2-2 | P2 | `services/faction_membership.py:813-832` | R16 diz "entrar **ou ser promovido** em fação pública gera `rival_awareness`". `_try_promote` não chama `_queue_rival_awareness`. Hoje só a entrada pública e a traição enfileiram. | Chamar `_queue_rival_awareness(work, fid, -1)` na promoção de fação `secret=false`, ou registrar o desvio na spec, já que o delta é sempre −1 e a pendência é idempotente. |
| P2-3 | P2 | `services/event_processor.py:575-578`, `faction_membership.py:715` | `check_expulsion` expulsa no mesmo turno da ofensa quando a reputação cruza −40. Exemplo: um membro `ativo` em −35 mata alguém da fação (−12): vira `suspeito` e logo `expulso`, sem aviso. A traição continua telegrafada; a expulsão não precisa ser. A regra já está nos desvios, mas não diz isso. | Documentar na spec que a expulsão por limiar hostil não tem aviso prévio, ou só expulsar quem já estava `suspeito` antes deste lote. |
| P2-4 | P2 | `specs/SPEC-301-faccoes-patentes.md:629` | O critério de aceite cita `handoffs/SPEC-301-review.md`; a revisão está em `handoffs/SPEC-301-sol-review.md`. O smoke real da §6 e o caso Playwright (bloqueado por `web/e2e/contracts` protegido) seguem pendentes. | Atualizar o nome no critério. O smoke §6 fica para antes do `done`. |

## Correções aplicadas

P1-1, P1-2, P2-1..P2-4 corrigidos pelo executor (ver 'Revisão Sol' em Desvios da spec; testes em tests/test_spec301_missoes.py e test_spec301_persistencia.py). Pendente de re-revisão.

## Pendências

- P1-1 e P1-2 bloqueiam o pouso. P2-1..P2-4 podem virar follow-up na própria 301 antes do `done`.
- Smoke real da §6 (DeepSeek), para validar o mapeamento de `membership_action` no provider real.
- Coordenador, no pouso: criar a entrada `faction_membership` em `project_index/state_ownership.yaml`
  (§3.5).

## Comandos rodados

```text
git diff e9127c4e...HEAD --stat → 37 arquivos, +5363/-49
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec301_*.py tests/test_spec302_*.py tests/test_spec298_*.py tests/test_fase2.py tests/test_fase27.py tests/test_fase34.py tests/test_bug_contabilidade_recompensas.py → 440 passed, exit 0
bash scripts/dev/py.sh scripts/validate_content.py → 0 erros, 0 avisos ([faction_membership] OK)
git diff e9127c4e...HEAD -- tests/test_fase2.py tests/test_fase27.py tests/test_bug_contabilidade_recompensas.py evals/ web/e2e → vazio
scratchpad/farm301.py (offer_mission ×8 no mesmo dia, QG da Legião) → 8 missões aceitas, 250 de ouro, 5 sem sair do QG
```
