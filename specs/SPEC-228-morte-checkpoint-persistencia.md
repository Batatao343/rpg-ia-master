# SPEC-228 — Morte sem checkpoint, ordem save/checkpoint e campos não persistidos

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-060 checkpoints-morte, SPEC-086 hardening-persistencia-sse-idempotencia e SPEC-101 checkpoint-seguro-fora-combate `done` são corrigidas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-202, SPEC-203, SPEC-207, SPEC-212, SPEC-213 (ordem final 2026-10-15)
> **Nota de schema (cadeia final 2026-10-15):** ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1".
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-04-01, 04-04, 04-05, 04-06, 04-07, obs-04-a, obs-04-b (`proximas-specs/novas-specs/bugs/achados/04-persistencia-concorrencia.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — altera o fluxo de morte e a ordem de persistência (perda de progresso do jogador)
> **EVAL_AUTHORING_REQUIRED:** `false` — cobertura por testes determinísticos de persistência/API (TestClient + MockLLM)

---

## 1. Contexto & Objetivo

A spec SPEC-060 (checkpoints-morte, D7) promete: "sem checkpoint → restaura do estado INICIAL da sessão".
A auditoria reproduziu (`death.py`, re-executado pelo orquestrador) que, pela API, **"Continuar" na tela de morte
sem checkpoint utilizável não restaura nada**: o herói revive no mesmo turno e lugar com Vitalidade 1, mantendo
mundo, inventário e memória — uma ressurreição grátis que o modal anuncia como restauração.

Fatos no HEAD `d6af933`:

- [F] `api.py:3382` chama `_cp.resolve_death_choice(state, req.choice)` sem `initial_state`; em
  `services/checkpoints.py:171` o fallback D7 é `deepcopy(initial_state) if initial_state is not None else
  deepcopy(state)` — o próprio estado morto — e `_sanitize_legacy_combat_checkpoint` + `death_pending=False`
  o "curam" para Vitalidade 1. Reprodução: estado morto no turno 30 sem checkpoint → `vit 1, dead False, turn 30`.
  Idem com `.checkpoint.json` vazio/corrompido: `has_checkpoint()` devolve `True` (só testa existência) e
  `load_checkpoint` devolve `None`.
- [F] `api.py::_commit_turn` (perfil legacy): ordem **save → checkpoint**, e `_prepare_checkpoint` marca
  `continuity.last_checkpoint_turn = N` ANTES de gravar. Falha em `save_checkpoint` (WinError 5/OneDrive, disco)
  → turno persistido com `processed_action_ids` contendo o `action_id`, cliente recebe 500, retry devolve replay 200,
  checkpoint nunca regravado e `will_lose_turns` calculado sobre um checkpoint inexistente.
- [F] `persistence._raw_to_state` força `"needs_replan": False` (l.825) e `_state_to_save_data` não grava a flag;
  a API recarrega o save a cada ação → o retry do planejador (SPEC-037 R4) e o replan pós-combate/fuga
  (`combat.py:1183`, `storyteller.py:848`, `campaign_manager.py:271/291`) só acontecem por gatilhos secundários.
  Round-trip executado: `needs_replan True → False`.
- [F] `api.py:640-643` `_game_lock(None)` → chave `"__latest__"`: requisição sem `game_id` não serializa com a
  que traz o UUID do mesmo save; `game_action_stream` resolve "mais recente" duas vezes (aceite e worker).
- [F] `persistence.py:250-275`: `messages` perde `ToolMessage`, `additional_kwargs`, `name`, `id`, `tool_calls`
  (latente: nenhum agente usa hoje).
- [F] `migrate_state` aceita `schema_version > 8` (rollback de deploy) sem erro, `_raw_to_state` descarta campos
  desconhecidos e o próximo save regrava `schema_version=8` — perda silenciosa de dados do schema mais novo.
- [F] `continuity.normalize`: `last_checkpoint_turn` ausente assume o turno atual → `will_lose_turns` de saves
  antigos mente ("0 turnos perdidos").

Objetivo: morte sempre resolve para um estado **honesto** (checkpoint válido, estado inicial reconstruído, ou
recusa explícita); persistência nunca anuncia checkpoint que não existe; flags de controle do grafo sobrevivem
ao reload; perfil legacy serializa por jogo real.

## 2. Requisitos

- **R1** — [R] `persistence.has_checkpoint(game_id)` devolve `True` só se o arquivo existe E parseia como JSON
  com `schema_version` e `player`. Teste de reprodução: arquivo vazio → hoje `True`; depois `False`.
- **R2** — [R] `POST /game/death` com `choice="continue"` e sem checkpoint válido: (a) se existe
  `continuity.initial_snapshot` (novo, ver R4) → restaura dele; (b) senão → HTTP 409 `detail="Sem ponto de
  retorno válido; aceite o memorial ou inicie nova jornada."` com `death_pending` preservado. Nunca devolve o estado
  morto saneado. Teste de reprodução (TestClient, MockLLM): save sem checkpoint + `death_pending` → hoje 200 com
  `vitalidade 1`; depois 409 (ou restauração do snapshot inicial quando presente).
- **R3** — [R] `resolve_death_choice` recebe `initial_state` obrigatório quando `checkpoint is None` e sem slot em
  disco; a assinatura passa a `resolve_death_choice(state, choice, *, checkpoint=None, initial_state=None,
  strict=True)` — `strict=True` levanta `NoRestorePoint` em vez de cair no estado morto. Harness mantém o uso atual
  (passa `initial_state`). Teste unitário: `strict=True` sem fontes → `NoRestorePoint`.
- **R4** — [R] `/game/new` grava `continuity.initial_snapshot_ref` = checkpoint inicial (já existe) e, para saves
  legados sem checkpoint inicial, o primeiro `load` cria um checkpoint inicial sintético a partir do estado atual
  **marcado** `synthetic_from_turn=N` (o modal informa "retorno ao turno N"). Teste: save legado v7 sem checkpoint →
  após load, `has_checkpoint` verdadeiro com marcação sintética.
- **R5** — [R] Ordem de persistência no legacy: `checkpoint` (quando devido) é gravado ANTES do save do turno e
  `last_checkpoint_turn` só é marcado após `save_checkpoint` devolver `True`; falha de checkpoint vira warning
  `continuity.checkpoint_deferred=True` (tentar no próximo turno), o save do turno prossegue e a resposta é 200.
  Teste de reprodução: `save_checkpoint` monkeypatched para `False` no turno 10 → hoje 500 + save gravado +
  `last_checkpoint_turn=10`; depois 200, `last_checkpoint_turn` inalterado, `checkpoint_deferred=True`, e no turno 11
  o checkpoint é gravado.
- **R6** — [R] `will_lose_turns`/`will_restore_turn` da resposta de morte derivam do checkpoint REAL em disco
  (turno lido do arquivo), não de `continuity.last_checkpoint_turn`. Teste: `last_checkpoint_turn=20` com arquivo do
  turno 10 → resposta diz 10.
- **R7** — [R] `needs_replan` persiste no save (`_state_to_save_data` + `_raw_to_state`, default `False`). Teste de
  round-trip: `True → True`. Teste de integração: fim de combate seta `needs_replan`; próximo `/game/action` chama o
  planejador (observável por `campaign_plan.last_planned_turn`).
- **R8** — [R] `_game_lock` no legacy resolve o `game_id` REAL antes de travar: requisição sem `game_id` resolve
  `_resolve_save_file(None)` → lê `game_id` do arquivo → trava por esse UUID. `game_action_stream` resolve o arquivo
  UMA vez e passa o path/game_id ao worker. Teste: duas threads (uma com `game_id`, outra sem) sobre o mesmo save →
  turnos serializados (contador de `session_action_count` = 2, nunca 1).
- **R9** — [R] `migrate_state` com `schema_version > SCHEMA_VERSION` → `IncompatibleSaveError` (API: 409 com
  mensagem "save de versão mais nova"); nunca regrava com versão menor. Teste: raw com `schema_version=99` → erro.
- **R10** — [R] `continuity.normalize`: `last_checkpoint_turn` ausente → `None` (desconhecido); `will_lose_turns`
  com `None` → calculado a partir do arquivo (R6) ou `null` na API (modal mostra "ponto de retorno desconhecido").
- **R11** — [H] `messages` serializadas via `langchain_core.messages.messages_to_dict/messages_from_dict`
  (preserva `ToolMessage`, `additional_kwargs`, `name`, `id`, `tool_calls`), com leitura retrocompatível do formato
  atual `{role, content}`. Teste de round-trip com os 5 tipos.

### Fora de escopo

- Memorial/permadeath/decisões de produto da SPEC-060 (mantidas).
- Perfis DB (`local/hosted`): o commit transacional já grava turno+checkpoint na mesma transação — só R7/R9/R11
  se aplicam; R2/R6 valem para ambos.
- Lease/heartbeat pós-commit e fila de jobs (spec `SPEC-230-jobs-lease-filas.md`).

## 3. Design técnico

### Arquivos alterados

- `persistence.py` — `has_checkpoint` validando JSON (R1); `needs_replan` em save/load (R7); `IncompatibleSaveError`
  em `migrate_state` (R9); `messages_to_dict` (R11); `checkpoint_turn(game_id) -> int | None` (R6).
- `services/checkpoints.py` — `NoRestorePoint`, parâmetro `strict` (R3); `maybe_write` devolve `(written: bool)` e
  não marca `last_checkpoint_turn` (R5); checkpoint inicial sintético (R4).
- `services/continuity.py` — `last_checkpoint_turn: int | None`, `checkpoint_deferred: bool` (R5/R10).
- `api.py` — `/game/death` (R2), `_commit_turn` legacy ordem checkpoint→save (R5), `will_lose_turns` por arquivo (R6),
  `_game_lock` por `game_id` real (R8), handler de `IncompatibleSaveError` → 409 (R9).
- `game_engine.py` (CLI) — prompt de morte respeita 409/`NoRestorePoint`.
- `web/src/components/DeathModal.tsx` — trata 409 ("sem ponto de retorno") e `will_lose_turns: null`.

### Schemas

```python
class Continuity(TypedDict, total=False):
    last_checkpoint_turn: int | None
    checkpoint_deferred: bool
    initial_snapshot_ref: str            # path/ident do checkpoint inicial
    synthetic_from_turn: int | None      # R4: checkpoint inicial sintético
    timeline_epoch: int
```

Resposta de `/game/death` (409): `{"detail": "...", "code": "no_restore_point", "death_pending": true}`.

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
1. `tests/test_bug_morte_checkpoint.py`: `test_has_checkpoint_rejects_empty_file` (R1),
   `test_death_continue_without_checkpoint_refuses` (R2), `test_resolve_death_choice_strict_raises` (R3),
   `test_checkpoint_written_before_save_and_failure_defers` (R5), `test_will_lose_turns_from_file` (R6),
   `test_needs_replan_roundtrip` (R7), `test_lock_latest_serializes_with_uuid` (R8),
   `test_newer_schema_refused` (R9), `test_messages_roundtrip_all_types` (R11).
2. Registrar a saída vermelha em `docs/<spec>/README.md`.
### Etapa 1 — persistence/checkpoints/continuity (R1, R3, R4, R7, R9, R10, R11)
### Etapa 2 — api.py (R2, R5, R6, R8) + CLI + DeathModal
### Etapa 3 — regressão: `uv run pytest` + playtest offline `combate` 40 turnos com morte → restauração honesta
(grep de `deaths_log` e `will_restore_turn` coerentes).

## 5. Critérios de aceite

- [x] 9 testes de reprodução vermelhos → verdes; `tests/test_checkpoints*.py`, `tests/test_persistence*.py`,
      `tests/test_hardening_sse*.py` verdes ou diff justificado.
- [x] `uv run pytest` verde.
- [x] Saves v0..v8 carregam; save v99 recusado com 409.
- [x] `npm run build` verde (DeathModal).
- [x] Guard de FallbackLLM: não se aplica.

## 6. Smoke test com LLM real

1. Jogo novo → morrer no turno ~5 → "Continuar" → volta ao turno do checkpoint inicial com inventário/mundo iniciais.
2. Apagar manualmente o `.checkpoint.json` de um jogo → morrer → "Continuar" → 409 diegético no modal; "Aceitar" funciona.
3. Fim de combate → próximo turno replaneja (log `[PLANNER]`).

## 7. Riscos & compatibilidade

- Saves legados sem checkpoint: R4 cria sintético marcado; o modal deixa claro o turno de retorno.
- Ordem checkpoint→save: em crash entre os dois, o checkpoint pode ficar 1 turno à frente do save — o load
  compara `turn` e descarta checkpoint > save (`_sanitize`), comportamento a cobrir por teste.
- R8 muda a chave de lock do CLI/smoke (`scripts/smoke_api.sh` não envia `game_id`): continua funcionando.

## 8. Pontos de decisão do dono

- **D-A (sem ponto de retorno):** default 409 + restauração do snapshot inicial quando houver; alternativa:
  reconstruir estado inicial determinístico a partir de `player` nível 1 + mapa (mais complexo, mais "mágico").
- **D-B (R11 formato de mensagens):** default migrar para `messages_to_dict` com leitura retrocompatível; alternativa:
  adiar (latente) e só documentar.
- **D-C (schema mais novo):** default 409; alternativa: carregar read-only (sem salvar).

## 9. Evidência requerida

- `uv run pytest` completo; testes de reprodução antes/depois.
- `docs/<spec>/README.md` com transcrição de `death.py`/`rt.py` como testes e screenshot do modal em 409.
- Revisão `Sol` independente (fluxo de morte e ordem de persistência).

## 10. Implementação (2026-10-16)

Defaults usados: **D-A** = 409 `no_restore_point` (sem snapshot inicial separado: o checkpoint de 1 slot é o único ponto de retorno; R4 cria checkpoint sintético `synthetic_from_turn` em save legado no primeiro `/game/action`, não no `load_game_state`, para não ter efeito colateral em leituras); **D-B** = `messages_to_dict` com leitura retrocompatível; **D-C** = 409 `save_schema_newer`, sem bump de `SCHEMA_VERSION` (permanece 8).
Desvios: a ordem checkpoint→save vale para o commit legacy via `checkpoints.write_now` (sem reavaliar a cadência); perfis DB seguem marcando antes (mesma transação). Testes: `tests/test_bug_morte_checkpoint.py`. Evidência: `docs/spec228/README.md`. Revisão Sol independente pendente (REVIEW_REQUIRED).
