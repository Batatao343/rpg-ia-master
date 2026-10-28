# SPEC-341 — Relatório (parcial: pacote R11 NÃO fechou o silencioso)

Estado: pacote mínimo aplicado e medido nas sementes 0–19; **a confirmação 20–99 (R3) não foi rodada**
porque o R9 falha nas sementes de ajuste (silencioso 76,2 % > 75,0 %) e o R11 manda parar e devolver.
`sim.py`, `arena_posturas.py`, `_orcamento.json`, `test_card_sim.py`, legadas e golden: sem diff.

## R6 — baseline da 339 reproduzido
Sangromante (todas/exposto/avaro/silencioso), Corruptor/alma e Médico/boticário: células **idênticas**
a `docs/spec339/arena-depois.json` (comando `posturas --compare`).

## R7 — atribuição (leave-one-out, padrão, sementes 0–19; Δ pp = baseline − sem a Carta)
Dados: `atribuicao.json`. Top por subclasse (média L1/L3/L5; só L5 pesa, as Cartas de `level_req` 4):

- avaro: `san1_ava_juros_do_primeiro` +13,8 (L5), `san1_ava_cobranca_adiada` +13,8, depois legadas
  (`san_transfusao_hostil` +12,5, `san_hemorragia` +10,0, `san_troco_carmesim` +10,0, `san_assinar_sangue` +8,8).
- silencioso: `san1_sil_corte_sem_aviso` +10,0 (L5), `san_troco_carmesim` +7,6, `san1_sil_ponto_cego` +5,1,
  `san_sil_veia` +5,1, depois legadas +3,8.
- exposto (controle): nenhuma Carta acima de +3,7 em célula; L5 do exposto = 47,5 % (baralho L5 sem as `level_req` 4 fortes).

No baralho L5 do silencioso só há **2 Cartas de onda** (`ponto_cego`, `corte_sem_aviso`); o resto é legado.

## R8 — bandeiras com as sementes 20–99 (`r8-bandeiras-sementes20-99.json`)
| Carta | delta 0–19 (339) | delta 20–99 | veredito |
|---|---|---|---|
| `cor1_alm_culpa_antiga` | +11,2 | +1,6 (uso 46 %) | **ruído**, nada muda (R12) |
| `san_exp_espetaculo` (legada) | +8,3 | −4,0 | **ruído**, sem proposta (R13) |
| 9 ex-pendentes (zel×3, exp×3, sil×2, ava×1) | — | −2,8…+5,3, nenhuma `dominante` | ok |
| `med1_bot_giz_vermelho` (dur. 2) | +7,5 | −2,8 | ruído |
| `neu1_ka_divida_gravada` (dur. 2) | — | −2,2 / +1,9 | ruído |

## Cartas alteradas (todas `versao` 1 → 2)
| id | campo | de → para | Δ medido (Sangromante, 0–19) |
|---|---|---|---|
| `san1_ava_cobranca_adiada` | `dano_base` (1º efeito) | 4 → 3 | avaro 78,7 → 77,1 |
| `san1_ava_juros_do_primeiro` | `custo_folego` | 1 → 2 | avaro 77,1 → 74,6 |
| `san1_sil_corte_sem_aviso` | `custo_folego` | 1 → 2 | silencioso 79,6 → 79,2 |
| `san1_sil_ponto_cego` | `custo_folego` | 1 → 2 | silencioso 79,2 → 76,2 |
| `med1_bot_giz_vermelho` | `duracao` | 2 → 1 (campo removido = 1) | +3,7 pp (0–19), uso 53 % |
| `neu1_ka_divida_gravada` | `duracao` | 2 → 1 | devoto −1,2 / arcanista −3,7 |

Tentativas descartadas (não aplicadas): `juros` livre→turno (0 pp), `juros` dano_base 2→1 (−0,0), `ponto_cego` vantagem 2→1 (0 pp),
`corte` +1 Entropia em vez de Fôlego (silencioso 77,9), `corte` dano_base 6→5 (77,5).
Curva exploratória fora do R11 (2 passos na mesma Carta, **não aplicada**): `corte` Fôlego 2 + dano_base 5 → silencioso 75,4 % (181/240), todas 75,0 %. Ainda 1 vitória acima de 75,0 %.

## Arena final 0–19 (leitura padrão / total)
| subclasse | 339 padrão | agora padrão | 339 total | agora total |
|---|---|---|---|---|
| Sangromante todas | 77,9 | **75,4** | 65,6 | 63,1 |
| exposto | 70,4 | 70,4 | 58,3 | 58,3 |
| avaro | 78,7 | **74,6** | 66,0 | 62,9 |
| silencioso | 79,6 | **76,2** | 66,2 | 64,0 |
| Corruptor/alma | 53,3 | 53,3 | 43,3 | 43,3 |
| Médico/boticário | 65,0 | 64,6 | 55,6 | 55,0 |
Devoto, Arcanista e demais subclasses: células idênticas à 339.

## R14/R15 — controle de duração
13 ids classificados (teste `test_inventario_controle_de_onda_fechado`); os 11 de `duracao` 1 valem no `run_round`
real nas duas ordens (taunt: 1 turno do portador e 1 ataque ao jogador; marca: cobre só o próximo ataque do aplicador).
`arc1_imp_parafuso`/`arame` ficam em 2 (desenho).

## Pendências / decisão do dono
O silencioso não fecha ≤ 75,0 % com ≤ 3 Cartas × 1 passo: só 2 Cartas de onda estão no baralho L5. Opções: (a) liberar
2º passo em `san1_sil_corte_sem_aviso` (75,4 %, ainda no limite) e/ou nerfar legada (`san_troco_carmesim`,
`san_sil_veia`; protocolo R11 da 339 + golden), (b) aceitar silencioso ~76 % (D1 alternativa). Depois disso: rodar
`posturas --seeds 20:100` e `cartas --seeds 20:100` uma vez (R3) e remover os `xfail` dos testes de arena.

## Confirmação 20–99 (uma vez, pacote final; `arena-confirmacao.json`) — D4-bis
| subclasse | padrão | total |
|---|---|---|
| Sangromante todas | 75,6 | 62,2 |
| exposto | 71,7 | 60,1 |
| **avaro** | **75,2** (> 75,0) | 62,7 |
| silencioso (exceção D4-bis) | 76,6 | 62,7 |
| Corruptor/alma | 50,7 | 41,2 |
| Médico/boticário | 63,0 | 56,1 |
Cartas (delta 20–99): `corte_sem_aviso` +9,1 pp, uso 52 % → **`dominante`** (nova bandeira real, pós-Fôlego 2); `cobranca_adiada` +4,1; `juros` −2,8; `ponto_cego` +3,1; Giz −2,8; Dívida −3,1/+2,2; `culpa_antiga` +1,6 (ruído).
Parado conforme instrução: avaro 0,2 pp acima do teto na held-out, sem reajuste.
