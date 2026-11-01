# SPEC-355 — Cartas: pendências abertas do épico (regras do motor, conteúdo e balanço final)

> **Status:** `approved`
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Origem:** levantamento do coordenador em `docs/spec355/pendencias.md` (19 itens em 4 blocos), conferido item a item no source da `main` (`9daed66c`) — §1.1
> **Depende de:** SPEC-339 `done`, SPEC-341 `done`; código das SPEC-328–336, 346, 347, 353 e 354 na `main` (353 aguarda só o smoke do coordenador)
> **Desbloqueia:** ligar as flags de cartas no staging (`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_ENEMY_DECKS`, `RPG_SCENE_CARDS`, `RPG_CARD_REWARDS`) com o épico sem pendência de motor
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (motor de conflito, presságio, balanço)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator muda: `scripts/cards/sim.py`, `docs/spec335/arena_posturas.py`, `docs/spec341/arena_spec341.py`, `data/cards/_orcamento.json`, `tests/spec330_equivalence.py`, `tests/fixtures/spec330_legacy_golden.json` (protegido, `evals/protected-paths.txt:14`), `tests/fixtures/spec330_card_text_snapshot.json` e `tests/fixtures/router_off_golden.json` ficam **sem diff** (R50). A única mudança de teste de balanço alheio (R44) segue protocolo próprio, em commit separado e por outro agente.

---

## 1. Contexto & Objetivo

O dono pediu (28/10): "pegue todos os ajustes que ainda estão em aberto, faça uma spec e execute". O
coordenador listou 19 pendências do épico de cartas espalhadas em handoffs e §9 das SPEC-335/336/339/341/
342/345/346/347/352/353/354. Esta spec confere cada uma no source, descarta o que já está resolvido,
e transforma o resto em etapas executáveis por um agente.

A ordem importa. O balanço (bloco A) vem **por último** porque mede o motor que o bloco B muda: a correção do
R8b (item 7) altera a duração de buffs de Reação dos inimigos, que a arena exercita. Por isso a arena "base"
desta spec é medida **depois** do bloco B (Etapa 7) e é contra ela que o bloco A se compara. O bloco D é
operacional e fica só como critério do coordenador (§5.2).

Princípios: **mecânica é Python** (nenhum item passa pelo LLM); **integridade de eval** — o executor não toca
avaliador, orçamento nem golden; carta legada só pelo protocolo D7/R11 da SPEC-339; carta de onda muda no
máximo **1 passo**, só número/custo, `versao`+1, ajuste nas sementes **0–19** e confirmação nas **20–99**
uma vez só; **sem flag nova** (R51).

### 1.1 Conferência das 19 pendências no source

| # | Pendência | Situação | Evidência (source da `main`) |
|---|---|---|---|
| 1 | Utilitárias fora da compra em combate + recalibrar Médico | **aberta** | A compra inclui toda Carta do baralho, exceto as de descanso já gastas: `services/card_piles.py:169-177` (comentário do D6 revertido em `:175-176`). O baralho aceita `utilitaria` por `_DECK_TIPOS` (`services/cards.py:414`). Na mão, a utilitária aparece como "Sem efeito no conflito" (`services/card_text.py:28-32`). Arena do D6: Médico 54,6 → 57,3 % (+2,7 pp), Arcanista −1,3 pp (`docs/spec353/arena.md:16-19`). Com −1,3 pp, o Arcanista iria de 45,8 % para ~44,5 % no total, **abaixo do piso de 45 %** (`docs/spec346/arena.md:19,24`), achado que a 353 não registrou |
| 2 | Provocação na mesma rodada | **aberta** | Com presságio `on`, o inimigo executa a declaração congelada (`services/conflict_orchestrator.py:2622-2635`), e a Provocação só é lida em `enemy_declaration` → `_taunt_target` (`:656-660`, `:439-470`), ou seja, no próximo congelamento. O teste da 339 fixa "exatamente 1 declaração afetada" (`tests/test_spec339_duracao_condicoes.py:538-563`) |
| 3a | `san1_sil_corte_sem_aviso` forte demais | **aberta** | Carta v2 (`data/cards/posturas/sangromante_silencioso.json:191-223`: `dano_base` 6, Fôlego 2). Ficou `dominante` na held-out (+9,1 pp, uso 52 %; `docs/spec341/RELATORIO.md:71,78`), e o dono aceitou "para a próxima onda" (`specs/SPEC-341-balanco-sangromante.md:353-355`). A 341 já fez o passo dela (Fôlego 1→2). Nesta spec cabe **um** passo novo |
| 3b | `san_exp_espetaculo` (legada) | **resolvida por evidência: só registrar** | É legada e está no golden (`tests/fixtures/spec330_legacy_golden.json:9671`; `data/cards/sangromante.json:181-206`). A bandeira **não se confirmou** com sementes novas: +8,3 pp nas 0–19 × **−4,0 pp** nas 20–99, veredito "ruído" (`docs/spec341/RELATORIO.md:27`; `docs/spec341/r8-bandeiras-sementes20-99.json:35`). Sem bandeira confirmada, a regra do dono manda só registrar. O protocolo D7 não é acionado |
| 4 | Emboscada no pior caso | **aberta** | Com emboscada em 100 % das lutas, Corruptor fica em 42,7 % e Arcanista em 39,2 % (`docs/spec346/arena.md:14-30`; wrapper `docs/spec346/arena_spec346.py:27-30`). A frequência real sai de `detection_check` (d20 + Mente contra CD 8+2×perigo; `world_utils.py:1501-1522`), usado só no encontro de viagem (`agents/storyteller.py:1593-1605`). Hoje só `dev_zel_vigilia` anula a emboscada (`agents/combat.py:1783-1808`), e essa Carta é `buff_iniciativa` (`data/cards/devoto.json:358-371`) |
| 5 | Cartas 2d6 em `exemplos.json` | **aberta** | `golpe_devoto`, `corte_sangrento`, `praga_lenta` e `raio_cinza` têm `formula: "2d6"` (`data/cards/exemplos.json:18,96,191,236`), que o motor rola pela via legada (`services/conflict_turn.py:276-277,749-750`). O arquivo é fixture ("cartas de EXEMPLO para os testes do motor", `:2`), mas as Cartas entram no pool jogável porque `cards_for_class` não as filtra (`services/cards.py:287-298`), e a criação só as põe no fim da fila (`character_creator.py:239-246`). As quatro estão no golden (`spec330_legacy_golden.json:5105,7070,8921,8966`), então **converter** exigiria o protocolo de golden |
| 6a | `full_deck` com viés de ordem | **resolvida na 339** | O desempate por hash estável está em `scripts/cards/sim.py:101-109` (SPEC-339 §5.1) |
| 6b | Arena por substituição; bandeira de "uso" rebaixada a aviso | **fora desta spec (avaliador)** | Hoje os braços são `sem` e `sem`+cópias, por acréscimo (`sim.py:319-331`), e `uso > 60 %` vira `dominante` (`sim.py:362-371`). Mudar isso é mudar o avaliador, e quem otimiza o produto não pode fazê-lo (D16) |
| 7 | R8b: buff de Reação em si mesmo dura 1 turno a menos | **aberta** | `_mark_fresh_conditions` só marca stat positivo dado por **aliado** no turno de um ator do mesmo time (`services/conflict_orchestrator.py:306-316`). O buff que o reagente põe em si durante o turno do inimigo não é marcado e expira no fim do turno do próprio reagente (`:334-353`). Desvio registrado na 339 (`specs/SPEC-339-controle-duracao-tick.md:224`). O chamador da Reação (`:1111-1118`) está **fora** do caminho do golden; `_resolve_reaction_effect` (`:1121`) está **dentro** (`tests/spec330_equivalence.py:127-130`) |
| 8 | Chefe abaixo de 35 % depois do anúncio | **aberta** | O `prenuncio` é congelado no fim da rodada N para a assinatura de N+2 (`services/enemy_decks.py:387-401`; `agents/combat.py:2751-2766`; `services/conflict_orchestrator.py:2848-2856` no modo sem presságio). Se em N+1 o chefe cai para ≤ 35 % ou troca de fase, `plan()` não joga a assinatura (`enemy_decks.py:369-376`, `_badly_wounded` em `:379-384`; fase nova só depois de 1 rodada em `:353-354`), e **nada no registro diz** que a promessa caiu. Follow-up da 332 (`specs/SPEC-332-cartas-05-baralhos-inimigos-por-faccao.md:118-120`; `handoffs/SPEC-332-sol-review.md:187`) |
| 9 | Router: heurística quando os 3 CLASSIFY falham | **aberta** | `_hostility_target` aceita qualquer criatura do bestiário citada, mesmo ausente da narração (`agents/router.py:350-353`; limite P3-10). Substantivo humano ("guarda", "saqueador") só vale se for NPC em cena, inimigo ou manifesto (`:345-364`; P3-6). "para abrir caminho" cai em `_NON_COMBAT_CONTEXT_RE` (`:294-297`; P3-11). Limites aceitos em `specs/SPEC-346-cartas-smoke-narracao.md:681` |
| 10 | Queda por Reação sem golpe final | **aberta** | `final_blows` só é gravado por `_check_terminal(..., record=True)` nos chamadores do turno, DoT e auto-dano (`services/conflict_orchestrator.py:1440,1979,2778`; wrapper em `:1525-1541`). A Reação não grava (SPEC-353 §9). O resumo perde a autoria (`services/round_log.py:452-482`) |
| 11a | "Descarga Arcana" no "Renegado (machado)" | **causa localizada** | O "Renegado do Ermo" ataca com "Machado de Caçada" e arpão, mas tem `arquetipo: "conjurador"` (`data/bestiary.json:5585-5628`; perfil `tatico` em `:5622`). `family_key` usa o `arquetipo` (`services/enemy_decks.py:144-152`), então ele recebe o baralho da família `conjurador`, com `bst_descarga_arcana`. O filtro R38a não pega porque ele tem ataque à distância (`:213-218`). Também muda a IA: `conjurador` = `control` (`services/tactical_profile.py:214-218`) |
| 11b | O 6 do Penitente foi Proteção? | **só no smoke** | `Proteção −N` já aparece no `mech_log` (SPEC-353 R20). Critério do coordenador (§6) |
| 12 | Gerador regrava arquivos sem `--force` | **aberta** (o caminho é `scripts/gen_tiers_5_plus.py`, não `scripts/cards/`) | Sem argumento, o laço regrava **todo** `data/cards/*.json` com classe (`:222-244`), inclusive `tier`/`level_req` de Cartas de onda; também regrava `data/classes.json` (`:265-267`) e `tiers_5_plus.json` (`:279`), com `write_text` sem `newline="\n"` (CRLF no Windows). O `--force` só protege `KEEP_FIELDS` (`:272-277`). Incidente em `handoffs/SPEC-335-sol-review.md:35,75,85` |
| 13 | `cards_for_class("")` | **aberta** | `or class_name == ""` devolve as Cartas de **todas** as Posturas (`services/cards.py:295`). Só um teste usa (`tests/test_scene_cards_extra.py:120`). `progression.py:91,258` chega aqui com ficha sem `class_name` (`handoffs/SPEC-335-sol-review.md:179`) |
| 14 | `armadura_comprometida` sem texto legível | **aberta** | A condição existe (`combat_mechanics.py:202`) e é usada em `data/cards/corruptor.json` e `data/combat/cartas_de_cena.json:387`, mas não tem rótulo em `_CONDICAO_LABEL` (`services/card_effects.py:1332-1341`, consumido em `:1400-1401`). O nome da condição no ator é a chave crua (`combat_mechanics.parse_condition`, `:148-149`), e a view repassa como veio (`api.py:2889-2894`) |
| 15 | `arc1_cal_leitura` com aviso `revelar intencao` | **aberta, e a Carta é inerte** | A Carta só tem `revelar intencao` (`data/cards/posturas/arcanista_cinzento_calibrado.json:5-31`). O efeito grava `_revelado` e um log (`services/card_effects.py:736-743`), mas **ninguém lê `_revelado`**: `knowledge_level` ignora o campo (`services/enemy_intent.py:207-216`). O lint avisa que ela "duplica o presságio" (`services/card_lint.py:325-342`) |
| 16 | Cartas neutras na loja e nas missões | **fora desta spec (feature nova)** | O único caminho de obtenção é o espólio pós-conflito (`agents/combat.py:2846-2849` → `services/card_rewards.py:29,115-119`). Loja e missões pedem preço (economia), dados de missão e front (D15) |
| 17–19 | Smoke final, migration de retratos, 319 P2-1 | **coordenador** | Critérios em §5.2 e §6 |

## 2. Requisitos

Valem com as flags de cartas `on`, salvo indicação. Com `off`, o comportamento fica byte a byte o de hoje,
exceto R1–R3, que corrigem o motor base, como a 339 fez.

### B. Motor / regras (itens 7, 2, 8, 10, 9)

- **R1 — Buff de Reação em si mesmo dura o que diz (item 7).** No chamador da Reação
  (`_open_reaction_window`, perto de `services/conflict_orchestrator.py:1116-1117`), o orquestrador tira um
  snapshot das condições do reagente antes de `_resolve_reaction_effect`. Depois, toda condição **nova**
  só-stat no reagente com `ac`/`protection` positivos recebe `source_actor_id = rid`. A gravação fica no
  chamador, **nunca** dentro de `_resolve_reaction_effect`. `_mark_fresh_conditions` passa a marcar
  (`_pula_tick`) a condição só-stat positiva de `ac`/`protection` em `aid ≠ current_actor_id` com
  `source_actor_id == aid`. Resultado testável: uma Proteção d=1 que o reagente põe em si no turno do
  inimigo ainda vale no **próximo ataque desse inimigo**, nas duas ordens de iniciativa. Hoje ela expira
  no fim do turno do reagente.
- **R2 — Provocação vale na mesma rodada (item 2; D1).** Com presságio `on`, em `_enemy_decl`, antes de
  cumprir uma intenção congelada do tipo `ataque`/`ataque_multiplo`: se o inimigo tem uma Provocação
  aplicada **nesta rodada** (entrada em `out["condicoes_novas"]` com `control == "taunt"` para ele) cuja
  fonte está viva, é oponente e **é diferente** do `alvo_id` congelado, o motor rola `_taunt_target`
  (mesma chance: 50 % × multiplicador de Entropia, teto 90 %). Se passar, o `target_id` da declaração passa
  a ser o provocador.
  - **Uma declaração por aplicação.** Depois dessa rolagem, passando ou não, a Provocação perde 1 de
    duração. Se chegar a 0, sai depois da ação do inimigo, com a linha "terminou". Assim o congelamento do
    fim da rodada não a lê de novo. O teste da 339 (`test_presagio_on_taunt_d1_afeta_exatamente_uma_declaracao`)
    continua verde **sem mudar o expected**.
  - Se o alvo congelado **já é** o provocador, o motor não rola (o rng não é consumido; a arena solo não
    muda).
  - Registro: `out["pressagios_desviados"]: [{actor_id, alvo_original, alvo_novo, por}]` e a linha
    "<Inimigo>, provocado por <Fonte>, muda de alvo." (passa pela troca para "Você" da SPEC-353 R36). Em
    falha, a linha de resistência que já existe (SPEC-353 R39a). Não dispara `ao_pressagio_frustrado`.
  - Com presságio `off`/`shadow`, nada muda (a decisão tardia já lê a Provocação).
- **R3 — Promessa do chefe nunca cai calada (item 8; D8).** Quando um `prenuncio` público é emitido para o
  inimigo X (agente, `agents/combat.py:2764`; orquestrador sem presságio, `conflict_orchestrator.py:2854`),
  grava-se `scene["prenuncios"][X] = {"carta": <assinatura>, "rnd": <rodada da assinatura>, "fase_idx":
  <fase atual>}`. É chave de **cena**, como `taunt_resistidos`, e nunca vai para o ator. Na decisão (ou no
  congelamento) da rodada prometida, se X está vivo, presente e **não** joga a Carta prometida, registra-se
  `out["pressagios_frustrados"]` com `{actor_id, tipo: "assinatura", motivo}`, em que `motivo ∈
  {"troca_de_fase", "muito_ferido", "impossivel"}` (nessa precedência), mais uma linha legível: "<X>
  abandona o golpe que preparava: <a nova fase o muda | ferido demais | não há como>.". A promessa sai da
  cena depois de cumprida ou frustrada. A regra 332 P1-4 (muito ferido não joga a assinatura) **não muda**.
  Na rodada em que o chefe troca de fase, a linha da fase vem **antes** da linha de frustração, e o
  presságio público seguinte não traz o `prenuncio` antigo.
- **R4 — Queda por Reação tem autor (item 10).** No mesmo chamador do R1, o orquestrador compara
  `deaths/terminal/incapacitated` de todos os atores antes e depois de `_resolve_reaction_effect`. Para
  cada mudança, chama `_record_final_blow(out, tid, by=rid, cause="reacao", card_id=card["id"])`; a
  assinatura ganha `card_id: str | None = None`. O tipo novo `"reacao"` entra nos fatos (`round_log`) pelo
  ramo de ator já existente ("Golpe final: <Reação> de Você em X" / "Quem derrubou o herói: <nome>") e no
  fallback determinístico. Cartas de efeito e Carta de cena seguem sem registro (fora de escopo).
- **R5 — Router com presença narrada (item 9; D9).** Só no fallback em que os 3 CLASSIFY falharam:
  - (a) **Criatura do bestiário** só conta como alvo se um token do nome dela aparecer nas **2 últimas**
    falas da IA, em `state["enemies"]` ou no manifesto. Fecha a P3-10.
  - (b) **Substantivo humano** de uma lista fechada (`guarda`, `sentinela`, `soldado`, `saqueador`,
    `salteador`, `bandido`, `ladrao`, `mercenario`, `capanga`, `cultista`, `cacador`, `assassino`,
    `pirata`, `contrabandista`, nos plurais também) conta como alvo presente se aparecer dobrado nas 2
    últimas falas da IA. Fecha a P3-6.
  - (c) `_NON_COMBAT_CONTEXT_RE` com "para abrir/arrombar/…" **não bloqueia** quando o objeto do verbo
    hostil resolveu para um alvo humano/criatura presente por (a), (b) ou pelas regras atuais. Fecha a
    P3-11. Contexto de jogo ("numa partida", "de dados") continua bloqueando sempre.
  - (d) Bateria ampliada (§4, Etapa 6): os 12 casos seguros da 346 continuam STORY e os novos casos de
    combate abrem COMBAT. Nenhum caso do caminho normal (CLASSIFY respondendo) muda.

### C. Conteúdo / autoria (itens 12–15, 11a)

- **R6 — Gerador não escreve por acidente (item 12).** `scripts/gen_tiers_5_plus.py`: o default vira
  `--check` (calcula, não grava, sai com 1 se algo mudaria e lista os arquivos). Gravar exige `--write`;
  `--force` mantém o sentido atual (sobrescrever `KEEP_FIELDS`). Toda gravação usa `newline="\n"`, o
  formato atual (`indent=2`, `ensure_ascii=False`) e **pula arquivos sem diferença**. O laço de
  `tier`/`level_req` (`:225-238`) **ignora** Cartas com campo `onda`.
- **R7 — Classe vazia só devolve neutras (item 13; D12).** `cards_for_class("")` devolve só Cartas neutras
  (`classe ∈ {"", "Neutra", "neutra", None}` ou `neutra: true`), com o mesmo predicado de
  `card_rewards.py:119`, extraído para `cards.is_neutral(card) -> bool`. Nunca devolve Carta de Postura.
- **R8 — Rótulo de condição na exibição (item 14; D14).** Novo `card_effects.condition_label(raw: str) ->
  str`: `_CONDICAO_LABEL` → glossário → mapa novo `_CONDICAO_LABEL_EXTRA` (`armadura_comprometida` →
  "Armadura Comprometida", `enfraquecido` → "Enfraquecido", `sangrando` → "Sangrando") → fallback
  `raw.replace("_", " ").capitalize()`. É usado em `card_text.effective_rule_text` (pós-processa o texto
  estático), nas linhas humanas do `round_log`, no `mech_log`/`round_board` e na view (`api._combat_block._conds`
  ganha `label`; `name` fica crua por compatibilidade; o front usa `label ?? name`). **Não muda** o nome
  gravado no ator (golden), `_CONDICAO_LABEL` nem `render_card_text` (snapshot de texto da 330).
- **R9 — `revelar intencao` passa a valer (item 15; D11).** `enemy_intent.knowledge_level(enemy, carta_id)`
  devolve `"estudada"` quando `"intencao" in enemy.get("_revelado", [])`. A partir daí, o presságio público
  desse inimigo mostra faixa, valor estimado e nome da Carta pelo resto do conflito. `card_lint`: `intencao`
  sai de `REVELAR_PUBLICO_AVISO`, com comentário que aponta esta spec. `arc1_cal_leitura` não muda e passa
  no lint sem aviso.
- **R10 — Renegado do Ermo sem baralho de conjurador (item 11a; D13).** `data/bestiary.json`
  `enemy_renegado_ermo.arquetipo`: `"conjurador"` → `"tatico"` (igual ao `behavior.profile`). Nova regra de
  `services/content_validator.py` (`warning`): criatura com `arquetipo` conjurador/místico sem nenhum ataque
  de tipo mágico (nenhum `attacks[*].type ∈ {"magic", "area"}`, os tipos não físicos do bestiário — ex.
  `data/bestiary.json:347,1137`) e sem `abilities`. As outras criaturas
  que a regra pegar ficam **listadas em §9**, sem correção nesta spec.

### A. Balanço (itens 1, 5, 3a, 4) — depois do bloco B

Leitura e faixas: piso **45 %** e teto **85 %** por Postura na leitura **total** (padrão+elite, como em
`docs/spec346/arena.md`); teto **75 %** por subclasse na leitura **padrão**, com as exceções aceitas na 341
(`tests/test_spec341_balanco.py:233-237`: avaro 75,2, silencioso 76,6, todas 75,6 na held-out). Avaliador:
`docs/spec341/arena_spec341.py` (congelado), níveis 1/3/5, `padrao` + `elite`, em série.

- **R11 — Utilitárias fora da compra (item 1; D3).** `card_piles.start_piles`: Carta `tipo: utilitaria` do
  baralho não entra em `compra`. Vai para `piles["fora_do_conflito"]` (lista nova, opcional em save
  antigo) e nunca é comprada, embaralhada nem descartada no conflito. O baralho (`player["deck"]`, 12–24) não
  muda. Fora de combate e no Acervo, a utilitária segue como hoje. Teste: nenhuma mão de 200 conflitos
  simulados (5 Posturas × 40 seeds) contém utilitária.
- **R12 — Cartas 2d6 fora do pool jogável (item 5; D2).** As quatro (`golpe_devoto`, `corte_sangrento`,
  `praga_lenta`, `raio_cinza`) entram em `cards.EXEMPLO_FORA_DO_POOL: frozenset[str]` e saem de
  `cards_for_class`, da criação, da progressão, do espólio e do `full_deck` da arena, que lê
  `cards_for_class`. Continuam em `cards.all_cards()`/`get_card`: o golden, os testes do motor e os saves que
  já as têm continuam funcionando. O JSON das Cartas **não** muda.
- **R13 — Recalibração (item 1).** Com R11+R12 aplicados, nas sementes 0–19, toda Postura fica dentro de
  ±2,0 pp do seu valor pós-B (Etapa 7, total) **e** dentro de 45–85 %. Se não ficar: no máximo **1 Carta de
  onda por Postura fora da faixa**, 1 passo (alavancas da 341 R4: ±1 `dano_base`/`valor`, ±1 Fôlego ou
  Entropia, 1 degrau de `frequencia`), `versao`+1, lint e `fx.budget_error` limpos. A Carta é escolhida pela
  atribuição (`arena_spec341.py atribuicao`, 0–19): a de maior |Δ| entre as de onda presentes no baralho
  L1–L5 da Postura. Sem Carta que resolva em 1 passo: parar, registrar em §9 e não aplicar um 2º passo.
- **R14 — `san1_sil_corte_sem_aviso` (item 3a; D4).** Um passo: `dano_base` 6 → 5, `versao` 2 → 3.
  Critérios: `cartas --seeds 0:20` com delta ≤ +8,0 pp (sem `dominante`); silencioso padrão ≤ 76,6 % e ≥
  65 %; Sangromante total ≥ 45 %. Se o passo não tirar a bandeira, ele **fica** se não violar as faixas, e a
  pendência é registrada sem 2º passo.
- **R15 — Legada intocada (item 3b).** `san_exp_espetaculo` não muda. §9 registra a evidência (341: ruído
  nas 20–99). O protocolo D7 da 339 **não** é acionado.
- **R16 — Emboscada realista (item 4; D6).** Novo `docs/spec355/arena_spec355.py`, que só **importa** o
  avaliador congelado, como fez o `docs/spec346/arena_spec346.py`, e calcula:
  - `p_emb(Postura, nível)` = média, em perigo ∈ {1, 2, 3, 4}, de P(d20 + `wis` + `perc` < 8 + 2×perigo),
    enumerando o d20 com a ficha que a arena usa (`wis`/`perc` como em `world_utils.detection_check`),
    `perception_mod` 0 e **f_viagem = 1** (cota superior: toda luta tratada como encontro de viagem);
  - taxa realista por célula = `p_emb × emboscada + (1 − p_emb) × base`, com `emboscada` do wrapper da 346
    rodado nas mesmas sementes;
  - com contrapartida (R17): na célula cujo `full_deck(cls, nível, sub)` tem Carta `buff_iniciativa`, a
    parcela de emboscada vale a de base.
  Grava `docs/spec355/arena-emboscada-{0-19,20-99}.json` e `RELATORIO-emboscada.md`.
- **R17 — Contrapartida só se preciso (item 4; D6).** Se alguma Postura ficar abaixo de 45 % na taxa
  realista (0–19), `agents/combat._has_vigilia` passa a aceitar **qualquer** Carta com `efeito.kind ==
  "buff_iniciativa"` no baralho/preparadas, não só `dev_zel_vigilia`. São Cartas existentes, sem número novo:
  `medico.json`, `sangromante.json`, `devoto.json` e `arcanista.json` ×2. Se a Postura continuar abaixo
  (o Corruptor não tem nenhuma), registra-se como **exceção pendente** em §9 e não há número novo nesta spec.
- **R18 — Confirmação uma vez.** Com R11–R17 fechados nas 0–19, uma única rodada nas 20–99 grava
  `docs/spec355/arena-confirmacao.json` (`posturas` + `cartas` das Cartas alteradas + emboscada realista),
  com `versoes`. Sem reajuste depois dela. Fora da faixa na held-out = registro em §9 para o dono, como na
  341 D4-ter.

### Transversais

- **R44 — Teste de artefato da 341.** Se R13/R14 subirem a `versao` de uma Carta que está em
  `docs/spec341/arena-*.json["versoes"]`, `tests/test_spec341_balanco.py::test_arena_versoes_batem_com_catalogo`
  falha por desenho. O ajuste, que é aceitar a versão do catálogo quando
  `docs/spec355/arena-confirmacao.json["versoes"][cid]` for igual a ela, é um commit **separado**
  (`test(arena): accept SPEC-355 superseding artifact`) feito pelo coordenador ou por outro agente, nunca pelo
  executor, com revisão Sol (D17).
- **R45 — Artefatos da 355.** `tests/test_spec355_arena.py` lê `arena-final.json` (0–19) e
  `arena-confirmacao.json` (20–99) e asserta as faixas acima, as `versoes` iguais ao catálogo e
  `len(alteradas) ≤ 4`.
- **R50 — Avaliador e goldens sem diff.** `git diff main -- scripts/cards/sim.py docs/spec335/arena_posturas.py
  docs/spec341/arena_spec341.py data/cards/_orcamento.json tests/spec330_equivalence.py
  tests/fixtures/spec330_legacy_golden.json tests/fixtures/spec330_card_text_snapshot.json
  tests/fixtures/router_off_golden.json` vazio. `tests/test_card_effects_grammar.py` e
  `test_spec341_balanco.py::test_legadas_intactas` verdes sem regenerar nada. Tudo o que é gravado novo
  (`source_actor_id` no R1, `pressagios_desviados`, `scene["prenuncios"]`, `final_blows` de reação) nasce fora
  de `ct.resolve_turn` e `orch._resolve_reaction_effect`.
- **R51 — Sem flag nova** em `config/flags.yaml`.
- **R52 — Saves.** `piles["fora_do_conflito"]`, `scene["prenuncios"]` e `label` são opcionais. Save sem eles
  carrega: utilitária já na `compra` de um conflito em voo continua comprável até o próximo conflito.
- **R53 — Sem LLM novo.** Nenhum `with_structured_output` novo; nenhum prompt muda.

### Fora de escopo

- Cartas neutras na loja e nas missões (item 16): spec própria (preço, dados de missão, front; D15).
- Arena por substituição e bandeira de "uso" como aviso (item 6b): mudança de avaliador, spec de
  eval-authoring por outro agente (D16).
- Converter as quatro Cartas 2d6 para `dano_base` (exigiria regenerar o golden); qualquer mudança em Carta
  legada; um 2º passo em Carta já ajustada nesta spec.
- Contrapartida de emboscada com número novo (R17 só usa Cartas existentes).
- Provocação furando o presságio de quem **não** ataca (defesa, fuga, apoio); `ao_pressagio_frustrado` no
  desvio por Provocação.
- Golpe final em Carta de efeito/Carta de cena (só Reação, R4).
- Corrigir outras criaturas que a regra do R10 apontar (só listar).
- Bloco D (itens 17–19): executado pelo coordenador (§5.2).

## 3. Design técnico

### 3.1 Arquivos novos

- `docs/spec355/arena_spec355.py`: subcomandos `base` (chama `arena_spec341.posturas` para as 5 Posturas e
  as subclasses; `--seeds`, `--out`) e `emboscada` (wrapper de `run_round` como em
  `docs/spec346/arena_spec346.py:27-30`, mais o cálculo de `p_emb` e a mistura do R16). Só importa o avaliador.
- `docs/spec355/arena-pos-b-{0-19,20-99}.json`, `arena-a1-0-19.json`, `arena-final.json`,
  `arena-emboscada-{0-19,20-99}.json`, `arena-confirmacao.json`, `RELATORIO.md`, `RELATORIO-emboscada.md`.
- Testes: `tests/test_spec355_reacao_buff.py` (R1), `test_spec355_provocacao_rodada.py` (R2),
  `test_spec355_promessa_chefe.py` (R3), `test_spec355_golpe_reacao.py` (R4), `test_spec355_router_fallback.py`
  (R5), `test_spec355_conteudo.py` (R6–R10), `test_spec355_compra_utilitaria.py` (R11),
  `test_spec355_exemplos_fora.py` (R12), `test_spec355_arena.py` (R45), `test_spec355_guardas.py` (R50–R52).

### 3.2 Arquivos alterados

- `services/conflict_orchestrator.py`: R1 (snapshot e tag no chamador da Reação; um ramo novo em
  `_mark_fresh_conditions`), R2 (`_enemy_decl`), R3 (verificação da promessa na decisão sem presságio), R4
  (`_record_final_blow(card_id=…)` no chamador).
- `services/enemy_decks.py` (helper `promised_signature(actor, rnd) -> str | None`), `services/enemy_intent.py`
  (R9 e o registro da promessa no congelamento), `agents/combat.py` (gravar `scene["prenuncios"]` e checar no
  congelamento, R3; `_has_vigilia` no R17, só se ativado).
- `services/round_log.py` (R4 `reacao`, R8 rótulos, linhas de R2/R3), `services/combat_preview.py` (R8 no
  `mech_log`/`round_board`).
- `agents/router.py` (R5). `scripts/gen_tiers_5_plus.py` (R6). `services/cards.py` (R7 `is_neutral`, R12
  `EXEMPLO_FORA_DO_POOL`). `services/card_rewards.py` (passa a usar `cards.is_neutral`).
  `services/card_effects.py` (só `condition_label` e `_CONDICAO_LABEL_EXTRA`; nenhum renderizador estático
  muda). `services/card_text.py`, `api.py` (`_conds.label`), `web/src` (1 linha: `label ?? name` no chip de
  condição; o executor localiza com `Grep "active_conditions" web/src`). `services/card_lint.py` (R9).
  `data/bestiary.json` (1 campo, R10), `services/content_validator.py` (R10). `services/card_piles.py` (R11).
- Cartas de onda (R13/R14): `data/cards/posturas/sangromante_silencioso.json` e, se a Etapa 9 exigir, 1
  arquivo de Postura por Postura fora da faixa.

### 3.3 Formatos

`scene["prenuncios"]` (R3):

```json
{"enemy_chefe_bandido_1": {"carta": "bst_golpe_de_misericordia", "rnd": 4, "fase_idx": 1}}
```

`out` de uma rodada com desvio por Provocação (R2):

```json
{"pressagios_desviados": [{"actor_id": "fallback_criatura_1", "alvo_original": "npc_ketil",
  "alvo_novo": "player", "por": "player"}]}
```

Registro: `Criatura, provocada por Você, muda de alvo.` Frustração (R3): `Chefe dos Bandidos abandona o
golpe que preparava: a nova fase o muda.`

`final_blows` por Reação (R4):

```json
{"target_id": "fallback_criatura_1", "kind": "reacao", "by_actor_id": "player",
 "card_id": "dev_reacao_x", "condition": null}
```

(`dev_reacao_x` = qualquer Carta `tipo: reacao` de dano real do acervo; o teste usa um id real.)

## 4. Plano passo a passo

Cada etapa: testes primeiro → código → só os testes do escopo, `-n 2` no máximo. Toda etapa roda também
`tests/test_card_effects_grammar.py` e `tests/test_spec339_duracao_condicoes.py` (R50). A arena roda **em
série**, em background com timeout explícito, um processo por vez. Antes de cada rodada de arena, medir a
RAM livre (regra do CLAUDE.md).

### Etapa 0 — Diagnóstico (sem código de produto)

1. Rodar e anotar as contagens de `tests/test_card_effects_grammar.py`, `test_spec339_duracao_condicoes.py`,
   `test_spec341_balanco.py`, `test_spec346_router_fallback.py`, `test_spec353_*` (escopo, `-n 2`).
2. Listar em §9 as Cartas `tipo: reacao` cujo efeito dá `ac`/`protection` ao reagente (alvo do R1) e as
   criaturas com `arquetipo` conjurador/místico sem ataque mágico (prévia do R10).

### Etapa 1 — Conteúdo e ferramentas (R6–R10)

1. **Testes:** `test_gen_tiers_default_is_check_and_writes_nothing` (roda `main([])` num `tmp_path` com
   cópia de 2 arquivos; nenhum arquivo muda; sai com 1 se divergir); `test_gen_tiers_skips_onda_cards`;
   `test_gen_tiers_write_uses_lf`; `test_cards_for_empty_class_only_neutral`;
   `test_condition_label_armadura_comprometida` (rótulo na mão, no registro e na view; `render_card_text`
   igual ao snapshot); `test_revelar_intencao_makes_pressagio_estudada` (depois de `arc1_cal_leitura`, o
   `public_round` traz `carta_nome`); `test_arc1_cal_leitura_lint_clean`;
   `test_renegado_family_is_not_conjurador` (baralho sem `bst_descarga_arcana`);
   `test_validator_warns_caster_without_spell`.
2. **Implementação:** como §3.2.

### Etapa 2 — Buff de Reação em si mesmo (R1)

1. **Testes:** `test_reaction_self_protection_d1_lasts_until_next_enemy_attack[ordem]` (Reação real com
   Proteção no reagente; o ataque do mesmo inimigo na rodada seguinte vê a Proteção);
   `test_tag_is_outside_resolve_reaction_effect` (chamar `_resolve_reaction_effect` direto não grava
   `source_actor_id`); `test_enemy_reaction_buff_also_marked` (simetria).
2. **Implementação:** chamador da Reação + ramo novo em `_mark_fresh_conditions`.

### Etapa 3 — Golpe final por Reação (R4)

1. **Testes:** `test_reaction_kill_records_final_blow` (contra-ataque mata o atacante → `kind: "reacao"`,
   `by`, `card_id`); `test_facts_and_fallback_name_reaction`; `test_enemy_reaction_downs_hero_has_author`.
2. **Implementação:** chamador da Reação, `_record_final_blow`, `round_log`.

### Etapa 4 — Provocação na mesma rodada (R2)

1. **Testes:** `test_taunt_same_round_redirects_frozen_attack` (presságio `on`, `hero_first`, aliado
   congelado como alvo, `_Rng0` → o ataque vai para o Devoto **nesta** rodada, com a linha de desvio);
   `test_taunt_same_round_spends_one_declaration` (o congelamento seguinte não lê de novo; reaproveita o
   cenário de `tests/test_spec339_duracao_condicoes.py:460-476`); `test_taunt_no_roll_when_already_target`
   (rng não consumido); `test_taunt_resisted_same_round_line`; `test_non_attack_intent_not_redirected`;
   `test_intent_off_unchanged`. O teste da 339 `test_presagio_on_taunt_d1_afeta_exatamente_uma_declaracao`
   tem de continuar verde **sem mudança**.
2. **Implementação:** `_enemy_decl`.

### Etapa 5 — Promessa do chefe (R3)

1. **Testes:** `test_prenuncio_broken_by_low_vitality_is_logged` (fases `[60, 35]`; anúncio no fim de N; em
   N+1 um golpe leva de 50 % a 30 %; no congelamento de N+2 há `pressagios_frustrados` com motivo
   `troca_de_fase`, a linha da fase vem antes da de frustração e não há `prenuncio` velho); mesmo cenário sem
   troca de fase → `muito_ferido`; `test_prenuncio_kept_is_not_frustrated`; `test_prenuncio_intent_off_path`
   (via log do orquestrador); `test_prenuncios_live_in_scene_not_actor`.
2. **Implementação:** como §3.2.

### Etapa 6 — Router (R5)

1. **Testes** (`tests/test_spec355_router_fallback.py`, CLASSIFY simulado esgotado):
   - COMBAT: "sem pensar ataco o saqueador" (saqueador na última fala da IA); "ataco o guarda para abrir
     caminho" (guarda narrado); "golpeio o bandido" (bandido em `enemies`); "ataco o lobo" (lobo na
     penúltima fala).
   - STORY: "ataco o lobo" sem lobo nas 2 últimas falas; "golpeio a porta para abrir caminho"; "não ataco o
     guarda"; "fui atacado pelo guarda"; "numa partida de dados ataco o rei"; "ataco o meu medo"; "enfrento a
     subida"; "ataco o guarda" sem guarda narrado.
   - `tests/test_spec346_router_fallback.py` inteiro verde **sem mudar expected**, exceto o caso que codifica
     a P3-10 (criatura do bestiário fora de cena abrindo combate), se houver; nesse caso, listar em §9 com o
     motivo (limite aceito → corrigido).
2. **Implementação:** `agents/router.py`.

### Etapa 7 — Arena pós-B (base do bloco A)

1. `bash scripts/dev/py.sh docs/spec355/arena_spec355.py base --seeds 0:20 --out docs/spec355/arena-pos-b-0-19.json`,
   depois `--seeds 20:100 --out …-20-99.json`, em série.
2. Comparar com `docs/spec353/arena.md` (20–99). Δ por Postura vai para `RELATORIO.md`. Mover a arena é
   esperado só pelo R1 (Reação de inimigo). Se alguma Postura sair de 45–85 % por causa do bloco B, registrar;
   o bloco A trata.

### Etapa 8 — A1: utilitárias e 2d6 (R11, R12)

1. **Testes:** `test_no_utility_in_combat_hand` (5 Posturas × 40 seeds); `test_utility_kept_in_deck_and_acervo`;
   `test_old_save_with_utility_in_compra_loads`; `test_exemplo_2d6_out_of_pool` (fora de `cards_for_class`,
   da criação e do `full_deck`; `get_card` ainda funciona; golden verde).
2. **Implementação:** `card_piles.start_piles`, `cards.EXEMPLO_FORA_DO_POOL`.
3. Arena 0–19 → `arena-a1-0-19.json`; tabela Δ contra `arena-pos-b-0-19.json`.

### Etapa 9 — A2: recalibração (R13)

1. Para cada Postura fora de ±2 pp ou de 45–85 %: `arena_spec341.py atribuicao --cls <Postura> --sub "" --seeds 0:20`,
   escolher a Carta pelo R13, aplicar 1 passo e rodar `posturas --seeds 0:20 --classes <Postura>`.
2. **Testes:** `test_alteradas_versao_lint_orcamento` (para cada Carta alterada: `versao`+1, lint limpo,
   `budget_error is None`).

### Etapa 10 — A3: `corte_sem_aviso` (R14)

1. `dano_base` 6→5, `versao` 3; `arena_spec341.py cartas --seeds 0:20 --ids san1_sil_corte_sem_aviso` e
   `posturas --seeds 0:20 --classes "Sangromante:silencioso" Sangromante`.
2. Gravar `arena-final.json` (0–19, todas as Posturas, `versoes`).

### Etapa 11 — A4: emboscada (R16, R17)

1. `arena_spec355.py emboscada --seeds 0:20` → `p_emb`, taxa realista e `RELATORIO-emboscada.md`.
2. Se alguma Postura < 45 %: **testes** `test_buff_iniciativa_card_negates_ambush` (as 5 Cartas) e
   `test_no_buff_iniciativa_keeps_ambush`; implementar R17; medir de novo (0–19).

### Etapa 12 — A5: confirmação 20–99 (R18, R45) e registro da legada (R15)

1. Uma rodada: `posturas --seeds 20:100` (todas), `cartas --seeds 20:100 --ids <alteradas>`,
   `emboscada --seeds 20:100` → `arena-confirmacao.json` com `versoes`. Sem reajuste.
2. `tests/test_spec355_arena.py` (R45).
3. Se R44 se aplicar, **parar** e avisar o coordenador no hand-back (commit separado por outro agente).

### Etapa 13 — Guardas (R50–R53)

1. `test_spec355_guardas.py`: `git diff` vazio nos caminhos do R50 (como `test_golden_files_have_no_diff_against_main`
   da 353); `find_record_keys` (`tests/spec330_equivalence.py:46-57`) com as chaves novas sobre `LAST_STATE`
   não acha nada em actors/scene do golden; nenhuma flag nova; saves sem os campos novos carregam.

## 5. Critérios de aceite

### 5.1 Do executor

- [ ] §9 com a Etapa 0, a evidência da legada (R15) e as criaturas apontadas pelo R10
- [ ] R1: Proteção de Reação em si mesmo vale até o próximo ataque do inimigo, nas duas ordens
- [ ] R2: desvio na mesma rodada com 1 declaração por aplicação; teste da 339 verde sem mudança
- [ ] R3: toda promessa (`prenuncio`) é cumprida ou frustrada com linha e motivo; fase antes da frustração
- [ ] R4: queda por Reação com golpe final e autoria nos fatos e no fallback
- [ ] R5: bateria nova verde; `test_spec346_router_fallback.py` sem regressão nos casos seguros
- [ ] R6–R10: testes da Etapa 1 verdes; `arc1_cal_leitura` sem aviso; Renegado sem Descarga Arcana
- [ ] R11/R12: nenhuma utilitária na mão de conflito; 2d6 fora do pool; golden verde
- [ ] R13/R14: no máximo 4 Cartas de onda alteradas, 1 passo cada, `versao`+1, lint e orçamento limpos
- [ ] R16/R17: `RELATORIO-emboscada.md` com `p_emb` por Postura e taxa realista; contrapartida só se < 45 %
- [ ] R18: confirmação 20–99 rodada **uma vez**; desvios na held-out registrados para o dono
- [ ] R50: avaliador, orçamento, golden, snapshot de texto e `router_off_golden` sem diff
- [ ] R51–R53: nenhuma flag nova, saves antigos carregam, nenhum LLM novo
- [ ] Revisão independente Sol sem P0/P1 aberto

### 5.2 Do coordenador (bloco D e pouso)

- [ ] R44 (se aplicável): commit separado do teste da 341 por outro agente, com revisão Sol
- [ ] `uv run pytest` verde (suíte completa, 1× no pouso)
- [ ] **Item 17:** smoke real final (§6 das 346/347/352/353/354 + §6 desta) no staging com as cartas `on`,
      gravando o corpo de `/game/history` (Livro) em `docs/spec355/smoke-final.md`
- [ ] **Item 18:** migration `20261028120000_creature_portraits.sql` aplicada no staging, bucket
      `rpg-shared-art` criado e 1–3 gerações reais de retrato (SPEC-352 §6) registradas
- [ ] **Item 19:** SPEC-319 P2-1 — `replace` do stream medido no combate, número no CHANGELOG
- [ ] **Item 11b:** no smoke, o golpe do Penitente mostra `Proteção −N` quando o alvo tem defesa; se o dano
      cair **sem** essa linha, abrir P1 de motor

## 6. Smoke test com LLM real (coordenador; ≤ 20 turnos; DeepSeek primário)

API local `legacy` com as flags de cartas `on` (`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_ENEMY_DECKS`,
`RPG_SCENE_CARDS`, `RPG_CARD_REWARDS`). Depois repetir os passos 1, 3 e 5 no staging (item 17). Registrar em
`docs/spec355/smoke-final.md`, sem segredos.

1. **Devoto com Ketil, presságio `on`:** com o presságio mirando Ketil, jogar "Voto Sussurrado" →
   na mesma rodada, "…provocado por Você, muda de alvo." ou "…resiste à Provocação." (R2). Mão sem "Aguentar"
   (R11).
2. **Arcanista calibrado:** jogar "Leitura de Pressão" → o presságio seguinte mostra o nome da Carta do
   inimigo (R9).
3. **Corruptor ou Carta de cena com Armadura Comprometida:** o chip e o registro dizem "Armadura
   Comprometida", nunca `armadura_comprometida` (R8).
4. **Skallgard, Renegado do Ermo:** baralho e registro sem "Descarga Arcana" (R10). Golpe do Penitente em
   alvo com defesa → `Proteção −N` no `mech_log` (item 11b).
5. **Vitória com Reação, se houver:** o resumo cita o autor da Reação (R4). Anotar a latência do turno de
   desfecho.
6. Router: não é testável no real (só age com os 3 CLASSIFY falhando); coberto pela bateria da Etapa 6.

## 7. Riscos & compatibilidade

- **R1 muda o motor em `off`** (como a 339): inimigos com Reação de Proteção ficam um pouco mais duros. A
  Etapa 7 mede, e o bloco A parte desse número.
- **R2 muda o balanço só em grupo** (a arena é solo, sem desvio possível). O efeito real só aparece com
  aliado; o smoke §6.1 e os testes de motor cobrem. O "uma declaração por aplicação" mantém a semântica da 339.
- **R11 pode derrubar o Arcanista abaixo de 45 %** (−1,3 pp na 353 sobre 45,8 %). O R13 trata com 1 passo.
- **R12 muda o `full_deck`** de quem tinha as 2d6 no baralho de arena. O A1 mede junto com o R11.
- **R16 é uma leitura nova.** As fórmulas (`p_emb`, f_viagem = 1, mistura) estão fixadas aqui pelo autor da
  spec, e não pelo executor, para que o executor não desenhe o critério que vai cumprir. f_viagem = 1
  superestima a emboscada, o lado seguro.
- **R5:** um falso positivo abre um combate que o jogador declarou ("ataco o guarda"), e um falso negativo
  cai em STORY, que é o lado seguro de hoje. O caminho normal do CLASSIFY não muda.
- **R10** muda a IA do Renegado (`control` → perfil tático). É coerente com o texto da criatura; fica fora da
  arena (categoria `lacaio`).
- **R44** é o ponto de integridade: o teste da 341 trava versões. Quem otimiza não o edita.
- **Saves:** R52. **MockLLM/FallbackLLM:** sem impacto (R53). **Quota/latência:** nenhuma chamada nova.

## 8. Decisões

### Do dono

- **28/10 — "faça e execute":** spec nasce `approved`. Itens que dependem de gosto são decididos pela
  recomendação e ficam **revogáveis**.
- **Regras do pedido:** mecânica é Python; o avaliador, o orçamento e o golden da 330 não mudam; carta
  legada só pelo D7 da 339 e só com bandeira confirmada em sementes novas; carta de onda com 1 passo, só
  número/custo, `versao`+1, 0–19 ajuste, 20–99 confirmação uma vez.

### Do autor (valem como aprovadas; revogáveis pelo dono)

- **D1 — Provocação na mesma rodada: sim (R2)**, uma declaração por aplicação, só sobre intenção de ataque,
  sem rolar quando o alvo já é o provocador e sem disparar `ao_pressagio_frustrado`. Cumpre o que o texto
  promete sem dobrar o efeito (preserva a 339).
- **D2 — As quatro Cartas 2d6: tirar do pool jogável (R12)**, sem converter. São fixture (`exemplos.json:2`),
  e converter mexeria no golden. O catálogo as mantém para testes e saves.
- **D3 — Utilitárias fora da compra em combate: sim (R11)**, com recalibração (R13).
- **D4 — `corte_sem_aviso`: `dano_base` 6→5 (R14).** A 341 mediu esse passo antes (77,5 % com Fôlego 1;
  75,4 % somado ao Fôlego 2, `docs/spec341/RELATORIO.md:43-44`); é o único passo que sobra no limite.
- **D5 — `san_exp_espetaculo`: só registrar (R15).** Ruído confirmado nas 20–99.
- **D6 — Emboscada: medir a mistura realista com f_viagem = 1 (R16).** Contrapartida só abaixo de 45 %:
  Cartas `buff_iniciativa` anulam a emboscada (R17), generalizando a regra que já vale para a Vigília
  Ciumenta. Sem Carta assim (Corruptor), a Postura fica como **exceção pendente**.
- **D7 — R8b da Reação: implementar com tag no chamador (R1)**, sem tocar no golden.
- **D8 — Promessa do chefe: frustração explícita (R3)**, sem forçar a assinatura de um chefe muito ferido. Mantém
  a 332 P1-4 e torna o registro honesto.
- **D9 — Router: presença narrada (R5)**, só no fallback.
- **D10 — Golpe final por Reação (R4).**
- **D11 — `revelar intencao` vira "estudada" (R9)** e sai do aviso do lint. A Carta deixa de ser inerte sem
  mudar número.
- **D12 — `cards_for_class("")` = só neutras (R7).**
- **D13 — Renegado do Ermo: `arquetipo` → `tatico` (R10)**; as outras criaturas só são listadas.
- **D14 — `armadura_comprometida`: rótulo só na exibição (R8)**; o estado, o texto estático e o snapshot não mudam.
- **D15 — Cartas neutras na loja/missões: spec própria.** Precisa de tabela de preço (número de economia), dados
  de missão e front.
- **D16 — Arena por substituição e bandeira de uso como aviso: spec de avaliador própria**, com
  `EVAL_AUTHORING_REQUIRED: true` e outro agente. Esta spec usa o avaliador como está.
- **D17 — Teste de versões da 341 (R44):** commit separado do coordenador ou de outro agente + Sol.
- **D18 — `gen_tiers_5_plus.py`: default `--check` (R6).**

### Para o dono confirmar (não bloqueiam a execução)

1. D1 (Provocação na mesma rodada) e D2 (Cartas 2d6 fora do pool).
2. D6: se o Corruptor ficar abaixo de 45 % na emboscada realista, aceitar a exceção ou abrir spec com número
   novo (ex.: Carta `buff_iniciativa` para o Corruptor).
3. D15 (loja/missões) e D16 (avaliador): reservar as duas specs?

## 9. Registro de implementação

**Etapa 0.** Baseline verde (grammar, 339, 341, 346: ~290 testes). Cartas `reacao` com `ac`/`protection`
no reagente: `bst_defesa_instintiva` (inimigo), `san_esquiva` e afins do jogador. Criaturas com `arquetipo`
conjurador/místico sem ataque `magic`/`area` nem `abilities` (regra nova do validador, `warning`): a lista sai de
`uv run python scripts/validate_content.py` (só o Renegado foi corrigido).

**R15 (`san_exp_espetaculo`).** Legada; a bandeira não se confirmou (+8,3 pp nas 0-19 × -4,0 pp nas 20-99,
"ruído", `docs/spec341/r8-bandeiras-sementes20-99.json`). Nada mudou; D7 não acionado.

**Desvios da spec**
- **R10:** a causa da "Descarga Arcana" no Renegado não era só o `arquetipo`: a Carta está em `cartas`
  próprio da criatura (`bst_descarga_arcana`, compartilhada por 15). Além do `arquetipo` → `tatico`, troquei a Carta
  própria por `bst_pancada_esmagadora` (martial pesada, machado). Sem isso o baralho seguia com a Descarga.
- **R8:** `condition_label` só humaniza o fallback quando o nome tem `_` ou é todo minúsculo (não deforma
  "Veneno Fraco").
- **R5/P3-10:** o teste da 346 que codificava criatura do bestiário fora de cena abrindo combate mudou (a
  narração do fixture agora cita bandido/goblin); `test_card_lint` (aviso `revelar intencao`) e
  `test_spec353_misc` (D6 da 353 reexecutado pelo R11) também mudaram de expected, por desenho.
- **Etapa 7:** arena pós-B só nas sementes 0-19 (a 20-99 inteira ficou para a confirmação, uma vez).
- **R13:** nenhum passo resolveu (ver `RELATORIO.md`); nenhuma Carta de onda alterada. `arena-final.json` = A1.
- **R14 NÃO aplicado:** `dano_base` 6→5 (v3) não tirou a bandeira (`dominante` +11,3 pp), deixou o silencioso
  padrão em 78,7 % (>76,6) e **derruba `test_arena_versoes_batem_com_catalogo`** (D17; o ajuste é de outro
  agente). Para reaplicar: `data/cards/posturas/sangromante_silencioso.json`, id `san1_sil_corte_sem_aviso`.
- **R17 implementado** (Corruptor 44,2 % e Arcanista 42,1 % realistas 0-19); as Cartas são passivas, então a
  arena não muda.

**Pendências para o dono (held-out 20-99, sem reajuste):** Arcanista Cinzento 43,9 % total (piso 45 %; 42,1 %
com emboscada); Corruptor sem contrapartida de emboscada (45,2 % realista); `avaro` 77,6 % e `silencioso` 76,8 %
padrão acima do teto; Devoto +2,7 pp pós-R11 (na faixa, 0,7 acima de ±2,0). Decisão: aceitar ou nova spec com
número novo (ex.: Carta `buff_iniciativa` para o Corruptor, buff ao Arcanista).

**Testes novos:** `tests/test_spec355_{conteudo,reacao_buff,golpe_reacao,provocacao_rodada,promessa_chefe,
router_fallback,compra_utilitaria,exemplos_fora,emboscada,arena,guardas}.py`. R2 ficou fora de
`ct.resolve_turn`; R3/R4 gravam só em `out`/cena. Fora do escopo desta spec e não feito: `web` só ganhou `label`.
