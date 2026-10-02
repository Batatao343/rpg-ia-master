
# SPEC — Fase 2.8: Context builder com orçamento de tokens

> **Status:** `done` (código + suíte; smoke LLM real pendente de quota — ver §6)
> **Criada:** 2026-07-01 · **Atualizada:** 2026-07-03
> **Depende de:** [SPEC-004-fase-2.7-rules-engine.md](SPEC-004-fase-2.7-rules-engine.md) (`done`)
> **Desbloqueia:** Fase 3 (clareza de campanha), encontros sistêmicos, clima

---

## 1. Contexto & Objetivo

Com 2.5–2.7, existe estado dinâmico rico (event_log, projection, edges, summaries) —
mas os agentes ainda montam prompt na mão: `query_rag` + `narrative_summary` + blocos
ad-hoc. Com campanha longa, ou o contexto explode, ou fatos críticos ("o líder morreu
ontem") ficam de fora e o narrador contradiz o mundo.

Esta fase centraliza a montagem: `build_context_pack()` ranqueia fatos dinâmicos por
relevância+impacto+recência, respeita um **orçamento de tokens** e devolve um bloco
`<ESTADO_ATUAL_DO_MUNDO>` pronto. **Estado atual entra ANTES de lore base** — a verdade
viva vence o canônico quando conflitam.

## 2. Requisitos

- **R1** — `services/context_builder.py` expõe
  `build_context_pack(state, query, purpose, token_budget=3500) -> ContextPack`.
- **R2** — Orçamento reservado por seção (percentuais configuráveis):
  current_state 25%, active_location 20%, relations 15%, entities 15%, lore 15%,
  session_memory 10%. Seção que não usa sua cota cede o excedente às seguintes.
- **R3** — Fatos dinâmicos ranqueados por
  `score = 0.35*relevance + 0.25*location_match + 0.20*entity_match + 0.10*impact + 0.10*recency`.
- **R4** — Saída nunca excede `token_budget` (estimativa `len(chars)/4`, margem de 5%).
- **R5** — Fatos com `visibility` acima do permitido para o `purpose` não entram
  (storyteller narra público+revelado; validador interno pode ver tudo).
- **R6** — `storyteller`, `npc_actor`, `combat` (narração) e `campaign_manager`
  consomem o context builder no lugar dos blocos manuais de lore/estado.
- **R7** — 50 eventos no mesmo local → prompt contém só os top-N que cabem no budget,
  sem estourar (teste).

### Fora de escopo

- Streaming/SSE (infra `stream_ctx.py` já existe, não muda aqui).
- Tokenizer real por provider — heurística chars/4 basta na v1.
- UI de debug do contexto (útil na Fase 4/telemetria).
- Mudar cadência do campaign_manager (bug de plot twist frequente é item separado do backlog).

## 3. Design técnico

> **Correções vs código (validadas 2026-07-03, aplicadas na implementação):**
> - `GameEvent` (state.py:139) tem `turn` (não `day`), `actor_id`/`target_id` (não `actor`/
>   `target`); `detail` mora em `payload["detail"]`. Render usa `[turno N]`.
> - `GameEvent` NÃO tem `visibility`. Visibilidade existe em 2 canais: lore via
>   `query_rag(..., max_visibility="public")` (rank public<hidden<secret); edges via
>   `resolve_edges(..., include_hidden=False)` (booleano). Eventos do log são fatos ocorridos
>   (públicos); `secret_revealed` só aparece se estiver em `world_projection.revealed_facts`.
> - `location_summaries` e `revealed_facts` são sub-chaves de `world_projection`, não top-level.
> - `build_context_pack` ganha `game_id: Optional[str] = None` (só storyteller passa — busca
>   híbrida lore+sessão; campaign/npc não). View de fação diverge por purpose: `story` = só
>   `intel.known` não-defeated; `npc` = todas não-defeated.
> - Memória de NPC reusa `query_npc_memory(game_id, npc_id, query, k=3)` (rag.py:183).

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/context_builder.py` | Ranking, budget e montagem do pack |
| `tests/test_fase28.py` | Suíte da fase |

### Arquivos alterados

- `agents/storyteller.py` — substitui `query_rag` manual + blocos de fação/memória
  pelos campos do pack (mantém estrutura do prompt; muda a origem do conteúdo)
- `agents/npc.py` — pack com `purpose="npc"` (inclui memória do NPC via `query_npc_memory`)
- `agents/combat.py` — pack enxuto (`token_budget=1200`) só para a narração
- `agents/campaign_manager.py` — pack com `purpose="planning"`

### Tipos e assinaturas

```python
PURPOSES = ("story", "npc", "combat_narration", "planning")

@dataclass
class ContextBudget:
    max_tokens: int = 3500
    reserved: Dict[str, float] = field(default_factory=lambda: {
        "current_state": 0.25,   # projection do aqui-agora (controlador, vivos/mortos, clima/clock)
        "active_location": 0.20, # summary dinâmico + lore do local atual
        "relations": 0.15,       # edges relevantes (resolve_edges)
        "entities": 0.15,        # EntityState + codex das entidades citadas na query/cena
        "lore": 0.15,            # query_rag global (respeitando visibility)
        "session_memory": 0.10,  # narrative_summary + RAG da sessão
    })

@dataclass
class ScoredFact:
    text: str
    score: float
    section: str
    source_id: str        # event_id / edge_id / chunk id (auditoria)

@dataclass
class ContextPack:
    world_state_block: str    # "<ESTADO_ATUAL_DO_MUNDO>...</...>" pronto p/ prompt
    lore_block: str
    memory_block: str
    total_tokens_est: int
    dropped: int              # quantos fatos ranqueados ficaram de fora (telemetria)

def estimate_tokens(text: str) -> int            # ceil(len(text) / 4)

def score_fact(fact_text: str, *, query: str, current_loc: str,
               scene_entities: List[str], impact: float, turns_ago: int) -> float
    # relevance: overlap de termos query×fato (normalizado 0..1; sem embeddings — barato)
    # location_match: 1.0 se cita current_loc/alias, senão 0
    # entity_match: fração das scene_entities citadas
    # impact: npc_killed/control_changed=1.0, secret_revealed=0.8, demais=0.4
    # recency: max(0, 1 - turns_ago/50)

def collect_dynamic_facts(state: GameState, *, purpose: str) -> List[ScoredFact]
    # event_log (últimos 100) renderizados em 1 frase cada + dynamic_edges +
    # location_summaries; filtra visibility por purpose

def build_context_pack(state: GameState, query: str, purpose: str,
                       token_budget: int = 3500,
                       game_id: Optional[str] = None) -> ContextPack
```

Montagem: para cada seção na ordem de `reserved`, preenche com fatos ranqueados até a
cota; sobra de cota rola para a próxima seção; corta no limite global com margem 5%.

### Renderização de eventos em fatos

Cada `GameEvent` vira 1 linha determinística (sem LLM), ex.:

```
[turno 12] Lorde Valerius foi morto (por: player).
```

Template por `type` em dict módulo-level `EVENT_TEMPLATES: Dict[str, str]`.

### Uso no storyteller (exemplo)

```python
pack = build_context_pack(state, query=f"{loc} {last_user_input}", purpose="story")
```

No prompt, `<ESTADO_ATUAL_DO_MUNDO>` entra ANTES de `<LORE_E_FATOS_PASSADOS>`, com a
instrução: "Se o estado atual contradisser o lore, o estado atual VENCE."

## 4. Plano passo a passo

### Etapa 1 — Score + budget puros

1. **Testes** (`tests/test_fase28.py`):
   - `test_estimate_tokens` — string de 400 chars → 100.
   - `test_score_pondera_local` — fato citando local atual > fato idêntico sem local.
   - `test_score_recencia_decai` — turns_ago 0 > turns_ago 40.
   - `test_budget_nunca_estoura` — 200 fatos grandes → `total_tokens_est <= budget*1.05`.
   - `test_sobra_de_cota_rola` — seção vazia → seção seguinte usa o espaço.
2. **Implementação:** `estimate_tokens`, `score_fact`, montador de seções.
3. `uv run pytest` verde.

### Etapa 2 — Coleta de fatos dinâmicos

1. **Testes:**
   - `test_event_vira_frase` — `npc_killed` renderiza com nome (não id cru) e turno.
   - `test_visibility_por_purpose` — fato `secret` não revelado fora do pack `story`;
     revelado (em `revealed_facts`) entra.
   - `test_50_eventos_top5` — 50 eventos no mesmo local, budget apertado → pack contém
     os de maior score (morte/controle recentes), `dropped > 0`.
2. **Implementação:** `EVENT_TEMPLATES` + `collect_dynamic_facts` + `build_context_pack`.
3. `uv run pytest` verde.

### Etapa 3 — Integração storyteller

1. **Testes:**
   - `test_storyteller_usa_pack` — monkeypatch em `build_context_pack` confirmando
     chamada com `purpose="story"`; prompt do nó contém `<ESTADO_ATUAL_DO_MUNDO>`.
   - Regressão: suíte existente do storyteller continua verde.
2. **Implementação:** trocar montagem manual (lore_context, faccoes_conhecidas,
   narrative_summary) pelos blocos do pack — cuidado para MANTER `faction_impacts`
   e `beat_completed` funcionando (a lista de fações conhecidas com ids exatos
   continua no prompt, agora vinda do pack/section relations).
3. `uv run pytest` verde.

### Etapa 4 — Integração npc_actor, combat, campaign_manager

1. **Testes:** análogos ao da etapa 3, um por agente (purpose certo, budget do combate = 1200).
2. **Implementação:** cada agente troca sua montagem manual pelo pack.
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [x] Contexto nunca excede o orçamento (teste com 200 fatos — `test_budget_nunca_estoura`)
- [x] Storyteller recebe `<ESTADO_ATUAL_DO_MUNDO>` antes de lore base, com regra de precedência
- [x] 50 eventos em 1 local → prompt inclui só os top relevantes (`test_50_eventos_top5`)
- [x] Segredo não revelado nunca entra em pack de `purpose="story"`/`"npc"`
      (`test_secret_so_se_revelado`: só entra se em `world_projection.revealed_facts`)
- [x] 4 agentes integrados (storyteller/npc/combat/campaign): `query_rag`+`narrative_summary`
      manuais trocados pelo pack. **Nota:** blocos de reputação (`factions`/`intel`) PERMANECEM
      nos agentes — são sistema à parte (não são lore/RAG nem estado do grafo), e mantê-los preserva
      `faction_impacts`/`faction_reveals`. "Lore/estado" aqui = RAG global + resumo + event/edge.
- [x] `uv run pytest` verde (216 offline: 201 baseline + 15 da 2.8)
- [x] Saves antigos continuam carregando (`world_projection`/`event_log` são `total=False`,
      tudo via `.get`; projection vazia → pack degrada para só lore+summary)

## 6. Smoke test com LLM real

> **Pendente de quota** (free tier 20 req/dia/modelo). A fase é determinística e NÃO
> adiciona nenhum `with_structured_output` novo (pack é puro), então o risco "MockLLM
> esconde bug de mapeamento" é baixo aqui. Rodar quando houver quota:

1. Campanha com 1 morte de líder (2.7): próximo turno, perguntar "quem manda aqui
   agora?" → narrador responde coerente com a projection (novo controlador).
2. Perguntar sobre segredo não revelado → narrador NÃO vaza (fato ficou fora do pack).
3. Conferir log `dropped`/`total_tokens_est` num turno com histórico longo — budget
   respeitado.

## 7. Riscos & compatibilidade

- **Regressão de prompt:** storyteller é o coração do jogo; mudar a origem do contexto
  pode mudar o tom. Mitigação: manter a MESMA estrutura de tags no prompt e integração
  agente-a-agente (etapas 3-4 separadas), com smoke test real após cada uma.
- **Relevance sem embeddings:** overlap de termos é grosseiro, mas barato e offline;
  se ficar ruim, trocar por similaridade FAISS depois (interface não muda).
- **MockLLM:** pack é determinístico e testável offline; nada muda no mock.
- **Latência/quota:** zero chamadas LLM extras; `query_rag` continua 1x por turno
  (agora dentro do builder).
