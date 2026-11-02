# SPEC-360 — Criaturas vivas no mundo: sinal antes da luta, ecologia determinística, tramas e telegrafo visível (guarda-chuva; Fase 1 executável)

> **Status:** `in-review`
> **Criada:** 2026-11-01 · **Atualizada:** 2026-11-02
> **Depende de:** SPEC-349 onda 1 (Nova Arcádia) na `main`: fichas `data/bestiario/fichas/nova_arcadia.yaml`, entradas `mon_*` no `data/bestiary.json` e `curadoria_legado.yaml`. Também SPEC-312 (sementes de rumor, `done`), SPEC-303 (calendário, `done`), SPEC-302/304 (motor de mundo e hooks diários, `done`) e Fase 6.3/6.4 (`services/ecology.py`, `resolve_track`). As filhas têm dependências próprias (§3.10).
> **Desbloqueia:** filhas 360-B (backfill das 11 regiões + legado), 360-C (saber do jogador: telegrafo e contra-jogo) e 360-D (criaturas de trama). Também a SPEC-361 (criatura gerada em runtime), que deve emitir o mesmo bloco de fauna.
> **EXECUTOR_MODEL:** Opus (`claude-opus-5-5`) para a autoria do bloco de fauna (sinais, cadeia alimentar, reações); `Terra` para schema, lint, motor, integração e eval. Fable nunca (dono, 28/10). **REVIEW_MODEL:** revisor de fauna independente (`spec-reviewer`, Opus, nunca o autor) e `Sol` técnico (motor, estado, determinismo, integridade de eval). **REVIEW_REQUIRED:** `true`.

---

## 1. Contexto & Objetivo

**O que o dono decidiu (01/11, não reabrir).** As ~280 criaturas novas da SPEC-349 (12 regiões) e os ~90 inimigos legados de Valoria precisam parecer **vivos** no mundo, e não só mais numerosos. São quatro pilares:

1. **Sinal antes da luta.** Rastro, marca, som, cheiro, corpos e restos, rumor de morador e testemunha. O encontro é anunciado, e o jogador pode se preparar, evitar ou caçar.
2. **Ecologia.** Quem caça quem, quem foge de quem, território, horário, estação e reação ao que o jogador fez na região. Tudo determinístico; a LLM não decide regra.
3. **Ligação com as tramas** da SPEC-350: criaturas que pertencem a uma trama aparecem quando ela avança.
4. **Telegrafo e contra-jogo visíveis**, no presságio (SPEC-329), na narração de aproximação e num registro de conhecimento. A luta ensina.

**Contagem verificada** (`Grep "^  - id: "` nas fichas de cada worktree): Nova Arcádia 27, Pântano 22, Aethelgard 25, Brekmar 20, Costa Negra 22, Deserto de Zhur 26, Floresta dos Sussurros 25, Montanhas Afiadas 27, Ophidia 20, Pradaria das Ruínas 22, Selva de Xylos 22, Skallgard 23, ou seja, **281 fichas**. O legado `classe: valoria` soma **88** (`data/bestiario/curadoria_legado.yaml`, branch `spec-349`). Nenhuma ficha `status: retro` existe ainda, então o legado não tem ficha.

**Problemas, com evidência:**

| # | Problema | Evidência |
|---|---|---|
| P1 | O encontro de fauna vira combate **no mesmo turno** em que o gatilho dispara, sem sinal anterior. O texto de chegada é genérico | `world_utils.py:1211-1268` (`check_encounter`: `looming_threat` e `high_danger` devolvem o encontro direto); `:1265` ("O perigo de {region} se materializa: algo hostil avança sobre você."); `agents/storyteller.py:1601-1615` (`COMBAT START. {flavor}`) |
| P2 | O "rastro" que já existe é um tipo de encontro sorteado (30 % em perigo baixo). Ele **nomeia** a criatura e não se liga a nenhum encontro futuro | `world_utils.py:1496-1497` (tabela de tipos); `:1661-1669` (`resolve_track`: "Rastros frescos de {name}") |
| P3 | A ecologia atual é só pressão de caça, fação dominante e migrante. Não há predador e presa, horário, território nem reação a evento do mundo | `services/ecology.py:1-14`, `:29-42`, `:91-116`; `world_utils.py:986-994` (porte só pelo `type`; nada de período do dia) |
| P4 | A estação só pesa 7 inimigos legados em 4 regiões, numa tabela à mão | `data/world/calendar.json:44-49`; `services/world_calendar.py:329-333` |
| P5 | A ecologia e os sinais já estão **escritos em prosa** na ficha, mas nenhum código lê isso. Ex.: "Aparece aos pares nas semanas de chuva, quando a Praga sobe das margens" | `data/bestiario/fichas/nova_arcadia.yaml:70-73` (branch `spec-349`) |
| P6 | O `contra_jogo` existe só na ficha (e na linha "Como se luta" do Codex). Não chega ao `bestiary.json`, ao presságio nem ao Codex do jogador | `nova_arcadia.yaml:81` vs `data/bestiary.json:11925-12014` (branch `spec-349`, sem `contra_jogo`); `services/discovery.py:116-151` (`bestiary_view` não tem sinais nem contra-jogo) |
| P7 | O telegrafo só aparece pelo `prenuncio`, com `RPG_ENEMY_DECKS` e `RPG_ENEMY_INTENT` ligados. Não fica registro do que o jogador já viu | `services/enemy_decks.py:387-401`; `services/enemy_intent.py:290-309`; `:207-218` (`knowledge_level` lê só Cartas reveladas) |
| P8 | A semente de rumor de avistamento **diz o nome** da criatura ("dizem que viram um Arame Vivo"), em vez de contar o que o morador viu | `scripts/build_rumor_seeds.py:238-265` (`creature_label`); `services/rumors.py:448-455` |
| P9 | Existem dois "bestiary_knowledge" com donos diferentes: o contador do save (`seen/fought/defeated`) e o catálogo runtime de Cartas e resistências reveladas. Uma spec nova precisa dizer qual estende | `services/discovery.py:64-103` vs `services/bestiary_knowledge.py:66-117` |
| P10 | As tramas da 350 não têm estágio. A própria 350 deixa "escalada mecânica de trama" fora de escopo | `specs/SPEC-350-mundo-povoado-tramas.md:232-234` (branch `spec-350`) |
| P11 | A SPEC-349 deixou a ecologia e o peso de encontro explicitamente para outra spec | `specs/SPEC-349-bestiario-valoria-esteira.md:187` (branch `spec-349`) |

**Precedente no próprio repo.** A lei (SPEC-299) já faz "sinal antes do confronto": sinais diegéticos de cena, com registro de `signals_shown`, num bloco `<LEI_NA_CENA>` de custo zero quando vazio. Os caçadores de recompensa só vêm depois do sinal (`services/law.py:901-1048`). Esta spec segue o mesmo padrão para a fauna.

**Objetivo.** Entregar a **Fase 1** executável (pilares 1 e 2, com a narração de aproximação do pilar 4) em Nova Arcádia, e deixar as filhas especificadas com ordem e dependências. Princípios:

- **Mecânica é Python.** Sinal, presença, peso, reação e caça são funções puras de estado mais `day_rng`. O narrador só recebe a pista pronta.
- **Sem chamada LLM nova por turno.** O custo é de prompt (≤ 1 bloco curto, e só quando há sinal).
- **Fonte única.** O bloco de fauna é autorado num YAML por região e compilado num JSON de runtime. O `bestiary.json` não muda (os números de linha dele alimentam o `source` das sementes; P6 da 349).
- **Integridade de eval.** O avaliador e os limiares são escritos e congelados antes do código de produto.

## 2. Requisitos

### A. Dados: bloco de fauna por criatura

- **R1 — Arquivo por região.** `data/bestiario/fauna/<regiao>.yaml` tem uma entrada por criatura da região: toda ficha (`nova`, `reinventada`, `adotada`) **e** todo legado `classe: valoria` com `regions[0] == <regiao>` (D1). Formato em §3.2. A entrada leva `ecologia`, `sinais`, `contra_jogo` (obrigatório no legado; nas fichas é copiado da ficha por teste de igualdade), `tramas` (opcional, inerte na Fase 1), `autor`, `revisor_fauna` e `revisao`.
- **R2 — Cobertura por região.** Teste: para toda região com `fauna/<regiao>.yaml`, as chaves do arquivo são exatamente {ids das fichas da região} ∪ {legado `valoria` da região}. BOSS entra (para sinais e cadeia), mas nunca é sorteado em encontro aleatório (`world_utils.py:976-982` não muda).
- **R3 — Compilação.** `scripts/fauna/build.py` gera `data/world/fauna.json` (compacto, LF, determinístico) a partir de todos os `fauna/*.yaml`. Teste de frescor: rodar o build em memória dá o mesmo conteúdo do arquivo versionado. O runtime lê só o JSON, pelo `services/fauna.py`.
- **R4 — Lint determinístico** (`services/fauna_lint.py`, fonte única, chamado por `content_validator.validate_fauna()` dentro de `validate_all` e por `scripts/fauna/lint.py --regiao`). Regras E1–E16 de §3.4. Termina com 0 erro para cada região coberta.
- **R5 — Sem nome no sinal.** Nenhum texto de `sinais` (rastro, resto, som, cheiro, marca, rumor, aproximacao) contém token do nome da criatura, do id, nem do nome da família em jogo (comparação `fold` sem acento, como `encounter_manifest._fold`, `services/encounter_manifest.py:165`). O jogador lê o sinal e deduz; quem nomeia é o encontro.
- **R6 — Sinal concreto e coerente com o corpo.** Cada sinal descreve um vestígio físico que a anatomia da ficha produz (ex.: o Arame Vivo arrasta arame na lama, `nova_arcadia.yaml:63-72`). O lint barra os vagos do léxico (`data/bestiario/_lexico_sinais.txt`, seção `[vagos]`: "presença maligna", "algo estranho", "energia sombria", "sensação ruim"…). A coerência com a anatomia fica com o revisor (§3.8, item 2).
- **R7 — Backfill autorado.** O backfill de Nova Arcádia (27 fichas + legado da região) segue o processo de §3.7: rascunho por script → autor Opus → revisor Opus independente → lint. O parecer fica em `handoffs/SPEC-360-fauna-review-nova_arcadia.md`.

### B. Motor de ecologia (pesos), flag `RPG_FAUNA`

- **R8 — Multiplicador ecológico.** `fauna.eco_multiplier(entry, ctx) -> tuple[float, list[str]]` devolve o fator e a lista de razões. `ctx` traz local, período, estação, `bestiary_knowledge`, turno, pressões da região, clima e carcaças. Com `RPG_FAUNA=on`, `pick_encounter_enemy` multiplica esse fator no **caminho ponderado** (`world_utils.py:1028-1040`), depois de caça, fação e tema. Criatura sem entrada em `fauna.json` (gerada em runtime, legado genérico ainda não reinventado) recebe fator 1,0. Os fatores, todos de `data/world/fauna_config.json` e marcados `[BALANCEAR]`, são:
  - **horário:** período fora de `ecologia.horario` → `HORARIO_FORA` (0,25);
  - **estação:** `ecologia.estacoes[season]` (default 1,0). Quando a criatura tem entrada em `fauna.json`, o valor da ficha **substitui** o `encounter_mult` do calendário (sem dupla contagem);
  - **território:** local fora de `ecologia.territorio` (mas na região) → `TERRITORIO_FORA` (0,4);
  - **presa liberada:** se algum predador da criatura na região tem `hunt_pressure ≤ 0,3` → `PRESA_LIBERADA` (1,8);
  - **predador faminto:** se todas as presas da criatura na região têm `hunt_pressure ≤ 0,3` → `PREDADOR_FAMINTO` (0,5);
  - **foge de:** se uma criatura de `foge_de` tem presença ativa no local (R13) → 0,3;
  - **reações explícitas** (`ecologia.reage`): pressão da região (`world_pressures`, banda `sinal`/`crise`), estado do clima (`world.weather_state`) e `carcaca_recente`, com efeito `mais` (1,6), `menos` (0,5) ou `some` (0,0).
- **R9 — O sorteio só escolhe QUEM, nunca QUANTOS.** A taxa de gatilho de encontro (`check_encounter`) não muda com `RPG_FAUNA=on`. Teste: nas mesmas seeds, o número de encontros disparados em `on` é igual ao de `off`.
- **R10 — Predador e presa derivados, sem estado novo.** A relação vem de `ecologia.presas` (autorada) e da inversa (derivada). O "matou o predador e a presa prolifera" sai da `hunt_pressure` do censo que já existe (`services/ecology.py:29-42`), com o mesmo decaimento: parar de caçar devolve o equilíbrio.
- **R11 — Carcaça.** Toda morte de criatura de fauna em combate registra `{loc, day, creature_id}` em `world_sim.fauna.carcacas` (cap 20, expira em `CARCACA_DIAS` = 2). Criaturas com `reage: [{quando: carcaca_recente, efeito: mais}]` pesam mais naquele local enquanto ela dura. Na próxima chegada ao local, o sinal "a carcaça que você deixou foi arrastada / roída" pode ser mostrado (texto do `resto` do necrófago).
- **R12 — Modo `shadow`.** Com `RPG_FAUNA=shadow`, o sorteio usa o resultado legado, mas registra `log_event("fauna", "shadow_pick", legado=…, fauna=…, razoes=…)`, para medir no staging antes de ligar.

### C. Presença e sinais, flag `RPG_FAUNA_SINAIS`

- **R13 — Presença.** É uma criatura que está "na área" antes do encontro. Fica em `world_sim.fauna.presencas` (schema em §3.3) e tem um writer único, `services/fauna.py`. Hook diário `fauna.day_hook` (`post`, `order=15`, antes dos rumores em 20; `services/world_engine.py:729-736`): em cada região frequentada (`rumors.frequented_regions`), com chance `P_PRESENCA` e no máximo `MAX_PRESENCAS_REGIAO` (2) ativas, nasce 1 presença. A criatura sai do sorteio ecológico de R8 (não BOSS, porte compatível com o perigo da região), e os `locais` saem do território efetivo. O TTL vem de `ecologia.permanencia` (dias, default 3–6). Tudo com `day_rng(game_id, day, "fauna")`.
- **R14 — Sinal em cena.** Ao chegar, descansar ou agir num local que está nos `locais` de uma presença ativa, `fauna.scene_block(state)` devolve `<SINAIS_NA_CENA>` com **no máximo 1** sinal novo por cena e registra o tipo em `presenca.sinais_mostrados`. A ordem segue a antecedência: primeiro um dos `{marca, rastro, resto}`, depois `{som, cheiro}` (só depois de ≥ 1 sinal mostrado). Cada tipo aparece no máximo uma vez por presença. Sem sinal novo, o bloco não existe (zero token, como em `law.py:1045-1046`). O bloco inclui a instrução fixa "narre como detalhe do ambiente; não nomeie nem descreva a criatura".
- **R15 — O encontro usa a presença.** Quando `check_encounter` dispara por fauna (`looming_threat`, `high_danger`, ou `rumor` com `criatura_avistada`) num local com presença ativa, a criatura é a da presença, com a mesma mecânica de preferência de `hunt_theme` (`world_utils.py:1058-1064`). O porte segue o perigo; se a criatura não couber, o sorteio normal segue. O `enc` ganha `presence_id`.
- **R16 — Encontro sem presença.** Se o gatilho de fauna dispara num local **sem** presença:
  - criatura com `sinais.antecedencia: cedo` → o encontro **vira sinal**. Nasce uma presença (`origem: "conversao"`) com o primeiro sinal já mostrado, e o turno não tem combate (`world_note` "ENCONTRO NA ESTRADA (sinal)"). O cooldown é carimbado como se fosse encontro;
  - criatura com `antecedencia: imediato` (emboscador, artilharia oculta; teto de 30 % por região, E14) → combate no mesmo turno, com a `aproximacao` no texto de início (R17).
  - (§9, desvio da execução) presença **ativa mas ainda sem sinal mostrado**, de criatura `cedo`, conta como "sem anúncio": o gatilho mostra o 1º sinal dela e não há combate (constante `ANUNCIA_PRESENCA_NOVA`). Sem isso uma presença nascida no dia vira luta na 1ª chegada, sem sinal antes (M1 caía para ~0,65).

  Esse é o único ponto em que a taxa de combate pode cair; o limite fica no M5.
- **R17 — Narração de aproximação.** Todo combate de fauna com entrada em `fauna.json` troca o `flavor` genérico (`world_utils.py:1265`, `:1229-1236`) pela `sinais.aproximacao` da criatura. Ela vai em `COMBAT START. {flavor} {sur_txt}` (`storyteller.py:1615`) e no `combat_encounter_hint` (`storyteller.py:216-229`, campo `aproximacao`). A abertura narrada pela IA (SPEC-346) recebe a frase como contexto, **na mesma chamada**.
- **R18 — Preparar.** Com ≥ 2 sinais mostrados da presença, o `detection_check` do encontro dessa presença ganha `+PRESENCA_BONUS_DETECCAO` (2) no `perception_mod` (`storyteller.py:1590-1593`). Quem leu os sinais tem mais chance de emboscar ou de recuar (texto `sur_txt` existente).
- **R19 — Evitar.** A presença expira no `expires_day` (`status: dispersa`). Sair do território e não voltar dentro do TTL basta. Descansar num local da presença conta como gatilho normal.
- **R20 — Caçar.** `fauna.hunt_intent(text)`: regex `fold` fechada ("sigo/seguir o rastro", "rastrear", "caçar", "ir atrás do que deixou", "seguir as pegadas", "seguir o cheiro/som"), no estilo de `rumor_adoption._is_search`. Com intenção de caça, ≥ 1 sinal mostrado e presença ativa no local, o storyteller dispara um encontro **no lugar** (reusa o caminho de `rested_player`, `storyteller.py:1502`) com `reason: "caca"`, `always_combat`, `encounter_surprise = "player"` e o cooldown carimbado. Sem presença ou sem sinal, a frase cai no fluxo de hoje. Sem LLM.
- **R21 — Rumor conta o sinal, não o nome.** Na semente `avistamento`, o `build_rumor_seeds.py` passa a gravar `sinal_rumor` (de `sinais.rumor`) quando a criatura tem fauna. O template `rumor.avistamento` usa `{sinal}` quando existe e cai no texto atual quando não existe (`rumors.py:437-464`). Com `RPG_FAUNA_SINAIS=on`, a semente da criatura com presença ativa na região pesa `RUMOR_BOOST` (3,0) em `rumors.candidates` (`rumors.py:195-243`). O morador "viu algo" antes de o jogador chegar. A testemunha NPC vem de graça pelo ledger da SPEC-215 (`SUBJECT_KINDS` "rumor", `services/npc_knowledge.py:78`) quando `RPG_NPC_KNOWLEDGE=on`.
- **R22 — O rastro sorteado vira sinal.** Com `RPG_FAUNA_SINAIS=on`, o tipo `track` de `roll_encounter_type` (`world_utils.py:1691-1703`) mostra o `sinais.rastro` da criatura sorteada, sem nome, e cria ou reforça a presença dela no local. O registro de `record_rumor` continua (`discovery.py:97-103`). O pedaço de "carga abandonada" (`treasure_hint`) não muda.
- **R23 — Associação no saber.** Quando o encontro da presença acontece (combate ou caça), os tipos de `sinais_mostrados` entram em `bestiary_knowledge[cid].sinais_vistos` (o contador do save, `discovery.py`; P9). Antes disso o jogador não sabe a que criatura o sinal pertence. Na Fase 1 isso só grava; a exibição é da 360-C.
- **R24 — Estado limitado e compatível.** `world_sim.fauna = {"v": 1, "presencas": [≤ 12], "carcacas": [≤ 20]}`. Save sem a chave carrega como vazio. O round-trip save/load preserva o conteúdo. Presença de criatura que sumiu do `fauna.json` é descartada no load, com `log_fallback`.

### D. Flags, custo e eval

- **R25 — Flags** em `config/flags.yaml` (SPEC-340), todas `kind: release`, `default: "off"`, `spec: SPEC-360`, com `expires` (D7):
  - `RPG_FAUNA` = `off|shadow|on`, para o motor de ecologia (R8–R12);
  - `RPG_FAUNA_SINAIS` = `off|on`, para presença, sinais, aproximação, caça e rumor (R13–R23). Ela exige `RPG_FAUNA != off`; caso contrário, é tratada como `off`, com `log_event` uma vez.

  Com as duas `off`, o comportamento é byte-idêntico ao de hoje. Teste: golden de 30 turnos do playtest MockLLM com as flags `off`, antes e depois.
- **R26 — Zero chamada LLM nova.** Teste: contador de `invoke` (via `set_llm_telemetry_hook` ou espião do `get_llm`) em 30 turnos do perfil `explorador`, flags `on` vs `off`, na mesma seed: contagem igual.
- **R27 — Latência.** `eco_multiplier` + `scene_block` + `day_hook` custam, em média, < 5 ms por chamada na suíte (teto de teste 20 ms, para não dar flake). O bloco `<SINAIS_NA_CENA>` tem ≤ 60 tokens (estimativa por `len(texto)/4`).
- **R28 — Eval determinístico** (`scripts/fauna/eval.py` + `tests/test_spec360_eval.py`). Os limiares são congelados na Etapa 1, **antes** do código de produto. Nova Arcádia, 20 seeds × 60 dias de jogo, perfil sintético de viagem (3 chegadas/dia entre os nós da região mais 1 descanso):
  - **M1 (sinal antes):** dos combates de fauna, ≥ **70 %** foram precedidos por ≥ 1 sinal da mesma presença numa cena anterior, e **100 %** têm `aproximacao`;
  - **M2 (horário):** a frequência de cada criatura fora do horário é ≤ 0,35 × a frequência dentro do horário;
  - **M3 (cadeia alimentar):** forçando `defeated ≥ 6` recente num predador, a fatia das presas dele no sorteio sobe ≥ 1,5×; com todas as presas suprimidas, a fatia do predador cai a ≤ 0,6×;
  - **M4 (território):** quando há candidata cujo território contém o local, ≥ 80 % das escolhas caem em criatura do território;
  - **M5 (quantidade):** combates de fauna por 100 chegadas, com as flags `on`, ficam entre −20 % e +5 % do baseline `off` nas mesmas seeds (o dono rejeita "mais criatura");
  - **M6 (vazamento):** 0 sinal renderizado com token do nome da criatura (R5), em todo o `fauna.json` e em todo texto emitido na simulação;
  - **M7 (determinismo):** duas execuções com a mesma seed dão relatório byte-idêntico.

  O relatório fica em `docs/spec360/eval-nova_arcadia.md`.
- **R29 — Playtest.** O harness (`playtest/`) ganha o invariante `fauna_presenca_valida`: criatura existe, `locais` dentro da região, `sinais_mostrados` ⊆ tipos da entrada, nenhuma presença vencida ativa, caps respeitados. A telemetria conta `fauna.sinal`, `fauna.encontro{precedido}` e `fauna.caca`. `playtest run --profile explorador --turns 50` com as flags `on` termina com 0 violação `error`.

### Fora de escopo (Fase 1)

- Backfill das outras 11 regiões e do legado fora de Nova Arcádia: filha **360-B**.
- Exibir sinais vistos, telegrafo e contra-jogo no Codex/BestiaryTab e no presságio; regra de revelação do contra-jogo; contexto do `prepare_encounter`: filha **360-C**.
- Criaturas de trama, estágio de trama e o campo `tramas` com efeito: filha **360-D**. Na Fase 1 o campo é validado só em forma e ignorado pelo motor.
- Composição do grupo (quantos inimigos), orçamento de encontro (`encounter_budget`), porte e níveis.
- Mudar a **taxa** de gatilho de encontro, o cooldown ou a tabela de tipos (`_ENCOUNTER_TYPES_*`).
- Migração de fauna entre regiões além do que `ecology.migrant_candidates` já faz.
- Criatura gerada em runtime (SPEC-361) e geração de bloco de fauna por LLM.
- Imagens, arte, Cartas novas, números de combate, `bestiary.json` (nenhum byte muda), `lore_nova/`.
- Ligar qualquer flag em staging ou produção (decisão do coordenador depois do smoke).

## 3. Design técnico

### 3.1 Arquivos

**Novos**

| Arquivo | Responsabilidade |
|---|---|
| `data/bestiario/fauna/nova_arcadia.yaml` | Bloco de fauna autorado (R1), fichas mais legado da região |
| `data/bestiario/_lexico_sinais.txt` | Seções `[vagos]` (proibidos) e `[sensorial]` (referência do autor) |
| `data/world/fauna.json` | Gerado por `scripts/fauna/build.py` (R3) |
| `data/world/fauna_config.json` | Constantes `[BALANCEAR]` (R8, R11, R13, R18, R21) |
| `services/fauna.py` | Loader, `eco_multiplier`, presenças, `day_hook`, `scene_block`, `hunt_intent`, `record_kill`, `normalize_fauna_sim` |
| `services/fauna_lint.py` | Regras E1–E16 (puro; recebe refs) |
| `scripts/fauna/{build,lint,rascunho,eval}.py` | Compilação, CLI de lint, pré-preenchimento (§3.7), eval (R28) |
| `docs/spec360/eval-nova_arcadia.md` | Relatório do eval |
| `handoffs/SPEC-360-fauna-review-nova_arcadia.md` | Revisão de fauna (§3.8) |
| `tests/test_spec360_{schema_lint,build,eco,presenca,sinais,caca,rumor,flags_off,eval,saves}.py` | Ver §4 |

**Alterados**

| Arquivo | O que muda |
|---|---|
| `world_utils.py` | `pick_encounter_enemy`: fator `eco_multiplier` no caminho ponderado; estação da ficha substitui a do calendário para quem tem fauna (R8). `check_encounter`: preferência pela presença, conversão em sinal e `aproximacao` (R15–R17). `resolve_track`: sinal sem nome mais presença (R22). Tudo atrás das flags |
| `agents/storyteller.py` | Gatilho de caça no lugar (R20); `perception_mod` da presença (R18); bloco `<SINAIS_NA_CENA>` montado como `lei_block` (`:1907-1914`); `world_note` do sinal (R16); `sinais_vistos` (R23) |
| `services/world_engine.py` | `register_day_hook("fauna", fauna.day_hook, stage="post", order=15)` |
| `services/rumors.py` | `RUMOR_BOOST` da semente com presença (R21); `{sinal}` no `render_news` |
| `scripts/build_rumor_seeds.py` | Campo `sinal_rumor` na semente `avistamento` (R21); rodar e regenerar `rumor_seeds.json` |
| `data/world/rumor_templates*` (onde mora `rumor.avistamento`; o executor localiza com `Grep "rumor.avistamento" data/`) | Variante com `{sinal}` |
| ponto de registro de mortes (`discovery.record_kills`; localizar o chamador em `agents/combat.py` com `Grep "record_kills"`) | `fauna.record_kill` (R11) |
| `services/content_validator.py` | `validate_fauna()` em `validate_all` |
| `playtest/invariants.py`, `playtest/telemetry.py` | R29 |
| `config/flags.yaml` | R25 |

### 3.2 Formato do bloco (`data/bestiario/fauna/<regiao>.yaml`)

```yaml
regiao: nova_arcadia
criaturas:
  mon_arame_vivo:
    fonte: ficha                 # ficha | legado
    ecologia:
      horario: [Anoitecer, Noite]          # ⊆ world_utils.PERIODS
      estacoes: {outono: 1.3, inverno: 1.0, primavera: 1.5, verao: 0.6}   # opcional; 0..3
      territorio: [na_anel_lama, na_anel_ferro]   # ⊆ habitat ∩ nós da região; default = habitat
      permanencia: [3, 5]                  # dias de presença (min, max)
      presas: []                           # ids de bestiary.json (região ou adjacente)
      foge_de: [mon_lencol_de_chamine]     # ids; opcional
      reage:
        - {quando: "clima:chuva", efeito: mais}
        - {quando: "pressao:praga", efeito: mais}
    sinais:
      antecedencia: cedo                   # cedo | imediato
      rastro: "Dois sulcos finos e paralelos riscam a lama da viela, como se alguém arrastasse fio de cerca."
      resto: "Num vão de porta, um trapo endurecido de sangue seco, preso num laço de arame enferrujado."
      som: "Um rangido de metal velho vem da viela ao lado, ritmado como passos que não têm pressa."
      cheiro: null
      marca: null
      aproximacao: "Da chuva sai um homem dobrado ao contrário, arrastando um emaranhado de arame que risca a lama."
      rumor: "uma lavadeira jura que ouviu arame rangendo atrás da casa dela a noite inteira"
    contra_jogo: "Manter distância e cortar o arame antes que feche; sem contato, não drena nada e cai depressa."
    tramas: []                             # inerte na Fase 1 (360-D)
    autor: opus
    revisor_fauna: opus-spec-reviewer
    revisao: aprovada                      # pendente | aprovada | rejeitada
```

> O exemplo usa o id e o texto real do `mon_arame_vivo` (`nova_arcadia.yaml:47-119`, branch `spec-349`). O `foge_de` e as frases são ilustrativos: quem escreve é o autor Opus na Etapa 3. A `aproximacao` pode descrever o corpo, porque o encontro já aconteceu, mas não usa o nome (R5).

- **Enums fechados:** `antecedencia ∈ {cedo, imediato}`. `reage.quando ∈ {carcaca_recente, clima:<estado de data/weather.json>, pressao:<guerra|fome|praga|abismo>}` (banda ≥ `sinal`). `reage.efeito ∈ {mais, menos, some}`.
- **Tipos de sinal:** `rastro`, `resto`, `som`, `cheiro`, `marca` (≥ 3 não nulos), mais `aproximacao` e `rumor` obrigatórios. Texto de sinal ≤ 160 chars; `rumor` ≤ 120 chars, em 3ª pessoa, sem nome.

**`data/world/fauna.json` (gerado):** `{"version": 1, "criaturas": {"<id>": {"regiao", "ecologia", "sinais", "contra_jogo", "tramas", "predadores": [derivado]}}}`. Ordenado por id, com `ensure_ascii=False` e LF.

### 3.3 Estado e assinaturas

```python
# services/fauna.py
MODES = ("off", "shadow", "on")            # RPG_FAUNA
SINAIS_MODES = ("off", "on")               # RPG_FAUNA_SINAIS

class Presenca(TypedDict):
    pid: str                 # sha(game_id, creature_id, born_day)[:12]
    creature_id: str
    region_id: str
    locais: list[str]        # <= 4, subconjunto do território efetivo
    born_day: int
    expires_day: int
    sinais_mostrados: list[str]   # tipos, na ordem em que apareceram
    origem: Literal["dia", "conversao", "rastro"]
    status: Literal["ativa", "encontrada", "dispersa", "cacada"]

class FaunaSim(TypedDict):
    v: int                   # 1
    presencas: list[Presenca]    # cap 12 (ativas primeiro; depois as mais recentes)
    carcacas: list[dict]         # {loc, day, creature_id}; cap 20

def mode() -> str: ...
def sinais_mode() -> str: ...
def entry(creature_id: str) -> dict | None: ...
def eco_multiplier(entry: dict, ctx: "EcoCtx") -> tuple[float, list[str]]: ...
def day_hook(ctx: "world_engine.DayContext") -> "world_engine.DayHookResult": ...
def presence_at(sim: dict, location_id: str, day: int) -> Presenca | None: ...
def scene_block(state: dict) -> tuple[str, dict]: ...          # ("<SINAIS_NA_CENA>…", {"world_sim": …})
def convert_to_signal(state: dict, entry: dict, location_id: str, day: int) -> tuple[str, dict]: ...
def approach_line(creature_id: str) -> str: ...                 # "" sem fauna
def hunt_intent(text: str) -> bool: ...
def hunt_hint(state: dict, world: dict, player_level: int) -> dict | None: ...  # forma do law_hint
def detection_bonus(sim: dict, presence_id: str) -> int: ...
def record_kill(sim: dict, creature_id: str, location_id: str, day: int) -> dict: ...
def mark_encountered(sim: dict, presence_id: str, day: int) -> tuple[dict, list[str]]: ...  # devolve sinais_mostrados
def normalize_fauna_sim(raw: Any) -> FaunaSim: ...
```

`EcoCtx` é um `dataclass(frozen=True)` com `location_id`, `region_id`, `period`, `season`, `bestiary_knowledge`, `turn`, `pressure_bands: dict[str, str]`, `weather_state` e `carcacas_aqui: list[str]`. É montado uma vez por chamada de `pick_encounter_enemy`.

### 3.4 Regras do lint (`services/fauna_lint.py`)

| Regra | O que asserta |
|---|---|
| E1 | Schema e enums de §3.2; campo desconhecido é erro |
| E2 | `horario` não vazio e ⊆ `PERIODS` |
| E3 | Chaves de `estacoes` ⊆ `world_calendar.SEASONS`; valores em [0, 3] |
| E4 | `territorio` ⊆ habitat da ficha (ou `regions` do legado) ∩ nós de `world_map.json` com aquele `region_id` |
| E5 | `presas`/`foge_de` existem no `bestiary.json`, ≠ a própria criatura |
| E6 | BOSS nunca é presa |
| E7 | Sem ciclo de predação de tamanho 2 (A come B e B come A) |
| E8 | Presa na mesma região ou em região adjacente (`world_pressures.region_adjacency`) |
| E9 | ≥ 3 tipos de sinal não nulos, mais `aproximacao` e `rumor`; limites de tamanho |
| E10 | R5: nenhum token (≥ 4 letras) do nome, do id ou da família em jogo em qualquer sinal |
| E11 | Nenhum termo de `[vagos]` em sinal |
| E12 | Anti-reskin de sinal: Jaccard de tokens (sem stopwords) entre os sinais de mesmo tipo de duas criaturas da região < 0,5 |
| E13 | `contra_jogo` não vazio; nas fichas, igual ao campo `contra_jogo` da ficha |
| E14 | ≤ 30 % das criaturas da região com `antecedencia: imediato` |
| E15 | ≥ 60 % das criaturas não-BOSS da região com ≥ 1 ligação trófica (presa ou predador) |
| E16 | `LEAK_PHRASES` da SPEC-348 em todo texto de `sinais` (mesma fonte que `content_validator._default_leak_phrases()` usa, conforme o registro da 350, §9) |

### 3.5 Fluxo de um turno de viagem com as flags `on`

1. Hooks diários (se o dia virou): `fauna.day_hook` nasce ou expira presenças. Depois, `rumors.day_hook` dá `RUMOR_BOOST` à semente da criatura presente.
2. `check_encounter`: lei, reforço e fação seguem iguais. Em fauna, a presença no local é preferida (R15). Sem presença e com `antecedencia: cedo`, o encontro vira sinal (R16).
3. Se houve combate, `flavor = approach_line(cid)` (R17), `perception_mod += detection_bonus` (R18), `mark_encountered` e `sinais_vistos` (R23).
4. Se não houve combate, `fauna.scene_block` é montado junto do `lei_block` e entra no prompt do narrador (R14).
5. Uma chamada LLM do narrador, como hoje.

### 3.6 Inspiração externa (só ideia; nada de nome, silhueta ou texto)

| Fonte | O que tomou | Distância |
|---|---|---|
| *Monster Hunter: World* (Capcom, 2018): rastros que, juntados, levam ao monstro e sobem o nível de pesquisa | Sinais acumulados preparam a luta (R18) e alimentam o saber (R23, 360-C) | Sem "insetos guia" nem medidor; o sinal é prosa diegética, 1 por cena |
| *S.T.A.L.K.E.R.: Shadow of Chernobyl* (GSC Game World, 2007), sistema A-Life | A fauna existe e se move fora da vista do jogador | A simulação é um hook diário barato e limitado (≤ 2 presenças por região) |
| *Rain World* (Videocult, 2017): cadeia alimentar que funciona sem o jogador | Predador e presa com efeito no sorteio (R8, R10) | Sem simulação de agente; só pesos derivados do censo |
| *Slay the Spire* (MegaCrit, 2019): ícone de intenção do inimigo | O telegrafo já é o presságio (SPEC-329); a 360-C só o liga ao saber | Nada novo na Fase 1 |
| *The Witcher 3* (CD Projekt Red, 2015): investigação do contrato antes da caça e bestiário que ensina a fraqueza | Contra-jogo revelado pelo que se viu (360-C); caçar seguindo o rastro (R20) | Sem "sentidos de bruxo"; tudo pelo texto e pela ação livre |
| *Hunt: Showdown* (Crytek, 2019): som do ambiente que trai presença | Sinal de `som`/`cheiro` só depois do primeiro vestígio (R14) | Não há mecânica de ruído do jogador |

### 3.7 Autoria do backfill (vale para a Fase 1 e para a 360-B)

1. **Rascunho por script** (`scripts/fauna/rascunho.py --regiao <r>`). Sem LLM, pré-preenche só o determinístico:
   - `territorio` = habitat;
   - `horario` por palavras de `comportamento`/`gancho` ("noite", "madrugada", "dia claro"; default: todos os períodos);
   - `antecedencia: imediato` sugerido para `papel_tatico ∈ {emboscador}`;
   - `revisao: pendente`.
2. **Autor Opus, 1 agente por região, no máximo 2 regiões em paralelo** (regra de RAM do `CLAUDE.md`). Lê só a ficha da região (Grep e Read por bloco) e as entradas legadas da região (Grep pelo id no `bestiary.json` e no Codex). Escreve `sinais`, `presas`, `foge_de`, `reage`, `estacoes` e ajusta `horario`. Usa o que a prosa já diz (P5): não inventa hábito que contradiga `comportamento`. Passa no lint antes do hand-back.
3. **Revisor Opus independente** (nunca o autor), com o checklist de §3.8. Registra o parecer no handoff da região. As correções seguem até `revisao: aprovada` em todas as entradas.
4. **Lint** com 0 erro, `build.py` e o teste de frescor.

Custo: autoria offline, sem chamada em runtime.

### 3.8 Checklist do revisor de fauna (por criatura)

1. Nenhum sinal nomeia ou descreve a criatura inteira; cada um é um **vestígio**.
2. Cada sinal decorre da anatomia, do material ou do comportamento da ficha (cite o trecho).
3. A cadeia alimentar é plausível para o corpo e a escala (o miúdo não come o enorme); um demônio encarnado não "come" por fome animal sem justificativa da ficha.
4. Horário e estação coerentes com a prosa (P5).
5. O `rumor` soa como morador da região, sem número e sem segredo (`LEAK_PHRASES`).
6. Não há reskin de sinal entre criaturas da região (além do E12, a leitura humana).
7. A `antecedencia: imediato` está justificada (emboscada, tocaia, disfarce).

### 3.9 Telemetria

`log_event("fauna", …)` com `presenca_nasce`, `presenca_expira`, `sinal`, `conversao`, `encontro{precedido: bool, sinais: int}`, `caca` e `shadow_pick`. Nunca texto de sinal nem nome em log (só ids).

### 3.10 Fatiamento: specs-filhas (recomendação; IDs a reservar pelo coordenador)

| Ordem | Filha | Conteúdo | Depende de | Flag |
|---|---|---|---|---|
| 1 | **SPEC-360 (esta), Fase 1** | R1–R29 em Nova Arcádia | 349 onda 1 na `main` | `RPG_FAUNA`, `RPG_FAUNA_SINAIS` |
| 2a | **360-B `fauna-backfill-regioes`** | §3.7 nas 11 regiões e no legado de cada uma, em lotes por região conforme cada onda (bst-*, 359) pousa; eval M1–M7 por região; M5 global | 360 `done`; a onda da região na `main` | nenhuma nova |
| 2b | **360-C `fauna-saber-telegrafo`** | Exibição no Codex/BestiaryTab de `sinais_vistos`, telegrafos vistos e contra-jogo; regra de revelação do contra-jogo (ex.: viu o telegrafo e sobreviveu à assinatura, ou tier "Estudada", ou testemunha); linha `contra_jogo` no `pressagios_publicos` (`enemy_intent.py:290-309`) quando revelado; `sinais_vistos` e `aproximacao` no contexto do `prepare_encounter` (mesma chamada); `knowledge_level` passa a considerar o saber acumulado; métrica "a luta ensina" (2º encontro com contra-jogo revelado: vitória e Vitalidade perdida, na arena) | 360 `done`; 329/332 com Cartas autorais da região (Etapa 5 da 349 e das ondas) | `RPG_FAUNA_SABER` |
| 3 | **360-D `fauna-tramas`** | O campo `tramas` passa a valer. `plot_stage(state, thread_id)` é uma visão derivada, sem estado novo: `dormente` → `tocada` (conheceu âncora de porta ou percebeu rumor da trama) → `investigada` (quest `investigar_rumor` da trama ativa ou concluída, ou rumor confirmado) → `revelada` (`revealed_facts` com `secret_id` da trama). A criatura de trama pesa 0 antes de `desde` e ×2 nos `locations` da trama depois; a presença nasce nos locais da trama; o rumor usa os `rumor_ids` da trama | 350 `done` com o catálogo de pelo menos 1 região; 360-B na região | `RPG_FAUNA_TRAMAS` |

2a e 2b podem correr em paralelo. A 360-D vai por último, porque depende de catálogo de trama real. O guarda-chuva fecha quando as quatro estiverem `done`; o status desta spec cobre só a Fase 1.

## 4. Plano passo a passo

### Etapa 0 — Sondas (sem código de produto)

1. Confirmar que a 349 onda 1 está na `main`: 27 fichas em Nova Arcádia, `mon_*` no bestiário, `curadoria_legado.yaml`. Listar o legado `valoria` com `regions[0] == "nova_arcadia"`.
2. Localizar o template `rumor.avistamento`, o chamador de `record_kills` e o ponto exato do `lei_block`. Registrar na §9.
3. Baseline: rodar `tests/test_spec312_seeds.py`, os testes de `check_encounter`/`pick_encounter_enemy` (`Grep -l "pick_encounter_enemy" tests/`) e `playtest run --profile explorador --turns 30` com MockLLM. Guardar a contagem de encontros e o golden de 30 turnos (R25).

### Etapa 1 — Avaliador e limiares congelados (TDD; commit próprio, antes do produto)

1. `scripts/fauna/eval.py` com o perfil sintético de R28 e a saída em Markdown, mais `tests/test_spec360_eval.py` com M1–M7 como asserts e os limiares literais. Os testes de M1/M3/M4/M5 ficam vermelhos (sem motor).
2. Commit `test(fauna): freeze SPEC-360 evaluator and thresholds`. Daqui em diante, o executor de produto não altera esse arquivo (§7, D6).

### Etapa 2 — Schema, lint e build (TDD)

1. **Testes** (`tests/test_spec360_schema_lint.py`, `tests/test_spec360_build.py`):
   - `test_fixture_boa_passa` e `test_fixture_ruim_por_regra[E1..E16]`, com YAML sintético em `tests/fixtures/spec360/`;
   - `test_nome_no_sinal_reprovado` (E10, com acento e caixa trocados);
   - `test_jaccard_reskin_pego` (E12);
   - `test_build_deterministico` e `test_fauna_json_fresco` (R3);
   - `test_cobertura_regiao` (R2, parametrizado pelas regiões com arquivo);
   - `test_contra_jogo_igual_ficha` (E13);
   - `test_bestiary_json_intocado` (`git diff --exit-code data/bestiary.json` no pouso).
2. **Implementação:** `fauna_lint.py`, `build.py`, `lint.py`, `validate_fauna()`, `_lexico_sinais.txt`.

### Etapa 3 — Backfill de Nova Arcádia (Opus + revisor)

1. `rascunho.py --regiao nova_arcadia`.
2. Autor Opus: as 27 fichas mais o legado da região (§3.7).
3. Revisor Opus independente: handoff com parecer por criatura.
4. **Verificação:** `lint.py --regiao nova_arcadia` com 0 erro; `build.py`; `validate_content.py` com 0 ERRO.

### Etapa 4 — Motor de ecologia (`RPG_FAUNA`)

1. **Testes** (`tests/test_spec360_eco.py`):
   - `test_fator_horario`, `test_fator_estacao_substitui_calendario`, `test_fator_territorio`;
   - `test_presa_liberada_quando_predador_caçado` e `test_predador_faminto`, com `bestiary_knowledge` sintético;
   - `test_reage_pressao_clima_carcaca`, `test_foge_de_presenca`;
   - `test_sem_entrada_fator_1`;
   - `test_taxa_de_gatilho_inalterada` (R9);
   - `test_shadow_nao_muda_escolha_e_loga` (R12);
   - `test_off_byte_identico`.
2. **Implementação:** `fauna.py` (loader, `EcoCtx`, `eco_multiplier`), a integração em `pick_encounter_enemy` e `record_kill` mais carcaças (R11).

### Etapa 5 — Presença, sinais, aproximação, caça e rumor (`RPG_FAUNA_SINAIS`)

1. **Testes:**
   - `tests/test_spec360_presenca.py`: `test_day_hook_nasce_no_maximo_2_por_regiao`, `test_ttl_e_dispersa`, `test_determinismo_day_rng`, `test_caps`, `test_normalize_save_antigo` (R13, R19, R24);
   - `tests/test_spec360_sinais.py`: `test_um_sinal_por_cena_na_ordem`, `test_tipo_nunca_repete`, `test_bloco_vazio_zero_token`, `test_bloco_sem_nome`, `test_encontro_prefere_presenca`, `test_conversao_em_sinal_sem_combate`, `test_imediato_combate_com_aproximacao`, `test_aproximacao_no_combat_start_e_handoff`, `test_bonus_deteccao_com_2_sinais`, `test_rastro_sorteado_vira_sinal` (R14–R18, R22);
   - `tests/test_spec360_caca.py`: `test_hunt_intent_regex` (positivos e negativos, ex.: "rastreio o mercador" não conta sem presença), `test_caca_dispara_no_lugar_com_surpresa_do_jogador`, `test_sem_sinal_nao_caca` (R20);
   - `tests/test_spec360_rumor.py`: `test_semente_tem_sinal_rumor`, `test_render_usa_sinal_sem_nome`, `test_boost_com_presenca`, `test_sem_fauna_texto_antigo` (R21);
   - `tests/test_spec360_saves.py`: round-trip de `world_sim.fauna`; save antigo sem a chave; presença de criatura removida é descartada (R24); `sinais_vistos` no `bestiary_knowledge` (R23).
2. **Implementação:** `fauna.py` (presenças, `day_hook`, `scene_block`, conversão, caça), as integrações em `world_utils`/`storyteller`/`world_engine`/`rumors`, `build_rumor_seeds.py` regenerado (overrides preservados, fração de falsos na faixa da 312).
3. **Verificação:** os testes da etapa, mais `tests/test_spec312_seeds.py`, os testes de rumor adotado (`Grep -l "rumor_adoption" tests/`) e os de encontro, com `-n 2`.

### Etapa 6 — Flags, custo, eval e playtest

1. **Testes:** `tests/test_spec360_flags_off.py` (golden de 30 turnos, R25; contagem de `invoke`, R26; tempo, R27).
2. `config/flags.yaml`; invariante e telemetria do playtest (R29).
3. Rodar `scripts/fauna/eval.py` → `docs/spec360/eval-nova_arcadia.md`. Se M1 ou M5 falhar, **não** mexer no avaliador. Ajustar só as constantes `[BALANCEAR]` de `fauna_config.json` (ex.: `P_PRESENCA`) e registrar cada ajuste na §9.
4. `playtest run --profile explorador --turns 50` com as flags `on`: 0 violação `error`.

### Etapa 7 — Revisões

- O revisor de fauna (Etapa 3) já fechou o conteúdo.
- O Sol revisa motor, estado (writer único de `world_sim.fauna`), determinismo, flags `off` e integridade de eval. Handoff em `handoffs/SPEC-360-sol-review.md`.

### Etapa 8 — Smoke real e pouso

Smoke da §6, depois `/spec-land`. A suíte completa é do coordenador.

## 5. Critérios de aceite

- [ ] `data/bestiario/fauna/nova_arcadia.yaml` cobre as 27 fichas e todo o legado `valoria` da região, com `revisao: aprovada` por revisor ≠ autor e parecer no handoff (R1, R2, R7)
- [x] `fauna_lint` E1–E16 com fixtures boas e ruins; `lint.py --regiao nova_arcadia` com 0 erro; `validate_content.py` com 0 ERRO (R4–R6)
- [x] `fauna.json` gerado, fresco e determinístico; `data/bestiary.json` byte-idêntico (R3)
- [x] Ecologia: horário, estação, território, presa/predador, `foge_de`, reações e carcaça com teste; taxa de gatilho inalterada; `shadow` só loga (R8–R12)
- [x] Presença: nasce, expira, tem caps e é determinística; round-trip de save; save antigo carrega (R13, R19, R24)
- [x] 1 sinal por cena, na ordem, sem nome; bloco ausente quando não há sinal (R14, R5)
- [x] Encontro prefere a presença; conversão em sinal para `cedo`; `aproximacao` em 100 % dos combates de fauna com entrada (R15–R17)
- [x] Bônus de detecção com ≥ 2 sinais; caça no lugar com surpresa do jogador (R18, R20)
- [x] Rumor de avistamento conta o sinal, sem nome; boost com presença; `rumor_seeds.json` regenerado com os overrides preservados (R21)
- [x] `sinais_vistos` gravado no `bestiary_knowledge` ao encontrar (R23)
- [x] Flags `RPG_FAUNA` e `RPG_FAUNA_SINAIS` registradas, `off` por default; golden `off` byte-idêntico (R25)
- [x] 0 chamada LLM nova por turno; latência dentro do teto (R26, R27)
- [x] Eval M1–M7 verde, com o avaliador congelado no commit da Etapa 1 e intocado depois; relatório publicado (R28)
- [x] Playtest `explorador` 50 turnos com as flags `on`: 0 violação `error` (R29)
- [ ] `uv run pytest` verde (suíte completa, no pouso, pelo coordenador)
- [x] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo). Se surgir algum, com guard
- [x] Saves antigos continuam carregando
- [ ] Smoke real da §6 executado e registrado na §9
- [ ] Filhas 360-B/C/D com ID reservado e spec `draft` criada a partir de §3.10 (pelo coordenador)

## 6. Smoke test com LLM real

Feito pelo coordenador, com chave (rotas `ROUTES` de hoje), `RPG_FAUNA=on` e `RPG_FAUNA_SINAIS=on`, API local. São ≤ 8 turnos (cerca de 3 chamadas por turno).

1. `scripts/fauna/smoke_setup.py` (scratch, não versionado) grava um save em Nova Arcádia: Noite, presença ativa de `mon_arame_vivo` em `na_anel_lama`, 0 sinal mostrado.
2. "vou para o Anel de Lama": o prompt do narrador (log de debug) tem `<SINAIS_NA_CENA>` com o `rastro`. A narração traz o vestígio como detalhe e **não** contém "Arame Vivo" nem "arame vivo".
3. "fico olhando a viela": 2º sinal (`som`); nenhum combate.
4. "sigo o rastro": o combate começa com surpresa do jogador. O `COMBAT START` traz a `aproximacao`; o spawn resolve em `mon_arame_vivo` (`cache_hit`/`entity_id`); a abertura narrada (346) não contradiz a frase.
5. Depois do combate, `GET /game/state`: `bestiary_knowledge.mon_arame_vivo.sinais_vistos == ["rastro", "som"]`.
6. Custo: a contagem de chamadas por turno com as flags `on` é igual à da mesma sequência com `off` (telemetria `set_llm_telemetry_hook`). Latência do turno: Δ p50 ≤ 300 ms (custo de prompt).
7. Avançar 1 dia de jogo: se nascer o rumor da criatura presente, o texto em "Ouvi dizer" usa o `rumor` da ficha, sem o nome.

## 7. Riscos & compatibilidade

- **Menos combate (R16).** A conversão em sinal pode reduzir lutas; o M5 limita a queda a 20 %, e `P_PRESENCA` cobre os locais antes do gatilho. Se o playtest mostrar marasmo, a alavanca é `P_PRESENCA` (constante), nunca o avaliador.
- **Saves antigos.** `world_sim.fauna` ausente vira vazio; `sinais_vistos` é campo opcional do contador. Nenhuma chave muda de sentido.
- **Conflito com as ondas em voo.** As fichas das bst-* e da 359 estão sendo editadas agora. Por isso o bloco mora em arquivo próprio (D1), sem tocar nas fichas nem no `bestiary.json` (que deslocaria o `source` das sementes, P6 da 349).
- **Vazamento de identidade.** O sinal sem nome é lint (E10) mais eval (M6); a `aproximacao` também não nomeia. O narrador pode nomear por conta própria: a instrução fixa do bloco proíbe, e o smoke confere.
- **Duas fontes de estação.** Para criatura com fauna, a ficha substitui o `encounter_mult` do calendário (R8). As 7 entradas legadas do calendário só seguem valendo para quem não tem entrada.
- **Integridade de eval.** O avaliador é commitado antes do produto (Etapa 1). O executor não o altera; mudança só pelo coordenador, com registro. Se o dono quiser, o arquivo entra em `evals/protected-paths.txt` (D6).
- **MockLLM / FallbackLLM.** Nenhum caminho novo de LLM. O MockLLM ignora o bloco, então os testes conferem o **prompt** capturado, não a prosa. O nome vazado na prosa só aparece no smoke real.
- **Quota e latência.** 0 chamada nova. O prompt cresce ≤ 60 tokens só nas cenas com sinal.
- **RAM na autoria.** No máximo 2 autores Opus em paralelo, medindo a RAM livre antes (regra do `CLAUDE.md`).

## 8. Decisões abertas (default; o coordenador decide)

- **D1 — Onde mora o bloco de fauna.** Default: **arquivo próprio por região** (`data/bestiario/fauna/<regiao>.yaml`), cobrindo fichas e legado. Motivos: as fichas estão em edição nas branches de onda (conflito de merge), o legado não tem ficha e o `bestiary.json` não pode deslocar linhas. Alternativa: bloco dentro da ficha, como o dono escreveu, mais um YAML só para o legado, com rebase em cada branch de onda.
- **D2 — Conversão em sinal (R16).** Default: **sim**, para `antecedencia: cedo`. Alternativa: nunca converter e contar só com as presenças do dia (M1 tende a cair para ~40–50 %).
- **D3 — Fatores ecológicos.** Default: os de R8 (`HORARIO_FORA` 0,25, `TERRITORIO_FORA` 0,4, `PRESA_LIBERADA` 1,8, `PREDADOR_FAMINTO` 0,5, `mais` 1,6, `menos` 0,5), todos `[BALANCEAR]`. O horário nunca zera; só `reage: some` zera.
- **D4 — Limiares do eval.** Default: M1 ≥ 70 %, M5 entre −20 % e +5 %, M2 ≤ 0,35×, M3 ≥ 1,5× / ≤ 0,6×, M4 ≥ 80 %. Congelados na Etapa 1.
- **D5 — Caça por regex ou pelo router.** Default: **regex fechada no storyteller** (R20), sem LLM. Alternativa: nova intenção `HUNT` no router; muda o prompt do CLASSIFY e o golden do router (`tests/fixtures/router_off_golden.json`), por isso não é o recomendado.
- **D6 — Proteger o avaliador.** Default: **sim**, `scripts/fauna/eval.py` e `tests/test_spec360_eval.py` em `evals/protected-paths.txt`, em commit próprio. Muda a governança de eval; precisa do aceite do dono, como na D7 da 339.
- **D7 — Validade das flags.** Default: `expires: 2027-03-01` (as `release` atuais vencem em 25/01/2027, o que é cedo para uma feature nova).
- **D8 — Fatiamento.** Default: Fase 1 aqui e filhas 360-B/C/D na ordem de §3.10 (B ∥ C, depois D). Alternativa: juntar a C na Fase 1 (cresce cerca de 40 % e depende das Cartas autorais de cada região).
- **D9 — Autoria do backfill.** Default: Opus por região mais revisor Opus independente (§3.7), no máximo 2 em paralelo. O legado entra no mesmo lote da região.
- **D10 — Testemunha NPC.** Default: **só pelo rumor** (R21) mais o ledger da 215 quando `RPG_NPC_KNOWLEDGE=on`. Alternativa: NPC do local com fala própria sobre a presença; exigiria escrever no `npc_knowledge` (writer da 215), por isso fica fora.

## 9. Registro de execução

**Execução da Fase 1 (02/11, executor Opus; branch `spec-360` sobre `spec-349` @ `830fb496`).**

*Etapa 0 — sondas.*
- Nova Arcádia: 27 fichas (`nova`/`reinventada`/`adotada`) mais 12 `retro` na ficha. O legado `valoria` com `regions[0] == "nova_arcadia"` (curadoria × `bestiary.json`) são **11**: `enemy_rato_peste_anel_lama`, `enemy_degolador_mao_sombria`, `enemy_soldado_legiao_ferro`, `enemy_iniciado_chama_azul`, `enemy_boss_valerius`, `enemy_boss_vibora`, `enemy_garrick,_o_silenciador`, `mon_rato_caldeira`, `mon_cao_rebite`, `mon_automato_fundicao`, `mon_locomotiva_penitente` (o `enemy_assassino_cinzeu` é retro aqui, mas `regions[0]` é a Pradaria: fica para a 360-B). Total do bloco: **38**. BOSS (5): Roda de Mandíbulas, Valerius, Víbora, Garrick, Locomotiva.
- `rumor.avistamento` mora em `data/world/rumor_config.json` (`templates`); a variante com sinal é `rumor.avistamento_sinal`. O chamador de `record_kills` é `agents/combat.py` (~2708). O `lei_block` é montado em `agents/storyteller.py` (~1911); o bloco de fauna entra **dentro** dele (sem linha nova no prompt com as flags `off`).
- Baseline: golden de 30 turnos do `explorador` (MockLLM, seed 0) gravado em `tests/fixtures/spec360_flags_off_golden.json` **antes** do produto (commit `0bae0f3a`). Os 4 testes de `tests/test_spec289_ameaca_tematica.py` já falham na base `830fb496` (bestiário da 349 trocou as criaturas temáticas); não são desta spec.

*Etapa 1.* Avaliador e limiares congelados em `731f49ff`; proteção D6 em `fa2fefbd` (`evals/protected-paths.txt`). O avaliador não foi tocado depois.

*Desvios (todos no código e nesta spec).*
1. R16 estendido: presença ativa **sem sinal mostrado** de criatura `cedo` também vira sinal no gatilho (ver R16). Sem isso M1 ≈ 0,65.
2. `presence_at` prefere a presença que o jogador já vem lendo (com sinal) e depois a mais nova; `scene_block` passa à próxima presença do local quando a primeira esgotou os sinais.
3. O hook diário pesa por `TERRITORIO_OCUPADO` (0,05) a criatura cujo território já está todo coberto por outra presença: as criaturas se espalham pelos nós da região.
4. Com `RPG_FAUNA=on` e criatura com fauna no pool, o sorteio ponderado usa um `Random` semeado por (turno, local, dia, período) em vez de `Random()` novo sem semente; sem isso o M7 falhava. Não consome o `random` global (as trajetórias `on`×`off` fora da fauna seguem iguais). `off`/`shadow` seguem byte a byte.
5. O R11 "a carcaça que você deixou foi arrastada" (opcional, "pode ser mostrado") **não** foi feito: a carcaça só pesa no sorteio.
6. E16: a fonte `content_validator._default_leak_phrases()` ainda não existe nesta base (vem da 350); o lint usa ela quando existir, mais `secret_signatures.SECRET_SIGNATURES` e a seção `[vazamento]` de `_lexico_sinais.txt`.
7. A caça (R20) chega ao combate com `reason: "caca"`, surpresa forçada do jogador e o cooldown carimbado; o gatilho de rumor com `criatura_avistada` (R15) não usa presença nesta fase.

*Constantes ajustadas (`fauna_config.json`, todas `[BALANCEAR]`), pelo eval:*

| Constante | Default da spec | Final | Por quê |
|---|---|---|---|
| `TERRITORIO_FORA` | 0,4 | 0,02 | M4 = 0,47 com 0,4: com 38 criaturas em 4 nós e a criatura sem fauna (`assassino_cinzeu`, fator 1,0) o território só domina com fator baixo |
| `HORARIO_FORA` | 0,25 | 0,2 | folga no M2 (0,34 → 0,28) |
| `PREDADOR_FAMINTO` | 0,5 | 0,45 | folga no M3 (0,597 → 0,548) |
| `P_PRESENCA` | — | 1,0 | cobertura dos nós antes do gatilho (M5) |
| `MAX_PRESENCAS_REGIAO` | 2 | 4 | 1 por nó de Nova Arcádia; com 2, M5 ≈ −0,30 |
| `TERRITORIO_OCUPADO` | (novo) | 0,05 | desvio 3 |
| `ANUNCIA_PRESENCA_NOVA` | (novo) | `true` | desvio 1 |

Conteúdo (autor, não constante): `permanencia` das não-BOSS subiu +4 dias (presença de ~1 semana; menos presenças novas sem sinal), e o legado ganhou o nó central onde é plausível (`rato_peste` no fosso da cidade, `cao_rebite` com a patrulha, `degolador` também no Anel Dourado).

*Eval final* (`docs/spec360/eval-nova_arcadia.md`, 20 seeds × 60 dias): M1 0,814 precedidos e 1,0 com aproximação · M2 pior razão 0,283 · M3 presa ×1,69 (mínimo), predador ×0,548 (máximo) · M4 0,817 · M5 −0,160 (off 15,06 → on 12,65 combates/100 ações; 1200 gatilhos iguais nos dois modos) · M6 0 vazamento · M7 byte-idêntico.

*Testes do escopo:* `test_spec360_{schema_lint,build,eco,presenca,sinais,caca,rumor,saves,flags_off,eval}.py` verdes; golden `off` byte-idêntico depois de todo o produto; contagem de `invoke` igual `on`×`off` em 30 turnos. Playtest `explorador` 50 turnos com as flags `on`: 0 erro, 0 violação. Mini-campanha MockLLM pelo grafo no Anel de Lama (scratch): presença nasce na virada do dia, 2 sinais em cena, "sigo o rastro" abre combate com surpresa do jogador, `sinais_vistos` gravado, 0 violação `fauna_presenca_valida`.

*Pendente (fora do executor):* revisão de fauna independente (todas as 38 entradas estão `revisao: pendente`; parecer em `handoffs/SPEC-360-fauna-review-nova_arcadia.md`), revisão Sol (`handoffs/SPEC-360-sol-review.md`), smoke real da §6 e IDs das filhas 360-B/C/D.

### Aprovação do dono (02/11)

Aprovada com todos os defaults da §8. Na SPEC-360 também ficou aprovado pôr o avaliador em
`evals/protected-paths.txt` (D6). Ordem de execução: primeiro a integração do bestiário (349 e as ondas),
depois 350 e 351, por último 360 e 361.
