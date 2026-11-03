# SPEC-380 — revisão independente (spec `draft`, antes de aprovar)

> **Veredito:** `SAFE-WITH-CHANGES` (no template: `CHANGES_REQUIRED` no texto da spec antes de virar `approved`)
> **Revisor:** Opus (`spec-reviewer`, contexto independente; não escrevi a spec) · **Data:** 2026-11-03 · **Commit revisado:** `2a6e0945` (main; durante a revisão a main andou de `b278f6af` para `2a6e0945` por outra sessão)

## Escopo

Só o texto de `specs/SPEC-380-evals-vivos-baseline-cartas.md`, conferido contra o source: `evals/__main__.py`,
`evals/core/{compare,governance,runner,hashing,schemas,adapters}.py`, `evals/evaluators/projection.py`,
`evals/metrics-registry.yaml`, `evals/manifest.lock.json`, `evals/protected-paths.txt`, `.github/workflows/eval-gates.yml`,
`eval-protected.yml`, `tests/test_ci_eval_gates.py`, `tests/test_workflows_contract.py`, `tests/test_ci_docs_only.py`,
`tests/test_eval_encounter_manifest.py`, `tests/spec330_equivalence.py`, `tests/test_playtest_real.py`,
`playtest/__main__.py`, `playtest/pricing.py`, `rag.py`, `.pre-commit-config.yaml`, `.gitattributes`, contrato 08 e política 12.
Nada de produto ou eval foi editado. Nenhum LLM real foi chamado.

## Fatos [F]/[H] da spec: conferência

| Alegação da spec | Resultado |
|---|---|
| `compare` sai 1 em regressão (`__main__.py:86`) e 2 em baseline incompatível (`:87-89`) | **Confere.** Detalhe: baseline **ausente** também sai 2 (`load_run` → `GovernanceError`, `runner.py:581-585`), não traceback. `compare` também reprova se o run atual não passou (`compare.py:58-59`). |
| `assert_baseline_compatible` em `governance.py:127-149`, `platform` em `:145` | **Confere.** |
| `run` reprova qualquer caso que falha (`runner.py:523`) | **Confere** (sai 1, `__main__.py:78`). |
| Baseline local de 30/09, `evaluator_version 1.6.0`, `windows-py3.13.14`, `evals/runs/` no `.gitignore:16` | **Confere.** |
| 15 caminhos protegidos | **Confere** (`protected-paths.txt:2-16`). |
| `platform` com patch do Python (`runner.py:442`) | **Confere**: `f"{system}-py{python_version()}"`. Baseline de outro patch ou de outro SO ⇒ `compare` sai 2. |
| CI proíbe `--real` no `eval-gates.yml` (`test_ci_eval_gates.py:105`) | **Confere.** |
| 281 casos / 11 datasets / 12 suítes no CI | **Confere.** |
| Datasets sem commit desde 19/10 [H] | **Confirmado:** `git log -1 --format=%cs -- evals/datasets/regression` = 2026-10-19. |
| R2.6 [H] "runner exige métrica por suíte?" | **Não exige.** Métrica é agregada por **oráculo**, não por suíte (`runner.py:75-115`): casos `projection` entram em `state_transition_pass_rate`. `cards_combat_pass_rate`, `evaluator_version` novo e mudança no registry **não são necessários**. Subir a versão quebraria `tests/test_ci_eval_gates.py:133` (`== "1.15.0"` fixo). |
| §3.2 [H] "`run_round` lê flags `RPG_*`?" | **Confirmado.** `RPG_ENEMY_INTENT` (`enemy_intent.py:44`), `RPG_CARD_DECK`, `RPG_ENEMY_DECKS` (`conflict_orchestrator.py:150,2567`) e `RPG_RUNTIME_PROFILE` (`card_effects.py:806`). O runner só fixa `RPG_FORCE_MOCK` (`runner.py:464-506`). Fixar as flags no adapter passa a ser **obrigatório**. |
| §3.3 [H] `JINA_API_KEY` necessário? | **Necessário de fato.** `faiss_lore_index/embeddings_meta.json` = `jina`, e o índice fica preso ao provider que o gerou (`rag.py:8-13`). Sem a chave, o RAG de lore fica **desligado com aviso**: a medição sai degradada sem falhar. |
| §3.3 [H] a telemetria estima custo do DeepSeek? | **Sim.** `playtest/pricing.py:31`: `deepseek-v4-flash` a US$ 0,14/0,28 por M. O teto `--max-cost` vale. |
| R3.2 a CLI tem `--max-requests`/`--max-cost` | **Confere** (`playtest/__main__.py:430-435`; `--max-cost` default 0 = desligado). |
| R2.7 `python -m evals.core.governance lock --root .` | **Errado.** Sem `--dataset`, `build_lock` aborta com "at least one public dev/regression dataset is required" (`governance.py:222-223`, `main` `:291`). É preciso passar os 12 `--dataset`. |
| R2.4 "erro/acerto/crítico pelas seeds 2/13/21 do golden 330" via `resolve_card` | **Errado.** O golden 330 é gerado por `conflict_turn.resolve_turn` mais a reação do orquestrador, com `random.seed` **global** e cena montada (`tests/spec330_equivalence.py:74-135`). `card_effects.resolve_card` é "SEM rolagem" (`card_effects.py:1085-1087`). Pela tabela §3.2 não dá para reproduzir erro/acerto/crítico. |

## Estabilidade da baseline (pergunta 2)

Rodei `evals run --suite state_rules --suite encounter_manifest` 2× (saída na scratchpad) e depois `compare` entre os dois runs: **exit 0**.
Entre os dois runs só mudaram `run_id`, `started_at`, `duration_ms` e `product_sha`. Nenhum desses campos entra em
`assert_baseline_compatible` nem nas métricas. `metric_values` deu idêntico. O arquivo não é byte-estável, mas o `compare` é estável.
Os hashes são de bytes, e `.gitattributes` força LF em `*.py/*.json/*.jsonl/*.yaml`, então checkout Windows × ubuntu não gera ruído.
**O ruído real é de plataforma:** a baseline do CI (`linux-py3.13.N`) é **incompatível por construção** com qualquer run local Windows (`windows-py3.13.14`).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | spec §3.1 passo 3, R1.1; `.pre-commit-config.yaml:18-19` | Rodei as 12 suítes do CI localmente: o run inteiro dá **688 KB**. O hook `check-added-large-files --maxkb=500` recusa o commit B. Toda regeneração esbarra nele. | Decidir na spec: (a) `exclude: ^evals/baselines/` no hook (arquivo não protegido, commit separado, fora do lote protegido) ou (b) medir o tamanho real do artefato do CI na Etapa 0 e documentar. Não "emagrecer" o JSON à mão: R1.1 manda copiar sem editar. |
| P1-2 | P1 | spec R2.1/R2.4, tabela §3.2 | A operação `resolve_card` não rola dados, então os 6 casos de dano "erro/acerto/crítico seeds 2/13/21" não têm caminho. O cenário do golden 330 (atores, Mira, `random.seed(11 if seed==7 else seed)`, `ct.resolve_turn`) não está descrito. | Nova operação `resolve_turn` (`services.conflict_turn.resolve_turn`) que reproduz **literalmente** o cenário de `tests/spec330_equivalence.py:74-135`, com o `random` global semeado e restaurado pelo adapter. Ou trocar a fonte desses casos por asserts numéricos explícitos de `tests/test_conflito_dano.py`. Dizer qual vale. |
| P1-3 | P1 | spec R2.3 | O golden 330 guarda **sha opaco + logs em texto** (`spec330_legacy_golden.json:2-35`). Vitalidade e dano só aparecem dentro de strings ("dano 6×2=12; Vitalidade 10 -> 0"). Tirar daí o `expected` estruturado é interpretar log, ou seja, a saída capturada de um motor, e isso fica na fronteira da proibição de R2.2/R2.3. | Regra explícita: fonte válida = `assert` numérico em pytest (citar função) **ou** o campo `res` do golden. Número tirado de log do golden só com a string exata citada em `description`. Revisor Astra confere 100 % dos casos vindos do golden, não só uma amostra de 5. |
| P1-4 | P1 | spec R2.8 | Falta o par known-bad exigido pelo contrato 08 ("cada evaluator deve ter testes próprios com known-good e known-bad") e pelo precedente `tests/test_eval_encounter_manifest.py:63,83`. | R2.8 += `test_adapter_reports_a_regression_instead_of_hiding_it` (actual adulterado ⇒ caso reprova) e `test_adapter_fails_closed_on_unknown_operation`, além de ≥ 2 casos `known-bad` no dataset. |
| P1-5 | P1 | spec "Desbloqueia", §7 | "375–385 passam a comparar contra um arquivo" é falso localmente: o W2 roda no Windows e a baseline do CI sai **2** por `platform`. | Reescrever: a baseline versionada só vale no CI. O W2 local continua A/B na mesma máquina. Avisar no README/SKILL para ninguém "consertar" o exit 2 local. |
| P2-1 | P2 | spec Depende de, R2.4 Presságio | A branch `spec-371` (draft) mexe em `services/enemy_intent.py` (+17) e em Cartas de postura `reacao_inicial`. A 368 já tem código na `main`, mas está `in-progress`. Cartas de conteúdo (balanço 362/371) mudam com frequência; caso preso a `card_id` vira trava de eval a cada ajuste de número. | Acrescentar 371 nas dependências dos casos de Presságio. Preferir **Carta inline no `input`** (dict de efeito) para semântica de motor, e `card_id` só para Cartas fora da esteira de balanço (critério na spec). |
| P2-2 | P2 | spec §3.2, [H] flags | Fixar flags é obrigatório (ver fatos). | Tornar R2: `input.flags` obrigatório em toda operação, com as 4 flags (`RPG_ENEMY_INTENT`, `RPG_CARD_DECK`, `RPG_ENEMY_DECKS`, `RPG_RUNTIME_PROFILE`); o adapter recusa (`AdapterError`) se faltar. Restaurar o env no `finally`. |
| P2-3 | P2 | spec R2.6, R2.7 | Métrica nova e bump de versão desnecessários; bump quebra `test_ci_eval_gates.py:133`. Comando de lock incompleto. | Remover o ramo "se [H]" de R2.6; corrigir R2.7 para `lock --root . --dataset evals/datasets/regression/<cada>.jsonl` (12×). |
| P2-4 | P2 | spec R3/§3.3 | Workflow novo precisa passar `tests/test_workflows_contract.py` (`permissions` no topo, actions pinadas por SHA com `# vN`) e `test_ci_docs_only.py:107-111` (sem `ubuntu-latest`). Sem `RPG_NO_MOCK=1`, chave ausente cai no MockLLM em vez de falhar. Sem `JINA_API_KEY`, medição degradada sem aviso. | R3 += `permissions: contents: read`, pins por SHA, `env: RPG_NO_MOCK: "1"`. `JINA_API_KEY` vira secret **obrigatório** (passo `test -n`), como `eval-protected.yml:34`. O `report` acha o `run_id` pelo diretório novo em `playtest_runs/`, não por parse de stdout. |
| P2-5 | P2 | spec R3.2 | `--max-requests 60` com 5 turnos: o teste vital usa `turns*10` = 50 (`test_playtest_real.py:59`). Não está medido se criação de ficha e campaign_manager cabem nisso. Aborto por teto só aparece no smoke. | Ok manter; registrar na Etapa 0 a contagem de invokes de 1 turno com `--real` no smoke §6. Aborto por teto não reprova o job (R3.3 já cobre). |
| P2-6 | P2 | spec R1.5, `eval-gates.yml:70` | `test_eval_baseline.py` só roda no `validate.yml`. | Incluir o teste no passo `pytest` do job `deterministic-evals`, para o erro sair junto do `compare`. |
| P2-7 | P2 | `compare.py:54-57` | `after_baseline` não tem catraca: uma melhora não sobe a régua, e uma regressão de volta ao nível antigo passa. | Só documentar em §7. Regenerar a baseline depois de melhora é opcional, via eval authoring. |
| P2-8 | P2 | spec R1.4 | O input `python-version` do `setup-uv@v10` é [H]: não confirmei offline. A versão do uv não está pinada; com o Python fixado, `platform` fica estável mesmo assim. | Etapa 0: confirmar o input no README da action no SHA pinado. Alternativa: `UV_PYTHON: 3.13.N` no `env` do job. |

## Riscos e governança (perguntas 3–5)

- **Governança:** o dataset novo não quebra `test_eval_governance.py`/`test_eval_harness.py`: eles leem só `governance.jsonl`/`harness.jsonl`, e `suite` é `str` livre (`schemas.py:40`). Adapter em `evals/core/adapters.py` muda `ruler_sources` ⇒ relock. `evals/core` está protegido ⇒ `scope.protected=true` ⇒ o job `eval-governance` pede aprovação. O `/eval-publish` cobre (lote sem produto, `eval_publish.py`).
- **Fluxo A/B da baseline:** coerente. Commit A sai 2 (baseline ausente ou stale) e commit B sai 0. Os dois vão no mesmo lote e numa aprovação só. Na janela A→B, o pytest completo local fica vermelho por R1.5; não pousar A sozinho.
- **Contrato 08 / decisões do dono:** sem contradição. Autor de eval (Sol≡Opus) não toca produto. Revisão Astra em outro contexto. 5 turnos não é long-run, e o `schedule` só liga por D1. Não muda expected junto com implementação. A tabela R4 é coerente com `.claude/agents/*.md`. Observação: o subagente `spec-executor` é Sonnet, então o executor desta spec precisa de `model: opus` explícito (memória do dono "modelo-criativo-opus").
- **Workflow semanal e ruído:** R3.3 só reprova medição inválida, o que é bom. Com DeepSeek sem saldo e Groq em 429, todos os perfis ficam sem provider e o job fica vermelho. Isso é sinal real, não ruído. O environment `eval-provider` existe, mas só tem `GOOGLE_API_KEY` (`eval-protected.yml:24-37`); concordo com D2 = environment novo sem revisores.
- **W1 (rodada 2×, de novo agora):** a única interseção é `evals/protected-paths.txt`, com `spec-370` e `spec-374`, como a spec já declara. A branch `spec-371` não colide com os arquivos da spec, mas colide com o **comportamento** coberto (P2-1).

## Pendências

Mudanças objetivas no texto, antes do `approved`: P1-1…P1-5 e P2-2/P2-3/P2-4. As demais P2 podem virar nota em §7.

## Comandos rodados

```text
W1 (laço §6.2 com os 17 arquivos de §3 + schemas) → interseção: evals/protected-paths.txt (spec-370, spec-374)
uv run --frozen python -m evals run --suite state_rules --suite encounter_manifest (2×, scratchpad) → exit 0 / exit 0
uv run --frozen python -m evals compare --current r2 --baseline r1 → exit 0, regressions []
uv run --frozen python -m evals run (12 suítes do CI, scratchpad) → exit 0, full.json = 688.309 bytes
git log -1 --format=%cs -- evals/datasets/regression → 2026-10-19
leitura: compare.py, governance.py:110-290, runner.py:400-585, hashing.py, schemas.py, projection.py, spec330_equivalence.py:74-135, rag.py:8-13, pricing.py:31
```
