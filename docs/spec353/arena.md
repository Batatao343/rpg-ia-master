# SPEC-353 Etapa 8 - arena de não-regressão por Postura

Avaliador congelado da SPEC-341 (`docs/spec341/arena_spec341.py posturas --seeds 20:100`), níveis 1/3/5,
`padrao` + `elite`, máquina em série. Base: `docs/spec346/arena-base.json`. Depois: `arena-depois.json`.

| Postura | Base | Depois (final) | Δ |
|---|---|---|---|
| Devoto do Abismo | 61,2 % | 61,2 % | 0,0 pp |
| Sangromante | 62,2 % | 62,2 % | 0,0 pp |
| Corruptor | 46,3 % | 46,3 % | 0,0 pp |
| Arcanista Cinzento | 45,8 % | 45,8 % | 0,0 pp |
| Médico de Campo | 54,6 % | 54,6 % | 0,0 pp |

As células por nível/tipo são idênticas ao `arena-base.json` (o motor não mudou; R1/R38a não aparecem na arena).

**D6 (utilitárias fora da compra) testado e revertido.** Primeira rodada com D6: Devoto +0,6, Sangromante +1,2,
Corruptor +0,7, Arcanista −1,3, **Médico de Campo +2,7 pp** (54,6 → 57,3 %, fora de ±2 pp). Médico sozinho com D6
desligado = 54,6 % (`arena-medico-sem-d6.json`). Regra do coordenador: reverter só o D6. Recomendação: spec própria
que tire utilitárias da compra e recalibre o Médico.
