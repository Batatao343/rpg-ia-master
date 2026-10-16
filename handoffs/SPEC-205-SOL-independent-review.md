# SPEC-205 — revisão Sol independente

- **Data:** 2026-10-16 · **Revisor:** Sol (Opus, contexto separado) · **Base:** `main` f98b12e + WT `spec-205`
- **Veredito:** **APPROVED_WITH_FIXES** — dois defeitos corrigidos no próprio WT; spec segue `in-progress` só pelo gate das jornadas F novas (`handoffs/SPEC-205-eval-authoring.md`).

## Verificações

| Item | Resultado |
|---|---|
| Paridade `valid_targets` × `_invalid_target_reason` (SPEC-232) | Varredura das **185 Cartas ativas** × 4 cenários (normal, inimigo morto, aliado de party, inimigo oculto) × todos os atores: **3.145 pares, 0 alvo anunciado recusado pelo motor, 0 alvo aceito pelo motor e fora da lista**. Nenhum `efeito.kind` fora de `_ATTACK_EFFECTS ∪ _SUPPORT_EFFECTS`. |
| 409 sem custo | `_apply_action_options` levanta antes de declarar; `test_invalid_target_rejected_without_spending` compara o estado inteiro. Economia (Entropia/frequência) segue com o motor, que não cobra com alvo inválido. |
| Idempotência | 409 ocorre antes do save; o cliente descarta o pendente (`shouldClearPending`) e o próximo gesto gera `action_id` novo. Em perfil hosted o claim é marcado `failed` (mesmo comportamento dos demais 409) e a SPEC-235 permite retomar a mesma chave. |
| Fallback sem `valid_targets` | Só cartas `target_kind: "enemy"` recebem `enemies[0]`; suporte vai sem `target_id` → servidor mira o jogador. Servidor também troca inimigo vindo da UI por jogador em Carta de suporte (R10). |
| Aliados/transitórios (231) e manifesto (203) | Ids = `enemy.id` (= `participant_id`) / `"player"` / id do aliado, iguais a `actors_by_id` do motor. |
| Duplo clique | `useTargeting.begin/beginDirect` trava por ref até a borda de descida de `busy`; coberto no Playwright. |
| Reação em 1 clique | Só seleciona `reaction_card_id` (toggle `aria-pressed`); não envia ação. |
| A11y | `aria-live="polite"` em `<p>` sempre montado, sem `role="status"`; foco volta ao gatilho no cancelamento; setas entre alvos. |
| 390 px / Axe | Playwright `combat-gesture` @390/@1440 verde, sem overflow, Axe sem serious/critical. |
| Dado oculto | `valid_targets` exclui inimigo oculto; o chip usa só `enemy_views` públicos (`revealed_cards`/`revealed_resistances`). |

## Defeitos corrigidos no WT

1. **409 `invalid_target` não refazia a mira** (`web/src/App.tsx`): no caminho SSE/POST, `shouldClearPending(409, "invalid_target")` relançava um `Error` simples e o catch externo, que testa `HttpError && code === "invalid_target"`, nunca buscava o estado novo. Agora relança `HttpError` preservando status/code.
2. **Divergência de aliados transitórios** (`services/combat_targeting.py`): com `combat.scene_allies == []` o motor recalcula (`or`) e o targeting não, o que levaria a 409 em alvo aceito pelo motor. Alinhado ao motor + teste `test_empty_scene_allies_recomputed_like_engine`.

## Observações (sem bloqueio)
- `legacyBasics` (servidor antigo) lista inimigos mortos como alvo; só afeta cliente novo contra servidor antigo.
- `out_of_zone` reservado e nunca emitido; `cooldown` = silêncio. Documentado na spec.

## Evidência
`npm test` 91/91; `npm run build` ok; Playwright combat-gesture + critical-journeys + combat-outcome + workspace-shell + pending-discard: **51 passed**; `tests/test_combat_targeting.py` 20 passed; ruff ok; suíte Python completa (`pytest -q --ignore=tests/test_project_index.py`, sem pipe): **exit 0**.
