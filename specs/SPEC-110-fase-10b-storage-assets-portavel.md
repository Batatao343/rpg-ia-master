# SPEC — Fase 10b.6 — Storage portátil para assets dinâmicos

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [turnos/fila](SPEC-111-fase-10b-turnos-duraveis-concorrencia-fila.md) `done` · [Auth/RLS](SPEC-103-fase-10b-auth-rls-isolamento.md) `done` · [pgvector](SPEC-107-fase-10b-pgvector-memoria-transacional.md) `done`
> **Desbloqueia:** Fase 8B (arte dinâmica), cleanup por usuário e certificação de object storage

---

## 1. Contexto & Objetivo

A Fase 8A já serve 90 WebPs curados e versionados em `web/public/art/v1`, com
catálogo/hash/visibilidade. Esses arquivos não precisam de banco ou bucket. A
lacuna é futura: imagens geradas para NPCs, monstros e itens não podem ser
gravadas no filesystem efêmero da API nem ficar sem owner, quota, moderação,
proveniência ou cleanup.

Esta spec implementa apenas o substrato de storage e lifecycle. `BlobStore`
possui adapters File, Supabase Storage local e S3 compatível. A geração/seleção
artística da Fase 8B será outra spec e consumirá jobs tipados.

## 2. Requisitos

- **R1 — arte curada intacta:** catálogo e WebPs atuais continuam estáticos;
  nenhum upload/migração obrigatória desses 15,86 MiB.
- **R2 — BlobStore portátil:** mesma suíte de contrato para arquivo temporário,
  Supabase Storage local e adapter S3 compatível; domínio não importa SDK de provider.
- **R3 — bucket privado:** asset dinâmico é privado por default; leitura ocorre
  por URL curta assinada ou proxy autenticado após owner/visibility gate.
- **R4 — identidade canônica:** metadata liga `owner_id`, `game_id`, `entity_id`,
  `asset_id`, tipo, variante, hash, dimensões e proveniência. A LLM nunca escolhe object key.
- **R5 — pipeline Python:** valida MIME por conteúdo, decode Pillow, limites de
  pixels/bytes, remove metadata, converte variantes WebP e calcula SHA-256 antes de ready.
- **R6 — dedupe scoped:** conteúdo igual do mesmo owner/purpose reutiliza blob;
  dedupe global não revela existência/hash de objeto de outro usuário.
- **R7 — lifecycle compensável:** DB e object storage não têm transação comum;
  estados `pending_upload → ready` e `delete_pending → deleted|orphaned` com jobs
  idempotentes garantem reconciliação.
- **R8 — upload direto controlado:** se adotado, URL assinada restringe key,
  MIME, tamanho e expiração; finalize revalida bytes no servidor. Nunca aceitar key do cliente.
- **R9 — segredo visual:** NPC/local/item hidden/secret só gera/serve depois do
  reveal canônico; URL assinada curta não aparece em logs/telemetria persistente.
- **R10 — quota/retenção:** limites por owner/game e políticas de expiração são
  calculados em Python e reforçados por constraints/jobs; sem exclusão silenciosa de asset em uso.
- **R11 — RLS/ownership:** metadata e `storage.objects` permitem apenas owner;
  service role backend não substitui testes de autorização. Upsert possui policies
  completas de INSERT/SELECT/UPDATE ou é evitado.
- **R12 — backup:** manifest de assets contém hashes/keys/metadata; backup de DB
  não é tratado como backup de objetos.
- **R13 — API estável:** `VisualAssetResponse` diferencia static URL e signed
  dynamic URL sem expor provider/object key; expiração permite refresh.

### Fora de escopo

- Chamar modelo de imagem, escolher prompt, estilo ou política de moderação final.
- Mover assets curados/CDN para Supabase.
- Upload de avatar/documento arbitrário pelo usuário.
- CDN custom, transformação proprietária e cobrança real.

## 3. Design técnico

### Arquivos novos

- `infrastructure/file_blob.py` — adapter de referência temporário.
- `infrastructure/supabase_blob.py` — Storage API por `httpx`.
- `infrastructure/s3_blob.py` — adapter opcional S3 compatível.
- `services/asset_pipeline.py` — validação, variantes, metadata e lifecycle.
- `workers/asset_jobs.py` — finalize/reconcile/delete handlers.
- `supabase/migrations/<ts>_assets_storage.sql` — tabela/RLS/bucket policies.
- `scripts/reconcile_assets.py` — preview/reparo de órfãos.
- `scripts/export_asset_manifest.py` — backup verificável.
- `tests/test_blob_contract.py`, `tests/test_asset_pipeline.py`.
- `tests/test_storage_local.py` — contrato Supabase/RLS marcado `infra_local`.

### Arquivos alterados

- `services/visual_catalog.py` — view composta static+dynamic sem escolher por nome.
- `api.py` — metadata/refresh URL autenticados; sem upload livre.
- `web/src/types.ts`, `SceneArtwork.tsx`, `VisualArtwork.tsx` — URL expira/refresh/fallback.
- `scripts/dev_stack.py`, `supabase/config.toml`, `.env.example` — bucket local/limites.

### Schema

```sql
create table app.assets (
  id uuid primary key,
  owner_id uuid not null,
  game_id uuid not null references app.games(id) on delete cascade,
  entity_id text not null,
  asset_kind text not null check (asset_kind in ('npc','location','item','monster')),
  variant text not null check (variant in ('full','thumb')),
  status text not null check (status in ('pending_upload','processing','ready','rejected','delete_pending','deleted','orphaned')),
  visibility text not null check (visibility in ('public','hidden','secret')),
  bucket text not null,
  object_key text not null,
  mime_type text not null,
  bytes bigint not null check (bytes >= 0),
  width integer not null check (width > 0),
  height integer not null check (height > 0),
  sha256 text not null check (length(sha256)=64),
  source_provider text,
  source_model text,
  prompt_sha256 text,
  moderation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  ready_at timestamptz,
  deleted_at timestamptz,
  unique (owner_id, game_id, entity_id, variant, sha256)
);
```

Object key é gerada pelo servidor:

```text
users/{owner_id}/games/{game_id}/{asset_kind}/{entity_id}/{asset_id}.{variant}.{sha12}.webp
```

`entity_id` passa pelo resolver canônico e key usa componentes sanitizados; a
autorização vem das colunas, não de confiar no prefixo.

### Pipeline

```text
job tipado → bytes temporários → validate/decode/strip → variantes+hashes
→ put em key final idempotente → transação metadata ready
→ falha entre blob/DB: reconcile encontra por pending/object hash
→ delete: marcar delete_pending → apagar blobs → marcar deleted
```

Pillow usa limites explícitos e trata decompression bomb como rejeição. Arquivo
temporário vive apenas em diretório efêmero controlado e é removido no `finally`.

### Contrato de resposta

```python
class DynamicVisualRef(BaseModel):
    asset_id: UUID
    url: str
    expires_at: datetime | None
    width: int
    height: int
    mime_type: Literal["image/webp"]
    alt: str
    source: Literal["static", "dynamic"]
```

Provider, bucket e key ficam fora do DTO público.

## 4. Plano passo a passo

### Etapa 1 — Contrato BlobStore

1. **Testes** (`test_blob_contract.py`): put/get-url/delete/idempotência, key
   traversal, hash errado, streams grandes, erro provider e isolamento.
2. **Implementação:** File adapter + suite compartilhada.
3. **Verificação:** zero mudança na arte curada.

### Etapa 2 — Pipeline/lifecycle

1. **Testes** (`test_asset_pipeline.py`): MIME falso, bomb, metadata strip,
   variantes, dedupe, secret gate, quotas e failpoints blob↔DB.
2. **Implementação:** serviço Python e jobs.
3. **Verificação:** reconcile torna cada caso `ready|rejected|deleted`, nunca invisivelmente órfão.

### Etapa 3 — Supabase Storage local/RLS

1. **Testes** (`test_storage_local.py`): A/B select/insert/update/delete, URL
   expirada, prefix forgery, service key ausente no client e bucket privado.
2. **Implementação:** adapter httpx, bucket/policies/migrations.
3. **Verificação:** contrato File e Supabase idêntico.

### Etapa 4 — S3 portátil

1. **Testes:** mesma suite contra endpoint S3 local opcional; signed URL e delete.
2. **Implementação:** adapter atrás de extra; sem condicional no domínio.
3. **Verificação:** trocar env não muda DTO/object naming.

### Etapa 5 — API/frontend/backup

1. **Testes:** static continua byte a byte; dynamic URL refresh; fallback; export
   manifest+hash; account deletion cleanup.
2. **Implementação:** view composta e scripts.
3. **Verificação:** desktop/mobile e nenhum secret object URL em log.

## 5. Critérios de aceite

- [x] 90 WebPs/45 entradas curadas permanecem estáticos e válidos.
- [x] File, Supabase local e S3 opcional obedecem o mesmo BlobStore contract.
- [x] Bucket dinâmico é privado; A nunca acessa metadata/blob de B.
- [x] MIME/pixels/bytes/metadata/hash são validados em Python.
- [x] Secret/hidden não gera nem serve antes do reveal.
- [x] Failpoints blob↔DB são reparáveis por reconcile idempotente.
- [x] Backup/restore de manifest+objetos valida todos hashes.
- [x] API não expõe provider, bucket, key ou service credential.
- [x] Perfil hosted não grava asset persistente no filesystem da API.
- [x] `uv run pytest -m infra_local`, build Vite e suíte offline verdes.
- [x] Guard de FallbackLLM — N/A; nenhum invoke novo.
- [x] Assets/saves antigos continuam funcionando sem migração.

## 6. Smoke test com LLM real

Zero LLM/imagem. Usar uma fixture PNG: job converte e publica duas variantes no
Storage local; owner vê, outro usuário recebe 404; URL expira e é renovada; delete
remove blobs/metadata conforme lifecycle. Arte estática continua na mesma URL.

## 7. Riscos & compatibilidade

- **DB/object sem transação comum:** estado explícito+reconcile, nunca “best effort” oculto.
- **URL assinada vazada:** TTL curto, sem log e visibility gate antes de emitir.
- **Dedupe e privacidade:** não retornar indicação de hash existente fora do owner.
- **Provider lock-in:** domínio conhece somente BlobStore e object key própria.
