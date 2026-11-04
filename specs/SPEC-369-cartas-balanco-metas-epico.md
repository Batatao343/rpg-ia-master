# SPEC-369 — Cartas: balanço das metas não atingidas do épico (Cartas por rodada, dominância, duração, Presságio, `draft.py`, emboscada do Corruptor, famílias × arena)

> **Status:** `approved` (04/11, coordenador, sob a ordem permanente do dono "manda bala"; decisões D-369-1, -4, -5, -6, -8 e -9 nos defaults. O gate do oráculo, R9c com D-369-2, -3 e -7, continua com o dono)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-327
> **Depende de:** SPEC-368 `done` (métricas e `docs/spec368/metricas_epico.py`), SPEC-362 `done` (protocolo de passo, Arcanista 49,7 %), SPEC-355 `done` (`arena_spec355.py emboscada`, R17), SPEC-358 `done` (arena por substituição `lote-v2`), SPEC-387/389 `done` (`draft.py` com reparo; nota L11).
> **Desbloqueia:** fechar as ressalvas D-368-1 nas specs 327 §7, 329 §8, 331 §10, 332 (fechamento), 335 (fechamento) e 336 (fechamento).
> **Risco:** `alto` (combate, balanço e avaliador da arena) → `spec-reviewer` obrigatório nas duas fases.
> **Evidência:** Fase A reproduz os números da 368 byte a byte (oráculo de equivalência) antes de medir qualquer coisa nova; Fase B é medida pela ferramenta congelada da Fase A; Fase C confirma uma vez em sementes nunca usadas.
> **EXECUTOR_MODEL:** Fase A `Sol` (autoria de régua; `model: opus` explícito) · Fase B `Terra` (`spec-executor`, Sonnet) · **REVIEW_MODEL:** Fase A `Astra` (Opus, contexto independente), Fase B `Sol` (Opus) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` **só na Fase A**: o executor da Fase A é autor de eval e não toca produto. O executor da Fase B é outro agente e não toca nada que a Fase A escreveu (R1).

Rótulos: **[F]** fato com evidência (arquivo:linha) · **[H]** hipótese que a Etapa 0 confirma ou derruba · **[D]** decisão (§8).

---

## 1. Contexto & Objetivo

[F] A SPEC-368 mediu pela primeira vez as metas do épico, com `docs/spec368/metricas_epico.py`: 1.800 conflitos, 5 Posturas × níveis 1/3/5 × padrão+elite × 3 criaturas × sementes 0–19, cartas `on`, bot `sim.full_deck_decl`. O JSON está em `docs/spec368/metricas-0-19.json`. Quatro metas falharam, e a 368 só as registrou (D-368-1, `specs/SPEC-368-cartas-fechamento-epico.md:169-170`, `:194`). A auditoria de fechamento de 04/11 juntou mais três ressalvas e mandou todas para esta spec.

| # | Meta (fonte) | Medido | Fonte do número |
|---|---|---|---|
| 1 | ≥ 2 Cartas jogadas por rodada em média (`SPEC-327:88`) | **1,921** (Devoto 1,799 · Sangromante 1,792 · Corruptor 1,864 · Arcanista 1,914 · Médico 2,102) | `metricas-0-19.json:92`, `:7`, `:23`, `:39`, `:57`, `:75` |
| 2 | Nenhuma Carta com uso > 60 % quando na mão (`SPEC-327:90`) | **14 Cartas** (uso geral 38,4 %) | `metricas-0-19.json:97-112` |
| 3 | p95 do conflito ≤ 10 rodadas (`SPEC-327:91`, `SPEC-331:60`) | **12** no total; Médico **19** com 4,4 % de timeouts; Devoto 11 | `metricas-0-19.json:113`, `:84-86`, `:15` |
| 4 | Arena `on`: dano recebido cai, vitória dentro da faixa (`SPEC-329:52`) | `off` 11,96 × `on` 13,17 (**+10,1 %**); vitória 64,6 → 57,6 % | `metricas-0-19.json:118-133` |
| 5 | Rendimento do `draft.py` (`SPEC-336:102`) | **2 de 4** Cartas reprovadas no lint (orçamento/raridade) | `docs/spec387/smoke-local.md:28`, `docs/spec389/smoke-local.md:50`, `SPEC-389:53`, `:434` |
| 6 | Corruptor com resposta à emboscada (`SPEC-355:185-189`, `SPEC-335:92`) | nenhuma Carta `buff_iniciativa`; realista **44,2 %** (0–19) e 45,2 % (20–99) | `SPEC-355:555-561` |
| 7 | Arena por família dentro da faixa (`SPEC-332:52`, `:57`) | "2 células-família fora" (sem nome no fechamento) | `SPEC-332:57`, `:131`; `docs/spec332/arena-results-2026-10-27.md:37-56` |

O que a leitura do source mostra sobre cada falha:

- **[F] Meta 1: o teto é estrutural.** O Fôlego padrão é **2**, não os 3 do D2 da 327 (`services/card_piles.py:32-42`, calibração da 328 Etapa 6; `config/flags.yaml:445-449`). Todas as 15 básicas custam 1 Fôlego (`data/cards/basicas.json:14`, `:33`, …, `:283`). Sem Carta de Fôlego 0 ou `ganhar_folego` na mão, o máximo por rodada é 2. O Médico passa de 2 (2,102) porque tem Cartas de Fôlego 0, como `med1_fer_lente_de_protese` (`data/cards/posturas/medico_cirurgiao_ferro.json:36-45`). A média só sobe com mais jogadas baratas ou com mais Fôlego.
- **[F] Meta 2: a maior parte das 14 Cartas é artefato do bot ou está travada por regra.** O bot joga **todo** ataque que cabe no Fôlego, do maior dano para o menor (`scripts/cards/sim.py:188-193`), e o baralho da arena tem 4 cópias do golpe básico (`sim.py:95`). Por categoria:
  - 5 **básicas**: `bas_dev_golpe`, `bas_cor_golpe`, `bas_cor_mofo`, `bas_med_golpe` e `bas_san_corte_raso`;
  - 4 **do Sangromante**, que o dono mandou não mexer: `bas_san_corte_raso` (contada também acima), `san_sil_exato`, `san1_ava_penhor_de_carne` e `san1_exp_selo_de_dor`;
  - 5 **legadas**, fixadas pelo golden e pelo snapshot da 330: `arc_descarga` (`data/cards/arcanista.json:5`; `tests/fixtures/spec330_legacy_golden.json:637`; snapshot `:20`), `arc_faisca` (`arcanista.json:33`), `arc_des_mao_nua` (`arcanista.json:291`), `cor_bio_gangrena` (`data/cards/corruptor.json:183`) e `med_fer_talas` (`data/cards/medico.json:377`);
  - **1 de onda** fora do Sangromante: `med1_fer_lente_de_protese`, com uso 1,0.

  A SPEC-358 já rebaixou o uso a **aviso** e deixou como bandeira só o delta por substituição (`SPEC-327:101`). `bomba_estopim` (`data/cards/posturas/arcanista_cinzento_improvisador.json:185-218`) é dominante **pelo delta**: +9,4 pp na v1, com uso de 55 % (`docs/spec362/RELATORIO.md:23`, `SPEC-362:351`). Por isso ela não aparece na lista de uso > 60 %.
- **[F] Meta 3: a arena não tem o Relógio.** No produto, o teto de 12 rodadas é o `clock_hard_stop` (`services/scene_cards.py:32-33`, `:532-548`), chamado em `services/conflict_orchestrator.py:2991`. Ele só vale com `RPG_SCENE_CARDS=on` **e** com um contexto de cena (`conflict_orchestrator.py:2643`). A arena da 368 não liga nenhum dos dois (`metricas_epico.py:275`), e o staging liga (`scripts/staging/staging_flags.json:28`). Os 4,4 % de timeouts do Médico batem no `MAX_ROUNDS = 20` da arena (`sim.py:53`). [H] A causa é o laço do bot com o Médico: o bot cura abaixo de 50 % e defende abaixo de 75 % (`sim.py:180-187`), e o Médico tem pouco dano por desenho (roda "dano alto: Nunca", `SPEC-335:31`; `bas_med_golpe` tem dano 3, `basicas.json:248`).
- **[F] Meta 4: o braço `on` mistura duas causas.** (a) O motor `on` executa as intenções **congeladas**, decididas antes da jogada do herói, e só re-decide quando a intenção fica impossível (`SPEC-329:28`; `conflict_orchestrator.py:2667-2668`). (b) O bot de `on` (`_heed_omen`, `metricas_epico.py:108-126`) só **acrescenta** uma defesa **antes** das jogadas e exige que tudo caiba no Fôlego (`:122-123`). Com Fôlego 2 e duas jogadas já declaradas, isso quase nunca cabe. Além disso, os inimigos da arena são **desconhecidos**: `knowledge_level` devolve `desconhecida` sem `known`/`revealed_cards` (`services/enemy_intent.py:207-223`), e então a `faixa` pública fica `None` (`enemy_intent.py:289-290`). Ou seja, o bot nunca viu uma faixa. [H] O +10,1 % vem quase todo de (a), e o ganho de informação nunca foi medido.
- **[F] Meta 5:** a triagem do `draft.py` só chama `fx.validate_card` (`scripts/cards/draft.py:296`), que é o vocabulário. O orçamento e a raridade só são checados depois, no lint (`services/card_lint.py:227-229` `check_budget`, `:232-252` `check_raridade`). Por isso o reparo de 1 chamada (`draft.py:264-274`, `:306-326`) nunca recebe esses motivos. O prompt lista as faixas (`draft.py:105-115`), mas o modelo não tem como calcular o `power_score` (`services/card_effects.py:1664-1684`). Já existe um ajuste determinístico de orçamento em outro gerador: `_fit_orcamento` (`scripts/bestiario/gerar_mecanica.py:209-…`).
- **[F] Meta 6:** `_has_vigilia` (`agents/combat.py:1926-1939`) anula a emboscada se o herói tiver **qualquer** Carta `buff_iniciativa` no baralho ou nas preparadas. Existem 5 dessas Cartas de Postura: `arcanista.json:516`, `:868`, `sangromante.json:867`, `medico.json:670` e `devoto.json:369`. **Nenhuma é do Corruptor**. O avaliador da emboscada realista só credita Carta presente em `sim.full_deck` (`docs/spec355/arena_spec355.py:58-63`), e o `full_deck` só aceita `ativa`/`reacao`/`utilitaria` (`services/cards.py:442`).
- **[F] Meta 7:** a tabela do lote 2 (`arena-results-2026-10-27.md:37-48`, 200 combates por célula, bot "cartas" da 285) não diz quais são as "2 células". Duas leituras possíveis:
  - pelo critério do lote 1 (|Δ `on`−`off`| > 10 pp), as células fora são morto_vivo L3 (−15,0), covarde L5 (−12,5) e guardião L3 (−11,5);
  - pela faixa absoluta, só **conjurador L5** é empurrado para fora pelo `on` (45,5 → 40,5).

  A Etapa 0 remede e fixa a definição (D-369-7).

**Objetivo.** Fechar as sete ressalvas com número, sem mexer no que o dono travou. As travas são: o Sangromante não muda; a faixa de vitória da arena é 45–85 %; o combate segue sem LLM por rodada; golden da 330, avaliadores, `sim.py`, arenas antigas e `web/e2e/contracts` ficam intocados; e arquivo com mais de 1.000 linhas não cresce. Como parte das metas depende de **como se mede**, a spec se divide em três fases com papéis separados:

- **Fase A — régua.** Autoria de eval, sem tocar produto. A régua nova reproduz a 368 e acrescenta os braços que faltam, entre eles o leitor de faixa.
- **Fase B — produto.** Outro agente mexe só em conteúdo e no `draft.py`, medindo com a régua congelada.
- **Fase C — confirmação.** Uma rodada só, em sementes nunca usadas.

## 2. Requisitos

### Integridade (valem para todas as fases)

- **R1 — Papéis e fases separados.** Cada fase tem as suas regras:
  - **Fase A** (`EVAL_AUTHORING`) só cria `docs/spec369/metricas_369.py`, `docs/spec369/bot_pressagio.py`, `tests/test_spec369_regua.py`, `tests/test_spec369_metas.py` e os JSON/relatórios de base. Não edita nada fora de `docs/spec369/` e desses dois testes.
  - **Fase B** (produto) começa só depois que a Fase A está na `main`. Os blocos B1 (`draft.py`, R12) e B2 (Corruptor, R17) não dependem do oráculo e podem começar assim que a Fase A pousar. Os blocos B3 em diante só começam depois que o dono aprovar o oráculo do R9 (D-369-2, -3 e -7). Ela não edita nenhum arquivo criado pela Fase A. Se a régua parecer errada, o executor para e devolve.
  - **Fase C** (confirmação) é rodada pelo coordenador ou por um terceiro agente, nunca pelo executor da Fase B.

  Prova: `git log --format='%an %s' -- docs/spec369/metricas_369.py docs/spec369/bot_pressagio.py tests/test_spec369_*.py` mostra só commits da Fase A. Na branch da Fase B, `git diff --exit-code <sha-A> -- <esses caminhos>` sai vazio. O `<sha-A>` fica registrado em §9.
- **R2 — Avaliadores e conteúdo protegido congelados.** Estes caminhos saem desta spec byte-idênticos à `main` de partida:
  - `scripts/cards/sim.py`, `scripts/cards/lint.py`, `scripts/cards/promote.py`;
  - `services/card_lint.py`, que **é importado e nunca editado**;
  - `docs/spec368/metricas_epico.py`, `docs/spec285/arena_lethality.py`, `docs/spec332/arena_familias.py`, `docs/spec335/arena_posturas.py`, `docs/spec341/arena_spec341.py`, `docs/spec355/arena_spec355.py`, `docs/spec362/arena_spec362.py`;
  - `data/cards/_orcamento.json`;
  - `tests/spec330_equivalence.py`, `tests/fixtures/spec330_legacy_golden.json`, `tests/fixtures/spec330_card_text_snapshot.json`;
  - `tests/test_card_sim.py`, `tests/test_spec341_balanco.py`, `tests/test_spec355_arena.py`, `tests/test_spec362_arcanista.py`, `tests/test_spec368_metricas.py`;
  - `web/e2e/contracts/`.

  Os limiares de `sim.py:53-59` também não mudam. Prova: `git diff --exit-code main -- <caminhos>` no pouso de cada fase.
- **R3 — Sementes.** Base e ajuste usam só as sementes **0–19**, como na 368. A confirmação usa as **260–339**, uma vez (Fase C). As faixas 20–99, 100–179 e 180–259 já foram vistas pela 362 e não valem como held-out aqui. Na arena de famílias, o ajuste usa as sementes 0–7 (8 sementes, como no lote 2) e a confirmação usa 260–267.
- **R4 — Travas do dono.**
  - (a) Nenhuma Carta do Sangromante muda, inclusive `bas_san_*`, e as Cartas dele com uso > 60 % ficam listadas como **exceção aceita**.
  - (b) Nenhuma Carta legada muda. A exceção é o `custo_folego` explícito, e só se D-369-4 aprovar e o golden e o snapshot da 330 ficarem byte-idênticos.
  - (c) O combate continua sem LLM por rodada.
  - (d) A faixa de vitória das Posturas é 45–85 % (total, padrão+elite), com o teto de 75 % na padrão por subclasse e as exceções de `tests/test_spec355_arena.py:18-…` intactas.
- **R5 — Tamanho e helper.** Nenhum arquivo com mais de 1.000 linhas cresce (`tests/test_size_budget.py`). `services/conflict_orchestrator.py` e `agents/combat.py` não são alterados nesta spec. Função nova tem no máximo 60 linhas. Antes de criar um helper, rodar `Grep "def <nome>"`.

### Fase A — régua (EVAL_AUTHORING)

- **R6 — Ferramenta nova, só por importação.** `docs/spec369/metricas_369.py` importa `sim`, `metricas_epico`, `arena_spec341`, `arena_spec355` e `arena_familias` e não edita nenhum deles. Cada subcomando tem `--seeds` e `--out`. Os monkeypatches são restaurados em `finally`.
  - `base`: chama `metricas_epico.run` com os mesmos parâmetros da 368.
  - `uso`: por Carta com n ≥ 5, dá a categoria (`basica` / `sangromante` / `legada` / `onda`), o uso, a `versao` e o **Δ por substituição** do protocolo `lote-v2` (`sim.simulate_protocolo_lote(batch, protocolo="v2")`, `sim.py:574-604`), passando a própria Carta do catálogo como lote [H: confirmar na Etapa 0 que o `lote-v2` aceita Carta já presente no catálogo; senão, leave-one-out como o R7 da 362].
  - `duracao`: histograma de rodadas por Postura, % de timeouts, % de rodadas em que o bot cura, e o braço informativo "teto 12": a mesma luta, contando como fim na rodada 12 o que passaria dela. Esse braço não é critério.
  - `pressagio`: o R7.
  - `posturas`: chama `arena_spec341.py posturas` e grava a guarda do R19.
  - `emboscada`: chama `arena_spec355.py emboscada`. Credita também uma Carta `passiva` `buff_iniciativa` da Postura com `level_req ≤ nível`, porque o produto a honra nas preparadas (`agents/combat.py:1933`) [D-369-6].
  - `familias`: chama `arena_familias.fight` com deslocamento de semente, 5 criaturas por família, níveis 3 e 5, `off` × `on`.
- **R7 — Bot leitor de Presságio, pré-registrado.** `docs/spec369/bot_pressagio.py`. A regra abaixo **é** o oráculo. O executor a implementa como está escrita e não a ajusta depois de ver número.
  1. No início da rodada, o bot lê `enemy_intent.public_intent(intent, knowledge_level(enemy, carta_id), actors_by_id=…)` para cada intenção. Ele vê o mesmo que o jogador: a faixa só aparece com `conhecida`/`estudada`.
  2. **Ameaça prevista** contra o herói é a soma, nas intenções `ataque`/`ataque_multiplo` com `alvo_id == "player"`, de `(faixa[0] + faixa[1]) / 2`. Sem faixa, cada ataque conta como `dano_base` 4 (`ct._DANO_BASICO_DEFAULT`; confirmar o valor na Etapa 0).
  3. A ameaça é **séria** se for ≥ 25 % da Vitalidade atual, ou se deixaria o herói abaixo de 50 % da máxima.
  4. Com ameaça séria, o bot **troca** o ataque de menor dano da declaração de `sim.full_deck_decl` pela Carta de defesa de maior `valor` que estiver na mão (`sim._DEFENSE_KINDS`). Se a troca não couber no Fôlego, ele mantém a declaração.
  5. Sem ameaça séria, o bot ataca primeiro o inimigo que vai atacar o herói **e** cujo dano previsto da rodada mata (Vitalidade ≤ soma do dano das jogadas). Senão, segue `alive[0]`, como hoje.
  6. Nada mais muda: mesma cura, mesma ordem de ataque e nenhum Pacto.
- **R8 — Braços do Presságio.** São **4 braços × 2 níveis de conhecimento × 2 modos de baralho de inimigo**, nas sementes 0–19:
  - braços: `off`; `on-cego` (motor `on` com o bot da 368 **sem** `_heed_omen`); `on-368` (`_heed_omen`, o número da 368); `on-faixa` (R7);
  - conhecimento: `desconhecida` (a arena de hoje) e `conhecida` (inimigo com `known: True`, que é o caso de um jogador que já viu a família);
  - baralho de inimigo: `RPG_ENEMY_DECKS` `off` e `on` (o staging usa `on`, `staging_flags.json:29`).

  Saída por braço: dano médio recebido, vitória, rodadas e o Δ pareado por semente contra `off` e contra `on-cego`.
- **R9 — Equivalência e base.**
  - (a) `metricas_369.py base --seeds 0-19` reproduz **exatamente** `metricas-0-19.json["r9"]` e `["r10"]`: 1,921 / 87,7 % / 14 Cartas / p95 12 / +10,1 %. Divergiu? A Fase A para e investiga (catálogo ou motor mudaram depois de 02/11), registra a causa, e a base nova vale.
  - (b) Grava `docs/spec369/base-0-19.json` e `docs/spec369/BASE.md`, com as 7 metas, a decomposição do R8 e a lista nomeada das células de família pela definição do D-369-7.
  - (c) **Gate do dono:** o BASE.md termina com o pedido explícito de aprovação do oráculo (D-369-2, D-369-3, D-369-7). Antes dessa aprovação, a Fase B não começa.
- **R10 — Testes da régua, com caso bom e caso ruim conhecidos.** `tests/test_spec369_regua.py`:
  - `test_base_reproduz_368` roda em 2 sementes e confere o schema e a igualdade com um recorte de `metricas_epico.run`;
  - `test_bot_faixa_troca_ataque_por_defesa` (ameaça séria → defesa no lugar do ataque mais fraco);
  - `test_bot_faixa_mantem_sem_ameaca`;
  - `test_bot_faixa_desconhecida_usa_dano_padrao`;
  - `test_bot_faixa_mira_quem_ameaca_e_morre`;
  - `test_braco_cego_nao_le_pressagio`;
  - `test_emboscada_credita_passiva_preparada`;
  - `test_categoria_de_carta` (básica / Sangromante / legada / onda, com ids reais).

  Todos com `-n 2`.
- **R11 — Testes de meta, escritos antes do produto.** `tests/test_spec369_metas.py` lê os artefatos da Fase B e da Fase C e **falha** enquanto eles não existirem ou não cumprirem os limiares do R13–R19. Os limiares ficam numa constante no topo do arquivo e só mudam por decisão do dono, num commit separado de autor de eval. Quem escreve esse arquivo é a Fase A, e a Fase B não o edita (R1).

### Fase B — produto

- **R12 — `draft.py` com orçamento e raridade na triagem (meta 5).**
  - (a) `_triagem` passa a juntar `card_lint.check_budget` e `card_lint.check_raridade` aos problemas de `fx.validate_card`. Os dois são importados, sem copiar código.
  - (b) A mensagem de reparo leva, por Carta reprovada, o `power_score` atual, a faixa `[min, max]` de (raridade, Fôlego) e a direção ("reduza poder em ≥ X" ou "aumente…"), calculados por `fx.power_score`/`fx.budget_band`.
  - (c) Se o reparo ainda falhar, um ajuste **determinístico** só de números (D-369-5) tenta pôr a Carta na faixa: ±1 em `custo_folego` (0..3) e −1 em `dano_base`/`valor` do maior efeito de dano, até 6 passos. A Carta ajustada leva `"ajuste_orcamento": [passos]` no rascunho para a curadoria ver. O que não couber continua em `_rejeitadas_vocabulario`, com o motivo.
  - (d) O guard de FallbackLLM continua: `isinstance(res, LoteRascunho)` no reparo, em `draft.py:323`.
  - **Meta:** num lote real de 4 Cartas, **≥ 3 passam em `lint.py` sem erro** (§6 item 1). Offline, com `ScriptedLLM`: 4 Cartas, 2 fora do orçamento → as 2 voltam ao reparo com o motivo de orçamento, e o lote final só tem Cartas com `card_lint.check_budget == []`.
- **R13 — Cartas por rodada (meta 1).** Na ferramenta da Fase A (`base`, 0–19): **total ≥ 2,00** e **nenhuma Postura < 1,90** (D-369-3). As alavancas são as do R18.
- **R14 — Dominância (meta 2), em duas camadas.**
  - **Meta numérica literal** (o critério do dono): o número de Cartas com uso > 60 % é registrado, por categoria, antes e depois.
  - **Meta da spec** (D-369-3):
    - (a) **0 Cartas de onda fora do Sangromante** com uso > 60 %, hoje 1 (`med1_fer_lente_de_protese`);
    - (b) **0 Cartas** fora do Sangromante com bandeira `dominante` por delta (Δ > +8 pp no `lote-v2`), entre elas `arc1_imp_bomba_estopim`;
    - (c) legadas com uso > 60 % só caem se o D-369-4 liberar o `custo_folego`, e as que ficarem são listadas como "travadas pelo golden";
    - (d) básicas: o golpe básico com uso > 60 % é aceito como fallback por desenho; a assinatura básica (`bas_cor_mofo`) entra na meta (a).
- **R15 — Duração (meta 3).** Na ferramenta da Fase A (`base`, 0–19, arena sem Relógio): **p95 total ≤ 10**, **p95 de toda Postura ≤ 12** e **timeouts ≤ 1,0 % por Postura** (D-369-3). O braço "teto 12" é só informativo.
- **R16 — Presságio (meta 4).** A meta primária mede o **valor da informação**: no braço `conhecida`, `on-faixa` recebe dano médio **≤ 95 %** do `on-cego`, pareado por semente, e a vitória de `on-faixa` fica em 45–85 %. A meta secundária é a do texto da 329, `on-faixa` < `off`: ela é registrada, e só vale como critério se o dono escolher (D-369-2). Se a primária já passar na base da Fase A, a Fase B **não** mexe em nada por esta meta. Se não passar, as alavancas são só de conteúdo (R18: custo e valor das defesas básicas e de onda). A semântica do congelamento (`SPEC-329` R4) fica fora (§Fora de escopo).
- **R17 — Emboscada do Corruptor (meta 6).** Uma Carta nova do Corruptor com efeito `buff_iniciativa`, no tronco (`data/cards/posturas/corruptor_tronco.json`, que hoje tem 3 Cartas: `:5`, `:34`, `:63`). Requisitos:
  - comum, `level_req` 1, `tipo` conforme o D-369-6 (proposta: `passiva`, como `dev_zel_vigilia`, `devoto.json:357-369`);
  - lint sem aviso, `fx.budget_error is None`, roda do Corruptor respeitada (`SPEC-335:29`), voz de Valoria (sem número na descrição) e `nota_voz` em `_ondas.yaml`.

  **Testes:**
  - `_has_vigilia` devolve `True` para um Corruptor com a Carta nas preparadas, sem mudar `agents/combat.py`;
  - `_opening_initiator` devolve `ambush_negated_vigilia` (`agents/combat.py:1951-1952`).

  **Meta:** na ferramenta `emboscada` (0–19), o Corruptor `todas` tem total realista **≥ 45,0 %**, e nenhuma outra Postura muda.
- **R18 — Alavancas permitidas e passo.** "Passo" é uma destas mudanças, em uma Carta ou constante:
  - (a) **Cartas de onda** fora do Sangromante (`data/cards/posturas/{devoto,corruptor,arcanista_cinzento,medico}_*.json`): +1 ou −1 em `dano_base`/`valor` de um efeito; ±1 em `custo_folego` ou `custo_entropia` (mínimo 0); um degrau de `frequencia`.
  - (b) **Básicas** fora do Sangromante (`data/cards/basicas.json`; só modo `on`, fora do golden; confirmar na Etapa 0 com `git diff` vazio no golden depois de um passo de teste): os mesmos passos de (a).
  - (c) **Legadas**: só `custo_folego` explícito, se o D-369-4 liberar.
  - (d) **Cartas de inimigo** (`data/cards/inimigos/<familia>.json`, só para o R20): ±1 em `dano_base`/`valor`, ou um degrau de `frequencia`.
  - (e) **Constantes do baralho**: `FOLEGO_BASE` (`card_piles.py:37`, `config/flags.yaml:447`) ou `MAO_BASE` (`card_piles.py:29`), só se o D-369-1 liberar.

  Limites:
  - cada Carta recebe no máximo 2 passos;
  - o pacote de heróis tem no máximo **8 Cartas** e o de inimigos no máximo 2 Cartas por família;
  - um passo por vez, remedindo tudo o que ele pode mover;
  - passo que não move a métrica-alvo (|Δ| abaixo de 1 luta, ou abaixo de 0,01 Carta por rodada) é revertido e conta no limite;
  - toda Carta alterada leva `versao` + 1 e passa em `fx.budget_error is None`, `card_lint` sem aviso e `validate_content` com 0 erros. Passo que estoura o orçamento é inválido.

  **Fora dos passos:** `tier`, `level_req`, `patamar`, `raridade`, `kind`, palavras-chave e efeitos novos ou removidos. A exceção é a Carta nova do R17.
- **R19 — Guardas globais**, que valem depois de cada passo e no fim, nas 0–19:
  - (a) toda Postura com total (`arena_spec341 posturas`) em 45–85 %, subclasses na padrão ≤ 75 % (salvo `EXCECOES_TETO`), e Arcanista `todas` ≥ 45 %;
  - (b) Sangromante `todas` com no máximo +2,0 pp sobre a base (D-369-8);
  - (c) a vitória agregada da ferramenta `base` em 45–85 %;
  - (d) nenhuma Postura cai mais de 5,0 pp no total;
  - (e) golden e snapshot da 330 e `web/e2e/contracts` sem diff;
  - (f) 0 LLM por rodada (`tests/test_spec346_*`/`test_combat_*` do escopo verdes).
- **R20 — Famílias (meta 7).** Pela definição do D-369-7 (proposta: célula em que `off` ∈ [45, 85] e `on` sai da faixa, **ou** |Δ `on`−`off`| > 10 pp), toda célula listada no BASE.md termina com `on` ∈ [45, 85] e |Δ| ≤ 10 pp, com 200 combates por célula. As células em que o `off` já está fora (`arena-results-2026-10-27.md:54-56`) ficam fora do escopo. Ordem: primeiro a Carta de maior dano da família (como a ablação da 332, `:52-53`), um passo por vez.
- **R21 — Ordem da Fase B.** Cada bloco é um commit próprio:
  - B1 `draft.py` (R12) e B2 Corruptor (R17) são independentes;
  - B3 Cartas por rodada, dominância e duração (R13–R15), que dividem as alavancas;
  - B4 `bomba_estopim` (R14b);
  - B5 Presságio (R16), só se a primária falhou na base;
  - B6 famílias (R20).

  Depois de cada bloco, a ferramenta `base` + `posturas` regrava `docs/spec369/passos-0-19.json`. Se 8 Cartas × 2 passos não fecharem uma meta: o executor **para**, registra a curva medida e devolve. Não abre alavanca nova.

### Fase C — confirmação

- **R22 — Uma vez, nas 260–339.** Depois do commit final da Fase B, o coordenador ou um terceiro agente roda **uma vez**:
  - `metricas_369.py base`, `uso`, `pressagio` (só `conhecida`, decks `on`), `posturas` e `emboscada` com `--seeds 260-339`;
  - `familias --seeds 260-267`.

  Grava `docs/spec369/confirmacao.json`. Critérios:
  - R13, R15, R16 primária, R17 e R20 dentro da meta;
  - R14(a)(b) sem bandeira;
  - R19(a)(c) dentro.

  Falhou: registro em §9 e devolução ao dono, **sem reajuste** com essas sementes.
- **R23 — Registro.** O coordenador põe os números finais nas specs 327 §7, 329 §8, 331 §10, 332, 335 e 336 (uma linha cada, apontando para esta spec). `ESTADO_ATUAL.md` vai pelo `/estado`.

### Fora de escopo

- Qualquer Carta do Sangromante, básica ou de onda, e as exceções de teto (R4a).
- Mudar o golden, o snapshot ou o orçamento da 330. Mudar `sim.py`, `lint.py`, `promote.py`, `card_lint.py`, a 368 ou as arenas antigas (R2). Se uma delas precisar mudar, isso vira uma spec própria de autoria de eval.
- Semântica do Presságio: re-decisão de intenção congelada, "mudança de ideia" do inimigo (`SPEC-329:66`) e conhecimento automático de família. Qualquer mudança de motor em `enemy_intent.py`/`conflict_orchestrator.py` fica fora.
- Pôr o Relógio do Abismo ou as Cartas de Cena dentro da arena como critério. Fica só o braço informativo do R6.
- Mecânica nova, palavra-chave nova, Carta nova além da do R17, ou mudança de `tier`/`level_req`/`raridade`.
- Nichos de família com `off` já fora de 45–85 % (morto-vivo, guardião, apex e predador L5). Isso é decisão do dono pendente desde a 332.
- Bot "cartas" da 285 e bot `full_deck_decl` (só importados). Avaliação no CI (SPEC-380). Long-run e playtest de 100+ turnos.
- UI e contrato da API: nada muda na tela além do número das Cartas alteradas.

## 3. Design técnico

### 3.1 Arquivos novos

**Fase A**
- `docs/spec369/metricas_369.py`: subcomandos do R6. Ele só importa outros módulos. Cada subcomando é uma função de no máximo 60 linhas.
- `docs/spec369/bot_pressagio.py`: `leitor_faixa_decl(player, piles, actors, sides, scene, forecast, seen) -> ct.TurnDeclaration` (R7) e `cego_decl = sim.full_deck_decl`.
- `docs/spec369/base-0-19.json`, `docs/spec369/BASE.md` (R9).
- `tests/test_spec369_regua.py` (R10) e `tests/test_spec369_metas.py` (R11).

**Fase B**
- `docs/spec369/passos-0-19.json`: um registro por passo, com `{bloco, carta|constante, campo, de, para, metricas_antes, metricas_depois, mantido}`.
- `docs/spec369/final-0-19.json` e `docs/spec369/RELATORIO.md`.
- O módulo `services/card_budget_fit.py` só nasce se o D-369-5 decidir extrair o `_fit_orcamento`. Nesse caso, `fit_orcamento(card: dict, max_passos: int = 6) -> tuple[dict, list[str]]`, e `scripts/bestiario/gerar_mecanica.py` passa a importá-lo, com teste de equivalência sobre a saída atual dele.

**Fase C**
- `docs/spec369/confirmacao.json`.

### 3.2 Arquivos alterados (Fase B)

- `scripts/cards/draft.py` (~390 linhas): `_triagem`, `_reparar` e o ajuste do R12.
- `data/cards/posturas/corruptor_tronco.json`: +1 Carta (R17).
- `data/cards/_ondas.yaml`: entrada da Carta nova e `nota_voz` de toda Carta cuja `descricao` mudar.
- `data/cards/basicas.json`, `data/cards/posturas/{devoto,corruptor,arcanista_cinzento,medico}_*.json` e `data/cards/inimigos/<familia>.json`: só passos do R18.
- `services/card_piles.py:37` e `config/flags.yaml:447`: só se o D-369-1 liberar.
- `tests/test_card_draft.py` e `tests/test_spec387_draft.py`, ou um teste novo `tests/test_card_draft_orcamento.py`: testes do R12.
- `tests/test_card_acervo_reparo.py` ou `tests/test_card_lint.py`: a Carta do R17 no lint, orçamento e roda.

### 3.3 Formatos

Carta do R17 (o nome e os números são da Fase B; ids e campos reais):

```json
{
  "id": "cor1_tro_<slug>",
  "name": "<até 4 palavras>",
  "tipo": "passiva",
  "origem": "onda-1",
  "classe": "Corruptor",
  "subclasse": "",
  "patamar": "inicial",
  "raridade": "comum",
  "custo_entropia": 0,
  "frequencia": "livre",
  "virtude_permitida": [],
  "efeitos": [{"kind": "buff_iniciativa", "valor": 2}],
  "descricao": "<sem número, voz de Valoria>",
  "momento": "Melhor jogada quando…",
  "tier": 1, "level_req": 1, "apex": false, "onda": 1, "versao": 1
}
```

Registro em `passos-0-19.json`:

```json
{"bloco": "B3", "carta": "bas_med_golpe", "campo": "efeito.dano_base", "de": 3, "para": 4,
 "versao": [1, 2], "metricas_antes": {"cartas_rodada": 1.921, "p95": 12, "medico_p95": 19},
 "metricas_depois": {"...": "..."}, "mantido": true}
```

Bloco do `pressagio` em `base-0-19.json`:

```json
{"conhecida": {"decks_on": {"off": {"dano_medio": 0.0, "vitoria_pct": 0.0},
  "on-cego": {}, "on-368": {}, "on-faixa": {},
  "delta_faixa_vs_cego_pct": 0.0, "delta_faixa_vs_off_pct": 0.0}}}
```

## 4. Plano passo a passo

Custo de máquina: a `base` da 368 levou 50,7 s (`metricas-0-19.json:207`). O `pressagio` são cerca de 16 braços de 1.800 lutas (≈ 15 min). `posturas` e `familias` levam minutos cada. Rodar em série, um processo por vez, com `run_in_background` e timeout explícito. Medir a RAM antes (`bash scripts/dev/ram.sh`), e nunca rodar em paralelo com a suíte.

### Etapa 0 — Confirmação no source (Fase A, sem código)

Anotar em §9 com arquivo:linha:

- se `lote-v2` aceita Carta do catálogo como lote (R6 `uso`);
- o valor de `ct._DANO_BASICO_DEFAULT` (R7.2);
- se uma `passiva` nas preparadas do herói da arena chega a `_has_vigilia`;
- se um passo de teste em `basicas.json`, revertido em seguida, deixa golden e snapshot sem diff (R18b);
- se `custo_folego` explícito numa legada muda golden ou snapshot (D-369-4).

### Etapa 1 — Régua (Fase A)

1. **Testes primeiro:** `tests/test_spec369_regua.py` (R10). Eles falham por módulo ausente.
2. `bot_pressagio.py` e `metricas_369.py`. Verificação: `bash scripts/dev/pt.sh tests/test_spec369_regua.py`, com `-n 2`.
3. `base --seeds 0-19` → igualdade com a 368 (R9a). Depois `uso`, `duracao`, `pressagio`, `posturas`, `emboscada` e `familias --seeds 0-7` → `base-0-19.json` e `BASE.md`, com as células de família nomeadas.
4. `tests/test_spec369_metas.py` (R11) com os limiares do §8. Ele falha pelo motivo certo: artefato final ausente.
5. Commit, revisão `Astra` e pouso da Fase A. O `<sha-A>` vai para §9. O BASE.md vai para o dono (gate R9c).

### Etapa 2 — `draft.py` (B1, R12)

1. **Testes** (`ScriptedLLM`):
   - `test_triagem_reprova_fora_do_orcamento`: Carta com `power_score` acima da faixa vai para `rejeitadas` com motivo `orcamento`;
   - `test_reparo_recebe_power_score_e_faixa`: a mensagem de reparo contém o score, a faixa e a direção;
   - `test_ajuste_deterministico_poe_na_faixa`: depois do reparo falho, a Carta sai com `ajuste_orcamento` e `check_budget == []`;
   - `test_ajuste_desiste_e_rejeita`: Carta impossível segue rejeitada, com motivo;
   - `test_reparo_fallback_llm`: `AIMessage` no reparo vira lote sem reparo, sem exceção.
2. **Implementação** em `draft.py`.
3. **Verificação:** `tests/test_card_draft.py`, `tests/test_spec387_draft.py` e o teste novo, com `-n 2`.

### Etapa 3 — Emboscada do Corruptor (B2, R17)

1. **Testes:**
   - `test_corruptor_tem_carta_de_iniciativa_no_tronco`;
   - `test_has_vigilia_corruptor_com_carta`;
   - `test_opening_initiator_corruptor_ambush_negated`;
   - a Carta nova passa em lint, orçamento e roda.
2. **Conteúdo** e `_ondas.yaml`.
3. **Verificação:** `metricas_369.py emboscada --seeds 0-19` com Corruptor ≥ 45,0 % e as outras Posturas idênticas à base; `posturas` dentro do R19.

### Etapa 4 — Cartas por rodada, dominância e duração (B3, R13–R15)

1. Ponto de partida: o `uso` e a `duracao` do BASE.md.
2. **Candidatas** [H], que o BASE.md confirma ou descarta:
   - `med1_fer_lente_de_protese` (uso 1,0): um degrau de `frequencia` ou `custo_folego` 0 → 1;
   - `bas_cor_mofo` (uso 60,7 %);
   - para as Cartas por rodada, as assinaturas básicas fora do Sangromante (`bas_dev_voto` `:43`, `bas_cor_mofo` `:158`, `bas_arc_vazao` `:216`, `bas_med_pressao` `:274`) com `custo_folego` 1 → 0;
   - para a duração do Médico, `bas_med_golpe` dano 3 → 4 (`basicas.json:248`) e Cartas de onda do Médico com Torpor/dano.
3. Um passo por vez, com `base` + `posturas` depois de cada um e o registro em `passos-0-19.json`.
4. **Verificação:** `tests/test_spec369_metas.py -k "rodada or dominancia or duracao"`, os testes de lint e acervo do escopo e `validate_content` com 0 erros.

### Etapa 5 — `bomba_estopim` (B4, R14b)

1. **Passos** em `arc1_imp_bomba_estopim` (`arcanista_cinzento_improvisador.json:199-209`), na ordem:
   - `valor` 3 → 2 no efeito em área;
   - depois `custo_entropia` 1 → 2.
2. **Verificação:**
   - `uso` sem bandeira por delta nas 0–19;
   - Arcanista `todas` ≥ 45 % e improvisador padrão ≤ 75 % (R19a).

### Etapa 6 — Presságio (B5, R16), condicional

Só se a primária falhou na base. Os passos de custo e valor nas defesas (R18a/b) vêm um por vez, remedindo `pressagio` (`conhecida`, decks `on`) e `posturas`.

### Etapa 7 — Famílias (B6, R20)

Para cada célula do BASE.md, a Carta de maior dano da família leva até 2 passos, com `familias --seeds 0-7 --only <familia>`. As outras células da família não pioram mais de 5 pp.

### Etapa 8 — Final e revisão (Fase B)

1. `final-0-19.json` e `RELATORIO.md` (antes × depois, com o Δ de cada passo).
2. `tests/test_spec369_metas.py` verde, exceto a confirmação.
3. `git diff --exit-code main -- <R2>` e `git diff --exit-code <sha-A> -- <arquivos da Fase A>` vazios.
4. Revisão `Sol` (`handoffs/SPEC-369-sol-review.md`). Ela confere R1, R2, R4, os limites do R18 e a ordem dos commits.

### Etapa 9 — Confirmação (Fase C, R22)

Uma rodada nas 260–339 → `confirmacao.json` → `tests/test_spec369_metas.py` inteiro. Falhou: registro e devolução, sem reajuste.

## 5. Critérios de aceite

- [ ] R1: Fase A e Fase B por agentes distintos; nenhum commit da Fase B em arquivo da Fase A; `<sha-A>` em §9
- [ ] R2: diff vazio em avaliadores, orçamento, golden, snapshot, testes de artefato e `web/e2e/contracts`
- [ ] R9: `base` reproduz a 368; BASE.md com as 7 metas, as células de família nomeadas e a aprovação do dono registrada
- [ ] R10/R11: testes da régua verdes; testes de meta escritos antes do produto
- [ ] R12: `draft.py` com orçamento e raridade na triagem, reparo com score e faixa, ajuste determinístico; testes offline verdes
- [ ] R13: Cartas por rodada total ≥ 2,00, cada Postura ≥ 1,90 (0–19 e 260–339)
- [ ] R14: 0 de onda fora do Sangromante com uso > 60 %; 0 `dominante` por delta fora do Sangromante (inclui `bomba_estopim`); tabela por categoria registrada
- [ ] R15: p95 total ≤ 10, toda Postura ≤ 12, timeouts ≤ 1,0 % (0–19 e 260–339)
- [ ] R16: `on-faixa` ≤ 95 % do dano do `on-cego` (`conhecida`, decks `on`), vitória em 45–85 %; secundária registrada
- [ ] R17: Carta `buff_iniciativa` do Corruptor; emboscada realista ≥ 45,0 % (0–19 e 260–339)
- [ ] R18: ≤ 8 Cartas de herói, ≤ 2 passos cada, `versao` + 1, lint, orçamento e `validate_content` limpos
- [ ] R19: guardas globais em todos os passos e no final
- [ ] R20: células de família dentro de 45–85 % e |Δ| ≤ 10 pp (0–7 e 260–267)
- [ ] R22: confirmação única gravada; nenhum reajuste depois dela
- [ ] Revisão `Astra` da Fase A e `Sol` da Fase B, sem P0/P1 aberto
- [ ] `uv run pytest` verde (suíte completa, 1× no pouso de cada fase, coordenador)
- [ ] Guard de FallbackLLM mantido no `draft.py`; nenhum `with_structured_output` novo
- [ ] Saves antigos carregam: saves guardam ids, e o motor lê a `versao` do catálogo; a Carta nova não aparece em save antigo
- [ ] Smoke §6 registrado em `docs/spec369/smoke.md`

## 6. Smoke test com LLM real

O balanço é determinístico, e a Fase C é a prova dele. O LLM real entra em dois pontos: no `draft.py` (structured output) e na narração do combate com as Cartas alteradas. O MockLLM esconde erro de mapeamento de campo. Registrar provider, modelo e custo.

1. **`draft.py` com chave real**, 2 lotes (2 chamadas SMART + até 2 reparos):
   `bash scripts/dev/py.sh scripts/cards/draft.py --postura "Médico de Campo" --subclasse boticario --n 4 --raridades comum,incomum --onda 369`
   e o mesmo para `--postura "Corruptor" --subclasse alma`. Depois rodar os 3 comandos impressos (`lint` → `sim --protocolo lote-v2` → `promote --voz-pendente`) **sem editar a linha**.
   - **Meta:** ≥ 6 de 8 Cartas passam no `lint` sem erro.
   - Registrar quantas precisaram de reparo e quantas de ajuste determinístico.
   - Os rascunhos ficam em `data/cards/_rascunhos/`, e nada é promovido ao pool.
2. **Corruptor emboscado**, API local `legacy` com o preset do staging (`scripts/staging/staging_flags.json`, cartas `on`):
   - criar um Corruptor nível 1 com a Carta nova preparada;
   - forçar `encounter_surprise == "enemy"` (a receita do `seed_save` da 368 com o mundo ajustado, ou uma viagem até o encontro);
   - **esperar:** abertura sem emboscada (`ambush_negated_vigilia` no trace), narração coerente e 0 LLM por rodada no log;
   - repetir com a Carta fora das preparadas e esperar a emboscada.
3. **Cartas alteradas na tela:**
   - um conflito com uma Postura que teve Carta alterada no B3 (Médico, se `bas_med_golpe` mudou);
   - o texto da Carta na mão mostra o número novo (`card_effects.render_card_text`);
   - o `mech_log` bate com esse número;
   - a narração final não contradiz o efeito.
4. **Presságio com família conhecida:** segundo conflito contra a mesma família. O painel mostra a `faixa`, e jogar a defesa naquela rodada reduz o dano em relação à faixa anunciada, conferido no `mech_log`.
5. **Staging**, depois do deploy e com os smokes pós-deploy verdes: itens 3 e 4 repetidos uma vez, com custo registrado.

## 7. Riscos & compatibilidade

- **Integridade de eval.** O risco central é "melhorar a meta mudando a régua". As defesas são três:
  - a régua é escrita e congelada por outro agente antes do produto (R1);
  - o bot do Presságio fica pré-registrado nesta spec (R7);
  - os limiares ficam em teste escrito pela Fase A (R11), e a confirmação é única, em sementes novas (R22).

  Se a Fase B precisar de régua nova, ela para e devolve.
- **A meta do Presságio pode fechar sem mudar produto.** Se `on-faixa` já baixa o dano na base, a 329 fecha pela régua nova. Isso é legítimo **porque** o bot está pré-registrado e a comparação é contra `on-cego`, no mesmo motor. O dono decide se a comparação contra `off` continua sendo critério (D-369-2).
- **Alavancas acopladas.** Básicas e Fôlego mexem em todas as Posturas ao mesmo tempo. O R19 trava a faixa por Postura, e o limite de 8 Cartas segura o escopo. O Fôlego 3 fica fora, salvo D-369-1: a calibração da 328 deu +19 pp sobre o `off` (`card_piles.py:33-35`).
- **Overfitting às 0–19.** A Postura tem 360 lutas na `base` (erro padrão de cerca de 2,5 pp na vitória). A confirmação nas 260–339 tem 4× mais lutas e não aceita reajuste.
- **Legadas.** Sem o D-369-4, 5 Cartas seguem com uso > 60 %, e isso fica registrado como "travadas pelo golden". Com o D-369-4, só o `custo_folego` muda, e o golden prova que o modo `off` não mudou.
- **Sangromante.** As guardas globais podem movê-lo, porque básicas e Fôlego são compartilhados. O R19b limita esse movimento a +2 pp.
- **Saves.** Saves guardam ids. Uma Carta alterada vale pela `versao` do catálogo, e não há migração. A Carta nova só aparece em personagens que a obtêm.
- **MockLLM/FallbackLLM.** O reparo e o ajuste do `draft.py` mantêm o guard (`draft.py:256`, `:323`). O ajuste é determinístico e não chama LLM.
- **Quota e latência.** O smoke usa cerca de 4 chamadas SMART e uns 30 turnos. O combate não ganha LLM.

## 8. Decisões

### Do autor (valem como propostas; o dono confirma ou troca)

- **D-369-1 — Fôlego e mão ficam como estão (`FOLEGO_BASE` 2, `MAO_BASE` 5).** *Default: não mexer.* A meta 1 sai de jogadas de Fôlego 0 em assinaturas básicas e Cartas de onda (R18a/b). Se 8 Cartas não bastarem, o executor devolve, e aí o dono escolhe entre Fôlego 3 (com uma rodada nova de arena por Postura) ou aceitar 1,9x.
- **D-369-2 — Critério da 329.** *Default: o primário é `on-faixa` ≤ 95 % do dano do `on-cego`, com inimigo `conhecida` e decks `on`; o `on` × `off` é só registrado.* O texto original ("cai em relação ao `off`") mistura o efeito do congelamento com o valor da informação (§1).
- **D-369-3 — Metas numéricas desta spec.** *Default:*
  - Cartas por rodada: total ≥ 2,00 e cada Postura ≥ 1,90;
  - dominância nas camadas do R14: o golpe básico é aceito como fallback; a meta é 0 Carta de onda com uso > 60 % e 0 `dominante` por delta, fora do Sangromante;
  - p95 total ≤ 10, toda Postura ≤ 12 e timeouts ≤ 1 %.

  O critério literal do dono ("nenhuma Carta com uso > 60 %") continua sendo medido e reportado, mas não é alcançável sem mudar o bot. Mudar o bot é régua, e ficou fora.
- **D-369-4 — `custo_folego` explícito em 5 legadas** (`arc_descarga`, `arc_faisca`, `arc_des_mao_nua`, `cor_bio_gangrena`, `med_fer_talas`). *Default: não.* Elas ficam como "travadas pelo golden". Com um "sim", só esse campo muda, e só se a Etapa 0 provar o golden e o snapshot byte-idênticos.
- **D-369-5 — Ajuste determinístico do orçamento no `draft.py`.** *Default: sim.* No máximo 6 passos, só nos números, com marca `ajuste_orcamento` para a curadoria ver. O `_fit_orcamento` da `gerar_mecanica.py` é extraído para `services/card_budget_fit.py` e reaproveitado, com teste de equivalência na saída do bestiário. Alternativa: só o reparo por LLM com score e faixa (R12a/b), sem ajuste.
- **D-369-6 — Tipo da Carta do Corruptor.** *Default: `passiva` comum de tronco*, como a `dev_zel_vigilia`. A ferramenta `emboscada` da Fase A credita passivas preparadas, como o produto faz. Alternativa: `reacao`. Ela entra no `full_deck` e na régua antiga, mas disputa vaga no baralho.
- **D-369-7 — Quais são as células de família.** *Default:* `off` ∈ [45, 85] e `on` fora, ou |Δ `on`−`off`| > 10 pp, com 200 combates por célula. Pelos números do lote 2, o candidato é **conjurador L5**. Os outros (morto-vivo L3, guardião L3, covarde L5) têm o `off` já fora da faixa ou passam a ficar dentro com o `on`. O BASE.md nomeia a lista.
- **D-369-8 — Sangromante sob alavanca global.** *Default:* a alavanca compartilhada (básicas que não são dele, Fôlego) pode movê-lo no máximo +2,0 pp no total. Acima disso o passo é revertido.
- **D-369-9 — Uma spec, três fases** (em vez de duas specs). *Default: uma spec.* Separar exigiria reservar um ID (é do coordenador). As garantias de integridade são as mesmas pelo R1. Se o dono preferir, a Fase A vira `SPEC-NNN-regua-metas-cartas` e esta spec passa a depender dela.

### Para o dono confirmar antes da Fase B (gate R9c)

1. D-369-2: o critério da 329 passa a medir o valor da informação (`on-faixa` × `on-cego`)?
2. D-369-3: as metas em camadas (sem exigir 0 golpes básicos com uso > 60 %) estão boas?
3. D-369-1 e D-369-4: manter o Fôlego 2 e as legadas travadas?
4. D-369-7: a lista de células do BASE.md.

## 9. Registro de implementação

(vazio — preencher por fase: Etapa 0, `<sha-A>`, base, passos, final, confirmação, desvios)
