# SPEC-206 — handoff de autoria de eval (corpus novo `player_knowledge`)

O implementador NÃO criou dataset, evaluator, registry nem lock (evals/ é protegido).
Autoria em tarefa separada, revisada por Astra, com relock no manifesto. Os datasets
da SPEC-171 (`evals/datasets/regression/narrative_npc.jsonl`) não são tocados.

## Superfície sob teste

`services.player_knowledge.project_player_knowledge(state, raw)` (via
`services.discovery.player_codex(state)` / `GET /game/codex`) e o oráculo
`services.player_knowledge.assert_no_player_leak(codex, state) -> list[str]`.
Entrada do caso = save sintético (dict GameState mínimo); saída = JSON do Codex.

## Casos mínimos (§9 da spec)

1. Entidade `hidden` sem reveal (ex.: `world.visited` com
   `mon_verme_primordial_das_raizes_do_mundo`) → entrada ausente; `meta.counts` exclui.
2. Reveal por evento: `event_log` com `secret_revealed` (target real) + `revealed_facts`
   → entrada `secrets` com `knowledge_kind=fact`, `source_ref=event:<id>`.
   Atenção: o nome do Verme é assinatura do segredo `rei_subterraneo`; revelar só a
   entidade mantém a entrada omitida (R6). Caso positivo exige também
   `secret_revealed` de `mon_rei_subterraneo`.
3. Reveal só por prosa (`narrative_summary`) e por `player.known_secrets` → continua
   omitido (deve falhar o reveal).
4. Relato repetido: N `MemoryFact` `npc_claim` iguais de fontes distintas → nunca `fact`.
5. Legado: `memory_facts` com string → `report` / `speculative` / "Relato não verificado".
6. Bestiário `seen` só → `rumor`; com `fought ≥ 1` → `fact`.
7. NPC `knowledge_source` mentioned → `rumor`; met → `fact`; lore → `report`.
8. Facção `known` sem `knows_goal` → `report`, `goal=""`; com `knows_goal` e
   `intel_turn` < turno → `report` + `stale=true`.
9. Nota sem âncora visível (`canonical_entity_ids` vazio ou só entidade oculta) → ausente.
10. Assinatura em nota (ex.: "pacto com Valerius") → texto substituído pelo
    `PUBLIC_RUMOR`, `meta.redactions ≥ 1`; assinatura em `goal`/`body` → entrada omitida.
11. Contagem vs lista: `meta.counts[c] == len(codex[c])` para as 5 categorias.
12. `canonical_event` com `source_id` não aplicável → `suspicion` / `inference`.

## Métricas

- `leak_count` = nº de casos com `assert_no_player_leak != []` → hard gate `= 0`.
- `kind_accuracy` = acerto de `knowledge_kind` por entrada/nota esperada.
- `count_consistency` = 1.0 (ramo (c) do oráculo).

## Expected

Fixture-authored, por caso: conjunto de ids/nomes por categoria, `knowledge_kind`
esperado por `source_ref`, `meta.redactions` mínimo. Zero LLM/provider.
