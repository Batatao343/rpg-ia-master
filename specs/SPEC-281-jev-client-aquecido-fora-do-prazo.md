# SPEC-281 — jev-client-aquecido-fora-do-prazo

> **Status:** `done`
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Aprovação:** `approved` pelo dono em 19/10 (autorizou tudo que não exige ação externa dele).
> **Depende de:** SPEC-217 (Jev no router) · **Origem:** revisão da SPEC-277 (`handoffs/SPEC-277-review.md`)

## 1. Contexto & Objetivo

`_default_backend` (`services/jev_rollout.py`) criava o `httpx.Client` (contexto SSL, lento em cold start da Vercel) dentro do worker, isto é, dentro do prazo de 1 s do Jev. O 1º turno de uma instância fria em `primary`/`shadow` podia dar timeout falso e cair no CLASSIFY. Objetivo: construir o client antes de o relógio do prazo começar.

## 2. Requisitos

- **R1** — `warm_client()` é um lazy singleton thread-safe do `httpx.Client`.
- **R2** — `begin()` chama `warm_client()` antes de `started = time.monotonic()` quando `backend is None`, e só depois dos retornos antecipados (off, kill switch, aprovação, limiar).
- **R3** — Com `RPG_JEV_ROUTER_MODE=off` nada é construído (byte-idêntico).
- **R4** — Backend injetado não aquece nada.

### Fora de escopo
Warm-up no import/boot; mudar o prazo; staging.

## 3. Design técnico

Alterado: `services/jev_rollout.py` (`warm_client`; `_default_backend` o reutiliza; `begin` aquece). Novo: `tests/test_jev_client_warm.py`.

## 4. Plano
1. Testes: construção lenta (0,4 s) com prazo 0,2 s não conta no relógio; `off` não constrói; singleton; backend injetado não aquece.
2. Implementação acima.

## 5. Critérios de aceite

- [x] R1–R4 cobertos por testes.
- [x] Testes jev/router da SPEC-217 verdes; suíte completa verde.
