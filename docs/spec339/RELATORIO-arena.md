# SPEC-339 — Relatório de arena (R15)

Dados brutos: `arena-antes.json` (motor da `main` 23d69e4e) e `arena-depois.json` (motor corrigido);
gerados por `docs/spec339/arena_spec339.py run <antes|depois>` e este texto por `... report`.
Protocolo de lote (20 sementes, encontro padrão) em 12 arquivos de Postura; default (níveis 1,3,5, 4 sementes)
nas Cartas com controle dos arquivos legados; arena por Postura (baralho completo, L1/L3/L5, padrão+elite,
4 criaturas, 20 sementes); encontros por categoria (D5). **Nenhum número de Carta mudou (R16).**

## Viés de ordem do `full_deck` (critério herdado da 335)

`sim.full_deck` desempatava o tier por `id`, e `*1_` (onda 1) vence os legados (`'1' < '_'`). Corrigido em
`scripts/cards/sim.py`: o desempate no tier é um hash estável de (Postura, subclasse, nível, id). Os dois
braços (antes/depois do motor) usam o mesmo baralho, então o delta é só do motor. A coluna "335" não é
comparável ao resto (outro baralho).

| Postura / subclasse | 335 (full_deck viesado, motor antigo) padrão | 339 deck sem viés, motor antigo | 339 deck sem viés, motor corrigido | faixa 45–75 % |
|---|---|---|---|---|
| Devoto do Abismo / todas | 77.1 | 74.2 | 70.4 | ok |
| Devoto do Abismo / consagrado | 76.7 | 76.2 | 75.0 | ok |
| Devoto do Abismo / zeloso | 69.6 | 70.0 | 70.8 | ok |
| Devoto do Abismo / enlutado | 71.7 | 72.9 | 71.7 | ok |
| Sangromante / todas | 80.0 | 77.5 | 77.9 | ACIMA |
| Sangromante / exposto | 79.2 | 75.8 | 70.4 | ok |
| Sangromante / avaro | 80.0 | 79.2 | 78.7 | ACIMA |
| Sangromante / silencioso | 81.7 | 80.0 | 79.6 | ACIMA |
| Corruptor / todas | 52.5 | 58.3 | 58.3 | ok |
| Corruptor / biologia | 66.2 | 64.2 | 63.7 | ok |
| Corruptor / alma | 44.6 | 54.2 | 53.3 | ok |
| Corruptor / inorganica | 53.7 | 60.0 | 60.0 | ok |
| Arcanista Cinzento / todas | 55.8 | 60.8 | 60.0 | ok |
| Arcanista Cinzento / calibrado | 58.8 | 62.9 | 62.5 | ok |
| Arcanista Cinzento / descoberto | 50.8 | 59.6 | 59.6 | ok |
| Arcanista Cinzento / improvisador | 54.2 | 67.9 | 68.8 | ok |
| Médico de Campo / todas | 75.0 | 61.3 | 63.3 | ok |
| Médico de Campo / cirurgiao_trincheira | 64.2 | 62.5 | 62.1 | ok |
| Médico de Campo / boticario | 63.7 | 65.0 | 65.0 | ok |
| Médico de Campo / cirurgiao_ferro | 67.1 | 69.2 | 70.4 | ok |

Leitura: com o viés removido, Devoto cai (77,1 → 74,2 % no motor antigo) e Corruptor/alma sobe (44,6 → 54,2 %):
o "34 % com elite" da 335 era em parte artefato de ordem. Faixa 45–75 % (leitura "padrão"): ver coluna final.
Fora da faixa só o Sangromante (todas, avaro e silencioso passam de 75 %); Devoto/zeloso sai de 77 para 70,8 %.
A faixa **não** foi tocada e nenhuma Carta foi alterada; o ajuste de poder é spec de balanceamento (R16).


Mesmas sementes nos dois lados; só o motor muda. Nenhum número de Carta foi alterado (R16).

## Variação de vitória por Postura/subclasse (baralho completo, L1/L3/L5)

| Postura / subclasse | padrão antes | padrão depois | Δ pp | total antes | total depois | Δ pp |
|---|---|---|---|---|---|---|
| Devoto do Abismo / todas | 74.2 | 70.4 | -3.8 | 64.0 | 61.3 | -2.7 |
| Devoto do Abismo / consagrado | 76.2 | 75.0 | -1.2 | 66.2 | 66.2 | +0.0 |
| Devoto do Abismo / zeloso | 70.0 | 70.8 | +0.8 | 58.8 | 58.1 | -0.7 |
| Devoto do Abismo / enlutado | 72.9 | 71.7 | -1.2 | 61.5 | 60.8 | -0.7 |
| Sangromante / todas | 77.5 | 77.9 | +0.4 | 65.0 | 65.6 | +0.6 |
| Sangromante / exposto | 75.8 | 70.4 | -5.4 | 61.5 | 58.3 | -3.2 |
| Sangromante / avaro | 79.2 | 78.7 | -0.5 | 66.5 | 66.0 | -0.5 |
| Sangromante / silencioso | 80.0 | 79.6 | -0.4 | 66.9 | 66.2 | -0.7 |
| Corruptor / todas | 58.3 | 58.3 | +0.0 | 46.7 | 46.9 | +0.2 |
| Corruptor / biologia | 64.2 | 63.7 | -0.5 | 54.2 | 53.7 | -0.5 |
| Corruptor / alma | 54.2 | 53.3 | -0.9 | 43.8 | 43.3 | -0.5 |
| Corruptor / inorganica | 60.0 | 60.0 | +0.0 | 51.5 | 51.5 | +0.0 |
| Arcanista Cinzento / todas | 60.8 | 60.0 | -0.8 | 47.7 | 47.3 | -0.4 |
| Arcanista Cinzento / calibrado | 62.9 | 62.5 | -0.4 | 51.5 | 51.0 | -0.5 |
| Arcanista Cinzento / descoberto | 59.6 | 59.6 | +0.0 | 45.4 | 45.4 | +0.0 |
| Arcanista Cinzento / improvisador | 67.9 | 68.8 | +0.9 | 54.4 | 54.8 | +0.4 |
| Médico de Campo / todas | 61.3 | 63.3 | +2.0 | 50.4 | 51.9 | +1.5 |
| Médico de Campo / cirurgiao_trincheira | 62.5 | 62.1 | -0.4 | 54.0 | 53.5 | -0.5 |
| Médico de Campo / boticario | 65.0 | 65.0 | +0.0 | 55.4 | 55.6 | +0.2 |
| Médico de Campo / cirurgiao_ferro | 69.2 | 70.4 | +1.2 | 60.6 | 61.3 | +0.7 |

## Cartas com maior variação (|Δ| >= 3 pp no delta de vitória) e bandeiras

| Carta | classe | delta antes (pp) | delta depois (pp) | variação | uso antes→depois | bandeiras antes → depois |
|---|---|---|---|---|---|---|
| `dev1_con_cicatriz_votiva` | Devoto do Abismo | +11.2 | +16.2 | +5.0 | 33%→33% | dominante → dominante |
| `dev1_zel_dedo_apontado` | Devoto do Abismo | -2.5 | +1.2 | +3.7 | 51%→55% | - → - |
| `dev1_zel_mao_no_peito` | Devoto do Abismo | -2.5 | +1.2 | +3.7 | 67%→68% | dominante → dominante |
| `dev1_zel_ciume_aberto` | Devoto do Abismo | +0.0 | +7.5 | +7.5 | 55%→55% | - → - |
| `dev1_zel_ferro_antes_do_ferro` | Devoto do Abismo | -5.0 | -8.8 | -3.8 | 42%→42% | - → - |
| `san1_ava_juros_do_primeiro` | Sangromante | -2.5 | +1.3 | +3.8 | 41%→40% | - → - |
| `san1_exp_selo_de_dor` | Sangromante | -1.3 | -5.0 | -3.7 | 74%→74% | dominante → dominante |
| `san1_exp_bis_de_cicatriz` | Sangromante | +8.8 | +7.5 | -1.3 | 33%→32% | dominante → - |
| `cor1_alm_culpa_antiga` | Corruptor | +6.2 | +11.2 | +5.0 | 44%→44% | - → dominante |
| `cor1_alm_corredor_sem_eco` | Corruptor | +0.0 | +0.0 | +0.0 | 5%→5% | em_branco → - |
| `cor1_alm_nome_apagado` | Corruptor | +0.0 | +3.7 | +3.7 | 14%→14% | - → - |
| `cor1_tro_peso_na_alma` | Corruptor | +0.0 | -3.7 | -3.7 | 30%→29% | - → - |
| `arc1_des_caldeira_sem_fundo` | Arcanista Cinzento | +3.7 | +7.5 | +3.8 | 62%→59% | dominante → - |
| `med1_bot_amargo_forte` | Médico de Campo | +5.0 | +8.8 | +3.8 | 63%→63% | dominante → dominante |
| `dev_cons_marca` | Devoto do Abismo | -6.2 | -2.1 | +4.1 | 72%→72% | dominante → dominante |
| `dev_zel_ciume` | Devoto do Abismo | +0.0 | +4.2 | +4.2 | 31%→27% | - → - |
| `dev_zel_possessao` | Devoto do Abismo | +6.2 | +12.5 | +6.3 | 17%→20% | - → - |
| `dev_zel_interdito` | Devoto do Abismo | +6.2 | +12.5 | +6.3 | 9%→6% | - → - |
| `san_exp_espetaculo` | Sangromante | +2.1 | +8.3 | +6.2 | 39%→37% | - → dominante |
| `san_exp_aplausos` | Sangromante | +25.0 | +18.8 | -6.2 | 0%→0% | em_branco → em_branco |
| `san_sil_fio` | Sangromante | +0.0 | +6.2 | +6.2 | 0%→0% | em_branco → em_branco |
| `cor_alm_eco` | Corruptor | +12.5 | +6.2 | -6.3 | 0%→0% | em_branco → em_branco |
| `med_marca_triagem` | Médico de Campo | -12.5 | -6.2 | +6.3 | 17%→12% | - → - |
| `arc_imp_grampo` | Arcanista Cinzento | -6.2 | +6.2 | +12.4 | 21%→21% | - → - |

**Bandeira `dominante` NOVA (2):** `cor1_alm_culpa_antiga`, `san_exp_espetaculo`

**Bandeira `dominante` que SUMIU (2):** `san1_exp_bis_de_cicatriz`, `arc1_des_caldeira_sem_fundo`

## Encontros contra baralhos de inimigo (D5, só medir) — herói L3, baralho completo

| Postura | categoria | antes | depois | Δ pp |
|---|---|---|---|---|
| Devoto do Abismo | lacaio | 65.0 | 65.0 | +0.0 |
| Devoto do Abismo | padrao | 82.5 | 82.5 | +0.0 |
| Devoto do Abismo | elite | 62.5 | 62.5 | +0.0 |
| Devoto do Abismo | chefe | 67.5 | 70.0 | +2.5 |
| Sangromante | lacaio | 72.5 | 72.5 | +0.0 |
| Sangromante | padrao | 70.0 | 70.0 | +0.0 |
| Sangromante | elite | 47.5 | 47.5 | +0.0 |
| Sangromante | chefe | 62.5 | 62.5 | +0.0 |

## Limites e observações

- O bot de arena joga solo (sem aliado): a Provocação não tem a quem redirecionar, então o ganho de Provocar
  aparece no teste de motor (`tests/test_spec339_duracao_condicoes.py`, com aliado), não na taxa de vitória.
  O smoke "Provocar efetivo > 0" por arena não se aplica a este bot; a prova é o teste com rng forçado.
- Encontros por categoria (D5): quase nulos porque o bot ataca sempre o primeiro vivo e poucas Cartas de
  inimigo com `taunt`/`marca` entram na rotação; só `chefe` do Devoto mexeu (+2,5 pp, 40 lutas).
- Cartas de onda escritas com `duracao: 2` só para escapar do lint (R14): `dev1_zel_*`/`san1_*` dos Lotes 1–3 ficaram
  em `CONTROLE_DURACAO_PENDENTES` (9 ids, sem alteração) e o Giz Vermelho (Médico, Lote 5) foi para `duracao: 2`.
  Nada foi mexido aqui; rever na 335/336.
- Ruído: a 20 sementes e 4 criaturas, 1 luta = 1,25 pp; variações abaixo de ~4 pp não são sinal.
