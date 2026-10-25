# SPEC-311 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-10-25 · **Commit revisado:** `fda7ad88` (branch `spec-311`, base `f24a72ea`)

## Escopo

`git diff f24a72ea...spec-311` (19 arquivos): `agents/{campaign_manager,loot,npc,storyteller}.py`,
`services/{economy,lore_query,planner_context,context_builder,context_sources,perceived_world}.py`,
`rag.py`, `data/world/region_lore_tags.json`, `observability/events.py`, testes
`tests/test_spec311_*.py`, spec §8. Fora: smoke real §6 (opt-in do coordenador), suíte completa,
perfil hosted real (sem `tags` no `memory_store`, R21 é no-op — já registrado na §8).

Conferido contra os requisitos:

- **Regra de ouro no planner (R1-R5).** `_planner_world_blocks` (`agents/campaign_manager.py:138-159`)
  só lê `perceived_world_block(audience="planning")`, `heard_block(world)` e
  `planner_quests_block(state)`. Nenhum acesso a `world_sim.pressures/bands/crises/tension`.
  `perceived_world` (309) filtra crises por região atual + `event_perceived`; linha de estado só do
  local atual. Bloco vazio não deixa linha nem instrução. Guard `try/except` + `log_fallback`.
- **Gatilho (R6-R9).** `world_replan_cause` (`services/planner_context.py:50-76`) lê só
  `perceived` e `wq_events`; crise/queda exigem `region_id == region_of(atual)` (D1). `perceived_items`
  vem de `_perceive_world`, que só devolve itens com `days_ticked` e modo `on` — o item sai do
  `pending_digest` ao ser percebido, então não há disparo repetido. Somado a `travel_needs_replan`
  antes do encontro (`agents/storyteller.py:1119-1122`), portanto vale na emboscada (`:1238`), no
  caminho feliz e no fallback (`:2082-2083`). Log com enum fechado, registrado em `EVENTS`.
- **Preço (R10-R16).** Ordem dos fatores idêntica à `price()` antiga (supply → mercador → relação
  → hostil → estado/festa → patente → venda), multiplicação sequencial. **Validei a matriz de
  caracterização contra o `services/economy.py` de `f24a72ea`** (módulo antigo injetado via plugin
  pytest): `test_price_characterization_matrix` passa com o código antigo, ou seja os inteiros
  esperados são de fato o comportamento anterior. Motivos: limiar 0,05, `venda` excluído, teto 3,
  ordenação `(-|log m|, code)`, frases da tabela §3.3, fação só nomeada se `known`, rota sem causa.
  Loot só acrescenta a linha ao `context` (`"cite no máximo um"`); `[SISTEMA]`/`observe`/validador
  intocados. `<SEU_COMERCIO>` não sobrepõe `<SOBRE_VOCE>` (310: `services/npc_self.py` não fala de
  comércio/preço).
- **RAG (R17-R25).** Query composta só com local atual/região/rótulo público/estação/mês + input
  ≤ 300. Reordenação aplicada **depois** do filtro de visibilidade nos três caminhos (legacy
  `similarity_search` → `visiveis`; `query_faiss_evidence(max_visibility=…)`; hosted
  `MemoryQuery(max_visibility=…)`); `query_faiss_evidence` intocado; `LORE_K=3`; fatiamento da lore
  em `assemble_pack` preserva o prefixo `lore_content_` e o primeiro chunk sobrevive à cota curta.
- **Compat.** Sem campo novo em `GameState`/save, sem `with_structured_output` novo, sem chamada LLM
  nova (testes de contagem de `invoke`), `evals/` intocado, nenhum segredo em log.

## Achados

Sem P0/P1.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/lore_query.py:95-114`, `data/world/region_lore_tags.json:4` | Cruzamento com SPEC-314: as páginas de fação secreta são `visibility: public`. A faixa 0 da reordenação **promove** duas delas na própria região: `cultistas_destilacao.md` (tag `Aethelgard`) em `aethelgard` e `druidas_renegados.md` (tag `Pântano`, que bate no alias curado `pantano`) em `pantano_melancolia`. Junto com `LORE_K` 2→3, isso aumenta a chance de o trecho do plano secreto entrar em `<LORE_PUBLICO_CANONICO>`/lore do narrador quando o herói está nessas regiões. `filhos_chama_azul` e `mao_sombria` não são afetadas. A causa raiz (visibilidade) é da 314. | Não bloquear a 311. Registrar na SPEC-314 como agravante e incluir nos testes dela o caso "herói em `pantano_melancolia`/`aethelgard` pergunta da fação". Alternativa barata se a 314 demorar: excluir `type: faction` com fação secreta da faixa 0. |
| P2-2 | P2 | `services/economy.py:334-347`, `agents/npc.py:639-672` | No `<SEU_COMERCIO>` o motivo `relacao` sai em 3ª pessoa no prompt do **próprio** keeper ("Brynja desconfia de você e ouviu falar mal de você por aqui") e repete o que o `<ATITUDE>` da 298 já diz (tier + fama). Não é vazamento, mas é redundante e pode soar estranho ao LLM. | Follow-up: no bloco do keeper, omitir `relacao` (o `<ATITUDE>` já cobre) ou trocar por frase em 2ª pessoa ("você cobra conforme o que pensa do herói"). |
| P2-3 | P2 | `agents/storyteller.py:1238` | O retorno antecipado de emboscada carrega `travel_needs_replan` (correto por construção, o gatilho é calculado em `:1119`), mas nenhum teste cobre esse caminho (o executor já sinalizou). | Acrescentar um teste com encontro forçado + `world_replan_cause` monkeypatched → `needs_replan is True`. |
| P2-4 | P2 | `tests/test_spec311_planner.py:93-101,248-259` | O oráculo §3.6(1) substitui `build_context_pack` por um stub (`<W/>`), então o `world_state_block` real do pack `planning` (que vê arestas `hidden`, risco anterior fora de escopo) não é exercitado contra "Brekmar/sitiada". O que a 311 adicionou está coberto; a frase "as mensagens do planner não contêm…" da spec fica mais forte do que o teste prova. | Follow-up: uma variante do oráculo com o pack real (MockLLM, motor `on`, `event_log` com `location_state_changed` não percebido em Brekmar). |
| P2-5 | P2 | `agents/campaign_manager.py:146-155`, `services/planner_context.py:29-41` | Orçamento: só `<MUNDO_PERCEBIDO>` tem teto de tokens. `<OUVIU_DIZER>` (3 notícias) e `<QUESTS_DO_HEROI>` (6 linhas, títulos sem corte) não têm, e a instrução R4 (~60 tokens) entra quase sempre porque a linha de estação aparece com calendário `on`. Pior caso estimado ~300-350 tokens, acima dos ~250 da §7. | Medir no smoke §6; se passar, cortar título em ~80 chars ou aplicar `estimate_tokens` ao conjunto. |
| P2-6 | P2 | `agents/npc.py:1023-1025` | A query do NPC usa `base = "{nome} {local} {fala}"` e `compose_lore_query` já prefixa o nome do local; a deduplicação é por parte inteira, então o local entra duas vezes na query (peso extra no embedding). Inofensivo, só diluição. | Opcional: tirar `{local}` do `base` do NPC (a spec R18 manda manter; ajustar a spec junto). |

## Correções aplicadas

Nenhuma (revisão sem P0/P1).

## Pendências

- P2-1 → SPEC-314 (coordenador anexa como agravante).
- P2-2, P2-3, P2-4, P2-5, P2-6 → follow-ups da 311 (podem entrar antes do pouso, sem bloquear).
- R21 hosted no-op até o `memory_store` gravar `tags` (já registrado na §8).
- Smoke real §6 pendente (coordenador).

## Comandos rodados

```text
git diff f24a72ea...spec-311 --stat → 19 arquivos, +2465/-87
pytest -n 2 tests/test_spec311_*.py + 309/310/context/economia/loot/replan (20 arquivos) → exit 0 (281 passed)
pytest -n 2 test_fase28/61/44/31/0, spec303_passes, spec301_perks, spec302_effects_factions, grounding, resumo_budget, world_rejection_logs, turn_pipeline_concurrency, transicoes_b1, balance_early, mvp → exit 0
pytest -p <plugin que injeta services/economy.py de f24a72ea> test_price_characterization_matrix → PASSED (matriz = comportamento antigo); test_price_equals_product_of_factors → falha esperada (sem price_factors no módulo antigo)
script ad hoc: tags das 4 páginas de fação secreta × region_lore_tags → cultistas_destilacao→aethelgard, druidas_renegados→pantano_melancolia
```
