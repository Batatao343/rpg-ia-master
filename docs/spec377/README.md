# SPEC-377 — evidências

- `arena-antes.json` / `arena-depois.json`: `arena_spec355.py base --seeds 0:20` antes e depois do R15 (rendido deixa de ser alvo de Carta). Resultado idêntico: Devoto 60,2 %, Sangromante 65,0 %, Corruptor 51,9 %, Arcanista 55,8 %, Médico 45,8 % (todos na faixa 45–85 %). O bot da arena não usa rendição.
- Matriz de facção (R20): fixada em `tests/test_faction_visibility.py` (6 facções: 2 públicas, 4 secretas).
- Item 2 (Fôlego) pendente: depende de publicar `lote-v2` via `/eval-publish` (dono).
