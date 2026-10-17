# SPEC-212 — follow-up de eval da revisão Sol (não bloqueante)

Revisão independente (Sol ≡ Opus). Nenhum arquivo de régua foi editado pelo revisor.

## Item 1 — comentário da allowlist contradiz KI-3 (cosmético)

`web/e2e/vertical-support.ts` (`VERTICAL_ALLOWLIST`) diz que o beacon de latência "é enviado com keepalive".
O cliente usa `fetch` comum (`web/src/api.ts` `sendClientLatency`, sem `keepalive`), como registra KI-3; o
`ERR_ABORTED` vem do beacon fire-and-forget abortado por `page.reload()`/navegação da jornada. A regex
(`/telemetry/client-latency net::ERR_ABORTED$`) está correta e estreita (o dataset `gg.console.allowlist_is_narrow`
prova que `/game/action*` nunca é tolerado). Sugestão: corrigir só o comentário na próxima autoria + relock.

## Item 2 — nenhum

Mutações aplicadas pelo revisor no evaluator (removendo `duplicate:replay_new_turn`, removendo `\d+\s*xp` do
`_XP_IN_PROSE`, allowlist que aceita tudo) foram todas pegas por `tests/test_eval_gameplay_gate.py`
(corpus + blind/paranoid oracle). Revertidas.
