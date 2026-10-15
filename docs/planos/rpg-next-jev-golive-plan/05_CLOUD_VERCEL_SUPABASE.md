# Vercel + Supabase — princípios de staging

## Supabase

Criar projeto remoto novo somente na spec de staging e após aprovação humana.

Alvo inicial: região Brasil quando disponível/adequada. Reusar migrations; nunca “reconstruir schema à mão”. Rodar Security/Performance Advisors, RLS A/B, Storage privado, Auth, pgvector, backup/restore e conexão pelo pooler adequado ao runtime serverless.

Não usar `profile=local` em produção. Como o `hosted` atual significa OIDC+S3, a SPEC-181 deve criar um contrato/profile hosted-Supabase explícito em vez de mudar silenciosamente a semântica existente.

## Vercel

Em 09/2026, o alvo é plausível por suportar FastAPI/Python, streaming, Fluid compute, Functions longas e Services/Queues em beta pública. Betas são aceitos pelo usuário, mas staging precisa medir:

- SSE/streaming;
- cold start;
- bundle/FAISS/dependencies;
- conexão/pooler Supabase;
- cookies/CSRF/same-origin;
- worker/jobs/redeploy;
- env/secrets;
- observabilidade e custos.

Não promover produção se a topologia de worker depender de comportamento não comprovado.

## Preview

Preview deployments nunca devem apontar para produção com permissões de escrita. Usar staging isolado ou fail closed.
