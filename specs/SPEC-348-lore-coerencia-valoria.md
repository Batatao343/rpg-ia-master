# SPEC-348 — Coerência da lore de Valoria: aplicar as decisões de 27/10 e escrever as expansões aprovadas

> **Status:** `in-review`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Origem:** decisões do dono em [`docs/lore/decisoes-2026-10-27.md`](../docs/lore/decisoes-2026-10-27.md)
> (fonte de verdade, não reabrir) sobre a revisão
> [`docs/lore/revisao-2026-10-27.md`](../docs/lore/revisao-2026-10-27.md) (evidência arquivo:linha por ID).
> **Depende de:** SPEC-312 (`done`: `rumor_seeds.json`, `build_rumor_seeds.py`, overrides),
> SPEC-313 (`done`: `lore_quests.json`, rotas de entrega), SPEC-303/307 (`done`: `festivals.json`,
> `calendar.json`), Fase 7.1–7.3 (lint de conteúdo, curadoria migration-safe, docs de segredo de NPC).
> **Desbloqueia:** specs futuras do mapa (G-03/G-04/C-12), do bestiário (G-14), do Hospedeiro jogável e
> das condições Vampiro/Lycan (G-05), da reescrita de `data/rules.txt` (G-02); assinaturas de segredo
> novas para os fatos escondidos aqui (§8 D11).
> **EXECUTOR_MODEL:** `Opus` (autoria em voz de crônica + curadoria de visibilidade; Sonnet só para as
> etapas mecânicas 1, 7 e 9) · **REVIEW_MODEL:** `Opus` (subagente independente, lê o diff de
> `lore_nova/` e os testes) · **REVIEW_REQUIRED:** `true` (mexe em visibilidade de segredo e no
> gerador do Codex) · **EVAL_AUTHORING_REQUIRED:** `false` (não toca `evals/`).

---

## 1. Contexto & Objetivo

A revisão de 27/10 achou três famílias de problema na lore de Valoria: **contradições** (o pacto de
Valerius tem duas contrapartes e três datas; a Praga tem quatro origens; o mundo presente não tem
âncora de anos), **vazamentos de segredo** em arquivos `visibility: public` que o narrador recebe pelo
RAG (Magda é a Víbora, o testamento no barril, os corpos marcados, a função do Farol, o Arauto) e
**lacunas** (as cinco Posturas, a Entropia e a Carga do Abismo não existem no mundo; facções sem rosto;
calendário sem lore). O dono respondeu tudo em `docs/lore/decisoes-2026-10-27.md`.

Esta spec **aplica** essas decisões nas fontes de lore e **escreve o texto canônico** das expansões
aprovadas (E-01…E-26, lista no §2.9), mais `world_story/posturas.md` com cinco NPCs mestres e a âncora
cronológica de 45 anos na Era 7. É trabalho de conteúdo: a mecânica não muda. O que muda no motor é só
o que o conteúdo exige para continuar verde (clusters de timeline oculta, sementes de rumor regeneradas,
âncoras `arquivo:linha` reapontadas, `YEAR_BASE` do calendário).

Princípios: `lore_nova/` é a fonte e o Codex é gerado (`docs/guias/AUTORIA.md:5-9`); curadoria só por
`codex_overrides.yaml`, arquivos `curated: true` e `data/graph/*` (`AUTORIA.md:40-72`); segredo nunca
em chunk público (`AUTORIA.md:27-29`, lint 7.3); tom de Valoria (§2 da revisão: custo, entropia,
instituições-armadilha, crônica cansada, segredos como inversão, léxico de
`data/cards/_lexico_valoria.txt`).

### 1.1 Problemas com evidência

Os IDs C/G/S/E remetem à revisão, que já traz a evidência por linha. Abaixo, só o que a spec precisa
para o plano e os **achados novos** desta leitura (marcados N).

| # | Problema | Evidência |
|---|---|---|
| P1 | Pacto: Daruun × armadura; décimo ano × "Guerra das Cinzas" (C-01/C-02) | `lore_nova/secrets.txt:10` "durante a Guerra das Cinzas", `:12` "No décimo ano", `:14`, `:16`; `lore_nova/timeline_completa.txt:448-454` |
| P2 | Sem âncora de anos; números colidem (C-09) | `npcs.txt:22`, `:52`, `:73`; `secrets.txt:30` "há quinze anos"; `factions.txt:43`, `:87` |
| P3 | Praga com quatro origens; o texto secreto diz que a doença "não é natural" (C-07) | `timeline_completa.txt:338`, `:384`; `secrets.txt:25-30`, `:98`; **N** `secrets.txt:26` "A Ferrugem do Sangue não é doença natural" (colide com a cadeia decidida) |
| P4 | Magda = Víbora em doc público (C-17) | `data/codex/npcs/npc_velha_magda.md:15` "(A VÍBORA)", `:18` "Papel real: Líder da Mão Sombria", `:22` "Escritório da Mão Sombria" ← `lore_nova/npcs.txt:44-52`; `data/codex/factions/mao_sombria.md:23`, `:31` ← `factions.txt:35`, `:43`, `:51`; **N** `npcs.txt:1266` "VELHA MAGDA/A VÍBORA (líder da Mão Sombria)" e "GRUM (taverneiro com o testamento real)" |
| P5 | Testamento público (C-18) | `data/codex/items/art_testamento_real_no_barril.md:9` `visibility: public`, `:17` ← `items.txt:747-749`; `data/codex/factions/legiao_ferro.md:33` ← `factions.txt:30` |
| P6 | Corpos marcados → Vane público (C-19) | `data/codex/factions/guilda_corvos.md:27` ← `factions.txt:87` |
| P7 | Função do Farol e ciclo do guardião públicos (C-20) — **N: também na timeline pública e no NPC Volkar** | `data/codex/locations/skallgard.md:27` ← `locations.txt:227`; `data/codex/monsters/mon_rede_carmesim.md:22` ← `creatures.txt:28`; `mon_gigantes.md:20`; **N** `timeline_completa.txt:16` "Para conter o que perceberam…" (Era 0, doc `timeline_e0_1_…` público), **N** `timeline_completa.txt:164-166` "O ciclo do guardião… A cada cem anos, um andarilho… mata o guardião anterior" (Era 4, `timeline_e4_1_o_abismo_concentrou_como_sempre_faz.md:9` `visibility: public`); **N** `npcs.txt:586-592` (Volkar: "Natureza"/"O que sabe"/"Para o narrador" não são rótulos secretos); **N** `items.txt:163` "para suprimir a Rede Carmesim", `:171` "quando o Farol falhará" |
| P8 | Arauto = Aprendiz em doc público (C-21) — **N: "Natureza" e "O que revela" também entregam a inversão** | `data/codex/npcs/npc_o_eco_do_aprendiz.md:21`, `:23`, `:25` ← `npcs.txt:1869`, `:1871`, `:1873` |
| P9 | O split de segredo de NPC só move parágrafos com rótulo da lista; "Papel real", "Natureza", "O que sabe", "O que revela", "Para o narrador" ficam públicos | `scripts/migrate_lore_nova.py:430-452`; `services/content_validator.py:67-79` (`NPC_SECRET_LABELS`) |
| P10 | Timeline: visibilidade por **cluster de frase** (início/fim); texto novo oculto exige cluster novo, e reescrever a frase-âncora de um cluster desprotege o trecho | `scripts/migrate_lore_nova.py:228-249` |
| P11 | **N** Calendário diz "Ano 112 da Era 7", incompatível com a âncora de 45 anos (Era 7 começa na fundação, `timeline_completa.txt:416`); o ano ainda está em revisão do dono | `data/world/calendar.json:3` `"YEAR_BASE": 112`; `tests/test_spec307_calendar.py:175-202` (`year_review == "dono"`); `tests/test_spec307_display_api.py:44-190` |
| P12 | **N** 237 âncoras `arquivo.txt:N` em 7 arquivos de dados apontam para linhas de `lore_nova/`; qualquer edição desloca linhas e quebra testes que leem a linha | `data/npc_seed_tables.json` (146), `data/world/rumor_seeds.json` (40, regenerável), `data/race_attitudes.json` (18), `data/world/festivals.json` (14), `data/world/calendar.json` (12), `data/world/world_quests.json` (5), `data/world/lore_quests.json` (2); testes `tests/test_spec313_catalog.py:61-76`, `test_spec303_festivals.py`, `test_spec306_npc_seed_expansion.py`, `test_spec297_*` |
| P13 | **N** O gerador de sementes exige exatamente 40 rumores e a suíte trava a distribuição 13/15/12 | `scripts/build_rumor_seeds.py:24`, `:277-278`; `tests/test_spec312_seeds.py:31`, `:39-41` |
| P14 | S-08: rumor do guardião está `truth: false` | `data/world/rumor_seeds.json:722-744`; `data/world/rumor_seed_overrides.json:146-151` |
| P15 | E-14/S-07: semente de Ophidia diz "arquipélago do sul"; o texto do rumor usa "Yuan-Ti" (clichê D&D, única ocorrência) | `rumor_seed_overrides.json:131-134`; `lore_nova/rumors.txt:253`; Ophidia no oeste: `locations.txt:281` |
| P16 | G-16: rota de entrega usa `minerio_ferro`, sem lore | `data/world/lore_quests.json:37-45`; Aço de Vorr: `items.txt:27` |
| P17 | G-13: "Dia do Céu Limpo" e festas sem texto na lore | `data/world/festivals.json:36`; `tests/test_spec303_festivals.py:43`, `test_spec307_festivals.py:50` (`review == "dono"`) |
| P18 | Posturas sem lore (G-01) | `data/classes.json:2-3`, `:120-121`, `:230-231`, `:359-360`, `:470-471`; 0 ocorrências em `lore_nova/` |
| P19 | Grafo: dois líderes de fato sem aresta (Morvan, Mãe Corva); Chama Azul sem líder (C-11/G-08) | `data/graph/edges.json:283-288`, `:402-405`; entidades `npc_keeper_morvan` (`entities.json:1388`), `npc_mae_corva` (`:1668`) já existem |
| P20 | Edição da 1ª frase de um trecho da timeline muda o **id** gerado do doc (ex.: `timeline_e4_1_o_abismo_concentrou_como_sempre_faz`) | `scripts/migrate_lore_nova.py:277-340`; só docs citam esses ids fora do Codex (`docs/descricao_projeto/…/explore_03_mundo_memoria.md:63`) |

## 2. Requisitos

Notação: "público" = doc `visibility: public` no Codex; "oculto" = `hidden` ou `secret`. Todo texto
novo segue o tom (§1) e não usa os termos `[proibidos]` de `data/cards/_lexico_valoria.txt:5-32`.

### 2.0 Processo e fonte

- **R1 — Linha de base do migrate.** Antes de editar qualquer fonte, `migrate_lore_nova.py` rodado no
  worktree limpo deixa `git status --porcelain data/codex data/graph/entities.json` vazio. Se não deixar
  (doc gerado editado à mão sem `curated: true`), a divergência é registrada na §9 e resolvida **antes**
  da Etapa 2: vira override, `curated: true` ou é descartada com aval do coordenador. Nenhum conteúdo
  manual some silenciosamente.
- **R2 — Edição só na fonte certa.** Fato de doc gerado muda em `lore_nova/*.txt`; visibilidade de doc
  gerado muda em `data/codex_overrides.yaml`; doc novo sem fonte em `lore_nova` (posturas, codex de nó)
  é `curated: true` + entrada em `data/graph/entities_extra.json`. Nenhum `.md` gerado é editado direto.
- **R3 — Clusters da timeline.** Toda frase-âncora de `_TIMELINE_HIDDEN_CLUSTERS`
  (`migrate_lore_nova.py:234-249`) continua aparecendo **exatamente uma vez** em
  `timeline_completa.txt` (normalizada sem acento, minúscula), ou o cluster é atualizado no mesmo
  commit. Clusters novos desta spec: §3.4.
- **R4 — Âncoras reapontadas.** Depois das edições, toda âncora `<arquivo>.txt:<N>` nos 7 arquivos de
  P12 aponta para uma linha não vazia do arquivo atual e, quando a entrada tem `lore_keyword`, a linha
  contém a palavra. O reapontamento é feito por `scripts/lore_reanchor.py` (§3.5) a partir do diff,
  não à mão; âncoras que caíram em linha reescrita saem num relatório e são conferidas uma a uma.
- **R5 — Idempotência.** Rodar `migrate_lore_nova.py` 2× seguidas não muda nada; `build_rumor_seeds.py
  --check` verde; `validate_content.py` com 0 ERRO.

### 2.1 Cronologia (C-09, C-03, C-04, C-16, G-06, G-07, S-06, calendário)

- **R6 — Âncora pública (C-09).** A Era 7 da timeline ganha um parágrafo público com a cronologia que
  o mundo conhece, contada a partir do presente: Guerra do Céu Vermelho terminou **há 45 anos**;
  fundação de Nova Arcádia **há 44** (Ano 1 da Era 7); Elaryin morre **há 41**; Valerius vira Lorde
  Protetor **há 40**; o Código de Ferro aparece numa noite **há 30**; a primeira onda da Praga de Ferro
  **há 30**. Nenhuma data oculta (pacto, acordo Corvos–Vane, caixa de Vane, fundação da Mão Sombria)
  entra nesse parágrafo.
- **R7 — Âncora oculta.** Um bloco `[CATEGORIA: SEGREDO]` novo em `secrets.txt` ("A cronologia que
  ninguém escreve") fixa as datas ocultas: pacto Valerius **há 30** (no décimo ano de governo, mesma
  noite do Código); acordo Corvos–Vane **há 30**; Magda funda a Mão Sombria **entre 44 e 29 anos
  atrás** (quinze anos de construção, `factions.txt:43`); caixa de Vane / cepa atual **há 15**.
- **R8 — Números concordantes.** Todo número de anos do presente em `lore_nova/` concorda com R6/R7.
  Mínimo a revisar: `npcs.txt:22` ("nos vinte anos seguintes" ao décimo ano: cabe), `:52`, `:73`;
  `secrets.txt:26` ("dezoito anos enquanto servia à corte": cabe em 40), `:30`, `:50`, `:136`;
  `factions.txt:43`, `:87`; `faction_perspectives.txt:9` (Ress, veterano de quinze anos). O executor
  registra na §9 cada número conferido e o que mudou.
- **R9 — Conselhos (C-03).** `timeline_completa.txt:432` "Por décadas" vira "Nos primeiros anos"; o
  texto diz que os conselhos sobrevivem **formalmente** sob Valerius até o Código de Ferro os dissolver
  no décimo ano.
- **R10 — Ciclo acelerando (C-04).** `timeline_completa.txt:158` passa ao passado ("como fazia a cada
  dois mil anos"); `:312` mantém "Mil anos passaram" e diz que o resíduo não dispersou; a Era 7 diz, na
  voz dos registros élficos, que o intervalo caiu à metade (2000 → 1000) e que quem sabe contar teme a
  casa dos quinhentos. Público.
- **R11 — Elaryin (C-16).** `npcs.txt:82` e `timeline_completa.txt:440-448`: morreu de overdose de Pó
  de Fada; a versão oficial diz que "bebeu até morrer", porque o Pó era vendido sob licença no Anel de
  Ferro. A versão oficial é pública; a causa real fica no parágrafo com rótulo secreto do NPC.
- **R12 — Nomes de evento (G-06).** "Dia Sem Sombra" sai do título da Era 5 (`timeline_completa.txt:218`)
  e entra no título da Era 6 (`:318`) e no corpo onde as sombras se desconectam (`:340`); `:298` passa a
  dizer "a Falha Crítica de Contenção (nome que os Anões dão ao colapso, porque 'colapso' não está no
  Protocolo)". `data/origins.json:44` já usa o nome e fica como está.
- **R13 — Brekmar na história (G-07).** A Era 6 ganha um parágrafo público: Brekmar nasce como porto de
  fuga da coalizão, nos navios de Durrak; Lyss chega "no ano em que o porto parou de enterrar os mortos".
  Kahen ex-mercadoria de Groth Algema-Fria fica oculto (E-13).
- **R14 — Dragões (S-06).** `timeline_completa.txt:410`: "cinco dragões dispersaram-se; Thessrak foi
  selado"; `:476` coerente ("os seis dragões restantes" continua certo como contagem, mas não pode dizer
  que todos estão "cada um no seu território" sem exceção de Thessrak).
- **R15 — Ano do calendário (D1, decisão do dono).** `YEAR_BASE` **fica 112**. O Ano 1 não é a
  fundação: é o início da contagem do **Protocolo dos Anões** (o registro das Landships), que começou
  antes da guerra. Nova Arcádia herdou a contagem sem saber de onde ela vem. Com a âncora de 45 anos:
  Guerra do Céu Vermelho no Ano 67, fundação de Nova Arcádia no Ano 68, presente no Ano 112. A timeline
  (Era 7, público) ganha a frase que explica a contagem; a Era 7 continua começando na fundação, só o
  número do ano é anão. `year_review` deixa de ser `"dono"`; os testes da 307 que fixam "Ano 112"
  continuam valendo (só o teste de `year_review` muda, declarado aqui).

### 2.2 O pacto de Valerius (C-01, C-02)

- **R16 — Uma versão em camadas.** `secrets.txt:9-18` e o cluster oculto da Era 6
  (`timeline_completa.txt:448-454`) contam a mesma história: Valerius decide no vácuo de Elaryin, passa
  a década seguinte rastreando Daruun e, **no décimo ano de governo**, na mesma noite do Código de Ferro,
  Daruun o leva às masmorras. Daruun é o **corretor**; a armadura de Malagor é a **interface** do Abismo;
  o preço contratual é a família (a mulher e os dois filhos, consumidos, não mortos); a perda da dúvida
  é **efeito colateral** (quem o contradizia era a mulher). "Guerra das Cinzas" sai de `secrets.txt:10`;
  `npcs.txt:16` mantém a definição de "Guerra das Cinzas" como nome antigo dos conflitos pré-Malagor.
- **R17 — Sem contradição de preço.** As frases "não era sobre a capacidade de duvidar"
  (`timeline_completa.txt:454`) e "consumiu a parte… responsável pela dúvida" (`secrets.txt:14`) ficam
  compatíveis no texto (a primeira fala do contrato, a segunda do efeito).
- **R18 — Continua oculto.** Os parágrafos de R16 na timeline seguem dentro do cluster
  `("daruun nao buscou valerius", "a primeira consequencia visivel do pacto")` ou de um substituto
  equivalente (R3). Nenhum doc público contém as assinaturas de `pacto_valerius`
  (`services/secret_signatures.py:18-24`).

### 2.3 A Praga de Ferro (C-07, S-03)

- **R19 — Cadeia única.** O organismo é um só, assinatura do Abismo (oculto, `secrets.txt:98`). Morrakh
  o carrega (público, `timeline_completa.txt:338`). Malagor o espalhou pelo sangue na guerra; o sangue
  encharcou minas e fundições e a **primeira onda** brotou **há 30 anos** (público, `:384`, com a data
  de R6; cola narrativa em D5). A onda ficou controlável. A **cepa atual** de Nova Arcádia veio da caixa
  de Vane **há 15 anos** (oculto, `secrets.txt:25-30`), que é o que Magda quer dizer com "não veio das
  minas" (`rumors.txt:108`).
- **R20 — Texto de laboratório reescrito.** `secrets.txt:26` deixa de dizer que a Ferrugem "não é doença
  natural": a **cepa atual** é de laboratório; a doença é do Abismo. `secrets.txt:98` cita a cadeia.
- **R21 — Silas Vane (S-03).** `npcs.txt:71`: Vane estudou os "dois únicos sobreviventes **não
  simbióticos**" do fungo de Xylos (os Hospedeiros são simbióticos, `timeline_completa.txt:256-258`).

### 2.4 Mundo, geografia e cosmologia (C-05, C-06, C-14, C-15, G-10, G-11, G-12)

- **R22 — Aethelgard (C-05).** `locations.txt:235-236`: lago de cratera que o mar leste invadiu na
  erupção da Era 6 (salobro, garganta para o mar); `:263` "décadas de imersão" → "eras de imersão";
  `timeline_completa.txt:272`, `:332`, `:398` coerentes com "lago que o mar invadiu".
- **R23 — Onze Landships (C-06).** Público: os Anões dizem doze (`timeline_completa.txt:298-302`,
  `races.txt:88`, `:105`); onze navegam; a que falta consta no Protocolo como "em manutenção
  prolongada", porque o Protocolo não tem procedimento para registrar perda. Onde ela está é oculto (E-08).
- **R24 — Estrelas (C-14).** `timeline_completa.txt:40` ganha a frase: da Borda não se veem estrelas,
  embora à noite haja estrelas sobre Valoria e ninguém saiba de onde vem a luz. Público. O resto (as
  estrelas são membrana; "além das estrelas" é o lado de lá) fica no segredo da Chama Azul
  (`secrets.txt:152`).
- **R25 — Verme (C-15).** `secrets.txt:206-208` ganha: o "algo" que selou o Rei Subterrâneo antes das
  raças era o Verme-Primordial, e o Rei **perdeu** essa guerra. Oculto.
- **R26 — Magia é combustível (G-10).** Público: o custo do Éter é **dor**; o Cinzéu não sente dor, não
  paga menos, só não sabe quanto pagou (`npcs.txt:132` deixa de dizer "mais acessível para um Cinzéu"
  sem essa ressalva); o "registro" da Legião (`factions.txt:20`) é a **Lista de Fornalha**: os magos
  registrados são os que a Legião consome, e é deles que vêm os magos dos Jardins (`locations.txt:47`).
  `timeline_completa.txt:104` coerente.
- **R27 — Deuses Antigos (G-11).** Dois parágrafos na Era 0: havia algo que os Gigantes serviam; foi
  devorado pelo Abismo antes das raças. Público só "havia, e não há mais". "O Farol é o que sobrou da
  liturgia" fica oculto (cluster novo, coerente com C-20; D9).
- **R28 — A Lua (G-12).** Um parágrafo público na Era 1 (e `races.txt:18`): os Elfos lançaram a lua com
  magia, por destilação em massa; milhares de Elfos queimados para movê-la.

### 2.5 Facções, NPCs e grafo (C-08, C-10, C-11, C-13, G-08, G-09, G-15, G-16)

- **R29 — O Rei de Grum (C-08).** O Rei é **o último Rei da Colina Cinza** (nome do dono, D4; o Rei fica sem nome próprio), reino
  humano da Pradaria anterior à guerra, queimado por Malagor. Público: o Reino da Colina Cinza existiu e caiu (Era 6). O
  que Grum viu, o testamento e o herdeiro são ocultos (`npcs.txt:35` já é "História real", rótulo
  secreto; `secrets.txt:66-68` ganha o nome do reino e a frase "legitimidade sem território é a única
  coisa que o Código não consegue proibir").
- **R30 — Árbitro de Brekmar (C-10).** O título de Kahen vira "Árbitro de Brekmar" em `npcs.txt:128`,
  `:282`, `races.txt:353`, `factions.txt:217-220`, `locations.txt:426`; "governante" só em fala de
  quem é de fora. `e_kahen_controla_brekmar` não muda.
- **R31 — Colmeia e Solvhen (C-11).** `factions.txt:477` explica que, para quem vem de fora, "lidera"
  quer dizer "é o consultado"; a aresta `e_ouve_longe_lidera_colmeia` fica. `edges.json` ganha
  `e_morvan_lidera_cidades` (`npc_keeper_morvan` `leads`
  `cidades_estado_sobreviventes_vaelorn_solvhen`, público) e `e_morvan_em_solvhen` (`located_in`
  `pr_solvhen`). Com Aerwen morta na projection, a fação continua com um líder vivo (teste, §4 Etapa 6).
- **R32 — Cripta da Que Afundou (C-13).** `locations.txt` (Pântano) ganha a cripta: os afogados de lá são
  os druidas que Saelwen afundou; não são os de Aethelgard. Público: "afogados que não são de
  Aethelgard e não gostam de visitas"; quem os afundou e por quê: no parágrafo secreto de Saelwen.
  Codex curado `data/codex/locations/pm_cripta_afogada.md` (o nó já existe em
  `entities_extra.json:982`). O nome do nó no mapa não muda aqui.
- **R33 — Rostos de facção (G-08).** `factions.txt:77` cita Mãe Corva como líder da Guilda dos Corvos e
  `edges.json` ganha `e_mae_corva_lidera_corvos` (`leads guilda_corvos`). Filhos da Chama Azul ganham
  líder (E-04). "Os Quebrados" vira facção nova em `factions.txt`: Elfos de estimação do Anel Dourado,
  clandestinos, ligados ao Pó de Fada e à morte de Elaryin; público o papel aparente, oculto o diário
  (E-20).
- **R34 — Juramento do Fogo Alto (G-09, E-10).** `factions.txt` (Skallgard) e `locations.txt`: uma noite
  por ano, sob o Farol, os dois clãs renovam a trégua no **Salão do Juramento**; o assento central está
  vazio desde que o último árbitro morreu (um Gigante, D4); quem senta vira alvo dos dois. Público. O
  nó do mapa segue "Salão do Jarl" até a spec do mapa (D12).
- **R35 — `mundo_vivo/` canônico (G-15).** `docs/guias/AUTORIA.md` ganha uma linha na tabela de camadas:
  `data/codex/npcs/mundo_vivo/` é canônico de segunda camada (gerado e curado, `curated: true`), e
  `lore_nova/` deixa de ser "fonte única" para NPCs.
- **R36 — Lingote de Vorr (G-16).** `data/artifacts.json` ganha `lingote_aco_vorr` (`type: material`,
  descrição com lore de `items.txt:27`); a rota `minerio_skallgard_brekmar` de `lore_quests.json:37-45`
  passa a entregar `lingote_aco_vorr` (o `id` da rota fica, para não quebrar save com quest aberta),
  `lore_ref` = a linha de `items.txt` com "Aço de Vorr", `lore_keyword` = "Vorr", `review` sai.

### 2.6 Vazamentos de segredo (C-17…C-21)

- **R37 — Víbora (C-17).** Público de Magda: só o papel aparente (vendedora de espetinhos e amuletos no
  Anel de Lama) e o "Como identificar" sem nomear a Mão Sombria. Título sem "(A VÍBORA)"; `[TAGS]` sem
  `Víbora`/`Identidade_Secreta`; "Papel real" e "O carrinho" passam a rótulo secreto ("Segredo:") e caem
  em `npc_velha_magda_segredo.md`. `factions.txt:43` e `:51` falam da "Víbora" sem nome; `:35` sem a tag
  `Magda`. `npcs.txt:1266` sem "/A VÍBORA (líder da Mão Sombria)" e sem "com o testamento real".
  `data/bestiary.json:2194` (`enemy_boss_vibora`): só a descrição perde "Líder da Mão Sombria" (D8).
- **R38 — Testamento (C-18).** `art_testamento_real_no_barril` vira `visibility: hidden` por override;
  `items.txt:749` mantém o fato (o doc é oculto). `factions.txt:30` diz "um documento que a Legião
  procura há anos sem saber o que é".
- **R39 — Corpos marcados (C-19).** `factions.txt:87` fica com o rumor ("a Guilda nunca queima certos
  corpos", `rumors.txt:234`); o destino (Vane) e o acordo de trinta anos vão para um parágrafo "Segredo:"
  do Doutor Silas Vane em `npcs.txt` (cai em `npc_doutor_silas_vane_segredo.md`).
- **R40 — Farol (C-20, interpretação em D3).** Público: o Farol foi erguido pelos Gigantes, emite
  anti-luz, tem um guardião que ninguém alcança, e **ninguém sabe por quê**. Oculto: que a anti-luz
  suprime a Rede Carmesim, o ciclo de cem anos do guardião, o "Abismo cobra vida", e a estimativa de
  falha. Trechos a tratar: `locations.txt:227`; `creatures.txt:28`, `:53`, `:146` e o bloco que gera
  `mon_gigantes.md:20`; `items.txt:161-171`; `npcs.txt:584-592` (Volkar: "Natureza", "O que sabe" e o
  miolo de "Para o narrador" viram "Segredo:"); `timeline_completa.txt:16` (a frase de propósito sai do
  parágrafo público para um parágrafo oculto logo depois) e `:164-166` (o ciclo do guardião vira
  parágrafo próprio, separado do nascimento dos Cinzéus, e entra em cluster oculto). A Rede Carmesim
  como fenômeno (Cristal-Sanguíneo, Câmara do Sinal) continua pública.
- **R41 — Arauto (C-21).** `npcs.txt:1869-1873` (Eco do Aprendiz): público fica com a cena (a figura
  repetindo o gesto) e a dúvida ("herói ou tolo"); a inversão (destruiu a cidade para impedir algo pior;
  é a mesma pessoa que o Arauto) vai para parágrafo "Segredo:". Varredura: nenhum "Para o narrador" de
  NPC público carrega fato de `secrets.txt` (teste de R44 cobre).
- **R42 — Fato preservado.** Cada fato retirado do público existe em pelo menos um doc oculto depois da
  mudança (o vazamento é corrigido movendo, nunca apagando).

### 2.7 Dados de mundo (S-08, E-14, G-13, rumores novos)

- **R43 — Guardião (S-08).** `rumor_seed_overrides.json` `rumor_o_guardiao_do_farol_era_um_de_nos`:
  `truth: true` (o `secret_id` fica). A fração de falsos entre sementes `lore` habilitadas segue em
  [0,20; 0,35] (SPEC-312 R6).
- **R44 — Ophidia (E-14).** Override da semente: `gist` diz "as ilhas do oeste"; `rumors.txt:253`
  troca "os Yuan-Ti" pelo nome do povo de Ophidia usado em `locations.txt`/`races.txt` (Etapa 0 confirma
  o nome). `truth` da semente não muda (o boato é falso: não é veneno contra humanos, ver E-14).
- **R45 — Calendário na lore (G-13).** `daily_life.txt` ganha a seção "Como Valoria conta o tempo":
  sete meses com nome de dragão; semana de cinco Sinos **contada só em Nova Arcádia** (fora dela, dias
  sem nome, D6); "Noite do Silêncio"; "Véspera do Céu Vermelho" (vigília, não festa); as outras 12 festas
  de `festivals.json` em 1–2 frases cada. `festivals.json:36` `name` → "Véspera do Céu Vermelho",
  `label` → "em vigília" (o `id` `fim_do_ceu_vermelho` fica); todas as festas: `review` → `"aprovado"`;
  `lore_refs` passam a apontar para a seção nova. `test_spec303_festivals.py:43` e
  `test_spec307_festivals.py:50` passam a esperar `"aprovado"`.
- **R46 — Rumores novos (D2).** `rumors.txt` ganha 8 blocos `[CATEGORIA: RUMOR]`: E-02 (o servo que
  sobrou), E-04 (o pregador tem a cicatriz da Legião), E-13 (o Árbitro de Brekmar tem um número gravado)
  e um rumor de origem por Postura (5). Cada um com `[TAGS]` que resolvem região (nenhuma semente nova
  `disabled`), `[FONTE]` e confiabilidade (§3.6). `EXPECTED_LORE` vira 48 e o teste de distribuição
  passa à contagem nova; fração de falsos dentro de R43. Rumor que toca segredo leva `secret_id` no
  override (bloqueia nascimento antes do reveal, SPEC-312).

### 2.8 Posturas (G-01, E-26)

- **R47 — `world_story/posturas.md`.** Doc curado (`curated: true`, `type: world_story`, `visibility:
  public`, ~1 página) que conta as cinco Posturas como tradições do mundo, uma seção por Postura com:
  postura diante do Abismo (o verbo de `classes.json`: ama, negocia, trabalha junto, manipula, nega),
  origem no mundo, lugar, mestre (NPC), facção que a despreza e um rumor de origem. Fala também da
  Entropia e da Carga do Abismo como o mundo as sente (sem números). Tabela canônica em §3.7.
- **R48 — Cinco mestres.** Cinco NPCs em `npcs.txt` (bloco `[CATEGORIA: NPC]`, papel aparente público,
  "Segredo:" quando houver), com `member_of` na facção de origem e `located_in` no lugar (arestas em
  `edges.json`, ids conferidos na Etapa 0). Hostilidade de facção fica só no texto (sem `enemy_of`, que
  o motor de mundo consome).
- **R49 — Sem drift com a mecânica.** Os nomes de classe citados em `posturas.md` são exatamente as
  chaves de `classes.json`; o doc não descreve número, carta nem regra (o narrador não pode tirar
  mecânica dele).

### 2.9 Expansões aprovadas (texto canônico)

- **R50 — Cada expansão vira texto na fonte certa, com a visibilidade da §3.8.** Lista: E-01, E-02,
  E-03, E-04, E-05, E-06, E-08, E-10, E-11, E-12, E-13, E-14, E-15, E-16, E-19, E-20, E-24, E-26.
  Só texto: quests, cartas, artefatos com efeito, nós de mapa e mecânica de Virtude citados nas
  expansões ficam fora (ver Fora de escopo).
- **R51 — E-24 sem origem dos Orcs.** A Forja Profunda: os Últimos Anões do Reino (Durgrim) forjam para
  o Rei Subterrâneo **em troca de proteção**; o texto não diz de onde vêm os Orcs (G-17 aguarda o dono).

### 2.10 Validação, visibilidade e índice

- **R52 — Lint verde.** `validate_content.py`: 0 ERRO; AVISOs novos explicados na §9.
- **R53 — Nenhum vazamento público.** Nenhum doc público do Codex (`services/codex_loader.load_codex`,
  metadado `visibility == "public"`) contém, sem acento e em minúsculas, nenhuma frase-chave da lista
  `LEAK_PHRASES` (§3.9). O mesmo vale para `data/world/rumor_seeds.json` (`gist`) e `data/bestiary.json`
  (descrições).
- **R54 — Fatos ainda existem (R42).** Para cada grupo de `LEAK_PHRASES`, pelo menos um doc oculto
  contém o fato.
- **R55 — Reindex.** `rag.py` reindexa lore e regras sem erro (precisa de `GOOGLE_API_KEY`; gate do
  lint embutido). Registro na §9: nº de docs/chunks por visibilidade antes e depois.

### Fora de escopo

- **G-14** bestiário (troca das criaturas clichê pelas de `creatures.txt`): spec própria. Exceção única:
  a descrição de `enemy_boss_vibora` (R37, D8).
- **G-05** Hospedeiro de Xylos jogável; Vampiro/Lycan como condição (Cicatriz-carta); Povo-Recife NPC-only.
- **G-02** reescrita de `data/rules.txt`.
- **G-03 / G-04 / C-12** nós e renomeações em `data/world_map.json` e `entities_extra.json` (Dragão
  Bêbado no Anel de Ferro, Salão do Juramento, Forja Profunda/Aelwin como nó, alias "Cidades nas
  Copas", 5 nós novos, `lore_seed` dos nós). Aqui a lore pode **nomear** "Salão do Juramento" e
  "Estaleiro das Almas"; o mapa acompanha na spec do mapa.
- **G-17** origem de Orcs e Goblins (o dono vai detalhar).
- Expansões na gaveta: E-07, E-09, E-17, E-18, E-21, E-22, E-23, E-25.
- Suspeitas abertas: S-01, S-02, S-04, S-05, S-07 (coberta por E-14), S-09 (sem guarda para Magda, por
  decisão), S-10 (coberta por G-08), S-11 (coberta por C-12, no mapa).
- Mecânica citada pelas expansões: quests (`investigar_rumor`, escolta, masmorra), Cartas de Cena e
  inimigas, efeito do artefato do Código (perder Virtude), oferta de posto por Postura, `pact_with`
  dinâmico.
- Rótulo de data por região (Sinos só em Nova Arcádia na UI): D6.
- Novas entradas em `services/secret_signatures.py` para os fatos escondidos aqui: D11.
- `ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml`, `project_index/` (coordenador).

## 3. Design técnico

### 3.1 Arquivos alterados

| Arquivo | O que muda |
|---|---|
| `lore_nova/timeline_completa.txt` | R6, R9–R14, R16–R19, R22–R24, R26–R28, R40; parágrafos novos da Era 0, 1, 6 e 7 |
| `lore_nova/secrets.txt` | R7, R16, R19–R20, R25, R29; blocos novos das expansões ocultas (§3.8) |
| `lore_nova/npcs.txt` | R11, R21, R26, R29–R30, R37, R39–R41; NPCs novos (E-02, E-04, E-01, cinco mestres); "Segredo:" nas expansões de NPC existente (E-11, E-13, E-15, E-16) |
| `lore_nova/factions.txt` | R26, R30–R31, R33–R34, R37–R39; facção "Os Quebrados"; E-05 |
| `lore_nova/locations.txt` | R22, R30, R32, R34, R40; E-12, E-24 (texto público) |
| `lore_nova/races.txt` | R23, R28, R30 |
| `lore_nova/items.txt` | R38 (mantém fato; doc oculto), R40 |
| `lore_nova/creatures.txt` | R40 |
| `lore_nova/rumors.txt` | R44 (Yuan-Ti), R46 (8 blocos) |
| `lore_nova/daily_life.txt` | R45 |
| `scripts/migrate_lore_nova.py` | só a lista `_TIMELINE_HIDDEN_CLUSTERS` (§3.4) |
| `scripts/build_rumor_seeds.py` | `EXPECTED_LORE` 40 → 48 (R46) |
| `data/codex_overrides.yaml` | `art_testamento_real_no_barril: {visibility: hidden}` (R38) |
| `data/graph/edges.json` | R31, R33, R48, E-04 (§3.3) |
| `data/graph/entities_extra.json` | sem mudança (desvio: `world_story` não é tipo registrável; `story_posturas` dispensa entidade) |
| `data/world/rumor_seed_overrides.json` | R43, R44; overrides das 8 sementes novas (`fonte_label`, `gist`, `secret_id`, `public_names`) |
| `data/world/rumor_seeds.json` | regenerado (`build_rumor_seeds.py`) |
| `data/world/festivals.json`, `data/world/calendar.json` | R15, R45 |
| `data/world/lore_quests.json`, `data/artifacts.json` | R36 |
| `data/bestiary.json` | só `enemy_boss_vibora.description` (R37, D8) |
| `data/npc_seed_tables.json`, `data/race_attitudes.json`, `data/world/world_quests.json` | âncoras reapontadas (R4) |
| `data/codex/**` | regenerado pelo migrate + 3 docs curados novos (§3.2) |
| `docs/guias/AUTORIA.md` | R35; uma linha sobre `lore_reanchor.py` no Fluxo C |
| `docs/lore/decisoes-2026-10-27.md` | linha 4: "Aplicadas pela SPEC-348" (sem mudar decisão) |
| testes da 303/307/312/313 citados | só os valores esperados de R15, R45, R46 |

### 3.2 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `data/codex/world_story/story_posturas.md` | R47 (`id: story_posturas` — desvio: o prefixo `story_` isenta o doc de entidade em `test_fase25`; `curated: true`, público) |
| `data/codex/locations/pm_cripta_afogada.md` | R32 (curado, público; segredo de Saelwen fica no NPC) |
| `data/codex/locations/pr_solvhen.md` | E-16 parte pública (curado); a verdade fica em `secrets.txt` |
| `data/codex/locations/ma_forja_profunda.md` | E-24 parte pública (curado); a verdade fica em `secrets.txt` |
| `scripts/lore_reanchor.py` | R4: lê `git diff` de `lore_nova/*.txt` entre dois commits, monta o mapa linha velha → linha nova (`difflib`), reescreve âncoras `arquivo.txt:N` e `arquivo.txt:N-M` nos 6 arquivos de P12 (o 7º é regenerado), e imprime as âncoras que caíram em linha alterada. Modo `--check` sai ≠ 0 se alguma âncora estiver quebrada. Sem LLM, determinístico, LF |
| `tests/test_spec348_leaks.py` | R37–R42, R53–R54 |
| `tests/test_spec348_canon.py` | R6–R36, R43–R51 |
| `tests/test_spec348_anchors.py` | R3, R4, R5 |

`pr_solvhen` e `ma_forja_profunda` já estão em `entities_extra.json` (`:201`, `:1020`); os docs curados
usam o mesmo `id` (Fluxo A do `AUTORIA.md`). Se o lint acusar id duplicado, o executor registra na §9 e
usa o caminho que o lint aceita, sem mudar o lint.

### 3.3 Formatos (exemplos com ids reais)

Bloco de NPC em `npcs.txt` (o split de `migrate_lore_nova.py:430-452` manda "Segredo:" para o doc
`npcs/segredos/<id>_segredo.md`, `hidden`):

```text
[CATEGORIA: NPC]
[TAGS: Velha_Magda, Anel_de_Lama, Mendiga]

VELHA MAGDA — A RATOEIRA
Papel aparente: Vendedora de espetinhos e amuletos no Anel de Lama
Aparência: …

Como identificar (se o jogador prestar muita atenção): … (sem citar a Mão Sombria)

Segredo: Papel real — Líder da Mão Sombria. É a Víbora. …

Segredo: O carrinho é o escritório da Mão Sombria. …
```

Override (`data/codex_overrides.yaml`):

```yaml
art_testamento_real_no_barril:
  visibility: hidden
```

Arestas (`data/graph/edges.json`; `type` de `relation_types.json:2-10`):

```json
{"id": "e_morvan_lidera_cidades", "source": "npc_keeper_morvan", "type": "leads",
 "target": "cidades_estado_sobreviventes_vaelorn_solvhen", "visibility": "public"},
{"id": "e_morvan_em_solvhen", "source": "npc_keeper_morvan", "type": "located_in",
 "target": "pr_solvhen", "visibility": "public"},
{"id": "e_mae_corva_lidera_corvos", "source": "npc_mae_corva", "type": "leads",
 "target": "guilda_corvos", "visibility": "public"},
{"id": "e_sennar_lidera_chama_azul", "source": "npc_sennar_o_pregador_da_cicatriz", "type": "leads",
 "target": "filhos_chama_azul", "visibility": "public"},
{"id": "e_sennar_membro_legiao", "source": "npc_sennar_o_pregador_da_cicatriz", "type": "member_of",
 "target": "legiao_ferro", "visibility": "hidden"}
```

O id exato de NPC novo é o que o migrate gera do cabeçalho (`slugify`); a Etapa 3 confere e ajusta as
arestas. Regra da casa: o `leads` de NPC novo só entra se o NPC tiver doc público.

Doc curado (`data/codex/world_story/posturas.md`), frontmatter:

```yaml
---
id: posturas
type: world_story
name: As Cinco Posturas diante do Abismo
aliases: [Posturas]
tags: [Posturas, Entropia, Carga_do_Abismo]
visibility: public
curated: true
related_entities: [sk_farol_chama_negra, brekmar, druidas_ciclo_cinzento, cultistas_destilacao, na_anel_lama]
---
```

### 3.4 Clusters ocultos da timeline (R3)

Clusters atuais (`migrate_lore_nova.py:234-249`) continuam. Novos, com frases-âncora definidas pelo
executor no texto que escrever (minúsculas, sem acento, únicas no arquivo):

| Cluster | Conteúdo | Era |
|---|---|---|
| propósito do Farol e liturgia | a frase de propósito que sai de `:16` + "o Farol é o que sobrou da liturgia" (R27, R40) | 0 |
| ciclo do guardião | o trecho de `:164-166` sobre o ciclo, já separado do parágrafo dos Cinzéus (R40) | 4 |
| (se preciso) pacto | só se a reescrita de R16 mexer nas frases-âncora atuais | 6 |

O parágrafo público que fica no lugar termina sem explicar ("Para quê, ninguém que ainda viva sabe
dizer.").

### 3.5 Âncoras (`scripts/lore_reanchor.py`)

```text
uso: lore_reanchor.py --base <commit> [--check] [--report <arquivo>]
entrada: git show <base>:lore_nova/<f>.txt × arquivo atual, para cada <f> com diff
saída:   reescreve as âncoras nos arquivos de P12 (exceto rumor_seeds.json, que é regenerado)
         relatório: âncora, linha velha, linha nova, "igual" | "linha alterada" | "linha removida"
```

Linha removida = erro (o executor escolhe a linha certa e registra na §9). Linha alterada = aviso
revisado à mão. O script não decide conteúdo.

### 3.6 Rumores novos (R46)

| Origem | Título (proposta) | Região (tag) | Confiab. | `truth` | `secret_id` |
|---|---|---|---|---|---|
| E-02 | "Um morto ainda varre o crematório" | Nova Arcádia (Setor Leste) | baixa | true (override) | `pacto_valerius` |
| E-04 | "O pregador tem a cicatriz da Legião" | Nova Arcádia | média | true | — |
| E-13 | "O Árbitro de Brekmar tem um número gravado" | Pradaria das Ruínas | média | true | — |
| E-26 Devoto | "Os que velam no gelo pedem para ser escolhidos" | Skallgard | alta | true | — |
| E-26 Sangromante | "Em Brekmar se paga o Éter em sangue, e a Legião queima quem aprende" | Brekmar | alta | true | — |
| E-26 Corruptor | "Há quem cure apodrecendo mais depressa" | Aethelgard | baixa | false | — |
| E-26 Arcanista | "Os druidas cinzentos guardam o que sobrou de Aethelgard" | Pântano da Melancolia | média | true | — |
| E-26 Médico | "A parteira do Anel de Lama ensina a costurar quem a Praga quer" | Nova Arcádia | alta | true | — |

Resultado esperado: 48 sementes `lore`; contagem alta/média/baixa = 16/18/14; falsos (baixa sem
override `true`, menos o guardião de R43, menos E-02) dentro de [0,20; 0,35]. O executor confere a conta
na Etapa 7 e ajusta só confiabilidade dos rumores **novos** se a fração sair da faixa.

### 3.7 Posturas: tabela canônica (R47–R48)

Nomes dos mestres são propostas (D4/D7). "Despreza" = facção hostil, só no texto.

| Postura (`classes.json`) | Diante do Abismo | Tradição de origem | Lugar | Mestre (NPC novo) | Despreza |
|---|---|---|---|---|---|
| Devoto do Abismo | ama | a vigília ao pé do Farol (Nascidos do Gelo que esperam ser escolhidos) e os Cultos do Despertar (`secrets.txt:289`) | `sk_farol_chama_negra` | **Hrefna da Vigília**, Nascida do Gelo que vela ao pé do Farol há décadas | Clãs Tecnológicos (querem o Farol medido, não amado) |
| Sangromante | negocia | sangrinomancia de Brekmar, dos "poucos sangrinomantes" de Kahen (`factions.txt:218-222`) | `brekmar` | **Oriel Talho-Fundo**, sangrinomante de Kahen que ensina a quem paga | Legião de Ferro (magia não registrada vai à fogueira, `factions.txt:20`) |
| Corruptor | trabalha junto | Cultistas da Destilação (Corvane, `factions.txt:521`) | `aethelgard` | **Mairen das Margens**, destiladora que aprendeu com Corvane e o deixou | Druidas do Ciclo Cinzento |
| Arcanista Cinzento | manipula | Druidas do Ciclo Cinzento (Gresh, `factions.txt:438`) e o que sobrou de Aethelgard | `pantano_melancolia` | **Hask, o Musgo**, druida cinzento que guarda instrumentos de Aethelgard | Druidas-Renegados de Saelwen |
| Médico de Campo | nega | os primeiros médicos da Ferrugem do Sangue (`timeline_completa.txt:384`) | `na_anel_lama` | **Benedita, a Parteira** (já existe em `daily_life.txt:70`; vira NPC) | Guilda dos Corvos (vende os marcados) |

Silas Vane aparece em `posturas.md` como o Médico que virou Corruptor (sem o segredo da caixa).

### 3.8 Expansões: ficha canônica e destino

"Público" vai para o bloco gerado público ou doc curado; "oculto" vai para `secrets.txt` (bloco
`SEGREDO`, `secret`) ou parágrafo "Segredo:" de NPC (`hidden`). Nomes marcados * são propostas (D4).

| ID | Fatos canônicos | Destino e visibilidade |
|---|---|---|
| E-01 | O herdeiro da Colina Cinza é **Ilsa*, remendeira de redes no Anel de Lama**, que não sabe. Só Magda sabe, por memória perfeita. A Legião procura "um documento"; a Mão Sombria protege Ilsa sem contar. Proteger a pessoa e destruir o papel são a mesma escolha | NPC Ilsa: papel aparente público; resto em "Segredo:" + bloco em `secrets.txt` (oculto) |
| E-02 | Um servo do décimo ano sobreviveu: **Bertil***, registrado como morto, vive no crematório dos Corvos no Setor Leste. Viu Valerius descer às masmorras na noite do Código e falar com a armadura; não sabe de Daruun | NPC Bertil: aparente público (velho do crematório); "Segredo:" oculto; rumor (§3.6) |
| E-03 | O Código de Ferro original (`art_codigo_de_ferro_original`) tem uma página arrancada: a cláusula do contrato. Corre em leilão clandestino no Mercado de Carne. Quem a lê sente algo se fechar por dentro | `secrets.txt` (oculto). Sem efeito mecânico |
| E-04 | Os Filhos da Chama Azul são pregados por **Sennar, o Pregador da Cicatriz***, ex-legionário treinado por Ress, que viu as sombras se desconectarem. Ainda consta nos rolos da Legião | NPC Sennar: pregador com cicatriz da Legião é público; treinado por Ress e ainda alistado, oculto; arestas §3.3; rumor |
| E-05 | Os Martelos Partidos descobrem que, em greve, o Aço de Sangue "lembra" os que morreram forjando; os Encapuzados da Fornalha adoram exatamente isso. Três lados no Anel de Ferro (Bors, Kald, Thrace) | conflito público em `factions.txt`; o mecanismo (o aço lembra de fato) em `secrets.txt` |
| E-06 | Os marcados resistem à Praga porque carregam a assinatura de Morrakh; os Hospedeiros de Xylos os reconhecem como quase-parentes | `secrets.txt` (oculto); depende de R19 |
| E-08 | A Landship que falta está sob o gelo, tripulação preservada, Éter nunca dispersado, alimentando a Rede Carmesim; a Coroa de Pressão do Rei Anão está a bordo. Os Anões sabem onde e não vão: abrir a escotilha seria admitir a perda. Só Durgrim pode autorizar | `secrets.txt` (oculto); a parte pública é R23 |
| E-10 | R34 | público |
| E-11 | A única coisa que Kahen sente com força é a **vergonha** do número gravado (E-13); Lyss procura isso; Helvira sabe e vende | "Segredo:" de Kahen e de Helvira (oculto) |
| E-12 | No Estaleiro das Almas, o Povo-Recife cobra uma alma por casco; os Sindicatos pagam com marinheiros endividados ("algumas dívidas são fabricadas", `rumors.txt:270`) | público: o estaleiro e o medo dos marinheiros (`locations.txt:331`); a cobrança, oculta em `secrets.txt` |
| E-13 | Kahen foi mercadoria de Groth Algema-Fria; Groth ainda tem o recibo. Por isso os Mercadores de Escravos nunca entram em Brekmar e Kahen compra Cinzéus em silêncio | "Segredo:" de Kahen e de Groth (oculto); rumor público (§3.6) |
| E-14 | O "veneno" de Ophidia é o que as ilhas produzem contra a Praga; mata o organismo e quem o carrega, e quase só humanos o carregam. Os Mercadores de Curiosidades querem as amostras catalogadas | `secrets.txt` (oculto); seed R44 |
| E-15 | A Ampulheta de Vaelorn mede o que resta da cidade; Aerwen troca os próprios anos para virar a areia. Quer que alguém ache quem assume; Illyan não aceita; Morvan é a resposta óbvia e errada | "Segredo:" de Aerwen (oculto); público: "a Senhora de Vaelorn está morrendo de pé" (já é rumor) |
| E-16 | Solvhen é um sonho coletivo sustentado por Solvhara, a Tristeza; Morvan sabe e escolheu não acordar ninguém. Solvhara ganha território fixo | `pr_solvhen.md` público (cidade quieta demais, gente que não lembra de ontem); verdade em `secrets.txt` + "Segredo:" de Morvan e Solvhara |
| E-19 | Morvath, a Decadência, mantém Thessrak vivo nas câmaras submersas: um dragão morrendo devagar é a obra-prima dela. Por isso as ruínas não acabam | `secrets.txt` (oculto) |
| E-20 | O diário em código dos Quebrados (`faction_perspectives.txt:195`) é a prova de que o aprendiz foi herói; publicá-lo destrói a única memória que ainda dá orgulho aos Elfos | `secrets.txt` (oculto); Os Quebrados públicos sem o diário (R33) |
| E-24 | Bigornas quentes da Forja Profunda: os Últimos Anões do Reino (Durgrim) forjam para o Rei Subterrâneo em troca de proteção; a Coroa de Pressão foi reforjada ali (antes de ir para a Landship, E-08: o executor fecha a ordem dos fatos); é porta para o Reino Subterrâneo | `ma_forja_profunda.md` público ("as bigornas estão quentes e ninguém diz quem as alimenta"); verdade em `secrets.txt` |
| E-26 | §3.7 | `posturas.md` + 5 NPCs |

E-08 e E-24 citam a mesma Coroa: a ficha final precisa de uma ordem só (reforjada na Forja, perdida
com a Landship, ou o inverso). O executor escolhe a que fecha com `timeline_completa.txt:480` e registra
na §9.

### 3.9 `LEAK_PHRASES` (teste de R53)

Lista no próprio teste, comparada sem acento e em minúsculas contra o corpo **e** o frontmatter dos
docs públicos. Cada grupo também é procurado nos ocultos (R54).

| Grupo | Frases |
|---|---|
| víbora | "magda e a vibora", "a vibora (velha magda)", "(a vibora)", "lider da mao sombria", "magda/a vibora", "escritorio da mao sombria" |
| barril | "testamento real", "testamento do antigo rei", "herdeiro ao trono", "herdeiro de ostmar" |
| corpos | "vao para o doutor silas vane", "nao vao ao crematorio" |
| farol | "suprime o despertar", "suprimir a rede carmesim", "contem a rede carmesim", "a cada cem anos", "ciclo de 100 anos", "ciclo de cem anos", "mata o guardiao anterior", "matou o anterior", "o abismo cobra vida", "se a chama se apagar", "quando o farol falhara", "resto da liturgia" |
| arauto | "mesma pessoa, dois residuos", "para impedir algo pior", todas de `SECRET_SIGNATURES["arauto_identidade"]` |
| pacto | todas de `SECRET_SIGNATURES["pacto_valerius"]`, "armadura de malagor" junto de "pacto" no mesmo parágrafo |
| praga | "caixa de amostras", "criada em laboratorio", "cepa atual" |
| expansões | por NPC novo com segredo: o doc público não contém os nomes/termos do segredo dele (ex.: Ilsa sem "ostmar"/"herdeir"; Sennar sem "ress"/"alistad"; Kahen sem "groth"/"recibo"/"vergonha"; Solvhen sem "solvhara"/"sonho coletivo"; Forja sem "rei subterraneo"; Volkar sem "rede carmesim") |

## 4. Plano passo a passo

Cada etapa: testes primeiro; rodar só os arquivos da etapa (`bash scripts/dev/py.sh -m pytest <arquivos>
-q --lf -x`, no máximo `-n 2`); suíte completa 1× no pouso, pelo coordenador. Commit por etapa. Nada de
`Read` inteiro em `lore_nova/` ou `data/codex/`: `Grep` + `Read` com offset.

### Etapa 0 — Linha de base e sondas

1. R1: rodar o migrate no worktree limpo; `git status` vazio ou divergência registrada na §9.
2. Confirmar: nome do povo de Ophidia (R44); padrão de designação das Landships (E-08); ids de local de
   §3.7 em `world_map.json`; id que o migrate gera para um cabeçalho de NPC novo (rodar `slugify` num
   cabeçalho de teste); se o lint aceita doc curado com id já em `entities_extra.json` (§3.2).
3. Medir docs/chunks por visibilidade (`load_codex`) para a §9.
4. Guardar o commit base (`git rev-parse HEAD`) para `lore_reanchor.py`.

### Etapa 1 — Testes vermelhos de vazamento e âncoras

1. **Testes** (`tests/test_spec348_leaks.py`):
   - `test_public_codex_has_no_leak_phrases` (R53; falha hoje: lista os docs de P4–P8);
   - `test_hidden_codex_keeps_each_leaked_fact` (R54; passa hoje, guarda contra apagar);
   - `test_seed_gists_and_bestiary_have_no_leak_phrases` (R53);
   - `test_npc_public_docs_have_no_secret_label_paragraphs` (reforça a 7.3 nos NPCs tocados);
   - `test_new_npc_public_docs_hide_their_secret_terms` (grupo "expansões"; vazio até a Etapa 5).
2. **Testes** (`tests/test_spec348_anchors.py`):
   - `test_timeline_cluster_phrases_unique` (R3);
   - `test_all_lore_anchors_resolve_to_nonempty_line` (R4; os 6 arquivos de P12);
   - `test_anchor_keyword_in_line_where_declared` (R4);
   - `test_migrate_is_idempotent` (R5; roda o migrate em `tmp_path` 2× e compara, se já não houver teste
     equivalente; se houver, reusar).
3. Sem mudança de produto. Registrar quais falham (esperado: só o de vazamento).

### Etapa 2 — Vazamentos (C-17…C-21)

1. Editar as fontes de R37–R41 (`npcs.txt`, `factions.txt`, `items.txt`, `locations.txt`,
   `creatures.txt`, `timeline_completa.txt:16` e `:164-166`), override de R38, clusters de §3.4,
   descrição do bestiário (D8).
2. Migrate → lint → `lore_reanchor.py` → testes da Etapa 1 verdes.
3. `tests/test_fase73.py` verde (split de segredo de NPC).

### Etapa 3 — Cronologia, pacto e Praga

1. **Testes** (`tests/test_spec348_canon.py`):
   - `test_era7_public_anchor_has_dates_and_no_hidden_dates` (R6; procura 45/44/41/40/30 escritos como
     o texto usar; nenhuma data de R7 no doc público);
   - `test_hidden_chronology_block` (R7);
   - `test_no_stale_phrases_in_lore_nova` (grep: "Por décadas, Nova Arcádia", "durante a Guerra das
     Cinzas" em `secrets.txt`, "Como sempre faz a cada dois mil anos", "décadas de imersão", "Os seis
     dragões que sobreviveram à guerra — Vorrnak", "GOVERNANTE DE BREKMAR", "dois únicos sobreviventes
     de infecção" sem "não simbióticos", "não é doença natural", "Dia Sem Sombra" no título da Era 5);
   - `test_pact_story_is_hidden_and_single_version` (R16–R18: doc oculto cita Daruun **e** armadura,
     "décimo ano"; nenhum doc público com assinatura de `pacto_valerius`);
   - `test_plague_chain_present` (R19–R20: público cita Morrakh e a primeira onda; oculto cita caixa e
     cepa atual);
   - `test_calendar_year_base_45` (R15) + ajuste dos testes da 307.
2. **Implementação:** R6–R21 nas fontes; `calendar.json`.
3. Migrate → lint → reanchor → testes.

### Etapa 4 — Mundo, facções e grafo

1. **Testes** (`test_spec348_canon.py`):
   - `test_world_fixes_present` (R22–R28: frases-chave de cada uma no doc certo e na visibilidade certa);
   - `test_kahen_title_arbitro` (R30);
   - `test_graph_new_leads_and_located_in` (R31, R33: arestas existem, tipos válidos, alvos existem);
   - `test_cidades_keep_living_leader_when_aerwen_dies` (R31: projection com `npc_lady_aerwen` morta →
     `npc_world.leaders()` ainda tem líder vivo para a fação; usar o helper de NPC vivo que o motor usa);
   - `test_quebrados_faction_public_without_diary` (R33, E-20);
   - `test_autoria_declares_mundo_vivo_canon` (R35);
   - `test_delivery_route_uses_vorr_ingot` (R36; `test_spec313_catalog.py` continua verde).
2. **Implementação:** R22–R36 nas fontes, `edges.json`, `artifacts.json`, `lore_quests.json`,
   `AUTORIA.md`, codex curado da cripta (R32).
3. Migrate → lint → reanchor → testes.

### Etapa 5 — Expansões

1. **Testes** (`test_spec348_canon.py`):
   - `test_each_expansion_has_canonical_text` (R50: para cada E-xx da §3.8, 1–3 frases-chave no doc de
     destino com a visibilidade da tabela);
   - `test_forja_text_does_not_explain_orcs` (R51);
   - grupo "expansões" de `test_new_npc_public_docs_hide_their_secret_terms` preenchido.
2. **Implementação:** texto da §3.8 nas fontes; docs curados `pr_solvhen.md`, `ma_forja_profunda.md`;
   arestas de Sennar. Registrar na §9 a ordem escolhida para a Coroa (E-08 × E-24).
3. Migrate → lint → reanchor → testes.

### Etapa 6 — Posturas

1. **Testes** (`test_spec348_canon.py`):
   - `test_posturas_doc_curated_public_and_complete` (R47: as 5 chaves de `classes.json`, cada uma com
     verbo, lugar, mestre, facção hostil e rumor);
   - `test_posturas_masters_are_graph_npcs` (R48: cada mestre é entidade com `member_of`/`located_in`
     válidos; nenhum `enemy_of` novo);
   - `test_posturas_no_mechanics_no_forbidden_terms` (R49: sem dígito, sem "carta", sem termo
     `[proibidos]`);
   - `test_new_texts_no_forbidden_lexicon` (varre `posturas.md`, docs curados novos e os blocos novos
     de `lore_nova/` desta spec, identificados por diff contra o commit base).
2. **Implementação:** `posturas.md`, 5 NPCs em `npcs.txt`, `entities_extra.json` (`posturas`), arestas.
3. Migrate → lint → reanchor → testes.

### Etapa 7 — Dados de mundo e rumores

1. **Testes**:
   - `test_guardian_rumor_true` (R43) e `test_false_ratio_in_range` (reusa a conta da 312);
   - `test_ophidia_seed_west_and_no_yuan_ti` (R44);
   - `test_festivals_named_and_approved` (R45: nome da véspera, `label`, `review == "aprovado"`,
     `lore_refs` na seção nova de `daily_life.txt`) + ajuste dos testes da 303/307;
   - `test_new_rumor_seeds_enabled_with_regions` (R46) + `EXPECTED_LORE` e distribuição da 312.
2. **Implementação:** `rumors.txt`, `daily_life.txt`, `festivals.json`, overrides, `EXPECTED_LORE`,
   `build_rumor_seeds.py` (regera), `--check`.
3. `tests/test_spec312_*.py`, `test_spec313_*.py`, `test_spec303_*.py`, `test_spec307_*.py`,
   `test_spec306_npc_seed_expansion.py`, `test_spec297_*.py` verdes (só esses arquivos, `-n 2`).

### Etapa 8 — Reindex e registro

1. `bash scripts/dev/py.sh rag.py` (lint embutido; precisa de `GOOGLE_API_KEY`). Sem chave: registrar
   `MODEL_HANDOFF_REQUIRED` para o coordenador rodar, sem marcar R55.
2. Registrar na §9: docs/chunks por visibilidade antes × depois; números de R8; AVISOs do lint.
3. `docs/lore/decisoes-2026-10-27.md:4` → "Aplicadas pela SPEC-348".

### Etapa 9 — Revisão independente

Revisor Opus lê o diff de `lore_nova/` contra as decisões (sem reabrir) e o tom, roda os testes da spec,
e escreve `handoffs/SPEC-348-review.md`. P0/P1 corrigidos antes do pouso.

## 5. Critérios de aceite

- [ ] R1–R5: linha de base do migrate limpa (ou registrada), clusters únicos, âncoras resolvem, migrate
      idempotente, `build_rumor_seeds.py --check` verde
- [ ] R6–R15: âncora de 45 anos pública e datas ocultas separadas; frases velhas fora de `lore_nova/`;
      `YEAR_BASE` 112 mantido, contagem do Protocolo explicada na Era 7
- [ ] R16–R21: pacto em uma versão em camadas, oculto; Praga em cadeia única; Vane "não simbióticos"
- [ ] R22–R36: mundo, facções, grafo (Morvan, Mãe Corva, Sennar), lingote de Vorr, `AUTORIA.md`
- [ ] R37–R42 e R53–R54: zero frase de `LEAK_PHRASES` em doc público, semente ou bestiário; todo fato
      movido segue em doc oculto
- [ ] R43–R46: guardião `truth: true`; Ophidia no oeste e sem Yuan-Ti; calendário e festas na lore;
      48 sementes, nenhuma nova desabilitada, fração de falsos na faixa
- [ ] R47–R49: `posturas.md` completo, 5 mestres no grafo, sem mecânica nem termo proibido
- [ ] R50–R51: texto canônico de todas as expansões aprovadas no destino e visibilidade da §3.8
- [ ] R52: `validate_content.py` 0 ERRO
- [ ] R55: reindex feito e registrado na §9
- [ ] `uv run pytest` verde (suíte completa offline, no pouso)
- [ ] Saves antigos carregam (nenhum campo de estado muda; rota `minerio_skallgard_brekmar` mantém o id;
      quest aberta com `minerio_ferro` continua resolvendo, ver §7)
- [ ] Revisão independente Opus sem P0/P1 (`handoffs/SPEC-348-review.md`)
- [ ] Smoke real (§6) executado e registrado na §9

(Não há `with_structured_output` novo: o item de guard de FallbackLLM do template não se aplica.)

## 6. Smoke test com LLM real

Pré-requisito: reindex da Etapa 8 feito; `GOOGLE_API_KEY` para embeddings; DeepSeek nas `ROUTES`. Teto:
US$ 0,50. O MockLLM não usa o FAISS real nem a prosa real; só o índice novo mostra se um chunk público
ainda entrega um segredo.

1. **RAG público (sem LLM de texto):** `query_rag(q, "lore", None, max_visibility="public")` para 6
   perguntas: "quem é a Víbora?", "o que Grum guarda no barril?", "para onde a Guilda dos Corvos leva os
   corpos marcados?", "para que serve o Farol da Chama Negra?", "quem é o Eco do Aprendiz?", "com quem
   Valerius fez o pacto?". Assertar: nenhum chunk devolvido contém frase de `LEAK_PHRASES`.
2. **RAG positivo:** "há quantos anos foi a Guerra do Céu Vermelho?" devolve o chunk da âncora (45);
   "o que é um Sangromante em Valoria?" devolve `posturas`.
3. **Narrador real:** `uv run python -m playtest run --profile secret_rusher --turns 10 --real
   --max-cost 0.30 --seed 348`. Assertar: `mock=False`; 0 violação `error` (inclui
   `knowledge.secret_leak`); no transcrito, nenhuma frase de `LEAK_PHRASES` na narração.
4. **Postura na narração:** 3 turnos reais com personagem Médico de Campo em `na_anel_lama`, ação
   "procuro quem ensina a costurar feridas da Praga": a narração cita Benedita ou a tradição sem número
   nem carta. Leitura humana de tom (crônica cansada, sem termo proibido) registrada na §9.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo de estado muda. `YEAR_BASE` não muda (D1). Quest de entrega já aberta guarda o `item_id` antigo na instância: a Etapa 4 confere se a
  resolução lê o item da instância ou da rota; se ler da rota, manter `minerio_ferro` aceito como
  alternativa nessa rota (registrar na §9).
- **Ids de doc da timeline mudam** quando a primeira frase de um trecho muda (P20). Nada fora do Codex
  os referencia; o lint pega `related_entities` órfão.
- **Âncoras:** 237 referências por linha (P12). Sem o `lore_reanchor.py`, cada edição em `lore_nova/`
  quebra testes da 297/303/306/307/313 longe desta spec. O script é a mitigação; o `--check` fica no
  teste.
- **Motor de mundo:** três `leads` novos mudam `npc_world.leaders()` e `world_engine._leaders()` (dict
  npc → fação, aceita dois líderes por fação). Simuladores da 302 podem ter baseline com 21 líderes; se
  algum teste fixar a contagem, atualizar o valor e registrar.
- **MockLLM / FallbackLLM:** sem caminho novo de LLM. O MockLLM não lê o FAISS real; daí o smoke §6.
- **Quota/latência:** reindex completo de embeddings (~700 docs) consome a quota de embedding do Gemini
  uma vez; nenhum custo por turno.
- **Volume de texto:** a spec escreve muito texto novo. Tudo passa pelo lint, pelo teste de léxico e
  pela revisão de tom; o dono pode editar qualquer frase depois sem reabrir as decisões.

## 8. Decisões que o dono precisa tomar

As decisões de 27/10 não são reabertas. Estas são só as escolhas de aplicação que elas deixaram abertas;
cada uma tem um default que o executor segue se o dono não disser nada antes do `approved`.

> **Respostas do dono (27/10):** D1 e D4 decididos (abaixo); D2, D3 e D5 aprovados como default;
> D6–D12 sem objeção, seguem o default.

- **D1 — Ano corrente. DECIDIDO (dono, 27/10):** manter `YEAR_BASE` 112; o Ano 1 é o início do
  Protocolo dos Anões, herdado por Nova Arcádia (ver R15).
- **D2 — Rumores novos.** +8 sementes (§3.6) e atualizar as contagens fixas da SPEC-312. Default: sim.
  Alternativa: nenhuma semente nova; os rumores ficam só como texto nos docs.
- **D3 — Alcance de C-20.** A Rede Carmesim como fenômeno segue pública (Cristal-Sanguíneo, Câmara do
  Sinal, ~30 trechos); o que fica oculto é a ligação Farol → Rede, o ciclo do guardião e o propósito do
  Farol. Default: assim. Alternativa: esconder a Rede inteira (exige reescrever ~35 trechos e tornar
  `mon_rede_carmesim` oculto).
- **D4 — Nomes. DECIDIDO (dono, 27/10):** "Reino da Colina Cinza" (nome do dono; substitui Ostmar; Rei
  sem nome próprio, Teodric recusado); aprovados Ilsa, Bertil, Sennar e os mestres das Posturas. Texto
  original: Ilsa, a herdeira (E-01); Bertil, o
  servo (E-02); Sennar, o pregador (E-04); o último árbitro do Fogo Alto foi um Gigante (G-09).
  Default: usar esses nomes.
- **D5 — Cola da Praga.** A primeira onda brotou há 30 anos das minas e fundições onde o sangue de
  Malagor encharcou a terra (mesmo ano do Código). Default: sim.
- **D6 — Sinos.** "Sinos só em Nova Arcádia" entra só na lore agora; o rótulo de data por região na UI
  fica para spec futura. Default: sim.
- **D7 — Mestres.** Cinco NPCs novos e acessíveis (Benedita promovida a NPC); Volkar, Corvane e Gresh
  ficam como origem da tradição, não como mestres. Default: sim.
- **D8 — Bestiário da Víbora.** Editar só a descrição de `enemy_boss_vibora` aqui, mesmo com G-14 fora.
  Default: sim.
- **D9 — Liturgia do Farol.** "O Farol é o resto da liturgia" fica oculto, para casar com C-20. Default: sim.
- **D10 — Calendário aprovado.** Todas as 14 festas passam a `review: "aprovado"`. Default: sim.
- **D11 — Assinaturas de segredo.** Assinaturas novas (Víbora, barril, corpos, Farol) em
  `services/secret_signatures.py` ficam para uma spec de runtime. Default: fora desta spec.
- **D12 — Nome do salão.** A lore passa a dizer "Salão do Juramento" antes de o mapa trocar "Salão do
  Jarl". Default: sim (a divergência dura até a spec do mapa).

## 9. Registro de execução

Pipeline de regeneração usado (e documentado no `AUTORIA.md`): `migrate_lore_nova.py` + `gen_world_living_npcs.py` + `validate_content.py` + `lore_reanchor.py --base <commit anterior>` (1× por etapa, nunca repetir com a mesma base).

- **Linha de base (R1):** `migrate` sozinho derrubava as 36 entradas `mundo_vivo` de `entities.json`/`edges.json` (são recolocadas por `gen_world_living_npcs.py`). Com o gerador depois do migrate, diferença de conteúdo = 0 (só CRLF do Windows, normalizado no `git add`). Nada manual se perdeu.
- **Sondas (Etapa 0):** o povo de Ophidia não tem nome na lore (só "Yuan-Ti" no rumor) -> "os de Ophidia". Landships: padrão `LS-PFC-n` (Durrak saiu da 7); a que falta é a `LS-PFC-9` (oculto). Ids de NPC = `npc_` + slug do trecho antes do "—" (sem "—" entra o título todo; por isso `ILSA — A REMENDEIRA` -> `npc_ilsa`). Lint aceita doc curado com o mesmo id de `entities_extra`.
- **Codex antes -> depois:** 699 -> 745 docs; chunks 2239 -> 2389 (public 2017->2102, hidden 135->165, secret 87->122).
- **R8 números conferidos:** `npcs.txt` 22 ("vinte anos seguintes": ok; servos agora "constam como mortos"), 53/Magda (15 anos, 44-29 atrás), 72 Vane (18 anos; "não simbióticos"), `secrets.txt` 26/30 (18 anos, caixa há 15), `factions.txt` Mão Sombria (15) e Corvos (acordo de 30 anos saiu do público), `faction_perspectives:9` Ress (15 anos, ok), `rumors:226` (avó há 30), `daily_life:79` Benedita (primeiros casos "dois anos atrás" -> "casos deixaram de ser raros há dois anos", para não colidir com a cadeia da Praga).
- **Coroa de Pressão (E-08 × E-24):** reforjada na Forja Profunda (depois da queda do Reino) -> embarcou na LS-PFC-9 -> perdida no gelo na guerra contra os dragões (casa com a linha da Landship perdida em `timeline_completa`).
- **Desvios:** (1) `story_posturas` no lugar de `posturas` e sem entrada em `entities_extra` (`test_fase25` exige entidade para doc não-`story_`). (2) `test_fase25`: as duas asserções passaram a usar `entities.json ∪ entities_extra.json`, como o lint (Fluxo A do AUTORIA). (3) Ophidia ficava a LESTE na Era 3/6 da timeline, a OESTE em `locations`/`creatures`: timeline corrigida para oeste; o mar leste só invade o lago de Aethelgard. (4) Benedita não tem facção de origem (sem `member_of`); só `located_in`. (5) `year_review` do calendário passou a `aprovado`. (6) Etapas 2 e 3 foram editadas e commitadas juntas. (7) A lore diz "Lista de Fornalha" também no `locations.txt` (Jardins). (8) `lingote_aco_vorr` com `lore_ref` `items.txt:26-28` (a linha de "Liga de Vorr (Aço Azulado)"; "Aço de Vorr" não existe literal).
- **Compat. de saves (§7):** a quest de entrega guarda `item_id` na instância (`anchor`), então quest aberta com `minerio_ferro` continua resolvendo; não foi preciso aceitar os dois itens.
- **Pendências fora do escopo:** `data/world_map.json` `lore_seed` do Farol ainda diz "suprime ... a cada cem anos" (vazamento no mapa; spec do mapa). `ma_forja_profunda`, `pr_solvhen`, `pm_cripta_afogada` ganharam doc, mas o nome do nó "Salão do Jarl" segue.
- **R5/R52:** `validate_content.py` 0 ERRO / 0 AVISO; `build_rumor_seeds.py --check` verde; 48 sementes lore (16/18/14), fração de falsos dentro de [0,20; 0,35].
- **Reindex (R55) e smoke §6: MODEL_HANDOFF_REQUIRED.** `rag.py` falhou na chave de embedding do checkout principal: `402 RESOURCE_EXHAUSTED — prepayment credits are depleted` (1ª tentativa teve também SSL EOF). Nenhum índice FAISS foi alterado. O coordenador precisa repor créditos do Gemini e rodar `bash scripts/dev/py.sh rag.py` e o smoke da §6 (RAG público x `LEAK_PHRASES`, `secret_rusher` real, Médico de Campo). R55 e o smoke seguem desmarcados.
- **Testes:** `pytest tests/test_spec348_*.py tests/test_spec31[23]*.py tests/test_spec30[367]*.py tests/test_spec297*.py tests/test_spec306*.py tests/test_fase2*.py tests/test_fase3*.py tests/test_fase44.py tests/test_fase7*.py` = 890 passed, 13 skipped; spec348 isolado = 66 passed. `ruff` limpo nos arquivos novos.
