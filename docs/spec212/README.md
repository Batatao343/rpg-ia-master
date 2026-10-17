# SPEC-212 — gate de gameplay do beta desktop

Contrato: [spec](../../specs/SPEC-212-beta-gameplay-gate-desktop.md). Autoria de eval (Etapa 0):
[handoff](../../handoffs/SPEC-212-etapa0.md). Defeito de autoria pendente:
[follow-up](../../handoffs/SPEC-212-etapa0-followup.md).

## O que mudou no produto (Etapas 1–5)

| Lacuna (handoff Etapa 0) | Resolução |
|---|---|
| `rpg.turn` de stream com `ttfmc/ttlt` nulos (R13) | `TurnTimeline.hold_log/submit_log/release_log`: o stream segura a linha até ttfmc/ttlt; `_stream_turn` libera ao fim (ou na desconexão). Teste: `test_stream_rpg_turn_line_carries_server_marks`. |
| Modal de nível cobrindo "Continuar" do desfecho | `PlayScreen` ordena: desfecho primeiro, modal de nível depois (`levelUpHeldByOutcome`); chip/atalho "Nível" abre na hora. Dispensa do desfecho elevada ao `PlayScreen`. Teste Node: `combat-outcome.test.mjs`. |
| Aliado fora do manifesto (R3) | Documentado: contrato SPEC-203 é de `enemies` (KI-2). |
| Dado sem seed (R5) | Documentado: spec §3.1 proíbe tocar a mecânica (KI-1). |
| Beacon `ERR_ABORTED` | Documentado: cliente não usa `keepalive` (KI-3); allowlist mantida. |

Novos: `services/gameplay_oracles.py` (mapa de nomes da spec → oráculos da régua; paridade testada),
`scripts/beta_gameplay_gate.py` (orquestrador + evidência), `tests/test_gameplay_oracles.py`,
`tests/test_beta_gameplay_gate.py`, `docs/spec212/{known-issues,handoff-spec197}.md`.

## Limites

- Evidência final (`gameplay-gate-<sha12>.json`) depende de commit + execução em árvore limpa (coordenador).
- V07 da J-V1 é flaky por defeito de autoria (follow-up); o gate acusa `known_issues_no_blockers` enquanto KI-11 estiver aberto.
- Sem provider real; sem mudança de schema de save.
