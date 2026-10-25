# SPEC-312 — Rumores com semente (lore → motor sorteia → LLM costura; boato falso nunca vira fato)

> **Status:** `in-progress`
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Origem:** proposta **N1** de `docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md` (§4.2, linha 234)
> + §3 "Rumores com metadado" (linha 191) + §2.3 (linha 175: rumor = "só motor; sem boato falso").
> Decisões do dono de 24/10 registradas na §9.
> **Depende de:** SPEC-302 (`done`: `world_engine.advance_days`, hooks diários, `day_rng`,
> `pending_digest`, `world_perception`), SPEC-215 (`done`: ledger `npc_knowledge`, canal `RUMOR`),
> SPEC-296 (`done`: `world.news`, `append_news`, `<OUVIU_DIZER>`), SPEC-305 (`done`:
> `perceived_ids`, canais de percepção), SPEC-304 (`done`: `npc_world.location_of`, nomes de NPC
> conhecidos).
> **Interfaces paralelas (não bloqueiam):** SPEC-313 (quest `investigar_rumor` consome
> `rumors.investigable`/`truth_of`/`mark_resolved`, §3.6) · SPEC-309 (bloco de mundo percebido e
> memória da narração diária precisam filtrar itens de rumor, R24) · SPEC-310 (`<O_QUE_VOCE_SABE>`
> do NPC passa a mostrar rumores como `[BOATO]`, sem mudança aqui).
> **Desbloqueia:** N6/SPEC-313 (`investigar_rumor`), pilar D (opções de ação com gancho de rumor).
> **EXECUTOR_MODEL:** `Opus` (Sol: writer novo dentro de `world_sim`, toca percepção, ledger da 215,
> storyteller e API) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:**
> `true` (regra de ouro, novo `subject_kind` no ledger, campo novo de structured output)
> **EVAL_AUTHORING_REQUIRED:** `false` (se o eval `npc_knowledge` precisar de relock por causa do
> `subject_kind` novo, é follow-up do coordenador; esta tarefa não toca `evals/`)

---

## 1. Contexto & Objetivo

O mundo de Valoria tem 40 rumores escritos à mão em `lore_nova/rumors.txt`, cada um com
`confiabilidade: alta|média|baixa` e `[FONTE: …]` (ex.: `lore_nova/rumors.txt:5-10`). Hoje nada no
código lê esses metadados: eles só entram no FAISS como texto público (13 arquivos em
`data/codex/rumors/`) e chegam ao narrador por acaso, quando o RAG os traz. Os "rumores" que o
jogo produz são 43 templates de sinal/crise da SPEC-302 (`data/world/signals.json`), todos
**verdadeiros** e todos sobre pressões; não existe boato, lenda nem mentira. A VISAO registra o
sintoma ("Rumores somem no turno seguinte", `docs/mundo-vivo/VISAO.md:39`).

Esta spec cria **rumores com semente**: uma tabela `data/world/rumor_seeds.json`, gerada da
lore (com `source` arquivo:linha, região, assunto, entidades, confiabilidade e `truth`), da qual
o **motor** sorteia, uma vez por dia de jogo e por região frequentada, 0 ou 1 rumor. O rumor
nasce num local, se espalha entre NPCs pelo canal `RUMOR` da SPEC-215 e chega ao jogador
**só** pela regra de ouro (ouviu na região ou alguém contou). A LLM só costura o rumor em uma
frase da narração diária que já existe (`narrate_day`); não há chamada nova. Cerca de 25 % dos
rumores são falsos. Um rumor falso entra como `[BOATO]` e **nunca** vira fato: não gera
`GameEvent`, não toca a projection, não vira `MemoryFact`, não alimenta pressão nem quest de
crise. O narrador pode, opcionalmente, propor um rumor (`ProposedRumor`), que só é aceito se
citar entidades reais do grafo e não duplicar outro.

Princípios: mecânica em Python (sorteio, verdade, propagação, prazo, teto); a LLM narra; regra
de ouro (o jogador só sabe o que viu ou ouviu, `VISAO.md:79-82`); LLM ocasional ≤ 1 chamada por
dia de jogo (`VISAO.md:55-56`); determinismo por seed (`world_engine.day_rng`,
`services/world_engine.py:47-50`).

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | 40 rumores da lore com `confiabilidade`/`FONTE` sem leitor estruturado (só RAG). Distribuição 13 alta / 15 média / 12 baixa | `lore_nova/rumors.txt:2`, `:5-7`, `:313-318`; `docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md:191` |
| P2 | Os rumores da lore se concentram em Nova Arcádia (19 de 40); 8 regiões têm 1–2. Um sorteio só da lore esgota a região em dias | `data/codex/rumors/story_rumores_nova_arcadia.md` (19 blocos), `story_rumores_floresta_sussurros.md` (1), `story_rumores_ophidia.md` (1) |
| P3 | Todo "rumor" do motor é template verdadeiro de pressão; não existe boato falso | `data/world/signals.json:2-30`; `REVISAO…:175` |
| P4 | Não há canal para a LLM propor rumor | `services/structured_outputs.py:72-100`; `REVISAO…:159` |
| P5 | `world.news` é um anel FIFO de 12 sem prazo: um rumor ficaria lá até ser empurrado, e um surto de rumores empurra as notícias de crise | `services/ambient.py:12`, `:93-126`; `services/world_perception.py:15` |
| P6 | A narração diária manda tudo como `FATO:`; um boato passaria como fato para a LLM | `agents/world_simulator.py:254` |
| P7 | A guarda de nomes da narração cai no template quando aparece nome de NPC do catálogo, mas o template de rumor da lore traz nomes ("Valerius", "Durrak") literalmente | `agents/world_simulator.py:210-239`, `:279-284`; `data/graph/entities.json:558` (`npc_valerius`), `:2192` (`npc_durrak`) |
| P8 | O ledger da 215 só aceita assuntos `event` e `memory_fact`; um rumor de semente não é nenhum dos dois, e gravar como `memory_fact` mistura boato com memória | `services/npc_knowledge.py:78`, `:255-276`, `:869`, `:904` |
| P9 | O caminho de rumor do ledger já marca `[BOATO, não confirmado]` e entrega só `told_to` (sem `believed_by`) para `memory_fact`; precisa valer igual para o tipo novo | `services/npc_knowledge.py:629-633`, `:838-845` |
| P10 | `pending_digest` guarda itens com `subject_id` por até 10 dias, e o anel tem teto 20: rumores competiriam com avisos de crise pelo espaço | `agents/storyteller.py:710-716`; `services/world_engine.py:711` |
| P11 | A narração diária só roda com item percebido; se o rumor for o único item do dia, contá-lo como item cria uma chamada LLM que não existiria | `agents/storyteller.py:746-753`, `:1257-1263` |
| P12 | API devolve `world.news` com lista branca de campos; um campo interno novo (verdade, id) vazaria se a lista mudasse sem cuidado | `api.py:2919-2926` |

## 2. Requisitos

Constantes marcadas `[BALANCEAR]` vivem em `data/world/rumor_config.json` e são calibradas pelo
simulador offline (Etapa 7, `docs/spec302/`).

### 2.1 Sementes (dados gerados da lore)

- **R1 — Tabela gerada.** `scripts/build_rumor_seeds.py` gera `data/world/rumor_seeds.json` de
  forma determinística (mesma entrada → arquivo byte a byte igual, LF, `newline=""`). Modo
  `--check` sai com código ≠ 0 se o arquivo versionado divergir do gerado (para teste/CI).
- **R2 — Família `lore` (40 sementes).** Uma semente por bloco `[CATEGORIA: RUMOR]` de
  `lore_nova/rumors.txt`, com:
  - `source` = `lore_nova/rumors.txt:<linha do [CATEGORIA]>` (teste lê a linha e confere);
  - `title` (linha de título do bloco), `fonte` (texto de `[FONTE: …]`), `confiabilidade`
    (`alta|media|baixa`, sem acento no valor);
  - `regions` (ids de `world_map.json`) e `location_id` resolvidos das `[TAGS]` por nome/alias de
    local e entidade; tag sem correspondência vai para `tags_unmapped` (relatório do script);
    sem região resolvida, a semente fica `disabled: true` até curadoria;
  - `entities` (ids **existentes** em `data/graph/entities.json`/`entities_extra.json`);
  - `subject` ∈ `pessoa|faccao|lugar|criatura|objeto|costume`;
  - `truth` default por confiabilidade: `alta`/`media` → `true`, `baixa` → `false`;
  - `review: "dono"` até o dono revisar (mesmo padrão de `data/npc_seed_tables.json:41`).
  Blocos vazios (ex.: `---` duplicado em `lore_nova/rumors.txt:273-275`) são ignorados; o script
  falha se contar ≠ 40 blocos de rumor.
- **R3 — Família `avistamento` (enche as regiões pobres em lore).** Uma semente por criatura de
  `data/bestiary.json` com `type ∈ {Minion, Standard, Elite}` e `regions` não vazio (BOSS e
  tipos fora do catálogo ficam de fora), `source = data/bestiary.json:<linha do id>`,
  `subject="criatura"`, `entities=[<enemy_id>]`, `confiabilidade="media"`,
  `truth_mode="regional"` (a verdade depende de onde o rumor nasce, R8). Texto de template
  (`rumor_config.json`), nunca a descrição do bestiário.
- **R4 — Curadoria preservada.** `data/world/rumor_seed_overrides.json` (editado à mão) é mesclado
  por `id` depois da geração e vence o gerado em: `truth`, `gist`, `fonte_label`,
  `public_names`, `labels`, `regions`, `location_id`, `quest_eligible`, `disabled`, `review`.
  Regerar nunca apaga curadoria (teste).
- **R5 — Texto curto e seguro.** Cada semente `lore` tem `gist` (≤ 200 caracteres, sem dígitos):
  por padrão o título em minúsculas + `fonte_label` derivado da FONTE (primeiro sintagma, ≤ 60
  caracteres); a curadoria pode reescrever. Nomes de NPC/fação no `gist` só podem aparecer se
  estiverem em `public_names` da semente; os demais viram o rótulo de `labels` (ex.:
  `"npc_durrak": "o dono do estaleiro"`). Teste varre as 40 sementes.
- **R6 — Proporção de falsos.** Com os defaults, a fração de `truth=false` entre as sementes
  `lore` habilitadas fica em [0,20; 0,35]; a fração entre rumores **percebidos** na simulação
  fica em [0,20; 0,30] (meta do dono: ~25 %, `[BALANCEAR]` por `AVISTAMENTO_FALSE_P` e pelos
  pesos de família).

### 2.2 Nascimento (motor)

- **R7 — Região frequentada.** `world_sim.region_presence[region] = último dia em que o herói
  estava na região` (escrito pelo hook diário a partir de `ctx.world.current_location_id`). Uma
  região é **frequentada** no dia `d` se `d − region_presence[region] ≤ FREQUENT_WINDOW_DAYS`
  (14, `[BALANCEAR]`). A região atual é sempre frequentada.
- **R8 — Sorteio diário.** Hook `rumors` (stage `post`, order 20, depois de `npc_world`) com
  `day_rng(game_id, day, "rumors")`. Para **cada** região de `region_ids()` em ordem estável,
  sorteia `roll` (sempre, para o fluxo do RNG não depender de quem é frequentada); se a região é
  frequentada e `roll < RUMOR_BIRTH_P` (0,5, `[BALANCEAR]`), nasce **1** rumor:
  - candidatas: sementes habilitadas da região (`regions` contém a região; `avistamento` também
    aceita criaturas de regiões **adjacentes**, `world_pressures.region_adjacency`), que não
    estejam ativas, não tenham sido percebidas pelo jogador, estejam fora do cooldown
    (`SEED_COOLDOWN_DAYS` = 30 desde o último nascimento não percebido), não citem NPC morto e
    cujo texto renderizado não case assinatura secreta não revelada
    (`memory_provenance.find_strict_unrevealed`, `services/memory_provenance.py:177-186`);
  - peso por família: `lore` `LORE_WEIGHT` (3) × `avistamento` 1 (`[BALANCEAR]`);
  - `avistamento`: criatura da própria região → `truth=true`; da adjacente → `truth=false`;
    a escolha entre as duas é `AVISTAMENTO_FALSE_P` (0,25, `[BALANCEAR]`);
  - `lore`: `truth` da semente;
  - local de nascimento: `seed.location_id` se for nó não-interior da região, senão
    `world_pressures.region_primary_location(region)`.
  Sem candidata → nada nasce (log `rumor.exhausted{region}`).
- **R9 — Instância.** O rumor nascido é um `RumorInstance` (§3.3) em `world_sim.rumors`, com
  `rumor_id = sha256(game_id|seed_id|born_day)[:16]`, `expires_day = born_day +
  RUMOR_TTL_DAYS` (10). O hook devolve um `DigestItem` `kind="rumor"`,
  `template_id="rumor.<family>"`, `subject_id=rumor_id`, `region_id`, `location_id` de
  nascimento. Teto do ledger `RUMOR_LEDGER_MAX` = 40 (despeja expirados mais antigos primeiro,
  nunca um ativo percebido).
- **R10 — Nunca lê o herói.** Nascimento, candidatas e verdade não leem nível, ficha, ouro,
  inventário nem fama. A posição só decide "frequentada" (R7) e percepção (R12). Teste: mesmo
  estado com `player.level` 1 e 20 → mesmos rumores.
- **R11 — Rumor nunca é fato.** Nenhuma função desta spec escreve em `event_log`,
  `pending_world_events`, `world_projection`, `memory_facts`, `quests` ou pressões. Rumor não é
  causa em `data/world/pressures.json` e itens `kind="rumor"` são ignorados por
  `world_quests.offer_from_perceived` e por `npc_world.on_perceived`. Teste por AST/grep no
  módulo novo + teste de comportamento nos dois consumidores.

### 2.3 Percepção (regra de ouro)

- **R12 — Canais.** Um item de rumor é perceptível (`world_perception.perceivable`) se:
  - (a) **regional habitado:** `item.region_id` = região atual **e** o local atual (ou seu pai)
    tem tag de povoado (`SETTLEMENT_TAGS`, default `cidade`, `vila`, confirmar na Etapa 0) ou
    está na família (`_family`) do local de nascimento; ou
  - (b) **ouvido:** `rumor_id ∈ location_heard[local atual]` (SPEC-215 `on`; mesmo caminho de
    `services/world_perception.py:79`).
  Com a 215 `off`/`shadow`, só o canal (a). Item não percebido espera em `pending_digest` até o
  `expires_day` (o filtro de 10 dias de `agents/storyteller.py:710-716` já cobre o TTL).
- **R13 — No máximo 1 rumor novo por dia.** Depois de `perceivable`, `rumors.limit_perceived`
  mantém **no máximo `RUMOR_PERCEIVED_PER_DAY` (1) rumor novo por dia de jogo** e
  `RUMORS_PER_ACTION_MAX` (1) por ação, ordenando por (canal `b` antes de `a`, nascimento mais
  recente, `rumor_id`). `world_sim.rumor_last_perceived_day` impede um segundo rumor no mesmo
  dia em outra ação. Os excedentes continuam em `pending_digest` (podem ser percebidos depois,
  dentro do TTL). Itens não-rumor não são afetados (teste de regressão da 302).
- **R14 — Registro da percepção.** Rumor percebido: `RumorInstance.perceived_day = dia`,
  `rumor_id` entra em `world_sim.perceived_ids` (ledger da 305), e `world.news` recebe a entrada
  do R15.
- **R15 — `world.news` com prazo e teto.** A entrada de rumor tem os campos atuais de
  `append_news` mais `kind="rumor"`, `rumor_id`, `expires_day`. Regras:
  - texto = `rumors.render_news` (template + `gist`, R5), nunca texto da LLM (mantém a R25 da
    302 para itens do motor);
  - entradas de rumor com `expires_day < dia` saem de `world.news` a cada tick
    (`rumors.prune_news`) e são ignoradas por `heard_block` (defesa dupla);
  - no máximo `RUMOR_NEWS_MAX` (4) entradas de rumor em `world.news` (as mais antigas saem
    primeiro); entradas não-rumor nunca são removidas por esta regra.
- **R16 — Prompt marca boato.** `ambient.heard_block` prefixa entradas `kind="rumor"` com
  `(boato)` e acrescenta ao cabeçalho: "Itens marcados (boato) podem ser falsos: narre como
  boato, nunca como fato confirmado." Nenhum prompt recebe `truth`, `truth_mode`,
  `confiabilidade`, `rumor_id` ou `seed_id`.
- **R17 — API.** `world.news` na API (`api.py:2919-2926`) ganha só `kind ∈ {"noticia","boato"}`.
  Nunca saem `truth`, `rumor_id`, `seed_id`, `expires_day`, `confiabilidade`. `world_sim.rumors`
  nunca sai (já é privado, `state.py:655-657`). O web mostra um selo "boato" na lista de notícias
  (`web/src/heardNews.ts`, `web/src/types.ts`). Sem aba de rumores (`VISAO.md:82`).

### 2.4 Propagação entre NPCs (SPEC-215)

- **R18 — Assunto novo `rumor`.** `npc_knowledge.SUBJECT_KINDS` ganha `"rumor"`.
  `_subject_type("rumor", …)` = `RUMOR` (parâmetros existentes `(0.35, 5, 1)`,
  `services/npc_knowledge.py:58`); `_subject_text` = `rumors.render_news` da instância (vazio se
  a instância não existe ou expirou). Saves antigos carregam (só ganham um valor aceito);
  `normalize_knowledge` continua descartando tipos desconhecidos.
- **R19 — Semeadura.** `npc_knowledge.turn_updates` (ponto único por turno,
  `agents/turn_finalizer.py:55`) passa a varrer `world_sim.rumors` com `born_turn == turno`: grava
  `rumor_id` em `location_heard[local de nascimento]`, liga `told_to` aos residentes do local
  (`_residents`, canal `local_rumor`, hops 0) e agenda `schedule_propagation(…, "rumor", …)`.
  Idempotente (ids determinísticos).
- **R20 — Sempre boato.** Para `subject_kind="rumor"`: a entrega cria só `told_to` (nunca
  `believed_by`, mesmo tratamento de `memory_fact` em `npc_knowledge.py:629-633`) e
  `knowledge_lines` rotula **sempre** `[BOATO, não confirmado]`, com ou sem `observed_by`. Rumor
  com assinatura secreta não revelada não propaga nem aparece (R7 da 215 continua valendo).
- **R21 — Expiração no ledger.** Instância expirada some do contexto do NPC (`_subject_text`
  vazio → linha descartada, `npc_knowledge.py:835-837`); os links ficam até o despejo normal
  (`_cap_links`).

### 2.5 Narração (a LLM só costura)

- **R22 — Sem chamada nova.** `narrate_day` recebe os itens de rumor como linhas `BOATO: <texto>`
  (os demais seguem `FATO:`), e o prompt de sistema ganha: "Linhas BOATO são coisas que o herói
  ouviu: costure em no máximo 1 frase, como boato (dizem, contam, juram), sem confirmar." Se os
  itens percebidos da ação forem **só** rumores, `narrate_day` **não** chama a LLM: o
  `[ECOS DO MUNDO]` usa o texto do template. Teste conta invokes no MockLLM: o número de chamadas
  por ação é igual ao baseline da 302 em qualquer combinação.
- **R23 — Nomes.** `world_simulator._allowed_names` inclui os `public_names` dos rumores
  percebidos na ação; `render_news` nunca emite nome de NPC/fação fora de `public_names` (usa
  `labels`; fação desconhecida usa o rótulo de `_faction_label`,
  `services/world_perception.py:90-102`). Teste varre todas as sementes × templates contra
  `_catalog_names()`.
- **R24 — Memória canônica não recebe boato.** Qualquer consumidor que grave a narração diária ou
  o digest como memória canônica (proposta R2(b) da revisão, SPEC-309) deve excluir itens
  `kind="rumor"` (helper `rumors.is_rumor_item`). Se a 309 pousar antes, esta spec ajusta o
  consumidor; se pousar depois, a 309 usa o helper. Teste aqui: com a gravação existente do
  arquivista, nenhum `MemoryFact` canônico contém `gist` de rumor.

### 2.6 Rumor proposto pelo narrador (opcional)

- **R25 — `ProposedRumor`.** `StoryUpdate` ganha `proposed_rumors: list[ProposedRumor]`
  (default vazio, item inválido descartado como em `coerce_crime_claims`,
  `services/structured_outputs.py:118-129`). Só entra se o narrador **contou um boato que alguém
  em cena disse neste turno**.
- **R26 — Validação (Python).** Aceito só se: modo `RPG_RUMORS_PROPOSED=on`;
  `quarantine_llm_payload` falso (`agents/storyteller.py:1575`); `entity_ids` não vazio e todos
  existentes no grafo com `visibility="public"`; `location_id` vazio (= local atual) ou nó real;
  `text` com 20–200 caracteres, sem dígitos, sem nome de catálogo fora do permitido (R23), sem
  nome do jogador, sem assinatura secreta não revelada; não duplica rumor ativo, semente da região
  nem notícia em `world.news` (`difflib` ≥ `TITLE_SIMILARITY` 0,75, `services/quest_log.py:30`, ou
  mesmo conjunto de entidades + mesmo `subject` dentro do TTL); e cabe no teto do dia (R13: conta
  como o rumor do dia). No máximo 1 por turno.
- **R27 — Efeito.** Aceito vira `RumorInstance` `family="narrador"`, `truth=false`,
  `quest_eligible=false`, `perceived_day=hoje` (o herói acabou de ouvir), entrada em `world.news`
  com o `text` validado (cortado em `NEWS_TEXT_MAX`, `services/ambient.py:13`) e semeadura pelo
  R19. Rejeição só loga `rumor.proposed_rejected{reason}`; nunca derruba o turno.

### 2.7 Estado, rollout, telemetria e prova

- **R28 — Schema aditivo.** `WorldSimState` ganha `rumors`, `region_presence`,
  `rumor_last_perceived_day`, `rumor_seed_last_born` (§3.3). Sem bump de `SIM_VERSION` nem de
  `SCHEMA_VERSION`; save sem as chaves carrega e começa vazio.
- **R29 — Determinismo e idempotência.** Repetir o tick do mesmo dia não cria rumor novo (o motor
  só tica dias novos); sem `random` global no módulo novo (teste AST, padrão SPEC-302 R3).
  Mesma seed + mesma rota do herói → mesma sequência de rumores.
- **R30 — Rollout `RPG_RUMORS=off|shadow|on`** (exige `RPG_WORLD_ENGINE=on`; com o motor fora de
  `on`, comporta-se como `off`). `shadow`: o hook calcula nascimentos e loga
  `rumor.shadow_born{family, truth}`, sem gravar instância, digest, notícia nem ledger.
  `RPG_RUMORS_PROPOSED=off|on` separado. Defaults: decisão D3.
- **R31 — Telemetria.** `log_event("rumor", born|perceived|expired|exhausted|proposed_accepted|
  proposed_rejected, family, region, channel)`; contagem de falsos só agregada no `report`
  (nunca o `gist`). Playtest grava por campanha: nascidos, percebidos, % falsos percebidos,
  propostos aceitos/rejeitados; `report` ganha linhas na seção "Mundo".
- **R32 — Invariantes de playtest (todos `error`).** `rumor.became_fact` (algum `rumor_id` ou
  `gist` em `event_log`/projection/`memory_facts` canônicos/`quests` criadas fora da SPEC-313);
  `rumor.over_daily_cap` (> 1 rumor percebido no mesmo dia, exceto via diálogo de NPC);
  `rumor.expired_in_news`; `rumor.truth_leak` (`truth`/`rumor_id`/`seed_id` em payload de
  `/game/state` ou `/game/action` ou em prompt registrado pelo harness).

### Fora de escopo

- Criação, prazo e resolução da quest `investigar_rumor` (SPEC-313; aqui só a interface §3.6).
- Rumor que muda preço, atitude de NPC, reputação, pressão ou encontro (um avistamento verdadeiro
  **não** aumenta a chance de encontrar a criatura).
- "Eco distorcido" (boato falso derivado de crise real: "dizem que a febre chegou a X") — decisão
  D5, fora do v1 por default.
- Rumor sobre o próprio herói (fama é da SPEC-298) e rumor de `daily_life.txt`.
- Trilha pista → revelação de segredo (N5): semente que toca segredo fica bloqueada (R8), não
  vira pista.
- Aba de rumores, filtro "verdadeiro/falso" na UI ou qualquer indicação de verdade ao jogador.
- `<O_QUE_VOCE_SABE>` no `npc_actor` (SPEC-310); aqui o NPC já recebe as linhas `[BOATO]` pelo
  gate de contexto existente da 215.
- Mudar `SUBJECT_PARAMS[RUMOR]` (0,35 / 5 / 1) — calibração da 215.
- Chamada LLM nova por rumor; geração de rumor por LLM fora do `ProposedRumor`.

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/rumors.py` | **Owner do ciclo de vida do rumor** dentro de `world_sim`: carga de sementes/config, região frequentada, hook diário de nascimento, render, limite de percepção, TTL/teto de notícias, validação de `ProposedRumor`, interface para a 313. Puro, sem LLM, sem RNG global |
| `scripts/build_rumor_seeds.py` | Gerador determinístico (R1–R5) + `--check` + relatório de `tags_unmapped` |
| `data/world/rumor_seeds.json` | **Gerado.** Sementes `lore` + `avistamento` (não editar à mão) |
| `data/world/rumor_seed_overrides.json` | Curadoria manual (R4) |
| `data/world/rumor_config.json` | Constantes `[BALANCEAR]`, `SETTLEMENT_TAGS`, templates de frase por família |
| `tests/test_spec312_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `state.py` (`WorldSimState`, `:655-684`): chaves do R28; `TypedDict` `RumorInstance`.
- `services/world_engine.py` (`_register_default_hooks`, `:724-730`): registra
  `rumors.day_hook` (`post`, order 20). O hook muta `ctx.sim` (precedente:
  `services/world_calendar.py:439-440`) e devolve `DayHookResult(digest=[…])`.
- `services/world_perception.py`: `perceivable` aceita a visibilidade `rumor` (canais do R12);
  `render` delega `template_id` `rumor.*` a `rumors.render_news`; `record_news` passa
  `kind`/`rumor_id`/`expires_day` para itens de rumor.
- `services/ambient.py`: `append_news` aceita `extra: dict | None` (campos adicionais na
  entrada; dedupe atual intacto); `heard_block` filtra expirados e marca `(boato)` (R16).
- `agents/storyteller.py`:
  - `_perceive_world` (`:682-722`): depois de `perceivable`, `rumors.limit_perceived`; depois de
    `record_news`, `rumors.prune_news`; grava `perceived_day` (R13–R15);
  - `_narrate_world` (`:746-753`): repassa itens marcados; nenhuma lógica nova de chamada (a regra
    "só rumor → sem LLM" fica em `narrate_day`);
  - `StoryUpdate` (`:90-164`): campo `proposed_rumors`; aplicação perto de `:1935-1942`
    (`rumors.accept_proposed`).
- `agents/world_simulator.py` (`narrate_day`, `:248-285`; `_allowed_names`, `:223-239`): linhas
  `BOATO:`, sem invoke quando só há rumor (R22), `public_names` (R23).
- `services/npc_knowledge.py`: `SUBJECT_KINDS` + `"rumor"` (`:78`); `_subject_type`/
  `_subject_text` (`:255-276`); `deliver_due` trata `"rumor"` como `memory_fact` (`:629-633`);
  `knowledge_lines` (`:838-845`); `turn_updates` (`:672-774`) semeia rumores nascidos no turno
  (R19); `inherit_local` (`:508`) reconhece `rumor_id` em `location_heard`.
- `services/world_quests.py` e `services/npc_world.py`: ignoram `kind="rumor"` (R11; guarda
  explícita + teste).
- `api.py` (`:2919-2926`): campo `kind` público (R17).
- `web/src/types.ts`, `web/src/heardNews.ts` (e o componente que lista notícias,
  `web/src/components/Hud.tsx` ou `web/src/workspace/ContextSurface.tsx`, confirmar na Etapa 0):
  selo "boato".
- `playtest/invariants.py`, `playtest/telemetry.py`, `playtest/report.py`: R31–R32.
- `docs/spec302/world_engine_sim.py` + `docs/spec302/README.md`: modo `--s312` (Etapa 7).

### 3.3 Schemas (`state.py`, aditivo)

```python
RumorFamily = Literal["lore", "avistamento", "narrador"]


class RumorInstance(TypedDict, total=False):
    rumor_id: str  # sha256(game_id|seed_id|born_day)[:16]
    seed_id: str  # id da semente ("narrador:<hash>" para proposto)
    family: RumorFamily
    region_id: str
    location_id: str  # local de nascimento
    entities: list[str]  # ids do grafo (para avistamento: [enemy_id])
    subject: str
    truth: bool  # INTERNO: nunca em prompt, API ou news
    quest_eligible: bool  # INTERNO (313)
    born_day: int
    born_turn: int
    expires_day: int  # born_day + RUMOR_TTL_DAYS
    perceived_day: int  # 0 = ainda não percebido pelo jogador
    text: str  # só para family="narrador" (texto validado)
    resolution: str  # "" | "confirmado" | "desmentido" | "inconclusivo" (escrito via 313)


class WorldSimState(TypedDict, total=False):
    version: int  # (campos atuais da 302-305 omitidos)
    rumors: list[RumorInstance]  # teto RUMOR_LEDGER_MAX (40)
    region_presence: dict[str, int]  # região -> último dia com o herói lá
    rumor_last_perceived_day: int
    rumor_seed_last_born: dict[str, int]  # seed_id -> último born_day (cooldown)
```

```python
# services/structured_outputs.py
class ProposedRumor(BaseModel):
    text: str = Field(description="O boato em 1 frase, como alguém em cena contou. Sem números.")
    entity_ids: list[str] = Field(
        default_factory=list, description="Ids EXATOS de <ENTIDADES_CANONICAS> citados no boato."
    )
    location_id: str = Field(default="", description="Id de local EXATO ou vazio (= aqui).")
```

### 3.4 Assinaturas públicas

```python
# services/rumors.py
MODES = ("off", "shadow", "on")
def mode() -> str
def proposed_mode() -> str
def load_seeds() -> dict[str, dict]                       # lru_cache; só habilitadas
def config() -> dict                                       # rumor_config.json
def frequented_regions(sim: dict, day: int) -> list[str]
def day_hook(ctx: "DayContext") -> "DayHookResult"         # R7-R9
def candidates(state: dict, sim: dict, region_id: str, day: int) -> list[tuple[dict, float]]
def is_rumor_item(item: dict) -> bool
def render_news(state: dict, rumor: dict) -> str           # template + gist/labels (R5, R23)
def public_names(rumor: dict) -> set[str]
def limit_perceived(state: dict, sim: dict, seen: list[dict], day: int) -> list[dict]  # R13
def mark_perceived(sim: dict, rumor_ids: list[str], day: int) -> dict
def prune_news(world: dict, day: int) -> dict              # R15
def accept_proposed(state: dict, proposals: list, *, turn: int, day: int,
                    quarantined: bool) -> tuple[dict | None, dict | None, list[str]]
    # -> (world_sim novo | None, world novo | None, motivos de rejeição)

# Interface SPEC-313 (§3.6)
def investigable(state: dict, day: int) -> list[dict]      # RumorHook (sem texto de verdade)
def truth_of(state: dict, rumor_id: str) -> bool | None
def mark_resolved(sim: dict, rumor_id: str, outcome: str, day: int) -> dict
```

Fluxo por ação que vira dia (storyteller): `advance_days` → hook `rumors` grava instâncias em
`world_sim.rumors` e devolve itens `kind="rumor"` no digest → `_perceive_world`: `perceivable`
→ `rumors.limit_perceived` → `record_news` → `rumors.mark_perceived` → `rumors.prune_news` →
`perceived_ids` → 305 (ignora rumor) → `_narrate_world` (`BOATO:`; sem LLM se só rumor). No
`turn_finalizer`, `npc_knowledge.turn_updates` semeia os rumores com `born_turn` = turno atual.

### 3.5 Formatos de dados (exemplos com IDs reais)

`data/world/rumor_seeds.json` (trecho; gerado):

```json
{
  "_doc": "GERADO por scripts/build_rumor_seeds.py a partir de lore_nova/rumors.txt e data/bestiary.json + rumor_seed_overrides.json. Não editar à mão.",
  "seeds": {
    "rumor_os_navios_de_durrak_atraem_o_fundo": {
      "family": "lore",
      "source": "lore_nova/rumors.txt:313",
      "title": "Os Navios de Durrak Atraem o Fundo",
      "fonte": "Marinheiro que se recusou a embarcar",
      "fonte_label": "um marinheiro que largou o contrato",
      "gist": "os navios do estaleiro são feitos de osso de leviatã, e o fundo do mar vem buscar o que é seu",
      "regions": ["brekmar"],
      "location_id": "brekmar",
      "subject": "objeto",
      "entities": ["npc_durrak", "brekmar"],
      "public_names": [],
      "labels": {"npc_durrak": "o dono do estaleiro"},
      "confiabilidade": "alta",
      "truth": true,
      "quest_eligible": true,
      "tags_unmapped": ["Estaleiro das Almas"],
      "review": "dono"
    },
    "rumor_valerius_nao_come_nem_dorme": {
      "family": "lore",
      "source": "lore_nova/rumors.txt:5",
      "title": "Valerius não Come Nem Dorme",
      "fonte": "Servos do Anel Dourado que bebem no Dragão Bêbado às sextas",
      "fonte_label": "servos do Anel Dourado",
      "gist": "o Lorde Protetor nunca é visto comendo, e a cama dele fica intocada por semanas",
      "regions": ["nova_arcadia"],
      "location_id": "na_anel_dourado",
      "subject": "pessoa",
      "entities": ["npc_valerius"],
      "public_names": ["Valerius"],
      "confiabilidade": "media",
      "truth": true,
      "quest_eligible": true,
      "review": "dono"
    },
    "rumor_avist_enemy_rato_peste_anel_lama": {
      "family": "avistamento",
      "source": "data/bestiary.json:2",
      "regions": ["nova_arcadia"],
      "subject": "criatura",
      "entities": ["enemy_rato_peste_anel_lama"],
      "creature_label": "ratos da peste",
      "confiabilidade": "media",
      "truth_mode": "regional",
      "quest_eligible": true,
      "review": "dono"
    }
  }
}
```

`data/world/rumor_config.json` (trecho; `[BALANCEAR]`):

```json
{
  "constants": {
    "RUMOR_BIRTH_P": 0.5, "FREQUENT_WINDOW_DAYS": 14, "RUMOR_TTL_DAYS": 10,
    "RUMOR_PERCEIVED_PER_DAY": 1, "RUMORS_PER_ACTION_MAX": 1, "RUMOR_NEWS_MAX": 4,
    "SEED_COOLDOWN_DAYS": 30, "RUMOR_LEDGER_MAX": 40, "LORE_WEIGHT": 3,
    "AVISTAMENTO_FALSE_P": 0.25, "PROPOSED_PER_TURN": 1
  },
  "settlement_tags": ["cidade", "vila"],
  "templates": {
    "rumor.lore": ["{fonte_label} juram que {gist}.", "Corre à boca pequena que {gist}."],
    "rumor.avistamento": ["Caçadores dizem ter visto {criatura} rondando {local}.",
                          "Na taverna, alguém jura que {criatura} anda perto de {local}."],
    "rumor.narrador": ["{text}"]
  }
}
```

A escolha do template dentro da família usa `sha256(rumor_id)` (não o RNG do dia), para que
re-renderizar a mesma instância dê o mesmo texto. `{local}` usa o nome do local de nascimento
(avistamento falso: local da região onde o rumor nasceu, não da criatura).

Exemplo concreto: dia 31, herói em `brekmar` (tag `cidade`), `region_presence` =
`{"brekmar": 31, "nova_arcadia": 24}`; o hook sorteia `nova_arcadia` (0,41 < 0,5 → nasce
`rumor_valerius_nao_come_nem_dorme` em `na_anel_dourado`) e `brekmar` (0,18 → nasce
`avistamento` de criatura adjacente, `truth=false`). O jogador percebe só o de `brekmar` (canal
a); o de Nova Arcádia se espalha pela 215 e, se chegar a `brekmar` antes do dia 41, pode ser
percebido num dia seguinte (canal b).

### 3.6 Interface com a SPEC-313 (`investigar_rumor`)

- `rumors.investigable(state, day)` devolve rumores **percebidos pelo jogador**, não expirados,
  `quest_eligible`, sem `resolution`, cujo texto não casa segredo não revelado:
  `{rumor_id, family, region_id, location_id, subject, entities, born_day, expires_day}`
  (**sem** `truth`; a 313 consulta `truth_of` só na resolução).
- Rumor **falso** pode gerar quest (decisão do dono 2). A 313 nunca revela a verdade na oferta
  nem no título; o desfecho "desmentido" não grava o `gist` como fato e o "confirmado" não grava
  nada como fato por esta spec (qualquer evento é da 313, com prova própria).
- `rumors.mark_resolved` é o único writer de `resolution` (a 313 chama). Rumor resolvido sai de
  `investigable` e do sorteio de cooldown.
- Família `narrador` tem `quest_eligible=false` (decisão D4).

## 4. Plano passo a passo

Marco único. Cada etapa: testes primeiro; rodar só os arquivos da etapa (`-q --lf -x`, no máximo
`-n 2`); suíte completa 1× no pouso pelo coordenador.

### Etapa 0 — Sondas e ownership

1. Confirmar no código: tags de povoado no `world_map.json` (`cidade`/`vila`; ex. `nova_arcadia`
   `:14-19`); campo de NPC morto na projection usado por `npc_layers.npc_alive`; componente web que
   lista `news`; status de 309/313 (quem pousa primeiro ajusta R24/§3.6).
2. Consultar `project_index` (`state_ownership`) para `world_sim` e `world.news`; registrar
   `services/rumors.py` como owner de `world_sim.rumors`/`region_presence`.
3. Divergência → ajustar esta spec no mesmo commit (seção 10, "Desvios").

### Etapa 1 — Gerador e dados

1. **Testes** (`tests/test_spec312_seeds.py`):
   - `test_forty_lore_seeds_with_source_line` (40 sementes `lore`; a linha de `source` em
     `lore_nova/rumors.txt` é `[CATEGORIA: RUMOR]`);
   - `test_confiabilidade_distribution_13_15_12`;
   - `test_regions_locations_entities_exist` (regiões ∈ `region_ids()`, locais em
     `world_map.json`, entidades no grafo);
   - `test_default_truth_by_confiabilidade_and_false_ratio` (R2, R6);
   - `test_avistamento_excludes_boss_and_points_to_bestiary_line`;
   - `test_gist_short_no_digits_no_unlisted_names` (R5);
   - `test_overrides_survive_regeneration` (R4);
   - `test_generator_is_byte_stable_lf` (`--check` verde após gerar; sem `\r`).
2. **Implementação:** `scripts/build_rumor_seeds.py`, `rumor_seed_overrides.json` (inicial com
   `public_names`/`labels` mínimos para passar R5), `rumor_seeds.json`, `rumor_config.json`.

### Etapa 2 — Nascimento no motor

1. **Testes** (`tests/test_spec312_birth.py`):
   - `test_frequented_regions_window` (R7);
   - `test_birth_rate_per_frequented_region` (média em 2.000 dias sintéticos ≈ 0,5 ± 0,05);
   - `test_rng_stream_independent_of_frequented_set` (R8);
   - `test_candidates_exclude_active_perceived_cooldown_dead_secret`;
   - `test_avistamento_truth_regional` (própria → true; adjacente → false);
   - `test_instance_ids_deterministic_and_ttl` (R9);
   - `test_ledger_cap_never_drops_active_perceived`;
   - `test_independent_of_player_stats` (R10);
   - `test_no_global_random_in_rumors` (AST, R29);
   - `test_rumor_module_never_writes_event_log_projection_memory_quests` (AST/grep, R11);
   - `test_shadow_writes_nothing` e `test_requires_world_engine_on` (R30).
2. **Implementação:** `services/rumors.py` (`frequented_regions`, `candidates`, `day_hook`),
   registro do hook, `state.py`.

### Etapa 3 — Percepção e notícias

1. **Testes** (`tests/test_spec312_perception.py`):
   - `test_regional_channel_requires_settlement_or_origin_family` (R12a);
   - `test_heard_channel_requires_location_heard_and_215_on` (R12b);
   - `test_max_one_new_rumor_per_day_and_per_action` (R13, inclusive em duas ações no mesmo dia);
   - `test_excess_rumor_stays_pending_until_ttl`;
   - `test_non_rumor_items_unaffected_by_cap` (regressão 302);
   - `test_news_entry_has_kind_and_expiry_and_template_text` (R15);
   - `test_prune_news_removes_expired_rumors_only`;
   - `test_rumor_news_cap_keeps_crisis_news`;
   - `test_heard_block_marks_boato_and_hides_expired` (R16);
   - `test_api_news_kind_only_no_truth_or_ids` (R17, varre `/game/state` e `/game/action`);
   - `test_world_quests_and_npc_beliefs_ignore_rumor_items` (R11).
2. **Implementação:** `world_perception`, `ambient`, `_perceive_world`, `api.py`, web (selo).

### Etapa 4 — Propagação pela SPEC-215

1. **Testes** (`tests/test_spec312_knowledge.py`):
   - `test_rumor_subject_kind_roundtrip_and_legacy_save` (R18);
   - `test_turn_updates_seeds_birth_location_and_schedules` (R19, idempotente);
   - `test_delivery_creates_only_told_to` e `test_label_always_boato_even_if_observed` (R20);
   - `test_secret_rumor_never_propagates`;
   - `test_expired_rumor_drops_from_npc_context` (R21);
   - `test_rumor_reaches_neighbor_and_becomes_perceivable_there` (integração com R12b).
2. **Implementação:** `npc_knowledge` (tipo, texto, entrega, rótulo, semeadura).

### Etapa 5 — Narração

1. **Testes** (`tests/test_spec312_narration.py`):
   - `test_rumor_lines_are_boato_not_fato` (prompt capturado no MockLLM);
   - `test_rumor_only_day_makes_zero_llm_calls` e `test_invoke_count_equals_302_baseline` (R22);
   - `test_public_names_allowed_and_others_labeled` (R23, todas as sementes × templates);
   - `test_no_canonical_memory_contains_rumor_gist` (R24).
2. **Implementação:** `narrate_day`, `_allowed_names`, `is_rumor_item` nos consumidores.

### Etapa 6 — `ProposedRumor`

1. **Testes** (`tests/test_spec312_proposed.py`):
   - `test_invalid_items_dropped_not_whole_response` (coerção);
   - `test_rejects_unknown_or_hidden_entity`, `test_rejects_digits_player_name_secret`,
     `test_rejects_duplicate_of_active_seed_or_news`, `test_rejects_when_quarantined`,
     `test_rejects_over_daily_cap` (R26);
   - `test_accepted_is_false_not_quest_eligible_and_perceived` (R27);
   - `test_fallbackllm_story_update_without_field_is_safe` (guard: `AIMessage` não quebra);
   - `test_proposed_mode_off_ignores_field`.
2. **Implementação:** `ProposedRumor`, campo em `StoryUpdate`, `rumors.accept_proposed`,
   aplicação no storyteller, instrução curta no prompt ("só se alguém em cena contou um boato").

### Etapa 7 — Interfaces, playtest e calibração

1. **Testes** (`tests/test_spec312_playtest.py`):
   - `test_investigable_hides_truth_and_filters` e `test_mark_resolved_single_writer` (§3.6);
   - `test_invariants_detect_fact_leak_cap_expired_truth` (estados sintéticos, R32);
   - `test_report_rumor_lines`;
   - `test_scenario_mundo_perceives_rumor_mock` (`--scenario mundo`, MockLLM, flags `on`: ≥ 1
     rumor percebido, 0 violação `error`).
2. **Simulador** (`docs/spec302/world_engine_sim.py --s312 --days 120 --seeds 60`), herói em dois
   perfis (parado em `nova_arcadia`; troca de região a cada 3 dias entre `brekmar`,
   `pradaria_ruinas`, `nova_arcadia`). Metas (registrar na §8 e no README):
   - S1 nascimentos por região frequentada por dia ∈ [0,45; 0,55];
   - S2 fração de dias com rumor novo percebido (herói em povoado) ∈ [0,35; 0,65];
   - S3 fração de falsos entre percebidos ∈ [0,20; 0,30];
   - S4 nenhuma semente `lore` percebida duas vezes no mesmo mundo;
   - S5 `world.news` nunca com > `RUMOR_NEWS_MAX` rumores nem rumor expirado;
   - S6 crescimento de `world_sim` ≤ 8 KB (repr) sobre o baseline da 302 (35,7 KB);
   - S7 dia médio de esgotamento da família `lore` por região (informativo; mostra o papel do
     `avistamento`).
   Fora da meta → ajustar só constantes de `rumor_config.json` (nunca o simulador).
3. **Implementação:** invariantes, telemetria, relatório, `--s312`.
4. **Verificação:** `python -m playtest run --all --turns 50` (MockLLM) com `RPG_WORLD_ENGINE=on`,
   `RPG_RUMORS=on`, `RPG_NPC_KNOWLEDGE=on`: 0 violação `error`; ruff nos arquivos tocados.

## 5. Critérios de aceite

- [ ] R1–R6: `rumor_seeds.json` gerado e estável (40 `lore` + `avistamento`), `source`
      arquivo:linha conferido, curadoria preservada, `gist` seguro, proporção de falsos
- [ ] R7–R11: nascimento por região frequentada com taxa `[BALANCEAR]`, determinístico,
      independente do herói; rumor nunca escreve fato
- [ ] R12–R17: percepção só por povoado/origem ou `location_heard`; ≤ 1 rumor novo por dia;
      `world.news` com TTL 10 e teto; `(boato)` no prompt; API só com `kind`
- [ ] R18–R21: assunto `rumor` no ledger da 215, sempre `[BOATO]`, só `told_to`, segredo bloqueado
- [ ] R22–R24: zero chamada LLM nova (contador), nomes protegidos, memória canônica sem boato
- [ ] R25–R27: `ProposedRumor` validado contra o grafo, dedupe, teto; aceito = falso e não
      elegível a quest
- [ ] R28–R32: saves antigos carregam; flags `off|shadow|on`; telemetria; invariantes
- [ ] Simulador S1–S6 dentro das metas (resultado na §8 e em `docs/spec302/README.md`)
- [ ] Guard de FallbackLLM no caminho de `StoryUpdate.proposed_rumors` (isinstance/try)
- [ ] `uv run pytest` verde (suíte completa offline, no pouso)
- [ ] Revisão independente Opus (`handoffs/SPEC-312-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado na §8
- [ ] Dono revisou `rumor_seed_overrides.json` (`truth`, `public_names`) — bloqueia só
      `RPG_RUMORS=on` no staging, não o `done` do código (D1)

## 6. Smoke test com LLM real

Pré-requisito: `RPG_WORLD_ENGINE=on`, `RPG_RUMORS=on`, `RPG_RUMORS_PROPOSED=on`,
`RPG_NPC_KNOWLEDGE=on`, DeepSeek nas `ROUTES`. Teto do dono: US$ 3/dia. A spec não cria chamada,
mas muda o prompt da narração diária (`BOATO:`) e o `StoryUpdate` (campo novo): o MockLLM não
mostra se a prosa confirma o boato nem se o provider preenche `proposed_rumors` com ids errados.

1. `uv run python -m playtest run --scenario mundo --turns 20 --real --max-cost 0.40 --seed 31`.
   Asserta: `mock=False`; ≥ 1 rumor percebido; nenhum dia com 2 rumores novos; no transcrito, o
   rumor aparece como boato ("dizem", "juram", "contam"), nunca confirmado; nº de invokes por ação
   igual ao baseline da 302; `/game/state` com `news[].kind="boato"` e sem `truth`/`rumor_id`;
   0 violação `error`.
2. No mesmo run, num povoado onde um rumor foi ouvido: ação "pergunto ao taverneiro o que se fala
   por aí" → o NPC repete o rumor como boato (linha `[BOATO]` no contexto registrado pelo
   harness); nenhum `GameEvent` novo com o texto.
3. `uv run python -m playtest run --profile diplomatico --turns 15 --real --max-cost 0.30 --seed 32`:
   registrar `proposed_rumors` aceitos/rejeitados e os motivos; leitura humana de 3 aceitos (ids
   reais, sem número, sem nome desconhecido). Rejeição de 100 % com motivo `entity` = bug de
   mapeamento → corrigir antes de `done`.
4. Descansar 11 dias no mesmo povoado → o rumor percebido no início some de `<OUVIU_DIZER>` e de
   `news` (TTL).

Custo esperado: ≤ US$ 0,80. Estourou o teto → parar e registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** chaves novas opcionais em `world_sim`; `news` sem `kind` = notícia;
  `knowledge_links` antigos não têm `rumor` e continuam válidos. Rollback de código (versão
  anterior lendo save novo): `normalize_knowledge` descarta links `rumor` e `heard_block` mostra o
  texto sem `(boato)` até o TTL; aceitável, documentado.
- **Regra de ouro:** rumor de outra região só chega por NPC (215 `on`); com 215 `off` o jogador
  só ouve rumores da região onde está. `truth` nunca sai do servidor (R17, R32).
- **Spam:** teto 1/dia, TTL 10, teto de 4 em `news`, `pending_digest` com teto 20 (rumores
  disputam com avisos de crise; S5 mede e, se preciso, rumor sai do digest antes de aviso).
- **Esgotamento:** Nova Arcádia tem 19 sementes `lore`, outras regiões 1–3; o `avistamento` cobre
  o resto. Sem ele, regiões remotas ficariam mudas em dias (S7).
- **Lore que toca segredo:** rumores como "Valerius e o Arauto da Névoa São o Mesmo Ser"
  (`lore_nova/rumors.txt:257-262`) podem casar assinatura secreta; ficam bloqueados enquanto o
  segredo não for revelado (R8). A curadoria pode marcar `quest_eligible=false` para segredos sem
  assinatura (4 de 19 têm, `REVISAO…:194`).
- **Prosa do storyteller:** a narração principal pode citar o boato e o arquivista resume o turno;
  o resumo registra "o herói ouviu que…", não um fato do mundo. A memória canônica estruturada é
  protegida por R24.
- **MockLLM/FallbackLLM:** todo o ciclo é Python; com FallbackLLM a narração cai no template e
  `proposed_rumors` some (guard). MockLLM não preenche `proposed_rumors` por padrão: o teste
  injeta.
- **Quota/latência:** zero chamada nova; +1 linha `BOATO:` na narração diária e no
  `<OUVIU_DIZER>`; schema do `StoryUpdate` cresce um campo.
- **Eval `npc_knowledge`:** o tipo novo pode mudar contagens do dataset da 215; não alterar
  evaluator/expected nesta tarefa — follow-up de relock pelo coordenador (como 298 R23).

## 8. Evidência

Simulador `bash scripts/dev/py.sh docs/spec302/world_engine_sim.py --s312 --days 120 --seeds 8`
(percepcao REAL via `storyteller._perceive_world`; metas na Etapa 7):

| meta | parado em `nova_arcadia` | viajante (3 em 3 dias) |
|---|---|---|
| S1 nascimentos por regiao frequentada por dia ∈ [0,45; 0,55] | **0,498** | **0,504** |
| S2 dias com rumor novo percebido ∈ [0,35; 0,65] | **0,498** | 0,933 (fora: ver §10, D-3) |
| S3 falsos entre percebidos ∈ [0,20; 0,30] | **0,209** | **0,295** |
| S4 semente `lore` percebida 2x no mesmo mundo | **0** | **0** |
| S5 violacoes em `world.news` (> 4 rumores ou expirado) | **0** | **0** |
| S6 crescimento de `world_sim` (repr) ≤ 8 KB | **7,7 KB** | 18,9 KB (fora: ver §10, D-3) |
| teto diario (>1 percebido no mesmo dia) | **0** | **0** |

S7 (informativo): a familia `lore` esgota as 22 sementes de Nova Arcadia; depois disso so o
`avistamento` (e a re-oferta por cooldown) sustenta o ritmo.

Playtest MockLLM `--all --turns 30` (16 perfis, `RPG_WORLD_ENGINE=on RPG_RUMORS=on
RPG_NPC_KNOWLEDGE=on`): 0 erros, 0 violacoes. Cenario `mundo` (40 turnos): 10 rumores percebidos,
0 violacao `rumor.*`. Smoke real (§6): **nao executado** (instrucao do coordenador).

## 10. Desvios da implementacao

- **D-1 `settlement_tags`** = `cidade, vila, porto, favela, docas` (a spec dizia `cidade, vila`;
  Brekmar e o Anel de Lama ficariam mudos). Confirmado no `world_map.json`.
- **D-2 `AVISTAMENTO_FALSE_P` 0,25 → 0,15** (calibracao S3: parado 0,31 / viajante 0,34 com 0,25).
- **D-3 viajante fora de S2/S6.** Com 3 regioes frequentadas nascem ~1,5 rumores/dia e o teto de 1
  percebido/dia fica saturado (0,93); o ledger maior pesa 18,9 KB. O perfil parado cumpre ambas.
  Nao mexi no `RUMOR_BIRTH_P` (decisao do dono); o coordenador decide se quer reduzir para
  regioes onde o heroi nao esta.
- **D-4 instancia compacta.** `entities`/`subject`/`quest_eligible` das familias `lore`/`avistamento`
  vem da semente (`rumors.entities_of/subject_of/is_quest_eligible`); so `narrador` os grava.
  `resolution` so existe depois de `mark_resolved` (que tambem grava `resolved_day`).
- **D-5 envelhecimento do ledger.** Instancia nao percebida some 5 dias depois de expirar, a
  percebida 20 dias depois (`_cap_ledger`); `rumor_seed_last_born` guarda o cooldown e o marcador
  `NEVER_AGAIN` (lore/narrador percebidos ou resolvidos nunca renascem; `avistamento` renasce
  depois do cooldown).
- **D-6 item do digest autossuficiente.** `params` do item de rumor leva `seed_id`, `family` e
  `expires_day`; `world_perception.render` renderiza so do item (a narracao nao tem o `world_sim` novo).
- **D-7 `ProposedRumor` sem texto novo no prompt.** A instrucao fica na `description` do campo do
  schema (so entra na chamada se o modo estiver `on`); o corpo do prompt do narrador nao mudou.
- **D-8 curadoria completa.** Os 40 `gist`/`fonte_label` foram escritos a mao em
  `rumor_seed_overrides.json` (o gerado sozinho produziria o titulo cru); `public_names` so
  `Valerius` nas duas sementes que o citam. `entities` do gerador vem de tags + corpo do texto.
- **D-9 default `RPG_RUMORS=on`** (D3 local/suite). O staging deve fixar `RPG_RUMORS=shadow`.
- **D-10 nao feito aqui:** passo 2 da Etapa 0 (`project_index`, gerado no pouso), relock do eval
  `npc_knowledge`, smoke real §6, revisao independente e a leitura do dono (D1).

## 9. Decisões do dono

### Registradas (2026-10-24)

1. **Frequência** (definida pelo coordenador, aprovada): cada região frequentada tem 50 % de
   chance por dia de jogo de gerar 1 rumor; o jogador percebe no máximo 1 rumor novo por dia;
   TTL de 10 dias em `world.news`; ~25 % dos rumores são falsos. Tudo `[BALANCEAR]`, calibrado
   pelo simulador offline (Etapa 7).
2. **Boato falso pode gerar quest** (`investigar_rumor`, SPEC-313; interface §3.6).

### Abertas (o executor segue o recomendado se o dono não disser nada)

- **D1 — Revisão da tabela.** O dono lê `rumor_seed_overrides.json`: `truth` das 40 sementes
  (default baixa → falso, alta/média → verdadeiro), `public_names` (quem o povo conhece pelo
  nome; recomendado: só governantes — Valerius, Lady Aerwen) e `quest_eligible`. Recomendado:
  bloqueia só `RPG_RUMORS=on` no staging (como D8 da 297).
- **D2 — "Região frequentada"** = região onde o herói esteve nos últimos 14 dias. Recomendado:
  **14** `[BALANCEAR]`.
- **D3 — Defaults das flags.** Recomendado: `RPG_RUMORS=on` local e na suíte (segue o motor),
  `shadow` no staging até o smoke §6, depois `on`; `RPG_RUMORS_PROPOSED=off` até o smoke §6.3.
- **D4 — Rumor do narrador** é sempre falso e não gera quest. Recomendado: **sim** (a LLM não
  cria fato nem gancho com verdade).
- **D5 — "Eco distorcido"** (boato falso derivado de crise real, ex.: febre no lugar errado).
  Recomendado: **fora do v1** (confunde a leitura da crise da 305 antes de medir o v1).
- **D6 — Teto por ação = 1** (descanso longo traz 1 rumor, não N). Recomendado: **1**
  `[BALANCEAR]`.
