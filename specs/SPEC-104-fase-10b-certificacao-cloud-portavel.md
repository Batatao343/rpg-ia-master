# SPEC — Fase 10b.8 — Certificação cloud portátil (execução futura)

> **Status:** `draft`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [observabilidade, backup e caos](SPEC-106-fase-10b-observabilidade-backup-caos.md) `done`
> **Desbloqueia:** beta externo controlado; não autoriza deploy enquanto permanecer `draft`

---

## 1. Contexto & Objetivo

O laboratório local consegue provar contratos, isolamento e recuperação, mas não
prova DNS/TLS, egress, cold start, limite de bundle/duração, e-mail/OAuth real,
pooler gerenciado, quotas, CDN, backups do provedor ou custos. Esses itens só
existem num ambiente remoto.

Esta spec define a certificação futura e evita que hospedagem e data plane virem
uma decisão irreversível antes do produto estar robusto. A escolha arquitetural
para o primeiro staging é **Railway**, com **Render** como contingência. Vercel
permanece somente como benchmark: em 2026-08-16, Services estava em Private
Beta e FastAPI usava uma Function Python com limites próprios de bundle e
duração, um encaixe menos natural para SSE longo e worker Python contínuo.

## 2. Requisitos

- **R1 — autorização separada:** nenhum comando cria projeto, deployment,
  domínio, banco ou recurso pago até o usuário aprovar esta spec e um orçamento.
- **R2 — matriz antes da promoção:** comparar ao menos três topologias com
  critérios reproduzíveis: custo mínimo/previsto, Python 3.13, SSE, duração,
  bundle, Postgres/pgvector, Auth/OIDC, Blob S3, backups, observabilidade e lock-in.
- **R3 — alvo primário e fallback:** Railway é o alvo do primeiro staging;
  Render é o plano B. O deploy só é promovido se os gates confirmarem a decisão,
  e Vercel Services Private Beta não pode ser dependência única.
- **R4 — staging descartável:** primeiro remoto é staging sem dados reais,
  domínio temporário e budgets/alerts; produção não recebe `db reset` ou seed.
- **R5 — migrations promovíveis:** dry-run, backup, apply, smoke e rollback/
  forward-fix documentados; connection role/pooler adequados ao runtime.
- **R6 — configuração segura:** secrets por ambiente, rotação, least privilege,
  preview isolado e nenhum secret em build/client/log.
- **R7 — filesystem independente:** runtime remoto passa guard de zero writes
  persistentes; corpus/arte curada são build artifacts ou storage remoto.
- **R8 — testes cloud-only:** TLS/CORS/cookies, JWKS rotation, confirmação/reset
  de e-mail, CDN/signed URL, cold start, timeout/SSE, concorrência internet,
  quotas/rate limit, backup gerenciado+blob e restore.
- **R9 — custo mensurável:** relatório separa LLM, functions/compute, DB, storage,
  egress e observabilidade; budget kill-switch e teto de playtest reais.
- **R10 — reversibilidade:** export de Postgres e blobs restaura no profile
  portátil local; trocar frontend/backend/provider não muda o domínio.
- **R11 — release gate:** beta externo só abre após G0–G7 local + todos os gates
  cloud do alvo, zero P0/P1 e runbooks de incidente/rollback/deleção.
- **R12 — evidência temporal:** versões/limites/preços são consultados nas docs
  oficiais no dia da execução e registrados; números desta spec não são tratados como eternos.

### Fora de escopo

- Executar agora qualquer deploy, login CLI remoto, link de projeto ou compra.
- Tratar a preferência Railway como certificação definitiva antes dos benchmarks.
- Multi-região ativo-ativo, Kubernetes ou escala antecipada.
- Marketing, analytics de produto e lançamento público amplo.

## 3. Design técnico

### Decisão arquitetural registrada

**Railway é a melhor alternativa à Vercel para o estado atual deste projeto.**
O motivo decisivo não é uma comparação genérica de plataformas, mas a topologia
que já existe no repositório:

1. `api.py` já serve `web/dist`; o primeiro deploy mantém frontend e API na
   mesma origem dentro do serviço público `valoria-api-web`, evitando um segundo
   deploy, CORS de credenciais e configuração prematura de domínio.
2. O worker de jobs usa a mesma imagem Docker e outro comando de entrada no
   serviço privado `valoria-worker`, sem tentar encaixar polling contínuo em uma
   Function.
3. FastAPI, SSE e chamadas LLM de dezenas de segundos rodam como processo de
   container normal; não dependem do ciclo de vida de uma função serverless.
4. A topologia local de containers mapeia diretamente para serviços Railway,
   preservando Docker como contrato portátil e deixando Render/Coolify viáveis.
5. O custo de idle deve incluir explicitamente um worker ativo. O modo
   serverless/sleep da Railway é uma otimização possível para a API, nunca uma
   premissa do orçamento, pois pools/conexões de saída podem impedir o sleep.

O data plane é ortogonal: o staging inicial pode usar Supabase remoto para
Postgres+pgvector/Auth/Storage, mas toda integração continua atrás das portas
Python definidas na spec-mãe.

```text
Browser
  └─ HTTPS/SSE ──> Railway: valoria-api-web
                     ├─ serve web/dist na mesma origem
                     ├─ executa FastAPI
                     └─ Postgres/Auth/Blob remotos

Railway: valoria-worker (sem domínio público)
  └─ mesma imagem, comando de worker ──> fila Postgres + Blob
```

### Matriz de alternativas

| Ordem | Frontend | Backend Python | Dados/Auth/Blob | Vantagem para Valoria | Risco a medir |
|---|---|---|---|---|---|
| **Primário — Railway** | servido por FastAPI no mesmo container | serviço Docker público + worker Docker privado | Supabase ou Postgres gerenciado+OIDC+S3 | menor mudança, mesma origem, SSE/worker naturais, Docker portátil | custo real de dois serviços, cold start, shutdown e região |
| **Fallback — Render** | mesma origem ou Static Site | Web Service Docker + Background Worker | Supabase ou Postgres gerenciado+OIDC+S3 | tipos de serviço explícitos, Blueprint e worker contínuo maduros | custo mínimo do worker separado, cold start e região |
| Benchmark — Vercel | Vite | Function FastAPI ou Services se disponível | Supabase | excelente entrega do frontend | Services Private Beta, ciclo de Function e ausência de worker contínuo simples |
| Anti-lock-in — Coolify/VPS | mesmo container | container FastAPI + worker | Postgres+pgvector, OIDC, MinIO/S3 | controle máximo e reaproveitamento integral | operação, backup, TLS, patching e plantão próprios |

O primeiro staging usa a topologia Railway acima. Render só é exercitado se um
gate Railway falhar, o custo projetado exceder o teto aprovado ou o serviço não
suportar uma exigência do produto. Separar o frontend em CDN/Static Site continua
possível depois, mas exige evidência de benefício e não faz parte do primeiro corte.

### Arquivos previstos

- `deploy/targets/railway/` — Docker/config dos serviços `api-web` e `worker`, sem secrets.
- `deploy/targets/render/` — contingência reproduzível, criada apenas se acionada.
- `scripts/cloud_doctor.py` — read-only: versões, link, env names, quotas conhecidas.
- `scripts/cloud_smoke.py` — testes cloud-only com teto e cleanup explícito.
- `docs/DEPLOYMENT.md`, `docs/INCIDENTS.md`, `docs/ROLLBACK.md`, `docs/COSTS.md`.
- `.github/workflows/` — preview/staging/production com approvals separados.

Nenhum desses arquivos é criado enquanto esta spec não for aprovada para execução.

### Gates cloud

```text
C1 build/bundle Python 3.13 e frontend reproduzíveis
C2 migrations dry-run + staging limpa
C3 auth cookies/JWKS/e-mail real
C4 SSE 5 turnos + timeout/cold start/fallback
C5 2 workers/instâncias + idempotência/lease
C6 pgvector recall/latência no pooler escolhido
C7 blob privado/signed URL/CDN/cleanup
C8 backup DB + backup blob + restore portátil
C9 observabilidade/alerta/incident drill
C10 relatório de custo e budget alert/kill switch
```

### Critérios de decisão

Pontuar 0–5 e anexar evidência para: custo idle/100/1.000 usuários, tempo de
deploy/rollback, latência first SSE/turno, suporte Python/SSE, portabilidade,
backup/restore, segurança, manutenção e maturidade do produto. Empate favorece
a topologia mais simples e reversível, não a maior lista de serviços.

### Referências que devem ser reverificadas

- https://vercel.com/docs/services
- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/limitations
- https://docs.railway.com/guides/fastapi
- https://docs.railway.com/guides/deploying-a-monorepo
- https://docs.railway.com/guides/docker-compose
- https://docs.railway.com/deployments/serverless
- https://docs.railway.com/pricing
- https://render.com/docs/service-types
- https://render.com/docs/background-workers
- https://render.com/docs/blueprint-spec
- https://supabase.com/docs/guides/local-development/cli-workflows
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/deployment/shared-responsibility-model

## 4. Plano passo a passo

### Etapa 1 — Confirmar decisão e orçamento

1. **Pesquisa oficial:** atualizar preços/limites de Railway e Render e confirmar
   runtime Python 3.13, SSE, healthcheck, shutdown e comandos por serviço.
2. **Aprovação humana:** confirmar Railway, Render como plano B, região, teto
   mensal, número de réplicas e política de cleanup.
3. **Verificação:** registrar orçamento incluindo um worker ativo; nenhum
   create/deploy antes da autorização explícita.

### Etapa 2 — Configuração de deploy local-only

1. **Testes:** build/config/lint e emulação local do alvo quando disponível.
2. **Implementação:** imagem reproduzível e config Railway para `api-web` e
   `worker`, sem link, projeto remoto ou secrets.
3. **Verificação:** runtime profile hosted falha fechado sem env.

### Etapa 3 — Staging descartável

1. **Testes:** C1–C10 com dados sintéticos e budget.
2. **Implementação:** provisionar só após aprovação específica; migrations/seed staging.
3. **Verificação:** export/cleanup e relatório de custo real.

### Etapa 4 — Escolha final/rollback

1. Comparar alvo com plano B usando resultados, não promessa.
2. Executar incident/restore/rollback drill.
3. Solicitar aprovação separada para beta externo.

## 5. Critérios de aceite

- [ ] Usuário aprovou Railway, Render como plano B, região, recursos e teto de custo.
- [ ] Limites/preços oficiais foram atualizados no dia da execução.
- [ ] C1–C10 verdes em staging sintética.
- [ ] Zero write persistente em filesystem remoto.
- [ ] Multi-instância e SSE passaram sob cold start/timeout real.
- [ ] Auth/RLS/blob impedem A↔B também pela internet.
- [ ] Backup DB+blob restaura no local/portable e no staging limpo.
- [ ] Alertas, rollback, incident e cleanup foram ensaiados.
- [ ] Custo observado/projetado cabe no teto aprovado.
- [ ] G0–G7 locais continuam verdes.
- [ ] Guard de FallbackLLM e contratos reais verdes com teto de requests.
- [ ] Nenhum dado histórico real foi enviado sem consentimento explícito.

## 6. Smoke test com LLM real

Cinco turnos reais com tetos de requests/custo, cobrindo POST/SSE, fallback,
restart/cold start e receipt idempotente. Repetir uma chave não pode gerar nova
cobrança após receipt confirmado. Dados sintéticos são removidos pelo cleanup
aprovado ao final.

## 7. Riscos & compatibilidade

- **Limites/preços mudam:** revalidar docs de Railway/Render no dia; Docker e o
  profile `portable` permanecem como saída.
- **Custo de espera LLM:** medir billing do runtime durante streaming, comparar
  container contínuo e function antes de escolher.
- **Preview com banco compartilhado:** proibido por default; usar schema/projeto
  isolado ou somente migrations dry-run.
- **Lock-in acidental:** gate de export/restore portátil bloqueia certificação.
- **Ação externa:** esta spec permanece deliberadamente `draft`; escrever o
  documento não concede autorização para provisionar ou publicar.
