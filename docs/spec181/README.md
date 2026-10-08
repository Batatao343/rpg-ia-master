# SPEC-181 — contrato hosted Supabase para Vercel

Data local: 2026-10-08. Nenhum projeto, tabela, bucket, usuário ou recurso
remoto foi criado.

## Topologia e fronteiras

`hosted` e `portable` continuam **OIDC + S3**. `local` continua **Supabase
local**. O novo `RPG_RUNTIME_PROFILE=hosted-supabase` escolhe Postgres/pgvector,
catálogo/fila/rate limit Postgres, Supabase Auth e Supabase Storage. Não há
branch novo no GameState ou nas mecânicas.

Ao partir de uma cópia de `.env.example`, remova os overrides ativos do perfil
`legacy` (`RPG_GAME_STORE`, `RPG_MEMORY_STORE`, `RPG_RUNTIME_CATALOG`,
`RPG_BLOB_STORE`, `RPG_JOB_QUEUE`, `RPG_RATE_LIMIT_STORE`, `RPG_AUTH_MODE`) para
usar os defaults do novo perfil, ou ajuste todos explicitamente. Também defina
`RPG_BIND_HOST=0.0.0.0`. O doctor informa qual seletor herdado está inválido.

`hosted-supabase` exige bind de serviço explícito, API HTTPS de projeto
Supabase, publishable key, chave elevada distinta e DSN transacional Supabase
em porta 6543. O project ref do DSN e da API precisa coincidir. Recusa
loopback, filesystem BlobStore, auth disabled/OIDC, DSN direto/sessão,
credenciais ausentes, `sslmode` fraco e pool fora dos limites. Para conectar,
copie o DSN de **Transaction pooler** do painel; não fabrique o hostname da
região.
No DSN hosted-Supabase, somente `sslmode=require|verify-full` pode aparecer na
query, uma vez; `host`, `hostaddr`, `port`, `user`, `service` e demais overrides
libpq são recusados. O perfil `hosted` OIDC/S3 também exige URL Postgres com
autoridade e recusa overrides de destino. JWT `service_role` legado tem role e
project ref conferidos estruturalmente; a validade criptográfica continua a
cargo do Supabase.

O pool por instância warm inicia em 0 e tem máximo 1 por padrão;
`RPG_DB_POOL_MIN_SIZE`, `RPG_DB_POOL_MAX_SIZE` (1–4) e
`RPG_DB_POOL_TIMEOUT_SECONDS` (0,1–30) podem ajustá-lo. `prepare_threshold=None`
evita prepared statements incompatíveis com modo transacional;
`sslmode=require` é forçado, preservando `verify-full` quando escolhido.
Cada checkout transacional abre `SET LOCAL` para `statement_timeout=15s` e
`lock_timeout=5s`, que expiram junto com a transação e não vazam entre clientes.
`reset_runtime()` fecha o pool compartilhado. [Guia oficial de conexão](https://supabase.com/docs/guides/database/connecting-to-postgres),
[Psycopg prepared statements](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html).

A chave publishable autentica o componente no Supabase Auth; o backend
continua verificando o JWT do usuário no endpoint `/auth/v1/user`, e o
Postgres aplica ownership/RLS do fluxo existente. A chave elevada fica só no
backend para Storage. `sb_secret_` (que mapeia para service_role) vai apenas no
header `apikey`; o `service_role` JWT legado conserva também `Authorization:
Bearer`. O frontend não recebe chave elevada, DSN ou segredo. [Guia oficial de
API keys](https://supabase.com/docs/guides/getting-started/api-keys).

## Diagnóstico seguro

`uv run python -m scripts.cloud_doctor` lê somente env e valida perfil,
presença de nomes obrigatórios, formato do DSN e contrato de config. O JSON
inclui apenas nomes/status (`present|missing|valid|invalid`) e o perfil
permitido; nunca imprime valores, host, project ref, senha ou texto de exceção.
Não testa reachability, validade remota de credenciais nem cria recursos.
Teste com sentinelas verificou ausência de todos os valores no stdout.

## Verificação

- Reprodução inicial: `hosted + supabase auth` falhava em “exige auth OIDC”.
- Matriz offline cobre defaults legados, hosted OIDC/S3, perfil novo,
  incompatibilidades de auth/storage, secrets e DSN, pool kwargs e wiring de
  Auth/Storage com um único pool. Testes de headers cobrem chave moderna e
  `service_role` JWT legado.
- Integração local real: 8 workers × 16 tarefas contra Postgres em
  `127.0.0.1:55322`, pool `max_size=2`, pico observado = **2**; nenhuma
  conexão cloud. O teste é `infra_local` opt-in.
- `cloud_doctor` é read-only; não há migração SQL nem mudança de esquema.

Revisão Sol High independente e gates finais serão registrados no fechamento.
