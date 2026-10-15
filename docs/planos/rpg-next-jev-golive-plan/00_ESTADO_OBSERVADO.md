# Estado observado do repositório antes deste pacote

Snapshot analisado: `main` `1beefc432cce5ded4e3468e42c5e583aa4431a44` (`feat: deliver deterministic eval system`, 2026-10-02).

## Evals / specs

- SPEC-163..SPEC-175 estão `done`; SPEC-176 estava livre no snapshot.
- A régua canônica força `RPG_FORCE_MOCK=1`; ela mede contratos determinísticos, não qualidade real de DeepSeek/Groq/Jev.
- `evals/datasets/regression/**`, evaluator/core, schemas, metrics registry e lock são protegidos.
- O push do snapshot falhou em CI por `narrative_npc.jsonl` não bater com `manifest.lock.json`, approval protegido ausente e Project Index stale. Frontend/audit-local/scope passaram.
- SPEC-175 decidiu que Project Index é **selective-only**. Source real permanece autoridade.

## LLM / Jev

- `dm_router` usa `ModelTier.CLASSIFY` somente depois de gates Python determinísticos.
- `llm_setup.py` já possui fallback multi-provider e attempt telemetry, mas `LLMAttemptEvent` não carrega usage token/custo real.
- `playtest/pricing.py` ainda estima ~1200 input / 400 output por invoke; isso não pode ser fonte de billing.
- Jev deve ser um `DecisionBackend`, não um candidato `RoutedLLM`.
- Nome canônico de segredo na documentação Jev: `JEVMODEL_API_KEY`; endpoint `POST /v1/systemone`, Bearer auth e idempotency key opcional. O pacote não expõe a chave ao frontend.

## Runtime / Supabase

- `RuntimeConfig` atual diferencia `legacy`, `local`, `portable`, `hosted`.
- `local` usa Supabase Auth/Blob; `portable`/`hosted` exigem OIDC + S3. Portanto o alvo Vercel + Supabase não deve ser obtido enfraquecendo o perfil `hosted`; criar contrato/profile hosted-Supabase explícito preserva portabilidade existente.
- `PostgresPool` usa `psycopg_pool` e default `max_size=4`; serverless/pooler precisa de configuração/env e teste de concorrência, não nova pool por operação.
- Auth local já cobre signup/login/refresh/logout, cookies HttpOnly/CSRF e ownership/RLS. Reset/verify público, CAPTCHA e lifecycle de produção ainda precisam fechamento.

## Operações / workers

- `app.operations`, `app.turns`, jobs, leases/fencing e replay idempotente já existem.
- `app.turns.llm_cost_usd` existe, mas não tem fonte financeira confiável ainda.
- Workers Postgres são duráveis; worker Python contínuo e jobs de arte/embedding/crônica exigem uma decisão explícita na topologia Vercel.
- `external_result_uncertain` na arte já impede retry pago cego. Reusar essa fronteira em billing de imagem.

## Arte

- O projeto já tem geração dinâmica e triggers automáticos para retrato/NPC/cena épica.
- Decisão de produto deste pacote: **nenhuma geração que consuma Estilhas pode chamar provider sem quote e confirmação explícita do jogador**. Portanto triggers existentes podem criar uma oferta/cue, mas não podem gastar saldo automaticamente.

## Frontend / conta

- `App.tsx` hoje tem fluxo bootstrap/auth/saves/create/simulator/play; não existe Account screen.
- `StoryLog` não tem custo/operation id.
- `presentation_history` fica no GameState e usa `game_id + epoch + turn + role`; billing não deve ser gravado nele. Custo por mensagem deve ser enriquecimento read-only vindo das tabelas de turn/usage/wallet, preservando save/gameplay.

## Billing

- Não existem wallet, purchase orders, Stripe ou Google Play billing.
- Wallet deve ser única web/Android e separada do GameState.
- Jogadas normais não mostram quote. Uso é medido e debitado silenciosamente; imagem é exceção com quote explícito.
- Sem free credits e sem assinatura.
- Meta econômica inicial: fee do canal + custos variáveis mensuráveis + 5% de margem-alvo; imposto fora desta primeira modelagem; fixed infra reportado separadamente.

## Voz

- Não existe voice input atualmente.
- v1 é record -> transcribe -> texto editável -> Send explícito. Sem TTS/full duplex e sem armazenamento permanente de áudio.

## Distribuição

- Web alvo: Vercel + Supabase.
- Android alvo: Capacitor sobre React/Vite + Google Play Billing.
- iOS fica fora do v1.
- Conta Play/domínio/policies não bloqueiam implementação técnica inicial, mas bloqueiam publicação final.
