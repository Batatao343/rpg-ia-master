# SPEC-380 — Evals vivos: baseline no CI, suíte `cards_combat` e playtest real semanal

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** [auditoria 03/11](../docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md) §4.6 "Evals" (a)–(d) e §5 letra J · regras da onda §6.2 (W1–W8, em especial **W5**)
> **Depende de:** SPEC-370 e SPEC-374 pousadas (as duas editam `evals/protected-paths.txt`, §6.3 da auditoria) · SPEC-375 pousada (edita `.github/workflows/eval-gates.yml`, ver SPEC-375 §R5/R7) · **só para R2:** SPEC-368 pousada (muda o comportamento das Cartas) e, para os casos de custo, SPEC-377 decidida (ver D3)
> **Desbloqueia:** oráculo W2 da onda com baseline versionada (375–385 passam a comparar contra um arquivo, não contra "antes/depois" manual); cobertura de eval do épico de Cartas
> **EXECUTOR_MODEL:** `Sol` (≡ Opus; é autoria de régua) · **REVIEW_MODEL:** `Astra` (≡ Opus em contexto independente, `spec-reviewer` com `model: opus` explícito) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — o executor desta spec é **autor de eval** e não toca produto (`agents/`, `services/`, `infrastructure/`, `workers/`, `web/src/`, `api.py`, `main.py`, `state.py`, `persistence.py`, `llm_setup.py` — lista de `scripts/dev/eval_publish.py:29-30`). Publicação via skill `/eval-publish`, com aprovação do dono no environment `eval-governance` (`.github/workflows/eval-gates.yml:40-57`).

Rótulos: **[F]** fato verificado no source (arquivo:linha) · **[H]** hipótese que a Etapa 0 confirma ou derruba · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

Os evals determinísticos existem e rodam no CI, mas estão parados e sem régua de comparação:

- **[F]** 11 datasets de regressão com 281 casos (contagem de `{"id"` em `evals/datasets/regression/*.jsonl`:
  gameplay_gate 54, npc_knowledge 39, player_knowledge 34, encounter_manifest 31, dossier_leak 28,
  narrative_npc 27, memory_context 27, routing_actions 25, state_rules 12, harness 2, governance 2) e 8
  evaluators (`evals/evaluators/*.py`). O CI roda 12 suítes em `.github/workflows/eval-gates.yml:71-81`.
- **[F]** O CI **não compara com baseline**: o job `deterministic-evals` só faz `evals run`
  (`eval-gates.yml:71-81`) e sobe o artefato. O `compare` existe e já é fail-closed:
  sai 1 em regressão (`evals/__main__.py:86`) e 2 em baseline incompatível (`evals/__main__.py:87-89`,
  via `assert_baseline_compatible`, `evals/core/governance.py:127-149`). **R1 não exige mudança em `evals/core`.**
- **[F] (corrige a auditoria)** A "única baseline" `evals/runs/baseline-v1-validation.json` é de
  **30/09** (`started_at`, linha 37), não de 17/10; tem `evaluator_version 1.6.0` (linha 5) contra
  `1.15.0` atual (`evals/manifest.lock.json:15`) e `platform: windows-py3.13.14` (linha 42).
  `evals/runs/` está no `.gitignore:16`. Ou seja: não existe baseline versionada nem compatível.
- **[F]** O `run` já falha em qualquer caso reprovado (`evals/core/runner.py:523`). Então o ganho real
  do `compare` é estreito e precisa ser dito: (1) as 5 métricas de ranking `blocking: after_baseline`
  (`evals/metrics-registry.yaml:47-86`) só passam a bloquear queda quando há baseline; (2) a baseline
  fixa o **denominador**: `case_selection_hash` e `dataset_hashes` (`governance.py:141-144`) fazem o CI
  falhar se alguém tirar uma `--suite` do `eval-gates.yml` — arquivo que **não** é protegido
  (`evals/protected-paths.txt:1-16`).
- **[F]** Épico de Cartas (327–368) e bestiário/tramas (349–361) sem caso de eval: nenhum dataset de
  `evals/datasets/regression/` cobre Cartas; o adapter registry (`evals/core/adapters.py:1418` e vizinhança)
  não tem operação de combate por Cartas. Os goldens 330/358 já são guardados por pytest
  (`tests/spec330_equivalence.py:1-12`, `docs/spec358/gerar_golden_v1.py:26`), mas cobrem **efeito por Carta**
  (330: hash por Carta, `tests/fixtures/spec330_legacy_golden.json:2-35`) e **simulador de arena** (358:
  `simulate_batch`, `tests/fixtures/spec358_sim_v1_golden.json:95-102`), não a **rodada**
  (`services/conflict_orchestrator.py:2501` `run_round`: vitalidade, fim de combate, Presságio).
- **[F]** Nenhuma medida recorrente com LLM real. `tests/test_playtest_real.py:52-81` existe, mas é
  pytest com `assert` (vira gate), sem teto de custo (só `max_requests`, linha 59) e só manual.
  O CI proíbe `--real` no `eval-gates.yml` (`tests/test_ci_eval_gates.py:105`).
- **[F]** A política de tiers Luna/Terra/Sol/Astra (`docs/evals-plan-v4/12_MODEL_EXECUTION_POLICY.md:7-10`,
  nomes de modelo GPT) não bate com os subagentes do Claude Code (`.claude/agents/*.md`: `code-locator`/
  `ci-watcher` haiku, `spec-executor`/`audit-reader` sonnet, `spec-author`/`spec-reviewer` opus). As specs
  da onda já escrevem "Terra (≡ Sonnet)" à mão (`specs/SPEC-375-refactor-higiene-index-ci.md:8`).
- **[H]** "Datasets sem commit desde 19/10" (auditoria §4.6): a Etapa 0 confirma com
  `git log -1 --format=%cs -- evals/datasets/regression`.

**Objetivo:** a menor mudança que deixa os evals vivos — baseline versionada comparada no CI, uma suíte
de combate por Cartas na rodada, uma medida semanal opt-in com LLM real (informativa) e uma tabela que
traduz os tiers para os agentes reais. A governança (lock de hashes, caminhos protegidos, aprovação do
environment) **fica**: ela é o que impede um agente que otimiza produto de mexer na régua, e esse risco
continua real.

## 2. Requisitos

- **R1 — Baseline versionada no CI.**
  - R1.1 Existe `evals/baselines/deterministic.json`: o JSON de um `evals run` das **mesmas** suítes e
    `--seed 7` do `eval-gates.yml`, gerado **pelo próprio CI** (ubuntu-24.04), sobre a `main`.
  - R1.2 `evals/baselines` entra em `evals/protected-paths.txt` (uma linha). Atualizar a baseline =
    só por eval authoring + `/eval-publish`.
  - R1.3 O job `deterministic-evals` roda, depois do `run`,
    `uv run python -m evals compare --current readiness_artifacts/evals/ci-<run>.json --baseline evals/baselines/deterministic.json --output readiness_artifacts/evals/compare.json`
    e o job falha se o exit code ≠ 0 (1 = regressão; 2 = baseline incompatível/stale).
  - R1.4 A versão do Python do job é fixada no patch (ex.: `3.13.N`), porque `platform` entra na
    compatibilidade (`evals/core/runner.py:442` → `governance.py:145`) e `.python-version` só diz `3.13`.
    Sem isso o CI fica vermelho sozinho quando o runner sobe de patch.
  - R1.5 Teste offline `tests/test_eval_baseline.py::test_baseline_bate_com_a_regua_atual`: carrega a
    baseline e chama `assert_run_matches_repository(meta, validate_repository(...))` — mudar dataset,
    evaluator ou registry sem regenerar a baseline falha já no pytest local.
  - R1.6 `evals/README.md` e `.claude/skills/eval-publish/SKILL.md` ganham o passo "regenerar a baseline"
    (§3.1). Nenhuma linha de `evals/core` muda por causa de R1.
- **R2 — Suíte `cards_combat` (~20 casos, determinística).**
  - R2.1 Novo dataset `evals/datasets/regression/cards_combat.jsonl`, `suite: "cards_combat"`, com
    operações sobre APIs públicas de produto: `services.card_effects.resolve_card`
    (`services/card_effects.py:1084`), `services.conflict_orchestrator.run_round`
    (`services/conflict_orchestrator.py:2501`) e `services.enemy_intent.public_intent`
    (`services/enemy_intent.py:252`).
  - R2.2 Oráculos só estruturados: dano aplicado, vitalidade final, condição aplicada/removida, Entropia
    gasta, combate encerrado + lado vencedor, intenção pública do Presságio (tipo/alvo, sem revelar Carta
    oculta). **Nenhum** oráculo compara texto de log/narração (voz muda; SPEC-367/368).
  - R2.3 Todo `expected` copia uma asserção que **já existe** em pytest ou golden, citada em
    `created_from` (`arquivo` e, na descrição, a função de teste). Proibido gerar `expected` rodando o
    produto atual e colando a saída (contrato §08: expected é autoria de fixture, não do produto).
  - R2.4 Distribuição mínima: 6 dano (inclui erro/acerto/crítico pelas seeds 2/13/21 do golden 330,
    `spec330_legacy_golden.json:4-27`), 4 condição (ex.: `antitoxina` sem condição a remover,
    `arc_aterramento` ganha condição — `spec330_legacy_golden.json:2-40`), 3 fim de combate, 3 Presságio,
    0–4 custo (ver R2.5). No máximo 2 casos do simulador 358 — e só se `scripts/cards/sim.py` for
    chamável pelo adapter sem importar o pacote `scripts` de forma frágil; senão, zero (é ferramenta de
    balanço, não produto).
  - R2.5 Casos de **custo de Fôlego** só depois da decisão da SPEC-377: hoje há duas implementações
    divergentes (`services/cards.py:442` × `services/card_effects.py:1595`, auditoria R3). Se a 380 rodar
    antes, eles ficam de fora e viram follow-up (D3).
  - R2.6 Adapter `CardsCombatAdapter` em `evals/core/adapters.py` (registrado ao lado de
    `"encounter_manifest"`, `adapters.py:1418`), reaproveitando o oráculo `projection` como
    `encounter_manifest.jsonl:1`. Sem evaluator novo. Se o runner exigir métrica própria por suíte **[H]**,
    entra `cards_combat_pass_rate` (`blocking: true`, `hard_limit: 1.0`) no registry e o
    `evaluator_version` sobe de minor.
  - R2.7 `--suite cards_combat` entra no comando do `eval-gates.yml`; `manifest.lock.json` é re-gerado
    (`python -m evals.core.governance lock`, `governance.py:235,285`); a baseline de R1 é gerada **depois**,
    já com a suíte nova.
  - R2.8 Teste `tests/test_eval_cards_combat.py`: a suíte passa, tem ≥ 16 casos, todo `created_from`
    aponta para arquivo existente, e nenhum `expected` contém chave de texto livre (`logs`, `narracao`).
- **R3 — Playtest real semanal, opt-in, informativo.**
  - R3.1 Novo workflow `.github/workflows/llm-playtest-weekly.yml` (não no `eval-gates.yml`, que proíbe
    `--real`). Gatilhos: `workflow_dispatch` sempre; `schedule` (segunda 09:00 UTC) **só** roda se a
    variável de repositório `RPG_WEEKLY_LLM_PLAYTEST == 'true'`. Nada de `push`/`pull_request`.
  - R3.2 Roda os 4 perfis vitais (`explorador`, `combate`, `diplomatico`, `secret_rusher` —
    `tests/test_playtest_real.py:42`) pela CLI, um por vez:
    `uv run python -m playtest run --profile <p> --turns 5 --seed 7 --real --max-requests 60 --max-cost 0.25`
    (a CLI tem os dois tetos, `playtest/__main__.py:430-435`; a suíte pytest não tem teto de custo).
  - R3.3 Sem gate de qualidade: o exit code de cada perfil é **registrado**, não propagado. O job só
    falha por **medição inválida**: nenhum turno com `provider` registrado ou `mock=True` (secret faltando).
  - R3.4 Métrica: para cada perfil, `turns_completed`, `aborted_reason`, contagem de violações por
    severidade e `check_id`, provider/modelo dominante e custo estimado — escritos no
    `$GITHUB_STEP_SUMMARY` via `playtest report <run_id>` e subidos como artefato (`playtest_runs/`).
    Sem histórico versionado (artefato do GitHub, 90 dias).
  - R3.5 `timeout-minutes: 45` no job; `concurrency` sem cancelamento.
  - R3.6 Teste `tests/test_ci_eval_gates.py::test_llm_playtest_semanal_e_opt_in_com_teto`: o YAML parseia,
    não tem `push`/`pull_request`, tem `workflow_dispatch`, o `schedule` está atrás de
    `vars.RPG_WEEKLY_LLM_PLAYTEST`, toda chamada `--real` tem `--max-cost` e `--max-requests` positivos e
    `--turns` ≤ 5.
- **R4 — Governança: manter e traduzir.**
  - R4.1 Tabela em `docs/evals-plan-v4/12_MODEL_EXECUTION_POLICY.md` (logo após a linha 10):
    Luna → Haiku (`code-locator`, `ci-watcher`); Terra → Sonnet (`spec-executor`, `audit-reader`);
    Sol → Opus (`spec-author`, `spec-reviewer`); Astra → Opus em **contexto independente** (outro agente,
    `model: opus` explícito) + aprovação do dono no `eval-governance` quando a régua muda. Não existe tier
    Claude acima de Opus; Astra é "quem revisa a régua", não "modelo maior".
  - R4.2 Uma linha em `AGENTS.md` § "Roteamento mínimo" apontando para a tabela.
  - R4.3 Lock de hashes, `protected-paths.txt`, `eval-protected.yml` e schemas **não** mudam (exceto a
    linha de R1.2). Simplificar mais é D4.

### Fora de escopo

- Juiz LLM como gate (segue informativo, `evals/README.md:15-18`).
- Qualquer mudança de produto (inclusive "consertar" algo que um caso novo de `cards_combat` revele:
  vira spec própria; o caso entra marcado e a spec para — ver §7).
- Reescrever, renomear ou apagar datasets existentes; mexer em evaluators existentes.
- Casos de eval para bestiário/tramas (349–361): o gate de fauna já tem eval protegido próprio
  (`scripts/fauna/eval.py`, `tests/test_spec360_eval.py`, `protected-paths.txt:15-16`). Follow-up se o dono quiser.
- Cobertura (`pytest-cov`, é a SPEC-379), long-runs de 30+ turnos, matriz 10×200.
- Tornar `eval-gates.yml` caminho protegido (D5).

## 3. Design técnico

### 3.1 Ciclo da baseline (R1)

A baseline precisa ser gerada na mesma plataforma do CI e bater com a régua do commit. Fluxo de eval
authoring (vale para esta spec e para as futuras):

1. Commit A (branch de eval): datasets/adapter/registry + `governance lock` + `--suite` no workflow.
2. Push → `eval-gates` roda; o `run` passa, o `compare` sai **2** (baseline stale). Esperado.
3. Baixar o artefato `deterministic-evals-<run_id>-<attempt>`, copiar `ci-<…>.json` para
   `evals/baselines/deterministic.json` (sem editar o conteúdo). Commit B.
4. Push → `compare` sai 0. A e B vão no **mesmo lote** do `/eval-publish` (1 aprovação).

O `product_sha` da baseline vai ser o do commit A, não o da `main` final: é esperado
(`evals/README.md:29-31` — o SHA de produto difere entre baseline e candidato).

**Arquivos alterados (R1):** `evals/protected-paths.txt` (+`evals/baselines`), `evals/baselines/deterministic.json` (novo),
`.github/workflows/eval-gates.yml` (Python fixado no job `deterministic-evals` via `setup-uv` input
`python-version`; passo `compare`), `evals/README.md`, `.claude/skills/eval-publish/SKILL.md`,
`tests/test_eval_baseline.py` (novo), `tests/test_ci_eval_gates.py` (asserta `evals compare` e
`evals/baselines/deterministic.json` no `eval-gates.yml`).

### 3.2 `cards_combat` (R2)

Formato do caso (mesmo schema de `evals/eval-case.schema.json`; ids reais do golden 330):

```json
{"id":"cards.condicao.antitoxina-sem-alvo","suite":"cards_combat",
 "description":"Antitoxina sem condição ativa gasta 1 de Entropia e não remove nada",
 "fixture":null,
 "input":{"operation":"resolve_card","card_id":"antitoxina","seed":2,
          "actor":{"virtudes":{"forca":3,"agilidade":2,"corpo":2,"mente":3,"carisma":2}},
          "target":null},
 "expected":{"entropia_delta":-1,"condicoes_removidas":[],"condicoes_aplicadas":[]},
 "oracle":"projection","tags":["cards","condicao","known-good"],"source":"regression",
 "created_from":"tests/test_card_effects_grammar.py"}
```

Operações do adapter (cada uma devolve só `actual`; projeção por caminhos, como `_project` em
`adapters.py:147`):

| operação | chama | `actual` projetado |
|---|---|---|
| `resolve_card` | `fx.bind` + `card_effects.resolve_card` | dano por alvo, `entropia_delta`, condições aplicadas/removidas |
| `round` | `conflict_orchestrator.run_round` com `rng` semeado | vitalidade final por ator, ferimentos, `combate_encerrado`, lado vencedor |
| `intent` | `enemy_intent.public_intent` | tipo da intenção, alvo, `revela_carta` (bool) |

Fontes para os `expected` (R2.3): `tests/test_card_effects_grammar.py` + golden 330 (dano/condição),
`tests/test_conflito_dano.py`, `tests/test_conflito_morte.py`, `tests/test_conflito_cartas.py`
(rodada/fim), `tests/test_enemy_intent.py` (Presságio). **[H]** Se `run_round` ler flags `RPG_*` de Cartas,
o adapter fixa o valor declarado em `input.flags` durante a chamada e restaura depois (o eval não pode
depender do env da máquina).

**Arquivos (R2):** `evals/datasets/regression/cards_combat.jsonl` (novo), `evals/core/adapters.py`
(adapter + registro), `evals/manifest.lock.json` (relock), `evals/metrics-registry.yaml` (só se R2.6 [H]),
`.github/workflows/eval-gates.yml` (`--suite cards_combat`), `tests/test_eval_cards_combat.py` (novo).
**Não** entra no `backend-selective` (a SPEC-375 tira de lá os `test_eval_*`; a suíte completa do
`validate.yml` roda o teste novo).

### 3.3 Workflow semanal (R3)

`.github/workflows/llm-playtest-weekly.yml`, job único `ubuntu-24.04`, `environment` = D2,
`uv sync`, laço sobre os 4 perfis com `set +e` capturando o exit code por perfil, depois um passo que
lê os `summary` em `playtest_runs/<run_id>/` (formato de `playtest/telemetry.py`) e falha só se nenhum
perfil tiver `mock=false` com provider registrado (R3.3). Upload de `playtest_runs/` com
`if-no-files-found: error`. Secrets por nome: `DEEPSEEK_API_KEY` (primário em todos os tiers),
`GROQ_API_KEY` (fallback grátis) e, **[H]** a confirmar na Etapa 0, `JINA_API_KEY` (primeiro da cadeia
de embeddings, `rag.py:92`; sem ele a cadeia cai para openai/ollama/gemini).

Custo **[H]**: 5 turnos × ~10 invokes × 4 perfis ≈ 200 chamadas por execução; teto duro
`--max-requests 60` por perfil (240) e `--max-cost 0.25` por perfil (US$ 1,00 por execução, ~US$ 4/mês
semanal). Se a tabela de preço da telemetria não conhecer o modelo DeepSeek, o custo estimado sai 0 e
só o teto de requests vale — a Etapa 0 verifica.

### 3.4 Tabela de tiers (R4)

Só documentação (`12_MODEL_EXECUTION_POLICY.md`, `AGENTS.md`); nenhum dos dois é caminho protegido.

## 4. Plano passo a passo

Etapas 1–3 formam **um lote** de eval authoring (um branch, uma aprovação). Etapa 4 (workflow) e
Etapa 5 (docs) não tocam caminho protegido e podem ir no mesmo branch, em commits separados.

### Etapa 0 — Travas e verificações (sem código)

1. **W1:** rodar o laço de `auditoria §6.2 W1` com a lista de arquivos de §3. Interseção com
   `evals/protected-paths.txt`, `evals/core/adapters.py`, `evals/manifest.lock.json`,
   `.github/workflows/eval-gates.yml` ou `tests/test_ci_eval_gates.py` ⇒ a etapa correspondente espera.
2. Confirmar os [H]: data do último commit em `evals/datasets/regression`; se o runner exige métrica por
   suíte (R2.6); se `run_round`/`resolve_card` leem flags; se `JINA_API_KEY` é necessário para o playtest
   real; se a telemetria estima custo do DeepSeek. Registrar as respostas na própria spec (§1/§3).
3. Ler o estado de SPEC-368 e SPEC-377. 368 não pousada ⇒ Etapa 2 espera. 377 não decidida ⇒ Etapa 2
   segue sem casos de custo (R2.5).

### Etapa 1 — Testes primeiro

1. `tests/test_eval_cards_combat.py` (vermelho: dataset não existe) — asserções de R2.8.
2. `tests/test_eval_baseline.py::test_baseline_bate_com_a_regua_atual` (vermelho: arquivo não existe) — R1.5.
3. `tests/test_ci_eval_gates.py`: `test_eval_gates_compara_com_baseline` (asserta `-m evals compare`,
   `--baseline evals/baselines/deterministic.json`, `--suite cards_combat` e Python com patch fixo no job
   `deterministic-evals`) e `test_llm_playtest_semanal_e_opt_in_com_teto` (R3.6).
4. Teste de `compare` contra baseline adulterada em `tmp_path` (copiar a baseline, baixar uma métrica
   `after_baseline`): exit 1. Mesmo teste com `dataset_hashes` alterado: exit 2. Prova que R1 não precisa
   de mudança em `evals/core`.

### Etapa 2 — Suíte `cards_combat` (protegido)

1. Escrever os casos (R2.3/R2.4), cada um com `created_from` real.
2. Adapter em `evals/core/adapters.py` + registro; registry só se R2.6 [H].
3. `uv run python -m evals.core.governance lock --root .` e `check`.
4. `uv run python -m evals --root . run --suite cards_combat --run-id local-cards` verde.
5. Se algum caso falhar contra o produto atual: **não** ajustar o `expected` para passar. Parar, registrar
   o caso e a asserção de origem no hand-back (é bug de produto ou asserção desatualizada — decisão do
   coordenador), e tirar o caso do lote.

### Etapa 3 — Baseline e `compare` no CI (protegido)

1. `evals/protected-paths.txt` += `evals/baselines`; workflow com Python fixo, `--suite cards_combat` e
   passo `compare`.
2. Commit A, push, baixar artefato, commit B com `evals/baselines/deterministic.json` (§3.1).
3. Verificação: `tests/test_eval_baseline.py`, `tests/test_ci_eval_gates.py`,
   `tests/test_eval_cards_combat.py`, `tests/test_eval_governance.py`, `tests/test_eval_harness.py`
   (`-n 2` no máximo; nada de suíte completa no subagente).

### Etapa 4 — Workflow semanal (não protegido)

1. `.github/workflows/llm-playtest-weekly.yml` conforme §3.3; teste R3.6 verde.
2. Nenhum disparo real pelo executor: o disparo é o smoke §6, feito pelo coordenador após D1/D2.

### Etapa 5 — Docs (não protegido)

1. Tabela R4.1 e linha R4.2.
2. `evals/README.md` e `SKILL.md` do `/eval-publish` com o ciclo §3.1.

### Etapa 6 — Publicação

1. `/eval-publish` (`bash scripts/dev/py.sh scripts/dev/eval_publish.py --base origin/main`): o lote não
   pode conter caminho de produto (`eval_publish.py:61-68`).
2. Dono aprova o environment `eval-governance` (D6). Revisão independente Astra (≡ Opus, outro agente)
   antes da aprovação: confere R2.3 caso a caso por amostra (≥ 5 casos) e roda o W2 item 2 uma vez.

## 5. Critérios de aceite

- [ ] `evals/baselines/deterministic.json` versionado, gerado pelo CI, e `evals/baselines` em `protected-paths.txt`
- [ ] `eval-gates` roda `evals compare` contra a baseline; um PR de produto qualquer fica verde; o teste de baseline adulterada sai 1 e o de dataset alterado sai 2
- [ ] Python do job `deterministic-evals` com patch fixo
- [ ] `cards_combat` com ≥ 16 casos (≥ 20 se D3 = esperar a 377), todos com `created_from` real, nenhum oráculo de texto, verde no CI
- [ ] `governance check` verde com o lock novo; nenhum dataset/evaluator antigo alterado (`git diff --stat main -- evals/datasets/regression evals/evaluators` só mostra `cards_combat.jsonl`)
- [ ] `llm-playtest-weekly.yml` opt-in (variável), com tetos, sem `push`/`pull_request`; teste R3.6 verde
- [ ] Tabela de tiers em `12_MODEL_EXECUTION_POLICY.md` + linha em `AGENTS.md`
- [ ] Lote publicado via `/eval-publish` com aprovação do dono; revisão independente registrada em `handoffs/SPEC-380-review.md`
- [ ] Zero arquivo de produto no diff (`eval_publish.py` não recusa)
- [ ] `uv run pytest` verde (suíte completa offline, coordenador no pouso)
- [ ] Smoke §6 executado

## 6. Smoke test com LLM real

R3 é o próprio smoke. Depois de D1/D2 resolvidos e secrets cadastrados:

1. Coordenador dispara `gh workflow run llm-playtest-weekly.yml` uma vez (manual).
2. Conferir no run: os 4 perfis com `mock=false` e provider registrado; custo estimado ≤ US$ 1,00;
   nenhum perfil abortou por teto de forma inesperada (se abortou por `max_cost`/`max_requests`, ajustar
   o teto na spec, não no código).
3. Conferir o `$GITHUB_STEP_SUMMARY` com a contagem de violações por perfil e o artefato `playtest_runs/`.
4. Registrar no hand-back: custo real, tempo total, violações por severidade (é o "ponto zero" da série).

Não há LLM nas Etapas 1–3 (tudo determinístico).

## 7. Riscos & compatibilidade

- **Saves:** nenhum efeito (não toca produto nem schema de estado).
- **MockLLM/FallbackLLM:** `cards_combat` é puro Python; nenhum `with_structured_output` novo.
- **CI vermelho por baseline stale:** toda mudança futura de régua quebra o `compare` até a baseline
  ser regenerada — é o comportamento desejado, mas precisa estar no `/eval-publish` (R1.6) para não
  parecer bug. Bump de patch do Python no CI ⇒ regenerar baseline (fica atrás do pin de R1.4).
- **Specs de Cartas em voo:** se a 368 ou um follow-up mudar de propósito um comportamento coberto por
  `cards_combat`, o executor dessa spec **não pode** editar o caso (protegido) e trava. Mitigação: casos
  só de comportamento estável (dano base, condição, morte, Presságio público), custo de Fôlego só após a
  377, e a spec que mudar comportamento de propósito declara `EVAL_AUTHORING_REQUIRED` desde o início.
- **Caso que reprova o produto atual:** sai do lote (Etapa 2.5); não se "conserta" eval para passar.
- **Custo/quota (R3):** opt-in duplo (variável + secrets); tetos por perfil; 5 turnos ≠ long-run
  (AGENTS.md trata long-run como 100/200 turnos e matriz 10×200). Free tier do Groq pode dar 429 —
  o roteamento troca de provider; aparece como `fell_back` na telemetria, não como falha.
- **Conflito com outras sessões:** W1 em cada etapa; 370/374/375 antes; W8 sem reescrita de histórico.

## 8. Decisões do dono

- **D1 — Playtest real semanal:** ligar o `schedule` (variável `RPG_WEEKLY_LLM_PLAYTEST=true`) ou deixar
  só manual? Orçamento proposto: teto US$ 1,00 por execução (~US$ 4/mês). Recomendação: ligar depois
  do smoke §6, se o custo real ficar abaixo do teto.
- **D2 — Secrets/environment:** criar environment novo `llm-playtest` (sem revisores, para o agendamento
  não esperar clique) com `DEEPSEEK_API_KEY` + `GROQ_API_KEY` (+ `JINA_API_KEY` se a Etapa 0 confirmar),
  ou reusar `eval-provider` (hoje só tem `GOOGLE_API_KEY`, `eval-protected.yml:24-37`, e pode exigir
  aprovação a cada run)? Recomendação: environment novo.
- **D3 — Custo de Fôlego em `cards_combat`:** esperar a SPEC-377 unificar `custo_folego` (20 casos de uma
  vez) ou publicar agora com ~16 casos e acrescentar os de custo depois (segunda aprovação)?
  Recomendação: publicar sem eles; a 377 já vai pedir eval authoring.
- **D4 — Governança:** manter como está + tabela (recomendado) ou simplificar mais (a auditoria sugeriu
  lock só de `evals/core` e apagar a política de tiers)? Simplificar abre espaço para um agente de produto
  editar dataset/expected sem aprovação; com 1 dev e vários agentes em paralelo o lock ainda paga o custo.
- **D5 — Proteger `eval-gates.yml`?** Hoje não é protegido; a baseline (R1) já pega a remoção de uma
  `--suite`, mas não a remoção do passo `compare`. Proteger obriga aprovação em toda mudança de CI
  (inclusive a SPEC-375). Recomendação: não proteger; revisão humana do diff de workflow basta.
- **D6 — Aprovar o lote** no environment `eval-governance` quando o `/eval-publish` imprimir o comando
  (1 clique; pré-requisito `EVALUATOR_CHANGE_APPROVED=true` no environment, já documentado no SKILL).
