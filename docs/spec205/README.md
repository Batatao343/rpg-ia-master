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
- Jornadas F novas: ver `handoffs/SPEC-205-eval-authoring.md`. Revisao Sol independente: pendente.
