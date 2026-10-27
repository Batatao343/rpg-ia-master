# SPEC-335 — arena do Lote 1 (Arcanista Cinzento, onda 1)

> Gerado a partir de `docs/spec335/sim-lote1-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote1.sh`
> (na raiz; equivale a `bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/posturas/arcanista_cinzento_<sub>.json --protocolo lote --out docs/spec335/sim-lote1-<sub>.json`).

**Protocolo** (`--protocolo lote`, fixado pelo coordenador, igual para todos os lotes): cada Carta isolada (as outras do lote
saem do catálogo na sua rodada), ao nível de entrada (`level_req`), encontro padrão (`padrao`, 4 criaturas por nível), 20 sementes
= 80 lutas por braço. Métrica, limiares e fórmulas são os de `simulate_batch` (nada mudou no evaluator).

**Arena corrigida (SPEC-335 P1-3, `sim.py`)**: o braço “sem” agora NÃO tem a Carta testada (era o mesmo multiconjunto do “com”, só em outra ordem), os dois braços usam a mesma tag de semente (pareados) e o baralho entra ordenado nas pilhas. Teste: `tests/test_card_sim.py::test_bracos_diferem_so_na_carta_testada`. Os deltas abaixo são os primeiros que medem a Carta; com 80 lutas por braço, 1 luta = 1,25 pp e ±9 pp é ruído.

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `arc1_cal_leitura` | 44% (43/98) | -3.7 pp | 80 | — |
| `arc1_cal_pulso_medido` | 57% (62/109) | +3.7 pp | 80 | — |
| `arc1_cal_prumo` | 43% (46/107) | +0.0 pp | 80 | — |
| `arc1_cal_compasso` | 28% (30/106) | -7.5 pp | 80 | — |
| `arc1_cal_gabarito` | 28% (29/102) | -5.0 pp | 80 | — |
| `arc1_cal_estilhaco` | 49% (67/136) | -2.5 pp | 80 | — |
| `arc1_cal_rede` | 54% (73/135) | +0.0 pp | 80 | — |
| `arc1_cal_segunda_medicao` | 27% (75/275) | +0.0 pp | 80 | — |
| `arc1_cal_folga` | 21% (14/66) | +8.8 pp | 80 | dominante |
| `arc1_cal_impacto` | 35% (24/68) | +7.5 pp | 80 | — |
| `arc1_cal_quadrante` | 12% (7/60) | +0.0 pp | 80 | — |
| `arc1_cal_mares` | 26% (22/83) | +0.0 pp | 80 | — |
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

**Rodada com a arena corrigida (substitui a anterior)**: 1 Carta(s) com bandeira — `arc1_cal_folga` (dominante, uso 21%, +8.8 pp). `arc1_cal_folga` fica a +8,8 pp com 80 lutas (7 lutas de diferença): na prática ruído, mas acima do limiar do protocolo; coordenador decide entre ajustar ou aceitar.

Histórico (arena antiga): 0 bandeiras na arena antiga. Ajustadas até limpar (v. histórico do commit): `arc1_des_dedos`
(Vantagem → +2 de acerto), `arc1_des_palma` (dano 3 → 2), `arc1_des_corrente` (Fôlego livre → descartar 2, 1 de Fôlego, `cena`).
Reescrevi o *efeito*. Atenção (P2-5): `arc1_des_palma` ganhou **Eco** (efeito principal só dano 2) e `arc1_des_faisca` ganhou **Ressoar** e passou a `livre`; Eco e Ressoar não pesam na decisão do bot, então para essas duas o **único freio é o orçamento**.

## Limitações da arena (declaradas, não contornadas)

- O bot ordena pelo `dano_base` do **efeito principal** e joga suporte só com Fôlego sobrando: efeitos secundários (área, Chamado,
  Rachadura, Torpor, Eco, Ressoar, Marca) **não pesam na decisão do bot**; para eles o único freio é o orçamento (`fx.budget_error`).
- Suporte com `custo_folego: 0` é sempre jogado; Entropia não limita o bot (reserva alta). Por isso Cartas de Fôlego livre ficam `cena`.
- Defensivas têm delta negativo porque o bot só defende ferido (`arc1_cal_segunda_medicao`, `arc1_imp_gambiarra`, `arc1_imp_bomba_estopim`, `arc1_imp_truque`). Não é bandeira; follow-up na SPEC-336 (bandeira `fraca` e bot que defende antes).
- Reações (`arc1_des_brasa`, `arc1_imp_mola`) saem `uso_nao_medido`: o bot não as declara.
- Com 80 lutas, 1 luta = 1,25 pp: delta entre ±9 pp é indistinguível de ruído.
