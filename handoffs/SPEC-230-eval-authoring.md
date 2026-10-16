# SPEC-230 — handoff para o corpus narrative/NPC (SPEC-171)
Casos de regressão sugeridos (evals/ não foi editado):
1. NPC morto em cena: `npcs={"Grum": {status:"morto", in_scene:True}}`; "Falo com Grum" -> resposta "Grum está morto.", sem diálogo; `npcs_in_scene`/`npcs_for_context` vazios.
2. Companheiro `waiting_at` em outro local: "não está aqui" no local atual; fala normal em `waiting_at`.
3. Clamp de relação: `relationship_change=+5` aplica no máximo +1 por turno; relação 0 permanece 0 no gate de recrutamento.
4. `npc_killed` aceito: `npcs[...].status=="morto"` e membro removido da party.
