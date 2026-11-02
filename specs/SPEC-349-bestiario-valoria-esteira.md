# SPEC-349 — Bestiário de Valoria: esteira por região de ameaças físicas, com gate de unicidade (onda 1: Nova Arcádia)

> **Status:** `done` (Etapas 0–8: 12 regiões com mecânica, baralho, arena e rumores; revisões de unicidade e Sol APPROVED_WITH_FOLLOWUPS na rodada 2. Pendem fora da 349: smoke real §6, teto de usos das famílias (SPEC-336) e `on` dos chefes)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-11-02
> **Depende de:** SPEC-348 (`approved`, em execução): o cânone da Praga em cadeia única (R19), magia = dor e Lista de Fornalha (R26), Posturas (R47) e o teste de vazamento `LEAK_PHRASES`, que também varre o bestiário (R53). As Etapas 0–2 daqui rodam em paralelo; a Etapa 3 (prosa) só começa com a 348 na `main`. Também depende de SPEC-332 (motor de baralhos de inimigo: Entregas 1 e 2 já na `main`, flag `off`), SPEC-336 (`services/card_lint.py`) e SPEC-330 (gramática e orçamento de Carta).
> **Desbloqueia:** ondas 2–12 (specs-filhas, uma por região, §3.10); curadoria G-14 completa; specs futuras de encontro/mundo povoado que queiram sortear criaturas por região.
> **EXECUTOR_MODEL:** **Opus** (`claude-opus-5-5`) para a prosa (Etapas 3–4 e 6: fichas, Codex, arte, nomes e textos de Carta); `Terra` para motor, lint, números e integração (Etapas 0–2, 5, 7). Dono, 28/10: Fable nunca, salvo pedido explícito. **REVIEW_MODEL:** revisor de unicidade independente (`spec-reviewer`, Opus, nunca o autor) + `Sol` técnico. **REVIEW_REQUIRED:** `true`.
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (HEAD `8c39dbfd`) · **[D?]** decisão aberta (§8, com default) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**O que o dono decidiu (27/10, não reabrir).** Ver `docs/lore/decisoes-2026-10-27.md:77-90`, na branch da 348.

- Ficam todos os perigos conceituais de Valoria e tudo o que já é único no bestiário. Não entram perigos conceituais novos.
- Faltam **ameaças físicas** que lutam contra o jogador, em quatro famílias:
  1. **corpos reescritos**: a Praga ou o Abismo refazendo o corpo;
  2. **bestas da entropia**: física quebrada que caça;
  3. **humanoides de facção que pagaram o preço** da magia ou do Éter;
  4. **demônios encarnados**: cria física de cada um dos 13 demônios.
- A referência de acerto é o Lycan da Praga dos Ossos (`lore_nova/races.txt:511-529`): placas ósseas sobre músculo exposto. A corrupção fica no corpo.
- Meta: **20–25 criaturas novas por região**, nas 12 regiões, uma região por onda. A onda 1 é Nova Arcádia.
- **Unicidade como nas Cartas** (SPEC-335/336): nada de reskin, nada de "matilha / solitário / meio-humano" da mesma ideia.
- Os genéricos são reinventados **no mesmo slot mecânico**.

**Problemas, com evidência:**

| # | Problema | Evidência |
|---|---|---|
| P1 | 103 dos 124 inimigos não existem na lore; vários são clichê de manual (Yeti, Wyvern, Mímico, Troll de Ponte, Djinn, Gárgula, Golem…) | `docs/lore/revisao-2026-10-27.md:227-230` (branch 348); `data/bestiary.json:1621` (`enemy_gargula_ferro`), `:2853` (`enemy_mimico_bau`), `:3043`, `:3131`, `:3392`, `:3651`, `:3740` |
| P2 | Faltam ameaças físicas. A arte gerada sai como "situação perigosa", com pouca criatura | `decisoes-2026-10-27.md:80`; o bestiário não tem nenhum campo `appearance` (0 ocorrências em `data/`); `services/art_brief.py:264-270` só descreve o chefe, por `appearance` ou `description` |
| P3 | Não existe gate de unicidade **de criatura**. O único anti-clone compara `(arquetipo, cartas, resistências, virtudes)` e só vale para `origem == "conflito-17"`. Anatomia, papel tático e lore não entram | `services/content_validator.py:624-639`, `:1089-1103` |
| P4 | `validate_bestiary` lê Cartas só no **topo** de `data/cards/` (`os.listdir`). Uma Carta de criatura em subpasta acusaria "Carta inexistente" | `content_validator.py:997-1008`. O loader já é recursivo: `services/card_lint.py:125-132` |
| P5 | A criatura só entra em jogo **pelo nome**: casamento exato de tokens (`resolve_bestiary_name`) e dedupe semântico do librarian. Nome ambíguo cai na criatura errada | `services/encounter_manifest.py:223-235`; `agents/bestiary.py:442` |
| P6 | Ids do bestiário são citados fora dele, então reinventar trocando o id quebraria essas referências. Os rumores de avistamento são gerados com **número de linha** do bestiário, e inserir entradas desloca o `source` | `data/world/rumor_seeds.json:1236-1246`, `:1305-1316`; `scripts/build_rumor_seeds.py:239-252`; `data/graph/entities_extra.json:434`, `:544`; `evals/experiments/data/spec217_frozen.jsonl` (protegido) |
| P7 | Na lore, os 13 demônios **não são físicos** ("manifestações conscientes das emoções"). A cria física precisa de um mecanismo que não contradiga isso | `lore_nova/timeline_completa.txt:20`, `:30`; `lore_nova/npcs.txt:145-147`. Precedente físico: `lore_nova/creatures.txt:246-247` ("Não um dos treze, mas algo que se desprendeu da mesma entropia") |
| P8 | O baralho de inimigo já existe (SPEC-332), mas nenhuma criatura declara padrão próprio. Tudo cai no padrão da família | `services/enemy_decks.py:288-317` (fase > perfil > família); `data/cards/inimigos/_decks.json:3-22` |

**Objetivo.** Entregar duas coisas:

1. **O processo**, uma esteira reprodutível: eixos antes da prosa → gerar 2× e cortar → lint de unicidade determinístico → revisão independente → mecânica dentro do orçamento → arena → pouso. Inclui os formatos (ficha de identidade, Codex, arte, ficha mecânica, baralho com padrão de intenção).
2. **A onda 1 completa**: Nova Arcádia, com 20–25 criaturas novas e os genéricos da região reinventados no slot.

As ondas 2–12 repetem o mesmo processo em specs-filhas.

Princípios:

- **Mecânica é Python.** Os números saem do orçamento de Carta e da tabela de Corpo. O autor da prosa não decide número.
- **Fonte única.** A identidade fica na ficha. O Codex, a arte e o bestiário derivam dela e são conferidos por teste.
- **Integridade de eval.** Quem autora o conteúdo não mexe em `evals/` protegido nem regenera golden.

## 2. Requisitos

### A. Curadoria do legado (as 124 entradas atuais)

- **R1 — Classificação total, uma vez.** Arquivo `data/bestiario/curadoria_legado.yaml` com **todas** as entradas de `data/bestiary.json`. Cada entrada leva:
  - `classe`: `valoria` | `generico`;
  - `motivo` (1 linha);
  - `evidencia`: uma ref `arquivo:linha` da lore, ou `"0 hits em creatures.txt/codex"`;
  - `destino`: `manter` | `reinventar` | `adotar:<id do codex>`;
  - `regiao_onda`: o `regions[0]` da entrada;
  - `revisor`.

  O pré-preenchimento é por script (§3.6) e a decisão final é registrada. Teste: chaves do YAML == chaves do bestiário; `classe=generico` ⇔ `destino != manter`.
- **R2 — Nada único é apagado.** Toda entrada `classe: valoria` mantém `id`, `name` e `description` byte-idênticos ao snapshot da Etapa 0 (`tests/fixtures/spec349_legado_snapshot.json`). Única exceção: a descrição de `enemy_boss_vibora`, que a SPEC-348 edita (D8 dela).
- **R3 — Reinvenção no mesmo slot.** Uma entrada `generico` reinventada ou adotada:
  - **mantém** `id`, `categoria`, `arquetipo`, `virtudes`, `max_vitalidade`, `ferimento_espacos`, `regions`, `faction` e `behavior.profile`, iguais ao snapshot;
  - **troca** `name`, `description`, `attacks[].name`, `appearance` (novo), `cartas` próprias (mesmo `kind` de efeito e mesma faixa de orçamento da carta substituída) e os `action_hint` do perfil;
  - ganha `substitui_generico: "<nome antigo>"`, para rastreio.

  O id não muda por causa de P6.
- **R4 — Adotar antes de inventar.** Se `lore_nova/creatures.txt` já tem uma criatura **física** que serve ao slot, ela é adotada:
  - a entrada do bestiário ganha `codex_id: <mon_…>`;
  - o doc do Codex gerado não é tocado.

  Exemplo: a Coisa-do-Esgoto (`creatures.txt:798-800`) para o slot de `enemy_horror_esgoto` (Ooze). Só se inventa uma criatura nova para o slot quando nenhuma criatura física de lore cabe. Uma criatura conceitual nunca é adotada como combatente.

### B. Ficha de identidade e gate de unicidade

- **R5 — Ficha obrigatória.** Toda criatura nova, reinventada ou adotada tem uma ficha em `data/bestiario/fichas/<regiao>.yaml`, com todos os eixos de §3.2.
- **R6 — Ficha retro.** Toda criatura que já existe na região (`classe: valoria`) ganha uma ficha `status: retro`, só com os eixos enumerados (sem prosa nova), para que a nova não repita a velha.
- **R7 — Gate determinístico** (`services/bestiary_lint.py`, fonte única; o `content_validator` e o `scripts/bestiario/lint.py` chamam o mesmo código). Regras U1–U13 de §3.4:
  - par com pelo menos uma criatura nova, reinventada ou adotada → **erro**;
  - par só de retros → **aviso** (o legado tem pares parecidos, como "Rato da Peste" × "Rato de Caldeira", e não é apagado).
- **R8 — Eixos antes da prosa.** A onda começa por um **tabuleiro de vagas** (`vagas:` no topo da ficha da região): família, categoria, papel tático, arquétipo e eixos de anatomia de cada vaga. O tabuleiro passa no U2/U3/U12 **antes** de qualquer texto. Assim a repetição é barrada no desenho, não depois.
- **R9 — Gerar 2× e cortar.** O autor (Opus) propõe **≥ 2× o número de vagas** em conceitos de 1 linha (`docs/spec349/conceitos-<regiao>.md`). O revisor de unicidade corta até 20–25 e registra no mesmo doc o motivo de cada corte.
- **R10 — Revisão independente.** Toda ficha nova traz:
  - `autor`;
  - `revisor_unicidade`, que passa em `card_lint.revisor_valido` e é diferente do autor;
  - `revisao: aprovada`.

  O parecer por criatura fica em `handoffs/SPEC-349-independent-review.md`, com o checklist de §3.9. Teste: nenhuma ficha nova com `revisao != aprovada` nem com revisor igual ao autor.
- **R11 — Léxico de bestiário.** `data/bestiario/_lexico_bestiario.txt` tem as seções:
  - `[proibidos_nome]`: genéricos de manual (yeti, wyvern, mimico, djinn, genio, troll, basilisco, gargula, minotauro, gazer, observador, mumia, golem, ooze, elemental, lich, ghoul, zumbi, lobisomem, vampiro, ogro, harpia, hidra, grifo, manticora, kobold, diabrete, sucubo, orc, goblin, dragao);
  - `[marcadores_variante]`: jovem, filhote, menor, maior, alfa, anciao, matilha, solitario, meio, variante, lider;
  - `[conceituais]`: "sem corpo", "não tem corpo", "sem forma", "só uma presença";
  - `[partes]`: vocabulário de partes do corpo, para U9.

  O `[proibidos]` de `data/cards/_lexico_valoria.txt` também vale.
- **R12 — Inspiração externa registrada.** Ideia vinda da internet ou de outra obra entra em `inspiracao: [{fonte, referencia, tomou, distancia}]` com os quatro campos preenchidos. A criatura nunca leva nome ou silhueta da fonte, e o revisor confere `distancia`.

### C. Conteúdo de cada criatura (nova, reinventada ou adotada)

- **R13 — Ficha mecânica** no `data/bestiary.json`, com o mesmo shape das entradas `origem: conflito-17` (ex.: `mon_cao_rebite`, `data/bestiary.json:8346-8434`). Mais:
  - `origem: "bestiario-349"`, `onda: <n>`, `familia_valoria`, `appearance` (≤ 300 chars);
  - `type` derivado da `categoria` (lacaio→`Minion`, padrao→`Standard`, elite→`Elite`, chefe→`BOSS`).

  Passa no `validate_bestiary`: Virtudes 0–5, Vitalidade pela tabela de Corpo, perfil com regra de fuga/rendição ou `resistance: absoluta`, e pelo menos uma Carta oculta.
- **R14 — Baralho próprio, compatível com a SPEC-332.**
  - 2 Cartas próprias para lacaio, 2–3 para padrão, 3 para elite e chefe, em `data/cards/criaturas/<regiao>.json`. Campos: `origem: "bestiario-349"`, `classe: "Inimigo"`, `subclasse: <id da criatura>`, `patamar: "inicial"`, e `oculta: true` em pelo menos uma.
  - Toda Carta passa em `card_lint.check_vocabulary`, `check_budget`, `check_voice` e `check_names`, como no teste de `inf_*` da 332.
  - O `arquetipo` está em `enemy_decks.FAMILIAS`, e `enemy_decks.family_key(entrada) == ficha.arquetipo`. Atenção: `abis`/`vazio`/`aberra` no id, no `type` ou na facção forçam a família `abissal` (`services/enemy_decks.py:49`, `:144-152`).
  - Nada é escrito em `data/cards/inimigos/<familia|faccao_*>.json`, que pertencem à 332 e à 336.
- **R15 — Padrão de intenção próprio.** `tactical_profile.padrao` tem 2–4 slots de `{ataque, ataque_multiplo, defesa, reforco_proprio, enfraquecer, mover}` (`enemy_decks.py:67-74`). `tactical_profile.assinatura` é `{carta: <Carta própria oculta>, a_cada_n: 2–4, telegrafo: "… {nome} …" (≤ 120 chars)}`.
- **R16 — Chefes com fases.** Todo chefe novo ganha `fases` em `data/cards/inimigos/_decks.json` → `"fases": {<id>: [...]}` (`_decks.json:222`): 60 % e 40 %, `baralho_extra` com Cartas próprias e `narracao` com `{nome}` por fase, no formato da Entrega 2 da 332. A única chave tocada em `_decks.json` é `fases`.
- **R17 — Codex migration-safe.** O doc fica em `data/codex/monsters/<id>.md` com:
  - frontmatter `id`, `type: monster`, `name`, `aliases`, `tags: [<regiao>, <familia>]`, `visibility: public`, `curated: true` e `related_entities` (região, nós de habitat, facção, `npc_<demônio>` quando houver);
  - corpo `Tipo: <Família> | Perigo: <Baixo|Médio|Alto|Extremo>`, como em `data/codex/monsters/mon_carnica_andante.md:16`;
  - 1 parágrafo de lore (3–6 frases);
  - a linha `Aparência: …`, mesma convenção que a arte lê nos NPCs (`services/art_brief.py:185-198`);
  - a linha `Como se luta: …`, sem número.

  Sem `curated: true` o migrate apaga o arquivo (`docs/guias/AUTORIA.md:21-33`, `scripts/migrate_lore_nova.py:462-468`). A entidade entra em `data/graph/entities_extra.json`, e segredo só vai num doc `visibility: hidden` paralelo.
- **R18 — Uma fonte para a aparência.** `bestiary[id].appearance` é igual ao texto da linha `Aparência:` do Codex, com no máximo 300 chars. Esse campo sobrevive ao `ensure_combat_sheet` e chega a `art_brief._boss_of` quando a criatura é chefe. Se não sobreviver, um repasse mínimo entra com teste.
- **R19 — Doc de arte próprio.** `docs/arte/bestiario-349/<regiao>.md` segue o formato de `BESTIARIO_VALORIA_ARTE.md` §0.4:
  - por entrada: `### Nome`, uma linha em crase `Família · Perigo · Região (habitat)`, **Visual**, **Composição** e **Evitar** (obrigatório aqui, porque é a guarda anticlichê);
  - o cabeçalho repete o bloco de estilo §0.1, as exclusões, as regras §0.2 e a linha da paleta da região (§0.3), porque o doc base não é versionado (§8 D9);
  - toda **Composição** traz uma referência humana ou de objeto para a escala ficar legível (regra 0.2).
- **R20 — Rumores e grafo regenerados.** Rodar `scripts/build_rumor_seeds.py`: as criaturas novas ganham rumor de avistamento e os `source` deslocados são atualizados. Os overrides são preservados, e a fração de falsos fica na faixa da SPEC-312/348. `validate_content.py` termina com 0 ERRO.

### D. Onda 1 — Nova Arcádia

- **R21 — Volume.** Entre 20 e 25 criaturas `status: nova` com `regions: ["nova_arcadia"]`. O habitat são nós com `region_id == "nova_arcadia"`: `nova_arcadia`, `na_anel_dourado`, `na_anel_ferro`, `na_anel_lama` (`data/world_map.json:5-126`). Cada anel é habitat de pelo menos 5 criaturas.
- **R22 — Cotas (U12).**
  - Cada família tem pelo menos 4 criaturas.
  - Categorias: `lacaio` ≥ 6, `padrao` ≥ 6, `elite` ≥ 4, `chefe` 1–2. A cidade tem perigo 1–3 (`world_map.json:13`, `:82`, `:114`), por isso o piso de lacaio é mais alto.
  - Pelo menos 8 papéis táticos distintos e pelo menos 7 arquétipos distintos.
- **R23 — Demônios na onda.** Pelo menos 4 crias de demônios **diferentes**. Uma delas é de Fehk, a Covardia, presente em Nova Arcádia "em grande quantidade" (`lore_nova/npcs.txt:292`). Cada cria explica o mecanismo físico (resíduo da emoção tomando carne do que está à mão) e **nunca** é o demônio em si (P7). As que tocam Daruun não podem revelar o pacto de Valerius (oculto, SPEC-348 R16–R18).
- **R24 — Genéricos da região reinventados.** A Etapa 2 confirma a lista. Proposta: `enemy_sentinela_ferro` (Constructo), `enemy_horror_esgoto` (Ooze, candidato a adotar a Coisa-do-Esgoto), `enemy_gargula_ferro`, `enemy_elemental_fogo_poluido`, `enemy_golem_lixo` e `enemy_polvo_esgoto`. Eles **não** contam nas 20–25 (D3).
- **R25 — Doc de mundo.** Um único doc curado `data/codex/world_story/story_corpos_do_abismo.md` (público, ~1 página, sem número e sem segredo) conta as quatro famílias como o mundo as vê. Inclui como uma emoção primordial deixa cria de carne, coerente com `timeline_completa.txt:20` e `creatures.txt:246-247`. O nome em jogo das famílias é decidido pelo executor e aprovado pelo coordenador (D10). Ondas futuras só acrescentam.
- **R26 — Arena.**
  - `scripts/bestiario/arena.py --regiao nova_arcadia` mede a vitória do herói-padrão contra cada criatura nova, no nível-alvo da categoria, com `RPG_ENEMY_DECKS=off` e com `on`.
  - Critério: 45–85 % por criatura nos dois modos (faixa aprovada pelo dono para as Cartas).
  - Para os reinventados, |Δ| ≤ 8 pp contra o slot antes, nas mesmas seeds.
  - Relatório em `docs/spec349/arena-nova_arcadia.md`.

### E. Esteira (ondas 2–12)

- **R27 — Plano da esteira.** `data/bestiario/_esteira.yaml` registra:
  - a ordem das 12 regiões e, por região, `status` (`planejada|em_autoria|pousada`), spec-filha, contagens e revisores;
  - o mapa de cobertura dos 13 demônios. Ao fim da onda 12, todo demônio tem pelo menos 2 crias, de anatomias diferentes. O teste global só falha quando as 12 regiões estiverem `pousada`; antes disso, é um relatório.
- **R28 — Spec-filha por onda.** O template `docs/templates/spec-bestiario-onda.md` (≤ 80 linhas) referencia §3 desta spec e preenche só o variável:
  - região, âncoras de lore com `arquivo:linha`, demônios da onda, slots genéricos (tirados de `curadoria_legado.yaml`) e ajustes de cota justificados;
  - smoke real e arena.

  Uma onda = uma spec-filha (D8).
- **R29 — Unicidade global.** Para cada onda nova:
  - nomes únicos no repo inteiro (bestiário, Codex, `entities*.json`);
  - `silhueta` com similaridade < 0,6 contra qualquer ficha de outra região;
  - a mesma cria de demônio não repete anatomia (`plano_corporal`, `material`) entre regiões.
- **R30 — Painel.** `scripts/bestiario/painel.py` gera `docs/bestiario/PAINEL.md`: por região, contagens por família, categoria, papel, arquétipo e status; cobertura de demônios; slots genéricos pendentes; inspirações registradas.
- **R31 — Guia.** `docs/guias/BESTIARIO.md` (≤ 2 páginas) explica a esteira passo a passo, os eixos, as regras U, os formatos e exemplos bons e ruins de reskin. O caso ruim de referência: "Cão de Rebite" → "Cão de Fuligem".

### F. Compatibilidade

- **R32 — Saves.**
  - Save antigo carrega: o id não muda (R3) e a instância em combate é snapshot.
  - `bestiary_knowledge` de um id reinventado continua valendo (D5).
- **R33 — Validador recursivo.** `validate_bestiary` passa a listar Cartas com `card_lint.iter_card_files`, recursivo e ignorando `_*` (P4). O anti-clone de `creature_signature` vale também para `origem` que começa com `bestiario-`.
- **R34 — Resolução por nome.** Para toda criatura nova ou reinventada:
  - `encounter_manifest.resolve_bestiary_name(name) == id`;
  - o conjunto de tokens do nome é único no bestiário;
  - o núcleo do nome (`name_tokens(name)[0]`) não repete o de outra criatura da mesma região (U4).
- **R35 — Sem flag nova** (D1). Conteúdo de bestiário não é feature com caminho de código. Com `RPG_ENEMY_DECKS=off`, a criatura joga só com as Cartas próprias e o perfil, como as demais. Se o coordenador optar por flag, ela entra em `config/flags.yaml` (SPEC-340).
- **R36 — Vazamento.** Todo doc público novo e toda `description`/`appearance` nova passa no teste `LEAK_PHRASES` da SPEC-348 (R53), que já varre o Codex público e o `data/bestiary.json`.

### Fora de escopo

- Perigos **conceituais** novos (proibido pelo dono). Também não se altera nenhum perigo conceitual existente.
- Apagar ou editar uma criatura `valoria` (R2). A descrição da Víbora é da 348.
- Ondas 2–12: as specs-filhas.
- Baralhos novos de família ou facção em `data/cards/inimigos/`, inclusive as 4 facções sem baralho (SPEC-332 §5, linha 56 → SPEC-336). Um humanoide de facção sem `faccao_<id>.json` joga com 0 Carta de facção (`enemy_decks.py:236-240`), e a falta vai no hand-back como demanda para a 336.
- Ligar `RPG_ENEMY_DECKS`/`RPG_ENEMY_INTENT` em `on` (332/334).
- Peso ou distribuição de sorteio de encontro por região, ou ecologia. Isso fica para a spec de mundo povoado, se for o caso.
- Gerar imagens. O doc de arte é prompt. Gatilho de arte para criatura que não é chefe também fica fora.
- G-05 (Lycan, Vampiro e Hospedeiro como condição) e G-17 (origem de Orcs e Goblins): **nenhuma** criatura nova é Lycan, Vampiro, Hospedeiro, Orc, Goblin ou dragão. Os 13 demônios em si continuam NPCs.
- Nós de mapa novos (G-03/G-04). O habitat só usa nós existentes: Catedral Afundada e Fosso dos Cães aparecem no `lore_seed` de `na_anel_lama`, mas não são nós.
- Editar `lore_nova/` (D2) e migrar os campos legados (`hp`/`ac`/`attributes`).

## 3. Design técnico

### 3.1 Arquivos

**Novos**

- `services/bestiary_lint.py`: o gate (U1–U13), fonte única.
- `scripts/bestiario/lint.py` (CLI), `curadoria.py` (pré-preenche R1), `arena.py` (R26) e `painel.py` (R30).
- `data/bestiario/curadoria_legado.yaml`, `data/bestiario/fichas/nova_arcadia.yaml`, `data/bestiario/_esteira.yaml` e `data/bestiario/_lexico_bestiario.txt`.
- `data/cards/criaturas/nova_arcadia.json`.
- `data/codex/monsters/<id>.md` (20–25 docs, curados) e `data/codex/world_story/story_corpos_do_abismo.md`.
- `docs/arte/bestiario-349/nova_arcadia.md`, `docs/spec349/conceitos-nova_arcadia.md` e `docs/spec349/arena-nova_arcadia.md`.
- `docs/bestiario/PAINEL.md` (gerado), `docs/guias/BESTIARIO.md` e `docs/templates/spec-bestiario-onda.md`.
- `handoffs/SPEC-349-independent-review.md`.
- `tests/fixtures/spec349_legado_snapshot.json`, `tests/test_spec349_bestiary_lint.py`, `tests/test_spec349_curadoria_legado.py` e `tests/test_spec349_onda_nova_arcadia.py`.

**Alterados**

- `data/bestiary.json`: entradas novas e slots reinventados.
- `data/cards/inimigos/_decks.json`: só a chave `fases`.
- `data/graph/entities_extra.json`.
- `data/world/rumor_seeds.json`: regenerado.
- `services/content_validator.py`: R33, e `validate_bestiary_identity()` chamando o gate.
- Possivelmente `services/conflict_orchestrator.ensure_combat_sheet` ou o caminho de template, para repassar `appearance` (R18), só se o teste mostrar perda.

### 3.2 Ficha de identidade (`data/bestiario/fichas/<regiao>.yaml`)

```yaml
regiao: nova_arcadia
onda: 1
vagas:                      # R8 — tabuleiro, preenchido ANTES da prosa
  - vaga: 1
    familia: corpo_reescrito
    categoria: padrao
    papel_tatico: quebra_defesa
    arquetipo: bruto
    plano_corporal: bipede_curvado
    material: escoria_fuligem
    habitat: [na_anel_ferro]
criaturas:
  - id: mon_<slug>           # == chave do bestiary.json == id do Codex == entities_extra
    vaga: 1
    nome: "<2–4 palavras>"
    status: nova             # nova | reinventada | adotada | retro
    substitui: null          # id do genérico (reinventada/adotada)
    familia: corpo_reescrito # corpo_reescrito | besta_entropia | humanoide_preco | demonio_encarnado | legado(retro)
    origem_lore:
      fonte: praga_ferro     # praga_ferro|praga_ossos|abismo|eter|demonio|faccao|dragao|outro
      detalhe: null          # npc_<demônio> | <id de facção> | <npc_dragão>
      refs: ["lore_nova/timeline_completa.txt:384", "lore_nova/locations.txt:59"]
    anatomia:
      plano_corporal: bipede_curvado
      material: escoria_fuligem
      escala: humana
      locomocao: anda
      percepcao: respiracao
      texto: "3–5 frases; ≥ 3 partes do corpo concretas"
    silhueta: "1 frase: o que se lê em contraluz"
    comportamento: "2–3 frases: como caça, vive, reage"
    papel_tatico: quebra_defesa
    arquetipo: bruto         # ∈ enemy_decks.FAMILIAS
    categoria: padrao
    faccao: null             # id de facção do grafo (humanoide_preco)
    mecanica_assinatura:
      carta: cri_<slug>_<carta>
      frase: "o que ESTA criatura faz que nenhuma outra da região faz"
    contra_jogo: "como o jogador vence, sem número"
    gancho: "por que esta existe AQUI (1–2 frases)"
    habitat: [na_anel_ferro]
    inspiracao: []           # [{fonte, referencia, tomou, distancia}]
    autor: opus
    revisor_unicidade: opus-spec-reviewer
    revisao: aprovada        # pendente | aprovada | rejeitada
```

A ficha retro (R6) só preenche `id`, `nome`, `status: retro`, `familia: legado`, `anatomia` (só os eixos; `texto` = `description` do bestiário), `papel_tatico`, `arquetipo` e `categoria`. Exemplo real: `mon_cao_rebite` → `quadrupede / ferro_ferrugem / pequena / anda / sangue_cheiro / perseguidor_marca / predador / padrao`.

**Enums fechados.** Ficam em `bestiary_lint` e são citados no guia. Valor fora da lista dá erro.

| Eixo | Valores |
|---|---|
| `plano_corporal` | bipede_ereto, bipede_curvado, quadrupede, hexapode_ou_mais, serpentiforme, segmentado, radial, sessil_ancorado, alado, composto (vários corpos num), hospedeiro_parasita (corpo dentro de corpo), acoplado (dois corpos que agem juntos) |
| `material` | osso, carne_exposta, ferro_ferrugem, escoria_fuligem, quitina, vidro_cristal, eter_cristalizado, cera_sebo, lama_turfa, couro_tecido, madeira_fibra, sal_mineral, cinza |
| `escala` | miuda, pequena, humana, grande, enorme |
| `locomocao` | anda, rasteja, salta, escala_paredes, nada, plana_voa, cava, ancorada, rola |
| `percepcao` | visao, calor, som, vibracao, sangue_cheiro, eter, medo_emocao, respiracao, luz |
| `papel_tatico` | batedor_rapido, bruto_de_linha, guarda_protetor, controlador, emboscador, artilharia, drenador, quebra_defesa, perseguidor_marca, saqueador, suporte, sacrificial, tanque_reativo |

### 3.3 Outros formatos

- **`curadoria_legado.yaml`**: `{<id>: {classe, motivo, evidencia, destino, regiao_onda, revisor}}`.
- **`_esteira.yaml`**: `{ordem: [...12 region_id], regioes: {<id>: {status, spec, n_novas, n_reinventadas, demonios: [npc_…], revisores}}, demonios: {npc_<x>: [ids das crias]}}`.
- **Carta de criatura**: mesmo shape de `data/cards/inimigos/predador.json:4-21`, com `origem: "bestiario-349"`, `subclasse: <id da criatura>` e id `cri_<slug-criatura>_<slug-carta>`.

### 3.4 Regras do gate (`services/bestiary_lint.py`)

| Regra | Escopo | O que asserta |
|---|---|---|
| U1 | global | `id` e `nome` únicos no bestiário, no Codex e em `entities*.json`; nome com 2–4 palavras; conjunto de `name_tokens` único; `resolve_bestiary_name(nome) == id` |
| U2 | região | a tripla `(plano_corporal, material, papel_tatico)` é única |
| U3 | região | qualquer par tem no máximo 3 de 6 eixos iguais (`plano, material, escala, locomocao, percepcao, papel`) |
| U4 | região | o núcleo do nome (`name_tokens(nome)[0]`) não se repete |
| U5 | ficha | `nome` e `silhueta` sem termo de `[marcadores_variante]` |
| U6 | região + Codex | similaridade (`card_lint.similarity`, Jaccard; `embed` opcional com chave) entre `anatomia.texto` de duas fichas < 0,45; entre `gancho` < 0,45; entre `silhueta` < 0,5; entre a anatomia nova e o corpo de todo doc `monsters/` com a tag da região < 0,5 |
| U7 | região | a assinatura mecânica da carta-assinatura (`card_lint.signature`) é única entre criaturas da região; Carta própria nunca é compartilhada |
| U8 | ficha | nome, `description`, `anatomia.texto` e `silhueta` sem `[proibidos_nome]` nem `[proibidos]` do léxico de Cartas |
| U9 | ficha | é físico: `anatomia.texto` com ≥ 3 termos de `[partes]` e nenhum de `[conceituais]` |
| U10 | ficha | `refs` resolvem (arquivo existe, linha ≤ total); `demonio_encarnado` → `detalhe` ∈ os 13 `npc_<demônio>`; `humanoide_preco` → `faccao` ou `fonte: eter`; `corpo_reescrito` → `fonte` ∈ {praga_ferro, praga_ossos, abismo, eter, dragao} |
| U11 | ficha | `revisor_unicidade` válido e ≠ `autor`; `revisao: aprovada` (só as novas) |
| U12 | região | cotas de R21–R23 (e as de cada spec-filha) |
| U13 | região | a tupla `(padrao, a_cada_n, signature(carta-assinatura))` é única; `telegrafo` com similaridade < 0,5 entre criaturas |

Os limiares (0,45 / 0,5 / 0,6) são calibrados na Etapa 1, com um conjunto sintético: o par reskin tem de ser pego e o par distinto tem de passar (D6).

```python
def load_fichas(regiao: str | None = None) -> dict[str, dict]: ...
def eixos_iguais(a: dict, b: dict) -> int: ...
def nucleo_nome(nome: str) -> str: ...  # encounter_manifest.name_tokens(nome)[0]
def lint_ficha(ficha: dict) -> list[Issue]: ...  # U5, U8–U11
def lint_regiao(
    regiao: str, fichas: list[dict], *, bestiary: dict, codex_docs: list[dict], embed=None
) -> list[Issue]: ...  # U1–U4, U6, U7, U12, U13
def lint_global(
    fichas_por_regiao: dict[str, list[dict]],
) -> list[Issue]: ...  # R29, cobertura de demônios (R27)
```

`Issue` reaproveita o tipo de `services/card_lint.py` se o shape servir.

### 3.5 Âncoras de Nova Arcádia (ponto de partida do autor, não conteúdo)

| Zona | Âncoras com evidência |
|---|---|
| Anel de Ferro | Fundições e Tosse de Ferro (`lore_nova/locations.txt:59`; `world_map.json:93`); Mercado de Carne e Oubliette (`world_map.json:93`); Aço de Sangue e os operários de Bors (`lore_nova/factions.txt:119`); Lista de Fornalha, os magos consumidos (SPEC-348 R26) |
| Anel de Lama | Pó de Sonho, Catedral Afundada (leprosos), Fosso dos Cães (`world_map.json:125`); esgotos que descem ao pântano (`creatures.txt:798-800`); Corvos e Mãe Corva (decisões G-08) |
| Anel Dourado | Palácio de Obsidiana que sangra e Jardins Suspensos com flores impossíveis (`world_map.json:61`); Os Quebrados e o Pó de Fada (decisões G-08, C-16) |
| Cidade inteira | Praga de Ferro, a Ferrugem do Sangue (`timeline_completa.txt:384`; cadeia única: 348 R19); Fehk em grande quantidade (`npcs.txt:292`); bioma "perigo majoritariamente urbano e humano" (`creatures.txt:736`) |

### 3.6 Pré-curadoria (`scripts/bestiario/curadoria.py`)

O script marca cada entrada assim:

- `valoria`: o nome bate com um `[CRIATURA:]` de `creatures.txt` ou com um doc `monsters/`, ou a `faction` é do grafo;
- `generico`: o nome tem termo de `[proibidos_nome]`;
- `revisar`: o resto.

Nenhum `revisar` sobrevive à Etapa 2: o autor (Opus) propõe, o revisor decide e registra.

### 3.7 Arena (`scripts/bestiario/arena.py`)

Reaproveita `docs/spec285/arena_lethality.py` e o recorte de `docs/spec332/arena_familias.py`: mesmo herói, mesmo encontro-piso por categoria, `run_round`, MockLLM. Nível-alvo: lacaio e padrão L1/L3, elite L3, chefe L5. Parâmetros: `--seeds` (default 20; 40 para fechar critério) e `--modo off,on`. A saída é JSON mais o Markdown do R26.

### 3.8 Mapa de demônios (proposta de `_esteira.yaml`, pela `Localização` em `npcs.txt`)

- Com lugar fixo: Urath → `deserto_zhur` (`:155`), Thessavar → `floresta_sussurros` (`:170`), Solvhara → `pantano_melancolia` (`:232`), Lyss → `brekmar` (`:277`), Fehk → `nova_arcadia` (`:292`), Morvath → `aethelgard` (`:307`).
- Itinerantes, distribuídos pelas ondas: Daruun, Maalrek, Vhrak, Veth, Dorrhen, Skarath, Veleth.

### 3.9 Checklist do revisor de unicidade (por criatura)

1. Não é reskin de nenhuma ficha da região, nem retro, nem de doc `monsters/`, nem de ondas anteriores.
2. A identidade cabe em uma frase que nenhuma outra criatura da região aceitaria.
3. É de Valoria: a ligação de lore é dela e não é monstro de manual com nome trocado.
4. É física e luta.
5. Nada no texto público entrega segredo.

Veredito `APPROVED` ou `CHANGES` com motivo. O registro final vai para o campo `revisao` da ficha.

### 3.10 Esteira (recomendação de forma)

Uma **spec-filha por região** (D8), criada com `/spec-new` a partir do template R28. Cada uma pousa sozinha com as Etapas 3–8 desta spec, e o status fica no cabeçalho dela. A 349 fecha na onda 1.

Ordem proposta (D9), pelo trânsito a partir do início (`world_map.json:20-28`): `pantano_melancolia`, `pradaria_ruinas`, `brekmar`, `deserto_zhur`, `costa_negra`, `montanhas_afiadas`, `floresta_sussurros`, `selva_xylos`, `skallgard`, `aethelgard`, `ophidia`.

## 4. Plano passo a passo

Cada etapa é um commit (ou mais) na branch `spec-349`. Testes só do escopo, no máximo com `-n 2`.

### Etapa 0 — Inventário e congelamento (Terra)

1. **Testes:** nenhum de produto.
2. **Implementação:**
   - gerar `tests/fixtures/spec349_legado_snapshot.json` (id → name, description, categoria, arquetipo, virtudes, max_vitalidade, ferimento_espacos, regions, faction, behavior.profile, cartas) **em commit separado, antes de qualquer edição** do bestiário;
   - contar as criaturas de Nova Arcádia (estimativa: 17) e as do Codex com a tag `nova_arcadia`;
   - confirmar os ids `npc_<demônio>` dos 13.
3. **Verificação:** o snapshot tem as 124 chaves.

### Etapa 1 — Gate (Terra, TDD)

1. **Testes** (`tests/test_spec349_bestiary_lint.py`):
   - `test_reskin_sintetico_pego`: anatomia com 2 palavras trocadas → U6;
   - `test_variante_pega`: "Rato Alfa" → U5;
   - `test_nucleo_repetido_pego`: "Cão de Rebite" × "Cão de Fuligem" → U4;
   - `test_tripla_repetida_pega` → U2;
   - `test_eixos_demais_iguais` → U3;
   - `test_conceitual_pego`: "sem corpo" → U9;
   - `test_generico_pego`: "Golem" → U8;
   - `test_demonio_sem_npc_valido` → U10;
   - `test_revisor_igual_autor` → U11;
   - `test_par_distinto_passa`;
   - `test_retro_x_retro_e_aviso`;
   - `test_cotas_regiao` → U12;
   - `test_padrao_assinatura_duplicados` → U13;
   - `test_validate_bestiary_acha_carta_em_subpasta` (R33);
   - `test_anticlone_vale_para_bestiario_349` (R33).
2. **Implementação:** `services/bestiary_lint.py`, `_lexico_bestiario.txt`, R33 em `content_validator.py`, `validate_bestiary_identity()` e `scripts/bestiario/lint.py`.
3. **Calibração:** rodar o lint nas fichas retro de Nova Arcádia da Etapa 3, a título informativo, e registrar os limiares na §9.
4. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_spec349_bestiary_lint.py tests/test_fase71.py -q`.

### Etapa 2 — Curadoria do legado (Terra + Opus + revisor)

1. **Testes** (`tests/test_spec349_curadoria_legado.py`):
   - `test_todas_classificadas` (R1);
   - `test_valoria_intocada` (R2, contra o snapshot);
   - `test_generico_tem_destino`;
   - `test_adotado_aponta_codex_fisico` (R4: o doc existe e passa no U9).
2. **Implementação:** `scripts/bestiario/curadoria.py` pré-preenche. O autor (Opus) propõe a `classe` dos `revisar`, o revisor decide, e o YAML entra no repo. A lista de `generico` vai no hand-back.
3. **Verificação:** os testes acima.

### Etapa 3 — Tabuleiro e conceitos de Nova Arcádia (Opus + revisor)

Precisa da SPEC-348 na `main`.

1. **Testes** (em `tests/test_spec349_onda_nova_arcadia.py`):
   - `test_fichas_retro_completas` (R6);
   - `test_vagas_passam_u2_u3_u12` (R8).
2. **Implementação:**
   - fichas retro;
   - tabuleiro de 20–25 vagas mais as vagas dos genéricos;
   - ≥ 2× conceitos em `docs/spec349/conceitos-nova_arcadia.md`;
   - o revisor corta (R9);
   - o doc `story_corpos_do_abismo.md` (R25).
3. **Verificação:** lint da região sem erro nas vagas.

### Etapa 4 — Prosa (Opus)

1. **Testes:**
   - `test_ficha_codex_arte_consistentes`: cada id nova/reinventada tem ficha, doc Codex `curated: true` e entrada no doc de arte com Visual, Composição e Evitar;
   - `test_aparencia_unica` (R18, parte de texto);
   - `test_codex_frontmatter_e_entidade` (R17).
2. **Implementação:** fichas completas, Codex, `entities_extra.json` e doc de arte.
3. **Verificação:** lint da região sem erro; `validate_content.py` com 0 ERRO.

### Etapa 5 — Mecânica e baralho (Terra; o autor Opus escreve nomes, descrições e telegrafos)

1. **Testes:**
   - `test_entradas_bestiario_validas` (R13, via `validate_bestiary`);
   - `test_cartas_criaturas_lint` (R14);
   - `test_family_key_bate` (R14);
   - `test_padrao_e_assinatura_validos` (R15: `enemy_decks.plan` devolve a assinatura na rodada certa e `prenuncio` devolve o telegrafo 1 rodada antes, com `on`);
   - `test_chefe_fases` (R16: `apply_phases` troca de fase e narra);
   - `test_resolve_por_nome` (R34);
   - `test_appearance_chega_ao_art_brief` (R18).
2. **Implementação:**
   - entradas no bestiário (números pela tabela de Corpo e pelo orçamento de Carta; nada vem da prosa);
   - `data/cards/criaturas/nova_arcadia.json`;
   - `fases` em `_decks.json`.
3. **Verificação:** testes do escopo, mais `tests/test_enemy_decks.py` e `tests/test_conflito_autoria_bestiario.py`.

### Etapa 6 — Genéricos de Nova Arcádia no slot (Opus + Terra)

1. **Testes:** `test_slot_preservado` (R3: campos de slot iguais ao snapshot; nome e descrição mudaram; `substitui_generico` presente).
2. **Implementação:** reinventar ou adotar os slots confirmados na Etapa 2. Testes de produto que fixam o nome antigo são atualizados no mesmo commit e listados no hand-back. `evals/` não é tocado.
3. **Verificação:** testes do escopo.

### Etapa 7 — Integração e arena (Terra)

1. **Implementação:**
   - `build_rumor_seeds.py` (R20);
   - `validate_content.py`;
   - `scripts/bestiario/arena.py` com 40 seeds, `off` e `on`, gerando `docs/spec349/arena-nova_arcadia.md`;
   - ajuste numérico só para criatura fora da faixa, e cada ajuste é registrado;
   - `painel.py`, `_esteira.yaml`, `docs/guias/BESTIARIO.md` e o template da spec-filha.
2. **Verificação:** `tests/test_spec312_seeds.py`, `tests/test_conflito_volume_conteudo.py`, `tests/test_fase71.py` e os testes da 349.

### Etapa 8 — Revisões

- O revisor de unicidade (Opus, outro agente, nunca o autor) preenche `handoffs/SPEC-349-independent-review.md` (§3.9).
- O Sol faz a revisão técnica: motor, lint, compatibilidade com a 332 e integridade de eval.
- Correções e re-revisão até `APPROVED`.

### Etapa 9 — Smoke real e pouso

Smoke da §6 → `/spec-land`. A suíte completa é do coordenador.

## 5. Critérios de aceite

- [ ] `curadoria_legado.yaml` cobre as 124 entradas; zero `valoria` alterada contra o snapshot (R1, R2)
- [ ] Genéricos de Nova Arcádia reinventados ou adotados no slot, com campos de slot idênticos (R3, R4, R24)
- [ ] 20–25 criaturas novas em Nova Arcádia, com as cotas de família, categoria, papel, arquétipo e demônio (R21–R23); `lint.py --regiao nova_arcadia` com 0 erro
- [ ] Toda criatura nova tem ficha aprovada por revisor ≠ autor, parecer em `handoffs/SPEC-349-independent-review.md` e conceitos 2× com o motivo dos cortes (R9, R10)
- [ ] Ficha ↔ bestiário ↔ Codex (`curated: true`) ↔ `entities_extra` ↔ Cartas ↔ doc de arte, consistentes por teste (R13–R19)
- [x] Padrão, assinatura e telegrafo próprios, e fases nos chefes, funcionando com `RPG_ENEMY_DECKS=on` (R15, R16); `off` sem regressão nos testes existentes
- [x] `resolve_bestiary_name(nome) == id` para toda nova ou reinventada (R34)
- [ ] Arena: 45–85 % por criatura nova nos dois modos; reinventados com |Δ| ≤ 8 pp (R26) — 253/281 na faixa nos dois modos e 247/281 pelo veredito completo (HEAD pós-sync); exceções nominais na §9
- [x] `validate_content.py` com 0 ERRO; rumores regenerados; teste `LEAK_PHRASES` da 348 verde (R20, R36)
- [x] `docs/guias/BESTIARIO.md`, template de spec-filha, `_esteira.yaml` e `PAINEL.md` publicados (R27–R31)
- [ ] `uv run pytest` verde (suíte completa, no pouso, pelo coordenador)
- [x] Nenhum `with_structured_output` novo (o conteúdo é autoral, sem LLM em runtime); se surgir um, guard de FallbackLLM
- [x] Saves antigos continuam carregando (id estável; teste de round-trip com save que tem `enemy_gargula_ferro` em `bestiary_knowledge`)
- [ ] Smoke real da §6 executado e registrado na §9

## 6. Smoke test com LLM real

Feito pelo coordenador, com chave. São ≤ 5 requests de LLM mais o reindex, que é de embeddings.

1. `uv run python rag.py` reindexa sem erro. Registrar os chunks por visibilidade antes e depois. `query_rag("criatura das fundições do Anel de Ferro", "lore")` traz pelo menos 1 doc novo no top-5.
2. Jogo novo em Nova Arcádia, com a ação "ataco o/a `<nome de uma criatura nova>`". O spawn resolve no **id novo** (`cache_hit` com o `entity_id` certo), não num genérico nem num inimigo gerado.
3. Com `RPG_ENEMY_DECKS=on` e `RPG_ENEMY_INTENT=on`, 3 rodadas: o telegrafo da assinatura própria aparece 1 rodada antes e a carta é jogada.
4. Contra o chefe novo de Nova Arcádia: o brief de arte (`build_*_art_brief`) traz a linha `BOSS:` com a `appearance` dele. Só confere o texto; não gera imagem.
5. A narração dos passos 2 e 3 não contém termo de `[proibidos_nome]` nem frase de `LEAK_PHRASES`.

## 7. Riscos & compatibilidade

- **Saves antigos.** O id não muda e a instância em combate é snapshot. `bestiary_knowledge` do id reinventado passa a valer para a criatura nova no mesmo slot (D5).
- **MockLLM e FallbackLLM.** Não há caminho novo de LLM. O MockLLM não exercita o librarian, por isso P5 só aparece no smoke (passo 2).
- **Quota e latência.** Nenhum impacto em runtime. O custo é de autoria, offline, do autor (Opus).
- **Conflito com a 332/336.** Arquivos próprios (`data/cards/criaturas/`). Em `_decks.json`, só a chave `fases`: rebase cuidadoso no `wt.sh sync`.
- **Conflito com a 348.** Rumores e overrides: a 348 pousa antes, e o R20 regenera depois.
- **Falso positivo do lint.** Limiares calibrados com conjunto sintético. Se o coordenador ajustar uma vez, a justificativa vai na §9 (D6).
- **O autor tende ao parecido.** Eixos antes da prosa, 2× com corte, U2/U3/U6 e revisor de outro modelo.
- **Sorteio.** 25 criaturas novas na região inicial mudam a frequência de cada uma no LLM e no RAG. Peso de encontro fica fora de escopo; acompanhar no playtest.
- **Lore nova sobre os demônios.** A cria física é cânone novo, contido no doc R25 e nas fichas. Contradição com `timeline:20` é barrada pelo checklist (§3.9, item 3) e pelo U10.

## 8. Decisões abertas (default; o dono liberou o coordenador para decidir)

- **D1 — Flag para o conteúdo novo?** Default: **não** (R35).
- **D2 — Fonte canônica das criaturas novas.** Default: **Codex curado + fichas** (migration-safe, padrão do `mundo_vivo/` G-15). Alternativa: blocos `[CRIATURA:]` em `lore_nova/creatures.txt`, que exigiria tirar o `curated` e regenerar.
- **D3 — Os reinventados contam nas 20–25?** Default: **não**. São substituição, não acréscimo.
- **D4 — Adotar criatura física de `creatures.txt` no slot genérico antes de inventar?** Default: **sim** (R4; casa com a decisão G-14).
- **D5 — Zerar `bestiary_knowledge` de id reinventado?** Default: **não**.
- **D6 — Limiares de similaridade.** Default: 0,45 / 0,5 / 0,6, calibrados na Etapa 1; o coordenador pode ajustar uma vez, com registro.
- **D7 — Revisão de voz.** Default: amostra determinística de 20 % para o coordenador, como na SPEC-336 R5. O dono lê se quiser.
- **D8 — Ondas 2–12: specs-filhas ou dentro da 349?** Default: **specs-filhas**, uma por região (status e revisão por onda; a 349 fecha na onda 1).
- **D9 — Ordem das ondas e doc de arte base.** Default: a ordem de §3.10. O doc novo copia o cabeçalho de estilo; versionar o `BESTIARIO_VALORIA_ARTE.md` do checkout principal fica a critério do dono, porque o arquivo é dele e não é versionado.
- **D10 — Nome em jogo das quatro famílias** (doc R25). Default: o executor propõe e o coordenador aprova.
- **D11 — Faixa de arena.** Default: 45–85 % (aprovada para as Cartas) e |Δ| ≤ 8 pp para reinventados.
- **D12 — Cotas por onda.** Default: ≥ 4 por família, chefe 1–2 e as categorias de R22; spec-filha só muda com justificativa.

## 9. Registro de execução

**Etapas 0-2 (executor Terra, 27/10) - concluídas; Etapas 3+ pendentes (autor de prosa, após a 348).**

- **Etapa 0.** Snapshot `tests/fixtures/spec349_legado_snapshot.json` com as 124 chaves, em commit próprio antes de qualquer edição do bestiário. Nova Arcádia: 17 entradas no bestiário; 51 docs `monsters/` do Codex com a tag `nova_arcadia`. Os 13 `npc_<demônio>` existem em `data/graph/entities.json`.
- **Etapa 1.** `services/bestiary_lint.py` (U1-U13, R29, cotas U12 por onda em `COTAS_ONDA`, `lint_vagas` para o tabuleiro R8, `checar_fisico`), `data/bestiario/_lexico_bestiario.txt`, `scripts/bestiario/lint.py` (`--regiao`, `--vagas`, `--sem-revisao`), `validate_bestiary_identity()` no `content_validator` (ligado ao `validate_content`; sem fichas devolve vazio) e R33 (varredura recursiva de Cartas; anti-clone também para `origem` `bestiario-*`).
- **Limiares (D6), calibração sintética:** reskin (2 palavras trocadas) Jaccard 0,67; par distinto 0,00. Limiares mantidos 0,45 / 0,5 / 0,6. A calibração com as fichas retro reais de Nova Arcádia fica para a Etapa 3 (as fichas ainda não existem).
- **Etapa 2 (revisada após auditoria Opus, 28/10).** `scripts/bestiario/curadoria.py` gera `data/bestiario/curadoria_legado.yaml` (124): 90 `unico` (manter), 3 `conceitual` (manter), 31 `generico` = 25 reinventar + 6 adotar (`mon_coisa_do_esgoto`, `mon_goblins_mineiros`, `mon_verme_de_vidro`, `mon_polvo_dos_destrocos`, `mon_brasa_profunda`, `mon_serpente_cipo_constritora`). Campos extras: `subclasse` e `duvida_dono` (+ `motivo_duvida`) em Sombra Espreitadora, Fantasma, Quimera de Cristal, Ent que Sonha Acordado e Jötunn de Cinza (todos mantidos). `revisor`: "opus-audit (independente) + coordenador".
- **Mudanças da auditoria:** C1 Goblin (canônico) vira adoção de Goblins Mineiros; C2 Verme da Areia vira adoção do Verme-de-Vidro; C3 Golem de Carne segue reinventar com âncora obrigatória em Silas Vane (npcs.txt:63; secrets.txt:26,134; rumors.txt:163); C5 Aranha Lobo vira reinventar (a Aranha-de-Pedra tem 0 partes concretas no Codex, não passa em U9); C7/C8 General Escorpião (âncora no Escorpião-de-Cristal) e Aranha de Cristal (creatures.txt:1128) viram reinventar; C10 léxico sem orc/goblin/vampiro (canon) e com quimera/ent; C11-C14 motivos e evidências corrigidos (Nômade Canibal agora por facção).
- **Desvio D4 (C4/C6):** Lobo das Geleiras e Esqueleto da Legião Antiga NÃO viram adoção de Lobo-de-Vidro e Afogado da Batalha, porque ambos já têm ficha mecânica no bestiário (D4 só permite criatura sem ficha). Ficam reinventar.
- **Desvio U9 nas adoções:** vários docs do Codex não citam partes do corpo (só Coisa-do-Esgoto, Serpente-Cipó e Flor-Carnívora passam em ≥3); o teste de adoção exige doc existente, sem ficha prévia e sem termo conceitual. O U9 completo vale na ficha da Etapa 4.
- **Dúvidas mantidas (na dúvida, manter):** Titã de Gelo, Necromante Renegado, Capitão dos Bandidos, Bandido, Goblin de Eco, além dos 5 `duvida_dono`.
- **Decisão do dono (28/10):** Sombra Espreitadora, Fantasma, Quimera de Cristal, Ent que Sonha Acordado e Jötunn de Cinza são **genéricos** (`classe/subclasse: generico`, `destino: reinventar`, motivo "dono 28/10: genérico"; `duvida_dono` removido). Contagem passa a 87 `unico` + 1 `conceitual` (manter) e 36 `generico` = 30 reinventar + 6 adotar. Nenhum dos 5 é de Nova Arcádia (Floresta dos Sussurros, Aethelgard ×2, Skallgard): ficam marcados para a onda da própria região.

**Etapas 3–4 (28/10) — concluídas; as 25 fichas desta rodada foram escritas pelo Fable (`autor: fable`, registro histórico); daqui em diante o autor de prosa é o Opus (dono, 28/10); revisão de unicidade em `handoffs/SPEC-349-independent-review.md`.**

- **Etapa 3.** Tabuleiro de 29 vagas (23 novas + 6 slots) em `data/bestiario/fichas/nova_arcadia.yaml` → `vagas:`, verde em U2/U3/U12 antes de qualquer prosa e também contra os eixos das 12 fichas retro (R6). 48 conceitos em `docs/spec349/conceitos-nova_arcadia.md` (24 cortes do autor com motivo). Doc de mundo R25 em `data/codex/world_story/story_corpos_do_abismo.md`; nomes em jogo das famílias (D10, a aprovar pelo coordenador): **Reescritos · Bestas Tortas · Cobrados · Crias de Apetite** (`familias_em_jogo:` na ficha; vão na linha `Tipo:` do Codex).
- **Etapa 4.** Fonte única = ficha; `scripts/bestiario/gerar_docs.py --regiao nova_arcadia` gera os docs `data/codex/monsters/<id>.md` (`curated: true`, linhas `Aparência:`/`Como se luta:`), o doc de arte `docs/arte/bestiario-349/nova_arcadia.md` (cabeçalho §0.1/§0.2 + paleta copiados do doc base não versionado, D9), as entidades em `entities_extra.json` e, nos 6 slots, só os campos de TEXTO do bestiário (R3: `name`, `description`, `appearance`, `attacks[].name`, `action_hint`, `substitui_generico`, `codex_id`). Cada ficha já traz `padrao`/`a_cada_n`/`telegrafo`/`mecanica_assinatura` para a Etapa 5. Testes: `tests/test_spec349_onda_nova_arcadia.py`.
- **Revisão de unicidade (Opus, 3 rodadas; veredito final APPROVED_WITH_FOLLOWUPS para 25 de 27).** Rodada 1: 13 aprovadas, 3 cortes (Costurador de Dentes = Cortadores de Dente; Vela da Chama Azul = Iniciado avançado; Abraço Duplo = par do Vira-Costas), 2 slots reinventados de novo (Pombo de Chumbo era gárgula → **Rã de Lótus**; Trouxa de Luto era golem → **Velório de Sal**), reescritas (Relicário → cristal de Éter; Remendado sem Vane no público; Pavio sem steampunk; Escritura sem contato; Enxerto, Fila, Arame). Entrou **Quebrado de Vitrine** (Dourado). Rodadas 2–3: Remendado virou **Sangrado da Clínica** (sangrado pela lanceta; sem retalhos), Quebrado sentado com vidro só nas rachas, Rã avisa em vez de cuspir (`suporte`), Velório salga sem absorver, Enxerto racha a peça mais blindada, Relicário com cor própria e os Corvos recolhendo os mortos da Catedral (sem contradizer a lore). **25 fichas `revisao: aprovada`**; `enemy_elemental_fogo_poluido` (Brasa Profunda) e `enemy_polvo_esgoto` (Polvo dos Destroços) ficam `pendente` até o coordenador decidir a pendência (a) abaixo — hoje são os 2 únicos erros do lint/`validate_content` (U11) e a única falha em `tests/test_spec349_onda_nova_arcadia.py::test_revisao_independente` e `tests/test_fase71.py::test_repo_content_sem_erros`. Resultado: **21 novas + 6 slots**, cotas: famílias 6/5/4/6, lacaio 6 / padrão 9 / elite 5 / chefe 1 (Roda de Mandíbulas), 7 demônios distintos (Fehk, Maalrek, Dorrhen, Veth, Daruun, Vhrak, Solvhara), ≥ 5 habitats por anel.
- **Ajuste no gate (D3):** `contar_cotas()["total"]` passa a contar só `status: nova` (reinventada/adotada ocupa slot); os demais contadores seguem incluindo os slots. Teste em `test_cotas_regiao`.
- **Convenção de refs (U10):** os `refs` das fichas apontam para a lore da **SPEC-348** (que pousa antes e reescreve `lore_nova/`); neste worktree algumas linhas ainda caem em texto antigo. O revisor marcou 9 como "erradas" por isso; a convenção foi explicada e fica registrada aqui. `daily_life.txt:320` (Sino Mudo, calendário G-13) só existe na 348, por isso a Traça cita `locations.txt:61` + `daily_life.txt:9`.
- **Pendências para o coordenador:** (a) o revisor objeta às adoções Brasa Profunda (Montanhas) e Polvo dos Destroços (Costa Negra) — pontes de lore inventadas nas fichas (forjas compradas aos Anões; gaiolas dos Nobres-Colecionadores); a curadoria da Etapa 2 fixa as 6 adoções e não foi alterada — decidir se trocam por reinvenção/adoção local (candidata: Prisioneiro-do-Nível-Dez); (b) follow-ups técnicos sugeridos: U10 conferir se a linha citada contém o nome do `detalhe`; um U14 comparando `mecanica_assinatura.frase`/`contra_jogo` entre fichas (os pares mecânicos escaparam porque U7/U13 olham a Carta, que só existe na Etapa 5); (c) Skarath, Veleth, Urath, Lyss, Morvath, Thessavar sem cria nesta onda (mapa de `_esteira.yaml`, Etapa 7); (d) o doc de arte base `docs/arte/BESTIARIO_VALORIA_ARTE.md` segue não versionado (D9).

**Slots refeitos e D10 (autor Opus, 28/10).**

- **Pendência (a) resolvida.** O coordenador aceitou a objeção D-B do revisor. `enemy_elemental_fogo_poluido` e `enemy_polvo_esgoto` deixam de adotar a Brasa Profunda e o Polvo dos Destroços (docs do Codex intocados) e viram `reinventada`, nos mesmos ids e com os campos de slot iguais ao snapshot (R3):
  - **Caído do Cadinho** (Reescritos, elite, `bruto_de_linha`, Anel de Ferro): fundidor com a Ferrugem do Sangue que caiu na panela de gusa. O ferro das veias chamou o metal e ele saiu com telhas de escória sobre o músculo cru, que ferve sem brilhar. É o único que esfria: trava como lingote e parte a própria crosta para voltar.
  - **Bagre de Varal** (Bestas Tortas, elite, `emboscador`, Anel de Lama): bagre sem pele, com placas de osso sobre o músculo, que nada pelo ar dentro de um bolsão da água do Pântano que não cai. Afoga o alvo de pé, e o alvo preso só joga 1 Carta por rodada.
  - O Prisioneiro-do-Nível-Dez foi avaliado e não adotado: o doc é um grupo, sem anatomia; o Oubliette já é da Centopeia; e adotar apagaria o mistério da lore. Os conceitos 49–54 e os cortes estão em `docs/spec349/conceitos-nova_arcadia.md` §4.
- **Revisão.** Rodada 4 em `handoffs/SPEC-349-independent-review.md` (`spec-reviewer`, Opus). Bagre APPROVED. Caído CHANGES: o corpo puxava para o golem de magma e para a paleta do Lençol. O texto pré-aprovado pelo revisor foi aplicado (músculo cru e fumegante, sem luz própria, punhos num malho), e as duas fichas estão `revisao: aprovada`.
- **Arquivos.** Curadoria: 30 reinventar + 4 adotar (`scripts/bestiario/curadoria.py`; o YAML foi corrigido só nas duas entradas, porque regenerar inteiro desloca as linhas `data/bestiary.json:N` e faz os slots já renomeados contarem hits do próprio doc). `test_adotado_aponta_codex_fisico` agora fixa 4 adoções. `gerar_docs.py` passou a tirar o `codex_id` velho de slot reinventado. O Codex dos 2 slots, o doc de arte e os rumores foram regenerados.
- **Para a Etapa 5.** Os slots mantêm `immunities: igneo` (Caído, coerente) e `resistances: corrosivo` (Bagre, coerente com o despejo). A carta-assinatura de cada um é `cri_caido_do_cadinho_partir_a_crosta` e `cri_bagre_de_varal_cabeca_na_agua`.
- **D10 aprovado pelo coordenador (28/10).** Os nomes em jogo das famílias são **Reescritos · Bestas Tortas · Cobrados · Crias de Apetite** (`familias_em_jogo:` na ficha e linha `Tipo:` do Codex).
- **Modelo de autoria (dono, 28/10).** O autor de prosa passa a ser o Opus; o Fable só entra por pedido explícito. As 25 fichas anteriores seguem `autor: fable`, como registro. O template das ondas 2–12 (`docs/templates/spec-bestiario-onda.md`, R28) ainda não existe e já nasce com Opus.

### Respostas do coordenador (27/10, autorizado pelo dono a decidir)

- **D4 (adotar de `creatures.txt`):** sim, com teto de 1/3 da cota da região. O dono pediu criaturas
  **novas e inovadoras**. A adoção só vale para uma criatura física de `creatures.txt` que ainda não tem
  ficha mecânica e passa no gate U1–U13.
- **D7:** o coordenador revisa a voz numa amostra de 20 %, e além disso lê todas as criaturas da família
  "corpos reescritos", que é a referência do dono (os Lycans).
- **D1–D3, D5, D6, D8–D12:** default aceito.
- **D10 (28/10):** aprovados os nomes Reescritos · Bestas Tortas · Cobrados · Crias de Apetite.
- **D4 (28/10):** Brasa Profunda e Polvo dos Destroços deixam de ser adoção e viram reinvenção (Caído do Cadinho, Bagre de Varal).
- **Divisão de execução:**
  - Etapas 0–2: executor técnico, podem começar já.
  - Etapas 3–4 (tabuleiro, conceitos e prosa): um agente Opus, depois do pouso da 348 (dono, 28/10: Fable nunca, salvo pedido explícito).
  - Etapas 5–7: executor técnico.
  - Etapa 8: revisores independentes (Opus para unicidade, Sol para a parte técnica).
- **Referências externas:** só inspiração, com a fonte registrada no doc da onda.

### Integração das 12 regiões (02/11)

Ondas autoradas em branches separadas e integradas por merge `--no-ff` (spec-359 + 10 `bst-*`). Campo `onda:` das fichas normalizado pela ordem do D9; `spec: SPEC-349` em todas, exceto o Pântano (`SPEC-359`).

| Onda | Região | spec |
|---|---|---|
| 1 | nova_arcadia | SPEC-349 |
| 2 | pantano_melancolia | SPEC-359 |
| 3 | pradaria_ruinas | SPEC-349 |
| 4 | brekmar | SPEC-349 |
| 5 | deserto_zhur | SPEC-349 |
| 6 | costa_negra | SPEC-349 |
| 7 | montanhas_afiadas | SPEC-349 |
| 8 | floresta_sussurros | SPEC-349 |
| 9 | selva_xylos | SPEC-349 |
| 10 | skallgard | SPEC-349 |
| 11 | aethelgard | SPEC-349 |
| 12 | ophidia | SPEC-349 |

- Pareceres das ondas 3–12 dobrados em seções de `handoffs/SPEC-349-independent-review.md` (nome por região não passa em `check_handoff_names.py`); links nos `conceitos-*.md` ajustados.
- `COTAS_ONDA` ganhou uma entrada por região (demônios mínimos, obrigatórios de lugar fixo: Lyss/Brekmar, Urath/Zhur, Thessavar/Floresta, Morvath/Aethelgard; `habitat_min`).
- Lint global em 0 erro. Correções para zerar R29 (crias do mesmo demônio com mesma anatomia entre regiões): Altivo do Vidro (`bipede_curvado`), Cabeça Acima (`segmentado`), Rixa Costurada (material `ferro_ferrugem`), Costura de Rancor (`composto`), Mastro dos Últimos (material `couro_tecido`). Para o `validate_content`, 14 `action_hint` de fuga dos slots ganharam verbo de recuo/fuga.

- **Revisão cruzada entre regiões aplicada (T1–T24, `handoffs/SPEC-349-independent-review.md`).** Renomes: Provador de Ophidia → Contrabandista Vítreo; Atirador de Olhos Vítreos → Arqueiro de Tendão; Iguana de Salmoura → Petrel de Papo Cheio (`alado`); Costura das Duas Cidades → Retalho das Duas Cidades; Rixa Costurada → Estivador das Facas (corpo único `bipede_ereto/ferro_ferrugem/grande`); Costura de Rancor → Peso dos Vencidos; Mapa de Cicatriz → Marco que Aponta; Enegrecido da Porta → Enegrecido que Espera (Dorrhen → Fehk, `controlador`). Despenseiro de Espinhos passa a Daruun; Mastro dos Últimos `sal_mineral`. Desvios literais: (a) a silhueta do Petrel trocou "maior que a cabeça" por "quase do tamanho da cabeça" (U5 proíbe "maior"); (b) `lint.py` passou a ler `data/bestiario/_esteira.yaml` e repassá-lo ao `lint_global`, senão o R27 nunca rodava; (c) nomes antigos nos `conceitos-*.md` foram substituídos só no nome (a mecânica descrita ali segue a pré-revisão); `revisao-brekmar.md`, o parecer e esta spec mantêm os nomes antigos como histórico. `_esteira.yaml` criado (12 regiões `pousada`; demônios: Daruun 4, Fehk 2, Dorrhen 8, Maalrek 7; R27 sem erro).

### Etapas 5, 6 (mecânica dos slots) e 7 — mecânica, baralho, arena e integração das 12 regiões (Terra, 02/11)

**Recuperação do WIP de 28/10 (`stash@{0}`, só a onda 1).** Nada de `pop`: li o patch e reaproveitei três peças. (1) `data/bestiario/mecanica/nova_arcadia.yaml`: as 27 criaturas da onda 1 com Cartas e dicas, mais quatro assinaturas que eram só de apoio e passaram a abrir com um golpe (ver abaixo) e uma 3ª Carta inicial para a Roda de Mandíbulas. (2) `scripts/bestiario/arena.py`: ganhou `--ids` para qualquer região e o delta de ±8 pp só vale quando o slot estava na faixa antes. (3) O gerador, reescrito para as 12 regiões. O `bestiary.json` atual manda: só entram as 249 entradas novas e, nos 32 slots, `cartas`/`cartas_autorais`/`tactical_profile.padrao|assinatura`; nome, descrição, `appearance` e campos de slot (R3) não são tocados. O stash continua intacto para o coordenador descartar.

**Fluxo (fonte única, idempotente).**
- `data/bestiario/mecanica/<regiao>.yaml` (281 criaturas): Cartas com nome, texto (≤ 140 chars, sem número) e efeitos no vocabulário da SPEC-330. Os textos vêm das fichas (`mecanica_assinatura`, `telegrafo`, `contra_jogo`) condensados no léxico de Valoria. A 1ª Carta é o ataque básico (a que a IA joga com `off`); a assinatura (`sig`) tem o id da ficha. Chefe: `fases` 60 % e 40 % com `baralho_extra`, `padrao`, `assinatura` e `narracao` com `{nome}`.
- `scripts/bestiario/gerar_mecanica.py --regiao X|--todas`: escreve `data/cards/criaturas/<regiao>.json` (12 arquivos, 689 Cartas, todas passam em vocabulário, orçamento, voz e nomes únicos), as entradas do bestiário e só a chave `fases` do `_decks.json` (13 chefes, incluindo `enemy_aranha_de_cristal` e `enemy_boss_general_escorpiao`, cujas fases antigas eram da concepção velha).
- Números: Vitalidade e espaços de Ferimento pela tabela de Corpo; Virtudes por tabela de categoria + papel + escala (`VIRT_*`); dado do ataque por categoria. Chefes ganham `acoes_por_rodada: 2` e `vitalidade_por_nivel_encontro: 12` como no `migrate_bestiary_v4.py` (testes 287/290/295) e Corpo ≥ 2 (invariante "chefe tem mais Vitalidade que lacaio").
- `scripts/bestiario/calibrar.py`: ajuste numérico por criatura fora de 45–85 % em `off` ou `on`, com 4 dials (`corpo`, `forca`, `dano` do ataque básico e da assinatura, `sig` só da assinatura). Slots só aceitam `dano`/`sig` (Virtudes congeladas, R3). Cada ajuste e a leitura da arena que o motivou ficam em `data/bestiario/mecanica/_ajustes.yaml` (R26: "cada ajuste é registrado"). Se um ajuste estoura o orçamento da Carta, o gerador sobe o Fôlego e depois tira dano (`_fit_orcamento`).
- Rumores: `build_rumor_seeds.py` regenerado (+249 avistamentos). Três seeds ganharam override `public_names` (`Vespa`, `Vespa`, `Névoa`) porque o nome da criatura contém um nome do catálogo (teste 312).
- `scripts/bestiario/painel.py` → `docs/bestiario/PAINEL.md`; guia `docs/guias/BESTIARIO.md`; template `docs/templates/spec-bestiario-onda.md`.

**Arena (40 seeds × 5 Posturas, MockLLM, L3 para lacaio/padrão/elite e L5 para chefe; `off` e `on`).** Relatórios por região em `docs/spec349/arena-<regiao>.md` e `.json`; baseline dos 32 slots em `docs/spec349/arena-slots-baseline.json` (medido antes de qualquer Carta nova).

**Resultado por região no HEAD pós-sync, baseline dos 32 slots remedido na `main` atual (criaturas dentro de 45–85 % em cada modo; "ambos" = nos dois).**

| Região | Criaturas | off em 45-85 % | on em 45-85 % | ambos | fora (id: off/on) |
|---|---|---|---|---|---|
| nova_arcadia | 27 | 25 | 27 | 25 | 2 |
| pantano_melancolia | 22 | 21 | 20 | 20 | 2 |
| pradaria_ruinas | 22 | 22 | 20 | 20 | 2 |
| brekmar | 20 | 19 | 18 | 18 | 2 |
| deserto_zhur | 26 | 25 | 23 | 22 | 4 |
| costa_negra | 22 | 21 | 21 | 21 | 1 |
| montanhas_afiadas | 27 | 26 | 24 | 23 | 4 |
| floresta_sussurros | 25 | 24 | 21 | 20 | 5 |
| selva_xylos | 22 | 21 | 21 | 20 | 2 |
| skallgard | 23 | 22 | 22 | 21 | 2 |
| aethelgard | 25 | 25 | 25 | 25 | 0 |
| ophidia | 20 | 19 | 19 | 18 | 2 |
| **Total** | 281 | 270 | 261 | 253 | 28 |

**Fora da faixa em `off` ou `on` (28 de 281; criatura: `off`/`on`).**

- nova_arcadia: mon_convidado_de_cera: 41%/84%
- nova_arcadia: enemy_polvo_esgoto: 44%/72%
- pantano_melancolia: mon_borda_que_anda: 75%/41%
- pantano_melancolia: enemy_zumbi_blindado: 42%/33%
- pradaria_ruinas: mon_chifres_travados: 64%/29%
- pradaria_ruinas: enemy_esqueleto_legiao_antiga: 48%/42%
- brekmar: mon_casco_de_costelas: 63%/32%
- brekmar: mon_torcido_da_rinha: 34%/86%
- deserto_zhur: mon_cavador_de_funil: 46%/88%
- deserto_zhur: enemy_aranha_de_cristal: 53%/28%
- deserto_zhur: mon_aguadeiro_de_bucho: 56%/88%
- deserto_zhur: enemy_boss_general_escorpiao: 90%/56%
- costa_negra: mon_hospede_do_estomago: 42%/32%
- montanhas_afiadas: enemy_minotauro_esqueleto: 82%/14%
- montanhas_afiadas: enemy_mimico_bau: 60%/87%
- montanhas_afiadas: enemy_troll_ponte: 44%/51%
- montanhas_afiadas: mon_peso_dos_vencidos: 66%/26%
- floresta_sussurros: enemy_urso_coruja_mutante: 64%/40%
- floresta_sussurros: mon_besouro_do_estalo: 75%/86%
- floresta_sussurros: mon_toldo_das_clareiras: 47%/32%
- floresta_sussurros: mon_mapa_de_cicatrizes: 41%/65%
- floresta_sussurros: mon_desafiante_rubro: 70%/44%
- selva_xylos: mon_escavador_das_camaras: 66%/30%
- selva_xylos: mon_isca_amarrada: 43%/76%
- skallgard: mon_ticao_do_juramento: 42%/77%
- skallgard: enemy_lobo_invernal: 46%/44%
- ophidia: mon_puxado_do_oeste: 41%/84%
- ophidia: mon_vigia_de_cor_errada: 46%/91%

- Leitura: 9 chefes (todos com `on` < 45 % exceto o General Escorpião, `off` 90 %): os dials chegaram ao mínimo e o baralho de família (332) mais as 2 ações por rodada dominam; Corpo não desce de 2 (invariante de Vitalidade). Os demais 19 têm `off` e `on` divergentes ou 1 a 4 pp fora. Parte da diferença vem do rebase sobre a `main` (SPEC-362 baixou a Vitalidade do Arcanista; SPEC-355/358 mexeram no motor) e das Cartas restauradas do R3 (abaixo). Não recalibrei: o critério é medir no código que pousa e registrar.
- Delta de 8 pp dos slots que estavam na faixa antes (comparação com `round(…, 1)`, então −8,0 pp passa): 6 estouram (Quimera de Cristal `on` −9,0; Verme de Vidro `off` +8,5; Ent Dormindo `on` +18,5; Basilisco `off` −18,0/`on` +11,5; Coisa do Esgoto `on` −9,5; Jötunn `on` −10,0). Pelo veredito completo do `arena.py` (faixa e delta): **247 de 281**.

**Efeitos que o motor atual NÃO suporta (efeito ideal × aproximação).** 145 das 281 criaturas têm a linha `aprox:` no yaml (`grep -n "aprox:" data/bestiario/mecanica/*.yaml`). Os pedidos pelo coordenador e as demais classes:

| Efeito ideal da ficha | Criatura | Aproximação na gramática atual | O que faltaria no motor |
|---|---|---|---|
| veneno determinístico: sorteia por semente sono/febre/cãibra/dor, sem repetir seguido | Escorpena de Basalto | `enfraquecido` 2 rodadas + `dot` 1 × 3 | efeito aleatório seeded por ferroada com memória do último |
| aperto pelo valor carregado (ouro, relíquia, melhor arma) | Ninho dos Mergulhadores | `enraizado` 2 + `torpor` fixos | `escala.por` lê a Carga do ATOR (`card_effects.scaled_value`), não o valor do alvo |
| baixa a Vitalidade máxima do herói até descansar | Trépano de Borda | `rachadura` 2 + `sangria` 1 | efeito que reduz `max_vitalidade` do alvo temporariamente |
| desvia cura, reforço e Fôlego do alvo para si | Rêmora de Convés | `purga_condicao` + `cura` própria | gatilho "alvo ganha X" com redirecionamento |
| placa torta/rachadura reparável gastando uma ação | Besouro de Alavanca | `armadura_comprometida` 3 rodadas + `rachadura` | condição que só sai por ação do alvo |
| refém: metade do dano do grupo no Novelo vai ao preso | Novelo de Anzóis | `enraizado` 2 + `proteção` | redirecionamento de dano entre atores |
| terreno/cena persistente criado por Carta (fileira de estacas, mancha da maré, poça, espinheiro, chão nu, represa) | Estaqueiro, Lavado, Caldeireiro, Ouriço, Recusado, Castor | `proteção`/`provocação`/`dot`/`mover_alvo_zona`/`enraizado` | objetos de cena criados por Carta de inimigo |
| convocar lacaios | Saltador de Palafita, Escuta do Sinal | `buff_acerto`/`buff_dano` em aliados | spawn de ator em combate |
| agir primeiro, ação extra, golpe sem Reação | Parado do Sopro, Virado do Avesso, Pernalta do Conselho | `buff_iniciativa`/`buff_dano` | bloqueio de Reação e ações extras por Carta |
| desviar o golpe ou o alvo do herói | Guia Avesso, Mapa de Cicatrizes, Costurado de Lentes | `desmoralizado` + `marca` | redirecionamento de alvo declarado |
| tirar o herói da luta ou levar item | Boia de Braços, Vespa Coveira, Despenseiro, Lacrador | `enraizado`/`atordoado`/`desarmado_risco` | remoção temporária de ator e transferência de item |
| dependência de luz, vento, água ou sol | Vidrado, Iniciado Refratado, Cabeleira de Vidro, Nadador Escaldado | efeito fixo | estado ambiental legível por Carta (`se: clima/luz`) |
| devolve/copia a última Carta do alvo | Cordão de Medida, Colecionador de Poses | golpe + `empurrão`; `revelar` + `torpor` | `copiar_ultima` só vale para o próprio ator |
| fase por ferida específica (patas de Goblin, estacas, tirante) | Peso dos Vencidos, Borda que Anda, Parelha Carmesim | fases por Vitalidade (60/40) | fases por parte do corpo |

**Desvios e decisões a registrar.**
1. **R14, `family_key` dos slots (resolvido, coordenador 02/11).** 8 fichas de slot propunham `arquetipo` diferente do bestiário; o campo do slot é congelado (R3), então a ficha (e a vaga) passou a repetir o do bestiário; `test_family_key_bate` exige igualdade; lint 0 erro.
2. **Teto de 15 usos por Carta de família (332).** Com 405 criaturas o uso chega a 31. Os 3 testes da 332 passaram a contar só a população original (`origem != bestiario-349`); `test_uso_das_cartas_de_familia_escala_com_o_bestiario` fixa o teto atual em 36. Pendência para a 336: crescer os pools de família.
3. **`test_conflito_autoria_bestiario`**: `_hidden_card_ids` agora varre as Cartas recursivamente (R33). **`test_boss_phases`**: `len(bosses) == 12` virou `>= 12`.
4. **Chefes no `off` e no `on`.** Os dials de chefe chegaram ao mínimo (dano −7, força −7) e vários seguem fora no `on`: o baralho de família e as ações duplas dominam. Corpo ficou em 2 por causa do invariante de Vitalidade.
5. **Assinaturas só de apoio** (buff/proteção em aliados) deixavam a criatura passiva sozinha na arena: as 12 mais afetadas passaram a abrir a Carta com um golpe leve.
6. **Slot chefe `enemy_aranha_de_cristal` (resolvido).** O `type` legado ("Monstrosidade (Gigante)") virou `BOSS`, e a linha `BOSS:` do art brief aparece; o teste cobre os 13 chefes.
7. **Arena do slot fora da faixa antes** (ex.: Aranha de Cristal 5 %, General Escorpião 9 %): a faixa 45–85 % manda; o delta de 8 pp só vale quando o slot estava na faixa.
8. **Follow-ups (coordenador, 02/11).** (a) O teto de 15 usos por Carta de família (332) só volta a valer para a esteira com mais Cartas de família na SPEC-336. (b) Os chefes ficam abaixo de 45 % no `on` (9 chefes), por causa do baralho de família e das 2 ações por rodada.
9. **Revisão Sol (Etapa 8) e correções, 02/11.** (P2-1) O delta da arena compara com `round(…, 1)`. (P1-1) Baseline dos 32 slots remedido com o `bestiary.json` da `main` atual no mesmo motor e arena completa no HEAD pós-sync (números acima). (P1-2) `test_save_load_com_criatura_nova_e_slot_em_bestiary_knowledge` cobre `off` e `on`. (P2-3) Os 16 slots que perdiam um `kind` de efeito do R3 (`dot`, `marca`, `esconder`, `aplicar_condicao`, `empurrao`, `protecao`) recuperaram o `kind` como efeito secundário da assinatura (`dot` 1 × 2 rodadas, `marca` 1, `esconder` 1, `desmoralizado` 1, `empurrao` 1, `protecao` 2); nenhum ficou como desvio, e o orçamento das Cartas segue verde. (P2-4) `validate_bestiary_identity` passa `_esteira.yaml` ao `lint_global`, então o R27 roda no `validate_content`. (P2-5/6) Docstring do teste de `appearance` e `cartas` das 5 entradas SPEC-355 do snapshot atualizados.
10. **`test_spec289_ameaca_tematica` (regressão apontada pelo executor da 360).** Os 4 testes fixavam "a única temática" da esfera. A esteira acrescentou temáticas legítimas em Aethelgard (Alambique de Carne, combatente da Destilação; Camarão Faxineiro entrava por coincidência de radical com "Câmara"; o radical `camarao` agora é próprio em `world_utils._theme_stems` e ele não é mais temático) e, nos slots reinventados, o Pajem de Obsidiana (ex-Sentinela de Ferro, radical `obsidi` da Chama Azul) entrou e a Quimera de Cristal virou Ariranha de Arcada, saindo do tema. A lógica da 289 está correta; o teste passou a medir sobre a população anterior à esteira (fixture) mais um teste novo que exige que, com a população cheia, o sorteio fique sempre dentro das temáticas da esfera. O fallback de porte estrito retira o Pajem da população do teste.
11. **Suíte completa do pouso (5 falhas, corrigidas).** (a) `test_card_lint` conta o legado fixo em 332: o catálogo agora também carrega as Cartas de criatura (o inimigo as resolve por id), então o teste exclui `origem: bestiario-349` do legado. (b) `test_card_sim::test_sim_flags_dominant_card`: com a população cheia o uso da Carta sintética cai a 52 % (< 60 %) e a bandeira sai pelo delta de vitória, que exige 40 lutas; o teste passou a 8 seeds (72 lutas). (c) `test_no_silent_except`: o `except` de `validate_bestiary_identity` vira Finding de erro e foi anotado `# silent-ok`. (d) `test_spec325_reinforcements`: o Arqueiro de Tendão é um Lacaio próprio da facção `bandos_nomades`, então é o reforço da mesma facção (comportamento pedido pela 325), no lugar do genérico. (e) `test_tactical_archetypes_runtime`: 5 criaturas usam `arquetipo: abissal` (família do baralho 332); `abissal` entrou em `_ENEMY_ARCHETYPE_ACTIONS` (foge muito ferido, ataca) em `services/tactical_profile.py`.

