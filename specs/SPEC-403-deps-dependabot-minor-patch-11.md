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

- [x] Lock + `requirements.txt` coerentes (`uv lock --check`; o teste de reexport, se houver, verde).
- [x] `ruff check .` limpo.
- [x] Web: test/lint/typecheck/build verdes; `@playwright/test` continua `^1.64.1`.
- [ ] Suíte completa verde no pouso (coordenador).
- [ ] PRs #71, #72, #67 e #65 fechados com comentário.

## 5. Decisões (coordenador, delegação do dono)

- **D-403-1** — Playwright 1.65 adiado: o pin é de eval (`test_eval_frontend.py:142`) e o snapshot visual muda.
- **D-403-2** — #65 adiado: major do provider do Gemini, só com spec e smoke real (o MockLLM esconde bug de mapeamento).
- **D-403-3** — #67 adiado com o gatilho da 399 (#49).

## 6. Execução (10/11, executor)

- **pip (R1):** `uv lock --upgrade-package` de 14 pacotes (o lock da main já estava à frente do #72 nos demais): boto3 1.43.126, botocore 1.43.127, hypothesis-graphql 0.13.6, jsonschema-rs 0.60.3, langchain-anthropic 1.7.10, langchain-core 1.7.6, langchain-openai 1.7.4, langgraph 1.2.20, playwright (py) 1.64.1, pydantic 2.14.3, pydantic-core 2.50.4, pytest 9.2.0, ruff 0.17.4, schemathesis 4.33.1. Reexport com o comando de `requirements.txt:2` (5 pins mudaram: langchain-core, langchain-openai, langgraph, pydantic, pydantic-core). `uv lock --check` ok. Nenhum major.
- **SIM102 (R2):** 3 `elif`+`if` combinados; em `event_processor.apply_event` a condição foi para o helper `_is_occupation` para a função não crescer (gate de tamanho). `ruff check .` e `format --check` limpos.
- **npm (R3):** @capacitor/android, core e cli 8.6.0 (exatos), @vitejs/plugin-react 6.2.1 (`^6.2.1`; o `npm install` livre dava 6.3.0, fixado na versão do #71), globals 17.14.0. `@playwright/test` omitido (D-403-1), fica `^1.64.1`.
- **Testes (R4):** web `npm test` 317 ok, lint, typecheck e build verdes. pytest -n 2: test_eval_baseline, test_eval_frontend, test_spec192_vercel_packaging, test_api_fuzz_harness, spec305*, rumor 313/360/372 e todos os que citam event_processor/rumor_adoption/world_quest_relief: verdes. Suíte completa e fechamento dos PRs ficam com o coordenador.
