# SPEC-212 — Beta de gameplay desktop: gate de jornada vertical

> **Status:** `in-progress`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-199, 200, 202, 203, 204, 205, 206, 207, 209, 210, 211 (onda beta desktop) + SPEC-226..235 (bloqueadores de bug de gameplay/API) + SPEC-218, 219 (deploy exposto fail-closed e cota por owner antes de convidar testers) — todas `done` · leitura (não editar): SPEC-172 `done`, SPEC-173 `done`, SPEC-197 `in-progress` (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-216; go do beta pago (D6) via handoff para SPEC-197; convite de testers desktop (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 15
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — jornada vertical nova (J-V1) e oráculos novos (console/duplicação/segredo/a11y/latência-presença) em `evals/` e `web/e2e/`; autoria em tarefa separada, antes do executor de produto.

---

## 1. Contexto & Objetivo

**[F]** O repositório já tem um gate frontend F01–F16 (SPEC-172): `web/e2e/critical-journeys.yaml` (16 jornadas `hard: true`), `web/e2e/critical-journeys.spec.ts`, fixture com guardas globais de `pageerror`/`console.error`/HTTP>=500/`requestfailed` em `web/e2e/fixtures.ts`, normalização do relatório em `scripts/frontend_eval_report.py` e CI seletivo (SPEC-173, `.github/workflows/eval-gates.yml`). Porém essas jornadas rodam contra `DeterministicBackend` (rotas de API interceptadas no navegador) e F16 só cobre 320/390/768/1440; **nenhuma jornada percorre a campanha inteira numa só sessão** (criar → conversar → combater → vencer/morrer → consultar abas → salvar/reabrir → exportar).

**[F]** `scripts/release/checklist.py` (SPEC-196/197) produz `docs/spec197/evidence/checklist-<sha12>.json` com `{schema, env, sha, ok, failing, results[]}`; é gate de infra/negócio (migrations, CI, health SHA, legal, riscos). SPEC-197 declara que o go final depende de checklist `--strict` verde (`docs/spec197/decision-request.md`, item 13), mas não tem nenhum critério de gameplay.

**[D]** (D6 do pacote) Esta spec é o gate de "beta jogável desktop" para usuários gratuitos/convidados e é **pré-requisito de go do beta pago**. Android/mobile não bloqueia (SPEC-216 é posterior; SPEC-198 não puxa mobile antes do desktop).

**Objetivo:** definir e implementar um gate reprodutível, determinístico (MockLLM, zero provider real), que prove a jornada vertical J-V1 com oráculos objetivos, e emita evidência por SHA consumível pela SPEC-197 sem alterá-la. Não entrega features de gameplay: só as integra e mede.

## 2. Requisitos

Jornada J-V1 (uma sessão contínua, backend real em modo `RPG_FORCE_MOCK=1`, navegador Chromium):

- **R1** — Criar personagem escolhendo raça e classe na UI (wizard SPEC-046) e abrir o chat com cena inicial narrada.
- **R2** — Interlocutor (SPEC-202), dois passos obrigatórios do prompt 15: (a) **pergunta ao narrador sobre** um NPC presente (ex.: "Quem é aquele homem no balcão?") é respondida pelo narrador e **não** vira fala do NPC; (b) em seguida, fala **dirigida** ao NPC é roteada ao NPC sem comando especial nem seletor Narrador/NPC. Oráculo: falante de cada turno no histórico/UI = esperado da fixture.
- **R3** — Ameaça no chat dispara combate; a aba Combate abre em split (SPEC-204 R10) com o manifesto da SPEC-203 (`combat.encounter_view`); oráculo: os `participant_id` (= `enemy.id`) exibidos permanecem os mesmos do manifesto até o desfecho (sem troca de identidade/desaparecimento).
- **R4** — Jogar carta com alvo por gesto direto, sem confirmação repetida (SPEC-205): carta com alvo = selecionar + clicar `participant_id`; sem alvo = um clique. Oráculo: nº de cliques por ação ≤ 2 e nenhum diálogo de confirmação; resultado mecânico (dano/Reação) aparece na UI.
- **R5** — Dois desfechos determinísticos em campanhas-semente distintas: **vitória** (loot/retorno narrativo; `combat_result.outcome` da SPEC-203 R7) e **derrota/morte** (`death_pending` + `DeathModal`, SPEC-060; restore do checkpoint ou aceitar). Após vitória, o turno seguinte é exploração sem mensagem extra (SPEC-203 R6).
- **R6** — XP/nível aparece em componente de UI estruturado alimentado por `turn_outcome` (SPEC-199: `xp_delta`, `level_delta`, `level_after`, `receipt_id`) e **não** como número na prosa; oráculo: a prosa do turno não contém padrão `\d+\s*XP`/`[RESULTADO]`, e o XP exibido = `turn_outcome.xp_delta` = delta de `player.xp`; replay do mesmo `action_id` devolve o mesmo `receipt_id` sem dobrar XP.
- **R7** — Abas Codex, Personagem, Combate, Bestiário, Mapa abrem e renderizam conteúdo coerente com o estado (SPEC-204/209/210/211); entidade ausente mostra placeholder honesto (nunca imagem errada).
- **R8** — Salvar, recarregar a página e reabrir a campanha preserva local, vitalidade, inventário, XP e histórico visível, sem turno duplicado.
- **R9** — Exportar sessão sob demanda pelo dono (SPEC-207) e validar o artefato: schema ok, PII redigida, ausência de segredo não revelado.

Critérios transversais (aplicam-se a J-V1 e às F01–F16):

- **R10** — Zero `pageerror`, zero `console.error` e zero request falha/HTTP>=500 inesperados (reusa guardas de `web/e2e/fixtures.ts`; lista de permitidos explícita e versionada, vazia por padrão).
- **R11** — Zero turno duplicado: ao longo de J-V1 (incluindo retry/replay forçado de um `action_id` e reload no meio do SSE), cada `action_id` produz exatamente um turno em `world.turn_count`/histórico/export.
- **R12** — Zero segredo vazado: oráculo determinístico baseado em `services/secret_signatures.py` (`find_unrevealed`, `revealed_corpus` — [F] existem hoje) e em `assert_no_player_leak` da SPEC-206 (a ser criado lá; não reimplementar aqui) varre prosa, painéis das abas, API pública e export; qualquer match de `hidden`/`secret` não revelado reprova.
- **R13** — Métricas de latência com os nomes da SPEC-200 (**TTFMC**, não TTFT; `ack_server_ms`, `ttfmc_server_ms`, `ttlt_server_ms`, `phase_ms`, `transport`, `pseudo_streaming` na linha `rpg.turn`; marcas cliente `rpg:turn:<action_id>:*`) estão **presentes** em todo turno de J-V1 e agregadas em p50/p95 (nearest-rank, "p95 indicativo" com n < 20). Turnos `transport=stream` exigem `ttfmc/ttlt` não nulos; turnos `transport=post` (fallback) têm `ttfmc_server_ms`/`ttlt_server_ms` nulos por contrato e contam como presentes pela marca cliente. O gate liga `RPG_CLIENT_LATENCY_REPORT=1` (default da SPEC-200 é desligado). **Sem meta de valor** nesta spec: o gate falha só por ausência/corrupção da métrica; o baseline é registrado como evidência.
- **R14** — F01–F16 verdes em viewports desktop **1440x900** e **1280x800** (F16 mantém os viewports móveis existentes como não-bloqueantes para este gate, mas não podem regredir).
- **R15** — A11y: `@axe-core/playwright` com zero violações `serious`/`critical` em cada aba de J-V1 e em cada viewport desktop.
- **R16** — Evidência por SHA: `docs/spec212/evidence/gameplay-gate-<sha12>.json` + `.md` (mesmo estilo de `scripts/release/checklist.py`: `schema`, `sha`, `ok`, `failing`, `results[]` com `name/status/blocking/detail`), com `dirty_files == 0` exigido para `ok: true`.
- **R17** — Known-issues: `docs/spec212/known-issues.md` classifica cada item como **bloqueia beta** vs **aceitável no beta**; item `P0/P1` aberto com impacto em R1–R9 reprova o gate.

### Fora de escopo

- Android/iOS/mobile single-pane (SPEC-216) e qualquer exigência em 320–768px para J-V1.
- Provider real, campanhas longas, matriz 100/200 turnos; qualidade de prosa/persona.
- Memória hierárquica, arquivista assíncrono, conhecimento por NPC (SPEC-213–215) e Jev (SPEC-217).
- Cobrança, wallet, Stripe, legal, infra cloud (SPEC-190–198). Esta spec **não edita** SPEC-197, SPEC-198 nem `scripts/release/checklist.py`.
- Metas numéricas de latência (decisão futura pós-baseline, D3).

## 3. Design técnico

### 3.1 Estado atual relevante

- **[F]** `web/playwright.config.ts`: `testDir ./e2e`, `retries: 0`, único projeto `chromium` com `devices["Desktop Chrome"]` (viewport 1280x720 por default), `webServer` = Vite em 4173; reporter JSON em `web/test-results/results.json`.
- **[F]** `critical-journeys.spec.ts` usa `backend` fixture determinística (API simulada no navegador); `audit-local.yml` já sobe stack real (`scripts/dev_stack.py`) e roda `scripts/audit_local_gate.py` com `--extra browser` (Python/Playwright), usando o MockLLM.
- **[H]** J-V1 deve rodar contra a **stack real em MockLLM** (não contra `DeterministicBackend`), pois R8/R9/R11 exigem save, SSE e export reais. [F, revisão] O export da SPEC-207 responde 404 no perfil `legacy` (SPEC-207 R14) e exige prova de auth recente; logo J-V1 roda a API com `RPG_RUNTIME_PROFILE=local` + `RPG_FORCE_MOCK=1` sobre o Supabase local de `scripts/dev_stack.py` (portas 55321–55324), com usuário sintético confirmado só no GoTrue local (padrão de `scripts/audit_local_gate.py`), servindo `web/dist` pela própria API. O `playwright.config.ts` atual sobe Vite em 4173 com API simulada; J-V1 precisa de config/projeto próprio com `baseURL` da API real e sem `webServer` Vite. [H] MockLLM precisa produzir roteamento narrador×NPC e ameaça determinísticos para R2/R3 — se não produzir, as fixtures-semente da Etapa 0 forçam o caminho (estado semeado), nunca relaxando o oráculo. Seeds de combate (vitória/derrota) vêm de fixtures de estado via `/game/new` com `scenario`/seed Python — sem tocar mecânica.
- **[H]** As specs 199–211 são dependências ainda `draft`; contratos finais de UI (seletores/`data-testid`) serão lidos delas na execução. Esta spec fixa apenas nomes lógicos; o executor mapeia para os `data-testid` reais.

### 3.2 Arquivos novos

- `web/e2e/vertical-journey.spec.ts` — J-V1 em Playwright (TS), uma sessão, etapas `test.step` nomeadas `V01..V09` (R1..R9).
- `web/e2e/vertical-support.ts` — helpers: criação de campanha-semente (vitória/derrota), coletor de métricas de turno, runner axe por aba, leitor do export.
- `web/e2e/critical-journeys.yaml` — **alterado pela tarefa de eval-authoring**: adiciona `V01`–`V09` com `hard: true`, `suite: vertical`, `viewports: [1440x900, 1280x800]` (schema_version sobe para 2; consumidores atualizados junto).
- `scripts/beta_gameplay_gate.py` — orquestra: sobe/valida stack (`scripts/dev_stack.py`), roda `npx playwright test` (F01–F16 + vertical, dois viewports), roda oráculos Python (R11/R12/R13/R16), emite `gameplay-gate-<sha>.{json,md}`. Funções puras testáveis (`build_report`, `check_*`) com `Deps` injetável, no estilo de `scripts/release/checklist.py` (importa `Result`/`write_report` apenas para **leitura de formato**; não o altera).
- `services/gameplay_oracles.py` — oráculos puros e determinísticos: `no_duplicate_turns(history, action_ids)`, `no_unrevealed_secret(texts, state)` (envolve `secret_signatures.find_unrevealed` + taxonomia SPEC-206), `xp_not_in_prose(prose, turn_outcome)`, `latency_present(turn_metrics)` (nomes SPEC-200), `speaker_matches(history, expected)`, `roster_stable(encounter_views)`.
- `tests/test_gameplay_oracles.py`, `tests/test_beta_gameplay_gate.py` — testes offline dos oráculos e do orquestrador.
- `docs/spec212/README.md`, `docs/spec212/known-issues.md`, `docs/spec212/evidence/` — contrato, classificação e evidência.
- `.github/workflows/beta-gameplay-gate.yml` — job `workflow_dispatch` + `pull_request` com path-filter em `web/**`, `agents/**`, `services/**`, `api.py` (padrão SPEC-173); sem provider real.

### 3.3 Arquivos alterados

- `web/playwright.config.ts` — projetos `desktop-1440` (1440x900) e `desktop-1280` (1280x800) ao lado de `chromium`; `retries: 0` mantido; `workers: 1`.
- `web/e2e/critical-journeys.spec.ts` — apenas parametrização de viewport se necessário (sem relaxar asserts; F16 intacto).
- `scripts/frontend_eval_report.py` — aceita `V01..V09` no `JOURNEY_RE` e agrega por viewport (mudança de leitura de relatório; **eval-authoring**).
- Nenhuma alteração em `scripts/release/checklist.py`, SPEC-197/198, `evals/manifest.lock.json` sem o relock da tarefa de autoria.

### 3.4 Contratos de dados

Evidência (R16), exemplo:

```json
{
  "schema": 1, "gate": "beta-gameplay-desktop", "sha": "<git rev-parse HEAD>",
  "dirty_files": 0, "ok": true, "failing": [],
  "viewports": ["1440x900", "1280x800"],
  "results": [
    {"name": "journeys_f01_f16", "status": "pass", "blocking": true, "detail": {"passed": 32, "failed": 0}},
    {"name": "vertical_v01_v09", "status": "pass", "blocking": true, "detail": {"steps": 9}},
    {"name": "console_clean", "status": "pass", "blocking": true, "detail": {"errors": 0}},
    {"name": "no_duplicate_turns", "status": "pass", "blocking": true, "detail": {"action_ids": 14, "duplicates": 0}},
    {"name": "no_secret_leak", "status": "pass", "blocking": true, "detail": {"surfaces_scanned": 9, "matches": 0}},
    {"name": "latency_present", "status": "pass", "blocking": true, "detail": {"turns": 14, "transport": {"stream": 13, "post": 1}, "pseudo_streaming": true, "ttfmc_ms": {"p50": 0, "p95": 0}, "ttlt_ms": {"p50": 0, "p95": 0}, "baseline_only": true}},
    {"name": "a11y_serious_critical", "status": "pass", "blocking": true, "detail": {"violations": 0}},
    {"name": "known_issues_no_blockers", "status": "pass", "blocking": true, "detail": {"blocking_open": 0}}
  ]
}
```

Os valores de `ttfmc_ms`/`ttlt_ms` acima são placeholders de formato; o baseline real é gravado na execução.

### 3.5 State ownership

- Estado de jogo, XP, combate, conhecimento: backend (Python). A UI só apresenta; o gate lê via API pública e UI, nunca altera estado fora das ações de jogador.
- Métricas de latência: produzidas pela SPEC-200; o gate só as lê e agrega (não instrumenta produto).
- Evidência: arquivos em `docs/spec212/evidence/`, escritos apenas pelo script do gate.

### 3.6 Degradação/fallback

- Stack indisponível ou browser ausente: status `not_provisioned` (não `pass`); `--strict` trata como falha (mesma semântica de `run_checklist`).
- Export (SPEC-207) exige prova de auth recente (D4): J-V1 roda em perfil `local` (ver §3.1) e reautentica o usuário sintético antes de V09. V09 nunca é `skip` em `--strict`; stack sem perfil `local` → `not_provisioned` (falha em `--strict`).
- Métrica de latência ausente em qualquer turno: `fail` (não há fallback silencioso).

### 3.7 Relação com SPEC-197 (handoff, sem edição)

A evidência desta spec é consumida por SPEC-197 como **pré-condição do go** (D6). Entrega via `docs/spec212/handoff-spec197.md`: caminho do `gameplay-gate-<sha12>.json`, SHA exigido (o mesmo SHA do `checklist-<sha12>.json` de produção ou ancestral comprovado) e proposta de linha para o `decision-request` ("Beta jogável desktop certificado: sim/não"). O coordenador/dono incorpora na SPEC-197; esta spec não a edita.

## 4. Plano passo a passo

Pré-condição: SPEC-199–211 `done` (nada aqui antecipa essas entregas).

### Etapa 0 — Autoria de eval (tarefa separada, `EVAL_AUTHORING_REQUIRED`)

1. Autor de eval (não o executor de produto) escreve: V01..V09 em `critical-journeys.yaml` + esqueleto de `vertical-journey.spec.ts` (asserts, sem produto novo), oráculos esperados e fixtures-semente, e faz relock (`evals/manifest.lock.json`) com aprovação de `eval-governance`.
2. Review Sol da autoria antes de qualquer otimização.

### Etapa 1 — Oráculos puros

1. **Testes** (`tests/test_gameplay_oracles.py`): `test_duplicate_action_id_detected`, `test_unrevealed_secret_in_prose_fails`, `test_revealed_secret_passes`, `test_xp_number_in_prose_fails`, `test_xp_matches_receipt_passes`, `test_latency_missing_fails`, `test_latency_present_baseline_only`, `test_post_transport_null_server_ttfmc_ok`, `test_narrator_question_not_npc_speaker`, `test_manifest_ids_stable`, `test_replay_same_receipt_no_double_xp`.
2. **Implementação:** `services/gameplay_oracles.py`, reusando `services/secret_signatures.py` (`find_unrevealed`, `revealed_corpus`).
3. **Verificação:** `uv run pytest tests/test_gameplay_oracles.py` verde.

### Etapa 2 — Orquestrador e formato de evidência

1. **Testes** (`tests/test_beta_gameplay_gate.py`): `test_report_ok_requires_zero_dirty`, `test_not_provisioned_blocks_in_strict`, `test_report_schema_matches_checklist_style`, `test_failing_lists_blocking_only`, `test_known_issues_blocker_fails`.
2. **Implementação:** `scripts/beta_gameplay_gate.py` com `Deps` injetável.
3. **Verificação:** `uv run pytest` verde.

### Etapa 3 — Playwright desktop

1. Projetos `desktop-1440`/`desktop-1280`; rodar F01–F16 em ambos (`cd web && npx playwright test --project=desktop-1440 --project=desktop-1280`).
2. Corrigir apenas **produto** (não a régua) quando uma jornada falhar; falha de régua volta à Etapa 0.

### Etapa 4 — Jornada vertical J-V1

1. Implementar/estabilizar `V01..V09` contra a stack real em MockLLM, com campanhas-semente de vitória e derrota.
2. Forçar replay de `action_id` e reload no meio de SSE (R11).
3. Axe por aba/viewport (R15).

### Etapa 5 — Evidência, known-issues e handoff

1. `uv run python scripts/beta_gameplay_gate.py --strict` no SHA candidato, árvore limpa.
2. Preencher `known-issues.md`; escrever `handoff-spec197.md`.
3. Review Sol com o JSON/MD e traces de falha (se houver).

## 5. Critérios de aceite

- [x] Etapa 0 concluída e relockada por tarefa separada; executor de produto não editou evaluator/expected/dataset protegido.
- [ ] J-V1 (V01..V09) verde em 1440x900 e 1280x800 contra stack real + MockLLM. *(parcial: verde em execuções isoladas, incl. a do gate completo; V07/V08 flaky ~50% por defeito de autoria — `handoffs/SPEC-212-etapa0-followup.md`, KI-11)*
- [x] F01–F16 (hoje F01–F40, 36 jornadas) verdes nos dois viewports desktop; F16 móvel não regrediu (gate local 2026-10-17, 36/36 por viewport).
- [x] Zero `pageerror`/`console.error`/request inesperado em toda a execução (execução verde do gate).
- [x] Zero turno duplicado (inclui replay de `action_id` e reload mid-SSE) (execução verde do gate).
- [x] Zero segredo não revelado em prosa, abas, API pública e export (execução verde do gate).
- [x] Latência (TTFMC/TTLT, nomes da SPEC-200) presente em 100% dos turnos (R13 corrigido: `rpg.turn` de stream sai após ttfmc/ttlt); p50/p95 baseline registrados (sem meta de valor).
- [x] XP aparece na UI estruturada e não como número na prosa; export válido e redigido (execução verde do gate).
- [x] Axe: zero `serious`/`critical` em cada aba, em ambos os viewports (execução verde do gate).
- [ ] `docs/spec212/evidence/gameplay-gate-<sha12>.json` com `ok: true`, `dirty_files: 0`, SHA = HEAD avaliado. *(pendente: gerar após commit, árvore limpa: `uv run python scripts/beta_gameplay_gate.py --strict`; ver `docs/spec212/handoff-spec197.md`)*
- [ ] `known-issues.md` sem bloqueador aberto (KI-11 aberto: V07/V08 flaky, autoria de eval); `handoff-spec197.md` entregue.
- [x] `uv run pytest` verde (suíte completa offline, exit 0, sem `test_project_index`); build `cd web && npm run build` verde; `uv run python scripts/validate_content.py` sem erros.
- [x] Guard de FallbackLLM: não aplicável (nenhum structured output novo); confirmar na revisão.
- [x] Saves antigos continuam carregando (nenhuma mudança de schema nesta spec).

## 6. Smoke

- **Offline/MockLLM (padrão, obrigatório):** `uv run python scripts/dev_stack.py start` → `uv run python scripts/beta_gameplay_gate.py --strict` → `stop`. Custo zero.
- **Provider real:** **não executado por padrão.** Opt-in somente com autorização do dono, teto explícito (sugerido: <= 40 requests e <= US$ 0,10, uma única passada de J-V1 curta) e sem substituir o gate determinístico. O gate real não é requisito de `done`.

## 7. Riscos & compatibilidade

- **Dependência em cadeia:** 11 specs `draft` precedem esta; seletores/contratos podem mudar. Mitigação: nomes lógicos aqui, mapeamento na execução; esta spec só é `approved` quando as dependências estiverem `done`.
- **Flakiness de SSE/animações:** `reducedMotion: reduce` e `retries: 0` mantidos; instabilidade é bug a corrigir, não retry.
- **Viés do MockLLM:** esconde bugs de mapeamento de campos reais (CLAUDE.md). Mitigação: smoke real opt-in e contratos `-m llm_contract` existentes continuam obrigatórios onde as dependências tocarem structured output.
- **Integridade da régua:** novas jornadas alteram `critical-journeys.yaml` e `frontend_eval_report.py` (protegidos); só via Etapa 0 + relock + `eval-governance`.
- **Saves:** nenhuma migração prevista; se alguma dependência 199–211 alterar schema, o teste round-trip é dela.
- **Falso verde por viewport:** `desktop-1280` (1280x800) difere do default do Playwright (1280x720); projetos fixam viewport explicitamente.

## 8. Pontos de decisão do dono

- **D-212-1:** J-V1 contra stack real+MockLLM (recomendado, R8/R9/R11 exigem save/SSE/export reais) vs. `DeterministicBackend` (mais rápido, não prova persistência). **Default: stack real.**
- **D-212-2:** F16 móvel (320–768) permanece como regressão não-bloqueante neste gate (recomendado, alinha D6/Android não bloqueia) vs. bloqueante. **Default: não-bloqueante.**
- **D-212-3:** Gate roda em PR (path-filtered) além de `workflow_dispatch`. **Default: ambos; obrigatório (required check) apenas no SHA candidato ao go.**
- **D-212-4:** Consentimento do tester/texto legal para export (D4) entra via handoff para SPEC-197, sem edição direta. **Default: handoff.**
- **D-212-5 (registrada 2026-10-17, Etapa 0):** o dono autorizou executar a onda. SPEC-218/219 estão `in-progress` só nos itens de staging/GitHub; o código delas já está na `main`. O gate roda localmente (stack real + MockLLM) e **não convida testers**, então a dependência de 218/219 `done` condiciona **somente o convite de testers**, não a execução desta spec. **Default: executar; convidar só com 218/219 `done`.**

## 9. Evidência requerida

- `docs/spec212/evidence/gameplay-gate-<sha12>.json` e `.md` (R16), mais `web/test-results/results.json` e traces/screenshots/vídeos de falhas (se houver).
- Saída de `uv run pytest` (suíte completa) e `npm run build`.
- Baseline de latência (p50/p95 TTFMC/TTLT) como número registrado, sem meta.
- `docs/spec212/known-issues.md` e `docs/spec212/handoff-spec197.md`.
- Parecer de review Sol (independente) e registro da autoria de eval (Etapa 0) com hash de relock.

## 10. Registro da execução de produto (2026-10-17)

- **Desvio D-1:** `rpg.turn` de stream sai depois de ttfmc/ttlt (`TurnTimeline.hold_log/submit_log/release_log` + `_stream_turn`); desconexão libera a linha com marcas nulas.
- **Desvio D-2:** modal de nível espera o painel de desfecho (`levelUpHeldByOutcome`); dispensa do desfecho elevada ao `PlayScreen`.
- **Decisões documentadas sem código:** aliado fora do manifesto (contrato SPEC-203 é de `enemies`), dado sem seed (§3.1 proíbe tocar a mecânica), beacon `ERR_ABORTED` (cliente não usa `keepalive`; allowlist mantida). Ver `docs/spec212/known-issues.md`.
- **Orquestrador:** `scripts/beta_gameplay_gate.py` + `services/gameplay_oracles.py` (mapa de nomes → régua). Playwright `workers=1` com configs temporárias; os projetos `desktop-1440/1280` são gerados pelo script (não alteram `web/playwright.config.ts`).
- **Pendente para `done`:** correção de autoria do V07/V08 (follow-up) + relock; evidência `gameplay-gate-<sha12>.json` `ok: true` no commit; revisão Sol; aprovação `eval-governance` para publicar.
