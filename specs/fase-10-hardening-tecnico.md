# SPEC — Fase 10 — Hardening técnico (single-player local)

> **Status:** `draft`
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** nada bloqueante (motor estável; Fases 2.5–7 `done`)
> **Desbloqueia:** Fase 10b (multiusuário: Postgres/pgvector/auth), releases externos

---

## 1. Contexto & Objetivo

A API confia no cliente em pontos que viram vulnerabilidade ou corrupção de
dado no momento em que o app sai do localhost: `api.py` monta caminho de save
com `f"saves/{game_id}.json"` **sem validar** o `game_id` (path traversal:
`game_id="../.env"` lê fora de `saves/`); CORS está `allow_origins=["*"]`;
saves não têm `schema_version` (todo backfill de load é heurístico — cada fase
nova adiciona mais um "if campo ausente"); não há rate limiting nem logs
estruturados.

Esta spec cobre o **hardening que vale AGORA, single-player local**: validação
de `game_id`, versionamento de saves com pipeline de migrations explícito,
CORS configurável e log estruturado por turno. A parte multiusuário (Postgres,
pgvector, autenticação, fila de assets) fica para a **Fase 10b** quando houver
usuários externos — infra sem demanda é peso morto.

Princípio: **mecânica é Python, validação na borda** — input do cliente nunca
chega cru ao filesystem.

## 2. Requisitos

- **R1 — game_id validado:** todo endpoint que recebe `game_id` valida formato
  UUID (`uuid.UUID(game_id)`); inválido → HTTP 400 sem tocar no filesystem.
  Vale para `/game/state`, `/game/action`, `/game/codex`, `/game/levelup`,
  `/game/equip` e qualquer outro que monte caminho de save.
- **R2 — caminho de save centralizado:** função única `save_path(game_id)` em
  `persistence.py` (valida UUID + `os.path.join("saves", ...)` + assert de que
  o caminho resolvido está DENTRO de `saves/`); `api.py` e `game_engine.py`
  param de montar f-string de caminho.
- **R3 — schema_version no save:** `save_game_state` grava
  `schema_version: 1`; `load_game_state` roda pipeline de migrations
  `_MIGRATIONS: dict[int, Callable[[dict], dict]]` (0→1 consolida os backfills
  heurísticos existentes: `known_abilities` id-canônico, inventário `{id,qty}`,
  `chronicle`, `equipment`, `game_over`...). Save sem o campo = versão 0.
- **R4 — migration idempotente:** rodar a migration 2× no mesmo save produz o
  mesmo resultado; save já na versão atual não passa por migration nenhuma.
- **R5 — CORS configurável:** `RPG_CORS_ORIGINS` no `.env` (CSV; default
  `http://localhost:8000,http://localhost:5173`); `*` só se explicitamente
  configurado. `.env.example` documenta.
- **R6 — Rate limiting mínimo:** `/game/action` e `/game/new` limitados por
  IP em memória (janela deslizante, ex.: 30 req/min) — sem dependência nova
  (dict + timestamps); acima do limite → HTTP 429. Desligável por env
  (`RPG_RATE_LIMIT=0`) para a suíte/smoke.
- **R7 — Log estruturado por turno:** 1 linha JSON por request de `/game/action`
  (game_id, turno, rota do grafo, latência ms, eventos aplicados/rejeitados,
  erro se houver) via `logging` stdlib para stderr — base da observabilidade
  da Fase 10b, sem lib nova.

### Fora de escopo (→ Fase 10b, multiusuário)

- Postgres / migração do FAISS para pgvector/Qdrant.
- Autenticação e isolamento por usuário.
- Storage/fila para imagens geradas (Fase 8).
- Controle de concorrência entre sessões (API continua stateless por save).

## 3. Design técnico

### Arquivos alterados

- `persistence.py` — `save_path(game_id)`, `SCHEMA_VERSION`, `_MIGRATIONS`,
  migration 0→1 (mover backfills que hoje vivem espalhados no load);
  `save_game_state` grava a versão; `load_game_state` aplica pipeline.
- `api.py` — usa `save_path` (remove f-strings de caminho); dependency
  `validated_game_id` (FastAPI `Depends`) nos endpoints; CORS de env;
  middleware de rate limit; logger de turno em `/game/action`.
- `game_engine.py` — usa `save_path` no load/save do CLI.
- `.env.example` — `RPG_CORS_ORIGINS`, `RPG_RATE_LIMIT`.

### Assinaturas

```python
# persistence.py
SCHEMA_VERSION = 1

def save_path(game_id: str) -> str:
    """Caminho canônico do save. Levanta ValueError se game_id não for UUID
    ou o caminho resolvido escapar de saves/."""

def migrate_state(state: dict) -> dict:
    """Aplica _MIGRATIONS de state['schema_version'] (default 0) até
    SCHEMA_VERSION. Puro e idempotente."""

# api.py
def validated_game_id(game_id: Optional[str] = None) -> Optional[str]:
    """Depends: None passa (carrega save mais recente); não-UUID -> HTTPException 400."""
```

### Log de turno (formato)

```json
{"evt": "turn", "game_id": "6f1c...", "turn": 12, "route": "COMBAT",
 "latency_ms": 2140, "events_applied": 1, "events_rejected": 0, "error": null}
```

## 4. Plano passo a passo

### Etapa 1 — save_path + validação de game_id

1. **Testes** (`tests/test_fase10.py`): `test_save_path_uuid_valido`;
   `test_save_path_rejeita_traversal` (`"../.env"`, `"..\\x"`, `"a/b"` →
   ValueError); `test_endpoint_400_com_game_id_invalido` (TestClient em
   `/game/state?game_id=../x`); `test_game_id_none_carrega_mais_recente`.
2. **Implementação:** `save_path` + `Depends` + troca das f-strings.
3. **Verificação:** `/qa` verde.

### Etapa 2 — schema_version + migrations

1. **Testes:** `test_save_novo_tem_schema_version`;
   `test_save_v0_migra_para_v1` (fixture de save antigo sem os campos novos →
   load devolve estado completo); `test_migration_idempotente`;
   `test_save_versao_atual_nao_migra` (monkeypatch numa migration que
   levantaria se chamada).
2. **Implementação:** pipeline + mover backfills existentes do load para a
   migration 0→1 (comportamento idêntico, lugar único).
3. **Verificação:** `/qa` verde + carregar na mão 1 save real antigo de `saves/`.

### Etapa 3 — CORS + rate limit + log

1. **Testes:** `test_cors_default_nao_e_wildcard`;
   `test_rate_limit_429_apos_janela` (limite baixo via env no teste);
   `test_rate_limit_desligado_na_suite` (conftest seta `RPG_RATE_LIMIT=0`);
   `test_log_de_turno_e_json_valido` (capsys/caplog).
2. **Implementação:** env parsing + middleware + logger.
3. **Verificação:** `uv run pytest` completo + `bash scripts/smoke_api.sh`.

## 5. Critérios de aceite

- [ ] `game_id` malicioso (`../.env`) → 400; nenhum arquivo fora de `saves/` é lido/escrito
- [ ] Save antigo (v0) carrega migrado; save novo tem `schema_version: 1`
- [ ] CORS default restrito a localhost; configurável por env
- [ ] Rate limit devolve 429 e é desligável por env (suíte passa)
- [ ] 1 linha JSON de log por turno no stderr
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM — N/A (zero LLM nesta spec)
- [ ] Saves antigos continuam carregando (é O PONTO da spec)

## 6. Smoke test com LLM real

Zero LLM. Smoke manual da API (MockLLM basta):

1. `uv run uvicorn api:app --port 8000` → `curl "localhost:8000/game/state?game_id=../.env"` → 400.
2. Jogar 1 turno → conferir linha JSON de turno no stderr e `schema_version` no save.
3. Loop de 40 `curl` em `/game/action` → 429 aparece; `RPG_RATE_LIMIT=0` → não aparece.

## 7. Riscos & compatibilidade

- **Backfills movidos para migration:** maior risco de regressão — cobertos
  pelos testes existentes de load (4.1/4.3 já testam backfill; eles têm de
  continuar verdes sem mudança).
- **Rate limit em memória** zera a cada restart e não distingue usuários atrás
  de NAT — aceitável para single-player local; Fase 10b troca por solução real.
- **MockLLM/FallbackLLM:** irrelevante. **Quota:** zero requests.
