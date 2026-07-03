# SPEC — Fase 4.4: Economia determinística — craft, mercadores e loot tables

> **Status:** `draft`
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 4.3 (inventário estruturado `{id, qty}` + stacks)
> **Desbloqueia:** "Economia regional" (backlog) — esta spec é a fundação dela

---

## 1. Contexto & Objetivo

Hoje `agents/loot.py` entrega os TRÊS sistemas econômicos à mão do LLM: o
`TransactionResult` decide sozinho sucesso, preço, itens consumidos e item criado
— o Python só aplica (forçando o sinal do ouro, único guard). Consequências:
preço inventado a cada conversa, craft sem receita (LLM aceita qualquer
combinação), loot sem raridade controlada, mercador de Skallgard idêntico ao de
Nova Arcádia.

Esta spec inverte: **Python decide (receitas, estoques, preços, drops), LLM só
identifica a intenção e narra o resultado**. Mesmo padrão do combate — que já
provou funcionar neste projeto.

Estado do mundo entra no comércio: local controlado por fação hostil ao jogador
= preços piores/estoque restrito (usa a verdade da projection, padrão 3.4).

## 2. Requisitos

- **R1 (craft)** — `data/recipes.json`: receita = ingredientes (`{id: qty}`) +
  ouro + local de craft (`craft_tag`: forja/laboratorio/altar) + classe/skill
  opcional → `result_id`. Python valida TUDO (ingredientes no inventário, ouro,
  local atual tem a tag, gating de classe) e aplica; falta ingrediente → falha
  determinística com motivo. LLM só narra o processo (sucesso OU falha).
- **R2 (craft_tags no mapa)** — locais de `data/world_map.json` ganham
  `craft_tags: []` (e `economy_tags`, R4) — curadoria manual dos 30 nós.
- **R3 (mercadores)** — `data/merchants.json`: mercador por local/região com
  estoque curado e persistente (`{item_id: qty}` no estado do mundo após a
  primeira visita), especialidade e multiplicador próprio. Reabastecimento
  determinístico pelo relógio do mundo (a cada N dias, volta ao estoque base).
  Skallgard vende coisa DIFERENTE de Nova Arcádia (critério de aceite da Fase 4).
- **R4 (preços)** — `services/economy.py`: `price(item_id, *, mode, location_id,
  factions, projection) -> int`. Fórmula determinística:
  `base(raridade) × mod_regional(economy_tags) × mod_mercador × mod_reputação
  (disposition da fação controladora do local — projection 2.5+, padrão 3.4) ×
  0.5 se venda`. LLM NUNCA decide preço. Números redondos (arredondar p/ 5).
- **R5 (drop tables)** — `data/loot_tables.json`: tabela por região × danger;
  raridade rolada em Python (pesos), item sorteado do pool. `loot_node` modo
  TREASURE usa a tabela; LLM só DESCREVE o item sorteado (nome/descrição de item
  novo gerado continua com o LLM — mas raridade, stats-alvo e valor vêm da
  tabela; `gold_value` do LLM é ignorado e substituído pelo canônico).
- **R6 (mundo afeta comércio)** — controlador do local hostil (disposition
  negativa): preços de compra +50%, estoque sem itens `rarity >= raro`;
  `threat_alerts` ativos na região: mercador pode recusar itens de guerra.
  Deriva de `state_views`/`graph_resolver` — zero estado novo.
- **R7 (intenção estruturada)** — novo structured output `TradeIntent`:
  `{mode: "buy"|"sell"|"craft", item_ref: str, qty: int}` (FAST tier). Python
  resolve `item_ref` → id (estoque/inventário/receitas), executa e devolve o
  resultado mecânico para o narrador. **Guard de FallbackLLM obrigatório**
  (isinstance) — nó novo com structured output.
- **R8** — `TransactionResult` (o LLM-decide-tudo atual) morre. `ItemGeneration`
  sobrevive só para descrever item inédito de TREASURE (R5).

### Fora de escopo

- Economia dinâmica (oferta/demanda simulada, rotas de comércio) — backlog
  "Economia regional" evolui em cima desta base.
- Roubo/barganha social (fica narrativo).
- Craft com minigame/chance de falha crítica (v1: receita válida = sucesso).
- Migração de itens custom já salvos por `save_custom_artifact` (continuam
  válidos como estão).

## 3. Design técnico

### Arquivos novos

- **`services/economy.py`** (puro): `price(...)` (R4), `merchant_stock(state,
  location_id) -> dict` (estoque efetivo com R6), `restock(world, merchants_db)`,
  `execute_trade(state, intent) -> TradeOutcome` (aplica compra/venda),
  `execute_craft(state, recipe_id|item_ref) -> TradeOutcome`,
  `roll_loot(region, danger, rng=None) -> LootRoll`.
- **`data/recipes.json`**, **`data/merchants.json`**, **`data/loot_tables.json`** —
  curadoria manual (Valoria: forja anã em Skallgard, laboratório em Nova Arcádia,
  altares em território druídico...).
- **`tests/test_fase44.py`**.

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `agents/loot.py` | reescrito: `TradeIntent` (parse) → `services/economy` (resolve) → narração; `TransactionResult` removido |
| `data/world_map.json` | `craft_tags` + `economy_tags` nos 30 nós |
| `state.py` | `WorldState.merchant_stocks: Dict[str, Dict[str, int]]` + `last_restock_day: int` (persistente) |
| `gamedata.py` | loaders dos 3 JSONs novos |
| `api.py` | `/game/state` pode expor estoque do mercador local (aba de comércio futura) |

### Schemas / formatos

`TradeIntent` (Pydantic, FAST):

```python
class TradeIntent(BaseModel):
    mode: Literal["buy", "sell", "craft"]
    item_ref: str          # nome livre dito pelo jogador; Python resolve -> id
    qty: int = 1
```

`recipes.json`:

```json
"lamina_temperada": {
  "result_id": "espada_aco_temperado", "result_qty": 1,
  "ingredients": {"espada_gasta": 1, "minerio_ferro": 2},
  "gold_cost": 40, "craft_tag": "forja", "classes": []
}
```

`merchants.json`:

```json
"ferreiro_skallgard": {
  "location_id": "skallgard_forja", "name": "...",
  "specialty": "weapon", "price_mult": 1.1, "restock_days": 3,
  "base_stock": {"espada_aco_temperado": 1, "minerio_ferro": 5}
}
```

`loot_tables.json` (por região, fallback `default`; pesos por danger):

```json
"skallgard": {
  "1-2": {"comum": 70, "incomum": 25, "raro": 5},
  "3-4": {"comum": 40, "incomum": 40, "raro": 18, "epico": 2},
  "pools": {"comum": ["minerio_ferro", "..."], "raro": ["..."]}
}
```

Tabela base de preço por raridade (em `economy.py`):
`comum 25 · incomum 100 · raro 400 · epico 1500 · lendario 6000`.

### Decisões

1. **Padrão combate aplicado ao comércio** — LLM classifica (`TradeIntent`),
   Python resolve, LLM narra resultado fechado. Falha também é narrada (mercador
   recusa, forja fria, ingrediente faltando — material narrativo bom).
2. **Estoque persiste no world state** (não no merchants.json) — comprar esgota;
   restock por relógio já existente (`world_clock.day`).
3. **`gold_value` do LLM ignorado** — item inédito descrito pela IA recebe valor
   canônico da tabela de raridade (o LLM já demonstrou inventar sinal/valor — bug
   histórico do sinal do ouro).
4. **Reputação usa disposition existente** (Fase 2 + 3.4) — sem sistema novo.

## 4. Plano passo a passo

### Etapa 1 — Dados + loaders (TDD)

1. **Testes:** `test_recipes_schema` (ids resolvem no ARTIFACTS_DB/receitas);
   `test_merchants_schema` (location_id existe no mapa); `test_loot_tables_schema`
   (pools resolvem; pesos > 0); `test_craft_tags_no_mapa` (≥1 forja, 1 laboratório,
   1 altar em Valoria).
2. **Implementação:** 3 JSONs (primeira leva: ~10 receitas, ~6 mercadores,
   tabelas p/ 4 regiões + default) + loaders + tags no mapa.

### Etapa 2 — Preços

1. **Testes:** `test_price_por_raridade`; `test_price_mod_regional`;
   `test_price_reputacao_hostil_sobe`; `test_venda_metade`; `test_arredonda_5`.
2. **Implementação:** `price()`.

### Etapa 3 — Mercadores + estoque persistente

1. **Testes:** `test_estoque_inicializa_do_base`; `test_compra_esgota`;
   `test_restock_por_dias`; `test_hostil_esconde_raros`;
   `test_skallgard_diferente_nova_arcadia` (critério da fase).
2. **Implementação:** `merchant_stock`/`restock` + `WorldState`.

### Etapa 4 — Craft

1. **Testes:** `test_craft_ok_consome_e_cria`; `test_craft_sem_ingrediente_falha`
   (critério da fase); `test_craft_local_errado_falha`; `test_craft_gating_classe`.
2. **Implementação:** `execute_craft`.

### Etapa 5 — Drop tables

1. **Testes:** `test_roll_loot_respeita_pesos` (rng semeado);
   `test_gold_value_llm_ignorado`; `test_regiao_sem_tabela_usa_default`.
2. **Implementação:** `roll_loot` + integração TREASURE.

### Etapa 6 — Reescrita do loot_node

1. **Testes:** `test_trade_intent_guard_fallback` (FallbackLLM → AIMessage → nó
   não estoura, cai em mensagem neutra); `test_buy_e2e_mock`; `test_sell_e2e_mock`;
   `test_craft_e2e_mock`.
2. **Implementação:** `loot.py` novo; remover `TransactionResult`.
3. **Verificação:** suíte completa + smoke_api.

## 5. Critérios de aceite

- [ ] Craft falha sem ingrediente, com motivo mecânico (critério da Fase 4)
- [ ] Mercador de Skallgard vende coisa diferente do de Nova Arcádia (critério da Fase 4)
- [ ] Preço de um mesmo item varia por região/reputação e NUNCA vem do LLM
- [ ] Comprar esgota estoque; estoque volta após N dias de relógio
- [ ] Local hostil: preços +50% e sem itens raros
- [ ] Loot de TREASURE sai da tabela da região (rng semeado testável)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM no `TradeIntent` (isinstance)
- [ ] Saves antigos carregam (`merchant_stocks` default `{}`)
- [ ] `ESTADO_ATUAL.md` + `ROADMAP.md` atualizados

## 6. Smoke test com LLM real

1. "Quero comprar uma espada" no mercador → `TradeIntent` mapeia certo (campo novo
   — MockLLM esconderia), preço bate com a tabela, narração coerente.
2. "Vendo minha adaga" → sinal do ouro correto (bug histórico), estoque do
   mercador ganha o item? (não — venda não entra no estoque, conferir).
3. Craft válido na forja de Skallgard → item criado; repetir SEM ingrediente →
   falha narrada.
4. Baú TREASURE → item da tabela da região com descrição da IA.

(≈ 5 requests.)

## 7. Riscos & compatibilidade

- **Saves antigos:** `merchant_stocks`/`last_restock_day` defaults; inventário já
  estruturado pela 4.3 (dependência dura).
- **MockLLM:** `TradeIntent` novo — adicionar caso no mock_llm.py p/ suíte offline;
  validar mapeamento real no smoke (item 1).
- **Curadoria é o gargalo:** 3 JSONs novos + tags em 30 nós — primeira leva pequena
  e temática > cobertura total; expandir depois é adicionar linha, não código.
- **Item custom antigo** (`save_custom_artifact`): continua no ARTIFACTS_DB e
  vendável pelo `gold_value` que já tem — sem migração.
