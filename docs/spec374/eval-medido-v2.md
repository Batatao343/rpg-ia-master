# SPEC-374 — rodadas medidas (protocolo R6)

- `eval-medido-v2-1.json`: modo=depois · real=True · mock=False · rodada=1 · commit=`7828e73be680` · pedidos=`baf383100546`
- `eval-medido-v2-2.json`: modo=depois · real=True · mock=False · rodada=2 · commit=`7828e73be680` · pedidos=`baf383100546`

| métrica | limiar | eval-medido-v2-1.json | eval-medido-v2-2.json |
|---|---|---|---|
| lint_primeira | >= 0.7 | 0.6364 **✗** | 0.8182 |
| lint_final | >= 0.9 | 0.9091 | 1.0 |
| fallback | <= 0.1 | 0.0909 | 0.0 |
| caminho_ok | >= 1.0 | 1.0 | 1.0 |
| proibidos | <= 0 | 0 | 0 |
| digitos | <= 0 | 0 | 0 |
| idioma_pt | >= 1.0 | 1.0 | 1.0 |
| fisico | >= 0.95 | 1.0 | 1.0 |
| campos_349 | >= 1.0 | 1.0 | 1.0 |
| vizinho_max | < 0.45 | 0.163 | 0.1667 |
| latencia_job_p95_ms | <= 30000 | 19358 | 18710 |
| latencia_variante_p95_ms | <= 50 | 6.0 | 8.0 |
| prompt_chars | <= 14000 | 13915 | 13915 |
| n_nova | — | 11 | 11 |
| n_gerados | — | 10 | 11 |
| lint_primeira_n | — | 7 | 9 |
| variante_vs_nova | — | {'variante': 1, 'nova': 0} | {'variante': 1, 'nova': 0} |
| latencia_nova_p50_ms | — | 6840 | 6747 |

Denominadores: `lint_primeira`/`lint_final`/`fallback` sobre as `forcar: nova` (`n_nova`); `fisico`/`campos_349`/`vizinho_max` só sobre as fichas escritas pelo gerador (`n_gerados`: as `nova` que caíram em fallback e as variantes ficam fora); `idioma_pt`/`proibidos`/`digitos` sobre todos os textos gravados; `caminho_ok` sobre as `auto` (`n_auto`).

## Veredito

- passou: **True**
- lint_primeira agregado: 16/22 (>= 0,70) · piso por rodada (>= 7/11): [True, True]
- validade: {'n_rodadas': True, 'real_sem_mock': True, 'mesmo_commit': True, 'set_361': True}
