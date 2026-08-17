# SPEC — Fase 10b — Plano mestre local-first para prontidão de produção

> **Status:** `draft`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [Fase 10 — hardening técnico](fase-10-hardening-tecnico.md) `done` · [hardening de persistência/SSE](hardening-persistencia-sse-idempotencia.md) `done`
> **Desbloqueia:** implementação ordenada da Fase 10b e, somente depois, certificação em infraestrutura externa

---

## 1. Contexto & Objetivo

O motor de jogo, o frontend e a validação de produto já têm cobertura ampla e
playtests longos. O que impede uma avaliação `production-ready` não é mais a
mecânica: é o data plane local. Hoje `persistence.py` grava o `GameState` v7 e
checkpoints em JSON; `rag.py` grava FAISS por sessão/NPC; `api.py` serializa
mutações com `threading.RLock`; o browser identifica a campanha apenas por um
UUID em `localStorage`; e quatro overlays (`npc_database`, `bestiary_runtime`,
`custom_artifacts`, `bestiary_knowledge`) ainda escrevem no filesystem.

Esta spec é o mapa mestre, não uma autorização para implementar tudo de uma
vez. Ela divide a Fase 10b em fatias testáveis localmente, sem publicar serviço,
comprar banco ou exigir chave de LLM. Supabase Local é o alvo primário de
compatibilidade porque reúne Postgres, Auth e Storage em Docker, mas o código de
domínio dependerá de portas Python, não da SDK ou de tabelas proprietárias. O
mesmo núcleo deverá operar com Postgres+pgvector e storage S3 compatível.

Princípios: **mecânica continua em Python**, infraestrutura é substituível,
estado confirmado tem uma única fonte de verdade por ambiente, e nenhum perfil
de API pública pode depender de disco persistente do processo.

## 2. Requisitos

- **R1 — mapa completo:** toda escrita mutável do jogo deve ser classificada e
  atribuída a uma spec: estado/checkpoint, memória vetorial, cache de entidades,
  conhecimento por usuário, assets, jobs ou telemetria.
- **R2 — perfis explícitos:** `legacy` mantém JSON+FAISS para CLI/suíte;
  `local` usa serviços locais reproduzíveis; `hosted` recusa startup se qualquer
  dado persistente estiver configurado para filesystem ou auth estiver desligada.
- **R3 — portas Python:** agentes, grafo e mecânicas não importam psycopg,
  Supabase, S3, Railway ou Vercel. `persistence.py` e `rag.py` continuam como fachadas
  compatíveis durante a migração.
- **R4 — corte sem dual-write permanente:** migração segue `exportar → importar
  → verificar → trocar configuração`; não haverá gravação simultânea indefinida
  em JSON/FAISS e Postgres/pgvector.
- **R5 — unidade de commit:** um turno confirmado persiste estado, eventos,
  memória, visual cue e recibo idempotente de maneira atômica; chamadas LLM
  podem ser repetidas antes do commit, mas um `action_id` só avança o jogo uma vez.
- **R6 — isolamento:** toda linha ou objeto mutável tem `owner_id` e, quando
  aplicável, `game_id`; conhecimento privado de uma campanha/usuário nunca vira
  cache global por acidente.
- **R7 — zero cloud no aceite local:** todas as specs anteriores à certificação
  cloud devem ser aceitas com Docker/local, MockLLM ou Ollama e sem projeto
  remoto Supabase/Railway/Vercel.
- **R8 — portabilidade verificável:** SQL, exportações e contratos não podem
  exigir PostgREST no caminho do jogo. O frontend conversa com FastAPI; o backend
  usa Postgres padrão, JWT/OIDC e BlobStore substituível.
- **R9 — dados existentes preservados:** os 1.390 arquivos históricos em
  `saves/` e os índices em `data/saves_memory/` só podem ser migrados por comando
  com preview, relatório e verificação; esta fase não autoriza limpeza automática.
- **R10 — evidência de prontidão:** a conclusão da Fase 10b exige suíte offline,
  contratos de adapters, testes RLS com dois usuários, multiworker, kill/retry,
  backup/restore, carga, caos e campanha longa sem escrita persistente no disco da API.

### Fora de escopo

- Publicar em Railway, Render, Vercel, Supabase ou qualquer servidor real.
- Comprar domínio, configurar DNS/TLS, OAuth externo, e-mail real ou billing.
- Implementar geração dinâmica de arte (Fase 8B); a Fase 10b prepara storage/fila.
- Mover a arte curada de `web/public/art/v1`: esses arquivos são imutáveis,
  versionados e adequados ao CDN do frontend.
- Alterar combate, progressão, economia, narrativa, lore ou roteamento de LLM.

## 3. Design técnico

### 3.1 Mapa do projeto e destino

| Área atual | Fonte/entrada real | Limitação para escala | Destino/spec |
|---|---|---|---|
| Estado canônico | `state.py` + `persistence.py` (`SCHEMA_VERSION=7`) | JSON inteiro, latest global, sem owner/version distribuída | [Postgres transacional](fase-10b-postgres-persistencia-transacional.md) |
| Checkpoint | `persistence.py` + `services/checkpoints.py` | JSON + cópia de diretório FAISS, sem commit único | Postgres + pgvector com watermark transacional |
| Turno REST/SSE | `api.py` `_run_turn`/`_stream_turn` | lock e ledger só no processo/save | [Turnos duráveis](fase-10b-turnos-duraveis-concorrencia-fila.md) |
| Memória | `rag.py`, `agents/archivist.py`, `services/context_builder.py` | FAISS mutável no disco; commit ocorre antes/depois do save sem transação DB | [pgvector](fase-10b-pgvector-memoria-transacional.md) |
| Lore/regras | Codex + dois FAISS globais (~9,94 MiB) | bundle pesado e provider pinado no filesystem | pgvector reindexável; fonte continua sendo Codex versionado |
| Runtime gerado | `gamedata.py`, `agents/npc.py`, `agents/bestiary.py` | quatro JSONs mutáveis; processo/host divergem | `RuntimeCatalogStore`, escopo global/user/game explícito |
| Conhecimento de bestiário | `state.bestiary_knowledge` + overlay global | overlay pode atravessar campanhas/usuários | estado/registro com `owner_id`; global só se curado |
| Identidade | `game_id` no body/query + `localStorage` | possuir UUID equivale a autorização; `/game/saves` lista tudo | [Auth/RLS](fase-10b-auth-rls-isolamento.md) |
| Arte curada | `data/visual_assets.json` + 90 WebPs (~15,86 MiB) | nenhuma relevante; já é imutável | permanece estática |
| Arte dinâmica futura | inexistente | sem BlobStore, metadados, quota ou cleanup | [Storage portátil](fase-10b-storage-assets-portavel.md) |
| Jobs | inexistente | geração futura ficaria presa à request | fila Postgres com leases/`SKIP LOCKED` |
| Telemetria | `rpg.turn`, hooks LLM/RAG, playtest JSONL | logs locais sem trace, dashboard, alerta ou retenção | [Operação local](fase-10b-observabilidade-backup-caos.md) |
| Frontend | React/Vite, mesma origem, sem sessão | sem login/refresh/logout; game id global ao navegador | Auth local + bearer token na API |
| Deploy | `Procfile`; FastAPI também serve `web/dist` | nenhum alvo certificado; filesystem/runtime não portável | [Certificação cloud](fase-10b-certificacao-cloud-portavel.md) |

Inventário observado em 2026-08-16: `saves/` ≈ 27,68 MiB; memória de sessão
≈ 72,23 MiB/1.841 arquivos; arte pública ≈ 15,86 MiB; índices globais ≈ 9,94 MiB.
A máquina já possui Docker 29.6.2 e cerca de 8 GiB alocados ao Docker, portanto
o bootstrap precisa de `doctor` e perfil de serviços mínimos, não de suposições
silenciosas sobre recursos.

### 3.2 Topologia alvo

```text
React/Vite
  └─ Bearer JWT ──> FastAPI
                      ├─ GameStore ─────────> Postgres JSONB
                      ├─ TurnCoordinator ───> leases + receipts + events
                      ├─ MemoryStore ───────> pgvector
                      ├─ RuntimeCatalogStore > Postgres
                      ├─ BlobStore ─────────> Supabase Storage | S3 | arquivo local
                      ├─ JobQueue ──────────> Postgres SKIP LOCKED
                      └─ TelemetrySink ─────> OTel/log JSON

CLI/suíte offline
  └─ mesmas portas ──> JSON + FAISS + arquivo + fila inline
```

### 3.3 Perfis obrigatórios

| Perfil | Estado | Memória | Auth | Blob | Uso |
|---|---|---|---|---|---|
| `legacy` | arquivo | FAISS | desligada/local fixa | arquivo | CLI e suíte atual |
| `local` | Postgres local | pgvector local | Supabase Auth local | Storage local | ensaio de produção sem custo |
| `portable` | Postgres+pgvector | pgvector | OIDC/JWT | S3 compatível | prova anti-lock-in |
| `hosted` | Postgres remoto | pgvector remoto | JWT obrigatório | remoto | futuro; não executado nesta rodada |

### 3.4 Ordem e dependências

```text
plano mestre
  → fundação local + portas
      → Postgres transacional
          → turnos duráveis + fila
          → Auth + RLS
          → pgvector transacional
              → storage de assets
                  → observabilidade + backup + carga/caos
                      → certificação cloud portátil
```

Postgres, Auth e pgvector podem ser desenvolvidos em branches conceituais
separadas depois da fundação, mas o corte da API só ocorre quando turnos,
identidade e memória compartilham o mesmo contrato transacional.

### 3.5 Decisões fechadas por esta spec

1. Supabase Local é ferramenta de ensaio, não dependência do domínio nem servidor
   a ser exposto; migrations SQL ficam versionadas.
2. O backend síncrono usa driver Postgres síncrono/pool; não se introduz async
   apenas por infraestrutura.
3. Postgres é também a primeira fila e coordenador distribuído; Redis/Valkey só
   será considerado com evidência de gargalo.
4. O frontend não acessa tabelas de gameplay diretamente. RLS é defesa em
   profundidade; as regras mecânicas e a autorização de comando ficam em FastAPI.
5. Um ambiente usa uma fonte de verdade; shadow read é permitido para auditoria,
   shadow write permanente não.
6. **Railway é o alvo primário da certificação cloud** e Render é a contingência.
   O primeiro corte usa dois serviços da mesma imagem: `api-web` público, que já
   serve `web/dist` e FastAPI na mesma origem, e `worker` privado. Vercel fica
   como benchmark opcional, não fundamento; Services estava em Private Beta na
   consulta de 2026-08-16.

### 3.6 Referências externas de implementação

- Supabase Local e migrations: https://supabase.com/docs/guides/local-development/cli-workflows
- Testes locais/RLS: https://supabase.com/docs/guides/local-development/testing/overview
- pgvector: https://supabase.com/docs/guides/ai/vector-columns
- Storage/RLS: https://supabase.com/docs/guides/storage/security/access-control
- Railway FastAPI: https://docs.railway.com/guides/fastapi
- Railway monorepo: https://docs.railway.com/guides/deploying-a-monorepo
- Railway Docker Compose: https://docs.railway.com/guides/docker-compose
- Render service types: https://render.com/docs/service-types
- Render workers: https://render.com/docs/background-workers
- Vercel Services: https://vercel.com/docs/services
- FastAPI/Vercel: https://vercel.com/docs/frameworks/backend/fastapi

## 4. Plano passo a passo

### Etapa 1 — Aprovar fronteiras e ordem

1. **Revisão:** validar as decisões de §3.5 e o escopo de cada spec filha.
2. **Documentação:** mudar esta spec para `approved`; nenhuma infraestrutura é
   criada nesta etapa.
3. **Verificação:** links e estados no ROADMAP/ESTADO_ATUAL consistentes.

### Etapa 2 — Executar as oito specs filhas

1. Implementar estritamente na ordem de §3.4, testes primeiro.
2. Cada spec só muda para `done` com seus gates locais.
3. Um desvio estrutural atualiza esta spec e a filha no mesmo commit.

### Etapa 3 — Auditoria de fechamento

1. Rodar a matriz de prontidão local da spec de observabilidade/caos.
2. Demonstrar `legacy`, `local` e `portable` sem alterar mecânicas.
3. Só então decidir se a certificação cloud será aprovada; Railway é o alvo de
   entrada, mas um gate objetivo pode acionar a contingência Render.

## 5. Critérios de aceite

- [ ] As oito specs filhas foram revisadas e aprovadas pelo usuário.
- [ ] Todo write mutável do inventário §3.1 possui adapter e escopo de owner.
- [ ] Perfis `legacy`, `local` e `portable` passam a mesma suíte de contratos.
- [ ] API `hosted` inicia sem writes persistentes no filesystem.
- [ ] Turno, memória e recibo têm commit atômico e retry idempotente multiworker.
- [ ] Dois usuários locais não acessam nenhum estado, memória, asset ou job entre si.
- [ ] Backup/restore e teste de caos atendem RPO/RTO definidos.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM em todo `with_structured_output` novo.
- [ ] Saves antigos continuam exportáveis/carregáveis; nenhum diretório histórico é limpo automaticamente.

## 6. Smoke test com LLM real

Esta spec não cria código nem contrato LLM. No fechamento do épico, executar uma
campanha curta real no perfil `local`, derrubar/reiniciar o processo entre dois
turnos e confirmar continuidade, memória e custo. MockLLM/Ollama cobre a matriz
longa; provider pago cobre apenas o contrato de integração final.

## 7. Riscos & compatibilidade

- **Escopo grande:** mitigado por nove documentos pequenos e corte por adapters.
- **Supabase Local pesado:** o bootstrap terá verificação de recursos e serviços
  mínimos; a suíte offline nunca dependerá de Docker.
- **Lock-in:** mitigado por psycopg/SQL padrão, OIDC, BlobStore e perfil portátil.
- **Longas chamadas LLM:** nenhum lock/transaction DB fica aberto enquanto o
  provider pensa; o coordenador usa lease e commit posterior.
- **Caches globais atuais:** precisam ser classificados antes do cutover para
  impedir vazamento entre usuários.
