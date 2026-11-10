# SPEC-403 — deps-dependabot-minor-patch-11

> **Status:** `approved` (10/11, coordenador com delegação do dono: "confio em vc nas decisoes" / "aprovar tudo conforme suas recomendações"; molde da SPEC-399)
> **Criada:** 2026-11-10 · **Atualizada:** 2026-11-10
> **Depende de:** SPEC-399 (`done`)
> **Desbloqueia:** fechar os PRs #71, #72, #67 e #65 do Dependabot
> **Risco:** `baixo` (tooling/deps, só minor e patch; a suíte e o CI provam). Revisão: testes + lint, como manda o AGENTS.md § Qualidade.
> **Evidência:** a suíte completa e o build web ficam verdes com o lock novo. Os 3 SIM102 que o CI do #72 aponta somem no `ruff check`.
> **EVAL_AUTHORING_REQUIRED:** `false`. O pin do `@playwright/test` em `tests/test_eval_frontend.py:142` fica intocado (R3).

## 1. Contexto & Objetivo

O Dependabot abriu em 09/11 dois PRs de grupo, e os dois têm CI vermelho:

- **#72 (pip, 29 updates):** o ruff novo traz SIM102 em `services/event_processor.py:255` e em `services/rumor_adoption.py:196,349`.
- **#71 (npm, 6 updates):** `tests/test_eval_frontend.py:142` fixa `@playwright/test` em `^1.64.1`, e o PR sobe para `^1.65.0`. O golden guard 353/363 falha só porque a base do PR é antiga.

Também seguem abertos o #67 (uuid-utils 1.2, major; mesmo gatilho do #49 adiado na 399) e o #65 (langchain-google-genai 4.x, major do provider do Gemini).

Objetivo: incorporar #72 e #71 na branch, como a SPEC-399 fez (lock regenerado + reexport, sem mergear o PR), e fechar os quatro PRs com o motivo.

## 2. Requisitos

- **R1** — pip: aplicar os mesmos bumps do #72 via `uv lock --upgrade-package` (ou `uv lock --upgrade` restrito a minor/patch, sem major) e reexportar o `requirements.txt` (D-399-4).
- **R2** — corrigir os 3 SIM102 sem mudar comportamento (`if` combinado), com `ruff format` + `ruff check` limpos no repo.
- **R3** — npm: aplicar os bumps do #71 **exceto** `@playwright/test`, que fica em `^1.64.1`, porque o pin é de eval (snapshot visual). Subir o Playwright exige autoria de eval e vira spec própria. Se outro pacote do grupo depender do Playwright novo, ele também fica de fora.
- **R4** — `npm test`, `lint`, `typecheck` e `build` em `web/` verdes.
- **R5** — fechar os PRs: #71 e #72 como "incorporados na SPEC-403" (o Playwright citado como adiado); #67 como adiado com o mesmo gatilho do #49 (SPEC-399); #65 como adiado: major do provider do Gemini, que exige spec com smoke real (structured output).

### Fora de escopo

Majors (uuid-utils 1.x, langchain-google-genai 4.x, Playwright 1.65), código de produto além dos 3 SIM102, `evals/`.

## 3. Plano

1. Worktree `spec-403`: `uv lock` dos pacotes do #72 + reexport; `uv sync`.
2. Ruff no repo e correção dos 3 SIM102.
3. `web/`: `npm install` das versões do #71 sem o Playwright; testes web.
4. Testes do escopo (`-n 2`) + `tests/test_eval_frontend.py`, `tests/test_eval_baseline.py`. A suíte completa é do coordenador, no pouso.

## 4. Critérios de aceite

- [ ] Lock + `requirements.txt` coerentes (`uv lock --check`; o teste de reexport, se houver, verde).
- [ ] `ruff check .` limpo.
- [ ] Web: test/lint/typecheck/build verdes; `@playwright/test` continua `^1.64.1`.
- [ ] Suíte completa verde no pouso (coordenador).
- [ ] PRs #71, #72, #67 e #65 fechados com comentário.

## 5. Decisões (coordenador, delegação do dono)

- **D-403-1** — Playwright 1.65 adiado: o pin é de eval (`test_eval_frontend.py:142`) e o snapshot visual muda.
- **D-403-2** — #65 adiado: major do provider do Gemini, só com spec e smoke real (o MockLLM esconde bug de mapeamento).
- **D-403-3** — #67 adiado com o gatilho da 399 (#49).
