# SPEC-409 — medição (Etapa 0) e Pouso A (Etapa 1)

Medido em 11/11/2026 no worktree `rpg-spec-409`, base `51ffb4a4`.

## R0(a) — testes que dependem do relógio real (oráculo de duas janelas)

Escopo: os 44 arquivos de `tests/` que citam `finops_alerts|image_pricing|speech_pricing|shard_pricing|
embedding_pricing|portrait_offer|require_paid_effect|api_presenters|routes.art|cron_internal|rate_card|
usage_metering|finops_job|local_pricing` (547 passed + 160 skipped `*_local`/Postgres; nenhum `-n` > 2).
Rodada A: `RPG_RATE_CARD_MAX_AGE_DAYS=365 RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS=365` (tudo fresco).
Rodada B: `…=1` (tudo vencido). Diferença entre A e B = dependência do relógio.

| Teste | Rodada A (fresco) | Rodada B / hoje (vencido) | Causa |
|---|---|---|---|
| `test_spec352_creature_portraits.py::test_view_offer_present_when_eligible` | verde | **vermelho** (`pricing_unavailable`) | `portrait_offer.gate()` chama `require_paid_effect("image")` com o relógio real; o card de imagem (12/10) venceu em 11/11 |
| `test_image_pricing.py::test_unpublished_model_and_stale_card_cannot_authorize_dispatch` | **vermelho** (janela 365 d aceita 12/11) | verde | prova a janela de 30 d, logo depende do env; agora hermético (`delenv`) |

Nenhum outro teste difere entre as janelas (antes da mudança). Os que "passam a depender" com o R4
(`run_finops` com `failed == 0`) ainda não dependem: o R4 é da Etapa 5. Data literal de card
(quebraria na renovação, não no relógio): `test_image_pricing`, `test_shard_pricing`,
`test_shard_pricing_local`, `test_bug_finops_wallet_jobs_local`, `test_image_quotes_local`,
`test_rls_effective`, `test_spec236_races_local`, `test_spec352_creature_portraits_db`,
`test_speech_finance_local`, `test_wallet_local` (achado extra), `test_spec237_embedding_pricing` (caminho do card LLM). Todos derivados
do card instalado no Pouso A.

Futuros (ex.: embedding vence em 16/11, 17/10 + 30 d): o card de embedding **não** está em
`installed_freshness()` hoje, então nenhum teste atual o consulta com relógio. A rodada B (tudo
vencido) é o proxy de qualquer data futura; o único vermelho foi o acima. Os `datetime.now(UTC)` que
restam no escopo (`test_spec196_finops.py:205` usa `now + 400 d`, `test_speech_to_text.py:455/463`,
os `_local`) não comparam contra data de card (verdes na rodada B).

Depois do Pouso A as duas rodadas ficam idênticas: A = 547 passed, B = 547 passed (+ o novo
`test_view_offer…` verde em ambas; ver §Prova).

## R0(b)(c) — consultas no staging

**Não medido** nesta rodada (instrução do coordenador: não conectar ao staging). Pendente para a
Etapa 4: `app.pricing_versions` (`rate_card_sha256`, `rate_card_observed_at`,
`rate_card_max_age_seconds`), `app.image_price_profiles` e `app.finops_evaluations`; reservas/jobs em
voo. Achado de leitura de código que muda a Etapa 4: `app.image_price_profiles.expires_at` é
`not null` (`20261012160000_image_quotes.sql:9`) e `services/image_quotes.py:77,141` recusa profile
com `expires_at <= now`: é um **segundo relógio**, independente do rate card; ao publicar profiles
novos, conferir/estender `expires_at` e medi-lo no staging. `scripts/staging/vercel_env.py` não
grava `expires_at` (só aponta o id do profile).

## R0(d) — acesso à web

Este executor não tem ferramenta de web: **BLOQUEADO: sem acesso à web** para o R1 (Etapas 3–4).
Fica para quem tiver (coordenador). Nada foi inventado.

## Pouso A (Etapa 1)

- `tests/fakes/local_pricing.py`: `card_observed_at()`, `card_epoch()` (maior `observed_at` + 12 h) e
  `pin_card_clock(monkeypatch)`. **Desvio da spec:** função em vez de fixture `pinned_card_clock`:
  `_live` (352) é helper comum, não recebe fixture, e fixture fora de `conftest` exige import que o
  ruff (F811) reprova. A função limpa as variáveis de janela e fixa só o "agora" do
  `require_paid_effect`; a lógica de janela continua real.
- Datas literais trocadas por `card_epoch()`/`INSTALLED_RATE_CARD_OBSERVED_AT + 12 h` nos 9 arquivos
  da spec; `test_spec237_embedding_pricing` importa `_INSTALLED_CARD_PATH`.
- "Vencido → recusa" continua provado: `test_image_pricing::test_unpublished_model_and_stale_card…`
  (+31 d), `test_spec196_finops::test_stale_rate_card_alerts_and_blocks_paid_effect`
  (`require_paid_effect("image", now=+400 d)`), `test_shard_pricing::test_missing_or_stale_fx_rate_card_fails_closed`,
  e o novo `test_local_pricing_fixture::test_pinned_card_clock_does_not_disable_the_window`
  (imagem e STT, epoch + 31 d).
