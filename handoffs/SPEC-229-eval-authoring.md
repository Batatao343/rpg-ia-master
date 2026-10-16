# SPEC-229 — handoff de autoria de eval (EVAL_AUTHORING_REQUIRED)

Adicionar ao dataset de routing (SPEC-169) como variantes metamórficas, com relock de hash por quem não implementou:
- NPC: "Pergunto ao viajante sobre a estrada"; LOOT: "Compro uma barraca de acampar"; COMBAT: "Ataco o acampamento dos bandidos", "Vou para cima do goblin e ataco"; STORY: "Descanso aqui", "Viajo para Skallgard".
- travel_neg (não são viagem): ver `tests/data/intent_corpus.json`.
Nota: `evals/experiments/jev_target_loot.py` (SPEC-179) tinha `target.missing_id` ("Falo com a viajante") dependente do bug; o teste correspondente fixa o gate antigo via fixture.
