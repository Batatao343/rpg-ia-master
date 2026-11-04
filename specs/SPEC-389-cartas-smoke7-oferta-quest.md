# SPEC-389 — Cartas: achados do 7º smoke (oferta de retrato que some sem log, entrega de missão que não fecha, presságio frustrado no painel, Reação na prosa, Voto, escolta falha e 5 arestas de texto/UI)

> **Status:** `approved` (04/11, coordenador, autorização do dono "manda bala"; D-389-1..8 pelas recomendações (a) do §8, veto do dono possível)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-327
> **Origem:** 7º smoke real (04/11), feito no §6 da SPEC-387. Staging: achado S7-1 em
> [docs/spec387/smoke-staging.md](../docs/spec387/smoke-staging.md) § Achados. Local: achados 1–11 e "Não verificado" em
> [docs/spec387/smoke-local.md](../docs/spec387/smoke-local.md). A evidência bruta fica no scratchpad do coordenador (`smoke6stg/s7*`, `vlogs/all.json`, `out/i*.json`).
> **Depende de:** SPEC-387 com o código na `main` (`in-progress`, só falta o §6). Esta spec corrige o que o smoke da 387
> achou e não reabre os requisitos dela.
> **Desbloqueia:** fechar como `done` a 387 e o épico de cartas sem pendência aberta (política do dono: zero pendência, P3 inclusive).
> **Risco:** `médio`: efeito pago (oferta de retrato), kill switch lido por várias instâncias, conclusão de missão (recompensa) e texto de combate.
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. Esta spec não muda evaluator, expected, baseline, dataset, arena, `web/e2e/contracts`,
> os limiares de `scripts/cards/{lint,sim,promote}.py` nem o golden da SPEC-330.
> **Evidência:** para cada R há um teste que falha antes da mudança (§4). S7-1 também precisa de uma medição em staging com logs lidos na mesma janela (§6).

Rótulos: **[F]** é fato no source (`main` em `ef6cdca1`). **[H]** é hipótese com evidência, que a Etapa 0 ou o 1º teste confirma ou derruba.
**[D]** é decisão do dono (§8).

---

## 1. Contexto & Objetivo

O 7º smoke confirmou 4 dos 5 itens de staging da 387. Sobrou **1 P2 em staging**: a oferta paga "Gerar retrato" ainda some
em parte dos carregamentos, e **nenhum** dos 4 logs que a 387 criou disparou. No navegador a oferta apareceu em 4 de 6
carregamentos e no cliente da API em 0 de 6, na mesma partida. O smoke local achou **1 P2**: a entrega de missão por
frase livre não fecha a quest, e o turno ainda zerou o arco. Achou também **7 P3** de texto e UI, deixou **1 cena "não
verificada"** (escolta falha) e fez **2 observações** sobre o roteiro e o `draft.py`.

O objetivo é: (1) **todo** caminho que zera `retrato.gerar` fica com a causa no log, e a diferença entre navegador e API é
explicada por uma medição que se lê **dentro da retenção curta dos logs da Vercel**; (2) corrigir a causa que essa
medição apontar; (3) corrigir os outros achados, cada um com teste determinístico; (4) tornar a escolta falha verificável
por seed. Princípios: **mecânica é Python** (0 LLM por rodada); **ausência de log não pode ser ambígua**, ou seja, a
medição tem controle positivo; **o estado salvo é a fonte**; **voz do jogador** nas superfícies de combate; nenhuma flag
nova sem registro em `config/flags.yaml`.

### 1.1 Achados e causa no source

| # | Achado (prio) | Causa no source |
|---|---|---|
| S7-1 | A oferta de retrato some sem log: navegador 4/6, API 0/6 (Necromante Renegado, execução 3). Na execução 1 (Onça Vazada) foi navegador 5/6 e API 6/6 (P2) | **[F]** Os caminhos que zeram `gerar` **sem log** são estes. (a) `_image_effect_open`: o switch `image_generation` está desligado com o snapshot carregado, sem `unreadable` (`api.py:2887-2890`), e esse retorno não loga. (b) O mesmo vale para `PricingUnavailable` de `require_paid_effect`, que retorna `False` calado (`api.py:2892-2893`; `services/finops_alerts.py:423-439`). (c) `peek_ceiling` engole `PricingUnavailable` e também devolve `None` sem perfil de preço válido (`services/image_quotes.py:137-154`). `_portrait_price_estilhas` guarda esse `None` no cache **por 60 s** como leitura "boa" (`api.py:2910-2925`): o R5 da 387 só deixou de guardar exceção. (d) `_portrait_registry` devolve `None` calado quando `_creature_art_live()` é falso, ou seja, `RPG_CREATURE_ART` diferente de `on`, perfil sem banco ou `RPG_DYNAMIC_ART_ENABLED` desligado (`api.py:2866-2874,2980-2981`). Com registro `None`, `_enemy_portrait` não pede preço (`api.py:3014-3017`). (e) `portrait_for` não oferece nada para inimigo de fallback (`services/creature_art.py:233-244`), com geração `pending` ou com arte própria/do tipo (`creature_art.py:268-271`). Uma linha `ready` em `store=private` de **outro** jogo vira `pending=True` (`creature_art.py:189-190`), o que apaga a oferta em toda partida que não é a de origem. Nada disso loga. **[F]** A causa do snapshot: `KillSwitches.snapshot` mantém o último snapshot bom **sem limite de idade** enquanto a releitura falha, e tenta de novo a cada TTL de 5 s (`services/kill_switches.py:162-186`). A falha loga `kill_switch_load_failed` por `log.warning` simples, sem a correlação de `log_event` (`kill_switches.py:172-178`; `observability/telemetry.py:127-140`). **[H]** "Preso em off" exige releitura falhando sem parar, e isso deixaria `kill_switch_load_failed` no log. Os logs da execução 3 não têm essa linha. Então a hipótese do snapshot preso fica **fraca** e a medição decide. **[H]** Navegador × API: os dois usam `GET /game/state` (`web/src/api.ts:265-266`; `api.py:4111-4128`), então **não** é outro endpoint. As candidatas são: as leituras da API e do navegador em momentos diferentes em relação ao `on` do switch ou à geração do item 3 (que muda `pending`/`has_own_art`); uma linha `private` de outro jogo; ou a leitura da API num jogo diferente (`/game/state` sem `game_id` carrega o save mais recente, `api.py:4121-4124`, e a execução 1 abriu o jogo errado). O script de amostragem do coordenador não está no repo, então a Etapa 0 confere |
| L3 | `seed_save(14, "entrega")` mais "Entrego a prova da caça ao contratante": Osshari (Brekmar) reage, mas `quests_completed=[]`, sem técnica. O turno fez `campaign.replan reason=region_change` (`current_step` 1→0, total 3→5) (P2) | **[F]** Pela rota NPC **não existe** caminho que conclua uma missão secundária. `npc_actor` só grava a evidência `npc_interaction` (`agents/npc.py:1504-1511`). Os eventos `quest_completed` só nascem no storyteller, seja por `sync_action_progress` (verbos de busca, `services/quest_log.py:231-271`; `agents/storyteller.py:2603-2628`), seja por `proposed_events` do LLM (`storyteller.py:2066-2075`). **[F]** A quest da seed não tem `origin_name` (`tests/fixtures/spec368_seed.py:360-376`), então `sync_npc_interaction` nunca registra a conversa com a origem (`quest_log.py:340-364`). **[F]** A seed cria o jogo em Nova Arcádia (`spec368_seed.py:75-88`) e teletransporta o herói para Brekmar sem alinhar `campaign_plan.location` (`spec368_seed.py:407-410`). Por isso `_replan_reason` dá `region_change` (`agents/campaign_manager.py:118-124`), o comportamento desenhado para troca de região real. **[H]** A prova exige evidência com `created_turn < turn(evidência) ≤ turn atual` (`quest_log.py:390-398`). A seed grava `investigation` no turno 2, e o teste offline força `turn_count=5` (`tests/test_spec387_seed.py:231`), o que sugere que o turno do save é menor que 2. **[H]** O router resolveu "o contratante" para um NPC nativo de Brekmar (Osshari) e não para o `Contratante` da seed |
| L2 | Presságio frustrado não aparece no `/game/state` nem no painel "Efeitos da rodada" (o cumprido aparece) (P3) | **[F]** `round_board` monta o painel `combat.last_round_board` (`services/combat_preview.py:451,493`). Ele lê só `pressagios_cumpridos` (`combat_preview.py:649-663`) e ignora `pressagios_frustrados`, que o registro já usa (`services/round_log.py:397-399`). O front não tem esse tipo: `RoundEntryKind` só inclui `"pressagio"` (`web/src/combat/deck.ts:243,272`) |
| L4 | `hostility_fallback` só abre o combate se a narração recente citou o inimigo (P3) | **[F]** É a regra da SPEC-355 R5: criatura do bestiário só conta se `_recent_ai_tokens` a citou (`agents/router.py:375-381`), e o alvo genérico exige ameaça e criatura na última fala da IA (`router.py:363-368`). A seed `12` abre o combate e não fixa nenhuma narração anterior (`spec368_seed.py:311-312`; `_open_combat` em `:91-93`). O resultado do §6 item 12 dependeu do narrador ao vivo, não do código |
| L5 | Voto: "Goblin está provocado: a próxima intenção dele mira você (com chance)" sai mesmo quando o ataque da rodada **já** foi desviado para o herói; "muda de alvo"/"resiste" não saiu (P3) | **[F]** O desvio grava o log "X, provocado por Y, muda de alvo." (`services/conflict_orchestrator.py:2758-2760`), mas `_HUMAN_LINE_RES` não tem `muda de alvo\.$` e o registro descarta a linha (`round_log.py:26-53,391-395`). A linha "está provocado… próxima intenção" sai para **toda** Provocação nova, sem olhar `pressagios_desviados` nem a resistência da mesma rodada (`round_log.py:375-382`) |
| L6 | `name` da condição no estado é o id cru (`armadura_comprometida`), com `label` humano; outras condições têm `name == label` (P3) | **[F]** A view copia o nome gravado no ator (`api.py:3073-3083`). A SPEC-355 R8 decidiu que o rótulo é só de exibição e que o nome gravado não muda (`services/card_effects.py:1341-1361`). A UI usa `label ?? name` (`web/src/combat/TargetChip.tsx:92`) |
| L7 | Vitória por Reação: o registro diz "Você ataca Goblin com Espada Gasta"; só o `mech_log` cita "Encaixe do Golpe" (P3) | **[F]** O contra-ataque da Reação é um `_basic_attack` com `label=<nome da Reação>` e sem `card_id` (`conflict_orchestrator.py:1174-1187`; `label` default "Ataque" em `:1307`). `_attack_line` só trata o `label` "Última Ação" e cai no ramo da arma (`round_log.py:181-197`). O fecho já tem "Sua reação termina o serviço" (`round_log.py:611-612,806-807`) |
| L8 | Não verificado: R20 da 387 (objetivo `proteger` falho, com a narração da causa) (P3) | **[F]** A seed `4` sorteia o presságio **antes** de pôr o escoltado (`spec368_seed.py:286-288`, `_escort` em `:228-241`): o inimigo nunca mira o escoltado. **[H]** O patch manual do smoke (`vitalidade 0`, `status "morto"` em `party[0]`) tira o escoltado dos atores, e pela R19 da 387 `check_objective` devolve `None` (nunca "falhou"), daí `resultado: null` |
| L9 | A linha impressa de `promote.py` falha sem `--voz-pendente` (P3) | **[F]** `draft.next_commands` imprime `promote.py <lote> --onda N --protocolo lote-v2 --sim-report …` sem `--voz-pendente` nem `--revisor-voz` (`scripts/cards/draft.py:329-338`). `promote` recusa quando falta revisor real (`scripts/cards/promote.py:122-127`). O teste da 387 só faz `parse_args` |
| L10 | O rótulo "Mão Sombria" não aparece no Acervo da UI (API correta) (P3) | **[F]** O "Acervo de Cartas" do HUD mostra só nome, "preparada" e tipo (`web/src/components/Hud.tsx:74-87`), que é o "preparada · ativa" do smoke. O chip de subclasse só existe no `DeckCard` da aba de baralho (`web/src/components/tabs/DeckCard.tsx:47`) |
| L1 | Observação: o roteiro do §6 da 387 precisa de `"ruptura": true` (armadura) e `reaction_card_id` no corpo (reação) | **[F]** `ruptura` existe em `PlayStepRequest`, e `reaction_card_id` só no `ActionRequest`, fora de `jogadas` (`api.py:1886-1910`). O roteiro e as seeds não trazem o corpo pronto |
| L11 | Observação: `draft.py` com 2 de 4 Cartas reprovadas por orçamento no lint | Só follow-up da SPEC-369 (balanço). **Nenhuma** mudança de avaliador aqui (R28) |

## 2. Requisitos

Valem com o preset de `scripts/staging/staging_flags.json` (cartas `on`).

### A. Oferta de retrato: causa medida e corrigida (S7-1)

- **R1 — Toda omissão tem causa.** Um módulo novo, `services/portrait_offer.py` (o `api.py` tem mais de 1.000 linhas e não
  cresce), passa a decidir a oferta. Ele recebe `_image_effect_open`, `_portrait_offer_price` e a decisão de `gerar` de
  `portrait_for` por meio de um motivo devolvido junto. Para cada inimigo vivo sem `gerar`, a causa sai de um conjunto
  **fechado**: `switch_off`, `switches_unreadable`, `switches_stale`, `env_off`, `pricing_unavailable`, `price_absent`,
  `price_peek_failed`, `art_not_live:<flag|profile|dynamic_art>`, `registry_read_failed`, `fallback_enemy`, `pending`,
  `private_other_game`, `has_own_art` e `image_gate_failed`. Um teste de catálogo prova que cada `return` sem oferta em
  `_image_effect_open`, `_portrait_price_estilhas`, `_portrait_registry`, `_enemy_portrait` e `portrait_for` corresponde a
  exatamente 1 causa.
- **R2 — Uma linha por resposta, com controle positivo [D-389-2].** Cada `_combat_block` com inimigo vivo emite **1**
  `creature_portrait.offer_view`, com `offered` (n), `omitted` ({causa: n}), `switch_age_s` (idade do snapshot do kill
  switch), `price_cached` (bool), `art_live` (bool) e `instance` (id curto do processo, gerado no import). O `request_id`
  vem da correlação de `log_event`. Não leva id de jogo, DSN nem nome. O nível é `warning` quando há causa inesperada (todas
  menos `fallback_enemy`, `pending`, `private_other_game`, `has_own_art` e `art_not_live`) e `info` nos outros casos. O evento
  entra em `observability/events.py` e em `EVENTOS_DE_LOG.md`. O `offer_omitted` da 387 continua para as 4 causas de falha.
- **R3 — `price_absent` não fica 60 s no cache.** `_portrait_price_estilhas` só guarda no cache um preço **não nulo**. O
  `None` de `peek_ceiling` (sem perfil, perfil vencido, `PricingUnavailable` interno) não grava `at`, e a próxima view tenta
  de novo. O R5 da 387 (exceção fora do cache) continua.
- **R4 — Kill switch com idade e log estruturado [D-389-1].** `KillSwitches` guarda `_loaded_ok_at` e expõe `age_s`. A
  falha de releitura passa a `log_event("kill_switches", "load_failed", level="warning", error_class=…, snapshot_age_s=…)`,
  no lugar do `log.warning` simples (a métrica fica). Com a opção (a) da D-389-1, o último snapshot bom vale por **no
  máximo 60 s** desde a última leitura boa. Acima disso, as chaves fail-closed caem como num cold start ilegível, e a oferta
  registra `switches_stale`. O TTL de 5 s não muda. Testes com relógio falso: snapshot `off` lido, `on` no banco e releitura
  OK vira `on` em ≤ 5 s. Releitura falhando por 61 s deixa `image_generation` `off` com `switches_stale`. Releitura falhando
  por 30 s mantém o snapshot bom.
- **R5 — Medição na janela da Vercel.** Um script novo, `scripts/staging/portrait_offer_measure.py`, segue o padrão de
  `scripts/staging/jev_shadow_measure.py:212,272` (`vercel logs --json`, junção por janela). Numa só execução de **≤ 15 min**
  ele faz o seguinte, sem segredo na saída:
  - (1) grava `admin_kill_switch list` e as 5 últimas linhas do `audit` de `image_generation`, com hora;
  - (2) faz N leituras de `GET /game/state?game_id=<id>` pelo cliente da API e N carregamentos do navegador (Playwright,
    larguras do §6). Para cada um, registra hora, `X-Request-ID`, `x-vercel-id`, `game_id` (hash curto), endpoint da rede e
    `gerar` presente ou não;
  - (3) **na mesma execução**, baixa os logs da janela e junta cada amostra ao seu `offer_view` pelo `request_id`;
  - (4) grava `docs/spec389/offer-measure-<hora>.json` com a tabela amostra → causa e um resumo por instância.

  O script falha se alguma amostra ficar sem `offer_view` (controle positivo: sem linha, o problema é o log, não a oferta).
- **R6 — Correção da causa medida.** A etapa 2 corrige a causa que a R5 mostrar, com teste que reproduz o caso. Se for o
  snapshot, valem R4 e D-389-1. Se for `price_absent`, vale R3. Se for `private_other_game`, a linha `private` de outro jogo
  deixa de bloquear a oferta do **tipo** num jogo que não a vê, porque esse jogo pode gerar a sua: `pending` só vale para a
  origem. O teste usa um registro falso com linha `private` de outro `origin_game_id`, e a oferta tem de estar presente. Se a
  causa for a amostragem (jogo errado, momento antes do `on`, depois da geração), o script de R5 passa a exigir `game_id`,
  ordena as amostras antes do item de geração e registra a causa no §9. Causa que não seja nenhuma dessas entra no §9 com o
  teste novo.
- **R7 — Navegador × API explicado.** O §9 registra, a partir de R5, o endpoint e o `game_id` de cada lado e a causa de
  cada carregamento sem oferta. A spec só fecha com 0 amostras com causa inesperada na medição final do §6.

### B. Entrega de missão (L3)

- **R8 — Seed coerente.** `seed_save(14, "entrega")` passa a fazer quatro coisas: (a) grava `origin_name: "Contratante"` e
  `origin_entity_id` na quest `q368`; (b) alinha `campaign_plan.location` (e a região) ao local novo, num helper usado também
  pela `15`; (c) deixa `turn_count` maior que o turno da última evidência; (d) põe o `Contratante` como o único NPC `in_scene`
  de Brekmar no save. Teste: carregar o save e rodar 1 turno pelo grafo (MockLLM) não gera `campaign.replan reason=region_change`
  e `has_completion_proof(q368)` dá `True` depois da conversa com a origem.
- **R9 — Entrega pela rota NPC fecha a missão [D-389-3].** Uma função pura nova em `services/quest_log.py`,
  `delivery_ready(quests, npc_name, action_text, state) -> list[str]`, devolve as quests que satisfazem quatro condições: a
  quest está ativa e não é mecânica nem pessoal; o NPC que fala é a origem dela (`origin_name`/`origin_entity_id`); a ação
  tem verbo de entrega em 1ª pessoa (`entrego`, `trago`, `devolvo`, `aqui está`, lista fechada, com negação barrando);
  `has_completion_proof` passa contando a `npc_interaction` deste turno. `npc_actor` enfileira `quest_completed` com
  `source: "system"` em `pending_world_events`, pelo mesmo formato de `storyteller.py:2610-2620`. O `agents/npc.py` tem mais
  de 1.000 linhas e não cresce: a chamada substitui a de `sync_npc_interaction` (`npc.py:1509-1511`) por um helper que
  devolve `(quests, ready_ids)`. Testes: entrega à origem fecha (recompensa e técnica pelo `event_processor`, como no teste da
  387); entrega a outro NPC não fecha; "não entrego" não fecha; quest mecânica (`cacar_criatura`) não fecha; 2ª entrega no
  mesmo turno ou dentro do cooldown é recusada pelo validador de hoje.
- **R10 — Replanejamento por região fica como está.** É o comportamento da SPEC-252. Teste de não regressão: a troca real de
  região continua gerando `region_change`. A preservação do arco de abertura entre regiões é decisão à parte (D-389-8).

### C. Texto e UI de combate (L2, L5, L6, L7, L10)

- **R11 — Presságio frustrado no painel.** `round_board` emite uma entrada `tipo: "pressagio_frustrado"` por item de
  `pressagios_frustrados`, com `ator_nome`, `efeito: "Presságio frustrado: <Nome>"`, sem `carta_id`, `carta_nome` nem id. O
  front aceita o tipo novo em `RoundEntryKind` e mostra "Presságio frustrado: Goblin" em "Efeitos da rodada". A mudança é
  aditiva e o tipo `pressagio` não muda. Testes: `seed 2 frustrar` (50 sementes) gera a entrada no `/game/state`; teste de
  front em `web/tests/` para o texto.
- **R12 — Voto diz o que aconteceu [D-389-5].** `round_log` aceita `muda de alvo\.$` como linha humana. Quando, na mesma
  rodada, o provocado já foi desviado (`pressagios_desviados`) ou resistiu ("resiste à provocação de"), a linha "está
  provocado: a próxima intenção…" desse provocado **não** sai: fica só o desfecho. Ela continua quando o provocado ainda não
  agiu na rodada. Testes: `13 voto` (50 sementes) mostra "muda de alvo" e não mostra "próxima intenção"; uma Provocação antes
  da ação do inimigo mantém a linha.
- **R13 — Condição com nome humano na view [D-389-4].** Pela opção (a), `conditions[]` da view (inimigos, herói, aliados)
  ganha `id` (o nome gravado), e `name` passa a ser o rótulo (`condition_label`). `label` continua. O estado salvo não muda
  (SPEC-355 R8). Teste: `13 armadura` com ruptura dá `name == label == "Armadura Comprometida"` e `id == "armadura_comprometida"`.
  Nenhum consumidor do front compara `name` com um id: um teste lista os usos.
- **R14 — Reação na prosa do registro.** `_attack_line` passa a tratar o ataque de Reação, isto é, `label` diferente de
  "Ataque" e de "Última Ação", sem `card_id` e com o nome casando com uma Carta `tipo: reacao` de `out["reactions"]` ou do
  catálogo. Do lado do herói vira "Você reage com <Reação> em <alvo>: <resultado>."; do lado do inimigo, "<Nome> reage com
  <Reação>…". O `mech_log` e o golden da 330 não mudam. Teste: `13 reacao` (50 sementes) tem "reage com Encaixe do Golpe" na
  linha do registro e "Sua reação termina o serviço" no fecho determinístico.
- **R15 — Subclasse no Acervo do HUD.** A lista "Acervo de Cartas" do `Hud` mostra o rótulo de subclasse quando há
  (`Pó nos Olhos · Mão Sombria · preparada · ativa`). Teste de front com uma Carta de facção; e2e novo a 390 e 1440.

### D. Seeds e roteiro (L1, L4, L8)

- **R16 — Escolta falha determinística.** Variante nova `4 falha`: o escoltado é aliado ator **antes** do presságio
  (`_reseed(..., allies=[escoltado], want_alvo=<id>)`), com Vitalidade 1 e Esquiva mínima. O inimigo tem Vitalidade alta,
  para não morrer antes de agir. Teste (50 sementes): `objetivo_resultado == "falhou"`, o herói de pé, o desfecho
  `objective_failed` com o motivo e sem "perde os sentidos"/"apaga"/"cai" (R20 da 387).
- **R17 — Hostilidade sem depender do narrador.** Variante nova `12 hostil`: o combate **fechado** e a última fala da IA no
  save cita o goblin com uma palavra de ameaça (texto fixo da fixture). Teste: com CLASSIFY esgotado (LLM falso),
  "Ataco o goblin" abre COMBAT por `hostility_fallback`. A regra da SPEC-355 R5 não muda (D-389-7).
- **R18 — Corpo pronto do roteiro.** `tests/fixtures/spec368_seed.py` ganha `smoke_body(item, variant, game_id) -> dict`, com
  o corpo exato do `POST /game/action` de cada variante. `13 armadura` leva `jogadas[…].ruptura: true`; `13 reacao` leva
  `reaction_card_id` no nível de cima. Teste: cada corpo passa pelo `ActionRequest` e, pelo `TestClient` (MockLLM), produz o
  resultado prometido da variante.

### E. `draft.py` (L9, L11)

- **R19 — Linha do `promote` que roda.** `next_commands` imprime `promote.py <lote> --onda N --protocolo lote-v2 --sim-report
  <rep> --voz-pendente` (D-389-6). Teste: o comando impresso passa por `parse_args` **e** pela checagem de revisor de
  `promote` (função de `promote.py:103-127`) sem erro. O `promote.py` não muda.
- **R20 — Orçamento do rascunho é follow-up.** Só registro: a observação L11 vai como nota no §1 da SPEC-369 (o coordenador
  integra; esta spec não edita a 369 nem `lint`/`sim`/`promote`).

### F. Guardas

- **R21 — 0 LLM por rodada.** `tests/test_spec346_board_no_llm.py` verde; R11–R14 não chamam LLM.
- **R22 — Flags.** Nenhuma flag nova (o limite de 60 s da R4 é constante derivada, não env). Se a D-389-1 escolher env,
  registrar em `config/flags.yaml`.
- **R23 — Contrato aditivo.** View: `retrato` sem campo renomeado; `round_board` com o tipo novo; `conditions[].id` novo e
  `name` humano (D-389-4). Os tipos de `web/src/types.ts` são atualizados no mesmo commit.
- **R24 — Integridade.** `git diff main -- tests/spec330_equivalence.py tests/fixtures/spec330_legacy_golden.json evals/
  web/e2e/contracts scripts/cards/lint.py scripts/cards/sim.py scripts/cards/promote.py` vazio (teste de guarda).
- **R25 — Saves.** Saves antigos carregam. Nada novo é persistido além do que as seeds gravam.
- **R26 — Tamanho.** `api.py`, `agents/npc.py` e `services/conflict_orchestrator.py` não crescem (`tests/test_size_budget.py`).
  `services/round_log.py` fica abaixo de 1.000 linhas.

### Fora de escopo

- Mudar a regra de hostilidade da SPEC-355 R5 ou o replanejamento por região da SPEC-252 (só seeds e testes; ver D-389-7/-8).
- Balanço das Cartas do `draft.py`, mudança de avaliador, limiar, `promote` ou `lint` (L11 vai para a SPEC-369).
- Campo de diagnóstico público na view ou header novo para o retrato, salvo se a D-389-2 escolher (b).
- Mudar o nome gravado das condições no save (SPEC-355 R8 segue).
- Persistir a técnica da quest por outro caminho que não o `event_processor` de hoje.
- Ligar `RPG_PLOT_THREADS`/`RPG_FAUNA`/`RPG_CREATURE_GEN` ou mexer em preço/débito do retrato (S6-3 está ok).

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/portrait_offer.py` | `OfferCause` (Literal fechado), `gate() -> tuple[bool, str \| None]` (switch/preço), `summarize(views) -> dict`, `log_view(...)` (R1, R2) |
| `scripts/staging/portrait_offer_measure.py` | Medição da R5 (amostras, logs, junção, JSON) |
| `tests/test_portrait_offer_causes.py` | R1–R4, R6 |
| `tests/test_quest_delivery_npc.py` | R8–R10 |
| `tests/test_combat_text_smoke7.py` | R11–R14 |
| (nenhum arquivo de seed novo) as variantes entram em `tests/test_spec387_seed.py`, sem `test_spec389_*` (`docs/guias/TESTES.md`) | R16–R18 |
| `web/tests/spec389-round-frustrado.test.mjs`, `web/tests/spec389-hud-subclass.test.mjs`, `web/e2e/spec389-hud-subclass.spec.ts` | R11, R15 |

### 3.2 Arquivos alterados

- `api.py`: `_image_effect_open`, `_portrait_price_estilhas`, `_portrait_registry`, `_enemy_portrait` e `_conds` delegam a
  `services/portrait_offer.py` e a um helper de condição. O saldo de linhas é ≤ 0.
- `services/creature_art.py`: `portrait_for` devolve o motivo da ausência de `gerar` por um parâmetro de saída opcional
  (`reasons: list[str] | None`), sem mudar o dict público. Muda também o caso `private_other_game` se a R6 apontar.
- `services/kill_switches.py`: `_loaded_ok_at`, `age_s`, limite de 60 s, `log_event` (R4).
- `services/quest_log.py`: `delivery_ready` e o helper `(quests, ready_ids)`. `agents/npc.py`: troca 1 chamada (R9).
- `services/combat_preview.py` (R11), `services/round_log.py` (R12, R14), `web/src/combat/deck.ts`, `web/src/types.ts`,
  `web/src/components/Hud.tsx` (R11, R15).
- `scripts/cards/draft.py` (R19); `tests/fixtures/spec368_seed.py` (R8, R16–R18); `observability/events.py` e `EVENTOS_DE_LOG.md` (R2, R4).

### 3.3 Formatos

```json
{"event": "creature_portrait.offer_view", "request_id": "…", "instance": "a1b2c3",
 "offered": 0, "omitted": {"switch_off": 1}, "switch_age_s": 3.2, "price_cached": false, "art_live": true}
```

```json
{"tipo": "pressagio_frustrado", "ator_id": "enemy_goblin_1", "ator_nome": "Goblin", "lado": "inimigo",
 "carta_id": null, "carta_nome": null, "efeito": "Presságio frustrado: Goblin", "origem": "turno", "resultado": "efeito"}
```

Corpo de `smoke_body(13, "reacao", gid)`: `{"game_id": gid, "input_text": "Encerro a rodada", "reaction_card_id": "dev_encaixe",
"jogadas": [{"card_id": "bas_dev_golpe", "target_id": "<inimigo>"}]}`. Para `smoke_body(13, "armadura", gid)`, a jogada leva
`"ruptura": true`. Os ids e a ordem final vêm da Etapa 0.

## 4. Plano passo a passo

Em cada etapa: testes primeiro, depois o código, e só os testes do escopo (no máximo `-n 2`). A suíte completa é do
coordenador, no pouso. Etapas que tocam `round_log`/`combat_preview` rodam também `tests/test_spec363_*.py`,
`test_spec364_*.py`, `test_spec367_*.py`, `test_spec368_*.py`, `test_spec387_*.py` e `test_spec353_misc.py`.

### Etapa 0 — Confirmação (sem código de produto)

1. **S7-1:** pedir ao coordenador o script de amostragem da 387 (`smoke6stg/s7/`) e anotar o endpoint, se passa `game_id`,
   a hora de cada amostra da API e do navegador, a hora do `on` de `image_generation` (`admin_kill_switch audit`) e a hora
   do `/art/confirm`. Sem acesso, anotar e seguir: a R5 mede.
2. **S7-1:** confirmar no staging o nível de log (`RPG_LOG_LEVEL`, `RPG_LOG_LEVEL_CREATURE_PORTRAIT`). Se `info` não chega,
   usar `RPG_LOG_LEVEL_CREATURE_PORTRAIT=info` no preset de staging (a variável por área já existe,
   `observability/logging_setup.py:134-139`).
3. **S7-1:** listar as linhas de `app.creature_portraits` com `store=private` e `status=ready` (contagem por `tipo:` e
   `npc:`, sem id de jogo) para ver se `private_other_game` é plausível.
4. **L3:** com `seed_save(14, "entrega")`, anotar o `turn_count` do save, a rota do router e o NPC escolhido para "Entrego a
   prova da caça ao contratante" (MockLLM e 1 turno real se a cota permitir).
5. **L7:** confirmar que o ataque da Reação chega ao `round_log` com `label == <nome da Carta>` e `card_id is None`.
6. **L8:** confirmar que o patch manual tira o escoltado dos atores (R19 da 387) e por isso dá `resultado: null`.
7. Anotar tudo no §9.

### Etapa 1 — Instrumentação e medição (R1–R5)

1. **Testes:** `test_every_omission_has_one_cause` (catálogo), `test_offer_view_once_per_response`,
   `test_offer_view_levels`, `test_price_absent_not_cached`, `test_switch_age_and_structured_log`,
   `test_switch_stale_after_60s_fail_closed`, `test_switch_recovers_on_within_ttl`, `test_measure_join_by_request_id`
   (logs falsos), `test_measure_fails_without_offer_view`.
2. **Implementação:** `services/portrait_offer.py`, `api.py` (delegação), `creature_art.py` (motivo), `kill_switches.py`, o script.
3. **Medição:** o coordenador sobe a branch no staging e roda o script uma vez (§6, passo 1). O resultado vai para o §9 e
   decide a Etapa 2.

### Etapa 2 — Correção da causa (R6, R7)

1. **Teste** que reproduz a causa medida (um dos casos da R6), vermelho antes.
2. **Implementação** mínima e §9 com a explicação navegador × API.

### Etapa 3 — Entrega de missão (R8–R10)

1. **Testes:** `test_seed_entrega_no_region_replan`, `test_seed_entrega_has_proof_after_origin_talk`,
   `test_delivery_to_origin_completes`, `test_delivery_other_npc_no`, `test_delivery_negated_no`,
   `test_delivery_mechanical_no`, `test_delivery_cooldown_respected`, `test_real_region_change_still_replans`.
2. **Implementação:** `quest_log.py`, `npc.py` (troca de chamada), seed.

### Etapa 4 — Texto e UI (R11–R15)

1. **Testes:** `test_round_board_has_frustrado`, `test_voto_outcome_replaces_next_intent`, `test_taunt_before_action_keeps_line`,
   `test_condition_view_name_is_label`, `test_front_never_matches_condition_name_to_id`, `test_reaction_named_in_log`.
   No front: `spec389-round-frustrado`, `spec389-hud-subclass`; e2e `spec389-hud-subclass` a 390 e 1440 (`--workers=1`).
2. **Implementação:** `combat_preview.py`, `round_log.py`, `api.py`/helper de condição, `deck.ts`, `types.ts`, `Hud.tsx`.

### Etapa 5 — Seeds, roteiro e `draft.py` (R16–R20)

1. **Testes** (em `tests/test_spec387_seed.py`): `test_escort_fail_50_seeds`, `test_hostile_fallback_seed`,
   `test_smoke_bodies_parse_and_play`, `test_printed_promote_passes_reviewer_check`.
2. **Implementação:** `spec368_seed.py`, `draft.py`.

### Etapa 6 — Guardas (R21–R26)

O guarda vai num teste existente de guarda da 387 ou em `tests/test_portrait_offer_causes.py` (sem `test_spec389_*` novo).
Rodar `npm run typecheck`, `typecheck:e2e`, `lint` e `test`; `ruff format --check .` e `ruff check .`. Expected de teste antigo
que mudar (por exemplo `conditions[].name`) entra no §9 com o motivo.

## 5. Critérios de aceite

- [ ] Etapa 0 anotada no §9
- [ ] S7-1: toda omissão com causa e 1 `offer_view` por resposta (R1, R2); `price_absent` fora do cache (R3); kill switch com idade e log estruturado (R4)
- [ ] S7-1: medição da R5 feita e lida na mesma janela; causa corrigida com teste (R6); navegador × API explicado no §9 (R7)
- [ ] L3: seed coerente e entrega à origem fechando pela rota NPC (R8, R9); replanejamento por região intacto (R10)
- [ ] L2, L5, L6, L7, L10: R11–R15
- [ ] L8, L4, L1: seeds `4 falha`, `12 hostil` e `smoke_body` (R16–R18)
- [ ] L9: linha do `promote` que roda (R19); L11 entregue ao coordenador como nota da 369 (R20)
- [ ] Guardas R21–R26
- [ ] `uv run pytest` verde (suíte completa, coordenador, no pouso); front `typecheck`/`lint`/`test` verdes; e2e novo verde a 390 e 1440
- [ ] Guard de FallbackLLM mantido; nenhum `with_structured_output` novo
- [ ] Saves antigos carregam (R25)
- [ ] Revisão independente `Sol` sem P0/P1 aberto
- [ ] **Smoke real §6 (coordenador)** registrado em `docs/spec389/smoke.md`

## 6. Smoke test com LLM real (curto)

DeepSeek primário. Registrar provider, modelo, chamadas e custo em `docs/spec389/smoke.md` (trechos, sem segredos). Teto:
~12 turnos com LLM e **0** retrato pago (o S6-3 já foi verificado na 387).

**Staging** (`hosted-supabase`, preset com cartas `on`, conta sintética, limpeza no fim). `image_generation` fica **ligado
antes** da 1ª amostra; o script grava a hora do `on`, e no fim o switch é desligado e conferido com `list`.

1. **S7-1 (R1–R7):** abrir combate no Pântano da Melancolia ou na Floresta dos Sussurros (até achar um inimigo do bestiário
   com oferta) e rodar `scripts/staging/portrait_offer_measure.py` com 6 leituras da API (com `game_id`) e 6 carregamentos do
   navegador (1440, 390, 1440, 1280, 1440, 390), tudo numa janela de ≤ 15 min. Os logs da Vercel são baixados **pelo próprio
   script, no fim da mesma execução** (a retenção do plano hobby é de ~30 min; não deixe para depois). Esperado: 12/12
   amostras com `offer_view`, 12/12 com oferta, ou só causas esperadas (`pending`/`has_own_art`) com a explicação. Se faltar
   oferta por causa inesperada, anotar a tabela e **não** fechar a spec.

**Local** (`legacy`, mesmo preset, saves de `seed_save` com o corpo de `smoke_body`; rodadas do meio sem LLM):

2. `seed_save(14, "entrega")`: 1 turno "Entrego a prova da caça ao contratante" → `quest_completed`, a técnica no Acervo e
   nenhum `campaign.replan reason=region_change` no log.
3. `seed_save(2, "frustrar")`: 1 rodada → "Presságio frustrado: Goblin" em "Efeitos da rodada" a 390.
4. `seed_save(13, "voto")`: "muda de alvo" (ou "resiste") no registro, sem "próxima intenção" depois do desvio.
5. `seed_save(13, "armadura")` com `smoke_body` (`ruptura: true`): `conditions[].name == "Armadura Comprometida"` no `/game/state`.
6. `seed_save(13, "reacao")` com `smoke_body` (`reaction_card_id`): "reage com Encaixe do Golpe" no registro e a Reação citada no resumo final.
7. `seed_save(4, "falha")`: o objetivo falha e a narração conta a causa, sem desmaio (R20 da 387).
8. `seed_save(12, "hostil")` com `RPG_ROUTES='{"classify":[["groq","modelo-inexistente"]]}'`: "Ataco o goblin" abre o combate por `hostility_fallback`.
9. `draft.py` (1 chamada SMART + até 1 de reparo): seguir os 3 comandos impressos; o `promote` roda sem editar a linha.
10. UI a 390 e 1440: "Mão Sombria" no Acervo do HUD.
11. Varrer o `/game/history` das campanhas: 0 ids, 0 nome do herói, 0 `": … terminou"`, 0 "cumpre o presságio".

## 7. Riscos & compatibilidade

- **R2 aumenta o volume de log:** 1 linha por view de combate. Com nível `info` fora de staging, o volume é desprezível; com
  `warning` só nas causas inesperadas.
- **R4 (a) pode tirar a oferta mais cedo** num incidente de banco longo (> 60 s): esse é o sentido do fail-closed da
  SPEC-236 R10 (não reabrir gasto com snapshot velho). Em leitura normal nada muda (TTL de 5 s).
- **R6 `private_other_game`**, se for a causa: o jogo B passa a poder gerar o retrato do tipo enquanto a linha `private` do
  jogo A ainda não foi promovida a `shared`. Risco de 2 gerações do mesmo tipo. A unicidade por chave do registro
  (`creature_portraits`) decide qual fica; o débito é por jogo. O revisor confere a idempotência.
- **R9 fecha missão por frase livre na rota NPC.** A prova determinística continua obrigatória (`has_completion_proof`,
  cooldown, 1 por turno), e o LLM não decide nada. Uma frase de entrega sem prova não fecha.
- **R13 muda o valor de `conditions[].name` na view.** O front já usa `label ?? name`. Teste de front existente que fixe o id
  entra no §9. O save não muda.
- **R14 e R12 mexem em `round_log`;** a guarda R24 prova que o golden da 330 não muda.
- **Sobreposição:** a SPEC-381 (`draft`) vai mover rotas do `api.py`. Se pousar antes, o executor aplica R1 no módulo novo.
  **MockLLM/FallbackLLM:** guard mantido. **Quota:** nenhuma chamada nova no jogo.

## 8. Decisões

### Do dono / coordenador (prompt de 04/11)

- Escopo: todos os achados do 7º smoke (S7-1, local 1–11), P3 inclusive, e a escolta falha tornada verificável.
- Integridade de eval: avaliador, arena, goldens, `web/e2e/contracts` e limiares intocados; L11 só como follow-up da 369.
- A medição de S7-1 tem de rodar e ser lida dentro da retenção dos logs da Vercel.

### Pendentes do dono (com recomendação do autor)

- **D-389-1 — Snapshot do kill switch em falha de releitura.**
  - (a) **Recomendado:** manter o último snapshot bom por no máximo 60 s desde a última leitura boa; acima disso, as chaves
    fail-closed caem e a oferta registra `switches_stale`. Logar a falha por `log_event` com a idade. O TTL de 5 s fica.
  - (b) Manter como hoje (sem limite) e só logar com a idade.
  - (c) Invalidação ativa (versão na tabela lida a cada view): mais leitura no banco, e não resolve nada que a medição tenha mostrado.

  Obs.: pelo source, com releitura OK um `off` antigo vira `on` em ≤ 5 s. "Preso" só acontece com o banco falhando, e aí
  `image_generation` fica `off` de propósito no staging (`RPG_DAILY_SPEND_CAP_BRL`).
- **D-389-2 — Onde fica o diagnóstico da oferta.**
  - (a) **Recomendado:** só no log (`offer_view`), correlacionado por `X-Request-ID`, sem mudar o contrato.
  - (b) Campo público `retrato.sem_oferta` com a causa grossa (`indisponivel`/`pendente`): dispensa os logs, mas é contrato
    novo e expõe o estado do switch.
- **D-389-3 — Entrega de missão pela rota NPC.**
  - (a) **Recomendado:** conclusão determinística quando o NPC que fala é a origem, há prova e verbo de entrega (R9).
  - (b) Só corrigir a seed e mandar o roteiro pela rota do storyteller (a entrega pela conversa continua sem fechar no jogo real).
  - (c) Campo novo no structured output do NPC para propor `quest_completed` (mais LLM, e exige guard).
- **D-389-4 — Nome da condição na view.**
  - (a) **Recomendado:** `name` = rótulo e `id` novo com o nome gravado.
  - (b) Manter `name` = id, documentar que a exibição é `label` e só testar o front.
- **D-389-5 — Texto do Voto.**
  - (a) **Recomendado:** depois do desvio ou da resistência na rodada, só o desfecho ("muda de alvo"/"resiste").
  - (b) Manter as duas linhas, trocando "a próxima intenção" por "esta rodada".
- **D-389-6 — Revisor na linha impressa do `promote`.**
  - (a) **Recomendado:** `--voz-pendente` (o rascunho ainda não teve revisão de voz).
  - (b) `--revisor-voz <SEU_NOME>`, que o operador edita antes de rodar.
- **D-389-7 — `hostility_fallback`.**
  - (a) **Recomendado:** manter a regra da SPEC-355 R5 e tornar o teste determinístico pela seed `12 hostil` (R17).
  - (b) Também aceitar um inimigo do manifesto de encontro pendente sem citação. Muda o roteamento; ficaria numa spec à parte.
- **D-389-8 — Arco de abertura em troca de região.**
  - (a) **Recomendado:** manter o replanejamento da SPEC-252 (R10) e só corrigir a seed.
  - (b) Abrir follow-up para preservar o arco ligado à trama de abertura (SPEC-351) quando o herói muda de região.

Nenhuma bloqueia a Etapa 0 nem a Etapa 1. A Etapa 2 depende de D-389-1, e as Etapas 3 e 4 dependem de D-389-3/-4/-5. O
executor segue a recomendação se o dono não vetar até a aprovação.

## 9. Registro de implementação

Executor (Sonnet), 04/11. Decisões D-389-1..8 pelas recomendações (a). Commits na branch `spec-389`: R1-R5 (oferta), R8-R10
(entrega), R11-R15 (texto/UI), R16-R19 (seeds/`draft`) e este registro.

**Feito (R -> teste)**
- R1/R2 -> `tests/test_portrait_offer_causes.py::{test_every_omission_has_one_cause,test_gate_causes,test_gate_env_off,test_art_cause,test_offer_view_once_per_response,test_offer_view_levels}`. Módulo novo `services/portrait_offer.py` (decisão, tally por resposta com `ContextVar` em `services/portrait_offer_log.py`, `INSTANCE`, `offer_view`); `creature_art.portrait_for(..., reasons=)` devolve o motivo; `api.py` ficou 15 linhas menor.
- R3 -> `test_price_absent_not_cached`, `test_price_absent_cause_in_tally`. R4 -> `test_switch_recovers_on_within_ttl`, `test_switch_stale_after_60s_fail_closed`, `test_switch_age_and_structured_log`, `test_gate_reports_stale_cause` (`MAX_STALE_SECONDS = 60`, `age_s`, `stale`, `kill_switches.load_failed` por `log_event`).
- R5 -> `scripts/staging/portrait_offer_measure.py` (+ `test_measure_join_by_request_id`, `test_measure_fails_without_offer_view`). Eventos novos no catálogo: `creature_portrait.offer_view`, `kill_switches.load_failed` (`gen_event_catalog.py`).
- R8-R10 -> `tests/test_quest_delivery_npc.py` (18 testes: seed coerente, entrega à origem, outro NPC, negação, mecânica/pessoal/encerrada, cooldown, 1 por turno, nó `npc_actor` com MockLLM, `region_change` real mantido). `quest_log.delivery_ready/sync_npc_delivery`; `agents/npc.py` 1605 -> 1604 linhas.
- R11-R15 -> `tests/test_combat_text_smoke7.py` (50 sementes: frustrado no painel, Voto, Reação na prosa; unit: Provocação antes da ação mantém a linha; `conditions[].id/name/label`; nenhum consumidor do front compara nome de condição com id), `web/tests/spec389-round-frustrado.test.mjs`, `web/tests/spec389-hud-subclass.test.mjs`, `web/e2e/spec389-hud-subclass.spec.ts` (390 e 1440, verde).
- R16-R19 -> em `tests/test_spec387_seed.py`: `test_escort_fail_50_seeds`, `test_hostile_fallback_seed`, `test_smoke_bodies_parse_and_play` (9 corpos), `test_printed_promote_passes_reviewer_check`. `spec368_seed.smoke_body`.
- R21-R26 -> `test_spec346_board_no_llm`, `test_spec389_integrity_and_no_new_flag` (guarda de branch), `test_size_budget` verdes; nenhuma flag nova.

**Desvios / achados da implementação**
1. **R9, cooldown.** O storyteller não precisa de mudança: a fonte do motor (`source: "system"`) fica fora do cooldown por desenho (`world_validators.py:273-286`, SPEC-223; o cooldown de 3 turnos é para conclusões propostas pelo LLM). A entrega pela rota NPC aplica o limite por exigência da R9, em `quest_log._completion_allowed` (lê o mesmo `event_log` e `QUEST_COMPLETION_COOLDOWN`), e `delivery_ready` devolve no máximo 1 quest.
2. **R14 / fecho.** O ataque da Reação só carrega o nome em `atk["fora_de_turno"]` (o `label` não é gravado no dict do ataque). `_attack_line` casa esse nome com as Reações de `out["reactions"]`. A frase "Sua reação termina o serviço" só sai no fecho determinístico quando há golpe final por Reação, então o teste de 50 sementes confere "reage com Encaixe do Golpe" na linha do registro e deixa o fecho ao teste existente (`final_blow_sentence`).
3. **R12.** A linha humana nova é `, provocado por .+, muda de alvo\.$` (mais estreita que `muda de alvo\.$`). "Resolvido" = `pressagios_desviados` ou `special:taunt_resisted` na mesma rodada.
4. **R16 `4 falha`.** Precisou de 3 ajustes além da spec: classe `Devoto do Abismo` (com o Sangromante o goblin só "flanqueia" o herói e nenhuma semente o faz mirar o escoltado), escoltado como ator ANTES do presságio e posto na cena depois (como o Ketil do Voto), e `ferimento_espacos={critico:1}` + `last_stand_resolved=True` (sem isso o escoltado entra em Última Ação/Estado Terminal e o objetivo só falha na rodada seguinte; 9/20 sementes falhavam na 1ª). Resultado: 50/50 `falhou`, herói de pé, sem "perde os sentidos".
5. **R18.** `smoke_body` da `13 reacao` usa a manobra `guardar` em `jogadas` (como o teste da 387) e não `bas_dev_golpe`: o golpe do herói mataria o goblin (Vit 1) antes de ele agir e não haveria o que reagir. Ids confirmados pelo `TestClient`.
6. **R8.** `turn_count` da seed `14 entrega` passou a `max(4, atual)`; só a origem fica `in_scene`; `_place_hero` agora alinha `campaign_plan.location` (afeta também a `15`, sem teste vermelho).
7. **R13.** `name` da view virou o rótulo; nenhum teste antigo precisou mudar (conferido com grep + 7 arquivos de teste que leem a view). Front: `Condition.id?` novo.
8. **Etapa 0 (anotações).** Sem acesso ao script de amostragem/logs do coordenador: S7-1 fica para a medição da R5. Código lido confirma: `/game/state` é o mesmo endpoint para API e navegador; `KillSwitches` sem limite de idade era real e foi corrigido; `peek_ceiling` `None` ficava 60 s no cache (corrigido, R3). L4/L7/L8 confirmados no source (itens 5 e 6 da Etapa 0 e a nota 4 acima). Itens 1-3 da Etapa 0 (hora do `on`, nível de log do staging, linhas `private`) ficam com o coordenador.

**Condicionado à medição do staging (coordenador; NÃO feito)**
- **R6**: a correção final de S7-1. Hipóteses a decidir pela tabela de `offer-measure-*.json`: `switches_stale`/`switch_off` (já tratados por R4), `private_other_game` (hoje a linha `ready` com `store=private` de outro jogo vira `pending` e some a oferta; o código só passou a REPORTAR a causa, o efeito não mudou; mudar exige o teste de linha `private` de outro `origin_game_id` e a conferência de idempotência do registro) e amostragem (script exige `game_id`: já exige `--game-id`). Se a causa for outra, entra aqui com teste.
- **R7**: a explicação navegador x API (endpoint/`game_id` de cada lado) sai da mesma tabela.
- **Etapa 0.2**: confirmar `RPG_LOG_LEVEL` do staging <= `info` (o `offer_view` normal é `info`; causa inesperada é `warning`). Não mexi em `staging_flags.json` (guarda de integridade).
- **R20**: nota L11 para a §1 da SPEC-369 (o coordenador integra): "`draft.py` real reprovou 2 de 4 Cartas por orçamento no lint; avaliar o prompt/orçamento, sem mudar `lint`/`sim`/`promote`".
- §6 inteiro (smoke com LLM real), a revisão `Sol` e o e2e do restante do bloco.


**Correções da revisão Sol (CHANGES_REQUIRED)**: P1-1 (`switches_snapshot` com `--dsn-env RPG_STAGING_DB_URL --env-file .env.staging`, JSON inteiro, `audit` filtrado por `image_generation`, falha se o snapshot não vier), P1-2 (amostra com o `game_id` real e o path real; contagem mínima API/navegador e status 200 em `count_problems`; `offer_view` ganhou `game_ref`), P2-1 (tally só com inimigo vivo), P2-2 (precedência `fallback_enemy` > `has_own_art` > `private_other_game`/`pending`, teste com o `portrait_for` real), P2-3 (`INSTANCE = observability.boot.INSTANCE_REF`), P2-4 (`_creature_art_live` usa `art_cause`), P2-5 (asserção por variante em `test_smoke_bodies_parse_and_play`; a `14 entrega` roda o nó `npc_actor` direto porque o MockLLM roteia "Entrego…" para STORY), P2-6 (recompensa e técnica no teste de entrega), P2-7 (docstrings).
