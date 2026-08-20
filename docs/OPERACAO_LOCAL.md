# Operação local — Valoria

Este runbook cobre o laboratório sem custo de infraestrutura externa. Ele usa
Supabase Local/Docker e MockLLM; nenhuma etapa cria projeto remoto.

## Bootstrap seguro

```powershell
$env:Path="$env:APPDATA\Python\Python314\Scripts;$env:Path"
$env:UV_PROJECT_ENVIRONMENT="$env:LOCALAPPDATA\valoria-venv-py313"
uv run python scripts/dev_stack.py doctor
uv run python scripts/dev_stack.py start
uv run python scripts/dev_stack.py status
```

`reset --confirm-local` apaga somente o banco/Storage do laboratório local. Faça
backup antes quando houver fixtures que devam ser preservadas. Nunca use
`supabase link`, `--linked` ou um DSN remoto nos gates locais.

## Gates de prontidão

```powershell
uv run pytest
uv run pytest -m infra_local
uv run pytest -m security_local
uv run pytest -m chaos_local
uv run python scripts/load_test.py
uv run python -m playtest run --all --turns 77
```

O soak deve totalizar pelo menos 1.000 turnos e registrar zero erro/violação
`error`. Build/lint/conteúdo e browser desktop+390 px compõem G7. Registre cada
resultado com `scripts/readiness_report.py record` e finalize com `build`.

## Backup e restore

```powershell
uv run python scripts/backup_local.py <diretorio-novo> --confirm-local
uv run python scripts/restore_local.py <backup> --confirm-local-empty-target
uv run python scripts/verify_restore.py
```

O backup só é válido com `manifest.json` íntegro, dumps `app` + dados de
`auth/storage` e o diretório de objetos. O restore é destrutivo apenas no alvo
local explicitamente confirmado. O objetivo é RPO zero para turnos confirmados
e RTO menor ou igual a 30 minutos.

## Observabilidade opcional

```powershell
uv sync --extra observability
docker compose -f infra/observability.compose.yml up -d
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://127.0.0.1:54318/v1/traces"
uv run uvicorn api:app --host 127.0.0.1 --port 8000
```

Prometheus fica em `http://127.0.0.1:59090`, Grafana em
`http://127.0.0.1:53000` e Tempo em `http://127.0.0.1:53200`. As imagens têm
limites locais de CPU/RAM e os volumes são dedicados. A ausência do endpoint ou
do extra OTel desativa traces sem derrubar request/turno; métricas em `/metrics`
continuam disponíveis. Valide regras com:

```powershell
docker exec infra-prometheus-1 promtool check rules /etc/prometheus/alerts/local.yml
docker exec -w /etc/prometheus/alerts infra-prometheus-1 promtool test rules local.test.yml
```

Ao terminar, `docker compose -f infra/observability.compose.yml down` libera os
recursos e preserva volumes; acrescente `-v` apenas se quiser apagar o histórico.

## Incidentes e caos

- API caiu antes do commit: repita o mesmo `action_id`; receipt/idempotência
  impede avanço duplicado.
- Worker morreu com job `running`: após expirar o lease, outro worker assume;
  o fencing token antigo não pode confirmar.
- Operação ficou presa: rode `scripts/recover_operations.py` em modo de inspeção
  e abandone somente leases expirados.
- Embedding/blob indisponível: o turno confirmado permanece canônico; o job
  converge por retry ou dead-letter sem inventar sucesso.
- Banco reiniciado: aguarde health, reinicie API/worker e repita a mesma chave;
  nunca remova receipts manualmente.
- Backup inválido: não restaure; preserve fonte e artefato corrompido para
  diagnóstico, gere novo backup e valide hashes.

## Segurança

O frontend nunca recebe service role. Assets dinâmicos ficam no bucket privado
`rpg-dynamic`, com chave `users/<owner>/games/<game>/...`. O gameplay usa FastAPI;
RLS é defesa em profundidade. Logs e relatórios não podem conter JWT, e-mail,
ação, narrativa, prompt ou URL assinada.

## Perfil portátil

`portable` usa Postgres+pgvector, S3 compatível e OIDC UserInfo. Configure
`RPG_OIDC_USERINFO_URL`, `RPG_OIDC_ISSUER`, `RPG_S3_BUCKET` e credenciais S3 do
ambiente. Password grant do Supabase não faz parte desse perfil; login/PKCE será
certificado somente na futura spec cloud, após autorização e orçamento.
