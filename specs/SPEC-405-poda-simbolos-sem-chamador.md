# SPEC-405 — poda-simbolos-sem-chamador

> **Status:** `done` (11/11: etapas 0–7, saldo −350 linhas; revisão Sonnet independente APPROVED em `handoffs/SPEC-405-terra-review.md`; oráculo W2 sem diferença; suíte completa do coordenador no pouso: única falha é `tests/test_spec352_creature_portraits.py::test_view_offer_present_when_eligible`, idêntica na `main` (rate card de imagem de 12/10 venceu em 11/11; passa com `RPG_RATE_CARD_MAX_AGE_DAYS=365`), fora do escopo; antes `approved`) (11/11: aprovada pelo coordenador por delegação do dono, "as decisões deixo para vc"; decisões do §8 = recomendações; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma
> **Desbloqueia:** nada (uma das 4 follow-ups de qualidade, SPEC-405..408)
> **Risco:** `baixo` no geral; **R4 toca `agents/archivist.py` (memória/persistência)** → revisor Sonnet obrigatório para a Etapa 4 (AGENTS.md § Qualidade, revisão e evidência).
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet), uma etapa por vez · **REVIEW_MODEL:** Sol-leve/Sonnet (`spec-reviewer` ou revisor Sonnet), obrigatório na Etapa 4 e conferência por amostragem das demais.
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum evaluator, expected, dataset ou baseline de `evals/` é tocado).
> **Evidência:** refatoração pura (W2): oráculo de equivalência no molde da SPEC-376 R25 (`evals run` + `evals compare` sem diferença e `playtest run --all --turns 10 --seed 0` com as mesmas violações e desfechos), mais re-grep `-w` por símbolo antes de apagar, testes do escopo por etapa, `ruff`. R5 e R6 têm oráculo próprio (antigo × novo) em teste.

---

## 1. Contexto & Objetivo

A auditoria "ponytail" de 11/11/2026 (5 subagentes) e a revisão independente do mesmo dia derrubaram a maior parte dos achados e deixaram um escopo pequeno e verificável: ~250–300 linhas de código sem chamador (símbolos mortos, três scripts de evidência já consumidos pela SPEC-381 `done`) e três duplicações exatas (duas cópias de `fold`, uma de `percentile`) mais um ramo de compatibilidade só para stubs de teste no `archivist`.

Nada aqui muda comportamento de produto. Cada item vale pelo mesmo motivo: código que ninguém chama (ou cópia de algo que já tem dono) custa leitura e esconde o dono real. Esta spec confirmou cada símbolo no source em 11/11 (`Grep -w` no repositório inteiro, exceto `docs/historico/`, `CHANGELOG.md`, specs e handoffs): **todos os 19 símbolos do R1–R2 (mais a cópia local de `_CODE_RE`) têm só a própria definição** (nenhum teste, `__all__`, `getattr`, string, yaml ou entry point). O executor refaz esse grep (W1) na hora de apagar, porque a `main` anda.

Princípio: "menor mudança correta" (AGENTS.md § Qualidade). Nada fora da lista; o que parece morto mas tem dono vai para §2 "Fora de escopo".

## 2. Requisitos

Linhas abaixo = estado da `main` em `9f21ef4a`.

- **R0 — W1 (re-grep por símbolo).** Antes de apagar cada símbolo, `Grep` com `\bNOME\b` em `*.py`, `*.yaml`, `*.yml`, `*.toml`, `*.json`, `*.sh`, `*.ts(x)` (excluindo `docs/historico/`, `CHANGELOG.md`, `specs/`, `handoffs/`, `docs/descricao_projeto/`). Só a definição pode aparecer. Qualquer outro acerto (incluindo `__all__`, string, `getattr`) ⇒ o símbolo **fica**, é registrado no hand-back e sai da spec. O resultado vai num bloco `docs/spec405/README.md` (símbolo → comando → saída).
- **R1 — `services/` e `observability/`.** Apagar (def inteira, mais imports que ficarem órfãos):
  - `services/law.py:127` `CrimeCandidate`, `:138` `PrisonerRef`, `:146` `LawReceipt` (TypedDicts);
  - `services/creature_variants.py:318` `_debug_scores`;
  - `services/creature_art.py:307` `has_curated_art` (o `handoffs/SPEC-352-sol-review.md:47` cita o nome, mas é histórico: `api.py` já não o usa);
  - `services/card_shop.py:40` `reload_config`;
  - `services/lore_quests.py:672` `seed_from_proposal`;
  - `services/rumor_adoption.py:448` `search_intent`;
  - `services/reputation.py:426` `deed_event_types`;
  - `services/npc_seed.py:213` `seed_ids`;
  - `services/companion_soul.py:546` `_soul_for_quest`;
  - `services/auth_sessions.py:104` `utc_now`;
  - `observability/telemetry.py:370` `run_with_context`.
- **R2 — raiz e rotas.** Apagar:
  - `world_utils.py:15` `_TRAVEL_CUES` (lista de 17 strings, 15–33; a viagem usa `_TRAVEL_VERBS`/`_TRAVEL_PREPS`);
  - `gamedata.py:266` `ARMADURAS` e `:273` `ESCUDOS`;
  - `api.py:242–251` `_CODE_RE = None` **e** `_error_code_of` (a cópia local lazy). O `_CODE_RE` vivo é o de `services/error_codes.py:14` (usado em `:192`) e **fica**;
  - `routes/turn.py:1488` `_MEMORIAL_DETAIL`;
  - `state.py:251` `CalendarDate` (TypedDict).
- **R3 — scripts de evidência da SPEC-381 (`done`).** `git rm scripts/dev/api_inventory.py`, `scripts/dev/api_scanner_counts.py`, `scripts/dev/api_importtime.py`. Só se citam entre si e na própria spec 381 (`specs/SPEC-381-refactor-api-routers.md:700`, texto histórico que fica). Conferido em 11/11: **não** há entrada deles em `ruff-baseline.toml`, `tests/size_budget.json` nem workflows; o executor confirma de novo e limpa só se aparecer. `scripts/dev/api_surface_dump.py` **fica** (citado em `docs/spec381/patch_inventory.json:4665`, fora desta lista).
- **R4 — `_persist_memory_records` sem `inspect`.** `agents/archivist.py:141–169`: remover o `inspect.signature(add_memory_to_session)` (`:149–155`) e o ramo `else` de 2 argumentos (`:163–164`); chamar sempre `add_memory_to_session(game_id, texts, metadatas=metadatas)`. O docstring deixa de dizer "aceita stubs antigos". `add_memory_to_session` (`rag.py:1462`) já tem `metadatas` por keyword. **Consertar os stubs de teste** que monkeypatcham `archivist.add_memory_to_session` com 2 posicionais e quebrariam com `metadatas=`; levantamento de 11/11 (o executor refaz por `Grep add_memory_to_session tests/`, e só mexe nos que patcham `archivist`, não em `world_simulator`):
  - `tests/test_conflict_summary_lifecycle.py` `:79`, `:112`, `:252`, `:315`, `:342`, `:382`, `:406` (`def persist(_game_id, facts)`), `:759`; os patches em `:461` e `:505` conferir à mão (não casaram no padrão automático);
  - `tests/test_grounding_boundaries.py:415`;
  - já aceitam `metadatas` e **não mudam**: `test_memory_provenance.py:450` (`**_kwargs`), `test_bug_memoria_resiliencia.py:60,85,96,177,352`, `test_narrative_evidence.py:75`, `test_projections.py:57`, `test_playtest_observability_hardening.py` (usa `rag.`/`runner`);
  - `tests/test_conflict_summary_lifecycle.py:735` patcha `world_simulator` (não passa por `_persist_memory_records`): **não mudar**.
  Os stubs ganham `**_kwargs`/`metadatas=None` e, onde assertam o payload, a asserção continua igual (W3: nenhum assert muda; só a assinatura do stub). `import inspect` fica (usado em `archivist.py:481` para `add_npc_memory`, **fora de escopo**).
- **R5 — duas cópias de `fold`.** Substituir por `services.text.fold`:
  - `services/plot_threads.py:157` `_fold` ≡ `fold(x, collapse=True)` (corpo: NFKD, sem marcas combinantes, `casefold()`, `" ".join(split())`);
  - `world_utils.py:81` `_fold_txt` ≡ `fold(x, case="lower")` (corpo: NFKD, sem marcas, `.lower()`, **sem** colapsar espaços). Cuidado: `casefold` ≠ `lower` (ex.: `ß`), por isso o `case="lower"` é obrigatório.
  Ambas ficam como o mesmo nome local (`_fold = functools.partial`/def de 1 linha delegando, ou `from services.text import fold` e troca dos 4 + 6 usos: `plot_threads.py:180,202,252`, `world_utils.py:105,111,136,183,186,312`). Escolha do executor, sem criar helper novo. **Prova:** estender `tests/test_spec378_text_fold.py` (tabela `SITES`, `:166`) com as duas linhas, no mesmo molde das existentes: `("services.plot_threads", "_fold", _legacy_services_plot_threads, {"collapse": True})` e `("world_utils", "_fold_txt", _legacy_world_utils, {"case": "lower"})`, com os corpos antigos copiados como `_legacy_*`; `CORPUS` existente. Se o site migrado deixar de existir como atributo, a linha usa o nome que sobrar.
- **R6 — `_percentile` duplicado.** `playtest/telemetry.py:832` é igual, linha a linha, a `observability/latency.py:348` `percentile` (nearest-rank, `round`, `0` se vazio). Trocar o corpo por `from observability.latency import percentile as _percentile` (o alias mantém os 3 usos em `:1224,1225,1481` e o import em `tests/test_latency_timeline.py:153`). Antes: confirmar de novo que os corpos são idênticos; se divergirem, o R6 sai. Verificar que não cria ciclo de import (`observability.latency` não importa `playtest`). O comentário em `latency.py:349` ("mesmo critério de playtest.telemetry._percentile") passa a dizer que `playtest` importa daqui.
- **R7 — oráculo W2 (SPEC-376 R25).** Antes da Etapa 1: capturar A (`evals run` das suítes do `eval-gates.yml` com `--seed 7`; `playtest run --all --turns 10 --seed 0`). Depois das Etapas 2, 4, 5 e 6 (as que mexem em caminho de runtime) e ao fim: capturar B. Exigir `evals compare --current B --baseline A` **sem diferença**, mesma contagem de violações e mesmo desfecho por perfil. A suíte completa é do coordenador, 1× no pouso.
- **R8 — gates.** `ruff format --check` e `ruff check` limpos nos arquivos tocados; `uv run python scripts/dev/dup_helpers.py --diff main...HEAD` sem helper novo; `tests/test_size_budget.py` verde (só encolhe); `git diff --stat` do conjunto: saldo de linhas negativo, ~−250 a −300.
- **R9 — um commit por etapa**, na branch da spec, inglês, Conventional Commits (`refactor:`/`chore:`).

### Fora de escopo (com motivo)

- `wallet_spend_scope`: gancho da SPEC-185, listado em "Não podar" de `docs/auditorias/ponytail-poda-2026-10-18.md` § Não podar.
- `services/gameplay_oracles.py`: contrato da SPEC-212.
- `FakeFinopsReader`, `MemorySwitchStore`, `MemoryDailyQuota`: decisão de 18/10 (dublês de teste que ficam).
- `NpcFavors` e `CalendarParams` (`state.py`): documentam a forma persistida. Só `CalendarDate` sai.
- `scripts/smoke/spec351_opening.py`, `scripts/staging/spec222_art_purge.py`, `scripts/migrate_embedding_profile.py`, `scripts/migrate_file_saves.py`, `scripts/dev/patch_liveness.py`: SPEC-376 "manter", CLI única ou ferramenta da SPEC-406.
- `scripts/dev/api_surface_dump.py` (citado em `docs/spec381/patch_inventory.json`).
- Ramos de ficha não-v4 (`tests/test_fase64.py` os usa).
- Demais `_fold` do repo: contrato da SPEC-378 (só as duas cópias do R5 entram, por serem equivalências provadas).
- O segundo `inspect.signature(add_npc_memory)` em `agents/archivist.py:481`: mesmo padrão, mas fora do pedido; vira follow-up se o R4 passar limpo.
- Outras `_percentile` do repo com assinatura diferente (`evals/experiments/*`, `scripts/benchmark_turn_pipeline_real.py`, `scripts/staging/smoke_ab.py`): tipos `float`/fração, não são cópias.
- Textos históricos: `docs/historico/`, `CHANGELOG.md`, `handoffs/`, `docs/descricao_projeto/`, `specs/SPEC-381-*.md:700`.
- Qualquer mudança de comportamento, evaluator, expected, dataset, baseline ou caminho protegido de `evals/`.

## 3. Design técnico

- **Arquivos novos:** `docs/spec405/README.md` (R0: re-greps; capturas A/B do R7 com hash do commit e caminhos dos artefatos). Nenhum código.
- **Arquivos alterados:** `services/{law,creature_variants,creature_art,card_shop,lore_quests,rumor_adoption,reputation,npc_seed,companion_soul,auth_sessions,plot_threads}.py`, `observability/telemetry.py`, `world_utils.py`, `gamedata.py`, `api.py`, `routes/turn.py`, `state.py`, `agents/archivist.py`, `playtest/telemetry.py`, `observability/latency.py` (só o comentário), `tests/test_conflict_summary_lifecycle.py`, `tests/test_grounding_boundaries.py`, `tests/test_spec378_text_fold.py`.
- **Arquivos removidos:** `scripts/dev/api_inventory.py`, `scripts/dev/api_scanner_counts.py`, `scripts/dev/api_importtime.py`.
- **Schemas/assinaturas:** nenhum novo. `_persist_memory_records(game_id: str, records: list[dict]) -> bool` mantém assinatura e retorno; a única mudança é a chamada única `add_memory_to_session(game_id, texts, metadatas=metadatas)` dentro do mesmo `try/except Exception` (que já loga `rag_persist_failed` e devolve `False`).
- **Ao apagar:** imports órfãos saem (o `ruff check` aponta `F401`); `from typing import TypedDict` etc. só se ficar sem uso. Sem renomear nada vivo.

## 4. Plano passo a passo

Uma etapa por R, em ordem de menor para maior risco. Executor roda só os testes da etapa (máx. `-n 2`, via `bash scripts/dev/pt.sh`), `ruff` e commita.

### Etapa 0 — Linha de base (sem código)
1. Criar `docs/spec405/README.md`. Capturar A do R7 (evals `--seed 7`, playtest `--all --turns 10 --seed 0`). Rodar o R0 para os 19 símbolos e colar as saídas.
2. Verificação: A gravado; qualquer símbolo com acerto extra sai do plano e entra no hand-back.

### Etapa 1 — R3: três scripts
1. **Teste:** nenhum novo (remoção de ferramenta). Antes: `Grep` confirma zero referência fora de si/spec 381/doc histórico, e `ruff-baseline.toml`/`tests/size_budget.json` sem entrada.
2. `git rm` dos três; limpar baseline/budget só se existirem.
3. Testes: `tests/test_size_budget.py tests/test_spec192_staging_scripts.py tests/test_spec191_staging_tools.py -q`; `ruff check .`; `scripts/ruff_baseline.py --check` se a baseline mudou.

### Etapa 2 — R1: `services/` e `observability/`
1. **Teste:** nenhum novo; `python -c "import services.law, services.creature_variants, ..."` (via `py.sh`) prova que os módulos importam.
2. Apagar os 13 símbolos (um commit só; R0 já registrado).
3. Testes: `tests/test_law*.py tests/test_creature_variants*.py tests/test_creature_art*.py tests/test_card_shop*.py tests/test_lore_quests*.py tests/test_rumor*.py tests/test_reputation*.py tests/test_npc_seed*.py tests/test_companion_soul*.py tests/test_auth_sessions*.py tests/test_telemetry*.py tests/test_mecanica_orfa.py tests/test_cutover_audit.py -q` (os que existirem; `Glob tests/test_*<modulo>*` define a lista final). W2 B.

### Etapa 3 — R2: raiz e rotas
1. **Teste:** nenhum novo; `tests/test_api*.py` cobre o import do `api.py`/`routes.turn`.
2. Apagar `_TRAVEL_CUES`, `ARMADURAS`, `ESCUDOS`, `_error_code_of` + `_CODE_RE` local, `_MEMORIAL_DETAIL`, `CalendarDate`. Conferir que `re`/`Any` ainda são usados onde ficaram.
3. Testes: `tests/test_world_utils*.py tests/test_gamedata*.py tests/test_api_errors*.py tests/test_error_codes*.py tests/test_turn*.py tests/test_state*.py tests/test_persistence*.py -q` (Glob define). Smoke offline: `bash scripts/smoke_api.sh`. W2 B.

### Etapa 4 — R4: `archivist` sem `inspect` (revisor Sonnet obrigatório)
1. **Testes primeiro:** ajustar os stubs listados no R4 para aceitar `metadatas`/`**_kwargs` (continuam verdes com o código antigo). Acrescentar em `tests/test_memory_provenance.py` (ou onde já houver teste de `_persist_memory_records`) `test_persist_memory_records_sempre_envia_metadatas`: stub grava `kwargs` e asserta `kwargs["metadatas"]` com `len == len(texts)`; e `test_persist_memory_records_falha_do_rag_devolve_false` (stub lança) asserta retorno `False` sem exceção. O 2º pode já existir (`test_bug_memoria_resiliencia.py`); reaproveitar e não duplicar.
2. Remover o `inspect.signature` e o ramo `else`; chamada única com `metadatas=`.
3. Testes: `tests/test_conflict_summary_lifecycle.py tests/test_grounding_boundaries.py tests/test_memory_provenance.py tests/test_bug_memoria_resiliencia.py tests/test_narrative_evidence.py tests/test_projections.py tests/test_playtest_observability_hardening.py tests/test_embeddings_provider.py -q`. Playtest curto (W2 B) obrigatório: é o caminho de gravação da memória.
4. Revisor Sonnet: lê o diff do `archivist.py` e de cada stub, confirma que nenhum assert mudou e que `world_simulator` ficou intacto.

### Etapa 5 — R5: duas cópias de `fold`
1. **Testes primeiro:** adicionar as duas linhas ao `SITES` de `tests/test_spec378_text_fold.py` com `_legacy_services_plot_threads` e `_legacy_world_utils` (corpos antigos copiados). Verdes antes e depois da troca (a primeira linha já passa com o código antigo e prova a equivalência `site(x) == legacy(x) == fold(x, **opts)`).
2. Delegar para `services.text.fold` (R5). Estender `CORPUS` só se faltar caso relevante (`ß`, `İ`, espaços múltiplos, `None`) — a diferença `casefold`/`lower` precisa estar no corpus.
3. Testes: `tests/test_spec378_text_fold.py tests/test_plot_threads*.py tests/test_world_utils*.py tests/test_travel*.py tests/test_world_engine*.py -q`. W2 B.

### Etapa 6 — R6: `_percentile`
1. **Teste primeiro:** `tests/test_latency_timeline.py::test_percentile_nearest_rank_matches_playtest` (`:152`) já compara as duas; passa a ser trivial (mesmo objeto). Acrescentar a asserção `playtest.telemetry._percentile is observability.latency.percentile` em `test_latency_timeline.py` (é o contrato: uma só implementação).
2. Importar com alias; apagar a def; ajustar o comentário de `latency.py:349`.
3. Testes: `tests/test_latency_timeline.py tests/test_latency_metrics_compat.py tests/test_playtest*.py -q`. W2 B.

### Etapa 7 — Fechamento
1. Capturar B final; `evals compare` sem diferença; playtest com mesmas violações/desfechos por perfil. Registrar em `docs/spec405/README.md`.
2. `ruff format --check`, `ruff check`, `dup_helpers.py --diff main...HEAD`, `git diff --stat main...HEAD` (saldo negativo, ~−250/−300).
3. Revisão (Etapa 4 obrigatória, demais por amostragem); depois o coordenador: `/spec-land` (suíte completa 1×).

## 5. Critérios de aceite

- [x] R0: `docs/spec405/README.md` com o re-grep dos 19 símbolos; todo símbolo apagado só tinha a definição. Símbolos que mostraram uso estão no hand-back e fora do diff.
- [x] `git grep -nw -e CrimeCandidate -e PrisonerRef -e LawReceipt -e _debug_scores -e has_curated_art -e reload_config -e seed_from_proposal -e search_intent -e deed_event_types -e seed_ids -e _soul_for_quest -e utc_now -e run_with_context -e _TRAVEL_CUES -e ARMADURAS -e ESCUDOS -e _error_code_of -e _MEMORIAL_DETAIL -e CalendarDate -- '*.py'` não devolve nada.
- [x] `git grep -n "_CODE_RE" api.py` vazio; `services/error_codes.py` intacto.
- [x] Os três scripts do R3 não existem; `ruff check .` verde.
- [x] `grep -n "inspect.signature(add_memory_to_session)" agents/archivist.py` vazio; `_persist_memory_records` chama `add_memory_to_session(..., metadatas=...)` uma só vez; nenhum assert de teste mudou (só assinaturas de stub); `world_simulator` intacto.
- [x] `tests/test_spec378_text_fold.py` com as 2 linhas novas verdes; `_fold` de `plot_threads` e `_fold_txt` de `world_utils` delegam a `services.text.fold`.
- [x] `playtest.telemetry._percentile is observability.latency.percentile`; a def duplicada não existe.
- [x] W2: `evals compare` A × B sem diferença; playtest `--all --turns 10 --seed 0` com mesmas violações e desfechos por perfil.
- [x] Testes do escopo de cada etapa verdes (contagem no hand-back); `ruff format --check`, `ruff check`, `test_size_budget.py` verdes; saldo de linhas negativo.
- [ ] Revisão Sonnet da Etapa 4 APPROVED (pendente, independente).
- [ ] `uv run pytest` verde (suíte completa offline, 1× pelo coordenador no pouso).
- [x] Saves antigos continuam carregando (nenhum `GameState` mudou; `CalendarDate` é só tipo).

## 6. Smoke test com LLM real

Não se aplica: nenhuma etapa muda `with_structured_output`, prompt, roteamento ou campo de modelo; a Etapa 4 só remove um ramo que o mock/produção nunca tomam (o `rag.add_memory_to_session` real já aceita `metadatas`). O oráculo W2 (evals + playtest MockLLM) substitui o smoke, como na SPEC-376 §6. Verificação equivalente de infra: `bash scripts/smoke_api.sh` offline após a Etapa 3 e `uv run pytest tests/test_embeddings_provider.py -q` (grava no FAISS de verdade) após a Etapa 4.

## 7. Riscos & compatibilidade

- **Símbolo "morto" usado dinamicamente:** mitigado por R0 (inclui string/`getattr`/yaml) e pelo W2 (evals + playtest pegam caminho de runtime). `git revert` por etapa é seguro (um commit por etapa).
- **R4:** se algum teste fora da lista patchar `archivist.add_memory_to_session` com 2 posicionais, falha com `TypeError` capturado por `except Exception` → `_persist_memory_records` devolve `False` e o teste afirma outra coisa. Falha silenciosa possível: por isso o grep completo de `tests/` e o revisor.
- **R5:** `casefold` × `lower` e colapso de espaços são as diferenças reais; o teste de oráculo antigo×novo com corpus que as exercita é a prova.
- **R6:** risco de ciclo de import `playtest` ↔ `observability`; checar com `py.sh -c "import playtest.telemetry"`.
- Saves/persistência: nenhum formato muda. MockLLM/FallbackLLM: sem mudança. Quota/latência: nenhuma.

## 8. Decisões do dono

Nenhuma bloqueante. Para confirmar na aprovação:
- **D1** — Deixar `agents/archivist.py:481` (mesmo `inspect.signature`, para `add_npc_memory`) fora desta spec? Proposta: sim, follow-up se R4 passar limpo.
- **D2** — Aceitar o oráculo W2 (evals + playtest) como substituto do smoke real, como na SPEC-376? Proposta: sim.
