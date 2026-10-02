# SPEC-186 — Roteamento Speech-to-Text e metering

> **Status:** `approved`
> **Depende de:** SPEC-185 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: benchmark/report de STT já executado; não implementa wallet/fallback/temp-file security.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-186` é source of truth para subtarefas/review focus

## Objetivo

Adicionar transcription service barato/rápido, primary Groq Whisper Turbo e fallback OpenAI mini, integrado à wallet/metering sem persistir áudio.

## Requisitos

- **R1** — endpoint autenticado de transcrição, max 60 s e limites de bytes/MIME.
- **R2** — Groq `whisper-large-v3-turbo` primary; OpenAI `gpt-4o-mini-transcribe` fallback.
- **R3** — provider abstraction e circuit/fallback semelhante ao LLM, sem misturar output com jogo.
- **R4** — reserve pequeno antes do request e settle pelo duration/rate-card/usage disponível.
- **R5** — áudio temporário apagado mesmo em erro; nunca em DB/log.
- **R6** — transcript pertence ao usuário, mas não vira ação automaticamente.
- **R7** — rate limit próprio e conteúdo máximo.

### Fora de escopo

Voice conversation realtime/TTS; armazenar recordings; Deepgram obrigatório.

## Plano

1. Fake providers e fixtures pt-BR.
2. Implementar service/routes + cleanup.
3. Integrar metering/wallet.
4. Benchmark curto real de latência/qualidade apenas com autorização.
5. Redaction/security tests.

## Critérios de aceite

- [ ] fallback não duplica cobrança.
- [ ] arquivo sempre removido.
- [ ] áudio > limites rejeitado antes de provider.
- [ ] zero auto-send.
- [ ] custo aparece como voice no account dashboard.

## Gates / evidência

Offline fixtures primeiro. Real: poucas frases pt-BR + nomes Valoria; sem long-run.

## Gate de fechamento

- [ ] provider/model IDs são reverificados no dia da implementação e ficam configuráveis, não hardcoded como eternos;
- [ ] 60s, bytes e MIME são validados antes de reservar/chamar provider;
- [ ] arquivo temporário é removido em success, 4xx, 5xx, timeout, cancelamento e exceção interna;
- [ ] fallback usa reference/idempotency único por tentativa e settlement soma somente tentativas billable;
- [ ] transcript nunca é autoenviado ao jogo;
- [ ] sem saldo/reserva válida, zero provider call;
- [ ] review Sol independente aprova wallet/privacy/fallback.
