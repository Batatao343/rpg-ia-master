# SPEC-191 — handoff de retomada do staging Supabase

**Estado em 14/10/2026:** `approved`, execução remota suspensa a pedido do
usuário. A SPEC-190 está `done` (`13d5f87`). O usuário autorizou Sol High como
executor substituto de Terra High e a criação de um projeto novo com custo
informado de US$ 0/mês, mas suspendeu a implementação após o bloqueio de cota.
Nenhum projeto, migration, usuário, bucket ou configuração cloud da SPEC-191 foi
criado ou alterado. Não marcar a spec `done` nem avançar à SPEC-192.

## Bloqueio da criação

- Organização escolhida: `jm0nteiroz` (`xhvlcfmmnzcngwhkxkqi`), plano Free.
  Projeto proposto: `rpg-ia-master-staging`, região `sa-east-1`, exclusivo de
  staging. O conector confirmou custo de criação de **US$ 0/mês**; consumo e
  limites do plano continuam aplicáveis.
- `supabase_create_project` foi chamado uma vez com a confirmação de custo.
  Retornou `BadRequestException`: um membro administrador atingiu o limite de
  **dois projetos Free ativos**. O limite agrega os projetos de organizações em que a pessoa é
  Owner/Admin, conforme a [FAQ de cobrança](https://supabase.com/docs/guides/platform/billing-faq).
- Não pausar, excluir, transferir, alterar papéis nem fazer upgrade de nenhum
  projeto existente para abrir vaga. `uzeagzcyvxzrpjgrhaql` continua sem
  permissão; não o usar. A próxima tentativa de criação depende da escolha do
  usuário sobre cota/organização e de nova confirmação de custo válida.

## Inventário local confirmado

- `supabase/migrations/` contém 16 migrations versionadas, de
  `20260819001305_game_store.sql` a `20261013173632_account_lifecycle.sql`.
  `supabase/config.toml` é configuração **local**; não aplica Auth/CAPTCHA,
  SMTP nem rate limits ao hosted. `supabase/tests/valoria_rls_test.sql` contém
  14 assertions pgTAP sobre role tenant, RLS, bucket privado e policies.
- O perfil `hosted-supabase` da SPEC-181 exige URL/API/chaves e **Transaction
  pooler** na porta 6543 com `sslmode=require|verify-full`; o ref da API e do
  DSN deve coincidir. Copiar o DSN do painel, sem construir hostname regional.
  O pool padrão por instância é 0..1 e desativa prepared statements. O
  `cloud_doctor` é apenas validador offline de env, não prova conexão.
- A SPEC-190 exige `RPG_AUTH_CAPTCHA_MODE=gotrue` e
  `RPG_AUTH_CAPTCHA_REQUIRED=1` no hosted, além de Turnstile **nativo no
  Supabase Auth**. Provar chamadas diretas a GoTrue sem token para
  signup/recover/resend e chamadas com token novo encaminhado pelo proxy.
  O proxy sozinho não cobre a API pública de Auth.
- Nesta sessão não há `SUPABASE_ACCESS_TOKEN`, senha do banco, chaves do novo
  projeto, CLI `supabase`, `psql` nem `pg_dump` disponíveis. Docker local
  respondeu `permission denied` ao pipe. Um `uv run pytest` focado inicialmente
  falhou por acesso negado ao cache global do uv; a repetição com
  `UV_CACHE_DIR` no workspace iniciou com erros de fixture e não concluiu.
  Nenhum teste foi declarado verde.

## Cuidados atuais da plataforma

- [Projetos Free novos com SMTP padrão não podem personalizar templates de
  email](https://supabase.com/changelog/46599-changes-to-email-template-customisation-on-free-tier).
  Para os templates de confirmação/reset da SPEC-190, custom SMTP ou plano com
  personalização é gate de release; o SMTP padrão pode servir só ao smoke de
  staging compatível com templates padrão.
- [Tabelas `public` novas não são expostas automaticamente à Data API](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically).
  Conferir grants explícitos e RLS antes de assumir acesso por PostgREST. O
  schema `app` permanece privado; os views `public` de wallet precisam do
  grant previsto na migration.
- [Backups do plano Free](https://supabase.com/docs/guides/platform/backups)
  exigem exportação própria com `supabase db dump`; backup do Postgres não
  contém bytes dos objetos Storage. O restore da SPEC-191 deve testar dados
  **e objetos sintéticos** em ambiente descartável, sem usar projeto pessoal.
- [Rate limits nativos de Auth](https://supabase.com/docs/guides/auth/rate-limits)
  são configurados no painel/API de gestão. Medir a consequência de IP de saída
  compartilhado do backend antes de definir limites; não substituir esse gate
  pela limitação do proxy. O adapter atual envia chave publishable nesses
  endpoints e não envia `Sb-Forwarded-For`; o encaminhamento de IP do cliente
  requer chave secret moderna e habilitação específica no Supabase. Não assumir
  que o IP do cliente chega ao Auth nativo com a configuração atual.

## Retomada após resolução da cota

1. Confirmar org e custo com o usuário; criar **novo** projeto de staging e
   registrar apenas o ref/ID não secreto. Não tocar nos projetos existentes.
2. Obter acesso seguro à CLI/credenciais e executar as migrations versionadas
   em ordem desde zero. Conferir `supabase_migrations.schema_migrations`, schema,
   roles e `supabase/tests/valoria_rls_test.sql`; não usar mudanças manuais como
   fonte da verdade. Rodar Security/Performance Advisors após DDL.
3. Configurar Auth email confirmation, CAPTCHA Turnstile nativo, rate limits,
   redirect URLs e SMTP conforme a capacidade do plano. Fazer matriz A/B real
   com dois usuários sintéticos: Auth, RLS no schema `app`, pgvector, Storage
   privado e signed URLs. Testar endpoints Auth diretos sem CAPTCHA e via proxy
   com token válido; registrar impacto de IP compartilhado sem expor tokens.
4. Validar `hosted-supabase` com a mesma DSN transacional/SSL da SPEC-192,
   `cloud_doctor` e conexão/query reais. Exportar DB e bytes Storage sintéticos,
   restaurar em ambiente descartável e comparar contagens/checksums.
5. Registrar advisors com links de remediação, config/custo/IDs não secretos,
   comandos, resultados e limitações em `docs/spec191/`. Rodar testes focados
   durante a execução; suíte completa só no gate pré-commit com o root.
   Solicitar **outro Sol High** para revisão independente antes de `done`.

Não recarregar modelos de IA, não executar long-runs e não publicar secrets em
logs, arquivos versionados ou tickets.
