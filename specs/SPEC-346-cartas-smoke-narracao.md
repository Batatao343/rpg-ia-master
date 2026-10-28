# SPEC-346 — Combate de cartas sem LLM por rodada, desfecho narrado pela IA e correções do smoke real (spawn, router, loot)

> **Status:** `approved` (dono, 27/10: "corrigir tudo" + mudança de escopo D-dono-1..3, ver §8)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Origem:** smoke com LLM real de 27/10 na `main` `fae9a4e5` (`docs/spec346/achados-smoke.md`, históricos `docs/spec346/smoke/hist-*.json`, prints em `docs/spec346/smoke/`)
> **Depende de:** SPEC-203, SPEC-226, SPEC-325, SPEC-339, SPEC-341 (`done`); código das SPEC-328/329/330/331/332/333/334 já na `main` (status `in-progress`, flags `off`); SPEC-345 (`in-progress`: mexe em `player_summary_text`/`strip_system_tags`; rebase antes do pouso)
> **Desbloqueia:** ligar `RPG_CARD_DECK=on` no staging (o ESTADO pede "e2e/smoke antes de `on`")
> **Fronteira:** layout, marginália visual, chip/retrato do inimigo e a forma como o front desenha o `mech_log` são da **SPEC-347**. Esta spec entrega o **conteúdo** (texto da rodada, `last_mech_log`, mensagem do turno); a 347 decide onde aparece.
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma fase por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (motor de conflito, roteamento, contrato da mensagem do turno)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected, baseline ou dataset de regressão é alterado.

---

## 1. Contexto & Objetivo

O smoke real de 27/10 (3 personagens, 17 turnos, cartas `on` + 1 rodada `off`, DeepSeek primário) achou 10
problemas. O dono decidiu, além de corrigir tudo, **mudar o modelo do combate com baralho**:

- **D-dono-1.** Com `RPG_CARD_DECK=on`, cada rodada se resolve **só pelo jogo de cartas, sem chamada de LLM**.
  A rodada mostra o **registro das cartas** (quem jogou o quê, em quem, com que resultado) em frases curtas
  determinísticas: sabor da carta (`descricao` em `data/cards/*.json`) + resultado do motor. O `mech_log`
  vira a superfície principal. Por isso os furos do log (item 6) sobem para P1.
- **D-dono-2.** A IA só aparece **no fim**, com um resumo do combate (vitória, fuga, incapacitação ou morte).
  Isso substitui o item 1 (golpe final e morte viram template). O resumo tem guard de FallbackLLM e um
  fallback determinístico legível.
- **D-dono-3.** A história (texto livre, fora do combate) **abre o tabuleiro**. Quando o roteamento detecta
  conflito, a tela vira tabuleiro e dali em diante é só toque. Os itens 2 e 3 seguem P1.
- Os itens 4, 5 e 7 (números e contradições na prosa da rodada, linhas de sistema na prosa) deixam de existir
  no combate com baralho, porque não há prosa por rodada. Valem só para o **resumo final**.
- Com `RPG_CARD_DECK=off`, o fluxo narrado atual fica como está (não pode regredir). Nele se corrigem só o
  item 1 (desfecho) e o item 9 (loot duplo).

### Achados e causa no source

| # | Achado (prioridade) | Evidência no smoke | Causa no source |
|---|---|---|---|
| 1 | Golpe final e morte sem narração (P1 → resolvido por D-dono-2) | `hist-Brannoc.json` t8: `"Saqueador de Barba de Cobre perde os sentidos.\n\nMaça de Ferro (incomum) e +12 de ouro"`, tipo `LOOT`. `hist-Torvin.json` t4: `"Criatura do Poço tomba.\n\nMinério…"`. `hist-Ysolde.json` t7: `"⚔️ • primeira criatura hostil…: ganha condição cego\n• Ysolde: ganha condição cego\n• Ysolde executa sua Última Ação.\n• Última Ação: … erro (7 vs 12).\n\n☠️ Você tomba…"` | (a) A vitória manda `next: "loot"` (`agents/combat.py:2406`). O loot cria **outra** `AIMessage` (`agents/loot.py:523-527`). (b) Com espólio, `_validated_narrative` **sempre** troca a prosa da LLM pelo resumo canônico (`agents/loot.py:59-60` → `services/conflict_summary.py:335-346`, "X perde os sentidos."): as duas chamadas ao narrador (combate `:1614` e loot `:169`) são jogadas fora. (c) O texto do turno é **só a última** mensagem não humana (`services/turn_outcome.py:74-78`, usada em `:223` e `:239`; `api.py:2191`; histórico em `services/presentation_history.py:20-59`). (d) A morte é o template `_narrate_fall` com os 4 últimos logs crus em bullets (`agents/combat.py:1457-1464`, chamado em `:2235-2237`); a LLM nunca é chamada nesse caminho |
| 2 | Nome de inimigo de fallback vaza (P1) | Inimigo `fallback_primeira_criatura_hostil_que_surgir_na_galeria_1`, nome "primeira criatura hostil que surgir na galeria" (chip, presságio, modal de morte, mech_log), enquanto a prosa diz "goblin" (`hist-Ysolde.json` t2, t5, t7) | A dica do router entra crua. `is_generic_hint` só é verdadeiro sem tokens de conteúdo (`services/encounter_manifest.py:243-244`). "primeira", "que", "surgir", "galeria" não estão no `_STOP` (`:96-151`). O scanner devolveu "Goblin", que não compartilha token com a dica e foi descartado (`agents/combat.py:805-811`, `spawn_scanner_discarded`). A dica inteira virou grupo. O bestiário devolveu outra espécie, e a trava de identidade materializou a dica como nome (`agents/combat.py:658-674`, `spawn_identity_mismatch`) |
| 3 | Router esgota os 3 candidatos num ataque explícito (P1) | `hist-Brannoc.json` t2: "Saco a espada e ataco o bandido mais próximo" → storyteller (`route_fallback_reason: not_router_decision`), sem combate | (a) Esgotado o CLASSIFY, o router manda **sempre** para STORY (`agents/router.py:551-576`), embora `_EXPLICIT_HOSTILITY_RE` (`:40-44`) case com o texto. (b) DeepSeek: timeout de 12 s (`llm_setup.py:457-462`). (c) Groq `openai/gpt-oss-20b` (`llm_setup.py:349`): HTTP 400. O structured output vai por `function_calling` com `tool_choice` nomeado (`llm_setup.py:741-752`; stream: `:1393-1396`). Qualquer exceção HTTP é `transport` e quebra o laço **sem** retry semântico (`:1037-1058`). O corpo do 400 **não é registrado**: só `type(e).__name__` (`:1039`). Por isso a causa exata do 400 ainda não é conhecida (§4, Etapa 0). (d) Gemini flash-lite: erro (quota/chave) |
| 4 | Números da mecânica na prosa (P2 → só no resumo) | "força de 23 contra a esquiva de 13. Sete pontos de vigor" (Brannoc t4); "(3 → 0)", "(14 contra Esquiva 14)" (Ysolde t4); "crítico de 5 contra 12 que rasga 16 de vitalidade" (Ysolde t5); "tirando-lhe três fôlegos" (Ysolde t3); `desferi­‑o` com U+00AD + U+2011 (Ysolde t5) | O narrador recebe `<log_mecanico>` cru (`agents/combat.py:1580,1603-1605`) com aritmética do motor (`services/conflict_damage.py:231,263,287,333`: "dano 7×1=7", "Vitalidade 8 -> 1 (excedente 0)"; `services/conflict_orchestrator.py:1217-1220,334-337`). Também recebe "Vit a/b" (`agents/combat.py:1581-1585,1606`). O prompt diz "Vitalidade é fôlego/vigor" (`:1597`), o que confunde com o **Fôlego** das cartas (SPEC-328) |
| 5 | Prosa contradiz o motor (P2 → só no resumo) | mech_log "Minotauro → Você · erro", mas a prosa diz que o chifre rasga a perna (o dano veio do DoT, Ysolde t6). "Espada Gasta" narrada como "bastão" (Brannoc t7). "imóvel e pálido" com o inimigo ainda `ativo` (Brannoc t7) | Errar e sofrer DoT chegam como linhas soltas, sem relação entre si. A arma do herói não está no prompt (`agents/combat.py:1592-1611`). O estado do inimigo vai só como "Vit a/b" |
| 6 | O mech_log não fecha a conta (P1 por D-dono-1) | DoT "Toque Gélido da Morte" (3/rodada) sem linha. "3d10 1 + 1 +3 = 5 vs 12 · crítico · 16 dano" e "4 + 4 +4 = 12 vs 13 · crítico" sem explicação. A "Última Ação" foi no Minotauro, e a carta mirava outra criatura | (a) `mech_log` só lista `out["attacks"]` (`services/combat_preview.py:177-202`). O DoT só existe como texto em `out["logs"]` (`services/conflict_orchestrator.py:328-337`). (b) Dupla nos dados mantidos é crítico **por regra**, mesmo abaixo da Esquiva (`services/conflict_resolution.py:98-106,190-194`), mas o log não diz isso. (c) A Última Ação mira `_nearest_target` (`services/conflict_orchestrator.py:1925-1929`) e ignora o alvo declarado |
| 7 | Linhas de sistema coladas na prosa (P3 → somem com D-dono-1) | "O ferimento abre espaço no Baralho: Dor Surda." / "Membro Falho: o corpo cobra 1 de Fôlego nesta rodada." no fim da prosa (Ysolde t4, t5, t6) | `agents/combat.py:2345-2347` acrescenta `status_logs` (`services/card_status.py:82,117`) a `narrative` |
| 8 | Prosa com 3 saqueadores, luta com 1 (P3) | Brannoc t1 ("três vultos") × 1 inimigo por luta (t3, t6) | A contagem sai da frase do jogador (`em.hint_count`, `services/encounter_manifest.py:298` e `agents/combat.py:811`), no singular quando ele escolhe um alvo ("o saqueador ferido à minha esquerda"). O narrador não é avisado de que só N lutam |
| 9 | Loot duplo, contexto errado, "Você" maiúsculo (P3, `off`) | Torvin t4 "Minério de Ferro … +14 de ouro"; t5 "Vasculho o corpo" → "Em Skallgard, …, Você arranca da rocha … Minério de Ferro … dezoito moedas" | (a) O arquivista limpa `conflict_summary` no fim do turno (`agents/archivist.py:1229-1237`). Na busca seguinte, o loot rola a tabela da região de novo (`agents/loot.py:452-494`). `build_result` grava `loot_ref` (`services/encounter_manifest.py:676`), mas ninguém o consome. (b) O contexto diz "O jogador vasculha {local}" (`agents/loot.py:516-519`), não o corpo. (c) `normalize_protagonist_voice` troca "o jogador" por "Você" maiúsculo até no meio da frase (`services/prose_guard.py:137-145`, regex `IGNORECASE`) |
| 10 | Sangromante nível 1 morre na rodada 5 contra 2 inimigos (observação) | Ysolde t7 | Coerente com a arena (SPEC-341). **Só registro**, sem mudança |

### Princípios aplicados

- **Mecânica é Python, LLM só narra.** No baralho `on`, a rodada não chama LLM. O resumo final recebe fatos
  **em linguagem**, sem números. Um pós-filtro remove o que escapar.
- **Guard de FallbackLLM** em toda chamada nova. Sem LLM, sempre há texto determinístico legível.
- **Sem flag nova.** O comportamento novo depende de `RPG_CARD_DECK` (`config/flags.yaml:125-130`). As
  correções 2, 3, 6 e 9 são bugfix e valem em qualquer modo.

## 2. Requisitos

### A. Tabuleiro sem LLM por rodada (D-dono-1, D-dono-3) — só com `RPG_CARD_DECK=on`

- **R1 — Abertura do tabuleiro.** No turno em que o router abre o conflito, o `combat_node`:
  - prepara a cena como hoje: spawn (`_spawn_v4_enemies`), `_prepare_scene`, manifesto, pilhas e mão
    (`agents/combat.py:1763-1835`);
  - emite **uma** narração de entrada: história, a última prosa livre antes do tabuleiro (R30 vale aqui);
  - **não resolve rodada.** `combat.round == 0`, sem `run_round`, sem parser de jogada (`:1239`).
  - Iniciativa (D4 revisada pelo dono, 27/10): quem age primeiro na rodada 1 vem do **contexto da cena**,
    por sinal determinístico que já existe, e fica gravado em `combat_meta["initiator"]` (+
    `initiator_reason`):
    - emboscada contra o jogador (`world.encounter_surprise == "enemy"`, SPEC-296/storyteller) → inimigos
      primeiro, inclusive sobre a proteção de herói novo (`_early_game_reaction_initiator`);
    - o jogador iniciou o ataque (`combat_origin == "player_provoked"`, hostilidade explícita do router) ou
      emboscou (`encounter_surprise == "player"`) → jogador primeiro;
    - sem sinal claro → `None`: regra de iniciativa atual do motor (dados + proteção de herói novo).
    - Exceção "vigília que anula a surpresa": **não implementada** — nenhuma carta/condição existente anula
      surpresa mecanicamente (ver hand-back; candidatas listadas para o dono escolher).
- **R2 — Rodada sem LLM.** Em turno com combate ativo e declaração estruturada (`combat_declaration` com
  `jogadas`), o grafo inteiro faz **zero** chamadas a `get_llm(...).invoke/stream`. Isso inclui router,
  combate, loot, campaign_manager e arquivista. A Cicatriz obrigatória usa o caminho determinístico
  (`services/death_flow.py:336`, `_fallback_scar`) em vez do SMART de `agents/combat.py:2171-2173`.
- **R3 — Sem texto livre com tabuleiro aberto (D5 revisada pelo dono, 27/10).** Sem declaração
  estruturada **nunca** há LLM nem rodada, e **nem a fuga por texto** vale (`FLEE_RE` e a viagem lida pelo
  router não bastam):
  - recusa determinística, sem consumir rodada, sem rerrolar presságio e sem deixar o combate expirar
    (`idle_turns = 0`). Mensagem: "No tabuleiro, escolha suas Cartas na mão — ou use o botão Fugir. O texto
    livre espera o fim do conflito." Evento `combat.freetext_refused`;
  - a fuga é uma **ação estruturada**: `ActionRequest.action_kind = "flee"` (já existe, SPEC-325) vira
    `combat_declaration.acao.kind == "flee"`; o motor rola a trilha da perseguição (`_attempt_flee`, dado do
    motor, determinístico por semente) e diz se escapou. O front (SPEC-347) mostra o botão "Fugir" e esconde
    o input de texto durante o conflito `on`.
- **R4 — Registro da rodada (mensagem do turno).** A `AIMessage` da rodada é o registro: uma frase curta por
  evento, nesta ordem:
  - jogadas do herói e dos aliados (inclui reações);
  - jogadas dos inimigos;
  - DoT e condições;
  - quedas, mortes e Última Ação;
  - Cartas de Cena e de status.

  Formato de uma jogada: `<Ator> joga <Carta> em <Alvo>: <sabor da carta>. <Resultado>.` (exemplo em §3).
  - O resultado vem do motor: erro / acerto / crítico (dupla) / supercrítico, dano final, ferimento e
    região, condição aplicada, queda.
  - Ataque sem carta: `<Ator> ataca <Alvo> com <arma>`.
  - Aritmética de dados e defesa **não** entra na frase. Ela fica no `last_mech_log` (R7–R10).
  - Nenhuma linha interna crua do motor ("dano 7×1=7", "Vitalidade 8 -> 1", "Proteção -2 -> 5",
    "resist/vuln") aparece no registro.
- **R5 — Status de Carta no registro, nunca anexado à prosa.** As linhas de `card_status`
  (`services/card_status.py:82,117`) entram no registro (R4) e no `last_mech_log`. A concatenação de
  `agents/combat.py:2345-2347` acaba nos dois modos. Em `off` essas linhas nem existem, porque
  `card_status` só age com o baralho ligado.
- **R6 — `shadow` = `off` para o jogador.** Com `RPG_CARD_DECK=shadow`, a narração por rodada e o parser
  seguem como hoje (R1–R4 só valem em `on`).

### B. `mech_log` fecha a conta (item 6, P1)

- **R7 — DoT tem linha.** Todo tick de DoT (`_tick_conditions_v4`, `services/conflict_orchestrator.py:312-346`)
  gera um registro estruturado em `out["ticks"]`: `{actor_id, condition, damage_type, dano_final,
  vitalidade_depois}`. Gera também uma linha no `last_mech_log`:
  `Toque Gélido da Morte → Você · dano contínuo · 3 dano`. Vale também com DoT de 0 de dano final
  (ex.: absorvido), para o jogador ver o tick.
- **R8 — Crítico por dupla é explicado.** Quando `resultado ∈ {critico, supercritico}` e
  `total < esquiva_alvo`, a linha diz por quê: `… = 5 vs 12 · crítico (dupla de 1) · 16 dano`. Quando o
  total também supera a Esquiva: `crítico (dupla de 4)`. A regra do motor (`conflict_resolution.py:98-106`)
  **não muda**.
- **R9 — Alvo da Última Ação.** A Última Ação do herói mira o **último alvo hostil que ele declarou** na
  rodada (o `target_id` da última jogada ofensiva), se esse alvo ainda está ativo. Se não está, vale o
  `_nearest_target` de hoje. Para inimigo, a Última Ação mira o alvo do presságio dele, se houver. Senão,
  `_nearest_target`. A linha do log diz o alvo.
- **R10 — Conta fechada.** Em cada rodada, a soma de dano das linhas do `last_mech_log` que miram o herói é
  igual à queda da Vitalidade dele mais o excedente que virou Ferimento. O cálculo é o do motor:
  `resolve_damage_and_wounds`. Cura e ganho de Vitalidade aparecem como linha própria. O teste é um
  oráculo com seed fixa.
- **R10b — `last_mech_log` em todo modo `on`.** `store_mech_log` (`services/combat_preview.py:205-211`) segue
  gravando só com o baralho `on`. As linhas de R7/R8/R9 seguem o formato de `mech_log` (`:177-202`).

### C. Desfecho (D-dono-2; item 1; itens 4/5/7 aplicados ao resumo)

- **R11 — Um resumo da IA no fim (`on`).** No turno em que o conflito termina, há **uma** chamada FAST de
  resumo. Desfechos cobertos: `victory`, `fled`, `death`, `defeat`, `surrendered_enemy`, incapacitação do
  herói (`post_combat_state == "inconsciente"`) e `expired`. É a **única** chamada de LLM do turno
  (fora o loot, que em pós-vitória fica sem LLM, R18).
  - A mensagem do turno é: registro da última rodada (R4) + linha em branco + resumo.
  - Na morte, o resumo é seguido pelo texto fixo da Roda do Abismo: "A escuridão te engole — mas a Roda do
    Abismo ainda não decidiu. Voltar ao último respiro seguro, ou aceitar o fim aqui?". É o texto de hoje
    em `agents/combat.py:1461-1463`, preservado literalmente.
- **R12 — Fatos em linguagem, sem números.** O resumo recebe, em linguagem e **sem nenhum dígito**:
  - o desfecho;
  - quem caiu, morreu, fugiu ou se rendeu;
  - os ferimentos do herói (categoria e região);
  - a arma equipada (nome do item de `player.equipment.weapon`);
  - as cartas decisivas (as do golpe final e as que mais causaram dano, pelo nome);
  - o estado qualitativo de cada combatente: "ileso", "ferido", "à beira do colapso", "caído",
    "inconsciente", "morto".

  O glossário do prompt separa **Vitalidade** (vigor, resistência) de **Fôlego** (energia para jogar
  Cartas, que nunca é dano).
- **R13 — Pós-filtro de números e hifenização.** `prose_guard.strip_mechanic_numbers(text) -> tuple[str, int]`
  roda no resumo e:
  - remove parênteses com dígitos ou setas;
  - remove as orações "N contra M" / "N vs M";
  - remove "N (pontos de )?(vitalidade|vigor|dano|fôlego|esquiva|proteção)", com N em algarismo ou por
    extenso até "vinte";
  - normaliza U+00AD (removido) e U+2011 (vira `-`).

  Se removeu algo: evento `combat.narration_numbers_stripped` (com `count`). A remoção não deixa espaço
  duplo nem pontuação órfã.
- **R14 — Não contradizer o motor.** O resumo passa por `conflict_summary.validate_narrative_text`
  (`services/conflict_summary.py:349-376`). Em violação, cai no fallback R15. Os fatos de R12 incluem o que
  **não** aconteceu e o jogador poderia confundir: "o último golpe do Minotauro errou; o dano veio do
  Toque Gélido".
- **R15 — Fallback determinístico legível.** Quando a LLM é `FallbackLLM`, dá exceção, volta vazia ou viola
  R14, o resumo é um parágrafo montado em Python: frase por desfecho + `player_summary_text`
  (`services/conflict_summary.py:335-346`) + uma frase de ferimentos do herói. Nunca tem bullets de log
  cru, `⚔️`, ids nem números.
- **R16 — `off`: a narração da rodada final é o desfecho.** Com `RPG_CARD_DECK` `off`/`shadow`:
  - a rodada que encerra o conflito narra o desfecho pelo `_narrate` de hoje, com `fecho` por desfecho
    (vitória como hoje; queda nova: "o herói tomba; não declare a morte definitiva");
  - na morte, `_narrate_fall` deixa de despejar logs em bullets: usa `_narrate` com o fecho de queda + o texto
    fixo da Roda (R11), e o fallback é o de R15;
  - o resto do fluxo `off` (números, prompt, status) fica **byte a byte** igual (R6, §7).
- **R17 — O loot não apaga o desfecho (dois modos).** O texto do turno (`player_message`, resposta da API,
  histórico) é a junção, na ordem, das `AIMessage` (`type == "ai"`) não vazias depois da **última**
  `HumanMessage`. Cada uma passa por `strip_system_tags`, as idênticas são deduplicadas e a junção usa
  `"\n\n"`. Isso vale para `services/turn_outcome.py:74-78` (usado em `:223` e `:239`). Turno com uma
  só `AIMessage` fica byte a byte igual ao de hoje.
- **R18 — Loot pós-vitória sem LLM.** Com `conflict_summary` vindo do combate deste turno, o loot TREASURE:
  - **não** chama `_narrate`;
  - emite só a linha `[SISTEMA] {achado}` (o espólio exato);
  - não repete o resumo canônico ("X perde os sentidos.").

  O `message_type` do turno de vitória é `COMBAT` (`services/presentation_history.py:8-17`).

### D. Loot duplo (item 9)

- **R19 — Espólio do encontro uma vez só.** O loot pós-vitória grava em `combat.result`: `loot_claimed: True`,
  `loot_turn` e `location_id`. São campos opcionais; save antigo sem eles = não reclamado.
- **R20 — Revistar o corpo não rerrola.** No TREASURE, considere `combat.phase == "ended"`,
  `result.loot_claimed`, mesma `location_id` e texto que casa `corpo|corpos|cad[aá]ver|restos|bolsos|`
  + o rótulo de espécie do manifesto. Nesse caso **não** há `roll_loot`, ouro nem item. A mensagem
  determinística é "Você revira o corpo de novo; o que havia de valor já está com você." Evento
  `loot.corpse_already_looted`. Busca no ambiente ("vasculho a sala") segue como hoje.
- **R21 — Contexto do corpo.** Quando o TREASURE é sobre um corpo ainda não saqueado, o contexto do
  narrador diz "o corpo de {espécie}", não "{local}" (`agents/loot.py:516-519`). O sujeito do contexto passa
  a ser "Você", não "O jogador".
- **R22 — Voz do protagonista com caixa certa.** `normalize_protagonist_voice` usa "Você" só no início de
  frase (início do texto ou depois de `.!?` + espaço/quebra). No meio da frase, usa "você".

### E. Spawn sem nome de fallback (item 2, P1)

- **R23 — Núcleo da dica.** `encounter_manifest.hint_core(text) -> str` tira da dica:
  - oração relativa ("que …" até o fim);
  - locativo final ("na/no/em … <lugar>");
  - qualificadores de posição e ordem: primeir*, segund*, últim*, mais, próxim*, perto, longe, esquerda,
    direita, frente, trás, ferid*, maior, menor;
  - verbos de surgimento: surgir, aparecer, vier, estiver.

  `is_generic_hint` passa a avaliar o núcleo: "primeira criatura hostil que surgir na galeria" → genérica;
  "o bandido mais próximo" → "bandido".
- **R24 — Nome de inimigo nunca é frase do jogador.** O nome materializado pela trava de identidade
  (`agents/combat.py:658-674`) é o núcleo (R23), com só a inicial maiúscula e no máximo 3 palavras. Com o
  núcleo genérico, o scanner manda (R25). O id `fallback_*` só nasce do núcleo. Invariante testável: nenhum
  inimigo do manifesto tem nome com " que ", com mais de 4 palavras ou igual à dica crua.
- **R25 — Dica genérica: o scanner manda.** Com o núcleo genérico, a saída do scanner é aceita sem o filtro
  de identidade (`agents/combat.py:805-811`). Se o scanner falha (LLM esgotada), antes do "Inimigo Sombrio"
  (`:820-832`) tenta um nome do bestiário citado na última narração do assistente: tokens via
  `resolve_bestiary_name`, que é determinístico.

### F. Router com fallback determinístico de ataque (item 3, P1)

- **R26 — Hostilidade explícita abre combate quando o CLASSIFY esgota.** Nos dois ramos de fallback de
  `_classify` (`invoke_exception` e `not_router_decision`, `agents/router.py:551-576`), a rota é **COMBAT**
  se:
  - `_EXPLICIT_HOSTILITY_RE` casa a última fala;
  - não há negação ("não|nunca|sem" até 2 tokens antes do verbo);
  - existe um destes: ameaça narrada na última `AIMessage` (`_THREAT_NARRATED_RE`, `:451-453`), NPC em cena
    casado pelo texto, ou nome do bestiário no texto.

  Detalhes do payload:
  - `combat_target` = núcleo (R23) do sintagma após o verbo, ou `"Inimigos"`;
  - `route_source = "hostility_fallback"`, `route_fallback_reason` = o motivo original;
  - `interlocutor_reason = "classify_fallback"` (código existente, `services/interlocutor.py:47`).

  Sem esses sinais, segue STORY como hoje.
- **R27 — Registro do motivo do provider.** `LLMAttemptEvent` ganha `provider_error_code: str | None`: o
  `error.code` do corpo JSON do provider (ex.: `tool_use_failed`), validado por `_IDENT_RE`
  (`llm_setup.py:128`). Nunca entra o texto do prompt nem a mensagem livre. Vale no `invoke` (`:1037-1058`) e
  no caminho de stream (`:1397-1414` e equivalentes).
- **R28 — Groq `gpt-oss-20b` no schema do router.** A Etapa 0 reproduz o 400 e registra o código.
  Correção conforme o diagnóstico:
  - `tool_use_failed` / `json_validate_failed` (a geração saiu inválida): passa a ser falha **semântica**
    (`structured_failure_code="provider_tool_use_failed"`), com **1** regeneração no mesmo candidato,
    dentro de `STRUCTURED_SEMANTIC_MAX_ATTEMPTS` (`llm_setup.py:336`);
  - parâmetro rejeitado (ex.: `parallel_tool_calls`, `tool_choice` nomeado, `strict`): o `_apply` deixa de
    enviar esse parâmetro **só** para o par provider/modelo afetado;
  - schema rejeitado: ajustar `RouterDecision` (`agents/router.py:250-289`) sem mudar a semântica (ex.:
    defaults explícitos em `loot_context`/`target`).

  O resultado da Etapa 0 é anotado nesta spec (§4) no mesmo commit da correção.

### G. Coerência spawn × narração (item 8)

- **R29 — O narrador sabe quantos lutam.** A narração de entrada (R1 em `on`; a primeira rodada em `off`)
  recebe "Lutam contra você exatamente: {N} {espécie(s)}". Se a prosa anterior ou o scanner indicou mais
  do que o spawn criou (scanner `count` > instâncias, ou `cut_ids` do orçamento, `agents/combat.py:836-838`),
  recebe também "Os demais recuam e não entram na luta". A contagem de spawn **não muda** (D8).
- **R30 — Teste de coerência.** Com um scanner simulado que devolve `Saqueador × 3` e orçamento que corta 2, o
  prompt da entrada contém "exatamente: 1" e "Os demais recuam".

### H. Transversais

- **R31 — Telemetria registrada.** Eventos novos entram em `docs/operacao/EVENTOS_DE_LOG.md` e em
  `observability/events.py` (`tests/test_log_event_registry.py`): `combat.freetext_refused`,
  `combat.narration_numbers_stripped` (`count`), `combat.outcome_narration_failed` (`error`, `outcome`),
  `loot.corpse_already_looted`, `router.decision` com `source="hostility_fallback"`.
- **R32 — Saves.** Campos novos (`combat.result.loot_claimed/loot_turn/location_id`, `combat_meta.initiator`,
  `out["ticks"]`, que é transitório) são opcionais. Um save gravado no meio de um combate `on` antigo
  (`round ≥ 1`) retoma sem erro. Um save antigo com `combat.phase == "ended"` sem `loot_claimed` permite uma
  busca normal.
- **R33 — Guard de FallbackLLM** no resumo final e na narração de entrada: `try/except` + `is_fallback` →
  texto determinístico (R15). Nenhum `with_structured_output` novo.
- **R34 — Sem flag nova.** Nada novo em `config/flags.yaml`.

### Fora de escopo

- Layout, marginália, onde o registro e o `mech_log` aparecem, chip e retrato do inimigo: **SPEC-347**.
- Balanço (dano de cartas, letalidade, arena por Postura) e o item 10. Só se mede (§5) que R1 não tira a
  arena da faixa.
- Mudar a regra de crítico por dupla, o orçamento de encontro ou a contagem de spawn (D8).
- Latência do CLASSIFY (timeout de 12 s do DeepSeek, ordem de `ROUTES`) além do necessário para R28. Se for
  preciso, vira spec de latência própria.
- Números e contradições na prosa da rodada em `off` (itens 4, 5 e 7 em `off`): o fluxo `off` não muda (R16).
- Farm de loot por "vasculho o ambiente" repetido (comportamento de hoje, R20).
- Front (`web/`): esta spec não toca em `web/`. Se o front precisar de campo novo, quem pede é a 347.

## 3. Design técnico

### Arquivos novos

- `services/round_log.py` — registro determinístico da rodada (R4, R5, R7–R9).
  - `round_registry(out: dict, actors_by_id: dict[str, dict], status_logs: list[str]) -> list[str]`:
    frases curtas, ordem de R4.
    - Fonte estruturada: `out["attacks"]` (com `card_id`, `actor_id`, `target_id`, `resultado`,
      `dano_final`, `dice_kept`), `out["ticks"]` (R7), `out["deaths"]`, `out["incapacitated"]`,
      `out["terminal"]`, `out["last_stands"]`, `out["reactions"]`, `out["cards_used"]`.
    - Linhas de `out["logs"]` só passam se casarem a lista branca de frases já humanas (prefixos fechados:
      "ganha condição", "terminou.", "executa sua Última Ação", frases de Carta de Cena). Linhas com
      aritmética (`\d+\s*[×x*]\s*\d+`, `->`, `→ \d`, `resist/vuln`, `Proteção -`) são descartadas do
      registro; continuam no `mechanics_trace`.
  - `outcome_facts(outcome: str, conflict_summary: dict, player: dict, enemies: list[dict], last_out: dict) -> list[str]`:
    fatos sem dígitos (R12, R14).
  - `deterministic_outcome_text(outcome: str, conflict_summary: dict, player: dict) -> str` (R15).
- `tests/fixtures/spec346_smoke.py` — textos reais do smoke usados como respostas simuladas da LLM (§4).

### Arquivos alterados

- `agents/combat.py`
  - Ramo de abertura (`:1763-1835`) com `card_piles.mode() == "on"`: chama `_narrate_entrance(...)`
    (FAST, guard; fallback = `spawned_flavor`) e devolve o resultado **antes** da montagem de lados (`:1901`),
    com `combat_meta["round"] = 0`, `phase` = `active` e `initiator` gravado (R1).
  - Rodada `on` (`:2041-2058`): sem declaração estruturada, usa `FLEE_RE` ou recusa (R3). Nunca chama
    `_parse_turn_declaration`.
  - Narração (`:2230-2265`):
    - `on` e conflito aberto: `narrative = "\n".join(round_log.round_registry(...))`, sem `_narrate`;
    - `on` e conflito encerrado: registro + `_narrate_outcome(...)` (R11–R15);
    - `off`/`shadow`: como hoje, exceto `player_dead`, que usa `_narrate` com fecho de queda (R16).
  - `:2345-2347`: `status_logs` não se concatena mais a `narrative` (vão para o registro, R5).
  - Cicatriz (`:2170-2173`): `on` usa o caminho determinístico (R2).
  - `_grounded_template` (`:638-674`) e `_spawn_v4_enemies` (`:790-832`): R23–R25. Prompt de entrada: R29.
- `agents/loot.py`
  - Pós-vitória: sem `_narrate`, só a linha `[SISTEMA]` (R18).
  - R19: grava `combat.result.loot_claimed` no `result["combat"]`.
  - R20 e R21: guarda e contexto do corpo.
- `services/turn_outcome.py` — `_turn_ai_text(state)` substitui `_last_ai_text` (R17). Mantenha
  `_last_ai_text` como alias, porque `playtest/runner.py:742` tem a sua própria.
- `services/presentation_history.py` — turno de vitória com loot fica `COMBAT` (R18).
- `services/conflict_orchestrator.py` — `out["ticks"]` (R7); Última Ação com alvo preferido (R9):
  `_resolve_last_stands(scene, actors_by_id, sides, out, rng, preferred_targets: dict[str, str] | None = None)`.
- `services/combat_preview.py` — `mech_log` com ticks (R7), o rótulo `crítico (dupla de N)` (R8) e o alvo
  da Última Ação (R9).
- `services/encounter_manifest.py` — `hint_core`, `is_generic_hint` sobre o núcleo (R23).
- `services/prose_guard.py` — `strip_mechanic_numbers` (R13); `normalize_protagonist_voice` com caixa (R22).
- `agents/router.py` — `_hostility_fallback(state, last_human, world) -> dict | None` (R26).
- `llm_setup.py` — `provider_error_code` (R27); correção de R28.
- `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md` (R31).

### Formatos

Registro de rodada (`on`), com cartas reais de `data/cards/sangromante.json` e nomes do smoke:

```
Você joga Talho de Sangue Ralo no Goblin: um talho rápido; o preço do sangue já está embutido. Acerta — 5 de dano, ferimento leve no braço.
Goblin ataca Você com Lâmina Enferrujada: erra.
Toque Gélido da Morte corrói Você: 3 de dano contínuo.
O ferimento abre espaço no Baralho: Dor Surda.
```

Linhas do `last_mech_log` (R7–R9):

```
Você · Corte Raso → Goblin · 3d10 1 + 1 +3 = 5 vs 12 · crítico (dupla de 1) · 16 dano
Toque Gélido da Morte → Você · dano contínuo · 3 dano
Última Ação: Você → Goblin (alvo declarado) · 2d10 3 + 4 +4 = 11 vs 12 · erro
```

Fatos do resumo (R12; nenhum dígito):

```
Desfecho: vitória. Saqueador de Barba de Cobre perde os sentidos (golpe sem matar).
Arma do herói: Espada Gasta. Carta decisiva: Golpe do Penitente.
Herói: ferido (ferimento leve na perna). Não houve outros inimigos.
```

`combat.result` (R19):

```json
{"encounter_id": "g:0:8", "outcome": "victory", "loot_ref": "loot:g:0:8",
 "loot_claimed": true, "loot_turn": 8, "location_id": "skallgard"}
```

## 4. Plano passo a passo

Cada etapa: testes primeiro, depois o código, depois só os testes do escopo (`-n 2` no máximo). A suíte
completa é do coordenador, no pouso.

### Etapa 0 — Diagnóstico do 400 do Groq (R27, R28)

1. **Testes** (`tests/test_spec346_provider_error_code.py`):
   - `test_attempt_records_groq_error_code`: um `openai.BadRequestError` falso com corpo
     `{"error": {"code": "tool_use_failed", "message": "…prompt…"}}` → evento com `http_status=400`,
     `provider_error_code="tool_use_failed"`, e nenhum trecho de `message` no evento;
   - `test_error_code_rejects_non_ident`: um código com espaço ou `<` vira `None`.
2. **Implementação:** R27.
3. **Diagnóstico (com chave, o coordenador autoriza o custo, ≤ 5 requests):** um script em
   `docs/spec346/diag_groq_router.py` chama `get_llm(tier=CLASSIFY)` com
   `RPG_ROUTES='{"classify":[["groq","openai/gpt-oss-20b"]]}'` e o `RouterDecision` sobre as falas
   reais do smoke ("Saco a espada e ataco o bandido mais próximo"; "Avanço pela galeria escura com a lâmina em
   punho e ataco a primeira criatura hostil que surgir").
   - Anotar aqui o `provider_error_code` e a hipótese confirmada:
     - **H1** `tool_use_failed` (o gpt-oss gerou a chamada de ferramenta fora do formato);
     - **H2** parâmetro rejeitado;
     - **H3** schema rejeitado.
   - Resultado (executor, 27/10, 4 requests Groq): **não reproduzido** com prompt curto — 4/4 sucesso
     (`COMBAT`) via `function_calling`, sem 400. Logo o 400 do smoke é **intermitente** e compatível com
     H1 (`tool_use_failed`: gpt-oss gera a chamada fora do formato; H2/H3 descartadas, pois o mesmo
     schema/parâmetros passam). Correção aplicada conforme H1 (R28): 400 com `error.code` em
     {`tool_use_failed`, `json_validate_failed`} vira falha semântica
     (`provider_tool_use_failed`) com **1** regeneração no mesmo candidato. A causa exata do 400 original
     segue sem registro (o corpo não era logado); `provider_error_code` (R27) confirmará no smoke §6.

### Etapa 1 — Router com fallback de hostilidade (R26, R28)

1. **Testes** (`tests/test_spec346_router_fallback.py`, padrão de `tests/test_turn_trace_logs.py:53-72` com
   `FallbackLLM` e um `RoutedLLM` esgotado que devolve `AIMessage("")`):
   - `test_exhausted_classify_explicit_attack_opens_combat`: a fala de Brannoc t2, com a narração anterior
     de Brannoc t1 (com "três vultos", ameaça) → `next == "combat_agent"`,
     `route_source == "hostility_fallback"`, `combat_target == "bandido"`;
   - `test_exhausted_classify_without_threat_stays_story`: "ataco o ar" sem ameaça, NPC nem bestiário → STORY;
   - `test_negated_attack_stays_story`: "não ataco ninguém" → STORY;
   - `test_invoke_exception_branch_same_rule`;
   - `test_off_path_unchanged`: "ando pela estrada vazia" → `classify_fallback`, como hoje;
   - `test_groq_tool_use_failed_is_semantic_retry` (só se a Etapa 0 confirmar H1): um cliente falso que
     levanta 400 `tool_use_failed` na 1ª chamada e devolve tool call válido na 2ª → sucesso no Groq, 2
     tentativas, sem cair para Gemini.
2. **Implementação:** R26; R28 conforme a Etapa 0.

### Etapa 2 — Spawn sem nome de fallback (R23–R25)

1. **Testes** (`tests/test_spec346_spawn_hint.py`):
   - `test_hint_core_examples`: tabela com, no mínimo:
     - "primeira criatura hostil que surgir na galeria" → genérica;
     - "o bandido mais próximo" → "bandido";
     - "o saqueador ferido à minha esquerda" → "saqueador";
     - "a criatura que mora lá embaixo" → genérica;
     - "Goblin" → "goblin";
   - `test_generic_hint_accepts_scanner`: dica de Ysolde t2 + scanner simulado `[{"name": "Goblin", "count": 1}]`
     → inimigo com nome "Goblin", sem `spawn_scanner_discarded`;
   - `test_identity_lock_never_uses_raw_phrase`: bestiário simulado devolve outra espécie → nome ≤ 3 palavras,
     sem " que ", id `fallback_<núcleo>`;
   - `test_scanner_down_uses_bestiary_from_narration`: scanner `FallbackLLM` + última narração citando
     "goblin" → inimigo do bestiário (sem "Inimigo Sombrio");
   - `test_manifest_invariant_names` (R24) sobre os 3 casos acima.
2. **Implementação:** R23–R25.

### Etapa 3 — `mech_log` e motor (R7–R10)

1. **Testes** (`tests/test_spec346_mech_log.py`, seed fixa, `orch.run_round` real):
   - `test_dot_tick_has_line_and_structured_record`: herói com condição DoT 3 → `out["ticks"]` e linha
     "dano contínuo · 3 dano";
   - `test_crit_by_doubles_below_esquiva_is_labeled`: rng forçado para kept `[1, 1]`, total < Esquiva →
     "crítico (dupla de 1)";
   - `test_last_stand_uses_declared_target`: 2 inimigos, a jogada do herói mira o B, o herói entra em terminal
     → a Última Ação mira o B; com o B morto, vale o mais próximo;
   - `test_enemy_last_stand_uses_pressagio_target`;
   - `test_mech_log_accounts_for_hero_vitality` (R10): soma das linhas contra o herói = queda de Vitalidade
     + excedente, em 20 seeds;
   - regressão: `tests/test_spec334*` e `tests/test_combat_preview*` passam sem mudança de expected, exceto o
     rótulo novo de R8, que é atualizado no mesmo commit com a justificativa.
2. **Implementação:** R7–R10.

### Etapa 4 — Tabuleiro sem LLM (R1–R6)

1. **Testes** (`tests/test_spec346_board_no_llm.py`, `RPG_CARD_DECK=on`, MockLLM, `combat_node` real):
   - `test_opening_turn_deals_hand_without_round`: abertura → `round == 0`, mão presente, sem `run_round`
     (spy), 1 `AIMessage` de entrada;
   - `test_round_with_jogadas_makes_zero_llm_calls`: spy em `get_llm` de `agents.combat`, `agents.router`,
     `agents.loot`, `agents.campaign_manager`, `agents.archivist`, `services.encounter_preparation`,
     `services.death_flow` → nenhum `invoke`/`stream` numa rodada com `combat_declaration.jogadas`.
     Usa `app.invoke` do grafo (`main.py`);
   - `test_round_message_is_registry`: a mensagem contém o nome da carta, o sabor (`descricao`) e o resultado,
     e não contém "×", "->", "Vitalidade " seguido de dígito nem "⚔️";
   - `test_status_lines_go_to_registry_not_appended` (R5): as linhas de `card_status` aparecem como linhas do
     registro e o texto **não termina** com a concatenação antiga de `:2347`;
   - `test_free_text_during_board_is_refused`: "ataco o goblin" sem `jogadas` → `action_refused`, rodada
     inalterada, presságio inalterado, zero LLM;
   - `test_free_text_flee_still_works`: "fujo para a saída" → fluxo de fuga;
   - `test_scar_is_deterministic_on`: Cicatriz obrigatória sem chamada SMART;
   - `test_shadow_and_off_keep_narrated_rounds` (R6): `shadow` e `off` produzem o mesmo estado e a mesma
     chamada `_narrate` de hoje (snapshot da mensagem com MockLLM).
2. **Implementação:** R1–R6.

### Etapa 5 — Desfecho (R11–R18)

1. **Testes** (`tests/test_spec346_outcome.py`; a LLM simulada devolve os **textos reais do smoke** de
   `tests/fixtures/spec346_smoke.py`):
   - `test_outcome_summary_single_call_on`: vitória `on` → exatamente 1 chamada FAST; mensagem = registro +
     resumo + linha de loot;
   - `test_outcome_facts_have_no_digits`: `outcome_facts` em vitória, morte, fuga, rendição e expirado → nenhum
     `\d`; contém a arma ("Espada Gasta") e distingue Fôlego de Vitalidade no glossário;
   - `test_strip_mechanic_numbers_on_smoke_texts`, com remoção esperada nestes 5 trechos reais:
     - "força de 23 contra a esquiva de 13. Sete pontos de vigor";
     - "(3 → 0)";
     - "(14 contra Esquiva 14)";
     - "crítico de 5 contra 12 que rasga 16 de vitalidade";
     - "tirando-lhe três fôlegos" → "três fôlegos" sai.

     O resultado não tem espaço duplo nem "  ,", e emite `combat.narration_numbers_stripped`;
   - `test_soft_hyphen_normalized`: `"desferi­‑o"` → `"desferi-o"`;
   - `test_contradiction_falls_back` (R14): resumo simulado "o Saqueador de Barba de Cobre sobrevive e foge"
     com o saqueador em `mortos` → fallback R15;
   - `test_fallback_is_readable` (R15): `FallbackLLM` → parágrafo sem `•`, `⚔️`, ids nem dígitos, para cada
     desfecho;
   - `test_death_on_appends_wheel_text` / `test_death_off_no_bullets` (R11, R16): o texto da morte termina com
     a frase da Roda e não contém "• ";
   - `test_off_victory_keeps_round_narration` (R16, R17): em `off` com vitória, o texto final começa pela
     narração da rodada e termina com a linha de loot (sem "[SISTEMA]"); o caso de Torvin t4 não vira mais
     "Criatura do Poço tomba." sozinho;
   - `test_loot_post_victory_no_llm` (R18): spy → 0 chamadas no loot; o tipo do turno é `COMBAT`;
   - `test_single_ai_message_turn_unchanged` (R17): turnos de storyteller, NPC e loot de loja → mesmo
     `player_message` de antes (snapshot);
   - `test_stream_final_extends_shown` (R17 × SPEC-316): o texto streamado é prefixo do final
     (`narrative_sink.replace_reason == "none"`) num turno `off` de vitória.
2. **Implementação:** R11–R18.

### Etapa 6 — Loot duplo e voz (R19–R22)

1. **Testes** (`tests/test_spec346_loot_once.py`):
   - `test_corpse_search_after_claimed_loot_does_not_reroll`: reproduz Torvin t4 → t5 (vitória, arquivista
     limpa `conflict_summary`, "Vasculho o corpo da criatura") → ouro e inventário inalterados, a mensagem
     de R20 aparece, evento registrado;
   - `test_environment_search_still_rolls`;
   - `test_old_save_without_loot_claimed_allows_search` (R32);
   - `test_corpse_context_mentions_species` (R21);
   - `test_protagonist_voice_case`: "Em Skallgard, o jogador arranca" → "Em Skallgard, você arranca";
     "O jogador avança." → "Você avança.".
2. **Implementação:** R19–R22.

### Etapa 7 — Coerência de contagem (R29, R30)

1. **Testes** (`tests/test_spec346_spawn_count_narration.py`): `test_entrance_prompt_states_exact_count`
   (R30), capturando o `SystemMessage` da narração de entrada.
2. **Implementação:** R29.

### Etapa 8 — Telemetria, saves, arena

1. **Testes:** `tests/test_log_event_registry.py` verde com os eventos novos (R31);
   `test_spec346_saves.py::test_mid_combat_old_save_resumes_on` (R32).
2. **Medição de não regressão do balanço (R1 tira a "rodada grátis" da abertura):**
   `bash scripts/dev/py.sh docs/spec341/arena_spec341.py posturas --seeds 20:100` (`-n` ≤ 2, conforme a regra
   da máquina). Nenhuma Postura sai da faixa aprovada pelo dono (45–85 %). Os números entram em
   `docs/spec346/arena.md`. Se sair da faixa: parar e devolver ao dono (D4).

## 5. Critérios de aceite

- [ ] Etapa 0 anotada em §4 (código do 400 e hipótese) e R28 aplicado conforme o diagnóstico
- [ ] Item 1: os testes da Etapa 5 passam; nenhum turno de desfecho (`on` ou `off`) mostra só o template ou os bullets
- [ ] Item 2: os testes da Etapa 2 passam; invariante R24
- [ ] Item 3: os testes da Etapa 1 passam
- [ ] Itens 4/5/7: no `on` não há prosa por rodada; o resumo passa por R12–R14 (testes com os textos reais do smoke)
- [ ] Item 6: os testes da Etapa 3 passam, incluindo o oráculo R10 em 20 seeds
- [ ] Item 8: o teste R30 passa
- [ ] Item 9: os testes da Etapa 6 passam
- [ ] Item 10: registrado em §1 (sem mudança)
- [ ] D-dono-1: rodada `on` com zero chamadas de LLM no grafo inteiro (teste de spy)
- [ ] D-dono-3: abertura sem resolução de rodada; texto livre recusado sem LLM
- [ ] `off`/`shadow`: os testes de combate existentes passam sem mudar expected (fora o rótulo R8, que só aparece em `on`)
- [ ] Arena por Postura dentro de 45–85 % (`docs/spec346/arena.md`)
- [ ] Eventos novos registrados (R31); nenhuma flag nova (R34)
- [ ] Guard de FallbackLLM no resumo e na entrada (R33)
- [ ] Saves antigos continuam carregando (R32)
- [ ] `uv run pytest` verde (suíte completa offline, só o coordenador, no pouso)
- [ ] Revisão independente `Sol` sem P0/P1 aberto
- [ ] Smoke real §6 executado e registrado em `docs/spec346/smoke-final.md`

## 6. Smoke test com LLM real (≤ 30 turnos)

API local `legacy`. Flags de cartas `on` como no smoke de 27/10 (`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`,
`RPG_SCENE_CARDS`, `RPG_ENEMY_DECKS`, `RPG_CARD_REWARDS`, `RPG_COMBAT_NONLETHAL`). DeepSeek primário. Teto:
30 turnos no total e `--max-cost` do harness, quando usado. Registrar em `docs/spec346/smoke-final.md`, com
trechos do histórico (sem segredos).

1. **Abertura e rodada sem LLM (Brannoc, Skallgard):** "Saco a espada e ataco o bandido mais próximo"
   abre o tabuleiro (round 0, mão visível). Jogar 3 rodadas por cartas. Nos logs do servidor, nenhum
   `llm.attempt` nos turnos de rodada. Cada rodada mostra o registro (R4), e o `last_mech_log` fecha a
   conta (R10).
2. **Vitória (mesmo personagem):** o desfecho mostra registro + resumo da IA (sem números, arma certa) +
   espólio. Depois, "Vasculho o corpo" → nada novo (R20).
3. **Morte (Ysolde, Sangromante nível 1):** "ataco a primeira criatura hostil que surgir" → o inimigo tem
   nome de espécie (nunca a frase). Jogar até a queda → resumo da IA + o texto da Roda, sem bullets.
   DoT, crítico por dupla e Última Ação aparecem certos no `mech_log`.
4. **Fuga (terceiro personagem):** abrir o combate e declarar fuga → resumo de fuga.
5. **Router esgotado:** reiniciar a API com `RPG_ROUTES` cujo CLASSIFY só tem um candidato inválido (modelo
   inexistente). "Ataco o saqueador" com ameaça narrada → o combate abre (`route_source=hostility_fallback`).
   Restaurar `ROUTES`.
6. **Groq:** repetir a fala do item 5 com o CLASSIFY só em `groq/openai/gpt-oss-20b` → sucesso ou
   `provider_error_code` registrado e coerente com a Etapa 0.
7. **Rodada `off`:** `RPG_CARD_DECK=off`, 1 combate até a vitória. A narração da rodada final aparece
   inteira, seguida do espólio (Torvin t4 corrigido), e o loot não dobra na busca seguinte.

## 7. Riscos & compatibilidade

- **Saves:** R32. Um save `on` com `round == 0` gravado no turno de abertura retoma pedindo cartas. Um save `on`
  antigo no meio do combate segue por `jogadas`.
- **`off` byte a byte:** R6/R16 restringem a mudança do `off` ao desfecho (morte e composição com o loot) e ao
  loot duplo. O teste de snapshot da Etapa 4 guarda isso.
- **R17 muda um contrato transversal** (texto do turno, usado pela API, histórico, playtest e invariantes:
  `playtest/invariants.py:526,1740`). Mitigação: só junta `type == "ai"` depois da última `HumanMessage`, e
  turno com uma só mensagem fica idêntico (teste). O revisor deve listar os nós que emitem mais de uma
  `AIMessage` no mesmo turno.
- **SPEC-345 `in-progress`** mexe em `player_summary_text` e `strip_system_tags`: rebase antes do pouso; os
  testes `tests/test_spec345_player_text.py` seguem verdes.
- **Balanço:** sem a "rodada grátis" na abertura, a letalidade sobe para o herói. Daí a medição da Etapa 8 e a
  D4.
- **Router:** o fallback de hostilidade só age com o CLASSIFY esgotado e com sinal de alvo. O caminho normal e
  os evals do router (SPEC-217/317) não mudam.
- **MockLLM/FallbackLLM:** o MockLLM devolve texto genérico no resumo, e os testes usam LLM simulada com os
  textos do smoke. Com `FallbackLLM`, entram os textos de R15. O `MockLLM` não pega erro de mapeamento: daí
  o §6.
- **Quota/latência:** no `on`, o combate fica mais barato e rápido: 0 chamadas por rodada (antes: parser
  CLASSIFY + narração FAST + Cicatriz SMART) e 1 FAST no fim. O loot pós-vitória perde 1 FAST. A retentativa
  do R28 adiciona no máximo 1 chamada Groq, só no 400 semântico.
- **Front:** a 347 decide como mostrar o registro e o `mech_log`. Esta spec não muda o schema da API além de
  campos opcionais em `combat.result` e do `provider_error_code` na telemetria.

## 8. Decisões

### Do dono (27/10)

- **D-dono-0** — Corrigir todos os achados do smoke; a spec nasce `approved`.
- **D-dono-1** — Com `RPG_CARD_DECK=on`, a rodada se resolve só por cartas, sem LLM. O registro (sabor da
  carta + resultado do motor) e o `mech_log` são a superfície principal. O item 6 vira P1.
- **D-dono-2** — A IA aparece só no fim, com resumo do desfecho (vitória, fuga, incapacitação, morte), guard
  de FallbackLLM e fallback determinístico legível. Isso substitui o item 1.
- **D-dono-3** — A história abre o tabuleiro: detectado o conflito, dali em diante é só toque. Os itens 2 e
  3 seguem P1.
- **D-dono-4** — Os itens 4, 5 e 7 só se aplicam ao resumo final. Com `off`, o fluxo narrado fica como está,
  corrigindo só os itens 1 e 9.
- **D-dono-5** — Itens 8 e 10 mantidos (o 10 só registro). Retrato do inimigo vai para a SPEC-347.

- **D-dono-6 (D4 revisada, 27/10)** — A abertura entrega a mão **sem rodada grátis**, mas quem age primeiro
  vem do contexto da cena: emboscada contra o jogador → inimigos primeiro; o jogador iniciou o ataque →
  jogador primeiro; sem surpresa clara → regra de iniciativa atual do motor. Sinal determinístico já
  existente (`encounter_surprise`, `combat_origin`); sinal ambíguo cai no neutro. Exceção de "vigília":
  só com carta/condição que já anule surpresa mecanicamente (hoje nenhuma; ver hand-back).
- **D-dono-7 (D5 revisada, 27/10)** — Com o tabuleiro aberto **não existe texto livre, nem fuga por texto**.
  A fuga é o botão "Fugir" (ação estruturada `flee`), que rola o dado no motor e resolve se escapa. O input
  de texto fica desabilitado/escondido durante o conflito `on` (SPEC-347 no front; o contrato da API é desta
  spec).

### Recomendações do autor (valem como aprovadas salvo veto do dono na revisão)
- **D6 — Composição do turno por junção das `AIMessage` do turno (R17),** em vez de o combate não emitir e
  passar a prosa ao loot por campo transitório. A junção é genérica, não exige campo novo no `GameState` e
  preserva o stream (o final estende o mostrado).
- **D7 — O pós-filtro remove trechos (R13) em vez de descartar o resumo inteiro.** Descartar por qualquer
  número mataria resumos bons por um "dois saqueadores". A lista é fechada a substantivos de mecânica.
- **D8 — Item 8 por coerência narrativa, sem mudar a contagem de spawn (R29).** Aumentar o spawn para N
  mexeria na letalidade e no orçamento (SPEC-203 R4). Se o dono preferir respeitar o N do scanner até o
  orçamento, isso vira spec de balanço própria.
- **D9 — Groq: correção pela causa medida (R28),** com no máximo 1 regeneração no 400 semântico. Trocar o
  modelo de CLASSIFY ou a ordem de `ROUTES` fica fora (spec de latência).
- **D10 — Última Ação mira o alvo declarado (R9).** O docstring de `_resolve_last_stands` fala em "alvo vivo
  mais próximo" como semântica mínima, não como regra de design. Mirar o declarado é o que o jogador espera
  da carta que escolheu.
- **D11 — Cicatriz determinística no `on` (R2).** A Cicatriz gerada por LLM no meio da rodada quebraria o
  "zero LLM". O resumo final pode citá-la pelo nome.

## 9. Registro de implementação (executor, 27/10)

Desvios e escolhas que o revisor deve conhecer:

- **Abertura só com `COMBAT START`** (R1): o atalho do tabuleiro vale quando o router abre o conflito
  (`is_start`). Encontro que chega ao nó com `enemies` já preenchidos e sem a marca (testes, e2e, saves)
  segue o caminho de antes e resolve rodada por declaração estruturada.
- **R3/D5 sem texto, nem fuga**: a recusa também zera `combat_flee_attempt` (viagem lida pelo router).
  A fuga é `ActionRequest.action_kind="flee"` (contrato que já existia); o nome da ação na API é `flee`.
- **R9 (Última Ação)** vale em todos os modos (não só `on`); **R8 (dupla)** idem — afeta só o texto do
  `mech_log`, que só é gravado com o baralho `on`.
- **R16**: `_narrate_fall` agora devolve só a frase de queda + a Roda; a prosa da queda `off` sai do
  `_narrate` (com `fecho_override`), com o texto R15 como fallback.
- **R18** vale nos dois modos (`on` e `off`): o loot pós-vitória nunca chama LLM.
- **Etapa 0**: o 400 do Groq não reproduziu em 4 requests (intermitente); correção por H1 (§4).
- **Testes antigos atualizados** (expected mudou por decisão do dono, não por conveniência):
  `test_api_jogadas` (rodada `on` não narra), `test_spec345_mech_log`/`test_wound_status_cards`
  (texto livre é recusado: agora declaram ação estruturada), `test_review_high_integration`/
  `test_spec345_player_text` (loot pós-vitória sem LLM e sem repetir o resumo canônico).
- **Exceção "vigília" (D4 revisada)** não implementada: nenhuma carta/condição existente anula surpresa.
- **Front (`web/`) não foi tocado**: esconder o input de texto e o botão "Fugir" ficam com a SPEC-347.
- **Arena**: ver `docs/spec346/arena.md`.
