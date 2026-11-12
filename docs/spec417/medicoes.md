# SPEC-417 — medições (shell local, 2026-11-12)

## R7 tempo do script
`time bash scripts/dev/py.sh scripts/dev/weak_tests.py --base 9f21ef4a --head 29dba5d5`
(36 arquivos, 63 testes novos): real 5,2 s (inclui o arranque do `uv`/`py.sh`; o script em si é
dominado por ~60 `git show`). Acima da meta de 3 s da spec; sem impacto no pouso (roda 1x).

## R9 calibração (specs 405-413; base = pai do 1º commit com `specN`, head = último)
| Spec | Arquivos | Testes novos | Marcas novas | FAIL | Falso positivo |
|---|---|---|---|---|---|
| 405 | 5 | 3 | 0 | 0 | 0 |
| 406 | 4 | 2 | 0 | 0 | 0 |
| 407 | 1 | 5 | 0 | 0 | 0 |
| 408 | 2 | 5 | 0 | 0 | 0 |
| 409 | 13 | 3 | 0 | 0 | 0 |
| 410 | 13 | 45 | 0 | 0 | 0 |
| 411 | 4 | 13 | 0 | 0 | 0 |
| 412 | 2 | 7 | 0 | 0 | 0 |
| 413 | 2 | 1 | 0 | 0 | 0 |

(Intervalo por `git log --grep=specN`: pode incluir commits de outras specs intercalados.)

## Etapa 0
- Marcas de pulo existentes em `tests/**/test_*.py` + `conftest.py`: 175, das quais 55 sem
  motivo (`has_reason=False`). O gate só olha marcas NOVAS; as 55 não reprovam nada.
- `hypothesis` antes: só no grupo `fuzz` (via schemathesis), ausente do venv default (coordenador
  instalou 6.170.12 no venv principal). `uv lock`: diff de 2 linhas (aresta do grupo `dev` + o
  `specifier`), nenhuma versão trocada; `requirements.txt` inalterado.

## R14 tempo (`-n 2 --durations=0`)
Mecânica: P1 0,13 s · P2 0,18 s · P3 0,17 s · P4 0,12 s + 0,05 s (xfail) · P5 0,06 s = ~0,7 s.
Persistência: RT1 0,63 s · RT2 1,02 s · RT3 0,21 s = ~1,9 s. Muito abaixo de 8 s / 10 s;
`max_examples` ficou nos valores de partida (100/100/30/30/30/20/20/20).

## R16
`.hypothesis/` é criado (só `constants/` e `tmp/`, com `.gitignore` próprio): `git status
--porcelain | grep hypothesis` vazio. Nenhuma linha em `.gitignore`.

## Mutações (§4.4): todas falharam com a mutação e voltaram ao verde ao desfazer
P1a, P1b, P2a, P2b, P3, P4a, P4b, P5, RT2, RT3: 1 failed cada. RT1: a 1ª versão do gerador
(listas de até 100 textos livres) NÃO falhava com `[:64]`; gerador reforçado (ramo de 65-100 ids
únicos) e então falhou. P4 (c) está em xfail estrito (achado 1).
