# SPEC-335 — arena do Lote 1 (Arcanista Cinzento, onda 1)

> Gerado a partir de `docs/spec335/sim-lote1-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote1.sh`
> (na raiz; equivale a `bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/posturas/arcanista_cinzento_<sub>.json --protocolo lote --out docs/spec335/sim-lote1-<sub>.json`).

**Protocolo** (`--protocolo lote`, fixado pelo coordenador, igual para todos os lotes): cada Carta isolada (as outras do lote
saem do catálogo na sua rodada), ao nível de entrada (`level_req`), encontro padrão (`padrao`, 4 criaturas por nível), 20 sementes
= 80 lutas por braço. Métrica, limiares e fórmulas são os de `simulate_batch` (nada mudou no evaluator).

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `arc1_cal_leitura` | 40% (41/102) | +2.5 pp | 80 | — |
| `arc1_cal_pulso_medido` | 58% (70/120) | +2.5 pp | 80 | — |
| `arc1_cal_prumo` | 37% (38/103) | +0.0 pp | 80 | — |
| `arc1_cal_compasso` | 27% (28/103) | +1.2 pp | 80 | — |
| `arc1_cal_gabarito` | 27% (28/103) | +1.3 pp | 80 | — |
| `arc1_cal_estilhaco` | 42% (56/134) | -2.5 pp | 80 | — |
| `arc1_cal_rede` | 56% (73/131) | -1.2 pp | 80 | — |
| `arc1_cal_segunda_medicao` | 28% (75/264) | -2.5 pp | 80 | — |
| `arc1_cal_folga` | 29% (17/59) | +0.0 pp | 80 | — |
| `arc1_cal_impacto` | 32% (19/59) | -2.5 pp | 80 | — |
| `arc1_cal_quadrante` | 26% (14/53) | -1.3 pp | 80 | — |
| `arc1_cal_mares` | 27% (21/77) | +0.0 pp | 80 | — |
| `arc1_des_faisca` | 28% (24/87) | +6.2 pp | 80 | — |
| `arc1_des_dedos` | 21% (19/91) | +7.5 pp | 80 | — |
| `arc1_des_palma` | 28% (24/87) | +2.5 pp | 80 | — |
| `arc1_des_corrente` | 21% (19/92) | +6.2 pp | 80 | — |
| `arc1_des_brasa` | 0% (0/91) | +7.5 pp | 80 | uso_nao_medido |
| `arc1_des_garganta` | 27% (24/88) | +2.5 pp | 80 | — |
| `arc1_des_sobrecarga` | 36% (44/121) | -7.5 pp | 80 | — |
| `arc1_des_vazao_selvagem` | 51% (63/123) | -2.5 pp | 80 | — |
| `arc1_des_raio_livre` | 23% (13/56) | -2.5 pp | 80 | — |
| `arc1_des_estouro_contido` | 16% (20/129) | -2.5 pp | 80 | — |
| `arc1_des_fenda` | 28% (14/50) | -1.2 pp | 80 | — |
| `arc1_des_caldeira_sem_fundo` | 41% (19/46) | -1.3 pp | 80 | — |
| `arc1_imp_parafuso` | 41% (41/101) | +5.0 pp | 80 | — |
| `arc1_imp_gambiarra` | 47% (69/146) | -10.0 pp | 80 | — |
| `arc1_imp_carretel` | 44% (41/94) | +2.5 pp | 80 | — |
| `arc1_imp_olho_latao` | 40% (41/102) | +2.5 pp | 80 | — |
| `arc1_imp_mola` | 0% (0/103) | +2.5 pp | 80 | uso_nao_medido |
| `arc1_imp_remendo_cobre` | 38% (39/103) | +0.0 pp | 80 | — |
| `arc1_imp_bomba_estopim` | 51% (67/131) | -7.5 pp | 80 | — |
| `arc1_imp_truque` | 45% (64/142) | -6.3 pp | 80 | — |
| `arc1_imp_arame` | 34% (19/56) | +1.3 pp | 80 | — |
| `arc1_imp_terceiro_dia` | 29% (15/52) | -2.5 pp | 80 | — |
| `arc1_imp_orquestra` | 9% (5/54) | -1.3 pp | 80 | — |
| `arc1_imp_ultima_gambiarra` | 43% (21/49) | +7.5 pp | 80 | — |

Cartas com bandeira no protocolo final: **0**. Ajustadas até limpar (v. histórico do commit): `arc1_des_dedos`
(Vantagem → +2 de acerto), `arc1_des_palma` (dano 3 → 2), `arc1_des_corrente` (Fôlego livre → descartar 2, 1 de Fôlego, `cena`).
Reescrevi o *efeito*, não movi poder para efeitos que a arena não mede.

## Limitações da arena (declaradas, não contornadas)

- O bot ordena pelo `dano_base` do **efeito principal** e joga suporte só com Fôlego sobrando: efeitos secundários (área, Chamado,
  Rachadura, Torpor, Eco, Ressoar, Marca) **não pesam na decisão do bot**; para eles o único freio é o orçamento (`fx.budget_error`).
- Suporte com `custo_folego: 0` é sempre jogado; Entropia não limita o bot (reserva alta). Por isso Cartas de Fôlego livre ficam `cena`.
- Defensivas têm delta negativo porque o bot só defende ferido (`arc1_cal_segunda_medicao`, `arc1_imp_gambiarra`, `arc1_imp_bomba_estopim`, `arc1_imp_truque`). Não é bandeira; follow-up na SPEC-336 (bandeira `fraca` e bot que defende antes).
- Reações (`arc1_des_brasa`, `arc1_imp_mola`) saem `uso_nao_medido`: o bot não as declara.
- Com 80 lutas, 1 luta = 1,25 pp: delta entre ±9 pp é indistinguível de ruído.
