# SPEC-227 — Integridade de economia e inventário (venda/craft/equipamento/únicos/consumíveis)

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-013/017/018 `done` corrigidas. Fronteira com SPEC-199 D-B: esta corrige o motor; recibo de economia na UI fica para spec futura (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-209, SPEC-212 (ordem final 2026-10-15)
> **Nota de schema (cadeia final 2026-10-15):** ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1".
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-03-03, 03-04, 03-05, 03-06, 03-07, 03-08, 03-09, 03-11 (`proximas-specs/novas-specs/bugs/achados/03-economia-loot-progressao.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — toca ouro/itens únicos (ledger de posse) e a API pública de criação
> **EVAL_AUTHORING_REQUIRED:** `false` — cobertura por testes unitários determinísticos (sem LLM no caminho)

---

## 1. Contexto & Objetivo

A auditoria de 2026-10-15 reproduziu offline (MockLLM) um **exploit de ouro infinito** e uma família de
inconsistências entre `inventory.py`, `services/economy.py` e `combat_mechanics.py`. Todos são bugs de
mecânica Python (princípio "mecânica é Python, não LLM"), sem dependência de provider.

Fatos reproduzidos no HEAD `d6af933` (scripts `r1.py`, `r2.py`, `r3.py`, `r5.py`, `r6.py` do scratchpad; re-executados pelo orquestrador):

- [F] `services/economy.py:346-356` (`execute_trade` modo `sell`): `get_qty` SOMA todas as entradas do item, mas
  `inventory.remove_item` (`inventory.py:94-107`) só consome a PRIMEIRA entrada e devolve `(inv, False)` quando ela
  não tem a quantidade; o retorno é descartado (`player["inventory"], _ = remove_item(...)`) e o ouro é creditado.
  Itens não-empilháveis entram sempre como entradas `{id, qty:1}` separadas (`add_item`), logo **vender 2 adagas
  compradas separadamente paga 10 de ouro e mantém as 2 adagas** — repetível indefinidamente. O craft
  (`execute_craft`, `:421-422`) ignora o retorno do mesmo jeito (ingredientes duplicados não são consumidos).
- [F] `sell` não exige mercador: `merchants_at(location_id) or [(None, {})]` — vender em `__nowhere__` devolve
  `ok True, gold_delta 5`. A compra, por contraste, recusa "Não há mercador neste local". Um único vendido sem
  mercador perde o `claim_event` (só emitido com `mid`) e fica com `holder=player` para sempre.
- [F] `sell`/`craft` não tocam `player["equipment"]`; `combat_mechanics.py:209-211, 721-723` leem os slots sem
  checar posse → item vendido (inclusive único já entregue ao mercador via `unique_item_lost`) segue dando bônus.
- [F] `economy.restock` (`:200-209`) faz `stocks[mid] = dict(base_stock)` e apaga o único que o mercador segurava
  (`:360-366`); como `holder != world`, ele também não volta ao pool de drop → artefato órfão.
- [F] `inventory.find_in_inventory` (`:118-129`) devolve o id `item_desconhecido` para qualquer item livre; `remove_item`
  remove a PRIMEIRA entrada com esse id → vender "Pedra Lisa" remove o "Amuleto da Avó"; `item_name` sai genérico.
- [F] `inventory.use_item_in_combat` (`:209-216`, `:241-246`) remove o consumível ANTES de validar efeito: poção com
  Vitalidade cheia é consumida ("recupera 0"); consumível hostil sem alvo é consumido e `continue`.
- [F] `character_creator.py` cria nível > 1 com `max_entropy = base + ganho×(nível−1)` sem o `cap` de
  `progression.late_entropy_curve` (Devoto nível 20: 52 vs cap 36), sem `pending_choices` e com Virtudes iniciais;
  `api.py:841` aceita `level` 1..20 e dá `gold = 50×level`.
- [F] Inventário de sabor do LLM na criação (`add_item(inv, free_name)`) passa por `resolve_item_name` e pode
  resolver para artefato raro/único sem `claim_event`.

Objetivo: fechar o exploit e tornar as transições de inventário/equipamento/posse **atômicas e verificáveis**
(ou a operação inteira acontece — item sai, ouro entra, claim registrado — ou nada acontece com `ok False`).

## 2. Requisitos

- **R1** — [R] `inventory.remove_item(inv, item_id, qty)` consome `qty` ATRAVÉS de múltiplas entradas com o mesmo
  `id` (ordem: entradas sem `display_name` primeiro, depois por ordem de lista) e devolve `(inv_original, False)`
  sem mutar nada quando a soma é insuficiente. Teste de reprodução ANTES da correção: `[adaga x1, adaga x1]`,
  `remove_item(..., 2)` → hoje `(inv, False)`; depois `([], True)`.
- **R2** — [R] `execute_trade(sell)` e `execute_craft` abortam com `ok False` (e `reason`) quando `remove_item`
  devolve `False`, SEM creditar ouro nem alterar estoque/`pending_events`. Teste de reprodução: venda de 2 adagas em
  entradas separadas → hoje `ok True, +10 ouro, inventário intacto`; depois `ok True, +10 ouro, inventário []`
  (com R1) e, com `remove_item` forçado a falhar, `ok False` e ouro inalterado.
- **R3** — [R] `execute_trade(sell)` exige mercador no local: `merchants_at(location_id)` vazio → `ok False,
  reason "Não há mercador neste local para comprar isso."` (mesma mensagem-padrão da compra). Teste: venda em
  `__nowhere__` → `ok False`, ouro e inventário intactos.
- **R4** — [R] Após `sell`/`craft` que removem item, `player["equipment"]` é reconciliado: todo slot cujo `id` não
  tem mais posse (`get_qty == 0`) é esvaziado (`None`) e o resultado traz `unequipped: [slot,...]`. Função pura
  `inventory.reconcile_equipment(player) -> (player, removed_slots)` reutilizável por `restore`/migração. Teste:
  `equipment={"weapon": "art_adaga_vidro_dragao"}` + venda → `equipment["weapon"] is None`.
- **R5** — [R] `combat_mechanics` ignora slot de equipamento sem posse (defesa em profundidade): bônus/passivas só
  contam se `has_item(inventory, slot_id)`. Teste: slot preenchido + inventário vazio → bônus 0 e passiva ausente.
- **R6** — [R] `economy.restock` preserva entradas de item ÚNICO cujo `holder` (na `world_projection`/claim) é o
  próprio mercador: `stocks[mid] = {**base_stock, **{u: q for u in únicos_segurados}}`. Teste de reprodução:
  vender único → avançar 3 dias → `restock` → hoje estoque `None`; depois `stock == 1` e recompra possível.
- **R7** — [R] Item livre (`item_desconhecido`) é referenciado pela ENTRADA (id + `display_name`), não só pelo id:
  `find_in_inventory` devolve `(id, display_name)` (ou nova função `find_entry_in_inventory`) e `remove_item`
  aceita `display_name` para desambiguar. `sell` de item livre usa o `display_name` em `item_name`. Decisão D-A
  define se item livre é vendável. Teste: `[Amuleto da Avó, Pedra Lisa]`, vender "Pedra Lisa" → resta `[Amuleto da Avó]`.
- **R8** — [R] `use_item_in_combat` valida ANTES de consumir: cura com Vitalidade cheia → `ok False, reason
  "Vitalidade já está cheia."`, item preservado, turno NÃO consumido (flag `consumed_turn: False` no retorno);
  consumível hostil sem alvo ativo → `ok False`, item preservado. Teste: poção com HP cheio → inventário intacto.
- **R9** — [R] Criação de personagem em nível > 1 (`/game/new` `level`): o personagem é criado no nível 1 pelo
  gerador e elevado por `progression.grant_xp` até o XP mínimo do nível pedido, com resolução DETERMINÍSTICA das
  escolhas (mesmo algoritmo do harness `start_level`: subclasse/Cartas/Virtudes por seed do `game_id`), de modo
  que `max_entropy == late_entropy_curve(...)` respeitando o cap e `pending_choices == []`. Alternativa D-B.
  Teste: Devoto nível 20 → `max_entropy == 36`, `pending_choices == []`, `len(known_cards)` igual ao de um
  personagem que subiu por XP.
- **R10** — [R] Inventário de sabor do LLM (criação e qualquer `items_gained` narrado): nome que resolve para item de
  raridade acima de `comum` ou único vira `item_desconhecido` com `display_name` = nome livre (sem claim, sem
  bônus). Teste: `add_item([], "Adaga de Vidro de Dragão")` via criador → `{id: item_desconhecido, display_name:...}`.
- **R11** — [R] Ouro nunca negativo em nenhum caminho de `economy`/`loot`: assert defensivo `gold >= 0` após toda
  transação (clamp + log `economy.negative_gold_prevented`). Teste de propriedade com 200 sequências aleatórias
  de compra/venda/craft.
- **R12** — [H] Saves existentes com equipamento sem posse são reconciliados no load (migração idempotente
  `_migrate_v8_to_v9` ou normalização em `_raw_to_state` — decisão D-C) sem alterar ouro.

### Fora de escopo

- Recibo/ledger de economia na UI (SPEC-199 D-B), linhas `[SISTEMA]` do `loot`.
- Balanceamento de preços, tabelas de loot, `_round5`.
- Política stateful do comerciante e livro de cotações (SPEC-126/`remediacao-playtest-comerciante-real`), exceto
  R6 (restock de único).
- XP (contabilidade de XP está em `SPEC-226-contabilidade-recompensas-xp.md`).

## 3. Design técnico

### Arquivos alterados

- `inventory.py` — `remove_item` multi-entrada (R1); `find_entry_in_inventory` / `remove_item(display_name=)` (R7);
  `reconcile_equipment` (R4); `use_item_in_combat` com validação prévia e retorno `{ok, reason, consumed_turn,
  logs}` (R8); `resolve_flavor_item` (R10).
- `services/economy.py` — `execute_trade(sell)`: checagem de mercador (R3), uso do retorno de `remove_item` (R2),
  `reconcile_equipment` (R4); `execute_craft`: idem (R2/R4); `restock`: preservação de únicos do mercador (R6);
  clamp/log de ouro (R11).
- `combat_mechanics.py` — leitura de `equipment` gated por posse (R5), nos dois callsites (`:209-211`, `:721-723`)
  via helper único `equipped_items(player) -> list[str]`.
- `character_creator.py` + `api.py` (`/game/new`) — nível > 1 via `grant_xp` + resolução determinística (R9);
  `resolve_flavor_item` no inventário de sabor (R10).
- `persistence.py` — normalização de equipamento no load (R12, conforme D-C).

### Assinaturas

```python
# inventory.py
def remove_item(inv: list[dict], item_id: str, qty: int = 1, *, display_name: str | None = None) -> tuple[list[dict], bool]
def find_entry_in_inventory(inv: list[dict], ref: str) -> dict | None          # {id, qty, display_name?}
def reconcile_equipment(player: dict) -> tuple[dict, list[str]]               # (player, slots_esvaziados)
def equipped_items(player: dict) -> list[str]                                  # só ids com posse
def use_item_in_combat(player, item_ref, target=None, rng=None) -> dict        # {ok, reason, consumed_turn, logs, player, target}
def resolve_flavor_item(name: str) -> dict                                     # entrada segura p/ nome livre do LLM
# services/economy.py
def restock(world: dict, *, now_day: int, projection: dict | None = None) -> dict
```

### Formato de dados

Retorno de `execute_trade`/`execute_craft` ganha `unequipped: list[str]` (default `[]`). `last_economy_action`
(`state.py:463`) replica `unequipped` para a UI. Sem mudança de schema de save além de R12 (se D-C = migração).

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)

1. **Testes** (`tests/test_bug_economia_integridade.py`): `test_sell_two_unstackable_separate_entries_removes_both`
   (R1/R2), `test_sell_without_merchant_refused` (R3), `test_sold_item_is_unequipped` (R4), `test_combat_ignores_slot_without_possession`
   (R5), `test_restock_keeps_unique_held_by_merchant` (R6), `test_sell_free_item_removes_correct_entry` (R7),
   `test_potion_full_hp_not_consumed` (R8), `test_create_level_20_respects_entropy_cap` (R9),
   `test_flavor_inventory_never_resolves_unique` (R10), `test_gold_never_negative_property` (R11).
2. **Verificação:** os 10 testes FALHAM no HEAD (registrar saída em `docs/<spec>/README.md`).

### Etapa 1 — `inventory.py` (R1, R7, R8, R10)
### Etapa 2 — `services/economy.py` (R2, R3, R4, R6, R11) + `combat_mechanics.py` (R5)
### Etapa 3 — criação em nível alto (R9) e reconciliação no load (R12)
### Etapa 4 — regressão: `uv run pytest` completo + `uv run python -m playtest run --profile comerciante --turns 30`
(offline) com grep de `gold_delta` ≥ 0 e `unequipped` coerente.

## 5. Critérios de aceite

- [ ] 10 testes de reprodução vermelhos no HEAD → verdes após a correção, sem alterar os asserts.
- [ ] Testes legados de venda/craft/comerciante (`tests/test_economy*.py`, `tests/test_fase6*.py`,
      `tests/test_comerciante*.py`) continuam verdes ou têm o diff justificado no README da spec.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Playtest offline `comerciante` 30 turnos: zero `gold < 0`, zero item vendido ainda equipado.
- [ ] Saves antigos continuam carregando (R12).
- [ ] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo).

## 6. Smoke test com LLM real

1. Comprar 2 adagas, vender "as duas adagas" → ouro e inventário coerentes na ficha.
2. Equipar arma, vender → HUD mostra slot vazio; atacar → sem bônus da arma.
3. "Vendo minha pedra lisa" numa estrada sem mercador → recusa diegética, nada muda.
4. Beber poção com Vitalidade cheia → mensagem de recusa, poção segue no inventário.

## 7. Riscos & compatibilidade

- Saves com equipamento órfão: R12 reconcilia no load; ouro nunca alterado retroativamente.
- MockLLM/FallbackLLM: sem impacto (caminhos puros).
- Testes do perfil comerciante que dependem de "vender sem mercador": ajustar o perfil para só vender em
  mercado (ele já conhece `merchants_at`).
- R9 muda a ficha de `/game/new` com `level>1` (usado pelo simulador/laboratório e harness): verificar
  `tests/test_combat_simulator.py` e o harness `start_level`.

## 8. Pontos de decisão do dono

- **D-A (item livre vendável?):** default recomendado: NÃO vendável (`ok False, "Esse item não tem valor de
  mercado."`); alternativa: vendável por preço fixo 1 com `display_name` correto.
- **D-B (criação em nível alto):** default R9 (subir por XP com escolhas determinísticas); alternativa: recusar
  `level>1` em `/game/new` fora do modo `combat_simulation` (422).
- **D-C (equipamento órfão em saves antigos):** default: normalização em `_raw_to_state` (sem bump de schema);
  alternativa: migração v9 explícita.

## 9. Evidência requerida

- Saída de `uv run pytest` completa; saída isolada dos 10 testes ANTES (vermelho) e DEPOIS (verde).
- `docs/<spec>/README.md` com os scripts de repro do scratchpad transcritos como testes, diff dos testes legados
  afetados e run_id do playtest offline.
- Revisão `Sol` independente sobre o commit exato (toca ledger de posse de únicos).
