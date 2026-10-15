# SPEC-193 — Fundação Android com Capacitor

> **Status:** `done`
> **Depende de:** SPEC-192 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: build/report e inventário de permissões; boundary WebView/native fica com Terra e revisão Sol.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-193` é source of truth para subtarefas/review focus

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

- [x] mesmo frontend web/Android.
- [x] resume preserva auth/pending operation.
- [x] mic funciona ou seam nativo documentado.
- [x] nenhum production package ID publicado.

## Gates / evidência

Android emulator/device + web regression.

## Gate de fechamento

- [x] AAB/debug build é reproduzível a partir do mesmo `web/` sem fork de UI;
- [x] auth cookie/session sobrevive background/resume e não vaza bearer/token para JS storage;
- [x] pending operation não duplica após process/background-resume;
- [x] permissões mínimas (internet/mic e apenas o necessário) documentadas;
- [x] secret scan do APK/AAB não encontra keys backend;
- [x] production applicationId permanece placeholder/config até SPEC-198;
- [x] review Sol independente do boundary WebView/native/session: CHANGES_REQUIRED (15/10) -> 6 correções aplicadas (Addendum); re-aprovação formal a cargo do orquestrador.

## Addendum 2026-10-15 (execução Claude)

Equivalência de modelo: o executor original exigido era `Terra`; esta rodada de correções foi feita por Claude Opus 5.5 por decisão do orquestrador (opção (a)) após o review independente CHANGES_REQUIRED. Detalhes e decisões: [docs/spec193/README.md](../docs/spec193/README.md#addendum-2026-10-15-execução-claude).

Decisões: refresh e `rpg_csrf` persistentes (mesmo Max-Age) só com `X-RPG-Client: android`; um único `POST /auth/refresh` no boot nativo; WebView depurável só em `BuildConfig.DEBUG`; sem `CAP_APP_ID`; FileProvider só com cache; topbar a 360px sem sobreposição; risco de spoofing do header aceito e documentado.

Evidência: `docs/spec193/evidence/emulator_smoke_v2.json` (rpg34, build debug do commit publicado no staging), `vercel_smoke_v2.json`, `e2e_session_v2.json`, `apk_secret_scan_v2.json`. Gates: pytest completo, `web` npm ci/test/build, Project Index.
