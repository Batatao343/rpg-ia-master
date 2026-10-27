# SPEC-335 — arena do Lote 6 (40 neutras de Valoria + 16 Cartas de tronco, R2/R6)

> Gerado a partir de `docs/spec335/sim-lote6*.json`. Reproduzir: `bash scripts/dev/py.sh docs/spec335/arena_neutras_lote6.py` (40 neutras x 2 baralhos), `... --seed-from 20 --seeds 80 --only <ids>` (confirmação) e `bash scripts/dev/py.sh docs/spec335/confirmar_tronco_lote6.py` (tronco por subclasse). O `sim.py` sai com 1 quando há bandeira; estes scripts não.

## Como as neutras foram medidas

As neutras **não pertencem a uma Postura** (`classe: Neutra`), e o `sim.py` monta o baralho pela `classe` da Carta. Cada neutra virou, só na simulação, uma **variante** com a `classe`/`subclasse` de dois baralhos de Posturas diferentes e rodou o protocolo de lote do `sim.py` (Carta isolada, `level_req`, encontro padrão, 20 sementes = 80 lutas por braço, braços pareados, o mesmo bot de baralho completo):

- **Devoto do Abismo / consagrado**: corpo a corpo, Vigília, golpes marciais (baralho com armadura).
- **Arcanista Cinzento / calibrado**: sem armadura, mão/Vazão, golpes leves fracos (baralho que mais depende de uma Carta de apoio).

Nada da variante é gravado: o catálogo real continua com `classe: Neutra`. 1 luta = 1,25 pp; ±9 pp é ruído nas 80 lutas. Delta perto de +8 pp foi **confirmado com as sementes 20–99** (320 lutas por braço): 13 Cartas.

## Resultado das 40 neutras

Colunas: taxa de uso quando na mão / delta de vitória (pp) em 80 lutas, por baralho; depois o delta em 320 lutas (Devoto / Arcanista) quando confirmado.

| Carta | Devoto: uso / delta (pp) | Arcanista: uso / delta (pp) | 320 lutas (20-99) D / A | bandeiras |
|---|---|---|---|---|
| `neu1_na_espada_da_legiao` | 68% / -2.5 | 65% / +5.0 | - | dominante |
| `neu1_na_fuligem_das_chamines` | 69% / -3.8 | 62% / +1.2 | - | dominante |
| `neu1_na_gazua_dos_telhados` | 68% / -7.5 | 63% / +0.0 | - | dominante |
| `neu1_na_salvo_conduto_falso` | 68% / -1.3 | 64% / +1.2 | - | dominante |
| `neu1_na_selo_da_legiao` | 31% / +3.8 | 35% / -2.5 | - | - |
| `neu1_na_elixir_do_doutor_vane` | 23% / -1.2 | 29% / +1.3 | - | - |
| `neu1_na_lembranca_do_aco` | 26% / -2.5 | 47% / -5.0 | - | - |
| `neu1_er_lanca_de_gancho` | 27% / -6.2 | 49% / -2.5 | - | - |
| `neu1_er_traje_branco` | 29% / -3.8 | 26% / +6.2 | +0.0 / +3.4 | - |
| `neu1_er_aguardente_de_liquen` | 10% / -6.2 | 10% / +10.0 | +0.6 / +4.7 | dominante |
| `neu1_er_luvas_de_veia_de_calor` | 14% / -6.2 | 24% / +2.5 | - | - |
| `neu1_er_emboscada_dos_renegados` | 41% / +1.3 | 44% / +6.3 | +0.6 / +7.2 | - |
| `neu1_er_machado_de_vorr` | 60% / +2.5 | 72% / -6.2 | - | dominante |
| `neu1_er_cerco_do_branco` | 12% / +1.2 | 42% / +0.0 | - | - |
| `neu1_br_sabre_de_pirata` | 66% / -2.5 | 68% / +10.0 | +0.9 / +7.2 | dominante |
| `neu1_br_grogue_do_porto` | 69% / -6.2 | 64% / +6.2 | +1.6 / +4.4 | dominante |
| `neu1_br_tinta_de_polvo` | 27% / -6.2 | 48% / -1.3 | - | - |
| `neu1_br_madeira_de_naufragio` | 29% / -2.5 | 26% / +6.2 | +0.3 / +3.7 | - |
| `neu1_br_arpao_de_osso` | 56% / +0.0 | 57% / +7.5 | +2.8 / +5.0 | - |
| `neu1_br_doce_de_mare` | 23% / -1.2 | 29% / +0.0 | - | - |
| `neu1_br_pistola_de_pederneira` | 26% / -1.2 | 47% / -5.0 | - | - |
| `neu1_ka_residuo_sanguineo` | 27% / -6.2 | 48% / +6.2 | -0.6 / +5.6 | - |
| `neu1_ka_divida_gravada` | 27% / -5.0 | 50% / +1.2 | - | - |
| `neu1_ka_guarda_de_sangue` | 31% / -2.5 | 37% / +1.3 | +2.5 / +7.2 | - |
| `neu1_ka_equilibrio_de_kahen` | 12% / -1.2 | 12% / -1.3 | - | - |
| `neu1_ka_xadrez_com_lyss` | 17% / -6.2 | 10% / +1.3 | - | - |
| `neu1_sb_pedagio_de_sangue` | 74% / -3.8 | 66% / +1.2 | - | dominante |
| `neu1_sb_martelo_de_guerra_anao` | 58% / -2.5 | 53% / +5.0 | - | - |
| `neu1_sb_corda_de_aranha` | 71% / -1.3 | 64% / +7.5 | +2.8 / +3.1 | dominante |
| `neu1_sb_emboscada_de_gruumsha` | 37% / +1.3 | 40% / +1.3 | - | - |
| `neu1_sb_pavor_do_fundo` | 32% / +0.0 | 26% / -8.8 | -0.9 / -5.0 | - |
| `neu1_sb_reliquia_arma_ana` | 26% / -2.5 | 47% / -5.0 | - | - |
| `neu1_ge_lanterna_de_aranha` | 28% / -6.2 | 63% / -2.5 | - | dominante |
| `neu1_ge_talisma_de_lebre` | 0% / -6.2 | 0% / +2.5 | - | uso_nao_medido |
| `neu1_ge_flecha_de_cristal` | 27% / -6.2 | 49% / -2.5 | - | - |
| `neu1_ge_nectar_da_furia` | 57% / +2.5 | 60% / +5.0 | -0.3 / +6.3 | dominante |
| `neu1_ge_armadura_de_quitina` | 31% / +0.0 | 33% / -5.0 | - | - |
| `neu1_ge_cataplasma_de_resina` | 14% / +6.2 | 18% / +0.0 | +3.4 / +6.3 | - |
| `neu1_ge_lamina_de_vidro_negro` | 12% / +1.2 | 42% / +2.5 | - | - |
| `neu1_ge_ampulheta_de_vaelorn` | 12% / -3.7 | 19% / +2.5 | - | - |

Bandeiras de uso (`dominante` por uso > 60 %) = artefato do bot; ver Leitura.

## Leitura (honesta)

- **Nenhum delta real acima de +8 pp.** Na 1ª passada (80 lutas) três Cartas passaram de +8 no Arcanista: `neu1_br_sabre_de_pirata` (+10,0), `neu1_er_aguardente_de_liquen` (+10,0) e `neu1_ka_guarda_de_sangue`; a confirmação com 320 lutas derrubou as duas primeiras para +7,2 e +4,7 (ruído). **`neu1_ka_guarda_de_sangue` era real**: +13,1 pp no Arcanista (sem armadura, Proteção + Sangria vale muito). Ajuste: Proteção 3 → 2 e Sangria 2 → 1; medida de novo com 320 lutas: Devoto +2,5 / Arcanista **+7,2 pp**, abaixo de +8, no mesmo patamar do Sabre e da Emboscada dos Renegados (+7,2). Nas 13 confirmadas (320 lutas) o maior delta é +7,2; as outras 27 não passaram de +6,2 nas 80 lutas.
- **Bandeiras só de uso (`dominante` por uso > 60 %, `em_branco`, `uso_nao_medido`) = artefato do bot**, como nos Lotes 3–5: o bot de baralho completo joga tudo o que é barato e está na mão, então Cartas de Fôlego 0–1 sem custo real passam de 60 % sem mudar o resultado (delta ≈ 0 em `neu1_na_fuligem_das_chamines`, `neu1_na_gazua_dos_telhados`, `neu1_sb_pedagio_de_sangue`, `neu1_sb_corda_de_aranha`). `neu1_ge_talisma_de_lebre` (reação) é `uso_nao_medido`: o bot não declara reações; o motor a joga e `buff_esquiva` em reação é o caso suportado.
- **Defensivas/suporte com delta negativo** (`neu1_sb_pavor_do_fundo` −8,8 no Arcanista, −5,0 em 320 lutas) não são bandeira (follow-up da 336: bandeira `fraca`, bot que defende antes de ser ferido).
- **Ampulheta de Vaelorn** (abissal, só chefe) saiu de `copiar_ultima` para `cura 8 + ganhar_folego 2` (Exaurir, Entropia 4): `tests/test_mecanica_orfa.py` exige um teste de efeito para cada par `tipo:kind`, e `card:ativa:copiar_ultima` não tinha (as `copiar_ultima` existentes são do Improvisador, de outro tipo). Com a troca, `em_branco` do Arcanista (0 %) virou +2,5 pp / uso 19 %.
- **Limitação (a de sempre):** as neutras com efeitos secundários (Rachadura, Torpor, Sangria, `empurrao`) têm poder que a arena só mede pelo delta de vitória; o orçamento é o freio. `revelar`, `comprar`, `ganhar_folego` e `marca` (Dívida Gravada) não são medidos pelo dano.

## As 16 Cartas de tronco (R6)

O R6 (`tests/test_card_variety.py`) exige, em cada faixa de nível, por Postura **e por subclasse**, ≥ 10 Cartas, ≥ 4 `kind`s e ≥ 3 palavras-chave. Antes do Lote 6 o teste falhava em **todas as 5 Posturas no nível 1–2**: o Acervo desses níveis é só o **tronco** (a subclasse é escolhida no nível 3) e o tronco legado tem 10–12 Cartas **sem nenhuma palavra-chave** (0 de 3). Em níveis mais altos várias subclasses também ficavam a 1–2 palavras-chave de distância (o tronco novo as cobre). Preenchimento: **16 Cartas de tronco** (3 por Postura, 4 no Arcanista) em `data/cards/posturas/<postura>_tronco.json` (ids `*_tro_*`, comuns, nível 1, sem subclasse, `onda: 1`), cada uma cobrindo uma palavra-chave da roda da Postura que o tronco não tinha:

- Devoto: Vigília, Interromper, Rachadura · Sangromante: Sacrifício, Sangria, Eco · Corruptor: Rachadura, Torpor, Marca do Abismo · Arcanista: Ressoar, Guardar, `comprar`, Interromper · Médico: Guardar, Torpor, Vigília.

Todas passam no lint sem avisos e no orçamento, e cada uma foi jogada no motor (`ct.resolve_turn`) pelo mesmo bot da arena. Arena **por subclasse** (variante com cada uma das 3 subclasses; sem subclasse o `sim.py` mistura as três no braço "sem", o braço fica fraco e infla o delta: `arc1_tro_centelha_ressoante` deu +26,2 pp em 80 lutas e +11,2 em 320 assim, e +2,5 a +5,0 por subclasse):

| Carta de tronco | subclasse 1 | subclasse 2 | subclasse 3 | 320 lutas (20-99) | bandeiras |
|---|---|---|---|---|---|
| `arc1_tro_centelha_ressoante` | calibrado: 52% / +2.5 | descoberto: 24% / +5.0 | improvisador: 58% / +2.5 | +5.0 / +5.0 / +2.8 | - |
| `arc1_tro_marca_de_giz` | calibrado: 29% / -6.2 | descoberto: 32% / -6.2 | improvisador: 23% / -8.7 | +2.5 / +1.2 / -2.8 | - |
| `arc1_tro_lance_calculado` | calibrado: 27% / -5.0 | descoberto: 5% / -2.5 | improvisador: 21% / -8.7 | +1.9 / +1.2 / -0.6 | - |
| `arc1_tro_contrassinal` | calibrado: 68% / +1.2 | descoberto: 73% / +1.3 | improvisador: 67% / +1.3 | +5.6 / +5.9 / +2.8 | dominante |
| `cor1_tro_fresta_no_osso` | biologia: 16% / -1.2 | alma: 13% / -3.8 | inorganica: 32% / -3.7 | +0.0 / -1.2 / +0.9 | - |
| `cor1_tro_peso_na_alma` | biologia: 16% / -1.2 | alma: 13% / -3.8 | inorganica: 32% / -2.5 | +0.0 / +0.3 / +1.6 | - |
| `cor1_tro_sinal_do_abismo` | biologia: 16% / +1.3 | alma: 13% / -2.5 | inorganica: 32% / +1.2 | +0.0 / +0.9 / +1.2 | - |
| `dev1_tro_vigilia_de_cinza` | consagrado: 16% / -3.8 | zeloso: 20% / +1.2 | enlutado: 28% / -3.8 | +2.5 / +1.6 / -0.6 | - |
| `dev1_tro_palavra_que_corta` | consagrado: 47% / +2.5 | zeloso: 57% / +3.7 | enlutado: 64% / +2.5 | +1.9 / +5.6 / +1.6 | dominante |
| `dev1_tro_dedo_de_sentenca` | consagrado: 30% / -6.2 | zeloso: 48% / -2.5 | enlutado: 35% / -2.5 | -0.3 / +1.9 / -2.2 | - |
| `med1_tro_faixa_bem_dada` | cirurgiao_trincheira: 8% / -5.0 | boticario: 8% / +0.0 | cirurgiao_ferro: 8% / +1.2 | -2.2 / +1.6 / +0.6 | - |
| `med1_tro_dose_de_torpor` | cirurgiao_trincheira: 46% / -6.2 | boticario: 49% / -2.5 | cirurgiao_ferro: 39% / +0.0 | -2.5 / +3.1 / +0.0 | - |
| `med1_tro_plantao_curto` | cirurgiao_trincheira: 34% / -8.7 | boticario: 31% / -5.0 | cirurgiao_ferro: 30% / -1.3 | -0.6 / +3.1 / -0.3 | - |
| `san1_tro_corte_de_penitencia` | exposto: 72% / -3.8 | avaro: 74% / -2.5 | silencioso: 74% / -2.5 | -3.1 / -1.6 / -1.6 | dominante |
| `san1_tro_veia_aberta` | exposto: 35% / +0.0 | avaro: 36% / -2.5 | silencioso: 28% / -1.3 | -0.9 / -0.6 / +1.2 | - |
| `san1_tro_eco_de_ferida` | exposto: 63% / +0.0 | avaro: 64% / -2.5 | silencioso: 53% / -1.3 | -1.9 / -0.9 / +0.0 | dominante |
