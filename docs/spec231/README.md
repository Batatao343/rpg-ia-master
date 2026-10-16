# SPEC-231 evidência

Mudanças: `_stabilizer_for` trata hero+ally como um lado; aliados usam categoria `companheiro` (`ensure_combat_sheet(is_ally=)`);
snapshot `combat.scene_allies` guarda fichas pós-rodada (mortos não voltam); `reset_terminal_episode` ao tratar Crítico
(`rest_treat_wounds`) e ao fim do conflito; carta `estabilizar` registra `scars_pending`.
Testes: `tests/test_bug_combate_morte_aliados.py` (7). Suíte completa verde. Revisão Sol independente: APPROVED_WITH_FOLLOWUPS (R8: Cicatriz da carta `estabilizar` agora chega ao resultado da rodada; alvo inválido usa o mesmo fallback). Coordenador: morte de aliado transitório grava `died_turn` (formato SPEC-230). Smoke real: mecânica Python determinística, coberta pelos testes R1–R9 + checagem de 3 rodadas com round-trip JSON; geração da Cicatriz mantém o guard de FallbackLLM.
