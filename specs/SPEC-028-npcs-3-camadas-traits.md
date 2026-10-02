# SPEC — NPCs em 3 camadas + traits ocultos com revelação progressiva

> **Status:** `done` (2026-07-06)
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** 2.6 (structured events) `done`; 3.2 (codex do jogador) `done`; 2.8 (context builder) `done`
> **Desbloqueia:** correção estrutural do bug "NPC errado responde"; profundidade de NPC sem custo de LLM

---

## 1. Contexto & Objetivo

Os NPCs da sessão vivem num dict plano (`GameState.npcs`) sem noção de ONDE
estão nem de QUEM o jogador conhece: o `npc_actor` responde por qualquer nome
que o router escolher — origem do bug conhecido "NPC errado responde fala
destinada a outro" — e um NPC de Skallgard atende o jogador no Deserto de Zhur
se o LLM alucinar a cena. Além disso, todo NPC nasce raso: a persona gerada é
estática, sem nada a descobrir em interações repetidas.

Esta spec organiza os NPCs em **3 camadas** (todos da sessão → conhecidos pelo
jogador → presentes em cena) e dá **traits ocultos determinísticos** (sorteio
seeded em Python na criação, catálogo curado em `data/traits.json`) revelados
progressivamente por contagem de interações. Camada 3 fecha o bug do NPC
errado por construção: falar com quem não está em cena devolve resposta
determinística "X não está aqui" sem gastar LLM.

Princípios: **LLM propõe, motor valida** (presença em cena vem de canal
estruturado validado); **mecânica é Python** (traits, revelação e contagem são
código+dado, o LLM só interpreta o que já foi revelado).

## 2. Requisitos

- **R1 — Schema de NPC estendido:** cada entrada de `GameState.npcs` ganha
  `home_location_id: str`, `hidden_traits: list[str]`,
  `revealed_traits: list[str]`, `interaction_count: int`,
  `known_by_player: bool`, `knowledge_source: str` (`met|mentioned|lore`),
  `in_scene: bool`. Backfill no load: NPC antigo ganha defaults
  (`known_by_player=True`, `knowledge_source="met"`, `in_scene=False`,
  `home_location_id=local atual do save`, traits sorteados na hora).
- **R2 — Catálogo de traits:** `data/traits.json` com **80 traits** curados:
  `{id, name, description, dc_modifiers: {<contexto>: int}, reveal_after: int,
  tags: [..]}`. Contextos de DC: `persuasao`, `intimidacao`, `comercio`,
  `insight` (usados em R6). `reveal_after` = interações necessárias (3–8).
- **R3 — Sorteio determinístico:** na criação (`generate_new_npc` e backfill),
  o NPC recebe 1–3 `hidden_traits` sorteados com RNG seeded por
  `hash(npc_id + game_id)` — mesmo NPC no mesmo save sorteia igual (replay
  estável); LLM NÃO escolhe traits.
- **R4 — Camada 3 (in_scene) como gate do npc_actor:** router escolheu
  `active_npc_name` cujo NPC tem `in_scene=False` → o nó devolve mensagem
  determinística "«X» não está aqui." (sem chamada LLM) e sugere onde foi
  visto (`home_location_id`). NPC inexistente no dict segue o fluxo atual
  (criação via `generate_new_npc` só quando a CENA o introduziu — R5).
- **R5 — Presença gerida por canal estruturado:** `StoryUpdate` (storyteller)
  ganha `npcs_in_scene: list[str]` (nomes que ENTRARAM na cena) e
  `npcs_left_scene: list[str]`; motor valida (nome resolve por
  librarian/dedupe; entrada desconhecida vira NPC novo com
  `home_location_id = local atual`). Determinístico: **viagem zera
  `in_scene` de todos** (ninguém teleporta junto — exceto party 4.5, que tem
  estado próprio); NPC alvo de conversa bem-sucedida marca
  `known_by_player=True, knowledge_source="met"`.
- **R6 — Traits aplicam DC modifiers em Python:** onde o motor já resolve
  interação social/comercial: encontro social 6.4 (`detection/negotiation`) e
  preço/recepção de mercador 4.4 somam `dc_modifiers` dos traits do NPC
  (ocultos TAMBÉM contam — o mundo é real antes de ser conhecido); prompt do
  `npc_actor` só recebe os `revealed_traits` (não-onisciência do narrador
  sobre o interior do NPC é aceitável: o trait oculto age via número, não via
  prosa).
- **R7 — Revelação progressiva:** ao fim de cada turno de NPC bem-sucedido,
  `interaction_count += 1`; trait oculto com `interaction_count >= reveal_after`
  move para `revealed_traits` + linha no diário ("Você percebe que Grum é
  Supersticioso.") + passa a entrar no prompt do npc_actor. 100% Python.
- **R8 — Camada 2 no frontend:** aba Personagens (estende o bloco de NPCs do
  `CodexTab` 3.2): lista só `known_by_player=True`, mostrando nome, papel,
  local onde foi visto, `knowledge_source` e `revealed_traits` (ocultos nunca
  aparecem). NPC `mentioned` (citado por outro NPC/narrador via R5) aparece
  acinzentado como "ouviu falar".
- **R9 — Anti-vazamento:** `hidden_traits` nunca sai pela API
  (`/game/state`, `/game/codex` filtram), nunca entra em prompt e nunca
  aparece no frontend. Teste asserta.

### Fora de escopo

- Agenda/rotina de NPC (NPC se move sozinho pelo mundo) — world_simulator já
  cobre off-screen no nível de fação; movimento individual fica pra depois.
- Traits que mudam combate (só contextos sociais/comerciais nesta fatia).
- Reescrever memória vetorizada de NPC (add_npc_memory continua igual).
- Party (4.5) — companions têm fluxo próprio; só a isenção do reset de viagem.

## 3. Design técnico

### Arquivos novos

- `data/traits.json` — catálogo (80 traits curados; escrever com auxílio de
  IA e revisar à mão, ancorando tags nas regiões/fações de Valoria).
- `services/npc_layers.py` — funções puras: sorteio de traits, revelação,
  reset de cena, filtro de camadas p/ API.
- `tests/test_npc_camadas.py`

### Arquivos alterados

- `state.py` — comentário do campo `npcs` documenta o shape novo (dict
  continua `Dict[str, Dict]` — sem quebra de schema).
- `agents/npc.py` — gate R4 no topo do `npc_actor_node`; `interaction_count`/
  revelação R7 no fim; `generate_new_npc` chama o sorteio R3; prompt recebe
  `revealed_traits`.
- `agents/storyteller.py` + `services/structured_outputs.py` — campos R5 no
  `StoryUpdate` + validação/aplicação (mesmo padrão dos canais 2.6).
- `world_utils.py` (`apply_travel`) ou storyteller — reset de `in_scene` na
  viagem (decidir na implementação; travel é o lugar determinístico).
- `persistence.py` — backfill R1 no load.
- `api.py` — filtro R9 + payload da aba Personagens.
- `web/` — aba Personagens (estende CodexTab).

### Formato de trait (exemplo)

```json
{
  "id": "supersticioso",
  "name": "Supersticioso",
  "description": "Vê presságio em tudo; símbolos sagrados o acalmam, magia aberta o apavora.",
  "dc_modifiers": {"persuasao": 2, "intimidacao": -2},
  "reveal_after": 4,
  "tags": ["comum", "pantano_melancolia", "skallgard"]
}
```

### Assinaturas

```python
# services/npc_layers.py
def roll_hidden_traits(npc_id: str, game_id: str, k_range=(1, 3)) -> list[str]:
    """Sorteio seeded (hash npc_id+game_id) do catálogo. Puro."""

def tick_interaction(npc: dict) -> tuple[dict, list[str]]:
    """interaction_count+=1; move traits maduros p/ revealed.
    Retorna (npc_atualizado, ids_revelados_neste_turno)."""

def reset_scene(npcs: dict) -> dict:
    """in_scene=False para todos (chamado na viagem)."""

def visible_npc_view(npcs: dict) -> list[dict]:
    """Camada 2 p/ API: só known_by_player, SEM hidden_traits."""

def trait_dc_modifier(npc: dict, contexto: str) -> int:
    """Soma dc_modifiers (hidden + revealed) do NPC para o contexto."""
```

## 4. Plano passo a passo

### Etapa 1 — Catálogo + sorteio + revelação (puro)

1. **Testes:** `test_traits_json_valido` (80 entradas, campos, contextos
   canônicos); `test_sorteio_deterministico_por_save`;
   `test_tick_revela_apos_n_interacoes`; `test_trait_dc_modifier_soma`.
2. **Implementação:** `data/traits.json` + `services/npc_layers.py`.
3. **Verificação:** `/qa` verde.

### Etapa 2 — Schema + backfill + gate in_scene

1. **Testes:** `test_backfill_save_antigo_ganha_campos`;
   `test_npc_fora_de_cena_nao_chama_llm` (monkeypatch get_llm que levanta);
   `test_resposta_nao_esta_aqui_cita_home`; `test_viagem_zera_in_scene`.
2. **Implementação:** backfill no load, gate no npc_actor, reset na viagem.
3. **Verificação:** `/qa` verde.

### Etapa 3 — Canal npcs_in_scene no StoryUpdate

1. **Testes:** `test_storyupdate_marca_npc_em_cena` (mock devolve nomes →
   npcs atualizados); `test_nome_desconhecido_cria_npc_com_home_atual`;
   `test_npc_left_scene_sai`; `test_guard_fallback` (AIMessage não estoura).
2. **Implementação:** campos + validação + aplicação no storyteller.
3. **Verificação:** `/qa` verde.

### Etapa 4 — DC modifiers nos consumidores + diário

1. **Testes:** `test_encontro_social_usa_trait` (6.4);
   `test_mercador_com_trait_ajusta_recepcao` (4.4);
   `test_revelacao_gera_linha_no_diario`.
2. **Implementação:** integração pontual nos consumidores.
3. **Verificação:** `/qa` verde.

### Etapa 5 — API + aba Personagens

1. **Testes:** `test_api_nao_vaza_hidden_traits` (R9, `/game/state` e
   `/game/codex`); `test_view_camada2_so_conhecidos`.
2. **Implementação:** filtro + frontend + `npm run build`.
3. **Verificação:** `uv run pytest` completo + smoke_api.

## 5. Critérios de aceite

- [x] Falar com NPC que não está em cena → "X não está aqui" sem request de LLM
- [x] Viajar → ninguém segue o jogador (in_scene zerado; companion 4.5 intacto)
- [x] Interações revelam trait (reveal_after do catálogo), nota na resposta, aba Personagens
- [x] `hidden_traits` invisível em API/prompt/frontend (teste R9)
- [x] Save antigo carrega com backfill completo (migration v2)
- [x] `uv run pytest` verde (629 testes) + `npm run build` ok
- [x] Guard de FallbackLLM nos campos novos do StoryUpdate (defaults [])
- [x] Saves antigos continuam carregando

**Desvios:**
- Canal de entrada em cena REUSA `introduced_npcs` (campo já existia no
  StoryUpdate); só `npcs_left_scene` é novo — menos schema pro Gemini errar.
- Gate trata `in_scene` AUSENTE como presente (compat: save antigo no meio de
  cena não fica órfão; backfill não força False — primeira viagem normaliza).
- R6 (DC modifiers): consumidor entregue = gate de recrutamento 4.5
  (`persuasao` ajusta o limiar de relationship); social 6.4/mercador 4.4
  ficam para quando NPC↔mercador se unificarem (mercadores não vivem em
  GameState.npcs).
- Catálogo: 40 traits (lote 1 previsto no §7 da spec; teste exige ≥40).
- "Linha no diário" virou nota na própria resposta do NPC (*(Você percebe...)*)
  — a crônica 3.1 é por milestone de evento, não caber trait ali é decisão.
- Smoke real (2026-07-06): viagem p/ interior zerou a cena; Gemini
  RE-INTRODUZIU a NPC conhecida via introduced_npcs (canal funcionando —
  semântica de "quem a narrativa traz entra em cena"; vigiar em playtest).

## 6. Smoke test com LLM real

(4–5 requests, valida o mapeamento dos campos novos no Gemini)

1. Novo jogo; cena com NPC nomeado pelo narrador → `npcs_in_scene` mapeado
   (NPC criado com home correto, `known_by_player=True`).
2. Falar com esse NPC 2× → `interaction_count` incrementa; resposta usa persona.
3. Tentar falar com NPC de OUTRA região ("falo com Volkar") → "não está aqui"
   **sem** gastar request.
4. Viajar e voltar → NPC não está mais em cena; reencontrá-lo via narração.

## 7. Riscos & compatibilidade

- **Regressão do fluxo atual de NPC:** o gate R4 muda o caminho feliz do
  router→npc_actor; mitigação: NPC recém-criado pela cena SEMPRE nasce
  `in_scene=True`, e o storyteller é quem introduz — cobrir com teste e2e
  offline do grafo completo.
- **LLM não preencher `npcs_in_scene`** (campo novo, Gemini pode omitir):
  campos com default `[]` — omissão degrada para "ninguém entrou", nunca
  crash; smoke §6 valida o preenchimento real.
- **80 traits é curadoria grande:** entregar em 2 lotes (40 no MVP da spec,
  +40 depois) é aceitável — catálogo é dado, não código; teste valida shape,
  não quantidade exata (≥40).
- **Saves antigos:** backfill R1 (traits sorteados na hora, determinístico).
- **MockLLM:** devolve `npcs_in_scene` vazio por default — caminho de criação
  via cena precisa de mock dedicado no teste; quota do smoke: 4-5 requests.
