# SPEC-335 — Arena por Postura (baralho completo), fechamento

Comando: `bash scripts/dev/py.sh docs/spec335/arena_posturas.py 20 --out docs/spec335/sim-posturas-final.json`
(generaliza `arena_postura_medico.py`; níveis 1, 3 e 5; categorias `padrao` e `elite`; 4 criaturas por
categoria; 20 sementes: 240 lutas por linha em `padrao`, 480 com `elite`). Baralho = `sim.full_deck`
(catálogo completo, Fôlego do catálogo), mesmo bot dos Lotes 2–6.

## Resultado (taxa de vitória)

Leitura A = só categoria `padrao` (a "arena padrão" do critério). Leitura B = `padrao` + `elite`
(a taxa total usada nos relatórios dos lotes).

| Postura | A: padrão | B: padrão+elite | Faixa 45–75 % (A) |
|---|---|---|---|
| Devoto do Abismo | **77,1 %** | 69,4 % | **fora (acima)** |
| Sangromante | **80,0 %** | 69,2 % | **fora (acima)** |
| Corruptor | 52,5 % | **41,9 %** | dentro em A; abaixo em B |
| Arcanista Cinzento | 55,8 % | **42,1 %** | dentro em A; abaixo em B |
| Médico de Campo | 75,0 % | 63,1 % | no limite (75,0 %) |

Por subclasse (A / B): Devoto consagrado 76,7/70,2, zeloso 69,6/59,2, enlutado 71,7/63,5 · Sangromante
exposto 79,2/64,4, avaro 80,0/69,2, silencioso 81,7/70,8 · Corruptor biologia 66,2/56,5,
**alma 44,6/34,4**, inorgânica 53,7/45,2 · Arcanista calibrado 58,8/44,4, descoberto 50,8/37,5,
improvisador 54,2/41,5 · Médico trincheira 64,2/56,7, boticário 63,7/53,5, ferro 67,1/54,4.
(Dados brutos por célula: `sim-posturas-final.json`.)

## Achados

- **Critério não fechado.** Na leitura A, Devoto (77,1 %) e Sangromante (80,0 %) passam do teto de 75 %
  (Médico está exatamente em 75,0 %). Na leitura B, Corruptor (41,9 %) e Arcanista (42,1 %) ficam abaixo
  de 45 %, e a subclasse Corruptor/alma (34,4 %) é a mais fraca. Nenhuma Carta foi alterada e a faixa
  não foi afrouxada (restrição desta rodada); o ajuste fica para a SPEC-336/decisão do coordenador.
- Em todas as Posturas a taxa cai do nível 1 para o 5 (a arena escala a criatura e o bot não usa a
  `level_req`+3 do baralho seguinte, v. P2-11 da 335).

## Vieses e limites

- **Viés de ordem do `full_deck`.** O baralho é preenchido por `(-tier, id)` até `DECK_MAX`. Dentro do mesmo
  tier os ids `*1_` (Cartas da onda 1) vêm **antes** dos legados (`*_...`, pois `'1' < '_'`): com o baralho
  cheio, as novas entram primeiro e as legadas do mesmo tier são cortadas. A taxa mede "tier mais alto +
  onda 1", não a escolha de um jogador real, e tende a superestimar as Posturas onde a onda 1 é forte.
- O bot joga o golpe/efeito barato de maior `dano_base`: subestima controle, reações e Eco/Ressoar.
- Amostra: 4 criaturas por categoria × 20 sementes; erro padrão ≈ ±3 pp por Postura em `padrao`.
