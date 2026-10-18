# SPEC-258 — Providers de STT, imagem e embeddings: tentativa, fallback, status, latência e custo em log

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240, SPEC-248
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** STT (`services/speech_to_text.py:206-262`): sem log nem métrica; fallback Groq→OpenAI silencioso; `except (SpeechError, httpx.HTTPError, TimeoutError)` (`249-250`) só alimenta o circuito; timeout de 22 s (`240`) engolido; circuito (`100-117`) abre calado; `_allowed_by_switches` fail-open silencioso (`137`); o endpoint converte qualquer exceção em 503 `speech_internal_error` sem log (`api.py:2865-2866`). Imagem (`infrastructure/openai_images.py:27-64`, `workers/dynamic_art_jobs.py`): sem log/métrica/latência; status do provider só no texto da exceção; `asset_pipeline.process_image` (`56`) relança sem log. Embeddings Jina (`rag.py:297-373`): só emite evento de uso via hook (no-op fora de turno), sem status/latência; retries transitórios (`328-336`) silenciosos. Ao contrário do LLM, nada disso passa por `rpg_llm_*`.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Evento comum `provider.attempt` (`debug` sucesso, `warning` falha) com `capability` (`stt|image|embedding`), `provider`, `model`, `outcome` (`success|http_error|timeout|transport_error|invalid_response|refused|circuit_open|kill_switch`), `http_status`, `latency_ms`, `attempt`, `fell_back`, `cost_basis` (`exact|estimated|unknown`).
- **R2** — Métricas `rpg_provider_attempts_total{capability,provider,outcome}` e `rpg_provider_duration_seconds{capability,provider}`.
- **R3** — `stt.circuit_opened` / `stt.switch_check_failed` (`warning`); 503 `speech_internal_error` passa a logar `error_type` (`error`).
- **R4** — Imagem: `image.generation_failed` com `http_status` (extraído do provider, não do texto) e `job_id`; refusal ⇒ `outcome=refused`.
- **R5** — Áudio, prompt de imagem, texto embeddado e URLs nunca em log (sentinelas).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Trocar providers/timeouts.

## 3. Design técnico

- **Novo:** helper `observability/telemetry.py::log_provider_attempt`. **Alterados:** `services/speech_to_text.py`, `api.py:2830-2866`, `infrastructure/openai_images.py`, `workers/dynamic_art_jobs.py`, `services/asset_pipeline.py`, `rag.py` (`_JinaEmbeddingsHTTPX`).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_provider_logging.py` (`httpx.MockTransport`): `test_stt_fallback_logged`, `test_stt_timeout_logged`, `test_image_http_status_logged`, `test_jina_retry_logged`, `test_no_audio_or_prompt_in_logs`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [ ] Toda chamada de STT/imagem/embedding tem `provider.attempt`.
- [ ] Fallback STT visível.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: 1 transcrição curta (Groq) ⇒ `provider.attempt capability=stt outcome=success`; com `GROQ_API_KEY` inválida num preview ⇒ falha + fallback OpenAI logados.

## 7. Riscos & compatibilidade

- Custo do smoke: ≤ 2 chamadas STT (~US$ 0,0005).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
