# SPEC — Fase 10b.7 — Observabilidade, backup e matriz local de produção

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** specs Fase 10b.1–10b.6 `done`
> **Desbloqueia:** declaração de prontidão local e certificação cloud

---

## 1. Contexto & Objetivo

O projeto já tem excelente observabilidade de gameplay: logs `rpg.turn`, hooks
LLM/RAG, métricas de nós, invariantes e playtests JSONL. Faltam correlação entre
request/worker/DB, dashboards, alertas, retenção, backup restaurado e evidência de
comportamento sob concorrência/falhas reais.

Esta spec transforma a stack local em ensaio de produção zero-custo. Ferramentas
de observabilidade rodam em profile Docker opcional; testes de carga, browser,
backup e caos são orquestrados em Python. A suíte padrão continua leve/offline.

## 2. Requisitos

- **R1 — correlação ponta a ponta:** `request_id`, `operation_id`, `game_id`
  pseudonimizado, owner pseudonimizado e trace context ligam FastAPI, turno,
  LangGraph node, LLM attempt, RAG, DB, job e blob.
- **R2 — telemetria segura:** prompts, ações, narrativa, JWT, e-mail, signed URL,
  cookies e payload de save nunca entram em logs/traces/labels.
- **R3 — OTel opcional:** traces/metrics via OpenTelemetry com exporter configurável;
  ausência do collector degrada para log sem derrubar turno.
- **R4 — stack observável local:** profile opcional oferece collector, métricas e
  visualização de traces/dashboards; `doctor` mede RAM/ports antes de iniciar.
- **R5 — SLOs realistas:** medir separadamente endpoints determinísticos, first
  SSE event, turno total, DB commit, query RAG, backlog job e erro/idempotência.
- **R6 — alertas testáveis:** regras têm fixtures que disparam e resolvem para
  error rate, p95, lease expirado, backlog/idade, RAG failed, DB pool e backup velho.
- **R7 — backup completo:** Postgres + objetos + manifest/config/corpus versionado;
  segredo não entra no artefato. Backup DB isolado não conta como backup de Storage.
- **R8 — restore provado:** restaurar numa stack limpa, rodar hashes/constraints,
  abrir campanhas, consultar memória, baixar asset e jogar turno novo.
- **R9 — RPO/RTO:** alvo local RPO = zero turnos confirmados perdidos; RTO ≤30 min
  para dataset de aceite. Medição, não declaração manual.
- **R10 — carga multiusuário:** dois workers no mínimo, jogos distintos paralelos,
  colisões intencionais no mesmo jogo e SSE; nenhuma perda/duplo commit.
- **R11 — caos:** kill de API/worker, restart DB, timeout de embedding/blob,
  lease expirado e falha entre blob/DB convergem sem corrupção.
- **R12 — soak gameplay:** ≥1.000 turnos MockLLM distribuídos entre perfis/jogos,
  invariantes atuais, restart periódico e zero write persistente no disco da API.
- **R13 — browser/E2E Python:** signup→new→SSE→restart→continue→death/checkpoint→
  logout em desktop e 390px, console/requests/accessibility básicos.
- **R14 — segurança/supply chain:** lint, content validation, dependency audit,
  secret scan, headers/CORS/CSRF/RLS e imagem/container sem secret; findings
  P0/P1 bloqueiam readiness.
- **R15 — relatório único:** comando Python produz JSON+Markdown com versão/git,
  ambiente, gates, SLOs, falhas injetadas, backup/restore e pendências.

### Fora de escopo

- Pager/SMS/e-mail real, Sentry/PostHog SaaS ou log drain pago.
- Prometer SLO de internet/provider com laboratório local.
- Teste real de LLM por 1.000 turnos.
- Multi-região, disaster recovery entre clouds e compliance formal.

## 3. Design técnico

### Arquivos novos

- `observability/telemetry.py` — setup OTel, redaction e correlation context.
- `observability/metrics.py` — nomes/buckets/cardinalidade fechados.
- `observability/dashboards/` e `observability/alerts/` — artefatos versionados.
- `infra/observability.compose.yml` — profile opcional, volumes locais dedicados.
- `scripts/backup_local.py`, `scripts/restore_local.py`, `scripts/verify_restore.py`.
- `scripts/load_test.py`, `scripts/chaos_test.py`, `scripts/readiness_report.py`.
- `tests/test_telemetry_redaction.py`, `tests/test_backup_restore_local.py`,
  `tests/test_multiworker_local.py`, `tests/test_chaos_local.py`,
  `tests/test_browser_local.py`.
- `docs/OPERACAO_LOCAL.md` — runbooks derivados da implementação.

### Arquivos alterados

- `api.py`, `services/turn_service.py`, adapters/workers — spans e métricas.
- `llm_setup.py`, `rag.py` — hooks existentes alimentam OTel sem payload.
- `playtest/telemetry.py` — IDs de correlação, sem acoplar ao exporter.
- `scripts/dev_stack.py`, `pyproject.toml`, CI — profiles/markers/gates.

### Métricas mínimas

```text
rpg_http_requests_total{route,status_class}
rpg_http_duration_seconds{route}
rpg_sse_first_event_seconds{route}
rpg_turn_duration_seconds{route,outcome,simulated}
rpg_turn_commits_total{outcome}
rpg_operation_lease_age_seconds{kind}
rpg_db_duration_seconds{operation,outcome}
rpg_db_pool{state}
rpg_llm_attempts_total{provider,tier,outcome}
rpg_llm_duration_seconds{provider,tier,outcome}
rpg_llm_cost_usd_total{provider,tier}
rpg_rag_duration_seconds{scope,outcome}
rpg_memory_embedding_backlog{status}
rpg_jobs{kind,status}
rpg_blob_operations_total{operation,outcome}
rpg_backup_age_seconds{component}
```

Owner/game nunca são labels de métrica. Logs/traces podem usar HMAC rotacionável
para correlação temporária, não UUID cru.

### SLOs locais iniciais

| Sinal | Alvo de aceite local |
|---|---|
| Health/read determinístico p95 | <300 ms |
| Primeira fase SSE p95 | <1 s |
| Commit DB p95 | <250 ms |
| Query pgvector p95 no corpus de aceite | <500 ms |
| Turno MockLLM p95 | <2 s |
| Turno LLM real | medir; warning >45 s, error >90 s preservados |
| Erro mecânico/commit em soak | 0 |
| Commit duplicado por request ID | 0 |
| Job mais antigo saudável | <60 s no laboratório |

Limiares só mudam com baseline registrado na spec/ROADMAP.

### Backup

`backup_local.py` cria diretório novo com manifest SHA-256, dump Postgres em
formato custom, export de objetos, versão de migrations, catálogo visual estático
referenciado (não duplicado) e relatório. `restore_local.py` só aceita destino
local vazio/explicitamente confirmado; não remove source. O teste restaura em
volume/database temporários e compara invariantes sem depender de paths originais.

### Matriz de gates

```text
G0 uv run pytest                         # sempre, sem Docker
G1 uv run pytest -m infra_local          # DB/Auth/Storage/pgvector
G2 uv run pytest -m security_local       # RLS/CSRF/ownership/secrets
G3 uv run pytest -m chaos_local          # kill/restart/timeouts
G4 uv run python scripts/load_test.py     # concorrência/SSE/leases
G5 uv run python -m playtest ... 1000t    # soak MockLLM
G6 uv run python scripts/backup_local.py + restore/verify
G7 browser Python + build/lint/content/audits
```

## 4. Plano passo a passo

### Etapa 1 — Instrumentação/redaction

1. **Testes** (`test_telemetry_redaction.py`): payloads contendo token/e-mail/
   ação/narrativa/signed URL nunca saem; cardinalidade de labels fechada.
2. **Implementação:** OTel opcional e spans nos boundaries.
3. **Verificação:** collector ausente não altera resposta/latência materialmente.

### Etapa 2 — Stack/dashboards/alertas

1. **Testes:** config válida; fixtures disparam/resolvem todas as regras.
2. **Implementação:** compose profile e artefatos versionados.
3. **Verificação:** `doctor` + dashboard de uma campanha sem payload sensível.

### Etapa 3 — Backup/restore

1. **Testes** (`test_backup_restore_local.py`): DB+blob, corrupção de hash,
   backup interrompido, destino não vazio, RPO/RTO medidos.
2. **Implementação:** scripts preview-first e manifest.
3. **Verificação:** restore limpo jogável com memória/asset/checkpoint.

### Etapa 4 — Multiworker/carga/caos

1. **Testes:** matriz R10/R11 com failpoints e processos reais.
2. **Implementação:** orquestradores Python; nenhuma mecânica especial de teste exposta.
3. **Verificação:** zero partial/duplicate, leases/jobs convergem.

### Etapa 5 — Soak/browser/relatório

1. **Testes:** 1.000 turnos, restart, A/B browser, mobile, accessibility/console.
2. **Implementação:** readiness report agrega artefatos dos gates.
3. **Verificação:** relatório reproduzível com commit e ambiente.

## 5. Critérios de aceite

- [x] Telemetria cobre request→turn→LLM/RAG→DB/job/blob com redaction validada.
- [x] Dashboards/alertas locais funcionam e ausência do stack não derruba jogo.
- [x] Backup completo restaura em stack limpa com RPO 0 e RTO ≤30 min no dataset.
- [x] Dois workers/carga não perdem nem duplicam commit.
- [x] Todos cenários de caos convergem ou falham fechados com runbook.
- [x] Soak ≥1.000 turnos: zero erro/invariante `error`/write persistente no disco da API.
- [x] Browser A/B desktop+390px conclui fluxo completo e isolamento.
- [x] Dependency/secret/security gates sem P0/P1.
- [x] G0–G7 verdes e relatório JSON+Markdown preservado.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM permanece; smoke real pequeno não substitui MockLLM soak.
- [x] Backups/saves antigos permanecem recuperáveis.

## 6. Smoke test com LLM real

Campanha curta de 5 turnos no perfil local registra trace/custo sem prompt,
inclui fallback se ocorrer e mantém SLO histórico. Reiniciar API depois do turno
3 e continuar. O smoke é opt-in, com teto de requests/custo; nenhum SaaS de
observabilidade é necessário.

## 7. Riscos & compatibilidade

- **Stack pesada:** observabilidade é profile separado e doctor bloqueia baixa RAM.
- **Cardinalidade/vazamento:** labels fechadas + testes de redaction; nenhum ID bruto.
- **Teste “verde” irreal:** separar MockLLM, Ollama local e provider real no relatório.
- **Backup falso:** só conta se restore limpo for executado e verificado.
