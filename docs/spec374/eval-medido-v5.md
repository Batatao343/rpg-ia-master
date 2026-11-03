# SPEC-374 — rodadas medidas (protocolo R6)

- `eval-medido-v5-1.json`: modo=depois · real=True · mock=False · rodada=1 · commit=`a3ee74f87574` · pedidos=`baf383100546`
- `eval-medido-v5-2.json`: modo=depois · real=True · mock=False · rodada=2 · commit=`a3ee74f87574` · pedidos=`baf383100546`

| métrica | limiar | eval-medido-v5-1.json | eval-medido-v5-2.json |
|---|---|---|---|
| lint_primeira | >= 0.7 | 0.5455 **✗** | 0.5455 **✗** |
| lint_final | >= 0.9 | 1.0 | 1.0 |
| fallback | <= 0.1 | 0.0 | 0.0 |
| caminho_ok | >= 1.0 | 1.0 | 1.0 |
| proibidos | <= 0 | 0 | 0 |
| digitos | <= 0 | 0 | 0 |
| idioma_pt | >= 1.0 | 1.0 | 1.0 |
| fisico | >= 0.95 | 1.0 | 1.0 |
| campos_349 | >= 1.0 | 1.0 | 1.0 |
| vizinho_max | < 0.45 | 0.1474 | 0.1429 |
| latencia_job_p95_ms | <= 30000 | 9648 | 11924 |
| latencia_variante_p95_ms | <= 50 | 5.0 | 5.0 |
| prompt_chars | <= 14000 | 13927 | 13927 |
| n_nova | — | 11 | 11 |
| n_gerados | — | 11 | 11 |
| lint_primeira_n | — | 6 | 6 |
| variante_vs_nova | — | {'variante': 1, 'nova': 0} | {'variante': 1, 'nova': 0} |
| latencia_nova_p50_ms | — | 6994 | 7273 |

Denominadores: `lint_primeira`/`lint_final`/`fallback` sobre as `forcar: nova` (`n_nova`); `fisico`/`campos_349`/`vizinho_max` só sobre as fichas escritas pelo gerador (`n_gerados`: as `nova` que caíram em fallback e as variantes ficam fora); `idioma_pt`/`proibidos`/`digitos` sobre todos os textos gravados; `caminho_ok` sobre as `auto` (`n_auto`).

## Veredito

- passou: **False**
- lint_primeira agregado: 12/22 (>= 0,70) · piso por rodada (>= 7/11): [False, False]
- validade: {'n_rodadas': True, 'real_sem_mock': True, 'mesmo_commit': True, 'set_361': True}
