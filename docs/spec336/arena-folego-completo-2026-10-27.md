# SPEC-336 - arena Fôlego 2 x 3 com o bot de BARALHO COMPLETO (27/10)

Script: `bash scripts/dev/py.sh docs/spec336/arena_folego_full.py 8 --folego 2,3`
(MockLLM, seeded; 5 Posturas x 4 criaturas x 8 sementes = 160 combates por célula e modo; 960 por linha "todas";
~36 s). `off` = bot `cartas` da SPEC-285 (1 ação por rodada). `on` = `sim.full_deck_decl`: baralho completo da
Postura (básicas + Acervo até o nível, 24 cartas), cura < 50 %, defesa < 75 %, golpes de maior dano enquanto houver
Fôlego, sem Pacto. Mão 5. Diferença da arena da SPEC-328: lá o baralho era só as básicas + preparadas do herói inicial.

| Fôlego | Célula | Vitória off | Vitória on | Rodadas off | Rodadas on |
|---|---|---|---|---|---|
| 2 | L1 padrão | 55% | 76% | 4.4 | 3.9 |
| 2 | L1 elite | 36% | 56% | 5.7 | 5.3 |
| 2 | L3 padrão | 71% | 73% | 4.2 | 3.7 |
| 2 | L3 elite | 53% | 59% | 6.4 | 5.4 |
| 2 | L5 padrão | 32% | 38% | 5.0 | 4.3 |
| 2 | L5 elite | 14% | 16% | 4.3 | 4.8 |
| 2 | **todas** | **43%** | **53%** | 5.0 | 4.6 |
| 3 | L1 padrão | 55% | 84% | 4.4 | 3.6 |
| 3 | L1 elite | 36% | 58% | 5.7 | 4.9 |
| 3 | L3 padrão | 71% | 83% | 4.2 | 3.5 |
| 3 | L3 elite | 53% | 64% | 6.4 | 5.3 |
| 3 | L5 padrão | 32% | 54% | 5.0 | 4.4 |
| 3 | L5 elite | 14% | 29% | 4.3 | 5.1 |
| 3 | **todas** | **43%** | **62%** | 5.0 | 4.4 |

Leitura:
- Com o baralho COMPLETO, Fôlego 2 fica a +10 pp do `off` (dentro do ±15 pp do critério da SPEC-328); Fôlego 3
  fica a +19 pp (fora). Na arena só-básicas da 328 a diferença era +21 pp (F2) e +31 pp (F3): o jogo de cartas
  completo dilui o ganho porque o bot passa a gastar Fôlego em cartas de suporte/defesa, não só em golpes.
- Fôlego 2 é a calibragem que mais se aproxima do `off` nas células que importam (L3 padrão: +2 pp), mas deixa
  L5 sem folga (padrão 38%, elite 16%) - o `off` já é fraco ali; isso é do encontro/Vitalidade, não do Fôlego.
- Por Postura (Fôlego 3, `on`): Arcanista Cinzento é a mais fraca em elites (31-38 %); Médico de Campo cai a
  9-16 % em L5 (poucas cartas de dano no baralho; o bot prioriza golpes de maior dano).
- Recomendação: manter `FOLEGO_BASE=3` e mão 5 só se o dono aceitar +19 pp; para ficar dentro de ±15 pp use
  Fôlego 2 (+10 pp). Nenhuma constante foi alterada nesta spec.
