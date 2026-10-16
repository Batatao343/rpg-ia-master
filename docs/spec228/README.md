# SPEC-228 — evidência

Mudou: `has_checkpoint` valida o JSON (R1); "Continuar" sem checkpoint válido devolve 409 `no_restore_point` com `death_pending` preservado, nunca o estado morto saneado (R2/R3, `NoRestorePoint`, `strict`); checkpoint sintético marcado para save legado (R4); legacy grava checkpoint antes do save e só marca `last_checkpoint_turn` após gravar, falha vira `checkpoint_deferred` com nova tentativa no turno seguinte (R5); `will_restore_turn`/`will_lose_turns` vêm do arquivo real, `null` se desconhecido (R6/R10); `needs_replan` persiste (R7); `_game_lock(None)` trava pelo UUID do save mais recente e o stream resolve uma vez (R8); `IncompatibleSaveError` → 409 sem regravar, sem bump de schema (R9); mensagens via `messages_to_dict` com leitura do formato antigo (R11).

Testes: `tests/test_bug_morte_checkpoint.py` (23 casos, incluindo round-trip de schemas v0, v3..v8 e v99 recusado). Suíte completa verde.
Limites: sem smoke com LLM real; sem screenshot do modal em 409 (o banner mostra o detalhe); revisão Sol independente pendente.

## Smoke com grafo/LLM real (2026-10-16, coordenador)

API `legacy`, DeepSeek real, jogo novo em Nova Arcádia; morte forçada injetando `death_pending` + Vitalidade 0 no save:
1. Com checkpoint inicial: 1 turno real → morte → "Continuar" = 200, `death_pending=false`, inventário (11) e local
   iguais aos iniciais.
2. Sem checkpoint (`.checkpoint.json` apagado): "Continuar" = 409 `no_restore_point`, queda segue pendente;
   "Aceitar" = 200, `game_over=true`.
3. Replan pós-combate (`needs_replan` persistido) coberto pelos testes R7 offline.
Revisão Sol independente: APPROVED (follow-ups 1–6 aplicados).
