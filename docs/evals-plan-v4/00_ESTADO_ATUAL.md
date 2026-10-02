# 00 — Estado atual do projeto

## O que já existe e deve ser reutilizado

O projeto está muito mais perto de uma infraestrutura de evals do que aparenta. Não faz sentido criar um framework paralelo.

### Backend / IA

O projeto já possui:

- `playtest/runner.py`: campanhas multi-turno sobre o grafo real.
- `playtest/profiles.py`: perfis distintos de jogador.
- `playtest/invariants.py`: dezenas de invariantes determinísticos por turno.
- `playtest/telemetry.py`: latência, provider, custo, falhas, rotas, memória, combate, economia etc.
- `playtest/report.py`: relatórios e comparação contra baseline.
- `playtest/scenarios.py`: cenários dirigidos com pré-condição e oráculo.
- `playtest/matrix.py`: matriz canônica de perfis/classes/níveis/seeds.
- `scripts/benchmark_turn_pipeline.py`: benchmark determinístico de concorrência.
- `scripts/benchmark_turn_pipeline_real.py`: gate pareado em provider real.
- `services/context_builder.py`: construção estruturada do contexto.
- `services/narrative_evidence.py`: evidência canônica e filtro determinístico de afirmações incompatíveis.
- `services/memory_provenance.py`: validação de origem, identidade, morte falsa, posse, localização e segredos.
- `rag.py`: busca global, sessão e NPC; operações RAG já emitem telemetria.
- `agents/router.py`, `agents/archivist.py`, `agents/npc.py`: pontos claros de instrumentação por componente.

### Baseline histórico

`docs/playtest-matriz-a-2026-08-27.md` registrou 10×200 turnos reais com DeepSeek, mas essa baseline **não deve ser usada como baseline do build atual**. O projeto mudou substancialmente depois dela.

O build atual deve ganhar uma baseline nova, criada somente depois da instrumentação de evals estar estabilizada.

### Frontend

O frontend atual é React/Vite/TypeScript em `web/`. Já existem:

- `web/tests/http.test.mjs`: CSRF, cookies, refresh single-flight, erro 401.
- `web/tests/pending.test.mjs`: operação pendente, reload, idempotência local.
- `tests/test_audit_browser_local.py`: browser autenticado, criação de jogo, arte, SSE, histórico, replay, divergência 409, reload.
- `tests/test_frontend_visual_contracts.py`: 390/1440 px, imagens, overflow.
- `tests/test_frontend_accessibility_contracts.py`: contratos estáticos básicos.
- `tests/test_browser_local.py`: smoke desktop/mobile opt-in.
- `scripts/audit_local_gate.py`: gate integrado local com Postgres/Auth/Storage/browser.

A principal lacuna é que esses testes não formam ainda uma **matriz explícita de jornadas do usuário**, com cobertura, IDs estáveis, artefatos, visual snapshots controlados, console/network errors e gate de navegação por fluxo.

## Snapshot recomendado para o plano

Tratar `b3dcc19` como `EVAL_BASE_COMMIT` inicial.

Antes da primeira alteração de eval:

```bash
git checkout main
git pull
git rev-parse HEAD
# deve corresponder ao SHA que se deseja medir
```

Gerar um manifesto:

```json
{
  "release_sha": "b3dcc19da1768fd11f391a13b301124c825ad6e7",
  "eval_schema_version": 1,
  "baseline_status": "pending"
}
```

O fato de um deploy ter ocorrido não torna a baseline válida por si só. A baseline passa a ser válida quando o build, dataset, evaluator, seeds, provider route e ambiente de browser forem registrados juntos.
