# SPEC-207 — evidência (export de sessão para auditoria beta)

## O que mudou
- `services/audit_trace.py` — ring buffer `audit_trace` (default 200, `RPG_AUDIT_TRACE_MAX`) gravado
  por `record_turn_trace` na finalização do turno (`api._record_audit_trace`, dentro da fase de
  persistência, antes do commit): `context_refs` (só ids/seção/visibilidade + selo SPEC-206 derivado
  do rótulo estrutural do ledger), delta da projeção fechada, erros por enum fechado, snapshot da
  `TurnTimeline` SPEC-200 com os nomes dela (`phase_ms.persistence = null`, `timing_partial`),
  `revealed_secret_ids` via `accepted_secret_ids` + `reveal_criteria_diverge`. Uma linha por
  `action_id` (replay não duplica). Campo **aditivo** com default `[]` no load — sem bump de
  `SCHEMA_VERSION` (segue 8).
- `services/context_builder.py` — `ContextPack.context_refs`; `build_context_pack` anexa ao
  coletor do turno (contexto de `planning` vira `visibility: "engine"`).
- `services/audit_redaction.py` — allowlist por arquivo + scrubber (e-mail, telefone, IP, UUID,
  token/JWT/chave, URL assinada/credenciais) + valores reais do dono; `scan_pii`.
- `services/audit_export.py` — builder puro, ZIP determinístico (ordem/`date_time` fixos), limites
  500 turnos / 25 MiB com truncagem marcada, scan final fail-closed, `verify_audit_zip`.
- `infrastructure/audit_source.py` — leitura owner-scoped (`app.games` via `store.get`, `app.turns`,
  soma de `app.usage_events` por operação, `app.game_events`, operações falhas); conta em exclusão → 401.
- `api.py` — `POST /game/{game_id}/audit-export`: legacy → 404 `audit_export_unavailable_in_legacy`;
  prova recente (`_require_recent`) → 403; rate limit 3/10 min por dono → 429; alheio = inexistente
  (404 idêntico); falha de redaction → 500 `audit_export_redaction_failed`. CSRF pelo middleware.
- `scripts/export_game_audit.py` — CLI de operador (Postgres com `--owner` ou `--save` local).
- `docs/auditoria/{AUDITOR_PROMPT,README_SCHEMA}.md` (cópia byte-idêntica em `data/auditoria/`,
  porque `docs/` não vai ao bundle Vercel; teste garante igualdade).
- Web: botão “⇩” por campanha na tela de saves (só com conta), modal com aviso de spoilers,
  reauth sob demanda (`web/src/lib/auditExport.ts`).
- Handoff legal: `handoffs/SPEC-207-legal-consent-handoff.md` (SPEC-197 intocada).

## Testes
- `tests/test_audit_redaction.py` (6), `tests/test_audit_export.py` (23, inclui turnos reais
  MockLLM, legacy 404 e CLI), `tests/test_audit_export_local.py` (7, Postgres local real com
  ROLLBACK: dono exporta, cross-account 404 com corpo idêntico, 403 sem prova, CSRF, conta excluída
  401, 429, soma de `usage_events` e zero `usage_events` novos).
- `web/tests/auditExport.test.mjs` (4): botão → 403 → reauth → download; cancelado; mensagens.
- Suíte offline completa: **2918 passed, 175 skipped, 15 deselected**, exit 0. `npm test` 62/62,
  `npm run build` verde, Ruff verde nos arquivos tocados.

## Evidência (`docs/spec207/evidence/`)
- `fixture-audit-export.zip` — campanha MockLLM (sem dado real); `verify_audit_zip == []`.
- `pii-scan-report.json` — achados por arquivo (todos vazios) + valores plantados ausentes.
- `two-user-smoke-local.json` — Supabase local: A 200 (verify `[]`), A sem prova 403,
  B→jogo de A 404 = B→uuid inexistente 404 (corpo idêntico).

## Decisões / desvios
- Defaults D4/D-a/D-b/D-c adotados (segredos só rotulados no `final_snapshot.private_reference` e
  nos itens não públicos; sem prompt/resposta bruta; ring 200; limites 500/25 MiB; nada retido).
- Sem bump de schema (regra da onda): a “migração v9” da spec virou campo aditivo com default.
- Teste Postgres em `tests/test_audit_export_local.py` (padrão `*_local.py` do repo), não em
  `tests/integration/`.
- `initial_snapshot` é derivado revertendo os deltas dos turnos exportados sobre a projeção final
  (não há snapshot inicial persistido); documentado no README_SCHEMA.
- `node` dos erros de LLM sai `null` (a tentativa só conhece o `tier`); `error_class` só para
  `turn_failed` (nome de classe validado por regex).
- Teste de UI é Node (fluxo puro com API mock), não Playwright.

## Limites / pendente
- Revisão Astra independente — APPROVED_WITH_FIXES (ver abaixo).
- Smoke em staging não executado (opcional/autorização); smoke de 2 usuários foi local.

## Revisão Astra (2026-10-16) — APPROVED_WITH_FIXES
Parecer: `handoffs/SPEC-207-ASTRA-independent-review.md`. Corrigido no WT: scrubber/scan ampliados
(CPF/CNPJ, celular cru, cartão, IPv6 comprimido, AWS/GitHub/Slack, `senha:`/`cookie=`/`api_key=`);
`audit_trace` compactado (refs agrupadas + delta de ids entre turnos; ring de 200 turnos reais ≈ 208 KB, antes ≈ 4 MB); IPv4 com ponto final; ZIP de evidência e `pii-scan-report.json` regenerados (valores plantados: e-mail, telefone, CPF, celular cru, AKIA, senha, IP, game_id — todos ausentes); `game_id` cru tratado
como valor sensível; prova recente expirada coberta no teste Postgres local.
