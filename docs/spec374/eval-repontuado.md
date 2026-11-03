# SPEC-374 — eval da 361 re-pontuado

Re-pontuação sem LLM (SPEC-374 R4/R5) dos registros gravados: `idioma_pt` sem "a"/"as" nas stopwords inglesas e latência renomeada para o job (`latencia_job_p95_ms <= 30000`). Os JSON originais não foram reescritos.

- `eval-antes-2026-11-02.json`: modo=antes · real=True · mock=False · rodada=— · commit=`—` · pedidos=`baf383100546`
- `eval-depois-2026-11-02.json`: modo=depois · real=True · mock=False · rodada=— · commit=`—` · pedidos=`baf383100546`
- `eval-depois-2026-11-02b.json`: modo=depois · real=True · mock=False · rodada=— · commit=`—` · pedidos=`baf383100546`
- `eval-depois-2026-11-02c.json`: modo=depois · real=True · mock=False · rodada=— · commit=`—` · pedidos=`baf383100546`

| métrica | limiar | eval-antes-2026-11-02.json | eval-depois-2026-11-02.json | eval-depois-2026-11-02b.json | eval-depois-2026-11-02c.json |
|---|---|---|---|---|---|
| lint_primeira | >= 0.7 | — | 0.6364 **✗** | 0.4545 **✗** | 0.5455 **✗** |
| lint_final | >= 0.9 | — | 1.0 | 0.8182 **✗** | 1.0 |
| fallback | <= 0.1 | — | 0.0 | 0.1818 **✗** | 0.0 |
| caminho_ok | >= 1.0 | — | 1.0 | 1.0 | 1.0 |
| proibidos | <= 0 | 0 | 0 | 0 | 0 |
| digitos | <= 0 | 0 | 0 | 0 | 0 |
| idioma_pt | >= 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| fisico | >= 0.95 | 0.9167 | 1.0 | 1.0 | 1.0 |
| campos_349 | >= 1.0 | 0.0 | 1.0 | 1.0 | 1.0 |
| vizinho_max | < 0.45 | 0.0833 (herdado) | 0.1286 (herdado) | 0.1268 (herdado) | 0.1443 (herdado) |
| latencia_job_p95_ms | <= 30000 | 7680 | 11936 | 12564 | 19068 |
| latencia_variante_p95_ms | <= 50 | 0.0 | 6.0 | 11.0 | 20.0 |
| prompt_chars | <= 14000 | 0 | 13401 | 13401 | 13923 |
| n_nova | — | 11 | 11 | 11 | 11 |
| n_gerados | — | 12 | 11 | 9 | 11 |
| lint_primeira_n | — | — | 7 | 5 | 6 |
| variante_vs_nova | — | — | {'variante': 1, 'nova': 0} | {'variante': 1, 'nova': 0} | {'variante': 1, 'nova': 0} |
| latencia_nova_p50_ms | — | 5658 | 7654 | 7552 | 8568 |

Denominadores: `lint_primeira`/`lint_final`/`fallback` sobre as `forcar: nova` (`n_nova`); `fisico`/`campos_349`/`vizinho_max` só sobre as fichas escritas pelo gerador (`n_gerados`: as `nova` que caíram em fallback e as variantes ficam fora); `idioma_pt`/`proibidos`/`digitos` sobre todos os textos gravados; `caminho_ok` sobre as `auto` (`n_auto`).

## O que mudou na re-pontuação

| arquivo | métrica | original | re-pontuado |
|---|---|---|---|
| `eval-antes-2026-11-02.json` | latencia_job_p95_ms | — | 7680 |
| `eval-antes-2026-11-02.json` | latencia_nova_p95_ms | 7680 | — |
| `eval-antes-2026-11-02.json` | n_gerados | — | 12 |
| `eval-depois-2026-11-02.json` | idioma_pt | 0.9932 | 1.0 |
| `eval-depois-2026-11-02.json` | latencia_job_p95_ms | — | 11936 |
| `eval-depois-2026-11-02.json` | latencia_nova_p95_ms | 11936 | — |
| `eval-depois-2026-11-02.json` | lint_primeira_n | — | 7 |
| `eval-depois-2026-11-02.json` | n_gerados | — | 11 |
| `eval-depois-2026-11-02b.json` | latencia_job_p95_ms | — | 12564 |
| `eval-depois-2026-11-02b.json` | latencia_nova_p95_ms | 12564 | — |
| `eval-depois-2026-11-02b.json` | lint_primeira_n | — | 5 |
| `eval-depois-2026-11-02b.json` | n_gerados | — | 9 |
| `eval-depois-2026-11-02c.json` | idioma_pt | 0.9932 | 1.0 |
| `eval-depois-2026-11-02c.json` | latencia_job_p95_ms | — | 19068 |
| `eval-depois-2026-11-02c.json` | latencia_nova_p95_ms | 19068 | — |
| `eval-depois-2026-11-02c.json` | lint_primeira_n | — | 6 |
| `eval-depois-2026-11-02c.json` | n_gerados | — | 11 |
