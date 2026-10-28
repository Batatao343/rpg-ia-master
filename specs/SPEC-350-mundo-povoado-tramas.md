# SPEC-350 — Mundo povoado por tramas: NPCs nomeados com papel concreto, por região, em ondas

> **Status:** `approved`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Origem:** pedido do dono (27/10): "o mundo tem poucos NPCs nomeados ligados às tramas; os NPCs
> gerados na abertura não levam a nenhuma história". Decisão do dono: **antes** de mudar a abertura
> (SPEC-351), povoar o mundo com NPCs nomeados por região, cada um com papel concreto numa trama
> (facção, segredo, rumor, quest de lore), começando por Nova Arcádia. O jogador começa na **borda**
> da trama (nada de escolhido).
> **Depende de:** SPEC-348 (`approved`; precisa estar `done`: cria Ilsa, Bertil, Sennar, Benedita e os
> outros mestres das Posturas, as arestas de Mãe Corva/Morvan, os rumores novos e o `lore_reanchor.py`;
> desloca linhas de `lore_nova/`), SPEC-310 (`done`: `services/npc_self.py`), SPEC-304 (`done`:
> `npc_world`, roster e agendas), SPEC-297 (`done`: pool compartilhado), SPEC-312/313 (`done`: rumores com
> semente, quests de lore), SPEC-215 (`done`: conhecimento por NPC), SPEC-340 (`done`: registro de flags).
> **Desbloqueia:** SPEC-351 (abertura amarrada a uma trama: consome `plot_doors`, §3.4); as ondas 2+
> (demais regiões) pelo mesmo processo (§3.9).
> **EXECUTOR_MODEL:** `Opus` (autoria em voz de crônica + curadoria de visibilidade; Sonnet só nas etapas
> mecânicas 1, 2 e 5) · **REVIEW_MODEL:** `Opus` (subagente `spec-reviewer` que não escreveu o conteúdo) ·
> **REVIEW_REQUIRED:** `true` (conteúdo canônico novo, segredo em doc oculto, mexe no prompt do NPC e no
> roster da 304) · **EVAL_AUTHORING_REQUIRED:** `false` (não toca `evals/`).

---

## 1. Contexto & Objetivo

Valoria tem muita gente com nome, mas quase ninguém com **papel jogável**. `lore_nova/npcs.txt` já lista
~140 NPCs em 12 seções regionais (Nova Arcádia tem 16 na seção própria, `npcs.txt:1264-1509`, mais os 5
"principais" citados em `:1266`), e o Codex tem 36 NPCs "mundo vivo" curados. O problema não é a
contagem: é que **nada no motor sabe em que história cada um está**. O texto de lore é prosa livre
("Para o narrador: …"), sem desejo, medo e segredo estruturados; os 36 curados do mundo vivo carregam a
mesma frase-modelo; e a abertura (`services/prologue.py`) manda a LLM **inventar** de 0 a 2 NPCs
pessoais, "não à trama global do mundo". Esses NPCs nascem sem id, sem facção e sem motivação, e por
isso não levam a lugar nenhum.

Esta spec cria a **camada de trama** do mundo: um catálogo curado (`data/world/plot_threads.json`) que
diz, por região, quais tramas estão ativas, quem está no núcleo de cada uma, quem está na **borda** (gente
pequena, alcançável no primeiro turno), e quais **portas** o jogador pode atravessar para entrar nela.
Cada NPC da trama tem uma ficha curta e única (desejo, medo, assunto que evita, voz) que o motor injeta
no prompt do NPC em Python, sem chamada LLM nova. NPCs novos são escritos só onde a trama precisa de uma
borda que ainda não existe: gente comum com um pé na história (a copista demitida, o contador de fichas
da fundição, o cabo que confisca papéis sem saber o quê). Ninguém é escolhido; todo mundo deve, viu,
carrega ou foi contratado.

A **onda 1** entrega o mecanismo e **Nova Arcádia completa**. As outras 11 regiões entram em ondas pelo
mesmo processo (mapa aprovado → autoria → lint → revisão → reindex → smoke), cada uma em spec própria
(D4). A SPEC-351 consome a interface `plot_doors(region_id)` para amarrar a abertura a uma porta de
trama; esta spec **não** muda a abertura.

Princípios: mecânica e seleção em Python, LLM só narra (AGENTS.md § Convenções); regra de ouro do NPC (ele
sabe o que viveu; segredo só como "assunto que evita", SPEC-310 R1); lore como fonte e curadoria
migration-safe (`docs/guias/AUTORIA.md:3-9`); tom de Valoria (`docs/lore/revisao-2026-10-27.md` §2:
custo, entropia, **instituições-armadilha**, crônica cansada com inversão seca, segredos como inversão,
léxico de `data/cards/_lexico_valoria.txt`); unicidade "como nas cartas" (SPEC-336 R3: assinatura +
similaridade, nada de reskin).

### 1.1 Problemas com evidência

Linhas de `lore_nova/` citadas são **anteriores à SPEC-348**; a Etapa 0 reaponta com
`scripts/lore_reanchor.py` (criado pela 348).

| # | Problema | Evidência |
|---|---|---|
| P1 | A abertura manda a LLM inventar NPCs pessoais, explicitamente fora da trama do mundo, e proíbe citar nomeados da lore | `services/prologue.py:186-189` ("beats são PESSOAIS … não à trama global"; "NPCs (0 a 2) são NOVOS … não cite personagens nomeados"); `:50-52` (`seed_npcs` 0–2) |
| P2 | O NPC da abertura entra no estado sem `id`, facção nem motivos; `npc_self` não tem o que dizer dele | `services/prologue.py:243-260` (só `name/role/persona/relationship`); `services/npc_self.py:349-352` (`motive_lines` lê só `seed_motives`) |
| P3 | O motor não tem conceito de trama: nenhum dado nem serviço liga NPC → história | Grep `trama|plot_thread|story_thread` em `services/`, `agents/`, `data/world/`: única ocorrência é a proibição de `prologue.py:186` |
| P4 | NPC canônico da lore não tem desejo/medo/segredo estruturados: só prosa "Papel/Personalidade/O que sabe/Para o narrador" | `lore_nova/npcs.txt:1441-1449` (Velha Netta), `:1501-1509` (Tibb), `:1273-1281` (Thrace) |
| P5 | Motivação só existe para NPC **gerado** com semente; o canônico chega ao prompt sem `<MOTIVACOES_INTERNAS>` | `services/npc_self.py:349-370`; `services/npc_seed.py:33-43` (campos da semente) |
| P6 | Os 36 NPCs "mundo vivo" (canônicos de 2ª camada, G-15) têm a mesma frase-modelo de traços; papel e gancho de uma linha, sem segredo nem voz | Frase "fala por imagens concretas, deseja algo verificável…" em **36 de 36** arquivos de `data/codex/npcs/mundo_vivo/` (ex.: `npc_mv_mara_do_setimo_sino.md:28`); só 3 deles moram em Nova Arcádia (Irena, Mara, Teo: `home_location_id: nova_arcadia`) |
| P7 | Segredo de NPC em doc oculto existe para só 14 NPCs; em Nova Arcádia, 4 (Grum, Magda, Valerius, Vane) | `data/codex/npcs/segredos/` (14 arquivos) |
| P8 | No grafo, a maioria dos NPCs de Nova Arcádia não tem aresta: Vespério, Oswin, Vesperina, Lírio, Netta, Liane, Tibb, Sylvenne, O Corretor, Vane | `data/graph/edges.json:1-155` (só Valerius, Thrace, Magda, Kald, Bors, Pardal, Korvus, Grum, O Cego, Malagor) |
| P9 | Roster da simulação off-screen tem teto 60; 21 líderes + 36 `key_npcs` já ocupam 57. NPC novo de trama posto em `key_npcs` cai fora do teto (congelado) | `data/world/npc_world.json:4` (`ROSTER_CAP: 60`), `:109-146` (36 `key_npcs`); `services/npc_world.py:102-109` (21 líderes), `:282-301` (ordem: party > queridos > líderes > conhecidos > chave) |
| P10 | Agenda só para 33 NPCs; o resto cai em radical de papel ou `sedentario` | `data/world/npc_world.json:74-108`; `services/npc_world.py:222-232` |
| P11 | O NPC canônico que entra em cena é gerado por LLM a partir do RAG; a persona não fica presa à lore (nem ao papel na trama) | `agents/npc.py:535-559` (`query_rag` + `NPCSchema`); `agents/storyteller.py:698-709` |
| P12 | Mundo compartilhado (Termos item 8): NPC gerado e aprovado vai ao pool e aparece para outros jogadores, sem nenhum vínculo de trama; a avaliação checa só coerência de região | `web/legal/terms.md:17`; `services/shared_pool.py:1-14`, `:380-389` (`_EVAL_SYSTEM`), `:683-718` (`cast_entries` por região); `services/shared_pool_models.py:38-54` (allowlist sem campo de trama) |
| P13 | O guia de autoria manda copiar um template de NPC que não existe | `docs/guias/AUTORIA.md:23` (`docs/templates/codex/`); Glob `docs/templates/**` → só `carta.json` e `handoff-review.md` |

O que **já** protege e será reaproveitado: `shared_pool_validators.curated_names` lê `entities.json` +
`entities_extra.json` e rejeita entrada do pool com nome de entidade curada
(`services/shared_pool_validators.py:335-365`), então registrar os NPCs novos em `entities_extra.json`
impede que o pool crie um sósia deles.

## 2. Requisitos

Notação: **núcleo** = NPC de poder da trama (líder, patrão, vilão), em geral já existente; **ponte** = NPC
intermediário com acesso ao núcleo; **borda** = gente pequena, alcançável no 1º turno, com um pé na
trama. **Porta** = um jeito concreto e mundano de o jogador entrar na trama por um NPC de borda/ponte.

### 2.1 Catálogo de tramas (dados)

- **R1 — Arquivo único curado.** `data/world/plot_threads.json` com `version`, `threads`, `cast`,
  `waves` e `excluded` (§3.3). Não é gerado; o migrate não toca. Carregado só por
  `services/plot_threads.py`.
- **R2 — Trama.** Cada trama tem `id` (`tr_<regiao>_<slug>`), `region_id` (de `data/origins.json`),
  `title`, `pergunta` (a questão em aberto que o jogador pode decidir, ≤ 160 caracteres), `resumo_publico`
  (≤ 300, sem segredo), `core` (≥ 2 ids de NPC), `borda` (≥ 2), `portas` (≥ 3), `factions` (≥ 1),
  `locations` (≥ 1), `rumor_ids` (≥ 1, de `data/world/rumor_seeds.json`), `secret_ids` (pode ser vazio),
  `lore_refs` (≥ 1, `"lore_nova/<arq>:<a>-<b>"`) + `lore_keyword`, `postura_afinidade` (0–2 chaves de
  `data/classes.json`) e `inspiracoes` (opcional; R27).
- **R3 — Três portas por trama.** Toda trama tem **≥ 3 portas** com âncoras **distintas** e, entre elas,
  ≥ 2 `location_id` distintos (regra das três pistas, R27): se o jogador perder uma porta, há outra.
- **R4 — Porta.** Cada porta tem `id` (`<thread_id>__p<n>`), `anchor_npc_id`, `location_id` (de
  `data/world_map.json`), `link_kind` ∈ {`divida`, `emprego`, `testemunha`, `vizinhanca`, `encomenda`,
  `achado`}, `hook_public` (1–2 frases, ≤ 220 caracteres, em 3ª pessoa, sem segredo), `rumor_ids`
  (opcional) e `quest_hint` (opcional, só tipos e âncoras **existentes** da SPEC-313: `investigar_rumor`
  com `rumor_id`, `entregar_material` com `route_id` de `lore_quests.json`, `escoltar` com o próprio
  âncora itinerante).
- **R5 — Âncora de porta é borda ou ponte, nunca núcleo.** `anchor_npc_id` tem `tier ∈ {borda, ponte}`
  no `cast`, não é líder (`npc_world.leaders()`, aresta `leads`) e não tem `secret_ids` próprios que a
  porta exija conhecer. Teste: nenhuma porta aponta para id de `leaders()`.
- **R6 — Nada de escolhido.** `hook_public`, `pergunta` e `resumo_publico` não contêm (sem acento,
  minúsculas) `escolhid`, `profeci`, `predestin`, `destinad`, `sangue real`, `herdeir`, `unico que pode`,
  `so voce`, `marcado pelo destino`, nem se dirigem ao jogador ("você"). A porta descreve o mundo, não o
  herói.
- **R7 — Ficha de elenco (`cast`).** Uma por NPC que participa de trama, chave = id canônico do grafo:
  `tier`, `threads` (≥ 1 `{thread_id, papel}`; `papel` público ≤ 120 caracteres), `desejo` (≤ 90),
  `medo` (≤ 90), `segredo_topico` (≤ 60, forma de "assunto que evita", nunca o fato), `segredo_doc_id`
  (doc oculto que guarda o fato; obrigatório para NPC novo e para `tier: borda`), `voz` (`registro` ≤ 60 +
  `fala` exemplo ≤ 120), `home_location_id`, `archetype` (chave de `npc_agendas.json`) e `fonte`
  (`lore_ref` arquivo:linha para NPC da lore, ou `"spec350"` para NPC novo).
- **R8 — Cobertura de região concluída.** Para toda região com `waves[...].status == "done"`: ≥ 5 tramas
  (Nova Arcádia) ou ≥ 3 (demais); cada NPC nomeado da seção regional de `npcs.txt` e cada NPC mundo vivo
  com `home_location_id` na região está no `cast` **ou** em `excluded` com motivo (ex.: demônio, morto,
  contido, inalcançável); cada NPC novo está em ≥ 1 trama.

### 2.2 Onda 1 — Nova Arcádia

- **R9 — Mapa de tramas.** As 6 tramas de §3.6 entram no catálogo com núcleo, borda, portas e ganchos
  daquela tabela (texto final pode ser lapidado; ids, membros e número de portas, não, sem nova aprovação
  do dono).
- **R10 — Doze NPCs novos.** Os 12 de §3.7 (nomes `*` sujeitos a D2), cada um com: doc público curado
  `data/codex/npcs/tramas/<id>.md` (`curated: true`, `visibility: public`), doc oculto
  `data/codex/npcs/segredos/<id>_segredo.md` (`type: npc_secret`, `visibility: hidden`, padrão
  `AUTORIA.md:27-29`), entrada em `data/graph/entities_extra.json`, aresta `located_in` (pública) e
  `member_of` quando houver (visibilidade conforme o segredo), `agenda_by_npc` em
  `data/world/npc_world.json` e ficha em `cast`. Nenhum vai a `lore_nova/` (D9).
- **R11 — Rute sai do cotidiano e vira NPC.** "Rute, Corvo Veterana" (`lore_nova/daily_life.txt:146-151`)
  ganha doc curado e ficha; o texto de `daily_life.txt` não muda. Conta entre os 12 de R10.
- **R12 — Mundo vivo de Nova Arcádia promovido.** Irena Prego-Frio, Mara do Sétimo Sino e Teo Chaminé
  entram em tramas (§3.6) e seus docs curados trocam a frase-modelo (P6) por papel, desejo público e voz
  coerentes com a ficha; ganham doc de segredo. Os outros 33 mundo vivo ficam como estão até a onda da
  região deles.
- **R13 — Canônicos da lore entram por ficha, sem reescrever a lore.** Cada NPC da seção Nova Arcádia
  (`npcs.txt:1264-1509`) e os principais citados em `:1266` estão no `cast` ou em `excluded` (Elaryin:
  morto; Malagor: contido; Fehk: demônio, fora do elenco jogável). A ficha é **derivada** do texto da
  lore (`fonte` aponta a linha) e não contradiz nada dele (revisão R18 confere). Docs gerados não são
  editados; arestas que faltam (P8) entram em `edges.json`.
- **R14 — Sem duplicar a 348.** Ilsa, Bertil, Sennar, Benedita e Mãe Corva usam o id e o texto que a
  SPEC-348 criou; esta spec só acrescenta a ficha em `cast` e a participação na trama. Fato oculto da 348
  (herdeiro, servo que sobrou, cicatriz da Legião) nunca aparece em campo público desta spec (R16).

### 2.3 Gate de qualidade

- **R15 — Lint `validate_plot_threads`.** Em `services/content_validator.py`, chamado por `validate_all`
  (logo coberto por `tests/test_fase71.py::test_repo_content_sem_erros` e pelo gate do `rag.py`). ERRO
  para: id de NPC/local/facção/rumor/rota/segredo inexistente; contagens de R2–R4/R8; comprimento de
  R2/R4/R7; R5; R6; termo `[proibido]` de `data/cards/_lexico_valoria.txt` em qualquer texto; `lore_refs`
  fora do arquivo ou sem `lore_keyword` no intervalo (leitura só do intervalo, `itertools.islice`, como
  SPEC-313 R2); `archetype` inexistente; `segredo_doc_id` inexistente ou não oculto.
- **R16 — Sem vazamento.** Nenhum campo público (`resumo_publico`, `pergunta`, `hook_public`, `papel`,
  `desejo`, `medo`, `voz`, `segredo_topico`) nem o corpo dos docs públicos novos contém: (a) termo de
  `services/secret_signatures.SECRET_SIGNATURES` dos `secret_ids` da trama; (b) as frases de
  `LEAK_PHRASES` da SPEC-348 (`tests/test_spec348_leaks.py`); (c) palavra ≥ 5 letras exclusiva do doc de
  segredo do próprio NPC que não apareça no doc público dele (lista de exceções curta no próprio teste).
- **R17 — Unicidade (nada de reskin).** (a) Nome dobrado (`shared_pool_models.fold_name`) e aliases de
  NPC novo não colidem com nenhum nome/alias de `entities.json`, `entities_extra.json`, `bestiary.json`
  nem `artifacts.json`. (b) **Assinatura** `(radical do papel, link_kind principal, thread_id, tier)`
  única no `cast`. (c) Jaccard lexical de `desejo + medo + segredo_topico + voz.fala` entre quaisquer
  duas fichas < 0,35 (limiar `[BALANCEAR]`; opção de embedding como SPEC-336). (d) Dentro de uma mesma
  região, nenhum par de NPCs novos com o mesmo radical de papel (ex.: dois "mensageiros", dois
  "cobradores"). Duplicata provável = ERRO com o par apontado.
- **R18 — Revisão independente com rubrica.** Um subagente `spec-reviewer` (Opus) que não escreveu o
  conteúdo lê os 12 docs novos, os 3 promovidos e todas as fichas de Nova Arcádia contra a rubrica de §3.8
  e grava `handoffs/SPEC-350-review.md` com veredito por NPC (`aprovado` / `refazer` + motivo) e por
  trama. Qualquer `refazer` bloqueia o `done` até nova rodada.
- **R19 — Aprovação do mapa antes do texto.** O mapa de tramas (§3.6) e a lista de nomes (§3.7) são
  aprovados pelo dono antes da autoria dos docs (Etapa 3). Nomes trocados pelo dono entram sem nova
  revisão de spec.

### 2.4 Motor: consumo mínimo e interface para a 351

- **R20 — Serviço puro.** `services/plot_threads.py` (§3.4): carrega e valida o catálogo uma vez
  (`lru_cache`), sem LLM, rede, RAG nem escrita. Arquivo ausente ou inválido → catálogo vazio +
  `log_event("plot", "catalog_invalid")`; nunca levanta para o jogo.
- **R21 — Resolver a ficha de uma linha de runtime.** `sheet_for_row(state, npc_key, row)` acha a ficha
  por, em ordem: `row["id"]`, `npc_world.npc_ref`, e nome dobrado contra `name` + `aliases` do grafo das
  entidades do `cast`. Teste com o NPC entrando como "Bors" e como "Velha Netta" (ids gerados por nome em
  `agents/npc.py:563` divergem do id canônico).
- **R22 — Motivos do NPC canônico.** `npc_self.motive_lines` passa a usar a ficha quando a linha não tem
  `seed_motives`: "Você deseja: …", "Você teme: …", "Seu jeito: <registro>. Fala assim: «<fala>»", e "Há
  um assunto que você evita: <segredo_topico>…" (mesmo texto de `npc_self.py:366-369`). Com
  `seed_motives`, nada muda. Orçamentos de `npc_self.py:26-30` não mudam (teste de teto com a ficha mais
  longa do catálogo).
- **R23 — Papel na trama em `<SOBRE_VOCE>`.** Uma linha "O que está em jogo para você: <papel>"
  (primeira trama do NPC) logo depois das linhas de identidade (`npc_self.py:421`), sujeita ao corte de
  `_fit`. Nada de outra trama, de outro NPC nem de `pergunta` entra no prompt do NPC.
- **R24 — Roster prioriza a trama da região atual.** Em `npc_world._candidates` (`npc_world.py:269-302`),
  os NPCs do `cast` cujas tramas são da região do local atual do jogador entram **depois** dos conhecidos
  e **antes** de `key_npcs`, em ordem de id. `ROSTER_CAP` não muda (D8). Teste: jogador em
  `na_anel_lama` → todas as âncoras de Nova Arcádia no roster; os `key_npcs` de outras regiões que caem
  fora são congelados (comportamento da 304, `npc_world.py:316-319`).
- **R25 — Interface para a SPEC-351.** `plot_doors(region_id, *, state=None, postura=None)` devolve as
  portas da região em ordem determinística (afinidade de Postura primeiro, depois `id`). Com `state`,
  exclui porta cujo âncora está morto, capturado, desertou ou está fora da região
  (`npc_world._is_dead`, `presence`, `npc_layers.npc_alive`). `cast_npc_row(npc_id, *, game_id,
  home_location_id)` monta a ficha de runtime determinística (sem LLM) para a 351 semear o NPC da porta.
  `public_thread_brief(thread_id)` devolve `title` + `resumo_publico` + `pergunta` para o prompt da
  abertura. Nenhuma dessas funções devolve `segredo_*`, `secret_ids` nem `core` com segredo.
- **R26 — Sem LLM nova, sem estado novo, sem API nova.** Nenhuma chamada LLM adicional (teste conta
  invokes do MockLLM num turno de `npc_actor` com e sem a ficha). `GameState` não ganha campo; save antigo
  carrega igual. `/game/state` e `visible_npc_view` (`services/npc_layers.py:251`) não expõem nenhum
  campo da ficha (teste varre o payload pelos textos de `desejo/medo/segredo_topico`).
- **R27 — Inspiração externa só com fonte.** Ideia vinda de fora entra em `inspiracoes`
  (`{fonte, url, o_que_inspirou}`), nunca como nome, frase ou personagem copiado. Inspirações da onda 1
  em §3.10.
- **R28 — Flag.** `RPG_PLOT_THREADS=off|on` registrada em `config/flags.yaml` (`kind: release`,
  `spec: SPEC-350`, validade pela regra da SPEC-340). `off`: R22–R24 e `plot_doors` desligados (prompt e
  roster byte a byte iguais a hoje; teste com spy). O lint (R15–R17) roda sempre. Default: D6.

### 2.5 Processo de onda

- **R29 — Fluxo E em `AUTORIA.md`.** Seção "Trama de região" com o roteiro de §3.9, o formato do doc
  público e do doc de segredo, e o template que P13 diz faltar (criado em
  `docs/templates/codex/npc_trama.md`, corrigindo `AUTORIA.md:23`).
- **R30 — Cobertura por onda é teste.** `test_region_coverage` é parametrizado por `waves`: região
  `done` precisa cumprir R8; região `pending` é pulada. Fechar uma onda = mudar o status e passar o teste.

### Fora de escopo

- **Mudar a abertura** (`services/prologue.py`, `/game/prologue`, `/game/new`): SPEC-351.
- Regiões 2–12: cada onda em spec própria (D4) com o processo de R29; aqui só a estrutura `waves` e a
  ordem recomendada (§3.5).
- Escalada mecânica de trama (relógio, presságio, diretor que avança a trama sozinho), fim de trama,
  consequência de escolha. A `pergunta` é texto; quem a responde é o jogo de hoje (quests 313, fações 301,
  rumores 312, mundo vivo 304).
- Rumores novos em `lore_nova/rumors.txt`, rotas novas em `lore_quests.json`, tipos novos de quest: as
  portas só citam o que já existe (a 348 está mexendo nesses arquivos; D11).
- Trama no diário/dossiê do jogador (`services/dossiers.py`), na UI ou na API.
- NPC do pool compartilhado ganhar trama automaticamente; pool continua figurante (D7). Mudança na
  avaliação do pool.
- Conhecimento inicial do NPC sobre a trama no ledger da 215 (`npc_knowledge`).
- Reescrever texto da lore de NPCs existentes, renomear nó do mapa (`na_taverna_javali` → Dragão Bêbado
  é da spec do mapa, C-12), arte dos NPCs novos.
- `ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml`, `project_index/` (coordenador).

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `data/world/plot_threads.json` | Catálogo curado (R1–R8): tramas, portas, elenco, ondas, exclusões |
| `services/plot_threads.py` | Loader + validação estrutural + API pura (§3.4) |
| `data/codex/npcs/tramas/npc_tr_*.md` | 12 docs públicos curados dos NPCs novos (R10, R11) |
| `data/codex/npcs/segredos/npc_tr_*_segredo.md` | 12 docs ocultos + 3 dos mundo vivo promovidos (R10, R12) |
| `docs/templates/codex/npc_trama.md` | Template do doc público + do doc de segredo (R29, P13) |
| `tests/test_spec350_catalog.py` | R1–R8, R30 (estrutura, ids, contagens, cobertura) |
| `tests/test_spec350_lint.py` | R6, R15–R17 (lint com fixtures sintéticas boas e ruins) |
| `tests/test_spec350_api.py` | R20, R21, R25, R26 (API pura, filtros de estado, nada de segredo) |
| `tests/test_spec350_npc_prompt.py` | R22, R23, R26, R28 (blocos do `npc_self`, orçamento, flag off) |
| `tests/test_spec350_roster.py` | R24, R28 (ordem do roster, teto, congelamento) |
| `handoffs/SPEC-350-review.md` | Revisão independente (R18) |

### 3.2 Arquivos alterados

| Arquivo | O que muda |
|---|---|
| `services/content_validator.py` | `validate_plot_threads()` + chamada em `validate_all` (R15–R17) |
| `services/npc_self.py` | `motive_lines(row, sheet=None)`; linha de trama em `npc_self_blocks` (R22, R23), atrás da flag |
| `services/npc_world.py` | `_candidates` com o bloco de elenco da região atual (R24), atrás da flag |
| `data/world/npc_world.json` | `agenda_by_npc` para os 12 novos e para os canônicos de Nova Arcádia sem agenda (P10) |
| `data/graph/entities_extra.json` | 12 entidades novas (R10) |
| `data/graph/edges.json` | `located_in`/`member_of` dos novos e dos canônicos sem aresta (P8); nenhuma `leads` nova |
| `data/codex/npcs/mundo_vivo/npc_mv_{irena_prego_frio,mara_do_setimo_sino,teo_chamine}.md` | Corpo reescrito (R12); frontmatter mantém `id`, ganha `related_entities` da trama |
| `config/flags.yaml` | `RPG_PLOT_THREADS` (R28) |
| `docs/guias/AUTORIA.md` | Fluxo E (R29); linha 23 aponta o template certo |

### 3.3 Schemas

```python
# services/plot_threads.py  (Pydantic v2, só leitura)
LinkKind = Literal["divida", "emprego", "testemunha", "vizinhanca", "encomenda", "achado"]
Tier = Literal["nucleo", "ponte", "borda"]

class QuestHint(BaseModel):
    kind: Literal["investigar_rumor", "entregar_material", "escoltar"]
    anchor_id: str  # rumor_id | route_id | npc_id (o próprio âncora)

class PlotDoor(BaseModel, frozen=True):
    id: str                      # "tr_na_corpos_marcados__p1"
    anchor_npc_id: str
    location_id: str
    link_kind: LinkKind
    hook_public: str             # <= 220
    rumor_ids: tuple[str, ...] = ()
    quest_hint: QuestHint | None = None

class InspirationRef(BaseModel):
    fonte: str
    url: str
    o_que_inspirou: str

class PlotThread(BaseModel, frozen=True):
    id: str                      # "tr_na_corpos_marcados"
    region_id: str
    title: str
    pergunta: str                # <= 160
    resumo_publico: str          # <= 300
    core: tuple[str, ...]        # >= 2
    borda: tuple[str, ...]       # >= 2
    portas: tuple[PlotDoor, ...] # >= 3
    factions: tuple[str, ...]
    locations: tuple[str, ...]
    rumor_ids: tuple[str, ...]
    secret_ids: tuple[str, ...] = ()
    lore_refs: tuple[str, ...]
    lore_keyword: str
    postura_afinidade: tuple[str, ...] = ()
    inspiracoes: tuple[InspirationRef, ...] = ()

class ThreadRole(BaseModel):
    thread_id: str
    papel: str                   # <= 120, público

class Voice(BaseModel):
    registro: str                # <= 60
    fala: str                    # <= 120

class CastSheet(BaseModel, frozen=True):
    npc_id: str
    tier: Tier
    threads: tuple[ThreadRole, ...]
    desejo: str                  # <= 90
    medo: str                    # <= 90
    segredo_topico: str          # <= 60
    segredo_doc_id: str = ""     # obrigatório p/ borda e p/ fonte == "spec350"
    voz: Voice
    home_location_id: str
    archetype: str
    fonte: str                   # "lore_nova/npcs.txt:1441-1449" | "spec350"

class Wave(BaseModel):
    order: int
    regions: tuple[str, ...]
    status: Literal["pending", "in_progress", "done"]
    spec: str = ""               # "SPEC-350" | id da spec da onda

class PlotCatalog(BaseModel):
    version: int = 1
    threads: tuple[PlotThread, ...] = ()
    cast: dict[str, CastSheet] = {}
    waves: tuple[Wave, ...] = ()
    excluded: dict[str, str] = {}   # npc_id -> motivo
```

### 3.4 Assinaturas públicas

```python
# services/plot_threads.py
def mode() -> Literal["off", "on"]                      # RPG_PLOT_THREADS
def catalog() -> PlotCatalog                             # lru_cache; inválido -> vazio + log
def threads_for_region(region_id: str) -> list[PlotThread]
def thread(thread_id: str) -> PlotThread | None
def cast_sheet(npc_id: str) -> CastSheet | None
def sheet_for_row(state: dict, npc_key: str, row: dict) -> CastSheet | None      # R21
def region_cast(region_id: str) -> list[str]                                      # R24, ordem por id
def plot_doors(region_id: str, *, state: dict | None = None,
               postura: str | None = None) -> list[PlotDoor]                      # R25
def cast_npc_row(npc_id: str, *, game_id: str, home_location_id: str = "") -> dict  # R25
def public_thread_brief(thread_id: str) -> str                                    # R25
def stake_line(sheet: CastSheet) -> str        # "O que está em jogo para você: <papel>" (R23)

# services/npc_self.py (mudança)
def motive_lines(row: dict, sheet: "CastSheet | None" = None) -> list[str]        # R22

# services/content_validator.py
def validate_plot_threads(path: str | None = None) -> list[Finding]               # R15–R17
def plot_signature(sheet: CastSheet, thread_index: dict) -> tuple                  # R17b
```

`cast_npc_row` copia só: `id`, `name` (do grafo), `role` (= `papel` da 1ª trama), `faction_id` (de
`npc_world.npc_faction` sem estado), `home_location_id`, `plot_sheet_id` e os atributos neutros que
`prologue.scenario_to_state_seed` já usa (`prologue.py:245-255`), e passa por
`npc_layers.ensure_npc_fields` (traços sorteados pelo `game_id`). Persona vem do doc público do Codex
(primeiro parágrafo, ≤ 400 caracteres), nunca do doc de segredo.

### 3.5 Recomendação por região (ondas)

Contagem atual = blocos `[CATEGORIA: NPC]` da seção regional de `npcs.txt` (linhas pré-348) + mundo vivo
com `home_location_id` na região. "Novos" = recomendação de NPCs de borda a escrever (2 por trama, menos
os que a lore/348 já oferecem). A Etapa 0 de cada onda confere.

| Onda | Região (`origins.json`) | Seção em `npcs.txt` | Hoje (lore + mv) | Tramas | Novos (rec.) |
|---|---|---|---|---|---|
| 1 | `nova_arcadia` | `:1264-1509` + principais `:1266` | 16 + 5 + 3 (+4 da 348) | 6 | **12** |
| 2 | `pantano_melancolia` | `:1106-1262` | 10 + 3 (+Hask) | 3–4 | 6 |
| 2 | `brekmar` | `:1877-2182` | 20 + 3 (+Oriel) | 4 | 6 |
| 3 | `skallgard` | `:473-777` | 20 + 3 (+Hrefna) | 4 | 6 |
| 3 | `pradaria_ruinas` | `:944-1105` | 10 + 3 (+Morvan grafo) | 3–4 | 6–8 |
| 4 | `montanhas_afiadas` | `:778-943` | 10 + 3 | 3 | 6 |
| 4 | `aethelgard` | `:1796-1876` | 5 + 3 (+Mairen) | 3 | 6–8 |
| 5 | `floresta_sussurros` | `:1512-1605` | 6 + 3 | 3 | 6–8 |
| 5 | `selva_xylos` | `:1606-1701` | 6 + 3 | 3 | 6–8 |
| 6 | `deserto_zhur` | `:1702-1795` | 6 + 3 | 3 | 6–8 |
| 6 | `costa_negra` | `:2183-2232` (Cemitério de Leviatãs) | 3 + 3 | 3 | 8 |
| 7 | `ophidia` | `:2233-…` | 2 + 3 | 2 (só de borda: "quem jura que veio") | 4 |

Total recomendado: ~90 NPCs novos em 7 ondas, **≤ 12 por onda** (qualidade > volume; a revisão R18 lê
tudo). Ordem: regiões de início mais escolhidas e com mais quests/rumores primeiro (D5).

### 3.6 Onda 1 — mapa de tramas de Nova Arcádia

`*` = NPC novo desta spec (§3.7). `(348)` = criado pela SPEC-348. Âncoras de porta em **negrito**.
Linhas de lore pré-348.

| Trama (`id`) | Pergunta | Núcleo | Borda / ponte | Portas (âncora · local · ligação · gancho público) | Facções · rumores · segredos | Lore |
|---|---|---|---|---|---|---|
| **O documento que a Legião procura** (`tr_na_documento_da_legiao`) | Proteger uma pessoa que não sabe quem é custa destruir o único papel que prova quem ela é? | `npc_grum`, `npc_velha_magda`, `npc_comandante_thrace` | Ilsa (348), Dalva Torneira*, Cabo Anselmo Tiza* | p1 **Dalva** · `na_taverna_javali` · emprego · "A ajudante da adega paga uma moeda por noite a quem rolar barris e não perguntar por que a adega já foi revistada duas vezes." · p2 **Anselmo** · `na_anel_lama` · testemunha · "Um cabo da Legião confisca papéis na rua e não sabe dizer o que está procurando." · p3 **Ilsa** · `na_anel_lama` · encomenda · "A remendeira de redes precisa que alguém leve um recado à velha dos espetinhos e traga a resposta sem ler." | `legiao_ferro`, `mao_sombria` · `rumor_grum_guarda_algo_no_barril_de_cerveja_azeda` · testamento (doc `art_testamento_real_no_barril`, oculto pela 348) | `rumors.txt:239`; `factions.txt:30` |
| **O que o Lorde trocou** (`tr_na_o_que_o_lorde_trocou`) | Quanto vale a verdade sobre o Código se o Código é a única coisa que mantém os anéis de pé? | `npc_valerius` (distante), Bertil (348) | Rute*, Tobias Pena-Seca*, `npc_mv_mara_do_setimo_sino` | p1 **Rute** · `na_anel_lama` (crematório do Setor Leste) · emprego · "A Guilda paga por um par de braços na maca; a corvo veterana escolhe quem e não explica as marcas de tiza." · p2 **Tobias** · `na_anel_ferro` · achado · "Um copista demitido vende folhas velhas de rascunho; numa delas a caligrafia não é de ninguém que ele conheça." · p3 **Mara** · `nova_arcadia` · testemunha · "A relojoeira quer alguém acordado na hora em que o sétimo sino toca sozinho." | `guilda_corvos`, `legiao_ferro` · `rumor_as_leis_de_valerius_foram_escritas_em_uma_noite`, `rumor_valerius_conhece_nomes_que_nunca_foram_ditos_a_ele` · `pacto_valerius` | `rumors.txt:194`, `:221`; `daily_life.txt:146` |
| **Os corpos marcados** (`tr_na_corpos_marcados`) | Quem fica com os marcados: o médico que os estuda, a guilda que os vende ou a lama que os esconde? | `npc_doutor_silas_vane`, `npc_mae_corva` | `npc_velha_netta`, Benedita (348), Pio Ferrugem*, Ludovina Agulha* | p1 **Pio** · `na_anel_lama` · vizinhança · "O menino da marca sumiu uma noite e voltou sem sapatos e sem lembrar onde dormiu." · p2 **Ludovina** · `na_anel_ferro` · emprego · "A enfermeira da clínica paga bem a quem levar caixas lacradas antes do amanhecer." · p3 **Netta** · `na_anel_lama` · encomenda · "A curandeira precisa de musgo do Pântano e de alguém que não conte ao Doutor." (`quest_hint`: `entregar_material`/`cha_druidas_anel_lama`) | `guilda_corvos` · `rumor_a_guilda_dos_corvos_nunca_queima_certos_corpos`, `rumor_a_praga_de_ferro_nao_veio_das_minas`, `rumor_o_doutor_esta_costurando_partes_de_monstros_em_humanos` · (corpos → Vane, oculto pela 348) | `rumors.txt:230`, `:104`; `npcs.txt:1441` |
| **O aço que lembra** (`tr_na_aco_que_lembra`) | Uma greve que faz o aço lembrar os mortos é vitória dos operários ou sacramento da seita? | `npc_bors_martelo_partido`, `npc_mestre_fundidor_kald`, `npc_comandante_thrace` | `npc_mv_irena_prego_frio`, `npc_mv_teo_chamine`, Gaspar Fole*, Lalo das Fichas* | p1 **Gaspar** · `na_anel_ferro` · testemunha · "Um foleiro do turno da noite jura que ouviu a mulher morta no chiado do aço." · p2 **Lalo** · `na_anel_ferro` · dívida · "O menino que conta as fichas do turno diz que a conta não fecha: sobram fichas de quem não voltou." · p3 **Irena** · `na_anel_ferro` · encomenda · "A fiscal de rebites procura a remessa oca antes que outra caldeira estoure." · p4 **Teo** · `na_anel_ferro` · encomenda · "O mensageiro dos telhados precisa levar uma lista de presos sem cruzar a patrulha." | `resistencia_operaria_martelos_partidos`, `encapuzados_fornalha`, `legiao_ferro` · `rumor_o_aco_de_sangue_tem_memoria` · (o aço lembra de fato: oculto, 348 E-05) | `rumors.txt:41`; `factions.txt:96`, `:115` |
| **A Lista de Fornalha** (`tr_na_lista_de_fornalha`) | O registro que salva um mago da fogueira é o mesmo que o manda para os Jardins? | `npc_arquimaga_sylvenne`, Sennar (348) | `npc_liane_chama_escondida`, `npc_korvus`, Matias Selo*, Caio Pavio* | p1 **Matias** · `na_anel_ferro` · emprego · "O escrivão dos Inquisidores procura uma testemunha que assine que um nome da lista é de morto." · p2 **Caio** · `na_anel_lama` · testemunha · "O acendedor de lampiões jura que a própria sombra não o segue mais e quer alguém que confirme." · p3 **Liane** · `na_anel_lama` · vizinhança · "Uma vizinha queima as luvas sem querer e pede que ninguém chame a Legião." | `legiao_ferro`, `filhos_chama_azul` · `rumor_os_magos_escravizados_dos_jardins_enlouquecem_sistematicamente` · (Lista de Fornalha, 348 G-10) | `npcs.txt:1486`; `factions.txt:20`; `rumors.txt:122` |
| **A Coleção** (`tr_na_a_colecao`) | Libertar uma "peça" da coleção paga a dívida de quem a vendeu? | `npc_lorde_vesperio_valante`, `npc_lorde_oswin_conta_de_ouro` | `npc_dama_vesperina`, `npc_lirio`, `npc_rato_de_ferro_tibb`, Bento Juros*, Aelis Sem-Ampulheta* | p1 **Bento** · `na_anel_ferro` · dívida · "Um cobrador gentil oferece renegociar a dívida de alguém em troca de um serviço no Anel Dourado." · p2 **Aelis** · `na_anel_dourado` · encomenda · "Uma criada élfica dos saraus pede que alguém compre de volta uma ampulheta penhorada." · p3 **Tibb** · `na_anel_ferro` · emprego · "O contrabandista precisa de mais um par de mãos para atravessar uma caixa que respira." | `mao_sombria` (tráfico), Os Quebrados (348) · `rumor_existem_contratos_que_nunca_vencem`, `rumor_o_preco_da_casa_dos_espelhos_e_literalmente_a_alma` | `npcs.txt:1288`, `:1411`; `rumors.txt:140` |

Afinidade de Postura (sugestão, `postura_afinidade`): Corpos marcados → `Médico de Campo`; Lista de
Fornalha → `Arcanista Cinzento`, `Devoto do Abismo`; Aço que lembra → `Sangromante`; Coleção →
`Corruptor`. As outras sem afinidade.

`excluded` de Nova Arcádia: `npc_elaryin_historico` (morto), `npc_malagor` (contido), `npc_fehk`
(demônio; aparece como pressão em cena, não como elenco), `npc_o_cego` (carcereiro sobrenatural do
Oubliette; núcleo possível de trama futura), `npc_o_corretor` (aparece só em lua nova; idem). A Etapa 0
confere ids e adiciona os de `npcs.txt:1-124` que forem de Nova Arcádia.

### 3.7 Onda 1 — NPCs novos (propostas para D2)

Ficha resumida; o doc público traz papel, aparência (2 frases), como fala e onde encontrar; o doc oculto
traz o segredo como fato. Ids `npc_tr_<slug>` (D3).

| NPC | Papel (borda) | Desejo | Medo | Segredo (vai ao doc oculto) | Voz |
|---|---|---|---|---|---|
| **Dalva Torneira** | ajudante de adega do Dragão Bêbado | pagar a fiança do irmão preso no Oubliette | a taverna fechar e ela voltar ao Fosso | deixa um sargento revistar a adega à noite em troca de notícias do irmão, sem saber o que ele procura | conta tudo nos dedos: "Três barris, duas mentiras e um sargento. Dia calmo." |
| **Cabo Anselmo Tiza** | cabo de patrulha do Anel de Lama | transferência para o Anel Dourado antes do inverno | virar exemplo, como o desertor | não sabe ler; revista papel pelo formato do selo e já deixou passar o que procurava | regulamento pela metade: "Artigo… o artigo diz que é pra entregar. Entrega." |
| **Rute, Corvo Veterana** (de `daily_life.txt:146`) | coletora de corpos da Guilda, crematório do Setor Leste | sair da Guilda antes do décimo segundo ano | ver a tiza vermelha num nome conhecido | sabe que o velho do forno não consta em registro nenhum e o esconde por pena | fala de morto como de tempo: "Hoje vieram sete. Choveu menos." |
| **Tobias Pena-Seca** | copista da corte demitido, vende folhas no Mercado de Carne | o posto e a pensão de volta | esquecer os nomes que copiou | guardou um rascunho do Código numa caligrafia que não era de nenhum copista e vende aos pedaços | cita artigo e parágrafo de tudo, inclusive do jantar |
| **Pio Ferrugem** | menino de recados do Anel de Lama, marcado pela Praga | ver o mar antes de morrer | o doutor que dá pão aos marcados | já foi levado uma noite à clínica e voltou sem lembrar; tem uma costura que não sabe explicar | pergunta tudo duas vezes |
| **Ludovina Agulha** | enfermeira da clínica do Doutor | a carta de mestra assinada | o porão da clínica | carimba "queimado" em fichas de corpos que nunca foram ao forno | educada até o fim da frase: "…não é?" |
| **Gaspar Fole** | foleiro do turno da noite, viúvo | o nome da mulher fora da lista de "acidentes" | ouvir a voz dela no aço | é Encapuzado iniciado e sabota a greve por fé | grita baixo, costume de fornalha |
| **Lalo das Fichas** | menino que conta as fichas de pagamento do turno | quitar a dívida da mãe | a conta não fechar | altera a contagem para pagar às viúvas as fichas dos mortos | conta em voz alta enquanto fala |
| **Matias Selo** | escrivão dos Inquisidores do Código | provar que o registro protege | o Éter que vaza das mãos do irmão | risca nomes da Lista de Fornalha e põe no lugar mortos do crematório | lê nomes como quem reza |
| **Caio Pavio** | acendedor de lampiões do Anel de Lama, ouvinte do pregador | a sombra de volta | a fogueira | denunciou um vizinho mago em troca de óleo de lampião | fala do escuro como de um vizinho |
| **Bento Juros** | cobrador de Oswin no Anel de Ferro | quitar o próprio contrato, que nunca vence | a lista de aquisições do Colecionador | vende devedores sem família à Coleção | gentil, fala de juros como de saúde |
| **Aelis Sem-Ampulheta** | criada élfica dos saraus do Anel Dourado | comprar de volta a ampulheta penhorada | envelhecer dentro da vitrine | carrega páginas do diário em código dos Quebrados costuradas na bainha | fala de si na terceira pessoa: "Aelis serve. Aelis não ouve." |

Cada um toca uma instituição-armadilha (Legião, Guilda, clínica, Fundições, Inquisidores, banco) por
baixo, e cada segredo é uma pequena traição ou um pequeno ato de decência que custa algo: o tom de §1.

### 3.8 Rubrica da revisão (R18)

Por NPC: (1) desejo e medo concretos e verificáveis em cena (não "poder", "vingança" genéricos);
(2) segredo é inversão ou custo, não "é secretamente poderoso"; (3) voz reconhecível numa fala só e
diferente dos outros da região; (4) ligação à trama mundana e na borda (sem destino); (5) coerente com a
lore citada e com a 348; (6) léxico de Valoria, sem `[proibido]`; (7) doc público não entrega o segredo.
Por trama: (a) pergunta sem resposta certa; (b) ≥ 3 portas que funcionam sozinhas; (c) uma
instituição-armadilha no centro; (d) nenhum NPC sobra sem função.

### 3.9 Processo de onda (Fluxo E de `AUTORIA.md`)

1. Etapa 0 da região: ler a seção regional de `npcs.txt` por `Grep` + `Read` com offset; listar
   canônicos, mundo vivo, facções (`factions.json` + grafo), rumores (`rumor_seeds.json` por
   `regions`), rotas de `lore_quests.json`, segredos.
2. Mapa da região (tabela como §3.6) + nomes (§3.7) → aprovação do dono.
3. Autoria: docs curados, segredos, `entities_extra.json`, `edges.json`, `agenda_by_npc`, `cast`,
   tramas e portas.
4. `validate_content.py` com 0 ERRO; `tests/test_spec350_*` do escopo.
5. Revisão independente (§3.8) → `handoffs/SPEC-<NNN>-review.md`.
6. `rag.py` (reindex; gate de lint) e smoke §6 na região.
7. `waves[...].status = "done"`.

### 3.10 Formatos (ids reais)

`data/world/plot_threads.json` (trecho):

```json
{
  "version": 1,
  "waves": [
    {"order": 1, "regions": ["nova_arcadia"], "status": "in_progress", "spec": "SPEC-350"},
    {"order": 2, "regions": ["pantano_melancolia", "brekmar"], "status": "pending"}
  ],
  "threads": [
    {
      "id": "tr_na_corpos_marcados",
      "region_id": "nova_arcadia",
      "title": "Os corpos marcados",
      "pergunta": "Quem fica com os marcados: o médico que os estuda, a guilda que os vende ou a lama que os esconde?",
      "resumo_publico": "No Anel de Lama a Praga marca alguns e não os mata. Os Corvos recolhem os mortos de todo mundo; dizem que certos corpos nunca chegam ao forno.",
      "core": ["npc_doutor_silas_vane", "npc_mae_corva"],
      "borda": ["npc_tr_pio_ferrugem", "npc_tr_ludovina_agulha", "npc_velha_netta"],
      "portas": [
        {"id": "tr_na_corpos_marcados__p3", "anchor_npc_id": "npc_velha_netta",
         "location_id": "na_anel_lama", "link_kind": "encomenda",
         "hook_public": "A curandeira precisa de musgo do Pântano e de alguém que não conte ao Doutor.",
         "quest_hint": {"kind": "entregar_material", "anchor_id": "cha_druidas_anel_lama"}}
      ],
      "factions": ["guilda_corvos"],
      "locations": ["na_anel_lama", "na_anel_ferro"],
      "rumor_ids": ["rumor_a_guilda_dos_corvos_nunca_queima_certos_corpos"],
      "secret_ids": [],
      "lore_refs": ["lore_nova/rumors.txt:230-231"],
      "lore_keyword": "corpos",
      "postura_afinidade": ["Médico de Campo"],
      "inspiracoes": [
        {"fonte": "The Alexandrian — Three Clue Rule",
         "url": "https://thealexandrian.net/wordpress/1118/roleplaying-games/three-clue-rule",
         "o_que_inspirou": "≥ 3 portas por trama (R3)"}
      ]
    }
  ],
  "cast": {
    "npc_velha_netta": {
      "tier": "borda",
      "threads": [{"thread_id": "tr_na_corpos_marcados", "papel": "cura no Anel de Lama quem o Doutor não atende, e vê a Praga que ele finge não ver"}],
      "desejo": "que nenhum marcado do seu beco vá parar na clínica",
      "medo": "o dia em que o Doutor resolver que ela atrapalha",
      "segredo_topico": "o que ela dá aos marcados que não adoecem",
      "segredo_doc_id": "npc_velha_netta_segredo",
      "voz": {"registro": "áspera e prática", "fala": "Senta. Não pergunta. Paga depois, se viver."},
      "home_location_id": "na_anel_lama",
      "archetype": "sedentario",
      "fonte": "lore_nova/npcs.txt:1441-1449"
    }
  },
  "excluded": {"npc_malagor": "contido nas masmorras; não é elenco jogável"}
}
```

Doc público curado (`data/codex/npcs/tramas/npc_tr_rute_corvo_veterana.md`), frontmatter:

```yaml
---
id: npc_tr_rute_corvo_veterana
type: npc
name: Rute
aliases: [Rute, Corvo Veterana]
tags: [nova_arcadia, guilda_corvos, trama]
visibility: public
curated: true
related_entities: [guilda_corvos, na_anel_lama]
home_location_id: na_anel_lama
role: coletora de corpos da Guilda dos Corvos
faction: guilda_corvos
---
```

Arestas (`edges.json`; tipos de `relation_types.json:1-11`):

```json
{"id": "e_tr_rute_em_lama", "source": "npc_tr_rute_corvo_veterana", "type": "located_in",
 "target": "na_anel_lama", "visibility": "public"},
{"id": "e_tr_rute_membro_corvos", "source": "npc_tr_rute_corvo_veterana", "type": "member_of",
 "target": "guilda_corvos", "visibility": "public"}
```

Inspirações registradas da onda 1 (URLs a conferir na Etapa 0; sem acesso web nesta sessão):

| Fonte | URL | O que inspirou |
|---|---|---|
| The Alexandrian, "Three Clue Rule" | https://thealexandrian.net/wordpress/1118/roleplaying-games/three-clue-rule | ≥ 3 portas por trama (R3) |
| Dungeon World SRD, "Fronts" | https://www.dungeonworldsrd.com/gamemastering/fronts/ | a `pergunta` de cada trama (stakes em aberto) |
| Blades in the Dark SRD, facções | https://bladesinthedark.com/factions | começar como peça pequena presa a gente com agenda própria (borda) |

## 4. Plano passo a passo

Pré-requisito: SPEC-348 `done` na `main` e rebase do worktree. Testes do escopo com no máximo `-n 2`.

### Etapa 0 — Sondas e reancoragem

1. Conferir os ids que a 348 gerou para Ilsa, Bertil, Sennar, Benedita e as arestas de Mãe Corva;
   ajustar §3.6 no mesmo commit se o slug divergir.
2. Reapontar as linhas de §1.1, §3.5 e §3.6 com `scripts/lore_reanchor.py --base <commit pré-348>`.
3. Listar NPCs de `npcs.txt:1-124` que moram em Nova Arcádia; decidir `cast` ou `excluded`.
4. Confirmar o local dos Inquisidores e do Mercado de Carne no mapa (portas de Matias e Tobias); se não
   houver nó, usar o anel que a lore cita.
5. Conferir as URLs de §3.10; inspiração que não abrir sai da tabela.

### Etapa 1 — Schema e lint (testes vermelhos)

1. **Testes** (`tests/test_spec350_lint.py`, fixtures sintéticas em `tmp_path`):
   - `test_valid_fixture_passes`;
   - `test_unknown_ids_are_errors` (NPC, local, facção, rumor, rota, segredo, archetype);
   - `test_thread_needs_three_doors_two_locations` (R3);
   - `test_door_anchor_cannot_be_core_or_leader` (R5);
   - `test_chosen_one_vocabulary_rejected` (R6, cada termo);
   - `test_lengths_enforced` (R2, R4, R7);
   - `test_forbidden_lexicon_rejected` (`_lexico_valoria.txt`);
   - `test_lore_ref_keyword_in_range` (lê só o intervalo);
   - `test_secret_doc_required_and_hidden` (R7, R10);
   - `test_public_field_leaking_secret_rejected` (R16 a/b/c);
   - `test_name_collision_with_curated_names` (R17a, inclui alias);
   - `test_duplicate_signature_rejected` e `test_jaccard_near_duplicate_rejected` (R17b/c);
   - `test_same_role_radical_in_region_rejected` (R17d).
2. **Implementação:** modelos de §3.3 em `services/plot_threads.py`; `validate_plot_threads` e
   `plot_signature` em `content_validator.py`; chamada em `validate_all`. Arquivo real ainda vazio
   (`threads: []`, onda 1 `in_progress`) → lint verde.

### Etapa 2 — API pura

1. **Testes** (`tests/test_spec350_api.py`, catálogo sintético):
   - `test_catalog_invalid_returns_empty_and_logs` (R20);
   - `test_plot_doors_deterministic_order_and_postura_first`;
   - `test_plot_doors_filters_dead_captured_defected_anchor` (R25, estados com `npc_sim` e projection);
   - `test_plot_doors_never_exposes_secret_fields` (serializa e busca `segredo`/`secret_ids`);
   - `test_sheet_for_row_by_id_ref_and_folded_alias` ("Bors", "Velha Netta");
   - `test_cast_npc_row_is_deterministic_and_secret_free` (mesmo `game_id` → mesmo dict; corpo do doc
     de segredo ausente);
   - `test_public_thread_brief_has_no_secret`;
   - `test_no_llm_no_io_in_module` (AST: sem `get_llm`, `query_rag`, `open(..., "w")`).
2. **Implementação:** §3.4.

### Etapa 3 — Gate do dono (sem código)

Apresentar §3.6 + §3.7 (com os ajustes da Etapa 0) ao dono. Registrar a resposta na §8 desta spec.
Nomes trocados entram direto.

### Etapa 4 — Autoria de Nova Arcádia

1. **Testes** (`tests/test_spec350_catalog.py`, arquivo real):
   - `test_nova_arcadia_has_six_threads_with_listed_members` (R9);
   - `test_twelve_new_npcs_have_public_secret_extra_edges_agenda_cast` (R10, R11);
   - `test_mundo_vivo_na_promoted_without_template_line` (R12: a frase-modelo some dos 3);
   - `test_every_na_named_npc_in_cast_or_excluded` (R13);
   - `test_348_npcs_reused_not_redefined` (R14: nenhum doc novo com nome de Ilsa/Bertil/Sennar/Benedita);
   - `test_region_coverage[nova_arcadia]` (R8, R30; vira obrigatório quando a onda fechar);
   - `test_repo_lint_has_no_plot_errors` (R15–R17 sobre o real).
2. **Implementação:** docs curados (template novo), segredos, `entities_extra.json`, `edges.json`,
   `agenda_by_npc`, `plot_threads.json`. Fichas dos canônicos derivadas da lore (campo `fonte`).
3. `bash scripts/dev/py.sh scripts/validate_content.py` → 0 ERRO.

### Etapa 5 — Prompt do NPC e roster

1. **Testes** (`tests/test_spec350_npc_prompt.py`, `tests/test_spec350_roster.py`):
   - `test_canonical_npc_gets_motives_from_sheet` (Netta: 4 linhas na ordem de R22);
   - `test_seed_motives_win_over_sheet`;
   - `test_stake_line_after_identity_and_cut_by_budget` (R23 com ficha mais longa; totais de
     `npc_self.py:26-30` respeitados);
   - `test_secret_never_literal_in_prompt` (texto do doc de segredo ausente do `SystemMessage`);
   - `test_flag_off_prompt_byte_identical` (spy, R28);
   - `test_no_extra_llm_invokes` (R26);
   - `test_state_payload_has_no_sheet_fields` (R26);
   - `test_roster_includes_region_cast_before_key_npcs` e `test_roster_cap_unchanged_and_freezes_overflow`
     (R24);
   - `test_roster_flag_off_identical`.
2. **Implementação:** `npc_self.motive_lines(row, sheet)`, linha de trama em `npc_self_blocks`,
   bloco de elenco em `npc_world._candidates`, flag em `config/flags.yaml`.

### Etapa 6 — Revisão independente

`spec-reviewer` (Opus) aplica §3.8 e grava `handoffs/SPEC-350-review.md`. `refazer` → autor corrige →
nova rodada só nos itens marcados.

### Etapa 7 — Reindex, guia e smoke

1. `rag.py` (precisa de `GOOGLE_API_KEY`; gate de lint embutido); registrar na §9 docs/chunks públicos e
   ocultos antes e depois.
2. `AUTORIA.md` Fluxo E + `docs/templates/codex/npc_trama.md` (R29).
3. Smoke §6. `waves[0].status = "done"`.

## 5. Critérios de aceite

- [ ] SPEC-348 `done` antes da Etapa 1; linhas reapontadas (Etapa 0)
- [ ] Mapa e nomes aprovados pelo dono (Etapa 3, registrado na §8)
- [ ] 6 tramas de Nova Arcádia, cada uma com ≥ 3 portas em ≥ 2 locais (R3, R9)
- [ ] 12 NPCs novos com doc público, doc oculto, entidade, arestas, agenda e ficha (R10, R11)
- [ ] 3 mundo vivo de Nova Arcádia promovidos, sem a frase-modelo (R12)
- [ ] Todo NPC nomeado de Nova Arcádia no `cast` ou em `excluded` com motivo (R13)
- [ ] `validate_content.py` com 0 ERRO, incluindo `validate_plot_threads` (R15–R17)
- [ ] `handoffs/SPEC-350-review.md` sem `refazer` pendente (R18)
- [ ] `tests/test_spec350_*` verdes; `uv run pytest` verde (suíte completa, coordenador)
- [ ] Flag `off` deixa prompt e roster idênticos (R28)
- [ ] Nenhuma chamada LLM nova; nenhum campo novo em `GameState`; saves antigos carregam (R26)
- [ ] Reindex feito e registrado (Etapa 7)
- [ ] Smoke real §6 executado e registrado na §9
- [ ] Fluxo E em `AUTORIA.md` + template (R29)

## 6. Smoke test com LLM real

Perfil `legacy`, `RPG_PLOT_THREADS=on`, `RPG_NPC_SELF=on`, chave real (ROUTES). 4–5 requests.

1. Novo jogo com região Nova Arcádia; viajar a `na_anel_lama`; ação "procuro a curandeira do beco".
   Esperado: Velha Netta em cena; a resposta reflete desejo/medo da ficha (marcados, o Doutor) sem citar
   o segredo; log `npc.self_block` com `sections` contendo `motives`.
2. Mesma cena: "o que você dá aos marcados que não adoecem?". Esperado: desconversa ou irritação
   (assunto que evita), sem o fato do doc oculto.
3. Ação "falo com a corvo que carrega as macas". Esperado: Rute (NPC novo) materializada com o nome
   certo, voz reconhecível (mortos contados como tempo) e o papel da trama; nenhuma duplicata no
   `/game/state` (`npcs` com uma Rute só).
4. Ação "falo com Bors" em `na_anel_ferro`. Esperado: a ficha é resolvida pelo alias (linha de trama
   presente no log/espião de prompt), apesar do id gerado por nome.
5. `/game/state`: nenhum texto de `desejo`, `medo`, `segredo_topico` ou do doc de segredo no payload.

Registrar provider/modelo, latência e qualquer campo trocado pela LLM na §9.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo novo; a ficha é resolvida por id/nome em tempo de prompt. NPC já
  materializado em save antigo ganha motivos da ficha no próximo turno (efeito desejado, só no prompt).
- **MockLLM/FallbackLLM:** sem structured output novo; nada a guardar. O mock não exercita voz: smoke §6
  é obrigatório.
- **Prompt e latência:** só linhas dentro dos tetos de `npc_self.py:26-30`; sem chamada nova; leitura do
  catálogo uma vez por processo.
- **Roster (304):** priorizar o elenco da região atual congela `key_npcs` de outras regiões enquanto o
  jogador está ali (eles voltam ao sair). Mede-se no playtest 50 turnos offline antes e depois
  (contagem de `npc_offscreen_fate` por região); se a simulação de outras regiões ficar vazia, D8 sobe o
  `ROSTER_CAP`.
- **Conflito com a 348:** ela edita `lore_nova/`, `edges.json`, `rumor_seed_overrides.json`,
  `lore_quests.json`. Esta spec só começa com a 348 `done`, não toca `lore_nova/` e só acrescenta arestas.
- **Pool compartilhado em produção:** um NPC do pool já promovido no staging pode ter o mesmo nome de um
  NPC novo daqui. O lint não enxerga o banco; o coordenador roda `shared_pool.get_by_name_fold` no staging
  antes do deploy e troca o nome se colidir. Depois do deploy, `curated_names` passa a barrar sósias
  (`shared_pool_validators.py:335-365`).
- **Vazamento pelo RAG:** os docs novos são públicos e vão para o FAISS; R16 + revisão R18 são o gate.
  Segredo só em `segredos/` (`hidden`).
- **Volume de autoria:** ~35 fichas e 12 docs numa onda; teto de 12 NPCs novos por onda e revisão com
  rubrica evitam lista de reskins.

## 8. Decisões que o dono precisa tomar

| ID | Decisão | Default se o dono não disser nada |
|---|---|---|
| D1 | Quantas tramas e NPCs novos em Nova Arcádia | 6 tramas, 12 novos (faixa aceitável 8–12) |
| D2 | Nomes e conceitos de §3.7 (12 NPCs) e o mapa de §3.6 | aprovar como estão; troca de nome não reabre a spec |
| D3 | Onde ficam os novos | `data/codex/npcs/tramas/`, id `npc_tr_<slug>`, canônicos de 2ª camada como o mundo vivo (G-15) |
| D4 | Ondas 2–7 | uma spec por onda (ID reservado na hora), reaproveitando esta infra e o Fluxo E |
| D5 | Ordem das ondas | §3.5: Pântano + Brekmar → Skallgard + Pradaria → Montanhas + Aethelgard → Floresta + Xylos → Zhur + Costa Negra → Ophidia |
| D6 | Flag `RPG_PLOT_THREADS` | `on` depois do smoke §6 verde; `off` até lá |
| D7 | NPC gerado do pool compartilhado ganha trama? | não: segue figurante; adoção só por curadoria manual (vira doc curado + ficha numa onda) |
| D8 | Roster da 304 | elenco da região atual antes de `key_npcs`, `ROSTER_CAP` 60 mantido; sobe para 80 só se o playtest mostrar outras regiões vazias |
| D9 | NPCs novos também em `lore_nova/npcs.txt`? | não (só Codex curado), para não colidir com a 348 nem deslocar âncoras |
| D10 | Afinidade de Postura nas portas | usar as sugestões de §3.6 (a 351 decide quanto pesa) |
| D11 | Rumores próprios das tramas novas (ex.: "o cabo não sabe ler") | não nesta onda; juntar numa spec de rumores depois da 351 |

## 9. Registro de execução

(vazio — preenchido pelo executor: divergências da Etapa 0, resposta do dono na Etapa 3, contagens do
reindex, resultado do smoke)

**Etapas 1 e 2 (executor Sonnet, 28/10, branch `spec-350`; Etapa 0 e 4+ pendentes):**

- Entregue: `services/plot_threads.py` (modelos §3.3 + API §3.4: `mode`, `catalog`, `threads_for_region`,
  `thread`, `cast_sheet`, `sheet_for_row`, `region_cast`, `plot_doors`, `cast_npc_row`,
  `public_thread_brief`, `stake_line`), `services/plot_threads_lint.py` (lint puro com `PlotRefs`),
  `validate_plot_threads`/`plot_signature` em `content_validator.py` (ligado em `validate_all`),
  `data/world/plot_threads.json` vazio (onda 1 `in_progress`), flag `RPG_PLOT_THREADS` (default `off`)
  registrada já aqui (o gate de flags exige quando o código lê a variável; antecipa parte da Etapa 5).
- Desvio: o lint puro mora em `plot_threads_lint.py` (como `faction_membership_lint.py`); `content_validator`
  só monta `PlotRefs` com os dados reais. Modelos sem limites de tamanho (o lint os cobre, para o catálogo
  não virar vazio por um texto longo demais em runtime).
- Desvio: `sheet_for_row` ganhou fallback "nome de 1 palavra que prefixa exatamente 1 nome do elenco"
  (ex.: "Bors" -> Bors Martelo-partido), pois `entities.json` não tem alias "Bors"; alternativa é
  acrescentar o alias no grafo na Etapa 4.
- `plot_doors` devolve `[]` com `RPG_PLOT_THREADS=off` (R28).
- **Integração SPEC-348 pendente:** `LEAK_PHRASES` vive em `tests/test_spec348_leaks.py` (só na branch
  da 348). `content_validator._default_leak_phrases()` tenta importá-lo e cai em lista vazia (R16b inerte
  até a 348 pousar). `validate_plot_threads(path, leak_phrases=...)` aceita a lista direta. Quando a 348
  pousar: confirmar o import, ou mover `LEAK_PHRASES` para dado (`data/`/serviço) e apontar o lint para lá;
  na Etapa 4 `test_repo_lint_has_no_plot_errors` deve afirmar `_default_leak_phrases()` não vazio.
- Pendente de dados reais: `secret_ids` aceitos = chaves de `SECRET_SIGNATURES` + `data/secret_entities.json`;
  segredos novos da 348 (testamento, Lista de Fornalha...) precisarão estar em um deles ou o lint reprova.

### Respostas do coordenador (27/10, autorizado pelo dono a decidir)

- **D1/D2:** aprovados o mapa da §3.6 e os 12 NPCs da §3.7, com um acréscimo obrigatório: a **7ª trama
  "Pó de Sonho"** (`tr_na_po_de_sonho`). O exemplo do próprio dono para a abertura foi "um elfo em Nova
  Arcádia já tem que ter algo do Pó de Sonho". Antes de escrever, a Etapa 4 faz Grep de "Pó de Sonho" e
  "Pó de Fada" em `lore_nova/` (npcs, items, creatures, rumors, timeline, races, locations) e nas sementes de
  rumor. Ligações que a trama deve ter: Elaryin (morte por Pó de Fada, versão oficial "bebeu", C-16 da 348),
  a venda sob licença no Anel de Ferro e Os Quebrados (348).
  - 2 NPCs novos de borda, com a mesma rubrica e unicidade, e ≥3 portas mundanas.
  - Afinidade de raça élfica: uma porta precisa servir a um personagem Elfo sem exigir que ele já saiba da trama.
  - Total da onda 1: 7 tramas e 14 NPCs novos.
- **D3–D11:** default aceito.
- **Interface com a 351:** os nomes desta spec (`plot_doors`, `cast_npc_row`, `public_thread_brief`) são os
  canônicos; o adaptador da 351 se ajusta.
- **Ordem de execução:** a Etapa 0 começa depois do pouso da 348 (reancoragem). A Etapa 3 (gate do dono)
  vira revisão do coordenador + revisão Opus independente da Etapa 6, por autorização do dono.
