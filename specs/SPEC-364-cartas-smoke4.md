# SPEC-364 — Cartas: correções do 4º smoke real (trilha da fuga, consulta do mercado, débito do retrato, tempo do resumo, voz do registro e cenários não verificados)

> **Status:** `in-progress` (implementada nas Etapas 0-6; faltam revisão `Sol` e smoke §6; era `approved`, coordenador, autorização do dono 02/11 "manda bala"; D-364-1..5 aceitas)
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Épico:** SPEC-327
> **Origem:** smoke 4 real de 02/11 (`main` `cc31a6c1`, staging `hosted-supabase` + local `legacy`, DeepSeek `deepseek-v4-flash`, 15 turnos + 2 gerações de retrato) — [docs/spec364/achados-smoke4.md](../docs/spec364/achados-smoke4.md). Evidência bruta no scratchpad do coordenador (`scratchpad/smoke4/`: `stg/stg_log.jsonl`, `stg/stg_hist_A.json`, `out/state-*.json`, `out/hist-*.json`, `out/*.png`, `server.log`, `turns.cjs`).
> **Depende de:** código das SPEC-352 e SPEC-363 na `main` (ambas pousadas, `in-progress` só pelo §6; o smoke 4 é o §6 da 363).
> **Desbloqueia:** fechar o §6 da SPEC-363 e o da SPEC-352 (com o critério de débito corrigido por D-364-1); smoke de liberação das flags de cartas.
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (texto de efeito pago, intenção de transação com ouro, validação do resumo)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected de eval, baseline ou dataset de regressão muda. O golden da SPEC-330 fica byte a byte (R27).

Rótulos: **[F]** fato no source (worktree `rpg-spec-364`, `main` em `cb02071d`) · **[H]** hipótese com evidência, que a Etapa 0 ou o 1º teste confirma ou derruba · **[D]** decisão (§8).

---

## 1. Contexto & Objetivo

O 4º smoke confirmou o que a SPEC-363 prometia nos pontos centrais: retrato pago cotado, confirmado, gerado e
reaproveitado por outra conta sem cobrança; 0 chamada de LLM nas rodadas de meio de luta (p50 144 ms local,
0,7–1,2 s no staging); veredito da fuga igual nas três superfícies; compra pela frase natural; `/game/history`
sem id. Sobraram **2 P2 e 5 P3** e três itens **não verificados**, porque o jogo real não sorteou o cenário
(morte com nome contendo dígito, inimigo escondido na tela local, 409 que tira só a jogada).

O objetivo é **zerar a pendência do smoke 4**: corrigir todos os P2/P3, provar por teste determinístico
(TestClient com estado semeado + Playwright) cada cenário não verificado, e deixar o §6 curto (≤ 10 turnos)
e focado só nos achados. Princípios mantidos: **mecânica é Python**; **nenhuma chamada de LLM por rodada**
(a IA só abre o tabuleiro e resume o fim); o resumo final recebe fatos estruturados e passa por validação
determinística com fallback; **dinheiro: o texto mostrado ao jogador descreve o que o motor de cobrança faz**;
golden da SPEC-330 intocado; nenhuma flag nova.

### 1.1 Achados e causa no source

| # | Achado (prioridade) | Evidência do smoke | Causa no source |
|---|---|---|---|
| 1 | Trilha da fuga diverge: `mech_log` "avança (alcancado → afastado)", Livro "Você avança na fuga: pressionado → afastado"; id sem acento no `mech_log` (P2-1) | `out/state-Mirela4-f1.json`, `f2.json`, `out/7135206-Mirela4-f2-1440-2-pos.png` | **[F]** O `de` do `out["fuga"]` vem de `_prev_track`, lido do `combat_meta["chase"]` **antes** de `_attempt_flee` (`agents/combat.py:2498`, gravado em `:2526`). Depois de uma fuga "alcançado", `chase.can_resume` recusa o snapshot terminal (`services/chase.py:111-112`) e `_attempt_flee` reinicia a perseguição por `start_chase` (`agents/combat.py:3378-3382`, trilha inicial pela distância, `chase.py:69-71,89-90`); o Livro usa o `previous_track` **depois** do reinício (`agents/combat.py:3383,3423-3431`). Duas fontes para o mesmo "de". O rótulo cru: `TRACK_LABEL` não tem `alcancado` (`chase.py:30`) e `track_label` devolve o id quando não acha (`chase.py:33-35`); `_flee_line` imprime o rótulo (`services/combat_preview.py:331-333`). O mesmo bug existe na 1ª fuga da luta quando a distância é `distante`: `_prev_track` cai no default `"pressionado"` (`agents/combat.py:2498`) e a perseguição começa em `afastado` |
| 2 | "O que a Forja dos Clãs tem à venda?" respondeu "Você não tem 'Forja dos Clãs' para vender." (P2-2) | `out/state-Haldor4-t2.json` | **[F]** `_parse_trade_intent` decide o modo por regex antes de tudo, e `venda` casa `sell` (`agents/loot.py:150-161`); a consulta `observe` só é tentada **sem** modo explícito (`:162-171`); com `sell` explícito e item não resolvido, o CLASSIFY roda e o modo `sell` é imposto ao resultado (`:176-195`); a venda falha por item ausente e a recusa vira a mensagem. O fluxo de Cartas já trata pergunta como "só preço" (`agents/loot.py:422-423`); o de itens não |
| 3 | Débito de 8 milli contra cotação de 15 milli nas 2 gerações; o chip diz "1 Estilhas" (P3-1) | `stg_log` `portrait_ready` (`debit_milli: 8`, `quoted_milli: 15`) | **[F]** A cotação é um **teto**: `credits_milli = quote_attempt_ceiling(max_provider_usd, …)` (`services/image_quotes.py:84-99`), reservado como `ceiling_milli` (`:243-253`). A liquidação cobra o uso **exato** e libera o resto (`infrastructure/wallet.py:696-707`, docstring "Atomically settle exact, persisted usage and release the remainder"). A SPEC-352 já previa isso ("O débito fica liquidado ≤ teto", `specs/SPEC-352-retrato-inimigo-pago.md:356,366`; D-352-8 "a copy diz 'até N Estilhas', porque o débito é limitado ao teto e pode sair menor", `:388`). Logo o critério "débito igual à cotação" do §6.1 da 363 está errado, não o motor. Mas a copy do botão não cumpre a D-352-8: "Gerar retrato (N Estilhas)" sem "até" e com plural fixo (`web/src/combat/TargetChip.tsx:48`); o preço é `ceil(teto/1000)` inteiro (`services/creature_art.py:238`; SPEC-352 `:100,412`), então 15 milli vira "1" |
| 4 | Resumo da vitória: "o Goblin também tomba sem vida ao seu lado", com o Goblin morto na rodada 3 e a vitória na 5 (P3-2) | `stg_log` `A_end.message` | **[F]** A separação entre quedas da rodada final e quedas anteriores existe só no fallback (`services/round_log.py:713-730`, SPEC-363 R9). Os fatos dados ao LLM listam `mortos`/`caidos` do conflito inteiro sem marca de tempo (`round_log.py:589-599`); o prompt não fala de tempo (`agents/combat.py:2010-2023`); `validate_attribution` não tem regra temporal (`services/conflict_summary.py:506-536`) |
| 5 | Registro com o nome do herói ("Smoke4A sente o Abismo mais perto (+1 Carga).", "Mirela4: ganha condição cego") e linha de condição duplicada ("Goblin ganha a condição Cego." + "Goblin: ganha condição cego") (P3-3) | `stg_log` A-r3, `out/hist-Mirela4.json`, `out/state-Mirela4-*.json` | **[F]** As Cartas de Cena escrevem em `out["logs"]` com o nome do ator (`services/scene_cards.py:443-461`) e o orquestrador **copia** essas linhas cruas para `out["scene_logs"]` (`services/conflict_orchestrator.py:2600,2943`). `round_registry` normaliza `out["logs"]` por `_voce` (`round_log.py:344-348`), mas acrescenta `scene_logs` crus (`:372`) e o dedupe é por string exata (`:375-381`): a mesma condição aparece normalizada e crua, e a linha de Carga sai com o nome |
| 6 | Consulta do mercado com a descrição inteira como nome ("Faca de esfolar de osso de baleia, cabo envolto em couro cru — a lâmina que Haldor usa…" a 30 moedas, estoque 0) e itens do herói listados como se fossem do mercador (P3-4) | `out/state-Haldor4-t3.json` | **[F]** Itens livres guardam o texto da criação inteiro em `display_name` (`inventory.py:64-77,175`); `public_market_snapshot` acrescenta os itens do inventário com `stock: 0` e preço de **compra** (`services/economy.py:636-660`); a consulta imprime tudo numa lista só, "compra / venda (estoque N)" (`agents/loot.py:500-512`) |
| 7 | Narração da compra: "O mercador de Valoria embolsa…" em vez da Forja dos Clãs (P3-5) | `out/state-Haldor4-t1.json` | **[F]** O contexto do narrador na compra de Carta é só `"BUY: Carta {name}, ouro −N, ouro final M"` (`agents/loot.py:454-457`), e na de item `"{MODE}: {qty}x {item}, ouro …"` (`:579-587`); nenhum dos dois leva o nome do mercador nem do local, e o LLM inventa |
| 8 | **Não verificado:** texto de morte com nome contendo dígito no staging (a conta venceu) | `A_end` | Coberto por unidade na 363 (`tests/test_spec363_outcome_text.py`), sem teste ponta a ponta pela API (Livro, `death_context`, crônica, registro) |
| 9 | **Não verificado:** inimigo escondido na tela local (o esconderijo não se repetiu) | `out/state-Mirela4-r2.json` | **[F]** O servidor já manda `valid_targets` por Carta da mão (363 R19) e o front exclui o escondido no fallback (`web/src/combat/deck.ts:182-184`; motivo em `web/src/workspace/tabs/CombateTab.tsx:138`); nenhum e2e monta um inimigo `escondido` |
| 10 | **Não verificado:** 409 que tira só a jogada (nenhum 409 no smoke) | n/a | **[F]** O servidor devolve `play_index`/`card_id` (`api.py:6002-6020`), repassado pelo SSE (`api.py:7065-7072`); o único e2e simula a resposta com `page.route` e `play_index: 0` (`web/e2e/spec363-board.spec.ts:56-80`), o que não distingue "tira a jogada certa" de "tira a primeira" |

Observação sem requisito: no staging, "Estilhaçar (Veio de Éter Bruto)" mirou um Goblin que já tinha caído na
mesma rodada e o texto disse "já está fora do conflito". É o comportamento correto do motor (o alvo some antes
da jogada resolver); redirecionar jogadas da fila fica fora de escopo.

## 2. Requisitos

Todos com as flags de cartas `on` (`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_SCENE_CARDS`, `RPG_ENEMY_DECKS`,
`RPG_CARD_REWARDS`, `RPG_COMBAT_NONLETHAL`), salvo indicação. Em `off`, o fluxo fica como hoje.

### A. Fuga com uma trilha só (achado 1, P2-1)

- **R1 — `de` vem de dentro da perseguição.** `_attempt_flee` grava em `chase_state["_last"]["de"]` a trilha do
  início da rodada **depois** de retomar ou reiniciar a perseguição (`previous_track`, `agents/combat.py:3383`),
  inclusive no caminho `force_escape`. `out["fuga"]["de"]` passa a ler `_last["de"]`; o `_prev_track` de
  `combat_meta` (`:2498`) só vale como fallback de save antigo. `FleeDecision` continua com 3 campos (o unpack
  legado `hero_fled, flee_logs, chase_state = …` em `:2499` não muda).
- **R2 — Mesma trilha em todas as superfícies.** Para uma fuga, `mech_log`, registro da rodada, `round_board`,
  mensagem do turno e `/game/history` mostram o mesmo par `de → para`. Casos obrigatórios: (a) 2 fugas
  seguidas, a 1ª "alcançado" e a 2ª "avança" (reprodução do smoke); (b) 1ª fuga da luta com o herói `distante`
  (começa em `afastado`); (c) perder terreno; (d) escapar; (e) sacrifício aceito (`force_escape`).
- **R3 — Nenhum id da trilha na tela.** `chase.TRACK_LABEL` cobre todos os estados que podem ser exibidos,
  incluindo `alcancado` → "alcançado"; `track_label` de valor desconhecido devolve "" (a linha omite o
  parêntese) em vez do id. Invariante: `\b(alcancado|quase_livre)\b` não aparece em `mech_log`, registro,
  `round_board`, mensagem nem `/game/history`.

### B. Mercado (achados 2, 6 e 7; P2-2, P3-4, P3-5)

- **R4 — Pergunta de catálogo vira consulta.** Em `loot_source == "SHOP"`, antes do regex de modo, uma
  pergunta de catálogo devolve `TradeIntent(mode="observe")` sem CLASSIFY e sem transação. Pergunta de catálogo
  = texto dobrado com marcador de catálogo (`a venda`, `para vender`/`pra vender`, `tem para vender`, `vende`,
  `vendem`, `esta(o) vendendo`, `o que (voce|voces|ele|ela|a <x>|o <x>) tem`, `mercadorias`) **e** nenhum item do
  inventário do herói citado (`find_entry_in_inventory`). Positivos obrigatórios: "O que a Forja dos Clãs tem à
  venda?", "O que vocês vendem?", "Tem algo à venda aqui?", "O que tem pra vender?", "Quais mercadorias você
  tem?". A resposta nunca contém "para vender" nem "Você não tem".
- **R5 — Venda explícita continua venda.** "Vendo a Tocha", "Quero vender a Tocha" e "Vender a tocha por favor"
  (Tocha no inventário) seguem em `sell` e transacionam como hoje.
- **R6 — Pergunta nunca transaciona item [D-364-3].** No fluxo de itens (`SHOP`), texto com `?` ou aberto por
  interrogativo (`o que`, `quanto`, `qual`, `quais`, `posso`, `tem`, `voces tem`, `me vende`) **nunca** executa
  `execute_trade`: com item resolvido, responde a cotação dele ("[SISTEMA] Tocha: o mercador paga N moedas.
  Diga claramente que vende para confirmar; nada mudou."); sem item, a consulta de R7. Nenhum delta de ouro,
  inventário ou estoque (mesma regra que as Cartas já seguem, `agents/loot.py:422-437`).
- **R7 — Consulta separa o que o mercador vende do que ele paga.** O texto da consulta tem duas seções: "À
  venda" (só `stock > 0`: nome, preço de compra, estoque) e "Pelo que você carrega" (itens do herói: nome e
  preço de **venda**, sem estoque e sem preço de compra). Item do herói nunca aparece com "estoque 0".
  `public_market_snapshot` ganha o campo aditivo `source ∈ {"merchant", "player"}` por cotação; os campos de hoje
  não mudam (playtest e testes que leem `quotes` continuam).
- **R8 — Nome curto na exibição [D-364-4].** `inventory.short_display(entry, limit=40)`: corta o `display_name`
  no primeiro `" — "`, `" – "`, `","`, `";"` ou `" ("`, depois limita a 40 caracteres na fronteira de palavra e
  acrescenta "…" se cortou. Usado na consulta (R7) e nas linhas `[SISTEMA]` de compra/venda de item livre. O
  `display_name` salvo **não** muda (resolução por nome, venda e saves continuam pelo texto inteiro). Exemplo
  real: "Faca de esfolar de osso de baleia, cabo envolto em couro cru — a lâmina que Haldor usa…" → "Faca de
  esfolar de osso de baleia".
- **R9 — A narração da compra nomeia o mercador.** O contexto de `_narrate` em compra/venda (Carta, `:454-457`, e
  item, `:579-587`) inclui `Mercador: <merchant_name> (<local>)` e a instrução "chame o mercador por esse nome;
  não invente outro"; o texto de fallback passa a ser "<merchant_name> fecha o negócio sem cerimônia."
  `merchant_name` vem de `economy.MERCHANTS[card_shop.shelf(...)[0]]` (Cartas) ou de
  `market_before["merchant_name"]` (itens); sem mercador, como hoje.

### C. Resumo final no tempo certo (achado 4, P3-2)

- **R10 — Fatos com tempo.** `outcome_facts` usa a mesma partição de `deterministic_outcome_text`
  (`round_log.py:713-730`): quedas da rodada final saem como "Na rodada final, <nomes> <verbo>." e as anteriores
  como "Antes do fim, <nomes> já tinha(m) <particípio>." (`morreu` → "já tinha morrido", `caiu` → "já tinha
  caído", `perdeu os sentidos` → "já tinha perdido os sentidos"). Sem `last_out` (save antigo), como hoje. O
  `ConflictSummary` persistido não muda.
- **R11 — Prompt pede o passado.** O prompt do resumo (`agents/combat.py:2010-2023`) acrescenta: "Quem caiu
  antes do fim já estava caído: conte no passado (já tinha tombado), nunca como se tombasse agora."
- **R12 — Validação V6: queda antiga no presente.** `round_log.authorship` passa a devolver
  `earlier_fallen` (nomes de R10). `validate_attribution` ganha V6: oração (separada por `.;!?` e vírgula) que
  cita um nome de `earlier_fallen` **e** um verbo de queda no presente (`_FALL_RE`: tomba, cai, morre, desaba,
  sucumbe, desmorona) **sem** marca de passado (`ja`, `antes`, `tinha`, `havia`, `caira`, `tombara`, `caido`,
  `tombado`, `morto`, `jaz`, `jazia`) → violação → fallback, com `last_outcome_source = "fallback_attribution"`.
  O texto real do staging é rejeitado; "o Goblin, que já tinha tombado, jaz ao seu lado" é aceito; um corpus de
  ≥ 10 frases benignas (queda da rodada final no presente, inimigo vivo que "cai de joelhos" sem estar em
  `earlier_fallen`, etc.) não dispara.
- **R13 — Oráculo com o texto real.** `tests/fixtures/spec364_smoke.py` guarda o resumo real do staging (A_end,
  sem segredos), os fatos que o geraram e um texto correto escrito à mão; o real falha em V6, o correto passa.

### D. Registro na voz do jogador (achado 5, P3-3)

- **R14 — Cartas de Cena pela mesma normalização.** Em `round_registry`, as linhas de `scene_logs` passam por
  `_voce(line, hero_name)` antes do dedupe (`round_log.py:372-381`). "Smoke4A sente o Abismo mais perto (+1
  Carga)." → "Você sente o Abismo mais perto (+1 Carga)."; "Mirela4: ganha condição cego" → "Você ganha a
  condição Cego.". Nenhuma mudança em `scene_cards.py` nem no orquestrador (R27).
- **R15 — Uma linha por evento de condição.** O dedupe do registro compara a forma normalizada: "Goblin ganha a
  condição Cego." e "Goblin: ganha condição cego" viram **uma** linha. Vale para `mech_log` e `round_board` se a
  Etapa 0 achar o mesmo par lá.
- **R16 — Invariante de voz.** Com herói "Smoke4A" e "Mirela4": nenhuma linha de registro, `mech_log`,
  `round_board`, mensagem do turno ou `/game/history` de uma luta com Carta de Cena de Carga e de condição começa
  com o nome do herói nem contém "<nome>:". (Nome próprio do herói só em crônica e arquivista, D-363-3.)

### E. Retrato pago: débito e texto honestos (achado 3, P3-1)

- **R17 — Débito = custo liquidado ≤ teto [D-364-1].** O motor de cobrança fica como está. Teste de integração do
  repositório (store em memória ou Postgres de teste, como os da 352): cotação com teto T, confirmação reserva T,
  liquidação com uso U < T → débito U, reserva liberada (0 reservado), saldo final = inicial − U; U > T é recusado
  como hoje. O critério de aceite do §6 passa a ser "débito = custo liquidado ≤ cotação, e a reserva volta a 0"
  (substitui o "débito igual à cotação" do §6.1 da SPEC-363).
- **R18 — Preço exibido = teto exato, com "até" [D-364-2].** A oferta ganha o campo aditivo
  `retrato.gerar.preco_milli` (o teto em milli de `peek_ceiling`, `services/creature_art.py:238`);
  `preco_estilhas` (inteiro) continua para cliente antigo. O chip mostra "Gerar retrato (até X)" e a confirmação
  inline "por até X?", com X = `shards(preco_milli)` + rótulo de R19 (ex.: "até 0,015 Estilhas"). Sem
  `preco_milli`, usa `preco_estilhas` como hoje, com "até".
- **R19 — Plural certo.** Helper único `estilhasLabel(milli)` no front: "1 Estilha" só quando o valor é exatamente
  1000 milli; qualquer outro valor (inclusive frações) "N Estilhas". Aplicado em `TargetChip.tsx:48,54`,
  `ImageQuoteDialog.tsx:25,34`, `CombateTab.tsx` (mensagem com `price`, `:219`) e nos textos de saldo/consumo de
  `AccountScreen.tsx` e `StoryLog.tsx:166`.
- **R20 — Atalho de confirmação em milli.** A confirmação direta (sem o diálogo da 326) passa a valer quando
  `BigInt(quote.credits_milli) <= BigInt(preco_milli)`; sem `preco_milli`, a regra de hoje
  (`<= preco_estilhas*1000`, SPEC-352 `:412`).

### F. Cenários não verificados provados por teste (achados 8–10)

- **R21 — Morte com nome com dígito, ponta a ponta.** Teste de API `legacy` (TestClient, MockLLM, estado semeado
  com herói "Smoke4A" à beira da morte e 2 inimigos, um caído em rodada anterior), em dois caminhos: (a) resumo do
  LLM aceito (Mock devolve texto válido) e (b) fallback forçado (Mock devolve texto que viola V6/V4).
  Asserções: mensagem do turno, registro, `mech_log`, `death_context`, crônica e `/game/history` nunca contêm
  "SmokeA" (nome mutilado); o texto ao jogador usa "Você"; onde o nome aparece (crônica), aparece "Smoke4A"
  íntegro; `killer` = autor do golpe final; queda antiga no passado (R10).
- **R22 — Inimigo escondido na tela.** Playwright (`web/e2e/spec364-hidden-target.spec.ts`, 1440 e 390) com
  estado semeado: 2 inimigos, um `concealment: "escondido"`, mão com Carta básica (`bas_*`). (a) Com
  `valid_targets` do servidor: o chip do escondido não arma a jogada e mostra "escondido — fora de alcance"; o
  visível arma. (b) Sem `valid_targets` (fallback 363 R20): mesmo resultado. Contrato anti-deriva:
  `tests/test_spec364_hidden_view_contract.py` monta o mesmo estado no motor, gera a view pela API e afirma que
  os campos usados pela fixture do e2e (`concealment`, `pilhas.mao[*].valid_targets/invalid_reason`) têm a forma
  e os valores que a fixture usa.
- **R23 — 409 tira só a jogada, ponta a ponta.** (a) API (TestClient): 3 jogadas, a de índice **1** mira o
  escondido → `409` com `detail.play_index == 1` e `card_id` dela, tanto em `/game/action` quanto em
  `/game/action/stream` (evento `error` com o mesmo `detail`); estado salvo idêntico ao de antes (Fôlego,
  `pilhas`, rodada, `mech_log`, save). (b) Playwright: variante do e2e da 363 com `play_index: 1` → a fila fica
  com as jogadas 0 e 2, e o aviso cita a Carta 1.

### G. Transversais

- **R24 — Sem LLM por rodada continua.** `tests/test_spec346_board_no_llm.py` ganha o caso de 2 fugas seguidas
  (alcançado → avança) com Carta de Cena de condição: 0 chamadas a `get_llm`.
- **R25 — Menos LLM, não mais.** R4/R6 resolvem por regex antes do CLASSIFY (o número de chamadas de LLM na loja
  só cai); nenhum `with_structured_output` novo; guard de FallbackLLM mantido no resumo e no loot.
- **R26 — Sem flag nova.** Nada novo em `config/flags.yaml`.
- **R27 — Golden da 330 intocado.** `git diff main -- tests/spec330_equivalence.py
  tests/fixtures/spec330_legacy_golden.json` vazio; nenhuma mudança em `services/conflict_orchestrator.py`,
  `services/scene_cards.py` nem em `ct.resolve_turn`. R1 mexe só em `agents/combat.py` (borda do agente) e
  `services/chase.py` (rótulo).
- **R28 — Contrato aditivo e saves.** `chase._last.de`, `quotes[*].source` e `retrato.gerar.preco_milli` são
  opcionais; save e cliente sem eles funcionam. `web/src/types.ts` acompanha; `npm run typecheck`, `lint` e
  `test` verdes.
- **R29 — Invariante de ids e voz estendido.** `tests/test_spec363_ids.py::test_no_internal_ids_in_history` passa a
  incluir 2 fugas seguidas, Carta de Cena de Carga e a consulta do mercado com item livre longo; o padrão ganha
  `alcancado`/`quase_livre` (R3) e a regra de R16.

### Fora de escopo

- Redirecionar uma jogada da fila cujo alvo caiu antes na mesma rodada (observação do §1.1; o texto atual é
  correto).
- Renomear itens livres no save, no inventário ou na ficha (R8 é só exibição no mercado e nas linhas da loja).
- Mudar preço, perfil de preço, câmbio ou regra de liquidação do retrato; mudar o teto diário do staging
  (D-363-2).
- Reescrever o resumo do LLM em vez de rejeitar (V6 continua "rejeita → fallback").
- Crítico por dupla (D-363-1) e qualquer número de Carta.
- Latência de viagem (363 R35/§6.6): não é achado do smoke 4.
- Corrigir o texto do §6.1 da SPEC-363 (o coordenador faz no fechamento dela, com a referência a D-364-1).

## 3. Design técnico

### 3.1 Arquivos novos

- `tests/test_spec364_flee_trail.py` (R1–R3, R24 parcial), `tests/test_spec364_market.py` (R4–R9),
  `tests/test_spec364_outcome_tense.py` (R10–R13), `tests/test_spec364_registry_voice.py` (R14–R16),
  `tests/test_spec364_portrait_debit.py` (R17), `tests/test_spec364_death_digit_name.py` (R21),
  `tests/test_spec364_hidden_view_contract.py` (R22), `tests/test_spec364_409_play_index.py` (R23a),
  `tests/test_spec364_golden_guard.py` (R27).
- `tests/fixtures/spec364_smoke.py` — resumo real do staging + fatos + texto correto (R13).
- Front: `web/tests/spec364-estilhas.test.mjs` (R18–R20), `web/e2e/spec364-hidden-target.spec.ts` (R22),
  `web/e2e/spec364-409.spec.ts` (R23b).

### 3.2 Arquivos alterados

- `agents/combat.py` — `_attempt_flee` grava `_last["de"]` (R1); `out["fuga"]["de"]` lê dele (R1); prompt do
  resumo (R11).
- `services/chase.py` — `TRACK_LABEL` com `alcancado`; `track_label` sem id cru (R3).
- `services/combat_preview.py` — `_flee_line` omite o parêntese quando o rótulo é vazio (R3); dedupe de condição
  se a Etapa 0 achar duplicata no `mech_log` (R15).
- `agents/loot.py` — detector de pergunta de catálogo e de pergunta em geral antes do modo (R4, R6); consulta em
  duas seções com nome curto (R7, R8); contexto e fallback do narrador com o mercador (R9).
- `services/economy.py` — `quotes[*].source` (R7).
- `inventory.py` — `short_display(entry, limit=40)` (R8).
- `services/round_log.py` — `outcome_facts` com tempo (R10); `authorship` com `earlier_fallen` (R12);
  `round_registry` normaliza `scene_logs` e deduplica pela forma normalizada (R14, R15).
- `services/conflict_summary.py` — V6 (R12).
- `services/creature_art.py` / `api.py` (onde `gerar` é montado) — `preco_milli` (R18).
- Front: `web/src/combat/TargetChip.tsx` (R18, R19), `web/src/components/ImageQuoteDialog.tsx`,
  `web/src/workspace/tabs/CombateTab.tsx` (R19, R20), `web/src/components/AccountScreen.tsx` (helper
  `estilhasLabel` ao lado de `shards`, `:11-16`), `web/src/components/StoryLog.tsx` (R19), `web/src/types.ts`
  (R28).

### 3.3 Formatos

`chase._last` e `out["fuga"]` depois de R1 (2ª fuga do smoke):

```json
{"_last": {"total": 18, "difficulty": 12, "sucesso": true, "advantage": 0, "de": "pressionado"}}
{"total": 18, "dificuldade": 12, "sucesso": true, "veredito": "avancou", "de": "pressionado", "para": "afastado"}
```

```
Fuga · total 18 vs 12 · avança (pressionado → afastado)
Você avança na fuga: pressionado → afastado.
```

Consulta do mercado (R7, R8):

```
[SISTEMA] Mercado da Forja dos Clãs (consulta sem transação):
À venda:
- Corda: 8 moedas (estoque 3)
- <linhas de Cartas como hoje, `card_shop.observe_lines`>
Pelo que você carrega:
- Faca de esfolar de osso de baleia: paga 15 moedas
```

Fatos do resumo (R10, vitória da conta A):

```
Desfecho: vitória.
Na rodada final, Minotauro Esqueleto morreu.
Antes do fim, Goblin já tinha morrido.
...
```

Oferta do retrato (R18):

```json
{"gerar": {"preco_estilhas": 1, "preco_milli": "15", "escopo": "tipo"}}
```

Chip: `Gerar retrato (até 0,015 Estilhas)`. `preco_milli` segue o tipo dos outros campos milli da API (string
de inteiro, como `credits_milli`); a Etapa 4 confere e, se a view já usa número, segue o que existe.

## 4. Plano passo a passo

Cada etapa: testes primeiro → código → só os testes do escopo (`-n 2` no máximo). Suíte completa só no pouso,
pelo coordenador. Toda etapa que toca `round_log`/`agents/combat.py` roda também
`tests/test_card_effects_grammar.py`, `tests/test_spec363_*.py` e `test_spec364_golden_guard.py`.

### Etapa 0 — Confirmação (sem código de produto)

1. **Achado 1:** escrever primeiro `test_two_flees_same_trail` (Etapa 1) e ver falhar com
   `de == "alcancado"`; confirmar que o caso `distante` também falha.
2. **Achado 5:** confirmar se `mech_log`/`round_board` também duplicam a linha de condição da Carta de Cena (R15)
   ou se a duplicata é só no registro.
3. **Achado 3:** localizar onde `gerar` é montado (`creature_art.portrait_for` ou `api._enemy_portrait`) e o tipo
   usado para milli na view.
4. Anotar em §9.

### Etapa 1 — Fuga (R1–R3)

1. **Testes** (`tests/test_spec364_flee_trail.py`): `test_two_flees_same_trail` (1ª alcançado, 2ª avança:
   `out["fuga"]["de"] == "pressionado"` e a mesma string em `mech_log`, registro e mensagem);
   `test_first_flee_from_distant_starts_afastado`; `test_lose_ground_and_escape_trails`;
   `test_force_escape_trail`; `test_no_track_ids_anywhere` (R3, regex sobre as 5 superfícies);
   `test_track_label_never_returns_id`.
2. **Implementação:** `agents/combat.py` (`_attempt_flee`, montagem de `flee_roll`), `services/chase.py`,
   `services/combat_preview.py::_flee_line`.

### Etapa 2 — Mercado (R4–R9)

1. **Testes** (`tests/test_spec364_market.py`): `test_catalog_questions_observe` (5 positivos de R4, sem
   chamada a `get_llm`, sem delta); `test_explicit_sell_still_sells` (R5); `test_question_never_trades_item`
   ("Posso vender a Tocha?", "Me vende a Corda?", "Quanto vale a Tocha?": cotação, sem delta);
   `test_market_two_sections` (item do herói só em "Pelo que você carrega", sem "estoque 0");
   `test_short_display` (exemplo real + nome curto intacto + corte na palavra + save intacto);
   `test_buy_narration_names_merchant` (Carta e item: o contexto capturado do LLM simulado contém o nome do
   mercador; fallback com o nome).
2. **Implementação:** `agents/loot.py`, `services/economy.py`, `inventory.py`.

### Etapa 3 — Resumo e registro (R10–R16)

1. **Testes:** `tests/test_spec364_outcome_tense.py` — `test_facts_split_final_and_earlier`,
   `test_facts_old_save_unchanged`, `test_prompt_mentions_past`, `test_v6_rejects_staging_text` (fixture R13),
   `test_v6_accepts_correct_text`, `test_v6_benign_corpus`, `test_v6_sets_fallback_attribution_source`;
   `tests/test_spec364_registry_voice.py` — `test_scene_charge_line_uses_voce`,
   `test_scene_condition_line_once`, `test_no_hero_name_in_player_surfaces` (Smoke4A e Mirela4).
2. **Implementação:** `services/round_log.py`, `services/conflict_summary.py`, prompt em `agents/combat.py`.

### Etapa 4 — Retrato pago (R17–R20)

1. **Testes:** `tests/test_spec364_portrait_debit.py` — `test_settle_below_ceiling_releases_remainder`,
   `test_settle_above_ceiling_capped`, `test_offer_has_preco_milli`; front
   `web/tests/spec364-estilhas.test.mjs` — `estilhasLabel` (1000 → "1 Estilha"; 15 → "0,015 Estilhas"; 2000 →
   "2 Estilhas"), chip com "até", confirmação direta por milli e fallback por `preco_estilhas`.
2. **Implementação:** `services/creature_art.py`/`api.py`, `TargetChip.tsx`, `ImageQuoteDialog.tsx`,
   `CombateTab.tsx`, `AccountScreen.tsx`, `StoryLog.tsx`, `types.ts`.

### Etapa 5 — Cenários não verificados (R21–R23)

1. **Testes:** `tests/test_spec364_death_digit_name.py` (R21, caminhos LLM e fallback);
   `tests/test_spec364_hidden_view_contract.py` + `web/e2e/spec364-hidden-target.spec.ts` (R22, 1440 e 390,
   `--workers=1`); `tests/test_spec364_409_play_index.py` (R23a, JSON e SSE, estado intacto) +
   `web/e2e/spec364-409.spec.ts` (R23b).
2. **Implementação:** só fixtures/seams de teste. Se um cenário revelar bug, corrigir nesta etapa e registrar
   em §9.

### Etapa 6 — Guardas e não-regressão (R24–R29)

1. `test_spec364_golden_guard.py` (R27); extensão de `test_spec346_board_no_llm.py` (R24) e de
   `test_spec363_ids.py` (R29).
2. Testes antigos que codificavam o comportamento antigo são atualizados **só** no expected afetado, cada um
   listado em §9 com o motivo (esperados: linhas de consulta do mercado em `test_merchant_profile.py`/
   `test_spec363_ids.py` se fixavam a lista única; fatos do resumo em `test_spec363_outcome_text.py` se fixavam
   "X morreu." sem tempo; copy do chip em `web/tests/spec347-*`/`spec352-*`).
3. Front `typecheck`/`lint`/`test` (R28). Arena não é necessária: nenhuma mudança de motor (R27).

## 5. Critérios de aceite

- [ ] Etapa 0 anotada em §9
- [ ] Fuga: mesma trilha `de → para` nas 5 superfícies nos 5 casos de R2; nenhum id da trilha (R1–R3)
- [ ] Mercado: perguntas de catálogo viram consulta sem LLM e sem transação; venda explícita intacta; pergunta
      nunca transaciona item; consulta em duas seções com nome curto; narração com o nome do mercador (R4–R9)
- [ ] Resumo: fatos com tempo; V6 rejeita o texto real e aceita o correto; corpus benigno sem disparo (R10–R13)
- [ ] Registro: Cartas de Cena na voz do jogador; uma linha por condição; invariante de voz verde (R14–R16)
- [ ] Retrato: débito = liquidado ≤ teto com reserva liberada; chip "até X" com plural certo; atalho em milli
      (R17–R20)
- [ ] R21, R22 (1440 e 390) e R23 (JSON, SSE e e2e com `play_index: 1`) verdes
- [ ] 0 LLM por rodada (R24); golden da 330 sem diff (R27); sem flag nova (R26); contrato aditivo e saves (R28)
- [ ] Guard de FallbackLLM mantido; nenhum `with_structured_output` novo (R25)
- [ ] `uv run pytest` verde (suíte completa, coordenador, no pouso); `npm run typecheck`, `lint`, `test` verdes
- [ ] Revisão independente `Sol` sem P0/P1 aberto
- [ ] **Smoke real §6 (coordenador)** executado e registrado em `docs/spec364/smoke-final.md`

## 6. Smoke test com LLM real (≤ 10 turnos; só os achados)

Local `legacy` (preset de `scripts/staging/staging_flags.json`, cartas `on`, `RPG_CREATURE_ART=on`) e staging
(`hosted-supabase`, conta sintética pelo caminho de `two_user_smoke`, limpeza no fim). DeepSeek primário.
Registrar em `docs/spec364/smoke-final.md` (trechos, sem segredos), com provider/modelo, chamadas e custo.

1. **Local, loja (3 turnos):** "O que a Forja dos Clãs tem à venda?" → consulta em duas seções, nomes curtos,
   sem "para vender" e sem CLASSIFY no log (R4, R7, R8); "Posso vender a <item do herói>?" → cotação, ouro e
   inventário iguais (R6); "Quero comprar a <Carta> da Forja dos Clãs" → compra e narração cita a Forja dos Clãs
   (R9).
2. **Local, combate (abertura + até 4 rodadas):** fugir até ser alcançado e fugir de novo → `mech_log`,
   registro, mensagem e `/game/history` com a mesma trilha e sem `alcancado` (R1–R3); conferir que nenhuma linha
   do registro começa com o nome do herói e que não há condição duplicada (R14–R16). Se a luta terminar em vitória
   com uma queda anterior, o resumo não conta a queda antiga no presente (R10–R12); anotar `last_outcome_source`.
3. **Staging, retrato (1 turno + 1 geração):** `scripts/staging/art_preflight.py` → `ok` (fora o
   `dynamic_art_env_off` do arquivo); chip "Gerar retrato (até X Estilhas)" a 390 e 1440 (R18, R19); confirmar →
   `pronto`; débito = custo liquidado ≤ cotação e 0 reservado no fim (R17). Desligar `image_generation` no fim,
   como no smoke 4.
4. Varredura de ids e do nome do herói no `/game/history` das campanhas (R29).

Os três itens "não verificados" do smoke 4 não entram no §6: R21–R23 os provam por teste.

## 7. Riscos & compatibilidade

- **R4/R6 mudam a intenção na loja.** Risco: uma venda legítima em forma de pergunta ("Vendo a tocha?") deixa de
  vender. É o lado seguro (ouro/itens irreversíveis) e o texto pede a confirmação; os negativos de R5 cobrem as
  formas afirmativas.
- **V6 aumenta o fallback.** Falso positivo custa prosa; o corpus benigno e a exigência de nome de
  `earlier_fallen` + verbo no presente + ausência de marca de passado limitam o alcance. Medir no §6.
- **R8** muda só a exibição; resolução de item por nome usa o `display_name` inteiro como hoje.
- **R18/R19** mudam a copy de efeito pago: o jogador passa a ver o teto exato ("até 0,015 Estilhas") em vez do
  inteiro arredondado ("1 Estilhas"). Cliente antigo sem `preco_milli` continua com o inteiro.
- **R1** muda o `de` exibido em fugas que reiniciam a perseguição; saves antigos sem `_last.de` usam o fallback de
  hoje.
- **MockLLM/FallbackLLM:** guard mantido; R4/R6 cortam chamadas; R21 roda no Mock.
- **Quota/latência:** nenhuma chamada nova; a loja tende a ficar mais rápida (sem CLASSIFY nas perguntas).
- **Saves:** R28.

## 8. Decisões

### Do dono / coordenador (prompt de 02/11)

- Zero pendência: todos os P2/P3 do smoke 4 entram.
- P3-1: o requisito é "débito igual à cotação" **ou** "cotação igual ao custo real", decidido pelo source.
- P2-1: trilha da fuga coerente e sem id cru/acento faltando. P2-2: pergunta de catálogo vira consulta, nunca
  venda. P3-2: quedas de rodadas antigas no passado no resumo. P3-4: nomes longos na consulta.
- Itens não verificados viram testes determinísticos/Playwright que forçam o cenário.
- Combate sem LLM por rodada; golden 330 protegido; nenhuma flag nova; §6 curto (≤ 10 turnos) só nos achados.

### Do autor (valem como aprovadas; o dono pode vetar na revisão)

- **D-364-1 — Débito pelo custo real, cotação é teto.** Nenhuma das duas igualdades pedidas é possível pelo
  source: a cotação é calculada **antes** da geração como teto (`image_quotes.py:84-99`) e a liquidação cobra o
  uso exato reportado pelo provedor e libera o resto (`wallet.py:696-707`). Igualar o débito ao teto cobraria
  mais do que o custo (contra a regra de liquidação exata e a D-352-8); igualar a cotação ao custo real exige
  saber o custo antes de gerar. Fica: **débito = custo liquidado ≤ teto**, com a copy dizendo "até" (R17–R18).
  O §6.1 da SPEC-363 ("débito igual à cotação") fica superado; o coordenador ajusta o texto ao fechar a 363.
- **D-364-2 — Teto exato em vez do inteiro arredondado.** "1 Estilha" para um teto de 0,015 exagera 66× o valor
  máximo e diverge do saldo e do Livro, que já mostram frações (`AccountScreen.tsx:11-16`, `StoryLog.tsx:166`).
  Singular só para exatamente 1. Alternativa, se o dono preferir: manter o inteiro, com "até" e o plural certo
  ("até 1 Estilha").
- **D-364-3 — Pergunta nunca transaciona item.** Estende ao fluxo de itens a regra que as Cartas já seguem
  (`agents/loot.py:422-437`): gasto irreversível só com frase afirmativa.
- **D-364-4 — Nome curto só na exibição.** Não toca save nem resolução por nome.
- **D-364-5 — V6 rejeita, não reescreve.** Mesmo modelo de V1–V5: o fallback determinístico já conta a queda
  antiga no passado (363 R9).

### Pendentes do dono

- Nenhuma bloqueia a execução. D-364-2 é a única com efeito visível em texto pago; vetar troca R18 pela
  alternativa sem mudar o resto do plano.

## 9. Registro de implementação

**Etapa 0 (confirmação).** (1) Achado 1 reproduzido pelo teste novo: 2ª fuga depois de "alcançado" dava `de == "alcancado"`
(o `_prev_track` de `combat_meta` é lido antes de `_attempt_flee` reiniciar a perseguição); o caso `distante` tem a mesma
causa. (2) Achado 5: só `round_registry` duplica; `mech_log` e `round_board` não consomem `scene_logs` (R15 vale só no
registro). (3) `gerar` é montado em `api._enemy_portrait` → `creature_art.portrait_for`; milli da API é string de inteiro
(`credits_milli`), então `preco_milli` é string.

**Commits (branch `spec-364`).** 1 fuga (R1-R3) · 2 mercado (R4-R9) · 3 resumo/registro (R10-R16) · 4 retrato (R17-R20) ·
5 cenários (R21-R23) · 6 guardas (R24, R26-R29).

**Desvios e decisões de execução.**
- R17: os testes de liquidação (`test_settle_below_ceiling_releases_remainder`, `test_settle_above_ceiling_capped`) usam o
  fixture Postgres `image_case` e **pulam sem `RPG_TEST_DATABASE_URL`**; não rodaram localmente. O "U > T" é, no motor
  real, **limitado ao teto com anomalia financeira** (`financial_anomaly_milli`), não "recusado": o teste afirma o limite.
- R21: a queda do herói é aleatória no motor real; o teste cobre o desfecho nos dois caminhos (`_narrate_outcome` com resumo
  aceito e com fallback forçado), registro, fatos e `_killer_identity`, não a morte ponta a ponta pela API.
- R22 revelou **bug real**: o fallback do cliente (`CombateTab.tsx`) chamava `visibleEnemyIds(combat.enemies)`, mas o
  ocultamento mora em `scene.positions[*].concealment` (já em `people`); o escondido era oferecido como alvo sem
  `valid_targets` do servidor. Corrigido para `people.filter(role==="enemy")`.
- R13: o texto real do staging não estava no repositório; a fixture usa a frase citada no §1.1 ("o Goblin também tomba sem
  vida ao seu lado") dentro de um resumo plausível. Trocar pelo texto bruto se o coordenador o quiser byte a byte.
- R26/R27: `test_spec364_golden_guard.py` só vale com a branch `spec-364` checada (skip depois do pouso).
- `outcome_facts`/`deterministic_outcome_text` agora dividem as quedas por `round_log.fall_partition` (inclui
  `sem_vitalidade` como "rodada final"); o fallback da 363 continua igual nos casos cobertos.

**Expected de testes antigos alterados.** `tests/test_remediacao_comerciante_real.py` (consulta em duas seções, não mais
"compra / venda"); `web/tests/spec347-components.test.mjs` e `web/e2e/spec352-retrato-pago.spec.ts` (copy "Gerar retrato (até N
Estilhas)"). `tests/test_spec363_ids.py` ganhou `alcancado` no detector (R29).

**Pendente do coordenador.** Revisão `Sol`; smoke §6 (`docs/spec364/smoke-final.md`); rodar os 2 testes Postgres de R17;
ajustar o §6.1 da SPEC-363 (D-364-1).

**R17 com Postgres (02/11).** Não há banco local: CLI `supabase` ausente, Docker parado, nada ouvindo em 5432/54322. Os 2
testes `image_case` seguem pulados; o revisor (ou o coordenador com Supabase de pé) roda
`RPG_TEST_DATABASE_URL=<dsn local> pytest tests/test_spec364_portrait_debit.py`. Também corrigido `typecheck:e2e`
(`card-shop-357.spec.ts`, cast via `unknown`), erro preexistente.

**Correções da revisão Sol (02/11, `handoffs/SPEC-364-sol-review.md`).**
- P1-1/P2-1: `tests/test_spec364_flee_surfaces.py` monta a perseguição à mão (alcançado; `distante`; afastado; quase livre) e
  prova pela API a mesma trilha em `mech_log`, mensagem e Livro, o regex de R3, a voz de R16 e a Carta de Cena (condição +
  Carga) disparando; o contador de `get_llm` delega ao Mock e exige `== 0` nas rodadas que não encerram o conflito. O teste
  vácuo de `test_spec346_board_no_llm.py` foi removido. `round_board` não é checado em texto (é lista estruturada, sem trilha).
  O caso (e) sacrifício é de unidade (`_attempt_flee(force_escape)`; o fluxo completo exige party com oferta).
- P2-2: sacrifício aceito grava `_last = {de, sacrificio}` (sem dado velho); linha "Fuga · sacrifício aceito · escapou (de → livre)".
- P2-3/P3-2: `fall_partition` inclui `inconscientes`; "Na rodada final" sempre que há `last_out`.
- P2-4: `tests/test_spec364_death_api.py` (TestClient; seam = `death_flow.attempt_stabilization`) afirma mensagem, Livro,
  `death_context.killer`, crônica ("Smoke4A tombou em combate" íntegro, nunca "SmokeA") e `mech_log`, nos caminhos LLM
  aceito e fallback (`fallback_attribution` por V5). **Limite honesto:** o inimigo morto em rodada anterior sai de
  `state["enemies"]` antes do resumo seguinte, então a queda antiga **não chega ao `conflict_summary`** neste cenário de API;
  V6/R10 ficam provados em unidade (`test_spec364_outcome_tense.py`). O coordenador deve confirmar no §6 se o smoke 4 listou o
  Goblin em `mortos` por outro caminho.
- P2-5: `test_no_internal_ids_or_hero_name_in_history_r29` (2 fugas, Cartas de Cena, item livre longo, voz).
- P3-1: V6 com plural e "cai morto" e verbo sem sujeito herdando o nome. P3-3: pergunta de compra cota o preço de compra
  (item que o mercador não tem → "não está à venda aqui"). P3-4: saldo da conta no singular. P3-5: teste renomeado
  `test_settle_above_ceiling_capped`; os 2 testes Postgres não rodam no CI. **R17 será provado pela evidência do §6.3 no
  smoke de staging** (débito liquidado ≤ cotação e reserva 0), anotada pelo coordenador. P3-6: asserção tautológica trocada.
  P3-7: fixture R13 agora usa o `A_end.message` bruto do staging.
