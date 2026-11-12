# SPEC-417 — revisão terra (review)

> **Veredito:** APPROVED_WITH_FOLLOWUPS
> **Revisor:** Sonnet (terra) · **Data:** 2026-11-12 · **Commit revisado:** `1a2bb9f3`

## Escopo

Branch `spec-417` sobre a `main` `c3346c1a` (14 arquivos, +1114): `scripts/dev/weak_tests.py`, ligação ao `land_check` (check `weak-tests`), `tests/fakes/property_settings.py`, `tests/test_mechanics_properties.py`, `tests/test_persistence_properties.py`, `pyproject.toml`/`uv.lock`, guia. Fora: suíte completa (coordenador); nenhum arquivo de produto foi tocado (conferido).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/dev/weak_tests.py:83-90`, `:125-135` | Falso negativo de pulo por nome: `import pytest as pt` (`@pt.mark.skip`, `pt.skip()`), `from pytest import skip`/`xfail`, `from pytest import mark as m`, `unittest.skip`, `pytestmark: list = [...]` (AnnAssign) e marca guardada em variável (`slow = pytest.mark.skip; @slow`) dão `marks() == []` (provado por sonda AST). Só `from pytest import mark` é tratado. O repo não usa essas formas hoje; o risco é um executor que as escolha. | Resolver aliases a partir de `Import`/`ImportFrom` (nome local -> `pytest.*`) antes de `_dotted`; tratar `AnnAssign` de `pytestmark`; cobrir `unittest.skip*`/`expectedFailure`. |
| P2-2 | P2 | `scripts/dev/weak_tests.py:157-164` | "Linha na spec que justifica" = substring do nome do teste + qualquer uma de `skip/skipif/xfail/importorskip` na mesma linha: `test_a` casa `test_abc`, e "nunca usar skip em test_a" justifica. Qualquer menção solta basta. | Exigir token inteiro (`\bnome\b`) e a palavra da própria marca (`m.kind`). |
| P2-3 | P2 | `scripts/dev/weak_tests.py:27,170-196,221-233` | `_RAISES_CALLS` casa só pelo nome: `foo.fail()` conta como asserção; `class T(unittest.TestCase)` e classes sem prefixo `Test` não entram em `test_functions`; `_verify(...)` perde o `_` e não casa `verify_`; se o arquivo ANTIGO não parseia, o arquivo inteiro vira só `INFO` (bypass). (`assert x == x`, `assert mock.called` contarem como assert está declarado fora de escopo na spec.) | Restringir `fail`/`raises` a `pytest.*`; tratar `TestCase`; não pular o lado novo quando só o antigo falha no parse. |
| P2-4 | P2 | `tests/test_persistence_properties.py:80-81` | RT1 só checa chaves EXTRAS em `player`/`world` (`set(p1) - set(p0)`), não chaves PERDIDAS: campo do `player` ou `world` que o save descarte passa. RT2 só pega se o descarte não for estável. | Acrescentar `set(p0) - set(p1)` vazio (ou lista explícita) para `player` e `world`. |
| P2-5 | P2 | `tests/test_mechanics_properties.py:179-184` | P4(a) não afirma `gold_delta == -price(...)*qty` (a R12 pedia) nem o decremento do estoque na compra. A mutação de sinal é pega pela conservação de ouro, preço errado na compra não. P5 não monta keeper/patente (limite declarado na docstring e em §9; aceito). | Acrescentar a igualdade com `economy.price`; keeper/patente em follow-up. |

Sem P0/P1.

### Achado de produto (item 4; não consertado)

Bug real, não artefato do gerador. `execute_trade` faz `world = dict(state["world"])` (cópia rasa, `services/economy.py:786`); `_ensure_stock` devolve `world["merchant_stocks"][mid]` que, com a loja já visitada, é o mesmo dict do `state` de entrada; `economy.py:812` decrementa nele (a venda de item único em `:876` também). Impacto: o estoque do mercador é gasto no estado do chamador mesmo que a troca seja descartada ou repetida (retry de turno), então o jogador vê estoque sumir sem compra efetivada.

### Respostas aos itens pedidos

1. `weak_tests.py`: falsos negativos em P2-1/P2-3. Sem falso positivo achado (helper local com assert, `pytest.raises`, `check_*`, `assert_*`, `fuzz_operation` passam; parametrizado sem assert é FAIL corretamente; fixture ignorada). O relatório `assert-delta` sai como `INFO`, sem bloquear (R6).
2. `land_check`: `check_weak_tests` roda o script irmão; rc != 0 (inclusive exceção ou git ausente) vira `FAIL`; `SKIPPABLE = {ram, ci}`, então `RPG_LAND_SKIP=weak-tests` é recusado com rc 2. OK.
3. Propriedades: P1/P2/P3 usam limites e invariantes, não a fórmula do produto; P3 troca `weather_effects` para cobrir os dois ramos. Perfil igual ao `fuzz_settings` (`derandomize`, `database=None`, `deadline=None`, mesmos 3 health checks). Bordas: ouro e vitalidade 0, vitalidade = máximo, `integridade_max=0`, unicode e 65-100 ids; sem ouro negativo (domínio da spec). Mutações reproduzidas por mim, cada uma falhou e foi desfeita (`git status` limpo): P3 (`world_utils.py:281`), P4b (`economy.py:856`), P2b (`conflict_damage.py:283`), RT1 (`persistence.py:674`; o shrinking levou 142 s, custo só quando falha).
5. `uv.lock`: +2 linhas (aresta no grupo `dev` e `specifier`), sem troca de versão; `requirements.txt` sem diff; `test_spec192_vercel_packaging.py` verde.
6. Tempo: 5 arquivos (dois de propriedade, `test_weak_tests`, `test_land_check`, `test_spec192_vercel_packaging`) = 60 passed, 1 xfailed em 9,5 s (`-n 2`).
- `weak_tests.py --spec 417`: `OK weak-tests: 5 arquivos, 24 testes novos, 2 marcas novas`.

## Evidência verificada

`bash scripts/dev/red_green.sh 417` sem flag deu `15/24 OK`: os 8 testes de propriedade ficam `verde | verde | FAIL: nao prova a mudanca`, porque testam produto que já existe na `main` (o oráculo é a mudança). Reexecutado com `--allow-green` para esses 8 (P1, P2, P3, P4-conserva, P5, RT1, RT2, RT3):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_land_check.py::test_weak_tests_check_reports_rc | vermelho | verde | OK |
| tests/test_mechanics_properties.py::test_p1_dice_stay_in_range | verde | verde | OK (allow-green) |
| tests/test_mechanics_properties.py::test_p2_damage_within_bounds | verde | verde | OK (allow-green) |
| tests/test_mechanics_properties.py::test_p3_rest_never_exceeds_max_nor_hurts | verde | verde | OK (allow-green) |
| tests/test_mechanics_properties.py::test_p4_trade_conserves_gold_and_stock | verde | verde | OK (allow-green) |
| tests/test_mechanics_properties.py::test_p4_trade_does_not_mutate_input | vermelho | skip (xfail estrito) | FAIL: nao passa na branch (esperado, R15) |
| tests/test_mechanics_properties.py::test_p5_no_arbitrage | verde | verde | OK (allow-green) |
| tests/test_persistence_properties.py::test_rt1_save_load_preserves_mutated_fields | verde | verde | OK (allow-green) |
| tests/test_persistence_properties.py::test_rt2_save_load_is_idempotent_after_first_pass | verde | verde | OK (allow-green) |
| tests/test_persistence_properties.py::test_rt3_save_does_not_mutate_input | verde | verde | OK (allow-green) |
| tests/test_weak_tests.py (14 testes, incl. `test_cli_em_repo_sintetico`) | vermelho (import) | verde | OK |

red_green: 23/24 OK; o único FAIL é o `xfail(strict=True)` de P4(c), exceção prevista em R15 (citado em §9 com a palavra `xfail`).

## Correções aplicadas

Nenhuma (revisão).

## Pendências

- P2-1 a P2-5: emenda na 417 antes do pouso ou follow-up (P2-1 e P2-2 são os que mais enfraquecem o oráculo).
- Bug de `execute_trade` (cópia rasa de `world`): spec própria; ao pousar, retirar o `xfail` de `test_p4_trade_does_not_mutate_input`.
- P5 sem estado de keeper/patente: spec futura.

## Comandos rodados

```text
bash scripts/dev/red_green.sh 417 (sem e com --allow-green) -> 15/24 e 23/24
bash scripts/dev/pt.sh <5 arquivos> -> 60 passed, 1 xfailed em 9,5 s
mutacoes P3/P4b/P2b/RT1 via sed + git checkout -> 1 failed cada; git status limpo
sonda AST (scratchpad) com 12 formas de pulo e 15 testes sem assert -> falsos negativos P2-1/P2-3
weak_tests.py --spec 417 -> OK
```
