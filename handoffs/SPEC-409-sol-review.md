# SPEC-409 — revisão sol (review)

> **Veredito:** APPROVED_WITH_FOLLOWUPS
> **Revisor:** Opus / sol (`spec-reviewer`) · **Data:** 2026-11-13 · **Commit revisado:** `4aba3d4b`

## Escopo

Branch `spec-409`, intervalo `48da95ab..4aba3d4b` (5 commits, Etapas 2–6 / Pouso B): os quatro
`data/pricing/*_2026-11-13.json`, os cinco apontamentos de leitor, `finops_alerts.py`
(`installed_freshness` com embedding, `stale_card_failures`), `finops_job.py`
(`_stale_card_summary`), `scripts/staging/publish_rate_card.py`, constantes de
`synthetic_data.py`/`vercel_env.py`, job `rate-cards` do `validate.yml`, runbook `budget.md`,
`docs/spec409/*` e os testes novos/alterados. As Etapas 0–1 (Pouso A) têm o handoff `terra` e
ficaram fora. Staging não foi tocado: o publicador foi revisado por leitura e pelos testes offline.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/staging/publish_rate_card.py:57-68` | O publicador não confere o que ficou no banco. `seed_wallet_prereqs` e o insert dos profiles usam `on conflict do nothing`. Se a linha `spec409-staging-2026-11-13` já existir com outro hash, o script devolve sucesso. Isso acontece se algum smoke (`two_user_smoke`, `voice_smoke`, `stt_fallback_smoke`, `browser_voice_smoke` e `docs/spec398/smoke_r6.py` chamam `seed_wallet_prereqs()` sem argumento e agora gravam esse id) rodar a partir de um checkout cujo card mudou depois. Também devolve sucesso se o profile de origem `staging-326-*` não existir (insert…select de 0 linhas). A linha é imutável, então o efeito é cotação e compra recusando com "conteúdo do rate card divergiu". É falha fechada, sem cobrança errada, mas o script diz que deu certo. | Depois do insert, ler a linha e exigir `rate_card_version`/`rate_card_sha256`/`rate_card_observed_at` iguais aos instalados e exatamente 2 profiles com o `pricing_version_id`; senão sair com código ≠ 0 e dizer "use outro `--pricing-id`". Hoje o passo 4 do `docs/spec409/README.md` faz a mesma conferência à mão: vale seguir até o follow-up. |
| P2-2 | P2 | `tests/test_rate_card_freshness.py:34-36,106-118` | O teste de arquitetura do R3 é mais fraco que o da spec. A spec manda que `datetime.now` só apareça no arquivo do guarda, entre os que importam `installed_freshness`/`rate_card_max_age`. Essa regra literal é inviável: 7 arquivos têm usos legítimos. Por isso a implementação usa uma regex que só olha a mesma linha. Provei com sonda: ela não pega `now = datetime.now(UTC)` seguido de `stale_rate_cards(installed_freshness(), now)` em duas linhas, nem `require_paid_effect("image")` sem `now` (o padrão exato do bug original, via `gate()`), nem `require_image_prices(MODEL, datetime.now(UTC))`, nem POST em `/internal/cron/finops` sem fixar os cards. O desvio não está registrado no cabeçalho da spec. | Registrar o desvio na spec. Follow-up: endurecer a heurística para chamadas a `require_paid_effect`/`require_image_prices`/`require_speech_prices`/cron finops sem `now=` explícito em arquivo sem `pin_card_clock`/`pin_fresh_installed_cards`, ou deixar a rodada de duas janelas como verificação recorrente. |
| P2-3 | P2 | `docs/spec197/runbooks/budget.md` § "O que o alerta do cron faz" | `stale_card_failures` filtra pelo kind `stale_rate_card`, que também nasce de `fx` e da linha `rate_card` da `pricing_versions` mais nova (`infrastructure/finops_reader.py:55-63`). O executor está certo: FX vencido também derruba o cron. Isso cumpre a letra do D4 (kind) e é coerente, porque FX e linha vencidos já bloqueiam venda em `require_fresh`. O runbook, porém, diz "só esse tipo" sem avisar que FX conta. Hoje o staging não é afetado (a linha nova nasce com `fx_max_age_seconds` = 1 ano). Em produção, com FX de janela curta, o cron vira 500 a cada hora se a cotação atrasar. | Uma frase no runbook: "`stale_rate_card` inclui `fx` e `rate_card` da `pricing_versions` mais nova; FX vencido também deixa o cron 500". Antes do go de produção (SPEC-197), confirmar se é isso que se quer. |
| P2-4 | P2 | `tests/test_pricing_card_files.py:73` | `observed <= datetime.now(UTC)` compara o relógio real com a data do card fora do arquivo do guarda (R2(a)). É monotônico: só falha com card datado no futuro, caso que o guarda também pega como idade negativa. Inofensivo. | Opcional: comparar com `date.fromisoformat(stamp)` do nome do arquivo ou aceitar e citar como exceção no docstring. |
| P2-5 | P2 | `docs/spec409/README.md:132-133` (rollback) | "Reverter os leitores e reaplicar ids antigos" volta para cards de 08/10 e 12/10, que já estão vencidos. O rollback leva a 503 em imagem e STT, não ao estado anterior funcional. | Dizer isso no passo 7 (rollback = falha fechada; o alívio é D1). |

Nenhum P0/P1.

### Pontos conferidos sem achado

- **Números dos 4 JSON contra `docs/spec409/fontes.md`, campo a campo.**
  - Imagem 5.00/8.00/30.00, `cached_input_discount: false`, mesmo `model`, descontinuação 2026-11-10→2027-02-10 em `derivation`, `observed_at` com `+00:00`.
  - Groq STT 0.04/h, mínimo 10 s.
  - gpt-4o-mini-transcribe 1.25/5.00, tetos 16000/2000.
  - Jina 0.05 com "SECONDARY SOURCE" no `source`.
  - gpt-oss-20b 0.075/0.037/0.30 e 120b 0.15/0.075/0.60, ambos 131072/65536, com as duas URLs Groq.
  - deepseek-flash e v4-flash 0.30/0.006/1.20, `conservative_peak`, 1000000/384000 (contexto de 1M e saída de 384K na fonte).
  - O `diff` contra os cards antigos mostra que só mudaram `version`, `observed_at` e `source`/`derivation`.
- **`max_cost_usd` do STT recalculado.** Groq: 0.04 × 60/3600 = 0.000666…, ROUND_UP em 9 casas = 0.000666667; o teto de 60 s confere com `services/speech_pricing.py:98,109`. OpenAI: (16000 × 1.25 + 2000 × 5.00)/1e6 = 0.030000000.
- **Cards antigos intactos.** `git diff --quiet` contra `48da95ab` e contra a `main` está vazio nos 4 antigos. Os sha256 batem com `OLD_CARD_SHA256` do teste e com o `3f62239b…` da `pricing_versions` do staging (`fontes.md` §7). Os sha256 dos novos batem com o README (`bd1d2942…`, `d25f1a5d…`, `8a931b35…`, `b49eb940…`).
- **Card LLM com os dois apontamentos.** `shard_pricing.py:24` e `usage_metering.py:20` apontam para `rate_card_2026-11-13.json`. `test_both_llm_card_readers_resolve_the_same_file` cobre caminho, `RATE_CARD_VERSION` = `2026-11-13-v1`, sha256 e data.
- **R3.**
  - T-9 falha (`image`).
  - Vencido falha (`llm` +1 d).
  - T-11 passa, medido no card que vence primeiro.
  - Embedding entra em `installed_freshness()` e em `EXPIRING_CARD_NAMES`, e a mensagem cita o card e os dias.
  - O fixture limpa as 3 envs.
  - O job `rate-cards` roda só no `schedule`, com o mesmo runner e as actions pinadas por SHA.
  - O guarda real fica vermelho a partir de 2026-12-03 (13/11 + 30 − 10), por desenho.
- **R4.**
  - `failed` só soma por kind `stale_rate_card`, no máximo 1 por rodada.
  - `rate_card_expiring` e outros bloqueantes (`unknown_pricing`) mantêm `failed == 0`.
  - O endpoint devolve 500 com `ok: false`.
  - `run_finops` não cresceu: o helper `_stale_card_summary` é chamado em uma linha e `test_size_budget.py` está verde.
- **`pin_fresh_installed_cards` (autouse em 196, 197 e bug_finops) não enfraquece "vencido → recusa".**
  - Ele só troca `finops_job.installed_freshness`.
  - Os testes de recusa usam `finops_alerts.installed_freshness`/`require_paid_effect` direto e seguem reais: `test_stale_rate_card_alerts_and_blocks_paid_effect` (+400 d), `test_rate_card_window_configurable` (`fa.installed_freshness()`, :410-413), `test_rate_card_expiring_warns_before_blocking` e os de `test_image_pricing`/`test_local_pricing_fixture`.
  - `test_run_finops_publishes_owner_free_metrics_and_response` continua provando `stale_rate_card` via fx do reader.
- **Publicador.**
  - Só acrescenta linhas: inserts com `on conflict do nothing`, sem update/delete.
  - `--dry-run` sai antes de ler env ou abrir conexão (teste com `RPG_STAGING_DB_URL` ausente).
  - Exige `--confirm-staging` igual a `SUPABASE_PROJECT_REF` e respeita `RPG_PROTECTED_PROJECT_REFS`; `assert_ref_in` confere que o DSN é do ref.
  - Não imprime segredo: só o caminho da evidência, que passa por `redact`. A senha do DSN nunca sai.
  - É idempotente nas linhas; a ressalva está no P2-1.
- **Ordem de deploy (pedido do coordenador).** Leitura de código: no produto, só três caminhos tocam `pricing_versions`, todos por id explícito.
  - Cotação e liquidação de imagem: profile → versão.
  - STT: `RPG_SPEECH_PRICING_VERSION`.
  - Compra: SKU → versão.
  - O turno de texto não reserva nem lê `pricing_versions` (sem `wallet.reserve` fora de imagem/STT). O finops reader usa a linha mais nova por `created_at`.

  Cenários depois do pouso:

  | Cenário | O que acontece |
  |---|---|
  | (a) Deploy da `main` antes de publicar, env antigo | Imagem, STT e compra no SKU antigo recusam (hash diverge, 503). É o mesmo estado de hoje: os cards de 12/10 já estão vencidos. O cron segue 200: cards instalados frescos e a linha mais nova ainda com janela de 1 ano. |
  | (b) `vercel_env.py` antes de publicar | Profile e versão inexistentes, recusa 503 (falha fechada). |
  | (c) Smoke da `main` antes de publicar | `seed_wallet_prereqs()` cria a linha e o SKU `spec409-*` com o hash certo (mesmos valores do publicador), mas não os profiles. Contra staging ainda com código antigo, a compra recusa (hash), e o smoke falha alto. |
  | (d) Publicar antes do deploy | Código antigo com env antigo continua em `spec197-restore-b` (já vencido de qualquer modo). O finops reader passa a ver a linha nova (fresca). Inofensivo. |

  Em nenhuma ordem há cobrança errada nem dado inconsistente. O pior caso é imagem, STT e compra continuarem em 503, como hoje. **Aceitável com aviso no ESTADO**, sem precisar de ids por parâmetro nem de manter as constantes antigas. Ordem recomendada, já no README: pré-condição → `publish --dry-run` → publicar → conferir (passo 4) → `vercel_env.py` → deploy → smoke §6. Único cuidado real: ninguém roda smoke de staging a partir da `branch`/`main` antes de o card estar final (P2-1).
- **Lint e qualidade.**
  - `ruff check` e `ruff format --check` limpos nos arquivos tocados.
  - `dup_helpers --diff` só acusa `publish`, homônimo sem relação em `observability/latency.py`.
  - Funções novas ≤ 60 linhas, sem `except` largo novo, sem mudança em `evals/`, sem segredo em log.

## Evidência verificada

`bash scripts/dev/red_green.sh 409` (worktree `rpg-spec-409`, `main` em `8e010153`):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_finops_stale_card_cron.py::test_cron_finops_ok_with_fresh_cards | verde | verde | FAIL: nao prova a mudanca |
| tests/test_finops_stale_card_cron.py::test_cron_finops_returns_500_on_stale_card | vermelho | verde | OK |
| tests/test_finops_stale_card_cron.py::test_run_finops_expiring_card_does_not_fail | vermelho | verde | OK |
| tests/test_finops_stale_card_cron.py::test_run_finops_fails_when_rate_card_stale | vermelho | verde | OK |
| tests/test_finops_stale_card_cron.py::test_run_finops_names_every_stale_card | vermelho | verde | OK |
| tests/test_finops_stale_card_cron.py::test_run_finops_other_blocking_alert_does_not_fail | verde | verde | FAIL: nao prova a mudanca |
| tests/test_finops_stale_card_cron.py::test_stale_card_failures_counts_once_per_run | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_both_llm_card_readers_resolve_the_same_file | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_embedding_card_flags_the_secondary_source | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_image_card_same_model_and_positive_decimals | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_llm_card_keeps_prices_and_cites_both_groq_pages | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_new_card_version_observed_at_and_source | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_old_cards_are_byte_identical | verde | verde | FAIL: nao prova a mudanca |
| tests/test_pricing_card_files.py::test_readers_point_at_the_new_cards | vermelho | verde | OK |
| tests/test_pricing_card_files.py::test_speech_card_max_cost_matches_the_ceilings | vermelho | verde | OK |
| tests/test_publish_rate_card.py::test_dry_run_prints_the_plan_without_touching_anything | vermelho (import) | verde | OK |
| tests/test_publish_rate_card.py::test_live_run_requires_matching_staging_confirmation | vermelho (import) | verde | OK |
| tests/test_publish_rate_card.py::test_profile_ids_follow_the_pricing_version | vermelho (import) | verde | OK |
| tests/test_publish_rate_card.py::test_profile_statements_copy_model_and_ceiling_from_the_old_profiles | vermelho (import) | verde | OK |
| tests/test_publish_rate_card.py::test_seed_prereqs_keep_the_wallet_ids_and_vercel_env_agrees | vermelho (import) | verde | OK |
| tests/test_rate_card_freshness.py::test_embedding_card_is_tracked | vermelho | verde | OK |
| tests/test_rate_card_freshness.py::test_guard_fails_nine_days_before_expiry | verde | verde | FAIL: nao prova a mudanca |
| tests/test_rate_card_freshness.py::test_guard_fails_when_already_stale | verde | verde | FAIL: nao prova a mudanca |
| tests/test_rate_card_freshness.py::test_guard_names_the_card_and_days_left | vermelho | verde | OK |
| tests/test_rate_card_freshness.py::test_guard_passes_eleven_days_before_expiry | verde | verde | FAIL: nao prova a mudanca |
| tests/test_rate_card_freshness.py::test_installed_rate_cards_not_near_expiry | vermelho | verde | OK |
| tests/test_rate_card_freshness.py::test_real_clock_only_in_freshness_guard | verde | verde | FAIL: nao prova a mudanca |
| tests/test_shard_pricing.py::test_quote_usage_rejects_event_with_previous_card_version | verde | verde | FAIL: nao prova a mudanca |
| tests/test_shard_pricing.py::test_version_row_pinned_to_old_card_is_rejected_after_renewal | vermelho | verde | OK |

red_green: 21/29 OK

Os 8 verde/verde são controles por desenho, não falta de prova:
- contrato preservado: `ok_with_fresh_cards`, `other_blocking_alert_does_not_fail`;
- imutabilidade dos antigos: `old_cards_are_byte_identical`;
- caracterização da armadilha 3, que vale também na `main`: `quote_usage_rejects_event_with_previous_card_version`;
- os simulados do guarda, cujo helper de asserção mora no próprio arquivo de teste: `nine_days`, `already_stale`, `eleven_days`, `real_clock_only`.

Desvio menor da spec: o `…nine_days…` não fica vermelho na `main` porque mira o card `image`. A prova de "embedding ausente" é o `…names_the_card_and_days_left`, que é vermelho na `main`. No `land_check`, o coordenador passa esses 8 por `--allow-green`.

Testes focados (`pt.sh`, `-n 2`) em 16 arquivos: `test_rate_card_freshness`, `test_finops_stale_card_cron`, `test_pricing_card_files`, `test_publish_rate_card`, `test_shard_pricing`, `test_spec196_finops`, `test_spec197_daily_cap`, `test_bug_finops_wallet_jobs`, `test_spec192_vercel_env`, `test_spec192_cron_endpoints`, `test_local_pricing_fixture`, `test_image_pricing`, `test_spec237_embedding_pricing`, `test_spec352_creature_portraits`, `test_speech_to_text`, `test_size_budget`. Resultado: **298 passed, 2 skipped**.

Sonda da regex do R3 (script no scratchpad, fora do repo): pega a mesma linha; **não** pega duas linhas, `require_paid_effect('image')` sem `now`, `require_image_prices(M, datetime.now(UTC))` nem o cron sem fixar os cards (P2-2).

## Correções aplicadas

Nenhuma ainda: o revisor não edita código.

## Pendências

- P2-1 (publicador confere a linha e os 2 profiles): coordenador/executor, de preferência **antes** de rodar `publish_rate_card.py` no staging. Se não for feito, o passo 4 do README é obrigatório.
- P2-2 (heurística do guarda + registrar o desvio na spec): follow-up de testes, sem urgência.
- P2-3 (runbook cita FX no alerta do cron; decisão para produção): uma frase agora e um item no checklist de go da SPEC-197.
- P2-4 e P2-5: nits de texto e teste.
- Pendente da própria spec, fora desta revisão: publicação no staging, `vercel_env.py`, deploy, smoke §6 e a suíte completa 1× no pouso.
- ESTADO: avisar que, depois do pouso, `vercel_env.py` e os smokes de staging apontam para `spec409-staging-2026-11-13*` e que a ordem é publicar → env → deploy. Qualquer outra ordem falha fechada (503 em imagem, STT e compra, como hoje) sem dano de dado.

## Comandos rodados

```text
git log/diff 48da95ab..HEAD (stat, services, scripts, tests, docs) → 5 commits, 33 arquivos lidos nos trechos alterados
diff cards antigos × novos; git diff --quiet (48da95ab e main) nos 4 antigos → só version/observed_at/source mudam; antigos intactos
sha256sum data/pricing/*.json → batem com OLD_CARD_SHA256 e com o README
bash scripts/dev/red_green.sh 409 → red_green: 21/29 OK (8 controles verde/verde justificados acima)
bash scripts/dev/pt.sh <16 arquivos> → 298 passed, 2 skipped
bash scripts/dev/py.sh scratchpad/probe.py (regex do R3) → mesma linha True; 4 casos de escape False
bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff 48da95ab..HEAD → só `publish` (homônimo sem relação)
ruff check / ruff format --check nos arquivos tocados → limpos
```
