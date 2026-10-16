# SPEC-235 — API/frontend: soft-lock da ação pendente, erros 422 legíveis, export unicode, storage bloqueado e detalhes de exibição

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-086 hardening-persistencia-sse-idempotencia, SPEC-111 fase-10b-turnos-duraveis-concorrencia-fila e SPEC-157 auditoria-2026-09-frontend-sessao `done` são corrigidas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-204, SPEC-212 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-07-01, 07-02, 07-04, 07-05, 07-06, 07-07, 07-08, 07-09, 04-06 (`achados/07-api-frontend.md`, `04-persistencia-concorrencia.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — altera o contrato de idempotência da operação no perfil durável
> **EVAL_AUTHORING_REQUIRED:** `false` — cobertura por testes Node/Playwright (frontend evals SPEC-172 podem ganhar F17 "pending descartável" em handoff)

---

## 1. Contexto & Objetivo

Fatos no HEAD `d6af933` (área 07; orquestrador conferiu os trechos de `postgres_turns.py:80-95`, `App.tsx:495-555`,
`pendingOperation.ts:15-45`):

- [F] **Soft-lock da ação pendente (perfil durável)** — `web/src/App.tsx:498-515`: qualquer texto diferente do pending
  é recusado ("Resolva a ação pendente antes de enviar outra."); o único `clearPending` em erro é para 400/422
  (`:540-544`). No servidor, `postgres_turns.claim()` com a MESMA `operation_id` exige `existing["base_game_version"]
  == base_version` (`:89-91`) → `Conflict("operação divergente")` → 409 `operation_conflict`. Sequência: turno falha
  (op `failed`) → jogador equipa item / escolhe nível / resolve morte (`/game/equip|levelup|death` não checam pending e
  avançam a versão do jogo) → reenvio da pendente → 409 permanente; sem UI de descartar → campanha travada até limpar
  `localStorage`. (Provável por leitura dos dois lados; sem Postgres offline.)
- [F] **422 como "[object Object]"** — `web/src/http.ts:21-25` `String(json.detail)`; em 422 `detail` é lista de
  objetos. Repro executada: `POST /game/new class_name:"Xyz"` → banner "Falha ao criar personagem: [object Object]".
- [F] **Export da crônica 500 com nome fora de latin-1** — `api.py:3735-3738` monta `Content-Disposition` com
  `c.isalnum()` (aceita cirílico/CJK); Starlette codifica headers em latin-1 → `UnicodeEncodeError`. Repro: `Дмитрий` → 500.
- [F] **`localStorage` sem guarda** — `App.tsx:76` (`useRef(localStorage.getItem(...))` no render), `:152,178,237,269,
  314,590,614`, `pendingOperation.ts:35` (`setItem` lança de propósito): storage bloqueado → `SecurityError` no 1º
  render (sem ErrorBoundary) → tela branca; ou toda ação falha. (Hipótese, sem browser.)
- [F] 404/409 não-recuperáveis (memorial, arquivado, save apagado) deixam o pending preso e o botão "retomar" reaparece
  (`App.tsx:540-544`); typewriter cortado em 300 ms no caminho POST (`:317-326`, `useTypewriter.ts`); chip do Abismo do
  Médico mostra "algo se acumula…" com Carga 0 (`api.py:1188-1195`, `Hud.tsx:604-616`); `backstory: null` vira "None"
  (`api.py:842,2705`); lock `"__latest__"` no legacy não serializa com o lock por UUID (`api.py:640-643`, área 04 —
  tratado em `SPEC-228` R8, citado aqui por afinidade).

Objetivo: a operação pendente é sempre resolvível (servidor reaproveita op `failed` ou o cliente oferece descarte
explícito); erros da API são legíveis; export funciona para qualquer nome; o app degrada sem storage.

## 2. Requisitos

- **R1** — [R] Servidor: `claim()` de `operation_id` existente com `status == "failed"` reaproveita a operação
  atualizando `base_game_version`, `lease` e `request_sha256` (mesma `kind`/`game_id`/owner) em vez de `Conflict`.
  Op `completed` continua devolvendo o recibo; `running` fresco continua `LeaseHeld`. Teste (fake store de
  `infrastructure/testing.py`): op falha → equip incrementa versão → reclaim com mesma id → sucesso; `request_hash`
  divergente continua 409 `operation_request_mismatch`.
- **R2** — [R] Cliente: 409 `operation_conflict`/`operation_request_mismatch` e 404 `game_not_found` e 409
  `memorial`/`archived` limpam o pending e mostram banner com ação; em QUALQUER erro ≥ 400 com pending, a UI oferece
  "Descartar ação pendente" (botão no composer) que chama `clearPending` e libera o input. Teste Node
  (`web/tests/pending.test.mjs`): tabela status → pending limpo/mantido; teste Playwright: após 409, botão visível e
  input liberado.
- **R3** — [R] `/game/equip`, `/game/levelup`, `/game/death` no perfil durável: se existe operação `failed` do mesmo
  jogo/owner, respondem 409 `pending_operation` (ou, D-A, marcam a op como `abandoned` e seguem). Teste: equip com op
  `failed` pendente → 409 com `operation_id` no corpo.
- **R4** — [R] `http.ts::errorFor`: `detail` lista → junta `msg` (+ `loc.slice(1).join(".")`) por `; `; objeto → `msg`
  ou JSON; string → como está. Teste Node: payload 422 real → "class_name: classe desconhecida".
- **R5** — [R] `/game/chronicle/export`: `filename=` só ASCII (`NFKD` + `[A-Za-z0-9_-]`, fallback `cronica`) e
  `filename*=UTF-8''<urlquote(nome)>`. Teste TestClient: `Дмитрий` → 200 e header válido.
- **R6** — [R] `web/src/lib/safeStorage.ts`: `get/set/remove/keys` com try/catch e fallback `Map` em memória por aba;
  todos os acessos a `localStorage` em `App.tsx`/`pendingOperation.ts`/`hooks` passam por ele; `preparePending` não lança
  quando persiste em memória (marca `volatile: true` e avisa 1× "sua retomada não sobrevive a recarga"). Teste Node com
  `localStorage` stub que lança → app continua; Playwright com `--block-third-party`/storage desabilitado → tela abre.
- **R7** — [R] Typewriter: `streaming:false` derivado do fim da animação (callback `onDone`) e estado inicial
  `useState(enabled ? "" : text)`; entradas de histórico não renderizam vazio por 1 frame. Teste Node do hook.
- **R8** — [R] `_abyss_tier_view`: classe com `abyss.hidden` → `"nenhum"` quando `abyss_charge == 0`, `"?"` só com
  carga > 0. Teste: Médico nível 1 → chip oculto.
- **R9** — [R] `StartCharacterIn.backstory: str = Field("", max_length=2000)` (null → ""); `req.backstory or ""` nos 2
  usos. Teste: `backstory: null` → resumo sem "None".

### Fora de escopo

- Métrica SSE (SPEC-200), composer/rascunho (SPEC-204), layout/menus (205/208/209/210/211/216), export de sessão (207).
- Lock por `game_id` real no legacy (spec `SPEC-228` R8).
- Segurança de sessão/CSRF (auditoria de segurança).

## 3. Design técnico

### Arquivos alterados

- `infrastructure/postgres_turns.py:80-100` — reaproveitamento de op `failed` (R1); `api.py` equip/levelup/death gate (R3).
- `web/src/App.tsx:76,152,178,237,269,314,317-326,498-552,590,614`, `web/src/pendingOperation.ts`, `web/src/http.ts:21-25`,
  `web/src/hooks/useTypewriter.ts`, novo `web/src/lib/safeStorage.ts` — R2, R4, R6, R7.
- `api.py:842,1188-1195,2705,3735-3738` — R5, R8, R9. `web/src/components/Hud.tsx:604-616` — R8 (só consome).
- `supabase/migrations/` — nenhuma mudança de schema (status `failed` já existe); se D-A escolher `abandoned`, enum nova.

### Contrato (R2) — corpo de erro 409

```json
{"detail": "Esta ação pendente não pode mais ser retomada.", "code": "operation_conflict", "operation_id": "…", "discardable": true}
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
Python: `tests/test_bug_api_pending_erros.py` — `test_failed_operation_reclaim_after_version_bump` (R1),
`test_equip_with_failed_pending_409` (R3), `test_chronicle_export_unicode_name` (R5), `test_abyss_tier_hidden_zero` (R8),
`test_backstory_null` (R9). Node: `web/tests/http.test.mjs` (R4), `web/tests/pending.test.mjs` (R2, R6),
`web/tests/typewriter.test.mjs` (R7). Playwright (opt-in, SPEC-172 harness): F17 "pending descartável".
### Etapa 1 — R1, R3 (servidor) · R2 (cliente) — revisão `Sol`
### Etapa 2 — R4, R5, R9 (erros/export)
### Etapa 3 — R6, R7, R8 (storage/typewriter/chip)
### Etapa 4 — `npm run build`, `npm test`, `npx tsc --noEmit`, `uv run pytest`; smoke Playwright 390/1440.

## 5. Critérios de aceite

- [ ] Testes de reprodução vermelhos → verdes (Python + Node); `web/tests/*` 100%; `tests/test_polish_sessao.py`,
      `test_hardening_sse*.py`, `test_turnos_duraveis*.py` verdes ou diff justificado.
- [ ] `uv run pytest` verde; `npm run build` e `npx tsc --noEmit` limpos.
- [ ] Playwright: após 409 de pending, o jogador consegue enviar nova ação sem limpar storage.
- [ ] Guard de FallbackLLM: não se aplica.

## 6. Smoke test com LLM real

1. Provocar falha de turno (desligar rede no meio do SSE) → equipar item → reenviar → turno conclui (sem 409 eterno).
2. Criar personagem com classe inválida via devtools → banner legível.
3. Herói "Дмитрий" → exportar crônica → download OK.

## 7. Riscos & compatibilidade

- R1 relaxa o contrato "idempotency key reutilizada com operação divergente" apenas para `failed` (nunca para
  `completed`/`running`): documentar em `docs/spec111`-equivalente; revisão `Sol` obrigatória.
- R6 muda a garantia "reload mantém identidade" para "quando o storage existe"; o aviso único cobre o caso degradado.
- Chip do Abismo (R8): o Médico deixa de ver o chip até acumular Carga — coerente com a regra de Recidiva oculta.

## 8. Pontos de decisão do dono

- **D-A (equip/levelup com op `failed`):** 409 `pending_operation` (default, explícito) ou marcar `abandoned` e seguir.
- **D-B (descartar pendente):** botão sempre visível com pending (default) ou só após erro.

## 9. Evidência requerida

- Saídas de `uv run pytest`, `npm test`, `npx tsc --noEmit`, `npm run build`; testes antes/depois.
- `docs/<spec>/README.md` com a repro do 422/export, screenshot do botão "Descartar" em 390/1440 e revisão `Sol`.
- Handoff opcional: F17 no harness de frontend evals (SPEC-172) — autoria separada.
