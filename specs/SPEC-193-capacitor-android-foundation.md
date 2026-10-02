# SPEC-193 — Fundação Android com Capacitor

> **Status:** `approved`
> **Depende de:** SPEC-192 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: build/report e inventário de permissões; boundary WebView/native fica com Terra e revisão Sol.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-193` é source of truth para subtarefas/review focus

## Objetivo

Empacotar o React/Vite existente como Android sem duplicar produto, mantendo ambiente de staging e preparando adapters de billing/microfone.

## Requisitos

- **R1** — Capacitor 8 GA pinado/lockfile.
- **R2** — dev package ID separado; produção não fixada ainda.
- **R3** — app aponta para staging de forma segura/configurável; cookies/session testados em WebView.
- **R4** — deep links mínimo para auth/payment somente quando necessário.
- **R5** — voice input funciona via web API ou adapter nativo pequeno.
- **R6** — Android back/resume/background não duplica pending operation.
- **R7** — nenhum secret de backend no APK.

### Fora de escopo

iOS; push notifications; offline gameplay.

## Plano

1. Adicionar Capacitor v8.
2. `android/` reprodutível + config environments.
3. Device/emulator smoke login→game→voice→resume.
4. Inspect APK/AAB por secrets.
5. Preparar purchase adapter interface sem compra ainda.

## Critérios de aceite

- [ ] mesmo frontend web/Android.
- [ ] resume preserva auth/pending operation.
- [ ] mic funciona ou seam nativo documentado.
- [ ] nenhum production package ID publicado.

## Gates / evidência

Android emulator/device + web regression.

## Gate de fechamento

- [ ] AAB/debug build é reproduzível a partir do mesmo `web/` sem fork de UI;
- [ ] auth cookie/session sobrevive background/resume e não vaza bearer/token para JS storage;
- [ ] pending operation não duplica após process/background-resume;
- [ ] permissões mínimas (internet/mic e apenas o necessário) documentadas;
- [ ] secret scan do APK/AAB não encontra keys backend;
- [ ] production applicationId permanece placeholder/config até SPEC-198;
- [ ] review Sol independente aprova WebView/native/session boundary.
