# SPEC — Início de campanha personalizado (prólogo + seed de arco)

> **Status:** `done`
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-17 (implementada; smoke real §6 executado no DeepSeek — ver nota)
> **Depende de:** onboarding-valoria (apenas o frontend do passo 6; o backend
> funciona sozinho — usa `data/onboarding.json` se existir, senão `origins.json`)
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Hoje a backstory digitada na criação só tempera atributos/inventário no
`create_player_character`. O início da campanha é genérico: a primeira
`HumanMessage` é "Descreva o cenário ao meu redor", o `campaign_plan` nasce
vazio e o campaign_manager planeja um arco qualquer da região. Um jogador que
escreve "renegado de uma família nobre de Nova Arcádia que quer recuperar seu
nome" começa exatamente igual a quem não escreveu nada.

Esta spec faz a descrição livre **dirigir o início**: um endpoint de prólogo
gera (1 chamada SMART) um cenário estruturado — texto de prólogo para o
jogador, direção de cena para o storyteller, arco pessoal de 3-5 beats e 1-2
NPCs da história. O jogador **confirma ou refina** o prólogo antes do jogo
existir; só então o `/game/new` cria o save já semeado. Fluxo sem cenário
permanece byte a byte o atual (CLI e clients antigos intactos).

Viabilidade confirmada no código: `campaign_manager` só replaneja com
`needs_replan`/plano vazio/beat concluído/15 turnos
([campaign_manager.py:74-97](../agents/campaign_manager.py)) — plano semeado
na criação sobrevive. Princípios: IA propõe, Python valida na borda; prólogo é
stateless (cenário vive no client entre preview e confirm — API continua
stateless por save).

## 2. Requisitos

- **R1** — `POST /game/prologue` recebe o payload atual de criação
  (`CreateCharacterRequest`) e devolve `{scenario: StartScenario, mock: bool}`
  em 1 chamada `ModelTier.SMART` com structured output.
- **R2** — O prompt do prólogo ancora em: lore curado da região
  (`data/onboarding.json`; fallback: `description`/`bonus` de `origins.json`),
  temas da classe (`class_themes.json` — o gancho não pode violar `forbidden`)
  e instrução explícita de pt-BR (lição do playtest: beat em inglês).
- **R3** — Guard de fallback obrigatório: sem instância de `StartScenario`
  (FallbackLLM/erro), o endpoint devolve cenário **determinístico de template**
  (interpola nome/classe/região; arco = `default_chapter_title(região)`;
  `seed_npcs=[]`), nunca 500.
- **R4** — `CreateCharacterRequest` ganha `scenario: Optional[StartScenarioIn]`.
  O server **valida na borda** (não confia no client): limites de tamanho por
  campo, `beats` ≤ 5, `seed_npcs` ≤ 2 — excedente é rejeitado com 422.
- **R5** — `/game/new` **com** scenario semeia o estado inicial:
  - `campaign_plan` = arco pessoal (`arc_title`, beats `pending`,
    `current_step: 0`, `last_planned_turn: 0`, `location` = região);
  - `chronicle[0].title` = `arc_title` (em vez de `default_chapter_title`);
  - `npcs{}` recebe os `seed_npcs` (shape mínimo + `npc_layers.ensure_npc_fields`
    com `in_scene=True` e `home_location_id` = local inicial);
  - a `HumanMessage` inicial vira brief da cena (usa `opening_scene_brief`);
  - `narrative_summary` inicial incorpora a essência do prólogo.
- **R6** — `/game/new` **sem** scenario: comportamento idêntico ao atual
  (mensagem genérica, plano vazio, npcs vazios). Nenhuma mudança para CLI.
- **R7** — O plano semeado sobrevive ao primeiro `invoke` (campaign_manager
  não replaneja no turno 0) e o `arc_title` pessoal aparece na crônica.
- **R8** — NPC semeado é alvo válido da rota NPC no turno 1 (falar com ele
  responde em persona, sem "Ninguém responde.").
- **R9** — Frontend: passo 6 do wizard — loading temático durante
  `/game/prologue`; exibe prólogo + resumo da ficha; **Refinar** volta ao
  passo 5 (descrição editável) e regenera; **Começar a jornada** chama
  `/game/new` com o scenario aprovado.
- **R10** — `MockLLM` devolve um `StartScenario` fixo válido (suíte offline
  cobre endpoint e seed de ponta a ponta sem rede).
- **R11** — `/game/prologue` entra no rate-limit existente (mesma janela de
  `/game/new`).

### Fora de escopo

- Sugestão automática de região/classe a partir da descrição (decisão de
  design: jogador escolhe informado pelo wizard; IA não sugere ajuste).
- CLI com prólogo interativo (CLI continua enviando backstory sem scenario).
- Persistir o prólogo rejeitado/histórico de refinamentos.
- Streaming SSE do prólogo (resposta única é suficiente; texto curto).

## 3. Design técnico

### Arquivos novos

- `services/prologue.py` — geração e fallback do cenário (puro, testável):
  - `build_start_scenario(char_input: dict) -> tuple[StartScenario, bool]` —
    monta contexto, chama SMART, aplica guard; retorna `(scenario, mock)`.
  - `fallback_scenario(char_input: dict) -> StartScenario` — template
    determinístico.
  - `scenario_to_state_seed(scenario, char_input, start_loc_id) -> dict` —
    traduz cenário aprovado em `{campaign_plan, npcs, opening_message,
    chronicle_title, summary_extra}` (função pura; `/game/new` só aplica).
- `tests/test_prologue.py` — suíte offline da spec.

### Arquivos alterados

- `api.py` — endpoint `POST /game/prologue`; `CreateCharacterRequest.scenario`;
  aplicação do seed em `new_game`; rota no middleware de rate-limit.
- `mock_llm.py` — branch para `StartScenario` (fixture válida em pt-BR com
  1 NPC semeado, p/ testes exercitarem R8).
- `web/src/api.ts` + `web/src/types.ts` — `postPrologue(payload)`, tipos.
- `web/src/components/CreateScreen.tsx` — passo 6 (prólogo/confirmação).

### Schemas (Pydantic v2)

```python
ATTITUDES = ("hostil", "neutro", "aliado")

class SeedNPC(BaseModel):
    name: str = Field(max_length=60)
    role: str = Field(max_length=80)          # "credor", "irmã exilada"...
    attitude: str = Field(max_length=20)      # normalizado p/ ATTITUDES; fora disso → "neutro"
    persona: str = Field(max_length=400)      # 1-2 frases de personalidade

class StartScenario(BaseModel):
    prologue: str = Field(max_length=2000)            # p/ o JOGADOR, 2ª pessoa, 100-180 palavras
    opening_scene_brief: str = Field(max_length=1200)  # p/ o STORYTELLER: local, situação, tensão
    arc_title: str = Field(max_length=80)              # 3-6 palavras, pt-BR
    beats: List[str] = Field(max_length=5)             # 3-5 beats pessoais (cada ≤ 300 chars)
    climax: str = Field(max_length=300)
    seed_npcs: List[SeedNPC] = Field(default_factory=list, max_length=2)
```

`StartScenarioIn` (entrada do `/game/new`) = mesmo shape/limites — Pydantic
rejeita excedentes com 422 (R4). Beat individual > 300 chars é truncado no
seed (não rejeitado — o client recebeu do próprio server).

### Mapeamentos determinísticos (Python, nunca LLM)

- `attitude → initial_relationship`: hostil=2, neutro=5, aliado=8.
- NPC semeado (shape mínimo, compatível com o fallback de
  [npc.py:176-181](../agents/npc.py)):

```python
npc = {
    "name": s.name, "role": s.role, "persona": s.persona,
    "initial_relationship": REL_MAP[attitude],
    "attributes": {k: 10 for k in ("str","dex","con","int","wis","cha")},
    "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
}
npc = npc_layers.ensure_npc_fields(npc, game_id,
                                   home_location_id=start_loc_id, in_scene=True)
npc["known_by_player"] = True
```

- `HumanMessage` inicial com scenario:
  `f"Comece minha história. Cena de abertura: {opening_scene_brief}"`
  (substitui "Descreva o cenário ao meu redor..."). Sem scenario: string atual.
- `narrative_summary` inicial: atual + `f" Prólogo: {prologue[:300]}"`.

### Prompt do prólogo (essência)

System: motor de cenários de abertura; contexto = card da região (tagline +
description + hook), bônus regional, temas allowed/forbidden da classe, raça;
regras: pt-BR SEMPRE; cena concreta na região escolhida; beats pessoais
ligados à descrição do jogador (não à trama global); NPCs novos (não citar
entidades nomeadas do lore além da própria região); prólogo em 2ª pessoa.
Human: nome, raça, classe, nível, região + descrição livre do jogador.

## 4. Plano passo a passo

### Etapa 1 — `services/prologue.py` + MockLLM

1. **Testes** (`tests/test_prologue.py`):
   - `test_build_scenario_mock` — com `RPG_FORCE_MOCK=1`, retorna
     `StartScenario` válido, `mock=True`, beats 3-5, pt-BR na fixture.
   - `test_fallback_scenario_deterministic` — com `RPG_NO_MOCK=1` (FallbackLLM),
     retorna template com nome/região interpolados e `seed_npcs == []`, sem raise.
   - `test_scenario_to_state_seed` — traduz cenário em `campaign_plan`
     completo (beats `pending`, `last_planned_turn=0`), npcs com
     `in_scene=True`/`known_by_player=True`/relationship mapeado, e
     `opening_message` contendo o brief.
2. **Implementação:** módulo novo + branch no `mock_llm.py`.
3. **Verificação:** `uv run pytest tests/test_prologue.py` verde.

### Etapa 2 — Endpoint `/game/prologue`

1. **Testes:** `test_api_prologue_returns_scenario` (TestClient, mock) — 200,
   shape completo; `test_api_prologue_rate_limited` — entra na janela (reusa
   padrão dos testes de rate-limit existentes).
2. **Implementação:** endpoint + rota no middleware `_rate_limit`.
3. **Verificação:** suíte verde.

### Etapa 3 — Seed no `/game/new`

1. **Testes:**
   - `test_new_game_with_scenario_seeds_plan` — save resultante tem
     `campaign_plan.arc_title` pessoal, beats `pending`, chronicle[0].title
     = arc_title.
   - `test_new_game_with_scenario_seeds_npcs` — npc no estado com
     `in_scene=True`/`known_by_player=True`; chamar `npc_actor_node` com
     `active_npc_name` = nome semeado NÃO devolve "não está aqui" (R8 —
     asserção direta no nó, sem depender do router classificar).
   - `test_new_game_without_scenario_unchanged` — payload sem scenario →
     mensagem inicial atual, plano/npcs vazios (R6).
   - `test_seeded_plan_survives_first_invoke` — após o invoke da criação,
     `arc_title` continua o semeado (R7).
   - `test_scenario_validation_rejects_oversize` — 6 beats ou 3 npcs → 422 (R4).
2. **Implementação:** `CreateCharacterRequest.scenario` + aplicação do seed
   via `scenario_to_state_seed` em `new_game`.
3. **Verificação:** `uv run pytest` (suíte completa) verde.

### Etapa 4 — Frontend (passo 6)

1. **Testes:** manual (checklist §6) + `npm run build`.
2. **Implementação:** chamada a `/game/prologue` ao concluir o passo 5;
   tela de prólogo com loading temático, Refinar (volta + regenera) e
   Começar (POST `/game/new` com scenario).
3. **Verificação:** build verde + smoke manual.

## 5. Critérios de aceite

- [x] `POST /game/prologue` → 200 com `StartScenario` no mock e no real (R1)
- [x] Fallback determinístico sem key/erro — nunca 500 (R3)
- [x] Seed completo: plano + crônica + NPCs + mensagem de abertura (R5)
- [x] Fluxo sem scenario idêntico ao atual (R6) — testes antigos intocados
- [x] Plano semeado sobrevive ao 1º invoke (R7)
- [x] NPC semeado responde em persona no turno 1 (R8)
- [x] Validação de borda: 6 beats / 3 npcs → 422 (R4)
- [x] Passo 6 funcional: loading, refinar, começar (R9)
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Guard de FallbackLLM em todo `with_structured_output` novo (try/except ou isinstance)
- [x] Saves antigos continuam carregando

> **Achado do smoke real (2026-07-17) — mudança de design:** os `max_length`
> duros do `StartScenario` derrubavam TODOS os candidatos reais por validação
> (DeepSeek: `climax` > 300; Groq: 400 `tool_use_failed`; Anthropic:
> `attitude` "ambígua e transacional" > 20) e o endpoint devolvia sempre o
> template. Fix: o schema voltado ao LLM tem tamanhos só como *descrição*;
> `_normalize` trunca em Python para os tetos; os limites ESTRITOS moram em
> `StartScenarioIn` (borda do `/game/new`, R4 — 422 preservado). MockLLM não
> pegava isso (fixture sempre válida) — exatamente o aviso do CLAUDE.md.
> Coberto por `test_normalize_truncates_llm_overflow`.

## 6. Smoke test com LLM real

(DeepSeek primário; ~4 requests, custo ~$0.01.)

1. `POST /game/prologue` com descrição "renegado de uma família nobre de Nova
   Arcádia que busca recuperar seu nome e voltar à corte" → prólogo em pt-BR,
   cena concreta em Nova Arcádia, arco coerente, 1-2 NPCs plausíveis.
2. Repetir com descrição vazia → cenário ainda coerente (genérico da região).
3. `POST /game/new` com o scenario de (1) → primeira narração abre NA CENA do
   brief (não "você está numa estrada..." genérico).
4. Turno 1: falar com o NPC semeado → responde em persona; `GET /game/state`
   mostra `arc_title` pessoal no plano.

**Executado 2026-07-17 (DeepSeek real):** (1) arco "O Nome Manchado", 2 NPCs
(Lyra contato do submundo / Aldric irmão herdeiro), prólogo rico em pt-BR ✓;
(2) descrição vazia → "O Preço do Silêncio Dourado", coerente com a região ✓;
(3) abertura NA taverna do brief (O Alfinete Enferrujado), capítulo 1 =
"O Nome Manchado" ✓; (4) rota NPC respondeu EM CENA (sem "Ninguém responde.")
e `arc_title` pessoal no estado ✓ — obs.: a fala veio dos capangas da cena em
vez da Lyra (comportamento do npc_actor com cena quente; território da spec
`npc-fallback-sem-alvo`, não regressão desta). Latência do prólogo ≈ 17-40s;
falha transitória de provider cai no template pelo guard (por design).

## 7. Riscos & compatibilidade

- **Saves antigos:** sem scenario nada muda; campos novos só existem em saves
  novos e são shape já suportado (`campaign_plan`/`npcs` padrão).
- **MockLLM/FallbackLLM:** mock devolve fixture válida (R10); FallbackLLM cai
  no template (R3). Guard `isinstance` no único site novo de structured output.
- **Quota/latência:** +1 SMART por criação (~$0.002 DeepSeek; +1 por refino).
  Latência do prólogo ≈ 5-15s — mitigada pelo loading temático do passo 6.
- **Cenário citando entidade inexistente:** prompt restringe a inventar NPCs
  novos e ancorar na região; NPCs semeados entram no estado, então nunca são
  órfãos. Beats são narrativos (validação dura de entidades = event_processor,
  fora do turno 0).
- **Prompt injection via descrição livre:** superfície igual à backstory atual
  (já limitada a 2000 chars na borda, auditoria A7); scenario re-validado no
  `/game/new` (R4) — client malicioso no máximo estraga o próprio jogo.
