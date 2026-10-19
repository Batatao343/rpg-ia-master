# SPEC-285: evidência da arena

Este arquivo guarda a tabela completa da arena usada na
[SPEC-285](../../specs/SPEC-285-letalidade-pos-232-275.md).

Para reproduzir, rode o comando abaixo em `main` e na branch. São 10 seeds e
2.250 lutas por célula.

```bash
bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena.json
```

As colunas mostram, para cada célula:

- a taxa de morte do herói por combate (`main` 866907d e final);
- a diferença em pontos percentuais;
- `early_deaths`, que conta as mortes em até 2 rodadas.

Os bots são dois: `basico`, que só faz ataque básico (o mesmo da arena da
SPEC-283), e `cartas`, o bot razoável. Em cada célula, o "nº" é o tamanho do
encontro piso de uma espécie.

| célula | nº | `main` morte | final morte | Δ pp | `main` ≤ 2 rod. | final ≤ 2 rod. |
|---|---|---|---|---|---|---|
| basico · L1 · lacaio | 1 | 0.252 | 0.172 | -8.0 | 77 | 77 |
| basico · L1 · padrao | 1 | 0.448 | 0.437 | -1.1 | 47 | 47 |
| basico · L1 · elite | 1 | 0.640 | 0.588 | -5.2 | 176 | 176 |
| basico · L1 · chefe | 1 | 0.423 | 0.346 | -7.7 | 101 | 101 |
| basico · L3 · lacaio | 2 | 0.496 | 0.430 | -6.6 | 316 | 320 |
| basico · L3 · padrao | 1 | 0.450 | 0.425 | -2.5 | 31 | 30 |
| basico · L3 · elite | 1 | 0.575 | 0.543 | -3.2 | 105 | 101 |
| basico · L3 · chefe | 1 | 0.446 | 0.382 | -6.4 | 90 | 90 |
| basico · L5 · lacaio | 3 | 0.646 | 0.611 | -3.5 | 562 | 541 |
| basico · L5 · padrao | 2 | 0.733 | 0.725 | -0.8 | 177 | 177 |
| basico · L5 · elite | 2 | 0.797 | 0.781 | -1.6 | 646 | 633 |
| basico · L5 · chefe | 1 | 0.460 | 0.382 | -7.8 | 93 | 93 |
| basico · L8 · lacaio | 5 | 0.706 | 0.667 | -3.9 | 856 | 852 |
| basico · L8 · padrao | 3 | 0.820 | 0.817 | -0.3 | 249 | 247 |
| basico · L8 · elite | 2 | 0.746 | 0.723 | -2.3 | 476 | 470 |
| basico · L8 · chefe | 1 | 0.338 | 0.274 | -6.4 | 40 | 40 |
| cartas · L1 · lacaio | 1 | 0.274 | 0.207 | -6.7 | 126 | 126 |
| cartas · L1 · padrao | 1 | 0.472 | 0.458 | -1.4 | 47 | 47 |
| cartas · L1 · elite | 1 | 0.612 | 0.560 | -5.2 | 255 | 255 |
| cartas · L1 · chefe | 1 | 0.537 | 0.448 | -8.9 | 150 | 150 |
| cartas · L3 · lacaio | 2 | 0.426 | 0.360 | -6.6 | 290 | 292 |
| cartas · L3 · padrao | 1 | 0.317 | 0.297 | -2.0 | 23 | 22 |
| cartas · L3 · elite | 1 | 0.465 | 0.423 | -4.2 | 90 | 87 |
| cartas · L3 · chefe | 1 | 0.332 | 0.246 | -8.6 | 76 | 75 |
| cartas · L5 · lacaio | 3 | 0.608 | 0.575 | -3.3 | 547 | 527 |
| cartas · L5 · padrao | 2 | 0.630 | 0.640 | +1.0 | 163 | 162 |
| cartas · L5 · elite | 2 | 0.771 | 0.740 | -3.1 | 591 | 561 |
| cartas · L5 · chefe | 1 | 0.328 | 0.255 | -7.3 | 76 | 75 |
| cartas · L8 · lacaio | 5 | 0.633 | 0.607 | -2.6 | 781 | 772 |
| cartas · L8 · padrao | 3 | 0.728 | 0.722 | -0.6 | 216 | 212 |
| cartas · L8 · elite | 2 | 0.711 | 0.675 | -3.6 | 395 | 374 |
| cartas · L8 · chefe | 1 | 0.292 | 0.240 | -5.2 | 41 | 39 |
