# SPEC-401 - relatorio

Base: `main` `f27238ee` (SPEC-400 pousada). Arena L3 off/on, sementes 0-39 (`base.json`), final 0-39
(`arena-final.json`), confirmacao 40-119 uma vez e sem reajuste (`confirmacao-40-119.json`).

| id | base 0-39 (off/on) | final 0-39 | confirmacao 40-119 | dials antes (corpo/dano/forca/sig) | dials depois |
|---|---|---|---|---|---|
| mon_odre_de_oleo | 56,5 / 53 (ok; 40-119 antiga 37,2/45,8) | 64,5 / 64,5 | 51,2 / 54,5 | 2/1/0/1 | 1/1/0/1 |
| mon_armador_de_fosso | 49,5 / 86 | 54 / 84 | 46 / 83 | 2/2/0/4 | 3/1/0/0 |
| mon_escuta_do_sinal | 41,5 / 87,5 | 48,5 / 83 | 45,5 / 81,2 | 1/1/1/3 | 3/0/0/3 |

Todas as celulas L3 dentro de 45-85 % nas duas janelas: nenhuma excecao nominal remanescente
(nenhuma linha `EXCECAO`).

## Metodo e desvios

- `calibrar.py` rodou 1x por id (armador e escuta, 40 sementes, 6 rodadas: sem ganho sobre o ponto
  de partida) e 1x em modo medicao (`--rodadas 0`) para gravar o texto `arena:`. Como o 1o passo nao
  moveu nada, os dials finais foram buscados por sondagem direta de `arena.py` (script de rascunho,
  fora do repo) e o `calibrar.py` validou/gravou a leitura.
- Odre: ja estava `ok` em 0-39, entao o `calibrar.py` nao se moveria; a falha era 40-119. O ajuste
  (corpo 2 -> 1) foi escolhido medindo 0-119 (sondagem: 55,7/57,8), e o `arena:` registra 0-119.
  A confirmacao 40-119 do odre portanto NAO e independente (a janela entrou na escolha).
- `sig` do escuta nao tem efeito na arena (sig=-3/0/3 deram o mesmo resultado); o gap off/on e ~35-40 pp
  em qualquer combinacao corpo/dano/forca, e 3/0/0 foi o unico ponto de ~25 testados dentro da faixa.
  Margem apertada: 83 / 81,2 on e 45,5 off na confirmacao.
- Armador confirmacao off 46 e margem de 1 pp.

`base-snapshot.json` x `final-snapshot.json` (373 ids menos os 3): hashes off e baralho on identicos.
`ajustes-base.yaml` e o `_ajustes.yaml` da base para o teste de dials mudados.
