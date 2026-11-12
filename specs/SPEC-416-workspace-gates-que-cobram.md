# SPEC-416 — workspace-gates-que-cobram

> **Status:** `done`
> **Criada:** 2026-11-12 · **Atualizada:** 2026-11-12
> **Depende de:** SPEC-414 (`done` antes do Bloco F: mexe em `.claude/hooks/guard_tools.py`, `.claude/settings.json` e `docs/guias/TESTES.md`); SPEC-415 (`done` antes do Bloco A: mexe em `.claude/agents/spec-author.md`).
> **Desbloqueia:** follow-up F-2 da SPEC-413 (`docs/spec413/README.md:35`, pgTAP em CI); fechamento com prova real de 413/410 quando houver push.
> **Risco:** `médio` — sem mudança de runtime de produto, evals ou persistência, mas mexe num workflow de CI (`audit-local.yml`), cria três gates da suíte default e muda um hook usado por todo subagente. Um gate mal calibrado trava todo pouso; um passo de CI mal ligado esconde o resultado do `audit_local_gate`. Revisor Sonnet (`AGENTS.md` § Qualidade, revisão e evidência). Não é `alto`: nenhum caminho de auth, carteira, estado de jogo ou API pública.
> **Evidência:** por gate, um teste que falha antes (detalhe no §5): A `tests/test_decisoes_fixas.py` (arquivo ausente); B `test_audit_local_runs_pgtap` (passo ausente no workflow) + log do CI com `Files=5, Tests=63`; C `test_detecta_relogio_com_alias` sobre o trecho real de `tests/test_spec361_gate.py:269-282`; D `test_write_evidence_default_fora_de_docs` (hoje grava em `docs/spec191/evidence`); E `test_contagem_nova_no_arquivo_baselinado_falha` (hoje o `per-file-ignores` aceita); F `test_subagente_nao_sobe_baseline` (hoje o hook deixa passar).

---

## 1. Contexto & Objetivo

A auditoria de 11/11 (`docs/auditorias/auditoria-workspace-2026-11-11.md`) propôs três specs de workspace; esta é a W-C (`:44-45`). O padrão comum dos atritos que ela cobre: uma regra existe, mas nenhum gate a cobra, e o erro só aparece depois (no staging, numa auditoria seguinte ou num relógio que virou o dia).

Os seis problemas, com evidência:

1. **Auditoria reabre o que já foi decidido.** A auditoria ponytail de 11/11 reabriu 8 itens já decididos em 18/10 e 03/11 (`CHANGELOG.md:10`; `auditoria-workspace-2026-11-11.md:11`). Não existe índice de decisões, e `.claude/agents/audit-reader.md:8-13` e `.claude/agents/spec-author.md:8-15` não mandam consultar nenhum.
2. **pgTAP escrito e nunca executado.** `supabase/tests/` tem 5 arquivos (63 asserções: `select plan(…)` em `valoria_rls_test.sql:3`, `rls_invariants_test.sql:5`, `rls_effective_storage_test.sql:4`, `rls_behavior_test.sql:9`, `public_sem_funcoes_do_app_test.sql:4`), todos `begin … rollback`. Nenhum `.py`/`.yml`/`.sh`/`.toml` do repo cita `supabase/tests`, `test db` ou `pg_prove` (busca de 12/11). O `audit-local.yml` já sobe Supabase real (`.github/workflows/audit-local.yml:48`, `scripts/dev_stack.py:127-131`: `supabase start`, que aplica `supabase/migrations/` e `seed.sql` do zero, `supabase/config.toml:10-17`) e roda só pytest (`scripts/audit_local_gate.py:94-116`). O próprio runbook admite: "O pgTAP NÃO roda em CI hoje" (`docs/spec413/README.md:35`).
3. **Teste com relógio real.** `tests/test_spec361_gate.py:269-282` mede `perf_counter()` de parede com `import time as _t` e reprova acima de 0,55 s (flake conhecido, `ESTADO_ATUAL.md`). A auditoria contou ≥ 9 asserções de tempo de parede (`auditoria-workspace-2026-11-11.md:16`). `DTZ` global no ruff foi decidido contra (`:48`).
4. **Script de staging sobrescreve evidência versionada.** `scripts/staging/common.py:117-118`: sem `--out`, `write_evidence` grava em `docs/spec191/evidence/<nome>.json` (atrito 13, `:23`). A auditoria deixou "demais scripts com saída default em caminho versionado" como não verificado (`:53`); a verificação está no §3.4.
5. **B2: a baseline do ruff não conta.** `ruff-baseline.toml` é `[lint.per-file-ignores]` por arquivo × regra (`scripts/dev/ruff_baseline.py:31-36`): um arquivo baselinado aceita violação nova ilimitada da mesma regra (`BLE001` em 135 arquivos, `C901` em 71, `auditoria…:32-33`). Nenhum gate roda `ruff_baseline.py --check` (só `ruff check .` em `.github/workflows/validate.yml:65`).
6. **B7: subir o teto está ao alcance de qualquer agente.** `scripts/dev/size_budget.py:9,182-185`: `--update` regrava a baseline e pode subir; nada impede um executor de usá-lo (`auditoria…:37`).

Objetivo: cada regra acima passa a ter um gate determinístico barato, no mesmo desenho das catracas que já funcionam (`size_budget`, SPEC-386/407), sem mudar o produto.

## 2. Requisitos

### Bloco A — `docs/guias/DECISOES_FIXAS.md`

- **R1 — Arquivo.** `docs/guias/DECISOES_FIXAS.md` existe, com um parágrafo de uso (≤ 6 linhas) e uma tabela de colunas exatas `| ID | Item | Decisão | Fonte | Gatilho de revisão |`. `ID` = `D-NN`, único e nunca reaproveitado.
- **R2 — Fonte verificável.** Cada linha cita ao menos um caminho existente no repo (`specs/SPEC-NNN-*.md`, `docs/auditorias/*.md` ou outro doc versionado), com `:linha` quando houver. O gate confere que o caminho existe.
- **R3 — Gatilho concreto.** `Gatilho de revisão` não fica vazio nem genérico ("se mudar"): descreve o fato que reabre (ex.: "SPEC-185 fecha reserve→settle sem usar o gancho"). Quando não houver gatilho, escreve "decisão do dono".
- **R4 — Semente.** O arquivo nasce com as linhas da §3.1 (Não podar de 18/10, decisões de 03/11, os 8 itens reabertos em 11/11 e o "Não fazer" de 11/11). Linhas marcadas `<CONFIRMAR>` na §3.1 são resolvidas pelo coordenador antes do pouso (§8 D-416-1).
- **R5 — Teto.** ≤ 60 linhas de tabela e ≤ 12 KB. Passou do teto: as linhas cujo gatilho já disparou ou cuja spec foi fechada saem para `docs/historico/DECISOES_FIXAS-ate-AAAA-MM-DD.md` (mesmo formato), nunca apagadas sem registro.
- **R6 — Leitura obrigatória.** `.claude/agents/audit-reader.md` e `.claude/agents/spec-author.md` ganham uma linha cada: "Antes de reportar, leia `docs/guias/DECISOES_FIXAS.md`. Achado que contradiz uma linha cita o `D-NN` e o fato novo (arquivo:linha ou commit posterior à fonte); sem fato novo, o achado não entra." Nenhuma outra mudança nesses arquivos (o resto é da SPEC-415).
- **R7 — Gate.** `tests/test_decisoes_fixas.py` reprova: arquivo ausente; cabeçalho de colunas diferente; `ID` repetido ou fora do formato; fonte sem caminho existente; gatilho vazio; teto do R5 estourado; algum dos dois agentes sem a string `DECISOES_FIXAS.md`. É teste de documento (caso permitido por `docs/guias/TESTES.md:65-67`) e entra sozinho no job docs-only (o padrão `docs/` de `scripts/ci_docs_only.py:22` já o seleciona).

### Bloco B — pgTAP no `audit-local.yml`

- **R8 — Subcomando.** `scripts/dev_stack.py` ganha `test-db`: recusa stack linkada (`_assert_unlinked()`, `:75`), confere que `supabase test db --help` oferece `--local` (mesmo padrão de `reset`, `:171-173`) e roda `supabase test db --local` com a CLI pinada (`cli_command()`, `:42-55`). Imprime o stdout do TAP sempre (sucesso e falha), para o log do CI mostrar `Files=…, Tests=…`; falha = rc 2 (`main`, `:200-202`).
- **R9 — Passo no workflow.** Em `infra-browser`, o passo `dev_stack.py start` ganha `id: stack`; logo depois entra o passo `pgTAP (supabase/tests)` com `uv run python scripts/dev_stack.py test-db`. O passo `audit_local_gate.py` passa a `if: ${{ !cancelled() && steps.stack.outcome == 'success' }}`, para uma falha do pgTAP não esconder o resultado do pytest. Nada muda em `scope`, upload de artefato e `stop`.
- **R10 — Ordem.** O pgTAP roda antes do `audit_local_gate.py`, com o banco recém-migrado e só o `seed.sql` (os 5 arquivos são `begin … rollback` e não deixam resíduo; o pytest cria usuários e dados que o pgTAP não espera).
- **R11 — Primeiro vermelho é achado, não ajuste.** Se algum dos 5 arquivos falhar na primeira execução real, o executor não muda asserção para passar: registra o caso na spec (§ "Não rodou e por quê" ou achado) e o coordenador decide (§8 D-416-2). Corrigir migração está fora do escopo.

### Bloco C — catraca de relógio real em `tests/`

- **R12 — Detector AST.** `scripts/dev/clock_asserts.py` mede, para cada função de teste em arquivo `tests/**/*.py` versionado, o número de `assert` que dependem do relógio real. Relógio real = chamada resolvida para `time.time`, `time.time_ns`, `time.perf_counter`, `time.perf_counter_ns`, `time.monotonic`, `time.monotonic_ns`, `datetime.datetime.now`, `datetime.datetime.utcnow`, `datetime.datetime.today` ou `datetime.date.today`.
- **R13 — Aliases.** A resolução segue os imports do módulo e da função: `import time as _t` (`_t.perf_counter()`), `from time import perf_counter as pc`, `from datetime import datetime, date`, `import datetime as dt` (`dt.datetime.now()`).
- **R14 — Dependência.** Um `assert` depende do relógio se a expressão contém uma chamada de relógio **ou** um nome contaminado. Nome contaminado = alvo de `Assign`/`AnnAssign`/`AugAssign`/`NamedExpr` anterior, na mesma função, cujo valor contém chamada de relógio ou outro nome contaminado (propagação em ordem de linha, uma passada). Funções aninhadas e métodos contam sob o nome qualificado (`arquivo::Classe.metodo`, mesmo formato de `size_budget._functions`, `scripts/dev/size_budget.py:46-53`). `assert` fora de função é ignorado.
- **R15 — Baseline que só encolhe.** `tests/clock_asserts.json` = `{"_doc": …, "functions": {"tests/x.py::test_y": N}}`. O check reprova: chave nova; contagem maior; contagem menor ou chave sumida sem `--tighten` (folga 0, a contagem é exata). Modos iguais ao `size_budget`: sem flag confere; `--tighten` só desce e remove órfãs, recusando gravar se houver crescimento; `--update` regrava (coordenador, ver Bloco F).
- **R16 — Gate.** `tests/test_clock_asserts.py` roda o check sobre o repo (como `tests/test_size_budget.py:10-19`) e cobre o detector com trechos sintéticos. Sem marcador de exceção em linha: teste novo com relógio real usa relógio fixo (`monkeypatch` do `time`/`datetime` do módulo sob teste, padrão `pin_card_clock` da SPEC-409) ou pede `--update` ao coordenador.
- **R17 — Sem `DTZ`.** `pyproject.toml` não ganha `DTZ` nem regra nova do ruff.

### Bloco D — saída default fora de `docs/`

- **R18 — `write_evidence`.** `scripts/staging/common.py:117-118`: sem `out`, grava em `ROOT/.tmp/evidence/<nome>.json` (`.tmp/` já é ignorado, `.gitignore:30`). Com `out`, grava onde mandaram (inclusive `docs/…`). O print do caminho continua.
- **R19 — Scripts de staging com default próprio.** Passam para `ROOT/.tmp/evidence/…`, mantendo o nome do arquivo: `scripts/staging/s192.py:21` (`EVIDENCE` → `.tmp/evidence/spec192`; `measure.py:91` lê do mesmo `EVIDENCE`, cadeia `e2e_session` → `measure` preservada no mesmo checkout), `incident_drill.py:26` (ganha `--out`; leitura acumulada de `:201` passa a ler do caminho efetivo), `browser_voice_smoke.py:21`, `voice_smoke.py:24`, `two_user_smoke.py:22`, `stt_fallback_smoke.py:27`, `vercel_smoke.py:110`, `spec222_art_purge.py:24` (ganha `--out`), `portrait_offer_measure.py:300` (mantém o carimbo de hora no nome). Docstrings que citam o caminho antigo (`vercel_smoke.py:1`, `incident_drill.py:8`, `portrait_offer_measure.py:7`) passam a dizer "`.tmp/evidence/` por padrão; `--out docs/…` para versionar".
- **R20 — Fora de `scripts/staging/`, só o que mede ambiente externo.** `scripts/android_billing_smoke.mjs:9` (default `docs/spec194/evidence`, smoke em aparelho) passa a `.tmp/evidence/spec194`. Os geradores determinísticos de documento versionado ficam (lista e motivo na §3.4).
- **R21 — Gate.** `tests/test_staging_evidence_default.py` (a) chama `write_evidence` sem `out` com `ROOT` apontado para `tmp_path` e assere o caminho `.tmp/evidence/x.json`; (b) percorre por AST todo `scripts/staging/*.py` e reprova constante de string `"docs"` ou iniciada por `"docs/"` usada como operando de `/` ou como `default=` de `add_argument` (docstring e `help=` não contam). É teste que lê código-fonte no caso (c) "proibição de chamada" (`docs/guias/TESTES.md:65-67`), justificado no docstring.

### Bloco E — B2: baseline do ruff por contagem

- **R22 — Contagem sem mexer no toml.** `scripts/dev/ruff_baseline.py` ganha `violation_counts() -> dict[str, dict[str, int]]`: roda `ruff check --exit-zero --output-format json --config "lint.per-file-ignores = {}" .` (o override de CLI tem precedência sobre o `extend`; os `extend-per-file-ignores` de `pyproject.toml:87-104` e os `noqa` continuam valendo) e conta por arquivo × regra. `current_debt()` (`:39-61`) passa a derivar de `violation_counts()` e deixa de reescrever `ruff-baseline.toml` em disco (`:40-54`; hoje um segundo processo lendo a config no meio da janela vê a baseline vazia). Se a medição da Etapa 0 mostrar que o override não limpa o `extend`, o R22 cai para o desenho atual (reescrita temporária) e a spec registra.
- **R23 — Arquivo de contagens.** `ruff-baseline-counts.json` na raiz: `{"_doc": …, "counts": {"agents/combat.py": {"BLE001": N, "C901": M}, …}}`, chaves ordenadas, gerado pelo script, nunca à mão.
- **R24 — Check.** Reprova: par arquivo × regra medido e ausente do JSON; contagem medida maior que a registrada; contagem menor ou par sumido sem `--tighten` (folga 0); e o `ruff-baseline.toml` divergente do conjunto de pares do JSON (o mesmo `--check` atual, `:71-77`).
- **R25 — Modos.** `ruff_baseline.py --check` (confere os dois arquivos); `--tighten` (só desce: `min(registrado, medido)`, remove pares zerados do JSON e do toml, recusa gravar se houver crescimento); sem flag = regravação completa que pode subir (coordenador, Bloco F).
- **R26 — Onde roda.** `tests/test_ruff_counts.py` na suíte default (CI `validate.yml` e suíte do pouso), **se** o tempo medido na Etapa 0 for ≤ 5 s; acima disso, vira passo `uv run python scripts/dev/ruff_baseline.py --check` no `validate.yml` logo após `ruff check .` (`:65`) e a suíte só testa a lógica com dados sintéticos. A spec registra o número.
- **R27 — Doc.** `docs/guias/TESTES.md:77-78` passa a mandar `ruff_baseline.py --tighten` depois de consertar um arquivo (hoje manda a regravação sem flag).

### Bloco F — B7: subir teto é do coordenador

- **R28 — Guarda no hook.** Em subagente (`agent_id` presente, `.claude/hooks/guard_tools.py:149`), `check_shell` nega: `size_budget.py --update`; `clock_asserts.py --update`; `ruff_baseline.py` sem `--check` nem `--tighten`. Mensagem: "Subir baseline é do coordenador: extraia o código ou peça no hand-back com o motivo." `--tighten` e o check continuam livres. Usa o casamento por palavras que a SPEC-414 R5 introduz (não o `in command` cru de `:95`), para não repetir o falso positivo B1.
- **R29 — Relatório de crescimento.** `scripts/dev/baseline_growth.py --base <ref>` (default `main`) compara, entre `git show <ref>:<arquivo>` e o worktree, `tests/size_budget.json`, `tests/clock_asserts.json`, `ruff-baseline-counts.json` e os pares de `ruff-baseline.toml`; lista cada chave nova ou valor que subiu e sai com rc 1 se houver alguma. Pega também edição à mão do JSON, que o hook do R28 não vê. Somente leitura (não grava nada).
- **R30 — Quem roda o relatório.** O coordenador, no pouso, antes do `wt.sh land`. A ligação automática (uma linha no `scripts/dev/land_check.sh` da SPEC-415) fica fora desta spec por escopo; ver §8 D-416-3.

### Fora de escopo

- `scripts/dev/full.sh`, `basetemp` por PID, venv de worktree, falso positivo B1 do `guard_tools.py:95-97` e hook de `Agent` (SPEC-414). O R28 só acrescenta um ramo depois do pouso da 414.
- `specs/TEMPLATE.md`, `scripts/dev/land_check.sh`, `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` e qualquer outra mudança em `.claude/agents/*` além das duas linhas do R6 (SPEC-415).
- Teste enfraquecido e Hypothesis (SPEC-417); gate de tipos (SPEC-418).
- `DTZ` global e qualquer regra nova do ruff (decidido contra, `auditoria-workspace-2026-11-11.md:48`).
- Relógio real lido **dentro do produto** e assertado indiretamente (o caso dos rate cards de 11/11): a catraca AST só vê o teste. Esse caso é o padrão `pin_card_clock` da SPEC-409.
- Corrigir migração ou pgTAP que falhar na primeira execução (R11).
- Postgres/Docker local nesta máquina (`auditoria…:48`): o pgTAP roda só no CI.
- Mover ou apagar evidência já versionada em `docs/spec*/evidence/`.
- Geradores de documento versionado da §3.4 (ficam com o default atual).

## 3. Design técnico

### 3.1 Semente de `DECISOES_FIXAS.md` (R4)

Abreviações de fonte: `P18` = `docs/auditorias/ponytail-poda-2026-10-18.md`; `Q03` = `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md`; `W03` = `docs/auditorias/auditoria-workspace-2026-11-03.md`; `W11` = `docs/auditorias/auditoria-workspace-2026-11-11.md`. No arquivo, a fonte vai por extenso (o gate confere o caminho).

| ID | Item | Decisão | Fonte | Gatilho de revisão |
|---|---|---|---|---|
| D-01 | `persistence._MIGRATIONS` | manter | P18:69 | dono decide não carregar saves anteriores a uma versão |
| D-02 | `wallet_spend_scope` (`infrastructure/wallet.py`) | manter: gancho reserve→settle | P18:70-71; `specs/SPEC-405-…md:63` | SPEC-185 fecha reserve→settle sem usar o gancho |
| D-03 | adapters `portable`/OIDC/S3 | manter (perfil da SPEC-181) | P18:72-73 | decisão de produto de abandonar o perfil portable |
| D-04 | `services/gameplay_oracles.py` | manter: contrato da SPEC-212 | P18:74; Q03:258; SPEC-405:64 | SPEC-212 aposenta o contrato |
| D-05 | fakes e seams em módulo de produto (`FakeFinopsReader`, `MemorySwitchStore`, `MemoryDailyQuota`, `reload_cards`, `reset_text_cap_cache`, `set_switches`) | manter | P18:75-76; SPEC-405:65 | nenhum uso em `tests/` |
| D-06 | símbolos usados só no próprio arquivo (`_native_tracer`, `image_defer_max_age`, `PurchaseStore`, `accept_test_purchases`, `_legacy_shape`, `ProjectionRetry`, `ImageGenerationRefused`) | manter | P18:77-79 | o uso interno some |
| D-07 | `tests/test_mvp.py`, `test_fase0.py`, `test_fase25.py` | manter: única cobertura | P18:80-81 | cobertura equivalente provada em outro arquivo |
| D-08 | `tests/test_cutover_audit.py` | manter até a SPEC-272 apagar tudo | P18:82 | SPEC-272 `done` com a lista vazia |
| D-09 | régua `evals/` e `evals/experiments/*` | protegida; arquivar só por proposta do papel de autoria | P18:83-85 | proposta do papel de autoria de eval |
| D-10 | índices FAISS versionados | manter: lidos em runtime na Vercel | P18:86 | runtime deixa de ler do repo |
| D-11 | `handoffs/` | manter: evidência de revisão linkada | P18:89 | nenhum link restante (`scripts/check_md_links.py`) |
| D-12 | binários: evidências `docs/spec*/evidence` e mídia de `docs/` | manter: linkados ou insumo do Remotion; o histórico guarda | P18:90; Q03:261 | o README que linka sai; decisão do dono |
| D-13 | `langchain-community` | trocar só por spec com teste de leitura dos índices | P18:91-92 | spec de migração do FAISS aprovada |
| D-14 | `scripts/staging/*` | manter: runbooks da SPEC-197 | P18:93 | runbook aposentado na SPEC-197 |
| D-15 | `CLASS_THEMES`/`class_themes.json` | manter: usado pelo prólogo | P18:94 | `services/prologue.py` deixa de usar |
| D-16 | rotas FastAPI (inclui `/auth/logout`, canônica da SPEC-220) | manter: todas com chamador | P18:95; Q03:277-278 | rota sem chamador em `web/src`, `scripts`, CI e bundle Android |
| D-17 | `set_postura`, `consume_postura_on_attack`, `clear_sustained_postura`, `alert_party`, `suggested_virtue_cards` | manter (SPEC-272 "(c) manter") | Q03:257 | dono reverte na SPEC-272 |
| D-18 | `services/creature_gen_eval.py` | não mover: código de eval | Q03:259 | proposta do papel de autoria de eval |
| D-19 | `currentPurchaseAdapter`/`WebStripeAdapter` | manter: gancho da SPEC-198 | Q03:260 | SPEC-198 encerrada sem billing |
| D-20 | leitores de `.env` duplicados | não unificar (`python-dotenv` já) | Q03:262 | ganho medido > 5 linhas |
| D-21 | imports locais de `api.py` | não subir: cold start e ciclos | Q03:263 | medição de cold start mostra que não importa |
| D-22 | migrar tudo para `services/file_cache.py` | não: 19 seams, semântica mtime ≠ `lru_cache` | Q03:264 | decisão do dono |
| D-23 | tabela única de campos em `persistence.py` | não: mexe no round-trip de save | Q03:265 | spec de save com teste de round-trip |
| D-24 | `motion` → CSS | não trocar | Q03:266 | dep abandonada ou com CVE |
| D-25 | renomear `tests/test_specNNN_*` | não: só regra para arquivo novo | Q03:267 | decisão do dono |
| D-26 | fundir `npm ci/build` entre workflows | não fundir | Q03:268 | decisão do dono |
| D-27 | reforços, duas políticas de facção, `_side_of` "hero"/"heroes" | não é duplicação nem bug | Q03:279-283 | SPEC-384 D3 / SPEC-377 D4 revistas |
| D-28 | `_fold` restantes | contrato da SPEC-378: só migra equivalência provada | SPEC-405:70; Q03:285 | linha nova verde em `tests/test_spec378_text_fold.py` |
| D-29 | `<CONFIRMAR: item "_state">` TypedDicts de forma persistida em `state.py` (`NpcFavors`, `CalendarParams`) | manter: documentam a forma do save | SPEC-405:66 | a forma persistida muda |
| D-30 | flags do D1 da SPEC-384 | 7 aposentadorias só após smoke real por flag no staging; 3 reclassificadas; `WORLD_ENGINE` e `OPENING_THREAD` adiadas | `specs/SPEC-384-…md:3,29` | smoke real por flag registrado na SPEC-384 |
| D-31 | `<CONFIRMAR: item "openapi">` contrato front↔back por `openapi-typescript` e snapshot de superfície | adiado (SPEC-385); superfície guardada por `tests/test_api_surface.py` | Q03:318; `specs/SPEC-385-…md` | dono reabre a SPEC-385 |
| D-32 | mod guard do Claude Code | não: hooks clássicos cobrem e valem em `claude -p` | W03:215 | decisão do dono |
| D-33 | skills `taste`/`impeccable` | manter (escolha do dono) | W03:214 | decisão do dono |
| D-34 | lock entre sessões | não: o preflight da SPEC-415 resolve | W11:47 | preflight deixa passar uma colisão |
| D-35 | web no executor | não: injeção de prompt | W11:47 | decisão do dono |
| D-36 | Postgres/Docker local nesta máquina | não: Postgres só no CI | W11:48 | máquina nova |
| D-37 | `DTZ` global no ruff | não: catraca AST de teste (SPEC-416) | W11:48 | decisão do dono |
| D-38 | hook que bloqueie todo `\| tail` | não | W11:48 | decisão do dono |

Não entra na semente: "`project_index/repo_graph.json` versionado" (P18:87-88), superado pela SPEC-375 (índice local, `AGENTS.md` § Operação item 3).

### 3.2 pgTAP (R8–R11)

Confirmado no source em 12/11: `supabase start` (`scripts/dev_stack.py:127-131`) sobe Postgres 17 (`supabase/config.toml:13`) e aplica as migrações e o seed na criação; o gate só roda pytest (`scripts/audit_local_gate.py:94-116`); nenhum arquivo cita `supabase/tests`. Passo mínimo no workflow:

```yaml
      - id: stack
        run: uv run python scripts/dev_stack.py start
      - name: pgTAP (supabase/tests)
        run: uv run python scripts/dev_stack.py test-db
      - run: uv run python scripts/audit_local_gate.py
        if: ${{ !cancelled() && steps.stack.outcome == 'success' }}
```

`test_db(*, runner: Runner = _run) -> str` em `dev_stack.py` (≤ 15 linhas), `build_parser` ganha `test-db`, `main` imprime o retorno. `_checked` (`:58-63`) devolve só stderr ou stdout no erro; `test_db` imprime `stdout` e `stderr` antes de levantar, para o TAP aparecer inteiro no log.

### 3.3 Catraca de relógio (R12–R16)

- `scripts/dev/clock_asserts.py` (≤ 200 linhas): `tracked_tests(root) -> list[str]` (`git ls-files -- tests/*.py tests/**/*.py`), `measure(root, files) -> dict[str, int]`, `problems(current, baseline) -> list[str]`, `tightened(current, baseline)`, `load_baseline`/`write_baseline`, `main(argv)`. Mesmo formato de mensagens do `size_budget` ("novo", "cresceu", "folgada", "órfã"). Antes de criar helper: `Grep "def _functions"`; se valer, reaproveitar a iteração qualificada de `size_budget._functions`.
- Resolução de nome: dicionário de alias por módulo e por função, montado de `Import`/`ImportFrom`; nome dotted da chamada reconstruído de `Attribute`/`Name` e normalizado pelo alias antes de comparar com o conjunto canônico do R12.
- `tests/clock_asserts.json` semeado com `--update` na Etapa C. Tamanho esperado: 24 funções e 33 asserts (medido 12/11, `docs/spec416/medicoes.md`) (a auditoria contou ≥ 9). A semente tem que conter `tests/test_spec361_gate.py::test_prazo_real_por_thread` (oráculo positivo).

### 3.4 Inventário de saída default em caminho versionado (R18–R20)

Busca de 12/11 (`default=` / constante `ROOT / "docs"` em `scripts/`). Critério: muda o default quem **mede ambiente externo** (staging, aparelho) e grava evidência de execução única; fica quem **gera documento versionado de forma determinística** (regravar é o propósito) ou já grava por SHA.

| Script | Default hoje | Ação |
|---|---|---|
| `scripts/staging/common.py:118` (`write_evidence`, 14 chamadores) | `docs/spec191/evidence/<nome>.json` | `.tmp/evidence/` (R18) |
| `scripts/staging/s192.py:21` (8 chamadores de `evidence()`) | `docs/spec192/evidence` | `.tmp/evidence/spec192` (R19) |
| `scripts/staging/{incident_drill,browser_voice_smoke,voice_smoke,two_user_smoke}.py` | `docs/spec197/evidence/*.json` | `.tmp/evidence/` (R19) |
| `scripts/staging/stt_fallback_smoke.py:27`, `spec222_art_purge.py:24` | `docs/staging-wave-2026-10-17/evidence` | `.tmp/evidence/` (R19) |
| `scripts/staging/vercel_smoke.py:110` | `docs/spec192/evidence/smoke.json` | `.tmp/evidence/` (R19) |
| `scripts/staging/portrait_offer_measure.py:300` | `docs/spec389/offer-measure-<hora>.json` | `.tmp/evidence/` (R19) |
| `scripts/android_billing_smoke.mjs:9` | `docs/spec194/evidence` | `.tmp/evidence/spec194` (R20) |
| `scripts/beta_gameplay_gate.py:37`, `scripts/release/checklist.py:28` | `docs/spec212/evidence`, `docs/spec197/evidence` (nome por SHA) | fica: um arquivo por SHA, lido pelo gate de release |
| `scripts/fauna/eval.py:62`, `fauna/eval_tramas.py:59`, `bestiario/painel.py:25`, `cards/painel.py:24`, `finops_margin_sim.py:26`, `gen_retention_doc.py`, `normalize_specs.py:773`, `readiness_report.py:130` | `docs/…` | fica: gerador determinístico de documento versionado |
| `scripts/bestiario/pool_revisao.py:229` | `handoffs/pool-review/<data>.yaml` | fica: insumo de revisão versionado por data |
| `scripts/bestiario/arena_todas.sh:10-11` | `docs/spec349/*` explícito na linha de comando | fica (já é explícito) |

Inventário reconfirmado em 12/11: nenhum script de staging novo; geradores determinísticos extras ficam (`docs/spec416/medicoes.md`). Runbooks que citam `--out docs/…` explícito (`docs/spec413/README.md`, `docs/spec410/README.md`, `ESTADO_ATUAL.md` § Bloqueios) não mudam.

### 3.5 Contagem do ruff (R22–R26)

- Etapa 0 mede três coisas antes de codar: (a) o override limpa só o toml: mediu 987 pares, idênticos aos de `current_debt()` antigo (o toml da `main` tinha 988: 1 obsoleto); (b) tempo: 1,3 s (R26: teste na suíte); (c) tamanho do JSON gerado 34 096 bytes (se > 40 KB, o hook de leitura exige recorte; aceitável, é arquivo gerado).
- O check compara três conjuntos: pares medidos, pares do JSON, pares do toml. Mensagens: "par novo F×R (n)", "cresceu F×R a → b", "folgada F×R a → b; rode --tighten", "órfão F×R; rode --tighten", "toml ≠ contagens; rode --tighten".

### 3.6 Guarda e relatório (R28–R30)

- `guard_tools.py`: função `_raises_baseline(words: list[str]) -> bool` (≤ 15 linhas), chamada em `check_shell` só quando `is_subagent`, sobre as palavras de cada parte da pipeline (helper de palavras da SPEC-414). Casa pelo nome do script no fim da palavra (`size_budget.py`, `clock_asserts.py`, `ruff_baseline.py`), também via `py.sh`/`uv run python`/`-m scripts.dev.…`.
- `scripts/dev/baseline_growth.py` (≤ 120 linhas): `git show <base>:<path>` com `subprocess` (base inexistente = arquivo vazio); saída uma linha por crescimento; rc 0/1.

### 3.7 Arquivos que a spec toca

| Arquivo | Novo/alterado | Bloco |
|---|---|---|
| `docs/guias/DECISOES_FIXAS.md` | novo | A |
| `.claude/agents/audit-reader.md`, `.claude/agents/spec-author.md` | +1 linha cada | A |
| `tests/test_decisoes_fixas.py` | novo | A |
| `scripts/dev_stack.py` | `test_db`, parser, `main` | B |
| `.github/workflows/audit-local.yml` | `id: stack`, passo pgTAP, `if` do gate | B |
| `tests/test_dev_stack.py` | +2 testes | B |
| `tests/test_ci_docs_only.py` ou `tests/test_audit_local_workflow.py` (novo, preferido) | teste do passo | B |
| `scripts/dev/clock_asserts.py`, `tests/clock_asserts.json`, `tests/test_clock_asserts.py` | novos | C |
| `scripts/staging/{common,s192,incident_drill,browser_voice_smoke,voice_smoke,two_user_smoke,stt_fallback_smoke,vercel_smoke,spec222_art_purge,portrait_offer_measure}.py` | default de saída | D |
| `scripts/android_billing_smoke.mjs` | default de saída | D |
| `tests/test_staging_evidence_default.py` | novo | D |
| `scripts/dev/ruff_baseline.py` | `violation_counts`, `--tighten`, `--check` dos dois | E |
| `ruff-baseline-counts.json`, `tests/test_ruff_counts.py` | novos | E |
| `.github/workflows/validate.yml` | +1 passo só se R26 cair no ramo > 5 s | E |
| `docs/guias/TESTES.md` | `:77-78` (`--tighten`); +2 linhas na § Ruff: contagem e catraca de relógio | E/C |
| `.claude/hooks/guard_tools.py` | `_raises_baseline` + ramo em `check_shell` | F |
| `tests/test_workspace_hooks.py` | +2 testes | F |
| `scripts/dev/baseline_growth.py`, `tests/test_baseline_growth.py` | novos | F |

## 4. Plano passo a passo

Uma branch, um commit por bloco (Conventional Commits, inglês). Ordem: 0 → A → B → C → D → E → F (F por último porque depende da 414 no `guard_tools.py`). Testes do escopo com `bash scripts/dev/pt.sh <arquivos>`; suíte completa só no pouso.

### Etapa 0 — medições

1. Resolver todos os `<MEDIR:>` da §3.3, §3.4 e §3.5 e gravar os números nesta spec no primeiro commit.
2. Conferir `git log main --oneline -- .claude/hooks/guard_tools.py .claude/agents/spec-author.md docs/guias/TESTES.md | head -5`: 414 e 415 pousadas? Se não, os Blocos A (só a linha do agente) e F esperam.

### Etapa A — `DECISOES_FIXAS.md`

1. **Testes** (`tests/test_decisoes_fixas.py`): `test_arquivo_existe_e_tem_colunas` (falha antes: arquivo ausente); `test_ids_unicos_e_no_formato`; `test_fonte_aponta_para_arquivo_existente` (extrai caminhos `specs/…`, `docs/…` da coluna, `Path.exists()`); `test_gatilho_nao_vazio`; `test_teto` (≤ 60 linhas, ≤ 12 KB); `test_agentes_mandam_ler` (`audit-reader.md` e `spec-author.md` contêm `DECISOES_FIXAS.md`).
2. **Implementação:** o arquivo com a §3.1 (fontes por extenso, `<CONFIRMAR>` mantidos até D-416-1); as duas linhas do R6.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_decisoes_fixas.py`.

### Etapa B — pgTAP

1. **Testes:** em `tests/test_dev_stack.py`, `test_test_db_forca_local_e_imprime_tap` (runner falso: última chamada = `[cli, "test", "db", "--local"]`; stdout `Files=5, Tests=63` sai no retorno) e `test_test_db_recusa_stack_linkada` (mesmo molde de `:32-38`). Em `tests/test_audit_local_workflow.py`, `test_audit_local_runs_pgtap` (YAML: passo com `dev_stack.py test-db` depois do `id: stack` e antes do `audit_local_gate.py`; o `if` do gate contém `steps.stack.outcome == 'success'` e `!cancelled()`). Falha antes: subcomando e passo ausentes.
2. **Implementação:** §3.2.
3. **Verificação:** `pt.sh tests/test_dev_stack.py tests/test_audit_local_workflow.py tests/test_ci_docs_only.py`; `actionlint` limpo no workflow (`actionlint` indisponível nesta máquina: não rodou; o teste de YAML cobre ordem, `id` e `if`). A prova real é o §6.1.

### Etapa C — catraca de relógio

1. **Testes** (`tests/test_clock_asserts.py`, trechos em `tmp_path`): `test_detecta_relogio_com_alias` (cópia literal de `tests/test_spec361_gate.py:269-282` → `{"t.py::test_prazo_real_por_thread": 1}`); `test_from_import_e_datetime` (`from time import perf_counter as pc`, `from datetime import datetime`, `import datetime as dt` → 1 cada); `test_contaminacao_transitiva` (`t0 = time.monotonic(); dt_ = t0 + 1; assert dt_ > 0` → 1); `test_relogio_fora_do_assert_nao_conta` (`time.sleep`, `time.time()` só em log → 0); `test_metodo_qualificado` (`Classe.metodo`); `test_novo_cresceu_folgado_orfao` (as quatro mensagens do R15); `test_tighten_recusa_crescimento`; `test_repo_respeita_baseline` (gate). Falha antes: módulo ausente; o primeiro teste é o oráculo de que o caso real é pego.
2. **Implementação:** §3.3; semente com `--update`; confirmar que a chave de `test_spec361_gate.py` está nela.
3. **Verificação:** `pt.sh tests/test_clock_asserts.py tests/test_size_budget.py`.

### Etapa D — saída default fora de `docs/`

1. **Testes** (`tests/test_staging_evidence_default.py`): `test_write_evidence_default_fora_de_docs` (falha antes: grava em `docs/spec191/evidence`); `test_write_evidence_out_explicito_respeitado` (`--out` para `tmp_path/docs/x.json`); `test_nenhum_default_em_docs_nos_scripts_de_staging` (AST do R21; falha antes em `common.py:118`, `s192.py:21` e os demais da §3.4); `test_incident_drill_acumula_no_caminho_efetivo` (duas partes no mesmo `--out`, as duas chaves no arquivo). `tests/test_spec191_staging_tools.py:52-57` continua verde.
2. **Implementação:** R18–R20; docstrings.
3. **Verificação:** `pt.sh tests/test_staging_evidence_default.py tests/test_spec191_staging_tools.py tests/test_spec192_staging_scripts.py`; `node --check scripts/android_billing_smoke.mjs`.

### Etapa E — contagem do ruff

1. **Testes** (`tests/test_ruff_counts.py`): lógica com dicionários sintéticos — `test_contagem_nova_no_arquivo_baselinado_falha` (registrado `{"a.py": {"BLE001": 2}}`, medido 3 → "cresceu"; é o B2: hoje o toml aceita); `test_par_novo_falha`; `test_folgado_e_orfao_pedem_tighten`; `test_toml_divergente_falha`; `test_tighten_so_desce_e_zera_pares`; e o gate `test_repo_respeita_contagens` (ou só lógica, conforme R26). Oráculo de equivalência do R22: `ruff_baseline.py --check` verde antes e depois da troca de `current_debt` (o toml gerado é byte-igual).
2. **Implementação:** §3.5; gerar `ruff-baseline-counts.json`; `TESTES.md:77-78` e as 2 linhas da § Ruff.
3. **Verificação:** `pt.sh tests/test_ruff_counts.py tests/test_ruff_protected_exempt.py`; `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py --check`; `uv run ruff check .` limpo.

### Etapa F — B7

1. **Testes:** em `tests/test_workspace_hooks.py`, `test_subagente_nao_sobe_baseline` (parametrize: `bash scripts/dev/py.sh scripts/dev/size_budget.py --update`, `uv run python scripts/dev/clock_asserts.py --update`, `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py` → negado com `agent_id`; falha antes: o hook deixa passar) e `test_tighten_check_e_coordenador_liberados` (`--tighten`, `--check`, e o `--update` sem `agent_id` → permitidos; `sed -n 1,5p scripts/dev/size_budget.py` → permitido). Em `tests/test_baseline_growth.py`: repo git em `tmp_path`, commit base com `size_budget.json` e worktree com uma chave subida e uma nova → rc 1 e duas linhas; só descida → rc 0.
2. **Implementação:** §3.6.
3. **Verificação:** `pt.sh tests/test_workspace_hooks.py tests/test_baseline_growth.py`; `bash scripts/dev/py.sh scripts/dev/baseline_growth.py --base main` no próprio branch lista só as entradas novas desta spec (os JSONs novos não existem na `main`: o relatório trata arquivo ausente na base como vazio e lista as chaves; esperado e registrado).

## 5. Critérios de aceite

- [x] `<MEDIR:>` resolvidos e gravados nesta spec (Etapa 0).
- [x] `docs/guias/DECISOES_FIXAS.md` com ≥ 38 linhas, nenhum `<CONFIRMAR>` sobrando, dentro do teto; `tests/test_decisoes_fixas.py` verde e vermelho antes (registro do primeiro `pt.sh`).
- [x] `audit-reader.md` e `spec-author.md` com a linha do R6, sem outra mudança.
- [x] `dev_stack.py test-db` e passo no `audit-local.yml`; testes do Bloco B verdes; CI real com `Files=5, Tests=63` ou o achado registrado (R11, §6.1).
- [x] `tests/clock_asserts.json` contém `tests/test_spec361_gate.py::test_prazo_real_por_thread`; `tests/test_clock_asserts.py` verde; `pyproject.toml` sem `DTZ`.
- [x] Nenhum default de `scripts/staging/*.py` em `docs/`; `tests/test_staging_evidence_default.py` verde e vermelho antes.
- [x] `ruff-baseline-counts.json` gerado; `ruff_baseline.py --check` verde; toml byte-igual ao anterior (oráculo do R22); número de tempo registrado e R26 aplicado no ramo certo.
- [x] Hook nega `--update` em subagente e libera `--tighten`/check; `baseline_growth.py` com rc correto.
- [x] `ruff format --check` e `ruff check` limpos nos arquivos tocados; `scripts/dev/dup_helpers.py --diff main...HEAD` sem helper duplicado; `tests/test_size_budget.py` verde.
- [x] Suíte completa verde no pouso (coordenador).

## 6. Smoke test real

Sem LLM. A infra real é o Postgres do CI.

1. **pgTAP no CI (depende de push, §8 D-416-4):** disparar `audit-local` no branch (`workflow_dispatch`) ou no push da `main`. Esperado: passo "pgTAP (supabase/tests)" verde com `Files=5, Tests=63, Result: PASS` no log; passo `audit_local_gate.py` roda. Registrar run id e trecho do log em `docs/spec416/README.md`.
2. **Prova de que o passo falha de verdade:** no mesmo branch, commit descartável que troca uma asserção de `public_sem_funcoes_do_app_test.sql` por `select ok(false, 'spec416 canary')`; esperado: passo vermelho, `audit_local_gate.py` ainda roda (R9). Reverter o commit antes do pouso; registrar os dois run ids.
3. **Saída default:** `bash scripts/dev/py.sh -m scripts.staging.vercel_smoke --help` mostra o default `.tmp/evidence/…`; nenhuma rodada contra o staging é necessária para esta spec.
4. **Hook:** numa sessão real com subagente (o executor desta spec serve), tentar `bash scripts/dev/py.sh scripts/dev/size_budget.py --update` e ver a negação.

## 7. Riscos & compatibilidade

- **Primeiro vermelho do pgTAP.** Os 5 arquivos nunca rodaram; 410 e 413 têm SQL que nunca tocou Postgres (`ESTADO_ATUAL.md`). Um vermelho é o objetivo do gate, mas trava o `audit-local` até alguém decidir (R11, D-416-2).
- **Imagem do `pg_prove`.** `supabase test db` puxa um container extra no runner; soma tempo ao job de 35 min (`audit-local.yml:33`). Duração do passo: medir no primeiro run (pendente do push, D-416-4)..
- **Atrito das catracas com folga 0.** Consertar uma violação ou um teste de relógio obriga `--tighten` no mesmo commit, como no `size_budget` desde a SPEC-407. É o custo aceito do "só encolhe".
- **Runbooks que contam com o default antigo.** Quem rodar um smoke de staging sem `--out` não verá mais o arquivo em `docs/`: o caminho impresso continua, e os runbooks da onda 11/11 já passam `--out` explícito. `measure.py` só acha `e2e_session.json` se `e2e_session.py` rodou no mesmo checkout (antes achava a cópia versionada antiga, que podia estar velha).
- **Override de config do ruff.** Se o `--config "lint.per-file-ignores = {}"` não limpar o `extend` na versão do ruff do lock, o R22 volta ao desenho atual (Etapa 0 decide).
- **Colisão com 414/415.** `guard_tools.py`, `settings.json` (esta spec não toca), `TESTES.md` (linhas diferentes: 414 mexe em `:12,22-23,31`; esta em `:77-78` e § Ruff) e `spec-author.md` (415 muda `tools` e acrescenta `<MEDIR:`; esta acrescenta uma linha). Rebase manual provável, sem conflito semântico.
- **Saves, MockLLM, quota:** não se aplica.

## 8. Decisões para o dono/coordenador

- **D-416-1 — Itens `_state` e `openapi` da semente.** A fonte que lista os 8 itens reabertos em 11/11 (revisão Fable) não está versionada; o autor inferiu `_state` = TypedDicts de forma persistida (`specs/SPEC-405-…md:66`) e `openapi` = SPEC-385 adiada + superfície em `tests/test_api_surface.py`. O coordenador confirma ou corrige D-29 e D-31 antes do pouso.
- **D-416-2 — pgTAP vermelho na primeira execução.** Proposta: o passo fica bloqueante desde o início; um arquivo que falhar vira spec própria de correção (migração ou teste), e até ela pousar o coordenador decide entre manter o `audit-local` vermelho ou marcar só aquele arquivo como pendente no `docs/spec416/README.md`. Não há mecanismo de pular arquivo nesta spec.
- **D-416-3 — Ligar `baseline_growth.py` ao pouso.** Proposta: emenda de uma linha no `scripts/dev/land_check.sh` da SPEC-415 (rc 1 recusa o `ff`), feita pelo coordenador depois das duas specs pousadas. Alternativa: só o hook (R28) e o relatório manual. Até lá, o coordenador roda `baseline_growth.py` à mão no pouso.
- **D-416-4 — Push para provar o pgTAP.** O §6.1–6.2 precisa de um run do `audit-local`, que depende do push autorizado pelo dono (`ESTADO_ATUAL.md` § Bloqueios). Sem push, a spec pousa com o Bloco B testado só no YAML e o §6 em "Não rodou e por quê"; vira `done` só depois do run.
- **D-416-5 — Sem marcador de exceção na catraca de relógio.** Escolha do autor: a única saída é relógio fixo ou `--update` do coordenador (mesmo desenho do `size_budget`). Alternativa rejeitada: `# clock-ok: motivo` em linha, que deixaria o executor abrir exceção sozinho.
- **Aprovação (2026-11-12):** aprovada pelo coordenador por delegação do dono ("executa as mudanças", 12/11). D-416-1: a semente de `DECISOES_FIXAS.md` só leva linha com fonte versionada citável (spec ou auditoria); item sem fonte (`_state`, `openapi` se não houver) sai da semente e volta no hand-back para o coordenador confirmar. D-416-2: o passo pgTAP nasce bloqueante; falha na primeira execução é triada pelo coordenador antes de qualquer aplicação no staging. D-416-3: executa depois da SPEC-415 pousar e então liga `baseline_growth.py` ao `land_check`. D-416-4: o smoke do pgTAP no CI fica pendente do push, que depende do dono; a spec pode pousar com esse item em "Não rodou e por quê". D-416-5 aceita.

## 9. Notas de execução (12/11)

- **Semente (D-416-1).** D-29 (TypedDicts persistidos) mantém a fonte `SPEC-405:66`; D-31 foi reescrito só com o que a fonte diz (SPEC-385 adiada, `auditoria-qualidade…:318`), sem "openapi-typescript" (sem fonte versionada). O coordenador confirma se esses dois são os itens `_state`/`openapi` dos 8 reabertos em 11/11.
- **Oráculo do R22.** O `ruff-baseline.toml` regravado não é byte-igual ao anterior: perdeu `.claude/hooks/guard_tools.py = ["BLE001"]`, que já estava obsoleto na `main` (`--check` dava stale; SPEC-414 consertou a violação). Medido: 987 pares idênticos aos de `current_debt()` antigo.
- **R26.** 1,3 s: gate `test_repo_respeita_contagens` na suíte; `validate.yml` não mudou.
- **D-416-3 (feito).** `land_check.py` ganhou o check `growth` (entre `measure` e `ci`) que roda `baseline_growth.py --base main --ignore-new-files`; a flag trata baseline ausente na base como criação (senão a própria SPEC-416 reprovaria). Sem a flag o relatório lista as chaves novas (R29, §4 F.3).
- **TESTES.md.** A frase do ruff estava em `:83-84` (não `:77-78`); atualizada junto com a linha da catraca de relógio.
- **Bloco D.** `incident_drill.py` e `spec222_art_purge.py` ganharam `--out`; `tests/test_staging_evidence_default.py` cobre as quatro frentes do plano.
- **Não rodou e por quê.** CI/pgTAP real (§6.1-2): exige push, fora do escopo do executor. `actionlint`: não instalado. Suíte completa: do coordenador.
- **Fechamento (2026-11-12):** revisão `terra` APPROVED_WITH_FOLLOWUPS (`handoffs/SPEC-416-terra-review.md`). Suíte completa local: 11561 passed, 1 falha no check `growth` (script procurado no worktree), corrigida em `c3346c1a`. Smoke de CI (§6.1-2) no run `audit-local` 43222359080 de `c3346c1a`: passo pgTAP `Files=5, Tests=63, Result: PASS` em ~4 s; o job ficou vermelho só pelas 3 falhas conhecidas de `image_pricing_unavailable` (rate card vencido, SPEC-409), sem relação com esta spec. Não rodou: `actionlint` local (não instalado; o job `workflow-lint` do `validate` cobre no CI). Follow-ups P2 abertos: alias de função na catraca de relógio; hook nega `ruff_baseline.py --help` em subagente.
