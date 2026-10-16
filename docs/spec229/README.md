# SPEC-229 — evidência

- `world_utils.is_travel_intent(text, world=None)`: verbo fechado + preposição (inclui ao/aos/à/pra/pro/rumo a/em direção a) + destino do mapa ou topônimo capitalizado. "Entro na taverna…", "Sigo em frente" deixam de ser recusados; "Vou ao Pântano da Melancolia" viaja.
- Router: hostilidade vence o atalho de história; atalho usa formas fechadas (`descanso|durmo|acampo|viajo|vou para|sigo para`).
- `services/chase.FLEE_RE`: formas fechadas; "recuperar/retirar/recusar" não são fuga.
- `validate_narrative_text`: sujeito-verbo na mesma oração (<=3 tokens, sem `.;,` entre).
- Telemetria `rpg.intent_guard` (kind/matched/text_hash).
- Testes: `tests/test_bug_intencao_parsers.py` + `tests/data/intent_corpus.json`; suíte completa verde; eval routing (`evals/datasets/regression/routing_actions.jsonl`) 21/21, exact_match 1.0.

## Smoke com LLM real (2026-10-16, coordenador)

API `legacy` + grafo real (DeepSeek), jogo novo em Nova Arcádia:
1. "Entro na taverna e peço uma bebida" → narração de cena (rota `npc_actor`), sem "Não há rota direta".
2. "Vou ao Anel Dourado" → local Nova Arcádia → Anel Dourado (deslocamento intra-cidade, mesmo período).
3. (combate) coberto offline por `FLEE_RE` — "recuperar" não dispara fuga.
4. "Pergunto ao viajante sobre a estrada" → rota `npc_actor`.
Ajuste do coordenador: atalho de história aceita infinitivos só com auxiliar ("quero/vou/vamos descansar") e a regex
de fuga cobre "fuja/fugindo/recuamos/nos retiramos/corro de volta"; testes parametrizados adicionados.
