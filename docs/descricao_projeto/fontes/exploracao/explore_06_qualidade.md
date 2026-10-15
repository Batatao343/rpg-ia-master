# Qualidade, Processo e Governança — rpg-ia-master

Relatório de exploração (somente leitura). Fonte: CLAUDE.md, AGENTS.md, ESTADO_ATUAL.md, ROADMAP.md, `pyproject.toml`, `tests/`, `playtest/`, `evals/`, `project_index/`, `specs/`, `docs/`, `handoffs/`, `.github/workflows/`. Números são os registrados nos docs ou contados por mim em 2026-10-12; onde só li o ESTADO_ATUAL (não rodei a suíte), digo isso.

---

## 1. Visão geral: como o projeto se garante

O projeto empilha cinco camadas de garantia, da mais barata e frequente à mais cara e rara:

1. **Suíte offline `pytest`** (~190 arquivos, ~1.900 testes). Roda sem rede e sem chave, com MockLLM forçado. É o gate de toda tarefa.
2. **Linters de conteúdo e de código** (`scripts/validate_content.py`, Ruff, build Vite). Validam o lore e os dados estáticos.
3. **Harness de playtest agêntico** (`playtest/`). Joga campanhas longas sobre o mesmo grafo, com 14 perfis e invariantes por turno. Offline com MockLLM, ou "real" com LLM pago (opt-in, com tetos).
4. **Plataforma de evals determinísticos** (`evals/`, SPEC-165 a 176). Mede a qualidade com datasets travados por SHA-256, oráculos estruturados e comparação fail-closed.
5. **Processo spec-driven** (`specs/`, 198 specs com ID estável). Nada é implementado sem spec `approved`, e nada é "done" sem critérios de aceite, pytest verde e smoke real.

O princípio que amarra tudo está em CLAUDE.md: "Mecânica é Python, não LLM". Por isso quase todo o teste é determinístico, e o LLM real é tratado como caso especial caro (markers `llm_contract` / `llm_playtest`).

---

## 2. `tests/` — organização e funcionamento

### 2.1 Tamanho e organização

- `tests/` tem 198 entradas. Descontando `__pycache__`, `fakes/`, `fixtures/`, `saves/` e `conftest.py`, sobram cerca de 190 arquivos `test_*.py`. Contei cerca de 1.814 definições `def test_*` por grep. Parametrizações elevam o número coletado, e o ESTADO_ATUAL (topo) registra **1.898 passed, 35 skipped, 15 deselected** no último gate do clone (SPEC-176, 317,92 s). Não reexecutei a suíte nesta exploração.
- A nomenclatura segue duas famílias:
  - **Por fase/spec:** `test_fase0.py`, `test_fase25.py`…`test_fase28.py`, `test_fase31..34`, `test_fase43/44`, `test_fase51..53`, `test_fase61..65`, `test_fase71..73`. Os números espelham as fases do ROADMAP (2.5, 3.x, 4.x, 5.x, 6.x, 7.x).
  - **Por domínio:**
    - Conflito/Cartas: `test_conflito_*.py` (cartas, dano, reações, morte, fuga, abismo, preparação, resumo, tática, turno, zonas, virtudes, volume), `test_combat_lifecycle.py`, `test_death_flow.py`, `test_cutover_audit.py`.
    - Classes e balanceamento: `test_classes_refactor.py`, `test_balance_classes*.py`, `test_progression_20.py`, `test_tiers_5_plus_content.py`.
    - Playtest: `test_playtest_harness.py`, `test_playtest_profiles.py`, `test_playtest_scenarios.py`, `test_playtest_watchdog.py`, `test_playtest_start_levels.py`, `test_matrix_lock.py`, `test_matriz_a_contratos.py`, `test_pre_matrix_contracts.py`, `test_merchant_profile.py`.
    - Evals: `test_eval_harness.py`, `test_eval_governance.py`, `test_eval_routing.py`, `test_eval_state_rules.py`, `test_eval_memory_context.py`, `test_eval_narrative_npc.py`, `test_eval_frontend.py`, `test_ci_eval_gates.py`, `test_project_index.py`, `test_project_index_ab_harness.py`.
    - Infra local da Fase 10b: `test_postgres_*`, `test_rls_local.py`, `test_pgvector_*`, `test_s3_blob.py`, `test_multiworker_local.py`, `test_chaos_local.py`, `test_backup_restore_local.py`, `test_worker_fence_local.py`, `test_oidc_identity.py`, `test_observability_stack.py`.
    - Arte: `test_art_*`, `test_dynamic_art_*`, `test_visual_assets.py`.
    - Specs: `test_spec_index.py`, `test_spec_migration_safety.py` (garantem a integridade do `index.yaml` e da normalização de IDs).
- Subpastas: `tests/fakes/` (dublês), `tests/fixtures/`, `tests/saves/` (saves de teste isolados).

### 2.2 Isolamento e determinismo

- `tests/conftest.py:9` faz `os.environ.setdefault("RPG_FORCE_MOCK", "1")`. O `get_llm()` devolve então o `MockLLM` (`mock_llm.py`) mesmo que exista chave no `.env`. A suíte é, assim, offline e determinística.
- Desde a sessão 35 (hardening), a suíte inteira isola `saves/` e `data/saves_memory/` em `tmp_path`. Desde a spec isolar-cache-runtime (SPEC-051), o cache de runtime (bestiário, NPCs, artefatos custom) vai para `data/runtime/` (gitignored) ou para tmp. Antes disso, rodar testes ou o playtest sujava arquivos versionados e exigia `git checkout` manual.
- O `conftest.py` da raiz só injeta `pythonpath`.

### 2.3 Markers e o que fica fora do default

`pyproject.toml:68-74` define:

```
addopts = "-q -m \"not llm_contract and not llm_playtest\""
markers: llm_contract, llm_playtest, infra_local
```

- **`llm_contract`** (Fase 11, SPEC-026): contratos de shape contra o provider real, 9 verdes no Gemini real em 2026-07-06. Gasta quota. Roda com `uv run pytest -m llm_contract -v -s`. Existe também `scripts/run_llm_contract_gate.py`, usado pelo workflow protegido.
- **`llm_playtest`** (`tests/test_playtest_real.py`): os 4 perfis vitais (explorador, combate, diplomático, secret_rusher) jogam 30 turnos no LLM real. Afirmam zero erro, zero violação `error` e `mock=False`. `RPG_PLAYTEST_TURNS` encurta a campanha.
- **`infra_local`**: integração opt-in com Postgres/Auth/Storage/pgvector locais (Supabase Local). Sem o stack de pé, os testes são pulados. Isso explica os 35 skipped e 15 deselected. O gate de 28/08 registrou `infra_local` 13/13, `security_local` 5/5 e pgTAP 14/14.
- Os 15 "deselected" vêm dos markers excluídos. Os 35 "skipped" são testes de infra, browser ou rede que dependem de opt-in.

### 2.4 Skills do projeto (`.claude/skills/`)

- **`/qa`** (`.claude/skills/qa/SKILL.md`): roda `uv run pytest -q 2>&1 | tail -15`. A regra é token-lean: se tudo passou, reporta só a contagem. Se falhou, mostra o nome do teste e a linha decisiva. Variações: `--lf -x` para re-rodar o que falhou, ou arquivo específico.
- **`/wrap-up`** (`.claude/skills/wrap-up/SKILL.md`): ritual obrigatório de fim de tarefa:
  1. suíte completa verde;
  2. atualizar `ESTADO_ATUAL.md` (enxuto, detalhe vai para `CHANGELOG.md`) e `ROADMAP.md`;
  3. atualizar o status da spec;
  4. reindexar com `rag.py` se mexeu em lore ou regras;
  5. commit.
- Há ainda skills de design/UI de terceiros (taste, impeccable, etc.) no diretório, sem relação com a qualidade do motor.

### 2.5 Convenções de teste que valem como regra de processo

- CLAUDE.md "Convenções": prefixo `test_` em arquivos e funções.
- **MockLLM esconde bugs de mapeamento.** Ele devolve instâncias Pydantic válidas, então bug de nome ou tipo de campo só aparece com chave real. Por isso toda spec que mexe em structured output exige "smoke real §6".
- Exemplo concreto do padrão: o smoke da spec inicio-personalizado (sessão 17) mostrou que `max_length` duro no schema voltado ao LLM derrubava todos os candidatos de provider. O fix foi truncar em Python e deixar o limite estrito só na borda da API.
- **Anti-órfão (sessão 20):** `combat_mechanics.HANDLED_KINDS` mais um teste que varre os JSONs de classes e exige handler para todo `kind` ou `trigger`. Pegaria os 3 bugs de mecânica morta (taunt, Transformação, Purga) que o mock escondia.
- Guard obrigatório de `FallbackLLM` em todo nó com `with_structured_output` (auditoria: 12/12 sites blindados em 2026-07-13).

---

## 3. `playtest/` — harness de playtest agêntico (Fase 5)

### 3.1 Arquitetura

Tamanhos de módulo (`wc -l`): `runner.py` 1.706, `telemetry.py` 1.513, `invariants.py` 1.312, `profiles.py` 1.272, `__main__.py` 425, `report.py` 398, `scenarios.py` 159, `provider_profiles.py` 142, `matrix_lock.py` 124, `pricing.py` 50, `metrics.py` 48, `matrix.py` 38.

O princípio é rodar campanhas sobre **o mesmo grafo** do produto (`app.invoke` / `stream`), sem lógica paralela. Cada turno segue estes passos:
1. O perfil gera a ação.
2. O grafo executa.
3. O runner captura estado, rota e telemetria.
4. As invariantes validam o estado.
5. Uma linha JSONL é gravada.

Saves ficam isolados em `saves_playtest/`. Runs ficam em `playtest_runs/<run_id>/`. Ambos são gitignored.

### 3.2 CLI (`playtest/__main__.py:349-414`)

- `run --profile X | --all --turns N --seed S --start-level 1..20 --class C --real --no-invariants --max-requests 15 --max-cost USD`: campanha avulsa ou todos os perfis.
- `report <run_id> [--baseline <run_id>]`: agrega em Markdown (per-perfil, violações, custo, seção Classes e Mortes).
- `transcript <run_id>`: renderiza ação→narração por turno (`report.py:114 render_transcript`). Serve para julgar o prompt à mão.
- `merchant-suite`: matriz longa do comerciante (1×200 real, ou 5×200 offline).
- `matrix-suite --label A|B --turns 200 --real --max-requests --max-cost --turn-timeout --start-index`: a matriz pareada 10×200.
- `--scenario recrutamento|comercio`: cenário dirigido (ver 3.4).

### 3.3 Os 14 perfis (`playtest/profiles.py:1266`)

Cada perfil é uma classe determinística (seed) com `decide(state, rng) → ProfileDecision`. A decisão é única e atômica: o texto e a mecânica derivam da mesma `ProfileDecision` (`profiles.py:100`). Foi o fix "decisão atômica" da sessão 28, para o texto não divergir do que o motor recebe.

| Perfil | Linha | Papel |
|---|---|---|
| `Agressivo` | 440 | Ataca tudo e provoca combate. Agente curioso: usa habilidades de Entropia. |
| `Explorador` | 454 | Viaja por fronteira, com memória anti-backtrack (fix SPEC-061, que evitou oscilar cidade↔interior). |
| `Comerciante` | 543 | Stateful e não onisciente: livro de cotações, metas de trade, política de venda/compra. |
| `Diplomatico` | 858 | Fala com todo NPC em cena e tenta recrutar. |
| `Troll` | 891 | Entradas absurdas e injeção: o motor não pode quebrar. |
| `MapaBreaker` | 908 | Viaja para lugares desconexos ou inexistentes. |
| `Combate` | 925 | Provoca encontros em perigo alto e ataca. |
| `NpcOnly` | 947 | Só conversa, inclusive com NPC fora de cena (testa o gate de cena). |
| `LootAbuser` | 961 | Loot, craft e compra repetidos; tenta duplicar item único. |
| `SecretRusher` | 977 | Pergunta direto pelos segredos (o narrador não pode vazar). |
| `Quester` | 998 | Persegue quests ativas e o beat atual. |
| `Fujao` | 1039 | Entra no perigo e foge (exercita a fuga de Python, depois chase/`escapou`). |
| `Recrutador` | 1069 | Faz o máximo de amigos (aliados em combate, SPEC-055). |
| `Normal` | 1128 | O 14º perfil: jogador curioso e prudente que mistura os sistemas (viagem, NPC, quest, loot, descanso, combate prudente) e resolve escolhas pendentes via `progression.apply_choice`. Restrito à visão pública (SPEC-120). |

Os perfis dos docs ("13 perfis") ficaram defasados em relação ao código, que tem 14 desde a sessão 39.

Helpers relevantes: BFS pelo mapa público (`_next_hop_toward`, `profiles.py:74`), filtro de locais fatais aprendidos (`_fatal_location_ids`, `profiles.py:51`, SPEC "explorador aprende com mortes"), recuperação razoável (`_recovery_decision`, `profiles.py:194`) e decisão de combate declarativa (`_combat_decision`, `profiles.py:337`).

### 3.4 Cenários dirigidos (`playtest/scenarios.py`)

Pré-condição, ação e oráculo fechados. Ficam fora de `PROFILES` e de `--all`. Existem dois, `recrutamento` (NPC "Brunna Ponte-Alta") e `comercio` (200 de ouro, `scenarios.py:15-24`). Provam uma vertical sem esperar que a simulação sorteie o NPC ou o mercador certo. Rodam via `--scenario`. Smokes reais de 2026-08-03: Brunna entrou na party e a Poção de Cura Menor foi comprada (200→140 de ouro).

### 3.5 Invariantes e severidades (`playtest/invariants.py`)

`Severity = Literal["error","warning"]` (linha 19). `check_all` (linha 1275) chama todos os checks e converte exceção de check em violação `invariant.crash` (1284 e 1296). Só **`error`** reprova a campanha. `warning` é sinal para a análise. A lista que consegui mapear:

**Estado e economia**
- `check_vitals` (38): HP, vitalidade e game_over. Inclui `vitals.dead_no_game_over`, ajustado para não disparar falso positivo com `death_pending`.
- `check_vitality_consistency` (90): `vitality.consistency`, error. HP e Vitalidade canônica não divergem.
- `check_wound_capacity` (129): `wound.capacity`, error.
- `check_economy` (175): ouro e inventário sem negativos nem NaN, unique não duplicado.
- `check_entities` (224): `entity.npc_duplicate_identity`, error.
- `check_world` (273): relógio, local válido e fações.
- `check_zero_vitality_outside_terminal` (999): `player.zero_vitality_outside_terminal`, error. Pegou 7 ocorrências reais na matriz A (perfil combate).
- `check_actor_lifecycle` (1017): `transition.unresolved_at_boundary`, error. Fase do ator (SPEC-141).
- `check_false_player_death` (1188): `narrative.false_player_death`, error.
- `check_roundtrip` (440): `save.roundtrip`, warning.

**Memória e resumo**
- `check_summary_bounds` (311): `memory.summary_bounds`, error. O resumo tem teto de 1.200 chars.
- `check_summary_lifecycle` (620) e `check_duplicate_consumed_summary` (644): `summary.lifecycle`, `summary.duplicate_consumption`.
- `check_memory_provenance` (545): `memory.location_grounding`, `memory.inventory_grounding`, `memory.npc_identity_grounding`, `memory.confirmed_without_source`.
- `check_rag_persistence` (529): `rag.persistence_error`.

**Narrativa e conhecimento**
- `check_knowledge` (403): `knowledge.secret_leak`, **warning** (linha 418). Ignora segredo já conhecido pelo jogador (fix D da sessão 23). Também checa o texto dos beats (SPEC-037).
- `check_reward_feedback` (362): `narrative.reward_contradiction`, error.
- `check_meta_leak` (1105): `narrative.meta_leak`, error.
- `check_repeated_opening` (1063): `narrative.repeated_opening`, warning. É filtrado em modo mock.
- `check_recycled_npc` (964): `narrative.recycled_npc`, warning. Exige uso observável.
- `check_invalid_sentinels` (500): `npc.invalid_sentinel`.
- `check_campaign_grounding` (324): `campaign.region_grounding`, error. Pegou o plano de Nova Arcádia que sobreviveu à viagem para Brekmar.

**Combate**
- `check_combat_zombie` (484): `combat.zombie`, error. `idle_turns >= 5` (SPEC-038).
- `check_combat_no_progress` (740): `combat.no_progress`.
- `check_phantom_ally` (1124): `combat.phantom_ally`, warning.
- `check_effect_catalog` (1165): efeito fora do catálogo fechado.
- `check_action_declaration` (754): `action.declaration_matches`, a ação declarada bate com a executada.
- `check_interaction_no_progress` (1087): `interaction.no_progress`, warning.

**Contextuais** (`check_contextual`, 821)
- `profile.private_plan_leak` (o perfil Normal só usa visão pública).
- `economy.transaction_conservation`, `economy.stock_bounds` e `economy.net_worth_finite` (livro-razão do comerciante).
- `combat.flee_progress_mislabeled`.
- `performance.turn_latency` (910-911): warning acima de 45 s, error acima de 90 s (`latency_ms > 90_000`).

**Reprodutibilidade:** `check_reproducibility(seed, rounds)` (1217) roda o harness duas vezes com a mesma seed e exige o mesmo resultado.

Observação: invariantes foram sendo adicionadas cada vez que um playtest achou um defeito sistêmico. É o mecanismo de "regressão permanente" do harness. O dataset de evals `playtest_invariants` (secção 4) reutiliza `check_all` sem copiar as regras.

### 3.6 Telemetria e relatório

- `telemetry.py` (1.513 linhas) escreve JSONL por turno e um `summary` por campanha (`write_turn`, linha 846). O JSONL tem rota, latência por nó (count, média, p50, p95, max, SPEC-116), violações, tentativas LLM (provider, modelo, `fell_back`, `network_attempted`), custo estimado e estado resumido.
- Ela agrega: diversidade de rotas, `% combate`, funil de pedidos de quest (pedido→quest→conclusão, D+0..D+3), mortes por epoch, conflitos iniciados e encerrados, gasto de Entropia (`spent_total`, `%ativa`, starvation/flooding redefinidos por gasto), escolhas de progressão e métricas econômicas.
- `circuit_open` é normalizado como `network_attempted=false` e fica em `llm_skipped`, sem contar como request nem custo (fix da sessão 33).
- `report.py` produz o Markdown. `render_transcript` (linha 114) produz o transcrito.
- `metrics.py` guarda utilidades de percentis.

### 3.7 Modo real, preços e tetos

- `--real` é opt-in e consciente de custo. Um hook `set_llm_telemetry_hook(fn)` de `llm_setup` entrega `(provider, model, tier, latency_ms, fell_back)` por invoke. Não entrega tokens.
- `pricing.py` converte invoke em USD por **estimativa**: 1.200 tokens de entrada e 400 de saída por invoke × preço por milhão (tabela `PRICE_PER_MTOK`, linhas 17-33). A tabela cobre `deepseek-v4-flash` a 0,14/0,28 e `gpt-oss-120b` a 0,15/0,60, entre outros. O default é (1,00 / 3,00). Nunca é fatura. Achado da matriz B: o custo estimado subconta o real.
- `--max-requests` e `--max-cost` abortam a campanha. O default de requests é 15.
- **Fail-closed** (`playtest-real-llm-fail-closed`): as tentativas são agrupadas por invoke. O primeiro grupo sem `success` aborta a matriz e nenhum par seguinte inicia. Isso evita que o fallback do produto (resiliente) mascare um provedor morto e produza uma "baseline" falsa. Foi exatamente o que aconteceu na A0/A1 de 20/08, e por isso virou regra.
- **Watchdog** (`--turn-timeout`, SPEC-088 e SPEC-120): prazo absoluto cobrindo o startup e o turno. Resultado que chega tarde, após suspensão do notebook, é rejeitado. Um timeout fecha o manifesto como `aborted`. Falha permanente de provedor abre um circuit breaker até a próxima campanha.
- **Manifesto v3** (SPEC-080): `owner (pid, host)` mais `heartbeat_at`, tocado por turno. Runs `running` antigas viram `aborted/stale_running_manifest` apenas se o PID estiver morto ou o heartbeat vencido. PID vivo no host atual sempre vence a idade.

### 3.8 `provider_profiles.py` e rotas

`provider_profiles.py` define perfis de rotas exclusivos do playtest real (`routes/deepseek_paid.json`, `routes/groq_free.json`). Eles são ativados via `RPG_ROUTES=<path>` por context manager (`activated_routes_profile`, linha ~40). O preset **`deepseek-paid`** isola `deepseek-v4-flash` nos três tiers (sem mistura de provedor, sem MockLLM) e eleva o timeout do DeepSeek a 40 s só para o experimento. O produto mantém o fail-fast. Há um `preflight` real estruturado (3/3 no tier CLASSIFY/FAST/SMART) que falha com `ProviderPreflightError` antes de gastar a matriz. O perfil `groq-free` usa pacing por limites de free tier.

### 3.9 Matriz pareada (`matrix.py`, `matrix_lock.py`)

`LONGRUN_MATRIX` (`matrix.py:17-28`) fixa 10 casos, com perfil, classe, nível inicial e seed:

| # | Perfil | Classe | Nível | Seed |
|---|---|---|---:|---:|
| 1 | normal | Devoto do Abismo | 1 | 6200 |
| 2 | explorador | Arcanista Cinzento | 3 | 6201 |
| 3 | diplomatico | Médico de Campo | 5 | 6202 |
| 4 | combate | Sangromante | 7 | 6203 |
| 5 | comerciante | Corruptor | 9 | 6204 |
| 6 | quester | Devoto do Abismo | 11 | 6205 |
| 7 | recrutador | Médico de Campo | 13 | 6206 |
| 8 | fujao | Arcanista Cinzento | 15 | 6207 |
| 9 | secret_rusher | Corruptor | 18 | 6208 |
| 10 | loot_abuser | Sangromante | 20 | 6209 |

- `select_matrix_cases(start_index)` (linha 36) devolve uma cauda canônica sem renumerar pares, seeds ou perfis. Foi o que permitiu a "continuação" de 21/08 (`--start-index 5`).
- **Níveis iniciais** (`start_level 1..20`) são aplicados pelo pipeline oficial de XP, com subclasse resolvida deterministicamente, Cartas preparadas e Ápice. Não é um atalho de gravação de estado.
- **Single-flight** (`matrix_lock.py`): `.matrix-suite.lock` em `playtest_runs/` impede duas matrizes simultâneas (`MatrixAlreadyRunningError`). O lock é atômico, grava pid e host, e usa `_pid_is_alive` com `ctypes`/`OpenProcess` no Windows (acesso negado conta como vivo). Existe porque um processo Groq órfão competia por quota e contaminava a medição (sessão 55).
- **Protocolo A/B pareado:** a matriz A mede a baseline. Depois vêm o diagnóstico, as specs e os fixes. A matriz B repete exatamente os mesmos pares, níveis, seeds e tetos. Qualquer regressão nova na B interrompe o ciclo para decisão humana. Tetos do `deepseek-paid`: 800 requests e US$ 0,25 por campanha.

---

## 4. `evals/` — plataforma de evals (SPEC-165 a 176)

### 4.1 Filosofia (`evals/README.md`)

- A "régua" (`evals/core`, `evals/evaluators`, CLI, datasets de regressão, registry, schemas e lock) é **protegida**. Quem otimiza o produto não pode alterar evaluator, expected, dataset, denominador, baseline ou exclusões na mesma tarefa. Isso evita "ajustar a régua para passar" (AGENTS.md, "Integridade de eval").
- Deterministic-first. LLM-as-judge **nunca bloqueia** nesta versão e não substitui oráculo estruturado. Fica informativo até existir uma meta-eval auditável (SPEC-171).
- Holdout verdadeiro vive em **repositório privado separado** e devolve só métricas agregadas e IDs opacos. É proibido ter `datasets/holdout` no repo público. Sem o companion privado, os scores são "dev scores", não evidência de generalização.

### 4.2 Estrutura

- `evals/core/`: `governance.py` (309 linhas, verificação do lock), `hashing.py`, `schemas.py`, `adapters.py` (694; registry e adapters), `runner.py` (464), `compare.py` (72).
- `evals/evaluators/`: `exact.py`, `routing.py`, `projection.py`, `memory.py`, `narrative.py`.
- `evals/datasets/regression/`: `governance` (2 casos), `harness` (2), `routing_actions` (25), `state_rules` (12), `memory_context` (27), `narrative_npc` (27). São 95 casos JSONL públicos. Mais os 86 casos determinísticos de produto referidos na baseline v1 (o CLI de sete suites deu 86/86 em SPEC-176).
- Schemas JSON gerados: `eval-case`, `eval-result`, `eval-run`, `eval-run-result`.
- `evals/runs/`: resultados endereçáveis (baseline-v1, smokes das SPEC-172/173).
- `evals/experiments/TEMPLATE.md`: modelo de experimento.

### 4.3 Manifest lock SHA-256 e governança

- `evals/manifest.lock.json` guarda: hash `sha256:` de cada dataset, `evaluator_version` (**1.6.0**), hash do `metrics-registry.yaml`, e `ruler_sources` com o hash de cada arquivo da régua (`__main__.py`, `core/*.py`, `evaluators/*.py`).
- `uv run python -m evals.core.governance check --root .` falha fechado se qualquer hash divergir.
- `evals/protected-paths.txt` lista o que tarefas de otimização não podem tocar: `evals/core`, `evals/evaluators`, `evals/__main__.py`, `evals/datasets/regression`, lock, registry, o próprio arquivo, os schemas e `web/e2e/contracts`. O CI valida isso via `scripts/verify_protected_eval_change.py` e o job `protected-evaluator-review` (`eval-gates.yml:40`).
- **Incidente SPEC-176 (02/10):** a integridade falhava em checkout limpo por diferença **LF vs CRLF** nos hashes. A correção foi `.gitattributes` fixando LF para a régua e o source, com relock canônico mudando só o hash dos 27 casos narrative/NPC (idênticos à evidência aprovada). Consequência: a baseline v1 é histórica e incompatível por hashes CRLF. Nenhum delta A/B é válido contra v1.

### 4.4 Registry de métricas (`evals/metrics-registry.yaml`)

Cada métrica define direção, tipo, se bloqueia, unidade, numerador, denominador e exclusões. Exemplos:
- `exact_match` (hard_limit 1.0);
- `route_accuracy` e `target_accuracy` (exclui casos sem contrato de target);
- `state_transition_pass_rate`;
- `memory_write_precision` (hard_limit 1.0);
- `memory_recall_at_1/3/5` (`blocking: after_baseline`);
- MRR, context recall, leaks e budget.

### 4.5 Adapters (`evals/core/adapters.py:661-673`)

O registry é explícito: `governance`, `playtest_invariants` (chama `playtest.invariants.check_all`), `state_rules`, `routing` e `action_contracts`, `memory_write`, `memory_retrieval`, `context_grounding`, `generation_boundary`, `narrative_claims`. Os adapters produzem só `actual`. O `expected` fica fora da visão do produto (fixture-authored).

### 4.6 Evaluators por domínio e SPEC

- **SPEC-167 (harness)**: executa datasets travados sem chave, contabiliza result/error/skip e grava JSON e Markdown. Comparação falha fechado por ruler, dataset ou config incompatível. A identidade do produto inclui HEAD, hash dos bytes visíveis ao Git e dirty state.
- **SPEC-168 (state/rules)**: 12 casos com `ProjectionEvaluator`, comparando só os campos declarados. Cobrem eventos, regras, economia, inventário, item único, quests, lifecycle/death/restore, combate, migração, save/load e replay. Métricas: `state_transition_pass_rate=1.0`, `exact_match=1.0`.
- **SPEC-169 (routing/action)**: 25 casos, com decisão estruturada pré-narração, target exato ou conjunto aceito, variantes metamórficas, negativos e matriz de confusão. Todas as métricas em 1.0 com matriz diagonal.
- **SPEC-170 (memory/RAG/context)**: 27 casos que separam `store→retrieve→context→generate`. Recall@1/3/5, MRR, inclusão e descarte de contexto, hard gates de secret/forbidden leak e budget. Smoke v3: R@1 `0.5833`, R@3/5 `1.0`, MRR `0.8333`. Vetores são fixtures offline, e a camada generate cobre só o guard determinístico (não mede qualidade semântica de prosa). Revisada pelo reviewer Astra.
- **SPEC-171 (narrative/NPC)**: 27 casos (morte, posse, localização, identidade, segredo, reward/outcome, presença em cena, ação, lifecycle). Mutações separam vazamento real, substituição neutra e supressão indevida. Persona fica não bloqueante e sem calibração.
- **SPEC-172 (frontend F01–F16)**: `web/e2e/critical-journeys.spec.ts` e `.yaml`, mais `visual-surfaces.spec.ts` e `fixtures.ts`, com Playwright/Chromium e API determinística. Guards globais de pageerror, console, rede e 5xx. axe mais viewports 320/390/768/1440. Smoke: 16/16, pass rate 1.0. A execução achou e corrigiu 5 falhas reais: bootstrap de auth vazando requests protegidos, fim de SSE sem narração, mapa não interativo, contraste 3,77:1 e HUD móvel sem botão de fechar.
- **SPEC-173 (CI gates)**: ver 4.7.
- **SPEC-174 (baseline v1)**: 86 casos mais F01–F16, hard gates verdes e hashes registrados em `docs/eval-baselines/v1/`. Provider real omitido por custo. Long-run excluído pela spec. Nenhum target foi inventado.
- **SPEC-175 (Project Index A/B)**: ver secção 5.
- **SPEC-176 (integridade em clean checkout)**: `review-pending` (ver 4.3).

### 4.7 CI (`.github/workflows/`)

- `validate.yml`: PR, job `test` (Ruff, lint de conteúdo, build web, pytest). `uv sync --extra openai --extra anthropic`, porque os testes de roteamento exercitam esses providers num ambiente limpo.
- `eval-gates.yml`: `scope` (calcula escopo via `scripts/ci_eval_scope.py`), `protected-evaluator-review`, `deterministic-evals` (sempre ativo), `backend-selective`, `frontend-selective`.
- `eval-protected.yml` (manual): `real-provider-short` (teto duro de 20 requests e US$ 0,20) e `private-holdout` (somente agregado), em Environment protegido.
- `post-deploy-smoke.yml`: smoke read-only com verificação de SHA (`scripts/post_deploy_smoke.py`).
- `audit-local.yml`: job `infra-browser` com gate de infraestrutura local (13/13 e 25 passed, zero skipped), promovido a push e PR da main.

---

## 5. `project_index/` — grafo do repositório

- **O que é:** grafo determinístico gerado por **AST Python** (`generator.py`), com mapa file-only de TS/JS, proveniência e `confidence` por aresta. Artefatos: `repo_graph.json` (schema `repo_graph.schema.json`), `manifest.json` (freshness por source-tree hash), mapas curados `domains.yaml`, `state_ownership.yaml` e `eval_map.yaml`. Conteúdo privado ou gerado é excluído. Relações HTTP são `static_best_effort`, sem alegar autoridade em Python dinâmico (SPEC-166).
- **CLI** (`project_index/__main__.py`): `build`, `check`, `query`, `symbol`, `impact`, `tests`, `state`, todos bounded (`--limit 12`).
- **Tamanho atual:** 5.516 nós e 14.089 arestas (SPEC-176).
- **Benchmark A/B v6 (SPEC-175):** quatro sessões, 32 observações, modelo `gpt-5.6-sol/high`, ground truth selado por AES-256-GCM antes dos runs e aprovado em revisão Sol (`SPEC-175-SOL-20261001-V6-01`). A condição B (com índice) tinha cada tarefa começando por `index:query`.

| | A (sem índice) | B (com índice) |
|---|---:|---:|
| Localização correta | 16/16 | 16/16 |
| Calls medianas | 5 | **8** |
| Bytes lidos medianos | 24.676 | **30.999,5** |
| Wall time mediano | 38,9 s | **58,3 s** |
| Vitórias de custo | n/a | **0/8** |

(Fonte: `docs/project-index-benchmark/v6/mechanical-summary.md`.)

- **Decisão (ESTADO_ATUAL, bloco 01/10):** retirar o índice do contexto e do fluxo padrão. Ele permanece só para consultas explícitas, seletivas e confirmadas no source. AGENTS.md ponto 3 codifica isso: "o Project Index não entra no contexto ou fluxo padrão". Versões v2–v5 do benchmark ficaram como histórico invalidado. O v6 foi o confirmatório selado.
- O arquivo `project_index/manifest.json` aparece como modificado no git status e é regenerado sempre que o source muda (o teste `test_project_index.py` cobre staleness).

---

## 6. `specs/` — desenvolvimento spec-driven

### 6.1 Regras (CLAUDE.md "Desenvolvimento spec-driven")

1. Feature nova começa como `specs/<nome>.md` copiado de `specs/TEMPLATE.md`, status `draft`.
2. O usuário revisa e a spec vira `approved`.
3. A implementação segue o plano da spec, com testes primeiro. Desvios atualizam a spec no mesmo commit.
4. Conclusão exige critérios de aceite marcados, `uv run pytest` verde e smoke real. Só então `done`, e ROADMAP e ESTADO_ATUAL são atualizados.
5. O ROADMAP é resumo e link. O detalhe técnico mora só na spec.

### 6.2 IDs e índice

- SPEC-163 normalizou as 162 specs históricas em **IDs estáveis SPEC-001 a SPEC-162**, pela ordem comprovada de criação no Git, e criou `specs/index.yaml` (reproduzível, gerado por `scripts/normalize_specs.py`). O índice registra: `id`, `slug`, `status`, `created_commit/at`, `completed_commit/at`, `completed_order`, `depends_on`, ambiguidades de linhagem (`lineage_ambiguous`, `tie_breaker: slug_lexical`).
- A ordem de criação é separada da ordem de conclusão. `test_spec_index.py` e `test_spec_migration_safety.py` guardam isso.
- Hoje há **200 arquivos** em `specs/` (`SPEC-001`…`SPEC-198`, `TEMPLATE.md`, `index.yaml`). O contador do índice dá **174 done, 22 approved, 1 draft, 1 review-pending**.
  - Draft: SPEC-104, a certificação cloud. Fica on hold.
  - `review-pending`: SPEC-176.
  - **22 approved** = SPEC-177 a 198. É o pacote "v5" importado em 02/10: JEV (decision backend adapter, router A/B, target/loot/context, expansão do tier CLASSIFY), monetização e hosted (Supabase remoto, medição de uso real, pricing, carteira e ledger, dashboard de custo, speech-to-text, voz web e mobile, cotação de imagens pagas, Stripe, segurança de conta, Vercel staging, Capacitor Android, Google Play Billing, reconciliação, FinOps, beta pago fechado e publicação Google Play).

### 6.3 Linha de ordenação de execução

`docs/evals-plan-v4/SPEC_EXECUTION_ORDER.md` e os arquivos `00` a `12` do plano v4: princípios, arquitetura-alvo, métricas, datasets, frontend, CI, roadmap, contrato do coding agent, checklist, indexação e política de execução de modelos. O arquivo `12_MODEL_EXECUTION_POLICY.md` define o menor tier suficiente. AGENTS.md resume o roteamento: Luna (inventário, transformações, relatórios), Terra (implementação bounded), Sol (cross-domain, concorrência, estado, revisão técnica) e Astra (só checkpoints conceituais e semântica de evaluators). Se o modelo ou reviewer mínimo não existir, escreve-se `MODEL_HANDOFF_REQUIRED` e prepara-se `handoffs/SPEC-xxx-<model>-review.md`, sem autoaprovação.

### 6.4 `handoffs/`

Nove revisões independentes: `SPEC-164-sol-review`, `SPEC-165-astra-review`, `SPEC-166-sol-review`, `SPEC-167-sol-review`, `SPEC-175-SOL-review` (v1, v4 e v6) e `SPEC-176-SOL-review` e `-independent-review`. Mostram o padrão "executor atestado ≠ revisor". Exemplo: SPEC-176, executor `gpt-6.1-sol/high`, revisor independente Sol com resultado "APPROVED técnico local". O approval humano `eval-governance`, o push e o CI verde continuavam pendentes.

### 6.5 Scripts úteis (`scripts/`)

Conteúdo e dados: `validate_content.py`, `content_report.py`, `migrate_lore_nova.py`, `gen_cards_v4.py`, `gen_classes_v2.py`, `gen_tiers_5_plus.py`, `gen_world_living_npcs.py`, `migrate_bestiary_v4.py`, `import_visual_assets.py`.
Gates e CI: `ci_eval_scope.py`, `verify_protected_eval_change.py`, `validate_holdout_aggregate.py`, `run_llm_contract_gate.py`, `post_deploy_smoke.py`, `frontend_eval_report.py`, `audit_local_gate.py`, `audit_local_server.py`.
Operação e infra local: `dev_stack.py`, `start_local_api.py`, `browser_local.py`, `chaos_test.py`, `load_test.py`, `backup_local.py`, `restore_local.py`, `verify_restore.py`, `recover_operations.py`, `readiness_report.py`, `smoke_local_profile.py`, `smoke_api.sh`, `migrate_file_saves.py`, `export_game_data.py`.
Medição: `benchmark_turn_pipeline*.py`, `project_index_ab_harness.py`, `normalize_specs.py`.

---

## 7. Pipeline de autoria e lint de conteúdo (Fase 7)

- `docs/guias/AUTORIA.md` define 3 camadas de conteúdo:
  - **Fonte:** `lore_nova/*.txt`, sempre sobrevive.
  - **Codex gerado:** `data/codex/**/*.md`, regenerado pelo `migrate_lore_nova.py`, **não** sobrevive.
  - **Curadoria:** `data/codex_overrides.yaml`, arquivos com `curated: true`, `entities_extra.json`, edges, `relation_types` e `components`, que sobrevivem.
- Fluxo A (NPC manual): copiar template de `docs/guias/templates/codex/`, nome do arquivo igual ao `id`, `curated: true` **obrigatório** (senão o migrate apaga), segredo em doc paralelo `type: npc_secret` com `visibility: hidden` (SPEC-024), registrar em `entities_extra.json`, rodar o lint e reindexar.
- `services/content_validator.py` (~900 linhas) tem os validadores `validate_frontmatter`, `validate_ids`, `validate_references`, `validate_aliases`, `validate_visibility`, `validate_encoding`, `validate_overrides`, `validate_cards` (anti-reskin via `effect_signature`), `validate_bestiary` (`creature_signature`) e `validate_visual_assets` (identidade, hash, bytes e cobertura da arte). `validate_all` (linha 855) agrega e devolve `Finding`s.
- `scripts/validate_content.py` imprime agrupado por validador e sai com 1 se houver ERRO (AVISO não falha). Roda também como teste (`tests/test_fase71.py::test_repo_content_sem_erros`), na CI e como **gate do reindex**: `uv run python rag.py` aborta se o lint achar erro. Estado atual: 0 erros e 0 avisos.
- Resultado prático: a curadoria da Rede Carmesim (sessão 20) mostrou o processo funcionando. Um over-share de segredo em `factions.txt` foi suavizado, o lore reindexado (2.203 chunks) e a assinatura de iminência foi adicionada a `secret_signatures`.

---

## 8. ROADMAP — resumo de cada fase

| Fase | Conteúdo | Estado/data |
|---|---|---|
| **0** | Fundação: mapa, relógio de mundo, viagem com fog of war, descanso, gating de classe (`world_utils.py`) | Entregue (primeira fase) |
| **1** | Frontend React+Vite+TS (tom Witcher, `motion`) com fallback vanilla | Entregue |
| **2 / 2.5-2.8** | Fações e memória de NPC; **Codex** estruturado e grafo de mundo (558 entidades), `event_log` e `world_projection` (2.5); dados mecânicos de Valoria (2.5b); eventos estruturados validados (2.6); rules engine sistêmica (2.7); context builder com orçamento de tokens (2.8) | 2026-07-02 a 07-03 |
| **3** | Clareza de campanha: crônica por capítulos (3.1), conhecimento revelável (3.2), quest log (3.3), visualização de estado (3.4) | 2026-07-03 |
| **4** | Gameplay core: progressão/XP (4.1, 4.1b árvores), buffs (4.2), inventário/equipamento (4.3), economia determinística (4.4), party (4.5), dificuldade e morte digna (4.6) | 2026-07-04/05 |
| **5** | Playtest agêntico: harness (5.1), invariantes (5.2), telemetria e relatório (5.3) | 2026-07-06 |
| **6** | Conteúdo sistêmico: economia viva, 20 itens únicos, migração de monstros, encontros sistêmicos, clima com efeito | 2026-07-05 |
| **7** | Autoria e validação: lint e CI (7.1), curadoria migration-safe (7.2), segredos de NPC (7.3) | 2026-07-05 |
| **8** | Arte contextual: 8A âncoras visuais curadas (45 assets, 90 WebPs, save v6, SPEC-094) `done` 2026-08-12; 8B arte dinâmica rara (GPT Image 2, budget por arco) local `done` | 2026-08 |
| **9** | Sprites e som | **Backlog**, sem spec aprovada |
| **10** | Hardening local: `game_id` UUID, `schema_version` e migrations, CORS/rate-limit/log JSON (SPEC-025) `done`; **10b** local-first (Supabase Local, Postgres+RLS+Auth+pgvector+storage, turnos duráveis, workers, backup/restore, observabilidade) `done` em 2026-08-20; certificação cloud (SPEC-104) `draft` | 2026-07-06 e 2026-08-20 |
| **11** | Contratos LLM reais (`-m llm_contract`, 9 verdes) | 2026-07-06 |

Marcos extras no ROADMAP: roteamento multi-provider (2026-07-06), migração do sistema de conflitos (Valoria v2, épico conflito-01..17), refatoração em 5 Posturas e árvore rica de 101 habilidades (07-19), criação imersiva (07-17), tiers 5+ (níveis 9–20) e Crônica avançada.

---

## 9. Histórico: principais playtests longos e o que descobriram

(Resumos dos `docs/playtest-*.md`. Não li os JSONL.)

1. **Longrun 2026-07-14** (`playtest-longrun-2026-07-14.md`): 3 perfis × 100 turnos no LLM real (DeepSeek), cerca de US$ 0,25 e zero erro de turno. O quester concluiu 7 de 7 quests, mas passou 100 turnos em 1 local. Revelou **7 defeitos**:
   - harness sem stop no game_over (rodava 140 de 300 turnos morto);
   - espiral pós-Saque;
   - combate zumbi (59 turnos ativo);
   - segredo vazando via beat;
   - "Ninguém responde." com aliado em cena;
   - beat em inglês;
   - NPC reciclado.
   Gerou 8 specs (SPEC-037 a 044) e a decisão de DeepSeek como primário. Também achou o RAG morto por 429 do Google, o que levou a Jina como provedor de embeddings (SPEC-039).
2. **Jogador normal 2026-08-12** (`playtest-jogador-normal-2026-08-12.md`): 440 turnos (2×200 mock + 40 real), 0 violações formais, mas **3 defeitos escondidos**: fuga reinicia a trilha (P0); checkpoint restaura o save mas deixa a morte descartada no FAISS como `CONFIRMADO` (P0); plano de Nova Arcádia sobrevive à viagem e contamina a memória (P1). Também resumo sem teto (11.029 chars) e cauda de latência de 94 s. Gerou o perfil `normal`.
3. **Real 100 turnos v2 (2026-08-12)**: 100/100 turnos. Falhou por 1 SLO error, um turno de 2.256 s (DeepSeek só devolveu timeout após 2.230 s, por suspensão do notebook) — origem do watchdog com prazo absoluto. Zero quests em 100 turnos, combate 45%, MiniMax 402 e Qwen 401. Gerou SPEC-120.
4. **Observabilidade 2026-08-13**: as métricas novas expuseram um **P0** — checkpoint gravado com combate ativo aprisiona o jogador no ciclo morte→restore (27 mortes). Também: origem sempre `player_provoked`, memória 27/27 especulativa, quest sem concluir. Gerou 5 specs (SPEC-101, 117, 113, 123, 112).
5. **Longrun real 2026-08-16**: `normal`/seed 46, 200/200, US$ 0,1378, p95 20 s. Falhou por 1 error de invariante. Checkpoint e origem passaram, mas dois `npc_claim` não entraram no ledger, a fuga deu falso positivo de `combat.no_progress`, e o combate ocupou 45%. Gerou 5 remediações (SPEC-114, 100, 119, 118, 121).
6. **Comerciante 2026-08-19 e 08-20**: 5×200 offline = 1.000/1.000, 36 transações. O 1×200 real (US$ 0,1629) achou 3 P1 e 3 P2: observação de mercado parseada como compra, NPC remoto como aliado, sinal visual errado ao vender. O preflight também achou o modelo Groq removido (`llama-3.3-70b-versatile` → `gpt-oss-120b`).
7. **Matriz A0 / A1 (2026-08-20)**: diagnóstico de capacidade, não baseline. A0 completou só 2 de 10 campanhas, e a A1 foi abortada com 707 falhas por quota. O resultado foi a regra **fail-closed** (secção 3.7).
8. **Matriz A (concluída 2026-08-27)** (`playtest-matriz-a-2026-08-27.md`): 10×200 = **2.000 turnos**, zero erro de turno, **12 violações `error`**, 193 warnings, 5.205 sucessos LLM em 5.224 tentativas, **US$ 1,46272**. Mostrou quatro recorrências de correções antigas incompletas (ciclo de vida de ação, resultado canônico, interações/progresso, structured output com evidência) e gerou SPEC-141, 142, 144 e 145. Destaques: 132 warnings no recrutador, 53 no secret_rusher e 7 `zero_vitality_outside_terminal` no combate.
9. **Matriz B (2026-09-27/28)** (`playtest-matriz-b-2026-09-28.md`): **1.951/2.000** turnos, DeepSeek `deepseek-v4-flash`, sem fallback. Campanhas 1–9 completas, zero erros, zero violações `error`, zero invocações terminais. A 10ª parou no turno 151 por HTTP 402 `Insufficient Balance`. O usuário dispensou a repetição e a SPEC-128 foi encerrada `done` com a limitação explícita. Custo estimado US$ 1,17628 e 4.201 requests. Achados: custo estimado subcontado, prefixo NPC duplicável e warnings de repetição ausentes do summary. A B comparada com a A (12 `error` → 0) é o resultado de qualidade mais forte do projeto.

Padrão recorrente que o processo extraiu: **cada playtest longo gera specs; cada spec gera invariantes ou testes curtos; a matriz B valida**. A estabilidade formal (0 violações) várias vezes escondeu defeitos que só a leitura do transcrito e as métricas novas (checkpoint, origem, ledger) revelaram.

---

## 10. Linha do tempo da evolução

Datas retiradas de `specs/index.yaml`, ESTADO_ATUAL e ROADMAP. O repositório tem 172 commits, e o primeiro commit do histórico é de 2025-12-13 (o motor MVP, anterior ao ciclo spec-driven).

| Data | Marco |
|---|---|
| 2025-12 a 2026-06 | MVP: grafo LangGraph multi-agente, RAG híbrido, saves, CLI e API; Fase 0 (mapa, relógio, viagem); frontend React (Fase 1); gameplay feedback de 2026-06-26 |
| 2026-07-02 | Specs 2.5, 2.5b, 2.6 e 2.7 (Mundo Vivo v1): Codex, event_log, projection, rules engine |
| 2026-07-03 | Fase 2.8 (context builder) e Fase 3 (crônica, conhecimento, quest log, visualização de estado) |
| 2026-07-04/05 | Fase 4 (7 specs), Fase 6 (conteúdo sistêmico) e Fase 7 (autoria e lint) |
| 2026-07-06 | Roteamento multi-provider (Groq grátis em todos os tiers), Fase 5 (harness, invariantes, telemetria), Fase 10 local, Fase 11, mapa de interiores, NPCs 3 camadas |
| 2026-07-13 | Ciclo de produto (balanceamento early-game, SSE streaming, polish de sessão); auditoria de segurança A1–A8; fix-playtest-achados |
| 2026-07-14/16 | DeepSeek vira primário em todos os tiers; playtest longo real; 8 specs `draft` |
| 2026-07-17/18 | Criação imersiva (onboarding e prólogo), 8 specs do playtest longo `done`, embeddings Jina |
| 2026-07-19 | Refatoração para 5 Posturas e árvore rica de 101 habilidades; revisão pós-épico (3 bugs de fiação) |
| 2026-07-20/21 | Sessão 22 (5 specs: agente curioso, aliados em combate, loot de exploração), sessão 23 (checkpoints de morte, letalidade v2) |
| 2026-07-23 a 08-02 | Épico Migração do Sistema de Conflitos (Valoria v2): conflito-01..17, cutover e volume de conteúdo (153 Cartas, 124 criaturas, 36 NPCs) |
| 2026-08-03 | Laboratório de combate, hardening do playtest (watchdog e manifesto v3), polish de prosa v2 |
| 2026-08-11/12 | Hardening de persistência e SSE (SPEC-086), Fase 8A de arte `done`, perfil `normal` |
| 2026-08-13/16 | Quatro ciclos de remediação de longrun (SPEC-100 a 123) |
| 2026-08-17 | Nove specs da Fase 10b e publicação do lote na main |
| 2026-08-19/20 | Fatia local da Fase 10b `done`, tiers 5+ (nível 20), Fase 8B, Crônica avançada, G0–G7 local certificada (readiness) |
| 2026-08-20 a 08-27 | Matriz A pareada (10×200), 2.000 turnos |
| 2026-09-17 | Fechamento local. Matriz B inicial parada em 751 turnos (HTTP 402) |
| 2026-09-19 | Remediação local pré-matriz (SPEC-162), 153 specs |
| 2026-09-22/26 | Auditoria de remediação, nove specs de execução e testes adversos |
| 2026-09-27 | SPEC-163: IDs estáveis SPEC-001..162; início do plano de evals v4 |
| 2026-09-28 | Matriz B real (1.951/2.000) e SPEC-164 a 168 (AGENTS.md, governança, Project Index, harness) |
| 2026-09-29/30 | SPEC-169 a 174 (routing, memory, narrative/NPC, frontend F01–F16, CI gates, baseline v1) |
| 2026-10-01 | SPEC-175: benchmark A/B do Project Index (v6): índice retirado do fluxo padrão. Plano de evals v4 concluído |
| 2026-10-02 | SPEC-176 (integridade LF/CRLF) `review-pending`; pacote v5 importado (SPEC-176 a 198, monetização, hosted, mobile) |

---

## 11. Observações críticas

1. **Defasagem de documentação**: CLAUDE.md diz "13 perfis", mas o código tem 14 (`profiles.py:1266`). O ESTADO_ATUAL carrega dezenas de blocos históricos, e o próprio texto avisa que o bloco do topo prevalece.
2. **Custo é estimado, não medido**: `pricing.py` usa tokens fixos por invoke. A matriz B registrou subcontagem. Ainda não há medição real de uso (a SPEC-182 `real-usage-metering` está `approved`).
3. **O LLM-as-judge está desligado como gate** por desenho. Persona e prosa não têm oráculo bloqueante. A qualidade de prosa é julgada à mão via `playtest transcript`.
4. **Holdout privado não é verificável aqui**: está em repo separado. Sem ele, os scores dos evals são de desenvolvimento.
5. **Baseline v1 incompatível com a régua atual** (hashes CRLF, SPEC-176). É preciso uma nova baseline antes de qualquer comparação A/B de produto.
6. **Cobertura de infra real**: 35 skipped e 15 deselected dependem de opt-in (Postgres/Auth/browser/LLM). A cloud (Railway/Supabase remoto) nunca foi certificada (SPEC-104 `draft`).
7. **Fase 9 (sprites e som)** continua sem spec aprovada.
8. **Pacote SPEC-177 a 198 inteiro `approved` mas não iniciado** (SPEC-177 "não iniciou"). Cobre o salto de laboratório para produto pago: Stripe, Google Play, Capacitor, carteira e FinOps. Depende do push, do approval humano e do CI verde da SPEC-176.
