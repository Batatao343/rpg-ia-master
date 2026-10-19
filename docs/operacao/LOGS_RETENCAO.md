# Retenção, níveis e drain de logs (SPEC-262)

> **Decisão registrada com o DEFAULT da spec (não é decisão do dono):** ficar **só nos runtime logs da Vercel**,
> **sem log drain**, até o dono decidir diferente. Nenhum dado de log sai da Vercel enquanto isso — por isso a
> política de privacidade (SPEC-222 R8) não precisa de novo operador. Reverter/ativar o drain é uma spec própria
> (fora de escopo aqui) e **exige** atualizar a política de privacidade *antes* de enviar logs a terceiros.

## Limites da plataforma (verificados em 2026-10-19)

Fonte: <https://vercel.com/docs/logs/runtime> (página atualizada em 2026-08-28), consultada na revisão Sol de 2026-10-19.
O staging roda no plano **Hobby**.

| Item | Valor | Situação |
|---|---|---|
| Retenção dos runtime logs — Hobby | **1 hora** | verificado (2026-10-19) |
| Retenção — Pro / Enterprise | **1 dia** / **3 dias** (30 dias com Observability Plus) | verificado (2026-10-19) |
| Tamanho máximo por linha | **256 KB** | verificado; nossas linhas ficam bem abaixo de 2 KB (o `redact` corta strings em 2000 caracteres) |
| Linhas por requisição | **256 linhas** e **1 MB** somados por requisição; acima disso só as mais recentes ficam consultáveis | verificado; um turno SSE fica na ordem de dezenas de linhas no máximo |
| `vercel logs` (CLI) | default: últimas 100 entradas dos últimos 30 min; `--since` amplia; busca livre só em `message`/`requestPath` | verificado |

Consequência prática: **a evidência de um relato some rápido no Hobby.** Para auditoria de um turno específico use o
`audit-export` (SPEC-207, vive no banco) e as tabelas `app.operations`/`app.jobs`/`app.payment_orders`, que não dependem
da retenção de logs. Se a janela de investigação precisar passar de horas, a saída é o drain (decisão do dono).

## Volume por turno (referência)

- SPEC-239 (staging, DeepSeek + Jev primary): **3–7 linhas JSON por turno SSE (média ≈ 4,2)** em `info`.
- SPEC-247/248/250/254/255/257 acrescentam, em `info` por turno: `router.decision` (1) e `sse.started` (1) — e, só em falha,
  `llm.attempt` (warning), `*.fallback`, `db.*`, `operation.*`. `llm.attempt` de sucesso é `debug`. Expectativa: **≈ 6–9
  linhas/turno** em `info`. **A medir no staging** (critério de aceite: reportar a média real aqui).
- Ruído controlado: `GET` de polling/estáticos e `401` sem cookie em `debug`; fallbacks deduplicados por (ação, nó, motivo);
  `auth.rate_limited` amostrado 1/min por chave.

## Níveis por área

Default global: `RPG_LOG_LEVEL=info`. Por área: `RPG_LOG_LEVEL_<AREA>=debug|info|warning|error` (ex.:
`RPG_LOG_LEVEL_LLM=debug`). Mudança vale após redeploy (variável de ambiente).

| área (`rpg.<area>`) | nível default | o que sai nesse nível | quando subir para `debug` |
|---|---|---|---|
| `runtime` | info | `boot` (1×/processo), `config_warning`, `build_failed` | nunca necessário |
| `http` | info | 1 linha por requisição de API (`http.request`), 5xx em `error` | ver GET silenciados |
| `turn` / `sse` | info | `turn`, `turn_delivery`, `sse.*` | latência fina por fase |
| `router` | info | `router.decision` por turno | — |
| `llm` | warning | falhas por tentativa, `exhausted`, `mock_selected`; sucesso é `debug` | custo/latência por candidato |
| `db` | warning | conflitos de lease/versão, timeouts, `slow_query` (> `RPG_DB_SLOW_MS`, default 500 ms) | — |
| `operation` | warning/info | `rejected` (409), `replayed` (info), `release_failed` (error) | — |
| `job` | info | `completed`, `failed`, `dead`; `started` é `debug` | fila lenta |
| `payments` / `wallet` | info/warning | webhook/verificação por entrega, falhas de carteira | — |
| `auth` | warning | rejeições com motivo fechado | `debug` mostra 401 sem cookie |
| `*.fallback` | warning | degradação de nó do grafo | — |

## Quando reavaliar

- Média de linhas/turno > 12 ou custo de log relevante → subir `RPG_LOG_LEVEL_<AREA>` das áreas ruidosas para `warning`.
- Relatos com evidência já expirada → decisão do dono sobre o drain (destino, custo, operador na política de privacidade).
