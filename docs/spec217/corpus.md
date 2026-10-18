# SPEC-217 — corpora DEV e FROZEN (autoria de eval)

Autorados sem chamada live. Local: `evals/experiments/data/` (fora de `evals/datasets/regression/`, régua protegida; não há registro/relock de governança, como o corpus da SPEC-179). Verificador: `uv run python evals/experiments/spec217_corpus_check.py` (exit 0 = ok).

| Corpus | Casos | Rotas esperadas | SHA-256 do JSONL (LF, UTF-8) |
|---|---|---|---|
| DEV | 59 (21 regressão `routing_actions` + 14 SPEC-179 + 24 sintéticos) | storyteller 14, combat_agent 11, npc_actor 21, loot 13 | `256d24bd53a8eda63daf0d6cd15d413ddd2c844b5f57771df8753ce6e5305f3d` |
| FROZEN | 21 (16 elegíveis + 5 gate Python) | elegíveis: npc_actor 6, storyteller 5, loot 3, combat_agent 2; gate: combat_agent 1, storyteller 4 | `442725e5dca9be7ed71c9abaa730cc7b61fd15180a04d4a290545794621d9d48` |

- DEV: 7 casos com `python_gate=true`, 8 com `critical=combat_escalation`; 27 `kind=target`, 32 `kind=route`.
- Desvio documentado: `routing_actions.jsonl` tem 25 linhas, mas só 21 são `operation=route` (as 4 de `action_contracts` são normalização/parse de decisão, sem rota). Entram as 21. Nos 3 casos `npc_actor` herdados a fixture ganhou o ID canônico `npc_corvo_rapido` e o alvo passou de nome para ID. Casos `unknown`/`unrepresentable` da SPEC-179 viram `target=null`; `loot.none` vira `storyteller`. `npc_sombra` (SPEC-179, segredo) é fixture sintética intencionalmente fora do grafo.
- FROZEN: mix dos 16 elegíveis pelo campo `mix` = npc_actor 5 (5 com alvo), storyteller 4, loot 3, combat_agent 2, ambiguous 2 (`critical=combat_escalation`); `priority` 1..16 intercalando as rotas, para que qualquer prefixo mantenha a mistura. 5 casos de gate (0 chamadas), `priority=null`. 5 casos com >1 NPC em cena, 2 com alvo por alias. NPCs, inimigos e locais disjuntos do DEV; toda fixture tem `world.current_location_id` próprio.
- Seed de redução (se a estrutura da J1 exigir menos casos): seleção determinística pelas `priority` crescentes, sem ler conteúdo (a ordem já preserva o mix).
- Não-sobreposição verificada: id, ação normalizada, distância de edição ≤ 3, mesmo template (nomes de NPC/inimigo/local mascarados) e fixture idêntica + mesma rota. Também verificado: hash, LF, alvo entre candidatos visíveis, IDs de NPC públicos no grafo, contagens do handoff §4 e `python_gate` contra o router real (sonda offline, `get_llm` bloqueado).
- Saída do verificador: `OK: hashes, schema, targets, frozen counts, non-overlap and gate probe`.
- Commit de congelamento: o commit que introduz `spec217_frozen.jsonl` (`git log --format=%H -1 -- evals/experiments/data/spec217_frozen.jsonl`).

**FROZEN selado:** o executor da J1 NÃO deve abrir `spec217_frozen.jsonl` (só hash, contagem e prioridades acima). O verificador lê o arquivo mas é ferramenta do autor/revisor, não da J1.
