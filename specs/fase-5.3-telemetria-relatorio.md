# SPEC — Fase 5.3 — Telemetria de playtest + relatório agregado

> **Status:** `done` (2026-07-06)
> **Criada:** 2026-07-06 · **Atualizada:** 2026-07-06
> **Depende de:** 5.1 (harness) `done`; 5.2 (invariantes) `done`;
> **roteamento-multi-provider `done`** (telemetria grava provider/modelo/custo
> por turno e conta fallbacks)
> **Desbloqueia:** decisões de balanceamento baseadas em dado (playtest da Fase 4 pendente); critério de aceite da Fase 5

---

## 1. Contexto & Objetivo

O harness 5.1 joga campanhas e a 5.2 acusa violações — mas o resultado morre
no terminal. Para o playtest render decisão (balanceamento da Fase 4,
frequência de replan do campaign_manager, letalidade por região), as campanhas
precisam deixar **rastro estruturado e comparável**: um JSONL por campanha e um
relatório agregado que responda "o que quebrou, onde o jogador morre, quanto
custou, o que mudou desde a última rodada".

Esta spec fecha a Fase 5: telemetria por turno gravada em disco (reusa o shape
do log JSON da Fase 10), agregação em métricas por campanha/perfil e um
relatório Markdown estático (zero dependência nova; dashboard web fica de fora
até haver demanda). 100% offline — analisa o que o runner já produziu.

Princípio: **estado auditável** — playtest sem número vira anedota.

## 2. Requisitos

- **R1 — Telemetria por turno (JSONL):** runner grava
  `playtest_runs/{run_id}/{profile}_{seed}.jsonl` — 1 linha por turno com o
  shape do logger `rpg.turn` da Fase 10 (`turn`, `route`, `latency_ms`,
  `events_applied`, `events_rejected`, `error`) + campos de playtest
  (`action`, `location_id`, `player_hp`, `player_level`, `gold`,
  `violations: [check_ids]`) + campos de roteamento (do hook
  `set_llm_telemetry_hook`): `provider`, `model`, `tier`, `fell_back` (bool),
  `cost_usd` (estimado por tabela de preço por modelo × tokens in/out).
- **R2 — Resumo por campanha (JSON):** ao fim, `summary.json` por campanha:
  turnos completados, erros, violações por check_id, distribuição de rotas,
  latência p50/p95, HP médio, mortes, nível final, ouro final, locais
  visitados, quests criadas/concluídas, requests de LLM por provider,
  **custo total estimado (USD)**, custo por tier, e contagem de `fell_back`
  (quantos turnos caíram no candidato de fallback — sinal de provider instável).
- **R3 — Métricas agregadas:** `playtest/report.py` —
  `aggregate(run_dir) -> RunReport` cruza todas as campanhas do run:
  totais por perfil, top violações, top erros por rota, campanha mais curta
  (onde morreu/travou), comparação opcional com run anterior
  (`--baseline <run_id>`: deltas de erros/violações/latência).
- **R4 — Relatório Markdown:** `python -m playtest report <run_id>
  [--baseline <id>]` gera `playtest_runs/{run_id}/report.md` — tabela por
  perfil, seção de violações com exemplo (turno + ação que disparou), seção
  de deltas vs baseline. Legível no GitHub/editor; sem HTML/JS.
- **R5 — Integração no CLI 5.1:** `python -m playtest run --all` já grava
  telemetria (R1/R2) e imprime o caminho do run; `report` é comando separado
  (rodar N vezes sobre o mesmo run).
- **R6 — Orçamento LLM real:** com `--real`, o resumo registra requests por
  provider E custo estimado (USD, via hook do roteamento). Aborta a campanha
  educadamente ao atingir teto de requests (`--max-requests`, default 15) OU de
  custo (`--max-cost`, USD, default 0 = desligado) — nunca estoura orçamento por
  acidente. (Produto paga por chave própria de cada provider; o teto protege o
  bolso, não uma quota grátis.)
- **R7 — Suíte:** teste offline roda 1 campanha curta + `aggregate` + geração
  do relatório e asserta: JSONL parseável linha a linha, summary com campos
  obrigatórios, report.md contém as seções canônicas.

### Fora de escopo

- Dashboard web/HTML interativo (Markdown basta; reavaliar com uso).
- Série histórica automática entre sessões (baseline manual via `--baseline`).
- Telemetria do jogo REAL de jogador humano (é playtest, não analytics de prod).
- Métrica de qualidade narrativa (LLM-as-judge) — números mecânicos apenas.

## 3. Design técnico

### Arquivos novos

- `playtest/telemetry.py` — writer JSONL + builder do summary (funções puras
  sobre `CampaignResult` + registros de turno).
- `playtest/report.py` — `aggregate`, `render_markdown`, comparação baseline.
- `tests/test_fase53.py`

### Arquivos alterados

- `playtest/runner.py` — emite registro de turno p/ o writer (hook interno já
  existe — `history` do 5.1 ganha os campos novos).
- `playtest/__main__.py` — subcomando `report`, flags `--baseline`,
  `--max-requests`.

### Formatos

`{profile}_{seed}.jsonl` (1 linha/turno):

```json
{"turn": 12, "action": "Viajo para Brekmar", "route": "storyteller",
 "latency_ms": 40, "events_applied": 1, "events_rejected": 0, "error": null,
 "location_id": "brekmar", "player_hp": 22, "player_level": 2, "gold": 35,
 "violations": [],
 "provider": "minimax", "model": "MiniMax-M2.5", "tier": "fast",
 "fell_back": false, "cost_usd": 0.0021}
```

`summary.json`:

```json
{"profile": "explorador", "seed": 42, "turns_completed": 50, "errors": 0,
 "violations": {"economy.gold_negative": 0}, "routes": {"storyteller": 41,
 "combat_agent": 6, "npc_actor": 2, "loot": 1}, "latency_ms": {"p50": 38,
 "p95": 95}, "deaths": 0, "final_level": 3, "final_gold": 120,
 "locations_visited": 14, "quests": {"created": 2, "completed": 1},
 "llm_requests_by_provider": {"groq": 50, "minimax": 41, "glm": 8},
 "cost_usd_total": 0.14, "cost_usd_by_tier": {"classify": 0.01, "fast": 0.09,
 "smart": 0.04}, "fell_back_turns": 2, "mock": true}
```

### Assinaturas

```python
# playtest/telemetry.py
def write_turn(fp, record: dict) -> None: ...
def build_summary(result: CampaignResult, turn_records: list[dict]) -> dict: ...

# playtest/report.py
@dataclass
class RunReport:
    run_id: str
    campaigns: list[dict]          # summaries
    top_violations: list[tuple[str, int]]
    top_errors: list[tuple[str, int]]
    deltas: Optional[dict]         # vs baseline (None sem baseline)

def aggregate(run_dir: str, baseline_dir: str | None = None) -> RunReport: ...
def render_markdown(report: RunReport) -> str: ...
```

`run_id` = timestamp `YYYYMMDD-HHMMSS` (ordena sozinho). `playtest_runs/` entra
no `.gitignore` (relatório interessante é commitado à mão quando embasar decisão).

## 4. Plano passo a passo

### Etapa 1 — Telemetria por turno + summary

1. **Testes** (`tests/test_fase53.py`): `test_jsonl_uma_linha_por_turno`
   (campanha 5 turnos → 5 linhas parseáveis); `test_summary_campos_obrigatorios`;
   `test_violacao_aparece_no_turno_e_no_summary` (violação plantada).
2. **Implementação:** `telemetry.py` + integração no runner.
3. **Verificação:** `/qa` verde.

### Etapa 2 — Agregação + relatório

1. **Testes:** `test_aggregate_cruza_campanhas` (2 summaries sintéticos);
   `test_render_markdown_secoes_canonicas` ("## Por perfil", "## Violações",
   "## Erros"); `test_baseline_gera_deltas`.
2. **Implementação:** `report.py` + subcomando CLI.
3. **Verificação:** `/qa` verde.

### Etapa 3 — Teto de orçamento no --real + fechamento

1. **Testes:** `test_max_requests_aborta_educadamente` (contador fake atinge
   teto no turno 2 → campanha para, summary marca `aborted_reason`);
   `test_max_cost_aborta_educadamente` (custo acumulado passa `--max-cost` →
   para); `test_custo_por_modelo_da_tabela` (tabela de preço × tokens → USD).
2. **Implementação:** contador de requests + custo (consome o hook do
   roteamento; tabela de preço por modelo em `playtest/pricing.py`) + flags
   `--max-requests`/`--max-cost`; `.gitignore`.
3. **Verificação:** `uv run pytest` completo; rodar
   `python -m playtest run --all --turns 30` + `report` e LER o relatório —
   achados viram issues/pendências no ROADMAP (entrega da Fase 5 é o CICLO,
   não só o código).

## 5. Critérios de aceite

- [x] `run --all --turns 50` gera JSONL + summary por campanha e imprime run_id
- [x] JSONL/summary trazem provider/modelo/tier/custo/`fell_back` por turno
      (smoke real: `providers deepseek=5/groq=9`, `fell_back_turns=4`, custo por tier)
- [x] `report <run_id>` gera report.md legível com per-perfil/violações/erros +
      custo por tier/provider e turnos com fallback
- [x] `--baseline` mostra deltas entre dois runs (inclui delta de custo) — `test_baseline_gera_deltas`
- [x] `--max-requests` e `--max-cost` param no teto — `test_max_requests/max_cost_aborta_educadamente`
- [x] 1ª rodada completa executada e lida; achados registrados no ROADMAP
- [x] `uv run pytest` verde (699 testes, 0 falhas)
- [x] Guard de FallbackLLM — N/A (zero LLM novo)
- [x] Saves antigos continuam carregando (nada de runtime de jogo muda)

> **Nota de custo:** o hook de telemetria do roteamento entrega
> `(provider, model, tier, latency_ms, fell_back)` — SEM tokens. `cost_usd` é
> ESTIMADO (`playtest/pricing.py`: tokens fixos por invoke × preço por modelo),
> suficiente p/ comparar campanhas e proteger o bolso no `--real`; não é fatura.

## 6. Smoke test com LLM real

1 campanha `--real --turns 4 --max-requests 12` → summary com `llm_requests`
> 0, report gerado; conferir latências p50/p95 plausíveis (SLA real do Gemini).

## 7. Riscos & compatibilidade

- **Métrica enganosa com MockLLM** (latência/rotas não representam produção):
  relatório marca `mock: true` por campanha — comparação mock×real proibida
  no próprio report (aviso no cabeçalho).
- **playtest_runs/ cresce:** gitignored; limpeza manual (barato, JSONL).
- **Baseline com schema antigo:** `aggregate` tolera campo ausente (get com
  default) — summary é dado, não contrato rígido.
- **Saves antigos / MockLLM / quota:** sem impacto; teto R6 protege a quota.
