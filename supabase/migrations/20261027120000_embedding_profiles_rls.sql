-- SPEC-343 R8: app.embedding_profiles era a única tabela de `app` sem RLS.
-- Tabela de configuração (sem PII): leitura por rpg_api preservada, sem escrita por clientes.
alter table app.embedding_profiles enable row level security;
alter table app.embedding_profiles force row level security;
revoke all on app.embedding_profiles from public, anon, authenticated;
grant select on app.embedding_profiles to rpg_api;
drop policy if exists embedding_profiles_read on app.embedding_profiles;
create policy embedding_profiles_read on app.embedding_profiles
  for select to rpg_api using (true);
