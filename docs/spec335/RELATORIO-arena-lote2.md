# SPEC-335 — arena do Lote 2 (Sangromante, onda 1)

> Gerado a partir de `docs/spec335/sim-lote2-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote2.sh`.

**Protocolo** (`--protocolo lote`): cada Carta isolada (as irmãs do lote fora do catálogo), ao `level_req`, encontro padrão, 20 sementes = 80 lutas por braço. Métrica e limiares inalterados.

**Arena corrigida (SPEC-335 P1-3, `sim.py`)**: o braço “sem” agora NÃO tem a Carta testada (era o mesmo multiconjunto do “com”, só em outra ordem), os dois braços usam a mesma tag de semente (pareados) e o baralho entra ordenado nas pilhas. Teste: `tests/test_card_sim.py::test_bracos_diferem_so_na_carta_testada`. Os deltas abaixo são os primeiros que medem a Carta; com 80 lutas por braço, 1 luta = 1,25 pp e ±9 pp é ruído.

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `san1_exp_talho_publico` | 52% (52/100) | +0.0 pp | 80 | — |
| `san1_exp_veia_a_mostra` | 32% (38/118) | +6.2 pp | 80 | — |
| `san1_exp_cicatriz_aberta` | 78% (79/101) | +0.0 pp | 80 | dominante |
| `san1_exp_aplauso_de_ferro` | 0% (0/104) | -1.3 pp | 80 | uso_nao_medido |
| `san1_exp_segundo_ato` | 52% (52/99) | +1.2 pp | 80 | — |
| `san1_exp_sangue_na_areia` | 23% (23/101) | +0.0 pp | 80 | — |
| `san1_exp_gole_rubro` | 6% (6/105) | -2.5 pp | 80 | — |
| `san1_exp_selo_de_dor` | 80% (78/98) | -7.5 pp | 80 | dominante |
| `san1_exp_plateia_cega` | 31% (38/123) | +6.2 pp | 80 | — |
| `san1_exp_bis_de_cicatriz` | 52% (30/58) | +2.5 pp | 80 | — |
| `san1_exp_teatro_de_facas` | 12% (5/40) | -1.3 pp | 80 | — |
| `san1_exp_ultima_cortina` | 68% (28/41) | -7.5 pp | 80 | dominante |
| `san1_ava_moeda_guardada` | 42% (59/140) | -2.5 pp | 80 | — |
| `san1_ava_cofre_estreito` | 9% (9/100) | -2.5 pp | 80 | — |
| `san1_ava_juros_do_primeiro` | 40% (50/126) | -5.0 pp | 80 | — |
| `san1_ava_poupar_ferida` | 4% (9/205) | -3.7 pp | 80 | em_branco |
| `san1_ava_livro_de_dividas` | 17% (28/161) | -3.7 pp | 80 | — |
| `san1_ava_gota_contada` | 56% (55/98) | -5.0 pp | 80 | — |
| `san1_ava_mao_fechada` | 0% (0/100) | -2.5 pp | 80 | uso_nao_medido |
| `san1_ava_cobranca_adiada` | 48% (58/122) | +1.2 pp | 80 | — |
| `san1_ava_penhor_de_carne` | 79% (76/96) | -6.2 pp | 80 | dominante |
| `san1_ava_hipoteca_de_sangue` | 22% (12/54) | -1.2 pp | 80 | — |
| `san1_ava_execucao_da_divida` | 44% (27/61) | +2.5 pp | 80 | — |
| `san1_ava_cofre_sem_fundo` | 70% (38/54) | -2.5 pp | 80 | dominante |
| `san1_sil_fio_de_barbeiro` | 45% (42/93) | +0.0 pp | 80 | — |
| `san1_sil_veneno_vermelho` | 16% (15/95) | +0.0 pp | 80 | — |
| `san1_sil_pe_de_pluma` | 0% (0/97) | +0.0 pp | 80 | uso_nao_medido |
| `san1_sil_olho_no_pulso` | 16% (15/97) | +0.0 pp | 80 | — |
| `san1_sil_estancar_calado` | 14% (13/94) | +1.2 pp | 80 | — |
| `san1_sil_marca_de_unha` | 16% (15/97) | +0.0 pp | 80 | — |
| `san1_sil_corte_sem_aviso` | 71% (77/109) | +3.7 pp | 80 | dominante |
| `san1_sil_ponto_cego` | 47% (55/118) | -1.2 pp | 80 | — |
| `san1_sil_arterial_fina` | 60% (32/53) | +2.5 pp | 80 | dominante |
| `san1_sil_silencio_cobrado` | 60% (32/53) | +0.0 pp | 80 | dominante |
| `san1_sil_cirurgia_sem_testemunha` | 46% (22/48) | +0.0 pp | 80 | — |
| `san1_sil_ultima_gota` | 67% (32/48) | +1.2 pp | 80 | dominante |

Bandeiras de **uso** no protocolo (dominante = uso > 60%, em_branco = uso < 5%): 10 Cartas — `san1_exp_cicatriz_aberta` (dominante, 78%, +0.0 pp), `san1_exp_selo_de_dor` (dominante, 80%, -7.5 pp), `san1_exp_ultima_cortina` (dominante, 68%, -7.5 pp), `san1_ava_poupar_ferida` (em_branco, 4%, -3.7 pp), `san1_ava_penhor_de_carne` (dominante, 79%, -6.2 pp), `san1_ava_cofre_sem_fundo` (dominante, 70%, -2.5 pp), `san1_sil_corte_sem_aviso` (dominante, 71%, +3.7 pp), `san1_sil_arterial_fina` (dominante, 60%, +2.5 pp), `san1_sil_silencio_cobrado` (dominante, 60%, +0.0 pp), `san1_sil_ultima_gota` (dominante, 67%, +1.2 pp).

**Leitura (honesta)**: nenhum `delta` passa de ±8 pp (todos dentro do ruído), então nenhuma Carta é dominante *em resultado*. As bandeiras são só de taxa de uso, e a taxa é insensível ao dano: reduzi o dano de 8 dessas Cartas em 1–2 pontos e o uso não se moveu (ex.: `san1_exp_selo_de_dor` 80% → 70% → de volta a 80% ao restaurar). O bot joga qualquer golpe da mão que caiba no Fôlego e ordena por `dano_base`, então numa Postura de dano o limiar de 60% pega os golpes mais fortes do baralho por construção. **Não tuniei poder para lavar a bandeira**; devolvo ao coordenador/SPEC-336 decidir se o limiar de uso vale para golpes de uma Postura de dano. `san1_ava_poupar_ferida` (`em_branco`) é cura de emergência: o bot só cura abaixo de 50% de Vitalidade.

Histórico: a 1ª versão deste relatório (arena antiga, braço “sem” contaminado) mostrava deltas de até −20 pp; o delta era ruído de ordem de baralho, não efeito das Cartas. Os ajustes de poder feitos para “mover o delta” (Arterial Fina, Silêncio Cobrado, Credencial) não tinham base e foram desfeitos ou refeitos pelos achados P1/P2 da revisão Sol.

## Limitações da arena

- O bot ordena pelo `dano_base` do efeito principal; Sangria, Marca, Eco, Ressoar, Chamado, Provocar, `ao_receber_dano` e cura condicional não pesam na decisão: para eles o único freio é o orçamento (`fx.budget_error`).
- Reações (`san1_exp_aplauso_de_ferro`, `san1_ava_mao_fechada`, `san1_sil_pe_de_pluma`) saem `uso_nao_medido`: o bot não as declara.
- Com 80 lutas, 1 luta = 1,25 pp: delta entre ±9 pp é ruído.
