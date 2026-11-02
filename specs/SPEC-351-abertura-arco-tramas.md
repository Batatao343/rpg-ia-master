# SPEC-351 — Abertura ligada às tramas do mundo (1º arco, 1 NPC pessoal + 1 NPC da trama)

> **Status:** `done`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Origem:** pedido do dono (27/10): "tô começando com um elfo em Nova Arcádia — ele já tem que
> ter algo do Pó de Sonho, na descrição dele já tem que falar algo que ele está buscando". Hoje a
> criação gera 2 NPCs aleatórios que não levam a nenhuma quest.
> **Depende de (`done`):** SPEC-045 (início personalizado: `services/prologue.py`, `/game/prologue`,
> seed no `/game/new`), SPEC-297 (pool compartilhado: `shared_pool.submit`/`promote_due`,
> validadores, semente de NPC), SPEC-312 (sementes de rumor), SPEC-311 (RAG com `prefer_region`).
> **Integra se estiver `done`, sem bloquear:** SPEC-350 (mundo povoado: portas de trama e
> NPCs-âncora; sem ela vale o fallback de §3.4), SPEC-348 (correções de lore C-17…C-21: tira
> segredos de arquivos `public` do Codex; sem ela o smoke E4 fica "provisório", ver §6).
> **Desbloqueia:** quests de abertura com âncora (ligação futura com `investigar_rumor` da SPEC-313).
> **EXECUTOR_MODEL:** `Opus` (Sol: prompt + pool compartilhado + borda da API + privacidade) ·
> **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (novo caminho de
> escrita no mundo compartilhado a partir da criação do personagem; dado do jogador perto do pool)
> **EVAL_AUTHORING_REQUIRED:** `true` (oráculo `playtest/opening_checks.py` escrito e congelado na
> Etapa 1, antes do código de produto)

---

## 1. Contexto & Objetivo

O prólogo (SPEC-045) transforma ficha + descrição livre num arco inicial, mas o prompt proíbe
exatamente o que o dono quer: os beats têm de ser "pessoais, não à trama global" e os NPCs têm de
ser "novos, não cite personagens nomeados do lore". O único contexto de mundo é o card curto da
região e o tema da classe. Resultado: dois NPCs inventados que não levam a lugar nenhum e um arco
que o planejador descarta no turno 15 sem ter tocado Valoria.

Esta spec liga o **primeiro arco** a uma **trama existente do mundo**, escolhida pela LLM a partir
da lore pública da região (RAG) e de um menu de "portas de trama" montado pelo motor. O jogador
começa **na borda**: busca algo pequeno e pessoal (dito no prólogo, campo `seeking`) que toca a
trama sem ele saber. A trama aparece aos poucos pelos beats, nunca de uma vez. A abertura traz
**exatamente 1 NPC pessoal** (criado para a história do personagem) e **1 NPC da trama** (já
existe no grafo, na borda da trama). O NPC pessoal entra no **pool compartilhado** da SPEC-297
(revisão automática, Termos item 8) **sem nenhum dado do jogador**.

Princípios: IA propõe e Python valida na borda (`AGENTS.md` § Convenções); não-onisciência (o
prólogo só usa lore `public`; segredos só como direção oculta do **planejador**, que já os vê e
sanitiza beats, `agents/campaign_manager.py:175-179`, `:210-212`, `:264-278`); regra de ouro do
pool (texto do jogador nunca vira entidade compartilhada, SPEC-297 R7/R9/D1); tom de Valoria
(`docs/lore/revisao-2026-10-27.md` §2, no worktree da SPEC-348: custo, entropia, instituições como
armadilha, crônica cansada, segredos como inversão, léxico próprio).

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | Prompt manda beats "PESSOAIS … não à trama global" | `services/prologue.py:186-187` |
| P2 | Prompt manda NPCs "NOVOS … não cite personagens nomeados do lore" | `services/prologue.py:188-189` |
| P3 | Contexto de mundo = só card da região + tema da classe; nenhum RAG, nenhuma entidade do grafo | `services/prologue.py:170-181`, `:74-88`; `data/onboarding.json:12-15` |
| P4 | Schema aceita 0 a 2 NPCs sem distinção de papel; nada liga NPC a trama | `services/prologue.py:35-39`, `:50-52` |
| P5 | Nenhum campo diz o que o personagem busca | `services/prologue.py:42-52` |
| P6 | A descrição livre entra crua no prompt (sem `wrap_player_input`) | `services/prologue.py:199-210`; regra em `services/prompt_guard.py:27`, `:57` |
| P7 | NPC semeado vira ficha só local: sem `id` de grafo, sem semente, sem pool | `services/prologue.py:241-260` |
| P8 | O arco do prólogo morre no replanejamento periódico (15 turnos) ou na troca de região, sem memória da ligação | `agents/campaign_manager.py:57`, `:96-107` |
| P9 | O cenário inteiro (beats, clímax, brief) vai ao cliente e volta dele no `/game/new`; o servidor só checa tamanho | `api.py:4470-4481`, `:1839-1842`, `:5099-5109` |
| P10 | O pool exige semente do motor e não recebe a cena (para não vazar texto do jogador); o NPC do prólogo nasce da descrição do jogador, logo não pode passar por `generate_new_npc` como está | `agents/npc.py:519-546`, `:601-630`; `services/shared_pool.py:177-180`; `services/shared_pool_validators.py:387-404` |
| P11 | NPCs da lore da região existem no grafo, mas a maioria sem casa: só 36 de 177 NPCs têm `home_location_id` | `data/graph/entities.json:1856-1869` (Vestra, `components: {}`), `:7075-7090` (Irena, com casa em `nova_arcadia`) |
| P12 | Ganchos prontos da região que ninguém usa na abertura: rumor do Pó de Sonho nas vielas de Nova Arcádia, Vestra Mão-vermelha (comércio do Pó para Nova Arcádia) | `data/world/rumor_seeds.json:151-169`; `data/codex/npcs/npc_vestra_mao_vermelha.md:17-24` |
| P13 | O Codex público ainda tem segredos escritos como fato (Víbora, barril, Vane, Farol, Arauto): RAG público na abertura pode entregá-los | `docs/lore/revisao-2026-10-27.md:139-157` (worktree SPEC-348) |

### 1.2 Inspiração externa (só referência; não verificada online nesta sessão, citada de memória)

- **Kicker** (Ron Edwards, *Sorcerer*, 2001): o jogador escreve o evento que tira o personagem da
  rotina; o mestre o liga ao mundo. Aqui: `seeking` + descrição livre.
- **Fronts e "grim portents"** (Vincent e Meguey Baker, *Apocalypse World*, 2010): ameaças do
  mundo avançam por presságios em etapas. Aqui: a trama aparece pelos beats, na borda primeiro.
- **Bonds** (Sage LaTorra e Adam Koebel, *Dungeon World*, 2012): laço pessoal com um NPC na
  criação. Aqui: o NPC pessoal com `bond` só local.
- **Trouble/Issues** (Evil Hat, *Fate Core*, 2013): o problema do personagem amarrado a um
  problema do cenário.

## 2. Requisitos

### 2.1 Contexto de trama no prompt (a LLM escolhe, o motor oferece)

- **R1 — Menu de portas de trama.** `services/opening_threads.thread_menu(region_id, *,
  backstory) -> ThreadMenu` monta, sem LLM, até `MENU_MAX_DOORS` (6) portas e até
  `MENU_MAX_NPCS` (4) NPCs da trama da região de início. Fonte preferencial: a SPEC-350 (§3.4,
  `_population_api()`); fallback sem ela:
  - **portas** = sementes de rumor (`data/world/rumor_seeds.json`) cuja `regions` contém a região,
    com `gist` público (nunca `truth`, `fonte` nem `confiabilidade`), mais entidades `public` do
    grafo (`faction`, `item`, `location`) com tag da região;
  - **NPCs** = NPCs `public` do grafo com casa resolvida (`npc_world.home_of`) em local da região.
  Ordenação determinística: primeiro as que casam tokens da descrição livre (≥ 5 letras, sem
  acento), depois por id. Teste: mesma entrada, mesmo menu.
- **R2 — "Na borda" é regra do motor.** Ficam fora do menu: NPCs líderes (`npc_world.leaders()`),
  NPCs e entidades de `data/secret_entities.json`, entidades `hidden`/`secret`, fações secretas
  (`faction_gate`), rumores com `_secret_locked` (`services/rumors.py:174`) e NPC morto na
  projeção. Decisão D6.
- **R3 — RAG público da região.** O prompt recebe `query_rag(<consulta>, index_name="lore",
  max_visibility="public", prefer_region=<region_id>)` (`rag.py:1280-1298`), com a consulta =
  nomes das portas do menu + até 12 palavras da descrição. Teto do bloco `<LORE_DA_REGIAO>`:
  `LORE_TOKENS_MAX` (900) por `context_builder.estimate_tokens`; o menu `<PORTAS_DE_TRAMA>`:
  `MENU_TOKENS_MAX` (350). Exatamente **1** consulta RAG por prólogo (teste conta chamadas).
- **R4 — O prólogo nunca vê segredo.** Nenhuma chamada do prólogo usa `max_visibility` acima de
  `public`, nem lê `truth` de rumor, nem `secret_entities.json` para o texto do prompt (teste
  injeta um chunk `hidden` no índice falso e asserta que não aparece no prompt). Decisão D1.
- **R5 — Novas regras do prompt** (substituem as regras 3 e 4 de `services/prologue.py:186-189`):
  1. escolha 1 ou 2 portas do `<PORTAS_DE_TRAMA>` e devolva os ids EXATOS em `thread_refs`;
  2. o personagem começa **na borda**: busca algo pequeno e pessoal que toca a trama sem saber;
     nada de escolhido, profecia, herança secreta ou começar no meio da crise;
  3. o `prologue` diz, em palavras do mundo, o que ele busca (`seeking`, 1 frase);
  4. os beats revelam a trama aos poucos: o 1º beat é pessoal e concreto, a trama aparece pelo
     2º ou 3º, o clímax do 1º arco ainda é na borda;
  5. NPCs: exatamente 1 `personal` (novo, criado para a história) e 1 `plot` (escolhido do menu
     por `entity_id` exato; nome e papel vêm do motor, a LLM só diz como ele cruza o caminho);
  6. o NPC pessoal tem duas camadas: `bond` (a relação com o protagonista, fica só nesta partida)
     e `persona_public`/`role_public`/`appearance` (quem ele é no mundo, **sem** mencionar o
     protagonista, o nome dele ou a história dele);
  7. tom de Valoria (6 linhas de `docs/lore/revisao-2026-10-27.md` §2, resumidas no prompt) e
     léxico proibido (`mana`, `buff`, `crítico`, `loot`, `boss`).
- **R6 — Descrição do jogador delimitada.** `backstory` e `name` entram com `wrap_player_input` e
  `PLAYER_INPUT_RULE` (`services/prompt_guard.py:27-65`), como no planejador
  (`agents/campaign_manager.py:222-231`).

### 2.2 Schema e saneamento

- **R7 — Schema aditivo.** `StartScenario` ganha `seeking: str`, `thread_refs: list[str]`,
  `plot_npc_id: str`, `plot_npc_hook: str` e `personal_npc: PersonalNPC | None`; `seed_npcs`
  continua existindo (compat de cliente antigo e saves) e passa a ser **derivado** em Python
  (§3.3). Tamanhos só como descrição no schema da LLM; tetos estritos em `StartScenarioIn`
  (lição da SPEC-045, `specs/SPEC-045-inicio-personalizado.md:228-236`).
- **R8 — `_normalize` valida as âncoras.** `thread_refs` fora do menu são descartados; vazio →
  1ª porta do menu. `plot_npc_id` fora do menu → 1º NPC do menu; menu sem NPC → sem NPC da trama
  (log `prologue.thread.no_plot_npc`, nunca inventa). Nome, papel e id do NPC da trama vêm do
  grafo/Codex, nunca da LLM. Mais de 1 NPC pessoal → fica o 1º. Teste por caso.
- **R9 — Template determinístico com trama.** `fallback_scenario` (FallbackLLM, exceção ou
  resultado não-`StartScenario`) usa a 1ª porta e o 1º NPC do menu: prólogo, `seeking` e beats de
  template citando o nome público da porta; **0 NPC pessoal** (Decisão D4). Nunca levanta.

### 2.3 Estado da partida

- **R10 — Fio de abertura no plano.** `scenario_to_state_seed` grava
  `campaign_plan.opening_thread = {thread_refs, plot_npc_key, personal_npc_key, seeking,
  arcs_left: 2, region_id}` (Decisão D3). Campo opcional; save antigo carrega sem ele.
- **R11 — NPC da trama na partida.** Ficha local com `id` = id do grafo (liga a
  `npc_world`/`dead_graph_npc`/`entity_identity`), `role` = linha "Papel:" do Codex público (ou
  tag), persona neutra, `sheet_status: "stub"` (o nó de enriquecimento da SPEC-318 completa),
  `relationship` 5, `known_by_player: True`. `in_scene: True` só se a casa dele é o local de
  início; senão `in_scene: False` e o brief de abertura diz onde encontrá-lo (Decisão D2).
- **R12 — NPC pessoal na partida.** Ficha local = camada pública + `bond` + relação pela
  `attitude` (`REL_MAP`, `services/prologue.py:26`), `in_scene: True`, semente do motor (§2.4) em
  `seed_motives` (SPEC-310 R13), sem `pool_entry_id` obrigatório.
- **R13 — O planejador continua a trama.** Enquanto `opening_thread.arcs_left > 0` e o jogador
  está na região do fio, `_build_plan` (`agents/campaign_manager.py:163-278`) recebe o bloco
  `<FIO_DE_ABERTURA>` (nomes públicos das portas, NPCs do fio, o que o herói busca) e a consulta
  de lore do planejamento (`compose_lore_query`, `:178`) inclui os nomes das portas: é por esse
  caminho (que já vê `hidden` com `purpose="planning"` e já sanitiza o texto) que a direção oculta
  chega. Cada replanejamento com o bloco decrementa `arcs_left`. Sem LLM nova.

### 2.4 NPC pessoal no mundo compartilhado (privacidade primeiro)

- **R14 — Semente do motor antes da LLM.** `/game/prologue` sorteia a semente com
  `npc_seed.roll_unique_seed` (`services/npc_seed.py:169-184`) usando `game_id =
  "prologue:" + nonce` (uuid4) e o local de início, e passa os rótulos (`seed_labels`, `:187-210`)
  ao prompt: a LLM costura o NPC pessoal em volta da semente (profissão, desejo, medo…), como no
  pool (SPEC-297 R4/R7).
- **R15 — Integridade do que volta do cliente.** `/game/prologue` devolve `scenario_token` =
  HMAC (`RPG_SESSION_SECRET`, mesmo padrão de `services/account_security.py:22-42`) sobre o JSON
  canônico de `{personal_npc, seed, nonce, thread_refs, plot_npc_id, owner}`, validade
  `TOKEN_MAX_AGE` (3600 s). No `/game/new`, token ausente, vencido, de outro dono ou que não
  confere → o NPC pessoal vira **só local** (`PoolStatus.LOCAL_ONLY`); a partida nasce igual.
  Sem `RPG_SESSION_SECRET` (perfil legado sem segredo) → só local (Decisão D8).
- **R16 — Documento compartilhado só com a camada pública.** O documento submetido contém só
  as chaves de `DOCUMENT_ALLOWLIST[NPC]` (`services/shared_pool_models.py:38-50`): `name`,
  `role_public`→`role`, `persona_public`→`persona`, `appearance`, `legend`, atributos neutros,
  `initial_relationship` 5 e os ids da semente. `bond`, `attitude`, nome do jogador, descrição
  livre, `seeking`, `thread_refs` e `plot_npc_id` **nunca** entram (teste varre o documento).
- **R17 — Barreiras de privacidade (reuso da 297).** `submit` recebe
  `player_inputs=[name, backstory, seeking]` (vira `input_shingles` → validador
  `literal_player_text`) e o `promote_due` recebe `owner_values` com o nome do personagem
  (validador `pii`). Nome do NPC digitado pelo jogador (`shared_pool.name_typed_by_player`,
  `services/shared_pool.py:650-658`) → `name_origin="player"` → só local (SPEC-297 D1). Nome que
  colide com entidade curada → rejeitado pelo validador `duplicate_curated`.
- **R18 — Submissão depois de persistir.** O `submit` roda no `/game/new` **depois** de
  `commit_create`/`save_game_state` darem certo (`api.py:5129-5144`); falha de submit loga
  `prologue.pool_submit_failed` e não falha a request. Só com `shared_pool.pool_mode() != "off"`
  (Decisão D5). O resto do fluxo da 297 vale sem mudança: hold de `RPG_POOL_HOLD_HOURS`, 1
  avaliação LLM CLASSIFY, mock nunca promove, promovido imutável.

### 2.5 Superfícies, rollout e prova

- **R19 — Front.** A tela de prólogo (`web/src/components/CreateScreen.tsx:466-483`) mostra a linha
  "O que você busca: …" e os NPCs com rótulo ("da sua história" / "do mundo"). Os campos novos são
  opcionais em `web/src/types.ts:866-880` (o fixture e2e antigo, `web/e2e/fixtures.ts:336`,
  continua válido). O `scenario_token` volta no `POST /game/new` ao lado de `scenario`.
- **R20 — Flag `RPG_OPENING_THREAD=off|shadow|on`** registrada em `config/flags.yaml` (SPEC-340).
  `off`: prompt e schema de hoje, byte a byte no seed. `shadow`: monta menu e RAG, loga
  `prologue.thread.shadow {doors, npcs}` e não muda o prompt. `on`: tudo. Default `on` local e
  na suíte; staging liga depois do smoke §6.
- **R21 — Telemetria sem texto.** `prologue.thread.linked {doors, plot_npc: bool, personal: bool,
  source: "350"|"fallback"}`, `prologue.thread.downgraded {reason}`, `prologue.pool_submit
  {status}`. Nunca nome, descrição ou id de jogador.
- **R22 — Latência.** O prólogo continua sendo **1** chamada SMART; o acréscimo é 1 consulta RAG e
  ≤ 1 250 tokens de entrada. Meta no smoke: p50 do prólogo ≤ p50 de hoje + 3 s, no mesmo provider.
- **R23 — Oráculo determinístico** (`playtest/opening_checks.py`, Etapa 1, congelado), usado pelos
  testes e pelo smoke:
  - **E1 `thread_linked`**: `thread_refs` ⊆ menu, não vazio, e o nome público de ≥ 1 porta aparece
    (sem acento/caixa) em beats + clímax + brief + prólogo;
  - **E2 `plot_npc_valid`**: NPC da trama existe no grafo, `public`, casa na região, vivo, fora de
    líderes e de `secret_entities.json`;
  - **E3 `personal_npc_private`**: documento do pool sem chave fora da allowlist, sem token do
    nome do personagem (≥ 3 letras), sem shingle de 6 palavras de `backstory`/`seeking`, e
    `run_validators(entry) == []` no caso limpo;
  - **E4 `no_hidden_leak`**: nenhum shingle de 6 palavras em comum entre (prólogo, brief, beats,
    clímax, NPCs) e os documentos `hidden`/`secret` do Codex; `secret_signatures.find_unrevealed`
    vazio; `faction_gate.beat_leaks` falso;
  - **E5 `seeking_present`**: `seeking` com 1 a 200 caracteres e ≥ 1 palavra de conteúdo dele no
    prólogo;
  - **E6 `starts_at_edge`**: prólogo e beats sem `escolhid`, `profecia`, `destinad`, `único capaz`,
    `salvar valoria`, `herdeiro secreto`;
  - **E7 `npc_cardinality`**: 1 pessoal (0 só no template) e 1 da trama (0 só com menu sem NPC).

### Fora de escopo

- Marcar o rumor da porta como "ouvido" pelo jogador ou abrir quest `investigar_rumor` na criação
  (Decisão D7; a ligação com a SPEC-313 fica para spec própria).
- Escrever portas de trama, NPCs-âncora ou casas de NPC no grafo: é da SPEC-350. Aqui só o
  fallback de leitura.
- Corrigir os vazamentos de segredo no Codex público (SPEC-348).
- Ligar `RPG_SHARED_POOL` no staging ou em produção (decisão do dono, D5).
- Mudar o job de promoção, os validadores ou o prompt do juiz da SPEC-297.
- Gerar retrato/arte do NPC pessoal; NPC pessoal companheiro (SPEC-300).
- Abertura para personagem de nível > 1 diferente da de nível 1.
- Fluxo clássico sem prólogo (`scenario=None`, `api.py:5096-5099`): segue igual.

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/opening_threads.py` | `thread_menu`, `menu_block`, `lore_block`, adaptador `_population_api()` (SPEC-350) e fallback, `plot_npc_sheet`, `planner_thread_block`, constantes |
| `services/prologue_token.py` | `sign_scenario`/`verify_scenario` (HMAC, validade, dono) |
| `playtest/opening_checks.py` | Oráculo E1–E7 (puro; congelado na Etapa 1) |
| `scripts/smoke/spec351_opening.py` | Smoke real §6: N personagens → `/game/prologue` + `/game/new` → E1–E7 + latência → `docs/spec351/smoke-<data>.json` |
| `tests/test_spec351_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `services/prologue.py`: schema (§3.3), prompt (R5/R6), `_normalize` (R8), `fallback_scenario`
  (R9), `build_start_scenario(char_input) -> tuple[StartScenario, bool, dict]` (o 3º item é o
  contexto do token: semente, nonce, menu), `scenario_to_state_seed` (R10–R12),
  `personal_pool_document` (R16).
- `api.py`: `/game/prologue` devolve `scenario_token` (`:4464-4481`); `CreateCharacterRequest`
  ganha `scenario_token: str | None = Field(None, max_length=1024)` (`:1828-1843`); `_create_game`
  revalida `thread_refs`/`plot_npc_id` contra o menu recalculado e submete o NPC pessoal depois de
  persistir (`:5099-5109`, `:5129-5144`).
- `agents/campaign_manager.py`: `<FIO_DE_ABERTURA>` e consulta de lore (R13); decremento de
  `arcs_left` no plano novo.
- `state.py`: `OpeningThread` (TypedDict opcional) em `CampaignPlan`.
- `mock_llm.py` (`:682-719`): `_start_scenario` lê `<PORTAS_DE_TRAMA>` e `<NPCS_DA_TRAMA>` do
  prompt e devolve a 1ª porta, o 1º NPC e 1 NPC pessoal fixo com camada pública limpa (o caminho
  offline exercita E1–E7).
- `web/src/types.ts`, `web/src/api.ts`, `web/src/components/CreateScreen.tsx`: R19.
- `config/flags.yaml`, `.env.example`: `RPG_OPENING_THREAD` (R20).
- `observability/events.py`: eventos de R21.

### 3.3 Schemas

```python
# services/prologue.py — voltado à LLM (sem max_length duro)
class PersonalNPC(BaseModel):
    name: str = Field(description="Nome curto, inventado; nunca um nome escrito pelo jogador")
    role_public: str = Field(description="Quem ele é no mundo, sem citar o protagonista")
    persona_public: str = Field(
        description="1-2 frases; sem citar o protagonista nem a história dele"
    )
    appearance: str = Field(description="1 frase concreta")
    legend: str = Field(description="O que dizem dele, 1 frase (<=160)")
    bond: str = Field(description="Laço com o protagonista (fica só nesta partida)")
    attitude: str = Field(description="EXATAMENTE uma palavra: hostil, neutro ou aliado")


class StartScenario(BaseModel):
    prologue: str
    opening_scene_brief: str
    arc_title: str
    beats: list[str]
    climax: str
    seeking: str = Field(
        default="", description="O que o personagem busca, 1 frase, em palavras do mundo"
    )
    thread_refs: list[str] = Field(
        default_factory=list, description="ids EXATOS do <PORTAS_DE_TRAMA>"
    )
    plot_npc_id: str = Field(default="", description="entity_id EXATO do <NPCS_DA_TRAMA>")
    plot_npc_hook: str = Field(default="", description="Como ele cruza o caminho do herói, 1 frase")
    personal_npc: PersonalNPC | None = None
    seed_npcs: list[SeedNPC] = Field(default_factory=list)  # DERIVADO em _normalize (compat)


# Borda (StartScenarioIn): seeking<=200, thread_refs<=2 itens de <=80, plot_npc_id<=80,
# plot_npc_hook<=300, personal_npc com name<=60, role_public<=80, persona_public<=400,
# appearance<=300, legend<=160, bond<=300; SeedNPCIn ganha kind: Literal["personal","plot"]="personal".


# state.py
class OpeningThread(TypedDict, total=False):
    thread_refs: list[str]
    plot_npc_key: str
    personal_npc_key: str
    seeking: str
    region_id: str
    arcs_left: int


# services/opening_threads.py
class ThreadDoor(TypedDict):
    door_id: str  # id de rumor_seed, de entidade do grafo ou da SPEC-350
    kind: str  # "rumor" | "entity" | "door"
    name: str  # nome público curto
    hook: str  # 1 frase pública (gist do rumor / tagline)
    entity_ids: list[str]
    location_id: str


class ThreadMenu(TypedDict):
    region_id: str
    start_location_id: str
    doors: list[ThreadDoor]
    npcs: list[dict]  # {entity_id, name, role, home_location_id}
    source: str  # "350" | "fallback"
```

### 3.4 Contrato esperado da SPEC-350 (não criado aqui)

```python
# módulo da SPEC-350 (nome a confirmar na Etapa 0; adaptador em opening_threads._population_api())
def thread_doors(region_id: str) -> list[dict]
#   cada item: {door_id, thread_id, name, hook (público), entity_ids, location_id,
#               anchor_npc_ids, visibility: "public"}
def anchor_npcs(region_id: str) -> list[dict]
#   cada item: {entity_id, name, role, home_location_id, edge: bool}  # edge=True = na borda
```

Sem o módulo (ou com lista vazia para a região) → fallback de R1. Se a 350 pousar com outros nomes,
a Etapa 0 ajusta só o adaptador e este §3.4 no mesmo commit.

### 3.5 Assinaturas

```python
# services/opening_threads.py
MENU_MAX_DOORS = 6; MENU_MAX_NPCS = 4; LORE_TOKENS_MAX = 900; MENU_TOKENS_MAX = 350
def mode() -> str  # RPG_OPENING_THREAD
def thread_menu(region_id: str, *, backstory: str = "") -> ThreadMenu
def menu_block(menu: ThreadMenu) -> str          # <PORTAS_DE_TRAMA> + <NPCS_DA_TRAMA>
def lore_block(menu: ThreadMenu, backstory: str) -> str  # 1 query_rag public, cortado
def plot_npc_sheet(npc: dict, game_id: str, start_location_id: str) -> dict
def planner_thread_block(state: dict) -> str     # "" sem fio ativo

# services/prologue_token.py
def sign_scenario(payload: dict, owner: str, *, now: int | None = None) -> str
def verify_scenario(token: str | None, payload: dict, owner: str, *, max_age: int = 3600) -> bool

# services/prologue.py
def personal_pool_document(npc: PersonalNPC, seed: NpcSeed) -> dict
```

### 3.6 Exemplo real (Nova Arcádia, sem SPEC-350)

Entrada: Elfo, Arcanista Cinzento, Nova Arcádia, descrição "saí do Anel Dourado depois que minha
irmã parou de me reconhecer". Menu (fallback): porta `rumor_o_po_de_sonho_mostra_o_futuro`
(`data/world/rumor_seeds.json:151-165`, hook "o pó de sonho mostra o futuro a quem o aspira",
local `na_anel_lama`); NPCs com casa na região, ex. `npc_mv_mara_do_setimo_sino`
(`data/graph/entities.json`, tags `nova_arcadia`/`guilda_corvos`). Saída esperada (forma, não
texto): `seeking` "descobrir quem vende o pó que tirou o olhar da irmã"; `thread_refs`
`["rumor_o_po_de_sonho_mostra_o_futuro"]`; 1º beat pessoal (a irmã, o frasco vazio), 2º beat
nas vielas do Anel de Lama; NPC da trama do menu; NPC pessoal com semente (profissão sorteada)
e `bond` "a boticária que vendia remédio à irmã". A `truth` do rumor (`false`) nunca aparece.

## 4. Plano passo a passo

### Etapa 0 — Sondas e ownership

1. Confirmar no código: `starting_world` e local de início por região (`world_utils.py:1691`);
   `npc_world.home_of`/`leaders` (`services/npc_world.py:102-184`); `rumors.load_seeds` e
   `_secret_locked` (`services/rumors.py:61-185`); estado da SPEC-350 (módulo e nomes) e da 348.
2. Consultar `project_index` (`state_ownership`) para `campaign_plan` e `npcs`: `prologue` só
   escreve via `scenario_to_state_seed` no `/game/new`; `campaign_manager` é o único que decrementa
   `arcs_left`. Medir cobertura do fallback: NPCs de menu por região de início (registrar no
   hand-back; regiões sem NPC = dado para a 350).

### Etapa 1 — Oráculo congelado (antes do produto)

1. **Testes** (`tests/test_spec351_checks.py`): cada E1–E7 com 1 caso que passa e 1 que falha
   (fixtures à mão: prólogo com "escolhido", documento com nome do jogador, beat com frase de
   `SECRET_SIGNATURES`, shingle de doc `hidden`, `thread_refs` fora do menu, NPC líder).
2. **Implementação:** `playtest/opening_checks.py`. Commit próprio. Depois disso o executor não
   muda limiares nem listas sem atualizar esta spec com aprovação do dono.

### Etapa 2 — Menu e contexto

1. **Testes** (`tests/test_spec351_menu.py`):
   - `test_menu_deterministic_and_ranked_by_backstory`;
   - `test_menu_excludes_leaders_secrets_hidden_dead` (R2);
   - `test_menu_never_has_rumor_truth_or_fonte` (rumor `truth=false` e `true` → mesmo bloco);
   - `test_menu_and_lore_token_budget` (R3);
   - `test_single_public_rag_query` (fake `query_rag` conta chamadas e asserta
     `max_visibility == "public"` e `prefer_region`);
   - `test_population_api_preferred_when_present` e `test_fallback_when_350_absent` (módulo
     injetado);
   - `test_nova_arcadia_menu_has_po_de_sonho_door`.
2. **Implementação:** `services/opening_threads.py`.

### Etapa 3 — Prompt, schema e saneamento

1. **Testes** (`tests/test_spec351_prologue.py`, e ajuste de `tests/test_prologue.py` só onde o
   contrato mudou de propósito):
   - `test_prompt_has_doors_npcs_lore_and_no_old_rules` (não contém "não à trama global" nem
     "não cite personagens nomeados");
   - `test_backstory_wrapped_as_player_input` (R6);
   - `test_normalize_drops_refs_outside_menu` e `test_plot_npc_from_graph_not_llm` (R8);
   - `test_exactly_one_personal_and_one_plot` (E7 no mock);
   - `test_fallback_template_linked_to_first_door` (R9; FallbackLLM);
   - `test_mock_path_passes_opening_checks` (E1–E7 no MockLLM);
   - `test_flag_off_keeps_legacy_prompt_and_seed` (R20).
2. **Implementação:** `services/prologue.py`, `mock_llm.py`.

### Etapa 4 — Estado e planejador

1. **Testes** (`tests/test_spec351_state.py`):
   - `test_seed_writes_opening_thread` e `test_old_save_without_thread_loads` (R10);
   - `test_plot_npc_sheet_uses_graph_id_and_stub` e `test_plot_npc_in_scene_only_at_home` (R11);
   - `test_personal_npc_local_has_bond_and_seed_motives` (R12);
   - `test_planner_receives_thread_block_and_decrements` e
     `test_planner_block_absent_after_arcs_or_region_change` (R13; conta invokes = os de hoje);
   - `test_seeded_plan_survives_first_invoke` (o teste da SPEC-045 continua verde).
2. **Implementação:** `scenario_to_state_seed`, `state.py`, `agents/campaign_manager.py`.

### Etapa 5 — Pool compartilhado e privacidade

1. **Testes** (`tests/test_spec351_pool.py`):
   - `test_seed_rolled_before_llm_and_in_prompt` (R14);
   - `test_token_roundtrip_and_tamper_goes_local_only` (persona alterada, token vencido, outro
     dono, sem segredo → `LOCAL_ONLY`; R15/D8);
   - `test_pool_document_only_public_layer` (sem `bond`, nome do jogador, `seeking`,
     `thread_refs`; R16);
   - `test_player_typed_name_never_promotes` e `test_backstory_shingle_rejected_by_validators`
     (R17);
   - `test_submit_after_persist_and_failure_does_not_break_new_game` (R18);
   - `test_pool_off_means_no_submit` (D5);
   - `test_promote_due_with_fake_judge_promotes_clean_personal_npc` (store JSON em `tmp_path`,
     `RPG_POOL_ALLOW_MOCK_EVAL=1`, `RPG_POOL_HOLD_HOURS=0`) e
     `test_promoted_personal_npc_castable_in_other_game` (`cast_entries` de outro `game_id`, sem
     `bond`).
2. **Implementação:** `services/prologue_token.py`, `personal_pool_document`, `api.py`.

### Etapa 6 — API e front

1. **Testes:** `tests/test_spec351_api.py`: `/game/prologue` devolve `scenario_token` e campos
   novos; `/game/new` com cenário antigo (sem campos novos) → 200 e mesmo comportamento;
   `thread_refs`/`plot_npc_id` forjados pelo cliente → descartados na revalidação; tetos → 422.
   Rodar `tests/test_api_fuzz_schemathesis.py` e `tests/test_abuse_policy.py` (`-n 2`).
2. **Implementação:** `api.py`; front (R19); `npm run build`; e2e de criação com `--workers=1`.

### Etapa 7 — Smoke real e evidência

Script e execução da §6; JSON em `docs/spec351/`; hand-back com a tabela E1–E7 por personagem.

## 5. Critérios de aceite

- [x] E1–E7 verdes no caminho MockLLM e no template (com as exceções de E7 previstas)
- [x] Prompt sem as regras 3/4 antigas; descrição livre delimitada (R5/R6)
- [x] Menu determinístico, na borda, sem `truth`, dentro do orçamento de tokens; 1 RAG `public`
- [x] `opening_thread` gravado e consumido pelo planejador por 2 arcos; save antigo carrega
- [x] NPC da trama com id do grafo; NPC pessoal com semente e camada pública separada
- [x] Token inválido/ausente → NPC pessoal só local; documento do pool sem dado do jogador
- [x] Submissão ao pool só após persistir e só com pool != `off`
- [x] `RPG_OPENING_THREAD` em `config/flags.yaml`; `off` = comportamento atual
- [x] Smoke real §6 executado e registrado (evidência em `docs/spec351/`)
- [ ] `uv run pytest` verde (suíte completa offline, pelo coordenador)
- [x] Guard de FallbackLLM no `with_structured_output` do prólogo (mantido: `isinstance` + `try`)
- [x] Saves antigos continuam carregando
- [ ] Revisão independente (Opus) sem P1 aberto

## 6. Smoke test com LLM real

Custo liberado pelo dono. ROUTES default (DeepSeek primário). `RPG_OPENING_THREAD=on`,
`RPG_SHARED_POOL=shadow`, `RPG_POOL_HOLD_HOURS=0`, `RPG_SESSION_SECRET` de teste. Estimativa:
8 SMART (prólogo) + 8 aberturas de jogo + 8 CLASSIFY (juiz do pool) + 1 replanejamento ≈ 30
requests, < US$ 0,20.

`bash scripts/dev/py.sh scripts/smoke/spec351_opening.py --real --out docs/spec351/smoke-<data>.json`
com 8 personagens:

1. **Elfo, Arcanista Cinzento, Nova Arcádia**, descrição "saí do Anel Dourado depois que minha
   irmã parou de me reconhecer" (caso do dono: espera porta ligada ao Pó, de Sonho ou de Fada
   se a 348 já pousou);
2. Humano, Sangromante, Nova Arcádia, descrição **vazia**;
3. Anão, Médico de Campo, Skallgard, "devo a vida a um clã que não é o meu";
4. Pântano da Melancolia, Devoto, descrição com nome próprio ("procuro meu pai, Toren") →
   NPC "Toren", se surgir, fica só local;
5. Deserto de Zhur, Corruptor, descrição longa (~1 500 caracteres);
6. Brekmar (ou região costeira disponível), Sangromante, "fugi de um contrato";
7. Floresta dos Sussurros, Arcanista Cinzento, "quero ver o que o pó mostra";
8. Descrição hostil do corpus de injeção (`tests/fixtures/prompt_injection`) em Aethelgard.

Critérios:
- E3 e E4: **zero** falhas (tolerância zero).
- E1, E2, E5, E6, E7: ≥ 7 de 8 personagens (template conta como falha).
- `promote_due` com juiz real: ≥ 1 NPC pessoal promovido; nenhum com nome do personagem; caso 4
  sem promoção do nome digitado; caso 8 rejeitado ou só local.
- Caso 1: jogar 3 turnos (falar com o NPC da trama; perguntar sobre o que busca) e forçar 1
  replanejamento (`needs_replan`): o plano novo mantém a trama (E1 sobre os beats novos) sem
  segredo no texto (E4).
- Latência: p50 do prólogo registrado antes (flag `off`) e depois (`on`), mesmo provider (R22).
- Leitura humana do coordenador de 3 prólogos (casos 1, 3, 7) contra o tom de §2 da revisão de
  lore; achados viram nota na spec.
- Sem a SPEC-348 `done`, E4 vale como **provisório** (o Codex público ainda tem segredos, P13):
  registrar e repetir os casos 1 e 7 depois da 348.

## 7. Riscos & compatibilidade

- **Saves antigos:** `opening_thread`, `bond`, `seed_motives` são opcionais; plano sem fio segue o
  caminho de hoje. Sem bump de `SCHEMA_VERSION`.
- **Cliente antigo:** cenário sem campos novos é aceito; sem `scenario_token` o NPC pessoal fica só
  local. Fixture e2e atual continua válido.
- **MockLLM/FallbackLLM:** o mock lê o menu do prompt e devolve âncoras válidas (o offline cobre o
  caminho, mas MockLLM esconde erro de nome de campo: o smoke é obrigatório). Fallback → template
  ligado à 1ª porta, sem NPC pessoal; nunca 500.
- **Latência/quota:** +1 RAG e ~1 250 tokens no SMART já existente; nenhuma chamada nova no
  `/game/new`; o juiz do pool roda no job, fora da request.
- **Privacidade:** o caminho de risco é texto do jogador chegar ao pool. Barreiras em camadas:
  camada pública separada no schema (R5.6), documento por allowlist (R16), shingles e PII nos
  validadores (R17), nome digitado nunca promove (R17), token contra edição no cliente (R15),
  juiz LLM com critério `pii` (`services/shared_pool.py:380-389`). Termos item 8 já cobrem
  (`web/legal/terms.md:17`).
- **Spoiler no cliente:** beats e clímax do 1º arco seguem visíveis no JSON do prólogo, como hoje
  (P9). Como o prólogo só usa lore `public` (R4), o pior caso é spoiler de lore pública, não de
  segredo.
- **Cobertura do fallback:** regiões sem NPC com casa (P11) ficam sem NPC da trama até a
  SPEC-350; registrado no hand-back da Etapa 0.

## 8. Decisões abertas (com default)

- **D1 — Segredos no prólogo.** Default: o prólogo vê só lore `public`; a direção oculta chega
  pelo planejador (R13), que já vê `hidden` e sanitiza. Alternativa: dar a direção oculta ao
  prólogo e sanitizar a saída (risco: beats vão ao cliente, P9).
- **D2 — Onde está o NPC da trama no início.** Default: na cena só se mora no local de início;
  senão o herói sabe onde achá-lo. Alternativa: sempre na cena (pode conflitar com `npc_world`).
- **D3 — Vida do fio de abertura.** Default: 2 arcos na região de início (o do prólogo + 1
  replanejamento) ou até sair da região. Alternativa: até o clímax do 1º arco.
- **D4 — Template sem LLM.** Default: template com trama e NPC da trama, sem NPC pessoal.
  Alternativa: NPC pessoal por template a partir da semente (nome exigiria tabela de nomes).
- **D5 — Pool desligado no staging** (`RPG_SHARED_POOL` default `off`, `config/flags.yaml:876-881`).
  Default: esta spec não liga; o NPC pessoal só é submetido quando o dono ligar o pool.
- **D6 — Líderes fora do menu** ("na borda"). Default: fora. Alternativa: permitir líder sem
  cargo público.
- **D7 — Rumor da porta como "ouvido" no início.** Default: não (fora de escopo).
- **D8 — Sem `RPG_SESSION_SECRET`.** Default: NPC pessoal só local. Alternativa: promover mesmo
  sem token (perde a proteção contra edição no cliente).

### Respostas do coordenador (27/10, autorizado pelo dono a decidir)

D1–D4, D6–D8: default aceito. **D5:** esta spec não liga o pool; depois do smoke real verde e do E3/E4
limpos, o coordenador avalia ligar `RPG_SHARED_POOL` **só no staging**, porque o dono quer ver o NPC pessoal
chegar ao mundo compartilhado. Produção fica `off`. **Dependências de execução:** a Etapa 0 só começa depois de
a SPEC-350 expor a interface (§3.4) ou de o coordenador mandar seguir com o fallback. E4 é certificado
depois do pouso da SPEC-348.
**Interface real da 350 (aprovada):** `plot_doors(region_id, state=, postura=)`, `cast_npc_row(...)` e
`public_thread_brief(thread_id)` em `services/plot_threads.py`, com o catálogo em `data/world/plot_threads.json`.
O adaptador `_population_api()` mapeia para esses nomes. Nova Arcádia tem 7 tramas, entre elas `tr_na_po_de_sonho`,
que tem uma porta para personagem Elfo. O smoke do elfo em Nova Arcádia deve cair nela ou justificar por que não caiu.

## 9. Registro de execução (executor)

### 28/10 — Etapa 0 parcial, Etapa 1 e correções de segurança sem schema novo

- **Oráculo E1–E7 congelado:** commit `816bb5795fa6f1bed407761978a34a576d130b5f`;
  `git hash-object playtest/opening_checks.py` = `5713a694c773d33b29337e692550cfeeb4462a48`
  (testes: `tests/test_spec351_checks.py`, 17 casos). Qualquer mudança posterior no arquivo exige
  aprovação do dono registrada aqui. Semânticas fixadas: E2 aceita `plot_npc_id` vazio só com menu
  sem NPC; E7 no template exige 0 pessoal; E3 só roda no `run_all` se houver documento do pool;
  E4 compara shingles de 6 palavras (sem acento) com corpo dos docs Codex `hidden`/`secret`.
- **Segurança (independente do schema novo):** (a) `wrap_player_input` em nome e descrição livre do
  prólogo + `PLAYER_INPUT_RULE` como regra 10 do sistema (`services/prologue.py`; P6/R6), com testes
  (incl. corpus de injeção); (b) `services/prologue_token.py` (`sign_scenario`/`verify_scenario`,
  HMAC sobre JSON canônico + dono + instante; sem `RPG_SESSION_SECRET` ≥ 32 → `""`/`False`).
  **Pendente:** ligar o token ao `/game/prologue` e `/game/new` (`api.py`) — depende do payload
  `personal_npc`/`thread_refs`/`plot_npc_id` das Etapas 3–5.
- **Etapa 0 (sondas):** `starting_world`/`start_location_for_region` e `services/world_pressures`
  (`region_of`, `region_primary_location`) confirmados; `npc_world.home_of/leaders/graph_entity`
  existem como na spec. `state_ownership.yaml` não lista `campaign_plan`/`npcs`: ownership
  confirmado só pelo código (`prologue` escreve só via `scenario_to_state_seed` no `/game/new`;
  `campaign_manager` é o único a replanejar). `services/plot_threads.py` e `data/world/plot_threads.json`
  (SPEC-350) ainda NÃO existem neste worktree: o adaptador `_population_api()` fica para depois.
- **Cobertura do fallback por região** (NPCs `public`, não líderes, com casa resolvida em local da
  região; menu usa até 4): aethelgard 3, brekmar 3, costa_negra 3, deserto_zhur 3,
  floresta_sussurros 3, montanhas_afiadas 3, nova_arcadia 3, ophidia 3, pantano_melancolia 3,
  pradaria_ruinas 3, selva_xylos 3, skallgard 3 (todas as 12 regiões têm ≥ 3; falta filtrar
  `secret_entities` no menu, que só afeta NPCs sem casa). 125 NPCs seguem sem casa (P11).

### 02/11 — Etapas 2–7 (executor)

- **Entregue:** `services/opening_threads.py` (menu, blocos, ficha da trama, bloco do planejador; adaptador
  `_population_api()` sobre `services.plot_threads.plot_doors`, import opcional, sem a 350 vale o fallback),
  `services/prologue.py` (schema/prompt/`_normalize`/template/token/documento do pool/`submit_personal_npc`),
  `api.py`, `agents/campaign_manager.py` (`<FIO_DE_ABERTURA>`), `state.py`, `mock_llm.py`, front (R19), flag
  `RPG_OPENING_THREAD`, eventos, testes `tests/test_spec351_{menu,prologue,state,pool,api}.py`.
- **Desvios:** (1) `build_start_scenario` continua devolvendo 2-tupla (compat com testes/clientes);
  `build_start_scenario_ctx` devolve a 3-tupla da spec. (2) `seed_npcs` derivado traz só o NPC pessoal (o da
  trama vive em `plot_npc_id`), preservando o contrato do template (`seed_npcs == []`). (3) O token que viaja ao
  cliente é `<nonce>.<slot>.<v1.epoch.hmac>`: nonce e slot permitem ao servidor re-sortear a semente de forma
  determinística no `/game/new` sem campo extra. (4) Fallback do menu só usa sementes de rumor `family=lore`
  (as `avist_enemy_*` são ruído) e desempata por `quest_eligible`; sem backstory que case, Nova Arcádia não
  oferece o Pó de Sonho nas 6 portas (a 350 resolve; fallback só com texto casando). (5) Prompt exige copiar o
  título da porta entre aspas (sem isso E1 caiu a 1/8 no smoke). (6) Restrição da revisão da 350 (P2-5): a 351
  nunca lê facção de linha da 350; nome/papel vêm do grafo/Codex público (teste com facção oculta simulada).
- **Smoke real 02/11 (`docs/spec351/smoke-2026-11-02.json`, DeepSeek):** E1–E7 = 8/8 em todos; replan forçado do
  caso 1 mantém a trama (E1) sem segredo (E4); 2 NPCs pessoais promovidos pelo juiz real, nenhum com nome do
  personagem; p50 do prólogo 8,7 s (off) → 9,95 s (on), +1,3 s. Ressalvas: RAG de lore estava indisponível no
  worktree (índice FAISS gitignored; `lore_block` vazio), E4 é provisório até a 348; leitura humana dos 3 prólogos
  e 3 turnos do caso 1 ficam com o coordenador.
- **Cobertura do fallback por região:** todas as 12 regiões têm ≥ 3 NPCs na borda (sem a 350).

### 02/11 (tarde) — correções da revisão independente (CHANGES_REQUIRED)

- **P1-1:** adaptador mapeia `PlotDoor` real (SPEC-350 na main): uma porta por trama, `name` = `title` da trama
  dona, `hook` = `hook_public`, âncora = `anchor_npc_id`, `postura` = classe passada a `plot_doors`; `_door_name`
  resolve porta/trama → título; log `thread.downgraded reason=350_unmapped|350_anchors_unusable`. Teste com
  `PlotDoor` Pydantic frozen e teste com o módulo real (Elfo/Nova Arcádia → `tr_na_po_de_sonho` no menu quando a
  backstory casa; por Postura "Arcanista Cinzento" a 350 ordena `tr_na_lista_de_fornalha` primeiro, e o caso do
  dono só chega ao Pó de Sonho se a descrição citar o tema ou se a trama couber nas 6 portas: justificativa
  registrada). Âncoras `npc_tr_*` têm casa e passam em `_eligible_npc`; âncoras sem casa (ex. `npc_ilsa`) são
  filtradas.
- **P2-1:** prompt pede o título COMPLETO como parte natural da frase (sem aspas) e proíbe porta/trama/menu na
  ficção; E1 7/8 no smoke (oráculo intocado); `consume_thread` acrescenta direção ao beat 2 quando o planejador
  ignora o fio (garante E1 no replan). **P2-2:** `looks_hostile` → entrada hostil vira `name_origin=player`
  (só local); caso 8 não promovido. **P2-4:** `ARCS_LEFT_DEFAULT=1` (D3: prólogo + 1 replanejamento).
  **P2-5:** `plot_npc_hook` vai ao brief e à ficha (`opening_hook`); `plot_npc_name` derivado; chip mostra
  `nome — gancho (do mundo)` fora da condição de `seed_npcs`. **P2-6:** semente já usada → só local.
  **P2-7:** NPC morto na projeção fora do menu (teste). **P2-8:** `seeking` e nomes no bloco do planejador
  passam por `wrap_player_input`. Beats e clímax passam por `sanitize_beat` (E4: vazamento de facção).
- **Smoke 2 (`docs/spec351/smoke-2026-11-02b.json`, RAG de lore real: 700–1300 caracteres por caso, 350 real
  em Nova Arcádia):** E1 7/8, E2/E3/E4/E5/E6/E7 8/8; 1 NPC pessoal promovido (caso 1), nenhum com nome do
  personagem nem o caso 8; p50 8,3 s → 9,4 s. O replan do caso 1 deu E1 falso antes de `consume_thread`
  forçar o título; essa última correção foi validada só por teste unitário (não repeti o smoke inteiro).

### 02/11 (noite) — raça no menu e smoke do replan

- **Raça pesa no menu:** a 350 não expõe raça na API; o adaptador lê a afinidade das tags da âncora no grafo
  público (`elfo` em `npc_tr_ysolt_fio_de_vidro`/`npc_tr_aelis_sem_ampulheta`). Porta com âncora da raça do herói
  vai à frente de tudo (Postura e tokens da descrição); entre duas de raça, a de trama com Postura contrária
  (ex. `tr_na_a_colecao` para Arcanista) fica atrás. Teste real: Elfo Arcanista Cinzento em Nova Arcádia →
  `tr_na_po_de_sonho` primeiro, âncora Ysolt; Humano não.
- **Smoke (`docs/spec351/smoke-2026-11-02c-replan.json`, caso 1 + replan forçado, 350 real):** E1–E7 verdes; o plano
  novo cita o título da trama (E1) sem segredo (E4); a LLM escolheu `tr_na_a_colecao__p2` + `tr_na_po_de_sonho__p1`
  (as duas portas élficas) e o NPC da trama foi Aelis, não Ysolt: o menu oferece as duas, a escolha é da LLM.

### Pouso (coordenador, 02/11)

Revisão independente rodada 2: APPROVED_WITH_FOLLOWUPS (`handoffs/SPEC-351-independent-review.md`). Follow-ups aceitos, não bloqueiam:

- `looks_hostile` é sinal extra, não barreira (falso positivo só deixa o NPC local); normalizar acento e ampliar padrões em spec futura.
- `sanitize_beat` ainda não cobre o texto do prólogo nem o brief da 1ª cena.
- Ordenação real do menu: afinidade de raça (+100) > Postura > tokens da descrição. Desvio consciente da R1 (pedido explícito do dono: Elfo em Nova Arcádia → Pó de Sonho).
- No replan, o E1 depende do "Mantenha em vista: …" colado pelo motor no beat 2; medir à parte a adesão do planejador ao bloco do fio.
