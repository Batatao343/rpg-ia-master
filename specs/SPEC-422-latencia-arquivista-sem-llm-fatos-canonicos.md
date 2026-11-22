# SPEC-422 — latencia-arquivista-sem-llm-fatos-canonicos

> **Status:** `in-progress` (aprovada pelo dono em 13/11; código pousado em 22/11 com a flag `off`; revisão Sol APPROVED na rodada 2; a promoção a `on` depende de R12(b), `shadow` no staging e smoke §6)
> **Criada:** 2026-11-13 · **Atualizada:** 2026-11-22
> **Depende de:** SPEC-318 (`done`, política `lean` e marca `archive_low`), SPEC-234 (`done`, ledger de memória e retry), SPEC-309 (`done`, fatos do dia percebido). Para **pousar com `off`/`shadow`**: nada além disso. Para **promover a `on`**: a spec de autoria de eval de §2 R12 (`EVAL_AUTHORING_REQUIRED`).
> **Desbloqueia:** follow-up opcional "resumo de conversa de NPC sem IA" (só se o dono quiser; ver §8 D2)
> **Risco:** `alto` (estado e memória da sessão: `narrative_summary`, `memory_facts`, crônica; `spec-reviewer` obrigatório)
> **Requer:** staging (fase `shadow` e medição A/B de §6) · nada de web
> **Domínios de revisão:** persistência, llm-structured (guia: `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md`)
> **Evidência:** `test_descanso_nao_chama_llm_do_arquivista` (ScriptedLLM conta 1 chamada `MemoryUpdate` hoje, 0 com `on`, e o registro está no estado) + oráculo de equivalência `test_rejeicao_sem_conflito_igual_ao_llm` (saída com `on` idêntica à saída com LLM roteirizado) + `off` byte a byte igual ao HEAD.
> **EXECUTOR_MODEL:** `Sol` (estado, memória, gate do arquivista) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` para a promoção a `on` (o dataset atual não exercita o arquivista; ver R12). Não bloqueia o pouso com `off`.

---

## 1. Contexto & Objetivo

Na medição de 13/11 o arquivista foi 18 % do tempo de servidor, com 4,0 s de mediana, em 20 de 60
turnos (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:41`). Nesses turnos o `state` sai
~4,4 s depois do texto e o jogador não pode agir (`…-medicao-2026-11-13.md:53`). O dono aprovou em
13/11 "resumo de memória sem IA nos turnos em que os fatos já são conhecidos, como o descanso",
com a condição "só passa se o teste de memória não piorar". Qualidade acima de velocidade.

Contagem refeita a partir de `docs/auditorias/latencia-l0-2026-11-13/resultado.json` (campo
`server.phase_ms.archivist` > 3 s, `llm_by_phase.archivist = 1`): os 20 turnos são **8 descansos**
(4011, 4248, 4029, 3721, 4133, 4116, 3658, 3896 ms; mediana 4,02 s), **8 falas com `npc_actor`**,
**3 cenas** e **1 viagem para outra região**. Exemplo de descanso: sessão 1, turno 11, texto completo
aos 5,4 s e `state` aos 9,75 s (`resultado.json:917-918`). A chamada é SMART, ~US$ 0,0018
(`resultado.json:962-964`).

Esta spec troca a chamada do LLM por um registro determinístico em **dois** tipos de turno, numa
lista fechada (R1): o descanso sem gancho e o turno em que a resposta do LLM já é descartada pelo
próprio código. O resto continua pagando o LLM, com o motivo em §2 "Fora de escopo". Princípio:
"mecânica é Python, a IA só narra" (`AGENTS.md` § Convenções). O registro gerado passa pelo mesmo
caminho de gravação de hoje, então nenhum writer novo de estado aparece.

### O que o código faz hoje (confirmado no source)

- **Gate.** `_should_archive_legacy` (`agents/archivist.py:229-246`) dispara com `archive_due`,
  `conflict_summary`, `memory_fact_policy == "canonical_only"`, `pending_npc_memory`, fatos pendentes
  na janela de retry ou a cadência `_ARCHIVE_EVERY = 10` (`:138`). Em `lean` (staging,
  `config/flags.yaml:44-48`), `_lean_keeps` (`:249-261`) mantém `conflict_summary`,
  `memory_canonical_facts`, `archive_due` **sem** `archive_low == turno`, a janela de retry e a cadência.
  Quando pula, `_lean_skip_updates` (`:552-569`) drena a fila de memória de NPC sem LLM.
- **Por que todo descanso paga.** O narrador marca `archive_due` em todo descanso
  (`agents/storyteller.py:2836-2838`) e a marca de baixo valor `archive_low` exclui o descanso
  (`t.rested_player is None`, `storyteller.py:2941-2951`). Logo `_lean_keeps` retorna `True` em
  `archivist.py:256`. Na virada de dia com algo percebido, o narrador também grava
  `memory_canonical_facts` (`storyteller.py:1602-1611`), e isso basta para `lean` manter
  (`archivist.py:254`). Correção ao achado B6 (`docs/auditorias/latencia-turno-2026-11-12.md:182`):
  `lean` **não** pula o turno cujo único gatilho é "fato canônico". Ele mantém.
- **Por que 8 de 10 falas com NPC já criado pagam.** O `npc_actor` sempre marca
  `archive_due: True` e `memory_fact_policy: "canonical_only"` (`agents/npc.py:1482-1485`). A marca
  `archive_low` só sai quando a fala não teve consequência nenhuma: sem aviso de relação, sem traço
  revelado, sem mudança de `faction_intel`, sem chave fora de `_CHAT_BASE_KEYS` e sem aviso de
  reputação (`npc.py:1589-1600`, `:599-614`). A causa mais provável é o `relationship_change` do LLM.
  Ele passa por `reputation.apply_npc_delta` (`npc.py:1327-1337`), e qualquer delta ≠ 0 gera
  `rel_notice` (`services/reputation.py:220-227`). Também contam `_law_scene_updates`
  (`npc.py:1155`, `:1574`) e a entrega de missão (`npc.py:1507-1510`). **A L0 não registra o gatilho**
  e o código não diz qual dominou nos 8 turnos, então R9 passa a registrá-lo. Nesses turnos o LLM só
  alimenta o `narrative_summary`: com `canonical_only` os fatos livres não são gravados
  (`archivist.py:1130-1137`) e a prosa da crônica é suprimida (`:1225`).
- **O que a saída alimenta.** `MemoryUpdate` (`archivist.py:42-52`) tem três campos:
  - `new_summary` → `narrative_summary` (`:1199`), lido no turno seguinte pelo `context_builder` como
    `[RESUMO NARRATIVO | speculative]` (`services/context_builder.py:956-960`) e pelas assinaturas de
    segredo (`services/secret_signatures.py:101`);
  - `important_facts` → registros `inference` no ledger `memory_facts` e na memória vetorial da sessão
    (`archivist.py:1121-1138`), lidos pelo `context_builder` (`:962-980`);
  - `chronicle_entry` → entrada `prose` da crônica (`:1224-1228`).

  Fatos canônicos (eventos percebidos, `memory_canonical_facts`, conflito) **já são determinísticos**:
  `_event_memory_records` (`:182-214`) e `authoritative_records` (`:851-865`) não dependem do LLM.
  A memória de NPC é drenada antes da chamada (`:720-734`). O narrador só vê `messages[-3:]`
  (`storyteller.py:2322`). Depois de um turno, o que o narrador inventou só sobrevive no resumo.
- **Resposta descartada.** Se `suppress_free_facts` vale (`:871-873`) e não há `conflict_summary`, o
  ramo de sucesso ignora a resposta inteira: o resumo é o anterior (`:1150-1151`), os fatos livres
  ficam vazios (`:1128`) e a crônica é suprimida (`:1225`). O LLM é pago e a resposta vai fora. Na L0,
  a cena da sessão 4, turno 6, pagou 4,36 s (`resultado.json:5782`) com `narrative_rejected.item = 3`
  (`:5840-5842`).
- **Tier e segunda chamada.** O tier é SMART (`archivist.py:938`). A segunda chamada possível é o
  fallback em texto puro quando o structured output não devolve `MemoryUpdate`. Ela usa FAST em
  `lean` (`:1017-1028`) e é pulada quando `suppress_free_facts` vale sem conflito (`:1017-1019`).
  O arquivista não tem reforço de idioma; esse reforço é do replan (SPEC-318 R4). Trocar o tier não
  ajuda: os tiers usam o mesmo modelo primário (`latencia-turno-2026-11-12.md:184`).
- **`extractive_digest`** (`services/chronicle_compression.py:51-74`) resume um **capítulo** da
  crônica: junta as 2 primeiras e as 2 últimas entradas de prosa. Não serve de base. Ele não vê
  fatos do turno, local nem relógio, e num descanso a entrada nova seria justamente a que falta. Não é
  reaproveitado.

## 2. Requisitos

- **R1 — Lista fechada de tipos de turno com registro determinístico.** Com `RPG_ARCHIVE_RECORD=on`, o
  arquivista não chama o LLM (nem o SMART, nem o fallback FAST) em exatamente dois casos. Qualquer
  outro turno segue como hoje.

  | Tipo | Quando (todas as condições) | Fatos que o motor já tem | Registro gerado | O que se perde frente ao LLM |
  |---|---|---|---|---|
  | **T0 — resposta descartada** | o gate manteve (`_should_archive` `True`); `suppress_free_facts` vale (`archivist.py:871-873`); `conflict_summary` vazio | os mesmos de hoje: eventos percebidos, `memory_canonical_facts`, fila de NPC | o mesmo de hoje no ramo de sucesso: resumo anterior, só registros autoritativos, crônica sem prosa | **nada**: hoje a resposta é ignorada (ver §1). Equivalência exata (I3) |
  | **T1 — descanso sem gancho** | marca `archive_record == {"kind": "rest", "turn": turno}` posta pelo narrador (R3); `conflict_summary` vazio; cadência não vencida (`turno − archivist_last_run < _ARCHIVE_EVERY`) | local atual (`world.current_location_id`/nome), relógio depois do descanso (`clock_label`), descanso bloqueado pelo clima ou não (`storyteller.py:1547`, `:1564-1574`), eventos do motor no turno (já em `event_log`), fatos do dia percebido (`memory_canonical_facts`, SPEC-309) | `narrative_summary` = resumo anterior + uma frase de template (R4); `memory_facts` = só os registros autoritativos (eventos + fatos do dia), como hoje; nenhuma entrada `prose` na crônica (os marcos do `event_processor` continuam) | (a) a cor da prosa do despertar no resumo; (b) os fatos `inference` que o LLM tiraria da narração do descanso; (c) a entrada do menestrel do turno, que o prompt já manda deixar vazia em turno banal (`archivist.py:995-998`). Gancho estruturado (NPC, missão, rumor, evento proposto, beat) **exclui** o turno de T1 (R3), então só se perde gancho que o narrador inventou sem registrar, e esse gancho não existe no estado do mundo |

- **R2 — Caminho único de gravação.** O registro determinístico vira um `MemoryUpdate` montado em
  Python e entra no **mesmo** ramo de sucesso de `_archive_node` (`archivist.py:1117-1233`). Passa pelos
  mesmos saneadores de local, inventário e identidade, por `merged_summary`, `persist_records`,
  `_validate_derived` e pela limpeza de `memory_canonical_facts`/`memory_fact_policy`. O writer de
  `narrative_summary`, `memory_facts` e `chronicle` continua sendo só `agents/archivist.py`
  (`project_index/state_ownership.yaml:18-28`). O módulo novo só **calcula** o registro e a decisão.
- **R3 — Marca do descanso (emissor: narrador).** `storyteller` grava
  `archive_record = {"kind": "rest", "turn": t.turn}` só no caminho feliz
  (`storyteller.py:1417-1426`, não no `_story_exception_fallback`). Também é preciso que **todas**
  estas condições valham:
  1. o descanso rodou (`t.rest_note` não vazio, `storyteller.py:1565`/`:1571`) e não houve viagem
     (`not t.dest`);
  2. nenhum encontro: `_story_roll_encounter` não deixou encontro (emboscada, armadilha, rastro,
     social) e nenhum sinal de fauna foi mostrado (`t._fauna_sign_shown` falso; `storyteller.py:1395-1398`,
     `:1846-1848`, `:1977-2050`);
  3. o herói não morreu (`not t.rested_player.get("dead")`, `storyteller.py:2857`);
  4. nenhum gancho estruturado do narrador: `t.beat_done` falso, `introduced_npcs` vazio
     (`storyteller.py:2660`), `"quests"` fora de `t.updates` (`:2926-2928`), `t.pending_llm_events`
     vazio, nenhum rumor novo gravado por `_apply_proposed_rumors` (`:2939`).

  A marca só é emitida com o flag em `shadow` ou `on`, no mesmo padrão de `archive_low_wanted`
  (`services/latency_flags.py:37-40`). Com `off`, o estado fica idêntico ao HEAD. A marca é
  transitória: vale só no turno carimbado e não é persistida (como `archive_low`, que não está em
  `persistence.py`).
- **R4 — Frase de template do descanso.** `pt-BR`, sem número na superfície, uma frase:
  - descanso normal: `"O herói descansou em {local}; agora é {clock_label} e ele recuperou parte das forças."`
  - descanso bloqueado pelo clima: `"O herói tentou descansar em {local}, mas o clima ({weather}) não deixou; agora é {clock_label}."`

  `{local}` é o nome canônico de `gamedata.get_location(current_location_id)`, com fallback
  `world.current_location`. `{clock_label}` é o mesmo texto do `rest_note`. O novo resumo é
  `compact_summary(f"{resumo_anterior} {frase}")`. **Não acumula:** se o resumo anterior já termina
  com uma frase desse template, ela é trocada pela nova. Dois descansos seguidos deixam uma frase só.
- **R5 — `archivist_last_run`.** T0 grava `archivist_last_run = turno`, como hoje. T1 **não**
  avança `archivist_last_run`: o campo continua dizendo "último resumo escrito pelo LLM". A cadência
  de 10 turnos (`archivist.py:245-246`, `:260-261`) e o invariante `memory.summary_frozen`
  (`playtest/invariants.py:802-819`) seguem medindo a última passada do LLM.
- **R6 — `archive_due` e filas.** Depois de T0 ou T1, `archive_due` vale `bool(pending_memory_facts or
  remaining_npc_memory)`, como no ramo de sucesso (`archivist.py:1231`). `pending_npc_memory` e
  `pending_memory_facts` seguem o fluxo de hoje (drenagem em `:720-734`, retry em `:670-718`). Nenhuma
  entrada fica sem dono.
- **R7 — Flag.** `RPG_ARCHIVE_RECORD=off|shadow|on`, registrada em `config/flags.yaml` (`kind:
  release`, `default: "off"`, `spec: SPEC-422`, `expires: 2027-02-28`) e lida em
  `services/latency_flags.py` com `env_choice` (valor inválido cai em `off`).
  - `off`: estado e chamadas byte a byte iguais ao HEAD (I1).
  - `shadow`: as marcas são emitidas, o LLM é chamado como hoje e o arquivista registra
    `archivist.record_shadow {kind: "rest"|"discarded"|null, would_skip: bool, reason}`. `reason` é a
    primeira condição que excluiu o turno.
  - `on`: T0 e T1 sem LLM.

  Vale com `RPG_ARCHIVE_POLICY` em `legacy` ou `lean`. Com projeção adiada (SPEC-213,
  `projections.deferral_active()`, `archivist.py:343-392`) o flag não tem efeito, porque a marca não é
  persistida até o executor da projeção. Um teste documenta isso.
- **R8 — Telemetria de ganho.** Turno com registro determinístico faz
  `observability.latency.bump("archive_deterministic")` e registra
  `archivist.record {kind}`. O `turn` log já leva `phase_ms.archivist` e `llm_by_phase`, e a L0
  (`docs/auditorias/latencia-l0-2026-11-13/l0_analyze.py`) mede o efeito sem mudança.
- **R9 — Gatilho registrado.** Quando o gate mantém **e a flag está em `shadow` ou `on`**
  (decisão do coordenador, 22/11: com `off` o log fica idêntico ao de hoje e o golden da SPEC-382 não
  muda; a medição de R9 acontece em `shadow`), o arquivista registra
  `archivist.trigger {reasons: [...]}`. Os valores vêm de uma lista fixa: `conflict`,
  `canonical_facts`, `archive_due`, `archive_due_low`, `canonical_only`, `pending_npc_memory`,
  `vector_retry`, `cadence`. Isso responde, na próxima medição, qual gatilho faz a fala com NPC pagar
  (hipótese de §1). Só nomes de gatilho: nenhum texto do jogador ou da narração no log.
- **R10 — Guard de FallbackLLM intacto.** O caminho do LLM continua com `isinstance(result,
  MemoryUpdate)` e `try/except` (`archivist.py:1003-1008`, `:1235-1237`). O registro determinístico
  nunca passa por `with_structured_output`. No MockLLM e no FallbackLLM, `off` e `shadow` se comportam
  como hoje.
- **R11 — Tamanho.** `agents/archivist.py` (1237), `agents/storyteller.py` (3020), `state.py` (1082),
  `_archive_node` (666) e `npc_actor_node` não crescem (`tests/size_budget.json:8-11`, `:43`, `:55`). O
  código novo vai para `services/archive_record.py`. O espaço sai de duas extrações com oráculo de
  equivalência:
  - os três blocos idênticos que montam linhas de rejeição do resumo (`archivist.py:750-783`,
    `:1039-1072`, `:1164-1197`, 34 linhas cada) viram uma função `summary_rejection_rows(turn, loc,
    inv, npc)`;
  - a marca `archive_low` da viagem (`storyteller.py:2940-2951`) e a marca nova saem juntas numa
    função do módulo novo.

  `state.py` não cresce (gate de crescimento de baseline, sem exceção): as marcas transitórias
  `archive_due`/`archive_low`/`archive_record` moram em `state_archive.ArchiveMarks` (módulo raiz sem
  imports do projeto) e `GameState` herda dela; `state.py` fica em 1081 linhas, teto 1082 intacto.
- **R12 — Gate de qualidade (condição do dono).** A promoção a `on` exige duas coisas:
  - **(a)** `evals compare` de `memory_context` (`evals/datasets/regression/memory_context.jsonl`,
    suítes `memory_write`, `memory_retrieval`, `context_grounding`, `generation_boundary`) sem piora em
    nenhum hard gate, com dois `run` da mesma máquina (`off` × `on`), como manda `evals/README.md:46-50`,
    `:69-72`. **Esse dataset não exercita o arquivista.** Ele testa o validador
    `validate_memory_fact`, o ranking e o contexto a partir de estado pronto. Então (a) é necessário,
    mas não prova nada sobre T1.
  - **(b)** `EVAL_AUTHORING_REQUIRED`: uma spec separada do papel de autoria de eval cria uma suíte
    que roda o arquivista em fixtures de descanso: com e sem fatos do dia, bloqueado, com gancho e com
    rejeição. Ela mede (i) todos os fatos canônicos do turno no ledger, (ii) local e relógio
    corretos no resumo, (iii) nenhuma contradição de local, inventário ou identidade e (iv) a
    continuidade do contexto do turno seguinte frente ao caminho com LLM. As fixtures devem incluir
    descanso com fatos do dia e eventos do tick (que ficam só no ledger; o resumo T1 não os cita) e o
    caso de `clock_label` legado "Dia N · Período", que contradiz o "sem número na superfície" de R4.

  Esta spec **não** edita evaluator, expected, dataset, baseline nem exclusões
  (`docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`, `evals/protected-paths.txt`).

### Fora de escopo

- **Fala com NPC (8/20 turnos com arquivista).** Nesses turnos o LLM só escreve o `narrative_summary`
  (§1). Esse resumo carrega o que foi dito na conversa, e o motor só tem a citação literal truncada
  (`npc.py:1343-1350`), não um resumo. Fica no LLM. Resumir a conversa a partir da citação é decisão
  do dono (§8 D2).
- **Cenas (3/20).** O gatilho na L0 não é conhecido (R9 passa a registrar). Uma das três, a da
  sessão 3, turno 10, é a cadência (nenhum arquivista antes nessa sessão). Outra, a da sessão 4,
  turno 6, é T0. A cena carrega a narração livre do turno, o caso típico de informação que o motor
  não tem.
- **Viagem para outra região (1/20).** A chegada a região nova é o marco narrativo em que a crônica
  do menestrel tem valor. Nesse turno o `enrich` (fichas e replan) também custa 4,4–5,1 s
  (`…-medicao-2026-11-13.md:44`), então o ganho seria parcial. Fica no LLM.
- **Turno cuja razão é só a cadência de 10 turnos.** A cadência existe para reescrever o resumo com o
  LLM. Também fica no LLM.
- **Fim de combate, `conflict_summary`, NPC novo, missão nova, morte, emboscada no descanso.**
  Todos ficam no LLM, como hoje.
- **Não reabre:** SPEC-214 (`NO_GO` da memória hierárquica), SPEC-213 (`post_response`; L2 não
  aprovada pelo dono), SPEC-143. Não entram fila de ação, liberação do envio antes do arquivista,
  narração menor nem troca de tier.
- **Não muda:** prompt do arquivista, `_ARCHIVE_EVERY`, política `lean`, `archive_low` da fala de NPC,
  cálculo de `suppress_free_facts`, `extractive_digest`, prompts do narrador.

### Invariantes

- **I1** — Com `RPG_ARCHIVE_RECORD=off`, o estado final e as chamadas ao LLM ficam byte a byte iguais
  ao HEAD no mesmo seed/MockLLM, inclusive sem a chave `archive_record` e sem eventos de log novos. A
  prova é o golden da SPEC-382 (66 casos, state/result/trace/events) sem alteração;
  `test_off_identico_ao_head` só mostra que, com `off`, a marca no estado é inerte.
- **I2** — Nenhum fato canônico deixa de ser registrado. Num descanso T1 com fatos do dia e um evento
  do motor percebido, todos os `memory_id` que o caminho com LLM grava como `canonical_event` estão em
  `memory_facts` com `on` (mesmo conjunto) (teste: `test_descanso_registra_todos_os_fatos_canonicos`).
- **I3** — Equivalência de T0: com `on`, a saída do arquivista num turno com `narrative_rejections`
  sem conflito é igual à saída com `off` e um `ScriptedLLM` que devolve um `MemoryUpdate` com fatos e
  crônica "lixo". A única diferença é zero chamadas (teste: `test_rejeicao_sem_conflito_igual_ao_llm`).
- **I4** — Round-trip: `save_game` → `load_game` depois de um descanso T1 preserva `narrative_summary`,
  `memory_facts`, `pending_memory_facts`, `chronicle`, `archivist_last_run`. `archive_record` não
  aparece no save (`persistence.py` sem diff; o campo nunca é salvo) (teste:
  `test_round_trip_depois_do_registro_deterministico`).
- **I5** — A fila de NPC não fica órfã. Com `pending_npc_memory` não vazio num descanso T1 (fala no
  turno anterior com escrita que falhou), a fila é drenada ou mantida exatamente como no caminho com
  LLM, e `archive_due` reflete o que sobrou (teste: `test_descanso_drena_fila_de_npc_como_hoje`).
- **I6** — Fatos pendentes (índice fora) seguem pendentes e entram no retry da janela `turn % 3`
  (teste: `test_descanso_com_indice_fora_mantem_pendentes`).
- **I7** — Nenhuma entrada `prose` nova na crônica em T0/T1. Os marcos do `event_processor` do turno
  continuam (teste: `test_descanso_cronica_so_marcos`).
- **I8** — O resumo de T1 passa por `validate_narrative(channel="summary")` e pelos três saneadores
  sem rejeição, para todo local do mapa usado no fixture (teste: `test_frase_de_descanso_sobrevive_aos_saneadores`).

## 3. Design técnico

- **Arquivo novo `services/archive_record.py`** (funções ≤ 60 linhas, sem LLM):
  ```python
  RecordKind = Literal["rest", "discarded"]

  def record_mode() -> Literal["off", "shadow", "on"]: ...          # ou em latency_flags
  def story_marks(t) -> dict: ...
      # devolve {"archive_low": turno} (lógica movida de storyteller.py:2940-2951, idêntica)
      # e/ou {"archive_record": {"kind": "rest", "turn": turno}} (R3); {} com flags off
  def deterministic_kind(state, turn, *, conflict_summary, suppress_free_facts) -> RecordKind | None
  def exclusion_reason(state, turn, *, conflict_summary) -> str | None   # p/ shadow (R7)
  def rest_sentence(state) -> str                                        # R4
  def rest_summary(current_summary: str, state) -> str                   # R4, sem acumular
  def memory_update(kind, *, current_summary, state) -> "MemoryUpdate"
      # T0: MemoryUpdate(new_summary=current_summary, important_facts=[], chronicle_entry="")
      # T1: MemoryUpdate(new_summary=rest_summary(...), important_facts=[], chronicle_entry="")
  def summary_rejection_rows(turn, location, inventory, npc) -> list[dict]   # R11, extraído
  def trigger_reasons(state, turn) -> list[str]                          # R9
  ```
- **`agents/archivist.py`:** em `_archive_node`, antes de `llm.with_structured_output`
  (`:1003-1006`): `kind = archive_record.deterministic_kind(...)`. Se `kind` existir, `result =
  archive_record.memory_update(kind, ...)`. Se não, entra a chamada de hoje. Com T1 o ramo de sucesso
  não grava `archivist_last_run` (R5). Os três blocos de rejeição viram chamadas a
  `summary_rejection_rows`. `_should_archive` chama `trigger_reasons` para o log de R9, sem mudar a
  decisão.
- **`agents/storyteller.py`:** `_story_assemble_quests` troca o bloco `archive_low`
  (`:2940-2951`) por `t.updates.update(archive_record.story_marks(t))`.
- **`state.py`:** `archive_due`/`archive_low`/`archive_record` (este novo, não persistido) vão para `state_archive.ArchiveMarks`,
  da qual `GameState` herda. `persistence.py` **não** muda.
- **`services/latency_flags.py`:** `archive_record_mode()` e `archive_record_marks_wanted()`.
- **`config/flags.yaml`:** entrada `RPG_ARCHIVE_RECORD` (R7).
- **Formato da marca:** `{"kind": "rest", "turn": 11}`. O arquivista ignora a marca se `turn` ≠
  `world.turn_count`.
- **Desvios da execução (22/11):** (1) descanso bloqueado pelo clima carrega a chave extra
  `"blocked": "<clima>"` na marca (`_StoryTurn.rest_blocked`), para a frase de R4 não depender de
  recomputar o clima depois do tick; o descanso normal mantém `{"kind","turn"}` exato. (2) `archivist.trigger`
  é logado em `_archive_node` quando o gate mantém (não dentro de `_should_archive`, que também roda no
  caminho adiado); a decisão não muda. (3) Com T0/T1 o `get_llm` do arquivista nem é construído. (4) `archivist.trigger`
  só sai com `shadow`/`on` (decisão do coordenador, 22/11), então com `off` os logs também ficam
  iguais a hoje e `tests/fixtures/spec382_node_golden.json` não é alterado. (5) `state.py` não cresce (campo da marca em `state_archive.ArchiveMarks`, herdada por `GameState`);
  `archivist.py` (−33) e `storyteller.py` (−1) encolhem.

Exemplo de resumo T1 (local canônico de `data/`; o executor escolhe um id real ao escrever o
fixture): `"… Ela seguiu pela estrada do norte. O herói descansou em {nome do local}; agora é
{clock_label} e ele recuperou parte das forças."`

### Concorrência

N/A: sem thread, async, cancelamento, timeout, retry ou lock novo. O arquivista segue síncrono no
grafo. O modo de projeção adiada da SPEC-213 não muda (R7).

## 4. Plano passo a passo

Antes do 1º teste: ler as seções `persistência` e `llm-structured` de
`docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` e cobrir cada item ou marcá-lo "não se aplica" no hand-back.

### Etapa 1 — Extrações sem mudança de comportamento (R11)

1. **Testes** (`tests/test_archive_record.py`):
   - `test_summary_rejection_rows_igual_ao_bloco_antigo` asserta que a lista é igual à montada pelo
     código atual para 1 linha de cada tipo, com o código atual copiado no teste como oráculo;
   - `test_story_marks_archive_low_igual` asserta, para os casos de `tests/test_archivist_policy.py:110`
     (`test_emitters_mark_low_only_when_policy_reads_it`), que a marca de viagem não muda.
2. **Implementação:** criar o módulo, mover os blocos e trocar as chamadas.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_archive_record.py tests/test_archivist_policy.py tests/test_archivist_facts.py tests/test_size_budget.py`. `archivist.py` e `storyteller.py` diminuem.

### Etapa 2 — Flag, marca do narrador e `off` idêntico (R3, R7, I1)

1. **Testes:**
   - `test_flag_registrada_default_off` (registro em `config/flags.yaml`; o gate de flags da suíte já
     cobre);
   - `test_off_identico_ao_head`;
   - `test_marca_rest_so_no_descanso_sem_gancho`, parametrizado nas variantes: descanso puro →
     marca; descanso bloqueado → marca; emboscada, armadilha, rastro, social, sinal de fauna, morte,
     beat, NPC introduzido, missão nova, evento proposto pelo LLM, rumor novo, viagem, fallback de
     exceção → sem marca;
   - `test_marca_ausente_com_off`.
2. **Implementação:** `story_marks`, flag e campo em `state.py`.
3. **Verificação:** os testes acima + `tests/test_archivist_policy.py`.

### Etapa 3 — Registro determinístico no arquivista (R1, R2, R4–R6, R10)

1. **Testes primeiro** (falham antes da implementação):
   - **`test_descanso_nao_chama_llm_do_arquivista`**: `make_state` (`tests/factories.py`) + `ScriptedLLM`
     com um `MemoryUpdate` roteirizado. Com `off`, 1 chamada `MemoryUpdate`; com `on`, 0 chamadas (nem
     texto puro). `narrative_summary` termina com a frase de R4 e `archivist_last_run` não muda;
   - `test_rejeicao_sem_conflito_igual_ao_llm` (I3);
   - os testes de I2, I5, I6, I7, I8;
   - `test_descanso_com_cadencia_vencida_usa_llm`;
   - `test_descanso_com_conflito_usa_llm`;
   - `test_marca_de_outro_turno_ignorada`;
   - `test_dois_descansos_nao_acumulam_frase`;
   - `test_projecao_adiada_sem_efeito`;
   - `test_fallback_llm_off_e_shadow_como_hoje` (R10).
2. **Implementação:** `deterministic_kind`, `memory_update`, `rest_summary` e o desvio em `_archive_node`.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_archive_record.py tests/test_archivist_policy.py tests/test_archivist_facts.py tests/test_npc_memory.py tests/test_memory_provenance.py tests/test_archived_state_persistence.py`.

### Etapa 4 — Shadow e telemetria (R7–R9)

1. **Testes:**
   - `test_shadow_chama_llm_e_registra_would_skip` (caplog: `archivist.record_shadow` com `kind` e
     `reason`; 1 chamada);
   - `test_trigger_reasons_lista_fixa`: todo valor está na lista fixa de R9; uma fala de NPC com
     `rel_notice` contém `archive_due` e `canonical_only`, e não contém `archive_due_low`; um descanso
     contém `archive_due`;
   - `test_bump_archive_deterministic`.
2. **Implementação:** logs e `bump`.
3. **Verificação:** testes do escopo + `ruff check`.

### Etapa 5 — Regressão offline e round-trip (I4)

1. **Teste:** `test_round_trip_depois_do_registro_deterministico`.
2. **Playtest offline (MockLLM), escopo do executor:** `bash scripts/dev/py.sh -m playtest run --profile combate --turns 30` e `--profile normal --turns 30`, uma vez com `RPG_ARCHIVE_RECORD=off` e outra com `on`. Zero violação nova de invariantes (`memory.summary_frozen` incluído) e `archive_skipped`/`archive_deterministic` no relatório.
3. **Eval R12(a):** dois `run` de `memory_context` (`off`, `on`) e um `compare` local. O resultado é anexado no hand-back (`docs/spec422/`).

## 5. Critérios de aceite

- [x] R1–R11 cobertos pelos testes nomeados em §4; I1–I8 verdes
- [x] `test_descanso_nao_chama_llm_do_arquivista` falhou antes da Etapa 3 (registrar no hand-back) e passa depois
- [x] `off` byte a byte igual ao HEAD (I1)
- [x] `tests/test_size_budget.py` verde sem `--update` em `archivist.py`/`storyteller.py`
- [x] `RPG_ARCHIVE_RECORD` em `config/flags.yaml`, default `off`
- [x] `memory_context` `compare` `off`×`on` sem piora de hard gate (R12a)
- [x] Suíte completa no pouso (22/11, `FULL_N=2 full.sh`, em `3d7b0f99`, já com a extração para `state_archive.py`): 11858 passed, 330 skipped, 2 xfailed, rc=0. Uma rodada anterior (11855 passed) foi no código de antes da extração e não conta. Depois da suíte entrou só o commit de configuração do P3-5; para ele rodaram os testes que cobrem as quatro listas e os gates de tipos, crescimento e formato (76 passed), não a suíte inteira
- [x] Guard de FallbackLLM intacto no caminho do LLM (R10); nenhum `with_structured_output` novo
- [x] Saves antigos continuam carregando (I4)
- [ ] Promoção a `on` em staging **só** depois de: R12(b) pousado e sem piora; `shadow` com ≥ 20 descansos e 0 exceção; A/B de §6 com mediana de "pode agir" do descanso ≥ 3 s menor; leitura do dono de 5 pares (resumo do LLM × registro) do mesmo save

## 6. Smoke test com LLM real

Local com chave (DeepSeek), ≤ 6 requests, flag `on`:

1. `/game/new` + 1 cena + **descanso**: no `turn` log, `llm_by_phase` sem `archivist`,
   `phase_ms.archivist` < 100 ms e `archivist.record {kind: "rest"}`. No estado, `narrative_summary`
   termina com a frase de R4 e `memory_facts` tem os fatos do dia, se houve.
2. Fala com NPC já criado: o arquivista chama o LLM como hoje, e `archivist.trigger` aparece com os
   motivos.
3. Segundo descanso seguido: uma frase só no resumo (R4).
4. Cena seguinte: o narrador recebe o resumo (`[RESUMO NARRATIVO | speculative]`) sem erro, e o
   arquivista com LLM (se o gate disparar) reescreve o resumo normalmente.

Staging (`Requer: staging`):

5. `shadow` por um dia de uso normal ou pela L0 (`docs/auditorias/latencia-l0-2026-11-13/l0_measure.py`,
   4 sessões × 15 turnos, ≤ US$ 0,25 como em 13/11). Contar `would_skip` por `reason` e `archivist.trigger`
   nas falas de NPC. O resultado vai para `docs/spec422/`.
6. A/B `off` × `on`, mesma L0: mediana de "pode agir" do descanso e número de turnos travados (hoje
   21/60).

## Não rodou e por quê

- **Smoke §6, fase `shadow` e A/B (staging):** não rodaram. O staging está em `d7aa4beb` (10/11) e o próximo deploy depende
  de o dono aplicar as migrações das SPEC-413/410 (`ESTADO_ATUAL.md` § Bloqueios).
- **CI pré-pouso de risco `alto`:** não rodou. Push de branch `spec-NNN` não está autorizado pelo dono; a suíte completa
  local e a revisão Sol com 23 mutações substituem.
- **Revisão Sol (22/11):** rodada 1 `APPROVED_WITH_FOLLOWUPS` (P2-1 e P3-1..4), tratados em `f1caa481`; rodada 2 `APPROVED`
  (`handoffs/SPEC-422-sol-review.md`). O playtest da Etapa 5 e o `evals run` de R12(a) foram rodados só pelo executor.
- **Pouso recusado e corrigido (22/11):** o `land_check` reprovou `growth` (`state.py` 1082 → 1083 em `tests/size_budget.json`).
  As marcas `archive_due`, `archive_low` e `archive_record` foram para `state_archive.ArchiveMarks` e `GameState` herda dele
  (`436197b8`); `state.py` voltou a 1082 linhas e nenhum teto subiu. Rodada 3 da revisão Sol: `APPROVED_WITH_FOLLOWUPS`, com as
  mesmas chaves e a mesma totalidade do estado e a marca chegando do narrador ao arquivista no grafo real.
- **P3-5 da rodada 3, feito no pouso:** `state_archive.py` registrado no `include` do basedpyright (`pyproject.toml`), em
  `AI_FILES` (`scripts/ci_eval_scope.py`), em `PRODUCT_FILES` (`scripts/dev/eval_publish.py`) e nos `entrypoints` de
  `state_rules` (`project_index/domains.yaml`). Nenhum dos quatro é caminho protegido (`evals/protected-paths.txt`).
- Da escrita da spec: nada foi executado além de leitura de código e da contagem em `resultado.json` (Grep).
- O caminho hospedado (Postgres + pgvector) não roda nesta máquina (D-36). O registro
  determinístico não muda a gravação vetorial, que é a mesma `persist_records`. O smoke §6 itens 5–6
  em staging cobre.
- R12(b) depende de outra spec (autoria de eval) e não roda nesta.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo persistido novo. A marca é transitória. Save sem `archive_record`
  carrega (I4).
- **T0 e exceção do LLM:** com `on`, T0 não passa mais pelo `except` quando o LLM levantaria. Hoje o
  nó devolve só `event_updates` nesse caso; com `on` grava como no caminho de sucesso (direção segura;
  I3 cobre só o sucesso).
- **MockLLM / FallbackLLM:** `off`/`shadow` iguais a hoje. Com `on`, T0 e T1 não tocam o LLM, então o
  FallbackLLM não tem como produzir resumo de erro nesses turnos (já protegido em `archivist.py:106-110`).
- **Qualidade:** o risco real é perder no resumo um detalhe que o narrador inventou no despertar.
  O narrador só vê `messages[-3:]`, então o detalhe vale por um turno. Mitigação: um gancho
  estruturado exclui o turno (R3.4), a cadência força o LLM a cada 10 turnos (R5) e o eval de autoria
  mede a continuidade (R12b).
- **Latência:** ganho esperado de ~4,0 s no "pode agir" de cada descanso elegível. São no máximo
  8 dos 20 turnos com arquivista da L0 (T1), mais T0 quando ocorrer (1 cena na L0). Em servidor: até
  8 × 4,0 ≈ 32 s dos 448 s medidos (~7 %). Turnos travados: de 21/60 para até 13/60. O número real
  depende da fração de descansos sem encontro nem gancho. Sai do `shadow` (§6.5), sem estimativa
  inventada aqui.
- **Custo:** uma chamada SMART a menos por turno elegível (~US$ 0,0018 cada na L0).
- **Tamanho/gates:** R11. Se a extração não couber, o executor para e reporta (não usa `--update` em
  `archivist.py`/`storyteller.py`).

## 8. Decisões do dono

Já tomadas (13/11): aprovou o resumo sem IA "nos turnos em que os fatos já são conhecidos, como o
descanso"; "só passa se o teste de memória não piorar"; qualidade acima de velocidade. Não aprovou
fila de ação, liberar o envio antes do arquivista nem narração menor.

Ficam para o dono:

- **D1 — Gate de qualidade para `on`.** O "teste de memória" atual (`memory_context`) não roda o
  arquivista. Proposta: a promoção exige a suíte nova de autoria (R12b) **e** a leitura de 5 pares.
  Alternativa mais rápida: só `memory_context` + leitura de 5 pares, ciente de que `memory_context`
  não cobre o caso.
- **D2 — Fala com NPC (8 de 20 turnos com arquivista).** Hoje o LLM só escreve o resumo dessas falas.
  Fica fora desta spec porque o resumo carrega o que foi dito. Um follow-up poderia resumir a partir
  da citação literal já gravada na memória do NPC. O dono quer que se escreva essa spec depois da
  medição de R9?
- **D3 — Prazo do flag** (`expires: 2027-02-28`): aceitar ou ajustar.

- **13/11–22/11, coordenador (delegação do dono; a spec e a execução foram aprovadas em 13/11, "pode. e execute elas"):** D1 = gate recomendado (suíte nova de eval + leitura de 5 pares) para promover a `on`; o pouso é com `off`. D2 = fica como pergunta ao dono, fora desta spec. D3 = `expires: 2027-02-28` aceito. Veto do dono continua possível.
