# SPEC-376 — revisão independente (spec `draft`, antes da execução)

> **Veredito:** `CHANGES_REQUIRED` — na escala pedida pelo coordenador: **SAFE-WITH-CHANGES**.
> A estrutura de proteção da spec é boa (Etapa 0 antes de apagar, W1 por etapa, R3, R23, exceção de teste
> explícita). Mas a Etapa 0 **como está escrita** pode gravar no checkout principal e mede a coisa errada
> nos geradores de Cartas e classes. As duas falhas se corrigem no texto, sem mudar o escopo.
> **Revisor:** Opus (spec-reviewer, adversarial) · **Data:** 2026-11-03 · **Commit revisado:** `main` em `b278f6af`
> (a spec cita `5fd2e920`; a `main` andou com commits da SPEC-367 feitos direto nela).

## Escopo

Revisei `specs/SPEC-376-refactor-fonte-cartas-e-poda-morta.md` (draft) contra o source, os branches abertos,
as SPEC-272, 273, 302, 313, 339, 377, 378, 379, 384 e a auditoria ponytail de 18/10 § "Não podar". Fora do
escopo: o código da implementação (ainda não existe). Não rodei nenhum gerador, nem o `ruff_baseline.py`
(até o `--check` reescreve `ruff-baseline.toml` por um instante, `scripts/dev/ruff_baseline.py:40-54`).

## Veredito por requisito/etapa

| Req/Etapa | Veredito | Evidência | Mudança exigida |
|---|---|---|---|
| R1 (W1) | OK, com furo | W1 rodada agora: só `docs/guias/AUTORIA.md` cruza (spec-374, +3/−1). A SPEC-367 commita **direto na `main`** (`b278f6af`, `4b03a430`), sem branch, e a W1 não enxerga isso | Além da W1, antes de cada etapa: `git log --since=<início da etapa> main -- <arquivos>` e `git status --porcelain -- <arquivos>` no checkout principal. A3 **espera** a 374 hoje |
| R5 (Etapa 0) | **UNSAFE como escrito** | `scripts/dev/env.sh:6,17` faz `RPG_ROOT="$(git rev-parse --show-toplevel)"` e `cd` para lá. O `RPG_ROOT` que vem de fora é **sobrescrito** (sonda: `RPG_ROOT=/c/nonexistent_wt bash scripts/dev/py.sh -c …` → `RPG_ROOT= C:/…/rpg-ia-master`). O destino da escrita é o toplevel do **cwd**, e o cwd de subagente volta para o checkout principal a cada chamada de Bash | Ver P0-1 |
| R6 (veredito da deriva) | **Metodologia errada** | `gen_tiers_5_plus.py:248-288` carimba `tier`/`level_req`/`apex` em toda Carta de classe sem `onda` e grava `late_entropy_curve`/`playstyle`/`tradeoff`/`preview_card_ids` em `classes.json`. Esses 7 campos estão na lista mínima do R6 como "removidos". Medir `gen_cards_v4` sozinho repete o erro que a SPEC-273 §8 pegou | Ver P1-1 |
| R7 | OK | `git grep`: nenhum import de `gen_cards_v4`/`gen_classes_v2`. Os únicos hits vivos são `_meta` dos 5 JSON, o docstring do teste e o `project_index/` (gerado no pouso) | Citar o `project_index/` como hit esperado no R3 |
| R8 | OK | `CARTAS.md:4-7,103-113` e `CLASSES.md:132` conferem. As esteiras `scripts/cards/{draft,lint,sim,promote}.py` existem | O `test_docs_nao_mandam…` precisa de critério exato (P2-1) |
| R9, R12 | OK | `gen_tiers_5_plus.py:233-311`: o default é check | — |
| R10/A4 | OK | O `motor_hash` inclui `data/cards/**/*.json` (`docs/spec358/gerar_golden_v1.py:84-95`) | A trava "espera 368" está velha: a 368 já pousou (`dff4c27c`, `061c330b`). Trocar por "espera a 367 (que commita na `main`) e a 369 (`draft`)" |
| R11/A5 | OK, com fato errado | O [H] "testes usam só constantes" é **falso**: `tests/test_spec295_chefe_no_topo.py:87-88` chama `gen.migrate_creature` (idempotência). A D3 só mexe em `main()`, então continua seguro | Corrigir o texto. Exigir que a A5 não mude `migrate_creature` nem as constantes, e atualizar a linha "Uso:" do docstring (`:15`) |
| R13–R14 (B) | OK | B1: sem refs vivas. As specs de origem estão `done` (236 em 23/10, 279, 217). `spec236-s62-plano.md` é plano do dia 2, já executado. `ruff-baseline.toml:82-83` confere | Ver P2-2 (regerar a baseline inteira absorve dívida nova de outros arquivos) |
| R15–R16 | OK | — | — |
| R17 (C1) | OK | `combat_mechanics.py:535-579` confere; `HANDLED_KINDS` e as tabelas ficam. Os únicos usos são `test_mvp.py:339` e `test_cutover_audit.py:29`. A SPEC-339:94 só cita o caminho legado, não manda manter. A allowlist de `except` silencioso não tem entrada nos arquivos de C | — |
| R18 | OK | A SPEC-313:382 (design) previa o `event_processor` chamando `escort_stop`, mas o R22 (`:829-831`) reverteu isso. 0 refs, incluindo os branches abertos | — |
| R19 (D6) | OK | 0 refs em código, testes, branches 370–374/359 e handoffs. **Choque:** a SPEC-377 item 1 edita `services/world_engine.py:729-738` | Registrar a ordem 376-C2 ↔ 377-item1 (W6 já serializa, mas as linhas citadas mudam) |
| R20, R21 | OK | 0 refs, incluindo strings e `monkeypatch`. A SPEC-378:203 deixa `_infer_tier_from_name` e os fallbacks `ImportError` de fora explicitamente, então não há sobreposição | Colocar na 378 uma nota "feito pela 376" (coordenador) |
| R22 | OK, com contagem errada | Os `setattr(npc, "RAG_AVAILABLE", …)` são **8 linhas em 7 arquivos**, não 10. Os outros 4 são em `cb` (`context_builder`, fora do escopo). Nenhum teste faz `setattr` em `world_simulator.RAG_AVAILABLE` | Listar os 7 arquivos explicitamente na C4 |
| R23 | Fraco (P1-2) | A matriz "0 erro antes e depois" **não** prova a ausência de ciclo **antes**: se houvesse ciclo, o stub o engoliria em silêncio e o "antes" daria 0 erro do mesmo jeito. Sonda feita hoje: em 4 ordens (`∅`, `rag`, `main`, `api` primeiro), `npc.RAG_AVAILABLE`/`world_simulator.RAG_AVAILABLE` são `True` e `query_rag`/`add_memory_to_session`/`find_existing_entity` são **os mesmos objetos** do `rag`/`librarian` | Acrescentar à matriz as asserções de identidade (P1-2) |
| R24–R26, W2 | OK | As 12 suítes de `eval-gates.yml:72-79` conferem; `--seed`/`--current`/`--baseline` existem (`evals/__main__.py:25-31`); `playtest --seed` também (`playtest/__main__.py:416`). Os digests congelados `_source()` de `evals/experiments/jev_router_hybrid.py:519` e `spec238_loot.py:354` não incluem nenhum símbolo da 376 | — |
| C5 | OK (opcional) | A condição "espera a 368" já foi cumprida | Atualizar o texto |
| §5/§6 | OK | — | — |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | spec R5 itens 1–4; §7 "O próprio teste de deriva…"; `scripts/dev/env.sh:6,17` | `RPG_ROOT=.` não protege nada: o `env.sh` o troca pelo toplevel do cwd. Basta um comando do executor sem `cd` (o cwd do subagente é resetado para o checkout principal) para o `gen_classes_v2` (que grava **ao importar**, `:1605-1608`) e o `gen_cards_v4` sobrescreverem `data/classes.json`, recriarem `data/player_abilities.json` e regravarem 6 JSON de Cartas **no checkout principal**, onde a sessão da SPEC-367 trabalha agora. O "assert de `git status`" só detecta depois do estrago | Reescrever o R5 assim. (a) Não usar `py.sh` nem worktree git: copiar `data/` para um diretório temporário fora de qualquer repo (`$TMP/deriva/data`) e rodar `"$MAIN/.venv/Scripts/python.exe" -I <cópia do script>` com `cwd=$TMP/deriva` e `RPG_ROOT=$TMP/deriva`. Os dois geradores só usam `json`/`os`. O `gen_tiers` usa `Path(__file__).parents[1]`, então a cópia do script tem que ficar em `$TMP/deriva/scripts/`. Comparar com `git diff --no-index`. (b) Se o worktree descartável for mantido: todo comando é `cd "$WT" && test "$(git rev-parse --show-toplevel)" = "$WT" && …` numa **única** chamada de Bash, e a doc deixa de dizer que `RPG_ROOT` protege. (c) Snapshot de `git status --porcelain -- data/` e `git stash list` do checkout principal **antes**, comparado depois |
| P1-1 | P1 | spec R5/R6; SPEC-273 §8 achado 1; `scripts/gen_tiers_5_plus.py:248-288` | A pipeline documentada é `gen_classes_v2 → gen_cards_v4 → gen_tiers_5_plus --write`. Medir cada gerador sozinho conta como "removidos" `tier`, `level_req`, `apex`, `late_entropy_curve`, `playstyle`, `tradeoff` e `preview_card_ids`, que o terceiro passo devolve. É o mesmo erro que tornou a SPEC-273 UNSAFE. O veredito "sai" provavelmente continua certo: `momento` (30–31 por classe, curado na SPEC-335, `2c68e2cf`), `raridade` e `player_abilities.json` não voltam. Mas a evidência tem que ser a da pipeline | O R5 mede **(i)** cada gerador sozinho **e (ii)** a cadeia completa, na ordem, no diretório temporário, incluindo `gen_tiers --write` **só** ali. O R6 decide pelo resultado da cadeia (ii): campo que a cadeia devolve não conta como destrutivo. A lista mínima separa os campos "da cadeia" dos campos "curados fora da cadeia" |
| P1-2 | P1 | spec R23 | A matriz de import não detecta um ciclo que o stub já mascara hoje | Em cada ordem, assertar `npc.RAG_AVAILABLE is True`, `world_simulator.RAG_AVAILABLE is True`, `npc.query_rag is rag.query_rag`, `bestiary.query_rag is rag.query_rag`, `world_simulator.add_memory_to_session is rag.add_memory_to_session` e `npc.find_existing_entity is agents.librarian.find_existing_entity`. Ordens: `∅`, `rag`, `main`, `api`, `agents.librarian` primeiro. Rodar com `RPG_FORCE_MOCK=1`. Resultado de hoje: todas `True` |
| P1-3 | P1 | spec R1/§4; W1 da auditoria §6.2 | A W1 só vê branches. A 367 commita direto na `main`, e a `main` andou durante esta revisão. A W1 também não vê mudança não commitada em worktree alheio. Além disso, `spec-349-pre-sync` (401 arquivos, 30 h sem commit) polui a lista travada | Acrescentar ao R1: `git log --oneline <sha do início>..main -- <arquivos>` vazio e `git status --porcelain -- <arquivos>` vazio no principal e nos worktrees (`git -C <wt> status`). Registrar `spec-349-pre-sync` como branch morto (decisão do coordenador) |
| P2-1 | P2 | spec §3 `test_docs_nao_mandam…`; R8 | O R8 manda escrever em `CLASSES.md` "o gerador foi removido pela SPEC-376", que contém o nome `gen_classes_v2.py`. Um teste de `not in` puro fica vermelho, e o critério "como passo a rodar" é subjetivo | Definir a asserção: não existe linha com `python scripts/gen_cards_v4.py`/`gen_classes_v2.py` (regex `python\S*\s+scripts/gen_(cards_v4\|classes_v2)\.py`) nem link `](../../scripts/gen_…)` |
| P2-2 | P2 | spec R14/B1; `scripts/dev/ruff_baseline.py:39-61` | Regerar a baseline inteira absorve em silêncio qualquer dívida de lint nova que a `main` tenha ganhado de outra sessão | Exigir que `git diff ruff-baseline.toml` seja **só** as linhas dos scripts apagados. Se vier qualquer outra linha, parar e reportar |
| P2-3 | P2 | spec R11 [H]; R22 | Fatos errados: (a) a 295 chama `migrate_creature`; (b) "10 testes" de `RAG_AVAILABLE` no `npc` são 8 linhas em 7 arquivos; (c) o cabeçalho "espera 368 pousar" está velho | Corrigir o texto |
| P2-4 | P2 | spec R5 (rodar testes no descartável depois de 1 e 2) | Com o diretório temporário do P0-1, os testes não rodam lá | Trocar por: copiar `data/` gerado para dentro de um worktree descartável (só leitura do principal) **ou** registrar quais asserções dependem dos campos perdidos, por leitura (`test_cutover_audit.py:78`, `test_conflito_autoria_cartas.py`) |

## Consumidores escondidos procurados

Procurei em `git grep` no repo inteiro (incluindo os 24 arquivos de `.claude/`/`.github/`), nos diffs
`main...` de todos os 18 branches à frente, em `evals/` (incluindo os digests `_source()`), em `playtest/`,
em `config/` e nos scanners AST de testes (`silent_except_scan`, `test_no_print_in_production`,
`test_session_hardening`, `test_spec352_creature_portraits`):

- **Nenhum consumidor novo** dos símbolos de C, dos geradores nem dos scripts de B1.
- `project_index/` cita os geradores. É regenerado no `wt.sh sync`, então não bloqueia.
- `tests/test_spec295_chefe_no_topo.py:87-88` chama `migrate_creature`. Não bloqueia a D3.
- `tests/data/silent_except_allowlist.txt` (só encolhe; entrada sobrando falha) não tem chave em nenhum
  arquivo de C.

## Choques com outras specs

- **377 item 1** edita `services/world_engine.py` (mesmo arquivo da C2). A W6 serializa, mas as linhas mudam.
- **378** deixa `_infer_tier_from_name` e os stubs `ImportError` explicitamente fora. Não há choque; falta
  registrar lá que a 376 é a dona.
- **379** reescreve fakes em `test_mvp.py`, e a C1 apaga um teste de lá. A W6 ordena (376 antes).
- **381/384** regeneram `ruff-baseline.toml`. Ver P2-2.
- **374** trava `docs/guias/AUTORIA.md` agora (A3 espera).

## Pendências

Depois das correções P0-1, P1-1, P1-2 e P1-3 no texto da spec, ela fica SAFE para a Etapa 0.
Não é preciso uma nova revisão completa: basta o coordenador conferir o diff da spec.

## Comandos rodados

```text
W1 (auditoria §6.2) em 18 branches → 557 arquivos; ∩ arquivos da 376 = docs/guias/AUTORIA.md (spec-374)
git diff main...{spec-359,370,371,374} | grep +símbolos apagados → 0
RPG_ROOT=/c/nonexistent_wt bash scripts/dev/py.sh -c 'print(os.environ[RPG_ROOT])' → toplevel do cwd (sobrescrito)
uv run --frozen python -c "import <m>" (9 combinações) → 0 erro
identidade stub×real em 4 ordens de import → todas True (stubs nunca usados hoje)
pytest -n 0 test_cutover_audit, test_mvp::test_condition_tick…, test_spec295_chefe_no_topo, test_no_silent_except → 32 passed
```
