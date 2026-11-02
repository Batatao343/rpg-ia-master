# SPEC-363 — arena de não-regressão (Etapa 8.2)

Comando: `bash scripts/dev/py.sh docs/spec341/arena_spec341.py posturas --seeds 20:100 --compare docs/spec353/arena-depois.json --out docs/spec363/arena-depois.json`
(níveis 1/3/5, Padrão e Elite, 80 sementes, em série). Dados: `docs/spec363/arena-depois.json`.

| Postura (todas as subs) | SPEC-353 (base) | SPEC-363 | Δ pp |
|---|---|---|---|
| Devoto do Abismo | 61,2 % | 60,4 % | −0,8 |
| Sangromante | 62,2 % | 60,4 % | −1,8 |
| Corruptor | 46,3 % | 46,0 % | −0,3 |
| Arcanista Cinzento | 45,8 % | 50,3 % | +4,5 |
| Médico de Campo | 54,6 % | 57,6 % | +3,0 |

**Leitura.** Devoto, Sangromante e Corruptor ficam dentro de ±2 pp. Arcanista e Médico saem da faixa, mas **não por esta
spec**: `git diff main --stat` sobre `data/`, `scripts/cards/`, `services/cards.py`, `card_effects.py`, `card_piles.py`,
`enemy_decks.py`, `conflict_orchestrator.py` e `conflict_turn.py` é vazio. A base `arena-depois.json` é da SPEC-353; depois
dela pousaram a SPEC-362 (pacote de balanço do Arcanista: `truque`, `pulso_medido`, +4,5 pp esperados) e as SPEC-355/357
(conteúdo/Médico). A comparação limpa para esta spec é `main` × branch, que dão o mesmo resultado por construção (nenhum
arquivo de motor ou de dados de Carta mudou). Sugestão ao coordenador: regravar a base como `docs/spec363/arena-depois.json`.
