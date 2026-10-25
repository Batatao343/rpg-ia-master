# SPEC-312 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer independente; não escreveu o código) · **Data:** 2026-10-25 · **Commit revisado:** `98fd37fa` (branch `spec-312`, `cc03d53c` + `98fd37fa` sobre `07eb5b10`, base `005017e4`)

## Escopo

`git diff 005017e4...spec-312` (36 arquivos, +6639/−70): `services/rumors.py` (novo), gerador
`scripts/build_rumor_seeds.py` + `data/world/rumor_*.json`, integração em `world_engine`,
`world_perception`, `ambient`, `storyteller`, `world_simulator`, `npc_knowledge`, `npc_world`,
`world_quests`, `perceived_world`, `structured_outputs`, `api.py`, `state.py`, playtest
(invariantes/telemetria/relatório), simulador `--s312`, web (selo). Fora do escopo: smoke real (§6,
não executado), relock do eval `npc_knowledge`, rebase sobre a SPEC-310 (a `main` mudou
`npc_knowledge.npc_knowledge_block`; conflito textual pequeno e compatível, porque a 310 consome
`knowledge_lines`, que já rotula `rumor` como `[BOATO]`).

Foco pedido, com o resultado de cada ponto:
1. **Boato falso nunca vira fato:** verificado. `rumors.py` não escreve `event_log`,
   `pending_world_events`, `world_projection`, `memory_facts`, `quests` nem pressões (teste AST
   `test_rumor_module_never_writes_…`). `day_memory_facts` (309) exclui rumor
   (`services/perceived_world.py:181-186`); `world_quests._item_matches` e `npc_world.on_perceived`
   descartam `kind="rumor"`; no modo `on` a prosa `[ECOS DO MUNDO]` não volta para `world.news`
   (só no ramo `off`, `agents/storyteller.py:1369`). O ledger da 215 grava `rumor` só como
   `told_to` e sempre rotula `[BOATO, não confirmado]`. Resta o caminho pré-existente da
   prosa → arquivista (LLM) → `memory_facts`, que a spec aceita no §7 e o invariante
   `rumor.became_fact` vigia.
2. **Verdade fora de prompt/API/news:** verificado. `news_extra` leva só
   `kind/rumor_id/expires_day`; a API devolve só `kind ∈ {noticia, boato}` (`api.py:2935-2940`) e
   filtra os expirados; `heard_block` não usa `rumor_id`; `narrate_day` recebe `BOATO:` com texto
   de template. `truth` só existe em `world_sim.rumors` (privado).
3. **Regra de ouro:** canal (a) regional habitado / família do local de nascimento, canal (b)
   `location_heard` só com 215 `on`. Teto de 1 por dia mais o intervalo global
   `RUMOR_MIN_GAP_DAYS=2`; o excedente fica no digest dentro do TTL. A propagação entre NPCs é só
   `told_to`.
4. **Interface da 313:** `mark_resolved` é o único writer de `resolution`. É idempotente: rumor
   já resolvido ou desfecho inválido não mudam nada. Devolve um `world_sim` novo e
   `investigable` não expõe `truth`. Há uma fragilidade de vida útil (P2-3).
5. **Save/tamanho:** chaves aditivas. Round-trip manual por `persistence.save_game_state`/
   `load_game_state` preserva `rumors`, `rumor_seed_last_born` (com `NEVER_AGAIN`) e os campos de
   `news`, mas não existe teste versionado (P2-4). A margem do S6 é frágil (P2-5).
6. **`ProposedRumor`:** guarda ok. `getattr(update, "proposed_rumors", None)` dentro de `try`
   (`agents/storyteller.py:775-798`); o coerce descarta itens inválidos; o default é `off` e a
   flag é dupla (`proposed_mode` e `mode`). Porém o campo vai no schema mesmo com `off` (P2-1).
7. **Determinismo:** só `world_engine.day_rng(game_id, day, "rumors")`, sempre 2 sorteios por
   região, candidatas ordenadas por id, template por `sha256(rumor_id)`; teste AST sem `random`
   global. Verificado.
8. **Visibilidade da tabela:** as 40 sementes `lore` vêm de `lore_nova/rumors.txt`, que já é
   `visibility: public` no Codex (13/13 arquivos em `data/codex/rumors/`). Logo não há texto
   `hidden/secret` novo nos prompts. Mas nenhuma das 40 casa assinatura secreta
   (`find_strict_unrevealed`): o bloqueio R8 está inerte, e algumas `truth`/`quest_eligible`
   tocam segredo (P2-2).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `agents/storyteller.py:141-153`, `:1632`; spec §10 D-7 | O D-7 diz que a instrução de `ProposedRumor` "só entra na chamada se o modo estiver `on`". Falso: o campo faz parte de `StoryUpdate` e vai no schema de toda chamada do narrador (`with_structured_output(StoryUpdate)`). Com `RPG_RUMORS_PROPOSED=off`, o provider ainda vê a instrução e pode preencher o campo (descartado), o que custa tokens em todo turno e pode mudar a prosa. O MockLLM não mostra isso. | Ou corrigir o D-7 (registrar o custo e medir no smoke §6.3), ou montar o modelo sem o campo quando `proposed_mode() != "on"` (ex.: subclasse `StoryUpdateWithRumors` escolhida em `:1632`). |
| P2-2 | P2 | `data/world/rumor_seed_overrides.json:36` (`rumor_a_vibora_e_uma_crianca`), `:4` (`rumor_valerius_nao_come_nem_dorme`), `:114` (`rumor_grum_guarda_algo…`), `:44`, `:99`; `services/rumors.py:201`, `:733` | (a) `vibora_e_uma_crianca` tem `truth=true`, mas `lore_nova/secrets.txt:43-44` diz "A Víbora é Velha Magda": a verdade contradiz o cânone. A semente cita `mao_sombria`, uma das 4 fações `secret` da SPEC-314. (b) `valerius_nao_come_nem_dorme` (`truth=true`, `quest_eligible=true`) é exatamente o "SEGREDO FUNDAMENTAL" (`secrets.txt:9-12`: "nunca dormir, nunca precisar comer"); `grum_guarda…` aponta para o documento do herdeiro (`secrets.txt:70`). Na 313, um desfecho "confirmado" dessas sementes revela o segredo por fora do gate de revelação. (c) O filtro de segredo (R8 e `investigable`) não pega nenhuma das 40: a proteção esperada pela spec (§7, "podem casar assinatura secreta") não existe na prática. | Na leitura do dono (D1): Víbora → `truth=false`; marcar `quest_eligible=false` nas sementes cuja confirmação implica segredo (Valerius come/dorme, Grum barril, Cego não humano, Homem de Cinza; avaliar Valerius conhece nomes). Na 313, gate extra: entidade fação secreta (`faction_gate.is_secret`, SPEC-314) sem `intel.known` → fora de `investigable`. Teste de dados que falha se semente `quest_eligible` cita fação secreta ou NPC com segredo. |
| P2-3 | P2 | `services/rumors.py:248-249`, `:261-273`, `:752-755` | Vida útil curta para a 313: a instância percebida sai do ledger 3 dias depois de expirar (`STALE_PERCEIVED_DAYS=3`). Uma quest `investigar_rumor` com prazo além de `expires_day+3` chama `truth_of` e recebe `None`. O cap (`RUMOR_LEDGER_MAX=24`) também pode despejar uma instância expirada e percebida que esteja ligada a quest. O comentário de `:248` ("some 5 dias depois") diverge do valor `0`. | Para a 313: ou a quest guarda a verdade no estado privado da própria quest na oferta, ou `rumors` ganha um marcador `quest_linked` que impede o despejo até `mark_resolved`. Documentar em §3.6. Corrigir o comentário. |
| P2-4 | P2 | `tests/test_spec312_knowledge.py:46` | Writer persistente novo (`world_sim.rumors`, `region_presence`, `rumor_seed_last_born`, campos extras em `world.news`) sem teste de round-trip `save_game_state`/`load_game_state` (o teste existente só cobre `normalize_knowledge`). Sondagem manual do revisor passou. | Adicionar teste: estado com instância + `NEVER_AGAIN` + news de rumor → save → load → igualdade, e save legado sem as chaves carrega. |
| P2-5 | P2 | `data/world/rumor_config.json` (`RUMOR_LEDGER_MAX`, `FREQUENT_WINDOW_DAYS`); `services/rumors.py:256`, `:287-289` | Margem do S6 frágil. 120 d × 30 seeds: viajante **8053 B** (margem de 139 B sobre 8192). Rodei 365 d × 6 seeds: parado **8176 B** (margem de 16 B). `NEVER_AGAIN` acumula até 40 chaves `lore` para sempre; chaves `narrador:<hash>` (uma por proposta aceita, até 1/dia com `PROPOSED=on`) também viram `NEVER_AGAIN` permanente sem uso, porque o narrador nunca renasce da tabela. Qualquer semente nova ou campo novo estoura o S6. | Guardar sementes esgotadas em estrutura compacta (lista de ids curtos/índices ou bitset) e nunca gravar `NEVER_AGAIN` para `narrador:*`. Medir o S6 também em 365 dias. |
| P2-6 | P2 | `services/rumors.py:303-307` | Em `shadow`, o hook ainda grava `region_presence` em `world_sim`; a R30 lista "sem gravar instância, digest, notícia nem ledger". É inofensivo (≤ ~15 chaves). Mas `shadow` não grava `rumor_seed_last_born`, então a telemetria `shadow_born` não tem cooldown e superestima a taxa/diversidade de `on`. | Documentar no §10 e avisar que `shadow_born` não é comparável com `born`; ou simular o cooldown num dict local. |
| P2-7 | P2 | `playtest/telemetry.py:913`; `playtest/invariants.py:2442-2509` | (a) `born` = tamanho do ledger atual (podado), não o total de nascidos na campanha que a R31 pede. (b) A R32 `rumor.truth_leak` cobre só o payload de `_world_block`, não "prompt registrado pelo harness". (c) Os invariantes só enxergam rumores ainda no ledger: um vazamento de `gist` para fato depois do despejo não é detectado. | Contador cumulativo em `perceived_stats` (ex.: `rumors_born`); varrer os prompts capturados pelo harness `--real` atrás de `truth`/`rumor_id`; manter as assinaturas a partir de `load_seeds()` em vez do ledger. |
| P2-8 | P2 | spec §10 D-2/D-9; staging | `FREQUENT_WINDOW_DAYS` 14 → 1 muda a decisão aberta D2 do dono (região frequentada = 14 dias): na prática o canal (b), rumor de outra região chegando por NPC, quase nunca acontece. O D-9 deixa o default `RPG_RUMORS=on` no código; como o staging já tem `RPG_WORLD_ENGINE=on`, um deploy sem `RPG_RUMORS=shadow` no env liga rumores antes da leitura do dono (D1). | Coordenador: pôr `RPG_RUMORS=shadow` no `.env.staging`/Vercel **antes** de deployar esta branch, e levar o D2 (1 vs 14) ao dono junto com o D1. |

Sem P0/P1.

## Correções aplicadas

Nenhuma (revisão só leitura; o executor ainda não respondeu).

## Pendências

- P2-1, P2-4, P2-5, P2-7: executor da 312 (podem ser follow-up antes do `done` ou na 313).
- P2-2, P2-3: pré-requisito da SPEC-313 (`investigar_rumor`) e da leitura do dono (D1).
- P2-8: coordenador (env do staging) e dono (D1/D2).
- Smoke real §6 e relock do eval `npc_knowledge` continuam abertos (já no D-10).

## Comandos rodados

```text
git diff 005017e4...spec-312 --stat → 36 arquivos, +6639/−70
py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec312_{seeds,birth,perception,knowledge,narration,proposed,playtest}.py → exit 0 (82 testes)
py.sh -m pytest -q -p no:cacheprovider -n 2 test_ambient{,_consumers} test_npc_knowledge{,_migration} test_eval_npc_knowledge test_spec302_perception test_spec305_{perception,lifecycle} test_spec309_{day_memory,golden_rule} → exit 0, 0 falhas
py.sh scripts/build_rumor_seeds.py --check → exit 0
ruff check (arquivos tocados) → All checks passed
py.sh docs/spec302/world_engine_sim.py --s312 --days 120 --seeds 30 → reproduz §8 (S6 viajante 8053 B, parado 7423 B)
py.sh docs/spec302/world_engine_sim.py --s312 --days 365 --seeds 6 → S6 parado 8176 B, viajante 6625 B; S2/S3 dentro
sondagem manual save→load (persistence) com rumors/NEVER_AGAIN/news kind → igual
sondagem find_strict_unrevealed nas 40 sementes (título+gist e render) → 0 casam
```
