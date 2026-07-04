# SPEC — Fase 4.3: Inventário e equipamento

> **Status:** `in-progress` — **Etapas 1–6 implementadas** (2026-07-04, 401 testes
> verdes + build web + smoke_api ok); falta SÓ o smoke com LLM real (§6) para `done`.
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 4.1 (padrão de ids canônicos + backfill em persistence)
> **Desbloqueia:** Fase 4.4 (economia usa inventário estruturado/stacks)

---

## 1. Contexto & Objetivo

Inventário hoje é `List[str]` de nomes livres. Consequências (bugs conhecidos,
ESTADO_ATUAL): "Espada Gasta" inicial não existe no `ARTIFACTS_DB` → arma inicial
não dá bônus; `compute_player_combat_stats` (combat_mechanics.py:277) varre o
inventário INTEIRO e auto-escolhe a melhor arma (jogador não decide o que empunha);
poção comprada é **inutilizável em combate** (parser só resolve habilidades);
item narrado pelo storyteller não entra no inventário; capitalização inconsistente.

Esta spec estrutura o inventário (id canônico + quantidade), cria slots de
equipamento (escolha do jogador vira mecânica) e torna consumíveis usáveis em
combate por caminho determinístico.

## 2. Requisitos

- **R1** — Inventário estruturado: `List[{"id": str, "qty": int}]`. Ids resolvem no
  `ARTIFACTS_DB`. Item ganho igual a existente empilha (`qty += n`) quando
  `stackable` (consumível/material); equipamento não empilha.
- **R2** — Slots de equipamento: `player["equipment"] = {"weapon": id|None,
  "armor": id|None, "accessory": id|None}`. `compute_player_combat_stats` lê SÓ os
  slots (fim do auto-scan). Equipar/desequipar: comando no jogo (CLI/web) —
  determinístico, sem LLM (item precisa estar no inventário e ser do tipo do slot).
- **R3** — Inventário inicial com ids canônicos: `classes.json` ganha
  `starting_equipment: [ids]`; os itens iniciais que não existirem no
  `artifacts.json` são criados lá (ex.: `espada_gasta` com `combat_stats` modestos).
  Arma inicial passa a dar bônus (fecha o bug).
- **R4** — Itens usáveis em combate: `CombatAction` (agents/combat.py:72) ganha
  `item_id: str = ""` — "bebo a poção" → LLM identifica `item_id` do inventário;
  **resolução é Python**: `use_item_in_combat(player, item)` aplica `mechanics`
  do item (cura, buff via condição tipada da 4.2), decrementa `qty`, consome o
  turno. Gate determinístico: item não está no inventário → ação falha com log
  (não confiar no LLM).
- **R5** — Item narrado entra no inventário: `StoryUpdate` (agents/storyteller.py)
  ganha `items_gained: List[str]` — Python resolve cada nome contra `ARTIFACTS_DB`
  (match id exato → nome case-insensitive → sem match: item NÃO entra e vira log
  de aviso; storyteller não cria item novo, isso é papel do loot_node).
- **R6** — Normalização de exibição: nome canônico vem SEMPRE do `ARTIFACTS_DB`
  (`item["name"]`), nunca de `title()`/`capitalize()` sobre id — caça e remoção
  dos usos existentes (bug de capitalização).
- **R7** — Backfill de saves antigos em `load_game_state`: `List[str]` →
  `List[{id, qty}]` (resolve nome→id; não-resolvível vira item genérico
  `item_desconhecido` preservando o nome em `display_name` — jogador não perde
  nada); `equipment` default: melhor arma/armadura do inventário (reproduz o
  comportamento antigo uma única vez).
- **R8** — API/frontend: `GET /game/state` expõe inventário estruturado +
  equipment; aba de inventário com equipar/usar/quantidades.

### Fora de escopo

- Preços/craft/mercadores/drop tables (Fase 4.4).
- Durabilidade, peso/carga, encantamento.
- Uso de item FORA de combate via mecânica (continua narrativo até a 4.4
  estruturar consumo; exceção: descanso já é determinístico na Fase 0).
- Loot equilibrado por região (4.4).

## 3. Design técnico

### Arquivos novos

- **`inventory.py`** (raiz, puro): `add_item(inv, item_id, qty=1)`,
  `remove_item(inv, item_id, qty=1)`, `has_item(inv, item_id)`,
  `resolve_item_name(name) -> str|None` (nome→id, case/acento-insensitive),
  `equip(player, item_id) -> (player, erro|None)`, `unequip(player, slot)`,
  `use_item_in_combat(player, item_id) -> List[str]` (logs; aplica mechanics),
  `backfill_inventory(player) -> player`.

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `state.py` | `PlayerStats.inventory: List[InventoryItem]`; `equipment: Dict` |
| `data/artifacts.json` | itens iniciais canônicos (`espada_gasta`, `kit_basico`...); campo `stackable`; `mechanics` tipado p/ consumíveis (`{"heal": "2d4+2"}` ou `effects` da 4.2) |
| `data/classes.json` | `starting_equipment: [ids]` |
| `combat_mechanics.py` | `compute_player_combat_stats` lê `equipment` (só slots) |
| `agents/combat.py` | `CombatAction.item_id`; rota de uso de item no round (gate determinístico R4) |
| `agents/storyteller.py` | `StoryUpdate.items_gained` + resolução Python (R5) — **guard de FallbackLLM já existe no nó; conferir campo novo dentro do try** |
| `agents/loot.py` | itens gerados entram como `{id, qty}`; dedupe empilha |
| `character_creator.py` | usa `starting_equipment` (ids) |
| `persistence.py` | backfill R7 |
| `api.py` / `game_engine.py` / `web/` | inventário estruturado, comandos equipar/usar |

### Schemas

```python
class InventoryItem(TypedDict):
    id: str
    qty: int
    display_name: NotRequired[str]  # só p/ item_desconhecido (backfill)
```

`artifacts.json` — consumível (exemplo):

```json
"pocao_cura_menor": {
  "name": "Poção de Cura Menor", "type": "potion", "rarity": "comum",
  "gold_value": 25, "stackable": true,
  "mechanics": {"heal": "2d4+2"}
}
```

### Decisões

1. **LLM identifica, Python valida** (R4/R5) — mesmo padrão do combate: `item_id`
   alucinado ou fora do inventário falha no gate determinístico.
2. **Storyteller NÃO cria item** — só referencia existentes; criação continua
   exclusiva do loot_node (senão economia da 4.4 nasce furada).
3. **Slot único de arma** — dual wield fica fora; `accessory` genérico (anel,
   amuleto) para não multiplicar slots antes de ter conteúdo.
4. **`item_desconhecido` preserva save antigo** — nome vira `display_name`,
   item vendável na 4.4 mas sem stats (era o status quo: nomes livres nunca
   deram stats).

## 4. Plano passo a passo

### Etapa 1 — `inventory.py` + schema (TDD)

1. **Testes** (`tests/test_fase43.py`): `test_add_stack`/`test_add_nao_stackable`;
   `test_remove_decrementa_e_zera`; `test_resolve_item_name_acentos`;
   `test_backfill_lista_strings` (resolve + `item_desconhecido` c/ display_name).
2. **Implementação:** `inventory.py`, `state.py`, `persistence.py`.

### Etapa 2 — Equipamento

1. **Testes:** `test_equip_slot_correto`/`test_equip_tipo_errado_falha`/
   `test_equip_item_ausente_falha`; `test_stats_leem_so_slots` (arma melhor no
   inventário mas NÃO equipada → não conta); `test_backfill_auto_equip`.
2. **Implementação:** `equip`/`unequip` + `compute_player_combat_stats`.

### Etapa 3 — Itens iniciais canônicos

1. **Testes:** `test_starting_equipment_resolve_no_db`;
   `test_arma_inicial_da_bonus` (fecha o bug — assert attack > 0).
2. **Implementação:** `artifacts.json` + `classes.json` + `character_creator.py`.

### Etapa 4 — Uso em combate

1. **Testes:** `test_pocao_cura_em_combate` (hp sobe, qty desce, turno consumido);
   `test_item_fora_do_inventario_falha_gate`; `test_item_buff_usa_condicao_42`.
2. **Implementação:** `CombatAction.item_id` + rota no round + `use_item_in_combat`.

### Etapa 5 — Item narrado + capitalização

1. **Testes:** `test_items_gained_resolve` (nome válido entra c/ qty);
   `test_items_gained_desconhecido_nao_entra` (log de aviso, sem item fantasma);
   `test_sem_title_capitalize` (grep programático nos agentes? — manual na revisão).
2. **Implementação:** `StoryUpdate.items_gained` (dentro do try existente) +
   varredura de `title()`/`capitalize()`.

### Etapa 6 — API/CLI/frontend

1. **Testes:** `test_state_expoe_inventario_estruturado`; smoke_api.
2. **Implementação:** endpoints/HUD; `npm run build`.

## 5. Critérios de aceite

- [ ] Arma inicial dá bônus de combate (bug fechado, assert)
- [ ] "Bebo a poção" em combate cura, gasta o turno e decrementa a quantidade
- [ ] Trocar arma equipada muda o ataque observável; item não equipado não conta
- [ ] Item narrado pelo storyteller entra no inventário (ou é recusado com aviso — nunca fantasma)
- [ ] Zero `title()`/`capitalize()` sobre nome de item
- [ ] Save antigo (lista de strings) carrega e auto-equipa uma vez
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: campos novos (`item_id`, `items_gained`) acessados dentro de guard existente
- [ ] `ESTADO_ATUAL.md` + `ROADMAP.md` atualizados

## 6. Smoke test com LLM real

1. Combate real: "bebo a poção de cura" → Gemini preenche `item_id` certo
   (MockLLM esconderia erro de mapeamento do campo novo — ESTE é o teste chave).
2. Narrativa em que o storyteller menciona item conhecido → `items_gained` popula
   e item aparece no inventário.
3. Comprar poção no shop → usar em combate na sequência (fluxo completo).

(≈ 4–5 requests.)

## 7. Riscos & compatibilidade

- **Saves antigos:** backfill R7; pior caso vira `item_desconhecido` SEM perda de
  informação (display_name).
- **MockLLM:** `item_id`/`items_gained` são campos novos de structured output —
  validar com chave real (smoke item 1–2); gates determinísticos seguram alucinação.
- **Frontend:** inventário muda de shape — atualizar tipos TS junto (build quebra
  se esquecer, o que é bom).
- **Testes existentes** que montam `inventory: []` de strings — ajustar fixtures.
