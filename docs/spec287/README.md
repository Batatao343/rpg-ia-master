# SPEC-287: evidência da arena

Tabela completa da [SPEC-287](../../specs/SPEC-287-encontros-escala-nivel-5-plus.md):
arena da SPEC-285 (`docs/spec285/arena_lethality.py`), 10 seeds, 2 bots, níveis 1–8.
"Antes" é `main` 3bf6cb3; "depois" é a branch `spec-287`. Os dois lados rodaram a
mesma versão do instrumento (com o `random` global semeado por luta, R5), então
toda diferença vem do motor e dos dados.

```bash
bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 --levels 1,2,3,4,5,6,7,8 > arena.json
```

"nº" é o tamanho do encontro piso de uma espécie (`fill_encounter` com perigo da
arena: nível 1–2 → 1, 3–4 → 2, 5–6 → 3, 7–8 → 4). "≤ 2 rod." conta mortes em até 2
rodadas. Níveis 1–4: idênticos célula a célula.

| célula | nº antes | nº depois | antes | depois | Δ pp | ≤2 rod. antes | ≤2 rod. depois |
|---|---|---|---|---|---|---|---|
| cartas · L1 · lacaio | 1 | 1 | 0.207 | 0.207 | +0.0 | 126 | 126 |
| cartas · L1 · padrao | 1 | 1 | 0.458 | 0.458 | +0.0 | 47 | 47 |
| cartas · L1 · elite | 1 | 1 | 0.565 | 0.565 | +0.0 | 255 | 255 |
| cartas · L1 · chefe | 1 | 1 | 0.454 | 0.454 | +0.0 | 150 | 150 |
| cartas · L2 · lacaio | 1 | 1 | 0.131 | 0.131 | +0.0 | 89 | 89 |
| cartas · L2 · padrao | 1 | 1 | 0.327 | 0.327 | +0.0 | 34 | 34 |
| cartas · L2 · elite | 1 | 1 | 0.477 | 0.477 | +0.0 | 182 | 182 |
| cartas · L2 · chefe | 1 | 1 | 0.311 | 0.311 | +0.0 | 91 | 91 |
| cartas · L3 · lacaio | 2 | 2 | 0.366 | 0.366 | +0.0 | 292 | 292 |
| cartas · L3 · padrao | 1 | 1 | 0.293 | 0.293 | +0.0 | 22 | 22 |
| cartas · L3 · elite | 1 | 1 | 0.418 | 0.418 | +0.0 | 87 | 87 |
| cartas · L3 · chefe | 1 | 1 | 0.242 | 0.242 | +0.0 | 75 | 75 |
| cartas · L4 · lacaio | 2 | 2 | 0.363 | 0.363 | +0.0 | 271 | 271 |
| cartas · L4 · padrao | 2 | 2 | 0.633 | 0.633 | +0.0 | 164 | 164 |
| cartas · L4 · elite | 1 | 1 | 0.397 | 0.397 | +0.0 | 92 | 92 |
| cartas · L4 · chefe | 1 | 1 | 0.255 | 0.255 | +0.0 | 75 | 75 |
| cartas · L5 · lacaio | 3 | 2 | 0.582 | 0.356 | -22.6 | 530 | 264 |
| cartas · L5 · padrao | 2 | 2 | 0.633 | 0.633 | +0.0 | 158 | 158 |
| cartas · L5 · elite | 2 | 2 | 0.739 | 0.739 | +0.0 | 562 | 562 |
| cartas · L5 · chefe | 1 | 1 | 0.255 | 0.432 | +17.7 | 76 | 80 |
| cartas · L6 · lacaio | 3 | 2 | 0.516 | 0.358 | -15.8 | 450 | 223 |
| cartas · L6 · padrao | 2 | 2 | 0.598 | 0.598 | +0.0 | 145 | 145 |
| cartas · L6 · elite | 2 | 2 | 0.716 | 0.716 | +0.0 | 503 | 503 |
| cartas · L6 · chefe | 1 | 1 | 0.275 | 0.423 | +14.8 | 65 | 77 |
| cartas · L7 · lacaio | 4 | 2 | 0.589 | 0.363 | -22.6 | 665 | 224 |
| cartas · L7 · padrao | 3 | 2 | 0.755 | 0.563 | -19.2 | 213 | 143 |
| cartas · L7 · elite | 2 | 2 | 0.705 | 0.705 | +0.0 | 501 | 501 |
| cartas · L7 · chefe | 1 | 1 | 0.269 | 0.440 | +17.1 | 65 | 78 |
| cartas · L8 · lacaio | 5 | 2 | 0.607 | 0.324 | -28.3 | 773 | 125 |
| cartas · L8 · padrao | 3 | 2 | 0.728 | 0.555 | -17.3 | 214 | 128 |
| cartas · L8 · elite | 2 | 2 | 0.674 | 0.674 | +0.0 | 373 | 373 |
| cartas · L8 · chefe | 1 | 1 | 0.246 | 0.423 | +17.7 | 41 | 58 |
| basico · L1 · lacaio | 1 | 1 | 0.172 | 0.172 | +0.0 | 77 | 77 |
| basico · L1 · padrao | 1 | 1 | 0.438 | 0.438 | +0.0 | 47 | 47 |
| basico · L1 · elite | 1 | 1 | 0.588 | 0.588 | +0.0 | 176 | 176 |
| basico · L1 · chefe | 1 | 1 | 0.340 | 0.340 | +0.0 | 101 | 101 |
| basico · L2 · lacaio | 1 | 1 | 0.136 | 0.136 | +0.0 | 72 | 72 |
| basico · L2 · padrao | 1 | 1 | 0.405 | 0.405 | +0.0 | 37 | 37 |
| basico · L2 · elite | 1 | 1 | 0.560 | 0.560 | +0.0 | 146 | 146 |
| basico · L2 · chefe | 1 | 1 | 0.278 | 0.278 | +0.0 | 76 | 76 |
| basico · L3 · lacaio | 2 | 2 | 0.431 | 0.431 | +0.0 | 320 | 320 |
| basico · L3 · padrao | 1 | 1 | 0.425 | 0.425 | +0.0 | 30 | 30 |
| basico · L3 · elite | 1 | 1 | 0.542 | 0.542 | +0.0 | 101 | 101 |
| basico · L3 · chefe | 1 | 1 | 0.377 | 0.377 | +0.0 | 90 | 90 |
| basico · L4 · lacaio | 2 | 2 | 0.438 | 0.438 | +0.0 | 297 | 297 |
| basico · L4 · padrao | 2 | 2 | 0.722 | 0.722 | +0.0 | 177 | 177 |
| basico · L4 · elite | 1 | 1 | 0.524 | 0.524 | +0.0 | 111 | 111 |
| basico · L4 · chefe | 1 | 1 | 0.382 | 0.382 | +0.0 | 93 | 93 |
| basico · L5 · lacaio | 3 | 2 | 0.615 | 0.434 | -18.1 | 538 | 297 |
| basico · L5 · padrao | 2 | 2 | 0.720 | 0.720 | +0.0 | 177 | 177 |
| basico · L5 · elite | 2 | 2 | 0.783 | 0.783 | +0.0 | 633 | 633 |
| basico · L5 · chefe | 1 | 1 | 0.385 | 0.568 | +18.3 | 93 | 93 |
| basico · L6 · lacaio | 3 | 2 | 0.568 | 0.402 | -16.6 | 466 | 258 |
| basico · L6 · padrao | 2 | 2 | 0.703 | 0.703 | +0.0 | 159 | 159 |
| basico · L6 · elite | 2 | 2 | 0.753 | 0.753 | +0.0 | 577 | 577 |
| basico · L6 · chefe | 1 | 1 | 0.349 | 0.517 | +16.8 | 86 | 86 |
| basico · L7 · lacaio | 4 | 2 | 0.667 | 0.399 | -26.8 | 718 | 258 |
| basico · L7 · padrao | 3 | 2 | 0.868 | 0.697 | -17.1 | 249 | 159 |
| basico · L7 · elite | 2 | 2 | 0.751 | 0.751 | +0.0 | 577 | 577 |
| basico · L7 · chefe | 1 | 1 | 0.349 | 0.665 | +31.6 | 86 | 86 |
| basico · L8 · lacaio | 5 | 2 | 0.665 | 0.359 | -30.6 | 847 | 169 |
| basico · L8 · padrao | 3 | 2 | 0.813 | 0.642 | -17.1 | 246 | 143 |
| basico · L8 · elite | 2 | 2 | 0.726 | 0.726 | +0.0 | 470 | 470 |
| basico · L8 · chefe | 1 | 1 | 0.274 | 0.606 | +33.2 | 40 | 48 |
