# SPEC-299 — Lei e crime por região

> **Status:** `in-progress` (implementada; aguarda revisão independente e suíte completa no pouso)
> **Criada:** 2026-10-20 · **Atualizada:** 2026-10-20
> **Origem:** `docs/mundo-vivo/VISAO.md` (Regra de ouro; C. Sociedade viva → "Crime e lei por região"; Calibração → "Procurado"; B. Combate vivo → "entregar/vender" prisioneiro)
> **Depende de:** SPEC-215 (`done`, conhecimento por NPC), **SPEC-298** (fama por local; precisa estar `done`, ver §3.9), SPEC-296 (soft: bloco de ambiente da Onda 0, ver R19)
> **Desbloqueia:** spec futura de prisioneiros (pilar B), SPEC-302 (tick diário consome `law.daily_tick`), SPEC-301 (patente na Legião pode mudar a relação com a lei)
> **EXECUTOR_MODEL:** `Sonnet` (etapas 1–6, 9) / `Opus` (etapas 7–8: router, combate, encontro) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (estado persistente novo, structured output novo, gate no router, encontro sistêmico)
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum evaluator/dataset protegido é tocado)

---

## 1. Contexto & Objetivo

O mundo de Valoria tem lei na lore e nenhuma no motor. O Código de Ferro rege Nova
Arcádia (`lore_nova/locations.txt:11`, `lore_nova/factions.txt:14-20`: "roubo = dedos,
sedição = língua, magia não registrada = fogueira"). A Legião patrulha os portões
(`locations.txt:19`), mantém o Oubliette no Anel de Ferro (`locations.txt:65`) e "matar um
legionário traz a cidade inteira atrás de você" (`lore_nova/creatures.txt:742`). Brekmar
"não tem leis" e se regula por reputação e vingança pessoal (`locations.txt:435-440`). O Anel
de Lama fica fora do Código (`locations.txt:73`). Os dados já marcam isso
(`data/world_map.json:18` `codigo_de_ferro`, `:117` `fora_da_lei`, `:780` `sem_lei`), mas
**nenhum código Python lê essas tags**: "Código de Ferro" só aparece num comentário de
`scripts/migrate_lore_nova.py:245`. A auditoria do mundo vivo registra "Código de Ferro (0
referências no código)" (`docs/mundo-vivo/VISAO.md:41-43`).

Hoje um crime não tem consequência mecânica. A única reação é a reputação de fação ±12
decidida pelo LLM (`agents/storyteller.py:1103-1133`, `world_utils.py:544-578`), sem saber
quem viu, onde, nem qual lei vale ali.

Esta spec cria a camada **lei por jurisdição**. Cada local pertence a um código (ou a
nenhum). Um crime **testemunhado** gera um relato que chega à lei com atraso geográfico. Daí
vêm notoriedade, preço pela cabeça, guardas e caçadores de recompensa. O jogador pode pagar
multa, cumprir pena, fugir ou lutar. Ele só percebe que é procurado **por sinais** (cartaz,
olhar de guarda, aviso de NPC), nunca por um indicador.

Princípios aplicados:

- **Regra de ouro:** a lei só sabe o que alguém viu e contou.
- **Mecânica em Python, determinística por seed:** o LLM só classifica o crime narrado e
  narra o resultado; validadores barram.
- **Duro, mas telegrafado:** a patrulha aparece na cena antes do crime, e o caçador vem
  depois de um sinal.
- **O mundo não escala com o herói:** a força do encontro vem do preço pela cabeça, não do
  nível.
- **Migração suave:** default neutro e flag de rollout.

## 2. Requisitos

### Dados e jurisdição

- **R1 — Códigos curados em dado.** O arquivo novo `data/law_codes.json` declara os códigos
  (§3.3) e o mapa `location_id → code_id | null`. Local ausente do mapa = **sem lei**. O lint
  (`scripts/validate_content.py`) falha se:
  - um `location_id` não existe em `world_map.json`;
  - uma `authority_faction_id` não é fação em `data/graph/entities.json`;
  - um id de `guard_pool`/`hunter_pool` não existe em `data/bestiary.json`;
  - `prison_location_id` está fora da própria jurisdição;
  - um tipo de crime não pertence ao catálogo fechado (R5).
- **R2 — Conteúdo inicial fiel à lore** (valores `[BALANCEAR]`; a lista é proposta para o
  dono revisar, decisão D1):
  - `codigo_de_ferro`: `nova_arcadia`, `na_anel_dourado`, `na_anel_ferro`. Autoridade
    `legiao_ferro`, prisão `na_anel_ferro` (Oubliette), rígido, sem suborno (Inquisidores
    "não aceitam suborno", `creatures.txt:822`).
  - **Sem lei:** `na_anel_lama` e `na_taverna_javali` (o Código "não menciona o Anel de
    Lama", `locations.txt:73`), `brekmar` e `bk_docas_velhas` (`locations.txt:435-438`).
  - `colmeia`: `sx_cidades_hospedeiros`. Autoridade `colmeia_hospedeiros`. A colmeia
    partilha percepção e "sente mentira e intenção" (`factions.txt:475-479`): testemunha
    compartilhada, sem furtividade, punição = expulsão.
  - `lei_dos_clas`: `skallgard`, `sk_salao_do_jarl`. Autoridade `clas_combate`, branda com
    multa, hostil a forasteiros (`locations.txt:223`). A lore é rasa aqui (D1).
  - `lei_de_vaelorn` (`pr_vaelorn`) e `lei_de_solvhen` (`pr_solvhen`). Autoridade
    `cidades_estado_sobreviventes_vaelorn_solvhen`, branda.
  - Todo o resto (ermos, ruínas, pântano, deserto, montanhas, costa) é **sem lei**.
- **R3 — Sem lei não é sem consequência.** Crime em local sem jurisdição não gera
  notoriedade, guarda nem caçador. A reputação com NPC e fação segue os caminhos que já
  existem (e a SPEC-298). Esta spec só garante que `law` não age ali.

### Crime: classificação e validação

- **R4 — Duas fontes de crime, uma porta.** Todo crime entra por
  `law.register_crime(state, CrimeCandidate)`, que valida e devolve o registro ou uma recusa
  com motivo. As fontes são:
  - **(a) LLM classifica.** Campo novo `crime_claims: list[CrimeClaim]` em `StoryUpdate`
    (`agents/storyteller.py:50`) e em `NPCResponse` (`agents/npc.py:158`).
  - **(b) Motor detecta.** Combate com `origin == "player_provoked"`
    (`services/combat_origin.py:7-14`) contra alvo não hostil ou da fação-autoridade num
    local com jurisdição vira `agressao`. `npc_killed` aceito nessas condições vira
    `homicidio`. A fuga de um confronto da lei vira `resistencia` (só motor).
- **R5 — Catálogo fechado.** `furto`, `agressao`, `homicidio`, `dano_propriedade`,
  `magia_ilegal` (vem desligada no dado, D2), `resistencia` e `evasao` (estes dois só o motor
  emite). Tipo fora do catálogo é recusado.
- **R6 — Validador anti-alucinação.** Um `CrimeClaim` do LLM só vira candidato se passar em
  todas as condições abaixo. Recusa vai para `event_rejections` com motivo, sem quebrar o
  turno.
  1. O tipo está no catálogo e é proponível pelo LLM.
  2. O turno não está em quarentena de payload (`quarantine_llm_payload`,
     `agents/storyteller.py:1108-1110`).
  3. A vítima é `""`/`"local"` (crime contra propriedade) ou um NPC presente em
     `npc_layers.npcs_in_scene` (`services/npc_layers.py:130-156`).
  4. A **ação do jogador** neste turno tem suporte lexical para o tipo (léxico `[BALANCEAR]`
     por tipo; ex.: furto ← roubar/furtar/surrupiar/afanar/"pego escondido"). Assim o
     narrador nunca acusa o jogador de algo que ele não tentou.
  5. Há no máximo 1 crime por tipo por turno.
- **R7 — Guard de FallbackLLM.** O campo novo tem default `[]`. Lê-lo segue o padrão de
  `faction_impacts` (`getattr(update, "crime_claims", []) or []`). Resposta não-instância
  (`AIMessage`) = sem crime.

### Testemunhas e relato (regra de ouro)

- **R8 — Testemunhas.** As testemunhas são:
  - os NPCs de `npcs_in_scene` no local, **exceto** a party ativa, a vítima morta e quem a
    narração marcou como cúmplice (fora de escopo: sempre vazio nesta spec);
  - a **patrulha**, se `law.patrol_present(state, loc, clock)` for verdadeiro.

  Atenção: `npc_knowledge._present_holders` (`services/npc_knowledge.py:169-178`) inclui a
  party. A lei usa um filtro próprio e não altera essa função.
- **R9 — Patrulha telegrafada.** A presença de patrulha é determinística por
  `sha256(game_id|loc|day|period)` × `patrol_density[loc]`. Ela é calculada **antes** da
  ação do turno e vai para o contexto do narrador como fato de cena ("Legionários vigiam o
  portão"). O crime nunca é testemunhado por uma patrulha que a cena não mostrou.
- **R10 — Furtividade.** Se o claim marca `covert=true` **e** o código permite
  (`covert_possible`; a colmeia não permite), cada testemunha civil faz um teste
  determinístico. Ela percebe se `2d10 + mod ≥ DC_furtividade[tipo]` `[BALANCEAR]`, usando
  `services/conflict_resolution.roll_kept`/`virtude_value` (o mesmo primitivo de
  `services/chase.py:18`), com seed `game_id|crime_id|witness`. A patrulha percebe sempre.
  Sem testemunha, o crime fica `unwitnessed`: é registrado só para auditoria e **nunca**
  gera relato.
- **R11 — Relato com atraso.** As regras de entrega são:
  - Patrulha testemunha → relato com `due_clock = clock` (imediato).
  - Civil → relata com probabilidade `report_chance` `[BALANCEAR]` (seed
    `game_id|crime_id|witness`) e `due_clock = clock + report_delay_periods`.
  - Colmeia → qualquer testemunha da colmeia = relato imediato e confronto (R16) sem atraso.

  O relato entregue cria/atualiza o `Wanted` da jurisdição e define `known_at[crime_loc] =
  due_clock`. A notícia chega aos demais locais da **mesma** jurisdição em `due_clock +
  services.world_distance.travel_periods(crime_loc, L) + courier_delay`
  (`services/world_distance.py:44`), o mesmo modelo de atraso da SPEC-215
  (`npc_knowledge.py:536`).
- **R12 — Testemunha que some não relata.** Na hora da entrega, um relato cuja testemunha
  está morta (`npc_layers.npc_alive`, `services/npc_layers.py:87`) é descartado. Uma
  testemunha que, no turno do crime, virou membro da party também. Matar a testemunha é um
  crime novo e pode ter outras testemunhas.
- **R13 — Evento auditável e propagação social.** O relato entregue emite um `GameEvent`
  `crime_witnessed` (só o motor emite, `source="law"`, mesmo gate de
  `world_validators.py:494-512`). O tipo entra em `npc_knowledge.SUBJECT_PARAMS`
  (`services/npc_knowledge.py:48-55`) com `p/raio/hops` `[BALANCEAR]`. Com
  `RPG_NPC_KNOWLEDGE` em `shadow`/`on`, os NPCs ouvem falar do crime pelo caminho da SPEC-215.
  A **lei** não depende dessa flag (`npc_knowledge.py:84-86`, default `off`): ela tem o
  próprio relato determinístico (R11). Os dois caminhos partem das mesmas testemunhas, então
  nenhum inventa conhecimento (decisão D3).

### Notoriedade, preço pela cabeça e sinais

- **R14 — Notoriedade por jurisdição.**
  - O `Wanted[jurisdiction]` guarda `heat` (0–100), `bounty` (ouro), `capital` (bool) e
    `known_at{loc: clock}`.
  - O `heat` sobe com a `severity` do crime, já multiplicada pelo código. Ele decai
    **preguiçosamente**, como função pura de `(heat, last_crime_clock, clock)`:
    `decay_per_day` `[BALANCEAR]` sem precisar de tick. `capital=true` nunca decai.
  - Nível derivado: `limpo` < `suspeito` < `procurado` < `cacado` (limiares `[BALANCEAR]`).
  - O número nunca sai de `services/law.py`.
- **R15 — Consome a fama por local (SPEC-298).** Em cada local do confronto/encontro, a
  chance de reconhecimento é `base[nível] + k × |fama_local|` `[BALANCEAR]`: o rosto famoso é
  reconhecido. Quando o relato é entregue no local do crime, a lei chama o escritor de fama
  da SPEC-298 com `reason="crime:<tipo>"`. Tudo isso passa por **um único** adaptador
  `law._fame_bridge` (§3.9). Sem a SPEC-298, o adaptador devolve 0 e não escreve.
- **R16 — Sinais, nunca indicador.** `law.signals_for(state)` devolve de 0 a 2 frases
  diegéticas, determinísticas e com teto por cena. Elas aparecem só em locais onde
  `known_at[loc] ≤ clock` (a notícia chegou):
  - `cartaz`: nível ≥ `procurado` em local com tag `cidade`. O texto usa faixa vaga, nunca
    número (D4).
  - `olhar_de_guarda`: nível ≥ `suspeito` com patrulha presente.
  - `aviso_de_npc`: um NPC em cena com relação ≥ `npc_knowledge.BELIEF_MIN_RELATIONSHIP`
    (`services/npc_knowledge.py:43`) avisa pelo contexto do `npc_actor`.
  - `perguntaram_por_voce`: obrigatório antes do 1º caçador, ver R18.
- **R17 — Sem vazamento.** O estado da lei:
  - **não** aparece em `GameResponse` (`api.py:2082-2094`; o modelo é explícito, então basta
    não adicionar campo e testar), em `/game/codex`, nos dossiês nem no mapa;
  - **não** entra no prompt do narrador como número, nível ou lista de crimes, só pelos
    sinais (R16) e pelo fato de cena da patrulha (R9).

### Consequências: confronto, multa, pena, fuga, caçadores

- **R18 — Caçadores de recompensa via `check_encounter`.** Em `world_utils.check_encounter`
  (`world_utils.py:975-1071`), a razão nova `bounty_hunters` entra **depois** do alerta de
  reforços (`:1023-1034`) e **antes** do domínio de fação (`:1036`). Condições:
  - o nível é `cacado`;
  - o local está na jurisdição ou a ≤ `hunter_radius_periods` dela (`world_distance`);
  - a notícia chegou à jurisdição há ≥ `hunter_delay_periods`;
  - **um sinal `perguntaram_por_voce` já foi mostrado** (telegrafado);
  - o roll seeded `game_id|jid|clock` passa.

  O encontro respeita o cooldown global (`world_utils.py:999-1004`) e só ocorre em viagem ou
  descanso, porque é o único chamador (`agents/storyteller.py:632-659`), coerente com "tempo
  só passa ao dormir e viajar". A criatura vem de `hunter_pool`. A força
  (`encounter_eff_danger`) vem da faixa do preço pela cabeça, **nunca** de `player.level`. A
  origem do combate é `law_enforcement` (valor novo em `combat_origin.ORIGINS`).
- **R19 — Confronto da lei.** Ele nasce quando:
  - uma patrulha testemunha o crime (no fim do turno);
  - o jogador, procurado num local onde a notícia chegou e há patrulha, é reconhecido
    (R15) ao entrar no local;
  - o jogador se entrega ou pede para pagar por iniciativa própria.

  O confronto é gravado em `law_state.confrontation`. No turno seguinte, um **gate
  determinístico** no router, no mesmo padrão de `_combat_gate` (`agents/router.py:130`),
  resolve por léxico:
  - `pagar` (ver R20);
  - `render-se` → pena (R21);
  - `fugir` (`services/chase.FLEE_RE`, `services/chase.py:22`) → crime `evasao` + combate de
    fuga com os guardas;
  - `atacar` → crime `resistencia` + combate com `guard_pool`;
  - outro texto → rota NPC com o guarda como interlocutor.

  Depois de `max_talk_turns` `[BALANCEAR]` de conversa, os guardas tentam a prisão (combate).
  A cena do confronto chega ao narrador como fato ("Dois legionários bloqueiam a saída"),
  não como menu. Se a SPEC-296 já tiver o bloco de ambiente, o fato entra nele; se não, entra
  num bloco próprio.
- **R20 — Multa.** `fine = Σ fine[tipo]` dos crimes **relatados** e não resolvidos da
  jurisdição.
  - Crime `capital` não admite multa.
  - Ouro insuficiente = a opção falha, é narrada e o confronto continua.
  - Pagar zera `heat`/`bounty` da jurisdição, marca os crimes como `resolved` e emite o
    evento `law_resolved{mode:"fine"}`. O ouro é debitado pelo caminho de economia que já
    existe (nunca valor vindo do LLM).
- **R21 — Pena.**
  - A pena é `Σ sentence_days` (teto `[BALANCEAR]`).
  - O jogador vai para `prison_location_id` e o relógio avança `dias × len(PERIODS)` via
    `world_utils.advance_clock` (`world_utils.py:64`).
  - A party ativa passa a `waiting_at` no local da prisão.
  - `heat`/`bounty` zeram, os crimes viram `resolved` e o motor emite
    `law_resolved{mode:"sentence"}`.
  - Sem efeito em Vitalidade, inventário ou ouro nesta spec. Execução e mutilação ficam para
    a decisão D5.
  - A colmeia usa `punishment="expulsao"`: o jogador é movido para o local conectado fora da
    jurisdição e fica com `heat` em `cacado` lá. Não há prisão.
- **R22 — Fugir é legítimo.** Sair da jurisdição encerra o confronto. O `heat` continua lá e
  só decai (R14). Fora do raio, os caçadores não vêm. Voltar reabre o reconhecimento (R15).

### Prisioneiros (só interface)

- **R23 — Interface para a spec futura de prisioneiros.** Esta spec define e testa (com
  fixture) as funções abaixo. **Nada** no grafo as chama:
  - `law.prisoner_bounty(state, prisoner: PrisonerRef, location_id) -> int`: 0 sem
    jurisdição ou sem preço.
  - `law.deliver_prisoner(state, prisoner, location_id) -> tuple[dict, LawReceipt]`:
    recompensa em ouro e recibo. Entregar no próprio local de jurisdição não é crime. Em
    local sem lei a função recusa (`reason="sem_lei"`).

  Preço do prisioneiro: `bounty_by_enemy` do código (ex.: membro de fação inimiga da
  autoridade). Com SPEC-301/298, entra também o `Wanted` do próprio NPC.

### Rollout, compatibilidade, determinismo

- **R24 — Flag `RPG_LAW=off|shadow|on`**, default `off`, no mesmo padrão de
  `npc_knowledge.mode()`:
  - `off`: comportamento byte a byte igual ao atual. Nenhum campo novo é escrito e
    `crime_claims` é ignorado.
  - `shadow`: registra crimes, testemunhas, relatos e `Wanted` e loga, mas sem sinais,
    confronto ou caçadores.
  - `on`: tudo ligado.
- **R25 — Save antigo.**
  - `law_state` ausente → `normalize_law(raw)` devolve estado vazio. É aditivo, **sem bump**
    de `SCHEMA_VERSION`, no mesmo padrão do ledger da SPEC-215 (`state.py:581-586`,
    `persistence.py:628-630`).
  - O round-trip save/load preserva `law_state`.
  - Com `data/law_codes.json` ausente ou inválido, a lei fica inerte e loga.
- **R26 — Determinismo.** Toda decisão (patrulha, percepção, relato, reconhecimento,
  caçador) usa seed `sha256` de ids estáveis (`game_id`, `crime_id`, clock), sem `random`
  global. Mesmo estado + mesma entrada = mesmo resultado.
- **R27 — Sem crime, nada muda.** Em `on`, uma campanha sem crime aceito produz o mesmo
  playtest que o `main` (mesmos combates, mortes e métricas da SPEC-285). Isso prova que a
  lei não encosta em quem não comete crime.
- **R28 — Tetos.** `crimes` ≤ 100, `reports` ≤ 100, `signals_shown` ≤ 32 por jurisdição e
  `served` ≤ 20 (FIFO).

### Fora de escopo

- Prisioneiros de fato: captura, escolta, resgate, interrogar ou recrutar. Só a interface
  (R23).
- Suborno (lore apoia em parte: `npcs.txt:1507` "guardas subornáveis"; Inquisidores não
  aceitam) → D6.
- Execução, mutilação (dedos/língua), confisco de contrabando e servidão por dívida (Mercado
  de Carne, `locations.txt:63`) → D5.
- Disfarce, identidade falsa, perdão pela autoridade e patente na Legião (SPEC-301).
- Vingança pessoal em Brekmar e guerra dos Osshari pelo Ossário (`factions.txt:284`; o
  Ossário não é um local do mapa).
- Mover reputação de fação por crime: continua com `faction_impacts`/SPEC-298. Esta spec só
  escreve fama por local pelo adaptador.
- Reação dos companheiros ao crime (SPEC-300).
- Tick diário do mundo (SPEC-302). O decaimento aqui é preguiçoso, e `law.daily_tick` é só
  um gancho opcional.
- Crimes de furto como **mecânica** de inventário (bater carteira, roubar loja). O motor não
  tem furto hoje (nenhum `roub|furt|steal` em `agents/`/`services/`). O crime é registrado,
  mas o item "roubado" segue as regras atuais de `items_gained`.
- UI nova (não há indicador por decisão do dono) e eventos de crônica para crimes.

## 3. Design técnico

### 3.1 Arquivos novos

- `data/law_codes.json`: códigos + jurisdições (curado à mão, lint em R1).
- `services/law_codes.py`: loader com cache, `code_for_location(loc_id) -> LawCode | None`,
  `jurisdiction_locations(code_id) -> list[str]` e `lint_law_codes() -> list[str]`.
- `services/law.py`: **owner único** de `law_state` (puro, sem LLM, sem I/O; devolve dicts
  novos):
  - `mode()` e `normalize_law(raw)`;
  - `register_crime`, `patrol_present`, `turn_updates` (entrega de relatos) e
    `effective_heat`/`level`;
  - `recognition_check`, `signals_for`, `confrontation_*` e `resolve_fine`/`serve_sentence`;
  - `hunter_encounter`, `prisoner_bounty`/`deliver_prisoner` e `_fame_bridge`.
- `tests/test_spec299_law_codes.py`, `tests/test_spec299_crime_claims.py`,
  `tests/test_spec299_witness_report.py`, `tests/test_spec299_wanted_signals.py`,
  `tests/test_spec299_confrontation.py`, `tests/test_spec299_hunters.py` e
  `tests/test_spec299_prisoner_api.py`.
- `playtest/profiles.py`: perfil novo `criminoso` (furta/agride em Nova Arcádia, foge,
  volta, paga). Atualizar os asserts que contam "14 perfis".

### 3.2 Arquivos alterados

- `state.py`: os TypedDicts de §3.4 e `law_state: LawState` no `GameState` (bloco "SPEC-299",
  aditivo).
- `persistence.py`: `normalize_law` no load (junto de `normalize_knowledge`, `:628`).
- `services/structured_outputs.py`: `EventType` ganha `crime_witnessed` e `law_resolved`
  (comentário: só motor).
- `services/world_validators.py`:
  - gate `source == "law"` para os dois tipos, no bloco de `:494-512`;
  - validadores `_v_crime_witnessed` (jurisdição existe, `crime_id` está em `law_state`) e
    `_v_law_resolved`, registrados em `_VALIDATORS` (`:467`).
- `services/npc_knowledge.py`: `SUBJECT_PARAMS["crime_witnessed"]` (R13). Nada mais muda.
- `agents/storyteller.py`:
  - `CrimeClaim` e `StoryUpdate.crime_claims`;
  - depois do bloco de `faction_impacts` (`:1103-1133`), chama `law.register_crime` por claim;
  - injeta o fato de patrulha, o fato do confronto e os sinais no contexto (R9/R16/R19);
  - repassa `law.hunter_encounter` para `check_encounter`.
- `agents/npc.py`: `NPCResponse.crime_claims` (`:158`) e o sinal `aviso_de_npc` no contexto
  do NPC.
- `agents/combat.py`: no fim do combate, a detecção R4(b) chama `law.register_crime`. O
  spawn de `law_enforcement` usa `guard_pool`/`hunter_pool` pelo handoff de
  `encounter_handoff` (`agents/storyteller.py:110`).
- `services/combat_origin.py`: `ORIGINS` ganha `law_enforcement`, e `from_encounter` mapeia
  `reason in {"bounty_hunters","law_confrontation"}`.
- `world_utils.py`: `check_encounter` aceita `law_hint: dict | None = None` e o devolve como
  razão `bounty_hunters` na posição de R18. Com `None`, o comportamento é idêntico.
- `agents/router.py`: `_law_gate` determinístico antes da classificação LLM, só quando
  `law_state.confrontation` existe e o modo é `on`.
- `agents/turn_finalizer.py`: chama `law.turn_updates(state)` logo depois do bloco da
  SPEC-215 (`:32-45`), com o mesmo `try/except` de "nunca derruba o turno".
- `mock_llm.py`: `_story_update` (`:260`) e a resposta de NPC emitem `crime_claims` só com
  léxico explícito ("roubo a bolsa", "furto", "esfaqueio o mercador"). A ideia é que os 14
  perfis atuais não mudem (verificado na etapa 10).
- `scripts/validate_content.py`: chama `lint_law_codes`.

### 3.3 Formato de `data/law_codes.json` (exemplo com ids reais)

```json
{
  "version": 1,
  "jurisdictions": {
    "nova_arcadia": "codigo_de_ferro",
    "na_anel_dourado": "codigo_de_ferro",
    "na_anel_ferro": "codigo_de_ferro",
    "skallgard": "lei_dos_clas",
    "sk_salao_do_jarl": "lei_dos_clas",
    "pr_vaelorn": "lei_de_vaelorn",
    "pr_solvhen": "lei_de_solvhen",
    "sx_cidades_hospedeiros": "colmeia"
  },
  "codes": {
    "codigo_de_ferro": {
      "name": "Código de Ferro",
      "authority_faction_id": "legiao_ferro",
      "prison_location_id": "na_anel_ferro",
      "witness_mode": "individual",
      "covert_possible": true,
      "punishment": "prisao",
      "bribe_allowed": false,
      "report_chance": 0.8,
      "report_delay_periods": 1,
      "courier_delay_periods": 1,
      "patrol_density": {"default": 0.5, "na_anel_dourado": 0.8, "na_anel_ferro": 0.7},
      "decay_per_day": 3,
      "max_talk_turns": 2,
      "hunter_radius_periods": 4,
      "hunter_delay_periods": 5,
      "guard_pool": ["enemy_soldado_legiao_ferro"],
      "hunter_pool": ["enemy_bandido_capitao", "enemy_bandido"],
      "bounty_by_enemy": {"enemy_bandido": 15, "enemy_bandido_capitao": 60},
      "crimes": {
        "furto":            {"severity": 15, "fine": 40,   "sentence_days": 3},
        "dano_propriedade": {"severity": 10, "fine": 30,   "sentence_days": 2},
        "agressao":         {"severity": 30, "fine": 90,   "sentence_days": 6},
        "homicidio":        {"severity": 70, "fine": null, "sentence_days": 30, "capital": true},
        "resistencia":      {"severity": 25, "fine": 120,  "sentence_days": 8},
        "evasao":           {"severity": 15, "fine": 60,   "sentence_days": 4},
        "magia_ilegal":     {"enabled": false, "severity": 60, "fine": null, "sentence_days": 30, "capital": true}
      },
      "victim_multiplier": {"legiao_ferro": 2.0}
    },
    "colmeia": {
      "name": "Consenso da Colmeia",
      "authority_faction_id": "colmeia_hospedeiros",
      "prison_location_id": null,
      "witness_mode": "colmeia",
      "covert_possible": false,
      "punishment": "expulsao",
      "...": "demais campos como acima, [BALANCEAR]"
    }
  }
}
```

`victim_multiplier` aplica a regra "matar um legionário traz a cidade inteira atrás de você"
(`creatures.txt:742`). Com vítima da fação-autoridade, `severity × 2`.

Ressalva: `enemy_soldado_legiao_ferro` é **Elite** (`data/bestiary.json:202-206`), e o
bestiário não tem caçador de recompensa próprio nem Inquisidor (o grafo tem
`mon_inquisidores_do_codigo`, `data/graph/entities.json:4663`, sem ficha). Os pools usam
fichas que já existem, e uma ficha nova de caçador fica para D7.

### 3.4 Schemas (`state.py`)

```python
class CrimeRecord(TypedDict):
    crime_id: str  # sha256(game_id|turn|type|location_id)[:16]
    crime_type: str  # catálogo R5
    jurisdiction_id: str  # code_id
    location_id: str
    clock: int  # npc_knowledge.clock_index
    turn: int
    victim_ref: str  # "" | "local" | holder id "npc:<id>"
    victim_faction_id: str  # "" se não houver
    severity: int  # já multiplicada
    witnesses: list[str]  # holder ids + "patrol:<loc>"
    covert: bool
    source: str  # "llm_claim" | "engine"
    status: str  # "unwitnessed" | "pending_report" | "reported" | "dropped" | "resolved"


class LawReport(TypedDict):
    report_id: str  # sha256(crime_id|reporter)[:16]
    crime_id: str
    jurisdiction_id: str
    reporter: str  # holder id ou "patrol:<loc>"
    due_clock: int
    status: str  # "queued" | "delivered" | "dropped"


class Wanted(TypedDict):
    jurisdiction_id: str
    heat: int  # 0..100, valor no last_crime_clock
    bounty: int  # ouro
    capital: bool
    last_crime_clock: int
    known_at: dict[str, int]  # location_id -> clock em que a notícia chega
    signals_shown: list[str]  # ids de sinal já exibidos (teto 32)
    hunters_last_clock: int  # -1 = nunca


class LawConfrontation(TypedDict):
    jurisdiction_id: str
    location_id: str
    started_turn: int
    talk_turns: int
    reason: str  # "patrol_witness" | "recognized" | "self_report"


class LawServed(TypedDict):
    jurisdiction_id: str
    mode: str  # "fine" | "sentence" | "expulsao"
    turn: int
    crime_ids: list[str]


class LawState(TypedDict, total=False):
    version: int  # 1
    crimes: list[CrimeRecord]  # ≤100
    reports: list[LawReport]  # ≤100
    wanted: dict[str, Wanted]
    confrontation: LawConfrontation | None
    served: list[LawServed]  # ≤20
```

Schema do LLM (em `agents/storyteller.py`, reaproveitado em `agents/npc.py`):

```python
class CrimeClaim(BaseModel):
    crime_type: Literal["furto", "agressao", "homicidio", "dano_propriedade", "magia_ilegal"]
    victim: str = Field(
        default="",
        description="Nome EXATO de quem está na cena, 'local' para propriedade, ou vazio.",
    )
    covert: bool = Field(default=False, description="True só se a ação foi às escondidas.")
```

`crime_type` inválido derruba só o item (validador `mode="before"` que descarta, no padrão
SPEC-045 citado em `agents/npc.py:162-164`), nunca a resposta inteira.

### 3.5 Assinaturas públicas (`services/law.py`)

```python
def mode() -> str  # RPG_LAW: off|shadow|on
def normalize_law(raw: Any) -> LawState
def patrol_present(state: dict, location_id: str, clock: int) -> bool
def register_crime(state: dict, cand: CrimeCandidate) -> tuple[dict, CrimeRecord | None, str]  # (updates, record, reason)
def turn_updates(state: dict) -> dict  # entrega relatos vencidos, aplica R12, emite eventos, abre confronto
def effective_heat(w: Wanted, clock: int) -> int
def level(w: Wanted | None, clock: int) -> str  # limpo|suspeito|procurado|cacado
def recognition_check(state: dict, location_id: str, clock: int) -> bool
def signals_for(state: dict, *, for_npc: str | None = None) -> list[str]
def hunter_encounter(state: dict, location_id: str, clock: int) -> dict | None  # {hint, flavor, reason:"bounty_hunters", enemy_id, eff_danger}
def resolve_choice(state: dict, text: str) -> dict  # gate do router: pagar|render|fugir|atacar|falar
def resolve_fine(state: dict) -> tuple[dict, bool, str]
def serve_sentence(state: dict) -> dict
def prisoner_bounty(state: dict, prisoner: PrisonerRef, location_id: str) -> int
def deliver_prisoner(state: dict, prisoner: PrisonerRef, location_id: str) -> tuple[dict, LawReceipt]
def daily_tick(state: dict, day: int) -> dict  # gancho para SPEC-302; hoje no-op além de podar
```

```python
class CrimeCandidate(TypedDict):
    crime_type: str
    victim_ref: str
    covert: bool
    source: str
    location_id: str
    turn: int
    player_text: str


class PrisonerRef(TypedDict):
    prisoner_id: str
    name: str
    enemy_id: str
    faction_id: str
    alive: bool


class LawReceipt(TypedDict):
    ok: bool
    reason: str
    gold: int
    jurisdiction_id: str
```

### 3.6 Fluxo de um turno (modo `on`)

1. **Início da cena:** `patrol_present` define o fato de patrulha, que vai para o prompt.
   Ao entrar em local da jurisdição com a notícia já chegada, `recognition_check` pode abrir
   o confronto.
2. **Nó do turno:**
   - storyteller/npc devolvem `crime_claims` → validação R6 → `register_crime` (testemunhas
     R8–R10, relatos R11 na fila);
   - o combate encerrado com `player_provoked` faz o mesmo pela fonte de motor.
3. **`turn_finalizer`:** `law.turn_updates`:
   - entrega relatos vencidos, aplicando R12;
   - atualiza `Wanted` e `known_at` e chama `_fame_bridge`;
   - enfileira `crime_witnessed`/`law_resolved` em `pending_world_events` com
     `source="law"`;
   - abre o confronto se uma patrulha testemunhou.
4. **Turno seguinte:** com confronto, o router passa antes pelo `_law_gate` (R19).

### 3.7 Contexto do narrador (não onisciência)

O bloco `<LEI_NA_CENA>` tem só frases de cena: o fato da patrulha (R9), o confronto (R19) e
os sinais (R16). Sem confronto, sem patrulha e sem sinal, o bloco nem aparece (zero token).
Proibido no prompt: `heat`, `bounty`, nível, lista de crimes e nomes de testemunhas.

### 3.8 Telemetria

O log `rpg.law` registra contagens (crimes, relatos entregues/descartados, sinais,
confrontos e caçadores), sem texto do jogador. No playtest, as invariantes novas em
`playtest/invariants.py` são:

- `law.no_leak`: `format_response(...).model_dump()` não tem as chaves
  `law_state`/`heat`/`bounty`/`wanted`;
- `law.report_needs_witness`: todo relato tem um `reporter` que estava em `witnesses`;
- `law.heat_bounds`: `heat` fica entre 0 e 100.

### 3.9 Dependência da SPEC-298 (contrato mínimo)

A SPEC-298 ainda está em `draft` (é o template). Esta spec precisa dela só no que segue.
Os nomes finais são definidos lá, e a adaptação acontece em **um** ponto, `law._fame_bridge`:

- **leitura:** a fama do jogador num local, como inteiro assinado ou como magnitude
  (`location_fame(state, location_id) -> int`). A lei usa só `abs()`;
- **escrita:** um escritor com motivo (`apply_location_fame(state, location_id, delta,
  reason) -> (updates, event | None)`). A lei chama com delta negativo
  `[BALANCEAR]`/`reason="crime:<tipo>"` só no local do crime, na entrega do 1º relato.

Se a SPEC-298 pousar com outro formato, só `_fame_bridge` e seu teste mudam. Até ela estar
`done`, as etapas 1–4 e 6–9 podem ser implementadas com o adaptador devolvendo 0. A etapa 5
(R15) só fecha com a SPEC-298 `done`. Decisão D8: ordem.

## 4. Plano passo a passo

Toda etapa: testes primeiro, `RPG_LAW` explícito nos testes. Ao fim de cada etapa, os
testes da etapa e os de SPEC-215 (`tests/test_spec215*`) ficam verdes. Cada etapa é
pousável sozinha atrás da flag.

### Etapa 1 — Dados e lint

1. **Testes** (`test_spec299_law_codes.py`):
   - `test_every_jurisdiction_location_exists`;
   - `test_authority_is_faction` (`legiao_ferro`, `colmeia_hospedeiros`…);
   - `test_pools_exist_in_bestiary`;
   - `test_prison_inside_jurisdiction`;
   - `test_unknown_location_is_lawless` (`brekmar`, `na_anel_lama`, `pantano_melancolia` →
     `None`);
   - `test_lint_flags_bad_crime_type`;
   - `test_missing_file_makes_law_inert`.
2. **Implementação:** `data/law_codes.json`, `services/law_codes.py` e hook em
   `scripts/validate_content.py`.

### Etapa 2 — Estado, flag e save

1. **Testes:**
   - `test_normalize_law_empty_on_old_save` (save sem a chave carrega);
   - `test_roundtrip_preserves_law_state`;
   - `test_caps_fifo` (R28);
   - `test_mode_off_writes_nothing` (o turno com `RPG_LAW=off` não cria `law_state`);
   - `test_no_schema_version_bump`.
2. **Implementação:** TypedDicts em `state.py`, `normalize_law`, hook em `persistence.py` e
   `law.mode()`.

### Etapa 3 — Classificação de crime (LLM + motor) e validador

1. **Testes** (`test_spec299_crime_claims.py`):
   - `test_claim_without_lexical_support_rejected` (narração diz "você furta", ação foi
     "converso com o mercador" → recusa `sem_suporte_na_acao`);
   - `test_claim_victim_must_be_in_scene`;
   - `test_quarantine_ignores_claims`;
   - `test_invalid_crime_type_drops_item_not_response`;
   - `test_fallback_aimessage_no_crime` (guard);
   - `test_one_claim_per_type_per_turn`;
   - `test_lawless_location_no_record` (Brekmar);
   - `test_engine_player_provoked_vs_neutral_is_agressao`;
   - `test_engine_travel_encounter_is_not_crime` (autodefesa);
   - `test_npc_killed_in_jurisdiction_is_homicidio`;
   - `test_magia_ilegal_disabled_by_default`.
2. **Implementação:** `CrimeClaim`, campos em `StoryUpdate`/`NPCResponse`,
   `law.register_crime` (parte de validação) e detecção em `agents/combat.py`.

### Etapa 4 — Testemunhas, furtividade, relato com atraso, eventos

1. **Testes** (`test_spec299_witness_report.py`):
   - `test_party_is_not_a_reporting_witness`;
   - `test_no_witness_no_report` (status `unwitnessed`, `Wanted` intocado);
   - `test_patrol_only_if_shown_in_scene` (R9: o mesmo seed decide o fato de cena e a
     testemunha);
   - `test_covert_check_deterministic` (mesma seed → mesmo resultado; colmeia ignora
     `covert`);
   - `test_civilian_report_delay`;
   - `test_dead_witness_report_dropped` (R12);
   - `test_spread_delay_uses_world_distance`;
   - `test_crime_witnessed_requires_source_law` (proposta do LLM recusada);
   - `test_npc_knowledge_propagates_crime_when_on` (SPEC-215 `on`);
   - `test_law_independent_of_npc_knowledge_off`.
2. **Implementação:** `patrol_present`, testemunhas, `turn_updates` (fila + entrega),
   `EventType`/validadores, `SUBJECT_PARAMS` e hook no `turn_finalizer`.

### Etapa 5 — Notoriedade, decaimento e fama (exige SPEC-298 `done` para fechar R15)

1. **Testes** (`test_spec299_wanted_signals.py`, parte 1):
   - `test_heat_levels_thresholds`;
   - `test_lazy_decay_pure` (mesmo valor sem tick);
   - `test_capital_never_decays`;
   - `test_victim_multiplier_legion`;
   - `test_recognition_uses_fame_magnitude` (adaptador fake);
   - `test_fame_written_once_on_first_report`;
   - `test_fame_bridge_absent_returns_zero`.
2. **Implementação:** `effective_heat`, `level`, `recognition_check` e `_fame_bridge`.

### Etapa 6 — Sinais e não vazamento

1. **Testes** (parte 2):
   - `test_signals_only_where_news_arrived`;
   - `test_poster_text_has_no_number`;
   - `test_npc_warning_needs_relationship`;
   - `test_signals_capped_per_scene`;
   - `test_prompt_block_absent_when_clean` (zero token);
   - `test_prompt_never_contains_heat_or_bounty`;
   - `test_game_response_has_no_law_keys` (`api.format_response`);
   - `test_codex_and_dossiers_unchanged`.
2. **Implementação:** `signals_for`, bloco `<LEI_NA_CENA>` no storyteller e no contexto do
   `npc_actor`.

### Etapa 7 — Confronto, multa, pena, fuga (Opus)

1. **Testes** (`test_spec299_confrontation.py`):
   - `test_patrol_witness_opens_confrontation`;
   - `test_gate_pay_clears_heat_and_debits_gold`;
   - `test_pay_insufficient_gold_keeps_confrontation`;
   - `test_capital_crime_has_no_fine`;
   - `test_surrender_advances_clock_and_moves_to_prison`;
   - `test_surrender_party_waits_at_prison`;
   - `test_flee_adds_evasao_and_starts_chase`;
   - `test_attack_adds_resistencia_and_spawns_guards` (origin `law_enforcement`);
   - `test_talk_turns_then_arrest_attempt`;
   - `test_colmeia_expels_instead_of_prison`;
   - `test_leaving_jurisdiction_ends_confrontation`;
   - `test_gate_inactive_without_confrontation` (router idêntico).
2. **Implementação:** `_law_gate` em `agents/router.py`, `resolve_choice`, `resolve_fine`,
   `serve_sentence` e `combat_origin.law_enforcement`.

### Etapa 8 — Caçadores de recompensa (Opus)

1. **Testes** (`test_spec299_hunters.py`):
   - `test_hunters_need_cacado_and_prior_signal`;
   - `test_hunters_respect_global_cooldown`;
   - `test_hunters_priority_after_reinforcements_before_ruler`;
   - `test_hunters_radius_world_distance`;
   - `test_hunter_strength_ignores_player_level` (nível 1 e 8 → mesmo `eff_danger`);
   - `test_check_encounter_identical_without_law_hint`;
   - `test_hunter_origin_maps_to_law_enforcement`.
2. **Implementação:** `law.hunter_encounter`, parâmetro `law_hint` em `check_encounter` e a
   chamada em `agents/storyteller.py:651`.

### Etapa 9 — Interface de prisioneiro

1. **Testes** (`test_spec299_prisoner_api.py`):
   - `test_prisoner_bounty_zero_lawless`;
   - `test_deliver_pays_bounty_by_enemy`;
   - `test_deliver_dead_prisoner_rejected`;
   - `test_deliver_is_idempotent_by_prisoner_id`;
   - `test_no_graph_caller` (grep: nenhum nó chama `deliver_prisoner`).
2. **Implementação:** `prisoner_bounty`, `deliver_prisoner` e os TypedDicts.

### Etapa 10 — Playtest, medição e smoke

1. Invariantes `law.*` (§3.8) e perfil `criminoso`.
2. **Medição (MockLLM):**
   - os 14 perfis × 50 turnos com `RPG_LAW=on` e `RPG_LAW=off`. Os perfis sem crime aceito
     ficam idênticos ao `main` (R27). Se algum mudar, registrar qual e por quê;
   - SPEC-285: playtest `combate` seeds 21–32 (200 turnos) e matriz SPEC-056 sem regressão
     (M1 ≤ 0,564; mediana da 1ª queda ≥ 20);
   - `criminoso` seeds 21–26 × 100 turnos: a contagem de crimes, relatos, sinais, confrontos
     e caçadores fica numa tabela na §8.
3. Smoke real (§6). Ruff nos arquivos tocados. A suíte completa fica com o coordenador no
   pouso.

## 5. Critérios de aceite

- [ ] R1/R2: `law_codes.json` com lint verde, 0 erro em `scripts/validate_content.py`
- [ ] R4–R7: claims validados, recusas logadas, guard de FallbackLLM testado
- [ ] R8–R13: sem testemunha não há relato; party não relata; testemunha morta não relata;
  atraso geográfico testado; `crime_witnessed` só com `source="law"`
- [ ] R14–R16: níveis, decaimento preguiçoso, `capital` e sinais só onde a notícia chegou
- [ ] R17: `GameResponse`, codex, dossiês e prompt sem estado da lei (testes)
- [ ] R18: caçadores só após sinal, respeitando cooldown e sem escalar com o nível
- [ ] R19–R22: confronto com as 4 saídas + conversa; multa, pena e expulsão testadas
- [ ] R23: interface de prisioneiro testada, sem chamador no grafo
- [ ] R24/R25: `off` byte a byte; save antigo carrega; round-trip preserva `law_state`
- [ ] R26: mesmas seeds → mesmos resultados (teste de reprodução)
- [ ] R27: os 14 perfis sem crime ficam idênticos ao `main`; metas da SPEC-285 mantidas
- [ ] Guard de FallbackLLM em todo `with_structured_output` tocado (`StoryUpdate`,
  `NPCResponse`)
- [ ] Smoke real (§6) executado e registrado na §8
- [ ] Revisão independente Opus sem P0/P1
- [ ] `uv run pytest` verde (suíte completa offline, `-n auto`, no pouso)

## 6. Smoke test com LLM real

Contexto: DeepSeek primário, `RPG_LAW=on`, `RPG_NPC_KNOWLEDGE=on`, save novo começando em
`nova_arcadia`. Custo ≤ US$ 0,10, dentro do teto de US$ 3/dia. O objetivo é pegar bug de
mapeamento do `CrimeClaim` que o MockLLM esconde.

1. "Furto a bolsa do mercador enquanto ele olha para o outro lado" com mercador em cena →
   `crime_claims=[furto, victim=<mercador>, covert=true]` chega como instância. Conferir no
   save: `law_state.crimes[-1]` com testemunhas ou `unwitnessed`. A narração não cita
   "procurado".
2. Controle: "Pago ao mercador pela maçã e guardo na bolsa" → `crime_claims=[]`. Se vier um
   claim, o léxico (R6.4) tem de recusar, e a recusa aparece em `event_rejections`.
3. "Dou um soco no legionário" com patrulha na cena → `agressao` com multiplicador da
   Legião. No turno seguinte, o narrador descreve os guardas bloqueando, sem números.
   Responder "pago a multa" → ouro debitado e `heat` zerado.
4. Ir a `brekmar` e "roubo a carteira de um pirata" → nenhum registro de lei (sem jurisdição).
5. Voltar a `nova_arcadia` após `homicidio` simulado (fixture de save com `cacado`) e viajar
   → aparece o sinal `perguntaram_por_voce` antes de qualquer encontro `bounty_hunters`.

Registrar na §8: modelo/provedor, se `crime_claims` veio como instância (campo e tipo) e
trechos curtos da narração (sem PII).

## 7. Riscos & compatibilidade

- **Saves antigos:** `law_state` ausente → vazio (R25), sem bump de schema. Em `off`, nada é
  escrito.
- **MockLLM/FallbackLLM:**
  - o mock só emite claims com léxico explícito; os perfis atuais não devem mudar, e a etapa
    10 verifica isso;
  - o `FallbackLLM` devolve `AIMessage`, o que dá zero claim pelo guard;
  - o campo novo no schema grande do `StoryUpdate` pode ser omitido pelo provider (smoke
    2026-07-05, `agents/storyteller.py:51-52`). Por isso o default é `[]`.
- **Falso positivo do narrador:** o risco maior é o jogador ser punido por algo que não
  tentou. O gate lexical (R6.4) é conservador de propósito: prefere deixar um crime passar
  a acusar. O smoke 2 mede isso.
- **Letalidade:** o Soldado da Legião é Elite, e confronto/caçador acrescentam combates só
  para quem comete crime. R27 isola o efeito, e as metas da SPEC-285 são medidas.
  O `hunter_pool` mistura `enemy_bandido` (Lacaio, `data/bestiary.json:5184-5185`) com
  `enemy_bandido_capitao` (Elite, `:3828-3830`). A faixa de preço escolhe a categoria
  (Lacaio em `procurado` baixo, Capitão só em `cacado` com `capital`) `[BALANCEAR]`. A força
  vem do preço pela cabeça, não do nível.
- **Quota/latência:** zero chamada LLM nova. Os campos novos vão nos schemas existentes, com
  poucos tokens a mais no prompt. O bloco `<LEI_NA_CENA>` só existe quando há algo.
- **Router (Jev primário no staging):** o `_law_gate` roda antes do classificador e só com
  confronto ativo. Sem confronto, o router fica idêntico (teste da etapa 7).
- **Ownership:** `law_state` tem um único escritor, `services/law.py`. O ledger da SPEC-215
  continua com dono único (`npc_knowledge.py:3`): a lei só acrescenta um tipo em
  `SUBJECT_PARAMS`.
- **Dado curado incompleto (Skallgard, Vaelorn, Solvhen):** a lore é rasa. Os valores são
  propostos e marcados `[BALANCEAR]` para o dono revisar (D1).

## 8. Evidência

(preenchido na implementação, 2026-10-24)

**Desvios da spec (registrados no mesmo commit):**

- **SPEC-298 já `done`:** `law._fame_bridge` usa `reputation.fame_at` (leitura, `max(renown, infamy)`) e o novo escritor público `reputation.add_location_fame` (idempotente por `crime:<tipo>:<crime_id>`, infâmia `FAME_DELTA_INFAMY`). Etapa 5 (R15) fechada.
- **Decisões do dono (23/10):** `magia_ilegal` LIGADA no Código de Ferro (multa 150 / 10 dias; isenta em combate e com licença; `law.buy_license` é o gancho de custo para a SPEC-301, sem chamador no grafo). Prisão longa (pena ≥ `prison_phase_days`=15) deixa o jogador PRESO (`confrontation.reason="imprisoned"`) com saídas: esperar, subornar, fugir (2d10+Agilidade ≥ `escape_dc`) ou resgate por companheiro que esperava na prisão. Suborno (D6) também no confronto: custo = multa × `bribe_multiplier` 2,0 (capital: `bribe_capital_gold`), recusado se a vítima era da autoridade; deixa metade do heat. Sem execução nem mutilação.
- `CrimeClaim`/`coerce_crime_claims` moram em `services/structured_outputs.py` (evita import circular storyteller/npc).
- Dado: `data/law_codes.json` aceita bloco `defaults` mesclado em cada código. Tipos `crime_witnessed`/`law_resolved` têm `target_id` = `crime_id` / `code_id`.
- Detecção do motor (R4b) roda no `turn_finalizer` (`law.turn_updates`), não no fim do `combat_node`; idempotente por `instance_id` do combate.
- Reconhecimento ao entrar (R19) roda no fim do turno de chegada (`law_state.last_loc`); o confronto vale no turno seguinte. Texto de viagem durante confronto conta como fuga. Fuga/ataque: combate com `guard_pool`, origem `law_enforcement` (o "combate de fuga" reaproveita a mecânica de fuga do combate existente).
- Fora do que foi feito: resgate de prisioneiro por NPC aliado externo (só companheiro da party em espera); wiring de uma ação de jogador "comprar licença"; execução (vetada).
- Perfil `criminoso` entra em `PROFILES` (15 perfis); invariantes `law.*` em `playtest/invariants.py`.

**Medição (MockLLM):** 14 perfis x 50 turnos seed 21 com `RPG_LAW=off` e `on`: resultado idêntico (turnos, erros, violações, eventos, mortes, ouro, local final). `criminoso` seeds 21-26 x 100 turnos, `on`: 0 erro, 0 violação; crimes 8/14/18/9/18/10 (parte `unwitnessed`), relatos entregues 7/7/7/5/6/5, sinais mostrados 5/6/5/3/4/4, multa paga em 3 das 6 campanhas. Letalidade SPEC-285 (combate 200 turnos, seeds 21-22, off x on): ver hand-back.

**Smoke real (§6):** NÃO executado (sem chave/custo autorizado nesta sessão); pendente para o coordenador.


## Decisões pendentes do dono

- **D1:** mapa de jurisdições e códigos (§3.3/R2), em especial Skallgard, Vaelorn e Solvhen
  (lore rasa) e se o Anel de Lama e a Taverna do Javali ficam mesmo sem lei (refúgio, como
  Korvus em `factions.txt:26`).
- **D2:** `magia_ilegal` sob o Código de Ferro. A lore pune com fogueira
  (`locations.txt:25`), mas o jogador usa Éter. Fica desligada (proposta) ou ligada só para
  magia **fora de combate** no Anel de Ferro?
- **D3:** a lei tem relato próprio, independente de `RPG_NPC_KNOWLEDGE` (proposta), ou
  exige a SPEC-215 em `on`?
- **D4:** o cartaz pode mostrar valor ("200 coroas") ou só faixa vaga ("uma recompensa
  gorda", proposta)?
- **D5:** pena para crime capital. Proposta: Oubliette por 30 dias, sem morte nem
  mutilação. Alternativas: execução (game over telegrafado) ou ferimento permanente
  ("dedos/língua").
- **D6:** suborno entra (lore: guardas subornáveis, Inquisidores não) ou fica para depois
  (proposta)?
- **D7:** criar ficha de "Caçador de Recompensa"/Inquisidor no bestiário (via gerador)
  ou reusar Bandido/Capitão (proposta)?
- **D8:** ordem e dependência. Proposta: a SPEC-298 pousa antes; até lá, as etapas 1–4 e
  6–9 avançam com o adaptador de fama em 0.
- **D9:** default de `RPG_LAW` no staging depois do pouso: `shadow` por 1 playtest e depois
  `on` (proposta, igual à SPEC-215).


## Decisões do dono (2026-10-23)

Todas as decisões abertas desta spec seguem o **default recomendado pelo autor**, exceto/explicitando:

- D2 (substitui a proposta): `magia_ilegal` LIGADA no Código de Ferro, com REGISTRO — usar Éter em público sem licença é crime testemunhado; licença obtida por custo/patente (SPEC-301) ou usar escondido.
- D5: crime grave = prisão (Oubliette, dias de jogo passam) com saídas: fuga, resgate ou suborno. Sem execução nem mutilação.
- D6: suborno entra como saída mínima da prisão/confronto (detalhe [BALANCEAR]).
