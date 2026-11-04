# SPEC-394 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Terra (revisor independente) · **Data:** 2026-11-04 · **Commit revisado:** `92120899`

## Escopo

`git diff main...HEAD` (68ed7b2d, 1cd82ce1, 1a8efc76, 92120899), `docs/spec394/RELATORIO.md`,
`tests/test_bestiario_calibragem.py`, `_ajustes.yaml`, `data/bestiary.json`, Cartas alteradas.
Fora: refazer a bisecção; rodar a arena.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `data/bestiary.json`, `data/cards/criaturas/montanhas_afiadas.json`, `_ajustes.yaml` | Armador e escuta são exceções D2 (fora da faixa), mas receberam dials novos (armador c2 d2 s4; escuta f1 s3) e entraram no bestiário. D2 permite "melhor ajuste visto", e o relatório registra os números antes/depois. A confirmação mostra os dois 2-3 pp abaixo do piso no `off` (sobreajuste em 0-39). Não bloqueia, mas o "só o anzolado recalibrou" vale apenas para o veredito, não para os dados. | Registrar na §9 que as duas ficam com ajuste parcial; follow-up: spec de Carta/mecânica para as duas (D2 alternativa). |
| P2-2 | P2 | `tests/test_bestiario_calibragem.py:56-83` | Os testes leem só artefatos gravados (`arena-final.json`, `final-snapshot.json`); não ligam ao estado atual de `data/`. Falham antes da mudança (artefato ausente) e não afrouxam a faixa, mas um edit posterior em `bestiary.json` passaria despercebido. Verifiquei por fora: regenerei o snapshot (369 ids, excluindo F) e ficou byte-idêntico a `final-snapshot.json`. | Aceitável pelo escopo (sem rodar arena). Opcional: teste que compare o `ok`/dials de `_ajustes.yaml` com `bestiary.json`. |
| P2-3 | P2 | `docs/spec394/RELATORIO.md` | O commit 1cd82ce1 diz "run 1" e o relatório diz duas execuções do `calibrar.py`; só um commit de dados existe (a 2ª não achou nada melhor). Coerente, mas sem log da 2ª execução nos artefatos. | Nota de uma linha com o resultado da 2ª execução, ou aceitar. |

Conferências sem achado:

1. Só o anzolado entrou na faixa (57,5/76; confirmação 56,8/71). Exceções armador, escuta e portão têm linha `EXCECAO`, números (antes/depois/confirmação) e motivo no relatório e na §9. `test_derivadas_387_com_ok_na_arena` exige `exceções <= F`.
2. Dials em `_ajustes.yaml` dentro de ±7, com `arena` preenchida (anzolado, armador, escuta). Portão intocado.
3. Snapshot: 369 ids, hash `off` (`ensure_combat_sheet`) e `on` (baralho, sementes 0-11); o teste exige `set(depois) == set(antes) - F` e compara hash a hash, então falharia com qualquer mudança (nenhum falso positivo por conjunto vazio ou chave faltando; ids com `cartas_autorais` só têm `off`, igual ao script da 373). Regeneração ao vivo idêntica.
4. `scripts/bestiario/arena.py`, `calibrar.py` e `evals/` não aparecem no diff (nenhum caminho de `protected-paths.txt` tocado). O teste novo checa a faixa 45-85 % fixa e exige o `ok` gravado pela arena.
5. R3: a bisecção e o raciocínio fecham (`e208f189` cria `abissal.muito_ferido -> flee`; `normalize_runtime_profile` preenche `action_key` ignorando `resistance: absoluta`/`nao_foge`; braço sem o flee devolve 61/63,5 = SPEC-349). Pela D3 vira a SPEC-395, separada; coerente com a reserva `f3b97cde`.
6. R7: uma só execução (commit 92120899 só adiciona resultados e docs), sem ajuste de dados depois.

## Correções aplicadas

Nenhuma (revisor não edita o produto).

## Pendências

- SPEC-395: corrigir a tabela de arquétipo (5 criaturas abissal; recalibrar portão/lacrador depois).
- Armador e escuta: spec própria ou nova calibração após a 395 (follow-up).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest tests/test_bestiario_calibragem.py tests/test_handoff_names.py -q -n 2 → 7 passed
bash scripts/dev/py.sh docs/spec394/snapshot.py --excluir <F> + cmp com final-snapshot.json → idêntico (369)
git diff main...HEAD --name-only | grep arena|calibrar|evals → nada
```
