# SPEC-315 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (independente, não escreveu o código) · **Data:** 2026-10-25 · **Commit revisado:** `f1a37de1` (branch `spec-315`, rebased em `main` `0149bdce` com SPEC-314)

## Escopo

`git diff main...spec-315` (22 arquivos, +2356/-15): `services/rumor_adoption.py` (novo),
`services/rumors.py`, `services/structured_outputs.py`, `services/exploration.py`,
`services/npc_world.py`, `world_utils.py`, `services/lore_quests.py`, `agents/storyteller.py`,
`playtest/{invariants,telemetry,report,scenarios}.py`, `observability/events.py`, config,
spec (incl. §10 desvios D-1..D-8) e os 5 arquivos `tests/test_spec315_*`. Fora: smoke real §6
(não rodado pelo executor), `evals/` (não tocado).

Pontos verificados e OK: falso/não adotado/shadow nunca chega a materializador
(`due_materialization` filtra `adopted`+`truth`+janela; `mark_materialized` é writer único e
idempotente; a instância e o `materialized_day` persistem em `world_sim`); achado só via
`grant_rumor_cache` → `roll_loot(boost=False)`, único re-sorteado/recusado, ouro ≤ 40,
`item_perdido` só item, alvo entra em `looted_locations`; o schema não tem campo de
quantidade/item/ouro; `rumor_hint` antes do cooldown e só na viagem (descanso seguro intacto);
`schedule_visit` → `_step_visit` usa `_start_trip` (viagem real), líder bloqueado
(`is_leader`), fuga/perigo/status cancelam; verdade = `day_rng(... "rumor_adopt:"+id)`, uma vez, e
`truth_p` não lê `player`; quarentena barra antes de `_apply_proposal`; `claim` só no schema com a
flag (`_story_schema_for_rumors`); guard de FallbackLLM (`getattr(update, "proposed_rumors")`);
desfecho 313 via `outcome_of`/`resolve_outcome` + `mark_resolved`; exceção do
`rumor.became_fact` restrita a `truth && materialized_day`; `_faction_hidden` agora importa o
`services.faction_gate` real (`is_secret`/`known_to_player` existem).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/storyteller.py:858` (+ `services/rumor_adoption.py:132-137`, `:278-282`) | **R8/D3 (anti-direção) morto no caminho real.** `pst = {**state, **updates, ...}` e `updates["messages"]` é `[AIMessage(narrativa)]` (montado em `:2059-2061`), então `_recent_player_inputs` não acha nenhum `HumanMessage` e `player_steered` nunca dispara. Prova (sonda): `validate_claim` direto → `player_steered`; o mesmo estado via `stt._apply_proposed_rumors` → `adopted=True truth=True`. O jogador pode "encomendar" o tesouro digitando o local. O teste `test_player_steered_loot_rejected` só chama `validate_claim` isolado. | Em `_apply_proposed_rumors`, preservar o histórico do jogador: `pst = {**state, **updates, "world": world, "messages": state.get("messages") or []}` (ou passar os inputs explicitamente). Teste de integração pelo `_apply_proposed_rumors` com `updates["messages"]=[AIMessage]` e o nome do local nos inputs → instância **não** adotada. |
| P1-2 | P1 | `services/rumor_adoption.py:302-311` × `services/rumors.py:315-323` | **Teto de achado (R13/D6, 1 a cada 20 dias) vaza.** `_budget_reason` procura o achado verdadeiro anterior no ledger, mas `_cap_ledger` resolve a adotada ao expirar (`_expire_adopted`) e, com `resolution` setada, a linha deixa de ser "investigável" e cai após `STALE_PERCEIVED_DAYS=3`. Sonda: achado verdadeiro nascido no dia 1 (TTL 10) → no dia 16 o ledger está vazio e `_budget_reason(esconderijo)` devolve `""` (aceita), 15 dias depois. A janela efetiva é ~TTL+4, não 20. O mesmo vale para o invariante `loot_over_cap` (`playtest/invariants.py`, janela calculada só sobre o ledger). `LOOT_TRUE_PER_WINDOW` nem é lido. | Persistir os dias dos achados verdadeiros fora do ledger (ex.: `world_sim["adopt_loot_true_log"]`, teto pequeno, gravado em `_apply_proposal` quando `adopted && truth && kind∈LOOT`) e usar `LOOT_TRUE_PER_WINDOW`; idem no invariante. Teste: achado no dia 1, `_cap_ledger` no dia 16, nova alegação de achado no dia 16 → `budget`; round-trip da chave nova. |
| P1-3 | P1 | `tests/test_spec315_claim.py:162-175` | **Teste vermelho após o rebase.** `test_secret_faction_gate` falha (`'' == 'secret'`): mocka o fallback (`npc_self._faction_is_secret/_faction_known`), mas com a 314 na `main` o adapter usa `services.faction_gate` de verdade. A suíte do pouso fica vermelha e o R7 deixa de ter cobertura do caminho real. | Mockar `faction_gate.is_secret` / `faction_gate.known_to_player` (ou usar uma fação secreta real do catálogo + `faction_intel`). |
| P2-1 | P2 | `services/rumor_adoption.py:109-122` | O fallback `except ImportError` chama `npc_self._faction_is_secret`, que hoje importa `faction_gate` — caminho morto/circular. | Com a 314 na `main`, remover o `try/except` e chamar `faction_gate` direto (atualizar D-7). |
| P2-2 | P2 | `agents/storyteller.py:2320-2330` | Exceção do LLM no turno do achado: `fallback` leva `player` e `world_sim` (rumor marcado), mas `world` só se `dest`/descanso → `looted_locations` do alvo se perde; e a nota aparece como "O boato era VERDADE: em X o jogador ENCONTROU…" (3ª pessoa, caixa alta; `_player_facing_note` não tem regra para ela). | Incluir `world` no fallback quando houve achado de rumor; adicionar regex diegético para a nota. |
| P2-3 | P2 | `services/rumor_adoption.py:69-72` | `rumor_adopt.{proposed,rejected,adopted,shadow,materialized}` saem pelo wrapper `_log` e escapam do scanner do catálogo: só `expired_unmaterialized` está em `observability/events.py`/`EVENTOS_DE_LOG.md`. | Chamar `log_event("rumor_adopt", "<literal>", ...)` direto (ou registrar manualmente) e regenerar o catálogo. |
| P2-4 | P2 | spec §10 D-5; `agents/router.py:411` | **Gap LOOT real, mas não de correção.** O router dá "Vasculhar…" como exemplo de LOOT/TREASURE; o `loot_node` não chama `due_materialization`. Como o `loot_node` não grava `looted_locations`, a alegação **não** é invalidada: só exige uma ação STORY depois, com verbo de busca (ou quest ativa). Na prática, parte das alegações verdadeiras vai expirar `inconclusivo`. | Follow-up: gancho no `loot_node` (TREASURE) ou medir no smoke §6 a taxa de `expired_unmaterialized` de achados; se alta, ligar o gancho. |
| P2-5 | P2 | `services/rumor_adoption.py:478-497`, `:524-525` | `npc_em_local` só materializa se o NPC já está lá **no turno da viagem** do herói; se o NPC chegar depois com o herói parado no local, expira `inconclusivo` mesmo estando presente. Invariante `npc_teleport` só checa `location_id && arrive_day`, não um salto de posição entre turnos. | Aceitar gatilho "presença" (herói no alvo e `present_here`) em qualquer turno STORY; invariante comparar `prev`→atual sem viagem. |
| P2-6 | P2 | `services/rumor_adoption.py:376-382` | `world_sim["forced_adopt"]` (só do harness) é lido no caminho de produção e sobrepõe a verdade. Não é gravável pela LLM, mas é um override persistente. | Guardar por flag de playtest (como o padrão `npc_sim["forced"]` deveria) ou documentar no R24. |

## Correções aplicadas

Nenhuma ainda (revisão sobre `f1a37de1`).

## Pendências

- P1-1..P1-3 bloqueiam o pouso; após corrigir, re-rodar os testes de escopo e esta revisão (delta).
- P2-1..P2-6: aceitáveis como follow-up registrados na spec, exceto P2-4, que deve ser medido no smoke real §6 (ainda não rodado; necessário para `done`).
- Default `shadow` confirmado: valida, sorteia e loga; não grava `claim`/`adopted`/`adopt_log` nem agenda NPC — nada visível ao jogador além do boato da 312 (o prompt do narrador ganha o bloco `<BOATOS_ALEGACAO>`, esperado em shadow).

## Comandos rodados

```text
git diff main...HEAD --stat → 22 arquivos, +2356/-15
py.sh -m pytest tests/test_spec315_{claim,truth,materialize,property,resolution}.py tests/test_log_event_registry.py tests/test_spec312_proposed.py tests/test_spec312_review.py tests/test_spec304_agenda.py (serial) → 158 passed, 1 failed (test_secret_faction_gate), exit=1
py.sh -m pytest tests/test_spec313_rumor.py tests/test_spec313_offer.py tests/test_spec312_{playtest,birth,narration}.py (serial) → todos passed, exit=0
sonda scratchpad/r315/probe315.py → validate_claim direto: player_steered; via _apply_proposed_rumors: adopted=True (P1-1)
sonda scratchpad/r315/probe_budget.py → dia 16 antes do _cap_ledger: budget; depois: '' (P1-2)
```
