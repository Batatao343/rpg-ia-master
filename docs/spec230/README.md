# SPEC-230 — evidência
- Guard `isinstance(NPCSchema)` em `generate_new_npc`; fallback (`id=="fallback"`) nunca persiste.
- `npc_layers.npc_alive/apply_npc_death`; `event_processor` sincroniza `npcs`/`party` em `npc_killed` (incl. derivados do rule_engine).
- Party: membro esperando só fala no `waiting_at`; morto não fala. `party._relationship` (0 válido). Clamp ±1 + log `rpg.npc.relationship_clamped`.
- `npc_fallback_hint` zerado pelo router.
- Testes: `tests/test_bug_npc_ciclo_de_vida.py` (11), `tests/test_structured_output_guards.py` (varre agents/, services/, character_creator.py, api.py).
- Playtest offline npc_only/recrutador 40 turnos: 0 erros, 0 violações.
- Handoff SPEC-171: caso "NPC morto responde" deve virar regressão do corpus (não editado aqui).

- Varredura no load: `load_npc_db` descarta (log warning) entradas com role/persona vazios ou id "fallback"; testes em `test_bug_npc_ciclo_de_vida.py`.
- Handoff SPEC-171: `handoffs/SPEC-230-eval-authoring.md`.
- Smoke §6.1 offline (teste `test_smoke_invalid_structured_output_leaves_cache_clean`): LLM devolve AIMessage -> NPC "Desconhecido", arquivo de cache continua `{}`.
