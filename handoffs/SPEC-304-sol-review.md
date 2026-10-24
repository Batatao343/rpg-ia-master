# SPEC-304 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão de `993ffff3`; a revisão inicial de `993aa7e2` foi `CHANGES_REQUIRED`)
> **Revisor:** Opus / Sol (estado, concorrência) · **Data:** 2026-10-24 · **Commits revisados:** `993aa7e2` (inicial) → `993ffff3` (re-revisão)

## Escopo

Branch `spec-304` (worktree `rpg-spec-304`), commits `9f2c19a0` e `993aa7e2`, diff contra o
merge-base com a `main` (42 arquivos, +5858/−62). Li por inteiro `services/npc_world.py`,
`services/npc_perils.py` e o diff de `agents/storyteller.py`, `services/world_engine.py`,
`world_director.py`, `world_perception.py`, `world_validators.py`, `event_processor.py`,
`npc_layers.py`, `dossiers.py`, `chronicle.py`, `context_builder.py`, `npc_knowledge.py`,
`world_quests.py`, `persistence.py`, `state.py`, `api.py`. Também li os testes de destino e de
crença e a calibração (`docs/spec304/README.md`). Conferi caminhos que existiam antes e que o diff
não tocou: `quest_log.fail_orphan_quests`, `companion_soul.apply_companion_fate`, o bloco
`party` da API, a cascata de `rule_engine` e o caminho de encontro do storyteller.
Ficaram fora: o smoke real §6 (sem chave) e a suíte completa (fica para o `/spec-land`).

O que está correto:
- Telegrama no mesmo dia, com `location_id`, `earliest ≥ opened+2`.
- Perigo maior só mata com percepção ≥ 1 dia antes do prazo e com vaga do diretor. Sem isso, o
  prazo estende e depois `morto` sai do sorteio.
- O mensageiro (canal d) conta como testemunho.
- A recusa `FateNotTelegraphed` vira intervenção.
- O intervalo entre mortes de líder é checado na hora do destino.
- Os 4 tipos engine-only estão no gate `_ENGINE_ONLY_TYPES`; numa sonda com o sim da 302, 20 seeds
  × 120 dias deram 0 eventos inválidos.
- A RNG é seeded e o hook é idempotente por `last_day`.
- Round-trip save/load funciona e save antigo carrega `{}`.
- `off` não muda nada (teste compara contra a execução sem o hook).
- `shadow` grava só `npc_sim_shadow`.
- Os vazamentos de `npcs`/dossiê/contexto/crônica de `npc_killed` e da linha "X: morto" estão
  fechados.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/event_processor.py:607-616` (+ `quest_log.py:423-453`, `dossiers.py:37-41`) | **Vazamento pela quest órfã.** Um `npc_killed` off-screen que o jogador não percebeu ainda roda `fail_orphan_quests` na hora. A quest vira `failed` no `/game/state`. O `quest_failed` derivado não tem `offscreen`, então a crônica grava na hora `A missão "X" fracassou.`. O dossiê do NPC também ganha o encontro "missão fracassada", porque `target_id` = o NPC morto. **Reproduzido:** sonda com o cenário de `test_graph_npc_death_uses_npc_killed_canonical_path` → crônica `A missão "Ajudar Skek" fracassou.`, quest `failed`, `npc_beliefs` vazio. É o mesmo vazamento P8 que a spec fecha, só que por outro caminho. Acontece com perigo **menor** (pode matar sem percepção), ou seja, com qualquer NPC neutro que deu uma quest. | Preferido: no `npc_killed` com `payload.offscreen`, **adiar** `fail_orphan_quests` até o `npc_fate_learned` (morto) desse alvo, ou até a chegada ao local com testemunho. Mínimo aceitável: marcar o `quest_failed` derivado com `offscreen: True` + `cause_event_id`, e fazer `event_hidden_from_player`/crônica/`public_quest_view` tratarem a quest como ativa até `cause_event_id ∈ _known_sources`. Teste-oráculo: estender `test_oracle_no_death_leak_anywhere` para cobrir `quests` + `chronicle` do `/game/state`. |
| P1-2 | P1 | `api.py:2199-2211` (bloco `party`); `services/npc_perils.py:408-418` → `companion_soul.py:975-991` | **Vazamento pelo bloco `party` da API.** `apply_companion_fate` roda no tick e o patch vai direto para `party`/`quests`. Resultado no `/game/state`, antes de qualquer percepção: (a) `capturado` → `party[i].status = "capturado"`, a string literal; (b) `ferido` → `vitalidade` cai pela metade; (c) `morto` → o companheiro some da party e a missão pessoal aparece `failed` na lista de quests. Nos casos (a) e (b) **não há gate de percepção nenhum**: um perigo maior não percebido estende o prazo e depois sorteia um destino não letal, que é aplicado e mostrado. O executor só registrou o caso (c). | Aplicar a crença ao bloco `party`: para um companheiro com destino não percebido (`belief_view` ≠ None pelo `comp_id`), mostrar o status da crença (`em_perigo`/vazio) e a vitalidade do último snapshot visto. Uma opção: guardar `last_seen_vitalidade` em `npc_sim.npcs[cid]`. Para (c), manter uma linha fantasma da party (`status` = crença, `waiting_at`) até o `npc_fate_learned`, e esconder a quest pessoal `failed` do mesmo jeito que na P1-1. Alternativa aceitável, se o coordenador preferir escopo menor: adiar `apply_companion_fate` até a percepção. Mas isso muda o contrato da SPEC-300 e precisa de aval. Teste: oráculo com companheiro `capturado`/`ferido`/`morto` não percebido → o payload `party`+`quests` não difere do pré-destino. |
| P2-1 | P2 | `agents/storyteller.py:1188` | No caminho de encontro (combate na chegada), `updates.update(sim_updates)` roda **depois** de `updates["npcs"] = scene_npcs`. Se o patch do tick tem `npcs` (resgate +1 pela 298, destino de companheiro), ele sobrescreve o `reset_scene` da viagem: quem estava na cena do local anterior continua `in_scene`. O caminho principal (`:1750`) faz na ordem certa (`**sim_updates` primeiro). | Mesclar `sim_updates` antes das chaves do encontro, ou aplicar `reset_scene` sobre o `npcs` do patch. Adicionar um teste. |
| P2-2 | P2 | `services/world_director.py` / `npc_perils.maybe_open` (vaga `npc_perigo`) | **C1 da 302 deriva.** O sim da 302 não mescla `state_patch`, então a 304 nunca mediu C1 com `npc_perigo`. Sonda minha (sim da 302 + merge do patch, 20 seeds × 120 d, sem contar `npc_perigo` em C1): `off` = NA 10 · brekmar 16 · pradaria 10 · pântano 12,5. `on` = NA **9** (abaixo do piso de 10) · brekmar **17** · pradaria 9,5 · pântano 13. São 1–7 vagas `npc_perigo` por seed. C3/C5 seguem verdes. | Follow-up antes de ligar `on` no staging: mesclar `state_patch` em `docs/spec302/world_engine_sim.py`, medir C1 com 304 `on` e decidir com o dono (D2/D4 da 302): o `npc_perigo` não consome `MAX_ACTIVE_CRISES`, ou recalibrar o `surge_p` da 302. |
| P2-3 | P2 | `services/event_processor.py:588-596` (cascata `rule_engine`) | Morte off-screen de líder: os `location_control_changed` derivados entram na hora na crônica ("X tomou o controle de Y") e no contexto do narrador. A morte não aparece em texto, mas a revelação indireta acontece antes da percepção. | Aceitável como fato público do mundo. Para fechar: propagar `offscreen`/`cause_event_id` aos derivados de um `npc_killed` off-screen, e só gravar o milestone quando o jogador perceber (ou passar pelo `world_perception`). |
| P2-4 | P2 | `services/event_processor.py:449-452`; `services/npc_world.py:1232-1239` | `payload.offscreen` é respeitado venha de onde vier. Uma proposta da LLM (`StoryUpdate.payload` é dict aberto) pode marcar `offscreen: true` e assim suprimir o próprio milestone e sumir do contexto. | Respeitar `offscreen` só com `source == "engine"`. Outra opção: o validator remove a chave de propostas que não são do motor. |
| P2-5 | P2 | `services/npc_world.py:667-710`, `agents/storyteller.py:987-1002` | Intervenção, percepção e crença por encontro em pessoa só rodam quando o dia vira, e só com a posição do jogador na hora do tick. Uma visita ao local do perigo dentro do mesmo dia, saindo antes da virada, não conta como intervenção (a R16 diz "chega ao local"). O `perceived_day` é gravado no tick seguinte à percepção: um atraso de 1 dia, conservador. | Registrar os locais visitados no dia (ex.: `world.visited_today`) e usar na intervenção/testemunho. Ou documentar a granularidade diária na spec (§7). |
| P2-6 | P2 | `services/npc_world.py:1128-1131`, `:1224-1229` | `npc_beliefs[ref].source_event_id` é sobrescrito a cada item novo. Um evento já percebido (ex.: o `npc_peril_warning`) volta a ficar oculto no contexto/dossiê quando chega uma crença nova. Esconde informação, não vaza. | Guardar `known_event_ids` (anel limitado) na crença, ou um conjunto global, e usar em `_known_sources`. |
| P2-7 | P2 | vários | (a) A R12 manda usar `companion_soul.companions_exposed`, mas a implementação usa a exposição própria. Registrar o desvio na spec. (b) A R32 pede o perfil `combate` com seeds 21–32 × 200; a evidência cobre só 21–22. (c) O gate engine-only só tem teste para `npc_defected`: parametrizar para os 4 tipos. (d) `npc_knowledge.turn_updates`: o novo `if not origin: continue` muda o comportamento `off` quando `current_location_id` está vazio (antes registrava testemunhas com origem ""). Restringir a eventos off-screen. (e) `_state_to_save_data` grava `npc_sim`/`npc_beliefs` = `{}` também com `off`. É o mesmo precedente da 302, mas o save JSON não fica idêntico byte a byte. | Itens de documentação/teste. Nenhum bloqueia sozinho. |

**`LEADER_DEATH_GAP_DAYS = 60` (desvio da D6, "1 a cada 30").** Aceito. É mais restrito que a
decisão do dono, então o mundo fica menos letal. A checagem fica no destino, não na abertura:
o líder continua recebendo perigo e telegrama, só não morre. E 60 é o mínimo que fecha N3
(≤ 2 mortes de líder em 120 dias; com 30 dias caberiam 4). Ressalva: o N3 medido (máx. 2) bate
exatamente no teto. Registrar a mudança para o dono ver na próxima rodada de decisões.

**Letalidade "0/0" (perfil `combate`, `off` vs `on`).** É coerente: a spec não toca o combate e
`npc_killed` off-screen usa `actor_id="world"` (R19, com teste). A amostra é pequena (P2-7b).

## Correções aplicadas

O executor corrigiu tudo em `993ffff3` (com `tests/test_spec304_review.py`). Re-revisão do delta
`993aa7e2..993ffff3` (10 arquivos, +475/−25):

| ID | Situação | Como foi conferido |
|---|---|---|
| P1-1 | **Fechado** | `event_processor.py:620-626`: `fail_orphan_quests` só roda com `npc_killed` on-screen ou com `npc_fate_learned` de `morto`. **Sonda refeita:** a mesma morte de Skek não percebida não muda `quests` e não grava nada na crônica; `public_quests` = `active`. Depois de perceber o item `npc_destino`, sai `npc_fate_learned`, a quest vira `failed` e a crônica grava "Chegou a notícia: Skek Eco-Curto morreu em Montanhas Afiadas. A missão "Ajudar Skek" fracassou." Ordem e momento corretos. |
| P1-2 | **Fechado** | `npc_world.public_party`/`public_quests` + `entry.ghost`/`ghost_quests` (o snapshot de antes do destino), usados em `api.py:2193` e `:2212`. O teste parametrizado (`ferido`/`capturado`/`morto`) compara a party e as quests públicas com o snapshot de antes do destino (sem status literal, sem vitalidade real, sem sumiço). O `quest_failed` pessoal fica oculto por `personal_of` + `fate_hidden`. Depois da percepção, vale a verdade. O contrato da SPEC-300 não mudou. |
| P2-1 | **Fechado (inspeção)** | `storyteller.py:1188-1189` passa a excluir `npcs` do merge. O `scene_npcs` (`:1043`) já é derivado do `state` com o patch aplicado (`:993-994`), então o resgate +1 e o destino entram e o `reset_scene` é preservado. O teste novo só confere o texto do source. Montar um turno de encontro de verdade numa sonda é caro; a inspeção basta. |
| P2-3 | **Fechado** | Os derivados de `rule_engine` herdam `offscreen` + `cause_event_id` e ficam ocultos até a causa entrar em `_known_sources`. Efeito colateral aceito: o milestone de controle derivado nunca entra na crônica, nem depois da percepção. |
| P2-4 | **Fechado** | `is_offscreen_event` exige `source ∈ {engine, rule_engine}` (crônica, contexto, `_event_origin`). Há teste de flag forjada. |
| P2-6 | **Fechado** | `known_events` (anel de 20) em `_knows`/`_known_sources`. |
| P2-7 | **Fechado / documentado** | Teste engine-only com os 4 tipos. O save omite as chaves vazias (com `off` o save fica idêntico ao de antes; o load continua dando `{}`). `if not origin` só para fato off-screen. R32 seeds 21–32 (evidência do executor). Desvio da R12 justificado na spec. |
| P2-2, P2-5 | **Follow-up** | Registrados na spec (§ "Correções da revisão Sol"). A flag segue `off`. |

**Achado novo (P2-8, não bloqueia):** `npc_world.py:770-777`: o `ghost` só é gravado quando há
`cpatch` e nunca é limpo. Cenário: um companheiro `ferido` (destino percebido) recebe, depois do
cooldown, um segundo perigo que termina em `escapou`. Esse destino não gera `cpatch`, mas troca
`fate_event_id`, então `fate_hidden` = True e `public_party` volta a mostrar o snapshot **antigo**
(vitalidade e `waiting_at` velhos) até o `escapou` ser percebido. Não vaza a verdade; mostra
informação desatualizada. Correção: limpar `ghost`/`ghost_quests` quando o destino é percebido, ou
quando um destino novo sem `cpatch` é aplicado. Também dá para gravar o ghost a cada destino.

## Pendências

- P2-2 (C1 da 302 com `npc_perigo`): obrigatório antes de `RPG_NPC_WORLD=on` no staging.
  Mesclar `state_patch` no sim da 302, medir e decidir com o dono (D2 da 304 / D4 da 302).
- P2-5 (granularidade diária da intervenção/percepção): spec 304b ou §7.
- P2-8 (ghost não limpo): barato; corrigir no pouso ou na 304b.
- `LEADER_DEATH_GAP_DAYS` 30→60: registrar para o dono (D6).
- Smoke real §6 e flip do default (D5): seguem pendentes no cabeçalho.

## Comandos rodados

```text
git diff main...HEAD --stat → 42 arquivos, +5858/−62 (sem mudança em evals/)
py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec304_*.py tests/test_spec302_*.py tests/test_spec305_*.py tests/test_spec300_*.py tests/test_dossier*.py tests/test_chronicle*.py → exit 0 (~430 testes, todos verdes)
sonda (scratchpad) cenário de morte de NPC de grafo com quest → crônica "A missão \"Ajudar Skek\" fracassou.", quest failed, npc_beliefs vazio (P1-1 confirmado)
sonda (scratchpad) sim da 302 + merge do state_patch, 20 seeds × 120 d, RPG_NPC_WORLD off vs on → C1 NA 10→9, brekmar 16→17; 0 eventos inválidos (P2-2)
--- re-revisão (993ffff3) ---
git diff 993aa7e2..HEAD --stat → 10 arquivos, +475/−25
sonda P1-1 refeita: morte não percebida → quests inalteradas, crônica vazia, public_quests active; após npc_fate_learned → quest failed + "Chegou a notícia: … morreu em Montanhas Afiadas. A missão \"Ajudar Skek\" fracassou."
py.sh -m pytest -q -p no:cacheprovider -n 2 (mesmos arquivos + tests/test_spec280_orphan_games*.py, inclui test_spec304_review.py) → exit 0 (~470 testes, todos verdes)
```
