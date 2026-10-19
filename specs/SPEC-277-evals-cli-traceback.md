# SPEC-277 — Evals CLI: traceback e `error_type` na falha (follow-up da SPEC-260 R2)

> **Status:** `approved` (dono, 19/10: autorizou tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** revisão independente logs P2/P3 (achado 10, [parecer](../handoffs/LOGS-P2P3-review.md)); SPEC-260 R2 ficou fora por desvio deliberado
> **Depende de:** SPEC-260
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus) · **REVIEW_REQUIRED:** `true` — toca caminho protegido da régua de evals
> **EVAL_AUTHORING_REQUIRED:** `true` — `evals/__main__.py` está em `evals/protected-paths.txt`; exige relock do `evals/manifest.lock.json` + aprovação do environment `eval-governance`

---

## 1. Contexto & Objetivo

A SPEC-260 pediu (R2) que o CLI de evals, quando um caso falha com exceção, imprima em stderr a suíte, o
`case_id` e o traceback, e que o JSON de saída traga `error_type`. A implementação não fez esse item porque
`evals/__main__.py` é caminho protegido: qualquer mudança altera o sha256 travado em
`evals/manifest.lock.json` e reprova o gate `eval-gates` sem o relock oficial. Esta spec isola essa mudança
para seguir o procedimento de publicação de evals.

## 2. Requisitos

- **R1** — Exceção ao rodar um caso: stderr recebe `suite`, `case_id` e o traceback (cauda ≤ 40 linhas, sem locals).
- **R2** — O resultado JSON do caso traz `error_type` (`type(exc).__name__`), nunca a mensagem da exceção (ela pode conter dado do dataset).
- **R3** — Comportamento de pontuação/contagem inalterado: um caso com erro conta como hoje (error, não skip).
- **R4** — Relock do manifesto pelo procedimento oficial e aprovação do environment `eval-governance` antes do merge.

## 3. Fora de escopo

- Mudar métricas, datasets ou a régua.
- Traceback em outros CLIs (playtest já coberto pela SPEC-260 R1).

## 4. Plano

1. Teste primeiro: caso sintético que levanta → stderr com `case_id` + traceback; JSON com `error_type`, sem mensagem.
2. Implementar (mínimo). **Desvio:** a exceção por caso é capturada em `evals/core/runner.py` (também protegido; traceback se perdia ali), então o stderr (suite, case_id, cauda ≤ 40 linhas) sai do runner; `evals/__main__.py` acrescenta `errors: [{case_id, error_type}]` ao JSON do CLI (classe da exceção, nunca a mensagem). Ambos entram no mesmo relock.
3. Relock + `/eval-publish` para aprovação do dono.

## 5. Critérios de aceite

- [x] stderr com suíte, `case_id` e traceback na falha de um caso.
- [x] `error_type` no JSON, sem a mensagem da exceção.
- [x] Contagens idênticas antes/depois em uma suíte sem falhas.
- [ ] `eval-gates` verde após o relock aprovado.
