# SPEC-387 — revisão sol (review)

> **Veredito (rodada 3):** `CHANGES_REQUIRED` (rodadas 1 e 2: `CHANGES_REQUIRED`)
> **Revisor:** Opus 5.5 / papel Sol · **Data:** 2026-11-03 · **Commits revisados:** rodada 1 `4ceb5f94` (`a965031e..4ceb5f94`, base `8ff8d674`); rodada 2 `07116abd` (`eb11d4a9..07116abd`); rodada 3 `1557736e` (`e53d525d..1557736e`)

## Escopo

`git diff main...spec-387` (56 arquivos) revisado contra R1–R41 e D-387-1..11 (recomendações do §8). Leitura completa
dos trechos de motor (`conflict_orchestrator`, `card_piles`, `cards`, `scene_cards`, `round_log`, `combat_preview`),
API (`_portrait_*`, `_image_effect_open`, `_cards_block`), `generic_spawn`, `checkout_retry`, `kill_switches`, `loot`,
`prose_guard`, `llm_setup`/`AGENTS.md`, `draft.py`, front (`App.tsx`, `portraitOrder.ts`, `PlayQueue.tsx`, `TargetChip.tsx`,
CSS) e testes novos e alterados. Fora: smoke §6 (LLM/staging), e2e Playwright (não rodados aqui; typecheck e eslint sim).

**O que está correto (conferido):**
- **S6-1:** `rehydrate_safe` no fim de `_raw_to_state` (`persistence.py:1167`), caminho comum de legacy e hosted. Toda
  rota da API carrega o estado por request (`load_game_state` → `_raw_to_state`), então `check_declared_target` já vê a
  Carta reidratada. O LRU de 64 só afeta o catálogo entre requests, e cada load o reconstrói. A órfã é omitida da view
  (`card_piles.py:752-754`). Sem cache de processo como fonte.
- **S6-2:** falha de leitura do preço nunca vai ao cache (`api.py:2922-2923`). `retry_once` repete só falhas de
  checkout (critério único movido para `services/checkout_retry.py`, e `ops_pool` importa de lá). Erro de `execute` sobe sem
  repetir. `offer_omitted` leva só `cause` e `error_class`: sem id de jogo e sem DSN.
- **S6-3:** `withPortraitPending` é aplicado antes do 1º `await`, com snapshot. `restorePortrait` roda no erro da
  cotação, no erro da confirmação e no cancelamento do diálogo. `disabled` real e `genDisabled={busy || imageBusy}`.
  Testes do helper verdes, typecheck e eslint verdes.
- **S6-4:** `services/generic_spawn.py` é determinístico (`crc32(game_id|turn|hint)` sobre lista ordenada), sem chefe e
  com o filtro de perigo da fauna. O inimigo gerado entra no estado salvo, então a escolha é restaurável. Dica específica não
  muda (`is_contentless_name` → `None`).
- **L1:** `ROUTES[CLASSIFY]` passa a ser 120b → 20b. `AGENTS.md` bate com `ROUTES`. Nenhuma rota ou fixture usa
  `llama-3.3-70b-versatile`. `load_dotenv(override=True)` foi mantido, com comentário.
- **L2:** `cards.playable_ids` é o predicado único de `use_card` e `plan_plays`. A recusa sai antes de gastar, e o catálogo
  de recusas é humano e sem id.
- **L3:** `proteger` sem ator vira `derrotar_todos` (sanitize e `check_objective` de save antigo). `objective_failed`
  narra a causa e o `outcome` salvo segue `defeat`.
- **Seeds:** as 11 variantes existem. Cada uma tem teste de save → load → view e uma rodada com 50 sementes.
- **`draft.py`:** `alvo` tem enum no schema, o reparo é feito 1× com guard de FallbackLLM, os comandos impressos fazem
  `parse_args` e `lint/sim/promote` ficam sem diff.
- **Integridade (R38–R40):** diff vazio em `evals/`, `tests/spec330_equivalence.py`, golden 330, `scripts/cards/{lint,sim,promote}.py`,
  `_orcamento.json`, `config/flags.yaml` e `web/e2e/contracts`. Em `web/e2e/` só há arquivos novos.
- **Testes antigos alterados:** nenhum afrouxa oráculo.
  - `test_spec368_seed`: o item 15 novo foi acrescentado ao conjunto esperado.
  - `test_enemy_intent`: a igualdade exata ganhou `carta_id` e continua exata.
  - `test_spec363_golden_guard`: o skip vale só para a guarda do motor fora da branch `spec-363`. Na `main` ela comparava
    com a própria `main` (vácua), e a guarda dos goldens segue ativa.
  - `size_budget.json`: o rebaseline usa a exceção prevista ("`--update` + motivo no commit", `4e246c45`).

## Commit 4ceb5f94 (`_can_act` depois da janela de Reação) — julgamento de motor

- **A regra está correta e é coerente com o precedente:** o caminho de AoO já faz `if not _can_act(actor): return` logo
  depois de `_resolve_opportunity_attacks`. Golden 330 e as guardas seguem verdes.
- **Arena de Cartas (`scripts/cards/sim.py`: `lote-v2`, ref. v2, 9 chefes, Arcanista 362): não precisa rebater.**
  - Instrumentei `_open_reaction_window` nos testes de sim e arena (`test_card_sim*`, `test_spec341_balanco`,
    `test_spec355_arena`, `test_spec362_*`). Resultado: **0 atacantes derrubados em 27.778 janelas**.
  - O bot do sim não declara Reação do herói (`sim.py:369`, "o motor joga, o bot não declara"). Só Reação de inimigo com
    dano pode disparar a regra: `bst_casca_reativa` (10 criaturas do bestiário) e `reflexo_lamina`, e só com o herói
    na beira.
  - Critério: rebater só se a frequência medida passar de 0,5 % das janelas ou se um chefe ou Postura tiver Reação letal
    no deck. Hoje nenhum dos dois acontece.
- **Arena "a luta ensina" (`scripts/fauna/arena_saber.py`, SPEC-371):** aqui a regra dispara, porque o bot `leitor`
  declara Reação do herói.
  - Medição nos testes da 371: 1 em 238 janelas (≈ 0,4 %).
  - O efeito é simétrico entre luta 1 e luta 2, e `test_spec371_eval` (E5 byte-idêntico + mini-arena) passou.
  - Não exige rebater para pousar. Se o coordenador quiser confirmar, basta 1×
    `arena_saber.py --regiao nova_arcadia --seeds 20` com o critério "veredito E2/E3 igual ao de `docs/spec371/`". Se o
    veredito virar, vai ao dono (o avaliador é congelado).
- **Efeito colateral:** ver P1-2. O presságio fica marcado "cumprido" com a Carta revelada mesmo quando o atacante não
  resolve o ataque.

## Golden `tests/test_spec360_flags_off.py`

- **Escopo da diferença:** comparei as mensagens dos 30 turnos (`explorador`, flags `off`) na base `8ff8d674` e na branch.
  A ÚNICA diferença está em 3 mensagens, todas do fallback `off` de `_narrate` (`⚔️ • …` → parágrafo). Turnos, rotas,
  Vitalidade, ouro, relógio, local e `bestiary_knowledge` são idênticos.
- **Testes afetados:** o mesmo golden derruba também `tests/test_spec371_flags_off.py::test_golden_360_inalterado_com_a_flag_off`.
- **Pode regravar?** Sim. `SPEC360_REGEN=1` pelo coordenador não viola integridade: o arquivo não está em
  `evals/protected-paths.txt`, é guarda de byte-identidade das flags de fauna (não um oráculo de qualidade do produto), e a
  mudança vem de requisito aprovado (R33).
- **Quando regravar:** **só depois de corrigir P1-1.** O texto novo ainda vai mudar. Na regravação, conferir de novo que a
  diferença fica restrita às mensagens do fallback `off` e registrar no §9.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/round_log.py:896-910` (`off_fallback_text`), chamado em `agents/combat.py:1828` | O fallback `off` (default do staging e da produção, cartas `off`) agora esconde os fatos da rodada. No golden 360, uma rodada em que o herói tenta fugir, é alcançado, vai a Vitalidade 0 e sofre **Ferimento grave no torso e na perna** vira só "Sua condição Sangramento terminou. O que você faz?". Outra rodada vira só "A condição Tirantes Esticados de Crescido do Clã terminou.". O filtro `_is_human_line` derruba até a linha já humana e na voz do jogador "Você tenta fugir, mas os inimigos te alcançam.". Com uma rodada só de ataques, o texto vira apenas "O que você faz?". R33 pede sem id e sem bullets, não sem fatos. | Manter as linhas que já são humanas (fuga, "Você …", recusas) e traduzir as técnicas em vez de descartá-las: ataque `X → Y: acerto/erro (…)` → "X acerta/erra Y"; `Ferimento <cat> em <região>` → "Você sofre um ferimento <cat> no/na <região>"; `Vitalidade a -> 0` → "Você fica sem Vitalidade". Reaproveitar o que o registro já faz (`_attack_line`/`_sem_vitalidade_line` ou um helper comum) e não criar um 3º dialeto. Teste com os logs reais do golden 360 (fuga + acerto + ferimento): o texto cita a fuga falha, o golpe e o ferimento, sem id, "⚔️" ou "•". Depois regravar o golden 360 (ver seção acima). |
| P1-2 | P1 | `services/conflict_orchestrator.py:1933-1934` com `:2776-2787` e `services/combat_preview.py:636-646` | Com 4ceb5f94, o atacante derrubado pela Reação não resolve o ataque, mas já tinha sido registrado em `pressagios_cumpridos` (com `carta_id`) e já tinha recebido o log "Goblin cumpre o que o presságio anunciava.". Reproduzi com a seed `13 reacao`, semente 0: `CUMPRIDOS [{'actor_id': 'enemy_goblin_1', …, 'carta_id': 'inf_bruto_investida_cega'}]`, `FRUSTRADOS None`, e "Usa Investida Cega" ausente. Com a R30, o quadro mostra "Presságio cumprido: Goblin — Investida Cega": mentira mecânica, e **revela a Carta oculta que nunca foi jogada** (a R30 só autoriza o nome de Carta jogada). O mesmo vale para o caminho de AoO, que já existia. | Quando `_can_act(actor)` cair depois da janela de Reação (e da AoO), mover a entrada do ator de `pressagios_cumpridos` para `pressagios_frustrados` (causa `incapaz`, via o `_frustrate` existente) e retirar a linha "cumpre o que o presságio anunciava." dessa rodada. Teste na `test_reacao_kills_and_the_summary_cites_the_author` (50 sementes): o inimigo não está em `pressagios_cumpridos`, está em `pressagios_frustrados`, o `round_board` não tem `tipo == "pressagio"` com `carta_nome`, e o registro mostra "Presságio frustrado: Goblin". Conferir de novo o golden 330 e o E5 da 371. |
| P1-3 | P1 | `services/conflict_orchestrator.py:3025` × `tests/test_objectives.py:153` | `out["objetivo"]` ganhou `motivo` (desvio 6 do §9), mas `test_objectives.py::test_run_round_encerra_com_desfecho_proprio` compara o dicionário por igualdade e **falha na branch**. O teste não foi atualizado nem aparece em "Testes antigos alterados" do §9. A suíte completa do pouso fica vermelha. | Atualizar a expectativa com `"motivo": "Vocês resistiram por 2 rodadas."`, mantendo a igualdade exata (não trocar por `<=`/subconjunto), e registrar no §9 com o motivo (R20). Rodar `tests/test_objectives.py` inteiro. |
| P2-1 | P2 | `tests/test_spec387_scene_cards_cold.py:52-61` | R3 pede `POST /game/action` com `_TEMP_CARDS` vazio respondendo **200, com a linha da Carta no registro e o efeito aplicado**, nada de 409. O teste só chama `check_declared_target` depois de `_reload`. Não prova o caminho da API nem o efeito. O mesmo vale para o caso do LRU (só confere `get_card`). | Teste pela API (`TestClient`, perfil legacy, save semeado com Carta de cena): limpar `_TEMP_CARDS` (e, num 2º caso, encher o LRU com 63 Cartas) antes do POST com `jogadas=[{card_id, target_id}]`. Afirmar 200, a linha "Empurrar (Poço Negro)" no registro e o dano aplicado no inimigo. |
| P3-1 | P3 | `tests/test_spec387_scene_cards_cold.py:72-80` | R4 manda registrar `combat.scene_card_orphan`, mas o teste da órfã só afirma que a linha some, sem conferir o evento. | Capturar `log_event` (monkeypatch em `card_piles.log_event`) e afirmar 1 evento `("combat", "scene_card_orphan")` sem campo de id. |
| P3-2 | P3 | `tests/test_spec387_generic_spawn.py:61-70` | `test_no_fallback_from_contentless_name` só afirma a ausência de `spawn_identity_mismatch`. Ele passa sem nunca chegar ao ramo novo (por exemplo, se o template casar por nome), então não prova R11. | Afirmar também `"spawn_generic_name" in events` e que o inimigo resultante não tem id `fallback_criatura_hostil` quando houver um candidato regional. Se R11 aceitar o fallback sem candidato, documentar isso no teste. |
| P3-3 | P3 | `scripts/cards/draft.py:105-116, 140` | A docstring de `_budget_text` diz "LIDOS do orçamento e do lint (nada copiado à mão)", mas a linha de complexidade (`regra`, `:114`) é cópia à mão de `card_lint.check_raridade` (`card_lint.py:247-251`). Se o lint mudar, o prompt mente. `_examples` recebe `postura`/`subclasse` e não os usa. | Expor os limites no `card_lint` como constante, sem mudar o valor, ou acrescentar um teste que compare `regra` com o comportamento de `card_lint.check_raridade` (Carta comum com 2 efeitos → erro; incomum com 2 → ok). Corrigir a docstring e tirar os parâmetros não usados. |
| P3-4 | P3 | `web/e2e/spec387-omen-390.spec.ts:12` | R32 pede a verificação "na rolagem padrão depois de abrir o combate", mas o teste chama `omen.scrollIntoViewIfNeeded()` antes de medir, o que muda a rolagem. O achado original (L11) era justamente na rolagem padrão. | Medir antes de qualquer rolagem explícita. Num 2º passo, rolar o contêiner até o fim e medir de novo (o caso em que o `padding-bottom` reservado importa). Manter a afirmação de `paddingBottom > 0`. |
| P3-5 | P3 | `specs/SPEC-387-cartas-smoke6-serverless.md` §9 | O registro não cita: (a) a mudança esperada do golden 360, que derruba 2 testes, `test_spec360_flags_off` e `test_spec371_flags_off::test_golden_360_inalterado_com_a_flag_off`; (b) `test_objectives` (P1-3); (c) o 2º rebaseline do `size_budget.json` em 4ceb5f94 (`_resolve_actor_turn_inner` 184→186), feito sem motivo no commit. | Acrescentar as três notas ao §9, com o motivo, junto com as correções acima. |

## Correções aplicadas

Nenhuma ainda: 1ª rodada.

## Pendências

Nenhuma aceita como follow-up (política do dono: zero pendência). Todos os achados acima bloqueiam. Ficam para o
coordenador:
- o smoke §6 (itens 1–16), que exige LLM e staging;
- a regravação do golden 360 depois de P1-1;
- a confirmação opcional da arena_saber (ver o julgamento do 4ceb5f94).

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_spec387_*.py test_spec368_seed test_enemy_intent test_spec363_golden_guard test_routing test_card_draft test_spec346_board_no_llm test_spec364_flee_surfaces test_scene_cards{,_extra,_node} test_size_budget → 232 passed, 2 skipped
bash scripts/dev/pt.sh (24 arquivos vizinhos: guards 353/355/364/367, registry, objetivos, prose_guard, reação, ops_pool, trade_gold, portrait 363/364/367, 371 reação, 368 scenarios, loot, flags) → FAILED tests/test_objectives.py::test_run_round_encerra_com_desfecho_proprio (P1-3); resto 302 passed, 2 skipped
bash scripts/dev/pt.sh (19 arquivos: market, latency, outcome 346, rótulo facção, progressão, classify_ab, prepare_api, acervo, fase53, portrait 352/354, routing_tiers, eval_routing) → 269 passed
bash scripts/dev/pt.sh tests/test_spec360_flags_off.py → FAILED test_golden_flags_off_byte_identico (esperado; diff só no fallback off)
bash scripts/dev/pt.sh test_card_sim test_card_sim_v2 test_spec341_balanco test_spec355_arena test_spec362_arcanista test_spec362_run_round test_card_piles → 119 passed, 1 skipped
pytest -p countplug (instrumentação de _open_reaction_window) sim/arena → 27.778 janelas, 0 atacantes derrubados; 371 → 238 janelas, 1 derrubado; seeds 387 + 355 → 54/1333
pytest -p countplug test_spec371_* → FAILED test_spec371_flags_off::test_golden_360_inalterado_com_a_flag_off (mesmo golden 360)
dump das mensagens do golden 360 (base 8ff8d674 via git archive × branch) → diff só em 3 mensagens do fallback off
seed 13 reacao, semente 0 → CUMPRIDOS com carta_id inf_bruto_investida_cega, FRUSTRADOS None (P1-2)
ruff check / ruff format --check (39 .py alterados) → ok
dup_helpers --diff main...HEAD → só `_refuse` (homônimo aninhado em inventory.py, semântica distinta; ok)
node --test web/tests/spec387-portrait-optimistic + spec354-roundboard → 7 pass; npm run typecheck → ok; eslint (arquivos alterados) → ok
```

---

## Rodada 2 (commit `07116abd`, diff `eb11d4a9..07116abd`)

### Estado dos achados da rodada 1

| ID | Estado | Evidência |
|---|---|---|
| P1-1 | **Parcial** (ver R2-P1-1) | `_translate_logs` (`services/round_log.py:907`) agora traduz golpe, ferimento, Vitalidade 0, fuga e "terminou". Mas o filtro de "técnica" (`:938`) descarta toda linha com dígito e todo "Usa …". |
| P1-2 | Resolvido, com 1 lacuna (ver R2-P2-1) | `_retract_omen` (`conflict_orchestrator.py:1866`) roda depois da Reação e da AoO. A seed `13 reacao` (50 sementes) afirma que o presságio sai de cumpridos e entra em frustrados, que não há "cumpre…", que o quadro não tem presságio com Carta e que o texto diz "Presságio frustrado: Goblin", sem "Investida". |
| P1-3 | Resolvido | `tests/test_objectives.py:156` ganhou `motivo` na igualdade exata (oráculo não afrouxado). |
| P2-1 | Resolvido | `test_cold_instance_play_via_api[0/63]`: POST real, 200, "Empurrar (Poço Negro)" no texto e dano no inimigo. |
| P3-1 | Resolvido | O evento `scene_card_orphan` é afirmado, 1×, sem id. |
| P3-2 | Resolvido | `spawn_generic_name` é alcançado sem candidato regional. Com candidato, não há `fallback_criatura_hostil` e nenhum dos dois eventos. |
| P3-3 | Resolvido | O teste compara a regra do prompt com `card_lint.check_raridade` (comum/incomum, nos limites). A docstring foi corrigida e `_examples` não tem mais parâmetro sem uso. |
| P3-4 | Resolvido | O e2e de 390 mede antes de qualquer rolagem e de novo rolado até o fim. eslint ok. O Playwright não rodou aqui. |
| P3-5 | Resolvido | O §9 registra o golden 360 (2 testes), o `test_objectives` e os rebaselines do `size_budget`. |

### Golden 360: escopo do diff e regravação

- **O que mudou:** gerei de novo as mensagens dos 30 turnos (`explorador`, flags `off`) na base `8ff8d674` e em `07116abd`.
  Só mudam as **mensagens 12, 14 e 20** (índice 0; linhas 14, 16 e 22 do JSON), todas do fallback `off`. O resto do
  fingerprint é idêntico.
- **"Usa Punho de Tala" não é jogada do herói.** A Carta é `cri_jotun_cinza_punho_de_tala`, do Crescido do Clã, e a linha
  seguinte é o golpe dela ("Crescido do Clã → Playtest-explorador: erro/acerto"). A ação do herói nessas 3 rodadas é a
  fuga, e ela continua no texto novo ("Você tenta fugir…" e "Você avança na fuga…"). O golpe aparece traduzido ("Crescido do
  Clã erra/acerta você"), e os ferimentos também. Nessas 3 mensagens só some o **nome** da Carta inimiga.
- **O defeito existe fora do golden:** o mesmo filtro perde ações do herói que não são ataque (ver R2-P1-1).
- **Pode regravar?** Sim. `SPEC360_REGEN=1` pelo coordenador não viola integridade: o arquivo não está em
  `evals/protected-paths.txt`, a guarda é de byte-identidade das flags de fauna e a mudança vem do R33. Mas **só depois de
  fechar R2-P1-1**, porque a correção pode mudar de novo as mensagens 12/14/20 (por exemplo, "Crescido do Clã usa Punho de
  Tala"). Ao regravar, conferir de novo que só mudam essas mensagens do fallback `off`.

### Achados novos / remanescentes

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R2-P1-1 | P1 | `services/round_log.py:938` (filtro `technical`) e `tests/test_spec387_text.py:227` | O tradutor ainda **apaga ações do herói que não são ataque**. Sonda: logs `["Usa Bandagem de Campo", "Smoke recupera 3 Vitalidade.", "Usa Golpe Rachado", "Smoke → Goblin: acerto (…)", "dano 6×1=6; Vitalidade 9 -> 3 …", "Smoke sofre 1 de Sangramento (Vit 4)."]` → `"Você acerta Goblin.\n\nO que você faz?"`. A cura com Carta (`conflict_turn.py:653-656`, "X recupera N Vitalidade com <Carta>.") e o dano contínuo caem pelo `re.search(r"\d", line)`, e toda linha "Usa <Carta>" cai pelo `startswith("Usa ")`. Uma rodada só de apoio (cura, proteção) vira "O que você faz?". O teste novo **fixa** esse defeito: `not re.search(r"\d", text)` em `:227`. O R33 não proíbe números no texto determinístico (o fallback antigo e o `deterministic_outcome_text` têm números); proíbe id, bullet e nome do herói. | (1) Traduzir "Usa <Carta>": o ator é o da próxima linha de golpe (`X → Y`) ou, sem golpe, o herói quando a Carta estiver em `deck`/`prepared_cards`/`virtue_cards`/cena. Resultado: "Você usa <Carta>." ou "<Inimigo> usa <Carta>.". Passar os ids ou nomes das Cartas do herói a `off_fallback_text`, com `_narrate` já tendo `player`. (2) Manter as linhas humanas com número: "X recupera N Vitalidade com C." → "Você recupera N de Vitalidade com C."; "X sofre N de <cond> (Vit k)." → "Você sofre N de <cond>.". Descartar só aritmética (`_is_arith`, "dano a×b=c", "a -> b") e id. (3) Trocar a asserção de `:227` por "sem aritmética e sem id". Somar um caso com Carta de cura e um com dano contínuo, os dois com a ação do herói no texto. Depois regravar o golden 360. |
| R2-P2-1 | P2 | `services/conflict_orchestrator.py:1866-1878` × `:2670-2684` | `_retract_omen` registra o presságio como frustrado, mas, ao contrário de `_frustrate`, **não dispara o gatilho `ao_pressagio_frustrado`** (SPEC-330 R3), nem quando o alvo do presságio está na cena. Uma Carta usa esse gatilho: "Ferro Antes do Ferro" (Devoto Zeloso, `data/cards/posturas/devoto_zeloso.json`, cura quando o presságio é frustrado, "abatê-lo antes vale uma cura"). Matar o atacante com a Reação (`dev_encaixe`, do mesmo Devoto) é exatamente esse caso. Quando o inimigo morre por outro caminho antes do turno, o `_frustrate(…, "incapaz")` dispara o gatilho. Pela Reação, não. Resultado: dois "frustrados" com efeitos diferentes. Não regride em relação à `main` (lá era "cumprido", sem gatilho), mas a reclassificação cria a incoerência. | Extrair o corpo de `_frustrate` (entrada, `fx.fire("ao_pressagio_frustrado", …)` e linha) para um helper de módulo usado pelos dois caminhos, e passar a intenção congelada do ator. A alternativa é registrar no §9/§8 a decisão explícita de não disparar (com o motivo). Teste: Devoto com "Ferro Antes do Ferro" ativa e Reação `dev_encaixe` matando o atacante → o gatilho dispara uma vez, ou fica comprovadamente inerte se a decisão for documentada. A arena de Cartas não é afetada (0 atacantes derrubados em 27.778 janelas na rodada 1). |

### Regressão nova

Nenhuma além dos dois itens acima.
- Golden 330 e as guardas 353/355/364 estão verdes.
- Sim e arena estão verdes. `test_spec371_eval` (E5 byte-idêntico) está verde.
- `size_budget` cresceu de novo (orquestrador +17, `_resolve_actor_turn_inner` +2). O motivo está no §9 (exceção prevista).

### Comandos rodados (rodada 2)

```text
bash scripts/dev/pt.sh tests/test_spec387_*.py test_objectives test_spec368_seed test_enemy_intent test_spec355_{golpe_reacao,guardas} test_spec353_registry test_spec364_registry_voice test_spec367_{omen_voice,condition_end} test_card_effects_grammar test_spec353_golden_guard test_spec364_golden_guard test_spec371_{eval,pressagio,reacao_inicial} test_spec346_board_no_llm test_spec364_flee_surfaces test_size_budget test_log_event_registry test_card_draft test_scene_cards_node → 375 passed, 1 skipped, 1 xfailed
bash scripts/dev/pt.sh test_card_sim{,_v2} test_spec341_balanco test_spec355_arena test_spec362_{arcanista,run_round} test_spec371_flags_off (--deselect golden 360) → 89 passed, 1 skipped
bash scripts/dev/pt.sh tests/test_spec360_flags_off.py → FAILED test_golden_flags_off_byte_identico (esperado; regravar após R2-P1-1)
dump golden 360 (base 8ff8d674 × 07116abd) → diff só nas mensagens 12, 14, 20 (fallback off)
sonda off_fallback_text com cura + dano contínuo → "Você acerta Goblin." (cura, Cartas e DoT perdidos: R2-P1-1)
ruff check (arquivos .py da rodada) → ok; eslint web/e2e/spec387-omen-390.spec.ts → ok
```

---

## Rodada 3 (commit `1557736e`, diff `e53d525d..1557736e`)

**Veredito da rodada 3: `CHANGES_REQUIRED`.**

### Estado dos achados da rodada 2

| ID | Estado | Evidência |
|---|---|---|
| R2-P2-1 | Resolvido | `_fire_omen_frustrated` é o helper comum de `_frustrate` e `_retract_omen` (`conflict_orchestrator.py:1866-1883`). Teste `test_reaction_kill_fires_ao_pressagio_frustrado_once` (`tests/test_spec387_seed.py:253`): o gatilho dispara 1× no abate por Reação. |
| R2-P1-1 | **Parcial** (ver R3-P1-1 e R3-P2-1) | Cura e dano contínuo agora entram ("Você recupera 3 de Vitalidade com …", "Você sofre 1 de Sangramento."), e "Usa X" seguido de golpe é atribuído ao atacante da linha seguinte. Mas o autor de "Usa X" **sem golpe** é adivinhado pelo nome da Carta ou pela linha seguinte, e erra. |

### Atribuição de "Usa X" pelo nome das Cartas do herói (pergunta do coordenador)

Sondas em `off_fallback_text` (herói "Smoke", Cartas do herói = {Golpe Rachado, Bandagem de Campo, Golpe Básico}):

| Logs | Saída | Problema |
|---|---|---|
| `Usa Pele de Veterano`, `Goblin coordena o próximo ataque de Lobo.` | "**Você usa Pele de Veterano.** Goblin coordena…" | Carta de apoio do **inimigo** atribuída ao herói. A linha seguinte não casa `_SUBJECT_RE` e o padrão é `hero` (`off_text.py:84`). |
| `Usa Pele de Veterano`, `Usa Grito de Guerra`, `Goblin: ganha condição Fúria` | "**` usa Pele de Veterano.`** Goblin usa Grito de Guerra…" | Frase **sem sujeito**: `flush("")` (`off_text.py:61`) quando a Carta pendente não é do herói. |
| `Goblin → Smoke: erro (…)`, `Usa Golpe Básico` | "Goblin erra você. **Você usa Golpe Básico.**" | **Colisão de nome**: Carta de mesmo nome no fim da rodada vai para o herói (`off_text.py:88`). Acontece com básica, neutra ou Carta de mesmo nome que inimigo e herói têm. |

**Conclusão:** o nome da Carta não identifica o ator. Existe fonte robusta no próprio motor: `out["cards_used"]`, lista
ordenada `{actor_id, card_id, …}` (`services/conflict_turn.py:473`; é a mesma que `round_log.round_registry` usa para "X joga
C"). Ela está no escopo das duas chamadas de `_narrate` (`agents/combat.py:2917, 2951`, variável `out`).

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R3-P1-1 | P1 | `services/off_text.py:59-62, 82-84, 88` | O autor de "Usa X" sem golpe é adivinhado: (a) por pertença do **nome** a `hero_card_names` (colide com básicas, neutras e nomes repetidos); (b) pelo sujeito da linha seguinte, com `hero` como **padrão** quando ela não casa. O resultado é atribuir ao herói Cartas do inimigo e gerar "` usa X.`" sem sujeito. É mentira mecânica na superfície do jogador, a mesma família do P1-1. | Atribuir pelo motor, não pelo texto: passar `out.get("cards_used")` e os nomes por id dos atores (`actors_by_id`/`enemies` + herói) a `off_fallback_text`. Cada "Usa X" consome, em ordem, a 1ª entrada ainda não usada cujo `_card_name(card_id) == X`, e o ator é o `actor_id` dela ("Você" para o herói). Sem entrada correspondente, usar frase sem ator ("A Carta X entra em jogo.") e **nunca** usar o herói como padrão. Remover `hero_card_names` se ficar sem uso. Testes: os 3 casos da tabela acima (Carta inimiga de apoio seguida de linha sem sujeito; duas Cartas inimigas seguidas; Carta de mesmo nome do herói usada pelo inimigo) e Carta de apoio do herói sem golpe ("Você usa Bandagem de Campo."). Depois regravar o golden 360. |
| R3-P2-1 | P2 | `services/off_text.py:8` × `services/round_log.py:902` | **Import circular**: `off_text` importa `round_log` no topo e `round_log` reexporta `off_text` no fim. Hoje funciona só porque `agents/combat` importa `round_log` antes. Um import direto em interpretador novo quebra: `bash scripts/dev/py.sh -c "import services.off_text"` → `ImportError: cannot import name 'hero_card_names' from partially initialized module 'services.off_text'`. | Remover a reexportação do fim de `round_log.py` e fazer `agents/combat.py` (e os testes) importar de `services.off_text`. Alternativa: em `off_text`, importar `round_log` dentro das funções. Teste: `subprocess` com `python -c "import services.off_text"` sai com código 0. |
| R3-P3-1 | P3 | `tests/size_budget.json` (`agents/combat.py::_narrate`: 101, entrada **nova**) e `agents/combat.py:1828-1834` | É o 3º rebaseline, e este cria um **ofensor novo**: `_narrate` passa de 100 para 101 só pela chamada formatada em 7 linhas. A exceção do `size_budget` existe para código que a spec manda pôr no god-file, não para formatação evitável. **Não é aceitável; extrair.** | Uma função em `off_text`, por exemplo `for_round(logs, player, out, actors, flavor, victory)`, que monta os argumentos (inclusive os de R3-P1-1). `_narrate` faz 1 chamada de 1–2 linhas e volta a ≤ 100. Retirar a entrada `_narrate` do `size_budget.json` e reverter o +6 de `agents/combat.py`. |

### Goldens 360 / 371

- **360:** comparei de novo as mensagens dos 30 turnos (base `8ff8d674` × `1557736e`). Só mudam as **mensagens 12, 14 e 20**
  (índice 0), todas do fallback `off`. Agora elas incluem "Crescido do Clã usa Punho de Tala." e, na 20, "Você sofre 1 de
  Sangramento.".
- **371:** `test_spec371_flags_off::test_golden_360_inalterado_com_a_flag_off` usa o **mesmo** `_run` e o mesmo arquivo de
  golden. Medi as duas impressões digitais na branch (360 com fauna `off`; 371 com `RPG_FAUNA_SABER=off` também): são
  idênticas, e a única chave diferente do golden é `messages`. Uma regravação conserta os dois testes.
- **Regravação:** é permitida (`SPEC360_REGEN=1`, coordenador; o arquivo não é protegido), mas **só depois de R3-P1-1**. A
  correção pode trocar a atribuição de "Usa Punho de Tala" nessas mensagens (aqui o golpe vem logo depois, então deve ficar
  igual, mas é preciso confirmar). Ao regravar, conferir que o diff continua só nas mensagens 12/14/20.

### Regressão nova

Nenhuma além dos 3 itens acima.
- Golden 330 e as guardas 353/355/364 estão verdes.
- Sim v2 e `test_spec362_run_round` estão verdes.
- `test_spec371_eval` (E5) está verde.
- `_run_round` encolheu 4 linhas, e o rebaseline dele está correto.

### Comandos rodados (rodada 3)

```text
bash scripts/dev/pt.sh tests/test_spec387_*.py test_objectives test_enemy_intent test_spec355_{golpe_reacao,guardas} test_spec353_registry test_spec367_omen_voice test_card_effects_grammar test_spec353_golden_guard test_spec364_golden_guard test_spec371_{eval,pressagio,reacao_inicial} test_spec346_board_no_llm test_size_budget test_log_event_registry test_card_sim_v2 test_spec362_run_round → 343 passed, 2 skipped, 1 xfailed
sondas off_fallback_text (6 casos) → 3 atribuições erradas ou sem sujeito (R3-P1-1); cura e dano contínuo ok
py.sh -c "import services.off_text" → ImportError (circular; R3-P2-1)
dump golden 360 (base × 1557736e) → diff só nas mensagens 12, 14, 20
fingerprint 360 × 371 (FAUNA_SABER=off) na branch → iguais; só `messages` difere do golden
ruff check (off_text, round_log, orchestrator, combat) → ok
```
