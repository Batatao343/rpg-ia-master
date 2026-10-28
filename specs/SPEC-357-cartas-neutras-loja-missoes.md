# SPEC-357 — Cartas neutras na loja do mercador e como recompensa de missão

> **Status:** `approved` (dono: "abre e executa", 28/10; as recomendações do §8 valem como decisão até o dono dizer o contrário)
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Origem:** SPEC-355 item 16 / D15 (`specs/SPEC-355-cartas-pendencias-abertas.md:52,220,516-517`, worktree `rpg-spec-355`); SPEC-333 § Fora de escopo (`specs/SPEC-333-cartas-06-espolio-e-forja-do-baralho.md:39`)
> **Depende de:** SPEC-333 (espólio/Forja, código na `main`, flag `off`), SPEC-335 Lote 6 (as 40 neutras `neu1_*`), SPEC-313 (quests de lore). Usa `cards.is_neutral` da SPEC-355 R7 se ela já tiver pousado; senão, esta spec extrai o predicado (R1) e quem pousar em segundo resolve o conflito trivial.
> **Desbloqueia:** ligar `RPG_CARD_REWARDS` no staging com as três vias de obtenção de neutras (espólio, loja, missão)
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (economia, persistência e idempotência de mutação)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator muda: `scripts/cards/sim.py`, `docs/spec335/arena_posturas.py`, `docs/spec341/arena_spec341.py`, `data/cards/_orcamento.json`, `tests/spec330_equivalence.py`, `tests/fixtures/spec330_legacy_golden.json` e `tests/fixtures/spec330_card_text_snapshot.json` ficam **sem diff** (R15).

Rótulos: **[F]** fato conferido no source (worktree `rpg-spec-357`, HEAD `1b492372`) · **[R]** recomendação · **[BALANCEAR]** número ajustável sem mudar código.

---

## 1. Contexto & Objetivo

[F] As 40 Cartas neutras de Valoria (`data/cards/valoria_neutras.json`, ids `neu1_*`) só chegam ao jogador pelo espólio pós-conflito: o próprio arquivo diz "so chegam por espolio" (`valoria_neutras.json:2`), e o único leitor é a fonte `neutra` (25 %) do sorteio (`services/card_rewards.py:29`, pool em `:115-123`). A SPEC-355 deixou loja e missões de fora por exigirem tabela de preço, dados de missão e front (D15, `SPEC-355…md:516-517`); a SPEC-333 já tinha empurrado "Loja de cartas em cidades" para um follow-up junto da economia (`SPEC-333…md:39`).

[F] Distribuição das 40 neutras por `regiao` (campo = `region_id` do mapa): `nova_arcadia` 7, `skallgard` 7, `brekmar` 12 (7 `neu1_br_*` + 5 `neu1_ka_*`, Kahen), `montanhas_afiadas` 6, sem região ("gerais", `neu1_ge_*`) 8. Por raridade: 20 comuns (tier 1, nível 1), 12 incomuns (tier 3–4, nível 4–7), 6 raras (tier 5–6, nível 9–12), 2 abissais (tier 7, nível 15: `neu1_ka_xadrez_com_lyss`, `neu1_ge_ampulheta_de_vaelorn`).

[F] A loja de itens já é determinística: preço = base × fatores (`services/economy.py:8-10`, `:283-289`), fatores locais de mercador/relação/controlador hostil/estado do local/patente (`:221-248`), mercador do local por `merchants_at` (`:474-476`), raros escondidos em local hostil (`:573-581`), recusa do keeper (`:739-750`). Há 6 mercadores (`data/merchants.json:2,20,41,59,79,97`) em `skallgard`, `na_anel_dourado` e `na_anel_ferro` (região `nova_arcadia`), `brekmar`, `pantano_melancolia` e `pr_vaelorn` (região `pradaria_ruinas`). Não existe UI de mercado no front: a compra é por texto no nó `loot` (`agents/loot.py:378-408`); a consulta lista até 12 linhas (`:381-402`).

[F] As quests de lore pagam ouro planejado na criação (`services/lore_quests.py:195-207`, `data/world/lore_quests.json:16-23`), gravado em `reward_gold_planned` com rótulo público em palavras (`services/world_quests.py:714-729`) e pago na conclusão (`services/quest_log.py:414-442`, chamado em `services/event_processor.py:546-557`; ouro e XP no jogador em `:685-703`).

Objetivo: duas vias novas de **obtenção** (não de poder) para as neutras — a **loja do mercador**, com prateleira curada por região/lore, rotação e preço em ouro determinísticos, e a **recompensa de missão de lore** — reaproveitando o caminho de entrada do espólio (Acervo → Baralho, teto, cópias, carta conhecida recusada; `card_rewards.py:260-288`). Princípio: mecânica é Python; o LLM no máximo classifica a intenção de compra e narra.

## 2. Requisitos

**Base comum**
- **R1 — Predicado único de neutra.** `cards.is_neutral(card: dict) -> bool` = `classe ∈ {"", "Neutra", "neutra", None}` ou `neutra: true` (o mesmo de `card_rewards.py:119`). `card_rewards._pools`, a loja e a missão usam só esse predicado. Se a SPEC-355 R7 já criou a função, reutiliza; nada de segunda cópia.
- **R2 — Configuração em dados, validada.** Novo `data/cards/_loja.json` (prefixo `_`: o carregador de Cartas ignora, `services/cards.py:156`) com preços, tamanho da prateleira e curadoria por mercador (§3). Um teste valida: todo `merchant_id` existe em `data/merchants.json`; toda região citada existe como `region_id` em `data/world_map.json`; todo id em `excluir`/prefixo casa ao menos 1 Carta; preços são inteiros > 0 e crescem com a raridade; nenhuma chave de raridade `abissal`.

**Loja**
- **R3 — Pool da prateleira.** Para o mercador `mid` do local atual (`economy.merchants_at(loc)[0]`, o mesmo da loja de itens), o pool é: Carta neutra (R1), `card_rewards._eligible(card, player, boss=False)` (tipo de baralho, não básica, nível ≥ `level_req`, nunca abissal/ápice; `card_rewards.py:93-103`), `regiao ∈ regioes` do mercador **ou** (`gerais: true` e sem `regiao`), e não excluída por `excluir`. Ordenado por id. Mercador sem entrada em `_loja.json` não vende Cartas.
- **R4 — Rotação determinística.** `epoca = dia // restock_days` do mercador (`world.world_clock.day`; `restock_days` de `merchants.json`). Prateleira = `random.Random(f"{game_id}:{mid}:{epoca}:cartas").sample(pool, min(prateleira, len(pool)))`, ordenada por raridade e nome. Mesmo estado → mesma prateleira; nenhuma escrita no `world` (não há estoque persistido). Carta já conhecida **continua** na prateleira marcada `conhecida: true` (comprar não reembaralha as outras).
- **R5 — Coerência de lore/facção.** Controlador do local `hostil` (`economy._controller_disposition`) ou keeper `hostil` → Cartas `rara` somem da prateleira (mesma regra dos itens rank ≥ 2, `economy.py:573-581`). Keeper que recusa negócio (`economy._keeper_refusal`) → bloco com `motivo` e compra recusada. Loja fechada por estado de local (`location_effects(...)["merchant_closed"]`, `economy.py:521-523`) → sem prateleira.
- **R6 — Preço.** `preco = economy._round5((preco_raridade[r] + preco_por_tier × (tier − 1)) × Π fatores)`, onde `r = card_rewards.rarity_of(card)` e os fatores são **exatamente** os de compra de item sem o fator de oferta (`economy._local_factors(state, "buy", merchant)`: mercador, relação, controlador hostil, estado do local, patente), expostos por uma função pública nova `economy.local_buy_mult(state, merchant) -> float`. Nenhum número vem do LLM. Defaults [BALANCEAR]: comum 45, incomum 110, rara 260, +10 por tier acima de 1 (comum t1 = 45; incomum t3 = 130, t4 = 140; rara t5 = 300, t6 = 310, antes dos fatores).
- **R7 — Compra.** `card_shop.buy(state, card_id) -> dict` (`ok/error/log/card_id/gold/destino/conflito`, contrato de `card_rewards._fail`): exige `RPG_CARD_REWARDS=on` (`_requires_on`), `cards.reorganize_status(state)` permitido (fora de conflito; recusa com `conflito: true`), mercador com prateleira aqui, `card_id` na prateleira **atual**, Carta não conhecida, nível ok, ouro ≥ preço. Debita com `economy.clamp_gold` e entra por `card_rewards._add_to_deck` (Acervo sempre; Baralho se houver vaga sob `cards.DECK_MAX = 24` e limite de cópias; senão Acervo; sem Baralho → Preparadas se houver vaga; `card_rewards.py:260-288`). A versão comprada é a base (afiar segue só pela Forja). Telemetria: `card_telemetry.offered(prateleira, picked=id)` + `picked(id)` sob `source_scope("loja")`.
- **R8 — Bloco público `player_stats.loja_cartas`.** Só com a flag `on`, mercador com prateleira não vazia no local e `reorganize_status` permitido. Campos: `merchant_id`, `merchant_name`, `renova_em_dias` (dias até a próxima época), `motivo` (recusa do keeper ou `null`), `ofertas[]` = `card_rewards.card_view(...)` + `preco`, `conhecida`, `destino` previsto (`"baralho"|"acervo"|"preparadas"`) e `bloqueio` (texto pt-BR pronto ou `null`: "Você já conhece essa Carta.", "Faltam N de ouro.", motivo do keeper). Montar o bloco não muta o estado (teste com `deepcopy` antes/depois).
- **R9 — Endpoint.** `POST /game/loja-cartas` `{game_id, action_id, card_id}` pelo esqueleto `_card_reward_mutation` (`api.py:7370-7426`: lock, idempotência por `action_id` com kind `equip`, 409 `card_rewards_off`, recusa `400 loja_cartas_rejected` ou `409` quando `conflito`). Resposta igual à do espólio mais `player_stats.loja_cartas` atualizado. Repetir o mesmo `action_id` devolve o recibo sem cobrar de novo.
- **R10 — Compra por texto no nó `loot`.** Em `loot_source == "SHOP"`: (a) `intent.mode == "buy"` e o texto normalizado contém **exatamente uma** Carta da prateleira atual pelo nome normalizado (`economy._fold_key`) → `card_shop.buy`, com a mesma linha `[SISTEMA]` dos itens ("+1 Carta: X | Ouro −N (total M)") e o mesmo `_narrate`; nome ambíguo ou fora da prateleira → fluxo de itens inalterado. (b) `observe` acrescenta até 3 linhas "Técnica: X — compra N moedas" depois das de itens. Sem chamada extra de LLM; flag ≠ `on` → nó idêntico ao de hoje.

**Missões**
- **R11 — Técnica prometida na criação.** Ao criar quest de lore (`world_quests._lore_fields`), com a flag `on` e o rótulo de ouro listado em `card_rewards` de `data/world/lore_quests.json` (defaults: `justa`, `generosa`), grava `reward_card_planned: true` e o `reward_hint` público vira "<rótulo> · uma técnica". Sem rótulo listado (`modesta`, vazio) → nada muda. Na prática `investigar_rumor` (10/0) e `recolher_mortos` (15) nunca prometem técnica; caça `padrao` (25) / `elite` (40) e entrega/escolta média ou longa prometem.
- **R12 — Técnica entregue na conclusão.** No apply de `quest_completed` (`event_processor.py:546-605`), só na transição real (`was_active`), com `reward_card_planned` e a flag `on`: `card_rewards.grant_for_quest(state, player, quest, turn) -> str | None` sorteia com `random.Random(f"{quest_id}:missao")` a raridade pelos pesos do rótulo (defaults `justa` comum 80/incomum 20; `generosa` incomum 70/rara 30) e a Carta do pool neutra + `_eligible(boss=False)` + não conhecida, **preferindo** `regiao == região da quest` (`quest.region_id`, senão a região de `quest.location_id`) e caindo para as gerais; raridade sem Carta → outra raridade do rótulo; pool vazio → nenhuma Carta (o ouro já pago fica; sem compensação). Entra por `_add_to_deck` no **mesmo** `player` que recebeu XP/ouro (`:688-693`); grava `quest.reward_card = id`; acrescenta aviso `{"kind": "carta", "subject_id": id, "text": "Você aprende <Nome> com a missão.", "turn": t}` em `reputation_notices` (mesmo canal de `:807-814`). `shadow` → só telemetria (`source=auto`), nada gravado. Telemetria `on`: `source_scope("missao")`.
- **R13 — Quest pública.** `quest_log.public_quest_view` (lista branca, `quest_log.py:603-630`) acrescenta `reward_card_name` só quando `reward_card` existe; `reward_card_planned` nunca sai.

**Front**
- **R14 — Painel "Técnicas à venda".** `web/src/components/combat/LojaCartasPanel.tsx`, renderizado na aba Combate fora de encontro, abaixo da Forja (`CombateTab.tsx:398-399`), quando `player_stats.loja_cartas` existe. Reusa a marcação de Carta do espólio (`EspolioPanel.tsx:39-56`: nome, raridade, Fôlego/Entropia, `RuleText`, descrição) + preço e destino ("vai para o Baralho"/"só para o Acervo — Baralho cheio"). Botão "Comprar por N de ouro" desabilitado com o texto de `bloqueio`; `data-loja-buy=<id>`; mensagem `role="status"`. O front nunca recalcula preço/bloqueio. `RewardSender` ganha `{ kind: "loja"; card_id: string }` → `POST /game/loja-cartas` (`web/src/api.ts:369-382`); `types.ts` ganha `LojaCartasView`; `errorCodes.json`/`errorMessages.ts` ganham `loja_cartas_rejected` ("O mercador não pôde vender essa Carta agora."). `QuestsTab` mostra `reward_card_name` ("Técnica: X") na quest concluída. Aviso `kind: "carta"` usa o render genérico de avisos.

**Invariantes**
- **R15 — Obtenção, não poder.** Nenhum número/efeito/texto de Carta muda; nenhum arquivo de `data/cards/*.json` com Cartas muda; arena e avaliadores ficam sem diff (lista do cabeçalho). `card_rewards.roll_rewards` devolve o mesmo resultado de antes para as mesmas entradas (teste de regressão com 20 seeds).
- **R16 — Saves antigos.** Nenhum campo novo obrigatório; quest sem `reward_card_planned` nunca dá Carta; save sem `_loja` no mundo carrega (a loja não persiste estoque).
- **R17 — Flag `off`/`shadow`.** Com `RPG_CARD_REWARDS ≠ on`: sem `loja_cartas` no state, `POST /game/loja-cartas` → 409 `card_rewards_off`, quest criada sem `reward_card_planned` e com o `reward_hint` de hoje, nó `loot` byte-idêntico na resposta.

### Fora de escopo

- Vender ou trocar Cartas com mercador/NPC; recomprar Carta esquecida.
- Cartas de Postura ou de inimigo na loja; Cartas abissais em qualquer via nova.
- Recompensa de Carta em missão de facção (`MISSION_GOLD`), quest comum (`QUEST_REWARD_GOLD`) ou de crise; escolha "1 de N" na missão.
- Preço por oferta/rota/escassez, desconto de keeper `leal` na Carta, prateleira extra por relação.
- UI de mercado de itens no front (segue só por texto).
- Material de Afiar (`essencia_de_cinza`) na loja (follow-up da SPEC-333).
- Arena por substituição e bandeira de uso (SPEC-358); qualquer mudança em evaluator.
- Mercador novo em `montanhas_afiadas`: as 6 neutras de lá continuam só por espólio e missão (D4).

## 3. Design técnico

**Arquivos novos**
- `services/card_shop.py` — `shelf_config(mid) -> dict | None`, `shelf_pool(state, mid) -> list[str]`, `shelf(state) -> tuple[str | None, list[str]]`, `card_price(state, card_id, merchant) -> int`, `public_shop(state) -> dict | None`, `buy(state, card_id) -> dict` (`@card_rewards._requires_on`), `match_offer(state, folded_text) -> str | None` (R10). Puro, zero LLM.
- `data/cards/_loja.json` — config (R2).
- Testes: `tests/test_card_shop.py`, `tests/test_card_shop_api.py`, `tests/test_card_quest_rewards.py`, `tests/test_card_shop_loot_text.py`; `web/tests/card-shop.test.mjs`; `web/e2e/card-shop-357.spec.ts`.

**Arquivos alterados**
- `services/cards.py` — `is_neutral` (se a 355 ainda não pousou).
- `services/card_rewards.py` — `_pools` usa `cards.is_neutral`; `grant_for_quest`; alias público `add_to_deck = _add_to_deck` (a loja não importa privado).
- `services/economy.py` — `local_buy_mult(state, merchant) -> float` (produto de `_local_factors(state, "buy", merchant)`, mesma ordem de multiplicação de `price`, `:286-288`). `price()` não muda.
- `agents/loot.py` — R10 dentro do ramo SHOP (`:378-408`), antes de `economy.execute_trade`.
- `services/world_quests.py` — `_lore_fields` (R11). `services/event_processor.py` — R12 após `grant_xp` (`:688-693`). `services/quest_log.py` — R13.
- `data/world/lore_quests.json` — chave `card_rewards` (abaixo).
- `api.py` — `LojaCartasRequest`, `POST /game/loja-cartas`, `_card_reward_blocks` (`:2411-2424`) acrescenta `loja_cartas`.
- `config/flags.yaml` — só a `note` de `RPG_CARD_REWARDS` (`:131-136`) vira "espólio, loja e missões de cartas" (sem flag nova; D1).
- Front: `LojaCartasPanel.tsx`, `CombateTab.tsx`, `cardRewards.ts`, `api.ts`, `types.ts`, `lib/errorCodes.json`, `lib/errorMessages.ts`, `components/QuestsTab.tsx` (`:50`), `workspace.css` (reusa `.espolio__*`; só `.loja__price`).

**Formatos de dados**

`data/cards/_loja.json` (curadoria recomendada, D4):
```json
{
  "_doc": "SPEC-357: loja de Cartas neutras. Precos [BALANCEAR]. regioes = campo `regiao` da Carta; gerais = Cartas sem `regiao`.",
  "preco_raridade": {"comum": 45, "incomum": 110, "rara": 260},
  "preco_por_tier": 10,
  "prateleira": 3,
  "mercadores": {
    "ferreiro_skallgard":     {"regioes": ["skallgard"],    "gerais": false},
    "mercado_anel_dourado":   {"regioes": ["nova_arcadia"], "gerais": true},
    "boticario_anel_ferro":   {"regioes": ["nova_arcadia"], "gerais": false},
    "quinquilharias_brekmar": {"regioes": ["brekmar"],      "gerais": true, "excluir": ["neu1_ka_"]},
    "curandeira_pantano":     {"regioes": [],               "gerais": true},
    "armeiro_vaelorn":        {"regioes": [],               "gerais": true}
  }
}
```
`excluir` aceita id exato ou prefixo terminado em `_`.

`data/world/lore_quests.json`, chave nova:
```json
"card_rewards": {
  "justa":    {"comum": 80, "incomum": 20},
  "generosa": {"incomum": 70, "rara": 30}
}
```

`player_stats.loja_cartas` (exemplo, Brekmar, nível 1, 60 de ouro):
```json
{"merchant_id": "quinquilharias_brekmar", "merchant_name": "Quinquilharias da Maré",
 "renova_em_dias": 2, "motivo": null,
 "ofertas": [{"id": "neu1_br_sabre_de_pirata", "name": "Sabre de Pirata", "raridade": "comum",
   "custo_folego": 1, "custo_entropia": 0, "texto": "…", "descricao": "…",
   "preco": 40, "conhecida": false, "destino": "baralho", "bloqueio": null}]}
```
(45 × `price_mult` 0,9 = 40,5 → `_round5` = 40.)

Quest de lore concluída com técnica (campos internos): `reward_card_planned: true`, `reward_card: "neu1_er_traje_branco"`; pública: `reward_hint: "justa · uma técnica"`, `reward_card_name: "Traje Branco"`.

## 4. Plano passo a passo

Testes primeiro em cada etapa; subagente roda só os arquivos da etapa (`-n 2` no máximo); e2e com `--workers=1`.

### Etapa 1 — Predicado e configuração
1. **Testes** (`tests/test_card_shop.py`): `test_is_neutral_matches_rewards_pool` (as 40 `neu1_*` são neutras; nenhuma Carta de Postura é); `test_loja_config_valid` (R2: mercadores, regiões, prefixos, preços crescentes, sem abissal); `test_rewards_roll_unchanged` (R15: `roll_rewards` com 20 seeds fixas igual ao resultado gravado **antes** da mudança no próprio teste).
2. **Implementação:** `cards.is_neutral`, `_pools` usando-o, `_loja.json`.

### Etapa 2 — Prateleira e preço (puro)
1. **Testes:** `test_shelf_deterministic` (mesmo estado → mesma lista); `test_shelf_rotates_by_restock_epoch` (Brekmar: 10 épocas → ≥ 2 prateleiras diferentes; dias da mesma época → iguais); `test_shelf_respects_region_and_generals` (Skallgard só `skallgard`; Pântano só gerais; Brekmar sem `neu1_ka_*`); `test_shelf_never_abissal_or_over_level`; `test_known_card_stays_marked` (comprar não muda as outras ofertas); `test_hostile_hides_rare`; `test_closed_merchant_no_shelf`; `test_card_price_formula` (comum t1 em Brekmar = 40; incomum t3 com `price_mult` 1.0 = 130; hostil × 1,5); `test_local_buy_mult_matches_item_price` (para um item de catálogo, `base × local_buy_mult × supply == economy.price`).
2. **Implementação:** `card_shop.shelf_*`, `card_price`, `economy.local_buy_mult`.

### Etapa 3 — Compra, bloco e API
1. **Testes** (`tests/test_card_shop.py`, `tests/test_card_shop_api.py`): `test_buy_debits_and_adds_to_deck`; `test_buy_deck_full_goes_to_acervo` (24 Cartas); `test_buy_refuses_known_off_shelf_low_gold_level_in_conflict` (5 recusas, ouro intacto); `test_buy_keeper_refuses`; `test_public_shop_pure` (deepcopy igual); `test_public_shop_bloqueio_texts`; `test_api_loja_cartas_ok_and_idempotent` (mesmo `action_id` 2× → 1 débito); `test_api_loja_cartas_off_409`; `test_api_state_has_no_loja_when_off`; `test_buy_telemetry_source_loja`.
2. **Implementação:** `card_shop.buy`, `public_shop`, endpoint, `_card_reward_blocks`.

### Etapa 4 — Compra por texto no `loot`
1. **Testes** (`tests/test_card_shop_loot_text.py`, MockLLM): `test_text_buy_exact_card_name` ("compro o Sabre de Pirata" em Brekmar → Carta no Acervo, `[SISTEMA]` com ouro); `test_text_buy_item_unchanged` ("compro corda" → fluxo de itens, mesma resposta de antes); `test_text_ambiguous_card_falls_back`; `test_observe_lists_techniques`; `test_loot_off_identical` (flag `off`: resposta igual à gravada).
2. **Implementação:** R10 em `agents/loot.py`.

### Etapa 5 — Missões
1. **Testes** (`tests/test_card_quest_rewards.py`): `test_planned_only_for_listed_labels` (justa/generosa sim; modesta não; flag off não); `test_reward_hint_suffix`; `test_grant_on_completion_regional_first`; `test_grant_deterministic_by_quest_id`; `test_grant_once_only` (segunda `quest_completed` da mesma quest não dá nada); `test_grant_skips_known_and_empty_pool`; `test_grant_same_player_as_xp_gold` (XP, ouro e Carta no mesmo `updates["player"]`); `test_notice_kind_carta`; `test_public_view_reward_card_name_only`; `test_old_quest_without_planned_no_card` (R16); `test_shadow_writes_nothing`.
2. **Implementação:** `_lore_fields`, `grant_for_quest`, `event_processor`, `public_quest_view`, chave em `lore_quests.json`.

### Etapa 6 — Front
1. **Testes:** `web/tests/card-shop.test.mjs` (helper `shopOfferState(oferta)` → `{enabled, label}` para livre/conhecida/sem ouro/keeper; rótulo de destino); `web/e2e/card-shop-357.spec.ts` com a fixture `backend` de `web/e2e/spec347-desktop.spec.ts:49-60`: painel aparece fora de encontro com 3 ofertas; botão bloqueado mostra o motivo; clicar "Comprar" envia `POST /game/loja-cartas` com `card_id` e o painel reflete o state devolvido; mobile 390 px sem rolagem horizontal; QuestsTab mostra "Técnica: X".
2. **Implementação:** componentes, tipos, api, códigos de erro, CSS.
3. **Verificação:** `npm run build`, `node --test web/tests/card-shop.test.mjs`, `npx playwright test card-shop-357 --workers=1`.

### Etapa 7 — Smoke e fechamento
Smoke §6, registro de implementação no §9, revisão Sol.

## 5. Critérios de aceite

- [ ] R1–R17 cobertos pelos testes nomeados no §4 (pytest + node + Playwright)
- [ ] Preço, prateleira, rotação e sorteio de missão determinísticos e sem LLM; ouro nunca negativo (`clamp_gold`)
- [ ] Mesma entrada no baralho que o espólio (teto 24, cópias, conhecida recusada)
- [ ] Arena/avaliadores/Cartas sem diff (`git diff --stat` dos caminhos do cabeçalho vazio)
- [ ] Flag `off`: state, API e nó `loot` iguais aos de hoje
- [ ] `uv run pytest` verde (suíte completa: coordenador, no pouso)
- [ ] Nenhum `with_structured_output` novo (R10 não chama LLM); o guard existente do `TradeIntent` intacto
- [ ] Saves antigos carregam (fixture de save pré-357 com quest de lore ativa)
- [ ] Smoke §6 executado e registrado

## 6. Smoke test com LLM real

Local (`uvicorn api:app`), chave real, `RPG_CARD_REWARDS=on`, `RPG_LORE_QUESTS=on`; ≤ 5 turnos com LLM.

1. Novo jogo começando em Brekmar; `GET /game/state` → `player_stats.loja_cartas` com 3 ofertas, sem `neu1_ka_*`, preços = R6.
2. Turno "Quero comprar o <nome da 1ª oferta> da Okka" → roteado para LOOT/SHOP pelo router real; `[SISTEMA]` com a Carta e o ouro; `known_cards` contém a Carta; ouro debitado exato.
3. Turno "Que técnicas você tem à venda?" → consulta lista as linhas "Técnica: …" (anotar se o router mandar para NPC; não é falha desta spec, vira achado).
4. No navegador: comprar outra oferta pelo painel; a oferta comprada fica "Você já conhece"; as demais não mudam.
5. Quest de lore `justa` (save de smoke com a quest ativa a um passo da conclusão, gerado pelo helper do teste R12): o turno que conclui mostra o aviso "Você aprende …" e a QuestsTab mostra "Técnica: …".

## 7. Riscos & compatibilidade

- **Saves antigos:** nada obrigatório novo; a loja não persiste estoque; quests antigas sem `reward_card_planned` só pagam ouro.
- **MockLLM/FallbackLLM:** R10 decide por nome exato antes do CLASSIFY e não depende do LLM; com o LLM caído, a compra pelo painel segue funcionando.
- **Quota/latência:** zero chamada nova; o bloco `loja_cartas` é cálculo puro por GET (amostra de ≤ 12 Cartas).
- **Economia:** preços chutados [BALANCEAR]; a missão dá técnica sem custo e pode acelerar o Acervo — mitigado por só `justa`/`generosa`, sem abissal e com teto do baralho. Medir no playtest (`--turns 50`) quantas neutras entram por via; ajustar só os JSON.
- **Flag trocada no meio da quest:** técnica prometida com flag `on` e concluída com `off` não é paga (flag `off` não toca a ficha); documentado.
- **Conflito com a SPEC-355:** só `cards.is_neutral` e `_pools` (mesmo predicado); quem pousar em segundo faz rebase.
- **Texto ambíguo:** nome de Carta que contém nome de item (ex.: `neu1_sb_corda_de_aranha` × item `corda`, se um dia entrar numa prateleira): R10 exige exatamente uma Carta e só intercepta o modo `buy`; teste `test_text_buy_item_unchanged` cobre "compro corda".

## 8. Decisões (recomendação adotada; o dono pode reverter)

- **D1 — Flag:** reaproveitar `RPG_CARD_REWARDS` (espólio, loja e missão ligam juntos) **[R]**. Alternativa: flag nova `RPG_CARD_SHOP` registrada em `config/flags.yaml` para ligar a loja separada do espólio.
- **D2 — Preço:** comum 45, incomum 110, rara 260, +10 por tier acima de 1, × fatores locais de compra (mercador/relação/hostil/estado/patente), arredondado a 5 **[R][BALANCEAR]**. Referência: recusa do espólio 15, Esquecer 25, Purgar 40, quests 10–45, item incomum 100 e raro 400.
- **D3 — Prateleira:** 3 Cartas, rotação a cada `restock_days` do mercador (2–4 dias) **[R]**.
- **D4 — Curadoria:** tabela do §3. Kahen (`neu1_ka_*`) fora da loja de Brekmar (técnica de culto não fica exposta no balcão; só espólio/missão); Saídas Baixas (`montanhas_afiadas`) sem loja, porque não há mercador lá **[R]**.
- **D5 — Missão:** Carta direta sorteada na conclusão (não "1 de N"), prometida na criação como "· uma técnica" **[R]**. Alternativa: reaproveitar `espolio_pendente`, que tem um só slot e expira no próximo conflito (colide com o espólio de combate).
- **D6 — Quais missões:** só lore com rótulo `justa`/`generosa`; facção, comum e crise ficam de fora **[R]**.
- **D7 — Nível:** a prateleira só mostra Cartas do nível atual ou abaixo (muda no level-up) **[R]**. Alternativa: mostrar bloqueadas ("Exige nível N").
- **D8 — Compra por texto:** incluída (R10), só por nome exato **[R]**.
- **D9 — Onde fica o painel:** aba Combate fora de encontro, abaixo da Forja (é onde o Baralho é gerido) **[R]**.
- **D10 — Carta conhecida na prateleira:** fica visível e desabilitada **[R]**.
- **D11 — Local/keeper hostil:** some a rara, como nos itens **[R]**.

Pergunta ao dono (não bloqueia a execução): os números de D2 e a exclusão de Kahen em D4 estão bons?

## 9. Registro de implementação

(preencher na execução)
