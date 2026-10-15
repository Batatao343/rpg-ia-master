# SPEC-186 — Roteamento Speech-to-Text e metering

> **Status:** `done`
> **Depende de:** SPEC-185 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: benchmark/report de STT já executado; não implementa wallet/fallback/temp-file security.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-186` é source of truth para subtarefas/review focus

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

- [x] fallback não duplica cobrança (gates determinísticos/Postgres).
- [x] arquivo sempre removido (success/errors/timeout/cancelamento/finanças).
- [x] áudio > limites rejeitado antes de provider e reserva.
- [x] zero auto-send.
- [x] custo aparece como voice no account dashboard (Postgres real).

## Gates / evidência

Offline fixtures primeiro. Real: poucas frases pt-BR + nomes Valoria; sem long-run.

## Gate de fechamento

- [x] provider/model IDs são reverificados no dia da implementação e ficam configuráveis, não hardcoded como eternos (2026-10-12);
- [x] 60s, bytes e MIME são validados antes de reservar/chamar provider;
- [x] arquivo temporário é removido em success, 4xx, 5xx, timeout, cancelamento e exceção interna;
- [x] fallback usa reference/idempotency único por tentativa e settlement soma somente tentativas billable;
- [x] transcript nunca é autoenviado ao jogo;
- [x] sem saldo/reserva válida, zero provider call;
- [x] review Sol independente aprova wallet/privacy/fallback (`SPEC-186-SOL-20261012-01`, APPROVED).

## Execução 2026-10-12

Implementação offline concluída pelo executor Sol High obrigatório, sem
substituição. Revisão Sol High independente `SPEC-186-SOL-20261012-01`
**APPROVED**. Smoke real explicitamente autorizado pelo usuário concluído,
sem recarga de providers; revisão de fechamento `SPEC-186-SOL-20261012-LIVE-01`
**APPROVED**. [Contrato, decisões e evidência](../docs/spec186/README.md).

Gate focado final: **44 passed**, incluindo Postgres real e decode real em
WebM/Ogg/MP4; 19 verificações afetadas também verdes. Suíte completa atingiu
100% com **exit 0** (duplo `-q` suprimiu contagens); Ruff e diff-check verdes.

Rota: `POST /account/transcriptions`, raw body (evita spool multipart), UUID
por operação, owner da sessão e CSRF. WAV é canonicalizado pelos frames
validados; formatos WebM/Ogg/MP4 exigem ffmpeg e falham antes da reserva se
ausente. Byte/duration/MIME e teto financeiro são server-side. Receipt guarda
só metadata, e replay não retranscreve nem persiste transcript. Usage exato
soma tentativas; cobrança desconhecida permanece em reserva com fence para
reconciliação. A estimativa OpenAI por minuto não autoriza settlement.

Migration acrescenta o tipo `speech_to_text` à operação. Cards históricos de
LLM, evaluator/expected/baselines/datasets permanecem intactos; STT usa card
separado com versão+hash e IDs configuráveis. Sem alteração de GameState.

## Fechamento live 2026-10-12

Exatamente **quatro chamadas Groq** com wallet Postgres real: todas success/
settled, eventos voice por owner **2 + 1 + 1**, saldo reservado final zero.
Áudios sintéticos com 1,75s/2,69s; latências da dupla final 648/829ms. Custo
normalizado pelo rate card: **US$0,000444448**, sem confirmação por invoice.
Áudio/transcript não foram persistidos. Nenhuma ativação comercial ocorreu.

A voz sintética flite em inglês não comprova qualidade pt-BR: similaridades
0,811/0,735 e nomes próprios parcialmente perdidos são observações desse smoke,
sem alegação de precisão. OpenAI live `skipped_missing_key`; fallback continua
validado offline. Limitações aceitas pela revisão independente de fechamento.
