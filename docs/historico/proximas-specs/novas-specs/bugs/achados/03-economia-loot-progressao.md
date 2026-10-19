# Área 03 — Economia / loot / inventário / progressão (auditoria de bugs funcionais, 2026-10-15)

**Arquivos cobertos:** `agents/loot.py`, `services/economy.py`, `services/exploration.py`, `inventory.py`,
`progression.py`, `character_creator.py`, `services/quest_log.py`, `services/event_processor.py` (quest/XP),
`services/restore_effects.py` (só infra; não trata ouro/XP), trechos de `agents/combat.py` (XP), `agents/storyteller.py`
(XP de beat / discover_on_arrival), `api.py` (`/game/new`, `/game/equip`, `/game/levelup`), `data/loot_tables.json`,
`data/recipes.json`, `data/merchants.json`.
**Não cobertos (tempo):** `party.py` (sem lógica de ouro — só grep), `services/cards.py` (aquisição/evolução),
`services/objectives.py` (sem ouro/XP), `gamedata.py` helpers de vitalidade, `services/image_quotes.py` (área 08).

**Contagem:** crítica 0 · alta 3 · média 6 · baixa 3.
Scripts de reprodução (scratchpad da sessão): `r1.py`…`r6.py`, `test_r4.py`; rodar com
`PYTHONPATH=. PYTHONIOENCODING=utf-8 uv run python <script>` a partir da raiz.

---

### BUG-03-01 — XP de kill é re-concedido a CADA rodada para inimigos já mortos
- **Severidade:** alta
- **Categoria:** contabilidade
- **Local:** `agents/combat.py:905` (`dead = [...]`) e `agents/combat.py:925-929` (`xp_for_kills(dead)` / `grant_xp`); inimigos mortos continuam em `result["enemies"]` enquanto o combate segue ativo.
- **Evidência:**
```python
dead = [e for e in enemies if e.get("dead") or e.get("status") == "morto"]   # TODOS os mortos do estado
...
if dead and not player_dead and not is_simulation:
    xp = pg.xp_for_kills(dead); player, level_up_events = pg.grant_xp(player, xp)
```
  `enemies` vem de `state["enemies"]` inteiro; nada marca "XP já pago" (grep `xp_paid|xp_granted` = 0). O docstring de `xp_for_kills` diz "mortos neste round".
- **Reprodução:** `test_r4.py` — `Goblin 1` já `status=morto,dead=True` (como após a rodada 1) + `Goblin 2` vivo (hp 200); jogador "Ataco o Goblin 2", combate segue ativo. 6 seeds: `xp 50` em 5 (combat active True), 1 seed `xp 100`. +50 XP por rodada sem nenhuma morte nova; com um Chefe morto seriam +1000 por rodada.
- **Impacto:** inflação de XP/level-ups em combates com mais de uma rodada e >=1 morte; muitas pending_choices; baseline de balanceamento distorcido.
- **Correção sugerida:** marcar `xp_awarded=True` no inimigo ao pagar (ou calcular `dead` só dos que passaram de ativo para morto nesta rodada, comparando com `state["enemies"]` de entrada).
- **Confiança:** confirmado por execução (estado pré-semeado) + leitura do caminho real
- **Testes existentes relacionados:** nenhum cobre XP multi-rodada. Não é o escopo da SPEC-199 (XP fora da prosa).

### BUG-03-02 — `quest_completed` duplicado no mesmo lote paga XP duas vezes (ouro só uma)
- **Severidade:** alta
- **Categoria:** contabilidade / estado-inconsistente
- **Local:** `services/event_processor.py:277-287` (`quests_completed += 1` incondicional) e `:320-324`; a validação usa `working = dict(state)` (`:247`) cujo `quests` nunca é atualizado dentro do loop.
- **Evidência:**
```python
quests, delivered = quest_log.complete_quest_with_reward(quests, qid, turn)
quest_reward_gold += delivered          # 0 na 2ª vez (quest já completed)
quests_completed += 1                   # soma mesmo assim -> XP_PER_QUEST * 2
```
  O dedupe do validador é por `(type, target_id, turn)`: duas propostas com `target_id` diferentes e o mesmo `payload.quest_id` passam; `_v_quest_completed` checa `state["quests"]` original (ainda `active`).
- **Reprodução:** `r1.py` — 1 quest ativa `q1`; `pending_world_events` = 2x `quest_completed` (target_id "a"/"b", `payload.quest_id="q1"`) -> saída `xp 400 gold 20 ['completed']` (esperado `xp 200 gold 20`; subiu para nível 2).
- **Impacto:** XP dobrado (N x) por quest quando o LLM propõe a conclusão repetida no turno; ouro é idempotente, XP não.
- **Correção sugerida:** incrementar `quests_completed` só se `delivered > 0`; atualizar `working["quests"] = quests` no loop.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum para duplicata no lote.

### BUG-03-03 — Vender 2+ unidades não-empilháveis (entradas separadas) paga ouro e NÃO remove os itens
- **Severidade:** alta
- **Categoria:** contabilidade / exceção-engolida (retorno ignorado)
- **Local:** `services/economy.py:350-356` (`get_qty` soma entradas; `remove_item` só olha a 1ª entrada e o retorno `_` é descartado); `inventory.py:94-107`; mesma falha no craft `services/economy.py:421-422`.
- **Evidência:**
```python
if get_qty(player["inventory"], iid) < qty: ...        # soma TODAS as entradas
player["inventory"], _ = remove_item(player["inventory"], iid, qty)   # ok ignorado
player["gold"] = int(player.get("gold", 0)) + total
```
  `add_item` de item não-empilhável cria sempre nova entrada `{id,qty:1}`; `remove_item` exige a quantidade numa única entrada.
- **Reprodução:** `r1.py` — inventário `[adaga_ferro x1, adaga_ferro x1]` (duas compras); `execute_trade(sell,"adaga_ferro",2)` -> `ok True, gold_delta 10`, inventário **inalterado** (2 adagas), ouro 10. Repetível = ouro infinito.
- **Impacto:** exploit de ouro; itens "vendidos" continuam no inventário; no craft, ingredientes duplicados em entradas separadas não são consumidos.
- **Correção sugerida:** `remove_item` consumir através de várias entradas (False se insuficiente); `execute_trade/execute_craft` abortarem antes de creditar se `ok` for False.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum (testes de venda usam 1 unidade ou itens empilháveis).

### BUG-03-04 — Item vendido continua EQUIPADO e ativo em combate (inclui único já "perdido")
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `services/economy.py:346-367` (sell não toca `player["equipment"]`); `combat_mechanics.py:721-723` e `:209-211` leem `equipment` sem checar posse.
- **Reprodução:** `r2.py` — `equipment={"weapon":"art_adaga_vidro_dragao"}`, vende o único ao mercador: `ok True, gold_delta 3300`, inventário `[]`, **`equipment` segue `{'weapon': 'art_adaga_vidro_dragao'}`** e o evento `unique_item_lost` já dá o item ao mercador. Idem ingredientes de craft equipados (`espada_gasta`, `escudo_amassado`).
- **Impacto:** vende e continua usando bônus/passivas do item; recomprar reequipa de graça.
- **Correção sugerida:** após sell/craft, desequipar slots cujo item saiu do inventário (`reconcile_equipment`), ou o combate ignorar slots sem posse.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-03-05 — Venda sem mercador: `execute_trade(sell)` não exige mercador no local
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `services/economy.py:346-353` (`merchants_at(...) or [(None, {})]`); a compra checa "Não há mercador neste local", a venda não.
- **Reprodução:** `r1.py` — `current_location_id="__nowhere__"`, vender `adaga_ferro` -> `ok True, gold_delta 5`.
- **Impacto:** qualquer rota SHOP mal classificada (ou "vendo X" na estrada) paga ouro sem comprador; um único vendido assim some do inventário sem `pending_events` (só emitido com `mid`) e fica com `holder=player` para sempre.
- **Correção sugerida:** retornar `ok False` quando `merchants_at(loc)` for vazio.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-03-06 — Item único vendido ao mercador some para sempre após o restock
- **Severidade:** média
- **Categoria:** regra-divergente / estado-inconsistente
- **Local:** `services/economy.py:200-209` (`restock` faz `stocks[mid] = dict(base_stock)`), cruza `:360-366` (venda de único injeta no estoque) e `:229-232` (loja só mostra único com `holder == mid`).
- **Reprodução:** `r3.py` — vende `art_adaga_vidro_dragao` ao ferreiro: `holder ferreiro_skallgard, stock 1`; avança 3 dias e `restock` -> `stock after restock None`; `recompra: False`; `is_unique_available: False` (holder != world, então também não dropa). Artefato órfão no mundo.
- **Impacto:** artefato lendário perdido na campanha, contra a regra "segue recomprável, nunca volta ao pool".
- **Correção sugerida:** no `restock`, preservar entradas de únicos com `holder == mid` (ou reinjetar a partir da projection).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-03-07 — Vender item "livre" (`item_desconhecido`) remove OUTRO item e usa nome genérico
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `inventory.py:118-129` (`find_in_inventory` devolve o id `item_desconhecido`), `inventory.py:94-100` (remove a 1ª entrada com esse id), `services/economy.py:347-359`.
- **Reprodução:** `r6.py` — inventário `[Amuleto da Avó, Pedra Lisa]` (ambos `item_desconhecido`); vender "Pedra Lisa" -> `item_name 'item_desconhecido'`, `gold_delta 15`, resta `[Pedra Lisa]` (**o Amuleto foi removido**). `public_market_snapshot` também cota `item_desconhecido` para qualquer item livre.
- **Impacto:** perde o item errado; todo item de sabor vira ouro (o `PlayerFlavorSchema.inventory` do LLM cria esses itens).
- **Correção sugerida:** `find_in_inventory`/sell devolverem a entrada (não só o id) para desconhecidos, ou recusar venda de `item_desconhecido`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-03-08 — `/game/new` com nível > 1: Entropia ultrapassa o `cap` e a criação não bate com a progressão
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `character_creator.py` (`final_entropy = base_entropy + gain*(level-1)`) vs `progression.py:61-73` (curva `late_entropy_curve` + `cap`); `api.py:841` aceita `level` 1..20 e `api.py:2726` dá `gold = 50*level`.
- **Reprodução:** `r5.py` — Devoto do Abismo nível 20 pelo creator: `max_entropy 52`, `pending_choices []`, `xp 0`; via `grant_xp` (0 -> 355000) o mesmo personagem fica com `max_entropy 36` (cap) e 27 escolhas pendentes. Criado direto no nível 20, as Virtudes ficam 4/3/2/1/1 e não há escolhas de Carta/Virtude pendentes.
- **Impacto:** entropia 44% acima do cap em níveis >= 11; fichas de nível alto inconsistentes, exposto pela API pública.
- **Correção sugerida:** criar sempre nível 1 e aplicar `grant_xp` até o nível pedido (como o harness `start_level`), ou limitar ao `cap` e gerar as escolhas.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_progression_20.py` (não cobre criação em nível alto).

### BUG-03-09 — `use_item_in_combat` consome o item mesmo sem efeito (HP cheio / alvo inválido)
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `inventory.py:209-216` (item removido antes de validar efeito) e `:241-246` (debuff/dot/control sem alvo só loga e segue).
- **Reprodução:** `r2.py` — poção de cura com Vitalidade cheia: inventário vira `[]`, log `recupera 0 de Vitalidade`. Para itens hostis sem alvo o consumo ocorre antes do `continue` (confirmado por leitura).
- **Impacto:** perda de consumíveis e do turno por clique errado ou alvo ausente.
- **Correção sugerida:** validar (cura útil / alvo ativo) antes do `remove_item`; devolver "turno não consumido".
- **Confiança:** confirmado por execução (poção) / leitura (alvo)
- **Testes existentes relacionados:** nenhum.

### BUG-03-10 — `xp_for_kills`: tipos `Standard`/texto livre pagam como Minion
- **Severidade:** baixa
- **Categoria:** regra-divergente
- **Local:** `progression.py:22,37-43` (`XP_BY_TIER = {minion, elite, boss}`, default minion) vs `data/bestiary.json` (`type`: 45 Minion, 54 Elite, 12 Standard, 11 BOSS, 1 "Monstrosidade (Gigante)", 1 "Humanoid (Human)"; `categoria` canônica: lacaio/padrao/elite/chefe/nomeado).
- **Evidência:** contagem executada sobre o bestiário; `categoria` (fonte canônica do conflito) não é lida pelo XP; 12 `chefe` vs 11 `BOSS`.
- **Impacto:** Padrão = Lacaio em XP; um Gigante vale 50; um chefe pode pagar 50.
- **Correção sugerida:** mapear por `categoria` (lacaio 50, padrao ~100, elite 200, chefe/nomeado 1000).
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum para `Standard`.

### BUG-03-11 — Nome de item do LLM no inventário inicial resolve para artefato (inclusive ÚNICO) sem claim
- **Severidade:** baixa
- **Categoria:** regra-divergente
- **Local:** `character_creator.py` (`for free_name in flavor_data["inventory"]: inv = add_item(inv, str(free_name), 1)`) -> `inventory.resolve_item_name`.
- **Reprodução:** `r5.py` — `add_item([], "Adaga de Vidro de Dragão")` -> `{'id':'art_adaga_vidro_dragao'}` (um dos 21 únicos), sem `claim_event`; `backfill_inventory` ainda a equipa se tiver o maior `attack_bonus`.
- **Impacto:** o LLM de sabor da criação pode conceder item de qualquer raridade/único.
- **Correção sugerida:** itens de sabor que resolvem para não-comuns/únicos devem virar `item_desconhecido`.
- **Confiança:** provável (função confirmada; depende do LLM real)
- **Testes existentes relacionados:** nenhum.

### BUG-03-12 — Progresso de quest: variações de pontuação contam como "ações distintas"
- **Severidade:** baixa
- **Categoria:** regra-divergente
- **Local:** `services/quest_log.py:176-211` (fingerprint = `casefold` da frase inteira).
- **Evidência:** "Investigo a missão." e "Investigo a missão!" geram dois fingerprints -> `completion_ready` em 2 turnos triviais (a spec pede "duas ações distintas").
- **Impacto:** conclusão de quest (20 ouro + 200 XP) por repetição quase literal.
- **Correção sugerida:** normalizar o fingerprint (sem pontuação, palavras >= 4 chars ordenadas) e/ou exigir turnos distintos.
- **Confiança:** confirmado por leitura (sem execução)
- **Testes existentes relacionados:** apenas repetição literal.

---

## Descartados / falsos positivos / observações
- **Gold negativo na compra/craft:** `execute_trade` e `execute_craft` checam saldo antes de debitar; venda soma `unit*qty` em Python (sinal imposto). Sem achado.
- **Arredondamento de preço (`_round5`):** `sell <= buy` sempre; preço 1 -> 1, nunca 0; só banker's rounding (12.5 -> 10), sem impacto.
- **Tabelas de loot:** bandas `3-4` somam 105, mas `rng.choices` usa pesos relativos; toda raridade tem pool; `danger` 0 cai em 1; nenhum item de pool inexistente.
- **XP no cap 20:** `xp_to_next(20)=None`; `grant_xp` não passa de 20 e não perde escolhas em multi-nível (0 -> 355000 = 27 pending com ids únicos).
- **`normalize_player_progression` re-adiciona `lvl{N}-carta` (11<=N<20) sem checar `progression_grants`:** só roda em `/game/new` e na migração v7->v8 (uma vez); impacto restrito a saves v7, não elevado.
- **`entropy_max_bonus`:** trigger registrado mas nenhuma Carta/dado o usa; código morto, sem bug.
- **`/game/equip` e `/game/levelup` durante combate ativo** não são bloqueados (só `death_pending`); troca de arma como ação livre — possível decisão de design; encaminhar à área 02.
- **1ª venda de único com mercador ainda sem estoque:** `stocks[mid]={u:1}` impede `_ensure_stock` de carregar o `base_stock` depois (`r2.py`); raro, absorvido por BUG-03-06.
- **Compra/venda ambígua por substring (`_resolve_ref_in`, `find_in_inventory`):** "poção" escolhe a primeira da prateleira/inventário; baixa, sem execução.
- **`restore_effects.py`:** só trata memória/jobs/arte; reversão de ouro/itens/XP vem do snapshot do checkpoint (não auditado nesta área).
