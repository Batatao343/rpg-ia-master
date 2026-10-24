# SPEC-301 — Fações com patente: entrar, subir, sair, trair (e mover o mundo)

> **Status:** `in-progress` (implementada; falta revisão independente e smoke real da §6)
> **Criada:** 2026-10-20 · **Atualizada:** 2026-10-20
> **Depende de:** SPEC-296 (Onda 0: `world.news` e bloco de ambiente no prompt), SPEC-298
> (reputação por fação com rótulo vago e API de delta). Integra **se estiverem `done`**, sem
> depender: SPEC-215 (propagação de notícias), SPEC-299 (lei/notoriedade por região).
> **Desbloqueia:** SPEC-302 (o motor de mundo consome `Faction.influence` e o quadro de membros;
> relações fação-fação passam a viver lá).
> **Origem:** `docs/mundo-vivo/VISAO.md` § "C. Sociedade viva" (linhas 104-106), Regra de ouro
> (79-82), "A. Mundo autônomo" (146-155) e Restrições permanentes (214-220).

---

## 1. Contexto & Objetivo

Hoje as 19 fações de `data/factions.json` são relógios lineares sem contra-jogo:
`advance_factions` soma `pace * periods` ao `progress` e conclui em 100
(`world_utils.py:351-380`). O jogador só toca na fação por um delta fixo de reputação de ±12
decidido pelo LLM (`world_utils.py:518-578`, chamado em `agents/storyteller.py:1103-1133`).
Não há como entrar numa fação, receber ordens, ganhar posto, equipamento ou serviço, nem
desacelerar um rival. A auditoria registra isso como "só progresso linear… o jogador não tem
contra-jogo" (`docs/mundo-vivo/VISAO.md:14-16`).

O dono decidiu (VISAO.md:104-106) que o jogador **pode entrar, subir de patente, sair ou
trair**, e que **só as fações que fazem sentido na lore aceitam membros**. A classificação
das 19 está na §3.2, para revisão. As ações do jogador como membro (missões) e como agente
livre (ajudar/prejudicar) passam a mover o `progress` da fação e o dos rivais.

Esta spec segue a regra "mecânica é Python": o LLM no máximo **propõe** a intenção
("quero me alistar", "peço uma missão", "saio da Legião") e **narra**. Requisitos, patente,
mérito, perks, missão, efeito no progresso e traição são resolvidos por código determinístico
(seed por `game_id`), validados e registrados no `event_log`. Também vale a Regra de ouro: os
rivais só passam a odiar o jogador **depois de saberem** (testemunho ou notícia), nunca por
onisciência.

## 2. Requisitos

### Dados e classificação

- **R1 — Catálogo curado.** O arquivo novo `data/faction_membership.json` tem **exatamente**
  uma entrada por id de `data/factions.json` (19). Cada entrada tem `accepts ∈ {"sim",
  "condicional", "nao"}` e, quando aceita, `ranks` (3 a 5, em ordem), `requirements`,
  `exit_policy`, `rivals`, `exclusive_with`, `secret`, `hq_location_ids`, `recruiter_npc_ids`,
  `perks_by_rank` e `mission_templates` (≥ 3: ≥ 2 `apoio` e ≥ 1 `sabotagem`). Um lint
  (`scripts/validate_content.py`) falha se aparecer id de local fora de `data/world_map.json`,
  NPC fora de `data/graph/entities.json`, item fora de `data/artifacts.json`, rival que não é
  fação, ou fação `nao` com `ranks`.
- **R2 — Fação `nao` nunca aceita membro.** `can_join` devolve `(False, "fechada")` para
  qualquer id com `accepts="nao"`, seja qual for a ficha ou a reputação. O trato com essas
  fações continua só por reputação (SPEC-298).

### Entrar

- **R3 — Requisitos determinísticos.** `can_join(state, fid)` checa, nesta ordem, e devolve o
  primeiro motivo de recusa de um enum fechado: `fechada`, `ja_membro`, `traidor_recente`
  (cooldown), `limite_membros`, `exclusiva:<fid>`, `raca`, `classe`, `origem`, `reputacao`,
  `procurado` (só se a SPEC-299 estiver ativa), `local` (não está num `hq_location_ids` nem
  com um `recruiter_npc_ids` presente), `rito_pendente`. Com tudo cumprido, devolve
  `(True, "")`.
- **R4 — Rito de entrada.** A fação com `requirements.entry_rite` não registra membro
  direto. Primeiro gera uma missão de rito (R11, `kind="rito"`). A entrada só se efetiva quando
  essa missão é concluída (prova via `quest_log.has_completion_proof`). Ritos com custo
  mecânico (ex.: Batismo de Fogo = 1 Ferimento leve + marca `cicatriz_labios`) são aplicados
  por Python na conclusão.
- **R5 — Limite e exclusividade.** No máximo `MAX_MEMBERSHIPS = 2` vínculos ativos. Entrar
  numa fação listada em `exclusive_with` de um vínculo ativo é recusado com
  `exclusiva:<fid>`. Fação `secret=true` não conta para exclusividade aos olhos de quem não
  sabe do vínculo (é o espião duplo), mas conta para o limite.
- **R6 — Entrar é canônico e auditável.** A entrada efetiva emite um único evento
  `faction_membership_changed` (`action="joined"`, `rank_id` = primeira patente,
  `source="engine"`). O evento passa pelo pipeline de `event_processor` e vira milestone da
  crônica. Também marca `faction_intel[fid].known=True` e `knows_goal=True`: quem entrou
  sabe a que fação pertence.

### Subir de patente

- **R7 — Mérito e promoção.** Cada missão concluída da fação soma mérito
  (`apoio`/`rito`: +tier; `sabotagem`: +tier+1). A patente sobe quando o mérito alcança o
  `merit` da próxima patente e `player.level >= min_level` dela. Sobe no máximo **1 patente
  por evento**. A promoção emite `faction_membership_changed` (`action="promoted"`). A
  patente nunca cai, exceto por expulsão ou traição (R14/R15).
- **R8 — Teto de patente.** A última patente da tabela nunca é a de líder (Thrace, Víbora,
  Vehkr…): o jogador não substitui um NPC-chave. Condição autorada `rank_cap` por
  raça/classe (ex.: não-Sangromante para no posto 2 no Poder de Kahen). O mérito acima do teto
  é ignorado.

### Benefícios (acesso, equipamento, serviços)

- **R9 — Perks de enum fechado.** `perks_by_rank` só aceita os tipos `desconto`
  (multiplicador ≤ 1.0 nos mercadores da fação e no intendente), `intendente` (itens
  liberados por patente), `abrigo` (descanso no QG não sorteia encontro, mesmo fora do
  early-game), `informacao` (1×/dia de jogo revela o nível `objetivo` de um rival via
  `apply_faction_reveal`), `passagem` (local controlado pela própria fação deixa de contar
  como "dominado por fação hostil" em `check_encounter`) e `intercessao` (reduz a
  notoriedade na região da fação; **no-op** se a SPEC-299 não estiver `done`). Tipo
  desconhecido é erro de lint.
- **R10 — Intendente.** No QG da fação, `faction_quartermaster_stock(state, location_id)`
  devolve os itens com `min_rank <= patente atual`, ao preço de `economy.price` × desconto.
  A compra usa o fluxo SHOP existente (`agents/loot.py`): mesmo validador de ouro e mesmo
  clamp (`economy.clamp_gold`). Item único continua único por mundo (`is_unique_available`).

### Missões

- **R11 — Missões geradas pelo motor.** `offer_mission(state, fid)` escolhe um
  `mission_template` com `min_rank <= patente` e seed
  `f"{game_id}:{fid}:{turn_count}"`, resolve o `location_id` entre os candidatos do template
  que estão no mapa e cria uma `Quest` com os campos novos `faction_id`, `mission_kind ∈
  {"apoio","sabotagem","rito"}`, `mission_tier ∈ {1,2,3}` e `target_faction_id` (só em
  `sabotagem`). Título e descrição vêm do template (texto autorado). O LLM **não** inventa
  missão de fação. Há no máximo 1 missão ativa por fação, e ela respeita
  `quest_log.MAX_ACTIVE_QUESTS`.
- **R12 — Conclusão pelo pipeline atual.** Missão de fação conclui pelo mesmo
  `quest_completed` com prova (`world_validators.PROOF_REQUIRED_TYPES`,
  `quest_log.has_completion_proof`). Na conclusão, o `event_processor` chama
  `faction_membership.on_mission_completed`, que aplica mérito (R7), contra-jogo (R13) e
  recompensa em ouro por tier (`MISSION_GOLD = {1: 20, 2: 35, 3: 50}`, no lugar do
  `QUEST_REWARD_GOLD` fixo **só** para quests com `faction_id`).
  Missão `failed` (`fail_orphan_quests`) tira 1 de mérito (piso 0) e não rebaixa patente.

### Contra-jogo (o mundo sente o jogador)

- **R13 — Progresso e ritmo.** Ao concluir uma missão:
  - `apoio`/`rito` dão `+MISSION_PROGRESS[tier]` (3/5/8) ao `progress` da própria fação e
    `+MISSION_INFLUENCE[tier]` (2/3/4) à `influence` dela;
  - `sabotagem` dá `−MISSION_PROGRESS[tier]` ao `progress` da `target_faction_id` (piso 0) e
    `−MISSION_INFLUENCE[tier]` à `influence` dela.

  O `progress` empurrado por missão **satura em 99**: a ascensão só acontece no tick de tempo
  (`advance_factions` → `resolve_faction_completions`), que continua sendo o único caminho de
  ascensão.
- **R14 — Pace efetivo.** Campo novo `Faction.influence: int` (default 0, clamp
  `[-INFLUENCE_MAX, +INFLUENCE_MAX]` = ±9). `advance_factions` passa a usar
  `pace_efetivo = max(0, pace + influence // 3)` (variação de −3 a +3). A influência decai 1
  em direção a 0 a cada `INFLUENCE_DECAY_PERIODS = 4` períodos avançados, com um acumulador
  em `Faction.influence_periods`. **Com `influence == 0` o resultado é idêntico ao de
  hoje**: os testes de `tests/test_fase2.py` seguem verdes sem edição.
- **R15 — Agente livre também conta.** Cada `reputation_changed` aplicado
  (`storyteller.py:1119`) também move a `influence` da fação em ±1 (ajudou/prejudicou). Já
  existe o limite de 1 por fação por turno (SPEC-226 R8). Se a proposta for rejeitada
  (`_revert_reputation`, `event_processor.py:290-315`), a influência também é desfeita.

### Rivais, saída e traição

- **R16 — Rivais odeiam ao saber.** Entrar ou ser promovido em fação **pública**
  (`secret=false`) gera uma `rival_awareness` pendente para cada fid em `rivals`. Ela é
  aplicada (delta −1 passo de reputação, via API da SPEC-298, em cada rival) **só quando** o
  rival fica sabendo: (a) o jogador chega a um local da região-base do rival ou controlado por
  ele; ou (b) a SPEC-215 está `on` e o evento `faction_membership_changed` chegou a um NPC
  daquela fação. Em fação `secret=true`, a pendência só nasce quando o vínculo é **exposto**
  (R18). Aplicada uma vez, a pendência é consumida (idempotente).
- **R17 — Sair.** `leave(state, fid)` encerra o vínculo conforme `exit_policy`:
  - `livre`: −1 passo de reputação com a fação;
  - `desonra`: −2 passos e `cooldown_days = 10` para voltar;
  - `traicao`: vale como R18 (ex.: "ninguém sai da Mão").

  Emite `faction_membership_changed` (`action="left"`). Mérito zera. A patente fica só no
  histórico.
- **R18 — Traição telegrafada.** Enquanto membro, um `reputation_changed` com direção
  `prejudicou` contra a **própria** fação ou a conclusão de uma `sabotagem` contra ela muda
  o status para `suspeito` e injeta um aviso narrável ("Seus superiores andam calados
  com você"). Uma 2ª ofensa em até `SUSPICION_WINDOW_DAYS = 5` dias de jogo **ou** entrar numa
  fação de `exclusive_with` confirma a traição. O vínculo vira `traidor`, a reputação com a
  fação cai para o limiar hostil (`_HOSTIL_AT`, `world_utils.py:520`), o
  `cooldown_days` é 30, nasce `rival_awareness` positiva (+1 passo) para os rivais da fação
  traída, e `faction_membership_changed` (`action="betrayed"`) é emitido. Exposição (R16):
  trair uma fação secreta expõe o vínculo a ela.
- **R19 — Fação destruída ou ascendida.** Se a fação do jogador for `defeated`
  (`resolve_faction_completions`, ramo `eliminar_faccao`, `world_utils.py:450-453`), o vínculo
  vira `dissolvida`, com evento `action="dissolved"` e nota narrável. Se ela ascender, a nota
  `[MUNDO MUDA]` ganha uma linha `[FAÇÃO]` para o membro (ele sabe o nome porque entrou).

### LLM, prompt e não-onisciência

- **R20 — Intenção proposta, nunca decidida.** `StoryUpdate` (`agents/storyteller.py:50`) e
  o modelo de resposta do `npc_actor` ganham `membership_action: MembershipAction | None`
  (`action ∈ {"join","leave","ask_mission"}`, `faction_id`). Python valida por
  `faction_membership.apply_intent`. Id fora da lista, fação `nao` ou requisito não cumprido
  viram uma nota narrável da recusa (motivo do enum de R3, sem números) e não mudam o estado.
  O guard do FallbackLLM vale para todo acesso ao campo (`getattr`/`isinstance`). Com payload
  em quarentena (`quarantine_llm_payload`), o campo é ignorado.
- **R21 — Bloco no prompt.** Com vínculo ativo, o storyteller e o `npc_actor` recebem
  `<FAÇÃO_DO_JOGADOR>`: nome da fação, nome da patente, status (`ativo|suspeito`), missão
  ativa (título e descrição) e perks em texto. **Sem números de mérito ou de influência.**
  Fação conhecida mas sem vínculo não ganha bloco novo.
- **R22 — View sem números.** `_factions_block` (`api.py:2517-2562`) ganha
  `membership: {status, rank_name, standing_label, perks: [str], active_mission_id}` só para
  fação com vínculo (ativo ou histórico). `standing_label` é vago, de um enum fechado
  ("recém-chegado", "visto com bons olhos", "a liderança nota seu trabalho", "sob suspeita",
  "expulso", "traidor"). Mérito, influência e `rival_awareness` **nunca** saem pela API.

### Persistência e migração

- **R23 — Migração suave.** Campos novos no `GameState`: `faction_membership: dict[str,
  MembershipRecord]` (default `{}`); `Faction.influence`/`influence_periods` (default 0
  por `ensure_factions`, `world_utils.py:335-348`); campos opcionais em `Quest`. Save antigo
  carrega sem bump de schema, e a primeira viagem/descanso depois do load se comporta como
  hoje (influence 0).
- **R24 — Round-trip.** `save_game_state` → `load_game_state` preserva
  `faction_membership`, `influence`, `influence_periods` e os campos novos de `Quest`, sem
  diferença.

### Fora de escopo

- Relações **fação ↔ fação** (guerra, aliança, troca de lado), estabilidade dinâmica e o
  tick diário do mundo: **SPEC-302**. Aqui os rivais são uma lista estática curada (`rivals`)
  e servem só à hostilidade contra o jogador e ao alvo de `sabotagem`.
- O modelo de reputação, os rótulos vagos de NPC/fação/local/raça e a remoção do número de
  reputação de `api.py:2556`: **SPEC-298**. Esta spec só chama a API de delta dela.
- Caçadores de recompensa, preço pela cabeça e multa: **SPEC-299** (aqui só o hook
  `intercessao` e o requisito `procurado`, ambos no-op sem a 299).
- Prazo em quest (missão com relógio). Missão de fação não expira nesta spec.
- Companheiros que reagem à fação do jogador (SPEC-300).
- Fações do grafo fora das 19 (`clas_tecnologicos`, `encapuzados_fornalha`,
  `resistencia_operaria_martelos_partidos`, `quadrilha_telhados`, `casa_mares_dominio_lyss`,
  `tres_sindicatos_comercio`, `guilda_corvos`, `cultos_despertar_dispersos`,
  `mercadores_curiosidades`): elas não estão em `data/factions.json` e não têm relógio.
  Integrá-las é outra spec.
- Itens novos em `data/artifacts.json`. O intendente usa só ids existentes.
- Bloqueio de entrada em locais por patente (ex.: sala restrita do QG).
- Tela nova no frontend. A UI só renderiza o campo `membership` do bloco de fações (Etapa 8,
  componente existente).
- Long-run de playtest: só o perfil novo em MockLLM (Etapa 9) e o smoke curto da §6.

## 3. Design técnico

### 3.1 Arquivos

**Novos**
- `data/faction_membership.json`: catálogo curado (R1). É lido em runtime e **não** é copiado
  para o save; o save guarda só o estado do jogador.
- `services/faction_membership.py`: núcleo puro. Contém `load_catalog`, `can_join`,
  `apply_intent`, `join`, `leave`, `register_offense`, `on_mission_completed`,
  `on_mission_failed`, `apply_rival_awareness`, `on_faction_defeated`, `perks_for`,
  `membership_view`, `prompt_block`.
- `services/faction_missions.py`: `offer_mission`, `mission_quest_from_template`.
- `tests/test_spec301_*.py`: um arquivo por etapa (§4).

**Alterados**
- `state.py`:
  - `MembershipRecord`;
  - `Faction.influence` e `influence_periods`;
  - `Quest.faction_id`, `mission_kind`, `mission_tier`, `target_faction_id`;
  - `GameState.faction_membership`.
- `world_utils.py`:
  - `ensure_factions` faz backfill de `influence`/`influence_periods`;
  - `advance_factions` usa o pace efetivo, a decadência e o retorno de eventos inalterado (R14);
  - `_hostile_ruler` aceita `membership` opcional (perk `passagem`);
  - `recovery_rest_safe` ou o ponto de chamada em `storyteller` consulta o perk `abrigo`.
- `agents/storyteller.py`:
  - campo `membership_action` no `StoryUpdate`;
  - chamada de `apply_intent`;
  - `influence ±1` junto de `apply_reputation` (R15);
  - `apply_rival_awareness` na chegada de viagem (junto de `advance_factions`, linhas
    538-543);
  - bloco `<FAÇÃO_DO_JOGADOR>`;
  - linha `[FAÇÃO]` na ascensão.
- `agents/npc.py`: `membership_action` no modelo de resposta, com recrutador presente
  (R3 `local`), e bloco no prompt.
- `services/event_processor.py`:
  - hook de conclusão/falha de missão de fação (perto de `event_processor.py:408-420`);
  - reversão da influência junto de `_revert_reputation`.
- `services/world_validators.py`: `_v_faction_membership_changed` no `_VALIDATORS`
  (`world_validators.py:467-483`). Aceita só `source="engine"`, `target_id` fação existente e
  `action` do enum; LLM nunca propõe este tipo.
- `services/chronicle.py`: template de milestone para `faction_membership_changed`.
- `services/economy.py`: `faction_quartermaster_stock` e desconto por patente em `price`
  (parâmetro opcional; sem vínculo, preço idêntico).
- `services/quest_log.py`: `MISSION_GOLD`; `complete_quest_with_reward` usa o ouro por tier
  quando há `faction_id`.
- `services/npc_knowledge.py`: inclui `faction_membership_changed` em `SUBJECT_PARAMS` só
  para fação pública (R16b). Só tem efeito com `RPG_NPC_KNOWLEDGE=on`.
- `api.py`: `membership` no `_factions_block` (R22).
- `scripts/validate_content.py`: lint de R1.
- `playtest/invariants.py` e `playtest/profiles.py`: perfil e invariantes (Etapa 9).
- `web/src/components/CodexTab.tsx` (ou o painel que já renderiza fações): exibe
  `rank_name`/`standing_label`/perks como texto.

### 3.2 Classificação das 19 fações (para revisão do dono)

Legenda de `accepts`: **sim** = aceita forasteiro que cumpre requisitos; **condicional** =
aceita só por um caminho específico (raça, conversão, rito ou traição); **não** = não aceita
membro (trato só por reputação). As patentes vão da entrada ao teto. A última **não** é o
cargo do líder (R8).

| # | id | Aceita? | Requisitos de entrada (proposta) | Patentes (proposta) | Rivais ao entrar | Justificativa (lore) |
|---|---|---|---|---|---|---|
| 1 | `legiao_ferro` | **sim** | reputação ≥ neutro; não procurado em Nova Arcádia (SPEC-299); classe arcana (Arcanista Cinzento, Sangromante, Corruptor) paga **registro** de 50 ouro (rito `registro_arcano`); QG `na_anel_ferro`; recrutador `npc_comandante_thrace` | Recruta → Legionário → Sargento → Tenente → Comandante de Batalhão | `filhos_chama_azul`, `mao_sombria` | "Hierarquia rígida… quotas" (`data/codex/factions/legiao_ferro.md:21-23`); patentes citadas na lore: "Comandante de Batalhão Ress", "Tenente Warda" (`lore_nova/faction_perspectives.txt:9,25`); caça "magos não registrados" (`legiao_ferro.md:23`); inimiga dos Filhos (`data/graph/edges.json:94-97`). `exit_policy=desonra` (Korvus desertor é foragido, `legiao_ferro.md:29`). |
| 2 | `mao_sombria` | **sim** (secreta) | reputação ≥ +1 passo; ter ouvido falar dela (`intel.known`); QG `na_anel_lama`; recrutadores `npc_rato_de_ferro_tibb`, `npc_pardal` (Magda nunca recruta) | Olheiro → Mula → Agente → Líder de célula | `legiao_ferro` (só ao expor) | Rede com Pardal como olhos e Tibb no contrabando (`mao_sombria.md:27`); "líderes de célula" (`faction_perspectives.txt:73`); ninguém de nível médio sabe quem é a Víbora (`mao_sombria.md:31`), daí o teto. `secret=true`; `exit_policy=traicao`. |
| 3 | `filhos_chama_azul` | **condicional** (rito) | rito **Batismo de Fogo** (1 Ferimento leve + marca `cicatriz_labios`, visível à Legião); QG `na_anel_lama`; sem recrutador no grafo (entrada por QG) | Simpatizante → Batizado → Brasa → Pregador | `legiao_ferro`, `mao_sombria` | "O Batismo de Fogo… quem não aguenta não entra" (`filhos_chama_azul.md:23`); "alto membro do culto" (`faction_perspectives.txt:41`); a Mão os evita (`faction_perspectives.txt:97`). Fação vilã (disposition `hostil`, `data/factions.json:42`). `secret=true` até ser batizado. |
| 4 | `clas_combate` | **sim** | rito **de passagem** (missão de caça no Ermo); origem `skallgard` dispensa o rito; QG `skallgard`; recrutadores `npc_vehkr_punho_de_gelo`, `npc_aslaug_duas_lancas` | Aspirante → Caçador → Caçador de Expedição → Voz do Clã | `renegados_ermo` | "Caçam no Ermo… enfrentam o rito de passagem" (`clas_combate.md:25`); Aslaug é "a promessa" (`clas_combate.md:23`). O rival principal (Clãs Tecnológicos) está fora das 19 (fora de escopo). |
| 5 | `renegados_ermo` | **condicional** | exilado/descartado: ter traído ou deixado com desonra os `clas_combate`, **ou** notoriedade em Skallgard (SPEC-299), **ou** reputação ≥ aliado com a fação; recrutador `npc_korrin_sem_cla` | Desgarrado → Batedor do Branco → Lâmina de Korrin | `clas_combate` | "Nascidos do Gelo exilados, desertores… produtos do rito que deu errado" (`renegados_ermo.md:21`); Korrin quer oferecer o que sabe aos caçadores (`renegados_ermo.md:27`). |
| 6 | `bandos_orc_saidas_baixas` | **não** | — (trato por reputação/pedágio) | — | — | Refugiados orcs do Reino; Gruumsha "pode negociar passagem ou aliança"; "trair um acordo é virar troféu" (`bandos_orc_saidas_baixas.md:21-27`). Aliança, não filiação de forasteiro. |
| 7 | `goblins_mineiros` | **não** | — | — | — | Skriit "negocia informação e passagem — traiçoeiramente" (`goblins_mineiros.md:27`). Sociedade de túnel fechada a forasteiros. |
| 8 | `ultimos_anoes_reino` | **sim** (contratado) | reputação ≥ neutro; QG `ma_forja_profunda`; recrutador `npc_durgrim_ultimo_martelo` | Contratado → Guia das Profundezas → Guardião dos Registros | `goblins_mineiros` | "Precisam de aventureiros que desçam onde eles não podem mais" (`ultimos_anoes_reino.md:25`); a ascensão deles elimina os Goblins (`data/factions.json:126-129`). |
| 9 | `druidas_ciclo_cinzento` | **sim** | reputação ≥ neutro; nunca ter sido membro dos `druidas_renegados`; QG `pantano_melancolia`; recrutadores `npc_arcante_gresh`, `npc_nilo_folha_nova` | Aprendiz → Irmão do Ciclo → Druida → Druida Sênior | `druidas_renegados` | Há "aprendiz" e "druida sênior" na lore (`faction_perspectives.txt:107,125`); fazem o chá e tratam infectados (`druidas_ciclo_cinzento.md:25`), daí os perks `abrigo` e `intendente` com `erva_amarga`/`musgo_cinzento`; inimigos dos Renegados (`edges.json:388-391`). |
| 10 | `druidas_renegados` | **condicional** (conversão) | só por **traição ao Ciclo** (R18) **ou** ter "ouvido demais" (≥ 3 conversas com `npc_saelwen_a_que_afundou`); QG `pm_profundezas` | Ouvinte → Afundado → Jardineiro de Tumores | `druidas_ciclo_cinzento` | "Ex-membros do Ciclo… convertidos pela melancolia" (`druidas_renegados.md:21`); "ouvi-los demais é começar a concordar" (`druidas_renegados.md:27`). |
| 11 | `tribos_devoradores_sol` | **não** | — | — | — | Forasteiro é "recurso (água, memórias), não inimigo" e "não negociam como humanos comuns" (`tribos_devoradores_sol.md:25`; `faction_perspectives.txt:305`). Ver decisão D3 (origem Zhur). |
| 12 | `colmeia_hospedeiros` | **não** | — | — | — | "Não se entra na colmeia querendo. A colmeia entra em você" (`faction_perspectives.txt:323`); "avaliam forasteiros antes de acolher ou repelir" (`colmeia_hospedeiros.md:24`). Acolhimento fica na reputação. |
| 13 | `cultistas_destilacao` | **condicional** (magos) | classe arcana (Arcanista Cinzento, Sangromante, Corruptor); QG `ae_ruinas_submersas`; recrutador `npc_corvane_o_mestre_destilador` | Coletor → Acólito-Destilador → Destilador | `cidades_estado_sobreviventes_vaelorn_solvhen` (D5) | "Magos atraídos às ruínas em busca de reaprender a Destilação" (`cultistas_destilacao.md:21`); capturam pessoas como matéria-prima (`cultistas_destilacao.md:25`). Fação vilã. |
| 14 | `poder_kahen` | **sim** (teto por classe) | reputação ≥ +1 passo; QG `brekmar`; recrutador `npc_veu_de_sangue`; `rank_cap` 2 para quem não é Sangromante | Agente do Poço → Executor → Sangue-Leal | `grupos_piratas_rivais` | "Comanda através de poucos sangrinomantes leais. Véu-de-Sangue é seu tenente executor" (`poder_kahen.md:23`); lê o Poço das Dívidas (`poder_kahen.md:25`). |
| 15 | `grupos_piratas_rivais` | **sim** | reputação ≥ neutro; QG `brekmar` (Boca do Fundo); recrutadora `npc_capita_tormenta_ruiva` (D4) | Grumete → Marujo → Contramestre → Imediato | `poder_kahen` | "A Boca do Fundo é o ponto de recrutamento… escalando o número de recrutadores" (`grupos_piratas_rivais.md:27`). |
| 16 | `osshari_brekmar` | **condicional** (raça) | só raça **Osshari** (`race_osshari`, `data/origins.json:99-100`); QG `bk_docas_velhas`; recrutadores `npc_mare_funda`, `npc_corrente_nova` | Filho da Maré → Arpoador → Guardião do Ossário | nenhum (neutralidade sagrada) | Comunidade de um povo; "não compartilham com forasteiros" e não tomam partido (`osshari_brekmar.md:21-29`). |
| 17 | `bandos_nomades` | **sim** | reputação ≥ neutro; QG `pradaria_ruinas`; recrutadores `npc_haldric_o_capitao_cinza` (Cavaleiros-Cinza), `npc_kaarg_osso_pintado` | Batedor → Cavaleiro → Capitão de Bando | `cidades_estado_sobreviventes_vaelorn_solvhen` | Bandos rivais "negociáveis em graus diferentes"; Haldric "honra acordos" (`bandos_nomades.md:25-30`); atacam as cidades-estado (`bandos_nomades.md:28`). |
| 18 | `mercadores_escravos_pradaria` | **não** (proposta; ver D2) | — | — | — | "Vilã clara num mundo de cinzas"; trata pessoas como inventário (`mercadores_escravos_pradaria.md:23-27`). Filiação ao tráfico como progressão do jogador fica para o dono decidir. |
| 19 | `cidades_estado_sobreviventes_vaelorn_solvhen` | **sim** | reputação ≥ neutro; nunca membro dos `mercadores_escravos_pradaria`; QG `pr_vaelorn` ou `pr_solvhen`; recrutadores `npc_lady_aerwen`, `npc_keeper_morvan` | Amigo da Cidade → Guarda da Ampulheta → Protetor das Cidades | `mercadores_escravos_pradaria`, `bandos_nomades` | "Possíveis aliadas de forasteiros contra os bandos" (`cidades_estado_sobreviventes_vaelorn_solvhen.md:27`); a ascensão elimina os traficantes (`data/factions.json:305-308`). |

Resumo: **9 sim** (1, 2, 4, 8, 9, 14, 15, 17, 19), **5 condicionais** (3, 5, 10, 13, 16) e
**5 não** (6, 7, 11, 12, 18). Fora as linhas 3 e 13, as condicionais são caminhos de nicho de
propósito: raça, conversão, exílio.

### 3.3 Schemas

```python
# state.py
class MembershipRecord(TypedDict, total=False):
    faction_id: str
    status: str  # "ativo" | "suspeito" | "ex_membro" | "expulso" | "traidor" | "dissolvida" | "rito_pendente"
    rank_index: int  # índice em catalog[fid]["ranks"]
    merit: int  # NUNCA exposto (R22)
    joined_day: int  # world_clock.day
    left_day: int  # 0 se ativo
    cooldown_until_day: int
    offenses: list[int]  # dias das ofensas (janela R18)
    exposed: bool  # fação secreta: vínculo conhecido por ela/rivais
    rival_awareness: dict[
        str, int
    ]  # rival_fid -> delta pendente em passos (+1/-1); consumido em R16
    last_info_day: int  # perk informacao 1x/dia
    rite_quest_id: str


class Faction(TypedDict, total=False):
    ...  # campos atuais
    influence: int  # -9..+9 (R14); default 0
    influence_periods: int  # acumulador de decadência; default 0


class Quest(TypedDict, total=False):
    ...  # campos atuais
    faction_id: str  # "" para quest comum
    mission_kind: str  # "apoio" | "sabotagem" | "rito"
    mission_tier: int  # 1..3
    target_faction_id: str  # só sabotagem


# GameState
faction_membership: dict[str, MembershipRecord]
```

```python
# agents/storyteller.py e agents/npc.py
class MembershipAction(BaseModel):
    action: str = Field(default="", description="'join' | 'leave' | 'ask_mission'; vazio se nada.")
    faction_id: str = Field(default="", description="id EXATO de <FACÇÕES_CONHECIDAS>.")


# StoryUpdate.membership_action: MembershipAction | None = None
```

### 3.4 Formato de dados (exemplo real)

```json
{
  "legiao_ferro": {
    "accepts": "sim",
    "secret": false,
    "exit_policy": "desonra",
    "hq_location_ids": ["na_anel_ferro"],
    "recruiter_npc_ids": ["npc_comandante_thrace"],
    "requirements": {
      "min_reputation_steps": 0,
      "races_allowed": [], "races_denied": [],
      "classes_allowed": [], "origins_allowed": [],
      "entry_rite": {"classes": ["Arcanista Cinzento", "Sangromante", "Corruptor"],
                     "kind": "registro_arcano", "gold_cost": 50},
      "not_wanted_in_region": "Nova Arcádia"
    },
    "exclusive_with": ["filhos_chama_azul"],
    "rivals": ["filhos_chama_azul", "mao_sombria"],
    "ranks": [
      {"id": "recruta",     "name": "Recruta",               "merit": 0,  "min_level": 1},
      {"id": "legionario",  "name": "Legionário",            "merit": 3,  "min_level": 2},
      {"id": "sargento",    "name": "Sargento",              "merit": 7,  "min_level": 3},
      {"id": "tenente",     "name": "Tenente",               "merit": 12, "min_level": 5},
      {"id": "comandante",  "name": "Comandante de Batalhão","merit": 18, "min_level": 7}
    ],
    "rank_cap": [],
    "perks_by_rank": {
      "0": [{"type": "abrigo"}],
      "1": [{"type": "desconto", "mult": 0.9}, {"type": "intendente"}],
      "2": [{"type": "passagem"}],
      "3": [{"type": "informacao"}, {"type": "desconto", "mult": 0.8}],
      "4": [{"type": "intercessao"}]
    },
    "quartermaster": {"escudo_de_aco": 1, "espada_aco_temperado": 2, "pocao_cura_maior": 3},
    "mission_templates": [
      {"id": "legiao_patrulha_lama", "kind": "apoio", "tier": 1, "min_rank": 0,
       "location_ids": ["na_anel_lama"],
       "title": "Patrulha no Anel de Lama",
       "description": "O sargento quer olhos nos becos onde as fogueiras de sedição acendem."},
      {"id": "legiao_quota_ferro", "kind": "apoio", "tier": 2, "min_rank": 1,
       "location_ids": ["na_anel_ferro"], "title": "...", "description": "..."},
      {"id": "legiao_cicatriz", "kind": "sabotagem", "tier": 2, "min_rank": 1,
       "target_faction_id": "filhos_chama_azul",
       "location_ids": ["na_anel_lama"], "title": "...", "description": "..."}
    ]
  },
  "tribos_devoradores_sol": {"accepts": "nao"}
}
```

`min_reputation_steps` é em passos (`REP_STEP=12` hoje, ou a unidade da SPEC-298). Os
números de mérito, nível e preço acima são **iniciais** e serão calibrados no playtest da
Etapa 9.

### 3.5 Assinaturas

```python
# services/faction_membership.py  (puras: recebem state/partes, devolvem cópias + eventos)
def load_catalog() -> dict[str, dict]: ...
def can_join(state: Mapping, faction_id: str) -> tuple[bool, str]: ...
def apply_intent(state: Mapping, action: str, faction_id: str) -> tuple[dict, list[dict], str]:
    """-> (updates parciais do GameState, propostas de evento source=engine, nota narrável)."""


def join(state, faction_id) -> tuple[dict, list[dict], str]: ...
def leave(state, faction_id) -> tuple[dict, list[dict], str]: ...
def register_offense(state, faction_id, kind: str) -> tuple[dict, list[dict], str]: ...
def on_mission_completed(state, quest: dict) -> tuple[dict, list[dict], str]: ...
def on_mission_failed(state, quest: dict) -> dict: ...
def apply_rival_awareness(state, location_id: str) -> tuple[dict, list[dict], str]: ...
def on_faction_defeated(state, faction_id: str) -> tuple[dict, list[dict], str]: ...
def perks_for(state, faction_id: str) -> list[dict]: ...
def has_perk(state, perk_type: str, *, location_id: str = "", faction_id: str = "") -> bool: ...
def membership_view(state, faction_id: str) -> dict | None: ...
def prompt_block(state) -> str: ...


# services/faction_missions.py
def offer_mission(state: Mapping, faction_id: str) -> tuple[list[dict], dict | None, str]: ...


# services/economy.py
def faction_quartermaster_stock(
    state: dict, location_id: str
) -> tuple[str | None, dict[str, int]]: ...


# world_utils.py (assinatura pública inalterada)
def advance_factions(factions, periods: int = 1) -> tuple[list, list]: ...
```

Ordem no turno (storyteller): viagem/descanso → `advance_factions` →
`resolve_faction_completions` → `on_faction_defeated` (para cada fação nova em `defeated`) →
`apply_rival_awareness(dest)` → LLM → `apply_reputation` + influence (R15) → `apply_intent`
(R20) → `register_offense` (R18) → as propostas vão para `pending_world_events` → o
`event_processor` aplica e faz o hook de missão (R12).

**Ownership (coordenador, no pouso):** criar a entrada `faction_membership` em
`project_index/state_ownership.yaml`, com writer canônico `services/faction_membership.py` via
`agents/storyteller.py`/`agents/npc.py`/`services/event_processor.py`, e as invariantes
`faction.rank_monotonic_unless_expelled` e `faction.no_membership_in_closed`. O subagente
não edita `project_index/`.

## 4. Plano passo a passo

Cada etapa é verificada com `bash scripts/dev/py.sh -m pytest tests/test_spec301_<etapa>.py -q`
mais os arquivos de teste existentes que ela toca.

### Etapa 1 — Catálogo e lint

1. **Testes** (`tests/test_spec301_catalogo.py`):
   - `test_catalogo_cobre_as_19_faccoes`: as chaves são iguais a `data/factions.json`;
   - `test_faccao_nao_sem_ranks`;
   - `test_ids_de_local_npc_item_rival_existem`;
   - `test_perk_tipo_fechado`;
   - `test_templates_minimos_por_faccao_aceitante` (≥ 2 apoio, ≥ 1 sabotagem com
     `target_faction_id` válido);
   - `test_ultima_patente_nao_e_lider` (nenhum `name` de rank igual ao nome de um NPC
     `leads` da fação);
   - `test_lint_validate_content_reporta_erro` (catálogo corrompido em tmp → exit ≠ 0).
2. **Implementação:** `data/faction_membership.json` conforme a §3.2 aprovada, `load_catalog`
   e a regra no `scripts/validate_content.py`.

### Etapa 2 — Entrar, requisitos, limite, exclusividade

1. **Testes** (`tests/test_spec301_entrada.py`):
   - `test_faccao_fechada_recusa_sempre` (R2, as 5 `nao`);
   - `test_ordem_dos_motivos` (R3: estado que falha em vários pontos devolve o primeiro);
   - `test_osshari_so_raca_osshari`;
   - `test_cultistas_so_classe_arcana`;
   - `test_kahen_rank_cap_nao_sangromante` (R8);
   - `test_limite_dois_vinculos` (R5);
   - `test_exclusiva_bloqueia`;
   - `test_secreta_conta_limite_nao_exclusividade`;
   - `test_local_exige_qg_ou_recrutador_presente`;
   - `test_join_emite_um_evento_engine_e_marca_intel` (R6);
   - `test_rito_cria_quest_e_nao_registra_membro` (R4);
   - `test_rito_concluido_efetiva_e_aplica_custo` (Batismo: 1 Ferimento leve + marca);
   - `test_procurado_noop_sem_spec299`.
2. **Implementação:** `can_join`, `join` e `apply_intent("join")`; `MembershipRecord` em
   `state.py`; validador `_v_faction_membership_changed`.

### Etapa 3 — Contra-jogo no relógio das fações

1. **Testes** (`tests/test_spec301_contrajogo.py`):
   - `test_influence_zero_identico_ao_legado`: propriedade com 50 combinações de
     pace/progress/periods, comparando com cópia da função antiga;
   - `test_pace_efetivo_por_influence` (±9 → ±3; piso 0);
   - `test_decadencia_a_cada_4_periodos`;
   - `test_ensure_factions_backfill_influence`;
   - `test_reputation_changed_move_influence_1` (R15);
   - `test_reversao_de_reputacao_reverte_influence`.
2. **Implementação:** `advance_factions`, `ensure_factions`, `storyteller.py:1116-1133` e
   `event_processor._revert_reputation`.
3. **Verificação adicional:** `tests/test_fase2.py`, `tests/test_fase27.py` e
   `tests/test_bug_contabilidade_recompensas.py` passam **sem edição**.

### Etapa 4 — Missões de fação

1. **Testes** (`tests/test_spec301_missoes.py`):
   - `test_offer_mission_deterministico_por_seed`;
   - `test_respeita_min_rank_e_uma_ativa_por_faccao`;
   - `test_respeita_max_active_quests`;
   - `test_location_fora_do_mapa_descartado`;
   - `test_conclusao_exige_prova` (sem `location_reached`, nada muda);
   - `test_conclusao_apoio_sobe_progress_satura_99` (R13);
   - `test_sabotagem_desce_rival_piso_0`;
   - `test_merito_e_promocao_uma_por_evento` (R7);
   - `test_min_level_segura_promocao`;
   - `test_ouro_por_tier_so_para_faction_quest`;
   - `test_falha_tira_1_merito_sem_rebaixar`;
   - `test_ascensao_so_no_tick` (progress 99 + `advance_factions(1)` → `completed`).
2. **Implementação:** `services/faction_missions.py`, `on_mission_completed`/`failed`, o hook
   no `event_processor` e `MISSION_GOLD` no `quest_log`.

### Etapa 5 — Perks (acesso, equipamento, serviços)

1. **Testes** (`tests/test_spec301_perks.py`):
   - `test_intendente_libera_por_patente`;
   - `test_desconto_aplicado_so_com_vinculo` (sem vínculo, `price` idêntico);
   - `test_unico_continua_unico_no_intendente`;
   - `test_abrigo_descanso_no_qg_sem_encontro`;
   - `test_passagem_ignora_hostile_ruler_da_propria_faccao`;
   - `test_informacao_uma_vez_por_dia_revela_objetivo_de_rival`;
   - `test_intercessao_noop_sem_spec299`;
   - `test_suspeito_perde_perks_ate_regularizar` (decisão D7; default: mantém `abrigo`,
     perde `intendente`/`desconto`).
2. **Implementação:** `perks_for`/`has_perk`, `economy.faction_quartermaster_stock`/`price`,
   `_hostile_ruler` e o ponto de descanso no storyteller.

### Etapa 6 — Saída, traição, rivais, dissolução

1. **Testes** (`tests/test_spec301_traicao.py`):
   - `test_leave_livre_desonra_traicao` (R17, as 3 políticas);
   - `test_primeira_ofensa_vira_suspeito_com_aviso`;
   - `test_segunda_ofensa_na_janela_trai` (R18);
   - `test_ofensa_fora_da_janela_so_suspeita`;
   - `test_entrar_em_exclusiva_confirma_traicao`;
   - `test_traidor_cooldown_30_dias`;
   - `test_rival_awareness_publica_aplica_ao_chegar_na_regiao` (R16a, idempotente);
   - `test_rival_awareness_secreta_so_apos_exposicao`;
   - `test_rival_awareness_via_npc_knowledge_quando_on` (R16b; `RPG_NPC_KNOWLEDGE=on` no
     monkeypatch);
   - `test_faccao_defeated_dissolve_vinculo` (R19);
   - `test_ascensao_da_propria_faccao_nomeia_no_bloco`.
2. **Implementação:** `leave`, `register_offense`, `apply_rival_awareness`,
   `on_faction_defeated` e o ponto de chamada pós-viagem no storyteller.

### Etapa 7 — Fiação do LLM, prompt e crônica

1. **Testes** (`tests/test_spec301_llm.py`):
   - `test_membership_action_ausente_nao_quebra` (FallbackLLM devolve `AIMessage` → no-op);
   - `test_id_invalido_vira_nota_de_recusa_sem_estado`;
   - `test_quarentena_ignora_campo`;
   - `test_bloco_faccao_sem_numeros` (regex: nenhum dígito de mérito/influência no bloco);
   - `test_npc_recrutador_presente_habilita_join`;
   - `test_milestone_cronica_por_acao`;
   - `test_validator_rejeita_membership_vindo_do_llm` (`source="storyteller"` → rejeitado).
2. **Implementação:** `MembershipAction` no `StoryUpdate` e no modelo do `npc_actor`, os
   blocos de prompt (instrução curta: "registre em `membership_action` só se o jogador pediu
   explicitamente"), o template no `services/chronicle.py` e o `MockLLM` mantendo o campo
   vazio por default.

### Etapa 8 — API e UI

1. **Testes** (`tests/test_spec301_api.py`):
   - `test_factions_block_membership_sem_merit_influence` (varre o payload atrás das chaves
     proibidas);
   - `test_membership_so_para_faccao_com_vinculo`;
   - `test_standing_label_enum_fechado`;
   - `test_assert_no_player_leak_continua_verde` (oráculo SPEC-206/211 com estado de
     membro).
   - Playwright: `web/e2e/` ganha 1 caso que monta um estado com vínculo e vê o nome da
     patente no painel.
2. **Implementação:** `api._factions_block` e a renderização no componente que já lista as
   fações.

### Etapa 9 — Persistência, playtest e invariantes

1. **Testes:**
   - `tests/test_spec301_persistencia.py`: `test_round_trip_save_load` (R24) e
     `test_save_antigo_sem_campos_carrega` (fixture de save pré-301);
   - `playtest/invariants.py`:
     - `faction_rank_monotonic` (cai só com `expulso|traidor|dissolvida`);
     - `no_membership_in_closed`;
     - `membership_count_le_2`;
     - `influence_bounded`;
     - `progress_le_99_outside_tick`;
   - perfil novo `faccionario` em `playtest/profiles.py` (se alista, pede missões, viaja,
     sabota rival, sai).
2. **Execução:**
   - `uv run python -m playtest run --profile faccionario --turns 50` (MockLLM), com 0
     violações `error`;
   - medir quantos dias de jogo leva cada promoção, para calibrar a §3.4.

## 5. Critérios de aceite

- [ ] R1–R24 cobertos por teste (arquivos `tests/test_spec301_*.py`)
- [ ] §3.2 aprovada pelo dono (linhas marcadas como decididas) antes da Etapa 1
- [ ] `tests/test_fase2.py`, `tests/test_fase27.py` e `tests/test_bug_contabilidade_recompensas.py`
      verdes **sem edição** (influence 0 = legado)
- [ ] Nenhuma superfície da API expõe mérito, influência ou `rival_awareness`
      (`assert_no_player_leak` verde)
- [ ] Guard de FallbackLLM em `membership_action` (storyteller e `npc_actor`)
- [ ] Saves antigos carregam; round-trip de `faction_membership`/`influence` sem diferença
- [ ] Perfil `faccionario` com 50 turnos em MockLLM e 0 violações `error`
- [ ] Revisão independente Opus (`handoffs/SPEC-301-review.md`)
- [ ] `uv run pytest` verde (suíte completa offline, 1× no pouso)
- [ ] Smoke real §6 executado e registrado

## 6. Smoke test com LLM real

Usa DeepSeek (primário, `ROUTES`), no teto do dono de US$ 3/dia. São ~6 turnos, com
`--max-requests 30 --max-cost 0.50`, usando o harness `playtest --real` com um roteiro fixo
ou o CLI. Personagem: Humano, Médico de Campo, origem Nova Arcádia.

1. Viajar para `na_anel_ferro` e falar com o Comandante Thrace: "Quero me alistar na
   Legião." **Esperado:** o `npc_actor` real preenche `membership_action={join,
   legiao_ferro}`, o evento `joined` entra no `event_log` e a narração cita "Recruta".
   Confere o mapeamento de campo, que o MockLLM esconde.
2. "Tem alguma missão para mim?" **Esperado:** `ask_mission` gera uma quest com `faction_id`
   e título do template, e a narração usa o texto do template, sem inventar outra missão.
3. Viajar ao local da missão, investigar e voltar para entregar. **Esperado:**
   `quest_completed` aceito com prova, mérito e `progress` alterados no estado e nenhum
   número na narração.
4. Pedir para entrar nos Osshari com personagem Humano. **Esperado:** recusa narrada
   ("não é do mar"), estado intacto.
5. "Deixo a Legião." **Esperado:** `left`, −2 passos de reputação, `cooldown_until_day`
   gravado.

Registrar custo e latência no hand-back. Se o provider real errar o nome do campo, corrigir a
`description` do `Field` antes do `done`.

## 7. Riscos & compatibilidade

- **Saves antigos:** todos os campos têm default neutro (R23). `influence = 0` reproduz o
  relógio linear atual. A missão de fação só existe depois que o jogador entra.
- **Conflito de semântica de `disposition`:** hoje o mesmo campo é a "postura geral"
  semeada (`data/factions.json:42`, Filhos `hostil`) e a postura derivada da reputação do
  jogador, que é sobrescrita em `world_utils.py:568`. Um membro de alta reputação tornaria uma
  fação vilã "aliada" no mundo inteiro (`_hostile_ruler`, `world_utils.py:661-669`;
  `economy._controller_disposition`, `services/economy.py:104-112`). Esta spec **não**
  muda isso e usa o perk `passagem` para o caso do membro. A separação dos dois sentidos é da
  SPEC-298 (ver D8).
- **MockLLM/FallbackLLM:** o MockLLM devolve `membership_action` vazio, então a suíte
  offline exercita o núcleo pelas funções puras e por monkeypatch do modelo. O FallbackLLM
  devolve `AIMessage`: guard obrigatório (R20). O caminho real só é validado no §6.
- **Prompt:** o bloco `<FAÇÃO_DO_JOGADOR>` tem ≤ ~80 tokens e só aparece com vínculo. Há 1
  campo opcional a mais no schema do storyteller e do `npc_actor`, sem chamada LLM extra.
- **Exploração de mérito:** o limite de 1 missão ativa por fação, a prova obrigatória e o
  progresso saturado em 99 impedem farm de ascensão. A calibragem vem do playtest (Etapa 9).
- **Interação com SPEC-302:** a 302 vai substituir o tick por "1× por dia virado". O
  contrato é que ela leia `Faction.influence` e o quadro de membros, sem reescrever as regras
  de R13/R14. Se a 302 mudar a unidade de tempo, as constantes de decadência migram junto
  (está registrado como interface).
- **Conteúdo sensível:** filiar-se a cultos vilões (Filhos, Cultistas) é permitido pela
  lore. O tráfico de pessoas (linha 18) fica fechado até o dono decidir (D2).

## 8. Decisões que o dono precisa tomar

- **D1 — Tabela §3.2:** aprovar ou ajustar o `accepts`, os requisitos e as patentes de cada
  uma das 19 fações.
- **D2 — Mercadores de Escravos:** `nao` (proposto) ou `condicional` ("caçador
  contratado", sem patente alta)?
- **D3 — Devoradores de Sol:** totalmente fechada (proposto) ou `condicional` para origem
  `deserto_zhur`?
- **D4 — Piratas:** uma fação só (proposto, com recrutadora Tormenta Ruíva) ou separar as
  tripulações (Tormenta × Garfo-de-Sal) em ids próprios? Separar exige mexer em
  `factions.json` e fica fora desta spec.
- **D5 — Rivais estáticos:** usar a lista curada `rivals` até a SPEC-302 (proposto) ou
  derivar só de `enemy_of` no grafo? Hoje o grafo tem só 2 arestas `enemy_of` entre as 19.
- **D6 — Limite de vínculos:** 2 simultâneos, com secreta contando no limite (proposto)?
- **D7 — Status suspeito:** perde intendente/desconto e mantém abrigo (proposto)?
- **D8 — `disposition`:** confirmar que a separação "postura do mundo × postura com o
  jogador" fica na SPEC-298, não aqui.


## Decisões do dono (2026-10-23)

Todas as decisões abertas desta spec seguem o **default recomendado pelo autor**, exceto/explicitando:

- D2: Mercadores de Escravos FECHADOS.
- D3: Devoradores de Sol aceitam só herói com origem no Deserto de Zhur.
- D6: máx. 2 vínculos simultâneos, a fação secreta conta no limite.


## Desvios da implementação (2026-10-24)

Contrato da SPEC-298 usado: reputação numérica -100..100 (`faction_tier`), "passo" = `REP_STEP = 10`;
`min_reputation_steps: 0` = "neutro ou melhor" (rep >= -9). Mudanças em relação ao texto acima:

- **D2/D3 do dono:** Mercadores de Escravos `nao`; Devoradores de Sol `condicional` só com
  `origin_region_id = deserto_zhur` (recrutador Vasketh). Totais: 9 sim, 6 condicionais, 4 não.
- **R3:** enum de recusa ganhou `caminho` (condicionais por exílio/conversão/encontros com NPC) e
  `reputacao` cobre também `requires_intel`; `never_member_of` recusa como `exclusiva:<fid>`.
- **R5/R18:** "entrar numa exclusiva confirma traição" só existe no caminho autorado
  `converts_from` (Ciclo→Renegados Druidas, Clãs→Renegados do Ermo); o resto é recusado.
- **R14:** `pace + int(influence/3)` (trunca rumo a 0, simétrico) em vez de `//`.
- **R15:** a influência ±1 e as ofensas (R18) são aplicadas em `event_processor` sobre as
  `reputation_changed` realmente aplicadas por `reputation.process_deeds` (não há mais
  `apply_reputation` no storyteller nem `_revert_reputation`). Reputação entregue depois por
  pendência (`_deliver_pending`) não move influência.
- **R12/R7:** `on_mission_completed` é chamado em `event_processor`; ouro por tier via
  `MISSION_GOLD` no `quest_log`. Apoio concluído regulariza o status `suspeito`.
  Nova regra mínima: reputação <= limiar hostil expulsa o membro (`check_expulsion`, evento `expelled`).
- **R4:** custo do rito é cobrado na conclusão (ouro com piso 0); marca/ferimento do Batismo
  ficam em `MembershipRecord.marks` e `player.ferimentos`.
- **R10:** o intendente amplia o estoque do mercador do QG (`merchant_stock`); só vale onde há
  mercador no QG (lint garante). Desconto = perk `desconto` nos QGs da fação.
- **R16:** pendência aplicada na chegada à região do rival ou, com `RPG_NPC_KNOWLEDGE=on`, quando um
  NPC da fação rival ouviu o evento (sempre checado a cada turno). Fação secreta nunca propaga.
- **R20:** recusa e sucesso viram nota anexada à mensagem; id inexistente vira nota genérica.
- **R22:** `standing_label` ganhou `ex-membro`, `fação dissolvida`, `em rito de entrada`.
- **offer_mission** devolve `(quests_atualizadas, quest|None, nota)`; perk `informacao` dispara
  em `ask_mission`.
- **Etapa 8:** o painel é `web/src/components/Hud.tsx`; o caso Playwright novo não foi criado
  (`web/e2e/contracts` protegido).
- Perfil `faccionario` (MockLLM propõe `membership_action` só com pedido explícito): 50 turnos, 0 violações.
- **Integração com a SPEC-302 (rebase na main):** com `RPG_WORLD_ENGINE=on`, a influência modula o
  pace no tick diário (`world_engine`, passo 6: `effective_pace`) e decai 1 por dia; o
  `advance_factions` legado (decaimento a cada 4 períodos) só vale com o motor off. Em ambos,
  influência 0 = comportamento anterior, e missão nunca leva o progress a 100 (só o tick ascende).
