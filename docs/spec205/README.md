# SPEC-205 — Combate por gesto: carta, mira e alvo direto

Evidencia curta. Status e criterios: `specs/SPEC-205-combate-gesto-alvo-direto.md`.

## O que mudou
- `services/combat_targeting.py` (puro, sem LLM): `valid_targets` + `invalid_reason` (enum fechado) por Carta e `basic_actions`
  (ataque, manobras, passar, fugir); `check_declared_target` para a borda.
- `api.py`: `combat.cards[].valid_targets/invalid_reason` e `combat.basic_actions` (aditivos); `_apply_action_options` rejeita alvo
  explicito invalido com HTTP 409 `{code: "invalid_target", invalid_reason, message}` antes de qualquer custo e normaliza Carta de
  suporte (inimigo vindo da UI -> jogador). `ActionRequest` nao mudou; sem mudanca de schema de save.
- Frontend: `web/src/combat/{targeting,useTargeting,Arena,TargetChip,CardTooltip}`, `CardHand` (a carta e o gesto), `ReactionPrompt`
  em um clique, `CombateTab` (arena, barra de mira, ataque basico no jogo real, teclado, Esc/clique fora, atalhos 1-9).
  Erro `invalid_target` (POST e SSE) recarrega o estado e refaz a mira.

## Decisoes de dono (defaults da spec)
P1 ataque basico com 1 alvo executa direto; P2 atalhos 1-9 ativos (ignorados ao digitar); P3 nenhuma confirmacao;
P4 suporte mira o heroi e aliados presentes (lista vem do servidor).

## Reproducao H/R12
`test_support_card_from_ui_targets_player` passou ja na entrada (corrigido antes pela SPEC-232); mantido como regressao,
agora tambem cobrindo "inimigo enviado pela UI para Carta de suporte".

## Limites
- `out_of_zone` e reservado (a cena nao impoe alcance a Cartas); `cooldown` = bloqueio temporario por silencio.
- Metricas de cliques/tempo: roteiro Playwright determinista usa 2 cliques (carta com alvo) e 1 (sem alvo/ataque com 1 alvo), 0 cliques falhos.
- Revisao Sol independente: APPROVED_WITH_FIXES (`handoffs/SPEC-205-SOL-independent-review.md`).

## Jornadas F (autoria de eval separada, 2026-10-16)
- `web/e2e/critical-journeys.{yaml,spec.ts}`: F20 `combat_gesture_target` (2 gestos, duplo clique = 1 request, HP so apos a
  resposta SSE atrasada, sem sobreposicao mao/acoes/alvos em 1440x900 split), F21 `combat_gesture_direct` (carta de suporte e
  ataque basico com 1 alvo em 1 clique, sem `target_id` no suporte; 320/390/768/1440 sem overflow), F22 `combat_gesture_cancel`
  (Esc, clique fora, re-clique, troca de origem, "Cancelar (Esc)", carta indisponivel com motivo; zero request), F23
  `combat_gesture_keyboard` (Enter/setas/Esc/atalho 1; atalho ignorado no composer), F24 `combat_invalid_target_reaim`
  (409 `invalid_target` via SSE: motivo visivel, estado novo, zero turno/Entropia/historico/pendente; nova mira so com alvo vivo,
  novo `action_id`). Todas com guards console/pageerror/5xx/requestfailed e Axe serious/critical.
- F08 adaptada: a fixture agora expoe `valid_targets` (`backend.armCombat`), entao a carta exige o 2o gesto (clicar o alvo);
  oraculos mantidos e reforcados (1 request com `card_id`/`target_id`/`reaction_card_id`).
- Fixture deterministica: `armCombat`, `combatHits` (dano -4 no alvo declarado, opt-in) e `staleTargets` (409 `invalid_target`
  como o `api.py` real: evento SSE `error`). Comportamento default inalterado para as demais specs.
- `scripts/frontend_eval_report.py` reconhece F01-F24 (`JOURNEY_COUNT = 24`); evaluator 1.8.0 -> 1.9.0; lock refeito por
  `python -m evals.core.governance lock`; `governance check` verde.
- Publicar exige aprovacao do environment `eval-governance` (regua/manifest protegidos).
