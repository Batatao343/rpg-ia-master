# SPEC-387 — Cartas: achados do 6º smoke (Carta de cena sem cache de processo, oferta de retrato estável, chip otimista, "Criatura hostil" de fallback, rota Groq, jogada inelegível explicada, escolta, seeds dos §6 não verificados, `draft.py` e 8 arestas de texto/UI)

> **Status:** `in-progress` (implementado em 03/11, aguarda revisão Sol e o smoke §6; aprovada em 03/11, coordenador, autorização do dono "manda bala"; D-387-1..11 pelas recomendações do §8, veto do dono possível)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Épico:** SPEC-327
> **Origem:** 6º smoke real (03/11, `main` `2a6e0945` local e `9e5f43d9` no staging). Achados S6-1..S6-4 em
> [docs/spec367/smoke-staging.md](../docs/spec367/smoke-staging.md) § Achados; achados 1–14 e "não verificado" em
> [docs/spec368/smoke-local.md](../docs/spec368/smoke-local.md) e [docs/spec367/smoke-local.md](../docs/spec367/smoke-local.md).
> Evidência bruta no scratchpad do coordenador (`smoke6stg/`, `out/`).
> **Depende de:** SPEC-367 e SPEC-368 com código na `main` (367 `approved`, 368 `in-progress`; esta spec corrige o que os
> smokes delas acharam e não reabre os requisitos delas).
> **Desbloqueia:** fechar como `done` 327–336, 345–347, 352, 355 e 357 (épico de cartas) e os §6 de 367/368, sem pendência
> aberta (política do dono: zero pendência, P3 inclusive).
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true`
> (estado servido em várias instâncias, efeito pago, roteamento de LLM e regra de motor)
> **EVAL_AUTHORING_REQUIRED:** `false`. Não muda evaluator, expected de eval, baseline, dataset de regressão, arena,
> limiares de `scripts/cards/{lint,sim,promote}.py` nem o golden da SPEC-330 (R40).

Rótulos: **[F]** fato no source (`main` em `3db86582`) · **[H]** hipótese com evidência; a Etapa 0 ou o 1º teste confirma ou
derruba · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

O 6º smoke foi o primeiro com o épico de cartas inteiro na `main` e o primeiro em que a Carta de cena rodou na Vercel. Ele
achou **1 P1** que só aparece em serverless: a Carta temporária de um objeto da cena vive num cache do processo, e a
instância seguinte não a conhece (id cru, custo 0, jogada recusada). Achou também **5 P2** (oferta de retrato
intermitente, chip que não troca no clique, fallback Groq quebrado no roteiro, jogada inelegível engolida em silêncio,
`draft.py` que rende quase nada) e **≥ 12 P3** de texto, UI e fixture. E deixou **8 cenas "não verificadas"** porque as
seeds da 368 não levam o jogo até elas de forma determinística.

O objetivo é **corrigir todos os achados** com teste determinístico para cada um e **tornar verificáveis as 8 cenas** por
seed, para que o §6 desta spec seja curto e feche o épico. Princípios: **mecânica é Python** (nada aqui acrescenta LLM por
rodada); **o estado salvo é a fonte** (nenhum dado de jogo pode depender de cache de processo); **falha de leitura não
some com a oferta por 60 s**; **recusa sempre explicada** (nada é gasto e o jogador lê por quê); **voz do jogador** nas
superfícies de combate (D-363-3); golden da 330, `web/e2e/contracts` e e2e existentes intocados; nenhuma flag nova.

### 1.1 Achados e causa no source

| # | Achado (prio) | Evidência do smoke | Causa no source |
|---|---|---|---|
| S6-1 | Carta de cena com id cru (`CENA_POCO_NEGRA_04930…`) e custo 0 no staging (P1) | `out/stg-1440-a-chip.png` | **[F]** A Carta de objeto é montada de forma determinística a partir da cena (`services/scene_cards.py:639-677`, id = `cena_<obj>_<sha1[:8]>`) e só é registrada no catálogo em memória `_TEMP_CARDS` (`services/cards.py:199-209`, LRU de 64) por `sync_hand` (`scene_cards.py:697-718`). `sync_hand` só roda dentro do nó de combate (`agents/combat.py:2344,2558,2964`). A view `/game/state` monta a mão por `card_piles.public_view` → `card_of` → `cards.get_card` (`services/card_piles.py:61-63,726-751`); numa instância sem o registro, `get_card` devolve `None` (`cards.py:212-219`), e a linha sai com `name = id` e custo 0. A validação de borda da jogada roda **antes** do nó: `_apply_play_list` → `check_declared_target` (`api.py:6095-6112`) → `hand_card_targeting` (`services/combat_targeting.py:142-161`), que, com a Carta vazia, devolve `valid_targets=[]` e motivo `None`; com `target_id` explícito, `check_declared_target` responde `no_valid_target` (`combat_targeting.py:220-225`) e a API dá **409 `invalid_target`**. `_in_scene_hand` também exige `card_id in _TEMP_CARDS` (`cards.py:558-564`). O mesmo bug ocorre numa instância só, quando o LRU de 64 descarta a Carta |
| S6-2 | Oferta de retrato aparece em 2 de 5 carregamentos, variando por instância (P2) | `stg/done-offer.txt` | **[F]** Três leituras fail-closed apagam a oferta: (a) `_portrait_price_estilhas` guarda `None` por 60 s quando `peek_ceiling` falha (`api.py:2902-2918`, cache de falha em `:2917`); (b) `_portrait_registry` devolve `None` em `registry_read_failed` (`api.py:2989-2993`), e com registro `None` não há preço (`api.py:3009`); (c) `_image_effect_open` devolve `False` em `image_gate_failed` (`api.py:2883-2891`), e o `KillSwitches.snapshot` de uma instância fria que falhou a 1ª leitura fica `unreadable` e força as chaves fail-closed a `False` por 5 s (`services/kill_switches.py:161-185`). Nenhuma das três tenta de novo. **[H]** Qual delas disparou no staging (provável: checkout do pool numa instância fria, como no A7 da 367); a Etapa 0 confere nos logs |
| S6-3 | Chip continua "Gerar retrato (até 0,015 Estilhas)" 400 ms depois do clique e aceita clique (P2; R4 da 367 não atendido ao vivo) | `done-offer.txt` (`1440-logo-apos-gerar`) | **[F]** O pendente só é aplicado depois do `/art/confirm` (`web/src/App.tsx:419-422`); `handleGeneratePortrait` não toca o chip antes da cotação (`App.tsx:392-403`). O botão usa só `aria-disabled` (`web/src/combat/TargetChip.tsx:48-49`), e `genDisabled` recebe só `busy` do turno, nunca `imageBusy` (`web/src/workspace/tabs/CombateTab.tsx:328,341`) |
| S6-4 | "Criatura hostil" de fallback em 3 de 4 aberturas no Pântano da Melancolia e na Floresta dos Sussurros, com `RPG_CREATURE_GEN` off (P3) | `fallback_seen` nos logs | **[F]** "criatura" e "hostil" estão em `_STOP` (`services/encounter_manifest.py:125-128`), então `name_tokens("Criatura hostil") == []`. `shares_identity` exige interseção de tokens (`encounter_manifest.py:238-240`): com o pedido vazio, **toda** espécie gerada é "troca de espécie", e a trava de identidade materializa `fallback_criatura_hostil` (`agents/combat.py:706-733`). Com o gerador `on` há a saída de `geracao.nome` (`:710-718`); com `off`, não. O nome genérico chega ao `_grounded_template` porque `_name_without_generic_head` só troca nomes com cabeça genérica **e complemento** (`encounter_manifest.py:337-341`); "Criatura hostil" passa direto quando a narração não cita espécie do bestiário (`agents/combat.py:646-655,874-876`). **[H]** Por que essas duas regiões: a narração de abertura delas descreve "uma criatura" sem nome do bestiário, e o scanner devolve o nome genérico; a Etapa 0 confere no `flavor`/narração das 3 aberturas |
| L1 | Fallback Groq quebrado: CLASSIFY `openai/gpt-oss-20b` → 400 `tool_use_failed` no `dm_router`; FAST `llama-3.3-70b-versatile` → 404 `model_not_found`; sem DeepSeek não abre combate (P2) | `out/server-8758.log`, `out/llm-8758.jsonl` | **[F]** O 404 é do **roteiro**, não do default: `ROUTES` FAST já usa `openai/gpt-oss-120b` (`llm_setup.py:379-385`; `tests/test_routing.py:149-152` fixa isso), mas o roteiro do item 10 e a fixture mandam `llama-3.3-70b-versatile` (`specs/SPEC-368-cartas-fechamento-epico.md:217`, `tests/fixtures/spec368_scenarios.py:525`), e o `AGENTS.md` ainda documenta o llama (`AGENTS.md:158,170`). CLASSIFY default é DeepSeek → `gpt-oss-20b` → Gemini flash-lite (`llm_setup.py:374-378`); o 400 `tool_use_failed` é tratado como falha semântica com 1 regeneração no mesmo candidato (`llm_setup.py:363,1112-1118`) e, com o roteiro só-Groq, esgota o tier. `load_dotenv(override=True)` (`llm_setup.py:38`) faz o `.env` vencer a variável do SO, então `GROQ_API_KEY=invalida` não teve efeito. **[H]** "Não abriu combate": com CLASSIFY esgotado, o `_hostility_fallback` só abre COMBAT se a narração recente citou o goblin (`agents/router.py:349-392`, regra da SPEC-355 R5); a Etapa 0 confere se o save do item 10 tinha essa narração |
| L2 | Seed 3 põe na mão Cartas fora de Preparadas/baralho; a jogada devolve `result: ok`, sem linha, sem efeito, e a Carta vai ao descarte (P2 fixture + P3 motor) | `out/i3r-r0.json`, `out/i3e-r0.json` | **[F]** A seed só chama `_known` (`tests/fixtures/spec368_seed.py:169-173,192-197`) e força a mão (`:99-106`), sem pôr a Carta em `deck`/`prepared_cards`. `plan_plays` só confere a **mão** (`services/card_piles.py:646-653`), então a lista passa na borda. Dentro do turno, `use_card` recusa porque a Carta não está em Preparadas/baralho/Virtude (`services/cards.py:574-589`, erro "X não pôde ser jogada."), o erro vai a `out["logs"]` (`services/conflict_turn.py:450-453`) e o Fôlego é devolvido (`services/card_deck_round.py:170-176`). O registro **descarta** a linha porque "não pôde ser jogada" não está na lista de frases humanas (`services/round_log.py:26-46,67-68`; só "não está na sua mão\|não está preparada\|Fôlego insuficiente" em `:45`). A Carta fica na mão e sai no descarte do fim da rodada |
| L3 | Seed 4 não produz escolta: `proteger` aponta para id que não é ator, falha na rodada 1 e a narração diz que o herói caiu (8/18) (P2) | `out/i4-r*.json` | **[F]** A seed põe o protegido em `scene["npcs"]` (`spec368_seed.py:198-202`). `sanitize_objective` aceita alvo de `scene.npcs` (`services/scene_cards.py:236-246`), mas `check_objective` procura o alvo nos **atores**; sem ator, falha na hora com "O protegido não resistiu." (`scene_cards.py:602-605`). O desfecho vira `defeat` (`agents/combat.py:2147-2148`), e o fecho de `defeat` manda narrar "O herói foi derrotado e perde os sentidos" (`agents/combat.py:2011`), contra a causa real (objetivo falhou, herói de pé). O mesmo `sanitize_objective` aceita esse alvo fora da seed, então é bug de motor |
| L4 | Seed 6 `espolio` sem baralho: Forja e Esquecer só aparecem depois de `activate_deck` (P3) | `out/i6e-rest.json` | **[F]** A receita de `(6, "espolio")` não chama `card_piles.activate_deck` (`spec368_seed.py:210-213`); só `(1, "rollback")` chama (`:181-183`) |
| L5 | Seed 13: `reacao` nunca dispara (goblin a 1 de Vitalidade prevê `fugir` em 8/8 sementes); `13` sem Ketil; `13 armadura` com goblin sem armadura (P3) | `out/i13-*.json` | **[F]** `reacao` usa `enemy_goblin` com `enemy_vitality=1` (`spec368_seed.py:236-241`); a variante padrão não tem aliado (`:222`); `armadura` usa `enemy_goblin` (`:229-234`). A IA do inimigo declara a manobra `flee` e o presságio a classifica como `fugir` (`services/enemy_intent.py:121-126`). **[H]** O limiar de fuga do goblin é Vitalidade baixa; a Etapa 0 confere. O RNG da rodada é o módulo `random` global (`agents/combat.py:2517-2518`), então a seed não fixa dado ao vivo: o resultado precisa ser garantido pelos números da cena, não pela semente |
| L6 | `draft.py` com chave real: Médico 0/4 válidas (vocabulário), Sangromante comum 2/2 reprovadas no lint (orçamento), `--n 4` devolve 2; roteiro com `lint.py --lote` errado; `promote` só passa com `lote-v2` (P2) | `out/rascunhos/`, `out/sim3681*.json` | **[F]** `EfeitoRascunho.alvo` e `escala` são livres (`scripts/cards/draft.py:42-55`); o prompt lista os alvos, mas não descreve a gramática de `escala` nem o orçamento por raridade, só "comum 1 efeito" (`draft.py:114-134`); não há 2ª tentativa para as rejeitadas nem aviso de `n` pedido × entregue (`draft.py:194-217,256`). `lint.py` e `promote.py` recebem o lote **posicional** (`scripts/cards/lint.py:43`, `scripts/cards/promote.py:169`), e o roteiro escreve `--lote` (`specs/SPEC-368-…md:212-213`). O `promote` usa `--protocolo lote` por padrão (`promote.py:179-184`) e a `lote-v2` é opt-in desde a SPEC-358 |
| L7 | "Presságio cumprido: cumpre o presságio" em "Efeitos da rodada" (P3) | 390 e 1440 | **[F]** `pressagio_entry` grava `efeito = "cumpre o presságio"` e `carta_nome = None` (`services/combat_preview.py:633-636`); o front mostra `Presságio cumprido: ${efeito ?? carta_nome ?? who}` (`web/src/combat/deck.ts:265`). O orquestrador não guarda a Carta no `pressagios_cumpridos` (`services/conflict_orchestrator.py:2752-2758`) |
| L8 | Rachadura: golpe de texto 6 saiu 7 e o `mech_log` não explica; "ganha a condição Rachadura" vem depois do ataque do goblin (P3) | `out/i3r-r0.json` | **[F]** O +25 % é aplicado em `conflict_damage` e só vai à linha técnica `"Rachadura/Torpor +25% -> 7"` (`services/conflict_damage.py:233-239`), que o registro filtra (`round_log.py:20-23`). `mech_log.attack_line` não lê o percentual (`services/combat_preview.py:371-401`). **[H]** A ordem: a linha da condição entra pelos logs humanos e é anexada depois dos eventos cronológicos; a Etapa 0 confere com a seed `3 rachadura` |
| L9 | Valerius: "age de novo. Ataque sem alvo válido." (rodadas 3 e 4) e troca de fase sem linha para o jogador (P3) | `out/5_*-auto*.json` | **[F]** A troca de fase escreve a `narracao` da fase em `out["logs"]` (`services/enemy_decks.py:545-585`; texto de Valerius em `data/cards/inimigos/_decks.json:235,252`), mas nenhuma frase de fase casa com `_HUMAN_LINE_RES` (`round_log.py:26-46`), então o registro a descarta. "X age de novo." é emitida antes de resolver a ação extra (`services/conflict_orchestrator.py:2879-2881`), e "Ataque sem alvo válido." (`services/conflict_turn.py:340-342`) é aceita como frase humana (`round_log.py:33,40`). **[H]** A ação extra usa o próximo presságio congelado (`conflict_orchestrator.py:2726-2751`), que na fase nova é `reforco_proprio` (Pele de Veterano); o recuo da SPEC-275 para ataque básico fica sem alvo; a Etapa 0 confere com a seed `5 chefe` |
| L10 | Rótulo cru "MAO_SOMBRIA" como chip da Carta no Acervo (P3) | UI 1440 | **[F]** `_cards_block` devolve `"subclass": card.get("subclasse", "")` cru (`api.py:2597,2674`); as Cartas de facção têm `"subclasse": "mao_sombria"` (`data/cards/inimigos/faccao_mao_sombria.json:9`); `DeckCard` mostra o valor como chip (`web/src/components/tabs/DeckCard.tsx:47`) |
| L11 | A 390, a barra fixa (Sem matar / Fugir / Encerrar a rodada) cobre a linha do presságio na rolagem padrão (P3) | `out/i367p-390-1.png` | **[F]** `.play-queue__end` é `position: sticky` no rodapé a 390 (`web/src/workspace.css:382`) e o conteúdo acima não reserva a altura dela |
| L12 | Modo `off` com LLM esgotado vaza `enemy_goblin_1 não está na cena` e ": Defesa Instintiva terminou"; a prosa `off` com LLM chama o herói pelo nome (P3) | `out/i9-last.json`, `out/server-8757.log` | **[F]** Sem `fallback_text`, a narração `off` despeja os logs crus em bullets (`agents/combat.py:1804-1808`), inclusive erros de cena com id (`services/conflict_scene.py:221,268,298,472,515`) e "Nome: cond terminou." sem `_voce`. O prompt `off` não proíbe o nome do herói |
| L13 | Recusa do Pacto diz "Fôlego insuficiente (0/1)" com Fôlego 2 (5 Cartas para 4 de capacidade) (P3) | `out/i1c-r1.json` | **[F]** `plan_plays` simula o lote e chama `_plan` com o Fôlego **que sobrou** depois das jogadas anteriores (`card_piles.py:670-673`); a mensagem cita esse resto e o custo da jogada isolada (`card_piles.py:443-450`), não o lote |
| L14 | Prosa da compra atribui a ação à cidade: "Skallgard desliza a Carta Lança de Gancho…" (P3, A9 da 364) | `out/i367-buy.json` | **[F]** O contexto do narrador escreve `Mercador: {nome} ({local}).` (`agents/loot.py:341-347`); o local entre parênteses vira sujeito na prosa e nada barra isso |

**Não verificado no smoke local** (precisa de seed determinística, R25): presságio frustrado; Eco com acerto; aviso de troca de
fase do chefe; Voto com o presságio mirando Ketil; Armadura Comprometida; vitória com Reação; entrega da técnica da quest
`justa`; V-G do ouro (`trade_prose_rejected`) disparando; condição de inimigo gerada por Carta terminando (R13 da 367).

Fora dos achados: a Jina 429 na criação de jogo (L-obs. 14) já é conhecida e tem retry; fica como está.

## 2. Requisitos

Valem com o preset de `scripts/staging/staging_flags.json` (cartas `on`). Em `off`, só R32 muda algo.

### A. Carta de cena sem cache de processo (S6-1)

- **R1 — Reidratação a partir da cena salva [D-387-1].** Nova função pura `scene_cards.rehydrate(state) -> int`: para cada
  objeto e interação de `state["combat"]["scene"]`, monta `_object_card` e registra com `cards.register_temp_card`, **sem**
  os filtros de zona/uso/destruído de `object_cards` (resolver nome de uma Carta que já está em `exaurida` também conta).
  Não muda pilhas nem cena. Devolve quantas registrou. É chamada no fim de `persistence._raw_to_state` (caminho comum de
  `legacy` e `hosted`: `persistence.py:899,1014`; `services/game_serialization.py:25-28`; `infrastructure/postgres.py:173`),
  dentro de `try` com `log_fallback("persistence", "scene_cards_rehydrate_failed", exc)`.
- **R2 — Instância fria vê a Carta.** Com `_TEMP_CARDS` vazio entre o turno que abriu a cena e o `GET /game/state` seguinte
  (simula outra instância), a linha da mão da Carta de objeto traz `name` = "`<Rótulo> (<Objeto>)`", `custo_folego` = 1,
  `tipo` = `ativa`, `alvo` coerente e `valid_targets` não vazio. Nenhuma linha da mão tem `name` igual ao `id`.
- **R3 — Instância fria aceita a jogada.** Com `_TEMP_CARDS` vazio antes do `POST /game/action` com `jogadas=[{card_id: <cena>,
  target_id: <inimigo>}]`, a resposta é 200, o registro tem a linha da Carta e o efeito aplicado; nada de 409 `invalid_target`.
  O mesmo vale quando o LRU de 64 descartou a Carta (63 Cartas de outras partidas registradas no meio).
- **R4 — Id órfão.** Se o catálogo de cena mudou entre deploys e o id na mão não é mais reconstruível, a Carta sai da mão no
  próximo `sync_hand` (como hoje) e a view nunca a mostra com id cru: a linha é omitida e `combat.scene_card_orphan` é
  registrado (sem id). Teste com uma cena salva cujo objeto mudou de rótulo.

### B. Oferta e chip do retrato (S6-2, S6-3)

- **R5 — Sem cache de falha [D-387-2].** `_portrait_price_estilhas` só guarda em cache leitura bem-sucedida (`value` não
  `None` ou `milli` `None` vindo do banco sem erro). Uma exceção não grava `at`, e a próxima view tenta de novo.
- **R6 — Uma nova tentativa no checkout.** O `peek_ceiling` (preço), o `get_many` (registro) e a 1ª carga do
  `KillSwitches.snapshot` fazem **1** nova tentativa quando a exceção é de checkout do pool (`PoolTimeout` ou
  `OperationalError` antes de qualquer comando; mesmo critério de `scripts/staging/ops_pool.py` da 367). Erro em `execute` não
  é repetido. Teste com pool falso: falha 1× → oferta presente; falha 2× → oferta ausente sem exceção.
- **R7 — Causa medida.** Quando a oferta é omitida por falha de leitura, a view registra `creature_portrait.offer_omitted`
  com `cause ∈ {price_peek_failed, registry_read_failed, image_gate_failed, switches_unreadable}` e `error_class`, sem id de
  jogo nem DSN. O evento entra em `observability/events.py` e `EVENTOS_DE_LOG.md`.
- **R8 — Chip otimista no clique.** Em "Gerar" (`data-gen-go`), `handleGeneratePortrait` aplica `withPortraitPending` **antes**
  do 1º `await` (guardando o `retrato` anterior). O chip mostra "Gerando retrato…" no mesmo frame, e nenhum
  `[data-gen-portrait]` existe para o inimigo e os irmãos do mesmo tipo. Em erro (402/409/503/rede na cotação ou na
  confirmação), no cancelamento do diálogo de cotação maior e no "Agora não" do diálogo, o `retrato` anterior volta, salvo
  quando `shouldHidePortraitOffer` manda esconder (regra de hoje). Helper puro novo em `web/src/lib/portraitOrder.ts`:
  `withPortraitRestored(data, enemyId, snapshot)`, imutável e com o mesmo objeto quando nada muda.
- **R9 — `disabled` de verdade.** O botão `[data-gen-portrait]` recebe o atributo `disabled` (além de `aria-disabled`) quando
  `genDisabled`; `CombateTab` passa `genDisabled={busy || imageBusy}` (prop nova `imageBusy` vinda de `App.tsx`). A cópia "Outro
  jogador já está gerando…" não muda (D-367-5).

### C. "Criatura hostil" de fallback (S6-4)

- **R10 — Nome genérico não vai ao gerador [D-387-3].** Em `_spawn_v4_enemies`, quando o nome do grupo (depois de
  `_name_without_generic_head`) não tem token de conteúdo (`not em.name_tokens(name)`), o elenco sai de uma criatura **da região
  atual**: candidatos do mesmo catálogo de `services/fauna._region_candidates(region, danger)` (região de
  `shared_pool._region_of(current_location_id)`, sem chefe, perigo compatível), escolha determinística por
  `crc32(game_id|turn_count|hint) % len(candidatos)`, instanciada por `template_by_id`. Independe de `RPG_FAUNA`. Sem candidato,
  segue o caminho de hoje. `meta.source = "regional_generic"`; evento `combat.spawn_generic_regional`.
- **R11 — Identidade com pedido vazio.** `_grounded_template` nunca materializa `fallback_<slug>` de um nome sem token de
  conteúdo. Se ainda chegar um, o evento é `combat.spawn_generic_name` (não `spawn_identity_mismatch`) e R10 decide.
- **R12 — Prova.** Com o gerador `off`, scanner simulado devolvendo `[{name: "Criatura hostil", count: 1}]` e o herói no
  Pântano da Melancolia e na Floresta dos Sussurros, o inimigo **não** tem id `fallback_*` em 20 de 20 `game_id`s, é do bestiário
  da região e a narração de entrada usa o nome dele. Com dica específica ("o goblin"), o caminho de hoje não muda (teste do
  `spawn_identity_mismatch` existente continua verde).

### D. Rota Groq e roteiro do router esgotado (L1)

- **R13 — CLASSIFY com candidato Groq que faz tool call [D-387-4].** `ROUTES[CLASSIFY]` passa a
  `deepseek-v4-flash → groq openai/gpt-oss-120b → groq openai/gpt-oss-20b → gemini flash-lite` (recomendação; o dono escolhe).
  `tests/test_routing.py` ganha `test_classify_groq_120b_antes_do_20b`. Nenhuma chamada de rede em teste.
- **R14 — Modelo morto fora de fixtures e documentação.** Nenhum arquivo fora de `docs/historico/`, `CHANGELOG.md`,
  `handoffs/`, `specs/` antigas, `playtest/pricing.py` (tabela de preço histórica) e testes de telemetria usa
  `llama-3.3-70b-versatile` como **rota**. `tests/fixtures/spec368_scenarios.py:525` troca para `openai/gpt-oss-120b`;
  `AGENTS.md:158,170` descrevem a ordem real de `ROUTES`. Teste: `test_no_dead_groq_model_in_routes_or_fixtures` varre
  `tests/fixtures/` e `llm_setup.py`.
- **R15 — `.env` continua canônico [D-387-5].** `load_dotenv(override=True)` fica, com comentário que diz por quê (variável
  antiga do SO não pode vencer o `.env`) e como simular falha: o roteiro de "router esgotado" usa `RPG_ROUTES` com um modelo
  inexistente, nunca uma chave inválida. O §6 usa esse roteiro.
- **R16 — Router esgotado abre combate quando há alvo.** Teste offline: CLASSIFY simulado esgotado (todos os candidatos
  levantam), narração anterior citando o goblin presente e "Ataco o goblin" → rota COMBAT via `hostility_fallback`; sem a
  citação → STORY (regra 355 R5 intacta). Se a Etapa 0 mostrar que o save do smoke tinha a citação e mesmo assim caiu em STORY, o
  defeito é corrigido aqui.

### E. Jogada inelegível explicada (L2, motor)

- **R17 — Um só predicado de elegibilidade.** Novo `cards.playable_ids(state) -> set[str]` com a regra de `use_card`
  (Preparadas, baralho com cartas `on`, Virtude, Sussurro, Carta de cena na mão). `use_card` e `card_piles.plan_plays` usam o
  mesmo predicado: uma Carta na mão que não é jogável faz `plan_plays` devolver `ok=False` com
  `motivo = "{Nome} não está no seu baralho."` **antes** de gastar qualquer coisa, e `card_deck_round.refusal` recusa a lista
  inteira (comportamento de recusa de hoje).
- **R18 — Nenhuma recusa some.** `round_log._HUMAN_LINE_RES` passa a aceitar `não pôde ser jogada\.$` e
  `não está no seu baralho\.$`. Teste de catálogo: toda string de recusa de jogador emitida por `cards.use_card`,
  `card_piles._plan`/`plan_plays` e `conflict_turn` (lista fechada no teste) é linha humana; nenhuma contém id. Teste de
  ponta: jogar pela API uma Carta só conhecida devolve a recusa explicada (sem Fôlego, Entropia ou Carta gastos) e a mão igual.

### F. Objetivo `proteger` (L3, motor)

- **R19 — Alvo do objetivo precisa ser ator [D-387-8].** `sanitize_objective` só aceita `proteger` cujo alvo esteja em
  `scene.allies` ou no elenco de aliados que vira ator no conflito (`combat.scene_allies`); um id só de `scene.npcs` derruba
  o objetivo para `derrotar_todos` com `scene_objective_dropped reason=target_not_actor`. `check_objective` com alvo que não é
  ator registra o mesmo evento e devolve `None` (nunca "falhou" na rodada 1).
- **R20 — Desfecho conta a causa.** Quando o desfecho vem de `objetivo_resultado == "falhou"` e o herói está consciente, o
  rótulo do desfecho é `objective_failed` (mapeado para o mesmo `outcome` `defeat` do manifesto, sem mudar `OUTCOMES`), com fecho
  próprio: "O objetivo se perdeu: {motivo do motor}. O herói segue de pé; não narre queda nem desmaio." `outcome_facts` inclui
  "Objetivo: {motivo}" e "Herói: {estado}" e o fallback determinístico diz o mesmo. Teste: seed 4 corrigida com o protegido
  abatido (vitalidade do aliado 0 por receita) → mensagem final sem "perde os sentidos"/"apaga"/"cai", com o motivo.

### G. Seeds determinísticas (L2–L5 e todos os "não verificado")

- **R21 — Seeds corrigidas.** Em `tests/fixtures/spec368_seed.py`: `3` e `3 rachadura` põem a Carta em `known_cards`,
  `deck` e `prepared_cards` (helper `_learn`, que substitui `_known` nas receitas de jogada); `4` põe o protegido como aliado
  ator em `combat.scene_allies` e o objetivo nele; `6 espolio` chama `card_piles.activate_deck` (Forja e Esquecer visíveis);
  `13 armadura` usa um inimigo com Proteção > 0 e Integridade (Etapa 0 escolhe o id, p. ex. `enemy_soldado_legiao_ferro`).
- **R22 — Resultado garantido pelos números, não pela sorte.** Como o RNG da rodada é global (`agents/combat.py:2517-2518`), cada
  cena que depende de acerto fixa a Esquiva do alvo em ≤ 2 + modificador mínimo do atacante (acerto certo em 2d10) e cada cena
  que depende de o inimigo atacar fixa um presságio `ataque` contra o alvo pedido (busca de semente em `forecast_round`, como
  `_reseed_for_reward`). O teste de cada variante roda **50** sementes de `random` e exige o mesmo resultado em todas.
- **R23 — Variantes novas.** `ITEMS` ganha:
  - `2 frustrar`: Carta que aplica `atordoado` na mão/baralho, inimigo com presságio `ataque` e Esquiva baixa → a rodada mostra
    o presságio frustrado.
  - `3 eco`: "Segundo Ato" depois de um golpe da mesma Postura, alvo com Esquiva baixa e Vitalidade alta → o efeito Eco aparece
    com acerto e o inimigo não morre antes.
  - `3 rachadura` (corrigida): o golpe de texto 6 sai 7 e o `mech_log` cita o +25 % (R28).
  - `3 inelegivel`: a receita antiga de propósito (Carta só em `known_cards` e na mão) → a jogada é recusada pela R17/R18.
  - `5 chefe_fase`: Valerius com Vitalidade 1 ponto acima do limiar de 60 % e golpe que cruza → a linha da fase aparece (R29).
  - `13 voto`: Devoto + Ketil como aliado ator, presságio mirando Ketil → "muda de alvo" ou "resiste".
  - `13 reacao` (corrigida): inimigo que não foge (família sem `flee`, ou presságio `ataque` fixado), Vitalidade 1, Reação
    "Encaixe do Golpe" na mão → a Reação mata e o resumo cita o autor.
  - `13 condicao_carta`: Carta do herói aplica condição de 1 rodada ao inimigo → "A condição X de Y terminou." (R13 da 367).
  - `14 entrega`: herói em `brekmar` (local da quest), contratante em cena, quest `justa` no último passo → aplicar
    `quest_completed` pelo `event_processor` entrega a técnica (offline) e 1 turno real fecha no §6.
  - `15 vg_ouro`: loja com saldo 80 e Carta de 50 (saldo final 30) para o teste ao vivo de V-G (§6).
- **R24 — Teste de cada seed.** `tests/test_spec387_seed.py`: para cada variante, save → load → `/game/state` mostra a cena, e
  uma rodada pelo motor (MockLLM, rodada sem LLM) produz o resultado prometido em 50/50 sementes. `tests/test_spec368_seed.py`
  segue verde (só o que R21 corrigiu muda, com motivo no §9).
- **R25 — Cobertura dos "não verificado".** Cada item da lista do §1.1 tem uma variante de R23 e um passo no §6.

### H. `draft.py` (L6; só gerador, prompt, roteiro e documentação)

- **R26 — Vocabulário no schema.** `EfeitoRascunho.alvo` vira `Literal` gerado de `fx.ALVOS` (ou validador que rejeita no
  parse com a lista); o prompt descreve a gramática de `escala` (chaves e valores aceitos por `fx.validate_card`) e o orçamento
  por raridade **lido** de `card_lint` (sem mudar o lint), com 1 exemplo válido por raridade pedida.
- **R27 — Reparo e contagem [D-387-10].** Cartas rejeitadas por vocabulário ganham **1** pedido de reparo (mesma chamada SMART,
  com os motivos), no máximo 1 chamada extra por execução; o lote final informa `pedidas`, `entregues`, `rejeitadas` e custo
  estimado. Sem LLM (Mock/Fallback), o comportamento é o de hoje (lote vazio com aviso). Ao terminar, `draft.py` imprime os 3
  comandos seguintes **corretos** (`lint.py <lote>`, `sim.py --lote <lote> --protocolo lote-v2 --json --out …`,
  `promote.py <lote> --onda N --protocolo lote-v2 --sim-report …`). Teste: os comandos impressos fazem `parse_args` sem erro em
  cada script. Teste com LLM falso que devolve 4 Cartas (2 com `alvo: "aliado"`): reparo chamado 1×, saída com 4 válidas.
  O `promote` não muda [D-387-7]: o default `--protocolo lote` fica, e o roteiro e o texto impresso passam `lote-v2`
  explicitamente; `scripts/cards/{lint,sim,promote}.py` sem diff (R40).

### I. Texto e UI (L7–L14)

- **R28 — Rachadura explicada e em ordem.** O ataque registra `pct_dano` (soma de Rachadura/Torpor) e `mech_log` acrescenta
  `· Rachadura +25 %` (ou `Torpor −25 %`) antes do dano final. No registro, a linha "ganha a condição Rachadura" do herói vem
  logo depois da jogada que a aplicou e antes do ataque seguinte do inimigo. Teste com a seed `3 rachadura`.
- **R29 — Fase do chefe visível, ação extra limpa.** (a) As frases de troca de fase (a `narracao` da fase ou o padrão
  "{nome} muda de postura…") entram no registro, na mensagem do turno e no `/game/history` uma vez por fase, marcadas pelo
  evento `out["fases"]` (não por regex do texto). (b) "X age de novo." só é emitida se a ação extra resolveu algo; uma ação
  extra sem alvo válido não gera linha no registro (vira `enemy_extra_action_skipped` na telemetria) e "Ataque sem alvo válido."
  sai de `_HUMAN_LINE_RES` para inimigos (continua para o herói). Teste com a seed `5 chefe_fase`.
- **R30 — Presságio cumprido com conteúdo.** `pressagios_cumpridos` guarda `carta_id`; `pressagio_entry` grava
  `carta_nome` (nome da Carta jogada, já revelada por ter sido jogada) e `efeito = "{ator} — {carta}"`, ou
  `"{ator} age como anunciou"` sem Carta. O front não muda (`deck.ts:265` e `web/tests/spec354-roundboard.test.mjs:39`
  seguem válidos). Nenhuma linha "cumpre o presságio" sobra. Exemplo: "Presságio cumprido: Goblin — Pancada de Tronco".
- **R31 — Rótulo de subclasse humano.** `_cards_block` passa `subclass` por `card_text.subclass_label(card)`: subclasse de
  Postura → nome do ramo em `data/classes.json`; facção → nome da facção no grafo do mundo (`data/graph/entities.json`, tipo
  facção); sem nome conhecido → `""` (sem chip). Teste: `inf_fac_mao_sombria_*` → "Mão Sombria"; nenhuma `subclass` da view
  casa `^[a-z0-9_]+$` com `_`.
- **R32 — 390 sem presságio coberto [D-387-9].** O contêiner rolável do combate reserva no fim a altura da barra fixa
  (`scroll-padding-bottom` + `padding-bottom` iguais à altura medida de `.play-queue__end`). E2e novo
  (`web/e2e/spec387-omen-390.spec.ts`, `--workers=1`): a 390, na rolagem padrão depois de abrir o combate, a caixa da linha do
  presságio não intersecta a de `.play-queue__end`.
- **R33 — Modo `off` sem texto técnico.** O fallback sem `fallback_text` (`agents/combat.py:1804-1808`) passa pelas mesmas
  regras do registro: só linhas humanas (`round_log._is_human_line`) com `_voce` aplicada, nenhuma linha com id (`snake_case` com
  `_` e dígito) e nada de "⚔️ •" em bullets: monta um parágrafo como `round_log.deterministic_outcome_text`. A prosa `off` com LLM
  ganha a regra "trate o jogador por você; nunca use o nome próprio do herói" e, se a prosa trouxer o nome, cai no fallback
  determinístico [D-387-6]. Teste com logs que contêm `enemy_goblin_1 não está na cena.` e `Goblin: Defesa Instintiva terminou.`.
- **R34 — Recusa do Pacto pelo lote.** Quando `plan_plays` recusa por Fôlego, a mensagem cita o lote:
  "Fôlego insuficiente: estas jogadas custam {total}, você tem {fôlego da rodada} e o Pacto do Abismo empresta no máximo
  {PACTO_MAX_FOLEGO} por rodada." O `pay_cost` de uma jogada isolada mantém a mensagem de hoje. Teste com 5 Cartas de custo 1,
  Fôlego 2: a mensagem traz 5, 2 e 2, e nunca "(0/1)".
- **R35 — Quem age na compra é o mercador.** `_merchant_context` passa a
  `"Mercador: {nome}. Lugar: {local} (o lugar não age; quem entrega e recebe é o mercador)."`. Nova função pura
  `prose_guard.place_as_actor(text, place) -> bool`: verdadeira quando o nome do lugar aparece seguido (≤ 1 palavra) de um verbo
  da lista fechada `{entrega, desliza, estende, conta, recebe, aceita, passa, oferece, vende, devolve, guarda, sorri, empurra,
  pousa}`. Nos dois caminhos de narração da loja (os mesmos da V-G da 367), verdadeira → `_deal_fallback` e evento
  `loot.trade_prose_rejected reason=place_as_actor`. Fixture com o texto real do smoke (rejeitado) e com
  "O ferreiro da Forja dos Clãs desliza a Carta…" (aceito).

### J. Guardas

- **R36 — 0 LLM por rodada.** `tests/test_spec346_board_no_llm.py` e `tests/test_spec364_flee_surfaces.py` verdes; R10, R17–R20,
  R28–R34 são determinísticos. R35 só valida. R27 é ferramenta fora do jogo.
- **R37 — Sem `with_structured_output` novo no jogo**; o guard de FallbackLLM do `draft.py` continua (lote vazio com aviso).
- **R38 — Sem flag nova.** `config/flags.yaml` sem diff.
- **R39 — Contrato aditivo.** View: só campos novos opcionais (nenhum renomeado); `outcome` do manifesto continua em `OUTCOMES`;
  `web/e2e/contracts` sem diff; nenhum spec existente em `web/e2e/` alterado (só arquivos novos).
- **R40 — Integridade.** `git diff main -- tests/spec330_equivalence.py tests/fixtures/spec330_legacy_golden.json evals/
  scripts/cards/lint.py scripts/cards/sim.py scripts/cards/promote.py data/cards/_orcamento.json` vazio. Arena de balanço não é
  necessária: nenhuma regra numérica de Carta muda (R17 só antecipa uma recusa que já existia).
- **R41 — Saves.** Saves antigos carregam: R1 é idempotente e tolerante (cena sem objetos → 0); R19 vale para objetivos novos e
  para o `check_objective` de saves em curso (alvo não ator → objetivo ignorado, nunca falha retroativa).

### Fora de escopo

- Ligar `RPG_CREATURE_GEN`, `RPG_FAUNA`, `RPG_PLOT_THREADS` (decisão do dono, ESTADO).
- Mudar o nome "Criatura hostil" quando o jogador **pede** uma criatura genérica sem região com bestiário (R10 sem candidato).
- Persistir as Cartas de cena no save (alternativa de D-387-1).
- Mudar `promote.py`, `lint.py`, `sim.py`, limiares, orçamento ou arena (integridade de eval; D-387-7).
- Trocar DeepSeek como primário ou mexer em timeout de provider.
- A cópia "Outro jogador já está gerando…" (D-367-5).
- Jina 429 na criação de jogo.
- Balanço (`bomba_estopim`, Arcanista, Sangromante, Médico p95) — follow-ups próprios.
- Achados de 359/360/361 (bestiário/criaturas) fora do S6-4.

## 3. Design técnico

### 3.1 Arquivos novos

- `tests/test_spec387_scene_cards_cold.py` (R1–R4), `tests/test_spec387_portrait_offer.py` (R5–R7),
  `tests/test_spec387_generic_spawn.py` (R10–R12), `tests/test_spec387_routes.py` (R13–R16),
  `tests/test_spec387_ineligible_play.py` (R17, R18), `tests/test_spec387_objective.py` (R19, R20),
  `tests/test_spec387_seed.py` (R21–R25), `tests/test_spec387_draft.py` (R26, R27),
  `tests/test_spec387_text.py` (R28–R31, R33–R35), `tests/test_spec387_guards.py` (R38–R40).
- `tests/fixtures/spec387_smoke.py`: texto real da compra ("Skallgard desliza a Carta Lança de Gancho…") e textos corretos (R35).
- Front: `web/tests/spec387-portrait-optimistic.test.mjs` (R8: `withPortraitPending`/`withPortraitRestored`),
  `web/e2e/spec387-portrait-optimistic.spec.ts` (R8, R9 a 390 e 1440, `page.route` com atraso de 1 s na cotação),
  `web/e2e/spec387-omen-390.spec.ts` (R32).

### 3.2 Arquivos alterados

- `services/scene_cards.py`: `rehydrate` (R1); `sync_hand` registra órfão (R4).
- `persistence.py`: chamada de `rehydrate` no fim de `_raw_to_state` (R1).
- `api.py`: `_portrait_price_estilhas` sem cache de falha (R5); retry de checkout no preço e no registro (R6); evento de
  omissão (R7); `_cards_block` com `subclass_label` (R31). Nada no fluxo de jogadas.
- `services/kill_switches.py`: 1 nova tentativa de checkout na carga (R6).
- `web/src/App.tsx`, `web/src/lib/portraitOrder.ts`, `web/src/workspace/tabs/CombateTab.tsx`, `web/src/combat/TargetChip.tsx`,
  `web/src/combat/Arena.tsx` (repasse de `genDisabled`), `web/src/workspace.css` (R8, R9, R32).
- `agents/combat.py`: R10/R11 no spawn; R20 (rótulo `objective_failed`, fecho); R33 (fallback `off`).
- `services/encounter_manifest.py`: só se R10 precisar de helper público (`is_contentless_name`).
- `llm_setup.py`: `ROUTES[CLASSIFY]` (R13) e comentário do `load_dotenv` (R15). `AGENTS.md` (R14).
- `tests/fixtures/spec368_scenarios.py`, `tests/fixtures/spec368_seed.py` (R14, R21–R23).
- `services/cards.py` (`playable_ids`), `services/card_piles.py` (`plan_plays`, mensagem do lote), `services/round_log.py`
  (frases humanas, ordem da condição, fases) (R17, R18, R28, R29, R34).
- `services/scene_cards.py` (`sanitize_objective`, `check_objective`) (R19).
- `services/conflict_orchestrator.py` (`carta_id` no cumprido; "age de novo" só com ação resolvida; `pct_dano` no ataque)
  (R28–R30); `services/conflict_damage.py` (devolve `pct_dano`) (R28); `services/combat_preview.py` (`mech_log`,
  `pressagio_entry`) (R28, R30).
- `services/card_text.py` (`subclass_label`) (R31). `agents/loot.py`, `services/prose_guard.py` (R35).
- `scripts/cards/draft.py` (R26, R27). `observability/events.py`, `EVENTOS_DE_LOG.md` (eventos novos).

### 3.3 Formatos e exemplos

Carta de cena reidratada (R1/R2), objeto real do staging:

```
id   = "cena_poco_negra_04930xxxx"   # cena_<obj.id>_<sha1(obj.id, label, efeito)[:8]>
view = {"id": "cena_poco_negra_…", "name": "Empurrar (Poço Negro)", "tipo": "ativa", "custo_folego": 1, "alvo": "inimigo"}
```

Spawn genérico (R10):

```
dica = "a criatura hostil"; scanner → [("Criatura hostil", 1)]; name_tokens → []
região = pantano_melancolia; candidatos = fauna._region_candidates(região, perigo)   # sem chefe
escolha = candidatos[crc32(f"{game_id}|{turn}|a criatura hostil") % len(candidatos)]
meta.source = "regional_generic"
```

Recusas (R17, R34):

```
"Junta Emperrada não está no seu baralho."
"Fôlego insuficiente: estas jogadas custam 5, você tem 2 e o Pacto do Abismo empresta no máximo 2 por rodada."
```

Fecho do objetivo (R20):

```
Desfecho: o objetivo falhou.
Objetivo: Escoltado não resistiu.
Herói: ferido, de pé.
→ fecho: "O objetivo se perdeu: Escoltado não resistiu. O herói segue de pé; não narre queda nem desmaio."
```

Contexto da loja (R35):

```
Mercador: Forja dos Clãs. Lugar: Skallgard (o lugar não age; quem entrega e recebe é o mercador).
```

## 4. Plano passo a passo

Em cada etapa: testes primeiro → código → só os testes do escopo (no máximo `-n 2`). A suíte completa é do coordenador, no
pouso. Etapas que tocam `round_log`, `combat_preview` ou o orquestrador rodam também `tests/test_spec363_*.py`,
`tests/test_spec364_*.py`, `tests/test_spec367_*.py`, `tests/test_spec368_*.py` e `tests/test_spec353_misc.py`.

### Etapa 0 — Confirmação (sem código de produto)

1. **S6-1:** teste que limpa `_TEMP_CARDS` entre abrir a cena e o `GET /game/state` e vê a linha com `name == id` (falha antes do código).
2. **S6-2:** ler os logs do staging (Vercel, janela 19:10–21:37 UTC de 03/11, por nome de evento) para `price_peek_failed`,
   `registry_read_failed`, `image_gate_failed`, `kill_switch_load_failed`; anotar a causa. Sem acesso aos logs, anotar e seguir (R7 mede).
3. **S6-4:** nos logs/estado das 3 aberturas, conferir `spawn_identity_mismatch` e o nome do grupo do scanner; anotar o texto da narração de abertura.
4. **L1:** conferir no save do item 10 se a narração anterior citava o goblin (decide se R16 é só teste ou correção).
5. **L5/L9/L8:** com as seeds atuais, confirmar (a) o limiar de fuga do goblin, (b) a intenção da ação extra de Valerius na
   fase 2 e (c) a ordem das linhas da Rachadura.
6. **R10:** confirmar que `fauna._region_candidates` lê o catálogo sem depender de `RPG_FAUNA`; se depender, usar o mesmo filtro sobre o bestiário com `regiao`.
7. Anotar no §9.

### Etapa 1 — Serverless (R1–R4)

1. **Testes** (`test_spec387_scene_cards_cold.py`): `test_rehydrate_registers_scene_cards`, `test_cold_instance_view_has_name_and_cost`,
   `test_cold_instance_play_accepted`, `test_lru_eviction_survives`, `test_orphan_card_never_shown_raw`, `test_old_save_without_scene_loads`.
2. **Implementação:** `scene_cards.rehydrate`, chamada em `_raw_to_state`, órfão em `sync_hand`/view.

### Etapa 2 — Retrato (R5–R9)

1. **Testes:** `test_price_failure_not_cached`, `test_checkout_retry_once_price_registry_switches`, `test_execute_error_not_retried`,
   `test_offer_omitted_event_cause`; front `web/tests/spec387-portrait-optimistic.test.mjs`; e2e `spec387-portrait-optimistic`:
   chip "Gerando retrato…" ≤ 100 ms depois de "Gerar" com cotação atrasada 1 s; botão com `disabled`; 503 na cotação devolve a oferta;
   cotação maior + cancelar devolve a oferta.
2. **Implementação:** `api.py`, `kill_switches.py`, front.

### Etapa 3 — Spawn genérico e rotas (R10–R16)

1. **Testes:** `test_generic_name_picks_regional` (Pântano, Floresta, 20 `game_id`s), `test_specific_hint_unchanged`,
   `test_no_fallback_from_contentless_name`, `test_classify_groq_120b_antes_do_20b`, `test_no_dead_groq_model_in_routes_or_fixtures`,
   `test_router_exhausted_opens_combat_with_cited_target`, `test_router_exhausted_without_citation_story`.
2. **Implementação:** `agents/combat.py`, `llm_setup.py`, `AGENTS.md`, fixture 368.

### Etapa 4 — Motor: jogada inelegível e objetivo (R17–R20)

1. **Testes:** `test_plan_plays_refuses_known_only_card`, `test_refusal_line_visible_no_cost`, `test_engine_refusal_catalog_is_human`,
   `test_protect_target_must_be_actor`, `test_protect_old_save_not_failed`, `test_objective_failed_outcome_text`.
2. **Implementação:** `cards.py`, `card_piles.py`, `round_log.py`, `scene_cards.py`, `agents/combat.py`.

### Etapa 5 — Seeds (R21–R25)

1. **Testes** (`test_spec387_seed.py`): uma por variante de R21/R23, cada uma com 50 sementes de `random`.
2. **Implementação:** `spec368_seed.py` (receitas, `_learn`, busca de semente do presságio, Esquiva baixa).

### Etapa 6 — Texto e UI (R28–R35)

1. **Testes:** `test_mech_log_rachadura_pct`, `test_condition_line_order`, `test_phase_line_once_all_surfaces`,
   `test_extra_action_without_target_silent`, `test_pressagio_cumprido_names_card`, `test_subclass_label_human`,
   `test_off_fallback_no_ids_no_bullets`, `test_off_prose_with_hero_name_falls_back`, `test_pact_refusal_cites_batch`,
   `test_place_as_actor_rejects_smoke_text`, `test_place_as_actor_benign_corpus`; e2e `spec387-omen-390`.
2. **Implementação:** arquivos do §3.2.

### Etapa 7 — `draft.py` (R26, R27)

1. **Testes:** `test_alvo_literal_rejects_aliado`, `test_prompt_has_escala_and_budget`, `test_repair_called_once`,
   `test_counts_reported`, `test_printed_commands_parse`, `test_mock_llm_empty_batch_unchanged`.
2. **Implementação:** `scripts/cards/draft.py`.

### Etapa 8 — Guardas (R36–R41)

`test_spec387_guards.py` (flags, golden, eval, scripts de lint/sim/promote, `web/e2e` existentes sem diff); `npm run typecheck`,
`typecheck:e2e`, `lint`, `test`; `ruff format --check .` e `ruff check .`. Expected de teste antigo que mudar entra no §9 com motivo.

## 5. Critérios de aceite

- [ ] Etapa 0 anotada no §9 (causa de S6-2, S6-4, L1, L5, L8, L9)
- [ ] S6-1: instância fria mostra e aceita a Carta de cena; LRU e órfão cobertos (R1–R4)
- [ ] S6-2: falha não fica em cache; 1 retry de checkout; causa medida (R5–R7)
- [ ] S6-3: chip "Gerando retrato…" no clique, `disabled` real, desfaz no erro/cancelamento (R8, R9)
- [ ] S6-4: nome genérico vira criatura da região; nenhum `fallback_*` de nome vazio (R10–R12)
- [ ] L1: CLASSIFY com Groq que faz tool call; nenhum modelo morto em rota/fixture/AGENTS; roteiro por `RPG_ROUTES` (R13–R16)
- [ ] L2: Carta inelegível recusada antes de gastar, com linha visível (R17, R18)
- [ ] L3: `proteger` só com alvo ator; desfecho de objetivo falho narrado pela causa (R19, R20)
- [ ] L4/L5 e "não verificado": seeds corrigidas e 9 variantes novas, 50/50 sementes (R21–R25)
- [ ] L6: `draft.py` com vocabulário no schema, reparo 1×, contagem e comandos certos; gate intocado (R26, R27)
- [ ] L7–L14: textos e UI (R28–R35)
- [ ] Guardas R36–R41
- [ ] `uv run pytest` verde (suíte completa, coordenador, no pouso); front `typecheck`/`lint`/`test` verdes; e2e novos verdes a 390 e 1440
- [ ] Guard de FallbackLLM mantido; nenhum `with_structured_output` novo no jogo
- [ ] Saves antigos carregam (R41)
- [ ] Revisão independente `Sol` sem P0/P1 aberto
- [ ] **Smoke real §6 (coordenador)** registrado em `docs/spec387/smoke.md`

## 6. Smoke test com LLM real (curto; só os achados e os "não verificado")

DeepSeek primário. Registrar provider/modelo, chamadas e custo em `docs/spec387/smoke.md` (trechos, sem segredos). Teto: ~25
turnos com LLM no total, ≤ 1 retrato pago, ≤ 1 execução de `draft.py`.

**Staging** (`hosted-supabase`, preset com cartas `on`, conta sintética pelo caminho de `two_user_smoke`, limpeza no fim;
`image_generation` ligado só no item 3 e conferido desligado com `list`):

1. **S6-1 (R1–R3):** abrir combate em local com objeto de cena (Costa Negra, Poço Negro, como no smoke 6). Recarregar
   `/game/state` 5 vezes (1440, 390, 1440, 1280, 1440): a Carta de cena sempre com nome e custo 1. Jogar a Carta de cena com alvo:
   200, linha no registro, sem 409.
2. **S6-2 (R5–R7):** na mesma partida, 6 recargas: a oferta "Gerar retrato" presente em todas; se faltar, anotar o
   `offer_omitted.cause` dos logs.
3. **S6-3 (R8, R9):** "Gerar" a 1440 → em ≤ 100 ms o chip mostra "Gerando retrato…" e o botão some/fica `disabled`; `/art/quote`
   1×, `/art/confirm` 1×; 1 débito ≤ cotação.
4. **S6-4 (R10):** 2 aberturas no Pântano da Melancolia e 1 na Floresta dos Sussurros com `RPG_CREATURE_GEN` off: nenhum
   `fallback_criatura_hostil`; o inimigo é do bestiário da região.

**Local** (`legacy`, mesmo preset, saves de `seed_save`; rodadas do meio sem LLM):

5. `seed_save(2, variant="frustrar")`: 1 rodada → presságio frustrado no chip e no registro.
6. `seed_save(3, variant="eco")` e `seed_save(3, variant="rachadura")`: Eco com acerto; `mech_log` com "Rachadura +25 %" e a linha da
   condição antes do ataque do inimigo (R28).
7. `seed_save(5, variant="chefe_fase")`: 1 rodada → linha da fase de Valerius no registro e no Livro; nenhum "Ataque sem alvo
   válido." (R29).
8. `seed_save(13, variant="voto")`, `"armadura"`, `"reacao"`, `"condicao_carta"`: Voto em Ketil ("muda de alvo"/"resiste");
   Armadura Comprometida no chip e no registro, nunca o id; vitória com Reação citando o autor; "A condição X de Y terminou." (R13
   da 367).
9. `seed_save(3)` com a Carta **só** conhecida (variante de teste `3 inelegivel`): jogada recusada com
   "… não está no seu baralho." e nada gasto (R17, R18). `seed_save(4)`: escolta jogada até o fim; se o objetivo falhar,
   a narração conta a causa, sem desmaio (R20).
10. `seed_save(14, variant="entrega")`: 1 turno "Entrego a prova da caça ao contratante" → `quest_completed` e a técnica no
    Acervo. Se o narrador não fechar a quest, anotar (R23 cobre offline).
11. `seed_save(15, variant="vg_ouro")`: "Compro a <Carta> com minhas últimas moedas" (saldo final 30) → se a prosa disser
    "últimas moedas", `trade_prose_rejected` no log e o texto do mercador no lugar; anotar qual dos dois ocorreu. Conferir também
    que a prosa não põe "Skallgard" como sujeito (R35).
12. Router esgotado (R13–R16): API com
    `RPG_ROUTES='{"classify":[["groq","openai/gpt-oss-120b"],["groq","openai/gpt-oss-20b"]],"fast":[["groq","openai/gpt-oss-120b"]],"smart":[["groq","openai/gpt-oss-120b"]]}'`,
    `seed_save(12)` e "Ataco o goblin" → combate abre pelo CLASSIFY do Groq. Depois
    `RPG_ROUTES='{"classify":[["groq","modelo-inexistente"]]}'` → `hostility_fallback` (narração citou o goblin) abre o combate.
13. Modo `off` com `RPG_ROUTES` de modelo inexistente em FAST: 1 rodada → texto sem id, sem "⚔️ •", sem nome do herói (R33).
14. `draft.py` (1 chamada SMART + até 1 de reparo):
    `bash scripts/dev/py.sh scripts/cards/draft.py --postura "Médico de Campo" --subclasse boticario --n 4 --raridades comum --onda 387`
    → seguir os 3 comandos impressos; registrar pedidas/entregues/rejeitadas e custo. Esperado: ≥ 1 Carta válida no lint.
15. UI a 390: presságio visível acima da barra fixa (R32); Acervo com "Mão Sombria" (R31); "Presságio cumprido: <inimigo> — <Carta>" (R30).
16. Varrer o `/game/history` das campanhas: 0 ids, 0 nome do herói, 0 `": … terminou"` cru, 0 "cumpre o presságio".

## 7. Riscos & compatibilidade

- **R1 no load:** custo de montar as Cartas de cena a cada load (≤ dezenas de objetos, sem I/O). Cena com objeto malformado
  não quebra o load (`try` + `log_fallback`). A colisão entre partidas no LRU é inofensiva: o id inclui o hash do objeto.
- **R6 com retry:** só no checkout, sem duplicar escrita; latência extra só no caminho de falha.
- **R8 otimista:** se a confirmação der certo, o servidor já está `pending`; erro devolve a oferta; `shouldHidePortraitOffer`
  continua mandando esconder nos casos de hoje.
- **R10 muda o elenco de aberturas genéricas.** É intencional (o dono pediu criaturas físicas da região). Risco: perigo da região
  acima do esperado numa abertura; o filtro de perigo de `fauna._fits_danger` e o orçamento de encontro (`_apply_encounter_budget`)
  continuam valendo.
- **R13 muda a ordem do fallback CLASSIFY.** `gpt-oss-120b` é mais lento que o 20b no Groq; só entra quando o DeepSeek falha.
  Limites do free tier do Groq por modelo podem diferir; o §6 item 12 mede.
- **R17 recusa antes** uma lista que hoje "passava" e falhava em silêncio. Nenhuma Carta jogável deixa de ser: o predicado é o mesmo
  do `use_card`. Teste de não-regressão com Sussurro, Cartas de Virtude, básicas e Carta de cena.
- **R19 pode tirar o objetivo de cenas que o LLM montou com um NPC que não vira ator.** Hoje essas cenas falham na rodada 1;
  depois viram `derrotar_todos`. D-387-8 é a alternativa (materializar o aliado).
- **R20 muda o texto do desfecho de objetivo falho**, não o `outcome` salvo (`defeat`). Crônica e manifesto seguem iguais.
- **R29/R33 mexem em `round_log` e no fallback `off`.** O golden da 330 é do motor `legacy`; a guarda R40 prova que não muda.
- **Sobreposição:** 367/368 já pousadas; esta spec toca `agents/combat.py`, `api.py`, `round_log.py` e o orquestrador, como elas.
  O guard `tests/test_spec367_guards.py` só vale na branch `spec-367` (skip fora), então não bloqueia.
- **Saves:** nada novo persistido além de `carta_id` em `pressagios_cumpridos` (aditivo, efêmero por rodada).
  **MockLLM/FallbackLLM:** guard mantido. **Quota/latência:** nenhuma chamada nova no jogo; `draft.py` +1 chamada máx.

## 8. Decisões

### Do dono / coordenador (prompt de 03/11)

- Escopo: todos os achados do 6º smoke (S6-1..S6-4, local 1–14), P3 inclusive, e as cenas "não verificado" tornadas verificáveis
  por seed, para fechar o épico.
- Integridade de eval: avaliador, sim, arena e limiares intocados; em `draft.py`, só gerador/prompt/roteiro/documentação.
- Golden 330, `web/e2e/contracts` e e2e existentes intocados; sem flag nova; 0 LLM por rodada.
- Aprovação (03/11, coordenador sob "manda bala"): D-387-1..11 seguem as recomendações abaixo; o dono pode vetar qualquer uma (em especial D-387-3, que muda o inimigo que aparece).

### Pendentes do dono (com recomendação do autor)

- **D-387-1 — Como a Carta de cena sobrevive a outra instância.** (a) **Recomendado:** reidratar no load a partir da cena salva
  (R1), sem mudar o schema do save; os ids já são determinísticos. (b) Persistir as definições em `combat.cartas_cena` no save
  (mais robusto a mudança de catálogo entre deploys, mas é dado novo no save e duplica a fonte).
- **D-387-2 — Cache da leitura de preço.** (a) **Recomendado:** nunca guardar falha (R5). (b) Guardar falha por 5 s (menos
  carga no banco em pane, oferta some por até 5 s).
- **D-387-3 — Nome genérico no spawn.** (a) **Recomendado:** criatura da região, escolha determinística (R10), sem LLM e sem
  poluir o bestiário/pool com "criatura hostil". (b) Aceitar a espécie que o gerador legado inventar para o nome genérico (gasta
  1 chamada e grava espécie nova a partir de um nome vazio).
- **D-387-4 — Modelo Groq do CLASSIFY.** (a) **Recomendado:** `openai/gpt-oss-120b` antes do `openai/gpt-oss-20b` (o 120b
  respondeu no smoke; o 20b falhou tool call no router). (b) Trocar o 20b por outro modelo do catálogo Groq que o dono indicar,
  verificado no §6 item 12. (c) Manter como está e só corrigir o roteiro. Nenhuma opção chama rede em teste.
- **D-387-5 — `load_dotenv(override=True)`.** (a) **Recomendado:** manter (o `.env` é canônico e protege contra chave velha no
  SO); simular falha por `RPG_ROUTES`. (b) `override=False` (variável do SO vence; risco: chave antiga no Windows do dono passa a
  valer em silêncio). Qualquer mudança aqui entra no §7 como risco.
- **D-387-6 — Nome do herói na prosa `off`.** (a) **Recomendado:** instrução no prompt + rejeitar a prosa com o nome e usar o
  fallback determinístico (R33). (b) Só a instrução.
- **D-387-7 — Default do `promote`.** (a) **Recomendado:** manter `--protocolo lote` e passar `lote-v2` explícito no roteiro
  (R27), porque mudar o default do gate é mudança de avaliador. (b) Mudar o default para `lote-v2` numa tarefa separada, por
  quem não otimiza o produto.
- **D-387-8 — `proteger` com alvo que não é ator.** (a) **Recomendado:** derrubar para `derrotar_todos` (R19). (b) Materializar
  o NPC da cena como aliado ator (mantém o objetivo, mas muda balanço e exige ficha de combate do NPC).
- **D-387-9 — Barra fixa a 390.** (a) **Recomendado:** reservar a altura da barra no fim do contêiner (R32). (b) Mover a linha do
  presságio para cima da mão.
- **D-387-10 — Reparo no `draft.py`.** (a) **Recomendado:** 1 chamada extra de reparo por execução (≈ US$ 0,002). (b) Sem
  reparo; só schema e prompt.
- **D-387-11 — Texto do presságio cumprido.** (a) **Recomendado:** "Presságio cumprido: Goblin — Pancada de Tronco" (R30).
  (b) "Goblin cumpre o presságio: Pancada de Tronco" (exige mudar `deck.ts` e o teste de front da 354).

Nenhuma bloqueia a Etapa 0. As Etapas 1, 3 e 4 dependem de D-387-1, -3/-4 e -8; o executor segue a recomendação se o dono não
vetar até a aprovação.

## 9. Registro de implementação

Branch `spec-387`, 6 commits de executor (ver `git log`). Testes novos: `tests/test_spec387_*.py` (10 arquivos),
`tests/fixtures/spec387_{rounds,smoke}.py`, `web/tests/spec387-portrait-optimistic.test.mjs`,
`web/e2e/spec387-{portrait-optimistic,omen-390}.spec.ts` (verdes a 390 e 1440, `--workers=1`).

**Etapa 0 (sem acesso à Vercel/logs do staging; o que deu para confirmar no source):**
- S6-1: o teste `test_cold_instance_*` reproduz o `name == id` com `_TEMP_CARDS` limpo (id órfão do catálogo).
- S6-2: **não confirmado** qual das 3 leituras disparou no staging (sem logs). A correção cobre as três (R5, R6) e
  `creature_portrait.offer_omitted` passa a medir a causa (`price_peek_failed | registry_read_failed | image_gate_failed |
  switches_unreadable`) para o §6 item 2.
- S6-4: confirmado no source (`name_tokens("Criatura hostil") == []`). Narração/flavor das 3 aberturas: **não verificado**.
- L1: o save do item 10 não está aqui; R16 virou só teste (a regra 355 R5 se mostrou intacta nos dois sentidos).
- R10 (item 6 da Etapa 0): `fauna._region_candidates` **não depende de `RPG_FAUNA`**, mas `data/world/fauna.json` só cobre
  `nova_arcadia` (38 criaturas). Para as outras 11 regiões `services/generic_spawn.py` usa o MESMO filtro sobre o bestiário
  (`regions` ∋ região, sem chefe, `fauna._fits_danger`), preferindo as de `familia_valoria` (criaturas físicas) quando a região as tem.
- L5: o goblin a 1 de Vitalidade previa `fugir`; a `13 reacao` agora prevê o ataque ANTES de baixar a Vitalidade
  (`late_vitality`). L8: a ordem da Rachadura confirmada (linha vinha depois do ataque do inimigo). L9: a ação extra de
  Valerius resolve um ataque básico (não é "sem alvo") na seed `5 chefe_fase`; a limpeza de R29(b) vale quando de fato não resolve.

**Desvios / decisões do executor (todos pequenos):**
1. R6: o critério de falha de checkout foi MOVIDO para `services/checkout_retry.py` (a 367 tinha em `scripts/staging/ops_pool.py`,
   que agora importa de lá; mesmo critério, uma só fonte).
2. R7: o helper se chama `log_offer_omitted` (o guarda `test_no_silent_except` só aceita nomes com "log"). O evento é `creature_portrait.offer_omitted`.
3. R8: `snapshotPortraits` (helper extra) devolve o `retrato` anterior por id; `withPortraitRestored(data, enemyId, snapshot)` só desfaz os
   inimigos ainda "gerando". `--play-end-h` foi declarado em `styles.css` (o teste `deck-tokens-342` exige token definido).
4. R10/R11: `_grounded_template` só troca o EVENTO (`spawn_generic_name`) quando o nome é vazio e não há candidato regional; com candidato
   o spawn nem chega lá. `meta.source = "regional_generic"` e a narração de entrada usa o nome da criatura.
5. R19: `check_objective` com alvo não-ator também troca `scene["objetivo"]` por `derrotar_todos` (para o evento não repetir por rodada).
6. R20: `out["objetivo"]` ganhou `motivo` (aditivo) e o rótulo `objective_failed` só existe dentro de `_narrate_outcome`/`round_log`.
7. R21/R23: seeds. `15 vg_ouro` grava saldo = preço da Carta mais barata + 30 (preço 50 hoje → saldo 80, final 30, como no §2). `13 armadura`
   usa o Soldado da Legião de Ferro + `evolved_cards["cor_ino_fadiga"]="B"` (a Ruptura A é dano; só a B aplica Armadura Comprometida).
   `13 condicao_carta` usa a Carta neutra `neu1_er_lanca_de_gancho` (única Carta ativa de herói com condição de 1 rodada que serve a
   Devoto); a condição "terminou" só aparece na rodada seguinte (o §6 item 8 cobre). `2 frustrar` usa `arc1_des_estouro_contido`
   (Arcanista; Atordoado frustra o presságio: confirmado em `pressagios_frustrados`).
8. R22: Esquiva baixa por `esquiva_penalidade = 30` (acerto certo), presságio por busca de semente em `forecast_round` (`want_alvo`).
9. R27: `to_card`/vocabulário não mudam; `alvo` ganhou só `enum` no JSON schema (parse tolerante: uma Carta fora do vocabulário NÃO derruba o lote).
10. R28: a linha "ganha a condição X" agora vem logo depois da jogada que a aplicou (lida da ordem de `logs`). Isso também move
    "Defesa Instintiva" etc. para depois do ataque do próprio inimigo que a aplicou.
11. R29(b): feito na ORIGEM (a ação extra sem efeito não emite "age de novo." nem "Ataque sem alvo válido."); a regex de `_HUMAN_LINE_RES`
    não mudou (o texto genérico continua humano para o herói).
12. Achados extras que apareceram ao montar as seeds e foram corrigidos pequeno: Provocação que NÃO desvia agora diz
    "X resiste à provocação de Y." (§6 item 8 espera "muda de alvo"/"resiste"); "Armadura_comprometida" vinha cru no registro
    (`_cap_cond` usa o rótulo do glossário); `Carta '<id>' desconhecida.` (com id) virou "Essa Carta não existe mais.".
13. R18: o catálogo de recusas ganhou regex para `já foi usada (`, `Entropia insuficiente`, `só pode ser jogada 1× por rodada.`, Fardo,
    descarte e silenciado, além das duas frases novas.

**Testes antigos alterados (motivo):** `tests/test_spec368_seed.py::test_every_combat_item_has_a_seed` (item 15 novo);
`tests/test_enemy_intent.py::test_on_executes_frozen_intent` (`pressagios_cumpridos` ganhou `carta_id`, R30);
`tests/test_spec363_golden_guard.py::test_engine_modules_untouched_by_spec363` (guarda de pouso da 363 passa a valer só na branch
`spec-363`, como a da 367; a R30 muda o orquestrador de propósito). `tests/size_budget.json`: baseline atualizada (arquivos de motor
que a spec manda tocar; o código novo grande foi para módulos novos).

**Pendências 6a/6b (corrigidas a pedido do coordenador, 03/11):** (a) o registro mostra "Presságio frustrado: Goblin" (sem id e SEM
a Carta, que ainda está oculta porque não foi jogada); teste `test_frustrated_omen_line_in_registry`. (b) Atacante derrubado pela Reação
resolvia o próprio ataque: era **bug**, não regra (SPEC-232 R3 só proíbe revide sem atacante vivo ANTES; nenhuma regra manda resolver o
ataque de quem já caiu). Em `_resolve_actor_turn_inner`, `if not _can_act(actor): return` depois da janela de Reação (commit separado, fácil
de reverter). Golden 330 e 453+223 testes de motor/sim verdes; **a arena não foi rodada**: só muda em rodadas em que uma Reação derruba o atacante
(raro), mas o coordenador decide se rebate a arena. Ainda fora do escopo: `ruff format --check .` acusa os specs 377–379 (`.md`, já na base).

**Fica para o smoke §6 (coordenador):** itens 1–16 inteiros — nenhum foi rodado com LLM/staging reais aqui. Em especial 2 (causa de
`offer_omitted`), 3 (latência do chip ao vivo), 4 (aberturas no Pântano/Floresta), 12 (Groq 120b faz tool call no router) e 14 (`draft.py` real).

**Correções da revisão Sol (rodada 1, 03/11):**
- P1-1: `round_log._translate_logs` traduz o registro técnico do modo `off` (golpe, ferimento, Vitalidade 0, fuga, "terminou") em
  frases na voz "você", sem descartar fatos, sem id, sem aritmética e sem o nome do herói; reaproveita `_voce`, `_cat_pt`,
  `_region_phrase`. Teste `test_off_fallback_keeps_the_facts_of_the_round` (logs reais do golden 360).
- P1-2: atacante que cai na janela de Reação (ou na AoO) sai de `pressagios_cumpridos`, entra em `pressagios_frustrados` (motivo `incapaz`),
  perde a linha "cumpre o que o presságio anunciava." e não aparece no quadro com Carta; o registro diz "Presságio frustrado: Goblin"
  (`_retract_omen`; asserções na seed `13 reacao`, 50 sementes).
- P1-3: `tests/test_objectives.py::test_run_round_encerra_com_desfecho_proprio` ganhou `"motivo": "Vocês resistiram por 2 rodadas."` na
  igualdade exata: `out["objetivo"].motivo` é campo ADITIVO da R20 (nenhum consumidor existente lê chaves a mais).
- P2-1: `test_cold_instance_play_via_api` (catálogo vazio e LRU com 63 Cartas): POST `/game/action` 200, linha "Empurrar (Poço Negro)" no
  registro e dano no inimigo. P3-1: o evento `combat.scene_card_orphan` é afirmado (1 evento, sem id). P3-2: `spawn_generic_name` é alcançado
  (sem candidato regional o fallback de hoje segue, documentado) e, com candidato, nenhum `fallback_*` nasce. P3-3: o teste compara a
  regra de complexidade do prompt com `card_lint.check_raridade`; `_examples` perdeu os parâmetros sem uso. P3-4: o e2e a 390 mede
  primeiro na rolagem padrão e de novo rolado até o fim.
- P3-5 (notas que faltavam): (a) o golden `spec360_flags_off_golden.json` MUDA de propósito (R33 + P1-1): derrubam `test_spec360_flags_off.py::
  test_golden_flags_off_byte_identico` e `test_spec371_flags_off.py::test_golden_360_inalterado_com_a_flag_off`; só 3 mensagens do fallback
  `off` (fuga + golpe do Crescido do Clã, 2 delas sem ferimento, 1 com 2 ferimentos e Sangramento) mudam, o resto do fingerprint é idêntico;
  o coordenador regrava (`SPEC360_REGEN=1`). (b) `test_objectives` (P1-3). (c) `tests/size_budget.json` teve 2 rebaselines: `4e246c45` (motor,
  App.tsx) e `4ceb5f94` + este (`_resolve_actor_turn_inner` +2 do `_can_act` pós-Reação, `round_registry` +3 do presságio frustrado,
  `round_log` +tradutor): exceções previstas ("spec manda tocar o motor").

**Correções da revisão Sol (rodada 2, 03/11):**
- R2-P1-1: `_translate_logs` agora diz quem usou cada Carta ("Você usa X." / "<Inimigo> usa X."; o herói reconhecido pelos nomes das suas
  Cartas via `round_log.hero_card_names(player)`), mantém linhas humanas com número (cura "Você recupera 3 de Vitalidade.", dano contínuo
  "Você sofre 1 de Sangramento.") e descarta só aritmética de dado/ids. `test_spec387_text.py` troca "sem dígito" por "sem aritmética e sem id"
  e ganha a sonda com Carta de cura + golpe + Sangramento (`test_off_fallback_keeps_cards_heal_and_dot`).
- R2-P2-1: helper comum `_fire_omen_frustrated` (usado por `_frustrate` e `_retract_omen`): matar o atacante pela Reação dispara
  `ao_pressagio_frustrado` uma vez (teste com "Ferro Antes do Ferro" armado: cura 5 -> 8 em 10 sementes). Decisão: dispara.
- Golden 360: as 3 mensagens (12, 14, 20) mudam como no §9 anterior, agora com "Crescido do Clã usa Punho de Tala." e, na 20, "Você sofre 1 de Sangramento.".

**Correções da revisão Sol (rodada 3, 03/11):**
- R3-P1-1: o autor de "Usa X" no fallback `off` vem de `out["cards_used"]` (em ordem, `actor_id`), casando cada "Usa X" com a próxima entrada
  daquela Carta; sem correspondência a frase não tem ator ("X é usada."), nunca "Você" por padrão. `off_text.context`/`context_from` montam o contexto;
  `hero_card_names` foi removido. Testes: apoio inimigo + linha sem sujeito, duas Cartas inimigas seguidas, Carta homônima do herói e do inimigo.
- R3-P2-1: `round_log` não reexporta mais `off_text` (sem ciclo); `import services.off_text` e `import services.round_log` rodam em interpretador limpo.
- R3-P3-1: `off_text.for_round` monta os argumentos; `_narrate` voltou a ≤ 100 linhas e saiu da baseline do `size_budget.json`.
