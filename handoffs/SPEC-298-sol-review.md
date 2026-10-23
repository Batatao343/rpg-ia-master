# SPEC-298 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, revisão independente) · **Data:** 2026-10-23 · **Commit revisado:** `be0ec2dc`

## Escopo

Branch `spec-298`, `main...HEAD` (commits `77692c7`, `8444af6`, `be0ec2d`; 47 arquivos). O foco
foram os 7 pontos pedidos pelo coordenador: regra de ouro e superfície sem números,
`faction_deed`, economia do keeper, intimidar/sondar/favores e guards, testes antigos
adaptados, desvio do R23 e migração. Li o diff de `services/reputation.py` (inteiro),
`services/economy.py`, `world_utils.py`, `services/world_validators.py`,
`services/event_processor.py`, `services/npc_knowledge.py`, `services/npc_layers.py`,
`services/dossiers.py`, `services/dossier_visibility.py`, `agents/{npc,router,storyteller,turn_finalizer}.py`,
`api.py`, `persistence.py`, `playtest/invariants.py`, `web/src/types.ts` e `DossierDetail.tsx`.
Ficaram fora: o CSS/HUD em detalhe, os e2e do `web/` (não rodei) e o smoke real do §6, que
ainda não foi executado.

O que está correto:
- **Superfície sem números.** `relationship`, `reputation`, `history[].value` e
  `disposition_label` saíram de `_npcs_block`/`visible_npc_view`, `_factions_block`, dossiês e
  tipos TS. O grep no produto só acha `relationship` em `audit_trace` (interno) e no prólogo
  (escrita). O oráculo cobre `format_response` e `build_dossiers`.
- **`faction_deed`.** É rejeitado sem `source="storyteller"`. O schema de proposta do LLM não
  tem `source`, então uma proposta livre cai na quarentena. Os cues foram removidos e não sobrou
  chamador antigo de `apply_reputation`. A reputação não se move antes do aceite, e
  `_revert_reputation` foi removido.
- **Guards.** `RouterDecision.social_approach`/`favor_kind` e `FactionImpact` têm
  `field_validator(mode="before")` que nunca derruba a resposta. `NPCSchema.race_id` é validado
  no uso. `_resolve_social` fica em `try/except`. O teste FallbackLLM do router e do NPC existe.
- **Economia.** É determinística e não tem lucro infinito no mesmo mercador. A compra tem piso
  de 0,75 × base. A venda é `SELL_FACTOR` 0,5 × `1/fator_compra`, com teto de 1,333 sem clamp,
  ou seja, no máximo ≈ 0,667 × base, abaixo do piso de compra. O empréstimo tem cooldown de 3
  dias e o código `debt_open` bloqueia um novo enquanto a dívida existe, inclusive vencida.
- **Testes antigos.** As adaptações preservam a intenção e não afrouxam asserts:
  - `test_bug_contabilidade` passou a provar que a reputação "nunca muda antes do aceite" e o
    valor tabelado 4 no aceite.
  - `test_grounding` agora faz o monkeypatch em `world_utils.apply_reputation`, que é o ponto
    real usado por `_apply_faction`.
  - `test_fase34` passou a afirmar que não há números.
  - `test_fase2` explicita o delta.
- **Desvio do R23.** O teto de linhas vale só para NPC com `relationship_basis`. É aceitável: o
  dataset `npc_knowledge` é protegido, o desvio está registrado na spec, e o clamp de
  `faction_reveals` vale para todos. O follow-up com relock fica abaixo.
- **Migração.** Os campos novos são aditivos, `ensure_reputation_fields` é idempotente no load,
  NPCs existentes não recalculam a relação e não há bump de schema.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/reputation.py:728-731` (+ `:565-577`) | `process_deeds` aplica o delta de fação **no mesmo turno** quando `faction_in_scene` é verdadeiro. Esse critério inclui "há quest ativa cuja origem é membro da fação". Exemplo: o jogador ajuda a Legião longe de qualquer membro e de território da Legião, mas tem uma quest ativa dada pelo Thrace. A Legião muda de opinião na hora e o jogador recebe o aviso "vai lembrar disso". Isso fura o R12 (só aplica na hora se a fação **testemunhou**, ou seja, controla o local ou tem membro presente; senão vira pendência) e a regra de ouro. O critério de quest é só de **aceite** no R11. | No ramo "aplica agora", usar só `faction_witnessed(...)`. Com quest e sem testemunha, seguir para pendência (modo `on`) ou nada (modo `off`). Teste: `faction_deed` aceito via quest ativa, sem membro presente e sem controle → reputação inalterada e `reputation_pending` com 1 entrada no modo `on`. |
| P1-2 | P1 | `services/reputation.py:547-562` (uso em `:728`) | No `npc_killed`, a própria **vítima** conta como "membro presente". `faction_witnessed` roda antes de `apply_npc_death` (`event_processor`, bloco `killed_targets`), então a vítima ainda está viva em `npcs`. Matar o único membro presente faz a fação saber na hora. A fama já exclui a vítima (`_present_witnesses(state, victim)`), mas a fação não: a regra de ouro fica inconsistente entre as duas camadas. | Passar `exclude_id=info.get("victim")` para `faction_witnessed` e ignorar esse NPC; com o controlador do local, a fação continua testemunhando. Teste: matar membro sozinho, sem controle local → pendência (`on`) e reputação inalterada. Ajustar `test_npc_killed_por_player_gera_delta`, que hoje depende da vítima como testemunha: pôr um segundo membro presente ou o controle do local. |
| P1-3 | P1 | `services/reputation.py:1026-1041`, `services/economy.py:320-323`, `:518` | O keeper (R17) vira registro em `state.npcs` por **mutação in place** do dict de entrada (`npcs[name] = row`, via o `{**state, "world": world}` raso do `execute_trade`). Nem `execute_trade` nem `loot_node` devolvem `npcs` no update parcial. A persistência depende de aliasing do canal do LangGraph (frágil, fora da convenção de que o nó devolve um dict parcial), e não há round-trip save/load pelo caminho real. Se não persistir, o keeper é recriado virtualmente a cada visita. Consequência: a relação com ele nunca evolui, e um `npc_actor` com o mesmo nome geraria um NPC novo pelo LLM. | `ensure_keeper` deve devolver a linha. `execute_trade` (e `merchant_stock` no caminho de transação) deve incluir `npcs` no `TradeOutcome`, e `loot_node` propagá-lo como update parcial, sem mutar o estado de entrada. Teste: comprar com `app.invoke`/`loot_node` → `save_game_state` → `load_game_state` → keeper presente com `relationship_basis` e `keeper_of`. |
| P2-1 | P2 | `services/reputation.py:626`, `:862` | `_apply_faction` sempre empurra "X vai lembrar disso." em `factions[*].recent_changes`, inclusive quando a pendência é entregue **longe** do jogador (`_deliver_pending`). `recent_changes` sai no `_factions_block` e no dossiê, então o jogador "ouve" uma mudança que o R26 manda não avisar. | Só chamar `_push_recent` quando o aviso de fação for emitido (testemunhou neste turno e `faction_intel.known`). Uma flag `emit_notice` em `_apply_faction` resolve. |
| P2-2 | P2 | `services/reputation.py:1291-1319` | O aviso de dívida vencida ("X cobra a dívida atrasada.") é emitido mesmo com o NPC fora de cena. O R26 restringe aviso de NPC a NPC conhecido e presente. | Emitir o aviso só se `is_in_scene(row)` e o NPC é conhecido. Se não, só `recent_changes`, ou adiar o aviso até o próximo encontro. |
| P2-3 | P2 | `services/reputation.py:557-561` | `faction_witnessed` herda de `is_in_scene` a regra "`in_scene` ausente = presente" e aceita `home_location_id` vazio. NPC legado de fação, sem esses campos, "testemunha" qualquer feito em qualquer local, e o validador de `faction_deed` aceita fora de cena. | Para fins de testemunha, exigir `in_scene is True` explícito e `home == loc`, ou que o local atual do NPC seja o atual. Alternativa: `ensure_reputation_fields` normaliza o `home_location_id` de NPCs legados. |
| P2-4 | P2 | `services/content_validator.py` (R7) | A spec pede lint também de `merchants.json.keeper` (`npc_id` existente no grafo, ou `name`/`role` com `race_id` válido). Só `race_attitudes` foi coberto. | Adicionar `validate_merchant_keepers()` em `validate_all`. |
| P2-5 | P2 | `tests/test_spec298_migracao.py:44-53` | O round-trip cobre só `location_fame` e `reputation_pending`. Ficam sem round-trip `npcs[*].favors` (`debt`/`intercession`), `heard_deeds`, `relationship_basis`, `recent_changes`, `world.shelter` e `factions[*].knows_player`/`recent_changes`, que passam por `coalesce_runtime_npcs`. | Estender o teste `save_game_state` → `load_game_state` com esses campos. |
| P2-6 | P2 | `tests/test_spec298_visibilidade.py:107-110` | `test_avisos_regras_de_emissao` só testa o filtro por turno, não as três regras do R26 (NPC presente, fação conhecida e testemunhada, fama só no local). | Cobrir os três casos, ou renomear e apontar para os testes de fama/fação que cobrem parte deles. |
| P2-7 | P2 | `services/reputation.py:1188` | `emprestar` soma ouro sem `clamp_gold`. `pay_debt` usa. | Usar `clamp_gold(player, gold + LOAN_AMOUNT)`. |

## Correções aplicadas

Nenhuma ainda: o executor corrige P1-1, P1-2 e P1-3, e os P2 que forem baratos, e reenvia.

## Pendências

- **Follow-up de eval, com relock** (`EVAL_AUTHORING_REQUIRED`, dono: coordenador): estender o
  teto do R23 a todo NPC e atualizar o dataset `npc_knowledge` protegido.
- **Smoke real do §6** (dono: coordenador). Ajustar o roteiro ao desvio registrado: a recusa
  −2 vem de NPC Elfo ou Cinzéu contra jogador Anão. Registrar em `handoffs/SPEC-298-smoke.md`.
- **Arbitragem entre locais** (não é regressão; P2 para a SPEC de economia). Comprar barato
  onde o item é produzido (×0,6) e vender caro a keeper `leal`/ganancioso em outro local
  (×1,33 × 0,5) já dava margem antes; o fator de venda > 1 a amplia. Calibrar no playtest
  (`[BALANCEAR]`).
- **Toast dos avisos no chat** não implementado (registrado na spec). Fica como follow-up de UI.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec298_*.py tests/test_fase2.py tests/test_fase34.py tests/test_bug_contabilidade_recompensas.py tests/test_grounding_boundaries.py tests/test_router_interlocutor.py tests/test_dossiers.py tests/test_npc_knowledge.py tests/test_npc_camadas.py → verde (~301 testes, 0 falhas)
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n auto tests -k "npc or reputation or economy or router or merchant or comerciante or faction or dossier or persistence or save" → 610 passed, 2 skipped (exit 0)
```
