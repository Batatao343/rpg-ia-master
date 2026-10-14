# SPEC-191 — revisão independente do preparo local

**14/10/2026 · Sol High · decisão: preflight revisado, sem aprovação final.** A execução remota está suspensa a pedido do usuário após a criação de `rpg-ia-master-staging` ser recusada pela cota Free. Revisei o diff documental (`ESTADO_ATUAL.md`, `ROADMAP.md`, `handoffs/SPEC-191-Terra-review.md`), a SPEC-191 e os contratos locais de migrations, Auth, RLS, Storage, pgvector e pooler. Não houve mudança de código nesta preparação. SPEC-191 deve permanecer `approved`; nenhum critério cloud foi demonstrado.

## Achados do preflight

- O handoff agora registra a dependência SPEC-190 `done`, a tentativa recusada, a ausência de recursos novos e a sequência de retomada. `supabase/config.toml` configura o laboratório local; não configura automaticamente CAPTCHA, SMTP ou limites do Auth hospedado. As 16 migrations versionadas ainda precisam ser aplicadas e verificadas **desde zero** no projeto novo.
- `infrastructure/supabase_identity.py` usa publishable key para signup/recover/resend e não encaminha `Sb-Forwarded-For`. O efeito do IP de saída compartilhado sobre os limites nativos permanece um gate remoto; o handoff o trata corretamente. A [documentação de rate limits](https://supabase.com/docs/guides/auth/rate-limits) exige secret API key moderna e opt-in para encaminhar IP; publishable e `service_role` legado não bastam.
- `infrastructure/runtime.py` e `infrastructure/postgres.py` validam a forma da DSN transacional em 6543, TLS e prepared statements desativados; `scripts/cloud_doctor.py` não abre conexão. A mesma DSN/SSL da SPEC-192 ainda precisa provar uma query real. A [documentação de conexão](https://supabase.com/docs/guides/database/connecting-to-postgres) recomenda pool transacional para serverless e conexão direta ou pool de sessão para dump/restore.
- O teste local de Storage prova leitura privada A/B e URL assinada acessível, mas não prova sua expiração. Os testes locais de RLS/pgvector usam Postgres local; não substituem dois usuários Auth reais no staging. O [backup de banco](https://supabase.com/docs/guides/platform/backups) não inclui bytes de Storage; o restore deve conferir objetos e hashes além das linhas.

## Pendências para revisão final

Após a resolução da cota: projeto exclusivo e migrations reproduzidas; dois usuários A/B reais em Auth, RLS, Storage e pgvector; CAPTCHA nativo e limites verificados por chamadas diretas e pelo proxy; Security/Performance Advisors; pooler/SSL real; export e restore descartável com objetos; evidências sem secrets e testes completos coordenados pelo root. Nenhum desses gates recebeu aprovação nesta revisão. Não avançar à SPEC-192 por este parecer.
