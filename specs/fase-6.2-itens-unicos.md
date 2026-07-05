# SPEC — Fase 6.2: Itens únicos — um por mundo, rastreados no event_log

> **Status:** `in-progress` — Etapas 1–4 implementadas (2026-07-05, 488 testes); falta smoke real (§6).
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 4.3 (inventário estruturado) · 4.4 (loot tables/mercadores) · 2.6 (event_log)
> **Desbloqueia:** artefatos de campanha com peso real (ganchos p/ quests da Fase 3.3)

---

## 1. Contexto & Objetivo

Hoje qualquer item pode aparecer N vezes: a `Lágrima Negra de Morrakh` (Codex tem
artefatos LENDÁRIOS nomeados) poderia dropar duas vezes e virar piada. Item único
é o que dá peso a artefato de campanha: **existe UM no mundo**; quem tem, tem; se
o dono morre, o item tem destino rastreável.

Padrão da casa: unicidade é FATO do mundo → evento `unique_item_claimed` no
`event_log` (Python, nunca LLM), estado atual na projection, e todos os pontos de
entrada de item (loot table, mercador, storyteller `items_gained`, craft) checam
antes de entregar. Zero sistema paralelo.

## 2. Requisitos

- **R1 (flag + autoria)** — `artifacts.json`: `"unique": true` em artefatos
  nomeados. **Leva: ~20 artefatos únicos** ancorados no Codex (`data/codex/items/`
  tem candidatos prontos: Lágrima Negra de Morrakh, Coração de Éter...; completar
  com autoria nova nos pilares do mundo — processo e anti-spoiler da 4.1b, incl.
  pesquisa via Grep e **executor Fable para a etapa de autoria**). Mix de
  raridades para não inflacionar: ~10 `raro`, ~7 `epico`, ~3 `lendario`; stats
  de verdade (`combat_stats`/`mechanics` que o motor resolve — zero item só-texto,
  mesmo assert da 4.1b) e ~2 por região temática nas loot tables/mercadores
  (curadoria: o machado anão fica em Skallgard, não no pântano).
- **R2 (evento)** — Item único entrando no inventário do player → motor enfileira
  `unique_item_claimed` (`target_id` = item_id, `source="engine"`, gate anti-LLM
  no validator como `level_up`). `apply_event` registra em
  `projection["unique_items"]: {item_id: {"holder": "player", "event_id": ...}}`.
- **R3 (gates de entrada)** — TODOS os caminhos que criam/entregam item checam
  `is_unique_available(item_id, projection)`:
  - `roll_loot` (4.4): único já reclamado → re-sorteia do pool sem ele;
  - `merchant_stock`/estoque base: único reclamado some da loja;
  - `storyteller items_gained` (4.3): único reclamado é recusado com log;
  - `execute_craft`: receita de único já existente falha ("já existe no mundo").
- **R4 (perda/transferência)** — vender item único: sai do inventário e o evento
  `unique_item_lost` registra (holder vira o merchant_id) — o item NÃO volta ao
  pool de loot (fica no estoque do mercador até recomprado). Morte do player
  (4.6): únicos permanecem no save-memorial (destino narrado na crônica).
- **R5 (crônica)** — `unique_item_claimed` vira milestone: "{item} agora pertence
  ao herói — não há outro no mundo." (`CHRONICLE_EVENT_TYPES`).
- **R6 (HUD)** — inventário marca o item único (◆ lendário) no web e no CLI.

### Fora de escopo

- NPCs disputando/roubando únicos (world_simulator — backlog).
- Únicos como pré-requisito mecânico de quest (3.3 pode referenciar por texto).
- Set items / colecionáveis.

## 3. Design técnico

| Arquivo | Mudança |
|---|---|
| `data/artifacts.json` | ~20 únicos (`unique: true`, raridade rara/épica/lendária, stats reais, lore do Codex sem spoiler — autoria Fable) |
| `services/structured_outputs.py` | `unique_item_claimed`/`unique_item_lost` no EventType |
| `services/world_validators.py` | gate `source == "engine"` (padrão level_up) + item existe e é `unique` |
| `services/event_processor.py` | `apply_event`: mantém `projection["unique_items"]` |
| `services/economy.py` | `is_unique_available()`; `roll_loot`/`merchant_stock`/`execute_craft` checam |
| `agents/storyteller.py` | `items_gained` de único reclamado → recusa; único disponível → entra + enfileira evento |
| `agents/loot.py` | TREASURE que entrega único → enfileira evento |
| `services/chronicle.py` | milestone R5 |
| `inventory.py` | `is_unique(item_id)` helper |
| `web/` + CLI | marcação ◆ |
| `tests/test_fase62.py` | suíte |

Assinaturas:

```python
def is_unique(item_id: str) -> bool                       # inventory.py
def is_unique_available(item_id, projection) -> bool       # economy.py
def claim_events_for(items_gained, projection) -> list     # eventos p/ fila (engine)
```

Decisões:
1. **`source="engine"`** — únicos nunca são "reclamados" por proposta de LLM;
   o motor observa o inventário mudar e registra o fato.
2. **Vendeu = mercador segura** — único não evapora nem re-dropa; rastreável.
3. **Loot table**: único entra no pool da SUA raridade apenas em regiões
   temáticas (~2 por região, curadoria) — chance real de achar, uma vez só;
   alguns ficam em mercador especial (comprável caro) em vez de drop.
4. **20 únicos ≠ 20 lendários**: mix de raridade segura a inflação; o que torna
   especial é a unicidade + a história, não o número.

## 4. Plano passo a passo

1. **Etapa 1 — dados (autoria Fable)**: ~20 únicos autorados — pesquisa em
   `data/codex/items/` + `world_story/` via Grep (candidatos existentes primeiro,
   autoria nova nos pilares depois; anti-spoiler da 4.1b); distribuição ~2 por
   região nas loot tables/mercadores. Testes de schema: `unique` ⇒ raridade ∈
   {raro, epico, lendario} + stats reais (zero só-texto) + registrar tabela de
   design (item × região × origem no Codex) em apêndice desta spec.
2. **Etapa 2 — evento + projection**: testes de validator (gate engine, item
   inexistente/não-único rejeitado), apply, milestone.
3. **Etapa 3 — gates de entrada**: testes por caminho (re-sorteio do loot,
   estoque, items_gained recusado, craft falha).
4. **Etapa 4 — venda/perda + HUD/CLI**: `unique_item_lost`, marcação visual.
5. `uv run pytest` verde + build web.

## 5. Critérios de aceite

- [ ] ~20 únicos autorados (mix raro/épico/lendário, ancorados no Codex, ~2 por região, zero só-texto)
- [ ] Mesmo único NUNCA aparece duas vezes (loot/loja/craft/narrado) — teste e2e com rng varrido
- [ ] Claim vira milestone na crônica com event_id auditável
- [ ] Vender único → rastreado no mercador; recomprável; sem re-drop
- [ ] LLM não consegue propor claim (gate source=engine)
- [ ] `uv run pytest` verde; saves antigos ok (`unique_items` default `{}`)

## 6. Smoke test com LLM real

1. Forçar drop de único (rng semeado num baú) → narração + milestone + ◆ no HUD.
2. Tentar obter de novo via narrativa ("encontro outra Lágrima...") →
   `items_gained` recusa; narrador segue coerente.

(≈ 2 requests.)

## 7. Riscos & compatibilidade

- Saves antigos: projection sem `unique_items` = tudo disponível; se save antigo
  JÁ tem um único no inventário (impossível — ids novos), n/a.
- MockLLM: caminho todo determinístico; smoke só confirma narração.
- Balance: stats de lendário são chute declarado (playtest ajusta).


---

## Apêndice — Registro de design (executado por Fable, 2026-07-05)

20 únicos, todos de `data/codex/items/` (public; descrições vagas — anti-spoiler):

| Raridade | Itens (slot) | Onde encontrar |
|---|---|---|
| Lendário (3) | Adaga de Vidro-Dragão (arma dex), Lágrima Negra de Morrakh (aces.), Armadura Vazia de Malagor (armadura) | pool `lendario` (peso 1) das bandas 3-4 de todas as tabelas |
| Épico (7) | Arpão do Primeiro-Osshari (arma str), Amuleto da Destilação, Coroa de Pressão do Rei Anão, Coração de Éter da Batalha, Coração do Trono, Selo de Urath, Oghma | pools `epico` temáticos: Skallgard (coroa/coração de éter), Nova Arcádia (amuleto), Deserto (Oghma), default (selo/estandarte); Arpão comprável em Brekmar |
| Raro (10) | Lanterna dos Suspiros, Ampulheta de Vaelorn, Máscara Funerária, Coração de Quitina, Estandarte do General Sem Nome, Chama Negra do Farol, Bússola de Ophidia, Código de Ferro Original, O-que-Selune-Trouxe, Diário de Nehla | pools `raro` por região temática; Bússola comprável no Anel Dourado; Coroa comprável em Skallgard |

Documentos puros do Codex (registros, mapas, testamento) ficaram FORA — sem
mecânica honesta de combate; candidatos a itens de quest na 3.3.
