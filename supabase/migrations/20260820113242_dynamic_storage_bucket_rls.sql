-- Bucket privado para arte dinâmica. O backend usa service role; estas policies
-- preservam defesa em profundidade caso uploads/downloads assinados sejam
-- habilitados no futuro. A chave canônica começa com users/<owner UUID>/.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'rpg-dynamic',
  'rpg-dynamic',
  false,
  20971520,
  array['image/webp']::text[]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy rpg_dynamic_select_own
on storage.objects for select to authenticated
using (
  bucket_id = 'rpg-dynamic'
  and (storage.foldername(name))[1] = 'users'
  and (storage.foldername(name))[2] = (select auth.uid())::text
);

create policy rpg_dynamic_insert_own
on storage.objects for insert to authenticated
with check (
  bucket_id = 'rpg-dynamic'
  and (storage.foldername(name))[1] = 'users'
  and (storage.foldername(name))[2] = (select auth.uid())::text
);

create policy rpg_dynamic_update_own
on storage.objects for update to authenticated
using (
  bucket_id = 'rpg-dynamic'
  and (storage.foldername(name))[1] = 'users'
  and (storage.foldername(name))[2] = (select auth.uid())::text
)
with check (
  bucket_id = 'rpg-dynamic'
  and (storage.foldername(name))[1] = 'users'
  and (storage.foldername(name))[2] = (select auth.uid())::text
);

create policy rpg_dynamic_delete_own
on storage.objects for delete to authenticated
using (
  bucket_id = 'rpg-dynamic'
  and (storage.foldername(name))[1] = 'users'
  and (storage.foldername(name))[2] = (select auth.uid())::text
);
