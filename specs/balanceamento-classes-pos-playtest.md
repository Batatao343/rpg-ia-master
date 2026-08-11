# SPEC — Balanceamento das 5 Posturas pós-playtest (knobs `[BALANCEAR]`)

> **Status:** `done`
> **Criada:** 2026-07-19 · **Atualizada:** 2026-08-02 (rebase pós-cutover de Cartas v4)
> **Depende de:** [refatoracao-sistema-classes](refatoracao-sistema-classes.md) `done` ·
> [arvores-habilidade-classes](arvores-habilidade-classes.md) `done` ·
> [playtest-agente-curioso-entropia](playtest-agente-curioso-entropia.md) `done` ·
> (recomendado) [isolar-cache-runtime](isolar-cache-runtime.md) — playtest sem poluir `data/`
> **Desbloqueia:** tiers 5+ (nível 9–20, spec futura — números base precisam estar sãos antes)

---

## 1. Contexto & Objetivo

O épico do sistema de classes fechou 2026-07-19 com números **chutados de
propósito**: `data/classes.json` carrega **8 knobs marcados `[BALANCEAR]`**
(gatilhos de Entropia/Carga e regras especiais das 5 classes — taunt do Devoto,
blood_leak do Sangromante, decay_nearby do Corruptor, caldeira do Arcanista,
on_ally_suffer do Médico). ESTADO_ATUAL/ROADMAP cravam o próximo passo:
"balanceamento dos números `[BALANCEAR]` após playtest".

Hoje não há dado: o harness (Fase 5) roda por default só com Devoto do Abismo
(`playtest/runner.py`), e a telemetria por turno não registra Entropia/Carga —
impossível julgar starvation/flooding de recurso ou acúmulo de Carga sem olhar
transcrito na mão.

Objetivo: instrumentar o harness p/ medir as 5 classes, rodar baseline
mock + playtest real curto, e ajustar os 8 knobs **nos geradores vigentes**:
`scripts/gen_classes_v2.py` para a configuração das classes e
`scripts/gen_cards_v4.py` para os marcadores mecânicos das Cartas. O catálogo
legado `data/player_abilities.json` foi removido pelo cutover conflito-13 e não
deve ser recriado.

Princípio: "Mecânica é Python" — tuning é mudança de constante determinística,
verificável por invariante, não por impressão de prosa.

## 2. Requisitos

- **R1 — Harness por classe.** `playtest run` aceita `--class <id>` (as 5:
  `devoto_do_abismo`, `sangromante`, `corruptor`, `arcanista_cinzento`,
  `medico_de_campo`); default continua Devoto. Perfil × classe × seed
  reproduzível.
- **R2 — Telemetria de recurso.** JSONL por turno ganha `entropy`,
  `max_entropy`, `abyss_charge`, `abyss_tier`; `summary.json` agrega por
  campanha: turnos com Entropia 0 em combate (starvation), turnos com Entropia
  cheia sem gasto (flooding), pico/fim de Carga, patamar máximo atingido,
  ativações de regra especial (taunt/leak/boiler/embrace/purga) e de
  consequência (Insônia/Cicatriz/Transformação/Dependência/Recidiva).
- **R3 — Relatório comparativo.** `playtest report` ganha seção **Classes**:
  matriz classe × (sobrevivência, nível final, starvation %, Carga final,
  mortes) + suporte a `--baseline` p/ comparar antes/depois do tuning.
- **R4 — Baseline ANTES do tuning.** Rodada mock (5 classes × perfis vitais ×
  ≥2 seeds × 50 turnos) + rodada REAL curta (4 perfis vitais × 30 turnos,
  classes variadas, tetos `--max-requests`/`--max-cost`) gravadas e
  referenciadas na spec antes de mexer em qualquer número.
- **R4b — Fiação v4 antes do tuning.** Cada gatilho/regra/consequência deve ser
  alcançável pelo fluxo real `run_round` usando Cartas v4, com teste de integração
  determinístico. Helpers chamados apenas por teste unitário não contam como
  mecânica entregue. Os marcadores autorais ficam nas Cartas geradas, em campo
  fechado, e nunca reintroduzem o catálogo legado.
- **R5 — Critérios de balance (viram asserts do relatório, não vibe):**
  - a) nenhuma classe morre ≥2× a média das outras nos mesmos perfis/seeds;
  - b) starvation < 30% dos turnos de combate em toda classe (recurso existe
    p/ ser gasto), flooding < 50% (gatilho não é irrelevante);
  - c) Carga atinge `leve` em campanha de 50 turnos p/ toda classe, e `severo`
    não é alcançável só com rotina defensiva (sem escolha deliberada);
  - d) caldeira do Arcanista estoura às vezes (>0) mas não é a causa
    dominante de dano sofrido da classe (<30%);
  - e) nenhuma consequência de descanso deixa classe sem caminho de
    recuperação (compatível com invariante `downed.no_recovery_path`).
- **R6 — Tuning no gerador.** Ajustes editam `scripts/gen_classes_v2.py` e,
  quando afetarem uma Carta, `scripts/gen_cards_v4.py`; regeneram os JSONs
  vigentes e removem o marcador `[BALANCEAR]` de cada knob decidido
  (a `note` vira o racional: "taunt 5%/pt, teto 60% — baseline X → Y").
  Knob sem dado suficiente PERMANECE marcado (não inventar).
- **R7 — Regressão.** Rodada mock pós-tuning com as MESMAS seeds comparada via
  `--baseline`; critérios R5 verdes; 918+ testes offline verdes (testes que
  fixam números de classes atualizados junto).

### Fora de escopo

- **Tiers 5+ (nível 9–20)** — spec própria depois desta (fast-follow declarado
  na spec das árvores).
- Rebalance de inimigos/economia/XP global (só os 8 knobs de classe + efeitos
  de habilidade que os dados condenarem).
- Novos perfis de playtest (os 12 existentes bastam; vitais: explorador,
  combate, diplomatico, secret_rusher).
- Mudança de mecânica (gatilho novo, regra nova) — se os dados pedirem, vira
  spec separada.

## 3. Design técnico

**Arquivos alterados**
- `playtest/runner.py` — opção `--class` no CLI (`__main__`/`run_campaign`);
  valida contra `gamedata.CLASSES`; propaga p/ criação do personagem da
  campanha.
- `playtest/telemetry.py` — campos novos por turno (R2), lidos de
  `state["player"]`; contadores de regra especial/consequência via eventos já
  logados por `combat_mechanics` (se não houver sinal estruturado, adicionar
  hook/log mínimo lá — sem mudar mecânica).
- `playtest/report.py` — seção Classes (R3) + diffs no `--baseline`.
- `scripts/gen_classes_v2.py` — knobs finais da configuração de classe (R6);
  regenerar `data/classes.json`.
- `scripts/gen_cards_v4.py` — marcadores fechados de auto-dano, pico,
  domínio de decadência e vazão da caldeira; regenerar `data/cards/*.json`.
- `tests/test_playtest_harness.py` (ou novo `tests/test_balance_classes.py`) —
  cobertura dos itens da Etapa 1.
- Specs/docs: `docs/CLASSES.md` (números finais), ESTADO_ATUAL/ROADMAP.

**Formato JSONL (linha de turno — campos novos):**
```json
{"turn": 12, "route": "combat_agent", "entropy": 4, "max_entropy": 16,
 "abyss_charge": 7, "abyss_tier": "leve", "special_rule_fired": "blood_leak"}
```

**CLI:**
```bash
uv run python -m playtest run --profile combate --class sangromante --turns 50 --seed 42
uv run python -m playtest run --all --turns 50 --class corruptor
uv run python -m playtest report <run_id> --baseline <run_id_anterior>
```

## 4. Plano passo a passo

### Etapa 1 — Instrumentação (testes primeiro)

1. **Testes:** `test_run_aceita_class` (campanha nasce com a classe pedida;
   id inválido = erro claro); `test_telemetry_registra_entropia`
   (linha JSONL tem os 4 campos; summary agrega starvation/flooding/Carga);
   `test_report_secao_classes` (markdown contém a matriz).
2. **Implementação:** runner + telemetry + report (R1–R3).
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Baseline (sem mexer em número)

1. Mock: 5 classes × 4 perfis vitais × 2 seeds × 50 turnos
   (`--class` em loop); guardar run_ids na spec (§8 registro de execução).
2. Real: 4 perfis vitais × 30 turnos, 4 classes ≠ Devoto cobertas ao longo
   das runs, com tetos de custo (~$0.05–0.10 no DeepSeek, padrão da suíte
   `llm_playtest`).
3. **Verificação:** relatório R3 renderiza; anotar violações dos critérios R5.

### Etapa 3 — Tuning + regressão

1. **Testes:** atualizar os que fixam números de classes
   (`test_classes_refactor`/`test_arvores_classes`) junto com o gerador.
2. **Implementação:** ajustar knobs no gerador, regenerar, repetir a rodada
   mock com as MESMAS seeds, comparar via `--baseline` até R5 verde.
3. **Verificação:** suíte completa verde + relatório comparativo anexado.

### Etapa 2.5 — Auditoria e correção da fiação v4 (testes primeiro)

1. **Testes de integração:** uma rodada real por classe prova que dano recebido,
   auto-dano, decadência, canalização e sofrimento de aliado geram Entropia/Carga.
2. **Regras e consequências:** provar no mesmo nível o vazamento de sangue,
   provocação, caldeira/vazão, Cicatriz e custo de Dependência.
3. **Implementação:** ligar os helpers sobreviventes ao orquestrador e à economia
   de Cartas; expor eventos estruturados mínimos para telemetria, sem parsing de log.
4. **Gate:** só iniciar tuning numérico depois que as cinco classes produzirem
   sinal mecânico observável no runtime v4.

## 5. Critérios de aceite

- [x] `--class` funciona p/ as 5 classes (teste offline)
- [x] Telemetria por turno tem Entropia/Carga; summary tem starvation/flooding/Carga
- [x] Baseline mock + real registrados ANTES do tuning (run_ids na spec)
- [x] Fiação v4 de gatilhos/regras/consequências coberta por `run_round`
- [x] Critérios R5 (a–e) verdes na rodada pós-tuning com mesmas seeds
- [x] Zero `[BALANCEAR]` órfão: cada knob foi decidido, marcador removido e racional gravado na `note`
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Guard de FallbackLLM em todo `with_structured_output` novo (nenhum novo — spec determinística)
- [x] Saves antigos continuam carregando (migração v3 intacta; tuning não muda schema)

## 6. Smoke test com LLM real

1. `uv run python -m playtest run --profile combate --class sangromante --real
   --turns 30 --max-cost 0.05` — completa sem erro; JSONL com Entropia/Carga.
2. Relatório do run mostra blood_leak disparando e Carga subindo.
3. 1 turno de API real com Médico de Campo: HUD/estado refletem os números
   pós-tuning (Entropia recompõe no descanso, Carga não).

## 7. Riscos & compatibilidade

- **Saves antigos:** knobs vivem em `data/classes.json` (lido em runtime) —
  personagem existente passa a usar os números novos ao carregar; aceitável e
  desejado (sem migração).
- **MockLLM:** combate mock é raso — critérios R5 medidos no mock valem como
  regressão relativa (antes/depois, mesmas seeds), não como verdade absoluta;
  o playtest real curto (R4) é o juiz de starvation/letalidade.
- **Quota/custo:** rodadas reais com tetos; DeepSeek ~$0.001/turno → baseline
  real ≈ $0.12 no pior caso. Groq free é fallback.
- **Risco de overfit ao harness:** perfis são determinísticos; mitigado por
  usar ≥2 seeds e 4 perfis distintos por classe.

## 8. Registro de execução (2026-07-19)

**Instrumentação (Etapas 1) — `done`:**
- `--class <nome|slug>` no harness (`resolve_class_name`, aceita acento/underscore/
  case). Telemetria por turno ganhou `entropy`/`max_entropy`/`abyss_charge`/
  `abyss_tier`; `summary.json` agrega `entropy.{starvation_pct_combat,
  flooding_pct_combat,peak_abyss_charge,final_abyss_charge,final_abyss_tier}` +
  `class_name`. `report` ganhou seção **Classes** (matriz classe × métricas).
  `persist_campaign(stem=...)` p/ runs por classe não colidirem.
- **+8 testes** `tests/test_balance_classes.py`. Suíte total 945 verdes.

**Baseline (Etapa 2) — capturado:**
- **Mock** `run_id 20260719-115640`: 5 classes × 4 perfis vitais × 2 seeds × 50t
  = **40 campanhas, 0 erros, 0 violações `error`**. Relatório em
  `playtest_runs/20260719-115640/report.md`.
- **Real (parcial)** `run_id 20260719-115906`: 4 campanhas × 30t no DeepSeek;
  degradado por rate-limit do Jina (colisão com um reindex simultâneo — erro
  operacional meu; o jogo seguiu resiliente).
- **Real pós-cutover v4 (2026-08-02):** a dependência
  `playtest-agente-curioso-entropia` foi fechada com dois sinais limpos:
  Sangromante `20260802-161653-555279` (30t, 30% ativa, gasto 2,
  flooding/starvation 35%/0%, Entropia 19→17) e Médico
  `20260802-161001-110214` (20t, 11,1% ativa, gasto 1, Entropia 19→18).
  A criação agora prioriza acervo autoral v4 e suporte escolhe alvo útil.

**Tuning (R5–R7) — ADIADO por dado insuficiente (decisão consciente, R6):**
1. **Mock não mede a economia de Entropia.** MockLLM em combate só dá ataque
   básico (custo 0) → **flooding 100% / starvation 0% em TODA classe** é
   artefato do mock, não sinal. (spec já previa: mock = regressão relativa, real
   = juiz — R7/§7.)
2. **Real ficou fino:** os perfis de combate morreram nível 1 (t7–t9 —
   letalidade early-game já conhecida, território de outra spec) antes de gerar
   economia de combate significativa; e o rate-limit do Jina degradou o
   archivist da rodada.
3. **Único sinal do mock** (a observar, não agir): só o **Devoto** acumula Carga
   de forma relevante (chegou a `severo`/13 no perfil combate) — mas confundido
   pelo mock nunca curar/descansar (leva dano todo turno). Não é limpo o
   bastante p/ mexer no gatilho.
- **Conclusão honesta:** os 8 knobs `[BALANCEAR]` PERMANECEM marcados. O tuning
  exige uma rodada real DEDICADA, mais longa e em nível sobrevivível (sem
  concorrência de Jina), que gere economia de combate real por classe. A
  ferramenta p/ medir isso agora existe (é a entrega desta sessão).

---

## 10. Parity ESTÁTICA das habilidades — `done` (2026-07-20)

Pedido do usuário: "garantir que todas as habilidades sejam mecanicamente
parecidas (nenhuma muito mais forte que a outra)". **Insight:** parity MECÂNICA é
número determinístico → mensurável direto do catálogo (`data/player_abilities.json`),
sem rodar playtest. Métrica: **dano-esperado-por-custo-real**, onde
`custo_real = Entropia + self_harm/2` (2 HP ≈ 1 Entropia) e `dano_efetivo =
dado + DoT(delta×duração) + ~4 por controle/debuff/buff`.

**Achados (role-aware — NÃO se achata papel):**
- O roster está, no geral, **bem balanceado por papel** (dano/custo das 4 classes
  ofensivas em ~2.5–3.5). O tank (Devoto) fica mais baixo POR DESIGN (troca dano
  por taunt + tem o maior HP); DoT do Corruptor tem dado baixo compensado pelo DoT.
- **Falso-alarme corrigido:** "Toque Cru" (Arcanista, `4d6` a custo 2) parecia
  quebrado (7.0/E dado cru), mas tem **`self_harm: 4`** — glass-cannon da
  subclasse "Descoberto"; contando o auto-dano vira 3.5/custo (normal do tier).
- **Médico e habilidades de suporte** pontuam baixo no dano só porque
  cura/buff/controle não entram na métrica de dano — é lacuna de MEDIÇÃO, não
  desbalanço. Buffar o dano deles seria errado (quebra o papel de suporte).
- **Único outlier de dano PURO real:** `fervor_ritual` (Devoto tier-3) fazia
  `2d6` (1.75/custo) contra `2d8` (2.25) dos irmãos diretos Retaliação/Intimidade,
  mesmo custo, todos puros → **estritamente pior**. **Fix aplicado:** `2d6→2d8`
  no gerador (racional inline). Regenerado; diff isolado a 1 fórmula.

**Guarda de regressão (`tests/test_arvores_classes.py`):**
- `test_parity_dano_puro_dentro_da_banda` — toda ativa de dano PURO (Entropia>0,
  sem self_harm, sem efeito) fica em **1.5–4.0 dano/Entropia**; pega mis-escala
  futura (ex.: `4d6` a custo 2 sem contrapartida = 7.0/E quebraria o teste).
- `test_parity_devoto_tier3_puro_alinhado` — trava o fix (os 3 tier-3 puros do
  Devoto com o MESMO dano/Entropia).

**Fora desta passada (parity EMERGENTE, não estática):** se cada classe consegue
de fato USAR o kit — economia de Entropia (starvation/flooding) e acúmulo de
Carga — é o tuning dos 8 knobs, que depende de rodada real DEDICADA. O run
`20260720-093014` (agente curioso) já deu o 1º sinal limpo de gasto por classe
(Devoto floda p/ `severo`; Corruptor gasta pouco), mas a baseline mudou com a
spec letalidade-v2 (HP/dano/recovery) → re-medir pós-A antes de mexer nos knobs.

## 11. Rebase v4 e baseline pós-fiação (2026-08-02)

**Fiação R4b — `done`:** o smoke real de 2026-08-02 mostrou que os helpers de
classe sobreviventes estavam sem callsite após o cutover conflito-13. Foram
ligados ao fluxo real de `run_round`: dano+quantidade (Devoto), auto-dano/
vazamento/Cicatriz (Sangromante), decadência (Corruptor), canalização/caldeira/
Dependência (Arcanista), sofrimento de aliado (Médico) e aggro de provocação.
As Cartas carregam somente `mecanica_classe` com vocabulário fechado; o lint
rejeita chaves/domínios livres. Nove regressões novas cobrem o runtime completo.

**Telemetria corrigida:** `class_mechanics` registra eventos estruturados por
turno e `summary.entropy.mechanic_activations` agrega contagens. O gasto passou
a ser o custo bruto retornado pela economia da Carta; delta antes/depois era
incorreto quando o gatilho repunha Entropia no mesmo turno.

**Baseline mock pareada:** runs `20260802-163728-596844` a
`20260802-163854-232187`: 5 classes × 4 perfis vitais × seeds 17/42 × 50 turnos
= 40 campanhas/2.000 turnos, zero erro e zero violação `error`. No perfil
combate, Carga máxima por classe/semente: Devoto 12/13, Sangromante 2/9,
Corruptor 5/9, Arcanista 7/5, Médico 0/0. O zero do Médico é esperado no perfil
solo: seu gatilho exige aliado ferido.

**Baseline real pós-fix:** `20260802-163942-749371`, Devoto/combate/seed 71,
30/30 turnos, zero erro/violação, 97 requests, US$ 0,031664; duas ativações
`on_damage_taken`, Carga 1 (`leve`), gasto 2, starvation 0%, flooding 72,7%.
Uma preparação de encontro esgotou os cinco providers por payload incompatível/
credenciais/quota e caiu corretamente na cena segura; a campanha permaneceu
completa. Relatório em `playtest_runs/20260802-163942-749371/report.md`.

**Decisão de ordem:** não ajustar os oito knobs ainda. A validação de R5 para o
Médico exige a spec `aliados-em-combate`/perfil recrutador; mortalidade também
está confundida pela spec `letalidade-early-game-v2`. Retomar esta Etapa 3 logo
após essas duas dependências, usando as mesmas seeds. Até lá os marcadores
`[BALANCEAR]` permanecem de propósito.

## 12. Tuning final e regressão — 2026-08-02

As dependências `aliados-em-combate` e `letalidade-early-game-v2` foram
concluídas. A grade final repetiu as mesmas seeds 17/42: 5 classes × 4 perfis
vitais × 50 turnos = **40 campanhas/2.000 turnos**, com **0 erros e 0 violações
`error`**. O Médico foi validado adicionalmente com o perfil `recrutador`.

**Correção da métrica.** `flooding` contava poção, fuga, manobra e passe como
“ataque básico”. Agora só `resolved_action.kind == attack` entra em
`basic_turns`; regressão fixa a definição. Pós-correção: starvation máximo 0%;
flooding máximo por classe Devoto 31,9%, Sangromante 23,8%, Corruptor 41,9%,
Arcanista 32,4%, Médico 14,8% — todos abaixo de 50%.

**Knobs finais.** Os valores de geração/consumo foram retidos porque não houve
starvation ou overdrain. Os únicos ajustes numéricos necessários foram caps de
Carga passiva em **6** para `on_damage_taken` (Devoto: pico 16→6) e
`on_ally_suffer` (Médico recrutador: pico 15→6). Assim ambos chegam a `leve`/
`moderado`, mas não a `severo` apenas por rotina defensiva. Corruptor e
Arcanista só escalam Carga ao usar suas mecânicas; Sangromante chegou a leve/
moderado. A caldeira estourou 3 vezes em 2.000 turnos, presente sem ser causa
dominante. Mortalidade máxima (Devoto 30) ficou abaixo de 2× a média das demais
classes (40,5). Todos os oito marcadores `[BALANCEAR]` foram removidos e cada
`note` passou a registrar o racional.

**Smoke real:** `20260802-175310-716794`, Sangromante/combate, 30/30 turnos,
primeira queda t29, 0 erros/violações, `mock=false`, Entropia gasta 4, habilidade
ativa em 42,1%, Carga pico 4, 78 tentativas/77 sucessos e US$ 0,02198. Relatório
em `playtest_runs/20260802-175310-716794/report.md`.

**Gates:** lint de conteúdo 0 erros/avisos; `uv run pytest` = **1.338 passed,
1 skipped, 14 deselected**. O restore de checkpoint legado sem Virtudes também
foi endurecido: HP é preservado em vez de inferir Corpo 0.
