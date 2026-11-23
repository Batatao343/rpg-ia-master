# SPEC-428 — latencia-narracao-tamanho-alvo

> **Status:** `in-progress` (aprovada em 22/11 pelo coordenador, por delegação do dono; código pousado em 23/11 com a flag `off`; revisão Sol APPROVED_WITH_FOLLOWUPS; faltam o pacote de 10 pares com chave real, o `evals compare` off × on, a medição no staging e a leitura do dono antes de ligar)
> **Criada:** 2026-11-22 · **Atualizada:** 2026-11-22
> **Depende de:** nenhuma spec pendente. Contratos que esta spec preserva: SPEC-043 R3 (`done`: fecho com 2 a 3 opções), SPEC-317 R9 (`done`: ordem estático/dinâmico do prompt, `services/prompt_layout.py`), SPEC-202 R11 (`done`: guard de segredo da mediação)
> **Desbloqueia:** — (follow-ups em "Fora de escopo")
> **Risco:** `alto` (muda a prosa, que é o produto, e o prompt de um nó com saída estruturada; o gate passa por evals) → `spec-reviewer` (Opus) obrigatório
> **Requer:** staging (medição `shadow` → `on`, §6); dono: ler o pacote de 10 pares antes de ligar fora do staging (não bloqueia código nem staging)
> **Domínios de revisão:** llm-structured (guia: `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md`)
> **Evidência:** teste que falha antes: com `RPG_NARRATION_SIZE=on`, o prompt do narrador de um turno de cena contém `TAMANHO DA RESPOSTA` com a faixa da classe `cena` (hoje não existe). Oráculo de equivalência: com `off`/ausente, o `SystemMessage` do narrador é byte a byte o golden capturado no código de hoje (Etapa 1). Comportamento real (texto mais curto) só se prova no smoke com chave (§6): o MockLLM não encurta por instrução.
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum evaluator premia tamanho nem exige elemento que a narração curta perderia; ver §2 R11)

---

## 1. Contexto & Objetivo

O jogo é divulgado no TikTok e o dono quer ritmo de pergunta e resposta. Na medição de 13/11 no staging
(`docs/auditorias/latencia-turno-medicao-2026-11-13.md:40`), a IA escrevendo a narração é **55 %** do tempo de
servidor: 4,4 s de mediana por turno, cerca de 2,1 s até a primeira palavra e depois a escrita. A cena tem
~1.350 caracteres e leva ~3 s para ser escrita depois da primeira palavra; a fala de NPC tem ~730 e fecha 1 s
antes (`:55`). A análise anterior (`docs/auditorias/latencia-turno-2026-11-12.md:170-176`, L5) já corrigiu a
conta: parte do tempo entre a primeira palavra e o fim são **campos de cauda do JSON**, que prosa menor não encolhe.

Causa no código (conferida no source de hoje, depois das SPEC-421/422):

- **A7.** O narrador pede "2 a 3 parágrafos" sem limite de palavras (`agents/storyteller.py:2590`) e fecha com
  "2 a 3 OPÇÕES" (`agents/storyteller.py:2213-2217`, SPEC-043 R3). Nenhuma das duas instruções muda por tipo de turno.
- **A9.** Nenhuma chamada passa `max_tokens`: `ChatOpenAI(...)` em `llm_setup.py:504-512`, Gemini em
  `llm_setup.py:437-448`, Anthropic em `llm_setup.py:528-533`. Os únicos tetos são timeouts.
- As instruções de `faction_impacts`, `membership_action`, `proposed_events` e `proposed_quests` aparecem no
  prompt (`agents/storyteller.py:2545-2551`, `:2556-2559`, `:2564-2571`) e de novo nas descrições do schema
  (`agents/storyteller.py:110-125`, `:152-170`). **Correção ao brief:** as duas cópias são tokens de **entrada**
  (o schema vai como definição de ferramenta); nenhuma delas aumenta a saída. Ver "Fora de escopo".

Objetivo: tamanho-alvo da narração por tipo de turno, por instrução no prompt, atrás da flag
`RPG_NARRATION_SIZE` (default `off`; staging em `shadow` e depois `on`). Encurta a cena, a fala mediada pelo
narrador e o descanso; **não** encurta turnos em que o texto longo carrega informação de que o jogador precisa
(local visitado pela 1ª vez, gancho/desfecho de quest, encontro na estrada, achado, abertura). Só o tamanho da
prosa muda: estilo, opções, eventos, quests, itens e fatos decididos pelo motor não mudam.

### 1.1 Medição de base (calculada nesta spec a partir dos dados de 13/11)

Fonte: `docs/auditorias/latencia-l0-2026-11-13/resultado.json` (60 turnos, 4 sessões × 15, roteiro fixo em
`docs/auditorias/latencia-l0-2026-11-13/l0_measure.py:24-39`). Campos por turno: `category`, `narration_chars`,
`first_chunk`, `done`, `delivery.pseudo_streaming`, `server.route`. `narration_chars` é o texto entregue
inteiro, **com** o bloco de opções.

| Grupo (como o L0 rotula) | n | `narration_chars` p50 | p25–p75 | mín–máx |
|---|---|---|---|---|
| `cena`, rota `storyteller` | 20 | **1.379** | 1.225–1.536 | 830–1.849 |
| `conversa` + `npc_novo` com rota `storyteller` (o narrador responde: fala mediada) | 14 | **1.298** | 1.130–1.439 | 928–1.766 |
| `descanso` | 8 | **1.491** | 1.420–1.659 | 1.203–1.883 |
| `viagem` narrada pela IA (região nova, sessão 0) | 1 | 1.799 | — | — |
| `conversa` + `npc_novo` com rota `npc_actor` | 10 | 734 | 690–852 | 493–914 |
| `combate` (início; rota `null`, narrado pelo `combat_agent`) | 4 | 548 | — | 523–679 |
| `viagem` sem IA | 3 | 139 | — | 96–155 |

Dos 14 turnos de fala mediada, 8 chegam sem texto ao vivo (`pseudo_streaming: true`): neles o 1º texto **é** o
texto completo, então encurtar adianta os dois. Dos 8 descansos, 2 também chegam sem stream.

**Velocidade de escrita, separando a cauda fixa.** Regressão linear simples nos 20 turnos de cena (todos com
stream): `done − first_chunk ≈ 0,41 s + 1,78 ms × caracteres` (≈ 563 caracteres/s de prosa). A mediana de
`done − first_chunk` é 2,89 s para 1.379 caracteres, o que dá os ~470 caracteres/s "médios" da auditoria: a
diferença é a parte fixa de ~0,4 s (campos de cauda do JSON + descarga do guard do stream,
`services/narrative_sink.py`, L4(1) da auditoria). Esta spec usa **1,78 ms por caractere cortado** para estimar
ganho; a parte fixa não muda. n = 20, estimativa, não medição causal: o critério de promoção (§6) mede o ganho real.

## 2. Requisitos

- **R1 — Flag.** `RPG_NARRATION_SIZE=off|shadow|on`, default `off`, valor inválido = `off` (via
  `services.env.env_choice`, literal do nome no chamador). Registrada em `config/flags.yaml` (`kind: release`,
  `default: "off"`, `spec: SPEC-428`, `expires: 2027-02-22`, nota "tamanho-alvo da narração por tipo de turno
  (off|shadow|on)"); nas duas listas de `scripts/staging/vercel_env.py` (`OPTIONAL_FLAGS`, `:69-118`, e
  `WORLD_FLAGS`, `:147-`, com o comentário `# SPEC-428 R1: off|shadow|on (ausente = off)`); e no preset
  `scripts/staging/staging_flags.json` com `"RPG_NARRATION_SIZE": "shadow"` e linha datada em `_updated`.
  A troca para `on` no preset é do coordenador depois da medição de base (§6 passo 2).
- **R2 — `off` é o prompt de hoje.** Com a flag ausente, `off` ou inválida, o `SystemMessage` do narrador é byte
  a byte o de hoje, com `RPG_PROMPT_STATIC_FIRST` em `off` e em `on`; nenhum evento novo é logado.
- **R3 — `shadow` mede sem mudar.** Com `shadow`, o prompt é idêntico ao de `off`; só loga `narration.size_class`
  (R9). Serve para a base por classe no staging antes de `on`.
- **R4 — Classe do turno.** Função pura `classify(t) -> SizeClass` sobre o `_StoryTurn` já montado (depois de
  viagem/descanso/tick/encontro, antes do prompt). Ordem de prioridade (a 1ª que casa vence):
  1. `abertura`: `world.turn_count <= 1` (cena de abertura, `agents/storyteller.py:2630-2633`);
  2. `local_novo`: `t.dest` e `t.dest["id"] not in (t.world_before.get("visited") or [])` (mesma regra de
     `first_visit`, `agents/storyteller.py:1470`; `apply_travel` copia o dict, `world_utils.py:205`, então
     `world_before` guarda a lista anterior);
  3. `revelacao`: `"<GANCHO_NOVO>"` ou `"<DESFECHO_DE_QUEST>"` em `t.gancho_novo` (`agents/storyteller.py:379-391`,
     `services/lore_quests.py:701-721`), ou `t.discovery_events` não vazio, ou `t.rumor_find`, ou
     `t.world_note` começando por `"ENCONTRO NA ESTRADA"` (armadilha com números já resolvidos, rastro, abordagem
     social: `agents/storyteller.py:1848,2005-2008,2034,2047-2052`);
  4. `fala_mediada`: `t.scene_state.get("interlocutor_reason") in interlocutor.MEDIATION_REASONS`
     (`agents/storyteller.py:443-444`);
  5. `descanso`: `t.rested_player is not None` (inclui o turno de recuperação, `agents/storyteller.py:1323-1326`);
  6. `cena`: todo o resto (inclui chegada a local já visitado, `rumor_nothing` e entrada em interior já visitado).
  O pulso do mundo do descanso (`[ECOS DO MUNDO]`, `agents/storyteller.py:2055-2084`) **não** vira `revelacao`:
  ele cabe na faixa do descanso e é protegido pela regra de prioridade de R6.
- **R5 — Tabela de alvos.** `TARGETS` em `services/narration_size.py` com, por classe: `shortened: bool`,
  parágrafos (texto), `chars_min`, `chars_max` (faixa medida em `narration_chars`, opções incluídas) e
  `words_min`, `words_max` (o que o prompt pede, prosa antes das opções). Valores da §3.1.
- **R6 — Texto do prompt com `on`.** (a) A linha estática `- Responda em 2 a 3 parágrafos.` passa a ser
  `- Responda em 2 a 3 parágrafos, salvo quando TAMANHO DA RESPOSTA, abaixo, pedir menos.` (constante por modo:
  não quebra o cache de prefixo da SPEC-317 R9). (b) Classe com `shortened=True` recebe, no pedaço **dinâmico**
  (junto da cláusula de opções), uma linha `- TAMANHO DA RESPOSTA: <parágrafos>, entre <words_min> e <words_max>
  palavras antes das opções. Corte descrição e repetição; nunca corte o que está em <EVENTOS_DESTE_TURNO>, fato
  novo, fala com informação, oferta de missão nem a consequência da ação do jogador.` (c) Classe com
  `shortened=False` não recebe linha nenhuma (fica com "2 a 3 parágrafos" como hoje). A cláusula de opções
  (`FECHE com 2 a 3 OPÇÕES…`) continua idêntica em todo modo e classe.
- **R7 — Mecanismo é só instrução.** Nenhum `max_tokens`/`max_output_tokens` novo em `llm_setup.py` nem no nó.
  Justificativa: com saída estruturada, truncar no meio do JSON vira `structured_invalid` → fallback
  determinístico (`agents/storyteller.py:2336-2347`) ou candidato seguinte, ou seja, piora a cauda que esta spec
  quer melhorar; e o maior texto medido (1.883 caracteres) não sugere corrida sem fim que um teto precisasse conter.
- **R8 — Schema intacto.** `StoryUpdate`, `StoryUpdateWithRumors` e as descrições de campo não mudam
  (`model_json_schema()` igual entre modos). As instruções duplicadas no prompt (§1) não mudam.
- **R9 — Telemetria.** Evento `narration.size_class`, 1× por chamada do narrador com flag ≠ `off`, campos
  `mode` (`shadow|on`), `size_class`, `shortened` (bool), `chars_max` (int, 0 se não encurtada). Nunca texto.
  Registrado em `observability/events.py` e em `docs/operacao/EVENTOS_DE_LOG.md`. O tamanho final vem do cliente
  (script de medição, §6) e do `turn_delivery` existente; o nó não ganha log pós-LLM.
- **R10 — Orçamento de tamanho.** `agents/storyteller.py` está a 1 linha do teto (`wc -l` = 3016;
  `tests/size_budget.json:11` = 3017): variação líquida **≤ 0** linhas nele (o plano da §3 dá −4). Texto de prompt
  novo e a classificação moram em `services/narration_size.py`; `llm_setup.py`, `routes/turn.py` e `agents/npc.py`
  não mudam.
- **R11 — Gate de evals.** `governance check` verde; os suítes do job `deterministic-evals`
  (`.github/workflows/eval-gates.yml:80-88`: `state_rules`, `routing`, `memory_write`, `memory_retrieval`,
  `context_grounding`, `generation_boundary`, `narrative_claims`, `player_knowledge`, `dossier_leak`,
  `gameplay_gate`, `encounter_manifest`, `npc_knowledge`, `cards_combat`) rodam duas vezes na mesma máquina, com
  `RPG_NARRATION_SIZE=off` e `=on`, e `evals compare` dá **0** (sem regressão; esperado idêntico). Achado desta
  spec: nenhum adapter de `evals/core/adapters.py` chama `agents.storyteller` (grep vazio em `evals/`), e o
  `narrative_claim_contract` (`evals/evaluators/narrative.py:13-118`) pontua só aceitação/rejeição de claims
  rotuladas, sem tamanho nem presença de opções. Logo o compare prova que a régua compartilhada (guards,
  `narrative_evidence`, `prose_guard`) não mudou, **não** prova a qualidade da prosa curta: essa vem dos critérios
  de staging e da leitura do dono (§6). Nenhum evaluator premia tamanho nem exige elemento que a narração curta
  perderia (os invariantes de `playtest/invariants.py` também não: `check_repeated_opening`, `:1450-1474`, olha
  as 6 primeiras palavras, não o tamanho). Quem implementa não edita evaluator, expected, dataset, baseline nem
  exclusões (`docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`).
- **R12 — Pacote de pares.** `scripts/dev/narration_pairs.py` gera, de forma reprodutível, 10 pares de narração
  (mesmo estado e mesma ação, `off` × `on`) para o dono ler, com contagens por par (§3.4).

### Fora de escopo

- Trocar modelo ou provedor; mexer em timeouts.
- Fala de NPC (`npc_actor`, já ~730 caracteres) e o prompt de `agents/npc.py`.
- Narração de carta/combate rodada a rodada, início de combate (o narrador devolve `COMBAT START` sem LLM,
  `agents/storyteller.py:1898-1914`; quem narra é o `combat_agent`) e o resumo de fim de combate (SPEC-073/199).
- Abertura/prólogo (SPEC-423) e a cena de turno 1 (classe `abertura`, não encurtada).
- Fila de ação (SPEC-427).
- Mudar estilo da prosa além do tamanho, o número de opções (SPEC-043 R3) ou o formato delas.
- **Follow-up L4(1):** descarregar o guard quando o campo `narrative` fecha no JSON, sem esperar os campos de
  cauda (`docs/auditorias/latencia-turno-2026-11-12.md:147-148`). É a parte fixa de ~0,4 s da §1.1.
- **Follow-up, deduplicação prompt × schema:** são tokens de entrada; o efeito na 1ª palavra não é mensurável
  com os dados de hoje (o log não registra tokens por campo, `docs/auditorias/latencia-turno-medicao-2026-11-13.md:87`)
  e tirar instrução pode mudar o que o modelo propõe em `faction_impacts`/`proposed_events`, que alimentam o motor
  (fere I2 em produção, sem teste offline que pegue). Precisa de spec própria com medição de tokens de entrada e
  smoke de precisão desses campos.
- **Follow-up opcional de eval:** um oráculo determinístico sobre narrações gravadas (faixa por classe, opções
  presentes) seria trabalho do papel de autoria de eval (D-09); esta spec não depende dele.

### Invariantes

- **I1 — `off` = hoje.** Para 6 estados de teste (uma por classe), com flag ausente e `off`, e com
  `RPG_PROMPT_STATIC_FIRST` `off` e `on`, o conteúdo do `SystemMessage` do narrador é igual ao golden capturado
  no código de antes da mudança. (teste: `test_narrator_prompt_off_matches_golden[...]`)
- **I2 — O motor decide igual.** Com o mesmo LLM roteirizado (mesma `StoryUpdate` com `proposed_events`,
  `proposed_quests`, `items_gained`, `faction_impacts`, `introduced_npcs`) e o mesmo estado, o dict devolvido por
  `storyteller_node` é igual com `off`, `shadow` e `on` (eventos, quests, itens, mundo, jogador, mensagens).
  (teste: `test_size_mode_does_not_change_engine_output[...]`)
- **I3 — Schema igual.** `StoryUpdate.model_json_schema()` e `StoryUpdateWithRumors.model_json_schema()` são
  iguais com `off` e `on`, e o schema passado a `narrate` é o mesmo objeto de classe. (teste:
  `test_size_mode_keeps_story_schema`)
- **I4 — Guard de FallbackLLM.** Com `on` e um LLM que devolve `AIMessage`, o nó não levanta, loga
  `structured_invalid` e usa `_deterministic_story_fallback`, como em `off`. (teste:
  `test_size_on_fallback_llm_aimessage_guard`)
- **I5 — NPC e combate intocados.** Com `on`, o prompt de `agents/npc.py` e o da narração de combate são iguais
  aos de `off`. (teste: `test_size_on_does_not_touch_npc_or_combat_prompt`)
- **I6 — Opções sempre pedidas.** Em todo modo e classe, o prompt do narrador contém a cláusula de opções
  byte a byte igual à de hoje. (teste: `test_options_clause_unchanged_every_class`)
- **I7 — Classificação total e determinística.** Todo `_StoryTurn` de teste cai em exatamente uma classe, pela
  ordem de R4; tabela de casos cobre cada regra e cada empate (ex.: 1ª visita + gancho = `local_novo`; mediação +
  descanso = `fala_mediada`). (teste: `test_classify_priority[...]`)

## 3. Design técnico

### 3.1 Tabela de tamanho-alvo por tipo de turno

Ganho = Δ caracteres × 1,78 ms (§1.1), no `done` (texto completo); em turno sem stream, também no 1º texto.
"Centro" usa o meio da faixa; "teto" usa o limite superior (estimativa conservadora, usada no critério de promoção).

| Tipo de turno (classe) | Hoje (medido, p50) | Alvo proposto | Ganho estimado no `done` | O que se perde |
|---|---|---|---|---|
| Cena / exploração (`cena`) | 1.379 car., n = 20 | **2 parágrafos curtos** (2 a 4 frases cada); **750–1.000** car. (90–140 palavras antes das opções) | centro 0,90 s · teto 0,67 s | ~⅓ da descrição de ambiente; menos frases de clima. Fatos, fala e consequência ficam (R6) |
| Fala mediada pelo narrador (`fala_mediada`) | 1.298 car., n = 14 (8 sem stream) | **1 a 2 parágrafos curtos**; **600–900** car. (70–120 palavras) | centro 0,98 s · teto 0,71 s (nos 8 sem stream, o mesmo no 1º texto) | Descrição de quem está presente e de reações secundárias. Risco: o guard de segredo troca um parágrafo inteiro (`agents/storyteller.py:499-527`); com 2 parágrafos, a troca pesa metade do texto (§7) |
| Descanso (`descanso`) | 1.491 car., n = 8 | **2 parágrafos curtos**; **800–1.100** car. (100–150 palavras) | centro 0,96 s · teto 0,70 s | Prosa da noite e do amanhecer. Fica: recuperação, hora, o pulso do mundo e o que está em `EVENTOS_DESTE_TURNO` |
| Chegada a local já visitado (vira `cena`) | não medido (n = 0: no L0 só a viagem da sessão 0 foi narrada, e era região nova) | o mesmo da cena | não estimado | Redescrição de lugar que o jogador já viu |
| Chegada a local novo (`local_novo`) | 1.799 car., n = 1 | **não muda** (2 a 3 parágrafos) | 0 | Nada. O texto é o mapa: saídas, quem está ali, perigo. Cortar faz o jogador perguntar de novo (mais um turno) |
| Revelação, gancho ou desfecho de quest, encontro na estrada, achado (`revelacao`) | não medido (n = 0: nenhum dos 60 turnos teve evento, `docs/auditorias/latencia-turno-medicao-2026-11-13.md:59`) | **não muda** | 0 | Nada. É informação que o jogador precisa (como soube do gancho, números da armadilha já resolvidos) |
| Abertura, turno 1 (`abertura`) | não medido no L0 | **não muda** | 0 | Nada (a abertura é da SPEC-423) |
| Início de combate | 548 car., n = 4 | **não muda** (fora: `combat_agent`) | 0 | — |
| Fim de combate | não medido | **não muda** (fora: SPEC-073/199) | 0 | — |
| Fala com NPC já criado (`npc_actor`) | 734 car., n = 10 | **não muda** (fora) | 0 | — |

**Ganho no mix do L0** (60 turnos: 20 cenas, 14 falas mediadas, 8 descansos encurtados): centro
(20 × 0,90 + 14 × 0,98 + 8 × 0,96) / 60 ≈ **0,66 s por turno** em média, ≈ 0,94 s nos 42 turnos encurtados;
teto ≈ 0,48 s por turno, ≈ 0,69 s nos encurtados. Consistente com o "cortar um terço tira cerca de 1 s" dito ao
dono em 13/11 (a cena cai 37 % no centro da faixa). Custo: menos tokens de saída no narrador, na mesma proporção
da prosa cortada; não estimado em dinheiro (o log não separa tokens por campo).

**Palavras × caracteres.** O prompt pede palavras (o modelo conta palavras melhor que caracteres); a faixa medida
é em caracteres. Conversão usada [H]: ~5,9 caracteres por palavra em pt-BR, mais ~150–200 caracteres do bloco
de opções (3 linhas `— …` + `— Ou outra ação.`). A Etapa 6 calibra os números de **palavras** com o pacote de pares
se a mediana de caracteres cair fora da faixa; a faixa de caracteres é o contrato e só muda com o dono.

### 3.2 Arquivos

- **Novo `services/narration_size.py`** (≤ 150 linhas; nenhuma função > 60):
  - `SizeClass = Literal["abertura", "local_novo", "revelacao", "fala_mediada", "descanso", "cena"]`
  - `@dataclass(frozen=True) class SizeTarget: size_class: SizeClass; shortened: bool; paragraphs: str;
    chars_min: int; chars_max: int; words_min: int; words_max: int`
  - `TARGETS: dict[SizeClass, SizeTarget]` (valores da §3.1; não encurtadas com `shortened=False` e `0` nos números)
  - `OPCOES_CLAUSE: str` — o literal de `agents/storyteller.py:2214-2216`, movido sem mudar um byte
  - `PARAGRAPH_RULE_OFF = "- Responda em 2 a 3 parágrafos."` e `PARAGRAPH_RULE_ON` (R6a)
  - `def mode() -> str` — `env_choice("RPG_NARRATION_SIZE", ("off", "shadow", "on"), "off")`
  - `def paragraph_rule() -> str` — `PARAGRAPH_RULE_ON` só com `on`
  - `def classify(t: Any) -> SizeClass` — R4; lê só atributos (`getattr(..., None)` tolerante), não muta `t`
  - `def size_line(target: SizeTarget) -> str` — a linha de R6b
  - `def closing_clause(t: Any) -> str` — `OPCOES_CLAUSE` em `off`/`shadow`; `OPCOES_CLAUSE + size_line(...)` em
    `on` para classe encurtada; com flag ≠ `off`, loga `narration.size_class` (R9) uma vez
- **`agents/storyteller.py`** (saldo −4 linhas):
  - `:18` `from services import archive_record, latency_flags, quest_log` ganha `narration_size` na mesma linha;
  - `:2213-2217` (5 linhas) viram `t.opcoes_clause = narration_size.closing_clause(t)` (1 linha);
  - `:2590` `    - Responda em 2 a 3 parágrafos.` vira `    {narration_size.paragraph_rule()}` dentro do f-string
    de `_rules_a` (mesmo recuo de 4 espaços; continua no pedaço estático).
  - `closing_clause` é chamado em `_story_prompt_blocks`, depois de `t.gancho_novo`, `t.scene_state` (mediação) e
    das notas de viagem/descanso/encontro estarem prontas (`:2163-2207`): o executor confirma a ordem na Etapa 0.
- **`config/flags.yaml`**, **`scripts/staging/vercel_env.py`**, **`scripts/staging/staging_flags.json`**: R1.
- **`observability/events.py`**, **`docs/operacao/EVENTOS_DE_LOG.md`**: evento de R9.
- **Novo `scripts/dev/narration_pairs.py`** e **novo `docs/spec428/pares_casos.json`**: §3.4.
- **Novos testes** em `tests/test_narration_size.py` (unidade + prompt) e `tests/test_narration_pairs_script.py`;
  golden em `tests/fixtures/narration_size_off/<caso>.txt`.

### 3.3 Exemplo do prompt com `on` (classe `cena`, ordem original)

```
<INSTRUÇÕES>
    - Responda em 2 a 3 parágrafos, salvo quando TAMANHO DA RESPOSTA, abaixo, pedir menos.
    ...
    - FECHE com 2 a 3 OPÇÕES concretas de ação, cada uma numa linha iniciada por '— ', e termine com '— Ou outra ação.' (dê rumo ao jogador; as opções mecânicas de combate vêm à parte).
    - TAMANHO DA RESPOSTA: 2 parágrafos curtos (2 a 4 frases cada), entre 90 e 140 palavras antes das opções. Corte descrição e repetição; nunca corte o que está em <EVENTOS_DESTE_TURNO>, fato novo, fala com informação, oferta de missão nem a consequência da ação do jogador.
```

Com `RPG_PROMPT_STATIC_FIRST=on`, a linha de parágrafos fica no bloco estático e a de tamanho no dinâmico,
depois do `DYNAMIC_LABEL` (`services/prompt_layout.py:23,40`): "abaixo" vale nas duas ordens.

### 3.4 Pacote de 10 pares para o dono (reprodutível e barato)

- `docs/spec428/pares_casos.json`: 10 casos fixos, cada um com `id`, `expected_class`, `state` (estado completo
  serializado, gerado uma vez com `tests/factories.make_state` + patch e commitado) e `action`. Distribuição:
  3 `cena`, 2 `fala_mediada`, 2 `descanso`, 1 chegada a local já visitado (`cena`), e 2 controles não encurtados
  (1 `local_novo`, 1 `revelacao`, a armadilha "ENCONTRO NA ESTRADA"). Casos escolhidos sem NPC novo a gerar (sem chamada extra
  de ficha).
- `scripts/dev/narration_pairs.py --cases docs/spec428/pares_casos.json --out docs/spec428/pares-<data>`:
  para cada caso roda `storyteller_node` (via `get_llm`, rota de hoje) com `RPG_NARRATION_SIZE=off` e depois
  `=on`, e grava `pares-<data>.md` (por par: classe, ação, texto `off`, texto `on`, caracteres, parágrafos,
  número de linhas de opção) e `pares-<data>.json` (só contagens, `git_sha`, modelo/provedor de cada chamada).
  Recusa rodar com `RPG_FORCE_MOCK=1` ou sem chave, salvo `--mock` (usado só no teste). Conta TODA chamada de LLM (narrador e qualquer
  outro `get_llm`, proibido no par) e recusa antes da 1ª se `2 × casos × samples` passar de 30; o pulso do mundo
  é neutralizado nos dois braços e cada par grava o hash do prompt sem as linhas de tamanho (falha se divergir). Custo: 20 chamadas do narrador ≈ US$ 0,06 (US$ 0,0028 por chamada no L0,
  `resultado.json`, `llm_by_tier.fast.cost_usd` do 1º turno).
- Reprodutível = mesmos casos, mesmo comando, mesmo sha; o texto varia entre execuções (temperatura 0,7, sem
  seed no provedor). `--samples N` (default 1) repete só para contagem de tamanho, sem entrar no `.md`.

### Concorrência

N/A — sem thread/async/cancelamento. Leitura de env por chamada, como as demais flags de `services/latency_flags.py`.

## 4. Plano passo a passo

Antes do 1º teste, o executor lê `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § llm-structured e § sql-rls item 5
("modo `off` byte a byte") e cobre cada item aplicável.

### Etapa 0 — Confirmar o source

1. Conferir as linhas citadas (`agents/storyteller.py:18,1351,1470,2163-2217,2590,2602-2611`;
   `llm_setup.py:504-512`); `wc -l agents/storyteller.py` contra `tests/size_budget.json`.
2. Confirmar que `closing_clause(t)` em `:2213` vê `t.gancho_novo`, `t.scene_state`, `t.world_note`,
   `t.discovery_events`, `t.rumor_find`, `t.rested_player`, `t.dest`, `t.world_before` já finais. Se algum for
   montado depois, mover só a chamada (sem crescer o arquivo) e registrar aqui.

### Etapa 1 — Golden de hoje (código intocado)

1. **Testes** (`tests/test_narration_size.py`): `test_narrator_prompt_off_matches_golden[caso × static_first]`
   captura o `SystemMessage` via o `_Spy` de `tests/test_ambient_consumers.py` (padrão de
   `tests/test_spec309_prompts.py:35-49`) para 6 estados (um por classe) e compara com
   `tests/fixtures/narration_size_off/<caso>-<sf>.txt`, gravados **neste commit, com o código de hoje**.
   Se algum pedaço do prompt variar entre execuções, escolher outro estado; não normalizar o texto.
2. **Commit** só com teste + golden, verde. É o oráculo de equivalência das etapas seguintes.

### Etapa 2 — Módulo `narration_size` (testes primeiro)

1. **Testes:** `test_mode_parsing` (ausente/`off`/`shadow`/`on`/`" ON "`/`"true"`/`"1"` → só `on` e `shadow`
   valem; `"true"`/`"1"` = `off`); `test_classify_priority[...]` (I7: uma linha por regra de R4 e os empates);
   `test_targets_table` (faixas da §3.1; `chars_min < chars_max`; não encurtadas com `shortened=False`);
   `test_opcoes_clause_is_todays_literal` (igual ao literal de hoje copiado no teste);
   `test_on_mode_prompt_has_class_target[cena|fala_mediada|descanso]` (**falha antes**: a linha
   `TAMANHO DA RESPOSTA` com as palavras da classe aparece só com `on`);
   `test_on_mode_unshortened_classes_have_no_size_line[local_novo|revelacao|abertura]`.
2. **Implementação:** `services/narration_size.py` (§3.2).

### Etapa 3 — Costura no narrador, flag e evento

1. **Testes:** `test_shadow_prompt_equals_off` (R3); `test_shadow_and_on_log_size_class` e
   `test_off_logs_nothing` (R9, com `caplog`/telemetria de teste); gate de flags (`config/flags.yaml`, suíte
   default) e teste de `vercel_env` que já confere as duas listas; registro de evento
   (`observability/events.py`).
2. **Implementação:** as 3 edições de `agents/storyteller.py` (§3.2), flag (R1), evento (R9).
3. **Verificação:** golden da Etapa 1 verde em `off`; `bash scripts/dev/py.sh -m pytest tests/test_size_budget.py`
   verde (storyteller ≤ 3016 − 4).

### Etapa 4 — Invariantes

1. **Testes:** I2 `test_size_mode_does_not_change_engine_output[off|shadow|on]` com `ScriptedLLM`
   (`tests/fakes/scripted_llm.py`) devolvendo uma `StoryUpdate` com evento, quest, item e impacto de facção;
   I3 `test_size_mode_keeps_story_schema`; I4 `test_size_on_fallback_llm_aimessage_guard`;
   I5 `test_size_on_does_not_touch_npc_or_combat_prompt`; I6 `test_options_clause_unchanged_every_class`.
2. **Verificação:** `bash scripts/dev/pt.sh tests/test_narration_size.py tests/test_spec309_prompts.py
   tests/test_ambient_consumers.py tests/test_size_budget.py` (mais os testes do narrador que o executor
   encontrar com `Grep "storyteller_node" tests/`), `-n 2` no máximo.

### Etapa 5 — Script do pacote de pares

1. **Testes** (`tests/test_narration_pairs_script.py`): com `--mock`, gera 10 pares, a classe de cada caso
   bate com `expected_class`, o `.json` tem só contagens (nenhum texto); sem chave e sem `--mock`, sai com
   erro antes de chamar LLM; com `RPG_FORCE_MOCK=1` e sem `--mock`, recusa.
2. **Implementação:** `scripts/dev/narration_pairs.py` + `docs/spec428/pares_casos.json` (§3.4).

### Etapa 6 — Evals e smoke real

1. `bash scripts/dev/py.sh -m evals.core.governance check --root .`; `evals run` dos suítes de R11 com
   `RPG_NARRATION_SIZE=off` e de novo com `=on` (mesma máquina, `--run-id spec428-off`/`spec428-on`);
   `evals compare --baseline <off> --current <on>` sai 0. Não comparar contra `evals/baselines/deterministic.json`
   localmente (sai 2 por plataforma, `evals/README.md:69-72`).
2. Smoke real §6 passo 1 (pacote de pares). Se a mediana de caracteres de alguma classe encurtada cair fora da
   faixa, ajustar **só** `words_min/words_max` da classe (uma vez), regenerar e registrar na spec.

## 5. Critérios de aceite

- [ ] R1–R12 com teste ou passo de smoke que os prova; I1–I7 com os testes nomeados.
- [x] `off`/ausente: golden da Etapa 1 verde nas duas ordens de prompt. O revisor rodou o golden contra a `main` (12 passed): ele veio do código antigo (`91c3e11e`).
- [x] `agents/storyteller.py` com saldo ≤ 0 linhas; `tests/test_size_budget.py` verde. 3016 → 3012 linhas.
- [x] Nenhum diff em `llm_setup.py`, `agents/npc.py`, `routes/turn.py`, `StoryUpdate*`, `evals/`.
- [ ] `evals compare` off × on sai 0 (R11).
- [x] Guard de FallbackLLM coberto com `on` (I4); nenhum `with_structured_output` novo.
- [ ] Pacote de 10 pares gerado com chave real e commitado em `docs/spec428/`.
- [ ] Testes do escopo verdes (subagente); `uv run pytest` completo verde no pouso (coordenador).
- [x] Saves antigos continuam carregando (nada persistido muda: a classe não vai para o estado).
- [x] Revisão `spec-reviewer` (Opus) APPROVED. Veredito final `APPROVED_WITH_FOLLOWUPS` em `928e04e7`, depois de duas rodadas com `CHANGES_REQUIRED` no script de pares (entradas diferentes entre os braços; `get_llm` falso vazando para outros testes). Os P3-4 e P3-5 foram aplicados depois.
- [ ] `done` só depois do §6 passo 3 (promoção no staging) e da leitura do dono (§8 D2); até lá, `in-progress`
      com a flag `off` no código e `on` só no preset do staging.

## 6. Smoke test com LLM real

O MockLLM devolve texto fixo e não encurta por instrução: só estes passos provam o comportamento.

1. **Pacote de pares (local, chave real, ≈ US$ 0,06).**
   `bash scripts/dev/py.sh scripts/dev/narration_pairs.py --cases docs/spec428/pares_casos.json --out docs/spec428/pares-AAAA-MM-DD`.
   Passa se: nas 7 narrações `on` encurtadas, ≥ 5 dentro da faixa de caracteres da classe e nenhuma acima de
   `chars_max × 1,2`; as 10 `on` com ≥ 2 linhas de opção `— ` e o fecho `— Ou outra ação.`; os 2 controles `on`
   com tamanho a ±20 % do seu par `off`; nenhuma resposta caiu em `structured_invalid`. O `.md` é o que o dono lê.
2. **Base no staging (`shadow`).** Deploy com o preset `RPG_NARRATION_SIZE=shadow`. Medição com o protocolo do
   L0 (`docs/auditorias/latencia-l0-2026-11-13/l0_measure.py`; cópia em `docs/spec428/medir.py`, sem editar o
   original, acrescentando por turno `paragraphs`, `options_lines` e o `size_class` lido do log
   `narration.size_class`; o texto não é gravado). 4 sessões × 15 turnos, ≈ US$ 0,19. Depois, coordenador troca o
   preset para `on` (linha datada em `_updated`) e repete igual.
3. **Critério de promoção `shadow` → `on` (staging, n por classe ≥ 8; cena ≥ 15):**
   - P1: mediana de `narration_chars` dentro da faixa em `cena` (750–1.000), `fala_mediada` (600–900) e
     `descanso` (800–1.100); classes não encurtadas a ±15 % da base.
   - P2: `done` p50 menor que a base em ≥ **0,65 s** (`cena`), ≥ **0,70 s** (`fala_mediada`) e ≥ **0,70 s**
     (`descanso`) — o ganho "teto" da §3.1.
   - P3: `log_fallback("storyteller", "structured_invalid")` (`agents/storyteller.py:2341`) e `token_replace`
     do `turn_delivery` sem alta (≤ base + 1 ocorrência em 60 turnos e ≤ base + 5 pp, respectivamente);
     `narrative.rejected` por turno sem alta, medido
     separado por `kind` (ouro rejeitado, SPEC-091 R6; segredo mediado, SPEC-202 R11): com 1–2 parágrafos os dois
     guards que apagam parágrafo inteiro pesam mais (P3-2 da revisão).
   - P4: fração de narrações com ≥ 2 linhas de opção ≥ a da base − 5 pp.
   - Falhou P1 ou P4: voltar o preset para `shadow`, recalibrar palavras (Etapa 6.2) e medir de novo.
     Falhou P2 com P1 ok: registrar (a velocidade não é a que a §1.1 estimou) e levar ao dono; não ligar fora do staging.
4. Resultado (tabelas por classe, sem texto) em `docs/spec428/medicao-AAAA-MM-DD.md`.

## Não rodou e por quê

- **Pouso (23/11, coordenador):** os critérios R11 (`evals compare` off × on) e R12 (pacote de 10 pares com chave real) ficam abertos; nenhum dos dois é necessário para o pouso com a flag `off` e os dois são exigidos antes de ligar. O smoke de turno no staging está parado desde 23/11 13:11 UTC (DeepSeek devolvendo 402 e teto diário estourado).

Atualizado após a execução e a revisão sol (`handoffs/SPEC-428-sol-review.md`):

- `evals compare` `off` × `on` (R11 / Etapa 6.1) **não rodou**. Nenhum adapter de `evals/` chama o narrador
  (conferido pelo revisor: `evals/core/adapters.py` não importa `main` nem `agents.storyteller`), então o compare
  seria idêntico para esta mudança; a prova de equivalência de `off` é o golden de `tests/fixtures/narration_size_off/`.
- O smoke §6 (passo 1, pacote com chave real) é do coordenador; o pacote não foi rodado com chave.
- §6 passos 2–3 dependem de deploy no staging (coordenador); o passo 1 é local com chave real, do coordenador, sem depender do staging.
- Ligar fora do staging depende da leitura do dono (§8 D2); não é passo da execução.

## 7. Riscos & compatibilidade

- **Saves antigos:** nada persistido muda (a classe vive só no prompt e no log).
- **MockLLM/FallbackLLM:** MockLLM ignora a instrução (texto fixo); o guard de `AIMessage` não muda e é testado
  com `on` (I4).
- **Prosa pior** (o maior risco): o corte pode levar informação junto. Mitigação: regra de prioridade em R6b,
  classes de informação não encurtadas, controles no pacote de pares, P1/P4 e leitura do dono.
- **Guard de segredo na mediação:** com 1–2 parágrafos, a troca de parágrafo da SPEC-202 R11 apaga uma fração
  maior do texto quando dispara. O guard não muda; a frequência entra em P3 (`narrative.rejected` com
  `kind=mediation`).
- **Repetição de abertura** (`narrative.repeated_opening`, `playtest/invariants.py:1471`): texto curto não muda
  a regra das 6 palavras; observar nos pares.
- **Cache de prefixo:** a linha estática muda uma vez por modo, não por turno (R6a); com `on` o 1º turno depois do
  deploy perde o prefixo uma vez.
- **Latência:** ganho estimado 0,66 s por turno no mix do L0 (0,48 s conservador); não toca a 1ª palavra (2,1 s)
  nem a cauda fixa (~0,4 s, follow-up L4(1)).
- **Quota/custo:** menos tokens de saída do narrador; pacote + 2 medições ≈ US$ 0,45 no total.

## 8. Decisões

- **D1 — Tamanho-alvo (coordenador, por delegação).** A tabela da §3.1 é decisão do coordenador por delegação do
  dono ("faz tudo ai… eu autorizo a fazer tudo que vc pode fazer", 22/11), a partir da recomendação de 13/11
  ("2 parágrafos curtos para cena, pensando em TikTok; o tamanho é escolha sua"), que o dono ouviu e não
  respondeu item a item. **O dono tem veto e ajuste** sobre qualquer linha da tabela; ajuste muda só os números
  de `TARGETS` (e o golden de `on`), sem nova spec.
- **D2 — Ligar para todos (dono).** A flag entra `off` no código e só o staging liga (`shadow` → `on`). Ligar fora
  do staging depende de o dono ler o pacote de 10 pares e as narrações reais do staging; sem essa leitura, fica
  no staging. A prosa é o produto: qualidade acima de velocidade.
- **D3 — Sem teto de tokens** (R7) e **sem deduplicação prompt × schema** nesta spec (follow-up): decisões
  técnicas do autor, revisáveis pelo revisor.
- Nenhuma linha de `docs/guias/DECISOES_FIXAS.md` é contrariada (D-09 respeitado: nenhum eval é editado).

- **22/11, coordenador:** spec aprovada para execução. O dono ouviu a explicação e a recomendação ("2 parágrafos curtos para cena") em 13/11, não respondeu item a item e em 22/11 delegou. A tabela de alvos (D1) fica como o autor propôs, com veto e ajuste do dono. Correção ao que foi dito ao dono em 13/11: o ganho estimado é de ~0,66 s por turno no mix da L0 (0,48 s na conta conservadora), não ~1 s; cerca de 0,4 s da escrita é cauda do JSON, que texto menor não encurta. Os gates automáticos não julgam a qualidade da prosa curta (nenhum adapter de `evals/` chama o narrador): quem decide ligar fora do staging é o dono, lendo o pacote de 10 pares (D2). Risco `alto`, `spec-reviewer`.

## Diário de execução e desvios (22–23/11)

- **Controle `revelacao`:** o pacote usa a armadilha `ENCONTRO NA ESTRADA` (números já resolvidos), não
  `<GANCHO_NOVO>`. Motivo: é o subtipo de `revelacao` mais comum em jogo e não depende de tick de quest de mundo;
  `<GANCHO_NOVO>` é coberto por `test_classify_priority`. (§3.4 e o golden refletem a armadilha.)
- **Estados do pacote:** vêm de `_base_state()` de `scripts/dev/narration_pairs.py` (estado mínimo fixo,
  serializado em `pares_casos.json`), não de `tests/factories.make_state` (o script de `scripts/` não importa
  `tests/`). Após a revisão (P3-1) `fala-mediada-1/2` e `cena-2` ganharam 1 NPC já criado e presente (Velha Magda)
  e 1 facção conhecida (`legiao_ferro`), para mostrar o risco real de cortar fala com informação.
- **Etapa 0, nota:** o golden de `off` foi capturado em `91c3e11e`, antes do código de produto (`62e53c17`);
  o revisor reproduziu os 12 casos na `main` (12 passed). `closing_clause(t)` vê os campos finais na ordem de
  `_story_prompt_blocks`; nenhuma chamada precisou ser movida.
- **Leitura da flag:** `RPG_NARRATION_SIZE` usa `env_choice` (`strip` + `lower`): `" ON "` vale `on`, como nas
  flags irmãs; qualquer valor fora de `off|shadow|on` vale `off`.
- **P2-1 da revisão (pacote):** `_run_one` troca `_story_world_pulse` por no-op nos dois braços; todo `get_llm`
  fora do narrador é contado e levanta; o teto é checado antes da 1ª chamada; `input_hash` por par.
