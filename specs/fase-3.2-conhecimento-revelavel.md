# SPEC — Fase 3.2: Conhecimento revelável (Codex do jogador + bestiário progressivo)

> **Status:** `draft`
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** [fase-2.5-codex-world-state.md](fase-2.5-codex-world-state.md) (`done`),
> [fase-2.6-structured-events.md](fase-2.6-structured-events.md) (`done`)
> **Desbloqueia:** Fase 7 (arte lazy por entidade descoberta), backlog "NPCs 3 camadas"

---

## 1. Contexto & Objetivo

O mundo tem 558 entidades canônicas com documentos ricos (`data/codex/`, frontmatter
`id/type/tags/visibility`) — mas o jogador não vê NADA disso. Descobre um local, conversa
com uma fação, mata 5 lobos-de-gelo… e não existe lugar na interface onde esse
conhecimento se acumula. Critério da Fase 3: "após voltar dias depois, jogador sabe o que
descobriu".

Insight central: **quase todo o conhecimento já está registrado no save** — `world.visited`
(locais), `faction_intel[].known` (fações), `npcs` (personagens), `world_projection.
revealed_facts` (segredos). O Codex do jogador é uma **view derivada** desses registros +
os documentos `.md` do Codex — zero estado novo para essas categorias, zero LLM.

A única lacuna: **criaturas**. Combate não registra o que o jogador enfrentou. O bestiário
progressivo adiciona contadores determinísticos (viu/enfrentou/venceu) e deriva 4 graus de
conhecimento, cada grau revelando mais da ficha (ROADMAP: ouviu falar → 1 encontro →
3 vitórias → conhecimento profundo).

Princípios: "Mecânica é Python" (graus por contador, sem LLM) e "não-onisciência"
(documento `hidden`/`secret` NUNCA aparece; segredo só via `revealed_facts`).

## 2. Requisitos

- **R1** — `state.py` define `BestiaryKnowledge` (`seen`, `fought`, `defeated`,
  `first_seen_turn`, `last_update_turn`) e `GameState.bestiary_knowledge:
  Dict[str, BestiaryKnowledge]` (chave = id do `data/bestiary.json`).
- **R2** — Combate atualiza contadores deterministicamente: spawn em cena → `seen`+1 e
  `fought`+1 por criatura; inimigo com `status="morto"` no fim do round → `defeated`+1.
  Ids de instância normalizam para o id base do bestiário (helper único).
- **R3** — `threat_alerts` regionais (2.5b) marcam `seen` sem `fought` — "ouviu falar"
  de criatura que ainda vai voltar como reforço.
- **R4** — Grau de conhecimento é função pura dos contadores:
  grau 1 "Rumores" (`seen ≥ 1`), grau 2 "Encontrada" (`fought ≥ 1`),
  grau 3 "Estudada" (`defeated ≥ 3`), grau 4 "Dominada" (`defeated ≥ 7`).
  Thresholds em constante única (`BESTIARY_TIERS`).
- **R5** — Cada grau revela um subconjunto crescente da ficha (grau 1: nome+regiões;
  2: +descrição/tipo; 3: +HP máx/defesa/nomes de ataques; 4: +dano exato, behavior
  profile, loot). Campo nunca revelado não sai na API.
- **R6** — `GET /game/codex?game_id=` devolve o Codex do jogador AGREGADO das fontes já
  persistidas: locais (`world.visited`), fações (`faction_intel[].known`), personagens
  (`npcs` + match canônico), segredos (`world_projection.revealed_facts`), criaturas
  (`bestiary_knowledge`). Nada além do que o jogador registrou aparece.
- **R7** — Corpo do documento vem do `.md` do Codex correspondente ao `entity_id`,
  **somente se `visibility: public`**. Docs `hidden`/`secret` não aparecem nem truncados;
  segredos revelados aparecem como fatos (`revealed_facts[].fact`) anexados à entidade.
- **R8** — Frontend ganha aba "Codex" no HUD: categorias (Locais · Fações · Personagens ·
  Bestiário · Segredos), grau visível por criatura, conteúdo carregado on-demand
  (endpoint separado — `GameResponse` não incha).
- **R9** — Saves antigos (sem `bestiary_knowledge`) carregam: campo default `{}`, Codex
  derivado funciona só com as fontes existentes.

### Fora de escopo

- Raças reveláveis (exigiria rastrear raça de NPC encontrada — v2 junto de "NPCs 3 camadas").
- Geração de texto por LLM para entradas de codex (só arquivos existentes + fatos).
- Arte por entidade (Fase 7 — mas o grau do bestiário é o gatilho futuro do lazy-gen).
- Busca textual no codex do jogador.
- Revelar seções parciais de um `.md` `hidden` (visibilidade é por arquivo na 2.5; split
  por seção é item da Fase 6 / technical debt "NPC miscel público+segredo").

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/discovery.py` | Contadores do bestiário, graus, agregação do Codex do jogador |
| `tests/test_fase32.py` | Suíte da fase |
| `web/src/components/CodexTab.tsx` | Aba Codex (categorias + detalhe) |

### Arquivos alterados

- `state.py` — `BestiaryKnowledge` + `GameState.bestiary_knowledge`
- `agents/combat.py` — hooks de `seen/fought` (spawn) e `defeated` (fim de round)
- `world_utils.py` — registro de `seen` ao criar `threat_alerts` (R3)
- `services/codex_loader.py` — `codex_index() -> Dict[id, path]` (cache módulo-level,
  varre frontmatters uma vez; reusa `parse_codex_file`)
- `persistence.py` — save/load do campo novo (default `{}`)
- `api.py` — endpoint `GET /game/codex`
- `game_engine.py` — init `bestiary_knowledge: {}`
- `web/src/types.ts`, `Hud.tsx` (nova Tab), `styles.css`

### Schemas (state.py)

```python
class BestiaryKnowledge(TypedDict, total=False):
    seen: int              # avistada/citada em alerta (rumor)
    fought: int            # combates iniciados contra ela
    defeated: int          # instâncias mortas pelo player
    first_seen_turn: int
    last_update_turn: int
```

### services/discovery.py

```python
BESTIARY_TIERS = {1: ("Rumores", "seen", 1), 2: ("Encontrada", "fought", 1),
                  3: ("Estudada", "defeated", 3), 4: ("Dominada", "defeated", 7)}

def normalize_bestiary_id(enemy: Dict) -> str
    # id de instância → chave do bestiary.json: usa enemy["id"] se existir no DB;
    # senão strip de prefixo "enemy_" e sufixos de instância ("_2", "#2");
    # senão slug do name. Não achou no DB → "" (criatura ad-hoc não entra no bestiário).

def record_encounter(bk: Dict, enemies: List[Dict], turn: int) -> Dict      # seen+fought (puro)
def record_kills(bk: Dict, dead: List[Dict], turn: int) -> Dict             # defeated (puro)
def record_rumor(bk: Dict, creature_id: str, turn: int) -> Dict             # só seen (puro)

def knowledge_tier(entry: BestiaryKnowledge) -> int      # 0..4 (0 = não mostra)

def bestiary_view(bk: Dict) -> List[Dict]
    # junta bk + data/bestiary.json; revela campos POR GRAU:
    # 1: name, regions, tier; 2: +description, type; 3: +max_hp, ac/defense,
    #    attacks (só names); 4: +attacks completos (damage/bonus), behavior, loot.

def player_codex(state: GameState) -> Dict[str, List[Dict]]
    # {"locations": [...], "factions": [...], "characters": [...],
    #  "creatures": bestiary_view(...), "secrets": [...]}
    # locations: world.visited → get_entity + corpo do .md (se public)
    # factions:  faction_intel known → mesma regra (goal só se knows_goal — reusa
    #            a lógica de _factions_block, não-onisciência preservada)
    # characters: npcs runtime; match canônico por nome/alias em load_entities()
    #            (determinístico; sem match → entrada só com dados runtime)
    # secrets:   revealed_facts → {fact, turn, entity_name}
```

`codex_body(entity_id) -> str` (helper): via `codex_index()`; retorna corpo SÓ se
`visibility == "public"`, senão `""`. Corpo truncado a ~2000 chars na API (documentos
têm até 100KB — aba não é leitor de livro; "ler mais" é v2).

### Hooks no combate (agents/combat.py)

- **Spawn/entrada em combate** (onde os inimigos entram no state): 
  `bestiary_knowledge = record_encounter(...)` — 1x por combate (não por round; usar
  flag do combate ativo para não recontar).
- **Fim de round** (bloco existente que separa `dead`, linha ~307):
  `record_kills(bk, dead, turn)` — junto de `_kill_events`, mas SEM depender de id
  canônico do grafo: criatura genérica do bestiário conta para o bestiário do jogador
  mesmo sem ser entidade do mundo.
- **threat_alerts** (`world_utils`): ao criar alerta com criatura concreta →
  `record_rumor` (R3).

Retorno dos nós: `{"bestiary_knowledge": novo_dict}` (dict parcial, convenção do projeto).

### API

```python
@app.get("/game/codex")
def get_player_codex(game_id: Optional[str] = None):
    state = load_game_state(game_id)      # mesmo carregamento do /game/state
    return player_codex(state)
```

`GameResponse` NÃO muda (codex é on-demand ao abrir a aba). Exceção: `world` block pode
ganhar `codex_counts` (nº de entradas por categoria) para badge na aba — opcional, barato.

### Frontend

- `Hud.tsx`: `Tab` ganha `"codex"`; aba lista categorias; fetch de `/game/codex` ao abrir
  (e re-fetch quando `turn` muda com a aba aberta).
- `CodexTab.tsx`: lista por categoria; criatura mostra selo do grau (I–IV) e campos do
  grau; entidade com corpo `.md` mostra excerpt; segredos com turno da revelação.
- Silhueta/placeholder visual para grau 1 (sem stats) — CSS, sem arte.

## 4. Plano passo a passo

### Etapa 1 — Contadores + graus puros

1. **Testes** (`tests/test_fase32.py`):
   - `test_normalize_id_instancia` — `enemy_lobo_de_gelo_2` → chave real do bestiary.json.
   - `test_record_encounter_uma_vez` — 3 lobos no spawn → `fought == 1` (por combate),
     `seen == 1`.
   - `test_record_kills_conta_instancias` — 2 lobos mortos → `defeated == 2`.
   - `test_tier_progressao` — seen=1→1; fought=1→2; defeated=3→3; defeated=7→4.
   - `test_funcoes_puras` — dict original não mutado.
2. **Implementação:** `services/discovery.py` (contadores + `knowledge_tier`).
3. `uv run pytest` verde.

### Etapa 2 — Revelação por grau + view do bestiário

1. **Testes:**
   - `test_view_grau1_sem_stats` — grau 1 não expõe `max_hp`/`attacks`/`loot`.
   - `test_view_grau3_ataques_sem_dano` — nomes de ataque sim, `damage` não.
   - `test_view_grau4_completo` — behavior/loot presentes.
   - `test_criatura_desconhecida_fora` — bestiary.json com 84 entradas, bk com 2 →
     view tem 2.
2. **Implementação:** `bestiary_view`.
3. `uv run pytest` verde.

### Etapa 3 — Hooks no combate + threat_alerts

1. **Testes:**
   - `test_combate_registra_encounter` — combat_node com spawn → state update contém
     `bestiary_knowledge` com `fought ≥ 1`.
   - `test_morte_registra_defeated` — inimigo morto no round → `defeated` incrementa.
   - `test_alerta_gera_rumor` — fuga cria threat_alert → criatura ganha `seen` sem `fought`.
   - Regressão: suíte de combate existente verde.
2. **Implementação:** hooks em `combat.py` e `world_utils.py`.
3. `uv run pytest` verde.

### Etapa 4 — Codex agregado + endpoint

1. **Testes:**
   - `test_codex_index_cacheia` — id → path para entidade conhecida do Codex.
   - `test_codex_body_public_only` — doc `hidden` → corpo `""`.
   - `test_player_codex_deriva_fontes` — state com 2 visited + 1 faction known +
     1 revealed_fact → categorias corretas, nada além.
   - `test_faction_goal_nao_vaza` — fação known sem `knows_goal` → `goal` vazio no codex.
   - `test_endpoint_codex` — TestClient em `/game/codex` com save de fixture.
2. **Implementação:** `codex_index()` no loader, `player_codex`, endpoint, persistência
   do campo novo.
3. `uv run pytest` verde.

### Etapa 5 — Frontend

1. **Implementação:** `CodexTab.tsx`, Tab nova, types, CSS.
2. **Verificação:** `cd web && npm run build` sem erro + `bash scripts/smoke_api.sh` +
   conferência visual (aba lista local visitado e criatura enfrentada).

## 5. Critérios de aceite

- [ ] Matar 3 lobos-de-gelo → bestiário mostra grau "Estudada" com stats; 7 → "Dominada"
      com behavior/loot
- [ ] Criatura citada em threat_alert aparece como "Rumores" (sem stats)
- [ ] Local nunca visitado / fação desconhecida / doc `hidden` NÃO aparecem no codex
- [ ] Segredo revelado (2.5/2.6) aparece na categoria Segredos com turno
- [ ] Fação conhecida sem `knows_goal` não expõe objetivo no codex (não-onisciência)
- [ ] Save antigo carrega; codex funciona só com visited/intel/npcs existentes
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A (fase 100% determinística, zero structured output novo)
- [ ] Saves antigos continuam carregando

## 6. Smoke test com LLM real

(≤3 requests — a fase é determinística; smoke valida integração no fluxo real)

1. Campanha real: viajar a 1 local + combate com criatura do bestiário → abrir aba
   Codex → local + criatura presentes com grau correto.
2. Vencer o combate → grau reflete `defeated`; conferir que threat_alert de fugitivo
   aparece como rumor.
3. Perguntar ao narrador sobre entidade NÃO descoberta → aba Codex segue sem ela
   (narração não revela codex; só registro mecânico revela).

## 7. Riscos & compatibilidade

- **Ids de instância ≠ ids do bestiário:** combate cria instâncias com sufixos; se a
  normalização falhar, contadores se perdem. Mitigação: `normalize_bestiary_id` valida
  contra o DB carregado e testes cobrem os formatos reais de spawn.
- **Documentos grandes:** codex `.md` de até 100KB; API trunca excerpt (~2000 chars).
  NUNCA fazer Read inteiro em teste — fixtures pequenas.
- **Duplo incremento:** combate multi-round não pode recontar `fought` por round — flag
  de combate ativo + teste dedicado.
- **MockLLM/FallbackLLM:** nada muda (zero LLM na fase).
- **Quota/latência:** zero chamadas LLM; endpoint lê save + arquivos locais.
- **Saves antigos:** campo novo com default `{}`; nenhum backfill estrutural necessário.
