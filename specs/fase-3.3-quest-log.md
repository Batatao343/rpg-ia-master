# SPEC — Fase 3.3: Quest log (objetivos visíveis)

> **Status:** `done`
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** [fase-2.6-structured-events.md](fase-2.6-structured-events.md) (`done`),
> [fase-3.1-diario-cronica.md](fase-3.1-diario-cronica.md) (`draft` — usa `arc_title` e o
> hook de crônica; implementar 3.1 primeiro)
> **Desbloqueia:** Fase 5 (quests dinâmicas reagindo ao mundo), 3.4 (marker de objetivo no mapa)

---

## 1. Contexto & Objetivo

Hoje o jogador vê só o "Objetivo Atual" — o beat corrente do `campaign_plan`
(`_quest_block` em api.py). Beats são **efêmeros**: replanejados a cada mudança de local
ou ~10 turnos. Promessa feita por um NPC no turno 5 ("traga a relíquia e te recompenso")
evapora da interface no replan seguinte. Critério da Fase 3: "jogador sabe quais objetivos
pode perseguir".

Distinção central do design:

- **Main quest = view derivada do campaign_plan** (arc_title da 3.1 + clímax + beat
  atual). Zero estado novo, sempre exatamente 1, nunca dessincroniza da campanha.
- **Side quests = estado novo persistente** (`GameState.quests`), propostas pelo LLM
  (storyteller/npc_actor) e **validadas/criadas pelo motor** (LLM propõe, Python aplica).

Ciclo de vida auditável: conclusão passa pelo pipeline de eventos 2.6
(`quest_completed`, validador estendido) e falha sistêmica é determinística — NPC que
originou a quest morreu → quest falha (hook no event_processor, mesmo espírito da
cascata 2.7). Milestones na crônica saem de graça (templates da 3.1).

## 2. Requisitos

- **R1** — `state.py` define `Quest` (`id`, `title`, `description`, `status:
  "active"|"completed"|"failed"`, `origin_name`, `origin_entity_id` opcional,
  `location_id` opcional, `created_turn`, `resolved_turn`, `reward_hint`) e
  `GameState.quests: List[Quest]` (só side quests).
- **R2** — `StoryUpdate` (storyteller) e o structured output do npc_actor ganham
  `proposed_quests: List[ProposedQuest]` (`title`, `description`, `origin_name`,
  `origin_entity_id`, `location_id`, `reward_hint`). Motor valida ANTES de criar:
  `location_id` existe no `world_map.json` (senão zera o campo, não rejeita),
  `origin_entity_id` existe no grafo (senão zera), dedupe por similaridade de título
  (`difflib.SequenceMatcher` ≥ 0.75 contra quests não-resolvidas → ignora), teto de
  quests ativas (`MAX_ACTIVE_QUESTS = 8` → excedente ignorado com log).
- **R3** — Conclusão de side quest via pipeline 2.6: `quest_completed` com
  `payload.quest_id` válido (quest ativa) → `event_processor` marca `completed` +
  `resolved_turn`. Modo atual por `beat_index` continua funcionando (main/beat).
- **R4** — Falha sistêmica determinística: `npc_killed` aplicado → toda quest ativa com
  `origin_entity_id == target_id` vira `failed` (+ evento `quest_failed`
  `source="system"` no event_log, auditável; milestone de crônica).
- **R5** — API: `_quest_block` passa a devolver `main` (arc_title, objetivo=beat atual,
  clímax, beats, progresso — shape atual preservado dentro de `main`) + `side:
  List[Quest]` (ativas primeiro, depois resolvidas recentes) + `markers:
  [{quest_id, location_id}]` para o mapa (quests ativas com local válido).
- **R6** — Frontend: aba "Missões" no HUD — main destacada no topo, side quests com
  status/origem/local; concluídas/falhas com estilo próprio. `WorldMap` recebe
  `markers` e destaca o local do objetivo (render mínimo aqui; polimento visual do
  mapa é 3.4).
- **R7** — Saves antigos (sem `quests`) carregam com `[]`; main quest funciona pois
  deriva do `campaign_plan` existente.
- **R8** — Quests não são onisciência reversa: `proposed_quests` só nasce da cena
  narrada (o prompt exige origem presente na cena — NPC falando, aviso lido, pedido
  explícito). Sem inventar quest de entidade que o jogador não encontrou.

### Fora de escopo

- Quests dinâmicas reagindo a mudanças de mundo além de R4 (fação perdeu local →
  contexto muda) — Fase 5.
- Recompensa mecânica automática ao concluir (ouro/item/XP via engine) — hoje a
  recompensa segue no fluxo narrativo/loot normal; `reward_hint` é só texto. Item
  próprio no backlog.
- Sub-objetivos/etapas por quest (checklist interno).
- Diário de quest com histórico por entrada (a crônica 3.1 já cobre o registro).
- Tracking de quest "seguida" (pin) no HUD.

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/quest_log.py` | Validação/criação/dedupe de side quests + falha sistêmica |
| `tests/test_fase33.py` | Suíte da fase |
| `web/src/components/QuestsTab.tsx` | Aba Missões |

### Arquivos alterados

- `state.py` — `Quest` + `GameState.quests`
- `services/structured_outputs.py` — `ProposedQuest` (Pydantic)
- `agents/storyteller.py` — campo `proposed_quests` no `StoryUpdate` + bloco de prompt
  + chamada a `register_proposed_quests` (dentro do try existente — guard de fallback)
- `agents/npc.py` — idem no structured output do npc_actor
- `services/world_validators.py` — `_v_quest_completed` aceita `payload.quest_id`
  (quest ativa em `state.quests`) além de `beat_index`
- `services/event_processor.py` — aplica `quest_completed` (marca quest) e hook R4
  (npc_killed → quests órfãs falham, emite `quest_failed`)
- `services/chronicle.py` (3.1) — template `quest_failed` em `CHRONICLE_TEMPLATES` +
  tipo em `CHRONICLE_EVENT_TYPES`
- `persistence.py`, `api.py`, `game_engine.py` — campo novo (default `[]`) + blocks
- `mock_llm.py` — MockLLM devolve `proposed_quests` plausível (e vazio no npc)
- `web/src/types.ts`, `Hud.tsx` (Tab "missoes"), `WorldMap.tsx` (markers), `styles.css`

### Schemas

```python
# state.py
class Quest(TypedDict, total=False):
    id: str                 # uuid4 hex
    title: str
    description: str
    status: str             # "active" | "completed" | "failed"
    origin_name: str        # quem/o que originou (nome exibível)
    origin_entity_id: str   # id canônico se houver (habilita R4); "" senão
    location_id: str        # alvo no mapa ("" se não aplicável)
    created_turn: int
    resolved_turn: int
    reward_hint: str        # texto livre ("o ferreiro prometeu 50 moedas")

# services/structured_outputs.py
class ProposedQuest(BaseModel):
    title: str
    description: str = ""
    origin_name: str = ""
    origin_entity_id: str = Field(default="", description="Id canônico EXATO da lista, ou vazio")
    location_id: str = Field(default="", description="Id de local do mapa, ou vazio")
    reward_hint: str = ""
```

### services/quest_log.py

```python
MAX_ACTIVE_QUESTS = 8
TITLE_SIMILARITY = 0.75

def register_proposed_quests(quests: List[Quest], proposals: List[ProposedQuest]|List[dict],
                             *, turn: int) -> Tuple[List[Quest], List[Quest]]
    # PURO. Retorna (lista_nova, criadas). Aceita dicts (proposta pode chegar
    # malformada do fallback — revalida do zero, padrão 2.6):
    #  - title vazio/duplicado (similaridade vs não-resolvidas) → ignora
    #  - location_id fora de gamedata.world_map → "" (não rejeita a quest)
    #  - origin_entity_id fora de graph_resolver.load_entities() → ""
    #  - len(ativas) >= MAX_ACTIVE_QUESTS → ignora com print de log

def fail_orphan_quests(quests: List[Quest], dead_entity_id: str, turn: int)
        -> Tuple[List[Quest], List[GameEvent]]
    # PURO. Ativas com origin_entity_id == dead_entity_id → failed;
    # 1 GameEvent quest_failed (source="system", payload={"quest_id","reason"}) por quest.

def complete_quest(quests: List[Quest], quest_id: str, turn: int) -> List[Quest]

def quest_markers(quests: List[Quest]) -> List[dict]   # ativas com location_id
```

### Pipeline de conclusão/falha

- **Conclusão:** storyteller propõe `quest_completed` com `payload.quest_id` (o prompt
  lista as quests ativas com ids — bloco `<QUESTS_ATIVAS>`; instrução análoga à de
  `<ENTIDADES_CANONICAS>`: id exato, na dúvida vazio). Validador estendido:

```python
def _v_quest_completed(ev, state, proj):
    qid = ev.payload.get("quest_id")
    if qid:
        ativas = {q["id"] for q in state.get("quests", []) if q.get("status") == "active"}
        return ValidationResult(qid in ativas, None if qid in ativas
                                else f"quest_id {qid} não é quest ativa")
    # modo beat (comportamento atual) permanece
    ...
```

- **Aplicação:** `event_processor` — `quest_completed` com `quest_id` → `complete_quest`
  e devolve `quests` nos updates (mesmo padrão do `chronicle` da 3.1).
- **Falha sistêmica (R4):** após aplicar `npc_killed`, chamar `fail_orphan_quests`;
  eventos `quest_failed` entram no event_log (append) e geram milestone (3.1).

### Prompt (storyteller — resumo do bloco novo)

```
<QUESTS_ATIVAS>
{lista: id · título · origem}
Se um personagem PRESENTE NA CENA ofereceu uma missão concreta ao jogador NESTE turno,
registre em 'proposed_quests' (origem = quem pediu; location_id só se o destino é claro).
Se a ação deste turno CONCLUIU uma das quests listadas, proponha 'quest_completed' com
payload.quest_id EXATO. Na dúvida, deixe vazio. NUNCA invente ids.
</QUESTS_ATIVAS>
```

### API

```python
quest = {
  "main": { ...shape atual do _quest_block..., "arc_title": plan.get("arc_title", "") },
  "side": [Quest ativas + resolvidas (últimas 5)],
  "markers": quest_markers(state.get("quests", [])),
}
```

**Compat frontend:** `web/src/types.ts` atualiza junto; campos antigos movem para
`quest.main` (mudança coordenada — frontend é nosso, sem consumidores externos).

## 4. Plano passo a passo

### Etapa 1 — quest_log puro

1. **Testes** (`tests/test_fase33.py`):
   - `test_registra_quest_valida` — proposta completa → quest ativa com turno.
   - `test_dedupe_titulo_similar` — "Caçar o lobo branco" vs "Cace o Lobo Branco" → 1 quest.
   - `test_location_invalida_zerada` — location_id inexistente → quest criada com `""`.
   - `test_teto_de_ativas` — 9ª proposta ignorada.
   - `test_fail_orphan` — morte da origem → failed + GameEvent `quest_failed`.
   - `test_proposta_dict_malformado` — dict sem title → ignorado sem exceção.
2. **Implementação:** `services/quest_log.py` + `Quest`/`ProposedQuest`.
3. `uv run pytest` verde.

### Etapa 2 — Validador + event_processor

1. **Testes:**
   - `test_quest_completed_por_id` — evento com quest_id ativo valida e aplica
     (status completed, `resolved_turn`).
   - `test_quest_completed_id_invalido` — rejeitado, jogo não quebra.
   - `test_quest_completed_beat_index_continua` — modo antigo (regressão 2.6).
   - `test_npc_killed_falha_quest_orfa` — pipeline completo: npc_killed aplicado →
     quest failed + `quest_failed` no event_log + milestone na crônica.
2. **Implementação:** `_v_quest_completed` estendido + hooks no `event_processor` +
   template de crônica.
3. `uv run pytest` verde.

### Etapa 3 — Agentes (storyteller + npc_actor)

1. **Testes:**
   - `test_storyteller_registra_proposed_quests` — MockLLM com proposta → state update
     contém `quests` com a quest criada.
   - `test_npc_propoe_quest` — idem no npc_actor.
   - `test_prompt_lista_quests_ativas` — bloco `<QUESTS_ATIVAS>` presente com ids.
   - Regressão: suítes existentes dos dois agentes verdes.
2. **Implementação:** campos novos + blocos de prompt + `register_proposed_quests`
   dentro dos trys existentes; MockLLM atualizado.
3. `uv run pytest` verde.

### Etapa 4 — API + frontend

1. **Testes:**
   - `test_quest_block_main_side_markers` — shape novo do bloco.
   - `test_save_antigo_sem_quests` — carrega com `[]`, main deriva do plan.
2. **Implementação:** `api.py`, `persistence.py`, `game_engine.py`, `QuestsTab.tsx`,
   markers no `WorldMap.tsx`, types, CSS.
3. `uv run pytest` verde + `npm run build` + `bash scripts/smoke_api.sh`.

## 5. Critérios de aceite

- [x] NPC oferece missão em cena → aparece na aba Missões com origem e local; sobrevive
      a replans da campanha (validado com Gemini real: NPC "Valdir" propôs quest,
      origem sobrescrita pelo código)
- [x] Concluir a missão → status muda via evento validado; crônica registra milestone
      com o TÍTULO da quest (validado com Gemini real)
- [x] Matar o NPC que deu a missão → quest falha automaticamente (evento `quest_failed`
      auditável no event_log) — coberto por `test_pipeline_npc_killed_falha_quest_orfa`
- [x] Proposta com id inventado (entidade/local) não quebra: campos zerados
- [x] Main quest sempre presente e sincronizada com o arco/beat atual (deriva do plan)
- [x] Mapa destaca o local de quest ativa (marker mínimo)
- [x] `uv run pytest` verde (290 testes offline, +32 de `test_fase33.py`)
- [x] Guard de FallbackLLM: campos novos só acessados dentro dos trys existentes de
      storyteller/npc (mesmo padrão de `proposed_events`/`faction_reveals`)
- [x] Saves antigos continuam carregando (`quests` default `[]` já existia em
      `persistence.py` antes desta fase)

## 6. Smoke test com LLM real

(≤5 requests — campos novos de structured output em DOIS agentes: risco clássico
"MockLLM esconde bug de mapeamento", smoke obrigatório)

1. Conversar com NPC que naturalmente ofereça tarefa → conferir `proposed_quests`
   mapeado (quest na aba com origem certa) — valida npc_actor.
2. Turno de história que conclua a tarefa → `quest_completed` com `quest_id` correto —
   valida storyteller + validador.
3. Turno banal → `proposed_quests` vazio (LLM não inventa quest sem origem em cena).
4. (Se quota) matar a origem de uma quest ativa → falha sistêmica aparece no HUD.

## 7. Riscos & compatibilidade

- **LLM spammar quests:** todo diálogo vira "missão". Mitigação: instrução "origem
  presente na cena + pedido concreto", teto de ativas, dedupe por similaridade. Se
  persistir, exigir `origin_entity_id` válido para criar (aperto futuro).
- **Dois agentes com structured output alterado:** dois pontos de mapeamento a validar
  com chave real (smoke itens 1–2). MockLLM atualizado para cobrir o caminho offline.
- **Ordem de merge:** `quests` tocada por storyteller (criação) e event_processor
  (conclusão/falha) em nós diferentes do mesmo turno — archivist roda por último e o
  event_processor lê o state já atualizado? NÃO: nós LangGraph fazem merge de dicts
  parciais por chave — conclusão no archivist (event_processor) sobrescreve a chave
  `quests` do storyteller no MESMO turno. Mitigação: storyteller enfileira proposta em
  `pending_world_events`? Não — decisão: **criação também acontece no event_processor**
  não é necessária; basta o event_processor partir de `state["quests"]` — LangGraph
  aplica updates do storyteller ao state ANTES do archivist rodar (nós são sequenciais
  no grafo: storyteller → archivist). Teste de integração do fluxo completo cobre isso.
- **Saves antigos:** `quests` ausente → `[]`; `arc_title` ausente → main sem título (ok).
- **Quota/latência:** zero chamadas novas (campos pegam carona nos calls existentes).

## 8. Desvios confirmados durante implementação (2026-07-03)

1. Conclusão de quest NÃO ganhou campo estruturado novo — reusa `proposed_events` (2.6):
   `EventType`/`_VALIDATORS`/`CHRONICLE_EVENT_TYPES` já tinham `"quest_completed"`. LLM
   propõe `ProposedWorldEvent(type="quest_completed", target_id=<quest_id>,
   payload={"quest_id": ...})` pelo mesmo canal de `npc_killed`/`secret_revealed`.
2. `apply_event` ficou intocado (contrato "só mexe em projection" preservado). Mutação
   de `state["quests"]` (conclusão/falha) vive só no laço de `process_pending_events`,
   mesmo padrão de `chronicle`/`chronicle_changed`.
3. `render_milestone` (`chronicle.py`) usa `payload.get("quest_title") or
   _name(target_id)` — `target_id` de quest é um uuid (quest_id), não id de grafo;
   `event_processor` embute `quest_title` no payload antes do milestone.
4. `quest_failed` é 100% sistêmico (nunca passa por `validate_proposal`), montado em
   `services/quest_log.py::fail_orphan_quests`, `source="system"`.
5. NPC-origem da quest é resolvido em Python no `npc_actor` (nome + match canônico via
   `graph_resolver.load_entities()`), não confiado ao LLM.
Detalhe completo: plano de implementação da sessão (`vamos-seguir-com-a-velvety-kite`).
