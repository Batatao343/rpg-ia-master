# SPEC-313 — Quests ancoradas em lore (caça, entrega, escolta, rumor, mortos)

> **Status:** `in-progress` (implementada 25/10 no worktree; falta revisão independente, suíte completa e smoke real; escopo e decisões D-A/D-B do dono em 24/10; demais Dx no default recomendado, §9)
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Origem:** `docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md` proposta **N6** (§4.2, linha 239),
> §2.3 (linhas 176-177: "Quest de mundo: só motor" / "Quest proposta pela LLM: sem âncora,
> prazo, recompensa") e §3 (lore não aproveitada, linhas 188-205).
> **Depende de:** SPEC-305 (`done`: `services/world_quests.py`, catálogo, `heard_via`, prazo,
> lista branca, `quest_failed` engine-only), SPEC-304 (`done`: `npc_world.presence/location_of`,
> arquétipos de agenda), SPEC-301 (`done`: missões de fação, para não duplicar), SPEC-223
> (`done`: prova de conclusão), SPEC-285 (`done`: régua de letalidade).
> Integra **se estiver `done`**, sem bloquear: SPEC-312 (rumores com semente e boato falso; sem
> ela o tipo `investigar_rumor` fica desligado por guarda, como `resgate` ficou na 305), SPEC-298
> (feito de reputação na conclusão; sem ela só XP e ouro), SPEC-308 (regra de ouro de eventos do
> motor; os eventos novos daqui já nascem com `offscreen`/percepção explícita).
> **Desbloqueia:** N2/N3 (criatura e item com semente têm um consumidor: caça e entrega), N5
> (trilha de segredos pode reusar `investigar_rumor`), pilar D (opções de ação com gancho).
> **EXECUTOR_MODEL:** `Opus` (Sol: writer em `quests`, `npc_sim` e inventário; integra 304/312) ·
> **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (novo campo no
> schema do LLM, novo writer de inventário via `event_processor`, mexe em encontros)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A SPEC-305 deu ao jogo quests de mundo com prazo, mas **só de crise**: os 9 tipos de
`data/world/world_quests.json` nascem de guerra, fome, praga, Abismo, ocupação, rota, ascensão,
objeto e perigo de NPC. Todo o resto das side quests vem de uma proposta de texto livre do LLM
(`ProposedQuest`), sem tipo, sem âncora no mundo, sem prazo e com recompensa fixa de 20 de ouro.
O NPC diz "cace o lobo que anda matando minhas cabras" e o diário ganha uma quest que o motor não
entende: não sabe que lobo, onde, até quando, nem como provar que foi caçado. A conclusão depende
de o LLM propor `quest_completed` com prova investigativa genérica.

Ao mesmo tempo, a lore tem ganchos prontos que nenhum código lê: NPCs curados descritos como
"contratante de escoltas" (`lore_nova/npcs.txt:925`, `:1042`, `:2263`), os Sindicatos de Brekmar
que vivem de "rotas e contratos" (`lore_nova/factions.txt:241`), o chá dos Druidas feito com plantas
do Pântano e vendido em Nova Arcádia (`lore_nova/locations.txt:111-114`), a Guilda dos Corvos que
existe porque "mortos-vivos eram consequência real de descuido" (`lore_nova/timeline_completa.txt:470`;
`lore_nova/factions.txt:75-89`), 40 rumores com `confiabilidade` e `[FONTE]` (`lore_nova/rumors.txt:5-16`)
e 337 criaturas com perigo e hábito (`lore_nova/creatures.txt`).

Esta spec cria **cinco tipos de quest ancorados em lore**: `cacar_criatura`, `entregar_material`,
`escoltar`, `investigar_rumor` e `recolher_mortos`. Cada tipo é um template do motor que cita sua
fonte de lore (arquivo:linha). A LLM do NPC escolhe um `kind` e uma âncora de uma lista fechada
que o motor oferece no prompt e **só redige** título e descrição. **Prazo, recompensa, conclusão e
falha vêm do motor** por template. Dois tipos também nascem do próprio motor, do que o jogador
percebeu: `recolher_mortos` (crise que escalou) e `investigar_rumor` (rumor da SPEC-312, inclusive
falso: investigar revela que era boato).

Princípios: mecânica em Python e LLM só redige (AGENTS.md § Convenções); regra de ouro (só nasce
quest do que o personagem viu ou ouviu; VISAO.md "Regra de ouro"); o mundo não escala com o herói
(prazo e recompensa nunca leem nível/ficha/ouro); duro mas telegrafado (rótulo de prazo vago da
305 R21); não-onisciência (verdade do rumor, âncoras e valores internos nunca saem pela API nem
pelo prompt antes da hora).

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | `ProposedQuest` não tem tipo nem âncora: só `title/description/origin_*/location_id/reward_hint` em texto livre | `services/structured_outputs.py:82-100` |
| P2 | Quest proposta pelo LLM nasce com `uuid4`, `reward_gold: 0`, sem prazo, e o `reward_hint` do LLM vai cru para o diário | `services/quest_log.py:142-156` |
| P3 | A recompensa é fixa (20) para toda quest comum; só missão de fação varia por tier | `services/quest_log.py:31-33`, `:405-408` |
| P4 | O prompt do NPC pede "recuperar/entregar/investigar/resgatar" sem dar nenhuma âncora do mundo; o LLM inventa o alvo | `agents/npc.py:1094-1098` |
| P5 | O motor só gera quest de crise: as fontes de `candidates` são crise, ocupação, rota, objeto e perigo | `services/world_quests.py:35-41`, `:322-333`; `data/world/world_quests.json:21-160` |
| P6 | A 305 deixou fora "entregar item específico"; não há conclusão por inventário | SPEC-305 §2 "Fora de escopo" (`specs/SPEC-305-quests-de-mundo-com-prazo.md:251-253`) |
| P7 | Vitória em combate só conta como evidência genérica no **local** da quest; o `bestiary_id` do inimigo morto não é comparado com nada | `agents/combat.py:1590-1606`; `services/quest_log.py:457`; `agents/combat.py:819` (`bestiary_id` existe no inimigo) |
| P8 | Ganchos de escolta e entrega da lore (`Para o narrador: … contratante de escoltas`) não têm consumidor estruturado | `lore_nova/npcs.txt:925`, `:1042`, `:2263`; REVISAO §3 linha 192 |
| P9 | Rumores com `confiabilidade`/`FONTE` não são lidos; não existe boato falso jogável | `lore_nova/rumors.txt:5-16`, `:24-25`; REVISAO §3 linha 191 |
| P10 | O NPC itinerante da 304 anda sozinho; não existe "viajar junto" sem virar companheiro (SPEC-300) | `services/npc_world.py:355-357` (`location_of` = `presence`); `data/world/npc_agendas.json:13`, `:40`, `:55` |
| P11 | Missões de fação (301) já cobrem apoio/sabotagem/rito para membros; um gerador novo pode duplicá-las | `services/faction_missions.py:1-6`, `:43-69`; `data/faction_membership.json:36-39` |

## 2. Requisitos

### 2.1 Catálogo e âncoras

- **R1 — Cinco tipos novos no catálogo da 305.** `data/world/world_quests.json` ganha em `kinds`
  os tipos abaixo, no mesmo formato (título, descrição por canal, `fail_text`, `action_vocab`,
  `combat_counts`, `relief`) mais os campos novos `origin` (`"engine"` | `"npc"` | ambos),
  `anchor_type`, `deadline_rule`, `reward_rule` e **`lore_refs`** (lista não vazia de
  `"lore_nova/<arquivo>:<a>-<b>"`) e `lore_keyword` (termo que aparece no trecho citado):

  | Tipo | Origem | Âncora | Fonte de lore (exemplos) |
  |---|---|---|---|
  | `cacar_criatura` | NPC | `enemy_id` do `data/bestiary.json` com `regions` contendo a região do NPC e `categoria ∈ {lacaio, padrao, elite}` | `factions.txt:152-153` (Clãs, "os caçadores … que alimentam e defendem Skallgard"); `locations.txt:111` (Druidas neutralizam mortos-vivos); `creatures.txt:600` (as feras migram) |
  | `entregar_material` | NPC | linha de `delivery_routes` (§3.5): `item_id` de `artifacts.json` com `type="material"`, quantidade e destino curados | `factions.txt:241` (Helvira: "rotas e contratos"); `locations.txt:114` (chá dos Druidas vendido em Nova Arcádia) |
  | `escoltar` | NPC | o próprio NPC em cena (arquétipo 304 `mercador_itinerante`, `peregrino` ou `mensageiro`) + destino da rota do arquétipo | `npcs.txt:925` (Brago, "contratante de escoltas"); `npcs.txt:1042` (Thessa, "missões de defesa e escolta"); `npcs.txt:2263` (o Cartógrafo pede escolta) |
  | `investigar_rumor` | motor e NPC | `rumor_id` da SPEC-312 que o jogador ouviu (motor) ou que o NPC conhece (NPC) | `rumors.txt:1-2` ("fontes não verificadas, confiabilidade variável"); `rumors.txt:6-7`, `:24-25` (`confiabilidade`, `FONTE`) |
  | `recolher_mortos` | motor | crise `guerra`/`praga` que **escalou** (item `ruina.crise.escala` ou `praga.crise.escala` percebido) | `timeline_completa.txt:470` (Corvos nascem porque mortos largados viravam surtos e mortos-vivos); `factions.txt:78`; `locations.txt:81` |

- **R2 — Lint de lore.** Teste lê **só** as linhas citadas em cada `lore_refs` (sem abrir o
  arquivo inteiro: `itertools.islice`) e asserta: o arquivo existe, o intervalo cabe no arquivo e
  `lore_keyword` aparece no trecho (sem acento/caixa). Tipo novo sem `lore_refs` válido falha a
  suíte.
- **R3 — Âncora validada pelo motor, nunca pela LLM.** `services/lore_quests.validate_anchor`
  aceita a âncora só se ela estiver no **menu** oferecido ao NPC naquele turno (R11) e passar nas
  regras do tipo: criatura existe, é da região, categoria permitida (`chefe` e `nomeado` nunca);
  rota existe em `delivery_routes`, origem = região do NPC, destino ≠ local atual e alcançável
  (`world_distance.travel_periods` não `None`); escolta só do próprio NPC falante, vivo, livre,
  no local atual, com arquétipo itinerante; rumor está em `rumor_seeds.heard_rumors` (jogador) ou
  no conhecimento do NPC (SPEC-215/312). Âncora inválida → a proposta vira quest **comum** (o
  comportamento de hoje), com log `lore_quest.downgraded {kind, reason}`; nunca levanta.
- **R4 — `ponto_fraco` de fação fica fora.** Os campos "Ponto fraco" da lore são segredos
  (`factions.txt:51`: "Nenhum membro de nível médio sabe que Magda é a Víbora"; `:30`, `:228`) e
  exigem trilha de pista → revelação (N5). Sabotagem contra fação já é missão da 301
  (`data/faction_membership.json:38`). Ver §2 "Fora de escopo" e D7.

### 2.2 Proposta da LLM (só redige)

- **R5 — `ProposedQuest` ganha dois campos opcionais.** `kind: Literal["comum",
  "cacar_criatura", "entregar_material", "escoltar", "investigar_rumor"] = "comum"` e
  `anchor_id: str = ""`. Nenhum campo de prazo, valor ou dificuldade é adicionado (teste de
  schema: `model_fields` não tem `deadline*`, `reward_gold*`, `days*`). `recolher_mortos` não é
  propônível (só o motor cria).
- **R6 — Só o `npc_actor` ancora.** Proposta com `kind ≠ "comum"` vinda do storyteller é
  rebaixada a comum (`reason="not_npc"`): só o NPC em cena, com `origin_name`/`origin_entity_id`
  carimbados em Python (`agents/npc.py:1312-1323`), tem âncora verificável. O caminho comum
  continua igual nos dois agentes (regressão de `register_proposed_quests`).
- **R7 — O motor monta a quest.** Proposta ancorada válida vira `QuestSeed` e passa por
  `world_quests.offer_from_proposal(state, proposal, origin_key, day)`, que reusa
  `_build_quest` (id determinístico `sha256(game_id|kind|world_source_id)[:16]`, `heard_via`,
  `deadline_day`, `fail_text`). A SPEC-305 R7 continua valendo: só `services/world_quests.py`
  monta dict com `world_kind` (o teste AST dela não muda).
- **R8 — Texto da LLM com guarda; o resto é template.** `title` e `description` da LLM são
  usados se passarem em `lore_quests.safe_llm_text`: não vazios, ≤ 90 / ≤ 400 caracteres, sem
  número seguido de unidade de tempo ou dinheiro (`\d+\s*(dia|dias|noite|semana|moeda|ouro|
  coroa|peça)`), sem nome de fação desconhecida (`world_utils.unknown_faction_names`,
  `world_utils.py:920`), sem nome de criatura/item/local diferente da âncora resolvida. Reprovou
  → template do tipo (`render_quest_text`). O `reward_hint` da LLM é **sempre** descartado em
  quest ancorada; o motor grava o rótulo de recompensa (R15).
- **R9 — Não duplica a 301.** No mesmo turno em que `membership_action` do NPC gerou missão de
  fação (`faction_missions.offer_mission`), propostas ancoradas desse NPC são descartadas
  (`reason="faction_mission_same_turn"`). Quest ancorada nunca grava `faction_id`,
  `mission_kind` nem `mission_tier` (teste: `faction_membership.active_mission_id` ignora a
  quest; `on_mission_completed` não roda).
- **R10 — Dedupe.** Vale o dedupe de título da `register_proposed_quests` (≥ 0,75) e o da 305 R10
  (proposta no alvo de quest de mundo ativa). Ancorada com a mesma âncora de uma quest ativa
  (qualquer origem) → ignorada (`reason="anchor_active"`).

### 2.3 Munição no prompt (regra de ouro)

- **R11 — Menu de âncoras no prompt do NPC.** `lore_quests.anchor_menu(state, npc_key)` devolve
  um bloco `<GANCHOS_POSSIVEIS>` (≤ 12 linhas, ~150 tokens) inserido junto do `<MISSÃO>`
  (`agents/npc.py:1094`), com no máximo 3 itens por tipo, cada um com `kind`, `anchor_id`
  exato e um rótulo em palavras:
  - **criaturas**: até 3 do bestiário da região do NPC, permitidas por R3, ordenadas por
    abundância (`ecology.hunt_pressure` menor primeiro, `services/ecology.py:29`) e depois por id.
    Só nome e "anda rondando a região": nenhum número, perigo ou fraqueza;
  - **entregas**: as linhas de `delivery_routes` cuja origem é a região do NPC e cujo `patron_tags`
    casa o `role`/fação do NPC (§3.5);
  - **escolta**: o próprio NPC, se elegível (R3), com até 2 destinos da rota do seu arquétipo;
  - **rumores**: até 2 rumores que o **NPC** conhece (linhas `[OUVIU]`/`[BOATO]` da SPEC-215/312),
    com o texto público do rumor. **A verdade (`truth`) nunca entra no prompt.**
  O texto do bloco manda: "Se oferecer uma dessas tarefas, use o `kind` e o `anchor_id` EXATOS.
  Não diga prazo nem valor: o mundo decide." Sem nenhum item elegível, o bloco não é emitido
  (teste de tokens: ≤ 150 tokens pelo contador do `context_builder`).
- **R12 — Percepção da quest proposta.** Quest ancorada vinda do NPC grava
  `heard_via={channel:"npc", event_id:"npc:<npc_key>:<turn>", day}` e só nasce se o NPC estava
  `in_scene` no turno (o carimbo de origem já exige isso). Quest de origem motor usa os canais da
  305 (`_resolve_channel`: testemunho, cartaz, npc, rumor). O invariante `quest.world_unheard`
  (305 R6) passa a cobrir os cinco tipos.
- **R13 — Fontes nunca leem o herói.** Prazo, recompensa, menu e candidatas não leem nível,
  ficha, inventário (exceto a **conclusão** de `entregar_material`), ouro nem party. Teste: mesmo
  estado com `player.level` 1 e 20 → mesmo menu, mesmos prazos, mesmas recompensas.

### 2.4 Prazo e recompensa do motor

- **R14 — Prazo por regra do template.** `deadline_day = day + N`, com `N` por tipo
  (`[BALANCEAR]`):
  - `cacar_criatura`: `HUNT_DAYS` (6), a fera migra (`creatures.txt:600`);
  - `entregar_material`: `ceil(travel_periods(origem, destino) / PERIODS_PER_DAY) × 2 +
    DELIVERY_SLACK` (2);
  - `escoltar`: `ceil(travel_periods(local, destino) / PERIODS_PER_DAY) + ESCORT_SLACK` (2);
  - `investigar_rumor`: `RUMOR_DAYS` (8), ou o TTL restante do rumor na 312 se for menor;
  - `recolher_mortos`: `BODIES_DAYS` (4).
  Só oferece se viável (305 R8, `world_quests.is_feasible`). Prazo nunca encurta (305 R2).
  Rótulo público = `quest_log.deadline_label` (305 R21), sem número.
- **R15 — Recompensa por template, materializada uma vez.** O motor grava na criação
  `reward_gold_planned` (INTERNO) e `reward_hint` (rótulo: `"modesta"`/`"justa"`/`"generosa"`):
  - `cacar_criatura`: por `categoria` da âncora: lacaio 15, padrão 25, elite 40;
  - `entregar_material`: por faixa de distância (`travel_periods` origem→destino): ≤ 1 dia 15,
    ≤ 3 dias 25, > 3 dias 40;
  - `escoltar`: idem faixa: 20 / 30 / 45;
  - `investigar_rumor`: 10 se a origem é um NPC, 0 se a origem é o motor (só XP);
  - `recolher_mortos`: 15.
  `complete_quest_with_reward` (`quest_log.py:394-420`) usa `reward_gold_planned` quando a quest
  tem `world_kind` em `LORE_KINDS`; XP segue `XP_PER_QUEST`. Feito de reputação pela 298 só se
  `origin_faction_id` ∈ `data/factions.json` (305 R14); fação só do grafo (ex.: `guilda_corvos`,
  `tres_sindicatos_comercio`) não gera feito até a N8.

### 2.5 Anti-farm

- **R16 — Uma por fonte.** `world_source_id` por tipo:
  `hunt:<enemy_id>:<region_id>:<origin_key>`, `deliv:<route_id>:<origin_key>`,
  `escort:<npc_key>:<destino>:<day>`, `rumor:<rumor_id>`, `mortos:<crisis_id>`. Já existe quest
  com esse `world_source_id` (qualquer status) → não oferece de novo (305 R3, D8 da 305).
- **R17 — Cooldowns.** Por NPC de origem: 1 quest ancorada a cada `ORIGIN_COOLDOWN_DAYS` (7),
  contado do `created_day` da última dele (qualquer status). Por âncora: a mesma criatura na
  mesma região, a mesma rota ou o mesmo rumor não voltam antes de `ANCHOR_COOLDOWN_DAYS` (10)
  depois de resolvida a quest anterior. Tudo contado em dias do `world_clock`, nunca em turnos.
- **R18 — Teto.** No máximo `MAX_LORE_QUESTS_ACTIVE` (2) quests destes cinco tipos ativas, fora
  do teto de 3 da 305 e dentro do `MAX_ACTIVE_QUESTS = 8` geral (`quest_log.py:29`). Sem vaga →
  `lore_quest.cap_reached`, nenhuma quest (decisão D1).
- **R19 — Prova mecânica, não textual.** Nenhum tipo novo conclui por texto do LLM sozinho:
  - `cacar_criatura`: só por vitória de combate (R20);
  - `entregar_material`: só com o item no inventário no destino (R21);
  - `escoltar`: só chegando ao destino com a escolta ativa (R22);
  - `investigar_rumor` e `recolher_mortos`: prova da SPEC-223 (`location_reached` no alvo + 2
    evidências distintas do `action_vocab` do tipo, posteriores à criação).
  Entrega exige `destino ≠ origem` e `travel_periods ≥ PERIODS_PER_DAY` (não dá para "entregar"
  na própria praça).

### 2.6 Conclusão, falha e efeitos por tipo

- **R20 — Caça.** Na vitória (`agents/combat.py:1590-1606`), novo
  `quest_log.sync_hunt_progress(quests, dead_bestiary_ids, region_id, turn)` marca evidência
  `hunt_kill` na quest `cacar_criatura` ativa cuja âncora está entre os `bestiary_id` dos mortos
  e cuja região é a do local atual (qualquer local da região). `world_quests.engine_completions`
  enfileira `quest_completed` (`source="engine"`) para quest com `hunt_kill`. Inimigo que fugiu
  não conta. Combate simulado (`is_simulation`) não conta.
- **R21 — Entrega.** `engine_completions` conclui `entregar_material` quando, no mesmo turno: o
  jogador está no `location_id` destino, o inventário tem `qty` do `item_id`
  (`inventory.py`), e a ação do turno casou o `action_vocab` de entrega (`entreg`, `deix`,
  `repass`, `descarreg`, `trag`). O `event_processor`, ao aplicar esse `quest_completed`, remove
  `qty` unidades com `inventory.remove_item` (`inventory.py:93`) **no mesmo apply** que paga o
  ouro (`event_processor.py:447`, `:656`), uma única vez (idempotente por `reward_delivered`).
  Sem o item no momento do apply (vendeu entre a proposta e o apply) → conclusão rejeitada, quest
  segue ativa. Falha no prazo: o item fica com o jogador, sem efeito extra.
- **R22 — Escolta (contrato com a SPEC-304).** Na criação, `npc_sim.npcs[<ref>].escort =
  {quest_id, to, since_day}`. Enquanto a escolta está ativa:
  - `npc_world.presence` devolve o local do jogador (o NPC viaja junto); o passo diário de
    posição (304 R5) e a fuga (R6) pulam esse NPC; `maybe_open` (perigo off-screen) não abre
    perigo para ele;
  - ele **não** entra em combate nem recebe dano (v1; decisão D5) e não vira companheiro (SPEC-300
    intacta: nada em `party`);
  - se o jogador viaja para um local que **não** reduz `travel_periods` até o destino, a escolta
    **pausa**: o NPC fica no local de onde o jogador saiu (`escort.paused_at`), e volta a seguir
    quando o jogador retorna a esse local. A quest não falha por isso (305: nenhuma falha antes do
    prazo);
  - chegar ao destino com a escolta ativa (não pausada) → `quest_completed` engine; o NPC fica no
    destino (`pos.location_id = to`, `since_day = day`) e a escolta é limpa;
  - prazo vencido → `quest_failed` (`reason="prazo"`); a escolta é limpa e o NPC volta à simulação
    da 304 a partir de onde está (inclusive podendo abrir perigo depois, pelas regras dela).
  O narrador não teleporta (304 R8): teste de que o NPC escoltado aparece `in_scene` em cada
  local da viagem e nunca em dois lugares.
- **R23 — Rumor (contrato com a SPEC-312; boato falso pode gerar quest).**
  - Origem motor: `world_quests.candidates` inclui `investigar_rumor` para cada rumor de
    `rumor_seeds.heard_rumors(state)` com `quest_hook=True` e `location_id` válido; canal = o
    `heard_via` do rumor. Origem NPC: âncora de R11.
  - Título/descrição usam só o texto **público** do rumor ("Dizem que…"). Nada no título,
    descrição, rótulo, API ou prompt indica `truth` antes da conclusão (oráculo: mesmo payload de
    `/game/state` para rumor verdadeiro e falso enquanto ativa, exceto ids aleatórios).
  - Conclusão (prova 223 no `location_id` do rumor) → `engine_completions` lê
    `rumor_seeds.rumor_truth(state, rumor_id)` **só aqui** e grava `outcome = "confirmado" |
    "boato"` e chama `rumor_seeds.mark_investigated(state, rumor_id, outcome)` (a 312 decide o
    que vira fato; boato **nunca** vira fato, regra da 312). A quest **conclui** nos dois casos,
    com a mesma recompensa (decisão D3).
  - O storyteller recebe no turno seguinte uma linha `<DESFECHO_DE_QUEST>` com o resultado em
    palavras ("o que diziam se confirma" / "era só boato: ninguém viu nada disso"), para narrar.
  - Sem SPEC-312 `done` (`services.rumor_seeds` ausente ou sem `heard_rumors`), o tipo fica
    desligado: fora do menu, fora de `candidates`; testes com módulo injetado.
- **R24 — Mortos.** `candidates` inclui `recolher_mortos` para crise `guerra` ou `praga` com
  escalada registrada (`severity` subiu ou `resolution="escalou"`), uma vez por crise, alvo =
  `location_id` da crise, só se percebida pelo item `ruina.crise.escala` ou `praga.crise.escala`
  (`data/world/signals.json:20`, `:29`) pelos canais da 305. Vocabulário: `recolh`, `queim`,
  `crem`, `enterr`, `carreg`, `cav`, `cobr`. Alívio: causa `world_quest_relief` com `praga −10`
  na região. Falha: `fail_causes` `praga +6` uma vez na região (a lore: corpos largados viram
  surto). Valores `[BALANCEAR]`. Teste: a crise que já gerou `conter_praga` pode gerar
  `recolher_mortos` (fontes diferentes), mas nunca duas `recolher_mortos`.
- **R25 — Falha sem revelar desfecho.** `fail_text` de todos os tipos é neutro (305 R18):
  nenhum contém "morreu", "morto", "boato", "verdade", "fugiu" ou nome de fação desconhecida
  (teste varre templates × canais). Só `recolher_mortos` tem consequência extra (R24); os outros
  quatro falham sem efeito no mundo (decisão D6).

### 2.7 Letalidade (SPEC-285)

- **R26 — Caça puxa a fera certa, sem encontro novo.** Com `cacar_criatura` ativa e o jogador na
  região da âncora, quando um encontro **já disparou** por `check_encounter`
  (`world_utils.py:1069`) ou quando `resolve_track` sorteia rastro (`world_utils.py:1622-1642`),
  o sorteio de `pick_encounter_enemy` (`world_utils.py:935`) recebe um `theme` que pontua só a
  âncora (o mesmo mecanismo da SPEC-289): ela sai se couber no porte do perigo; senão, o sorteio
  normal segue. Nenhum gatilho de encontro novo, nenhum cooldown alterado, nenhum spawn extra,
  nunca `chefe`/`nomeado`. Medição SPEC-285 M1/M2/M5 (seeds 21-32 × 200 turnos, perfil
  `combate`) sem regressão contra a última medição da 305, com `RPG_LORE_QUESTS=on`.
- **R27 — Escolta e entrega não mudam encontros.** Teste: mesma seed, mesma viagem, com e sem
  escolta/entrega ativas → mesma sequência de `check_encounter`.

### 2.8 Superfícies, estado, rollout e prova

- **R28 — API com lista branca.** `public_quest_view` (305 R20) continua sendo a única
  projeção. Campos novos internos que **nunca** saem: `lore_anchor`, `reward_gold_planned`,
  `lore_origin_key`, `lore_ref`, `rumor_truth`, `escort`. Sai, só depois de concluída, `outcome_label`
  ("confirmado" / "era só boato"). `kind` público continua `"mundo"` para os cinco tipos. Teste
  varre `/game/state` e `/game/action`.
- **R29 — Prompt do narrador.** `_quests_ativas_block` (`agents/storyteller.py:266`) mostra os
  tipos novos com `· tipo: mundo · prazo: <rótulo>` (sem âncora técnica: o nome da criatura,
  material e destino em palavras) e `<GANCHO_NOVO>` (`agents/storyteller.py:298-313`) cobre a
  oferta de origem motor. Nenhuma chamada LLM nova (teste conta invokes no MockLLM).
- **R30 — Schema aditivo.** Campos novos opcionais em `Quest` e `NpcSimEntry` (§3.3). Save antigo
  carrega sem migração; quest sem os campos segue as regras atuais. Sem bump de `SCHEMA_VERSION`.
- **R31 — Determinismo.** Menu, candidatas, ids e prazos são função pura do estado (sem `random`
  global nos módulos novos; teste AST como 305 R25). Repetir oferta/sync com o mesmo estado não
  cria quest nem evento.
- **R32 — Rollout `RPG_LORE_QUESTS=off|shadow|on`.** Só vale com `world_quests.mode() == "on"`
  (senão `off`). `off`: menu não é emitido e `kind ≠ comum` vira comum. `shadow`: calcula menu,
  validação e ofertas, loga `lore_quest.shadow_offer` e **não** emite o menu nem grava quest.
  Default: decisão D9.
- **R33 — Telemetria e playtest.** Log `lore_quest.offered|downgraded|completed|failed|
  cap_reached` com `{kind, channel, reason}` (sem ids). Playtest grava por campanha ofertas,
  rebaixamentos (por motivo), conclusões e falhas por tipo; o `report` ganha linhas na seção
  "Mundo". Invariantes novos (todos `error`): `quest.lore_anchor_invalid` (âncora fora do
  catálogo/menu), `quest.lore_cooldown_violated`, `quest.rumor_truth_leaked` (`outcome`/`truth`
  em quest ativa na API ou no prompt), `quest.escort_split` (NPC escoltado não pausado em local
  ≠ do jogador), `quest.delivery_without_item` (entrega concluída sem remoção de item).
- **R34 — MockLLM exercita o caminho.** O mock do `npc_actor` (`mock_llm.py:486-492`), quando o
  prompt tem `<GANCHOS_POSSIVEIS>`, propõe de forma determinística o primeiro item do menu (por
  `seed` do turno, 1 em cada 4 conversas), para o playtest offline cobrir oferta → conclusão.
  Sem o bloco, comportamento atual.

### Fora de escopo

- `ponto_fraco` de fação e qualquer quest que toque segredo (`visibility: hidden/secret`): N5
  (trilha de segredos) e N8 (fações da lore completas).
- Criatura ou item **novos** (semente N2/N3): a âncora é sempre do catálogo existente
  (`bestiary.json`, `artifacts.json`).
- Escoltado lutando, sendo ferido ou morto em combate; escolta de grupo; emboscada roteirizada
  na estrada.
- Carga entregue pelo próprio NPC (item de quest criado no inventário). Na v1 o jogador arranja
  o material (compra, coleta, saque).
- Quests encadeadas (rumor confirmado → caça), segunda chance após falha, recompensa em item.
- Prazo em missão de fação (301) e em quest comum (sem `kind`).
- Mudar o gerador de rumores, a taxa de rumor ou a semântica de `truth` (são da SPEC-312).
- Quadro de recompensas/cartaz de caça gerado pelo motor (sem fonte na lore: grep por
  "cartaz"/"recompensa" em `lore_nova/` não acha nada); pode vir numa spec própria.
- Novos nós de mapa para destinos de entrega (N4).

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/lore_quests.py` | Menu de âncoras (`anchor_menu`), validação (`validate_anchor`), guarda de texto (`safe_llm_text`), conversão proposta → `QuestSeed` (`seed_from_proposal`), prazo e recompensa por regra (`deadline_for`, `reward_for`), cooldowns. **Não monta dict de quest** (305 R7). |
| `data/world/lore_quests.json` | Constantes `[BALANCEAR]`, `delivery_routes` curadas, `allowed_hunt_categories`, vocabulários de entrega/escolta, rótulos de recompensa |
| `tests/test_spec313_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `services/structured_outputs.py` (`:82-100`): `ProposedQuest.kind`, `ProposedQuest.anchor_id`.
- `state.py`: campos opcionais em `Quest` e `NpcSimEntry` (§3.3); `WorldQuestKind` + 5 tipos.
- `data/world/world_quests.json`: 5 tipos novos com `lore_refs`/`lore_keyword` (§3.5).
- `services/world_quests.py`:
  - `QuestSeed` ganha `enemy_id`, `route_id`, `rumor_id`, `escort_npc_key`, `qty`,
    `reward_gold`, `reward_label`, `llm_title`, `llm_description`, `origin_key`;
  - `_build_quest` grava os campos de §3.3 e usa `llm_title/llm_description` quando não vazios;
  - `candidates` + `_rumor_seeds(state)` (guardado por `_rumor_api()`, como `_peril_api`) e
    `_dead_seeds(sim, day)`;
  - `offer_from_proposal(state, proposal, origin_key, day) -> tuple[list[dict], dict | None]`;
  - `engine_completions` + ramos `cacar_criatura` (`hunt_kill`), `entregar_material`,
    `escoltar`, `investigar_rumor` (prova 223 + `outcome`);
  - `_source_state` + ramos dos tipos novos (rumor some da 312 → `ok_end`; NPC escoltado morre
    por outra via → `ok_end` sem falha, R25);
  - `sync_deadlines` limpa a escolta na falha.
- `services/quest_log.py`: `sync_hunt_progress`; `PROOF_EVIDENCE_KINDS` + `hunt_kill`;
  `complete_quest_with_reward` lê `reward_gold_planned` (R15); `register_proposed_quests` aceita
  `lore_hook` (callable injetado pelo `npc_actor`) que desvia propostas ancoradas para
  `offer_from_proposal`; `public_quest_view` + `outcome_label` e lista negra de R28.
- `agents/npc.py`: `<GANCHOS_POSSIVEIS>` junto do `<MISSÃO>` (`:1094-1098`); no bloco de
  `:1312-1323`, propostas com `kind ≠ comum` vão para `offer_from_proposal`; R9 (descarta se
  houve missão de fação no turno).
- `agents/storyteller.py`: rebaixa `kind ≠ comum` (R6) antes de `register_proposed_quests`
  (`:1937-1942`); `_quests_ativas_block` (R29); `<DESFECHO_DE_QUEST>` (R23).
- `agents/combat.py` (`:1590-1606`): coleta `bestiary_id` dos mortos e chama
  `sync_hunt_progress` (R20).
- `world_utils.py`: `check_encounter`/`resolve_track` aceitam `hunt_anchor: str = ""` e montam o
  `theme` de R26; o chamador (storyteller/viagem) passa a âncora da quest ativa da região.
- `services/npc_world.py`: `presence` respeita `escort` (R22); o passo diário, a fuga e
  `maybe_open` pulam escoltado; helpers públicos `escort_start(state, ref, quest_id, to, day)`,
  `escort_stop(state, ref, day)`, `escort_destinations(state, ref) -> list[str]` (rota do
  arquétipo, sem bloqueadas).
- `services/event_processor.py`: no apply de `quest_completed` de `entregar_material`,
  `inventory.remove_item` (R21); de `escoltar`, `npc_world.escort_stop`.
- `data/world/pressures.json`: causas de `recolher_mortos` (alívio `praga −10`; `fail_causes`
  `praga +6`, `once`).
- `mock_llm.py`: R34.
- `playtest/invariants.py`, `playtest/telemetry.py`, `playtest/report.py`, cenário
  `lore_quests` em `playtest/scenarios` (R33).
- `.env.example`: `RPG_LORE_QUESTS`.

### 3.3 Schemas (aditivo)

```python
# services/structured_outputs.py
class ProposedQuest(BaseModel):
    ...  # campos atuais (:89-100)
    kind: Literal[
        "comum", "cacar_criatura", "entregar_material", "escoltar", "investigar_rumor"
    ] = Field(default="comum", description="Tipo da tarefa; só use um kind do <GANCHOS_POSSIVEIS>.")
    anchor_id: str = Field(
        default="", description="anchor_id EXATO do <GANCHOS_POSSIVEIS>, ou vazio."
    )


# state.py
LoreQuestKind = Literal[
    "cacar_criatura", "entregar_material", "escoltar", "investigar_rumor", "recolher_mortos"
]


class LoreAnchor(TypedDict, total=False):  # INTERNO
    type: Literal["enemy", "route", "npc", "rumor", "crisis"]
    id: str  # enemy_id | route_id | npc_key | rumor_id | crisis_id
    item_id: str  # entrega
    qty: int  # entrega
    to: str  # entrega/escolta: location_id destino


class Quest(TypedDict, total=False):
    ...  # campos atuais + os da SPEC-305
    lore_anchor: LoreAnchor  # INTERNO
    lore_origin_key: str  # INTERNO: npc_key de origem ou "engine"
    lore_ref: str  # INTERNO: primeiro lore_refs do tipo (auditoria)
    reward_gold_planned: int  # INTERNO
    outcome: str  # "" | "confirmado" | "boato" (só investigar_rumor, após concluir)


class EscortState(TypedDict, total=False):
    quest_id: str
    to: str
    since_day: int
    paused_at: str  # "" = seguindo o jogador


class NpcSimEntry(TypedDict, total=False):
    ...  # campos atuais (SPEC-304)
    escort: EscortState
```

### 3.4 Assinaturas públicas

```python
# services/lore_quests.py
MODES = ("off", "shadow", "on")
LORE_KINDS = frozenset({"cacar_criatura", "entregar_material", "escoltar",
                        "investigar_rumor", "recolher_mortos"})
NPC_PROPOSABLE = LORE_KINDS - {"recolher_mortos"}
MAX_LORE_QUESTS_ACTIVE = 2
def mode() -> str
def anchor_menu(state: dict, npc_key: str) -> tuple[str, list[dict]]   # (bloco, itens oferecidos)
def validate_anchor(state: dict, kind: str, anchor_id: str, npc_key: str,
                    menu: list[dict], location_id: str = "") -> tuple[bool, str]  # (ok, motivo)
def safe_llm_text(state: dict, text: str, anchor_names: set[str], max_len: int) -> str  # "" = use template
def deadline_for(state: dict, kind: str, anchor: dict, day: int) -> int
def reward_for(kind: str, anchor: dict, origin_key: str) -> tuple[int, str]  # (ouro, rótulo)
def on_cooldown(state: dict, kind: str, anchor: dict, origin_key: str, day: int) -> str  # "" = livre
def seed_from_proposal(state: dict, proposal: dict, npc_key: str, menu: list[dict],
                       day: int) -> "QuestSeed | None"

# services/world_quests.py (extensões)
def offer_from_proposal(state: dict, proposal: dict, npc_key: str, menu: list[dict],
                        day: int) -> tuple[list[dict], dict | None]

# services/quest_log.py
def sync_hunt_progress(quests: list[dict], dead_bestiary_ids: list[str], region_id: str,
                       *, turn: int = 0) -> list[dict]

# services/npc_world.py (extensões, contrato com a SPEC-304)
def escort_start(state: dict, ref: str, quest_id: str, to: str, day: int) -> dict  # npc_sim novo
def escort_stop(state: dict, ref: str, day: int) -> dict
def escort_destinations(state: dict, ref: str) -> list[str]

# services/rumor_seeds.py — CONTRATO esperado da SPEC-312 (não criado aqui)
def heard_rumors(state: dict) -> list[dict]
#   cada item: {rumor_id, text (público), region_id, location_id, quest_hook: bool,
#               heard_via: {channel, event_id, day}, ttl_day: int | None}
def rumor_truth(state: dict, rumor_id: str) -> bool | None     # só o motor, só na conclusão
def mark_investigated(state: dict, rumor_id: str, outcome: str) -> tuple[dict, list[dict]]
```

Se a SPEC-312 pousar com outros nomes, a Etapa 0 ajusta este contrato no mesmo commit (o
adaptador fica em `world_quests._rumor_api()`).

Fluxo de proposta (turno do `npc_actor`): `anchor_menu` → prompt → resposta → para cada
`ProposedQuest` com `kind ≠ comum`: `mode()` → R9 → `seed_from_proposal` (R3, R13, R14, R15, R16,
R17) → `offer_from_proposal` (cap R18, viabilidade 305 R8, `_build_quest`) ou rebaixa a comum.
Fluxo motor: o mesmo da 305 (`offer_from_perceived`/`offer_from_heard`), com `candidates`
estendido. Conclusão: `engine_completions` (caça, entrega, escolta, rumor) ou prova 223 via
proposta (mortos), sempre aplicada pelo `event_processor`.

### 3.5 Formato de dados (IDs reais)

`data/world/world_quests.json` (trecho dos tipos novos; valores `[BALANCEAR]`):

```json
"cacar_criatura": {
  "origin": ["npc"],
  "anchor_type": "enemy",
  "deadline_rule": "day+HUNT_DAYS",
  "reward_rule": "by_categoria",
  "lore_refs": ["lore_nova/factions.txt:152-153", "lore_nova/creatures.txt:600-600"],
  "lore_keyword": "caçadores",
  "action_vocab": ["caç", "rastre", "persig", "embosc", "arm", "isc"],
  "combat_counts": false,
  "relief": {},
  "title": "Caçar {criatura} perto de {local}",
  "description": {"npc": "{origem} quer {criatura} longe de {local}. A fera não fica muito tempo no mesmo lugar."},
  "fail_text": "A trilha de {criatura} esfriou."
},
"investigar_rumor": {
  "origin": ["engine", "npc"],
  "anchor_type": "rumor",
  "deadline_rule": "min(day+RUMOR_DAYS, rumor.ttl_day)",
  "reward_rule": "npc_only",
  "lore_refs": ["lore_nova/rumors.txt:1-2", "lore_nova/rumors.txt:24-25"],
  "lore_keyword": "confiabilidade",
  "action_vocab": ["investig", "pergunt", "procur", "examin", "vasculh", "confer", "escut"],
  "title": "Ver com os próprios olhos: {rumor_curto}",
  "description": {"rumor": "Dizem que {rumor}. Alguém precisa ir até {local} e ver.",
                  "npc": "{origem} jura que {rumor}. Vale ir até {local} conferir."},
  "fail_text": "Ninguém foi conferir a história de {local} a tempo."
},
"recolher_mortos": {
  "origin": ["engine"],
  "anchor_type": "crisis",
  "deadline_rule": "day+BODIES_DAYS",
  "reward_rule": "flat",
  "lore_refs": ["lore_nova/timeline_completa.txt:470-470", "lore_nova/factions.txt:78-78"],
  "lore_keyword": "mortos-vivos",
  "action_vocab": ["recolh", "queim", "crem", "enterr", "carreg", "cav", "cobr"],
  "relief": {"pressure": "praga", "delta": -10},
  "title": "Os mortos de {local}",
  "description": {"testemunho": "Há corpos sem recolher em {local}. Quem conhece a Guilda dos Corvos sabe o que acontece com mortos largados.",
                  "rumor": "Dizem que os mortos de {local} ficaram onde caíram."},
  "fail_text": "Os mortos de {local} ficaram sem ninguém."
}
```

`data/world/lore_quests.json` (trecho; `delivery_routes` exige revisão de conteúdo do dono, D8):

```json
{
  "constants": {"HUNT_DAYS": 6, "RUMOR_DAYS": 8, "BODIES_DAYS": 4, "DELIVERY_SLACK": 2,
                "ESCORT_SLACK": 2, "ORIGIN_COOLDOWN_DAYS": 7, "ANCHOR_COOLDOWN_DAYS": 10,
                "MAX_LORE_QUESTS_ACTIVE": 2, "MENU_MAX_PER_KIND": 3},
  "allowed_hunt_categories": ["lacaio", "padrao", "elite"],
  "rewards": {"cacar_criatura": {"lacaio": 15, "padrao": 25, "elite": 40},
              "entregar_material": [15, 25, 40], "escoltar": [20, 30, 45],
              "investigar_rumor": {"npc": 10, "engine": 0}, "recolher_mortos": 15},
  "reward_labels": {"15": "modesta", "25": "justa", "40": "generosa"},
  "escort_archetypes": ["mercador_itinerante", "peregrino", "mensageiro"],
  "delivery_routes": [
    {"id": "cha_druidas_anel_lama", "origin_region": "pantano_melancolia",
     "to": "na_anel_lama", "item_id": "musgo_cinzento", "qty": 2,
     "patron_tags": ["druida", "erv", "curandeir", "druidas_ciclo_cinzento"],
     "lore_ref": "lore_nova/locations.txt:114-114", "lore_keyword": "Nova Arcádia"},
    {"id": "minerio_skallgard_brekmar", "origin_region": "skallgard",
     "to": "brekmar", "item_id": "minerio_ferro", "qty": 3,
     "patron_tags": ["mercador", "ferr", "minei", "sindicat"],
     "lore_ref": "lore_nova/factions.txt:241-241", "lore_keyword": "rotas", "review": "dono"}
  ]
}
```

Exemplos concretos:

- **Caça.** O jogador conversa com um caçador em `skallgard`; o menu oferece
  `enemy_lobo_invernal` ("Lobo das Geleiras", `lacaio`, `data/bestiary.json:1012-1014`). O LLM
  devolve `kind="cacar_criatura"`, `anchor_id="enemy_lobo_invernal"`, título "Lobos no caminho
  das armadilhas". O motor cria a quest com `deadline_day = day + 6` (rótulo "há algum tempo"),
  `reward_gold_planned = 15` (rótulo "modesta"). Vencer um combate na região em que morre um
  inimigo com `bestiary_id = "enemy_lobo_invernal"` conclui.
- **Entrega.** Um druida no `pantano_melancolia` oferece a rota `cha_druidas_anel_lama`:
  levar 2 `musgo_cinzento` (`data/artifacts.json:358-363`) a `na_anel_lama`. Prazo = 2 × viagem
  + 2. Ao chegar a `na_anel_lama` com 2 unidades e dizer "entrego o musgo ao boticário", o motor
  conclui, remove 2 unidades e paga.
- **Rumor falso.** A 312 entrega ao jogador o rumor de `lore_nova/rumors.txt:24-27` ("A Legião
  Está Fabricando Soldados a Partir de Mortos", `confiabilidade: baixa`) com `quest_hook=True`
  e `truth=False`. A quest diz "Dizem que…"; ao investigar em `na_anel_ferro` com prova, conclui
  com `outcome="boato"`, e o narrador recebe "era só boato". Nada vira fato.

## 4. Plano passo a passo

Pousa em um marco, depois da 305 (`done`). Sem a 312 `done`, a Etapa 5 roda com módulo injetado
e o tipo fica desligado em produção por guarda.

### Etapa 0 — Ownership e sondas

1. Consultar `project_index` (`state_ownership`) para os writers de `quests`, `npc_sim` e
   `player.inventory`; registrar `services/world_quests.py` como único criador dos tipos novos e o
   `event_processor` como único que remove item por entrega.
2. Confirmar no código: `npc_world.presence`, passo diário e `maybe_open` (304); `bestiary_id`
   nos inimigos mortos (`agents/combat.py:819`); estado da SPEC-312 (`services/rumor_seeds.py`).
   Divergiu → ajustar §3.4 no mesmo commit.

### Etapa 1 — Catálogo, schema e lint de lore

1. **Testes** (`tests/test_spec313_catalog.py`):
   - `test_five_lore_kinds_in_catalog_with_required_fields`;
   - `test_lore_refs_exist_and_keyword_in_range` (lê só o intervalo citado; R2);
   - `test_delivery_routes_reference_real_ids` (`item_id` material em `artifacts.json`, `to` em
     `world_map.json`, `origin_region` real, `lore_ref` válido);
   - `test_proposed_quest_has_kind_and_anchor_only` (sem campo de prazo/valor; R5);
   - `test_legacy_quest_and_npc_sim_roundtrip` (save/load sem os campos novos; R30);
   - `test_no_global_random_in_lore_quests` (AST; R31).
2. **Implementação:** JSONs, `state.py`, `structured_outputs.py`, esqueleto de `lore_quests.py`.

### Etapa 2 — Menu, validação e guarda de texto

1. **Testes** (`tests/test_spec313_proposals.py`):
   - `test_menu_lists_regional_creatures_without_numbers` (sem "perigo", números, fraquezas);
   - `test_menu_never_contains_rumor_truth` (rumor falso e verdadeiro produzem o mesmo bloco);
   - `test_menu_absent_when_nothing_eligible` e `test_menu_token_budget`;
   - `test_anchor_outside_menu_downgrades_to_common`;
   - `test_boss_and_named_never_anchor` (`chefe`, `nomeado`);
   - `test_escort_only_self_itinerant_alive_here`;
   - `test_storyteller_kind_downgraded` (R6);
   - `test_llm_text_with_days_or_gold_falls_back_to_template`;
   - `test_llm_text_with_unknown_faction_falls_back_to_template`;
   - `test_llm_reward_hint_discarded`;
   - `test_faction_mission_same_turn_drops_anchored` e `test_anchored_never_has_faction_fields`
     (R9);
   - `test_independent_of_player_stats` (R13).
2. **Implementação:** `anchor_menu`, `validate_anchor`, `safe_llm_text`, `seed_from_proposal`,
   integração no `npc_actor` e rebaixamento no storyteller.

### Etapa 3 — Oferta, prazo, recompensa e anti-farm

1. **Testes** (`tests/test_spec313_offer.py`):
   - `test_offer_from_proposal_builds_world_quest_with_heard_via_npc`;
   - `test_deadline_rules_per_kind` e `test_deadline_never_shortens`;
   - `test_reward_by_categoria_and_distance_band` + `test_reward_label_no_number`;
   - `test_one_per_source_any_status` (R16);
   - `test_origin_cooldown_and_anchor_cooldown_in_days` (R17);
   - `test_lore_cap_two_and_global_cap` (R18);
   - `test_infeasible_not_offered`;
   - `test_deterministic_ids_and_idempotent_offer`;
   - `test_only_world_quests_builds_world_kind` (o teste AST da 305 continua verde).
2. **Implementação:** `deadline_for`, `reward_for`, `on_cooldown`, `offer_from_proposal`,
   `_build_quest` estendido, `complete_quest_with_reward` com `reward_gold_planned`.

### Etapa 4 — Caça e encontros

1. **Testes** (`tests/test_spec313_hunt.py`):
   - `test_hunt_completes_on_anchor_kill_in_region`;
   - `test_hunt_ignores_fled_and_simulation_and_other_species`;
   - `test_hunt_counts_once_per_combat`;
   - `test_encounter_theme_prefers_anchor_when_encounter_fires`;
   - `test_no_new_encounter_trigger_with_hunt_active` (mesma seed: `check_encounter` dispara nos
     mesmos turnos com e sem quest; R26);
   - `test_anchor_above_porte_falls_back_to_normal_pick`.
2. **Implementação:** `sync_hunt_progress`, `combat.py`, `hunt_anchor` em
   `check_encounter`/`resolve_track`, ramo em `engine_completions`.

### Etapa 5 — Rumor (com e sem SPEC-312)

1. **Testes** (`tests/test_spec313_rumor.py`; módulo `rumor_seeds` injetado):
   - `test_heard_rumor_with_hook_creates_quest_engine_origin`;
   - `test_unheard_rumor_creates_nothing` (regra de ouro);
   - `test_false_rumor_quest_payload_equals_true_rumor_payload_while_active` (R23 oráculo);
   - `test_false_rumor_completes_with_boato_and_no_fact` (`mark_investigated` chamado com
     `"boato"`; nenhum evento de fato no `event_log`);
   - `test_true_rumor_completes_with_confirmado`;
   - `test_desfecho_line_next_turn_only_after_completion`;
   - `test_rumor_kind_disabled_without_312` (skip do tipo, menu sem rumores).
2. **Implementação:** `_rumor_api`, `_rumor_seeds`, ramo em `engine_completions`,
   `<DESFECHO_DE_QUEST>`.

### Etapa 6 — Entrega e escolta

1. **Testes** (`tests/test_spec313_delivery_escort.py`):
   - `test_delivery_completes_at_destination_with_item_and_vocab`;
   - `test_delivery_removes_item_once_in_same_apply_as_gold`;
   - `test_delivery_rejected_if_item_gone_before_apply`;
   - `test_delivery_requires_distance_at_least_one_day`;
   - `test_delivery_fail_keeps_item`;
   - `test_escort_npc_follows_player_and_skips_daily_step`;
   - `test_escort_no_offscreen_peril_while_escorted`;
   - `test_escort_pauses_when_player_detours_and_resumes_on_return`;
   - `test_escort_completes_on_arrival_and_npc_stays_at_destination`;
   - `test_escort_fail_on_deadline_clears_escort_resumes_simulation`;
   - `test_escorted_npc_never_in_party_nor_combat`;
   - `test_escort_and_delivery_do_not_change_encounters` (R27).
2. **Implementação:** ramos de `engine_completions`, `event_processor`, `npc_world.escort_*`,
   `presence`.

### Etapa 7 — Mortos, falha e superfícies

1. **Testes** (`tests/test_spec313_dead_surfaces.py`):
   - `test_dead_quest_from_perceived_escalation_once_per_crisis`;
   - `test_dead_and_conter_praga_coexist_distinct_sources`;
   - `test_dead_relief_and_fail_cause_praga`;
   - `test_fail_texts_neutral_all_kinds_all_channels` (R25);
   - `test_api_whitelist_hides_lore_internals` (`/game/state` e `/game/action`; R28);
   - `test_outcome_label_only_after_completion`;
   - `test_prompt_block_shows_kind_in_words_no_ids_no_numbers` (R29);
   - `test_no_extra_llm_invoke` (contador de invokes).
2. **Implementação:** `_dead_seeds`, `pressures.json`, `public_quest_view`, blocos do storyteller.

### Etapa 8 — Rollout, playtest e prova

1. **Testes** (`tests/test_spec313_playtest.py`):
   - `test_mode_off_downgrades_and_hides_menu`; `test_shadow_writes_nothing`;
     `test_requires_world_quests_on`;
   - `test_invariants_detect_anchor_invalid_cooldown_truth_leak_escort_split`;
   - `test_mock_npc_proposes_from_menu` (R34);
   - `test_scenario_lore_quests_offers_and_completes_hunt` (MockLLM, cenário `lore_quests`:
     conversa → oferta → combate na região → conclusão).
2. **Implementação:** flag, invariantes, telemetria, relatório, cenário, mock.
3. **Verificação:** playtest `--all --turns 50` (MockLLM) com `RPG_WORLD_ENGINE=on`,
   `RPG_WORLD_QUESTS=on`, `RPG_LORE_QUESTS=on`, `RPG_NPC_WORLD=on`: 0 violação `error`; registrar
   na §8 ofertas/rebaixamentos/conclusões por tipo e perfil. Letalidade SPEC-285 M1/M2/M5 (seeds
   21-32 × 200, `combate`) sem regressão contra a medição da 305. Ruff nos tocados; suíte completa
   1× no pouso (coordenador).

## 5. Critérios de aceite

- [ ] R1-R4: cinco tipos no catálogo com `lore_refs` válidos (lint verde); âncora validada pelo
      motor; `ponto_fraco` fora
- [ ] R5-R10: `ProposedQuest.kind/anchor_id`; só o `npc_actor` ancora; motor monta a quest; texto
      da LLM com guarda; sem duplicar a 301; dedupe
- [ ] R11-R13: menu sem números nem verdade de rumor; percepção gravada; independente do herói
- [ ] R14-R19: prazo e recompensa só do motor; uma por fonte; cooldowns em dias; teto 2; prova
      mecânica
- [ ] R20-R25: caça por `bestiary_id`; entrega consome item uma vez; escolta sem teleporte e sem
      combate; rumor falso conclui como "boato" sem virar fato; mortos com alívio/falha; falha neutra
- [ ] R26-R27: letalidade SPEC-285 sem regressão; nenhum encontro novo
- [ ] R28-R34: API com lista branca; prompt sem ids; saves antigos carregam; determinismo;
      rollout `off|shadow|on`; invariantes e relatório; mock exercita o caminho
- [ ] Guard de FallbackLLM: o schema do `npc_actor` muda (campo novo em `ProposedQuest`); o
      `isinstance` existente (`agents/npc.py:1325`) cobre; teste com FallbackLLM sem quest nova
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Revisão independente Opus (`handoffs/SPEC-313-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado na §8

## 6. Smoke test com LLM real

Teto: US$ 3/dia, campanhas curtas. Pré-requisito: `RPG_WORLD_ENGINE=on`, `RPG_WORLD_QUESTS=on`,
`RPG_LORE_QUESTS=on`, `RPG_NPC_WORLD=on`, `RPG_NPC_KNOWLEDGE=on`, DeepSeek nas `ROUTES`. O ponto
crítico é de mapeamento: o MockLLM sempre devolve `kind`/`anchor_id` válidos; o modelo real pode
devolver `anchor_id` com nome em vez de id, `kind` fora do enum (Groq strict) ou prazo no texto.

1. **Caça dirigida** (`uv run python -m playtest run --scenario lore_quests --turns 12 --real
   --max-cost 0.40 --seed 31`): herói em `skallgard` pede trabalho a um caçador. Assertar
   `mock=False`; ≥ 1 proposta com `kind="cacar_criatura"` aceita **ou** rebaixamento logado com
   motivo (anotar o motivo); `/game/state` com `kind="mundo"`, `deadline_label`, `reward_hint` em
   palavras e sem `lore_anchor`/`reward_gold_planned`; combate na região com a âncora → concluída.
2. **Entrega** (`--scenario lore_quests_entrega --turns 10 --seed 32`; início no `pantano_melancolia`, druida em cena e 2 `musgo_cinzento` no inventário): a quest
   `cha_druidas_anel_lama` é oferecida; viajar a `na_anel_lama` com 2 `musgo_cinzento` (fixture do
   cenário) e entregar → concluída, item removido uma vez, ouro pago uma vez.
3. **Rumor falso** (`--scenario lore_quests_rumor --turns 10 --seed 33`; boato `truth=False` já percebido): rumor ouvido →
   quest → investigar no local → `outcome="desmentido"` (rótulo "era só boato"); ler o transcrito: o narrador não trata como
   verdade antes nem depois; nenhum fato novo no `event_log`.
4. **Escolta** (`--scenario lore_quests_escolta --turns 10 --seed 34`, mercador itinerante em cena): oferta → viagem de 2 locais → o NPC
   aparece em cena em cada parada → chegada conclui.
5. Leitura humana de 5 trechos dos transcritos: nenhum número de dias ou moedas na fala do NPC
   sobre a tarefa, nenhuma fação desconhecida nomeada, nenhuma tarefa que o personagem não ouviu.

Comando-base (todas as flags; trocar `--scenario`/`--seed`): `RPG_WORLD_ENGINE=on RPG_WORLD_QUESTS=on
RPG_LORE_QUESTS=on RPG_NPC_WORLD=on RPG_NPC_KNOWLEDGE=on RPG_LOG_LEVEL=info bash scripts/dev/py.sh -m
playtest run --scenario <lore_quests|lore_quests_entrega|lore_quests_rumor|lore_quests_escolta>
--turns <12|10|10|10> --real --max-cost 0.40 --seed <31|32|33|34>`. Contar `lore_quest.downgraded` por
`reason` (`menu_empty`, `kind_mismatch`, `name_not_id`, `not_in_menu`): só `name_not_id`/`not_in_menu`
com menu não vazio contam como erro do modelo; `menu_empty` é a LLM ancorando sem menu (o prompt agora
diz `kind="comum"` quando o teto/cooldown esvazia o menu).

Custo esperado: ≤ US$ 1,20. Se um passo estourar o teto, parar e registrar. Se o modelo errar o
`anchor_id` com frequência (> 50% de rebaixamentos), registrar e ajustar só o texto do menu (nunca
afrouxar a validação).

## 7. Riscos & compatibilidade

- **Saves antigos:** campos opcionais; quest sem `world_kind` ou com os 9 tipos da 305 segue
  igual; `NpcSimEntry` sem `escort` = sem escolta.
- **Schema do LLM:** `kind` é `Literal` com default; Groq usa function calling
  (`RoutedLLM._apply`), que aceita enum. Valor fora do enum → falha de parse daquele candidato →
  fallback de provider; o guard atual cobre. Teste com FallbackLLM: nenhuma quest e nenhum erro.
- **Regra de ouro:** o menu é o ponto de vazamento possível. Mitigação: só fauna regional pública,
  rotas curadas, o próprio NPC e rumores que ele conhece; verdade de rumor só no motor, só na
  conclusão; invariante `quest.rumor_truth_leaked`.
- **Farm:** cooldowns em dias + uma por fonte + teto 2 + prova mecânica. Risco residual: comprar
  material barato para entregar (lucro de 5-30 de ouro por viagem de dias). Aceitável; valores
  `[BALANCEAR]`.
- **Letalidade:** só a caça mexe no sorteio, e só depois de o encontro disparar; medido na Etapa 8.
  Se regredir, a correção é no `theme` (desligar a preferência em perigo ≥ 4), nunca no combate.
- **Acoplamento com a 304:** `presence` e o passo diário ganham um ramo. Teste de regressão: com
  nenhuma escolta, todo o comportamento da 304 é idêntico (mesma seed, mesmo `npc_sim`).
- **Acoplamento com a 312 (paralela):** contrato mínimo (§3.4) atrás de `_rumor_api()`; sem ela,
  o tipo some sem erro.
- **Duplicação com a 301:** R9 e a ausência de `faction_id` na quest ancorada; a conclusão nunca
  chama `on_mission_completed`.
- **Quota/latência:** zero chamada LLM nova; +~150 tokens no prompt do NPC quando há ganchos.
- **Rollback:** `RPG_LORE_QUESTS=off` esconde o menu e rebaixa propostas; quests já criadas seguem
  pelo caminho da 305 (prazo e conclusão do motor) até resolverem.

## 8. Evidência

### 8.1 Implementação (25/10)

Testes do escopo: `tests/test_spec313_*.py` (catálogo/lint de lore, menu e validação, oferta/anti-farm,
caça e encontros, rumor, entrega/escolta, mortos/superfícies, rollout/invariantes/mock/cenário
`lore_quests`). Pendentes (coordenador): suíte completa 1×, playtest `--all --turns 50`, letalidade
SPEC-285 M1/M2/M5 (seeds 21-32 × 200, `combate`), smoke real §6, revisão independente.

### 8.2 Desvios da implementação em relação ao texto acima (todos deliberados)

- **Contrato da 312 (como já previsto na nota do coordenador):** `rumors.investigable(state, day)`,
  `rumors.truth_of(state, rumor_id)`, `rumors.mark_resolved(sim, rumor_id, outcome, day)`. O
  desfecho da quest usa o vocabulário da 312: `confirmado | desmentido | inconclusivo` (no lugar de
  `boato`); o rótulo público de `desmentido` continua "era só boato". Gancho único para a 315:
  `lore_quests.resolve_rumor_outcome(state, quest, day)` (só ele lê a verdade). `investigable`
  não devolve texto nem canal: a descrição usa `rumors.text_for` (texto público) e o canal de
  origem-motor é `rumor` com `event_id = rumor_id` (o invariante `quest.world_unheard` aceita o
  rumor com `perceived_day`).
- **R10/§3.4:** `world_quests.offer_from_proposal(state, proposal, npc_key, menu, day, *,
  origin_entity_id="")` devolve `(quests, criada | None, motivo)`; motivo em
  `lore_quests.DOWNGRADE_REASONS` => o `npc_actor` registra como quest comum; qualquer outro =>
  descartada. Não há `lore_hook` em `register_proposed_quests`: o desvio é feito em
  `agents/npc.py::_apply_lore_proposals`, depois do bloco de `membership_action` (R9).
- **R19 (entrega):** o piso de distância é `DELIVERY_MIN_PERIODS = 1` (não `PERIODS_PER_DAY`). No
  mapa real nenhuma rota curada de lore tem ≥ 5 períodos (pântano → Anel de Lama = 1), então a
  regra original eliminaria a rota-exemplo da própria spec. Destino = local de origem continua
  proibido. Prazo e recompensa seguem as bandas por dias (R14/R15).
- **R25:** o `fail_text` de `recolher_mortos` foi reescrito ("O prazo para recolher o que restou em
  {local} passou.") porque o texto original continha "mortos", proibido pelo próprio R25.
- **R11:** ordenação das criaturas por abundância decrescente (`hunt_pressure` maior primeiro; o
  "menor primeiro" do texto contradizia "abundância"); itens intercalados por tipo e cortados para
  ≤ 150 tokens (≤ 9 itens). Rumores do menu = rumores `investigable` da região do NPC (o filtro "o
  NPC conhece" da 215/312 é aproximado pela região).
- **R22:** além de `escort_start/escort_stop/escort_destinations`, `npc_world.escort_sync` roda no
  `turn_finalizer` (acompanha/pausa; solta a escolta cuja quest não está mais ativa: concluída,
  falhada, expirada ou abandonada); o `event_processor` não chama `escort_stop`.
- **R20:** a prova `hunt_kill` é registrada na vitória (`agents/combat.py`); a conclusão é emitida
  por `engine_completions` no turno seguinte do narrador.
- **R23/312 R24:** títulos de evento de `investigar_rumor` no `event_log`/crônica são genéricos
  ("Conferir um rumor") e o payload do alívio não carrega o `rumor_id`.
- **R32:** em `shadow` o menu é calculado e logado (`lore_quest.shadow_offer`) mas nunca emitido.
- **R34:** o mock propõe o primeiro item do menu em toda conversa (sem o "1 em cada 4"); o
  cooldown de origem (R17) impede repetição.
- **305 `_offer`:** o teto de 3 quests de crise passou de `break` para `continue` para não bloquear
  ofertas de lore na mesma rodada.

## 9. Decisões do dono

Já decididas em 24/10:

- **D-A — Boato falso pode gerar quest.** Sim (R23).
- **D-B — Quais tipos.** A critério da spec, ancorados na lore: os cinco de R1; `ponto_fraco`
  fica fora (D7).

Abertas (o executor segue o **recomendado** se o dono não disser nada):

- **D1 — Teto.** Recomendado: **2** quests ancoradas ativas, separado do teto de 3 da 305
  (dentro das 8). Alternativa: dividir as 3 da 305.
- **D2 — Valores de recompensa e prazo** (R14/R15). Recomendado: os da §3.5, `[BALANCEAR]`.
- **D3 — Rumor falso investigado.** Recomendado: **conclui** com "era só boato" e a mesma
  recompensa do verdadeiro (o trabalho foi feito; recompensa diferente vazaria a verdade antes da
  hora pelo `reward_hint`). Alternativa: concluir sem ouro.
- **D4 — Entrega consome o material.** Recomendado: **sim** (é uma entrega).
- **D5 — Escoltado em combate.** Recomendado: **não luta e não sofre dano na v1**; desvio pausa a
  escolta em vez de falhar.
- **D6 — Consequência de falha.** Recomendado: só `recolher_mortos` (`praga +6` na região); os
  outros quatro falham sem efeito no mundo.
- **D7 — `ponto_fraco` de fação.** Recomendado: **fora**, para N5/N8 (são segredos).
- **D8 — Revisão de conteúdo de `delivery_routes`.** As rotas são curadas (como as sementes da
  297 D8). O dono revisa a lista antes de `on` no staging; a suíte e o local rodam com ela.
- **D9 — Default de `RPG_LORE_QUESTS`.** Recomendado: `on` local e na suíte; `shadow` no staging
  até o smoke §6; `on` no staging depois do OK.
- **D10 — Storyteller ancora?** Recomendado: **não** (só o `npc_actor`; R6).


## Nota do coordenador (2026-10-24) — contrato com a SPEC-312

A SPEC-312 (escrita em paralelo, branch `spec-312`) define a interface de rumor como
`investigable(state, rumor_id)`, `truth_of(state, rumor_id)` e `mark_resolved(state, rumor_id, outcome)`
(§3.6 da 312), sem expor `truth` na oferta. **Esta spec segue a interface da 312**, que pousa antes; os
nomes `heard_rumors`/`rumor_truth`/`mark_investigated` daqui são substituídos por ela na Etapa 0. Sem a
312 pousada, `investigar_rumor` fica desligado (como já previsto).
