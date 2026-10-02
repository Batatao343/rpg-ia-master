# SPEC-181 — Contrato hosted Supabase + runtime serverless

> **Status:** `approved`
> **Depende de:** SPEC-180 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: matriz de env/docs e relatório de pool; não altera auth/runtime.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-181` é source of truth para subtarefas/review focus

## Objetivo

Representar corretamente a topologia Vercel + Supabase no runtime antes de billing/deploy. Eliminar a necessidade de usar `profile=local` contra cloud e provar que Postgres pool/auth/storage falham fechado em ambiente hosted.

## Requisitos

- **R1** — adicionar um contrato/profile hosted-Supabase explícito (ou combinação equivalente validada) **sem mudar o significado atual** de `portable`/`hosted` OIDC+S3. Não “afrouxar” `hosted` para aceitar qualquer combinação.
- **R2** — `hosted` recusa loopback, filesystem persistente e auth disabled.
- **R3** — conexão Supabase usa DSN/pooler apropriado a serverless; limites de pool configuráveis e testados.
- **R4** — service role continua somente backend; publishable key nunca substitui autorização server-side.
- **R5** — nenhuma mudança de mecânica/GameState.
- **R6** — `cloud_doctor` read-only valida env names, profile, DSN shape e secrets ausentes sem imprimir valores.

### Fora de escopo

Provisionar cloud real; trocar provider; alterar regras do jogo.

## Plano

1. Reproduzir falha atual de `hosted + supabase auth`.
2. Escrever testes de config fail-closed e pool lifecycle.
3. Implementar profile/adapter sem branches no domínio.
4. Atualizar `.env.example` e docs; Project Index só é regenerado se esta spec o consultar explicitamente.
5. Rodar suíte offline + infra local relevante.

## Critérios de aceite

- [ ] hosted Supabase é um profile legítimo e testado.
- [ ] portable OIDC/S3 continua funcionando.
- [ ] nenhum secret aparece no frontend/log.
- [ ] pool não cria tempestade de conexões em teste concorrente.
- [ ] zero recurso remoto criado.

## Gates / evidência

pytest focado + suíte offline + audit-local afetado. Sol revisa fronteira auth/pool/profile.

## Gate de fechamento

- [ ] testes provam que perfis legados mantêm defaults anteriores;
- [ ] hosted-Supabase rejeita loopback, auth disabled, filesystem blob e ausência de secrets necessários;
- [ ] pool size/timeout são configuráveis por env e um teste concorrente comprova que conexões ativas não excedem `max_size` configurado;
- [ ] `cloud_doctor` imprime apenas nomes/status/redacted metadata, nunca valores de secret;
- [ ] nenhum recurso remoto é criado;
- [ ] review Sol independente aprova auth/storage/pool boundary.
