# SPEC-235 — evidência

Mudou: `postgres_turns.reclaimable` (op `failed` re-claimável após mudança de versão, atualiza `base_game_version`);
gate `pending_operation` em equip/levelup (`api._failed_pending_operation`); `formatDetail` (422 legível);
export da crônica com `filename*=UTF-8''`; `safeStorage`; `shouldClearPending` + botão "Descartar ação pendente";
typewriter com `onDone`/estado inicial; chip do Abismo `nenhum` com Carga 0; `backstory: null`.

Testes: `tests/test_bug_api_pending_erros.py` (7), `web/tests/{http,pending,typewriter}.test.mjs`.
Resultados: pytest offline verde; `npm test` 43/43; `tsc --noEmit` e `npm run build` limpos.

## Revisão independente `Sol` (2026-10-16) — APPROVED_WITH_FOLLOWUPS

Segurança do reclaim (R1), verificada contra Postgres real (Supabase local, `infra_local`,
`tests/test_spec235_reclaim_local.py`, 3 testes, dados apagados no teardown):

- `failed` → equip avança a versão → reclaim com a mesma chave/hash/kind/dono: `running`,
  `base_game_version` atualizada, token novo; o token antigo fica cercado (`complete` → `LeaseHeld`).
- Hash divergente → `Conflict`; outro dono → `NotFound` (jogo invisível) ou `Conflict` (chave indisponível);
  outro kind → `Conflict`; `running` com lease fresco → `LeaseHeld`; `running` expirado com versão mudada →
  `Conflict` (estrito); `completed` → `Conflict` em qualquer versão, e `app.turns` tem exatamente 1 linha da
  operação (efeito confirmado nunca reexecuta). `failed` nunca tem efeito de jogo: `commit_game` marca
  `completed` na mesma transação do UPDATE de `app.games`.
- Gate R3 contra `app.operations` real: equip/levelup → 409 `pending_operation` com o `operation_id` da falha;
  death não é bloqueado; outro dono não vê a falha; um turno posterior concluído supera a falha e libera equip.

Frontend: `web/e2e/pending-discard.spec.ts` (Playwright, API determinística do repo, 3 testes):
falha de rede → "Consultar / retomar" e "Descartar ação pendente" visíveis (axe sem serious/critical)
→ descartar → nova ação enviada; 409 `operation_conflict` definitivo → pending limpo, input liberado, nova
ação OK. Screenshots `discard-pending-390.png` / `discard-pending-1440.png` (captura opt-in
`RPG_SPEC235_SHOTS=1`). `e2e/critical-journeys.spec.ts` 16/16 verde. `tests/test_audit_browser_local.py`
continua achando `get_by_role('button', name='Consultar / retomar ação pendente')` (nome inalterado, único).

Correções do revisor: (1) "Consultar / retomar" herdava fundo claro do UA (texto ilegível) ao virar filho do
novo grupo → `btn--primary`; (2) a mensagem do 409 `pending_operation` dizia "descarte-a", mas o descarte é
local e não libera o gate do servidor → agora "Retome-a ou conclua uma nova ação".

Follow-ups (não bloqueiam): o descarte local não informa o servidor — equip/levelup seguem bloqueados até um
turno concluir (turnos continuam livres, sem soft-lock); um abandono server-side (`abandoned`, alternativa D-A)
resolveria. Smoke §6 com LLM real não executado: o fluxo não depende de LLM e foi coberto por Postgres real +
Playwright + TestClient (422 legível e export `Дмитрий`).
