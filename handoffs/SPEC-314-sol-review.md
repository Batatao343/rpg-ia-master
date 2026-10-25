# SPEC-314 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, revisão independente) · **Data:** 2026-10-25 · **Commit revisado:** `0a43591a` (sobre `81d76cd6`, base `main` `1ddb9a46`)

## Escopo

Branch `spec-314`, `git diff main...spec-314` (16 arquivos): `services/faction_gate.py` (novo),
`agents/npc.py`, `rag.py`, `services/context_builder.py`, `services/context_sources.py`,
`services/lore_query.py`, `services/lore_quests.py`, `services/npc_self.py`, telemetria, fixture
`tests/fixtures/spec215_npc_pack_off.txt` e os 4 arquivos de teste novos. Também conferi quem mais
consome nome/plano de fação: `npc_knowledge`, `archivist`, `chronicle`, `economy`, `world_engine`,
`world_director`, `campaign_manager`, `rumors` (312), `lore_quests` (313) e `dossiers`/`discovery`.
Fora do escopo: smoke §6 com LLM real e a suíte completa (fica com o coordenador).

O gate do bloco `<FACÇÕES_DO_MUNDO>` (R1–R8), as propostas estruturadas (R9–R12), o filtro de lore
(R13), a falha fechada (R16/R17) e a telemetria (R18) estão corretos e cobertos por testes. Os dois
P1 abaixo são vazamentos de **nome** que ainda chegam ao prompt do LLM pelo pack, no mesmo tipo de
fato que o R14 mascara. Os dois se corrigem com uma linha cada.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/npc_knowledge.py:280` (usado em `services/context_builder.py:817-822` e `services/npc_self.py:399`) | `_subject_text` chama `render_event(ev, projection)` **sem `state`**, então o R14 não age. Com `RPG_NPC_KNOWLEDGE=on` (ligado no staging), as linhas `[VIU]/[OUVIU DE …]` que o gate de conhecimento põe no pack levam o nome da fação secreta ignota. `faction_relation_changed` é testemunhável (`SUBJECT_PARAMS` 0.7; a origem cai no local atual) e o motor o emite para qualquer par (`world_engine.py:364-376`). Reproduzido: `_subject_text` → "Relação de A Mão Sombria mudou (enemy_of) com A Legião de Ferro."; o mesmo evento com `state` → "uma facção desconhecida". O R19 só roda com o conhecimento `off` (`tests/test_spec314_no_leak.py:27`). | Passar `state` adiante: `render_event(ev, projection, state)` em `_subject_text`. Acrescentar ao R19 uma variante com `RPG_NPC_KNOWLEDGE=on` e um link `observed_by` para um `faction_relation_changed` com fação secreta. |
| P1-2 | P1 | `services/context_builder.py:430` | A linha "Quem controla {local} agora: {controller}." usa `_name(controller)` sem máscara. O evento `location_control_changed` é mascarado (R14), mas o mesmo fato vaza por esta linha. É alcançável: `world_director._attacker` (`:257-273`) não exclui fação secreta, e `_occupy` (`:632-640`) grava a aresta dinâmica `controls`. Reproduzido com a aresta `filhos_chama_azul —controls→ na_anel_ferro` e `purpose="npc"`: "Quem controla Anel de Ferro agora: Os Filhos da Chama Azul." (a seção `relations` do mesmo pack já mostra "uma facção desconhecida —controls→ Anel de Ferro"). | Fora do `planning` (`not include_hidden`), passar `controller` por `faction_gate.display_if_faction(state, controller, _name(controller))`. Teste de regressão com essa aresta. |
| P2-1 | P2 | `services/faction_gate.py:89-103`, `services/lore_quests.py:419-423` | `mask_secret_names` só pega o nome inteiro e o nome sem artigo. Rótulos reais da 313 passam sem máscara: "Iniciado da Chama Azul", "Cultista da Destilação", "Druida-Renegado", "Faísca da Destilação" (só "Degolador da Mão Sombria" é mascarado). O `anchor_id` vai cru (`enemy_degolador_mao_sombria`, `enemy_iniciado_chama_azul`), com o nome dentro do slug. A frase do §9(c), "o nome não aparece em NENHUM ponto do prompt", vale só para o cenário de teste. | Escolher um: (a) tirar do menu a caça de criatura ligada a fação secreta ignota; ou (b) aceitar que o nome da criatura é público (ele já aparece no combate) e corrigir o §9(c) na spec. Se ficar com a máscara, casar também pelos termos-núcleo ("Chama Azul", "Destilação", "Renegad"). |
| P2-2 | P2 | `data/codex/npcs/npc_pardal.md:24`, `data/codex/rumors/story_rumores_nova_arcadia.md:69-73`, `data/codex/monsters/mon_mao_sombria_agentes.md` | Páginas `public` do Codex que não são a página da fação também nomeiam as fações secretas. O R13 só filtra `metadata.id == fid`. A página da Pardal diz "Mão Sombria (para quem trabalha)": o RAG do NPC pode desfazer o alias `sua_irmandade` (R5) da própria Pardal. O plano não vaza por aqui (as `perspectivas` com o plano são `hidden`). | Follow-up de conteúdo: curar os trechos "Para o narrador:" de membros de fação secreta (ex.: via `codex_overrides`), ou incluir no `exclude_ids` a página do próprio NPC quando ele está no alias. Registrar na spec que o sigilo de nome não é garantido pelo lore. |
| P2-3 | P2 | `agents/archivist.py:210`, `services/chronicle.py:146` | O `render_event` sem `state` também grava em `memory_facts` (que voltam ao pack pela memória de sessão) e na crônica e no HUD (o jogador vê) o nome do ocupante secreto ou das partes da relação. | Decisão do dono: (a) ocupar um local torna a fação `known` (o jogador vê quem ocupa); ou (b) mascarar no momento da gravação (passar `state`). Hoje o comportamento é incoerente com o P1-2. |
| P2-4 | P2 | `agents/campaign_manager.py:174-211`, `services/secret_signatures.py:122-130`, `agents/storyteller.py:1499` | O planner recebe a página da fação secreta com o plano (D4, fora de escopo por decisão) e enxerga as arestas sem máscara. Os beats vão ao prompt do narrador. O `sanitize_beat` só procura assinaturas do catálogo de segredos, não o `goal` de fação. É a via de **plano** que sobra. | Follow-up barato e determinístico: o `sanitize_beat` também troca o beat que contiver termos do `goal` de fação secreta sem `knows_goal`. Pode entrar na SPEC-315 ou numa spec curta. |
| P2-5 | P2 | `rag.py:1149-1160`, `rag.py:996-1014` | No caminho hosted (pgvector), o filtro depende de `metadata.id` nos documentos de lore. Os testes usam stubs. | No smoke §6 em perfil hosted, ou com uma consulta ao staging, confirmar que um chunk de `filhos_chama_azul` some com `knows_goal` falso. |

### Respostas aos focos do coordenador

1. **Nome/plano em prompts:** o plano está fechado no NPC, no narrador, no combate, no `world_simulator`, em 312 e em 313. Resta só a via planner→beats (P2-4). O nome ainda vaza por P1-1, P1-2 (pack) e P2-1/P2-2/P2-3. `economy` (`controlador_hostil` checa `known`), `npc_self` (`:309` pula secreta ignota), `faction_membership._display_name` (recusa) e `dossiers`/`discovery` (goal só com `knows_goal`) estão OK.
2. **Filtro de RAG:** `_drop_excluded` roda antes do `rerank_by_region` e do corte em K nos três caminhos (hosted texto, hosted/FAISS vetor, FAISS texto). O desvio da "assinatura antiga" só afeta dublês de teste: nenhum código de produção troca `cb.query_rag` (grep). O adapter de eval `evals/core/adapters.py:1060` usa `**k` e recebe o filtro. Não é buraco em produção.
3. **Alias / `resolve_proposed_id` / `cap_reveal`:** está correto. Um id fora do bloco é descartado e gera `faction_id_not_visible`. O alias com faixa < leal descarta a revelação (`anon`). Uma linha sem plano limita a `existencia`. O join via alias da Pardal chega a `apply_intent("join","mao_sombria")` e o `can_join` continua sendo o gate. A proposta não volta ao prompt, então não serve para descobrir o nome. Observação (não é achado): abrir o rito revela o nome (`faction_membership.py:623`), o que bate com D3 ("a entrada revela").
4. **Audiência planning:** o prompt vai ao LLM (SMART) e pode virar beat narrado (ver P2-4). Por design (D4), mas falta o sanitizador.
5. **D2:** confere com a spec (`_other_plan_allowed`: secreta + `known` + faixa amistoso/leal + `fid ∈ rivals(own)`; unidirecional pelo catálogo de `own`). Na tabela 4×3×2 do R19, legião × {chama_azul, mão} em `leal` libera o plano. O R13 continua redigindo o lore nesse caso. É fail-closed e coerente, porque a revelação grava `knows_goal` e o lore só abre depois.
6. **Save antigo:** `_intel_row` aceita `None`, lista ou não-dict → `{}`. Nenhuma secreta é listada, o lore é redigido e nada é gravado. OK.
7. **Fixture:** `tests/fixtures/spec215_npc_pack_off.txt` não está em `evals/protected-paths.txt`, e o diff não toca `evals/`. A mudança é só a máscara das arestas. OK.
8. **Desempenho:** `collect_dynamic_facts` (npc) leva ~3,9 ms/turno; `npc_faction_view` + `redacted_lore_ids` ~0,19 ms; `mask_secret_names` ~0,42 ms/item. Os catálogos estão em cache (`lru_cache` / cache de módulo). Desprezível.

## Correções aplicadas

P1-1, P1-2, P2-1, P2-2, P2-3, P2-4 corrigidos no commit seguinte a `0a43591a` (testes em `tests/test_spec314_review_fixes.py` e `test_spec314_no_leak.py`). P2-5 fica para o smoke §6.

## Pendências

- P2-1 e P2-2: decidir se o **nome** da fação secreta é segredo de verdade, dado que o conteúdo público (bestiário, rumores, Codex) já o cita. Recomendo garantir o plano (atendido) e tratar o nome como "melhor esforço" no bloco e nos eventos. Dono / coordenador.
- P2-3: dono decide se a ocupação torna a fação `known`.
- P2-4: sanitizador de beats para `goal` de fação (SPEC-315 ou spec curta).
- P2-5: no smoke §6.
- §5: suíte completa e smoke §6 continuam abertos (coordenador).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec314_{faction_gate,lore_events,no_leak,npc_proposals}.py → exit 0 (50 testes)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec310_no_leak.py tests/test_spec310_npc_prompt.py tests/test_spec310_npc_self.py tests/test_context_npc_gate.py tests/test_context_sources_concurrency.py tests/test_npc_knowledge.py tests/test_spec301_llm.py tests/test_spec301_entrada.py tests/test_spec298_visibilidade.py tests/test_spec298_faccao_eventos.py tests/test_spec311_lore_query.py tests/test_spec313_offer.py tests/test_spec313_hunt.py tests/test_spec312_knowledge.py → exit 0
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_eval_npc_knowledge.py tests/test_context_identity.py → exit 0
py.sh -c (npc_knowledge._subject_text vs render_event com state) → nome cru vs "uma facção desconhecida" (P1-1)
py.sh -c (collect_dynamic_facts purpose=npc, aresta controls de filhos_chama_azul) → "Quem controla Anel de Ferro agora: Os Filhos da Chama Azul." (P1-2)
py.sh -c (mask_secret_names em rótulos reais do bestiário) → 4 de 5 sem máscara (P2-1)
py.sh -c (timing) → facts 3.93 ms, view+redact 0.19 ms, mask 0.42 ms/item
```
