# SPEC-363 — Cartas: correções do 3º smoke real (retrato pago coerente, texto de morte, autoria do resumo, mira, fuga, ids e cenários raros)

> **Status:** `done` (02/11, coordenador, autorização do dono "manda bala"; fechamento na nota final da última seção)
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Épico:** SPEC-327
> **Origem:** smoke 3 real de 02/11 (`main` = staging `b4f35507`, DeepSeek `deepseek-v4-flash`, 29 turnos + 3 criações, local e staging) — [docs/spec363/achados-smoke3.md](../docs/spec363/achados-smoke3.md). Evidência bruta no scratchpad do coordenador (`scratchpad/smoke3/`: `server.log`, `out/state-*.json`, `out/hist-*.json`, `out/*.png`, `stg1/`, `stg2/`).
> **Depende de:** código das SPEC-342, 345, 346, 347, 352, 353, 354, 355, 357 e 362 na `main` (todas pousadas; o status `done` delas espera o §6 desta spec ou o próprio).
> **Desbloqueia:** fechar o §6 da SPEC-352 (retrato pago, hoje BLOQ) e os §6 pendentes de 345/346/353/354/355/357/362; smoke 4 de liberação das flags de cartas.
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (gate de efeito pago, prompt e validação do resumo, contrato da API, latência do roteador)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected de eval, baseline ou dataset de regressão muda. O golden da SPEC-330 fica byte a byte (R47).

Rótulos: **[F]** fato no source (worktree `rpg-spec-363`, `main` em `ebcc6cc1`) · **[H]** hipótese com evidência, que a Etapa 0 ou o 1º teste confirma ou derruba · **[D]** decisão (§8).

---

## 1. Contexto & Objetivo

O 3º smoke real confirmou o que importava do épico de cartas: **0 chamada de LLM nas 12 rodadas de meio de luta**
(p50 114 ms local; 0,7–1,0 s no staging), abertura e desfecho dentro do orçamento, ordem igual nas três
superfícies, `/game/history` íntegro. Mas achou 2 P1, 5 P2 de produto (o P2-6 é balanço e fica com o dono) e 8 P3,
e deixou uma lista de itens **não verificados** porque o jogo real não sorteou o cenário (objeto de cena, iniciativa
contra emboscada, fuga concluída, cartas alteradas do Arcanista, modo `off`, router esgotado, quest de lore,
Leitura de Pressão etc.).

O objetivo é **zerar a pendência do smoke 3**: corrigir todos os P1/P2/P3 de produto, provar por teste
determinístico (seed/fixture) cada cenário que o smoke real não alcança, e deixar o §6 desta spec curto e focado
só nos achados. Princípios: **mecânica é Python**; **nenhuma chamada de LLM por rodada** (a regra da SPEC-346 e
da memória do dono continua: a IA só abre o tabuleiro e resume o fim); o resumo final continua recebendo fatos
estruturados e passando por validação determinística com fallback; **oferta paga coerente com a capacidade real**
(nunca oferecer o que a cotação vai recusar); golden da SPEC-330 intocado; sem flag nova.

### 1.1 Achados e causa no source

| # | Achado (prioridade) | Evidência do smoke | Causa no source |
|---|---|---|---|
| 1 | Retrato pago oferecido (`retrato.gerar`) mas a cotação responde `503 image_generation_disabled`; a 390 o chip não mostra "Gerar retrato" (P1) | `stg1/stg_log.jsonl` (`portrait_offer`, `quote`), `out/stg-board-390.png` | **[F]** A oferta passa por `api._creature_art_live` (`api.py:2851-2859`: flag `RPG_CREATURE_ART`, perfil com banco, `RPG_DYNAMIC_ART_ENABLED`) e `creature_art.portrait_for` (`services/creature_art.py:230-232`: flag + preço). A cotação passa **também** por `_guard_image_effect` (`api.py:4801-4813`): kill switch `image_generation` (`services/kill_switches.py:187-192`) e `require_paid_effect("image")` (rate card fresco, `services/finops_alerts.py:423-439`). A oferta não consulta nenhum dos dois. O 503 `image_generation_disabled` só sai de `SwitchOff` (`api.py:4810-4811`), logo **o switch `image_generation` estava desligado no staging**. **[H]** Causa provável: o teto diário (`RPG_DAILY_SPEND_CAP_BRL=5` com `RPG_DAILY_SPEND_CAP_TEXT=1`, `scripts/staging/vercel_env.py:50-51`) estourou num dia de smokes de texto e o cron desligou o switch, que **nunca religa sozinho** (`services/daily_spend_cap.py:1-13,219-230`). Alternativas a descartar: env `RPG_KILL_SWITCHES_OFF` (`kill_switches.py:127-130`), fail-closed por store ilegível com teto configurado (`kill_switches.py:119-123,180-182`), linha deixada pelo drill (`scripts/staging/incident_drill.py:84-105,140-141`). Tela: **[F]** `TargetChip` só renderiza a oferta quando **não** há mira ativa (`web/src/combat/TargetChip.tsx:103-108`); com mira, o chip vira `<button>` sem a oferta (`:111-123`). **[H]** o print a 390 foi tirado com uma Carta armada |
| 2 | Texto de morte do staging: "Você tomba. Goblin tomba. SmokeA cai. SmokeA perde os sentidos. Você carrega ferimento crítico na perna, ferimento crítico no braço." (P1) | `stg2/stg_log.jsonl` (A-r5), `stg2/stg_state_A_end.json` | **[F]** É o fallback `round_log.deterministic_outcome_text` (`services/round_log.py:591-621`). (a) "SmokeA": `_no_digits` roda sobre o **texto inteiro** (`:621`, função em `:549-555`) e arranca o "3" de "Smoke3A". (b) Herói 3×: o lead "Você tomba." (`:604`) + `player_summary_text(conflict_summary)` (`services/conflict_summary.py:335-346`), que lista o herói por nome em `caidos` **e** em `inconscientes` — `inconscientes` inclui por construção todo `caido` (`conflict_summary.py:183-188`); a crônica mostra o mesmo ("Caídos: Smoke3A. Inconscientes: Smoke3A.", `stg_state_A_end.json:961`). (c) "Goblin tomba": `mortos` é do conflito inteiro, não da rodada final; o Goblin caiu na rodada 2. (d) Ferimentos: **[H, contraria o achado]** `player_stats.ferimentos.critico` = perna + braço (`stg_state_A_end.json:19-35`); o "na perna" do `last_action.region` (`:803`) é a região do golpe do herói, mas a ficha do herói também tem perna. A Etapa 0 confirma pelo histórico se a perna do herói é real. Por que caiu no fallback com 2 chamadas LLM bem-sucedidas: **não há como saber** — a rejeição por `validate_narrative_text` não emite evento (`agents/combat.py:1967`), só a de autoria (`:1971-1973`) e a de orçamento (`:1959-1961`), e nenhuma das duas aparece no log |
| 3 | Mira em inimigo escondido com Carta básica: o chip aparece válido e a rodada inteira volta `409 invalid_target`; a fila continua apontando para o mesmo alvo (P2) | `out/8029576-Mirela-r2-1440-4-pos-combate.png`, `server.log` (`09f640012c13`) | **[F]** `combat.cards` vem de `_cards_block(player, prepared_only=True)` (`api.py:3165`), então Cartas da mão fora das preparadas (`bas_*`) não têm `valid_targets`; o front cai em "todos os inimigos" (`web/src/combat/deck.ts:175-179`, chamado em `web/src/components/combat/DeckCombat.tsx:74-75` e `web/src/workspace/tabs/CombateTab.tsx:128-129`); o motor exclui o oculto (`services/combat_targeting.py:88-104`) |
| 4 | Resumo da vitória sobre o Mímico atribui ao herói o ferimento do inimigo ("fio de sangue… pelo seu braço"; herói 18/18) (P2) | `out/state-Haldor-a3.json` | **[F]** A linha de fato diz "Você atacou Mímico: acertou, ferimento leve no braço." sem dono do braço (`services/round_log.py:396-406,437`). O validador só procura marca de dano no herói **na mesma oração que uma Carta do herói** (V1, `services/conflict_summary.py:425-429`); a frase do Mímico não cita Carta e passa |
| 5 | Fuga em perseguição: `mech_log` diz "escapou" e a tela diz "Não escapou" (P2) | `out/state-Mirela-f1.json` … `f3.json` | **[F]** `_flee_line` usa `roll["sucesso"]` (`services/combat_preview.py:322-327`), que na perseguição significa "avançou um passo"; o veredito real está em `chase_state` (`escapou`/`alcancado`/`_last.sucesso`, `agents/combat.py:3306-3322`) |
| 6 | Ids internos no Livro: "com espada_gasta", "afastado → quase_livre" (P2) e "item_desconhecido: compra 30 / venda 15" na consulta do mercado (P3) | `out/hist-Haldor.json`, `out/hist-Mirela.json`, `out/state-Haldor-t6.json` | **[F]** `_weapon_name` devolve a string de `equipment.weapon` (id) sem catálogo (`services/round_log.py:178-183`); a trilha da fuga usa o id cru e o nome do herói (`agents/combat.py:3311-3321`; ids em `services/chase.py:29`; o front já tem rótulos em `web/src/components/SceneZones.tsx:6`); o mercado cota itens do inventário com `make_entry(item_id)`, perdendo o `display_name` dos itens livres `item_desconhecido` (`services/economy.py:639-657`; `inventory.py:21,68`) e o agente imprime o id quando falta nome (`agents/loot.py:470-477`) |
| 7 | "Quero comprar a Lança de Gancho da Forja dos Clãs" só responde o preço (P2) | `out/state-Haldor-t7.json` | **[F]** Gramática fechada: o `tail` aceita só "por favor/agora/então" (`agents/loot.py:378-391`) |
| 8 | Linhas de condição duplicadas, minúsculas e com o nome do herói ("Mirela: ganha condição cego"; "Smoke3A: condição Cego renovada" no `mech_log`) (P3) | `out/hist-Mirela.json`, `out/state-Mirela-*.json` | **[F]** O formato cru vem de `combat_mechanics.py:532` e dos logs do orquestrador (`services/conflict_orchestrator.py:351,400,2662`); a normalização "Você"/maiúscula existe só em `round_log._voce` (`services/round_log.py:186-206`). **[H]** o bloco das Cartas de Cena e o `mech_log` não passam por ela; a Etapa 0 localiza o emissor do bloco duplicado |
| 9 | Nome genérico "Criatura da Fogueira" e família "desconhecida" para o Goblin (P3) | `out/state-Haldor-*.json`, `stg2/stg_state_A_open.json:605` | **[F]** `family_of` = `enemy_decks.family_key(enemy) or "desconhecida"` (`services/creature_art.py:101-102`); `family_key` lê `arquetipo` **da instância** (`services/enemy_decks.py:144-152`), e o bestiário tem `enemy_goblin.arquetipo = "bruto"` (`data/bestiary.json:5073-5107`). **[H]** a instância em combate não carrega `arquetipo`. Nome: `hint_core` já corta oração relativa (`services/encounter_manifest.py:308-313`), então "criatura que ronda a fogueira" vira "criatura" (genérica); **[H]** o nome "Criatura da Fogueira" veio do gerador do bestiário/narração, sem a trava de cabeça genérica da SPEC-353 R16 |
| 10 | Resumo da Ilsa mistura "tu" e "você"; espólio "Moeda de Ouro e +24 de ouro" (P3) | estado da vitória da Ilsa em `out/state-Ilsa-*.json` e print `out/Ilsa-v3-390-full.png` | **[F]** O prompt pede "segunda pessoa" sem fixar o tratamento (`agents/combat.py:1931-1947`); nada valida a mistura. `moeda_ouro` é `type: currency`, `value_gold: 1` (`data/artifacts.json:2-7`) e entra como item ao lado do ouro (`agents/loot.py:635-642`) |
| 11 | Morte local: "Goblin morre." antes da Última Ação que o matou; `death.killer` = "Goblin" quando quem derrubou foi o Minotauro; mão, "Encerrar" e "Fugir" ativos por alguns segundos depois da morte (P3) | `out/state-Mirela-f4b.json`, `out/8694215-Mirela-f4-1440-2-pos.png` | **[F]** `_killer_identity` pega o **primeiro inimigo ativo**, não quem deu o golpe final (`agents/combat.py:1494-1503`, usado em `:3010,3018`), apesar de `out["final_blows"]` existir (SPEC-353 R7). Ordem: a Última Ação é "fora de turno" e vai para o fim (SPEC-353 R12), mas a queda que ela causa sai antes |
| 12 | Espólio ofereceu "Leitura Arcana" (utilitária) e ela entrou no Baralho; loja diz "só para o Acervo — Baralho cheio" para quem ainda não tem Baralho (P3) | `out/state-Ilsa-esp.json`, `out/7679990-Ilsa-loja-390-0.png` | **[F]** `roll_rewards` não filtra `tipo: utilitaria` (`services/card_rewards.py:155-197`); `_add_to_deck` devolve `"acervo"` tanto para Baralho cheio quanto para Preparadas cheias ou sem Baralho (`:277-296`), e o front traduz todo `acervo` como "Baralho cheio" (`web/src/cardRewards.ts:43-47`) |
| 13 | "Preparação 4/24" mistura Preparação com Baralho (P3) | `out/7404167-Haldor-esp-1440-3-pos-espolio.png` | **[F]** Com Baralho `on`, `prepared_slots` = `DECK_MAX` (`api.py:2453-2458`) e `player_stats.baralho` já existe (`api.py:2461+`), mas o Acervo ainda rotula "Preparação {preparadas}/{slots}" (`web/src/components/tabs/CombatDeckTab.tsx:40,45,91`) |
| 14 | Latência fora do combate: viagem 27,7 s; compra 17,2 s (timeout de 12 s do DeepSeek CLASSIFY antes do Groq); abertura da Mirela 14,1 s com 6 chamadas (P3) | `server.log`, `turns.cjs` | **[F]** Timeout DeepSeek = 12 s em qualquer tier (`llm_setup.py:484-489`); `enrich_node` roda ficha de NPC e replan **em série** (`agents/enrich.py:224-242`); o replan só lê o estado do plano (`agents/campaign_manager.py:426-457`) — **[H]** independente das fichas |
| — | Crítico por dupla abaixo da defesa, ~28 % com 3d10 (P2-6) | `mech_log` do smoke | **Balanço, decisão do dono** — ver §8 D-363-1. Sem requisito nesta spec |

### 1.2 Itens "não verificados" do smoke 3 (cenário raro)

O smoke real não sorteou: objeto de cena (353 §6.2), Carta de iniciativa contra emboscada, fuga concluída
(346 §6.4), cartas alteradas do Arcanista na mão (362 §6.4: `arc1_imp_truque`, `arc1_cal_pulso_medido`),
modo `off` (345 §6.1, 346 §6.7), router esgotado/CLASSIFY só no Groq (346 §6.5–6), quest de lore `justa` (357 §6.5),
Leitura de Pressão (`arc1_cal_leitura`, 355 §6.2), Voto Sussurrado com presságio no aliado (355 §6.1),
"Armadura Comprometida" legível (355 §6.3), Renegado sem "Descarga Arcana" (355 §6.4), vitória com Reação
(355 §6.5), "Vasculho o corpo" (346 §6.2), toast no instante da vitória a 1440 (354 §6.3) e cena com 2 inimigos **e**
aliado (354 §6.1). Esta spec os cobre com teste determinístico que força o cenário (R38–R39).

## 2. Requisitos

Todos com as flags de cartas `on` (`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_SCENE_CARDS`, `RPG_ENEMY_DECKS`,
`RPG_CARD_REWARDS`, `RPG_COMBAT_NONLETHAL`), salvo indicação. Em `off`, o fluxo fica como hoje.

### A. Retrato pago coerente com a capacidade (item 1, P1)

- **R1 — Causa registrada (Etapa 0).** Antes de qualquer código, o executor (com o coordenador para o acesso ao
  staging) determina **qual** das quatro causas desligou `image_generation` no staging: (a) linha no store com
  ator `system:finops` (teto diário), (b) `RPG_KILL_SWITCHES_OFF` no env da Vercel, (c) fail-closed por store
  ilegível com teto configurado, (d) linha deixada pelo drill. Fonte: `scripts/admin_kill_switch.py --dsn-env
  RPG_STAGING_DB_URL --env-file .env.staging audit --limit 20` (só leitura) e a lista de envs do projeto Vercel por
  **nome** (nunca valor). Registra em §9 a causa, o ator e a data. Também confirma se o chip a 390 estava com mira
  ativa no print (R3).
- **R2 — A oferta usa o mesmo portão da cotação.** `api._creature_art_live()` passa a exigir também
  `get_switches().is_enabled(IMAGE)` e que `require_paid_effect("image")` não levante (`PricingUnavailable` → sem
  oferta), reaproveitando a lógica de `_guard_image_effect` num predicado sem exceção
  (`_image_effect_open() -> bool`). Consequência: com o switch desligado, rate card vencido, arte dinâmica
  desligada ou sem preço, **nenhum** inimigo tem `retrato.gerar`; o retrato curado/registro/marcador continua.
  Contrato: para todo estado em que a view mostra `gerar`, `POST /game/{id}/art/quote` com o mesmo inimigo **não**
  responde `image_generation_disabled` nem `image_pricing_unavailable` (teste de propriedade sobre os 2⁴ estados
  das quatro condições).
- **R3 — Oferta visível também com mira.** Com `retrato.gerar` e `onGenerate`, o "Gerar retrato" aparece no chip
  com ou sem mira ativa (com mira, fora do `<button>` do alvo, como irmão, sem aninhar botões), a 390 e a 1440.
  Tocar na oferta não seleciona alvo nem dispara a fila.
- **R4 — Recusa da cotação apaga a oferta.** Se a cotação ainda assim responder 503 (`image_generation_disabled` ou
  `image_pricing_unavailable`, corrida de TTL), o front mostra o banner de erro já existente e esconde a oferta
  daquele inimigo até o próximo estado do servidor; nenhum débito.
- **R5 — Correção de staging versionada.** Conforme R1:
  - causa (b): remover a chave do preset/script versionado (`scripts/staging/vercel_env.py`) e reaplicar;
  - causa (a) ou (d): religar com `scripts/admin_kill_switch.py on image_generation --actor <coordenador> --reason
    "SPEC-363 smoke" --apply` (ação do coordenador, auditada); o valor do teto é decisão do dono (D-363-2);
  - causa (c): corrigir o acesso do runtime ao store (role/DSN) no script versionado que o configura.
  Em todos os casos, um **preflight versionado** `scripts/staging/art_preflight.py` (só leitura) devolve JSON
  `{switch_image, pricing_fresh, dynamic_art_env, creature_art_env, price_estilhas, ok, causa}` e o §6 roda antes de
  testar o retrato pago.

### B. Texto de morte e resumo final (itens 2, 4, 10 e 11; P1/P2/P3)

- **R6 — Nomes nunca perdem dígitos.** O pós-filtro de números do fallback (`_no_digits`) e das linhas de fato
  protege os nomes de participantes (herói, inimigos, aliados) antes de remover dígitos e os restaura depois.
  "Smoke3A", "Bandido 2" e "Anão-Eco 3" sobrevivem intactos; números mecânicos continuam sumindo.
- **R7 — O herói aparece uma vez no fallback.** `deterministic_outcome_text` nunca cita o herói pelo nome: o lead
  ("Você tomba.", "A escuridão fecha sobre você…") já o cobre, e o herói sai das orações de `mortos/caidos/
  inconscientes/…` montadas para o jogador.
- **R8 — Uma categoria por nome.** `player_summary_text` e `canonical_summary_text` listam cada nome **uma** vez, na
  categoria mais forte (mortos > capturados > rendidos > fugitivos > caídos > inconscientes). O
  `ConflictSummary` (dados, archivist, saves) **não** muda.
- **R9 — Quedas antigas no passado.** O fallback separa as quedas da **rodada final** (de `last_out`:
  `deaths`/`terminal`/`final_blows`) das anteriores do conflito; as anteriores vão no passado e depois do lead
  ("Antes, Goblin já tinha tombado."), ou somem se o resumo passar de 4 frases. Nunca "Você tomba. Goblin tomba."
  como se fosse o mesmo instante.
- **R10 — Ferimento com dono.** Toda linha de fato que cita ferimento diz de quem é: "ferimento leve no braço do
  Mímico" (inimigo/aliado) ou "ferimento leve no seu braço" (herói). Vale para `_event_result`, `outcome_facts`,
  o fallback e o registro da rodada (`round_registry`). O fallback "Você carrega …" lista só `player.ferimentos`
  (já é assim) — e a Etapa 0 registra em §9 se a perna crítica do herói no staging era real (§1.1 item 2d).
- **R11 — Validação V4: dano no herói sem fato.** `validate_attribution` ganha V4: oração com marca de corpo do
  herói (`seu/sua/teu/tua + região`, "pelo seu braço", "te atinge/rasga/fere", "seu sangue") quando os fatos dizem
  que o herói terminou **ileso** ou **sem ferimento novo naquela região** neste conflito → violação. O texto real do
  Mímico é rejeitado; um texto correto sobre o mesmo fato passa.
- **R12 — Validação V5: tratamento misto.** O prompt do resumo fixa "trate o jogador por **você** (nunca tu/teu/
  tua)". `validate_attribution` ganha V5: presença de marcadores de "tu" (`teu, tua, teus, tuas, ti, contigo` e as
  formas `ficas, estás, tens, és, vês, sentes`) junto de "você/seu/sua" no mesmo texto → violação → fallback. O texto
  real da Ilsa é rejeitado.
- **R13 — Toda rejeição deixa rastro.** A rejeição por `validate_narrative_text` emite
  `combat.outcome_narrative_rejected` (códigos, sem texto), como já fazem autoria e orçamento. O fallback grava em
  `combat_meta["last_outcome_source"] ∈ {"llm", "fallback_budget", "fallback_narrative", "fallback_attribution",
  "fallback_llm_error"}` (aditivo, para o §6 e para o próximo smoke saberem por que caiu).
- **R14 — Matador = golpe final.** `death_context.killer`, o evento `player_downed` (`killer`, `killer_id`) e o
  `_narrate_fall` usam o autor de `out["final_blows"]` com `target_id == "player"` (ataque → espécie do autor;
  dano contínuo → "o <condição>"; auto-dano → "o preço da própria Carta"). Sem `final_blows` (save antigo), cai na
  regra de hoje.
- **R15 — A queda vem depois da causa.** No registro, no `mech_log` e no `round_board`, a linha de queda/morte de um
  alvo aparece **logo depois** do evento que a causou (o golpe final de R14/353 R7), inclusive quando a causa é a
  Última Ação fora de turno. Nunca "Goblin morre." antes de "Você executa a Última Ação em Goblin".
- **R16 — Tabuleiro fecha junto com a morte.** Assim que a resposta do turno traz `death_pending` ou
  `combat.active == false`, a mão, "Encerrar a rodada" e "Fugir" ficam desabilitados no mesmo render (sem a janela de
  alguns segundos do print `8694215`).
- **R17 — Oráculo com os textos reais.** Fixture `tests/fixtures/spec363_smoke.py` com: o texto de morte do staging
  (R6–R9), o resumo do Mímico (R11) e o da Ilsa (R12). Os três falham na regra correspondente; três textos corretos
  escritos à mão sobre os mesmos fatos passam.
- **R18 — Espólio sem moeda redundante.** Item de loot com `type: currency` vira ouro (`value_gold × qty`) no momento
  do sorteio e não entra no inventário; o texto mostra só "+N de ouro". Mesmo valor, sem item (D-363-4).

### C. Mira válida para toda Carta da mão (item 3, P2)

- **R19 — `valid_targets` por Carta da mão.** A view do combate manda `valid_targets`/`invalid_reason` para **toda**
  Carta em `pilhas.mao` (básicas, preparadas, de cena), calculados por `combat_targeting.card_targeting` — o mesmo
  caminho do motor. Contrato: Carta com alvo X na view ⇒ o motor aceita X no mesmo estado (teste de propriedade
  sobre a mão das 5 Posturas com um inimigo `escondido`).
- **R20 — Fallback do front respeita ocultação.** Se uma Carta chegar sem `valid_targets` (save antigo/servidor
  antigo), `cardTargets` exclui inimigos com `concealment` diferente de `visivel` e o chip mostra "escondido — fora
  de alcance" como motivo.
- **R21 — Recusa aponta a jogada.** O `409 invalid_target` passa a trazer, de forma aditiva, o índice/id da jogada
  recusada; o front tira **só** essa jogada da fila, mantém as outras, e mostra "<Carta> perdeu o alvo — escolha de
  novo."

### D. Fuga honesta (item 5, P2)

- **R22 — Veredito pela perseguição.** `out["fuga"]` ganha `veredito ∈ {"escapou", "avancou", "perdeu_terreno",
  "alcancado", "falhou"}` derivado de `chase_state` (não de `roll.sucesso`). `_flee_line`:
  `Fuga · total 16 vs 12 · avança (afastado → quase livre)`; `· escapou` só quando `chase_state.escapou`. Tela,
  `mech_log`, registro e Livro dizem a mesma coisa.

### E. Nenhum id na tela (itens 6 e 8)

- **R23 — Arma pelo catálogo.** `round_log._weapon_name` resolve string de id pelo catálogo de itens
  (`inventory.item_display`/`ARTIFACTS_DB`), devolvendo o nome ("Espada Gasta"); id desconhecido → "a arma".
- **R24 — Trilha da fuga legível e na voz do jogador.** As linhas de fuga usam rótulos ("pressionado", "afastado",
  "quase livre", "livre") e "Você" no lugar do nome do herói.
- **R25 — Mercado sem id.** `public_market_snapshot` cota itens do inventário com o nome da **entrada** (`display_name`
  dos itens livres); `agents/loot.py` nunca imprime `item_id` (sem nome → linha omitida).
- **R26 — Condições: uma linha, normalizada.** Toda linha de condição que chega ao Livro, ao registro ou ao `mech_log`
  passa pela mesma normalização (`round_log._voce`: "Você", condição com inicial maiúscula do glossário) e um mesmo
  evento (ator, condição, rodada) aparece **uma** vez por superfície, venha do motor ou do bloco das Cartas de Cena.
- **R27 — Invariante de ids estendido.** O teste de invariante da SPEC-353 R4 passa a cobrir também o Livro
  (`/game/history`) e a consulta do mercado, e acrescenta ao padrão os ids de item do catálogo (`ARTIFACTS_DB`), os
  estados da trilha (`services/chase.py:29`) e `item_desconhecido`.

### F. Compra pela frase natural (item 7, P2)

- **R28 — Complemento do mercador.** A gramática fechada aceita, depois do nome da Carta, `(da|do|de|na|no)
  <nome>` onde `<nome>` ∈ {nome do mercador da prateleira, nome do local atual, nome de NPC presente no local}
  (dobrado como o resto, sem acento). Continua fechada: qualquer outra sobra, "?" ou negação → só preço, sem
  débito. Casos obrigatórios: "Quero comprar a Lança de Gancho da Forja dos Clãs" compra; "Quero comprar a Lança de
  Gancho da Okka" compra se Okka está no local; "…da Okka?" e "…da Okka depois" não compram.

### G. Nome e família do inimigo (item 9, P3)

- **R29 — Família pelo bestiário.** `creature_art.family_of` (e o ícone) resolve `arquetipo` pelo registro do
  bestiário (`normalize_bestiary_id` → `gamedata.BESTIARY[...]`) quando a instância não traz o campo. Goblin →
  `bruto`.
- **R30 — Nome com cabeça genérica proibido.** Nenhum inimigo materializado tem nome cuja primeira palavra de
  conteúdo seja um substantivo genérico (o `_STOP` de `encounter_manifest`: criatura, inimigo, vulto…) seguido de
  complemento ("Criatura da Fogueira", "Vulto do Poço"). Nesses casos vale a espécie do scanner ou do pool regional
  (346 R25 / 353 R16). A Etapa 0 localiza em `server.log` qual caminho produziu "Criatura da Fogueira".

### H. Espólio, loja e Acervo (itens 12 e 13, P3)

- **R31 — Espólio de conflito sem utilitária.** `roll_rewards` não oferece Cartas `tipo: utilitaria` no espólio de
  conflito (loja, missão e Acervo continuam podendo). Pool vazio cai nas outras fontes como hoje.
- **R32 — Destino da loja com o motivo certo.** O destino previsto da compra traz `motivo ∈ {"baralho_cheio",
  "limite_de_copias", "preparadas_cheias", "sem_baralho"}` quando o destino é `acervo`; o front mostra o texto do
  motivo ("só para o Acervo — Baralho cheio" **apenas** com `baralho_cheio`). Invariante: nunca "Baralho cheio" com
  `len(deck) < DECK_MAX`. Etapa 0 confirma como o Baralho de um herói recém-criado nasce (para prever o destino
  certo com Baralho `on` e `deck` ainda vazio).
- **R33 — Acervo fala de Baralho.** Com `player_stats.baralho` presente, o cabeçalho do Acervo é "Baralho
  {total}/{maximo}" (e a mensagem de toggle segue o mesmo modelo); sem `baralho`, "Preparação N/M" como hoje.

### I. Latência fora do combate (item 14, P3)

- **R34 — CLASSIFY desiste cedo no DeepSeek.** O candidato DeepSeek no tier `CLASSIFY` usa timeout próprio
  (constante em código, sem env/flag nova), escolhido na Etapa 0 como o maior entre 4 s e o p99 das chamadas
  CLASSIFY **bem-sucedidas** do DeepSeek no `server.log` dos smokes 2 e 3; FAST/SMART ficam em 12 s.
  `LLM_TIMEOUT_SECONDS` global continua vencendo. Meta: compra na loja com timeout do DeepSeek ≤ timeout + latência do
  Groq (≈ 6–8 s em vez de 17 s).
- **R35 — Enriquecimento em paralelo.** `enrich_node` roda `_enrich_npcs` e `_enrich_plan` em paralelo (2 threads,
  merge determinístico na ordem de hoje) **se** a Etapa 0 provar que `_build_plan` não lê a ficha completa dos NPCs
  pendentes; se ler, fica em série e a §9 registra o porquê. Saída idêntica à serial (teste com LLM simulado).
- **R36 — Abertura medida.** A Etapa 0 lista, a partir do `server.log`, as 6 chamadas da abertura da Mirela
  (nó, tier, provider, latência) e registra em §9 quais são sequenciais evitáveis; R34 já corta o timeout do
  CLASSIFY nela. Nenhuma chamada nova; nenhuma removida sem requisito próprio (fora de escopo, §2 "Fora de
  escopo").

### J. Cenários raros provados por teste determinístico (§1.2)

- **R37 — Sem LLM por rodada continua.** `tests/test_spec346_board_no_llm.py` estendido: 5 rodadas de meio de luta
  com Carta de cena, fuga, Reação e Última Ação → **0** chamadas a `get_llm` (contador no `RoutedLLM`/Mock).
- **R38 — Motor/agente (integração com seed/fixture, `agents/combat.py` + orquestrador, MockLLM):**
  - (a) **objeto de cena:** abertura com cena que tem objeto (fixture de `cartas_de_cena`), a Carta do objeto vai
    à mão, é jogada e resolve (353 R1), sem "não pôde ser jogada";
  - (b) **iniciativa contra emboscada:** emboscada (inimigo age primeiro) + herói com Carta `buff_iniciativa` na mão
    → a surpresa cai e a ordem nas três superfícies mostra o herói primeiro;
  - (c) **fuga concluída:** perseguição roteirizada até `escapou` → conflito encerra com desfecho `fled`, resumo
    "fuga", `mech_log` "escapou", registro da rodada final preservado (353 R54);
  - (d) **Arcanista alterado:** mão forçada com `arc1_imp_truque` e `arc1_cal_pulso_medido` → o texto da mão mostra
    os números da SPEC-362 e a prévia bate com o motor (353 R21);
  - (e) **Leitura de Pressão** (`arc1_cal_leitura`): jogada revela o que a SPEC-355 promete, no registro e na view;
  - (f) **Voto Sussurrado com presságio no aliado:** presságio congelado mirando Ketil + Voto jogado → o registro
    diz o que a SPEC-355 §6.1 promete;
  - (g) **Armadura Comprometida:** condição aplicada aparece legível (nome do glossário, sem id) no chip e no
    registro;
  - (h) **Renegado de corpo a corpo:** baralho montado sem `bst_descarga_arcana` (353 R38a), 20 seeds;
  - (i) **vitória com Reação:** golpe final por Reação → fatos "Sua reação termina o serviço" (355 R4) e desfecho
    vitória;
  - (j) **"Vasculho o corpo"** depois da vitória: loot uma vez só (346), texto sem id;
  - (k) **modo `off`:** `RPG_CARD_DECK=off` → rodada pelo fluxo antigo, sem `pilhas`, `mech_log` sem `?` (345 §6.1,
    346 §6.7);
  - (l) **router esgotado:** todos os candidatos falham → FallbackLLM; a abertura do combate ainda abre o
    tabuleiro com narração determinística e o turno não quebra (346 §6.5); CLASSIFY só no Groq (346 §6.6) com
    `RPG_ROUTES` de teste;
  - (m) **quest de lore `justa`** (SPEC-357 R12): conclusão entrega a Carta prometida, uma vez, determinística por
    `quest_id`.
- **R39 — Tela (Playwright, servidor `legacy` com estado semeado por fixture, sem LLM):**
  - (a) cena com **2 inimigos e 1 aliado** a 1440 e a 390: mão sem rolar, registro em uma coluna, nenhum id cru
    (354 §6.1);
  - (b) **vitória a 1440 no instante**: sem toast sobre o tabuleiro (354 §6.3);
  - (c) oferta de retrato com e sem mira a 390 (R3) e oferta ausente com o switch desligado (R2), com a API
    simulada;
  - (d) 409 de alvo escondido: só a jogada recusada sai da fila (R21);
  - (e) morte: tabuleiro desabilitado no mesmo render (R16).

### K. Transversais

- **R40 — Sem flag nova.** Nada novo em `config/flags.yaml`; constantes em código (R34).
- **R41 — Eventos.** `combat.outcome_narrative_rejected` (R13) entra em `docs/operacao/EVENTOS_DE_LOG.md` e no
  registro de eventos (`observability/events.py`).
- **R42 — Saves.** `combat_meta["last_outcome_source"]` e `out["fuga"]["veredito"]` são opcionais; save sem eles
  carrega. R8 não muda o `ConflictSummary` persistido.
- **R43 — Guard de FallbackLLM** mantido no resumo; nenhum `with_structured_output` novo.
- **R44 — Contrato da view aditivo.** `pilhas.mao[*].valid_targets/invalid_reason` (R19), `veredito` (R22),
  `motivo` do destino (R32) e o detalhe do 409 (R21) são campos novos e opcionais; front antigo não quebra.
- **R45 — Tipos do front.** `web/src/types.ts` e `web/src/lib/errorCodes.json` acompanham os campos novos; `npm run
  typecheck`, `lint` e `test` verdes.
- **R46 — Ids e voz no histórico.** O teste de R27 roda sobre o `/game/history` de uma campanha simulada com
  combate, fuga e loja.
- **R47 — Golden da 330 intocado.** `git diff main -- tests/spec330_equivalence.py
  tests/fixtures/spec330_legacy_golden.json` vazio; nada novo dentro de `ct.resolve_turn` nem de
  `orch._resolve_reaction_effect` (R14/R15 leem `final_blows`, já gravado no orquestrador).

### Fora de escopo

- **P2-6 (crítico por dupla, ~28 % com 3d10)** e qualquer número de Carta, regra de crítico, Padrão/Elite ou
  Provocação — decisão do dono (D-363-1).
- Mudar o valor do teto diário de gasto do staging ou a regra "o cap nunca religa sozinho" (D-363-2).
- Remover chamadas de LLM da abertura do combate, do prólogo ou da viagem além de R34/R35 (só medição em R36).
- Hedge global, troca de provider primário ou de modelo.
- Balanço da fuga com 0 de Vitalidade (observação do P2-3; spec de balanço própria se o dono quiser).
- Prints de `docs/spec347/depois/` e `docs/spec354/depois/` (tarefa do coordenador, fora de código).
- Tirar utilitárias do **Baralho** em combate (353 D6 revertido); R31 só tira do **espólio**.

## 3. Design técnico

### 3.1 Arquivos novos

- `scripts/staging/art_preflight.py` — R5, só leitura: lê switches (store do staging), frescor do rate card de
  imagem, envs por nome e o teto da cotação; imprime JSON e sai ≠ 0 se a oferta não puder ser honrada.
- `tests/fixtures/spec363_smoke.py` — textos reais (morte do staging, Mímico, Ilsa) e os corretos (R17).
- Testes: `tests/test_spec363_portrait_offer.py` (R2, R4 backend), `test_spec363_outcome_text.py` (R6–R10, R13, R17,
  R18), `test_spec363_attribution_v4_v5.py` (R11, R12), `test_spec363_killer_order.py` (R14, R15),
  `test_spec363_hand_targets.py` (R19, R21 backend), `test_spec363_flee_verdict.py` (R22, R24),
  `test_spec363_ids.py` (R23, R25–R27, R46), `test_spec363_shop_grammar.py` (R28), `test_spec363_enemy_name.py`
  (R29, R30), `test_spec363_rewards_shop.py` (R31, R32), `test_spec363_latency.py` (R34, R35),
  `test_spec363_rare_scenarios.py` (R38), `test_spec363_golden_guard.py` (R47); front:
  `web/tests/spec363-*.test.mjs` (R3, R4, R16, R20, R21, R32, R33) e `web/e2e/spec363-*.spec.ts` (R39).

### 3.2 Arquivos alterados

- `api.py` — `_image_effect_open()` + `_creature_art_live` (R2); `valid_targets` por Carta de `pilhas.mao` (R19);
  detalhe do 409 (R21); `motivo` no destino da loja (R32, se o destino é montado aqui).
- `services/round_log.py` — `_no_digits` com proteção de nomes (R6); fallback sem herói por nome e com quedas
  antigas no passado (R7, R9); ferimento com dono (R10); `_weapon_name` pelo catálogo (R23); ordem queda-após-causa
  (R15, junto com `services/combat_preview.py::chrono_events`).
- `services/conflict_summary.py` — dedupe por nome (R8); V4/V5 em `validate_attribution` (R11, R12).
- `services/combat_preview.py` — `_flee_line` com `veredito` (R22); queda depois da causa no `mech_log`/`round_board`
  (R15); normalização de condição no `mech_log` (R26).
- `agents/combat.py` — evento e `last_outcome_source` (R13); `_killer_identity` por `final_blows` (R14); prompt
  "você" (R12); `veredito` em `out["fuga"]` e linhas de fuga com rótulo/"Você" (R22, R24); bloco das Cartas de Cena
  pela normalização (R26, emissor exato na Etapa 0).
- `agents/loot.py` — gramática com complemento (R28); nunca `item_id` na consulta (R25); moeda vira ouro (R18).
- `services/economy.py` — cotação do inventário com `display_name` (R25); `roll_loot` converte `currency` (R18, se a
  conversão morar no sorteio).
- `services/creature_art.py` — `family_of` pelo bestiário (R29). `services/encounter_manifest.py` /
  `agents/bestiary.py` — trava de cabeça genérica no nome materializado (R30).
- `services/card_rewards.py` — sem utilitária no espólio (R31); motivo do destino (R32).
- `llm_setup.py` — timeout do DeepSeek por tier (R34). `agents/enrich.py` — paralelo condicional (R35).
- Front: `web/src/combat/TargetChip.tsx` (R3), `web/src/combat/deck.ts` (R20), `web/src/workspace/tabs/CombateTab.tsx`
  e `web/src/components/combat/DeckCombat.tsx` (R4, R16, R21), `web/src/cardRewards.ts` (R32),
  `web/src/components/tabs/CombatDeckTab.tsx` (R33), `web/src/types.ts`, `web/src/lib/errorCodes.json` (R45).
- `docs/operacao/EVENTOS_DE_LOG.md`, `observability/events.py` (R41).

### 3.3 Formatos

Fatos do resumo (Mímico, R10):

```
Desfecho: vitória.
Mímico (Baú) fugiu.
Você atacou Mímico (Baú) com Espada Gasta: acertou, ferimento leve no braço do Mímico (Baú).
Arma do herói: Espada Gasta. Herói: ileso.
```

Fallback de morte (staging, depois de R6–R9 e R14):

```
Você tomba diante de Minotauro Esqueleto. Antes, Goblin já tinha tombado. Você carrega ferimento crítico na perna, ferimento crítico no braço.
```

`out["fuga"]` e `mech_log` (R22):

```json
{"total": 16, "dificuldade": 12, "sucesso": true, "veredito": "avancou", "de": "pressionado", "para": "afastado"}
```

```
Fuga · total 16 vs 12 · avança (pressionado → afastado)
```

Carta da mão com alvo (R19):

```json
{"id": "bas_san_corte_raso", "alvo": "inimigo", "valid_targets": ["enemy_minotauro_esqueleto_2"],
 "invalid_reason": null}
```

409 com a jogada (R21, aditivo ao `detail` de hoje):

```json
{"detail": {"code": "invalid_target", "message": "O alvo escolhido deixou de ser válido. Escolha de novo.",
 "play_index": 0, "card_id": "bas_san_corte_raso"}}
```

Preflight (R5):

```json
{"switch_image": false, "switch_actor": "system:finops", "pricing_fresh": true, "dynamic_art_env": true,
 "creature_art_env": true, "price_estilhas": 1, "ok": false, "causa": "daily_cap"}
```

> O formato exato do `detail` do 409 segue o que `api.py` já devolve para `invalid_target` (a Etapa 3 confere e só
> acrescenta `play_index`/`card_id`).

## 4. Plano passo a passo

Cada etapa: testes primeiro → código → só os testes do escopo (`-n 2` no máximo). Suíte completa só no pouso, pelo
coordenador. Toda etapa que toca `round_log`/orquestrador roda também `tests/test_card_effects_grammar.py` e
`test_spec363_golden_guard.py` (R47).

### Etapa 0 — Diagnóstico (sem código de produto)

1. **R1:** audit do switch no staging (só leitura) + nomes das envs Vercel; causa em §9. Conferir se o print
   `out/stg-board-390.png` tinha Carta armada.
2. **§1.1 item 2:** em `stg2/` e `stg_hist_A.json`, a sequência de golpes que mirou o herói: a perna crítica do herói é
   real? Registrar em §9 (decide se R10 corrige um bug real ou só um texto ambíguo).
3. **R30:** em `server.log`, o caminho que nomeou "Criatura da Fogueira" (dica, scanner, bestiário, LLM).
4. **R26:** emissor do bloco "X: ganha condição y" duplicado (Cartas de Cena) e do `mech_log` com nome do herói.
5. **R32:** como nasce o `deck` de um herói recém-criado com Baralho `on`.
6. **R34/R36:** p99 das chamadas CLASSIFY bem-sucedidas do DeepSeek (smokes 2 e 3) → constante; lista das 6
   chamadas da abertura da Mirela. **R35:** `_build_plan` lê ficha completa de NPC?
7. Tudo anotado em §9 antes da Etapa 1.

### Etapa 1 — Retrato pago coerente (R2–R5)

1. **Testes:** `test_offer_requires_image_switch` / `test_offer_requires_fresh_pricing` /
   `test_offer_requires_dynamic_art_env` / `test_offer_requires_price`; `test_offer_implies_quote_ok` (propriedade
   sobre os 16 estados, cotação com repositório falso); front: `spec363-portrait-offer.test.mjs` (oferta com e sem
   mira; 503 esconde a oferta).
2. **Implementação:** `_image_effect_open`, `_creature_art_live`; `TargetChip` (irmão do botão com mira);
   `CombateTab` (R4); `scripts/staging/art_preflight.py` (+ teste unitário com store em memória).
3. **Correção de staging** (coordenador, conforme R1/R5), registrada em §9.

### Etapa 2 — Texto de morte e resumo (R6–R18)

1. **Testes:** `test_no_digits_keeps_names` (Smoke3A, Bandido 2); `test_fallback_never_names_hero`;
   `test_player_summary_one_category_per_name`; `test_old_falls_in_past_tense`;
   `test_wound_has_bearer_in_facts_and_registry`; `test_v4_rejects_mimic_text` /
   `test_v4_accepts_correct_text`; `test_v5_rejects_ilsa_text`; `test_narrative_rejection_emits_event_and_source`;
   `test_killer_from_final_blows` (ataque, DoT, auto-dano, sem `final_blows`); `test_fall_after_cause_last_stand`
   (três superfícies); `test_currency_loot_becomes_gold`; front: `spec363-death-board.test.mjs` (R16).
2. **Implementação:** `round_log`, `conflict_summary`, `combat_preview`, `agents/combat.py`, `agents/loot.py`/
   `economy`, `CombateTab`/`DeckCombat`.

### Etapa 3 — Mira (R19–R21)

1. **Testes:** `test_hand_cards_have_valid_targets` (5 Posturas, inimigo escondido); `test_view_target_implies_engine_accepts`;
   `test_409_names_the_play`; front: `spec363-hand-targets.test.mjs` (fallback com `concealment`; 409 tira só a
   jogada).
2. **Implementação:** `api.py`, `deck.ts`, `DeckCombat.tsx`/`CombateTab.tsx`.

### Etapa 4 — Fuga, ids e condições (R22–R27, R46)

1. **Testes:** `test_flee_verdict_matches_chase` (avançou, perdeu terreno, alcançado, escapou);
   `test_flee_lines_use_labels_and_voce`; `test_weapon_name_from_catalog`; `test_market_quote_uses_display_name`;
   `test_condition_line_once_and_normalized` (motor + Carta de Cena, `mech_log` incluso);
   `test_no_internal_ids_in_history` (campanha simulada com combate, fuga e loja).
2. **Implementação:** `combat_preview`, `agents/combat.py`, `round_log`, `economy`, `agents/loot.py`.

### Etapa 5 — Compra, nome/família, espólio, loja e Acervo (R28–R33)

1. **Testes:** `test_buy_with_merchant_complement` (casos de R28, positivos e negativos);
   `test_family_from_bestiary_record`; `test_generic_head_name_rejected`; `test_rewards_never_offer_utility`
   (200 seeds, 5 Posturas); `test_shop_destination_reason` (sem baralho, cheio, cópias, preparadas);
   front: `spec363-shop-label.test.mjs`, `spec363-acervo-header.test.mjs`.
2. **Implementação:** `agents/loot.py`, `creature_art`, `encounter_manifest`/`bestiary`, `card_rewards`, `api.py`,
   `cardRewards.ts`, `CombatDeckTab.tsx`.

### Etapa 6 — Latência (R34–R36)

1. **Testes:** `test_deepseek_classify_timeout_constant` (CLASSIFY usa a constante; FAST/SMART 12 s;
   `LLM_TIMEOUT_SECONDS` vence); `test_enrich_parallel_same_output` (LLM simulado com atraso: saída idêntica à serial e
   tempo ≈ max em vez de soma) — ou `test_enrich_stays_serial_when_plan_reads_sheets`, conforme a Etapa 0.
2. **Implementação:** `llm_setup.py`, `agents/enrich.py`.

### Etapa 7 — Cenários raros (R37–R39)

1. **Testes:** `tests/test_spec363_rare_scenarios.py` com um teste por item de R38 (a–m), cada um com seed/fixture
   explícita e asserts sobre estado, registro e view; extensão de `test_spec346_board_no_llm.py` (R37); Playwright
   `web/e2e/spec363-board.spec.ts` (R39 a–e, `--workers=1`, estado semeado).
2. **Implementação:** só fixtures/seams de teste; se um cenário revelar bug, corrigir nesta etapa e registrar em §9.

### Etapa 8 — Guardas e não-regressão (R40–R47)

1. `test_spec363_golden_guard.py`; `tests/test_card_effects_grammar.py`; testes da 346/347/353/354/355/357/362 sem
   mudar expected, **exceto** os que codificavam: "escapou" por `roll.sucesso` (R22), herói por nome no fallback
   (R7), `acervo` sem motivo (R32), "Preparação" com Baralho (R33) — listar cada um em §9 com o motivo.
2. Arena de não-regressão (`docs/spec341/arena_spec341.py posturas --seeds 20:100`, níveis 1/3/5, em série):
   cada Postura dentro de ±2 pp do `docs/spec353/arena-depois.json` (R31 não mexe na arena, que não sorteia espólio;
   a arena prova que nada de motor mudou). Gravar `docs/spec363/arena.md`.
3. Eventos (R41), saves (R42), front `typecheck`/`lint`/`test` (R45).

## 5. Critérios de aceite

- [x] Etapa 0 anotada em §9 (causa do switch, perna do herói, nome genérico, emissor das condições, Baralho inicial,
      p99 CLASSIFY, chamadas da abertura, dependência do replan)
- [x] Retrato: R2 por propriedade (16 estados); oferta com e sem mira (R3); 503 apaga a oferta (R4); preflight
      versionado e staging corrigido (R5)
- [x] Morte e resumo: os 3 textos reais de `spec363_smoke.py` rejeitados/corrigidos e os 3 corretos aceitos (R17);
      nomes com dígito intactos (R6); matador = golpe final (R14); queda após a causa (R15); tabuleiro fecha junto (R16)
- [x] Mira: toda Carta da mão com `valid_targets` e contrato view ⇒ motor (R19); 409 tira só a jogada (R21)
- [x] Fuga: veredito igual em tela, `mech_log`, registro e Livro (R22)
- [x] Nenhum id em Livro, registro, `mech_log`, `round_board`, mercado e `/game/history` (R27, R46)
- [x] Compra com complemento do mercador; negativos sem débito (R28)
- [x] Goblin com família `bruto`; nenhum nome de cabeça genérica (R29, R30)
- [x] Espólio sem utilitária; destino da loja com motivo; Acervo "Baralho N/M" (R31–R33)
- [x] CLASSIFY DeepSeek com timeout próprio; enrich paralelo ou justificativa em §9 (R34, R35)
- [x] R38 (a–m) e R39 (a–e) verdes, cada um com seed/fixture explícita
- [x] 0 LLM por rodada (R37); golden da 330 sem diff (R47); arena dentro de ±2 pp
- [x] Nenhuma flag nova; evento registrado; saves antigos carregam (R40–R42)
- [x] Guard de FallbackLLM no resumo (sem `with_structured_output` novo) (R43)
- [x] `uv run pytest` verde (suíte completa, coordenador, no pouso); `npm run typecheck`, `lint`, `test` verdes
- [x] Revisão independente `Sol` sem P0/P1 aberto
- [x] **Smoke real §6 (coordenador)** executado e registrado em `docs/spec363/smoke-final.md`

## 6. Smoke test com LLM real (≤ 15 turnos; só os achados)

Local `legacy` (flags de cartas `on` + `RPG_CREATURE_ART=on`, preset de `scripts/staging/staging_flags.json`) e
staging (`hosted-supabase`, contas sintéticas pelo caminho de `two_user_smoke`, limpeza no fim). DeepSeek primário.
Registrar em `docs/spec363/smoke-final.md` (trechos, sem segredos), com provider/modelo e custo.

1. **Staging, retrato pago:** `scripts/staging/art_preflight.py` → `ok: true`. Conta nova, combate → chip com "Gerar
   retrato" a 390 com e sem Carta armada; cotar → confirmar → geração → débito = custo liquidado ≤ cotação, reserva 0 (D-364-1) → retrato no chip
   (fecha o §6 da SPEC-352). Se o preflight der `ok: false`, conferir que **nenhum** inimigo tem `gerar` (R2) e
   anotar.
2. **Staging, morte:** jogar até a queda → texto do Livro sem nome mutilado, herói uma vez, quedas antigas no passado,
   `killer` = quem derrubou (R6–R9, R14); anotar `last_outcome_source` (R13).
3. **Local, vitória com ferimento no inimigo:** resumo sem ferimento atribuído ao herói e só com "você" (R10–R12);
   se cair no fallback, anotar o código.
4. **Local, Sangromante com inimigo escondido:** Carta básica não mira o escondido; se o 409 vier, só a jogada sai da
   fila (R19–R21). Tentar fugir 2× → `mech_log` "avança/perde terreno" igual à tela (R22).
5. **Local, loja:** "Quero comprar a <Carta> da <mercador>" compra (R28); consulta do mercado sem id (R25); tempo do
   turno de compra anotado (R34).
6. Varredura de ids no `/game/history` das campanhas (R27) e latência de uma viagem anotada (R35).

## 7. Riscos & compatibilidade

- **R2 esconde a oferta mais vezes.** É o comportamento certo: oferta só quando a cotação passa. Risco: o predicado
  ler o store a cada view → usa o cache de 5 s do `KillSwitches` (`kill_switches.py:142,161-185`) e o de 60 s do preço.
- **V4/V5 (R11, R12)** aumentam o fallback. Falso positivo custa prosa; medir no §6 e registrar a taxa. O fallback
  fica mais legível com R6–R9.
- **R14/R15** mudam a ordem de linhas e o `killer` exibido; testes da 353 que fixavam a ordem da Última Ação são
  atualizados com motivo em §9.
- **R18 (moeda vira ouro)** muda o inventário (sem o item), não o valor; registrar no CHANGELOG.
- **R31 (sem utilitária no espólio)** muda a distribuição das ofertas; a arena não sorteia espólio, então não mede;
  o `test_rewards_never_offer_utility` cobre.
- **R34** pode cair no Groq mais vezes se o DeepSeek tiver cauda longa; a constante sai do p99 medido.
- **R35** paralelo só com independência provada; sem ela, nada muda.
- **MockLLM/FallbackLLM:** guard mantido; os cenários raros rodam no Mock.
- **Quota/latência:** nenhuma chamada nova; R34/R35 só reduzem.
- **Saves:** R42.

## 8. Decisões

### Do dono / coordenador (prompt de 02/11)

- Zero pendência: todos os P1/P2/P3 do smoke 3 entram, **exceto o P2-6**.
- P1-1: investigar a causa e corrigir; se for config de staging, a correção é no preset/script versionado; a
  oferta nunca aparece com a geração desligada.
- P1-2 e P2-2: fatos estruturados + validação de atribuição, com fallback determinístico.
- Combate sem LLM nas rodadas permanece.
- Itens não verificados por cenário raro viram teste determinístico com seed/fixture.

### Do autor (valem como aprovadas; o dono pode vetar na revisão)

- **D-363-3 — Fallback sem nome do herói (R7).** O jogador é "você" em todo texto ao jogador; nome próprio do herói
  só em crônica/archivist.
- **D-363-4 — Moeda vira ouro (R18).** `moeda_ouro` é `currency` de valor 1; como item ao lado do ouro só confunde.
- **D-363-5 — Utilitária fora do espólio (R31), não do Baralho.** Tirar do Baralho mexeu no Médico de Campo (353 D6,
  +2,7 pp); tirar só da oferta de espólio não toca a arena.
- **D-363-6 — Timeout do CLASSIFY por medição (R34)**, constante em código, sem flag: é parâmetro de engenharia, não
  de produto.

### Pendentes do dono (não bloqueiam a execução)

- **D-363-1 — P2-6, crítico por dupla abaixo da defesa (decisão do dono pendente).** O achado estima ~28 % por
  ataque com 3d10, que é a chance de **algum** par entre os 3 dados (1 − 720/1000); a SPEC-353 §1.2 calculou 14,5 %
  para dupla **nos 2 mantidos**. Os exemplos do smoke ("2 + 2 +1 = 5 vs 12 · crítico (dupla de 2)") mostram dupla nos
  dados exibidos; a spec de balanço confere primeiro qual das duas o motor aplica. A regra (§13.2/§13.3 das regras consolidadas) diz que qualquer dupla nos mantidos
  é acerto automático e Crítico. Opções: manter; exigir total ≥ defesa para o Crítico por dupla; dupla só com 2d10;
  Crítico por dupla vira "acerto" sem dobrar. Qualquer opção pede arena por Postura numa spec de balanço própria.
  **Nenhum requisito nesta spec.**
  **Decidido em 09/11, pelo coordenador com delegação do dono ("confio em vc nas decisoes"): manter a regra.**
  Qualquer dupla nos mantidos é acerto automático e Crítico, como nas §13.2/§13.3 das regras consolidadas. O balanço
  da SPEC-369 foi calibrado e confirmado (260–339) com essa regra em vigor, e o round_log já explica o
  crítico abaixo da Esquiva (353 R29). Mexer exigiria uma nova rodada de arena por Postura, e nada mostra
  necessidade disso.
- **D-363-2 — Teto diário do staging.** Se a Etapa 0 provar que o cap (R$ 5/dia contando texto) desligou a imagem, o
  coordenador religa para o smoke; subir o valor ou separar texto de imagem no cap é decisão do dono.
  **Decidido em 09/11, pelo coordenador com delegação do dono: manter R$ 5/dia, com texto e imagem no mesmo cap e a
  regra "o cap nunca religa sozinho".** No smoke, o coordenador religa à mão, auditado, como já é feito hoje.
  Isso só vale para o staging; o teto de produção entra no go/no-go da SPEC-197.

## 9. Registro de implementação

(Etapas 0–8 executadas na branch `spec-363`; resultado por requisito no hand-back. Revisão independente `Sol` e §6 ficam com o coordenador.)

### Etapa 0 — diagnóstico

- **R1 (causa do switch):** `image_generation` está `false` no staging por ator **`system:finops`** (teto diário), última linha em
  **2026-10-27 01:00 UTC** ("daily spend cap exceeded"); o mesmo ator o desligou em 19/10 e 23/10 e o `staging-1910` o religou
  duas vezes. É a causa (a); (b) env, (c) fail-closed e (d) drill descartadas (o drill de 15/10 foi resetado na hora). Fonte:
  `scripts/admin_kill_switch.py --dsn-env RPG_STAGING_DB_URL audit --limit 20` e `list` (só leitura, nada alterado). **O
  coordenador religa** (`on image_generation --actor <coordenador> --reason "SPEC-363 smoke" --apply`) e roda
  `scripts/staging/art_preflight.py` antes do §6. Se o chip a 390 tinha mira no print não foi verificável (evidência no
  scratchpad do coordenador); o código mostrava mesmo a oferta só sem mira (corrigido por R3).
- **§1.1 item 2d (perna crítica do herói):** não verificável (os `stg2/` são do coordenador). O texto de R10 agora diz de quem
  é cada ferimento; o fallback "Você carrega…" lista só `player.ferimentos` (como antes).
- **R30:** sem `server.log`, o caminho do "Criatura da Fogueira" não foi medido; a trava vale no loop dos grupos do scanner
  (`_name_without_generic_head` em `_spawn_v4_enemies`), que é o único ponto onde um nome livre do LLM vira inimigo.
- **R26:** emissor do bloco duplicado = `status_logs` (`card_status.on_start/on_round_end/on_hand_drawn`) que ia cru ao
  registro e ao `mech_log`; `out["logs"]` já passava por `_voce`. Agora `_normalize_status_logs` normaliza uma vez para os dois.
- **R32:** com o Baralho `on`, `deck` nasce em `card_piles.migrate_deck` (1º combate); antes disso `deck` é vazio e a compra cai
  em Preparadas/Acervo → motivo `sem_baralho` (flag do Baralho `on`) ou `preparadas_cheias`.
- **R34:** o p99 das chamadas CLASSIFY do DeepSeek **não foi medido** (os `server.log` dos smokes 2 e 3 estão no scratchpad do
  coordenador). Constante provisória `DEEPSEEK_CLASSIFY_TIMEOUT_S = 6.0` (piso da spec = 4 s; 6 s dá a meta "≈ 6–8 s" da
  compra com o Groq). **Pendência do coordenador:** confirmar com o p99 real e ajustar a constante, se maior.
- **R35/R36:** `enrich_node` fica **em série**: `_build_plan` monta `build_context_pack(purpose="planning")`, que lê os NPCs da
  cena (`npcs_for_context`), e `_complete_sheet` pode renomear/fundir o stub (`merged_into`). As 6 chamadas da abertura da
  Mirela não foram listadas (sem `server.log`).

### Desvios e notas de implementação

- R15: a causa fora de turno (Última Ação) agora vem antes da queda no **registro**; `mech_log` e `round_board` não emitem
  linhas de queda (só o `round_board` tem `queda`, já depois de todos os eventos), então não mudaram.
- R16: `blocked` do `PlayScreen` já incluía `death_pending`; a janela do print `8694215` não foi reproduzida no código. Foi
  acrescentado `boardClosed(data, blocked)` (também `combat.active === false`) em `CombateTab`, com teste.
- R19: `check_declared_target` passa a usar os alvos da mão **só** quando a Carta está em `pilhas.mao` e não é preparada.
- R21: o `HttpError` reconstruído em `App.tsx` perdia `playIndex/cardId`; corrigido (achado pelo e2e).
- R38 coberto: (a)(b)(c)(d)(e)(g)(h)(i)(j)(k)(l)(m). **Abertos:** (f) Voto Sussurrado com presságio no aliado (cobertura de
  motor em `test_spec339_duracao_condicoes.py`/355, sem teste integrado novo) e a variante de (e) "presságio seguinte mostra o
  nome da Carta" (só o log/`revelacoes` é afirmado). R39: (c)(d)(e) feitos; **(a) cena com 2 inimigos e aliado e (b) toast
  da vitória a 1440 não foram escritos** (já têm `spec354-*.spec.ts`).
- R27/R46: o invariante cobre registro, fatos do resumo, consulta do mercado e fuga; **não** há teste que monte um
  `/game/history` de campanha completa (combate+fuga+loja).
- Testes antigos atualizados (só expected que codificava o comportamento antigo): `test_spec346_outcome.py` (nomes com dígito
  sobrevivem, R6), `test_spec353_registry.py` ("no seu torso", R10), `web/tests/spec347-components.test.mjs` (oferta com mira, R3).
- Suíte: `tests/test_project_index.py` falha 2 testes até o `project_index/` ser regenerado no pouso (coordenador).


### Fechamento das pendências (pós-hand-back)

- **R34 (medido):** `docs/spec363/measure_classify.py` sobre `smoke3/server.log` + `smoke2/server.log` →
  `docs/spec363/classify_latency.json`: n=22 ok, p50 1,3 s, p95 1,7 s, **p99 6,0 s** (um outlier), 2 falhas. Constante =
  max(4 s, p99) arredondada: `DEEPSEEK_CLASSIFY_TIMEOUT_S = 6.5`.
- **R38(f):** `test_f_voto_sussurrado_on_ally_targeted_omen` (`tests/test_spec363_rare_scenarios.py`, 2 ordens): presságio
  congelado mirando o aliado; `hero_first` → "provocado por … muda de alvo."; `enemy_first` → o inimigo mira o herói na rodada seguinte.
- **R27/R46:** `test_no_internal_ids_in_history` (`tests/test_spec363_ids.py`) joga uma campanha curta pela API (MockLLM, cartas on:
  abre combate, cartas, fuga, recusa por alvo escondido, "Vasculho", mercado) e varre `/game/history` + mensagens. **Achou um id real**
  ("fallback_goblin_1 sem posição conhecida", log de `conflict_turn`); corrigido sem tocar o motor com
  `round_log.humanize_ids` (registro e recusa da rodada). A fase de loja/espólio da campanha é só consulta/recusa (o herói
  inicial não está num mercado); o espólio e a consulta de mercado têm teste próprio (R18/R25).
- **R39(a,b) já cobertos** (`web/e2e/`): (a) `spec354-desktop.spec.ts › mao_sem_rolar_1440_registro_dois_inimigos` (2 inimigos, 1440) e
  `spec354-mobile.spec.ts › sem_id_cru_na_arena_390` (aliado + sem id cru, 390); (b) `spec354-desktop.spec.ts › vitoria_sem_toast_duplicado_1440`.
  A combinação literal "2 inimigos **e** aliado na mesma cena" não tem teste único.
- **R16:** não reproduz no código: `PlayScreen` já passava `blocked = gameOver || deathPending` e `combat.active` vem `false` na
  resposta de morte (`api.py` zera `combat.active` com `death_pending`); o print 8694215 deve ser atraso de render/stream. `boardClosed`
  permanece (teste `spec363-death-board` + e2e "morte pendente").
- **R15:** `mech_log` e `round_board` já emitem a queda depois do evento que a causou (as quedas são anexadas após `chrono_events`);
  só o registro (`round_registry`) tinha a queda antes da Última Ação — corrigido.
- **Arena:** a base da comparação continua `docs/spec353/arena-depois.json`; regravá-la é assunto de outra spec.

### Correções da revisão Sol (`handoffs/SPEC-363-sol-review.md`)

- **P1-1:** V4 só dispara na oração (entre vírgulas) que junta parte do corpo do herói **e** marca de dano (`_DAMAGE_MARK_RE`);
  corpus de 12 frases benignas em `test_v4_never_fires_on_benign_prose`; `MIMIC_BAD` segue rejeitado.
- **P2-1:** condição de dano contínuo sai por `condition_label`, sem artigo (killer, `player_downed`, texto de morte e
  `final_blow_sentence`; teste com `veneno_fraco`). `tests/test_spec353_registry.py` passou a esperar "Sangramento termina o serviço".
- **P2-2:** propriedade 2^5 × preço com switch e rate card independentes, afirmada sobre `api._enemy_portrait(...)["gerar"]`.
- **P3-1:** `last_outcome_source` é limpo no início e gravado também quando o filtro de números esvazia o texto.
  **P3-2:** R37 com Carta de cena, Reação declarada, fuga e passes (≥ 4 rodadas ativas) + teste da Última Ação, 0 LLM.
  **P3-3:** o evento grava códigos (`dead_alive`, `captured_free`). **P3-4:** `announceRef` no assinante do 409.
  **P3-5:** preflight lê só o `--env-file` para as flags e fecha o pool. **P3-6:** §3.3 ajustada para "diante de Minotauro Esqueleto".

- **Fechamento:** Auditoria de fechamento (02/11, coordenador): revisão Sol final aprovada (`handoffs/SPEC-363-sol-review.md`), suíte completa verde no pouso, smokes reais em `docs/spec363/achados-smoke3.md`, `docs/spec364/achados-smoke4.md` e `docs/spec364/smoke-final.md` (staging `90cfaa18`, cartas `on`). Smoke em `docs/spec364/achados-smoke4.md` (não em `docs/spec363/smoke-final.md`). §6.1 corrigido por D-364-1 (débito = custo liquidado ≤ cotação; provado no smoke final: 8 ≤ 15 milli, reserva 0). §6.2 (morte) coberto pelo R21 da 364 por teste; §6.6 R35 (latência de viagem) não verificado ao vivo. D-363-1 (crítico em dupla abaixo da defesa) segue como decisão pendente do dono, fora do fechamento.
