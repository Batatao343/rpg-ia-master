# SPEC-187 — Voice input no web/mobile

> **Status:** `draft`
> **Depende de:** SPEC-186 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL:** `none`
> **REVIEW_EFFORT:** `n/a`
> **REVIEW_REQUIRED:** `false`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: matriz de navegadores/a11y e relatório; implementação React permanece com Terra.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-187` é source of truth para subtarefas/review focus

## Objetivo

Integrar microfone ao composer com transcript editável e UX compatível com navegador e futuro Capacitor.

## Requisitos

- **R1** — estados idle/recording/uploading/transcribing/error.
- **R2** — contador e stop; 60 s hard stop.
- **R3** — transcript preenche input, preserva edição e requer Send explícito.
- **R4** — permissões negadas têm mensagem clara e input textual continua.
- **R5** — não gravar em background inadvertidamente.
- **R6** — touch/keyboard/accessibility.
- **R7** — adapter de recorder permite trocar Web MediaRecorder por native apenas se teste Android exigir.

### Fora de escopo

TTS, wake word, voice chat full-duplex.

## Plano

1. Hook/adapter recorder com fake determinístico.
2. UI no PlayScreen.
3. Endpoint integration.
4. Browser permission/test fixtures.
5. Deixar seam para Capacitor.

## Critérios de aceite

- [ ] fluxo padrão é exatamente `tap record -> tap stop (ou hard-stop) -> transcript no composer -> Send explícito`; não existe confirmação intermediária obrigatória nem auto-send;
- [ ] erro de STT não envia ação.
- [ ] input textual nunca fica bloqueado.
- [ ] mobile layout sem overlap.

## Gates / evidência

Node/browser tests; áudio real manual curto somente quando disponível.

## Gate de fechamento

- [ ] state machine cobre cancelamento, permission denied, tab/background e component unmount;
- [ ] background/unmount para captura e libera tracks do microfone;
- [ ] falha STT preserva input textual e não perde texto já digitado;
- [ ] Playwright/browser cobre 390 e 1440, teclado e touch;
- [ ] nenhuma dependência nativa obrigatória é introduzida antes da SPEC-193.
