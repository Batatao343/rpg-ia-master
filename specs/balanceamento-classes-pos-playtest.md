# SPEC — Balanceamento das 5 Posturas pós-playtest (knobs `[BALANCEAR]`)

> **Status:** `in-progress` (instrumentação R1–R3 + baseline R4 `done` 2026-07-19; tuning R5–R7 adiado — dado insuficiente, ver §8)
> **Criada:** 2026-07-19 · **Atualizada:** 2026-07-19
> **Depende de:** [refatoracao-sistema-classes](refatoracao-sistema-classes.md) `done` ·
> [arvores-habilidade-classes](arvores-habilidade-classes.md) `done` ·
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
mock + playtest real curto, e ajustar os 8 knobs **no gerador**
(`scripts/gen_classes_v2.py` — `data/classes.json` e `data/player_abilities.json`
são GERADOS; nunca editar o JSON direto) contra critérios objetivos.

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
- **R6 — Tuning no gerador.** Ajustes editam `scripts/gen_classes_v2.py`,
  regeneram os JSONs e removem o marcador `[BALANCEAR]` de cada knob decidido
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
- `scripts/gen_classes_v2.py` — knobs finais (R6); regenerar
  `data/classes.json` + `data/player_abilities.json`.
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

## 5. Critérios de aceite

- [ ] `--class` funciona p/ as 5 classes (teste offline)
- [ ] Telemetria por turno tem Entropia/Carga; summary tem starvation/flooding/Carga
- [ ] Baseline mock + real registrados ANTES do tuning (run_ids na spec)
- [ ] Critérios R5 (a–e) verdes na rodada pós-tuning com mesmas seeds
- [ ] Zero `[BALANCEAR]` órfão: cada knob ou decidido (marcador removido, racional na note) ou justificado como "sem dado"
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM em todo `with_structured_output` novo (não deve haver nenhum — spec é determinística)
- [ ] Saves antigos continuam carregando (migração v3 intacta; tuning não muda schema)

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
