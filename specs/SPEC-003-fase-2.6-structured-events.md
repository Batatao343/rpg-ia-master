# SPEC — Fase 2.6: Structured world changes

> **Status:** `done`
> **Criada:** 2026-07-01 · **Atualizada:** 2026-07-02
> **Depende de:** [SPEC-001-fase-2.5-codex-world-state.md](SPEC-001-fase-2.5-codex-world-state.md) (`done`)
> **Desbloqueia:** [SPEC-004-fase-2.7-rules-engine.md](SPEC-004-fase-2.7-rules-engine.md), 2.8

---

## 1. Contexto & Objetivo

Com a Fase 2.5, existe `event_log` e `world_projection` — mas ninguém escreve neles.
Esta fase fecha o ciclo: **LLM não altera mundo por narrativa livre**. Quando uma ação
tem consequência persistente (morte de NPC canônico, revelação de segredo, mudança de
controle), o agente **propõe** um evento estruturado; um processor Python **valida**
contra o grafo e o estado; só então o evento entra no `event_log` e atualiza a
`world_projection`.

Princípio: *LLM propõe, motor aplica. Tudo estruturado ou rejeitado.* Evento rejeitado
não quebra o turno — é descartado com log.

## 2. Requisitos

- **R1** — Schemas Pydantic para propostas: `ProposedWorldEvent` e `WorldChangeProposal`
  em `services/structured_outputs.py`.
- **R2** — `services/world_validators.py` valida cada proposta: tipo conhecido, IDs
  existem em `entities.json`, entidade-alvo viva (para `npc_killed`), fato secreto só
  revelável se existir chunk/edge `hidden|secret` correspondente, sem evento duplicado
  no mesmo turno.
- **R3** — `services/event_processor.py` transforma proposta válida em `GameEvent`
  (uuid, turn, source), faz append no `event_log` e aplica efeito direto na
  `world_projection` (efeitos em cascata ficam para a rules engine da 2.7).
- **R4** — `storyteller_node` propõe eventos via structured output quando a narrativa
  contém revelação/conclusão/mudança persistente (`StoryUpdate.proposed_events`).
- **R5** — `combat_node` gera `npc_killed` **determinístico em Python** quando inimigo
  canônico (id presente em `entities.json`) chega a HP ≤ 0 — sem passar pelo LLM.
- **R6** — Fluxo no grafo: agentes escrevem em `pending_world_events`; o `archivist`
  (fim de todo turno) chama o processor, que valida/aplica/limpa a fila.
- **R7** — Proposta inválida é rejeitada com razão logada; turno continua normal.
- **R8** — Guard de FallbackLLM: acesso a `proposed_events` protegido
  (isinstance/try-except), como todo structured output do projeto.

### Fora de escopo

- Cascata sistêmica (líder morre → fação destabiliza) — Fase 2.7. Aqui `npc_killed`
  só marca `alive=False` na projection.
- Ranking de contexto (2.8).
- `npc_actor` e `loot` proporem eventos (adicionar depois, mesma infra).
- Tool use nativo do provider — v1 usa `with_structured_output`, já suportado pelos
  4 providers via `llm_setup.get_llm()`.

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/structured_outputs.py` | Schemas Pydantic de proposta |
| `services/world_validators.py` | Validação de propostas contra grafo/estado |
| `services/event_processor.py` | Proposta válida → GameEvent → projection |
| `tests/test_fase26.py` | Suíte da fase |

### Arquivos alterados

- `agents/storyteller.py` — `StoryUpdate` ganha `proposed_events`; updates incluem
  `pending_world_events`
- `agents/combat.py` — morte de inimigo canônico gera proposta determinística
- `agents/archivist.py` — chama `process_pending_events(state)` no início do nó
- `mock_llm.py` — `StoryUpdate` mockado inclui `proposed_events=[]` (default)

### `services/structured_outputs.py`

```python
from typing import Dict, List, Literal
from pydantic import BaseModel, Field

EventType = Literal[
    "npc_killed",
    "secret_revealed",
    "location_control_changed",
    "quest_completed",
    "faction_relation_changed",
]

class ProposedWorldEvent(BaseModel):
    type: EventType
    actor_id: str = Field(default="player", description="Quem causou. 'player' ou id canônico.")
    target_id: str = Field(description="Entidade afetada — id EXATO de entities.json.")
    detail: str = Field(default="", description="1 frase objetiva do que aconteceu.")
    payload: Dict = Field(default_factory=dict, description="Dados extras por tipo (ex.: new_controller_id).")

class WorldChangeProposal(BaseModel):
    events: List[ProposedWorldEvent] = Field(default_factory=list)
    reason: str = Field(default="", description="Por que a narrativa implica essas mudanças.")
```

### `services/world_validators.py`

```python
class ValidationResult(NamedTuple):
    ok: bool
    reason: str = ""

def validate_proposal(proposal: dict, state: GameState) -> ValidationResult
```

Regras por tipo (todas consultam `graph_resolver` da 2.5):

| Tipo | Validações |
|---|---|
| todos | `type` conhecido; `target_id` existe em `entities.json`; sem duplicata (mesmo type+target no turno atual do `event_log`) |
| `npc_killed` | target é `type: npc`; `is_alive(target, projection)` é True |
| `secret_revealed` | existe edge/entidade com `visibility` `hidden`/`secret` ligada ao target; fato ainda não revelado (`revealed_facts`) |
| `location_control_changed` | target é `location`; `payload["new_controller_id"]` existe e é `faction` viva (não `defeated`) |
| `quest_completed` | beat/quest referenciado existe no `campaign_plan` |
| `faction_relation_changed` | ambos ids são fações; relação proposta existe em `relation_types.json` |

Propostas chegam como `dict` (vindas de `pending_world_events` serializável), não como
Pydantic — o validator revalida do zero (`ProposedWorldEvent.model_validate`, dentro de
try/except → inválido = rejeitado).

### `services/event_processor.py`

```python
def process_pending_events(state: GameState) -> dict
    # Retorna updates parciais: {"event_log": [...], "world_projection": {...},
    #                            "pending_world_events": []}
    # Para cada pending: validate_proposal → ok? aplica : loga rejeição.

def apply_event(event: GameEvent, projection: WorldProjection) -> WorldProjection
    # Efeito DIRETO por tipo (sem cascata):
    #   npc_killed                -> entities[target].alive = False
    #   secret_revealed           -> revealed_facts[event_id] = RevealedFact(...)
    #   location_control_changed  -> disable edge "controls" atual + dynamic_edge nova
    #   quest_completed           -> (nada na projection; evento só registra)
    #   faction_relation_changed  -> dynamic_edge nova (ex.: enemy_of)
```

`apply_event` é puro (recebe/retorna projection) — testável sem grafo LangGraph.
Na 2.7, `process_pending_events` ganha a chamada à rules engine após `apply_event`.

### `agents/storyteller.py`

`StoryUpdate` ganha:

```python
proposed_events: List[ProposedWorldEvent] = Field(
    default_factory=list,
    description=(
        "APENAS se a ação deste turno causou mudança PERSISTENTE no mundo "
        "(morte de personagem nomeado, segredo revelado, mudança de controle de local). "
        "Use ids EXATOS. Deixe vazio na dúvida."
    ),
)
```

No corpo do nó (dentro do `try` existente):

```python
pending = [e.model_dump() for e in getattr(update, "proposed_events", []) or []]
if pending:
    updates["pending_world_events"] = state.get("pending_world_events", []) + pending
```

O prompt do sistema ganha bloco `<ENTIDADES_CANONICAS>` com ids+nomes das entidades
da cena (local atual, NPCs presentes, fações conhecidas) — o LLM só pode usar esses ids.

### `agents/combat.py` (determinístico)

Após resolução do round, para cada inimigo com `status == "morto"` neste round cujo
`id` (ou match por `aliases` via `entities.json`) seja canônico:

```python
pending.append({
    "type": "npc_killed", "actor_id": "player", "target_id": canonical_id,
    "detail": f"{enemy['name']} morto em combate", "payload": {}, 
})
```

Sem LLM: o motor já sabe quem morreu. Inimigos genéricos (spawn de bestiário sem id
canônico) não geram evento.

### `agents/archivist.py`

Primeira coisa no `archive_node`:

```python
from services.event_processor import process_pending_events
event_updates = process_pending_events(state)
```

e mescla `event_updates` no dict de retorno do nó (o `archivist` roda em TODO fim de
turno — `main.py` já garante isso).

## 4. Plano passo a passo

### Etapa 1 — Schemas + validadores

1. **Testes** (`tests/test_fase26.py`):
   - `test_valida_npc_killed_ok` — proposta com NPC canônico vivo → `ok=True`.
   - `test_rejeita_id_inexistente` — `target_id="npc_fantasma"` → `ok=False`, reason menciona id.
   - `test_rejeita_npc_ja_morto` — projection com `alive=False` → rejeitado.
   - `test_rejeita_duplicata_no_turno` — mesmo type+target já no event_log do turno → rejeitado.
   - `test_rejeita_payload_malformado` — dict que não valida no Pydantic → rejeitado sem exceção.
2. **Implementação:** `structured_outputs.py` + `world_validators.py`.
3. `uv run pytest` verde.

### Etapa 2 — Event processor

1. **Testes:**
   - `test_npc_killed_aplica_na_projection` — processa pending válido; `is_alive` vira False; `event_log` +1; `pending_world_events` limpo.
   - `test_location_control_changed_troca_edge` — aplica; `get_current_controller` retorna novo controlador; edge antiga em `disabled_edges` com `disabled_by_event`.
   - `test_rejeitado_nao_entra_no_log` — pending inválido; event_log inalterado; sem exceção.
   - `test_secret_revealed_registra_fato` — `revealed_facts` ganha entrada com turn.
2. **Implementação:** `event_processor.py` (`process_pending_events` + `apply_event`).
3. `uv run pytest` verde.

### Etapa 3 — Integração archivist

1. **Testes:**
   - `test_archivist_processa_pendings` — estado com pending válido → invocar `archive_node` (RPG_FORCE_MOCK=1) → updates contêm event_log aplicado e fila vazia.
2. **Implementação:** chamada no início do `archive_node`, mesclando no retorno.
3. `uv run pytest` verde.

### Etapa 4 — Storyteller propõe

1. **Testes:**
   - `test_storyupdate_schema_tem_proposed_events` — campo existe com default vazio.
   - `test_storyteller_enfileira_proposta` — MockLLM configurado para devolver `StoryUpdate` com 1 evento → updates do nó contêm `pending_world_events`.
   - `test_storyteller_fallback_nao_quebra` — `RPG_NO_MOCK=1` (FallbackLLM) → nó não estoura (guard).
2. **Implementação:** campo no `StoryUpdate`, bloco `<ENTIDADES_CANONICAS>` no prompt, enfileiramento; `mock_llm.py` atualizado.
3. `uv run pytest` verde.

### Etapa 5 — Combat determinístico

1. **Testes:**
   - `test_combate_gera_npc_killed_para_canonico` — inimigo com id canônico morre no round → pending com `npc_killed`.
   - `test_inimigo_generico_nao_gera_evento` — spawn genérico morre → fila vazia.
2. **Implementação:** hook pós-resolução em `combat_node` (matching id/alias via `graph_resolver.get_entity`).
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [x] Nenhuma mudança persistente entra no event_log sem passar por `validate_proposal`
- [x] Evento rejeitado não quebra o turno (teste cobre — `test_rejeitado_nao_entra_no_log`)
- [x] Morte de inimigo canônico em combate vira `npc_killed` sem LLM (`_kill_events`, determinístico)
- [x] `uv run pytest` verde (177 offline: 146 baseline + 31 da 2.6)
- [x] Guard de FallbackLLM em todo `with_structured_output` novo/alterado (storyteller try/except;
      combat R5 é Python puro; `test_storyteller_fallback_nao_quebra`)
- [x] Saves antigos continuam carregando (`event_log`/`world_projection`/`pending_world_events`
      já com defaults em persistence — coberto por test_fase25)

## 6. Smoke test com LLM real — ✅ executado 2026-07-02 (Gemini)

1. ✅ Turno real "revelo em praça pública que a Velha Magda é a líder da Mão Sombria" →
   Gemini propôs `secret_revealed` com `target_id="npc_velha_magda"` (id EXATO, sem inventar);
   `validate_proposal` aprovou; entrou no `event_log` (`source=storyteller`, `detail` preservado no payload).
2. `npc_killed` de combate é **determinístico em Python** (`_kill_events`, sem LLM) — coberto
   offline (`test_combate_gera_npc_killed_para_canonico` + ponta-a-ponta com o processor);
   não gastou quota real.
3. ✅ Turno banal "olho ao meu redor observando a neblina" → `proposed_events` veio **vazio**
   (LLM não inventou evento).

## 7. Riscos & compatibilidade

- **MockLLM esconde mapeamento:** campo novo `proposed_events` só é exercitado de
  verdade no Gemini — smoke test obrigatório.
- **LLM inventando ids:** mitigado por bloco `<ENTIDADES_CANONICAS>` no prompt +
  validator rejeitando id desconhecido (defesa em profundidade).
- **Providers não-Gemini:** `with_structured_output` já é a via comum dos 4 providers;
  Ollama com modelo fraco pode devolver lixo → validator segura.
- **Latência/quota:** zero chamadas LLM extras — proposta pega carona no structured
  output que o storyteller já faz.
