# SPEC-295: evidência da arena

Tabela completa da [SPEC-295](../../specs/SPEC-295-chefe-no-topo.md): arena da
SPEC-285 (`docs/spec285/arena_lethality.py`, sem alteração), 10 seeds, 2 bots,
níveis 1–8. "Antes" é `main` 36cda92; "depois" é a branch `spec-295`.

```bash
bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 --levels 1,2,3,4,5,6,7,8 > arena.json
```

Toda célula Lacaio/Padrão/Elite é idêntica (o dicionário inteiro da célula, inclusive
`per_class` e rodadas). Só a célula "chefe" muda.

| célula | nº | antes | depois | Δ pp | ≤2 rod. antes | ≤2 rod. depois |
|---|---|---|---|---|---|---|
| cartas · L1 · lacaio | 1 | 0.207 | 0.207 | +0.0 | 126 | 126 |
| cartas · L1 · padrao | 1 | 0.458 | 0.458 | +0.0 | 47 | 47 |
| cartas · L1 · elite | 1 | 0.565 | 0.565 | +0.0 | 255 | 255 |
| cartas · L1 · chefe | 1 | 0.454 | 0.729 | +27.5 | 150 | 228 |
| cartas · L2 · lacaio | 1 | 0.131 | 0.131 | +0.0 | 89 | 89 |
| cartas · L2 · padrao | 1 | 0.327 | 0.327 | +0.0 | 34 | 34 |
| cartas · L2 · elite | 1 | 0.477 | 0.477 | +0.0 | 182 | 182 |
| cartas · L2 · chefe | 1 | 0.311 | 0.649 | +33.8 | 91 | 197 |
| cartas · L3 · lacaio | 2 | 0.366 | 0.366 | +0.0 | 292 | 292 |
| cartas · L3 · padrao | 1 | 0.293 | 0.293 | +0.0 | 22 | 22 |
| cartas · L3 · elite | 1 | 0.418 | 0.418 | +0.0 | 87 | 87 |
| cartas · L3 · chefe | 1 | 0.242 | 0.551 | +30.9 | 75 | 184 |
| cartas · L4 · lacaio | 2 | 0.363 | 0.363 | +0.0 | 271 | 271 |
| cartas · L4 · padrao | 2 | 0.633 | 0.633 | +0.0 | 164 | 164 |
| cartas · L4 · elite | 1 | 0.397 | 0.397 | +0.0 | 92 | 92 |
| cartas · L4 · chefe | 1 | 0.255 | 0.563 | +30.8 | 75 | 170 |
| cartas · L5 · lacaio | 2 | 0.356 | 0.356 | +0.0 | 264 | 264 |
| cartas · L5 · padrao | 2 | 0.633 | 0.633 | +0.0 | 158 | 158 |
| cartas · L5 · elite | 2 | 0.739 | 0.739 | +0.0 | 562 | 562 |
| cartas · L5 · chefe | 1 | 0.432 | 0.845 | +41.3 | 80 | 188 |
| cartas · L6 · lacaio | 2 | 0.358 | 0.358 | +0.0 | 223 | 223 |
| cartas · L6 · padrao | 2 | 0.598 | 0.598 | +0.0 | 145 | 145 |
| cartas · L6 · elite | 2 | 0.716 | 0.716 | +0.0 | 503 | 503 |
| cartas · L6 · chefe | 1 | 0.423 | 0.771 | +34.8 | 77 | 161 |
| cartas · L7 · lacaio | 2 | 0.363 | 0.363 | +0.0 | 224 | 224 |
| cartas · L7 · padrao | 2 | 0.563 | 0.563 | +0.0 | 143 | 143 |
| cartas · L7 · elite | 2 | 0.705 | 0.705 | +0.0 | 501 | 501 |
| cartas · L7 · chefe | 1 | 0.440 | 0.772 | +33.2 | 78 | 161 |
| cartas · L8 · lacaio | 2 | 0.324 | 0.324 | +0.0 | 125 | 125 |
| cartas · L8 · padrao | 2 | 0.555 | 0.555 | +0.0 | 128 | 128 |
| cartas · L8 · elite | 2 | 0.674 | 0.674 | +0.0 | 373 | 373 |
| cartas · L8 · chefe | 1 | 0.423 | 0.791 | +36.8 | 58 | 125 |
| basico · L1 · lacaio | 1 | 0.172 | 0.172 | +0.0 | 77 | 77 |
| basico · L1 · padrao | 1 | 0.438 | 0.438 | +0.0 | 47 | 47 |
| basico · L1 · elite | 1 | 0.588 | 0.588 | +0.0 | 176 | 176 |
| basico · L1 · chefe | 1 | 0.340 | 0.694 | +35.4 | 101 | 203 |
| basico · L2 · lacaio | 1 | 0.136 | 0.136 | +0.0 | 72 | 72 |
| basico · L2 · padrao | 1 | 0.405 | 0.405 | +0.0 | 37 | 37 |
| basico · L2 · elite | 1 | 0.560 | 0.560 | +0.0 | 146 | 146 |
| basico · L2 · chefe | 1 | 0.278 | 0.651 | +37.3 | 76 | 186 |
| basico · L3 · lacaio | 2 | 0.431 | 0.431 | +0.0 | 320 | 320 |
| basico · L3 · padrao | 1 | 0.425 | 0.425 | +0.0 | 30 | 30 |
| basico · L3 · elite | 1 | 0.542 | 0.542 | +0.0 | 101 | 101 |
| basico · L3 · chefe | 1 | 0.377 | 0.614 | +23.7 | 90 | 193 |
| basico · L4 · lacaio | 2 | 0.438 | 0.438 | +0.0 | 297 | 297 |
| basico · L4 · padrao | 2 | 0.722 | 0.722 | +0.0 | 177 | 177 |
| basico · L4 · elite | 1 | 0.524 | 0.524 | +0.0 | 111 | 111 |
| basico · L4 · chefe | 1 | 0.382 | 0.631 | +24.9 | 93 | 178 |
| basico · L5 · lacaio | 2 | 0.434 | 0.434 | +0.0 | 297 | 297 |
| basico · L5 · padrao | 2 | 0.720 | 0.720 | +0.0 | 177 | 177 |
| basico · L5 · elite | 2 | 0.783 | 0.783 | +0.0 | 633 | 633 |
| basico · L5 · chefe | 1 | 0.568 | 0.889 | +32.1 | 93 | 198 |
| basico · L6 · lacaio | 2 | 0.402 | 0.402 | +0.0 | 258 | 258 |
| basico · L6 · padrao | 2 | 0.703 | 0.703 | +0.0 | 159 | 159 |
| basico · L6 · elite | 2 | 0.753 | 0.753 | +0.0 | 577 | 577 |
| basico · L6 · chefe | 1 | 0.517 | 0.863 | +34.6 | 86 | 174 |
| basico · L7 · lacaio | 2 | 0.399 | 0.399 | +0.0 | 258 | 258 |
| basico · L7 · padrao | 2 | 0.697 | 0.697 | +0.0 | 159 | 159 |
| basico · L7 · elite | 2 | 0.751 | 0.751 | +0.0 | 577 | 577 |
| basico · L7 · chefe | 1 | 0.665 | 0.880 | +21.5 | 86 | 174 |
| basico · L8 · lacaio | 2 | 0.359 | 0.359 | +0.0 | 169 | 169 |
| basico · L8 · padrao | 2 | 0.642 | 0.642 | +0.0 | 143 | 143 |
| basico · L8 · elite | 2 | 0.726 | 0.726 | +0.0 | 470 | 470 |
| basico · L8 · chefe | 1 | 0.606 | 0.874 | +26.8 | 48 | 155 |

| bot | nível | Padrão | Elite | Chefe | Chefe − Elite (pp) | C1 ≥ 3 | C2 ≤ 20 |
|---|---|---|---|---|---|---|---|
| cartas | 1 | 0.458 | 0.565 | 0.729 | +16.4 | ok | ok |
| cartas | 2 | 0.327 | 0.477 | 0.649 | +17.2 | ok | ok |
| cartas | 3 | 0.293 | 0.418 | 0.551 | +13.3 | ok | ok |
| cartas | 4 | 0.633 | 0.397 | 0.563 | +16.6 | ok | ok |
| cartas | 5 | 0.633 | 0.739 | 0.845 | +10.6 | ok | ok |
| cartas | 6 | 0.598 | 0.716 | 0.771 | +5.5 | ok | ok |
| cartas | 7 | 0.563 | 0.705 | 0.772 | +6.7 | ok | ok |
| cartas | 8 | 0.555 | 0.674 | 0.791 | +11.7 | ok | ok |
| basico | 1 | 0.438 | 0.588 | 0.694 | +10.6 | ok | ok |
| basico | 2 | 0.405 | 0.560 | 0.651 | +9.1 | ok | ok |
| basico | 3 | 0.425 | 0.542 | 0.614 | +7.2 | ok | ok |
| basico | 4 | 0.722 | 0.524 | 0.631 | +10.7 | ok | ok |
| basico | 5 | 0.720 | 0.783 | 0.889 | +10.6 | ok | ok |
| basico | 6 | 0.703 | 0.753 | 0.863 | +11.0 | ok | ok |
| basico | 7 | 0.697 | 0.751 | 0.880 | +12.9 | ok | ok |
| basico | 8 | 0.642 | 0.726 | 0.874 | +14.8 | ok | ok |
