# SPEC-300 — Companheiros com alma

> **Status:** `draft`
> **Criada:** 2026-10-20 · **Atualizada:** 2026-10-20
> **Origem:** `docs/mundo-vivo/VISAO.md` — decisão 8 (Companheiros), decisão 7 (Visibilidade), Regra de ouro, § C. Sociedade viva (morte off-screen, relação alta destrava romance, "Companheiros falam"), § Calibração (migração suave)
> **Depende de:** — (nenhuma spec aberta é pré-requisito técnico; na ordem da onda entra depois da SPEC-296). Integra-se, sem bloquear, a SPEC-298 (vocabulário de rótulos), SPEC-299 (tag de crime) e SPEC-302 (motor de mundo).
> **Desbloqueia:** SPEC-302 (morte/perigo off-screen de companheiro, via interface §3.8); spec futura do pilar B "rendido → prisioneiro → recrutar" (via interface §3.9)
> **EXECUTOR_MODEL:** `Sonnet` (etapas 0–4, 8–9) / `Opus` (etapas 5–7: máquina de estados, romance, interfaces) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (novo campo persistente com writer único, prompts do narrador e do NPC, conteúdo sensível p/ Google Play)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Hoje companheiro é só ficha de combate. `party.make_companion_from_npc`
([party.py:201-238](../party.py)) copia a ficha v4 do NPC e um template de
[data/companions.json](../data/companions.json) (5 arquétipos com
`attributes`/`attacks`/`behavior`, nada de personalidade). O recrutamento é um gate
de `relationship >= 7` + 2 interações ([party.py:19-20](../party.py),
[party.py:305-351](../party.py)); depois disso o companheiro nunca mais opina,
nunca discorda, não tem objetivo próprio e só sai se o jogador o dispensar
([party.py:385-389](../party.py)). Aliados de cena (`scene_allies`, rel ≥ 6) são
transitórios ([party.py:260-302](../party.py)). A `relationship` 0–10 do NPC muda
só por proposta da LLM (±1 por turno, [agents/npc.py:155](../agents/npc.py),
[agents/npc.py:836-839](../agents/npc.py)) e a memória guarda 20 linhas
([agents/npc.py:850](../agents/npc.py)). Os traços (`hidden_traits`/
`revealed_traits`, 80 em `data/traits.json`) só influenciam DC
([services/npc_layers.py:217-223](../services/npc_layers.py)). O narrador não
recebe nada sobre a party além do nome em "NPCs na cena"
([agents/storyteller.py:915-923](../agents/storyteller.py)).

O dono decidiu (VISAO §8 e § C): companheiros com **autonomia alta, com aviso** —
opinam, discordam, têm missão pessoal; com aprovação em queda **avisam e depois
saem, ou traem se o traço permitir**; falam espontaneamente em **escolhas
marcantes**, **ao descansar** e **quando o jogador se dirige a eles**, **sem
chamada LLM extra**; o jogador vê só **rótulos vagos** ("Brunna não gostou
disso"); romance/vínculo com arco próprio, **fade-to-black**; companheiro afastado
num lugar perigoso **pode morrer off-screen, sempre telegrafado**.

Esta spec cria a "alma" do companheiro como **mecânica Python determinística**:
valores derivados de traços/fação/raça/origem, aprovação 0–100 movida por **tags de
escolha detectadas em Python** a partir de `GameEvent`s, desfecho de combate,
baseline do turno e um conjunto fechado de regex sobre a ação. A LLM só **narra** o
que o motor decidiu, por meio de um bloco no prompt do narrador e do `npc_actor`.
Princípios: "Mecânica é Python, não LLM"; "LLM propõe, motor aplica"; Regra de ouro
(o companheiro só reage ao que testemunhou); migração suave (default neutro,
nenhum bump de `SCHEMA_VERSION`).

## 2. Requisitos

### 2.1 Valores e aprovação

- **R1 — Valores derivados, determinísticos.** Todo companheiro tem um vetor de
  valores em 7 eixos fechados (`compaixao`, `honra`, `ordem`, `ganancia`, `fe`,
  `coragem`, `abismo`), cada eixo inteiro em [-2, 2], calculado por
  `derive_values(npc)` como a soma, com clamp por eixo, de: vetores dos traços
  (`hidden_traits` + `revealed_traits`), vetor da fação (`npc["faction"]`), vetor da
  raça (`npc["race"]`, se houver) e vetor da região de origem
  (`npc["home_location_id"]` → região de `data/origins.json`, se houver). Mesmo NPC
  e mesmo save → mesmo vetor. Sem LLM.
- **R2 — Tabelas curadas e completas.** Os vetores vêm de
  `data/companion_values.json`. Teste de contrato: **todo** id de `data/traits.json`
  (80) e **toda** fação de `data/factions.json` (19) tem entrada (vetor vazio `{}`
  é permitido, mas explícito); todo valor está em {-2..2}; todo eixo é um dos 7.
- **R3 — Aprovação inicial.** Ao entrar na party, o companheiro ganha
  `approval = clamp(50 + 3·(relationship − 7), 40, 65)` `[BALANCEAR]`.
  Prisioneiro recrutado (R27) começa em `PRISONER_START_APPROVAL = 20`.
  Companheiro de save antigo sem alma recebe a alma no primeiro fim de turno
  (R18) pela mesma fórmula.
- **R4 — Catálogo fechado de tags de escolha.** `data/companion_choice_tags.json`
  define cada tag: `id`, `source` (`event` | `combat` | `baseline` | `action_regex`
  | `engine`), `axes` (vetor nos 7 eixos), `magnitude` (1–3) e, quando aplicável,
  `faction_param` (a tag carrega um `faction_id`). Tags que vêm de regex têm
  `magnitude = 1`. O catálogo inicial está na §3.4; nova tag = PR no JSON + teste.
- **R5 — Detecção só em Python.** `detect_choice_tags(state)` lê, no fim do turno:
  (a) eventos **novos** do `event_log` (ids ausentes de
  `turn_baseline["event_ids"]`, [services/turn_outcome.py:52-70](../services/turn_outcome.py));
  (b) o desfecho do combate encerrado neste turno (`combat.phase == "ended"`,
  `outcome` de [agents/combat.py:945-959](../agents/combat.py));
  (c) diferenças de baseline (ouro, `abyss_charge`); (d) regex fechadas sobre a
  última ação do jogador. Nunca lê `faction_impacts`, `relationship_change` nem
  texto narrado pela LLM.
- **R6 — Delta determinístico.** Para cada companheiro testemunha e cada tag:
  `align = Σ tag.axes[a] · values[a]`;
  `delta = clamp(round(tag.magnitude · K_ALIGN · align), −TAG_CAP, +TAG_CAP)`;
  com `faction_param` igual à fação do companheiro soma `±FACTION_DIRECT`
  (sinal da tag). Soma por turno limitada a `±TURN_CAP`. `|delta| < MIN_NOTICE`
  é aplicado mas não gera reação. Constantes `[BALANCEAR]`: `K_ALIGN = 2`,
  `TAG_CAP = 10`, `FACTION_DIRECT = 8`, `TURN_CAP = 15`, `MIN_NOTICE = 2`.
  Aprovação sempre em [0, 100].
- **R7 — Regra de ouro (testemunha).** Só companheiros **presentes** — os de
  `party.active_allies(state)` ([party.py:241-251](../party.py)) — recebem deltas e
  reações. Companheiro em `waiting_at` ([party.py:392-400](../party.py)) não reage
  ao que não viu. Exceção única: tags da **própria** missão pessoal (R20).
- **R8 — Rótulos vagos, nunca números.** Faixas de aprovação → rótulo
  (substantivo, sem gênero): `< 15` "ressentimento", `15–34` "desconfiança",
  `35–59` "cordialidade", `60–79` "amizade", `≥ 80` "lealdade". Mudança no turno →
  frase: `|delta|` 2–3 "X reparou nisso." (só no prompt, não na UI), 4–7
  "X gostou disso." / "X não gostou disso.", ≥ 8 "X aprovou muito." /
  "X não vai esquecer isso.". Frases sem flexão de gênero (o NPC não tem campo de
  gênero). Nenhum endpoint, log público ou prompt expõe o número da aprovação nem
  o vetor de valores (teste varre o payload da API).

### 2.2 Fala espontânea (sem chamada LLM extra)

- **R9 — Bloco no prompt, zero chamadas novas.** `storyteller` e `npc_actor`
  recebem um bloco `<COMPANHEIROS>` gerado por `companion_prompt_block(state,
  purpose)`; nenhum `get_llm`/`invoke` novo é criado (teste conta chamadas ao LLM
  por turno com e sem companheiro: iguais). Nenhum campo novo de structured output.
- **R10 — Quando o bloco manda falar.** Prioridade, uma decisão por turno:
  1. despedida/traição pendente (R15/R16) → o companheiro se despede;
  2. aviso pendente (R14) → o companheiro avisa, sem rodeios;
  3. reação pendente com `|delta| ≥ 4` → **um** companheiro (o de maior `|delta|`;
     empate por RNG seeded `(game_id, turn, "companion_voice")`) comenta a escolha
     do turno anterior em 1–2 falas;
  4. turno de descanso (`world_utils.is_rest`, [world_utils.py:76](../world_utils.py);
     ramo em [agents/storyteller.py:583-607](../agents/storyteller.py)) → "conversa
     de acampamento" de até **2** companheiros, com tópico escolhido em Python
     (R21 missão, R24 romance, ou valores/aprovação);
  5. senão → o bloco diz que os companheiros ficam calados (só presença).
- **R11 — Dirigir-se ao companheiro.** Quando o `npc_actor` atende um
  companheiro ([agents/npc.py:747-810](../agents/npc.py)), o bloco
  `purpose="npc"` traz: rótulo de aprovação, 2 eixos mais fortes em linguagem de
  personagem (sem nome de traço oculto), últimas ≤ 3 reações (tag em prosa curta),
  estado do aviso, estágio da missão pessoal e do romance. A `relationship_change`
  da LLM continua mexendo **só** em `relationship` (não em aprovação).
- **R12 — Orçamento de prompt.** Bloco ≤ 600 caracteres por companheiro e
  ≤ 1.200 no total (teste). Sem companheiro presente o bloco é string vazia.
- **R13 — Reação consumida só quando narrada.** Reações pendentes ficam em fila
  (máx. 3 por companheiro, expiram em 3 turnos). O nó narrador devolve
  `companion_voice_ack` (transitório, ids das reações/tópicos usados) **só no
  caminho feliz** do structured output; caminho de fallback não consome. Quem marca
  como consumida é o writer único (R19).

### 2.3 Aviso, partida e traição

- **R14 — Aviso antes de partir.** Ao cruzar para baixo de `WARN_BELOW = 25`, o
  companheiro entra em `warned` (grava `warned_turn` e `warned_day`) e gera uma
  reação de aviso (prioridade 2 da R10). O aviso some se a aprovação voltar a
  `≥ CLEAR_WARN_AT = 35` (histerese). Sem aviso prévio, **nunca** há partida
  (invariante de playtest, R30).
- **R15 — Partida.** Com `warned` ativo, `approval < LEAVE_BELOW = 15` e
  (dia de jogo virou desde `warned_day` **ou** houve outra tag negativa para ele
  depois de `warned_turn`), o companheiro fica `departure_pending`. A partida só é
  executada no fim de um turno **narrado e fora de combate** depois do turno em que
  ficou pendente (o jogador vê a despedida antes de a party mudar). Efeito:
  removido da party; no `state.npcs` o NPC fica `in_scene=False`,
  `relationship = max(0, relationship − 2)`, `left_party_day`; evento
  `companion_left` (source `engine`).
- **R16 — Traição, se o traço permitir.** Se, no momento da partida,
  `approval < BETRAY_BELOW = 8`, o companheiro tem ≥ 1 traço de
  `BETRAYAL_TRAITS` e nenhum de `BETRAYAL_BLOCKERS` (listas em
  `data/companion_values.json`, propostas na §8 para revisão do dono), a partida
  vira traição: além da R15, leva `min(floor(gold · 0,25), 60)` de ouro
  `[BALANCEAR]`, `relationship = 0`, `grudge = True` e o evento é
  `companion_betrayed`. O desconto de ouro aparece no recibo do turno (SPEC-199).
  Companheiro `loyal` (R22) nunca trai.
- **R17 — Recrutar de novo.** `recruitment_decision`
  ([party.py:305-351](../party.py)) ganha os códigos `estranged` (partiu há menos de
  `ESTRANGED_DAYS = 3` dias de jogo) e `betrayed` (traiu: nunca mais). Fora disso
  o gate atual vale, e a alma volta com a última aprovação + 10, limitada a 40.

### 2.4 Estado, persistência e writer único

- **R18 — Campo novo, aditivo.** `GameState.companion_souls: dict[str,
  CompanionSoul]` (chave = id do companheiro: `origin_npc` ou `id` da party) e o
  transitório `companion_voice_ack: list[str] | None`. Os dois entram no
  `TypedDict` (sem isso o LangGraph descarta o update — ver comentário em
  [state.py:462-463](../state.py)). Sem bump de `SCHEMA_VERSION`
  ([persistence.py:80-85](../persistence.py)); default `{}` em `_raw_to_state`
  ([persistence.py:972](../persistence.py)), como na SPEC-202. Save antigo com
  party carrega e o companheiro ganha alma no 1º fim de turno.
- **R19 — Writer único.** Só `services/companion_soul.apply_turn(state)` escreve
  `companion_souls` (e, na partida, `party`/`npcs`/`event_log`), chamado em
  `turn_finalizer_node` ([agents/turn_finalizer.py:7-49](../agents/turn_finalizer.py))
  depois do archivist (eventos do turno já aplicados,
  [agents/archivist.py:301](../agents/archivist.py)). Falha interna é logada e o
  turno segue (mesmo padrão do SPEC-215 em
  [agents/turn_finalizer.py:35-45](../agents/turn_finalizer.py)). A alma
  sobrevive à saída e à morte do companheiro (memória da relação).

### 2.5 Missão pessoal

- **R20 — Origem da missão.** Cada companheiro tem no máximo **uma** missão
  pessoal, id determinístico `pq_<companion_id>`. Fonte, em ordem: (a) o
  `gancho` dos 36 NPCs `mundo_vivo` (ex.: Brunna Ponte-Alta: "Firmar uma ponte que
  o eco insiste em desmontar durante a noite.",
  [data/codex/npcs/mundo_vivo/npc_mv_brunna_ponte_alta.md:26](../data/codex/npcs/mundo_vivo/npc_mv_brunna_ponte_alta.md)),
  com `location_id = home_location_id`; (b) um template de
  `data/companion_quests.json` escolhido pelo 1º traço do companheiro que tenha
  template (ex.: `luto_recente`, `dividas`, `divida_de_sangue`, `protege_alguem`,
  `desertor_envergonhado`, `orfao_da_legiao`); (c) um template genérico por
  `home_location_id`. Texto 100% template, sem LLM.
- **R21 — Revelação no acampamento.** A missão é revelada numa conversa de
  acampamento (R10.4) quando `approval ≥ PERSONAL_REVEAL_AT = 55` e o companheiro
  já descansou ≥ 1 vez com o jogador. Ao revelar, vira `Quest` ativa em
  `state.quests` com `origin_entity_id` = id do companheiro e o campo novo
  opcional `personal_of` (aditivo no `Quest`, [state.py:303-319](../state.py)).
- **R22 — Conclusão e falha determinísticas.** Chegar ao `location_id` com o
  companheiro **ativo** marca `completion_ready`; no fim do próximo turno narrado
  (o bloco pede a cena de resolução), o motor conclui via `quest_log`
  ([services/quest_log.py:341](../services/quest_log.py)), sem proposta da LLM.
  Conclusão: `+15` de aprovação; se ficar `≥ 70`, o companheiro vira `loyal`
  (partida só abaixo de 5, nunca trai). Falha (companheiro partiu ou morreu —
  `fail_orphan_quests`, [services/quest_log.py:366-372](../services/quest_log.py))
  fica registrada; se ele ainda estiver na party, `−15`.

### 2.6 Romance / vínculo (fade-to-black)

- **R23 — Arco em estágios, Python decide.** `romance` ∈ `none` → `interesse` →
  `vinculo` → `compromisso`, mais `rompido`. Avanços:
  `interesse` exige intenção romântica do jogador dirigida ao companheiro
  (regex fechada em `npc_actor`) e `approval ≥ ROMANCE_OPEN_AT = 65`;
  `vinculo` exige `approval ≥ 75` e ≥ 2 descansos juntos em `interesse`;
  `compromisso` exige missão pessoal concluída e `approval ≥ 85`.
  `approval < 40` em qualquer estágio → `rompido` (só reabre após 5 dias de jogo).
  Gate fechado → o bloco manda recusar com delicadeza, sem penalidade.
- **R24 — Cena de vínculo só no acampamento.** Avanço de estágio vira tópico de
  conversa de acampamento (R10.4). O bloco carrega, **sempre que há romance
  ativo**, a regra fixa: "cena íntima termina em corte antes de qualquer contato
  físico explícito; nada sexual; foco em diálogo, gesto e consequência".
- **R25 — Interruptor de loja.** `RPG_COMPANION_ROMANCE=on|off` (default `on`).
  `off`: estágio nunca avança, intenção romântica recebe recusa gentil, nenhuma
  regra de romance entra no prompt. Elegibilidade por companheiro conforme
  decisão do dono (§8, D4).

### 2.7 Interfaces para outras specs (só contrato + testes com dublê)

- **R26 — Perigo e morte off-screen (para a SPEC-302).** Funções puras
  `companions_exposed(state)`, `telegraph_companion_danger(state, cid, kind, day)`
  e `apply_companion_fate(state, cid, fate, day)` (assinaturas na §3.8).
  `apply_companion_fate` **recusa** (`FateNotTelegraphed`) se não houver
  telegrama registrado há ≥ `TELEGRAPH_MIN_DAYS = 1` dia de jogo, ou se o jogador
  voltou ao local / chamou o companheiro (`set_following`) depois do telegrama
  (chance de intervir). Esta spec **não** sorteia perigo nem morte.
- **R27 — Prisioneiro recrutado (para o pilar B).**
  `party.recruit_prisoner(state, prisoner)` cria companheiro a partir de um inimigo
  rendido: ignora o gate de `relationship`, respeita `MAX_ACTIVE`
  ([party.py:21](../party.py)), aceita fação hostil, aprovação inicial 20,
  `bound = "rendicao"`. Sem chamador no produto nesta spec.

### 2.8 Rollout, UI e prova

- **R28 — Flag.** `RPG_COMPANION_SOUL=off|shadow|on` (default `on`). `off`:
  `apply_turn` e o bloco são no-op (comportamento atual byte a byte nos testes
  existentes). `shadow`: calcula e persiste a alma e loga, mas não injeta bloco,
  não executa partida e não mostra rótulo na UI.
- **R29 — API e UI.** Cada item de `party` na resposta de estado
  ([api.py:2195-2208](../api.py)) ganha `approval_label` e, se houver,
  `bond_label` (só a partir de `vinculo`: "vínculo"/"compromisso"). A resposta do
  turno ganha `companion_feedback: list[str]` com as frases da R8 (só as
  `|delta| ≥ 4`, aviso e partida). `web/src/types.ts` (`PartyMember`) e
  `PartyBars` ([web/src/components/Hud.tsx:359-380](../web/src/components/Hud.tsx))
  mostram o rótulo; a área de narração mostra as frases de `companion_feedback`.
  Nenhum número.
- **R30 — Invariantes de playtest.** `playtest/invariants.py` ganha: aprovação em
  [0, 100]; partida/traição só com `warned_turn` anterior; morte off-screen só com
  telegrama ≥ 1 dia; no máximo uma missão pessoal por companheiro; companheiro
  `loyal` nunca com `companion_betrayed`.
- **R31 — Sem regressão.** `--all --turns 50` (14 perfis, MockLLM) com a flag `on`:
  zero erro e zero violação `error`. Metas M1 e M5 da SPEC-285 inalteradas (esta
  spec não toca o motor de combate; a prova é rodar o perfil `combate`).

### Fora de escopo

- Sortear perigo/morte off-screen, agenda e deslocamento de NPC (SPEC-302; aqui só
  a interface R26).
- Fluxo de rendição → prisioneiro → escolta/interrogatório (pilar B; aqui só R27).
- Romance com NPC que não é companheiro; ciúme e relação companheiro↔companheiro.
- Mudar a escala ou os rótulos da `relationship` de NPC e da reputação de fação
  (SPEC-298). `visible_npc_view` continua expondo `relationship` como hoje
  ([services/npc_layers.py:259](../services/npc_layers.py)) — tratar na SPEC-298.
- Detecção de crime e lei (SPEC-299): esta spec só **consome** os eventos
  `crime_witnessed`/`fine_paid` **se** existirem; não os cria.
- Bloco de companheiros na narração de combate; mudança na IA tática de aliado.
- Missão pessoal escrita por LLM; arte, retrato, voz ou som de companheiro.
- Propagar notícias para companheiro em `waiting_at` (SPEC-215 futura).
- Inventário/equipamento próprio de companheiro.
- Qualquer número de aprovação visível ao jogador.

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/companion_soul.py` | Núcleo puro: `derive_values`, `initial_approval`, `ensure_soul`, `apply_tags`, rótulos, máquina de aviso/partida/traição, missão pessoal, romance, `apply_turn` (writer único), interfaces R26. |
| `services/companion_tags.py` | `detect_choice_tags(state)` e regex fechadas (`detect_action_tags`, `detect_romance_intent`). Puro. |
| `services/companion_prompt.py` | `companion_prompt_block(state, purpose)` e a seleção de quem fala (R10–R12). Puro. |
| `data/companion_values.json` | Vetores de traço/fação/raça/região, `BETRAYAL_TRAITS`, `BETRAYAL_BLOCKERS`, `ROMANCE_BLOCKERS`. |
| `data/companion_choice_tags.json` | Catálogo de tags (R4, §3.4). |
| `data/companion_quests.json` | Templates de missão pessoal por traço e genérico por região (R20). |
| `tests/test_spec300_values.py`, `test_spec300_tags.py`, `test_spec300_approval.py`, `test_spec300_departure.py`, `test_spec300_prompt.py`, `test_spec300_personal_quest.py`, `test_spec300_romance.py`, `test_spec300_interfaces.py`, `test_spec300_persistence_api.py` | Ver §4. |

### 3.2 Arquivos alterados

- `state.py` — `CompanionSoul` (TypedDict), `GameState.companion_souls`,
  `GameState.companion_voice_ack`, `Quest.personal_of: str` (opcional).
- `persistence.py` — `_raw_to_state`: `companion_souls` default `{}`.
- `agents/turn_finalizer.py` — chama `companion_soul.apply_turn(state)` em
  `try/except` depois do bloco SPEC-215 e antes do `return`; mescla `party`,
  `npcs`, `quests`, `event_log`, `companion_souls` e `companion_feedback` no
  `updates`. Zera `companion_voice_ack`.
- `agents/storyteller.py` — injeta `companion_prompt_block(state, "story")` logo
  depois de `{hero_state_block}` ([agents/storyteller.py:930](../agents/storyteller.py));
  devolve `companion_voice_ack` só no caminho feliz (após o `isinstance` da
  [agents/storyteller.py:995](../agents/storyteller.py)).
- `agents/npc.py` — injeta `companion_prompt_block(state, "npc", target=npc_id)`
  no `<ROLE>` quando o interlocutor é companheiro; `detect_romance_intent` antes do
  invoke registra a intenção em `companion_voice_ack` (o writer decide); comandos de
  party ([agents/npc.py:593-661](../agents/npc.py)) inalterados.
- `party.py` — `recruitment_decision`: códigos `estranged`/`betrayed` (Literal na
  [party.py:26-33](../party.py)); nova `recruit_prisoner`. `make_companion_from_npc`
  inalterado (a alma mora em `companion_souls`, não na ficha).
- `services/turn_outcome.py` — `capture_baseline` grava também `abyss_charge`
  (aditivo; receitas existentes ignoram a chave).
- `services/structured_outputs.py` + `services/world_validators.py` — tipos
  `companion_left`, `companion_betrayed`, `companion_fate` **só** com
  `source="engine"` (mesmo padrão de `unique_item_claimed`,
  [services/structured_outputs.py:39-42](../services/structured_outputs.py)); a
  LLM não consegue propor.
- `services/chronicle.py` — milestones para `companion_left`,
  `companion_betrayed`, `companion_fate` e conclusão de missão pessoal.
- `scripts/gen_world_living_npcs.py` — grava `hook` nos `components` de cada NPC
  `mundo_vivo` em `data/graph/entities.json` (regenerado pelo script; o corpo do
  Codex não muda, então não exige reindex).
- `api.py` — `approval_label`/`bond_label` em `party`; `companion_feedback` na
  resposta do turno.
- `web/src/types.ts`, `web/src/components/Hud.tsx` (+ componente da narração que
  já mostra o recibo) — rótulos e frases.
- `playtest/invariants.py` (R30), `playtest/scenarios.py` (cenário `companheiro`,
  §6), `.env.example` (`RPG_COMPANION_SOUL`, `RPG_COMPANION_ROMANCE`).

### 3.3 Schemas

```python
# state.py
Axis = Literal["compaixao", "honra", "ordem", "ganancia", "fe", "coragem", "abismo"]

class CompanionReaction(TypedDict, total=False):
    id: str            # f"{turn}:{tag_id}" — estável
    tag: str           # id do catálogo (ou "aviso" | "despedida" | "traicao")
    delta: int         # interno; nunca sai na API
    turn: int
    consumed: bool

class CompanionSoul(TypedDict, total=False):
    companion_id: str
    npc_key: str                     # chave em state.npcs (pode ser "")
    values: dict[str, int]           # Axis -> -2..2 (congelado na criação)
    approval: int                    # 0..100
    origin: str                      # "recruit" | "prisoner" | "legacy"
    reactions: list[CompanionReaction]   # máx. 3 não consumidas
    warned_turn: int | None
    warned_day: int | None
    departure_pending: Literal["", "leave", "betray"]
    departed: Literal["", "left", "betrayed", "dead"]
    left_party_day: int | None
    loyal: bool
    grudge: bool
    rests_together: int
    personal_quest: Literal["none", "revealed", "ready", "completed", "failed"]
    romance: Literal["none", "interesse", "vinculo", "compromisso", "rompido"]
    romance_rests: int
    romance_reopen_day: int | None
    telegraphs: list[dict]           # [{kind, day, turn}] — R26
    last_seen_day: int
```

`values` é calculado uma vez em `ensure_soul` e congelado (revelar um traço depois
não muda a personalidade; os traços ocultos já contam desde o início, como em
`trait_dc_modifier`).

### 3.4 Catálogo inicial de tags (`data/companion_choice_tags.json`)

| id | fonte (evidência) | eixos | mag. |
|---|---|---|---|
| `aceitou_rendicao` | `combat.outcome == "surrendered_enemy"` ([agents/combat.py:956-958](../agents/combat.py)) | compaixao +1, honra +1 | 2 |
| `fugiu_do_combate` | `outcome == "fled"` ([agents/combat.py:950-951](../agents/combat.py)) | coragem −2 | 1 |
| `matou_nomeado` | evento `npc_killed`, `actor_id == "player"`, alvo era inimigo do combate | coragem +1, compaixao −1 | 1 |
| `matou_inocente` | `npc_killed` do jogador com alvo **fora** de combate e `relationship ≥ 5` | compaixao −2, honra −2, ordem −2 | 3 |
| `quest_concluida` | evento `quest_completed` | honra +2 | 1 |
| `quest_falhou` | evento `quest_failed` ([services/quest_log.py:371](../services/quest_log.py)) | honra −1 | 1 |
| `ajudou_faccao` / `prejudicou_faccao` | evento `reputation_changed` com delta > 0 / < 0 (`faction_param` = alvo) | — (só `FACTION_DIRECT`) | 1 |
| `revelou_segredo` | evento `secret_revealed` | ordem −1, fe −1 | 1 |
| `usou_abismo` | `abyss_charge` subiu vs. baseline | abismo +2, fe −1 | 2 |
| `doou_ouro` | regex de doação **e** ouro caiu sem `last_economy_action` no turno | compaixao +2, ganancia −2 | 1 |
| `ameacou` | regex de ameaça/intimidação na ação | compaixao −1, coragem +1 | 1 |
| `crime_testemunhado` | evento `crime_witnessed` (SPEC-299, se existir) | ordem −2, honra −1 | 2 |
| `pagou_multa` | evento `fine_paid` (SPEC-299, se existir) | ordem +1 | 1 |
| `missao_pessoal_concluida` | motor (R22) | — (fixo +15, só o dono da missão) | — |

`reputation_changed` hoje nasce de `faction_impacts` da LLM com delta decidido em
Python ([services/event_processor.py:289-293](../services/event_processor.py)); ele é
usado porque é evento validado, e herda qualquer melhoria da SPEC-298.

### 3.5 Exemplo de `data/companion_values.json` (IDs reais)

```json
{
  "axes": ["compaixao", "honra", "ordem", "ganancia", "fe", "coragem", "abismo"],
  "traits": {
    "ganancioso": {"ganancia": 2, "honra": -1},
    "honesto_demais": {"honra": 2},
    "covarde": {"coragem": -2},
    "devoto": {"fe": 2, "abismo": -1},
    "veterano_de_guerra": {"coragem": 1, "ordem": 1},
    "odeia_o_codigo": {"ordem": -2},
    "generoso_escondido": {"compaixao": 2},
    "rancoroso": {"compaixao": -1},
    "tagarela": {}
  },
  "factions": {
    "legiao_ferro": {"ordem": 2, "honra": 1},
    "filhos_chama_azul": {"fe": 2, "abismo": -2},
    "ultimos_anoes_reino": {"honra": 2, "ordem": 1},
    "mercadores_escravos_pradaria": {"ganancia": 2, "compaixao": -2}
  },
  "races": {"race_osshari": {}, "race_humanos": {}},
  "regions": {"montanhas_afiadas": {"coragem": 1}},
  "betrayal_traits": ["ganancioso", "cinico", "rancoroso", "dividas", "contrabandista",
                      "lingua_dupla", "guarda_subornavel", "apostador", "usurario_paciente"],
  "betrayal_blockers": ["honesto_demais", "leal_a_familia"],
  "romance_blockers_until_personal_quest": ["luto_recente", "viuva_do_mar"]
}
```

O executor preenche as 80 + 19 entradas consultando o Codex por `Grep` (nunca `Read`
inteiro de lore) e gera uma tabela de revisão para o dono (§8, D1).

### 3.6 Assinaturas

```python
# services/companion_soul.py
def mode() -> Literal["off", "shadow", "on"]: ...
def derive_values(npc: dict) -> dict[str, int]: ...
def initial_approval(npc: dict, *, origin: str = "recruit") -> int: ...
def ensure_soul(state: dict, companion: dict) -> CompanionSoul: ...
def apply_tags(soul: CompanionSoul, tags: list[ChoiceTag], *, turn: int,
               companion_faction: str) -> tuple[CompanionSoul, int]: ...  # (soul, delta do turno)
def approval_label(approval: int) -> str: ...
def change_phrase(name: str, delta: int) -> str | None: ...
def step_departure(soul: CompanionSoul, *, turn: int, day: int,
                   negative_after_warn: bool, traits: list[str]) -> CompanionSoul: ...
def apply_turn(state: dict) -> dict: ...   # writer único; devolve updates parciais

# services/companion_tags.py
class ChoiceTag(TypedDict):
    id: str
    faction_id: str          # "" se não se aplica
    sign: int                # +1 / -1 (para FACTION_DIRECT)
    source_ref: str          # event_id | "combat:<encounter_id>" | "regex" | "baseline"
def detect_choice_tags(state: dict) -> list[ChoiceTag]: ...
def detect_action_tags(text: str) -> list[str]: ...
def detect_romance_intent(text: str) -> bool: ...

# services/companion_prompt.py
def companion_prompt_block(state: dict, purpose: Literal["story", "npc"],
                           *, target: str = "") -> tuple[str, list[str]]: ...  # (bloco, ids p/ ack)
```

### 3.7 Formato do bloco (exemplo real, cenário Brunna)

```
<COMPANHEIROS>
Brunna Ponte-Alta (engenheira das passagens anãs) — desconfiança.
O que importa: palavra dada; ordem e ofício bem feito.
No turno anterior você ameaçou um mercador. Brunna não gostou disso.
FAÇA: uma fala curta de Brunna reagindo a isso, no tom dela. Não decida nada por ela
além disso; não mude o que o motor registrou.
</COMPANHEIROS>
```

Com romance ativo, acrescenta a linha fixa da R24. Sem companheiro presente: `""`.

### 3.8 Interface off-screen (para a SPEC-302)

```python
class Exposure(TypedDict):
    companion_id: str
    location_id: str      # waiting_at
    days_away: int
    danger_level: int     # do world_map do local

def companions_exposed(state: dict) -> list[Exposure]: ...
def telegraph_companion_danger(state: dict, companion_id: str,
                               kind: Literal["rumor", "pedido_de_ajuda"], day: int) -> dict: ...
def apply_companion_fate(state: dict, companion_id: str,
                         fate: Literal["ferido", "capturado", "morto"], day: int) -> dict: ...
class FateNotTelegraphed(Exception): ...
```

`"morto"` usa `npc_layers.apply_npc_death` ([services/npc_layers.py:102-118](../services/npc_layers.py))
para manter `npcs`/`party` coerentes e emite `companion_fate` (source `engine`). Como
o telegrama chega ao jogador (testemunho/propagação) é decisão da SPEC-302 (Regra
de ouro).

### 3.9 Interface de prisioneiro

```python
def recruit_prisoner(state: dict, prisoner: dict) -> tuple[list[dict] | None, str]: ...
```

Monta o companheiro com `make_companion_from_npc(prisoner, name)` e cria a alma
com `origin="prisoner"` (aprovação 20, `bound="rendicao"` gravado na alma).

## 4. Plano passo a passo (TDD)

### Etapa 0 — Dados e contratos
1. **Testes** (`tests/test_spec300_values.py`): `test_todo_trait_tem_vetor` (80 ids de
   `traits.json` presentes); `test_toda_faccao_tem_vetor` (19); `test_valores_no_intervalo`;
   `test_eixos_fechados`; `test_betrayal_traits_existem_no_catalogo`;
   `test_catalogo_de_tags_schema` (fonte, eixos, magnitude 1–3, regex ⇒ magnitude 1);
   `test_templates_de_missao_pessoal_referenciam_traits_reais`;
   `test_hook_mundo_vivo_em_entities` (36 NPCs `npc_mv_*` com `components.hook`
   não vazio, igual ao "Gancho:" do Codex).
2. **Implementação:** os três JSON; `hook` no gerador e regeneração de
   `entities.json`.
3. **Verificação:** os testes acima + `scripts/validate_content.py`.

### Etapa 1 — Núcleo de valores e aprovação
1. **Testes** (`test_spec300_approval.py`): `test_derive_values_deterministico`
   (mesmo NPC/game_id → mesmo vetor); `test_derive_values_clamp`;
   `test_initial_approval_por_relationship` (rel 7 → 50; rel 10 → 59; rel 3 → 40);
   `test_prisioneiro_comeca_em_20`; `test_delta_alinhado_positivo` e
   `test_delta_desalinhado_negativo` (Brunna × `ameacou`);
   `test_faction_direct_soma_sinal`; `test_tag_cap_e_turn_cap`;
   `test_aprovacao_limitada_0_100`; `test_change_phrase_buckets`
   (2→prompt apenas, 4→"não gostou", 8→"não vai esquecer");
   `test_approval_label_faixas`.
2. **Implementação:** `derive_values`, `initial_approval`, `apply_tags`, rótulos.

### Etapa 2 — Estado, persistência e writer único
1. **Testes** (`test_spec300_persistence_api.py`): `test_save_load_round_trip_alma`;
   `test_save_antigo_sem_companion_souls_carrega`;
   `test_companheiro_legado_ganha_alma_no_primeiro_turno` (origin `legacy`);
   `test_flag_off_nao_escreve_nada` (updates do finalizer iguais aos de hoje);
   `test_finalizer_falha_na_alma_nao_derruba_turno`;
   `test_companion_souls_no_typeddict` (chave aceita pelo grafo).
2. **Implementação:** `state.py`, `persistence._raw_to_state`, `apply_turn`
   mínimo (só `ensure_soul`), hook no `turn_finalizer`.

### Etapa 3 — Detecção de tags e testemunha
1. **Testes** (`test_spec300_tags.py`): um teste por linha da §3.4 com estado
   montado à mão (evento novo vs. baseline; combate `ended` com cada `outcome`;
   `abyss_charge` subiu); `test_evento_antigo_nao_reconta` (id já no baseline);
   `test_regex_ameaca_e_doacao` (frases positivas e negativas, inclusive
   "não vou te ameaçar"); `test_nao_le_faction_impacts_nem_narracao`;
   `test_companheiro_em_espera_nao_reage` (R7);
   `test_mesmo_turno_mesmo_resultado` (determinismo).
2. **Implementação:** `companion_tags.py`; `abyss_charge` no baseline;
   `apply_turn` aplica tags e enfileira reações.

### Etapa 4 — Bloco de prompt e fala espontânea
1. **Testes** (`test_spec300_prompt.py`): `test_sem_companheiro_bloco_vazio`;
   `test_prioridade_despedida_aviso_reacao_descanso`;
   `test_um_companheiro_por_reacao_empate_seeded`;
   `test_descanso_ate_dois_companheiros`; `test_orcamento_600_e_1200`;
   `test_bloco_sem_numero_nem_nome_de_traco_oculto`;
   `test_npc_actor_recebe_bloco_do_alvo`;
   `test_zero_chamadas_llm_extras` (conta invokes de um turno de storyteller e de
   npc_actor com e sem companheiro); `test_ack_so_no_caminho_feliz`
   (FallbackLLM → reação continua pendente); `test_reacao_expira_em_3_turnos`.
2. **Implementação:** `companion_prompt.py`; injeção em `storyteller.py` e `npc.py`;
   `companion_voice_ack` consumido no `apply_turn`.

### Etapa 5 — Aviso, partida, traição, re-recrutamento
1. **Testes** (`test_spec300_departure.py`): `test_aviso_ao_cruzar_25`;
   `test_histerese_limpa_aviso_em_35`; `test_sem_aviso_nao_parte`;
   `test_parte_apos_dia_virado_ou_nova_tag_negativa`;
   `test_partida_espera_turno_narrado_fora_de_combate`;
   `test_partida_remove_da_party_e_ajusta_npc`; `test_trai_so_com_traco_e_sem_blocker`;
   `test_traicao_leva_ouro_limitado_e_aparece_no_recibo`;
   `test_loyal_nunca_trai_e_so_parte_abaixo_de_5`;
   `test_recruitment_decision_estranged_e_betrayed`;
   `test_eventos_companion_left_betrayed_so_engine` (proposta da LLM rejeitada);
   `test_chronicle_milestone_partida`.
2. **Implementação:** `step_departure`; execução no `apply_turn`; códigos em
   `party.recruitment_decision`; tipos de evento + validator + crônica.

### Etapa 6 — Missão pessoal
1. **Testes** (`test_spec300_personal_quest.py`): `test_brunna_usa_gancho_mundo_vivo`;
   `test_template_por_traco` e `test_template_generico`;
   `test_revela_so_no_descanso_com_aprovacao_55`; `test_uma_missao_por_companheiro`;
   `test_completion_ready_so_com_companheiro_ativo_no_local`;
   `test_conclusao_pelo_motor_mais_15_e_loyal`;
   `test_falha_quando_companheiro_parte_ou_morre`.
2. **Implementação:** em `companion_soul.py` + `Quest.personal_of`.

### Etapa 7 — Romance
1. **Testes** (`test_spec300_romance.py`): `test_regex_intencao_romantica`;
   `test_interesse_exige_65`; `test_vinculo_exige_75_e_dois_descansos`;
   `test_compromisso_exige_missao_e_85`; `test_rompido_abaixo_de_40_e_reabre_em_5_dias`;
   `test_blocker_luto_ate_missao_pessoal`; `test_regra_fade_to_black_no_bloco`;
   `test_flag_romance_off_recusa_e_sem_regra`.
2. **Implementação:** em `companion_soul.py` e `companion_prompt.py`.

### Etapa 8 — Interfaces off-screen e prisioneiro
1. **Testes** (`test_spec300_interfaces.py`): `test_companions_exposed_so_em_espera`;
   `test_fate_sem_telegrama_recusa`; `test_fate_telegrama_mesmo_dia_recusa`;
   `test_fate_cancelado_se_jogador_voltou_ou_chamou`;
   `test_fate_morto_sincroniza_npcs_party_e_falha_missao`;
   `test_recruit_prisoner_ignora_relationship_respeita_max_active`.
   Dublê: um "motor" de teste que chama as três funções em sequência por dias.
2. **Implementação:** funções da §3.8 e `party.recruit_prisoner`.

### Etapa 9 — API, UI, playtest
1. **Testes:** `test_api_party_tem_rotulo_sem_numero` (varre o JSON de `/game/state`
   e da resposta do turno: nenhuma chave `approval`/`values`, nenhum inteiro de
   aprovação); `test_companion_feedback_frases`; teste de componente/Playwright
   existente de HUD continua verde; invariantes R30 em `tests/` do playtest.
2. **Implementação:** `api.py`, `web/`, `playtest/invariants.py`, cenário
   `companheiro` em `playtest/scenarios.py`.
3. **Verificação:** `python -m playtest run --all --turns 50` (MockLLM, flag `on`):
   zero erro/violação `error`; perfil `combate` (`--turns 200`, 3 seeds) sem
   `combat.no_progress` e letalidade dentro de M1 (SPEC-285); `npm run build`.

## 5. Critérios de aceite

- [ ] R1–R31 cobertos pelos testes da §4 (todos verdes).
- [ ] Tabelas de valores revisadas pelo dono (D1) ou aceitas como default registrado.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Nenhum `with_structured_output` novo; nenhuma chamada LLM nova (teste R9).
- [ ] Saves antigos (com e sem party) carregam; companheiro legado ganha alma.
- [ ] `RPG_COMPANION_SOUL=off` reproduz o comportamento atual nos testes existentes.
- [ ] Playtest `--all --turns 50` (MockLLM) sem erro e sem violação `error`.
- [ ] M1/M5 da SPEC-285 inalteradas.
- [ ] API e UI sem nenhum número de aprovação.
- [ ] Smoke real da §6 executado e registrado na §9.

## 6. Smoke test com LLM real

DeepSeek (rota padrão), cenário dirigido novo `companheiro` (Brunna Ponte-Alta já
recrutada, alma derivada, em `montanhas_afiadas`), `--real`, teto
`--max-requests 40 --max-cost 0.50` (dentro do teto de US$ 3/dia da VISAO).

1. Ação "Ameaço o mercador com a faca até ele baixar o preço." → API traz
   `companion_feedback` com "Brunna não gostou disso."; turno seguinte (qualquer
   ação neutra) → a narração traz uma fala curta de Brunna reagindo, coerente com
   "desconfiança/cordialidade". Conferir no `transcript` que nenhuma chamada extra
   ao LLM aconteceu (telemetria por turno igual ao baseline do cenário).
2. "Descanso aqui esta noite." → conversa de acampamento; com aprovação ≥ 55
   preparada no cenário, Brunna revela a missão da ponte e a `Quest`
   `pq_npc_mv_brunna_ponte_alta` aparece.
3. "Brunna, o que você acha do que eu fiz lá atrás?" → `npc_actor` responde como
   Brunna, citando a escolha sem número e sem inventar fato.
4. Variante do cenário com aprovação 22: uma escolha negativa → aviso explícito na
   narração seguinte; outra → despedida narrada e, no turno depois, Brunna fora da
   party (sem traição: ela não tem traço de `BETRAYAL_TRAITS`, ou registrar o
   traço real sorteado).
5. Variante com romance em `interesse` e aprovação 76 após 2 descansos → cena de
   vínculo no acampamento termina em corte, sem conteúdo físico explícito
   (leitura humana do transcrito; anexar trecho na §9).

## 7. Riscos & compatibilidade

- **Saves antigos:** campo aditivo com default `{}`; alma criada lazy no 1º fim de
  turno; sem bump de schema. `party` antiga continua passando por
  `backfill_party` ([party.py:434-458](../party.py)) no combate, sem relação com a alma.
- **MockLLM/FallbackLLM:** o MockLLM ignora o bloco; a mecânica (tags, aprovação,
  partida) roda igual, então o playtest MockLLM exercita tudo, menos a qualidade
  da fala. No fallback, reações não são consumidas (R13).
- **Latência/custo:** zero chamadas novas; +≤ 1.200 caracteres de prompt só com
  companheiro presente.
- **Atraso de um turno:** a tag é detectada no fim do turno N (depois do archivist)
  e a fala vem no turno N+1. A UI mostra a frase já no turno N
  (`companion_feedback`). Aceito para manter um só ponto de detecção.
- **Partida em campanhas longas** pode tirar aliados de perfis do playtest e mexer
  em letalidade; por isso R31 roda o perfil `combate` e a partida só ocorre fora de
  combate.
- **Regex de ação** é a fonte mais fraca (o diagnóstico da VISAO critica decisões
  por palavra-chave): por isso magnitude 1, lista fechada, testes com negação, e
  as tags estruturadas (eventos/combate/baseline) dominam.
- **Conteúdo / Google Play:** romance só fade-to-black por regra fixa no prompt,
  mais o interruptor `RPG_COMPANION_ROMANCE`. Não há filtro determinístico de
  saída nesta spec; o questionário de classificação da SPEC-198 deve declarar
  "temas românticos sem conteúdo sexual".
- **Conflito com specs paralelas:** SPEC-297 (pool) e SPEC-298 também tocam NPC e
  rótulos; esta spec não muda `relationship` nem a geração de NPC. Pouso
  sequencial com `wt.sh sync`.

## 8. Decisões pendentes do dono

- **D1 — Tabela de valores.** Aprovar os vetores de 80 traços + 19 fações (o
  executor gera a tabela de revisão na etapa 0). Default se não houver resposta:
  vetores propostos pelo executor com base no Codex.
- **D2 — Quem pode trair.** `BETRAYAL_TRAITS` proposto: ganancioso, cinico,
  rancoroso, dividas, contrabandista, lingua_dupla, guarda_subornavel, apostador,
  usurario_paciente; `BETRAYAL_BLOCKERS`: honesto_demais, leal_a_familia.
- **D3 — O que a traição faz.** Proposto: parte + leva ≤ 25% do ouro (máx. 60) +
  vira desafeto (`grudge`, hook para a SPEC-302 trazê-lo de volta como inimigo).
  Alternativas: só partir hostil; ou entregar a posição do jogador a inimigos
  (depende da SPEC-302).
- **D4 — Elegibilidade a romance.** Proposto: todo companheiro adulto, sem filtro
  pelo gênero do herói, salvo `romance_blockers` até a missão pessoal. Alternativa:
  só um subconjunto sorteado/curado.
- **D5 — Default da flag.** Proposto `on` (com `off` de emergência). Alternativa:
  `shadow` no staging por um dia de playtest antes de `on`.
- **D6 — Missões pessoais fora do `mundo_vivo`.** Proposto: templates por traço,
  sem LLM. Alternativa: 1 chamada LLM na revelação (contraria "sem chamada extra").

## 9. Registro de execução

(preenchido pelo executor: sondas, smoke real, desvios)
