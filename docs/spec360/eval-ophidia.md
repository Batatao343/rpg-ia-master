# SPEC-360 — eval da fauna viva: Ophidia

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `ophidia` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.9845 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2471 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7615 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4734 | ≤ 0.6 | ok |
| M4 território | 1.0 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.3734 | -0.2 a +0.05 | FALHOU |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 453 | 456 | 725 |

Combates por 100 ações: off 15.062 · on 9.438.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"mon_cobra_de_sangria": 0.2471, "mon_doente_de_encomenda": 0.2471, "mon_lagarto_espirrador": 0.2471, "mon_moreia_vulcanica": 0.1871, "mon_nadador_escaldado": 0.24, "mon_oraculo_coral": 0.24, "mon_os_que_voltaram_e_nao_eram_eles": 0.1871, "mon_ossada_de_pomes": 0.2268, "mon_puxado_do_oeste": 0.24, "mon_remora_de_conves": 0.2471, "mon_sereia_de_ophidia": 0.2041, "mon_tatuzinho_de_afogado": 0.1871, "mon_trepano_de_borda": 0.2471, "mon_vela_sem_barco": 0.2141, "mon_vigia_de_cor_errada": 0.24}
- M3 presa sobe por predador: {"mon_caranguejo_cinza": 1.7615, "mon_escorpena_de_basalto": 1.8312, "mon_leviata_caldeira": 1.784, "mon_moreia_vulcanica": 1.8232, "mon_sereia_de_ophidia": 1.8087, "mon_tatuzinho_de_afogado": 1.8605, "mon_vela_sem_barco": 1.763}
- M3 predador cai: {"mon_caranguejo_cinza": 0.4573, "mon_escorpena_de_basalto": 0.4444, "mon_moreia_vulcanica": 0.4632, "mon_sereia_de_ophidia": 0.4629, "mon_tatuzinho_de_afogado": 0.4634, "mon_vela_sem_barco": 0.4734}
- M4 contextos com candidata territorial: 5

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 1. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.9845 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.9845 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2471 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7615 · cai 0.4734 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 1 nó raiz na região: não há 'fora do território' | ≥ 0.8 | N/A |
| M5 por região (informativo, D5) | -0.3734 | alerta fora de -0.3 a +0.1 | ALERTA |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `6b67774de752653b` × `6b67774de752653b` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2569 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 453 · precedidos (oráculo próprio): 446 · (antigo): 446.
- Divergências: só o antigo conta 0 · só o próprio conta 0.
- Textos de sinal emitidos: 1233 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1233 de 4800.
- Gatilhos off = on (R9 da 360): ok.
