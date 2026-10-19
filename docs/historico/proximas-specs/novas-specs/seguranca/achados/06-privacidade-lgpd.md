# Área 06 — Privacidade / LGPD (auditoria 2026-10-15)

Escopo: comparar `docs/spec197/legal/privacy-policy.md` e `docs/spec198/data-safety.md` com o código. Somente leitura.

Arquivos inspecionados: `docs/spec197/legal/privacy-policy.md`, `docs/spec198/data-safety.md`, `docs/spec198/store-listing.md`,
`observability/telemetry.py`, `observability/metrics.py`, `infrastructure/account_lifecycle.py`, `services/speech_to_text.py`,
`infrastructure/openai_images.py`, `infrastructure/supabase_blob.py`, `infrastructure/s3_blob.py`, `infrastructure/postgres.py` (delete),
`infrastructure/postgres_turns.py` (`commit_delete`), `api.py` (export/delete/`_log_turn`/prints/`DELETE /game/save`), `agents/archivist.py`,
`agents/librarian.py`, `services/prose_guard.py`, `supabase/migrations/*` (google_play_purchases, purchase_reconciliation, stripe_checkout,
wallet_ledger, blob_assets_chronicle, cron_health, account_lifecycle), `supabase/templates/*.html`, `supabase/config.toml`,
`web/src/components/AuthScreen.tsx`, `AccountScreen.tsx`, `TurnstileChallenge.tsx`, `web/index.html`.

---

### PRIV-01 — Política/Data Safety dizem "logs sem conteúdo de jogo", mas `print()` joga texto do jogador/fatos no stdout (Vercel logs)
- **Severidade:** média
- **Categoria:** Privacidade/PII
- **Local:** `agents/archivist.py:123` (`print(f"📚 [ARCHIVIST] Fatos: {texts}")`), `api.py:2679` (`print(f"Criando personagem: {req.name}")`),
  `agents/librarian.py:42,46` (`user_query`), `agents/archivist.py:121` e `api.py:2837` (`{exc}`/`{e}` crus), outros `print` de agentes (`combat.py:166`, `router.py`).
- **Evidência:** `print(f"📚 [ARCHIVIST] Fatos: {texts}")` roda a cada turno em todo perfil (inclusive hosted/Vercel, onde stdout vira log da plataforma).
  `texts` = fatos extraídos do texto do jogador/narração; `req.name` é nome de personagem (texto livre); `user_query` é texto do jogador.
  Política §1 "Técnicos: logs ... sem conteúdo de jogo e sem e-mail/token" e Data Safety linha "Logs/metricas tecnicas ... sem conteudo de jogo" ficam falsas.
  Esses prints NÃO passam por `safe_json`/`redact` (o cuidado só existe nos logs `rpg.*`).
- **Cenário:** qualquer jogador em staging/produção Vercel; operador/terceiros com acesso a logs Vercel leem texto das campanhas (pode conter dado pessoal digitado livremente). Perfis hosted*/portable.
- **Impacto:** dado pessoal em log não apagável com a exclusão da conta (política só promete apagar jogos/memória/arquivos); contradição com declaração ao Play.
- **Correção sugerida:** trocar `print` por `logging` com `safe_json` e apenas contagens/ids pseudonimizados (`len(texts)`, `pseudonym(game_id)`); remover `{texts}`, `req.name`, `user_query`; exceções logar só `type(exc).__name__`. Teste: caplog em `tests/` garantindo que a string da ação do jogador não aparece em stdout/stderr num turno MockLLM.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não (SPEC-182/190 tratam logs `rpg.*`, não `print`)
- **Status:** válido

### PRIV-02 — Exclusão de conta não apaga/exporta `google_play_purchases` (purchase_token cru + order_id) e políticas não declaram essa retenção
- **Severidade:** média
- **Categoria:** Privacidade/PII (LGPD art. 16/18)
- **Local:** `infrastructure/account_lifecycle.py:8-13` (`PRIVATE_TABLES`/`FINANCIAL_TABLES` não listam `google_play_purchases`, `wallet_debt_entries`, `purchase_reconciliation_state`);
  `supabase/migrations/20261015130000_google_play_purchases.sql:2-23` (`owner_id`, `purchase_token`, `order_id`, `google_state jsonb`); `20261015140000_purchase_reconciliation.sql:88-137`.
- **Evidência:** `finish()` só deleta `PRIVATE_TABLES`; `export()` só consulta `PRIVATE_TABLES + FINANCIAL_TABLES` + `payment_financial_events`. As tabelas Google/débito/reconciliação (adicionadas após SPEC-190) nunca entram em nenhuma das duas listas.
  A política §5 diz que permanecem apenas "extrato de créditos e eventos de pagamento vinculados a identificador opaco"; `google_play_purchases` guarda também `purchase_token` (segredo de bearer da Play API) e `google_state` bruto por tempo indeterminado, sem prazo.
- **Cenário:** usuário Android compra, exclui conta → linhas com `owner_id` + token Google permanecem; pedido de acesso/portabilidade (`/account/export`) não as devolve ao titular.
- **Impacto:** export incompleto (art. 18 II/V) e retenção não declarada; token de compra retido além do necessário (basta `token_sha256` após consumo).
- **Correção sugerida:** (a) incluir `google_play_purchases`, `wallet_debt_entries`, `purchase_reconciliation_state` no `export()` (omitindo `purchase_token`); (b) após `state='consumed'` anular/limpar `purchase_token` (manter `token_sha256`), e ao `begin()/finish()` limpar `purchase_token` e `google_state` não-financeiro; (c) listar as tabelas retidas e prazo na política §5. Teste: estender o teste Postgres de ciclo de conta (`tests/test_spec190_*`) para afirmar que nenhuma tabela `app.*` com coluna `owner_id` fica fora de `PRIVATE_TABLES ∪ FINANCIAL_TABLES ∪ allowlist`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não (SPEC-194/195 criaram as tabelas sem atualizar SPEC-190)
- **Status:** válido

### PRIV-03 — `DELETE /game/save/{id}` (perfis DB) não remove os blobs de imagem da campanha (órfãos no Storage até a exclusão da conta)
- **Severidade:** média
- **Categoria:** Privacidade/Retenção
- **Local:** `api.py:3628-3665`, `infrastructure/postgres_turns.py:345-374` (`commit_delete` só faz `delete from app.games`), `supabase/migrations/20260819002404_blob_assets_chronicle.sql:3-28` (`assets.game_id ... on delete cascade`).
- **Evidência:** a linha de `app.assets` some por cascade, mas nenhuma chamada a `blob_store.delete` existe no caminho de delete de jogo (grep: `blobs.delete` só em `account_lifecycle.py:97`). Objetos `users/{owner}/...` permanecem no bucket privado, sem referência no banco (`assets.status='delete_pending'` nunca é usado aqui).
- **Cenário:** usuário apaga uma campanha achando que apaga retratos/cenas gerados (derivados de `appearance`, texto livre); arquivos continuam armazenados e só são varridos na exclusão de conta (`finish()` sweep por prefixo).
- **Impacto:** retenção além do que a UI/política sugerem; dado derivado de texto pessoal permanece; custo de storage.
- **Correção sugerida:** em `commit_delete` (ou job pós-commit), selecionar `object_key` de `app.assets where game_id=%s` antes do delete e enfileirar remoção (`delete_pending` + job) ou apagar via `blob_store.delete`; teste: delete de jogo com asset `ready` deixa 0 objetos em `storage.objects` com o prefixo.
- **Confiança:** confirmado por leitura (sem trigger em `storage.objects` fazendo isso — `grep storage.objects supabase/migrations`)
- **Já coberto por spec?** não
- **Status:** válido

### PRIV-04 — Terceiros reais não declarados / `<...>` abertos: OpenAI (imagens), Google Fonts, Supabase Auth SMTP; política diz "sem terceiros" para cookies/IP
- **Severidade:** média
- **Categoria:** Privacidade/Transparência
- **Local:** `infrastructure/openai_images.py:30-53` (envia `prompt` derivado de `appearance` e PNG de referência do herói para `api.openai.com`); `web/index.html:9-12` (carrega `fonts.googleapis.com`/`fonts.gstatic.com`); `web/src/components/TurnstileChallenge.tsx:18` (script `challenges.cloudflare.com`); política §4 linha "Provedor de imagem (`<...>`)".
- **Evidência:** a política lista o provedor de imagem como placeholder (código fixa OpenAI GPT Image 2); OpenAI só aparece como STT fallback. Google Fonts (Google LLC recebe IP + User-Agent de todo visitante, inclusive não logado) não aparece em nenhuma seção; §7 afirma "sem ... analytics de terceiros" mas não menciona requisições a terceiros. Data Safety deixa imagem/SMTP "CONFIRMAR".
- **Impacto:** divergência política×código (art. 9 LGPD transparência; Play exige exatidão); transferência internacional não coberta para esses operadores.
- **Correção sugerida:** preencher OpenAI (imagens + STT), Google Fonts (ou self-host das fontes em `web/public` e remover o preconnect — preferível, elimina o terceiro), SMTP real; atualizar `data-safety.md` e CSP consistente. Teste: `scripts/` de release que compara hosts externos do `web/dist/index.html` com allowlist da política.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** SPEC-197/198 pontos abertos (parcialmente; Google Fonts e OpenAI-imagem não citados)
- **Status:** válido

### PRIV-05 — Sem link para política/termos, aviso de IA/terceiros ou verificação de idade na UI; `<18/13?>` indefinido
- **Severidade:** média
- **Categoria:** Privacidade/Consentimento
- **Local:** `web/src/components/AuthScreen.tsx` (nenhum link/checkbox de privacidade/termos; busca por "privacidade|termos|política|idade" sem resultado), `AccountScreen.tsx`, `web/public/` (sem páginas legais), `api.py` (sem rota `/privacidade`); política §9 e `store-listing.md` com idade `<18/13?>`.
- **Evidência:** o cadastro coleta e-mail/senha e envia texto livre a LLMs sem exibir finalidade, operadores ou aceite; não há gate de idade; conteúdo inclui violência/linguagem gerada por IA (store-listing l.68-77).
- **Impacto:** base legal/consentimento e transparência não materializadas; risco de tratar dados de menores (art. 14 LGPD) e rejeição na revisão do Play (URL de privacidade obrigatória).
- **Correção sugerida:** servir `docs/spec197/legal/*.md` renderizados em rotas públicas estáticas, link no rodapé do `AuthScreen` e no signup com texto "Ao criar conta você concorda..."; aviso curto "texto e voz são processados por provedores de IA"; declarar idade mínima e checkbox de maioridade (ou autodeclaração). Teste e2e Playwright existente (`web/e2e`) assertando presença dos links.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** SPEC-197 (tarefas de publicação, em andamento) — não implementado no código
- **Status:** válido

### PRIV-06 — Export é parcial e síncrono: não inclui conteúdo dos blobs (imagens), nem `google_play_purchases`/dívida; `select *` com colunas internas
- **Severidade:** baixa
- **Categoria:** Privacidade/Direitos do titular
- **Local:** `infrastructure/account_lifecycle.py:28-38`, `api.py:500-513`.
- **Evidência:** o JSON entrega apenas metadados de `app.assets` (object_key, sha256), não os arquivos; `select *` inclui colunas internas (`lease_token`, `request_sha256`, `payload` de jobs). A resposta é montada integralmente em memória numa única transação (memória pgvector pode ser grande → risco de timeout/DoS autenticado, recent-session exigido).
- **Impacto:** portabilidade incompleta; export por owner (não há compartilhamento via signed URL — **OK**), mas vaza colunas técnicas ao titular (baixo risco).
- **Correção sugerida:** acrescentar URLs assinadas de curta duração (≤300 s) ou ZIP em job; listas explícitas de colunas; streaming/paginação. Teste em `tests/test_spec190_*`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** SPEC-190 `done` (escopo mais restrito)
- **Status:** válido

### PRIV-07 — Sem política de retenção/TTL para `usage_events`, `turns`, `operations`/`jobs` terminais, `account_deletions`, `finops_evaluations`
- **Severidade:** baixa
- **Categoria:** Privacidade/Retenção
- **Local:** migrations (apenas `cron_requests` 2 dias e `cron_health_alerts` 90 dias têm purge: `20261015125000_cron_health.sql:51-52`; `rate_limit_buckets` 24 h via `cron_internal.py:109`).
- **Evidência:** nenhuma limpeza periódica para tabelas por-owner; política §5 diz "mantidos enquanto a conta existir" (coerente para dados de jogo) mas não declara prazo de `usage_events`/`operations` (contêm `request_hash`, ids). `account_deletions` (tombstone com `owner_id`) é permanente, e `status='deleted'` nunca é compactada.
- **Impacto:** acúmulo de metadados pseudonimizados; baixo. Declarar na política "tombstone e extrato retidos por X anos".
- **Correção sugerida:** job de purge (operações concluídas > 90 d, jobs terminais > 30 d) + prazo explícito na política; manter `account_deletions` por prazo legal definido.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### PRIV-08 — `pseudonym()` usa chave pública default (`local-telemetry-only`) se `RPG_TELEMETRY_SECRET` não estiver definido; sem validação em perfis hosted
- **Severidade:** baixa
- **Categoria:** Privacidade/Telemetria
- **Local:** `observability/telemetry.py:64-66`; nenhum guard em `infrastructure/runtime.py` (grep `RPG_TELEMETRY_SECRET` só em `telemetry.py`).
- **Evidência:** `key = (secret or os.getenv("RPG_TELEMETRY_SECRET") or "local-telemetry-only")`. Em produção sem a env, `owner_id_ref`/`game_id_ref` são HMAC com chave pública: quem conhece um UUID (ex.: o próprio titular, ou lista vazada) consegue correlacioná-lo nos logs; sem enumeração prática (UUID v4), logo impacto baixo.
- **Correção sugerida:** exigir `RPG_TELEMETRY_SECRET` (≥32 chars) nos perfis hosted* no `doctor`/startup (fail-closed como `RPG_SESSION_SECRET`); teste no doctor.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### PRIV-09 — `rpg.prose` loga trecho de abertura da narração em texto claro
- **Severidade:** info
- **Categoria:** Privacidade/PII
- **Local:** `services/prose_guard.py:260` (`_LOG.warning("Abertura repetida (%s): “%s…”", where, opening(new_text))`).
- **Evidência:** loga o início da narração gerada (pode incluir nome do personagem/NPC dado pelo jogador) fora de `safe_json`. Correlato de PRIV-01.
- **Correção sugerida:** logar apenas `where` + hash/len.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** SPEC-043 (feature), não privacidade
- **Status:** válido (agrupável com PRIV-01)

### PRIV-10 — Auditoria SPEC-196: alertas "sem ids de usuário" — CONFIRMADO, nenhum achado
- **Severidade:** info
- **Categoria:** Privacidade/PII
- **Local:** `observability/metrics.py:12-41`
- **Evidência:** labels fechados (`route`, `outcome`, `provider`, `tier`, `kind`, `sku_id`, `channel`...), `_key` levanta erro se labels divergem; nenhum `owner_id/game_id/order_id`. `/metrics` público não expõe ids de usuário.
- **Status:** descartado (controle correto)

---

## Verificado e OK
- **Logs `rpg.turn` / `rpg.account`:** `api.py:3206-3224` usa `pseudonym(game_id)` + `correlation()` (que pseudonimiza `owner_id`/`game_id` em `correlation_scope`, `telemetry.py:93-102`) e `safe_json` com `redact` (chaves `email/password/action/input_text/...`, regex de e-mail, Bearer e signed URL). Nenhum texto de ação do jogador no log JSON. `account.delete.finish_failed` e `auth.email_delivery_failed` logam só tipo/status (`api.py:420,533`).
- **Métricas:** cardinalidade fechada, sem ids (PRIV-10).
- **STT:** áudio só em `tempfile.TemporaryDirectory` (`services/speech_to_text.py:~200`), apagado em sucesso/erro/timeout/cancelamento; transcript não persistido (retorna só no response); apenas `request_hash` (sha256) e `usage` saneado (`usage` descarta corpo do provedor). Coerente com política §1. Provedor fixo HTTPS, `trust_env=False`, sem redirect.
- **Signed URLs:** TTL máx. 3600 s (`supabase_blob.py:90`, `s3_blob.py:53`); único uso em produção `api.py:2582` com 300 s, bucket privado. Export não gera signed URLs.
- **Export:** owner-scoped via `principal.user_id` (sem parâmetro de owner), exige sessão recente (`_require_recent`), `Cache-Control: no-store`, bloqueado se tombstone existe.
- **Delete de conta:** revoga sessões e cancela jobs ANTES de apagar; fence por trigger (`account_write_fence`); sweep duplo de Storage por prefixo `users/{owner}/`; apaga Auth user; retém apenas tabelas financeiras com UUID; limpa `checkout_url`; remove buckets de rate limit por e-mail; `stripe_events.facts` documentado sem PII; Stripe não recebe e-mail do app (sem `customer_email`).
- **E-mail/verify:** token em fragmento `#auth_action=...&token_hash=` (não vai a servidor nem `Referer`) e removido com `history.replaceState` (`AuthScreen.tsx:10-15`); templates HTML sem recursos externos; `Referrer-Policy: same-origin` (`api.py:199`).
- **Google Play:** `obfuscated_account_id` HMAC (`services/google_play.py:44`), sem e-mail.
- **Perfil legacy:** `saves/` e `data/saves_memory/` ficam em disco sem expiração (info, só dev).
