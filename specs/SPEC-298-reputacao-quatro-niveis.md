# SPEC-298 — Reputação em quatro níveis (NPC, fação, local, raça/origem)

> **Status:** `in-progress` (aprovada pelo dono 2026-10-23; etapas 1-9 implementadas, falta revisão independente + smoke real §6)
> **Criada:** 2026-10-20 · **Atualizada:** 2026-10-20
> **Depende de:** SPEC-215 (`npc_knowledge`: testemunha/propagação, `done`), SPEC-226 R8 (reputação só com evento aceito, `done`), SPEC-230 (teto ±1/turno de relação, `done`), SPEC-206/293 (projeção player-facing fail-closed, `done`). Dependência **suave** da SPEC-296 (liga `RPG_NPC_KNOWLEDGE=on` no staging): sem ela a fama por local fica restrita a testemunhas diretas (ver R14).
> **Desbloqueia:** SPEC-299 (lei/crime: consome `fame_at`, `register_deed_kind`, `world.shelter`, `intercession_available`), SPEC-300 (companheiros/romance: consome `npc_tier`, `apply_npc_delta`, avisos), SPEC-301 (patentes: consome `faction_tier`).
> **Origem:** `docs/mundo-vivo/VISAO.md` (decisões 6 e 7; § Regra de ouro; § C. Sociedade viva; § Calibração; § Restrições). Ajuste do coordenador (20/10): os contextos de DC `comercio`/`intimidacao`/`insight` são desta spec, não da SPEC-296.

---

## 1. Contexto & Objetivo

Hoje a reputação existe em dois níveis desconectados e nenhum deles tem consequência mecânica:

| # | Problema | Evidência |
|---|---|---|
| P1 | Reputação de fação decidida por **palavra-chave** na string `direction` (`"+"`, `"-"`, `"contra"`, `"atac"`…), delta fixo ±12. | `world_utils.py:518-541` (`REP_STEP`, `_POS_CUES`, `_NEG_CUES`, `_direction_sign`), `world_utils.py:544-578` |
| P2 | O LLM escolhe livremente fação e direção (string livre); o storyteller aplica **antes** da validação e o processador precisa desfazer. | `agents/storyteller.py:41-47` (`FactionImpact.direction: str`), `agents/storyteller.py:1103-1133`, `services/event_processor.py:287-315` (`_revert_reputation`) |
| P3 | Fação muda de ideia sobre o jogador sem ter visto nem ouvido nada (fura a regra de ouro). | `agents/storyteller.py:1116-1133` (aplica para qualquer fação listada, sem checar presença/testemunha) |
| P4 | Preço ignora a relação com o NPC; só a disposição da fação controladora (`hostil` ×1,5). | `services/economy.py:176-189`, `services/economy.py:104-112` |
| P5 | Os 6 mercadores são dados soltos, sem NPC, sem traços, sem relação. | `data/merchants.json:1-15` (sem `npc_id`), `services/economy.py:230-232`, `:289-320` |
| P6 | Dos 4 contextos de DC dos traços, só `persuasao` tem consumidor (recrutamento); `comercio`, `intimidacao` e `insight` são dados mortos, apesar de 60+ traços os definirem. | `services/npc_layers.py:24`, `:217-223`; único chamador `party.py:316-319`; ex.: `data/traits.json:7-10,20-23,33-35` |
| P7 | Não existe teste social: `general_test` (2d10 Ímpeto/Presságio + Virtude) não tem chamador de produto. | `services/conflict_resolution.py:230-279` (definida, sem uso fora de testes) |
| P8 | A relação inicial de NPC é 5 fixo (ou o que o LLM disser); raça, origem e fama não pesam. | `agents/npc.py:135` (`initial_relationship: int = 5` no schema do LLM), `agents/npc.py:571` |
| P9 | Raça é só texto de ficha (nome exibível, não id); a região de origem nem é persistida no `player`. NPCs não têm raça. | `state.py:125`, `game_engine.py:220-221`, `api.py:4565-4568` (sem `region`), `agents/npc.py:129-144` (sem raça); grafo só tem raça em `tags` (`data/graph/entities.json:2515-2519`) |
| P10 | A atitude do NPC não chega ao prompt do ator: o LLM não sabe se o NPC gosta ou desconfia do jogador. | `agents/npc.py:747-761` (bloco `<ROLE>` sem relação) |
| P11 | Relação alta não destrava nada: `faction_reveals` aceitos de qualquer NPC em qualquer nível; não há favores. | `agents/npc.py:941-948` |
| P12 | A UI mostra **números** (corações 0–10, "reputação +N", sparkline, "(8/10)"), contra a decisão 7. | `services/dossiers.py:173`, `api.py:2555-2558`, `web/src/components/Hud.tsx:129-135,152-166,208`, `web/src/components/tabs/DossierDetail.tsx:63,118` |
| P13 | Não existe fama por local. | — (ausência; `state.py:229-260` sem campo) |

**Objetivo.** Um único serviço determinístico (`services/reputation.py`) passa a ser o dono das quatro camadas:

1. **NPC** — `npcs[*].relationship` 0–10 (já existe), agora com relação inicial calculada em Python e mudanças derivadas de eventos validados e do que o NPC **testemunhou/ouviu**.
2. **Fação** — `factions[*].reputation` −100..100 (já existe), agora com delta tabelado a partir de um evento validado (`faction_deed`) e aplicado **só quando a fação sabe** (membro presente/local controlado, ou notícia entregue pela SPEC-215).
3. **Local (fama)** — novo `location_fame[loc] = {renown, infamy}`, que só cresce quando o feito é testemunhado ali ou a notícia chega ali (SPEC-215 `location_heard`).
4. **Raça/origem** — nova tabela curada da lore (`data/race_attitudes.json`) que desloca a **relação inicial** e pode causar recusas raras. Como mexe só no ponto de partida da mesma escala, a reputação pessoal supera o preconceito por construção.

Efeitos: preço e estoque raro (mercador ligado a um NPC), informação (gating de `faction_reveals` e de rumores), favores (esconder, emprestar, interceder), testes sociais de intimidação e intuição com `trait_dc_modifier`. Exibição só por rótulos vagos e avisos de mudança ("Brenna não gostou disso."), sem números.

Princípio: mecânica em Python, determinística por seed; o LLM só **classifica** (rota/abordagem/impacto) e **narra** (VISAO § Restrições).

## 2. Requisitos

### 2.1 Núcleo e rótulos

- **R1 — Dono único.** `services/reputation.py` é o único escritor de `npcs[*].relationship` (fora da criação), `factions[*].reputation`/`disposition` e `location_fame`. `agents/npc.py:836-839` e `agents/storyteller.py:1116-1133` passam a chamar suas funções. Antes de implementar, confirmar o owner atual em `project_index/state_ownership` (consulta seletiva, AGENTS.md § Operação) e registrar o novo owner.
- **R2 — Faixas de NPC.** `npc_tier(rel) -> "hostil"|"desconfiado"|"neutro"|"amistoso"|"leal"` com as faixas atuais de `services/dossiers.py:28-34` (≤1, ≤3, ≤6, ≤8, ≤10). `dossiers.disposition_label` passa a delegar a esta função (mesmo texto capitalizado).
- **R3 — Faixas de fação.** `faction_tier(rep) -> "hostil"(≤−40)|"desconfiado"(−39..−10)|"neutro"(−9..9)|"amistoso"(10..39)|"aliado"(≥40)`. `factions[*].disposition` (`hostil|neutro|aliado`, consumido por `economy._controller_disposition`) continua derivado por `_disposition_for` com os limiares atuais (`world_utils.py:520`), sem mudança de comportamento.
- **R4 — Fama.** `fame_view(renown, infamy) -> {renown_label, infamy_label}`; renome: `desconhecido`(<10) · `conhecido`(10–29) · `afamado`(30–59) · `lendário`(≥60); infâmia: `—`(<10) · `malvisto`(10–29) · `temido`(30–59) · `odiado`(≥60). Ambos clampados em 0..100.

### 2.2 Raça e origem

- **R5 — Ids persistidos.** Jogo novo grava `player.race_id` (id de `data/origins.json:2-117`) e `player.origin_region_id` (id de `data/origins.json:118-130`) além do `race` exibível. Save antigo: `race_id` resolvido pelo nome (`"Humano"` → `race_humanos`, sem diferenciar caixa/acento); sem match ou sem região → `""` (neutro).
- **R6 — Raça do NPC.** `npcs[*].race_id` resolvido em ordem: (a) NPC do grafo → token de raça em `tags` (`humano|elfo|anao|vrel|cinzeu|osshari`, ex. `data/graph/entities.json:2518`); (b) NPC gerado → campo novo opcional `NPCSchema.race_id` validado contra os 6 ids (inválido → `""`); (c) senão `""`. Raças não jogáveis da lore ficam `""` (neutro).
- **R7 — Tabela curada.** `data/race_attitudes.json` define `attitude(observador, alvo) ∈ {−2,−1,0,+1,+2}`, com `source` (arquivo:linha da lore) obrigatório em cada entrada ≠ 0. Humanos usam **cultura** (derivada da região do local-casa do NPC), não a raça. Inclui regras locais (ex.: Vrel aceitos em Skallgard). Lint em `scripts/validate_content.py`: ids válidos, valores na faixa, `source` presente. Conteúdo inicial proposto em §3.4 (para revisão do dono).
- **R8 — Relação inicial.** Na criação/primeiro registro de um NPC na sessão, `initial_relationship(state, npc)` = `5 + race_term + origin_term + fame_term + faction_term`, clampado em **2..8**:
  - `race_term` = `attitude(npc, player)` (R7);
  - `origin_term` = +1 se `player.origin_region_id` == região do local-casa do NPC ("conterrâneo"), senão 0. Atenção: `data/world_map.json` guarda a região como **nome exibível** (`"region": "Nova Arcádia"`, `:7`); a comparação resolve nome → id por `data/origins.json:118-130` (helper único `region_id_of(location_id)`, reusado pela cultura humana de R7);
  - `fame_term` = +1 se renome no local-casa ≥ `conhecido`, +2 se ≥ `afamado`; −1 se infâmia ≥ `malvisto`, −2 se ≥ `temido` (a fama só existe ali se foi ouvida — R14);
  - `faction_term` = `round(rep_fação_do_NPC / 25)` clampado em −2..+2, **só se** a fação do NPC já soube de algum feito do jogador (R12).
  O `initial_relationship` proposto pelo LLM (`agents/npc.py:135`) é ignorado para NPC novo do motor (o prólogo, `services/prologue.py:25,249`, mantém o seu `REL_MAP`). Grava `npcs[*].relationship_basis = {race, origin, fame, faction}` (auditoria interna, nunca na API).
- **R9 — Recusa rara.** `refuses(state, npc, kind)` é verdadeiro **só** se `attitude(npc, player) == −2` **e** `relationship ≤ 2`. `kind ∈ {"comercio","favor"}`. Conversa nunca é recusada por raça. Como a raça só desloca o ponto inicial (R8), uma relação pessoal ≥ 3 anula a recusa.

### 2.3 Fação por eventos validados

- **R10 — Fim das palavras-chave.** `FactionImpact.direction` vira `Literal["ajudou","prejudicou"]` e ganha `magnitude: Literal["menor","maior"] = "menor"`. Valor inválido → impacto descartado (validador antes da validação Pydantic, padrão SPEC-045). `_POS_CUES`/`_NEG_CUES`/`_direction_sign` são removidos; `apply_reputation` passa a aceitar só `"ajudou"|"prejudicou"` exatos e um `delta` explícito.
- **R11 — Evento `faction_deed`.** O storyteller **não** aplica mais reputação; enfileira uma proposta `faction_deed` (`actor_id="player"`, `target_id=faction_id`, `payload={direction, magnitude, location_id}`, `source="storyteller"`). O validador `_v_faction_deed` aceita só se a fação existe e está viva **e** está *em cena*: controla o local atual (`gr.get_current_controller`) **ou** há NPC presente (`in_scene`) com `faction == faction_id` **ou** há quest ativa com `origin_entity_id` de membro dessa fação. Um impacto por fação por turno (SPEC-226 R8 mantido).
- **R12 — A fação só muda quando sabe.** Para cada feito aceito, o motor calcula o delta pela tabela `DEED_TABLE` (§3.3) e:
  - se a fação **testemunhou** (controla o local atual ou tem membro presente) → aplica no mesmo turno e emite `reputation_changed` (`source="reputation"`);
  - senão → grava em `reputation_pending` e aplica quando a SPEC-215 entregar o assunto a um local controlado pela fação ou a um NPC-membro (`knowledge_links` com `holder` membro), emitindo `reputation_changed` naquele turno;
  - pendência mais velha que `PENDING_TTL_DAYS` (30 dias de jogo) expira sem efeito.
  Com `RPG_NPC_KNOWLEDGE=off` só o ramo "testemunhou" existe (pendências não são criadas).
- **R13 — Feitos derivados de eventos do motor.** Além de `faction_deed`, o motor gera feitos a partir de eventos **já aceitos** no `event_log` do turno (nunca de texto): `quest_completed` (fação/NPC de origem da quest), `npc_killed` com `actor_id="player"` (fação da vítima; local) — pesos em `DEED_TABLE`. `_revert_reputation` (`services/event_processor.py:287-315`) deixa de ser necessário e é removido junto com o caminho "aplica antes".

### 2.4 Fama por local (regra de ouro)

- **R14 — Fama só pelo que foi visto/ouvido.** Todo feito (R11/R13) com peso de fama vira assunto testemunhável da SPEC-215 (tipo `player_deed` em `SUBJECT_PARAMS`, `services/npc_knowledge.py:48-55`). `location_fame[loc]` recebe o peso do feito quando: (a) o feito acontece em `loc` com ao menos uma testemunha registrada (`record_witnesses`, `npc_knowledge.py:322-354`) — sem NPC presente, ninguém viu, sem fama; ou (b) a notícia é entregue em `loc` (`deliver_due`, `npc_knowledge.py:563-622`). Idempotente por `(loc, subject_id)` (lista `deeds`, teto 100 por local). Com `off`, só o caso (a) vale.
- **R15 — NPC reage ao que sabe.** Quando um NPC passa a ter `observed_by`/`told_to` de um `player_deed` que o afeta (vítima é da sua fação, aliado ou o próprio NPC; ou feito a favor da sua fação), `apply_npc_delta` aplica ±1 **uma vez por assunto** (`npcs[*].heard_deeds`, teto 50). Respeita o teto por turno da SPEC-230 (±1 do LLM) somado a no máximo ±1 do motor (teto efetivo ±2/turno).
- **R16 — Interface de fama para outras specs.** Públicas e estáveis: `fame_at(state, location_id) -> FameView`; `register_deed_kind(event_type, weights)` (SPEC-299 registra crimes com peso de infâmia); `deed_known_at(state, subject_id, location_id) -> bool`. Notoriedade/procurado/caçadores ficam na SPEC-299 (que pode ler `infamy`).

### 2.5 Efeitos (o que a relação destrava)

- **R17 — Mercador é um NPC.** `data/merchants.json` ganha `keeper` por mercador: `{"npc_id": "<id do grafo>"}` **ou** `{"name", "role", "race_id"}` curados. Na primeira visita (`merchant_stock`) o keeper vira registro em `state.npcs` sem chamada LLM (`ensure_npc_fields`, traços seeded por `npc_layers.roll_hidden_traits`), com relação inicial por R8. Mapeamento inicial proposto em §3.4 (decisão do dono).
- **R18 — Preço por relação e traço `comercio`.** `economy.price(..., merchant=...)` multiplica por `relation_price_mult(state, keeper)` = faixa (hostil 1,30 · desconfiado 1,15 · neutro 1,00 · amistoso 0,92 · leal 0,85) × `(1 + 0,03 × trait_dc_modifier(keeper, "comercio"))` — modificador negativo = mais barato na compra. Venda usa o inverso (amistoso paga mais). Resultado do fator combinado clampado em **0,75..1,50**; empilha com escassez e `HOSTILE_BUY_MULT` sem mudar a ordem atual (`economy.py:179-189`).
- **R19 — Estoque raro e recusa.** `merchants.json` ganha `rare_stock` opcional; entra na prateleira só com keeper `leal` (e respeita as regras atuais de escassez/único, `economy.py:306-319`). Keeper `hostil` esconde raro+ (mesma regra de `economy.py:297-305`, agora também por NPC). `refuses(...,"comercio")` (R9) → `execute_trade` devolve código `merchant_refuses` com texto curto.
- **R20 — Abordagem social classificada, resolvida em Python.** `RouterDecision` ganha `social_approach: Literal["conversar","intimidar","sondar","pedir_favor","pagar_divida"] | None = None` e `favor_kind: Literal["esconder","emprestar","interceder"] | None = None` (preenchidos só na rota NPC; inválido → `conversar`). O `npc_actor` resolve **antes** de chamar o LLM e passa o resultado no prompt; o LLM só narra.
- **R21 — Intimidação.** `general_test(player, "forca", dc, rng=seeded)` com `dc = 12 + trait_dc_modifier(npc,"intimidacao") + infamy_bonus` (`temido` −2, `odiado` −3 no local), seed `sha256(game_id|turn|npc_id|intimidar)`. Sucesso → o NPC cede (nível de revelação de fação deste turno sobe um degrau acima do permitido pela faixa, R23) e relação −1. Falha → relação −1 e o NPC se fecha (nível de revelação = nenhum neste turno). Sempre emite aviso (R26).
- **R22 — Intuição (insight).** `general_test(player, "mente", dc)` com `dc = 12 + trait_dc_modifier(npc,"insight")`, mesma seed. Sucesso → revela o primeiro traço oculto (ordem estável) via `npc_layers` (mesmo caminho de `tick_interaction`, `npc_layers.py:200-214`) e o rótulo de atitude do NPC entra no aviso ("Você percebe que Brenna desconfia de você."). Falha → nada muda. Sem efeito na relação.
- **R23 — Informação por faixa.** `faction_reveals` do NPC (`agents/npc.py:941-948`) é clampado por Python ao teto da faixa: hostil/desconfiado → nenhum; neutro → `existencia`; amistoso → `objetivo`; leal → `progresso`. As linhas de conhecimento do NPC injetadas no prompt (`npc_knowledge_block`, SPEC-215 R11) têm teto por faixa: 0 · 2 · 4 · 6 · 8. O NPC não pode contar o que não recebeu.
- **R24 — Favores.** `favor_decision(state, npc, kind)` determinística: limiar = faixa mínima (`esconder` e `interceder` ≥ amistoso; `emprestar` ≥ leal) com `required = base + trait_dc_modifier(npc,"persuasao")` (mesmo padrão de `party.py:319`), recusa por R9, e 1 favor por NPC a cada 3 dias de jogo (`npcs[*].favors.last_day`). Efeitos:
  - `esconder` → `world.shelter = {npc_id, location_id, until_clock}` (até o fim do período seguinte). Contrato para a SPEC-299 (busca de guardas ignora o jogador abrigado); nesta spec só é gravado e exibido.
  - `emprestar` → +ouro (`50` leal; `[BALANCEAR]`), `npcs[*].favors.debt = {amount, due_day = dia+7}`. `pagar_divida` quita (Python debita, `clamp_gold`). Vencida sem pagamento → relação −2 uma vez e aviso.
  - `interceder` → `npcs[*].favors.intercession = {faction_id}` consumível: o próximo delta negativo de reputação dessa fação é reduzido à metade. Interface `intercession_available(state, faction_id)` para a SPEC-299 (multa).

### 2.6 Prompt, visibilidade e avisos

- **R25 — Atitude no prompt.** O `<ROLE>` do `npc_actor` ganha `<ATITUDE>`: rótulo da faixa, motivos qualitativos (raça/origem/fama/feitos ouvidos, sem números) e o resultado da abordagem social do turno. O storyteller recebe uma linha de fama do local atual **só** se o rótulo ≠ `desconhecido`/`—`.
- **R26 — Avisos de mudança.** `reputation_notices: list[{kind, subject_id, text}]` é sobrescrito a cada turno pelo `turn_finalizer` e sai na resposta. Templates fixos em Python (sem LLM), ex.: `"{npc} não gostou disso."`, `"{npc} parece mais à vontade com você."`, `"{fação} vai lembrar disso."`, `"Em {local}, já falam de você."`. Regras de emissão (regra de ouro):
  - NPC: só NPC conhecido e presente na cena;
  - fação: só fação com `faction_intel.known` **e** que testemunhou neste turno (pendência entregue longe do jogador **não** gera aviso);
  - fama: só quando o jogador está no local e o rótulo mudou.
  O texto passa pela projeção da SPEC-293 (`conceal_for`).
- **R27 — Sem números na superfície.** Payloads player-facing (`_npcs_block`, `_factions_block` em `api.py:2530-2562`, `build_dossiers`, Codex) deixam de levar `relationship`, `reputation` e `history[].value`; passam a levar `attitude_label` (NPC), `standing_label` (fação) e `recent_changes: [{turn, text}]` (até 3, dos avisos já emitidos). O HUD troca corações, "reputação +N" e sparkline por rótulo + mudanças recentes; `DossierDetail` idem. Oráculo: teste percorre os payloads e falha se achar as chaves numéricas.

### 2.7 Compatibilidade

- **R28 — Migração suave, sem bump.** Campos novos são aditivos com default neutro (`SCHEMA_VERSION` segue 8, `persistence.py:85`): `player.race_id/origin_region_id`, `npcs[*].race_id/relationship_basis/heard_deeds/favors`, `location_fame = {}`, `reputation_pending = []`, `reputation_notices = []`, `world.shelter = None`. NPCs já existentes **não** têm a relação recalculada (só NPC novo usa R8). Backfill idempotente num `ensure_reputation_fields(state)` chamado no load.

### Fora de escopo

- Romance, vínculo e companheiros que opinam/saem (SPEC-300); aqui só a interface `npc_tier`/`apply_npc_delta`/avisos.
- Crime, lei por região, notoriedade, guardas, caçadores, multa, cartazes (SPEC-299); aqui só `fame_at`, `register_deed_kind`, `world.shelter`, `intercession_available`.
- Patentes de fação (SPEC-301); NPCs off-screen, decaimento de fama com o tempo e motor de mundo (SPEC-302).
- Pool compartilhado entre mundos (SPEC-297): `race_id` do NPC é estado por jogo.
- Classe social/riqueza como critério dos humanos urbanos (`lore_nova/races.txt:356,368`): entra como 0 (neutro).
- Raças não jogáveis (Hospedeiros de Xylos, Povo-Recife como observador fora do mapa etc.): neutro.
- Recalcular a relação de NPCs já existentes em saves antigos.
- Mudar `evals/` protegido ou datasets (`npc_knowledge` incluso); casos novos de eval ficam como follow-up com relock.
- CLI (`game_engine.py`) além de gravar `race_id`/`origin_region_id` na criação.
- Persuasão como teste rolado (segue o limiar do recrutamento); barganha por rolagem no SHOP.

## 3. Design técnico

### 3.1 Arquivos

**Novos**
- `services/reputation.py` — núcleo puro (sem LLM, sem I/O além do cache de dados): faixas, relação inicial, deltas, fama, pendências, favores, testes sociais, avisos.
- `data/race_attitudes.json` — tabela curada (R7).
- `tests/test_spec298_reputacao_nucleo.py`, `tests/test_spec298_raca_origem.py`, `tests/test_spec298_faccao_eventos.py`, `tests/test_spec298_fama_local.py`, `tests/test_spec298_economia_keeper.py`, `tests/test_spec298_social.py`, `tests/test_spec298_visibilidade.py`, `tests/test_spec298_migracao.py`.

**Alterados**
- `state.py` — campos de R28 (TypedDicts `FameEntry`, `ReputationPending`, `ReputationNotice`, `NpcFavors`).
- `world_utils.py` — remove cues (R10); `apply_reputation(factions, faction_id, direction, delta)`.
- `agents/storyteller.py` — `FactionImpact` (R10); enfileira `faction_deed` (R11); linha de fama (R25); remove aplicação direta.
- `services/world_validators.py` — `_v_faction_deed`; registro no mapa de validadores (`:473`).
- `services/structured_outputs.py` — `faction_deed` na lista de tipos (perto de `:23`).
- `services/event_processor.py` — remove `_revert_reputation` e seu uso (`:394-400`); após aplicar o lote, chama `reputation.process_deeds(...)`.
- `services/npc_knowledge.py` — `player_deed` em `SUBJECT_PARAMS` (`(0.7, 10, 2)` `[BALANCEAR]`); nenhum outro comportamento muda (datasets de eval existentes não têm esse tipo).
- `agents/turn_finalizer.py` — depois de `npc_knowledge.turn_updates` (`:35-45`), chama `reputation.turn_updates({**state, **updates})` (fama por entrega, pendências, `heard_deeds`, dívidas vencidas, avisos), com o mesmo `try/except` que não derruba o turno.
- `agents/npc.py` — `NPCSchema.race_id`; relação inicial por R8; `apply_npc_delta` no lugar de `:836-839`; `<ATITUDE>`; resolução social antes do LLM; clamp de `faction_reveals` (R23); teto de linhas de conhecimento por faixa.
- `agents/router.py` — `social_approach`/`favor_kind` (R20) + prompt curto.
- `services/economy.py` — keeper (R17), `relation_price_mult` em `price` (R18), `rare_stock`/recusa (R19).
- `data/merchants.json` — `keeper`, `rare_stock`.
- `services/dossiers.py`, `services/npc_layers.py` (`visible_npc_view`, `:259`), `api.py` (`_factions_block`, `_npcs_block`, `format_response` com `reputation_notices`) — R27.
- `character_creator.py`, `api.py` (criação, `:4529-4615`), `game_engine.py:220-254` — `race_id`/`origin_region_id` (R5).
- `persistence.py` — `ensure_reputation_fields` no load (R28).
- `scripts/validate_content.py` — lint de `race_attitudes.json` e `merchants.json.keeper`.
- `web/src/types.ts`, `web/src/components/Hud.tsx`, `web/src/components/tabs/DossierDetail.tsx`, `web/e2e/fixtures.ts`, `web/e2e/dossiers.spec.ts`, `web/e2e/critical-journeys.spec.ts` — R27.
- `mock_llm.py` — devolve `social_approach=None`, `magnitude="menor"`, `race_id=""` nos schemas tocados.
- `playtest/invariants.py` — invariantes novos (§3.6).

### 3.2 Schemas

```python
# state.py (aditivo)
class FameEntry(TypedDict, total=False):
    renown: int            # 0..100
    infamy: int            # 0..100
    deeds: list[str]       # subject_ids já contados aqui (teto 100, FIFO)

class ReputationPending(TypedDict):
    subject_id: str        # event_id do feito (assunto SPEC-215)
    faction_id: str
    delta: int             # já calculado pela DEED_TABLE
    created_day: int

class ReputationNotice(TypedDict):
    kind: Literal["npc", "faction", "fame", "favor", "social"]
    subject_id: str
    text: str

class NpcFavors(TypedDict, total=False):
    last_day: int
    debt: dict | None          # {"amount": int, "due_day": int, "overdue_applied": bool}
    intercession: dict | None  # {"faction_id": str}

# PlayerStats += race_id: str; origin_region_id: str
# npcs[*] += race_id: str; relationship_basis: dict[str,int]; heard_deeds: list[str]; favors: NpcFavors
# GameState += location_fame: dict[str, FameEntry]; reputation_pending: list[ReputationPending];
#              reputation_notices: list[ReputationNotice]
# WorldState += shelter: dict | None   # {"npc_id","location_id","until_clock"}

# agents/storyteller.py
class FactionImpact(BaseModel):
    faction_id: str
    direction: Literal["ajudou", "prejudicou"]
    magnitude: Literal["menor", "maior"] = "menor"
    # field_validator(mode="before"): valor fora do Literal -> None -> impacto descartado

# agents/router.py (RouterDecision +)
social_approach: Literal["conversar","intimidar","sondar","pedir_favor","pagar_divida"] | None = None
favor_kind: Literal["esconder","emprestar","interceder"] | None = None
```

### 3.3 Assinaturas e tabelas

```python
# services/reputation.py
NpcTier = Literal["hostil","desconfiado","neutro","amistoso","leal"]
FactionTier = Literal["hostil","desconfiado","neutro","amistoso","aliado"]

def npc_tier(relationship: Any) -> NpcTier: ...
def faction_tier(reputation: Any) -> FactionTier: ...
def fame_view(renown: int, infamy: int) -> dict[str, str]: ...
def fame_at(state: Mapping, location_id: str) -> FameView: ...         # {renown, infamy, renown_label, infamy_label}
def race_attitude(state: Mapping, npc: Mapping) -> int: ...            # −2..+2
def initial_relationship(state: Mapping, npc: Mapping) -> tuple[int, dict[str, int]]: ...
def refuses(state: Mapping, npc: Mapping, kind: str) -> bool: ...
def apply_npc_delta(state: Mapping, npc_key: str, delta: int, *, reason: str,
                    source: Literal["llm","engine"]) -> tuple[dict, ReputationNotice | None]: ...
def faction_deed_delta(direction: str, magnitude: str) -> int: ...
def process_deeds(state: Mapping, accepted_events: list[dict]) -> dict: ...   # updates parciais
def turn_updates(state: Mapping) -> dict: ...                                 # finalizer
def register_deed_kind(event_type: str, weights: DeedWeights) -> None: ...
def deed_known_at(state: Mapping, subject_id: str, location_id: str) -> bool: ...
def relation_price_mult(state: Mapping, keeper: Mapping, mode: str) -> float: ...
def social_check(state: Mapping, npc: Mapping, approach: str) -> SocialResult: ...
def favor_decision(state: Mapping, npc: Mapping, kind: str) -> FavorDecision: ...
def intercession_available(state: Mapping, faction_id: str) -> bool: ...
def reveal_ceiling(tier: NpcTier) -> Literal["","existencia","objetivo","progresso"]: ...
def knowledge_lines_cap(tier: NpcTier) -> int: ...
def ensure_reputation_fields(state: dict) -> dict: ...
```

`DEED_TABLE` (valores `[BALANCEAR]`, decisão do dono D3, §8):

| Feito (fonte validada) | Fação | NPC (quem sabe) | Fama no local |
|---|---|---|---|
| `faction_deed` ajudou/menor | +4 | +1 membros que sabem | renome +3 |
| `faction_deed` ajudou/maior | +10 | +1 | renome +8 |
| `faction_deed` prejudicou/menor | −6 | −1 | infâmia +3 se a fação controla o local |
| `faction_deed` prejudicou/maior | −15 | −1 | infâmia +8 idem |
| `quest_completed` (origem com fação) | +8 | origem +1 | renome +10 |
| `npc_killed` por `player`, vítima não hostil ao local | −12 (fação da vítima) | −1 (aliados/fação) | infâmia +15 |
| `npc_killed` por `player`, vítima hostil ao controlador do local | −12 (fação da vítima) | — | renome +5 |

### 3.4 Dados (propostas para revisão do dono)

`data/race_attitudes.json` (trecho; `source` obrigatório):

```json
{
  "races": {
    "race_elfos": {
      "race_humanos": {"value": 1, "source": "lore_nova/races.txt:71"},
      "race_anoes_fuligem": {"value": -2, "source": "lore_nova/races.txt:73"},
      "race_cinzeus": {"value": -1, "source": "lore_nova/races.txt:75"},
      "race_vrel": {"value": -1, "source": "lore_nova/races.txt:77"},
      "race_osshari": {"value": 1, "source": "lore_nova/races.txt:79"}
    },
    "race_cinzeus": {
      "race_elfos": {"value": -1, "source": "lore_nova/races.txt:250"},
      "race_humanos": {"value": 0, "source": "lore_nova/races.txt:252"},
      "race_vrel": {"value": 1, "source": "lore_nova/races.txt:256"},
      "race_anoes_fuligem": {"value": -2, "source": "lore_nova/races.txt:258"}
    },
    "race_anoes_fuligem": {"*": {"value": 0, "source": "lore_nova/races.txt:119"}},
    "race_osshari": {"*": {"value": 0, "source": "lore_nova/races.txt:293"}},
    "race_vrel": {}
  },
  "human_cultures": {
    "nascidos_do_gelo": {"regions": ["skallgard"],
      "race_elfos": {"value": -1, "source": "lore_nova/races.txt:364"},
      "race_osshari": {"value": 1, "source": "lore_nova/races.txt:364"}},
    "devoradores_de_sol": {"regions": ["deserto_zhur"], "*": {"value": 0, "source": "lore_nova/races.txt:366"}},
    "urbanos": {"regions": ["nova_arcadia"], "*": {"value": 0, "source": "lore_nova/races.txt:368"}},
    "andarilhos": {"regions": ["pradaria_ruinas"], "*": {"value": 0, "source": "lore_nova/races.txt:370"}},
    "piratas": {"regions": ["brekmar"], "race_osshari": {"value": 1, "source": "lore_nova/races.txt:372"}}
  },
  "local_rules": [
    {"region": "skallgard", "target": "race_vrel", "value": 1, "source": "lore_nova/races.txt:197"}
  ]
}
```

Lacunas da lore (decisão D2): Vrel como observadores não têm visão escrita (proposta: 0 para todos; −1 para Anões seria inferência de `races.txt:134`, não texto); culturas humanas de regiões sem cultura descrita → 0.

`data/merchants.json` — `keeper` proposto (D4): `ferreiro_skallgard` → `{"npc_id": "npc_brynja_forja_fria"}` (grafo: `skallgard`, `comerciante_liga`, `data/graph/entities.json:1141-1150`); os outros 5 (`mercado_anel_dourado`, Botica da Fuligem, Quinquilharias da Maré, Tenda da Curandeira, Armeiro de Vaelorn) precisam de keeper curado (`name/role/race_id`) via `docs/guias/AUTORIA.md`. `rare_stock` inicial vazio até curadoria (a regra funciona sem itens).

### 3.5 Fluxo por turno

1. Router classifica rota + `social_approach`/`favor_kind`.
2. `npc_actor`: garante campos (R6/R8); se abordagem social → `social_check`/`favor_decision` (seed fixa) **antes** do LLM; monta `<ATITUDE>` + teto de conhecimento; LLM narra; Python aplica `relationship_change` via `apply_npc_delta(source="llm")`, clampa `faction_reveals`, aplica efeitos do favor.
3. Storyteller: `faction_impacts` → propostas `faction_deed` (nada aplicado).
4. `event_processor`: valida; para aceitos → `reputation.process_deeds` (fação se testemunhou; pendência se não; fama por testemunha; `reputation_changed` com `source="reputation"`).
5. `turn_finalizer`: `npc_knowledge.turn_updates` → `reputation.turn_updates` (fama por entrega, pendências entregues, `heard_deeds`, dívida vencida, avisos).

### 3.6 Invariantes de playtest (novos, `playtest/invariants.py`)

`relationship ∈ [0,10]`; `reputation ∈ [−100,100]`; `renown/infamy ∈ [0,100]`; nenhuma mudança de reputação de fação sem `reputation_changed` no mesmo turno; nenhum payload player-facing com `relationship`/`reputation` numéricos; `reputation_notices` de fação só para fação `known`.

## 4. Plano passo a passo

Cada etapa pode pousar sozinha (flag não é necessária: os efeitos ficam inertes até a etapa que os liga). Testes primeiro.

### Etapa 1 — Núcleo puro e faixas (R2–R4)
1. **Testes** (`test_spec298_reputacao_nucleo.py`): `test_npc_tier_faixas_iguais_dossie` (0..10 → mesmos rótulos de `disposition_label`); `test_faction_tier_limiares`; `test_fame_view_rotulos_e_clamp`; `test_apply_npc_delta_clamp_0_10_e_teto_turno` (LLM ±1 + motor ±1 = ±2 máx.); `test_aviso_template_sem_numero`.
2. **Implementação:** `services/reputation.py` (faixas, `apply_npc_delta`, templates); `dossiers.disposition_label` delega.
3. **Verificação:** testes do escopo + `tests/test_dossiers.py`.

### Etapa 2 — Raça e origem (R5–R9)
1. **Testes** (`test_spec298_raca_origem.py`): `test_race_id_por_nome_em_save_antigo`; `test_npc_grafo_raca_por_tag` (Albrecht → `race_humanos`); `test_npc_schema_race_id_invalido_vira_vazio`; `test_cultura_humana_por_regiao` (NPC humano de Skallgard × jogador elfo = −1); `test_regra_local_vrel_skallgard`; `test_initial_relationship_soma_e_clamp_2_8`; `test_conterraneo_mais_um`; `test_recusa_so_com_menos_dois_e_rel_ate_2`; `test_relacao_pessoal_supera_preconceito` (elfo × anão: começa 3, sobe a 3+ → `refuses` falso); `test_lint_race_attitudes_exige_source`.
2. **Implementação:** `data/race_attitudes.json`, loader+lint, `race_attitude`, `initial_relationship`, `refuses`; `race_id`/`origin_region_id` na criação (API, CLI, `character_creator`); `NPCSchema.race_id`; `agents/npc.py:571` usa `initial_relationship`.
3. **Verificação:** + `tests/test_npc_camadas.py`, `tests/test_prologue.py`, `tests/test_contracts_llm.py` (offline).

### Etapa 3 — Fação por eventos validados (R10–R13)
1. **Testes** (`test_spec298_faccao_eventos.py`): `test_direction_livre_descartada` (`"+"`, `"atacou"` → nenhum impacto); `test_sem_cues_no_world_utils`; `test_faction_deed_rejeitado_fora_de_cena`; `test_faction_deed_aceito_controlador_local`; `test_faction_deed_aceito_membro_presente`; `test_estado_so_muda_apos_aceite` (substitui o cenário da SPEC-226 R8); `test_um_impacto_por_faccao_turno`; `test_quest_completed_gera_delta_tabela`; `test_npc_killed_por_player_gera_delta`; `test_pendencia_sem_testemunha_em_modo_on`; `test_off_sem_pendencia`; `test_pendencia_expira_30_dias`; `test_reputation_changed_source_reputation_alimenta_historico` (`services/state_views.py:26-30`).
2. **Implementação:** schema, validador, `process_deeds`, remoção de `_revert_reputation`/cues; ajustar testes antigos que dependiam de cues (`tests/test_fase2.py`, `tests/test_fase34.py`) para os valores do `Literal`, sem afrouxar asserts.
3. **Verificação:** + `tests/test_fase34.py`, testes de `event_processor`/SPEC-226.

### Etapa 4 — Fama por local e reação a notícias (R14–R16)
1. **Testes** (`test_spec298_fama_local.py`): `test_feito_sem_testemunha_nao_gera_fama`; `test_feito_testemunhado_gera_fama_no_local`; `test_entrega_spec215_gera_fama_no_destino` (modo `on`); `test_fama_idempotente_por_assunto`; `test_off_so_testemunha`; `test_npc_reage_uma_vez_por_assunto`; `test_pendencia_aplicada_quando_noticia_chega_a_local_da_faccao`; `test_aviso_de_faccao_nao_emitido_quando_longe`; `test_register_deed_kind_extensivel` (tipo fictício de teste com infâmia); `test_turn_updates_replay_identico` (determinismo).
2. **Implementação:** `player_deed` em `SUBJECT_PARAMS`; `reputation.turn_updates` no finalizer; `fame_at`, `deed_known_at`, `register_deed_kind`.
3. **Verificação:** + `tests/test_npc_knowledge.py` (sem mudança de resultado nos casos existentes).

### Etapa 5 — Mercador NPC, preço e estoque (R17–R19)
1. **Testes** (`test_spec298_economia_keeper.py`): `test_keeper_criado_sem_llm_na_primeira_visita`; `test_keeper_grafo_brynja`; `test_preco_por_faixa`; `test_traço_comercio_ganancioso_barateia` (`ganancioso` −2 → ×0,94); `test_clamp_fator_075_150`; `test_venda_amistoso_paga_mais`; `test_rare_stock_so_leal`; `test_keeper_hostil_esconde_raro`; `test_recusa_comercio_codigo`; `test_preco_sem_keeper_inalterado` (saves/mercadores sem `keeper` = comportamento atual).
2. **Implementação:** `merchants.json` (`keeper`, `rare_stock`), `economy.py`, lint.
3. **Verificação:** + `tests/test_remediacao_comerciante_real.py` e testes de economia existentes.

### Etapa 6 — Abordagens sociais, informação e favores (R20–R24)
1. **Testes** (`test_spec298_social.py`): `test_router_social_approach_invalido_vira_conversar`; `test_intimidar_usa_trait_e_infamia_no_dc`; `test_intimidar_seed_deterministica`; `test_intimidar_sucesso_eleva_revelacao_e_custa_relacao`; `test_sondar_sucesso_revela_um_traco`; `test_sondar_falha_sem_efeito`; `test_reveal_clamp_por_faixa`; `test_teto_linhas_conhecimento_por_faixa`; `test_favor_esconder_grava_shelter`; `test_favor_emprestar_e_divida_vencida`; `test_pagar_divida_debita_com_clamp_gold`; `test_interceder_reduz_proximo_delta_negativo`; `test_cooldown_favor_3_dias`; `test_favor_recusado_por_raca`; `test_guard_fallbackllm_router_e_npc` (FallbackLLM → `conversar`, sem efeito).
2. **Implementação:** `RouterDecision`, `social_check`, `favor_decision`, integração no `npc_actor` antes do LLM.
3. **Verificação:** + testes do router e do `npc_actor`.

### Etapa 7 — Atitude no prompt e fama no narrador (R25)
1. **Testes**: `test_prompt_npc_tem_atitude_sem_numero`; `test_prompt_storyteller_fama_so_se_conhecida`; `test_atitude_cita_motivo_raca_quando_aplicavel`.
2. **Implementação:** blocos de prompt.
3. **Verificação:** + `tests/test_prompt_guard.py`, `tests/test_prompt_injection_corpus.py`.

### Etapa 8 — Visibilidade e avisos (R26–R27)
1. **Testes** (`test_spec298_visibilidade.py`): `test_payloads_sem_relationship_reputation` (oráculo sobre `/game/state`, `/game/action`, dossiês, Codex); `test_avisos_regras_de_emissao`; `test_avisos_passam_por_conceal_for`; `test_recent_changes_max_3`. Front: e2e com fixtures atualizadas (rótulo no lugar de corações/sparkline).
2. **Implementação:** API, dossiês, `visible_npc_view`, `web/`.
3. **Verificação:** testes do escopo; `cd web && npm run build` e `npm run test:e2e` dos specs tocados.

### Etapa 9 — Migração, invariantes e smoke
1. **Testes** (`test_spec298_migracao.py`): `test_save_antigo_carrega_com_defaults_neutros`; `test_ensure_idempotente`; `test_npc_existente_nao_recalcula_relacao`; playtest MockLLM 50 turnos, 14 perfis, sem violação nova (§3.6).
2. **Implementação:** `ensure_reputation_fields` no load; invariantes.
3. **Verificação:** suíte completa 1× no pouso (coordenador); smoke §6.

## 5. Critérios de aceite

- [x] R1–R28 cobertos por teste nomeado no §4
- [x] Nenhuma ocorrência de `_POS_CUES`/`_NEG_CUES`/`_direction_sign` no código de produto
- [x] Reputação de fação só muda com `reputation_changed` aceito no mesmo turno (invariante de playtest)
- [x] Fama nunca cresce num local sem testemunha registrada ou entrega SPEC-215 (teste dos dois modos)
- [x] `trait_dc_modifier` consumido em `comercio`, `intimidacao`, `insight` e `persuasao` (favores)
- [x] Nenhum payload player-facing com `relationship`/`reputation` numéricos (oráculo)
- [x] `data/race_attitudes.json` revisado pelo dono, com `source` em toda entrada ≠ 0
- [x] Keepers dos 6 mercadores curados (ou decisão explícita de manter só os ligados)
- [x] Guard de FallbackLLM em `RouterDecision`, `NPCResponse`/`NPCSchema`, `StoryUpdate` alterados (try/except ou isinstance)
- [x] Saves antigos continuam carregando (sem bump; defaults neutros)
- [x] Playtest MockLLM 14 perfis × 50 turnos sem violação `error` nova; letalidade da SPEC-285 inalterada (sem mudança de combate)
- [ ] `uv run pytest` verde (suíte completa offline) e build/e2e do `web/` verdes
- [ ] Revisão independente (`handoffs/SPEC-298-review.md`)
- [ ] Smoke real §6 executado e registrado

## 6. Smoke test com LLM real

Rotas reais (DeepSeek primário), dentro do teto da VISAO § Processo (US$ 3/dia; estimativa < US$ 0,10). `RPG_NPC_KNOWLEDGE=on`. Save novo: jogador **Elfo** de `floresta_sussurros`.

1. **NPC anão / Cinzéu** (2 requests): falar com um NPC do grafo com tag de raça hostil à do jogador → conferir no save `relationship_basis.race = −2`, `relationship` inicial 3, e a fala do NPC refletindo desconfiança (bloco `<ATITUDE>` chegou). Verifica `NPCSchema.race_id` no provider real.
2. **Intimidação** (1 request): "Eu o encosto na parede e exijo que fale da Legião." → `social_approach="intimidar"` vindo do router real (mapeamento do `Literal`), resultado do `general_test` no trace, relação −1, aviso "… não gostou disso."
3. **Feito para fação** (1 request): ação clara a favor da fação que controla o local → `faction_impacts` com `direction`/`magnitude` válidos no provider real (function_calling), `faction_deed` aceito, `reputation_changed source=reputation`, aviso de fação.
4. **Mercador** (1 request): Skallgard → loja → preço de Brynja coerente com a faixa; `/game/state` sem números.
5. **Fama propagada** (opcional, MockLLM é suficiente para a mecânica): viajar 1 dia e conferir `location_fame` no destino só após entrega.

Registrar custo, provider, modelo e resultado em `handoffs/SPEC-298-smoke.md`.

## 7. Riscos & compatibilidade

- **Saves antigos:** campos aditivos com default neutro; NPCs existentes mantêm a relação; facções idem. Reputações já acumuladas por palavra-chave ficam como estão (não há como reconstruir a causa).
- **Contrato de API:** remover `relationship`/`reputation`/`history[].value` quebra fixtures e2e (`web/e2e/fixtures.ts:43`, `dossiers.spec.ts:31`, `critical-journeys.spec.ts:993,1008`) e qualquer consumidor externo. Verificar se algum adapter de eval lê esses campos **da API** (os de `evals/core/adapters.py` leem o estado); se ler, é follow-up com relock, não mudança aqui.
- **SPEC-215 `off` em prod:** com `off`, fama só por testemunha direta e fação só muda com presença. É o comportamento correto pela regra de ouro, mas reduz a percepção de reputação até a SPEC-296 ligar `on`.
- **MockLLM:** devolve `social_approach=None`/`magnitude="menor"`; os caminhos novos ficam cobertos por testes unitários que injetam a decisão. O mapeamento real só se prova no §6.
- **FallbackLLM:** router/npc/storyteller já têm guard; campos novos têm default e validador `mode="before"` que nunca derruba a resposta (padrão SPEC-045).
- **Quota/latência:** zero chamada LLM nova (abordagem social vem no mesmo `RouterDecision`; keeper sem LLM). Custo de prompt: +1 bloco curto no `npc_actor` e 1 linha no storyteller. `reputation.turn_updates` é O(links do turno).
- **Economia:** fator combinado limitado a 0,75..1,50 para não quebrar o balanço de ouro; `[BALANCEAR]` via playtest.
- **Integridade de eval:** nada em `evals/` protegido muda; o tipo `player_deed` é novo e não aparece nos datasets `npc_knowledge`.
- **Escopo grande:** 9 etapas independentes; se o dono preferir, as etapas 5–6 (economia/social/favores) podem virar spec irmã sem mudar as interfaces (D1).

## 8. Decisões pendentes do dono (antes de `approved`)

- **D1 — Tamanho.** Uma spec com 9 etapas (proposta) ou separar economia/social/favores (etapas 5–6) numa spec irmã.
- **D2 — Tabela de raças (§3.4).** Aprovar os valores e as lacunas: Vrel observadores = 0; Anões = 0 para todos ("sem hostilidade", `races.txt:119`); Elfo×Anão e Cinzéu×Anão = −2 (únicas recusas possíveis).
- **D3 — Pesos (`DEED_TABLE`, preço por faixa, empréstimo 50, TTL 30 dias).** Aceitar os defaults `[BALANCEAR]` e calibrar no playtest, ou fixar outros.
- **D4 — Keepers dos mercadores.** Brynja Forja-fria para a Forja dos Clãs; quem cuida dos outros 5 (curadoria nova via AUTORIA) e se entram `rare_stock` já nesta spec.
- **D5 — Virtudes dos testes.** Intimidar = `forca`, sondar = `mente` (proposta); alternativa: intimidar = maior entre `forca` e `carisma`.
- **D6 — HUD.** Remover corações e sparkline (proposta, decisão 7 da VISAO) ou manter um ícone de rótulo sem escala.


## Decisões do dono (2026-10-23)

Todas as decisões abertas desta spec seguem o **default recomendado pelo autor**, exceto/explicitando:

- D6: sim — UI só com rótulos e avisos; remover corações, sparkline e '+N reputação'.
- D8 (vinda da SPEC-301): separar os dois sentidos de `disposition` fica nesta spec.


## Entrega (implementação, 2026-10-23)

Etapas 1-9 implementadas em `services/reputation.py` (dono único). Desvios e escolhas:

- **D8** — `factions[*].disposition` (hostil/neutro/aliado) segue interna (economia/rule_engine); a superfície usa `standing_label` (faixa de fação) e `attitude_label` (NPC). `disposition_label`/`relationship`/`reputation`/`history` saíram dos payloads (API, dossiês, web).
- **R23 teto de linhas de conhecimento** só vale para NPC com `relationship_basis` preenchido (NPC criado pelo motor após esta spec). NPC legado/fixture mantém o teto 8: aplicar a todos quebraria o dataset de regressão `npc_knowledge` (protegido). Follow-up de eval com relock (EVAL_AUTHORING_REQUIRED).
- **Keepers**: 5 dos 6 mercadores têm keeper curado com nomes provisórios (revisão do dono); `rare_stock` vazio.
- `faction_deed` só é aceito com `source="storyteller"` (proposta livre do LLM é rejeitada); `FactionImpact` inválido é descartado antes da validação Pydantic.
- Tabela de raças usada verbatim da §3.4 (Anão como observador = 0): o exemplo do §6.1 (NPC anão/Cinzéu × jogador elfo = −2) não bate com a tabela; a recusa −2 ocorre com NPC Elfo/Cinzéu × jogador Anão. Ajustar o roteiro do smoke.
- Exibição dos avisos no chat (toast) não implementada; eles saem em `reputation_notices` e alimentam `recent_changes` no HUD/dossiês.
