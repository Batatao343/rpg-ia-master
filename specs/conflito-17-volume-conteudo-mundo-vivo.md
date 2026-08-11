# SPEC — Conflito v2 #17: Volume de Conteúdo — Mundo Vivo (Cartas, Bestas, NPCs)

> **Status:** `done`
> **Criada:** 2026-07-23 · **Atualizada:** 2026-08-02
> **Depende de:** `conflito-14` (`done` — Cartas + gerador), `conflito-15`
> (`done` — bestiário v4 + migração), `npcs-3-camadas` (`done` — traits/gate/
> layers). Idealmente DEPOIS do `conflito-13` (cutover), pra autorar contra o
> motor vivo e medir com o playtest novo — mas o grosso da autoria não depende
> do cutover (usa os mesmos geradores).
> **Desbloqueia:** mundo mais denso/rejogável; tabelas de encontro por região
> cheias; elenco de NPCs por região.
> **Épico:** Migração do Sistema de Conflitos de Valoria (fast-follow de conteúdo)
> **Nota:** pedido explícito do usuário (2026-07-23) — "preciso de volume alto de
> Cartas, bestas e NPCs pro mundo ficar bem mais vivo". Spec de ESCALA: 14/15
> entregaram a fundação mínima jogável; esta multiplica o conteúdo.

---

## 1. Contexto & Objetivo

> **Aprovação para execução:** 2026-08-02 — o usuário pediu a execução das
> specs abertas em ordem; esta é a próxima após o fechamento da `conflito-16`.

`conflito-14`/`15` entregaram a **fundação jogável**: 80 Cartas (16/classe), 84
criaturas migradas + 18 Cartas de inimigo, 10 arquétipos táticos. É suficiente pra
o cutover e o smoke, mas ainda é **raso** pra um mundo vivo: cada subclasse tem só
~3 Cartas próprias, várias regiões de Valoria têm poucas criaturas, e o elenco de
NPCs nomeados por região é fino. Rejogar sente repetição.

Esta spec é **autoria em ESCALA** — o mesmo padrão de "motor primeiro, depois
autoria dedicada" (`arvores-habilidade-classes`), agora aplicado a VOLUME, com
três frentes independentes que podem correr em lotes:

1. **Cartas** — aprofundar o Acervo (mais opções por patamar/subclasse; mais
   Cartas de inimigo pra variedade tática).
2. **Bestas** — encher as tabelas de encontro por região; criaturas novas
   ancoradas na lore, não reskin de dano (R8 da 15).
3. **NPCs** — elenco nomeado por região (3 camadas: traits seeded / gate in_scene
   / view da API), com relações e ganchos.

Princípio (ROADMAP § Princípios): **conteúdo é dado, mecânica é Python**. Nada
aqui muda motor — só popula `data/` no schema já validado, com geradores/curadoria
e **guardas de variedade** que impedem reskin.

## 2. Requisitos

### Cartas
- **R1** — Acervo por subclasse cresce de ~3 → **≥5 Cartas próprias** por
  combinação classe×subclasse (15 combos), cobrindo os 3 patamares (inicial/
  avançado/superior), sem furos de patamar (cada combo tem ≥1 Carta superior).
- **R2** — Cada classe ganha **≥2 Cartas de reação** e **≥2 utilitárias** novas
  (hoje o roster de reação/utilitária é escasso). Total de Cartas de jogador
  alvo: **≥150** (de 80).
- **R3** — Cartas de inimigo (`data/cards/bestiario.json`) crescem de 18 → **≥40**,
  cobrindo os 10 arquétipos com variedade (não 1 assinatura repetida) + Cartas
  temáticas por elemento/região.
- **R4** — **Guarda de variedade** (anti-reskin, R8/R10 de 14/15): nenhum par de
  Cartas ativas pode ter a MESMA assinatura de efeito (kind + valor/dano_base +
  frequência + custo) sem diferença de papel — teste que falha em duplicata pura.

### Bestas
- **R5** — Toda região com encontros no `world_map.json` tem uma **tabela de
  encontro viável**: **≥6 criaturas** associadas via `regions`, distribuídas em
  categorias (pelo menos 1 lacaio + 1 elite/chefe). Medir cobertura por região.
- **R6** — **≥40 criaturas novas** ancoradas na lore de Valoria (nome/descrição/
  região coerentes com o Codex), migradas pro schema v4 no mesmo passo (reusar
  `migrate_bestiary_v4`), cada uma com Virtudes/Vitalidade/categoria/perfil
  tático/≥1 Carta assinatura oculta. Total alvo: **≥120 criaturas**.
- **R7** — **Guarda de variedade de bestas:** nenhuma criatura nova pode ser
  cópia de perfil+cartas+resistências de outra do mesmo arquétipo sem diferença
  temática — teste de dedupe por assinatura.

### NPCs
- **R8** — Cada região MAIOR de Valoria (as com hub no mapa) tem **≥3 NPCs
  nomeados curados** no Codex (`data/codex/**/npc`), com as 3 camadas
  (`npc_layers`): traits seeded (`data/traits.json`), `home_location_id`,
  papel/fação, e ≥1 gancho de missão ou segredo (`hidden`/`npc_secret` da 7.3
  quando couber).
- **R9** — Elenco alvo: **≥30 NPCs nomeados** novos (de +/− os já existentes),
  com relações (`data/graph/edges.json`) que os conectam a fações/locais.
- **R10** — NPCs seguem a autoria da Fase 7 (`docs/AUTORIA.md`): passam no lint
  (`scripts/validate_content.py` — frontmatter/ids/refs/visibility), sem vazar
  segredo em doc `public`.

### Medição (transversal)
- **R11** — **Relatório de cobertura** (`scripts/content_report.py` ou teste que
  imprime): Cartas por classe/subclasse/patamar; criaturas por região/categoria/
  arquétipo; NPCs por região. Serve pra saber ONDE ainda falta volume e provar os
  alvos R1/R3/R5/R6/R8.

### Fora de escopo

Motor de Cartas/combate/NPC (14/15/08/npcs-3-camadas — todos `done`); UI
(`conflito-16`); geração em runtime via LLM (`conflito-11`); rebalanceamento fino
dos números `[BALANCEAR]` de classe (spec própria); lore NOVA de mundo (isto usa a
lore existente do Codex, não inventa regiões).

## 3. Design técnico

**Arquivos alterados/novos:**
- `scripts/gen_cards_v4.py` — estender a fonte autoral (mais Cartas por combo +
  reações/utilitárias). Mantém o schema/geração já validados.
- `scripts/migrate_bestiary_v4.py` — ganha um **catálogo de criaturas NOVAS**
  (fonte autoral: nome/tipo/região/descrição/attributes) que entram no
  `data/bestiary.json` pela MESMA pipeline de migração (inferência de arquétipo/
  Virtudes/Cartas). Ampliar `ENEMY_CARDS` (R3) e `TEMA_CARTA`/`TEMA_RESIST`.
- `data/codex/**/npc/*.md` — NPCs curados novos (frontmatter `id/type:npc/tags/
  visibility`), + `data/traits.json` (se precisar de traços novos) +
  `data/graph/edges.json` (relações). Reindex do Codex (`uv run python rag.py`).
- `services/content_validator.py` — **guardas de variedade** (`validate_cards`/
  `validate_bestiary` ganham dedupe por assinatura, R4/R7) + cobertura mínima por
  região (R5). Já valida campos; aqui acrescenta as regras de VOLUME/variedade.
- `scripts/content_report.py` (novo) — imprime a matriz de cobertura (R11).
- `tests/test_conflito_volume_conteudo.py` (novo) — asserts dos alvos.

**Assinatura de variedade (R4/R7):** função pura
`effect_signature(card) -> tuple` = `(kind, dano_base|valor, frequencia, custo,
alvo)`; duas Cartas ativas com a MESMA tupla E mesma classe/arquétipo E sem
`descricao` distinta o suficiente = duplicata. Para bestas:
`creature_signature(cre) = (arquetipo, tuple(sorted(cartas)), tuple(resist),
tuple(virtudes))`.

**Cobertura por região (R5):** ler `data/world_map.json` (nós com encontro) ×
`data/bestiary.json` (`regions`) → dict `regiao -> {categorias presentes,
n_criaturas}`; falha se alguma região de encontro tiver < 6 ou faltar
lacaio+elite/chefe.

## 4. Plano passo a passo

Três frentes independentes; podem correr em lotes/sessões separadas. Cada frente
é TDD (guarda de volume/variedade primeiro, autoria depois).

### Etapa 1 — Guardas de volume/variedade + relatório (habilita medir)
1. **Testes** (`tests/test_conflito_volume_conteudo.py`):
   `test_relatorio_de_cobertura_roda`; `test_variedade_cartas_sem_duplicata_pura`
   (R4); `test_variedade_bestas_sem_clone` (R7). Começam medindo o estado ATUAL
   (podem começar xfail/threshold baixo e subir conforme a autoria avança).
2. **Implementação:** `scripts/content_report.py` + `effect_signature`/
   `creature_signature` em `content_validator`.

### Etapa 2 — Cartas em escala (R1/R2/R3)
1. **Testes:** `test_cada_combo_tem_5_cartas_proprias`;
   `test_cada_classe_tem_2_reacoes_e_2_utilitarias`;
   `test_total_cartas_jogador_min_150`; `test_cartas_inimigo_min_40`.
2. **Implementação:** estender `gen_cards_v4.py` + `ENEMY_CARDS`; regenerar;
   `validate_cards` verde.

### Etapa 3 — Bestas em escala (R5/R6/R7)
1. **Testes:** `test_toda_regiao_de_encontro_tem_6_criaturas`;
   `test_total_criaturas_min_120`; `test_criaturas_novas_ancoradas_em_regiao`.
2. **Implementação:** catálogo de criaturas novas em `migrate_bestiary_v4.py`
   (por região, ancorado no Codex); rodar migração; `validate_bestiary` verde.

### Etapa 4 — NPCs em escala (R8/R9/R10)
1. **Testes:** `test_cada_regiao_maior_tem_3_npcs`;
   `test_total_npcs_nomeados_min_30`; `test_npcs_passam_no_lint` (reusa
   `validate_all` — sem vazar segredo).
2. **Implementação:** NPCs curados no Codex + traits + edges; reindex do RAG.

### Etapa 5 — Fechamento
1. Relatório de cobertura provando R1/R3/R5/R6/R8.
2. `uv run pytest` verde; `scripts/validate_content.py` 0 erros.

## 5. Critérios de aceite

- [x] Cartas: ≥5 próprias/combo (15 combos), ≥2 reações + ≥2 utilitárias/classe,
  total ≥150 jogador + ≥40 inimigo; guarda de variedade passa (R1-R4).
- [x] Bestas: toda região de encontro com ≥6 criaturas (lacaio+elite/chefe),
  total ≥120, novas ancoradas na lore; guarda de variedade passa (R5-R7).
- [x] NPCs: ≥3 nomeados/região maior, total ≥30 novos, todos no lint sem vazar
  segredo (R8-R10).
- [x] `scripts/content_report.py` imprime a matriz de cobertura (R11).
- [x] `uv run pytest` verde (suíte completa offline) + `scripts/validate_content.py`
  0 erros.
- [x] Nenhum motor tocado (só `data/` + geradores + validador/relatório).

## 6. Smoke test com LLM real

Conteúdo é estático (N/A pra geração). O smoke REAL é de **experiência**: rodar o
playtest longo (`playtest run`, pós-cutover) por 2-3 regiões e conferir que
(a) os encontros variam (não repetem a mesma criatura), (b) Cartas de inimigo
ocultas diferentes aparecem, (c) NPCs nomeados novos entram em cena com ganchos.
Julgar pelo `transcript`.

## 7. Riscos & compatibilidade

- **Saves antigos:** conteúdo aditivo (novas Cartas/criaturas/NPCs) não quebra
  saves; criatura removida quebraria referência — só ACRESCENTAR, nunca remover
  ids existentes.
- **RAG:** NPCs novos exigem reindex do Codex (`uv run python rag.py`); Jina free
  tier = 100k tokens/min (espaçar re-index grande).
- **Overlay runtime:** autorar só nos arquivos CURADOS (`data/bestiary.json`,
  `data/codex/**`), nunca em `data/runtime/` (isolar-cache-runtime).
- **Reskin (o risco central do pedido):** os guards de variedade (R4/R7) são a
  trava — o volume não pode virar cópia com número trocado. Se um lote falhar o
  guard, é sinal de que a autoria precisa de ideia, não de mais dano.
- **Escopo grande:** as 3 frentes são independentes — entregar em lotes (ex.: uma
  região por vez) é aceitável; a spec só vira `done` quando os alvos numéricos
  batem, mas o progresso é incremental e sempre verde.

## 8. Evidências de execução (2026-08-02)

- Resultado: **153** Cartas de jogador, **40** de inimigo, **124** criaturas
  (40 novas) e **36** NPCs novos — três em cada um dos 12 hubs.
- As 15 subclasses têm 5–6 Cartas próprias e ao menos uma Superior; cada classe
  ganhou ≥2 Reações e ≥2 Utilitárias. O gerador agora falha em colisão de ID.
- `effect_signature` e `creature_signature` foram incorporadas ao lint; cobertura
  regional também é gate. Ophidia passou de 3 para 7 criaturas e ganhou toda a
  escada Lacaio/Padrão/Elite/Chefe.
- NPCs vivem em `data/codex/npcs/mundo_vivo`, com entidade canônica e aresta
  `located_in`. Reindex Jina: 2.239 chunks; busca pelo lote novo confirmada.
- Lint: **0 erros/0 avisos**. Suíte: **1358 passed, 1 skipped, 14 deselected**.
- Smoke real aceito: `20260803-025211-710980`, 3/3 turnos, 4 locais/3 regiões,
  `mock=false`, zero erro/violação, custo US$ 0,010528; smoke direcionado carregou
  `mon_guardiao_basalto` com Cartas regionais e `Brunna Ponte-Alta` pela rota NPC.
- Relatório detalhado: [`docs/content-coverage-2026-08-02.md`](../docs/content-coverage-2026-08-02.md).
