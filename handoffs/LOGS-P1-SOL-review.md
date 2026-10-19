# Revisão Sol independente — logging P1 (SPEC-242/243/247/248/249/250/254/255/257/262)

- **Revisor:** Sol (Claude Opus 5.5), independente — não escreveu as specs nem a implementação.
- **Data:** 2026-10-19. **Branch:** `logs-p1`, rebaseada em `main` `79951f7` (rebase limpo, sem conflito).
- **Commits revisados:** `8fadd75` (249), `b32e9ef` (242), `7a436bd` (243), `d3e1f0b` (247), `0862469` (248),
  `4b7a594` (250), `b655797` (254), `e65f3fb` (255), `b009275` (257), `985e35e` (262) + as 3 correções do executor
  `57f9315` (dedupe de fallback por turno), `94c6243` (erro original do fetch preservado p/ fallback SSE→POST),
  `96d659d` (PNGs de evidência da SPEC-209 restaurados — conferido: `git diff main -- docs/spec209` vazio).
- **Veredito:** **APPROVED** com as correções abaixo (aplicadas e testadas) + smoke staging verde.

## Defeitos encontrados e corrigidos (com testes)

1. **Código de suporte não era encontrável nos logs (bloqueante p/ SPEC-243/262).** A UI mostrava os 8 primeiros
   caracteres do `request_id`, mas a busca dos runtime logs da Vercel casa **token inteiro**: no staging,
   `--query 5c6525e9` → 0 registros; `--query 5c6525e92b49…` (inteiro) → 7. Correção: o cliente gera ids de
   **12 hex** (`newRequestId`) e o código de suporte é o `request_id` **inteiro** (curto quando vem do web; o id de
   32 hex do servidor também aparece inteiro, com quebra de linha). Testes Node + e2e atualizados.
2. **Runbook (dry-run em staging):** `--since 24h`/`--since 1h` são **recusados** no Hobby (`outside the available
   retention`) → `--since 55m`; busca por prefixo não funciona (nota adicionada); SQL de (g) usava
   `status='retry'` (não existe; estados reais `queued|running|succeeded|dead|cancelled`) e
   `cron_health_alerts.created_at` (a coluna é `detected_at`). Corrigidos e reexecutados (SQL só leitura).
   Acrescentado: na Vercel a desconexão do cliente **não chega à função** (ver smoke abaixo).
3. **`payments.fee_reconcile_failed`** gravava `str(exc.args[0])[:60]` sem filtro — agora passa pelo mesmo `_code`
   fechado (texto livre ⇒ `other`); teste com sentinela de cartão/e-mail.
4. **Catálogo de eventos (SPEC-262 R4) quebrou no rebase:** o scanner tratava qualquer dict com `"event"` +
   `"outcome"` como linha de log; o `events.append({"event": "conflict_stalemate_broken", ...})` da SPEC-275 (evento
   de jogo, não log) entrou e falhou `test_event_names_are_area_dot_event`. Agora só dicts passados a
   `safe_json(...)` ou `extra=` contam; catálogo regenerado (176 eventos, idêntico ao do executor).
5. **`test_cross_account_404` (`-m infra_local`)** comparava o corpo byte a byte; com o `request_id` por
   requisição (SPEC-241/242) nunca é igual. O teste agora compara tudo menos `request_id` (anti-enumeração mantida).
6. **Flakiness:** `test_worker_sse_persiste_mesmo_se_consumidor_fecha` tinha folga de 2 s para o worker persistir
   sob carga da suíte inteira (Windows/OneDrive) → 10 s (o laço sai assim que persiste).
   `test_campaign_planner_error_logs_template_used` agora ignora linhas de threads de turno de outros testes
   (só a chamada direta, sem `request_id`). 8 execuções seguidas dos 3 arquivos afetados: 8/8 verdes.

## Escopo verificado

| Tema | Resultado |
|---|---|
| PII/segredos em pagamentos | `payment_log` só usa códigos fechados (`_code`), `event_ref`/`order_ref` pseudonimizados, `product_id` por regex; nenhum `purchase_token`/`client_secret`/e-mail/cartão (sentinelas nos testes). Staging: webhook com `evt_SENTINELA_P1` ⇒ `payments.stripe_webhook outcome=disabled`, sentinela ausente. |
| LLM sem prompt | Verificação real local (DeepSeek com modelo inexistente via `RPG_ROUTES`): `llm.attempt outcome=invoke_error http_status=400 node=dm_router` → `groq … fell_back=true outcome=success`; texto do prompt (sentinela) ausente. `error_type` só identificador (regex), texto ⇒ `other`. |
| Rótulos de métrica | `rpg_payment_verifications_total{provider,outcome}` (outcome por `_code` ⇒ conjunto finito de códigos), `rpg_db_query_seconds{query_name}` só com 16 rótulos estáticos em decorators. OK. |
| Envelope de erro × clientes | `detail` preservado (web/Android leem `detail`; Android é o mesmo bundle no WebView); `code` + `request_id` aditivos. SSE mantém `code` numérico e acrescenta `error_code`/`request_id` (consumidor web atualizado). Staging: 401 `{"detail":"session_invalid","code":"session_invalid","request_id":…}`, 404 `not_found`, 422 `validation_failed`, todos com `X-Request-ID`. |
| Código de suporte (a11y) | `role="alert"` + botão “Copiar” com `aria-label`, `aria-live` polite ao copiar, alvo ≥ 28 px; `overflow-wrap:anywhere` (390 px). Follow-up: banner com código fecha em 15 s. |
| Jobs com trace | `_trace` = só `request_id` (cliente, validado `[A-Za-z0-9._:-]{8,64}`) + `action_ref` (pseudônimo); retirado do payload no lease; dedupe não compara payload; SQL que lê `payload->>` usa chaves específicas. Jobs antigos sem trace ok (teste). |
| Postgres (volume) | lease/versão/pool só em conflito/falha (warning/error); `slow_query` > 500 ms; nada por query em `info`. |
| SPEC-217 golden | `dm_router_node` não muda o payload (fonte vai por contextvar); golden `off` e diferencial verdes na suíte. No staging (Jev primary) `router.decision source=jev` nos turnos decididos pelo Jev, `interlocutor`/`story_regex` nos gates. |
| Linhas por turno | Local (MockLLM): POST 4, SSE 6. **Staging (DeepSeek + Jev primary): 5–7 linhas JSON por turno SSE (média ≈ 6,0)**, sob o limite de 256 linhas/requisição da Vercel. |
| `infra_local` | Supabase local (Docker Desktop iniciado): 158 coletados, 1 falha (#5, corrigida); demais verdes/skip. |

## Smoke staging (Vercel `rpg-ia-master-staging` + Supabase `uzeagzcyvxzrpjgrhaql`)

- Deploy `bd2c708` (`GIT_SHA` injetado; `/health` confere, `hardened=true`, `hosted-supabase`, `/openapi.json` 404),
  redeploy final com a correção #1 (sha no commit desta revisão). **Nenhum env var alterado** (Jev `primary` mantido).
- `e2e_session`: login, cookies, CSRF, novo jogo, 5 turnos SSE, retry com mesmo `action_id`, estado, logout,
  limpeza — **verde**. `sse_disconnect`: exatamente 1 turno — **verde**.
- Logs: `runtime.boot` por instância (`git_sha` 12, `llm_mode=routes`, `llm_providers_with_key` só nomes,
  `jev_mode=primary`, `embedding_provider=jina`, `region=gru1`), nenhum `runtime.config_warning`;
  `router.decision`, `sse.started`, `turn` com `route_source`, `operation.replayed` no retry, 401/404/422 forçados
  com `error_code` + `request_id`. Varredura: 0 e-mail, 0 IPv4, 0 UUID cru, 0 JWT, 0 texto de ação.
- **Limitação de plataforma:** na Vercel o cliente que fecha o SSE não interrompe a função — ela termina de
  transmitir e loga `turn_delivery outcome=ok`; `sse.client_disconnected` só aparece onde o servidor vê o
  fechamento (local/uvicorn, coberto por teste). Runbook atualizado.
- `log_ref.py owner <id> --stdin` com o segredo do staging reproduziu o `owner_ref` da linha `http.request`.
- Não exercitado no staging (cobertos offline/`infra_local`): 409/429 forçados, `db.lease_conflict` com 2 turnos
  concorrentes, job `project_archive` com trace (staging está em `inline`), falha real de provider (exigiria mexer
  em env var).

## Pendências / follow-ups (não bloqueiam)

- SPEC-262: **decisão de retenção/drain é do dono** — fica o default (só Vercel, sem drain), registrado como
  pendente de confirmação. Limites da Vercel agora verificados na doc oficial (Hobby 1 h; 256 KB/linha;
  256 linhas e 1 MB por requisição).
- `cold_start_ms` mede do import de `observability.boot` ao import do `api` (não ao 1º request como a spec diz).
- Banner com código de suporte some em 15 s (considerar persistir até fechar).
- `messageFor` mostra prosa em inglês do Starlette (`Not Found`) se ela chegar a um banner.
- ~87 `except` silenciosos seguem na allowlist congelada (só pode diminuir); combate fora por decisão do executor.

## Rollback

- Ruído/volume: `RPG_LOG_LEVEL=warning` (ou `RPG_LOG_LEVEL_<AREA>`) + redeploy.
- Regressão: `npx vercel@64.2.0 promote https://rpg-ia-master-staging-pyjmtedvr-guilherme-medeiros-projects.vercel.app`
  (deploy anterior, `358c628`).
