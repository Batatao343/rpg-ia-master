# SPEC — Fase 3.4: Visualização de estado (mapa dinâmico + histórico de reputação)

> **Status:** `done`
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** [fase-2.7-rules-engine.md](fase-2.7-rules-engine.md) (`done`),
> [fase-2.5b-valoria-dados-mecanicos.md](fase-2.5b-valoria-dados-mecanicos.md)
> (`in-progress` — usa `threat_alerts`)
> **Desbloqueia:** critério de aceite da Fase 3 fecha com esta spec

---

## 1. Contexto & Objetivo

O estado do mundo evoluiu (event_log, projection, rules engine), mas a interface mostra
quase nada disso. Dois gaps:

1. **Mapa estático demais.** `WorldMap.tsx` já pinta local atual, fog of war,
   `controlled` e `danger_overrides` — mas `controlled` é o campo LEGADO da Fase 2
   (`world.controlled`, escrito por ascensão de fação). A verdade pós-2.5/2.7 é
   `get_current_controller(loc, projection)` — quando a rules engine muda o controle de
   Brekmar, o mapa não fica sabendo. `threat_alerts` (2.5b) e `looming_threat` também
   não aparecem.
2. **Reputação sem história.** `apply_reputation` retorna um evento efêmero que morre no
   turno. O jogador vê o número atual e não sabe O QUE o levou até ali. ROADMAP pede
   "timeline visual por facção (estabilidade, mudanças recentes)".

Solução alinhada à arquitetura: **tudo view derivada do event_log/projection** (nada de
estado paralelo) + **1 tipo de evento novo** (`reputation_changed`) para que mudanças de
reputação entrem no log auditável como o resto do mundo (via pipeline 2.6).

Não-onisciência preservada: mapa só mostra o que está dentro do fog of war
(`world.visited`); fações só as `intel.known`; estabilidade interna vira rótulo
qualitativo, nunca o número interno da projection.

## 2. Requisitos

- **R1** — Mudança de reputação (storyteller aplica `faction_impacts` via
  `apply_reputation`) enfileira proposta `reputation_changed` em `pending_world_events`
  (`payload: {delta, new_value, reason}`; `source="storyteller"`); validador novo
  (fação existe no grafo e não-defeated) + aplicação no event_processor (evento é fato
  consumado determinístico — validação é sanidade, não gate de LLM).
- **R2** — `_factions_block` ganha, por fação conhecida: `history: [{turn, delta,
  value}]` (derivado do event_log, últimos `N=20` eventos `reputation_changed` da
  fação) e `stability_label: "estável"|"instável"|"em colapso"` (derivado de
  `projection.entities[fid].stability` por limiares; ausente → "estável"). O número
  cru de stability NUNCA sai na API.
- **R3** — `_world_block` ganha `map_overlays`:
  - `control_changes: [{location_id, controller_name, turn}]` — eventos
    `location_control_changed` dos últimos `RECENT_TURNS=30` cujo local ∈
    `world.visited` (fog of war vale para overlay também);
  - `threats: [{region_id, hint, turn}]` — `world.threat_alerts` não expirados;
  - `looming_threat: str` — campo existente, agora exposto.
- **R4** — `controlled` exibido no mapa unifica legado + projection:
  `get_current_controller(loc_id, projection)` para cada local visitado vence
  `world.controlled` quando divergirem (verdade 2.5+ manda; edges hidden/secret NÃO
  contam — usar `resolve_edges(include_hidden=False)` variante do resolver, visão do
  jogador).
- **R5** — Frontend `WorldMap.tsx`: badge de controlador recém-mudado (marcador visual
  distinto quando `control_change.turn` está a ≤10 turnos), ícone de ameaça na região
  com alerta ativo, banner discreto de `looming_threat`.
- **R6** — Frontend `FactionsTab`: sparkline SVG inline (sem lib) da `history` +
  rótulo de estabilidade + lista das 3 mudanças mais recentes ("turno 12: ajudou +10").
- **R7** — Derivações são funções puras testáveis em `services/state_views.py`
  (Python decide; api.py só chama).
- **R8** — Saves antigos: sem event_log/projection → `history=[]`,
  `stability_label="estável"`, overlays vazios; nada quebra.

### Fora de escopo

- Gráfico de estabilidade numérico ao longo do tempo (o interno fica interno; rótulo
  qualitativo basta na v1).
- Mudanças de controle em locais NÃO visitados chegarem como rumor (sistema de rumores
  é candidato à Fase 5/NPCs).
- Redesenho visual do mapa (posições, arte, zoom) — só overlays sobre o render atual.
- Marker de quest no mapa — já entregue na 3.3.
- Histórico de reputação retroativo para campanhas existentes (eventos passam a ser
  logados daqui em diante).

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/state_views.py` | Derivações puras: history, stability_label, map_overlays, controle unificado |
| `tests/test_fase34.py` | Suíte da fase |

### Arquivos alterados

- `agents/storyteller.py` — após `apply_reputation` com evento não-None, appenda
  proposta `reputation_changed` a `pending_world_events` (já dentro do try)
- `services/world_validators.py` — `_v_reputation_changed`
- `services/event_processor.py` — aplicação (no-op na projection; evento só entra no
  log — reputação mora em `factions`, que o storyteller já atualizou)
- `services/chronicle.py` (3.1) — `reputation_changed` fica FORA de
  `CHRONICLE_EVENT_TYPES` (ruído; timeline da fação é o lugar dele)
- `api.py` — `_factions_block` (history/stability_label) + `_world_block` (map_overlays,
  controlled unificado)
- `web/src/components/WorldMap.tsx`, `Hud.tsx` (FactionsTab), `types.ts`, `styles.css`

### services/state_views.py

```python
RECENT_TURNS = 30
STABILITY_LABELS = ((-100, "em colapso"), (-30, "instável"), (30, "estável"))  # limiares

def reputation_history(event_log: List[GameEvent], faction_id: str, limit: int = 20)
        -> List[dict]        # [{turn, delta, value}] em ordem cronológica

def stability_label(projection: dict, faction_id: str) -> str

def recent_control_changes(event_log: List[GameEvent], visited: List[str],
                           current_turn: int) -> List[dict]
    # location_control_changed com turn >= current_turn - RECENT_TURNS e
    # target_id ∈ visited; controller_name via gr.get_entity (nome, não id)

def active_threats(world: dict, current_turn: int) -> List[dict]
    # threat_alerts não expirados (mesmo TTL do world_utils._ALERT_TTL — importar)

def visible_controllers(world: dict, projection: dict) -> Dict[str, str]
    # para cada loc ∈ visited: controller via resolve_edges(include_hidden=False,
    # edge_type="controls"); fallback world.controlled[loc]; valor = NOME da fação
```

### Evento novo (pipeline 2.6)

```python
# proposta enfileirada pelo storyteller (Python, não LLM):
{"type": "reputation_changed", "actor_id": "player", "target_id": fid,
 "payload": {"delta": ev["delta"], "new_value": ev["reputation"],
             "reason": direction},   # "ajudou" | "prejudicou"
 "source": "storyteller"}

def _v_reputation_changed(ev, state, proj):
    f = gr.get_entity(ev.target_id)
    if not f or f.get("type") != "faction":
        return ValidationResult(False, f"{ev.target_id} não é facção")
    if not gr.is_alive(ev.target_id, proj):
        return ValidationResult(False, f"facção {ev.target_id} está derrotada")
    return ValidationResult(True)
```

`apply_event` para `reputation_changed`: **no-op na projection** (o valor vivo mora em
`state.factions`, já atualizado pelo storyteller no mesmo turno) — o evento existe pelo
LOG (auditoria + timeline). Comentário no código deixando isso explícito.

**Nota fog-of-war da timeline:** eventos só são consultados para fações `intel.known`
(o `_factions_block` já filtra antes de chamar `reputation_history`) — reputação de
fação desconhecida continua invisível mesmo estando no log.

### API (shapes)

```python
# _factions_block item ganha:
"history": [{"turn": 12, "delta": 10, "value": 25}, ...],
"stability_label": "instável",

# _world_block ganha:
"map_overlays": {
    "control_changes": [{"location_id": "brekmar", "controller_name": "Garra Vermelha", "turn": 41}],
    "threats": [{"region_id": "skallgard", "hint": "Soldado da Legião", "turn": 44}],
    "looming_threat": "",
},
# e "controlled" passa a vir de visible_controllers (nomes, com fallback legado)
```

**Atenção compat:** `controlled` hoje é `Dict[loc_id, faction_id]` e o front pinta
`is-controlled`. Passar a mandar NOME mantém o front simples (exibição direta); types.ts
atualiza junto. Fallback: se resolver não achar nada, manda o valor legado.

### Frontend

- `WorldMap.tsx`: prop nova `overlays`; nó com control_change recente ganha classe
  `is-contested` (badge/pulso); região com threat ganha ícone ⚠ com tooltip `hint`;
  `looming_threat` vira banner acima do mapa.
- `FactionsTab`: sparkline SVG (`<polyline>`, ~20 pontos, eixo -100..100), rótulo de
  estabilidade colorido, últimas mudanças em texto ("turno 12 · +10").

## 4. Plano passo a passo

### Etapa 1 — Views puras

1. **Testes** (`tests/test_fase34.py`):
   - `test_history_ordena_e_limita` — 25 eventos → 20, ordem cronológica, values corretos.
   - `test_history_ignora_outras_faccoes` — eventos de outra fação fora.
   - `test_stability_label_limiares` — -50→"instável" ... (cobrir os 3 rótulos e ausente).
   - `test_control_changes_respeita_fog` — mudança em local não visitado → fora.
   - `test_control_changes_janela` — evento com turn antigo (>30) → fora.
   - `test_visible_controllers_projection_vence` — dynamic edge de controle vence
     `world.controlled` legado; edge hidden NÃO aparece.
2. **Implementação:** `services/state_views.py`.
3. `uv run pytest` verde.

### Etapa 2 — Evento reputation_changed no pipeline

1. **Testes:**
   - `test_storyteller_enfileira_reputation_changed` — faction_impact aplicado →
     proposta em `pending_world_events` com delta/new_value.
   - `test_validador_reputation` — fação inexistente/defeated rejeita; válida passa.
   - `test_apply_noop_projection` — aplicar não toca `projection.entities`.
   - `test_nao_vira_milestone` — crônica (3.1) não ganha entrada.
   - Regressão: suíte 2.6/2.7 verde.
2. **Implementação:** storyteller + validador + apply.
3. `uv run pytest` verde.

### Etapa 3 — API

1. **Testes:**
   - `test_factions_block_history_so_known` — fação desconhecida sem history mesmo com
     eventos no log.
   - `test_world_block_overlays` — shape completo com fixture de event_log +
     threat_alerts.
   - `test_save_antigo_overlays_vazios` — sem event_log/projection → defaults (R8).
2. **Implementação:** `_factions_block` + `_world_block`.
3. `uv run pytest` verde + `bash scripts/smoke_api.sh`.

### Etapa 4 — Frontend

1. **Implementação:** overlays no `WorldMap.tsx`, sparkline/estabilidade na
   `FactionsTab`, types, CSS.
2. **Verificação:** `npm run build` sem erro; conferência visual com save de fixture
   (mapa com badge de controle + ameaça; fação com sparkline).

## 5. Critérios de aceite

- [x] Matar líder de fação (cascata 2.7 muda controle) → mapa mostra badge de novo
      controlador no local (se visitado) sem tocar código específico do NPC
- [x] Ajudar/prejudicar fação em turnos distintos → sparkline com pontos e lista de
      mudanças com turnos (`test_history_ordena_e_limita`)
- [x] Fação desconhecida (intel) não expõe history nem estabilidade; número interno de
      stability nunca aparece na API (`test_factions_block_history_so_known`)
- [x] Local não visitado não aparece em `control_changes` (fog of war)
- [x] threat_alert ativo aparece no mapa; expirado some (TTL de `world_utils._ALERT_TTL`)
- [x] Save antigo carrega com overlays vazios e fações sem history
- [x] `uv run pytest` verde (313 testes offline, +23 de `test_fase34.py`)
- [x] Guard de FallbackLLM: N/A confirmado — zero structured output novo (evento
      `reputation_changed` é gerado por Python, não proposto pelo LLM)
- [x] Saves antigos continuam carregando

## 6. Smoke test com LLM real

(≤3 requests — fase determinística; smoke valida o fluxo integrado)

1. Ação clara pró-fação conhecida → conferir evento `reputation_changed` no event_log
   do save e ponto novo na sparkline.
2. Matar líder com cascata → badge de controle no mapa + rótulo de estabilidade da
   fação muda.
3. Fugir de combate → alerta ⚠ na região; descansar além do TTL → alerta some.

## 7. Riscos & compatibilidade

- **Dupla contabilidade de reputação:** valor vivo em `state.factions` E eventos no
  log podem divergir se algum caminho alterar reputação sem logar (ex.: futuro
  world_simulator). Mitigação: comentário em `apply_reputation` apontando o contrato
  ("quem chama e persiste, loga"); teste de integração cobre o caminho do storyteller.
  Divergência não corrompe nada — timeline fica incompleta, valor atual segue correto.
- **`controlled` muda de id→nome:** front e types atualizam juntos; nenhum consumidor
  externo. Teste de shape trava o formato novo.
- **event_log crescente:** derivações fazem scan linear — ok para centenas de eventos;
  se campanha passar de milhares, indexar por tipo (otimização adiada, interface pura
  não muda).
- **MockLLM/FallbackLLM:** nada muda (zero LLM novo).
- **Quota/latência:** zero chamadas LLM; +1 evento por mudança de reputação no save
  (bytes, não requests).

## 8. Desvios confirmados durante implementação (2026-07-03)

1. `event_processor.py` NÃO precisou de nenhuma mudança: `apply_event` já tem
   fallthrough no-op pra tipo sem `elif`; `_chronicle_milestone` já pula tipos fora de
   `CHRONICLE_EVENT_TYPES`. `reputation_changed` só precisou de entrada no `EventType`
   Literal + validador.
2. `get_current_controller` (`graph_resolver.py`) ganhou `include_hidden: bool = True`
   (default retrocompatível) em vez de duplicar a lógica "dynamic edge vence base" em
   `visible_controllers`.
3. `region_id` por local já vinha cru de `GET /data/map` (world_map.json já tem o
   campo) — só o tipo TS `MapLocation` estava desatualizado.
Detalhe completo: plano de implementação da sessão (`vamos-seguir-com-a-velvety-kite`).
