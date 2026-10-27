# SPEC-335 — arena do Lote 2 (Sangromante, onda 1)

> Gerado a partir de `docs/spec335/sim-lote2-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote2.sh`
> (equivale a `bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/posturas/sangromante_<sub>.json --protocolo lote --out docs/spec335/sim-lote2-<sub>.json`).

**Protocolo** (`--protocolo lote`, igual ao do Lote 1): cada Carta isolada, ao nível de entrada (`level_req`), encontro padrão, 20 sementes = 80 lutas por braço. Métrica e limiares inalterados.

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `san1_exp_talho_publico` | 55% (52/94) | +1.2 pp | 80 | — |
| `san1_exp_veia_a_mostra` | 25% (23/93) | +3.7 pp | 80 | — |
| `san1_exp_cicatriz_aberta` | 15% (14/95) | +2.5 pp | 80 | — |
| `san1_exp_aplauso_de_ferro` | 55% (52/94) | +1.2 pp | 80 | — |
| `san1_exp_segundo_ato` | 56% (52/93) | +1.2 pp | 80 | — |
| `san1_exp_sangue_na_areia` | 28% (26/93) | +2.5 pp | 80 | — |
| `san1_exp_gole_rubro` | 13% (13/98) | +1.2 pp | 80 | — |
| `san1_exp_credencial_de_dor` | 59% (63/106) | -20.0 pp | 80 | — |
| `san1_exp_plateia_cega` | 29% (33/115) | -8.7 pp | 80 | — |
| `san1_exp_bis_de_cicatriz` | 53% (31/58) | -3.7 pp | 80 | — |
| `san1_exp_teatro_de_facas` | 14% (7/49) | -1.2 pp | 80 | — |
| `san1_exp_ultima_cortina` | 46% (19/41) | -3.7 pp | 80 | — |
| `san1_ava_moeda_guardada` | 52% (66/127) | +1.3 pp | 80 | — |
| `san1_ava_cofre_estreito` | 24% (22/93) | +1.3 pp | 80 | — |
| `san1_ava_juros_do_primeiro` | 58% (54/93) | +3.7 pp | 80 | — |
| `san1_ava_poupar_ferida` | 10% (10/96) | -1.3 pp | 80 | — |
| `san1_ava_livro_de_dividas` | 29% (27/92) | +3.7 pp | 80 | — |
| `san1_ava_gota_contada` | 58% (54/93) | +3.7 pp | 80 | — |
| `san1_ava_mao_fechada` | 0% (0/93) | +0.0 pp | 80 | uso_nao_medido |
| `san1_ava_cobranca_adiada` | 59% (74/125) | +1.2 pp | 80 | — |
| `san1_ava_penhor_de_carne` | 37% (77/210) | -3.7 pp | 80 | — |
| `san1_ava_hipoteca_de_sangue` | 19% (12/63) | +1.2 pp | 80 | — |
| `san1_ava_execucao_da_divida` | 48% (31/65) | +2.5 pp | 80 | — |
| `san1_ava_cofre_sem_fundo` | 48% (29/61) | +5.0 pp | 80 | — |
| `san1_sil_fio_de_barbeiro` | 55% (48/88) | +0.0 pp | 80 | — |
| `san1_sil_veneno_vermelho` | 24% (21/88) | -1.2 pp | 80 | — |
| `san1_sil_pe_de_pluma` | 0% (0/89) | -1.2 pp | 80 | uso_nao_medido |
| `san1_sil_olho_no_pulso` | 24% (21/88) | +0.0 pp | 80 | — |
| `san1_sil_estancar_calado` | 29% (26/90) | +0.0 pp | 80 | — |
| `san1_sil_marca_de_unha` | 24% (21/88) | +0.0 pp | 80 | — |
| `san1_sil_corte_sem_aviso` | 60% (81/136) | +0.0 pp | 80 | — |
| `san1_sil_ponto_cego` | 29% (44/150) | -2.5 pp | 80 | — |
| `san1_sil_arterial_fina` | 26% (17/65) | -12.5 pp | 80 | — |
| `san1_sil_silencio_cobrado` | 37% (24/65) | -12.5 pp | 80 | — |
| `san1_sil_cirurgia_sem_testemunha` | 41% (19/46) | -11.3 pp | 80 | — |
| `san1_sil_ultima_gota` | 55% (26/47) | +7.5 pp | 80 | — |

Cartas com bandeira no protocolo final: **0** [].
Ajustadas até limpar (rodadas intermediárias fora do repositório): `san1_exp_talho_publico`, `san1_exp_segundo_ato`, `san1_ava_moeda_guardada`, `san1_sil_fio_de_barbeiro`, `san1_sil_corte_sem_aviso` (Fôlego livre → `cena`, dano ou palavra-chave reduzidos: uso > 60%); `san1_exp_ultima_cortina` (dano 14 → 11); `san1_sil_silencio_cobrado` (dano 5 → 3, cura 3 → 4). Reescrevi o *efeito*, não o limiar.

## Delta negativo (não é bandeira; follow-up P2-11 da SPEC-336, bandeira `fraca`)

- `san1_exp_credencial_de_dor` -20.0 pp
- `san1_exp_plateia_cega` -8.7 pp
- `san1_sil_arterial_fina` -12.5 pp
- `san1_sil_silencio_cobrado` -12.5 pp
- `san1_sil_cirurgia_sem_testemunha` -11.3 pp

Investiguei `san1_exp_credencial_de_dor` (−20 pp): o delta não muda removendo Sacrifício, zerando Entropia ou trocando a categoria da arma; é artefato do braço “sem” no nível 4 (a arena não modela Sacrifício). Subi o poder de Arterial Fina, Silêncio Cobrado e Credencial sem mover o delta; mantive no orçamento e registro aqui em vez de empilhar poder que a arena não mede.

## Limitações da arena (as do Lote 1, valem aqui)

- O bot ordena pelo `dano_base` do efeito principal; Sangria, Marca, Eco, Ressoar, Chamado, Provocar, `ao_receber_dano` e cura condicional não pesam na decisão: para eles o único freio é o orçamento (`fx.budget_error`).
- Sacrifício não é modelado como custo de Vitalidade na arena (o delta de `credencial_de_dor` independe dele).
- Reações e esquivas (`san1_ava_mao_fechada`, `san1_sil_pe_de_pluma`) saem `uso_nao_medido`: o bot não as declara.
- Com 80 lutas, 1 luta = 1,25 pp: delta entre ±9 pp é ruído.
