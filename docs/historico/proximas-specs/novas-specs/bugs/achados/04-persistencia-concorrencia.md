# Área 04 — Persistência / migrações / concorrência (auditoria 2026-10-15)

**Arquivos cobertos:** `persistence.py` (inteiro), `services/game_serialization.py`, `services/checkpoints.py`, `services/continuity.py`, `state.py` (chaves), `api.py` (lock por game_id, ledger `action_id`, `_run_turn_collected`, `_commit_turn`, `_stream_turn`, `/game/death`, `/game/equip`, `/game/levelup`, saves/DELETE), `infrastructure/postgres_turns.py`, `infrastructure/postgres_jobs.py`, `infrastructure/postgres.py`, `services/lease_heartbeat.py`, `services/turn_execution.py`, `services/job_fence.py`, `services/operation_recovery.py`, `workers/job_worker.py`, `workers/drain.py`, `workers/run_worker.py`, `workers/embedding_jobs.py`, `services/memory_retry.py`, trechos de `infrastructure/pgvector_memory.py`/`chronicle_repository.py` (enqueue) e DDL de `app.turns/jobs`.
**Não cobertos (tempo):** `infrastructure/local_adapters.py` (só índice), `infrastructure/runtime.py`, `infrastructure/contracts.py`, `services/restore_effects.py`, `services/turn_effects.py`; nada foi executado contra Postgres real (sem DB local) — achados PG são por leitura + simulação do componente Python.
**Scripts de repro (scratchpad):** `rt.py` (round-trip), `lease.py`, `death.py`, `ctime.py`.

**Contagem:** crítica 0 · alta 1 · média 4 · baixa 3 (+ 6 descartados)

---

### BUG-04-01 — "Continuar" na tela de morte sem checkpoint utilizável NÃO restaura nada (revive no mesmo lugar com Vitalidade 1)
- **Severidade:** alta
- **Categoria:** regra-divergente / estado-inconsistente
- **Local:** `services/checkpoints.py:resolve_death_choice` (fallback `restored = deepcopy(initial_state) if initial_state is not None else deepcopy(state)`), chamada em `api.py:3381` (`_cp.resolve_death_choice(state, req.choice)` — nunca passa `initial_state`)
- **Evidência:** o docstring/spec D7 promete "sem checkpoint → restaura do estado INICIAL da sessão", mas a API não fornece `initial_state`; o fallback é o próprio estado morto, e `_sanitize_legacy_combat_checkpoint` + `death_pending=False` o "curam" para Vitalidade 1.
- **Reprodução (executado, `death.py`):** estado morto turno 30 (`vitalidade 0, dead, estado_terminal`), sem arquivo de checkpoint → `resolve_death_choice(dead,"continue")` => `vit 1, dead False, terminal False, turn 30` (nada voltou). Idem com `.checkpoint.json` vazio/corrompido (`has_checkpoint()` devolve True, `load_checkpoint` devolve None) => mesmo resultado.
- **Impacto:** saves anteriores à feature de checkpoints (ou com slot corrompido/removido) ganham ressurreição grátis sem perda de progresso e sem reverter mundo/inventário/memória; o modal anuncia `will_restore_turn` que não ocorre. Novos jogos criam checkpoint inicial, então atinge saves legados/corrompidos.
- **Correção sugerida:** no `/game/death` legado, se `load_checkpoint` falhar, recusar com 409/mensagem clara ou reconstruir um estado inicial determinístico; nunca devolver o estado morto como "restaurado". Fazer `has_checkpoint` validar que o JSON parseia.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre o fallback D7 pela API (apenas o harness passa `initial_state`).

### BUG-04-02 — `operation_scope` converte turno JÁ COMMITADO em erro (LeaseHeld "lease_lost") quando o heartbeat ticka após o commit
- **Severidade:** média
- **Categoria:** race
- **Local:** `services/lease_heartbeat.py:keep_lease_alive` (`watch.check()` após `yield`), `services/turn_execution.py:operation_scope`
- **Evidência:** `commit_game` marca a operação `completed` e zera `lease_token`; o próximo `heartbeat()` faz `update ... where status='running' and lease_token=%s` => rowcount 0 => `LeaseHeld` => `watch.lost.set()`. Se o tick cai entre o commit e a saída do `with` (ou fica bloqueado no `select ... for update` do jogo durante o commit), `watch.check()` levanta `LeaseHeld` pós-commit; `operation_scope` ainda chama `coordinator.fail()` (engolido) e relança. `_execute_action` não trata (não há exception_handler de LeaseHeld no api.py) => HTTP 500 / evento SSE `error`.
- **Reprodução (simulada, `lease.py`):** coordinator fake cujo `heartbeat` levanta `LeaseHeld` depois de `committed=True`: `EXC apos commit: LeaseHeld lease_lost | fail() chamado: ['LeaseHeld']`.
- **Impacto:** em ~duração-do-commit/intervalo(45 s) dos turnos o jogador vê erro apesar do turno estar salvo; retry devolve o recibo (benigno, mas confunde e polui métricas `lease lost`).
- **Correção sugerida:** parar o heartbeat (`stop.set()` + join) ao sinal de commit e/ou `check()` ignorar `lost` se a operação já está `completed`; `heartbeat()` tratar rowcount 0 + status completed como sucesso.
- **Confiança:** provável (mecânica simulada; janela temporal não medida em PG real)
- **Testes existentes relacionados:** nenhum (testes de turns cobrem fence, não o pós-commit).

### BUG-04-03 — Fila de jobs sem teto de tentativas para jobs que expiram o lease (poison loop)
- **Severidade:** média
- **Categoria:** outro (retry sem limite)
- **Local:** `infrastructure/postgres_jobs.py:lease` (cláusula `(status='running' and lease_until < now())`)
- **Evidência:** o re-lease de um job `running` expirado só faz `attempts=j.attempts+1`; a transição para `dead` só existe em `fail()` (quando o handler devolve exceção). Se o handler derruba o processo/função serverless (timeout de 58 s do cron, OOM, kill), o job é re-leased indefinidamente, `attempts` ultrapassa `max_attempts` e nunca vira `dead`.
- **Reprodução:** por leitura (sem PG local): job com `max_attempts=3` cujo handler excede o budget de `drain_jobs` => a cada lease expirado `attempts` = 4,5,6... e `status` segue `running`/re-leased.
- **Impacto:** geração de arte/embedding/crônica "venenosa" re-executa para sempre (custo de provedor repetido, reserva de Estilhas presa em hold).
- **Correção sugerida:** no `lease`, marcar `dead` (`last_error_code='lease_expired_max_attempts'`) os running-expirados com `attempts>=max_attempts` antes de selecionar; ou filtrar `attempts < max_attempts`.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** `tests/test_postgres_jobs_local.py` (não cobre expiração com max_attempts atingido).

### BUG-04-04 — Falha ao gravar checkpoint DEPOIS do save do turno deixa save gravado + 500 e `last_checkpoint_turn` mentiroso (legacy)
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `api.py:_commit_turn` (legacy: `_require_saved` -> `_cp.maybe_write` -> `raise RuntimeError`), `_prepare_checkpoint` (marca `continuity.last_checkpoint_turn` ANTES de gravar)
- **Evidência:** ordem save -> checkpoint. Se `save_checkpoint` falha (WinError/OneDrive, disco), o turno já está persistido com `processed_action_ids` contendo o `action_id` e `last_checkpoint_turn=N`, mas o cliente recebe 500. O retry cai em `_action_already_processed` e devolve o replay 200 — o checkpoint nunca é regravado e `will_lose_turns` é calculado a partir de um checkpoint que não existe (a restauração real volta ao checkpoint anterior, possivelmente muito mais velho).
- **Reprodução:** por leitura; basta `persistence.save_checkpoint` retornar False num turno múltiplo de 10.
- **Impacto:** "Continuar" após a morte volta mais turnos do que o modal informa; 500 espúrio num turno persistido.
- **Correção sugerida:** gravar o checkpoint antes do save (ou só marcar `last_checkpoint_turn` após confirmar) e tratar falha como warning com nova tentativa no turno seguinte.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum encontrado para falha de checkpoint pós-save.

### BUG-04-05 — `needs_replan` não é persistido: replanejamento forçado se perde a cada recarga da API
- **Severidade:** média
- **Categoria:** round-trip
- **Local:** `persistence.py:_state_to_save_data` (ausente) e `_raw_to_state` (`"needs_replan": False` fixo, linha 825); setters em `agents/campaign_manager.py:271/291`, `agents/combat.py:1183`, `agents/storyteller.py:848`
- **Evidência / repro (executado, `rt.py`):** estado com `needs_replan=True` -> save -> load => `CHG .needs_replan: True -> False`. A API recarrega do disco a cada ação, então a flag só vale dentro do turno.
- **Impacto:** (a) a spec beats-visibilidade-ptbr R4 ("plano em inglês/falho mantém needs_replan para tentar de novo no próximo turno") não funciona no fluxo da API: o retry só ocorre quando outro gatilho de `_should_replan` dispara (REPLAN_INTERVAL); (b) fim de combate/fuga que pede novo plano depende de beats esgotados/mudança de região. Mitigado por esses gatilhos secundários, por isso média.
- **Correção sugerida:** persistir `needs_replan` (booleano) em save/load.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre persistência da flag.

### BUG-04-06 — Chave de lock `"__latest__"` não serializa com o lock do mesmo jogo identificado por UUID
- **Severidade:** baixa
- **Categoria:** race
- **Local:** `api.py:640-643` (`_game_lock(None)` -> `"__latest__"`), usado por `/game/action`, `/game/death`, `/game/equip`, `/game/levelup`; `game_action_stream` resolve `_resolve_save_file(None)` (save mais recente) duas vezes (criação do SSE e dentro do worker)
- **Evidência:** requisição sem `game_id` usa lock diferente de uma com `game_id=X` para o mesmo save => duas mutações simultâneas leem o mesmo save e a última sobrescreve (turno perdido). No stream, o "mais recente" pode mudar entre o `accepted` e o worker.
- **Reprodução:** por leitura; o cliente web sempre envia `game_id`, então atinge CLI/smoke/scripts que omitem o campo.
- **Correção sugerida:** resolver o `game_id` real antes de pegar o lock (`state["game_id"]`) ou exigir `game_id` no legacy.
- **Confiança:** provável
- **Testes existentes relacionados:** nenhum.

### BUG-04-07 — `messages` não faz round-trip: ToolMessage descartada, `additional_kwargs/name/id/tool_calls` perdidos, tipo "unknown" salvo e ignorado no load
- **Severidade:** baixa (produção atual só usa Human/AI/System simples)
- **Categoria:** round-trip
- **Local:** `persistence.py:250-275`
- **Repro (executado, `rt.py`):** 5 mensagens (Human com kwargs/name/id, AI com tool_calls, System, Tool, AI com content-list) -> 4 recarregadas; ToolMessage some; `additional_kwargs={}`, `name=None`, `id=None`, `tool_calls=[]`.
- **Impacto:** nenhum hoje (grep: sem `additional_kwargs`/ToolMessage em agents/services); latente se um agente passar a usar tool calling/ids (dedupe do reducer `operator.add`).
- **Correção sugerida:** serializar via `messages_to_dict/messages_from_dict` de `langchain_core.messages`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** testes de persistência cobrem só Human/AI texto.

### BUG-04-08 — Jobs `embed_memory`/`compress_chronicle` mortos (`dead`/`cancelled`) nunca são reenfileirados (dedupe por `kind,dedupe_key`)
- **Severidade:** baixa
- **Categoria:** outro
- **Local:** `infrastructure/pgvector_memory.py:107` (`on conflict (kind,dedupe_key) do nothing`, `dedupe_key=document_id`), `services/chronicle_repository.py:66`
- **Evidência:** job de embedding que esgota 5 tentativas (queda de provider) fica `dead`; reescrever o mesmo fato cai no ramo "documento existente" e retorna sem novo job => documento fica `pending` sem vetor (só busca lexical).
- **Reprodução:** por leitura.
- **Correção sugerida:** no enqueue, reativar job `dead` (status queued, attempts 0) quando o documento segue `pending`; ou varredura periódica.
- **Confiança:** provável
- **Testes existentes relacionados:** nenhum.

---

## Observações menores (não numeradas)
- `migrate_state`: save com `schema_version` > 8 (rollback de deploy) é aceito sem erro e `_raw_to_state` descarta campos desconhecidos; o próximo save regrava `schema_version=8` perdendo dados do schema novo. Sem proteção explícita.
- `continuity.normalize`: `last_checkpoint_turn` ausente assume o turno atual (parece "checkpoint agora" sem haver), afetando `will_lose_turns` de saves antigos.
- `get_latest_save_file` (legacy): se o save mais recente estiver corrompido, `load_game_state()` sem argumento devolve None em vez de cair no anterior (a listagem em si é tolerante).
- DELETE no perfil DB: se `claim()` levantasse `NotFound`, `claim` ficaria não-atribuído (UnboundLocalError em `_fail_operation(claim,…)`); hoje `claim()` com `game_id=None` não levanta NotFound.

## Descartados / falsos positivos
1. **`getctime` no Windows não elege "mais recente"** — testado (`ctime.py`): tmp+`os.replace` produz ctime novo (save A re-salvo virou o mais recente). Sem bug.
2. **Chaves do GameState "perdidas" no round-trip** (`active_npc_name`, `combat_declaration`, `turn_baseline`, `last_action_outcome`, `last_economy_action`, `narrative_rejections`, `router_confidence`, `combat_flee_*`, `combat_origin_hint`, `action_guard_blocked`, `turn_prepared`, `player_reaction_card_id`, `npc_fallback_hint`): todas transitórias, reescritas no início de cada turno (router/action_guard/turn_prepare).
3. **`interaction_progress`/`canonical_outcomes` "perdidos"** — não são chaves de GameState (chaves que eu inventei no script; já persistidas aninhadas por SPEC-142).
4. **`player.vitalidade 10->11` no round-trip** — `_normalize_vitality_actor` aplica o bônus de Postura (dado sintético inconsistente meu); comportamento documentado (letalidade-v2).
5. **Eviction do ledger `action_id` (64)** — reexecução só com retransmissão atrasada em >64 ações; irrealista.
6. **Lock SSE/desconexão** — o worker detém o lock e persiste mesmo sem consumidor (SPEC-086); RLock criado sob `_game_locks_guard` (sem race de criação); `os.replace` com retry e unlink do tmp corretos; fsync de diretório inaplicável no Windows.
