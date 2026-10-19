# Área 04 — Injeção (SQL, path traversal, SSRF, deserialização, XSS, upload) — 2026-10-15

Arquivos inspecionados: infrastructure/{account_lifecycle,pgvector_memory,supabase_blob,supabase_identity,openai_images,local_adapters,file_blob,runtime}.py,
services/{speech_to_text,asset_pipeline,local_backup,game_transfer,account_security,stripe_checkout}.py, persistence.py, rag.py (storage paths),
api.py (rotas transcriptions, webhook, art, chronicle export, CSP, modelos Pydantic), web/src/lib.ts + componentes com dangerouslySetInnerHTML,
TurnstileChallenge.tsx, frontend/app.js, supabase/migrations (EXECUTE format), scripts/staging/*.py (grep).

## Achados

### INJ-01 — Content-Disposition do export da crônica usa `isalnum()` Unicode (500 com nome fora de latin-1)
- **Severidade:** baixa
- **Categoria:** Header injection / robustez
- **Local:** `api.py:3736-3738`
- **Evidência:** `hero = "".join(c for c in player.get("name","cronica") if c.isalnum()) ...; headers={"Content-Disposition": f'attachment; filename="cronica_{hero}.txt"'}`.
  `str.isalnum()` aceita letras Unicode (ex.: "Ω", CJK). Starlette codifica cabeçalhos em latin-1 -> `UnicodeEncodeError` -> HTTP 500. CR/LF e aspas são excluídos por `isalnum`, então NÃO há response splitting.
- **Cenário:** jogador cria personagem com nome "Ωmega" (CreateCharacterRequest só limita `max_length=80`) e chama `GET /game/chronicle/export` -> 500 (auto-DoS do próprio export). Todos os perfis.
- **Impacto:** export inutilizável para nomes não-latin-1; sem impacto de segurança entre usuários.
- **Correção sugerida:** `hero = re.sub(r"[^A-Za-z0-9]", "", unicodedata.normalize("NFKD", name))[:40] or "cronica"` ou `filename*=UTF-8''` + `urllib.parse.quote`. Teste novo nos testes de API do export.
- **Confiança:** provável (comportamento do Starlette; não executado)
- **Já coberto por spec?** SPEC-207 (export de sessão, draft) toca o export, mas não esse header.
- **Status:** válido

### INJ-02 — Sem limite global de tamanho de body JSON antes da validação Pydantic
- **Severidade:** baixa
- **Categoria:** DoS/custo
- **Local:** `api.py` (`ActionRequest` l.876, `CreateCharacterRequest` l.834, `AuthRequest` l.207: `max_length` só valida após o parse completo); só Stripe webhook (l.2163-2175) e STT (l.2208-2216) leem o stream com teto.
- **Evidência:** grep por `413|MAX_BODY|body_limit` em api.py retorna apenas Stripe/STT; não há middleware de teto de body.
- **Cenário:** em hosts não-Vercel (Railway/uvicorn/portable), POST de dezenas de MB em `/auth/login` (pública) ou `/game/action` é lido inteiro em memória antes do 422. Na Vercel o limite da plataforma (4,5 MB) mitiga. Rate-limit reduz, não elimina.
- **Impacto:** pressão de memória/CPU (DoS) em self-host; sem corrupção.
- **Correção sugerida:** middleware ASGI que rejeita `Content-Length > 256 KB` (exceto `/account/transcriptions`) e conta bytes em `receive` quando sem Content-Length; ou limite no proxy. Teste em tests/ de API.
- **Confiança:** provável
- **Já coberto por spec?** não
- **Status:** válido (baixa)

### INJ-03 — Desserialização FAISS (`allow_dangerous_deserialization=True`) restrita ao perfil legacy e a arquivos do repo
- **Severidade:** info
- **Categoria:** Deserialização
- **Local:** `rag.py:661,812,845,873,938,1065,1208,1293`; `infrastructure/runtime.py:188,237` (legacy = ("file","faiss",...))
- **Evidência:** índice de sessão `data/saves_memory/{game_id}/` só existe no perfil `legacy` (loopback, sem login); perfis local/portable/hosted usam `pgvector_memory` (sem pickle). `game_transfer.py` e `local_backup.py` não carregam FAISS/pickle (só JSON). Índices globais `faiss_lore_index/` e `faiss_rules_index/` vêm do repositório (confiáveis).
- **Cenário:** só com escrita local em disco (já seria execução local). Restaurar backup de origem não confiável contendo `data/saves_memory` seria RCE no legacy; `restore_files` não valida conteúdo, mas é ferramenta de operador.
- **Impacto:** nenhum vetor remoto identificado.
- **Correção sugerida:** manter; runbook "nunca restaurar saves_memory de origem não confiável"; considerar hash do índice global no manifesto de release.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** descartado como vulnerabilidade (info)

## Verificado e OK

- **SQL:** todo `execute` usa `%s`. Únicos f-strings: `infrastructure/account_lifecycle.py:34,103` interpolam `table` de tuplas constantes `PRIVATE_TABLES`/`FINANCIAL_TABLES` (l.8,11), owner parametrizado; `scripts/staging/*.py` com tabelas/extensões constantes. `pgvector_memory.py:172-187` interpola apenas `where` montado internamente com `%s` e usa `websearch_to_tsquery('simple', %s)` (não lança erro de sintaxe com input livre). Migrations: `EXECUTE format` usa `%I` (`20261013173632_account_lifecycle.sql:85`, `20261015140000_purchase_reconciliation.sql:189-191`).
- **Path traversal saves:** `persistence.py:73-88 save_path` exige UUID + containment; `_safe_session_memory_path` (l.384) alfanumérico + containment; `_safe_save_path` (l.500) só sanitiza ids legados internos; API valida via `_resolve_save_file` (api.py:745) -> 400. `rag.py:225 _contained_storage_path` + `_safe_storage_component` para sessão/NPC.
- **Blobs:** `infrastructure/local_adapters.py:357-374` rejeita `..`, vazio, absoluto, `\` e faz `resolve()`+parents; `asset_pipeline.py:30-42` sanitiza `entity_id` por regex e fixa UUIDs/hash; `supabase_blob.py:53` exige prefixo `users/{owner}/`; signed URL de chave vinda do banco, owner-scoped (`api.py:2551-2582` confere `generation.game_id == state.game_id`), expira em 300 s (limite 1..3600 s).
- **Restore/backup:** `services/local_backup.py:57-97` `verify_manifest` exige igualdade do conjunto de caminhos com o disco (impede `../` em manifesto adulterado); destino precisa estar vazio; sem zip/tar. `game_transfer.py` só lê JSON e valida via `deserialize_game_state`/UUID.
- **SSRF:** todos os `httpx` usam base URL de configuração ou hosts fixos (Turnstile, Supabase, OpenAI, Stripe/Google Play/STT com `follow_redirects=False`). `openai_images.py` recebe `b64_json` (não baixa URL). URL de checkout validada: https + `checkout.stripe.com` sem userinfo/porta (`stripe_checkout.py:183`); `RPG_CHECKOUT_ORIGIN` validado.
- **STT upload:** `api.py:2184-2232` Content-Length e contagem por chunk antes de acumular (8 MiB), timeout 15 s de leitura, rate limit 5/min, UUID de operação; `services/speech_to_text.py:166-203` valida magic bytes (webm/ogg/mp4/RIFF-WAVE), WAV reconstruído só com PCM, duração por frames decodificados (<=60 s), ffmpeg com lista de args, `-nostdin`, `-protocol_whitelist file,pipe`, `-t 61`, `timeout=10`; `TemporaryDirectory` remove arquivos em todos os exits (l.222).
- **Command injection:** único `subprocess` em produção é o ffmpeg acima; sem `os.system`, `shell=True`, `pickle`, `yaml.load`, `eval/exec` em services/infrastructure/api/persistence/agents.
- **XSS frontend:** `web/src/lib.ts:5-14 mdLite` escapa `& < >` ANTES de aplicar `<strong>/<em>`; resultado só entra em conteúdo de elemento (nunca atributo) e não há suporte a links, logo `<img onerror>` vira texto e `javascript:` não vira href. Os 5 usos de `dangerouslySetInnerHTML` (StoryLog:81, Hud:438, CodexTab:85/105/133) passam por mdLite (aprofunda SPEC-211: sem achado). Sem `innerHTML/eval/new Function/srcdoc/window.open` em `web/src`. `<img src>` usa URLs assinadas do servidor (CSP `img-src` limita a self/data/blob/*.supabase.co). Turnstile carregado de `challenges.cloudflare.com`, permitido por CSP (sem SRI, inviável para script dinâmico da Cloudflare). `frontend/app.js` legado: mdLite/escapeHtml equivalentes; único innerHTML com dado usa escapeHtml (l.149).
- **CSP/headers:** `api.py:150-203` CSP restritiva (`object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`), nosniff, X-Frame-Options; `X-Request-ID` do cliente validado por regex (`observability/telemetry.py:59`).
- **Redirect/header:** sem `RedirectResponse` com URL de query; Content-Disposition fixo no export de conta (api.py:509).
- **StaticFiles:** `app.mount("/", StaticFiles(..., html=True))` (api.py:3748) com proteção de traversal do Starlette.
- **ReDoS:** grep de quantificadores aninhados em input_normalization/prose_guard/secret_signatures/router não encontrou padrões `(x+)+`.
- **Limites de borda:** `ActionRequest.input_text<=2000`, `CreateCharacterRequest` limitado, `StartScenarioIn` estrito, `ChronicleSearchRequest.query<=300`, Auth/Verify/Reset com max_length, webhook Stripe com teto por stream.
