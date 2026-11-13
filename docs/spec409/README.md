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

## Pouso B — cards renovados em 13/11/2026 (Etapas 2–6)

Preços e datas: `fontes.md` (lidas pelo coordenador) e `evidencia-{imagem,speech,embedding,llm}.md`. Nenhum
preço mudou; mudaram `version`, `observed_at` (2026-11-13), `source(s)` e, no de imagem, `derivation`.

| Card | Arquivo novo | sha256 |
|---|---|---|
| LLM | `data/pricing/rate_card_2026-11-13.json` | `bd1d2942c1cb4ca248481f6854f4d857e0f9dd727dff4ea8f8646dfa28dc2fe7` |
| Imagem | `data/pricing/image_rate_card_2026-11-13.json` | `d25f1a5dcd7442e99538b94c201dd221e753506aa751b328559b2d5f8b0926ae` |
| STT | `data/pricing/speech_rate_card_2026-11-13.json` | `8a931b35f05455bc5a9003a96bf5d22e27ff04de2483da5d6a9e788791af0798` |
| Embedding | `data/pricing/embedding_rate_card_2026-11-13.json` | `b49eb940cb0821e857a2e78f8d878074667a82df4d0d4538dd8f566725fbb93e` |

Os quatro antigos continuam byte a byte iguais (`tests/test_pricing_card_files.py`).

- **Imagem:** mesmo `model` (`gpt-image-2-2026-04-21`), marcado "Deprecated" em 10/11/2026, desligamento em
  10/02/2027. Trocar de modelo é decisão de produto: **spec própria antes de 10/02/2027**.
- **Embedding:** o valor (0.05/1M) vem de **fonte secundária** (usagepricing.com); a página oficial da Jina não
  mostrou os valores. O JSON e `evidencia-embedding.md` dizem isso. Conferir no painel oficial quando houver acesso.
- **Achado extra (muda a pré-condição de deploy):** `quote_usage` também recusa evento de **texto** (`token_priced`)
  cuja `pricing_version` (= `RATE_CARD_VERSION`) difere da `rate_card_version` da linha de `pricing_versions` da
  reserva (`shard_pricing.py`, `rate card de usage diverge da versão`). Uma reserva de texto aberta com a linha
  antiga (`2026-10-08-v1`) que liquidar depois do deploy trava igual à de imagem/STT. Pré-condição: **nenhuma
  reserva aberta de nenhum tipo** (abaixo).
- **`expires_at` dos profiles:** `spec197-staging-portrait` vence 2026-12-14; `staging-326-*` vencem 2027-01-24.
  Os profiles novos nascem com `now() + 90 days` (mesmo prazo da SPEC-326) e copiam `model`/`size`/
  `max_provider_usd` dos `staging-326-*`; nada de preço comercial é inventado.

### Etapa 4 — passo a passo para o coordenador (staging; NADA disso foi rodado pelo executor)

Ids: pricing version `spec409-staging-2026-11-13`; SKU `spec409-staging-2026-11-13-sku`; profiles
`spec409-staging-2026-11-13-portrait` e `…-scene`. Estão nas constantes `synthetic_data.WALLET_PRICING/WALLET_SKU`
e `vercel_env.NON_SECRET_LITERALS["RPG_SPEECH_PRICING_VERSION"]`/`DYNAMIC_ART_PRICE_PROFILES`, e um teste
(`tests/test_publish_rate_card.py`) garante que os três lugares concordam. Linhas antigas (`spec197-*`,
`staging-326-*`) ficam como histórico. Ordem importa: **publicar no banco antes do deploy do código novo**, e
`vercel_env.py` só depois de publicar (ele aponta para ids que ainda não existem no banco).

1. **Pré-condição (somente leitura, `psql`/MCP no staging).** Tem de dar zero linhas; se não, reconciliar antes
   (`docs/spec197/runbooks/budget.md` § Falhas de provider; nunca editar reserva à mão):
   ```sql
   select reference_type, status, count(*) from app.wallet_reservations
    where status in ('reserved','effect_started','uncertain') group by 1,2;
   select status, count(*) from app.art_generations
    where status in ('pending','generating','failed_retryable') group by 1;
   select kind, blocking, message from app.finops_evaluations order by evaluated_at desc limit 20;
   select profile_id, pricing_version_id, model, expires_at from app.image_price_profiles order by 1;
   ```
   Quotes de imagem em voo (`app.image_quotes` não expirados) vão pedir cotação nova depois do deploy; é esperado.
2. **Plano (sem tocar em nada):** `bash scripts/dev/py.sh -m scripts.staging.publish_rate_card --dry-run`.
   Conferir `rate_card_sha256` = `bd1d2942…2dc2fe7` e `rate_card_version` = `2026-11-13-v1`.
3. **Publicar** (usa `RPG_STAGING_DB_URL` e `SUPABASE_PROJECT_REF` do `.env.staging`; recusa se o DSN não for do
   ref): `bash scripts/dev/py.sh -m scripts.staging.publish_rate_card --confirm-staging "$SUPABASE_PROJECT_REF"`.
   Insere `pricing_versions` + `purchase_skus` (via `seed_wallet_prereqs`, `on conflict do nothing`) e os dois
   `image_price_profiles`. Evidência em `.tmp/evidence/publish_rate_card.json`. Depois dos inserts o script relê as
   linhas e sai com código 1 (`FAIL: …`) se a `pricing_versions` que ficou no banco não tiver versão, hash e data do
   card instalado, ou se faltar um dos dois profiles (revisão Sol P2-1: `on conflict do nothing` deixava passar em
   silêncio uma linha `spec409-*` criada antes com outro hash). Saiu 1 ⇒ não seguir para o passo 5.
4. **Conferir no banco:**
   ```sql
   select version_id, rate_card_version, left(rate_card_sha256,8), rate_card_observed_at
     from app.pricing_versions where version_id = 'spec409-staging-2026-11-13';
   select profile_id, pricing_version_id, model, size, max_provider_usd, expires_at
     from app.image_price_profiles where pricing_version_id = 'spec409-staging-2026-11-13';
   ```
   Esperado: `2026-11-13-v1`, `bd1d2942`, `2026-11-13`; dois profiles com `gpt-image-2-2026-04-21` e `expires_at`
   ~ +90 dias.
5. **Env vars:** `bash scripts/dev/py.sh scripts/staging/vercel_env.py --dry-run` (confere `RPG_SPEECH_PRICING_VERSION`
   e os dois `RPG_IMAGE_PRICE_PROFILE_*` nos nomes enviados) e depois sem `--dry-run`.
6. **Deploy do staging** com o código do pouso B (leitores nos cards novos) e **smoke §6** da spec; rodar o cron
   `finops` e conferir que não há `stale_rate_card`. Registrar o resultado aqui (sem tokens nem ids de owner).
7. **Rollback:** reverter o commit dos leitores e reaplicar `vercel_env.py` com os ids antigos (as linhas novas são
   append-only e inofensivas). **Limite (revisão Sol P2-5):** isso volta para os cards de outubro, que já venceram;
   imagem, STT e compra voltam a 503 (falha fechada), não a um estado que funciona. Rollback só serve para tirar um
   card novo errado; o conserto de verdade é publicar o card certo.

## Notas da revisão Sol (13/11, APPROVED_WITH_FOLLOWUPS)

- **Ordem de deploy:** depois do pouso, `vercel_env.py` e os smokes apontam para os ids `spec409-staging-2026-11-13*`.
  Deploy antes de publicar falha fechada (imagem, STT e compra em 503, como já estão desde 11/11); o turno de texto
  não lê `pricing_versions` e o cron segue 200. Ordem certa: publicar → conferir → `vercel_env.py` → deploy → smoke.
- **P2-2 (follow-up):** o guarda "relógio real só no teste do R3" olha `datetime.now` na mesma linha de
  `installed_freshness`. Não pega o `now` em duas linhas, `require_paid_effect` sem `now` nem
  `require_image_prices(..., datetime.now(UTC))`. A catraca de relógio da SPEC-416 (`clock_asserts.py`) cobre parte.
- **P2-4:** `tests/test_pricing_card_files.py` compara `observed_at <= hoje` com o relógio real; só falha com card
  datado no futuro (aceito).
