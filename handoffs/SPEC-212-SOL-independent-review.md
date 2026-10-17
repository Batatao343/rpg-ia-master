# SPEC-212 — revisão Sol independente

- Revisor: Sol (≡ Opus 5.5, contexto separado; não escreveu a spec nem a implementação).
- Escopo: `4b4ffad` (Etapa 0), `92964fd` (produto), `b435436`/`0666576` (follow-ups de autoria da jornada).
- Veredito: **APPROVED**. Todos os critérios do §5 foram atendidos; D-212-5 vale só para o convite de testers.

## Verificação

| Item | Resultado |
|---|---|
| Gate `--strict` | `docs/spec212/evidence/gameplay-gate-0666576fc421.json`: `ok: true`, `dirty_files: 0`, `strict: true`, SHA `0666576fc421…` (evidência commitada em `9628f46`; o SHA avaliado é o commit anterior à evidência, padrão documentado) |
| F01–F40 | 36/36 por viewport (1440x900, 1280x800) |
| J-V1 | V01–V09 18/18; oráculos console/turnos/segredo/latência/a11y/XP-speaker-roster-gesture `pass`; known-issues sem bloqueador |
| Latência (baseline, sem meta, n<20) | 1440: TTFMC p50/p95 445/564 ms, TTLT 452/568 ms (10 turnos) · 1280: 351/461, 359/467 ms (9 turnos) |
| Governança de eval | `evals.core.governance check` válido (11 datasets) |
| Suítes | ver relatório final (pytest, `npm test` 119/119, build, `validate_content` 0/0, ruff) |

## Solidez dos oráculos

O dataset `gameplay_gate.jsonl` tem casos negativos em todos os 9 oráculos. Fiz 3 mutações no evaluator e as 3 foram pegas por
`tests/test_eval_gameplay_gate.py` (corpus + oráculo cego/paranoico): (1) remover `duplicate:replay_new_turn`;
(2) tirar `\d+\s*xp` de `_XP_IN_PROSE`; (3) allowlist que aceita tudo. Depois reverti as 3.

## Pontos revisados

- **Allowlist do beacon** (`/telemetry/client-latency net::ERR_ABORTED$`): justificada. É telemetria fire-and-forget,
  desligada por padrão e abortada pelo reload da jornada. A regex é estreita e `gg.console.allowlist_is_narrow` prova que
  `/game/action*` nunca é tolerado. O comentário que citava `keepalive` foi corrigido em `0666576`.
- **`rpg.turn` hold/release no SSE:** nenhuma linha se perde. `release_log` roda no `finally`, inclusive na desconexão,
  e o worker que termina depois dele emite direto. Não há crescimento de memória: no máximo 1 closure pendente por turno.
  **Corrigido:** uma exceção na linha adiada pulava `turn_delivery`/publicação da timeline. Agora é capturada e logada
  (teste `test_held_rpg_turn_line_failure_never_breaks_delivery_bookkeeping`).
- **Desfecho antes do nível:** o chip "⬆ Nível!" e a aba Personagem abrem o modal na hora e dispensam o painel. Foco e Esc
  passam pelo `LevelUpModal` existente. Teste Node cobre a sequência. Observação não bloqueante: se o painel de desfecho
  não estiver visível (modo chat), o modal espera até o próximo turno, quando `combat_result` se esvazia; o chip segue
  disponível.
- **Known issues:** KI-1 (dado sem seed; jornada adaptativa) e KI-2 (aliado fora do manifesto; contrato da SPEC-203 é de
  `enemies`) estão bem classificados como P3. Não há bloqueador oculto. KI-9/10/11 estão fechados com evidência.
- **D-212-5:** correta. O gate é local e não convida testers; o convite exige SPEC-218/219 `done`.

## Correções do revisor (`2f3aacb`, com testes)

1. `check_known_issues` fail-closed: só `fechado` fecha (status ambíguo conta como aberto).
2. `clear_previous()`: relatórios e traces da execução anterior são apagados antes de rodar. Sem isso, uma falha do
   Playwright reaproveitava o JSON antigo e certificava o SHA errado.
3. `--reuse` nunca certifica (`fresh_run=not_provisioned`, reprova em `--strict`).
4. `TurnTimeline.release_log` à prova de exceção.

## Corrida de V01 (achado da 1ª execução do gate, `2f3aacb8badf`)

O produto monta o composer enquanto `/game/new` está em voo, e a jornada lia `/game/saves` cedo demais. Isso falhou em
1280 sob carga. A correção de autoria em `0666576` espera o POST e o composer habilitado, sem afrouxar nenhum oráculo.
Registro: `handoffs/SPEC-212-review-eval-followup.md`.

## Publicação

A régua mudou (J-V1, dataset `gameplay_gate`, evaluator, registry/lock, `critical-journeys.yaml`). Publicar exige
aprovação do environment `eval-governance`.
