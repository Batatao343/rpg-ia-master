# SPEC — Fase 2.7: Rules engine sistêmica

> **Status:** `done`
> **Criada:** 2026-07-01 · **Atualizada:** 2026-07-02
> **Depende de:** [SPEC-003-fase-2.6-structured-events.md](SPEC-003-fase-2.6-structured-events.md) (`done`)
> **Desbloqueia:** [SPEC-005-fase-2.8-context-builder.md](SPEC-005-fase-2.8-context-builder.md)

---

## 1. Contexto & Objetivo

Na 2.6, `npc_killed` só marca `alive=False`. Falta a consequência sistêmica: líder de
fação morre → fação destabiliza → controle de local muda → rival ocupa. E isso NÃO pode
ser `if npc_id == "npc_valerius"` — tem que valer para **qualquer** entidade com os
componentes certos.

Princípio: *Regras genéricas, não hardcode. Tags + componentes = zero ifs por NPC.*
Entidades ganham `components` (dados); eventos disparam regras declarativas
(`world_rules.json`); a engine executa ações permitidas — **sem `eval`**, só um
resolvedor de paths whitelisted.

## 2. Requisitos

- **R1** — `data/graph/world_rules.json` com 5-10 regras genéricas cobrindo ao menos:
  `npc_killed` (líder de fação; NPC comum), `secret_revealed`,
  `location_control_changed`, `quest_completed`.
- **R2** — `services/rule_engine.py` executa regras: match de trigger → checagem de
  conditions → execução de actions. Sem `eval`/`exec`; valores dinâmicos só via
  resolvedor de paths permitidos (ex.: `component:power_vacuum_trigger.base_instability_delta`).
- **R3** — `entities.json` preenchido com `tags` + `components` para todos os NPCs
  canônicos e as 3 fações (`selo_palido`, `clas_skallgard`, `culto_clareira`).
- **R4** — Ações de regra geram **eventos derivados** (source=`rule_engine`) que passam
  pelo MESMO `apply_event` da 2.6 — auditáveis no `event_log` como qualquer evento.
- **R5** — Cascata limitada: eventos derivados não disparam novas regras além de
  profundidade 2 (anti-loop).
- **R6** — Duas entidades diferentes com componente `faction_leader` disparam a mesma
  regra (testado).
- **R7** — Exceções autorais são raras e explícitas: campo opcional
  `overrides.on_death_rule: "rule_id"` no componente, nunca if por id no código.

### Fora de escopo

- Novos tipos de evento além dos da 2.6.
- Regras econômicas (Fase 5) e de clima.
- UI/notificação para o jogador (a narrativa percebe via context builder, 2.8).
- Editor/validador de regras autoral (Fase 6).

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `data/graph/world_rules.json` | Regras declarativas por tipo de evento |
| `services/rule_engine.py` | Match + execução segura de regras |
| `tests/test_fase27.py` | Suíte da fase |

### Arquivos alterados

- `data/graph/entities.json` — componentes preenchidos
- `services/event_processor.py` — após `apply_event`, chama
  `rule_engine.run_rules(event, state)` e aplica eventos derivados (com limite de profundidade)

### Componentes (schema por convenção, dados em `entities.json`)

```json
{
  "npc_valerius": {
    "id": "npc_valerius",
    "type": "npc",
    "name": "Lorde Valerius",
    "tags": ["noble", "ruler", "faction_leader", "boss"],
    "visibility": "public",
    "components": {
      "faction_member": {"faction_id": "selo_palido", "rank": "leader"},
      "faction_leader": {"successor_id": "npc_darius"},
      "power_vacuum_trigger": {
        "affected_locations": ["nova_arcadia"],
        "rival_factions": ["culto_clareira"],
        "base_instability_delta": -45
      }
    }
  }
}
```

> IDs acima são canônicos do projeto (2.5). `npc_darius` (sucessor) deve ser criado em
> `entities.json` nesta fase se ainda não existir.

Componentes reconhecidos na v1: `faction_member`, `faction_leader`,
`power_vacuum_trigger`, `secret_keeper` (opcional: NPC que guarda segredo — morte revela
ou enterra o fato).

### `data/graph/world_rules.json`

```json
[
  {
    "id": "rule_faction_leader_death",
    "trigger": "npc_killed",
    "conditions": [
      {"target_has_component": "faction_leader"},
      {"target_has_component": "faction_member"}
    ],
    "actions": [
      {"op": "set_entity_state", "entity": "target", "field": "alive", "value": false},
      {"op": "adjust_faction_stability",
       "faction": "component:faction_member.faction_id",
       "delta": "component:power_vacuum_trigger.base_instability_delta"},
      {"op": "disable_controls_edges",
       "faction": "component:faction_member.faction_id",
       "locations": "component:power_vacuum_trigger.affected_locations"},
      {"op": "emit_event", "type": "location_control_changed",
       "targets": "component:power_vacuum_trigger.affected_locations",
       "payload": {"new_controller_id": "component:power_vacuum_trigger.rival_factions[0]"}}
    ]
  },
  {
    "id": "rule_npc_death_generic",
    "trigger": "npc_killed",
    "conditions": [{"target_missing_component": "faction_leader"}],
    "actions": [
      {"op": "set_entity_state", "entity": "target", "field": "alive", "value": false}
    ]
  }
]
```

Regras avaliadas em ordem; TODAS as que casarem executam (não first-match), exceto se a
regra tiver `"exclusive": true`.

### `services/rule_engine.py`

```python
class RuleActionError(Exception): ...

def load_rules() -> List[dict]                      # cache, lê world_rules.json

def resolve_path(expr: str, ctx: dict) -> Any
    # ctx = {"event": GameEvent, "target": entity_dict, "component": components_do_target}
    # Aceita SOMENTE: literais JSON, "event.<campo>", "target.<campo>",
    # "component:<comp>.<campo>" e sufixo de índice "[N]". Qualquer outra coisa → RuleActionError.

def check_conditions(rule: dict, event: GameEvent, projection: WorldProjection) -> bool
    # Suporta: target_has_component, target_missing_component, target_has_tag,
    #          event_payload_equals {"key": ..., "value": ...}

def run_rules(event: GameEvent, state: GameState, depth: int = 0) -> List[GameEvent]
    # Retorna eventos derivados JÁ construídos (source="rule_engine").
    # depth >= 2 → retorna [] (anti-loop).

def execute_action(action: dict, event: GameEvent, state: GameState) -> ActionResult
    # Whitelist de ops: set_entity_state | adjust_faction_stability |
    #                   disable_controls_edges | create_dynamic_edge | emit_event
    # Op desconhecido → RuleActionError (regra ignorada com log, turno não quebra).
```

Semântica das ops (todas operam via `apply_event`/projection, nunca mutação direta fora dela):

| Op | Efeito |
|---|---|
| `set_entity_state` | `projection.entities[id].<field> = value` |
| `adjust_faction_stability` | `entities[faction].stability += delta` (clamp -100..100); espelha em `state.factions[i]` se a fação existir lá (compat com Fase 2 atual) |
| `disable_controls_edges` | edges base `controls` da fação nos locais → `disabled_edges` |
| `create_dynamic_edge` | nova `DynamicEdge` com `created_by_event` |
| `emit_event` | constrói `GameEvent` derivado (1 por target da lista) e retorna para reprocesso |

### Integração no `event_processor`

```python
def process_pending_events(state) -> dict:
    ...
    for event in aplicados:
        derived = rule_engine.run_rules(event, state, depth=0)
        for d in derived:
            projection = apply_event(d, projection)
            event_log.append(d)
            # derivados de derivados: run_rules(d, state, depth=1) — e para em depth 2
```

## 4. Plano passo a passo

### Etapa 1 — Resolver seguro + conditions

1. **Testes** (`tests/test_fase27.py`):
   - `test_resolve_component_path` — `"component:faction_member.faction_id"` com ctx real → `"selo_palido"`.
   - `test_resolve_index` — `"component:power_vacuum_trigger.rival_factions[0]"` funciona.
   - `test_resolve_rejeita_expressao_arbitraria` — `"__import__('os')"`, `"event.__class__"` → `RuleActionError`.
   - `test_conditions_has_component` / `test_conditions_missing_component`.
2. **Implementação:** `resolve_path` + `check_conditions`.
3. `uv run pytest` verde.

### Etapa 2 — Ações + run_rules

1. **Testes:**
   - `test_op_desconhecido_nao_quebra` — regra com op inventado → ignorada com log, sem exceção.
   - `test_adjust_stability_clampa` — delta -200 → stability trava em -100.
   - `test_emit_event_gera_derivado` — action `emit_event` devolve GameEvent com `source="rule_engine"`.
   - `test_profundidade_maxima` — regra que emite evento que dispararia a si mesma → para em depth 2.
2. **Implementação:** `execute_action` + `run_rules` + `load_rules`.
3. `uv run pytest` verde.

### Etapa 3 — Dados: componentes + regras

1. **Testes:**
   - `test_rules_json_valido` — toda regra tem id único, trigger conhecido, ops whitelisted, paths resolvíveis sintaticamente.
   - `test_lideres_tem_componentes_completos` — toda entidade com tag `faction_leader` tem `faction_member` + `faction_leader` + sucessor existente em entities.json.
2. **Implementação:** `world_rules.json` (mínimo: as 2 regras de morte + 1 de `secret_revealed` + 1 de `location_control_changed` + 1 de `quest_completed`); componentes em `entities.json` (Valerius/selo_palido; definir líderes canônicos para clas_skallgard e culto_clareira a partir do lore — criar NPCs se o lore não nomear).
3. `uv run pytest` verde.

### Etapa 4 — Integração + prova de generalidade

1. **Testes:**
   - `test_morte_de_lider_dispara_cascata` — pending `npc_killed` de Valerius → event_log contém derivados (`location_control_changed`), `get_current_controller("nova_arcadia", proj)` mudou, stability ajustada.
   - `test_mesma_regra_dois_lideres` — matar líder do culto_clareira dispara a MESMA `rule_faction_leader_death` (asserta pelo rule_id logado/derivados equivalentes).
   - `test_codigo_nao_menciona_valerius` — grep programático: `services/` e `agents/` não contêm a string `npc_valerius` (só `data/` e testes podem).
2. **Implementação:** hook no `event_processor` (§3).
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [x] Matar qualquer chefe de fação gera destabilização sistêmica (2 líderes testados:
  `npc_kahen`, `npc_o_que_ouve_mais_longe`)
- [x] Nenhum arquivo em `services/`/`agents/` menciona id de NPC específico
  (`test_codigo_nao_menciona_valerius`)
- [x] Eventos derivados aparecem no `event_log` com `source="rule_engine"` (auditável)
- [x] Regra malformada/op desconhecido não quebra o turno (`test_op_desconhecido_nao_quebra`)
- [x] `uv run pytest` verde (201 offline; `test_real_llm` precisa de chave, falha pré-existente)
- [x] Saves antigos continuam carregando (`test_save_antigo_sem_projection_nao_quebra`)

> **Divergências vs. rascunho da spec** (dados reais 2.5b): ids-exemplo (`selo_palido`,
> `clas_skallgard`, `culto_clareira`, `npc_darius`) não existem — usados os canônicos reais
> (`legiao_ferro`, `mao_sombria`, `poder_kahen`, `colmeia_hospedeiros`, ...). Modelo HÍBRIDO:
> estrutura (líder/controle/rival) DERIVADA dos edges (`leads`/`controls`/`enemy_of`/
> `operates_in`); componente `power_vacuum_trigger` guarda só delta/sucessor/override e é o
> DISCRIMINADOR da regra. Componentes vivem em `data/graph/components.json` (overlay
> migration-safe, mergeado por `graph_resolver.load_entities`), NÃO em `entities.json` (que
> `migrate_lore_nova.py` sobrescreve). `run_rules` é dono da cascata (aplica derivados +
> recursa até depth 2); `event_processor` só anexa ao `event_log`.

## 6. Smoke test com LLM real

> **Status:** pendente (quota Gemini). A fase é 100% determinística (zero LLM novo) — a
> cascata foi validada por smoke offline: matar `npc_valerius` → `event_log` ganha
> `location_control_changed` (`source=rule_engine`), `get_current_controller("nova_arcadia")`
> vira `mao_sombria`, stability do novo dono +5 (ripple depth-2). Rodar o roteiro abaixo
> quando houver quota.

1. Campanha real: provocar combate com um líder canônico até a morte → conferir
   `event_log` no save: `npc_killed` + derivados da regra.
2. Próximo turno: perguntar ao narrador "quem controla a cidade agora?" — narrativa
   ainda NÃO precisa refletir (context builder é 2.8), mas o estado no save sim.

## 7. Riscos & compatibilidade

- **Fase toda determinística** — zero chamadas LLM novas; MockLLM irrelevante aqui.
- **Loop de regras:** limite de profundidade 2 + regra `exclusive` disponível.
- **Coexistência com `state.factions`:** o sistema de fações da Fase 2
  (`world_utils.advance_factions` etc.) continua dono de `progress`/`reputation`;
  `stability` vive na projection e espelha via op. Unificação total fica para depois
  da 2.8 (registrar em ROADMAP se incomodar).
- **Segurança:** sem eval; paths whitelisted; ops whitelisted; teste de expressão
  arbitrária obrigatório.
