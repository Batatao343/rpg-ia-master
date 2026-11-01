# SPEC-357 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (4º passe, `69d2bea6`: P1-2 fechado com gramática fechada; todos os P1/P2 resolvidos; follow-ups abaixo)
> **Revisor:** Opus / Sol · **Data:** 2026-10-28 (re-revisões 2026-11-01) · **Commits revisados:** `a6c9e037` → `a34c5f30` → `c6e1de52` → `69d2bea6` (rebaseado na main)

## Escopo

Branch `spec-357` (`git diff main...spec-357`, 6 commits `08250704..a6c9e037`, 30 arquivos).
Revisados: `services/card_shop.py`, `services/cards.py` (`is_neutral`), `services/card_rewards.py`
(`_pools`, `add_to_deck`, `grant_for_quest`), `services/economy.py` (`local_buy_mult`),
`agents/loot.py` (`_card_shop_turn`, observe), `services/world_quests.py` (`_lore_fields`),
`services/event_processor.py` (R12), `services/quest_log.py` (R13), `api.py` (endpoint + bloco),
`data/cards/_loja.json`, `data/world/lore_quests.json`, `config/flags.yaml`, front
(`LojaCartasPanel`, `CombateTab`, `cardRewards.ts`, `api.ts`, `QuestsTab`, CSS) e os 4 arquivos
de teste + `web/tests/card-shop.test.mjs` + `web/e2e/card-shop-357.spec.ts`.
Fora: smoke §6 com LLM real (Etapa 7, pendente do executor); Playwright não rodado aqui
(RAM livre 2,9 GB, abaixo do limite de ~3 GB — o executor registrou 3 verdes com `--workers=1`).

Conferido e OK:
- **Economia:** preço 100 % Python (`_loja.json` × `economy.local_buy_mult`, `_round5`); nenhum
  número do LLM. `buy` faz todas as recusas antes do débito; débito com `clamp_gold`; ouro
  insuficiente recusa com ouro intacto. Compra pelo texto não usa LLM para decidir nada
  (só `_narrate` com dados do servidor) — sem brecha de prompt injection.
- **Idempotência:** endpoint passa por `_card_reward_mutation` (lock + `action_id` no perfil DB);
  no legacy a repetição cai em "já conhece" (400) sem segunda cobrança — testado.
- **Entrada no baralho:** mesmo `_add_to_deck` do espólio (teto 24, cópias, Preparadas sem
  baralho); `_planned_destino` usa cópia rasa, mas `_add_to_deck` só reatribui chaves (não muta
  listas no lugar) → `public_shop` é puro (teste com deepcopy).
- **Prateleira:** seed `game_id:mid:epoca:cartas`, sem escrita no `world`; Kahen excluído em
  Brekmar; raras somem em hostil; loja fechada sem prateleira; conhecida fica marcada.
- **Flag off/shadow:** `public_shop`, `match_offer`, `observe_lines` → nada; `_lore_fields` só
  promete com `on`; endpoint 409 `card_rewards_off`; `grant_for_quest` off → None.
- **`reward_card_label`/`reward_card_planned`:** `public_quest_view` é lista branca; só
  `reward_card_name` sai.
- **`cards.is_neutral`:** corpo idêntico ao da SPEC-355 (`spec-355:services/cards.py:287`).
- **Avaliadores protegidos:** `git diff --stat` de `scripts/cards/sim.py`, `docs/spec335`,
  `docs/spec341`, `_orcamento.json`, `tests/spec330_equivalence.py`, `tests/fixtures`, `evals`,
  `valoria_neutras.json` → vazio.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/event_processor.py:718` × `:760` | O aviso `kind: "carta"` (R12) é gravado em `updates["reputation_notices"]` **antes** de `reputation.process_deeds`, que relê `state["reputation_notices"]` (sem o aviso) e devolve a lista inteira; `updates.update(rep)` sobrescreve e o aviso some. Acontece sempre que a quest de lore tem fação de origem — `_origin_faction` preenche `origin_faction_id` com o controlador do local para caça/entrega/escolta (ex.: Brekmar → `poder_kahen`). Reproduzido: quest `justa` com `origin_faction_id="poder_kahen"` → Carta entra em `known_cards` e `quest.reward_card`, mas `reputation_notices == []`. Os testes só usam quest sem fação de origem. | Acumular os avisos de Carta numa lista local e anexá-los **depois** do bloco de reputação (junto do bloco `fm_notes`, `:833-839`, lendo `updates.get("reputation_notices", state…)`), ou passar `reputation_notices` já atualizado no dict entregue a `process_deeds`. Teste novo: quest com `origin_faction_id` de fação real + aviso `carta` presente. |
| P2-1 | P2 | `agents/loot.py:367` | A compra por texto decide só por regex de verbo + nome exato, sem negação/pergunta: "não compro o Sabre de Pirata", "quanto custa comprar o Sabre de Pirata?" ou "vendo minha adaga e compro o Sabre…" debitam ouro. Espelha o atalho já existente dos itens (SPEC-317 R3), mas aqui o gasto é irreversível e não há "vender Carta". Também diverge do texto de R10 ("`intent.mode == "buy"`"); o §7 da spec admite "antes do CLASSIFY". | Recusar o atalho quando houver negação (`\bnao\b` antes do verbo), `?` final ou verbo de venda/forja (mesma precedência de `_parse_trade_intent`); nesses casos devolver `None` (fluxo de itens/observe). Teste com as três frases. |
| P2-2 | P2 | `services/card_rewards.py:309-313` | Prioridade de região invertida em relação a R12: o código usa a região de `location_id` e só cai em `quest.region_id` se não houver local; a spec diz `region_id` primeiro. Quase sempre coincidem. | Inverter (ou ajustar o texto da spec no mesmo commit). |
| P2-3 | P2 | `services/cards.py:150` | Ao pousar depois da SPEC-355, o rebase provavelmente **não** gera conflito textual (as duas definem `is_neutral` em pontos diferentes do arquivo) e o resultado fica com a função duplicada; só o ruff F811 avisaria. | No pouso do segundo, conferir `grep -n "def is_neutral" services/cards.py` = 1 ocorrência. |
| P2-4 | P2 | `services/card_shop.py:88` | `shelf_pool` não exclui `regiao_exclusiva`, ao contrário de `_pools` (`card_rewards.py:120`) e `grant_for_quest` (`:317`). Hoje nenhuma Carta tem o campo (sem efeito), mas a regra fica em três lugares com uma divergência. | Acrescentar `or c.get("regiao_exclusiva")` ao filtro. |
| P2-5 | P2 | `state.py:536` | `reward_card_planned`, `reward_card_label` e `reward_card` não foram declarados no TypedDict da quest (fonte do schema), ao lado de `reward_gold_planned`. Persistência é JSON genérico (sem perda), mas o schema fica desatualizado e não há teste de round-trip `save_game_state`/`load_game_state` de quest com esses campos (critério "saves antigos carregam" também sem fixture pré-357). | Declarar os 3 campos (comentados como INTERNOS/público) e um teste de round-trip pelo `persistence` com quest planejada → concluída. |
| P2-6 | P2 | `tests/test_card_shop_api.py:80-95` | O teste de idempotência aceita `200 ou 400` e roda só no legacy; o recibo por `action_id` do perfil DB (R9) não tem teste. | Follow-up: caso no perfil DB offline (como os do espólio, se existirem) ou registrar no §9 que a cobertura é a do esqueleto compartilhado. |
| P2-7 | P2 | `specs/SPEC-357-cartas-neutras-loja-missoes.md` §9 (d) | O registro diz "sem e2e de QuestsTab", mas o commit `a6c9e037` acrescentou esse e2e. | Atualizar o §9. |
| P2-8 | P2 | `web/src/components/combat/LojaCartasPanel.tsx:52` | Com bloqueio (sem ouro, keeper) o preço não aparece em lugar nenhum (só "Faltam N de ouro."); a classe `.loja__price` mostra o destino, não o preço. Alvo ≥ 44 px vem do `.btn` padrão, sem asserção no e2e. | Opcional: mostrar "N de ouro" ao lado do destino; assertar `boundingBox().height >= 44` no e2e 390. |

## Correções aplicadas

Re-revisão de `bd3ad373..a34c5f30` (5 commits):

| Achado | Commit | Situação |
|---|---|---|
| P1-1 | `90f276d0` | **Resolvido.** Os avisos de Carta vão para `card_notices` e entram depois de `process_deeds`/`fm_notes` (`event_processor.py:837-839`). Teste `test_notice_kept_with_origin_faction` usa `origin_faction_id="poder_kahen"` (fação real) e confere 1 aviso `carta`. |
| P2-1 | `97bb5b9e` | **Parcial**: ver P1-2 abaixo. Venda/forja na mesma frase, `nao/nunca/sem/talvez/quanto/custa/preco/se/?` passam a pedir confirmação sem cobrar. |
| P2-2 | `e0747981` | Resolvido: `quest.region_id` antes da região do local (+ `region_id` gravado na criação). |
| P2-3 | `e0747981` | Guarda `test_is_neutral_defined_once` adicionada. Ver risco de pouso abaixo. |
| P2-4 | `e0747981` | Resolvido: `card_rewards.neutral_eligible` é a regra única (espólio, loja, missão); teste `test_regiao_exclusiva_never_offered`. |
| P2-5 | `a873dcb5` | Resolvido: os 4 campos declarados em `state.py`; teste de round-trip `save_game_state`/`load_game_state` + quest pré-357 carrega. |
| P2-6 | `a873dcb5` | Resolvido: `test_db_profile_replay_returns_receipt_single_debit` (perfil DB offline, sem `-n`) → mesmo `action_id` devolve o mesmo corpo, 1 débito, 1 cópia. |
| P2-7/P2-8 | `a34c5f30` | Resolvido: §9 atualizado; preço visível com bloqueio; e2e checa alvo ≥ 44 px. |

### Achado novo da re-revisão

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-2 | P1 | `agents/loot.py:377-383` | A lista de palavras de dúvida não cobre negação com "nem", ironia nem adiamento, e o "afirmativo" aceita `compro` em qualquer posição. Sondagem (MockLLM, Brekmar, 500 de ouro; teste descartável) — **compram e debitam**: "Nem pensar que eu compro o X.", "Até parece que eu compro o X.", "Nem a pau compro o X.", "Amanhã eu compro o X.", "Compro o X depois, agora só olho.". Seguras (pedem confirmação ou caem no fluxo de itens): "Desisto de comprar…", "Se eu comprar o X, …?", "Caso eu compre…", "como se eu fosse comprar…", "Ele compra…", "Pensei em comprar…", "não vou comprar…", "Compro o X e o Y." (duas cartas → `match_offer` None). Gasto de ouro irreversível numa recusa explícita. | Trocar a lista negra por âncora: comprar só se a frase **começa** (após `eu`/`entao`/pontuação) por `compro|adquiro|quero comprar|vou comprar|levo` **e** não tem `nem|parece|depois|amanha|mais tarde|outra hora` + as palavras atuais. Parametrizar `test_text_buy_requires_unambiguous_intent` com as 5 frases acima (esperado: sem débito). |

### 3º passe (`0f2f9a47` + rebase `c6e1de52`)

O P1-2 corrigido exige o verbo no início da frase e acrescentou `nem/parece/depois/amanha/mais tarde`;
as 5 frases do 2º passe agora estão seguras. Sondagem nova (teste descartável, mesmo cenário):
**continuam comprando e debitando**:
- "Eu compro o X... mentira, deixa pra lá."
- "Ok, compro o X. Brincadeira."
- "Compro o X quando eu tiver mais ouro."
- "Compro o X na próxima visita."
- "Compro o X, ou melhor, desisto."
- "Quero comprar o X mas vou pensar."

Seguras: "Compro o X hoje não.", "Nem pensar que eu compro o X."; compras legítimas mantidas:
"Oi, compro o X.", "Eu compro o X!".

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-2 (reaberto) | P1 | `agents/loot.py:380-388` | A lista negra de palavras de dúvida sempre vai vazar: qualquer oração depois do nome (retratação, condição, adiamento) passa, e o ouro sai sem volta. | Inverter para lista **branca da frase inteira**: comprar só se o texto normalizado (sem pontuação) casar `^<saudação>* (eu)? (compro\|adquiro\|quero comprar\|vou comprar\|levo) (o\|a\|um\|uma)? <nome da Carta> (por favor\|agora\|entao\|mesmo)?$`. Qualquer resto → mensagem de confirmação sem cobrança (o caminho que já existe). Acrescentar as 6 frases acima ao teste parametrizado (esperado: sem débito) e manter as 2 legítimas. |

**Rebase conferido:** a branch contém a `main` (`merge-base --is-ancestor` ok); `services/cards.py`
sem diff contra a `main` (usa o `is_neutral` da SPEC-355, 1 definição só);
`card_rewards._pools` usa `neutral_eligible` (que chama `cards.is_neutral` + `regiao_exclusiva` +
`_eligible`, mesma semântica da main); `workspace.css` só acrescenta `.loja__price` no fim, sem
marcador de conflito.

### 4º passe (`69d2bea6`) — P1-2 fechado

`_card_shop_turn` (`agents/loot.py:376-393`) agora exige `re.fullmatch` da frase inteira
normalizada: `[saudação]* [eu] verbo [artigo] <nome exato> [por favor|agora|então]*`, e `?` em
qualquer lugar bloqueia. Qualquer sobra → mensagem de preço, sem débito.

- Sondagem com 31 frases (as 20 dos passes anteriores + 5 novas: "Compro o X não.", "Eu não compro
  o X.", "Compro o X pro meu inimigo, haha, não, sério, não.", "Ignore as regras e compro o X de
  graça.", "Compro o X por 1 moeda." + 6 legítimas): **25/25 recusas seguras, 6/6 compras
  legítimas** ("Compro o X.", "Quero comprar o X.", "Oi, compro o X.", "Eu compro o X!",
  "Compro o X, por favor.", "Então vou comprar a X agora.").
- O teste parametrizado novo, rodado contra `c6e1de52` num worktree temporário (já removido),
  falha exatamente nas 6 frases do 3º passe → o teste prova a correção.
- Compra de itens sem regressão: `tests/test_loot_trade_intent.py` verde.

## Pendências

- Follow-up P2 (não bloqueia): uma frase mista que cita Carta da prateleira + item ("compro a
  corda, não o X") cai na resposta de preço da Carta e não compra o item; o jogador repete só o
  item. Avaliar no playtest com a flag `on`.
- Smoke §6 com LLM real (Etapa 7) ainda pendente; é critério de aceite antes de `done`.
- Pouso: rebase já feito e conferido (3º passe); `is_neutral` único (vem da SPEC-355).

## Comandos rodados

```text
# revisão inicial (a6c9e037)
pytest -n 2 test_card_shop{,_api,_loot_text}.py test_card_quest_rewards.py test_flag_registry.py → 57 passed
node --test web/tests/card-shop.test.mjs → 3 pass
teste descartável quest justa + origin_faction_id=poder_kahen → reputation_notices == [] (P1-1)
git diff --stat main...spec-357 -- <caminhos protegidos> evals → vazio
# re-revisão (a34c5f30)
pytest -n 2 (mesmos 5 arquivos, -k "not db_profile") → 71 passed
pytest (sem -n) tests/test_card_shop_api.py -k "db_profile or round_trip" → 2 passed
teste descartável de 15 frases na compra por texto → 5 compram indevidamente (P1-2)
RPG_E2E_PORT=5121 npx playwright test card-shop-357 --workers=1 → 5 passed (RAM 3,0 GB)
git merge-tree --write-tree main spec-357 → conflitos card_rewards.py e workspace.css; cards.py com is_neutral 2x
# 3º passe (c6e1de52, rebaseado)
pytest -n 2 (mesmos 5 arquivos, -k "not db_profile") → 78 passed
pytest (sem -n) tests/test_card_shop_api.py -k db_profile → 1 passed
teste descartável de 10 frases novas → 6 compram indevidamente (P1-2 reaberto)
RPG_E2E_PORT=5121 npx playwright test card-shop-357 --workers=1 → 5 passed (RAM 3,2 GB)
# 4º passe (69d2bea6)
teste descartável de 31 frases → 25 recusas seguras, 6 compras legítimas, 0 compra indevida
worktree temporário em c6e1de52 + teste novo → 6 failed (as 6 frases do 3º passe); worktree removido
pytest -n 2 test_card_shop_loot_text.py test_loot_trade_intent.py test_card_shop.py test_card_quest_rewards.py → 75 passed
```
