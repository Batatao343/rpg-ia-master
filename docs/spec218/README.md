# SPEC-218 - evidencia

## O que mudou
- `infrastructure/runtime.py`: `exposure_markers`, `assert_boot_policy`, `HOSTED_SECURITY_REQUIREMENTS`
  (+ `HOSTED_REQUIRED_ENV`, `FORBIDDEN_IN_HOSTED`), `hosted_security_problems`, `is_hardened`, `docs_enabled`,
  `kill_switch_fail_closed_default`. `RuntimeConfig.from_env` agrega todos os motivos num unico
  `ValueError("hosted_config_insecure: ...")` (so nomes/motivos, nunca valores). `apply_serverless_defaults`
  faz `setdefault(RPG_NO_MOCK, 1)` em hosted*.
- `api.py`: `assert_boot_policy` no import (antes de criar o app); docs/redoc/openapi off em portable/hosted*
  salvo `RPG_EXPOSE_OPENAPI=1`; CORS com metodos/headers explicitos; cron router fora do schema;
  `/health` com `profile` e `hardened`.
- `services/kill_switches.py`: default fail-closed `image_generation,stt_fallback_expensive` em hosted* quando a env
  esta AUSENTE (env explicita, inclusive vazia, vence; compras seguem fail-open).
- `scripts/release/checklist.py`, `scripts/cloud_doctor.py`, `scripts/post_deploy_smoke.py`: usam a fonte unica.
- `Procfile` em loopback por default (`RPG_BIND_HOST`); `.env.example`; `tests/conftest.py` limpa marcadores.

## Testes
`tests/test_boot_policy.py` (novo, ~85 casos: boot exposto, bypass de PORT/bind loopback, cada requirement positivo e
negativo, override de laboratorio, paridade checklist, doctor sem valores, kill switch, docs, health, CORS).
Fixtures de `test_hosted_supabase_contract.py`/`test_spec192_vercel_env.py`/`test_ci_eval_gates.py` atualizadas.
Smoke local: `PORT=8000 python -c "import api"` -> `RuntimeError: legacy_profile_exposed: markers=PORT ...`
(sem valores); sem `PORT`, loopback sobe normalmente.

## Decisoes (defaults da spec)
D-A incluir `PORT`; D-B limite aceito (processo sem NENHUM marcador e bind manual 0.0.0.0 e responsabilidade do operador);
D-C docs off em todo perfil hosted/portable, `RPG_EXPOSE_OPENAPI` so staging; D-D compras seguem fail-open.
Desvio: `local` mantem docs ligados (spec R6 diz "legacy/local nada muda"); `portable` desliga.

## Pendente (nao feito aqui)
- Staging Vercel: o redeploy so passa no boot com `RPG_TELEMETRY_SECRET` (>=32), SEM `RPG_FORCE_MOCK` (hoje
  `scripts/staging/vercel_env.py` o seta) e com chave de provider ou `RPG_NO_MOCK=1`; sem isso o boot falha de
  proposito. Ajustar env remota + `vercel_env.py` e verificar `/health` (`hardened=true`), `/openapi.json` 404.
- Revisao Astra independente, `checklist --env staging` contra `.env.staging`, atualizar risk-register da SPEC-197.
- Evidencia vermelha da Etapa 0 no HEAD nao foi capturada separadamente (testes escritos junto da implementacao).

## Revisao Astra independente (2026-10-17)
Parecer: `handoffs/SPEC-218-ASTRA-independent-review.md` (APPROVED com correcoes). Correcoes: conftest limpa marcadores
no import (coleta importa `api`); marcadores `DYNO` e `RPG_HOST`; fixture portable com OIDC completo (SPEC-220).
Staging ainda precisa de `RPG_TELEMETRY_SECRET` e de remover `RPG_FORCE_MOCK` de `scripts/staging/vercel_env.py`.
