# SPEC-335 — arena do Lote 3 (Devoto do Abismo, onda 1)

> Gerado a partir de `docs/spec335/sim-lote3-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote3.sh`.

**Protocolo** (`--protocolo lote`, `sim.py` corrigido do Lote 2): cada Carta isolada (as irmãs do lote fora do catálogo), ao `level_req`, encontro padrão, 20 sementes = 80 lutas por braço, braços pareados. 1 luta = 1,25 pp; ±9 pp é ruído.

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `dev1_con_cinza_no_peito` | 24% (28/119) | +1.2 pp | 80 | — |
| `dev1_con_veu_de_incenso` | 93% (107/115) | +7.5 pp | 80 | dominante |
| `dev1_con_cajado_votivo` | 93% (110/118) | +6.2 pp | 80 | dominante |
| `dev1_con_uncao_curta` | 10% (12/120) | +2.5 pp | 80 | — |
| `dev1_con_selo_contra_o_abismo` | 0% (0/120) | +1.2 pp | 80 | uso_nao_medido |
| `dev1_con_postura_de_oracao` | 26% (32/121) | +2.5 pp | 80 | — |
| `dev1_con_marca_votiva` | 47% (55/116) | +2.5 pp | 80 | — |
| `dev1_con_cicatriz_votiva` | 37% (61/166) | +7.5 pp | 80 | — |
| `dev1_con_bencao_do_aco` | 54% (81/151) | +11.2 pp | 80 | dominante |
| `dev1_con_hora_canonica` | 44% (32/72) | +3.7 pp | 80 | — |
| `dev1_con_missa_fechada` | 14% (10/71) | +2.5 pp | 80 | — |
| `dev1_con_sacramento_do_vazio` | 59% (36/61) | -1.2 pp | 80 | — |
| `dev1_zel_mao_na_frente` | 46% (52/114) | +1.2 pp | 80 | — |
| `dev1_zel_dedo_apontado` | 39% (46/117) | +0.0 pp | 80 | — |
| `dev1_zel_mao_no_peito` | 43% (52/120) | -1.3 pp | 80 | — |
| `dev1_zel_ciume_subito` | 0% (0/117) | -1.3 pp | 80 | uso_nao_medido |
| `dev1_zel_anteparo_ciumento` | 0% (0/117) | -1.3 pp | 80 | uso_nao_medido |
| `dev1_zel_olhar_fixo` | 14% (16/115) | -1.3 pp | 80 | — |
| `dev1_zel_zelo_em_brasa` | 14% (16/117) | -1.3 pp | 80 | — |
| `dev1_zel_ciume_aberto` | 57% (85/149) | +13.7 pp | 80 | dominante |
| `dev1_zel_ninguem_toca` | 38% (60/159) | -1.3 pp | 80 | — |
| `dev1_zel_ferro_antes_do_ferro` | 74% (50/68) | +6.2 pp | 80 | dominante |
| `dev1_zel_corpo_entre` | 20% (13/66) | +1.3 pp | 80 | — |
| `dev1_zel_ninguem_mais` | 48% (30/62) | +7.5 pp | 80 | — |
| `dev1_enl_braco_de_chumbo` | 43% (54/125) | +1.3 pp | 80 | — |
| `dev1_enl_pranto_lento` | 47% (55/117) | +2.5 pp | 80 | — |
| `dev1_enl_nome_repetido` | 67% (76/114) | +1.3 pp | 80 | dominante |
| `dev1_enl_consolo_da_lembranca` | 7% (24/357) | -2.5 pp | 80 | — |
| `dev1_enl_rosto_do_morto` | 0% (0/131) | +2.5 pp | 80 | uso_nao_medido |
| `dev1_enl_ler_o_luto` | 43% (54/125) | -1.2 pp | 80 | — |
| `dev1_enl_nome_gravado` | 59% (82/140) | +8.7 pp | 80 | dominante |
| `dev1_enl_consolo_roubado` | 38% (60/156) | +7.5 pp | 80 | — |
| `dev1_enl_peso_dos_ausentes` | 48% (32/67) | +2.5 pp | 80 | — |
| `dev1_enl_luto_que_aquece` | 30% (20/67) | +12.5 pp | 80 | dominante |
| `dev1_enl_cortejo_de_cinzas` | 48% (32/67) | +2.5 pp | 80 | — |
| `dev1_enl_missa_dos_ausentes` | 6% (4/67) | -1.3 pp | 80 | — |

**Leitura (honesta)**

- Bandeiras de **uso** (`dominante` por uso > 60 %, `em_branco`) são artefato do bot (joga todo golpe/proteção barato da mão por ordem de `dano_base`), como registrado na revisão Sol do Lote 2; **não mexi no poder para sumi-las**. Reações saem `uso_nao_medido` (o bot não as declara): `dev1_con_selo_contra_o_abismo`, `dev1_zel_ciume_subito`, `dev1_zel_anteparo_ciumento`, `dev1_enl_rosto_do_morto`.
- Quatro Cartas passaram de +8 pp no protocolo (80 lutas). Conferi cada uma com **sementes 20–99 (320 lutas por braço)**, mesmo protocolo (`sim-lote3-confirmacao-sementes20-99.json`, quando a Carta era a versão inicial):

| Carta | 80 lutas | 320 lutas (sementes 20–99) | decisão |
|---|---|---|---|
| `dev1_con_bencao_do_aco` | +16,2 pp | **+13,8 pp** (efeito real, > 3 erros-padrão) | `frequencia` `turno` → `cena` (igual à irmã `dev1_zel_ciume_aberto`: dano 4 + efeito de guarda, uma vez por cena). Depois: +11,2 pp (80) e **+8,4 pp** (320 lutas, ≈ 2 EP; limiar da bandeira é 8). Mantida: o nível-base de L4 vence só 38 %, qualquer golpe de 4 pesa muito. |
| `dev1_zel_ciume_aberto` | +13,7 pp | +7,2 pp | abaixo do limiar com amostra maior; **não alterada** |
| `dev1_enl_luto_que_aquece` | +12,5 pp | +3,7 pp | ruído; **não alterada** |
| `dev1_enl_nome_gravado` | +8,7 pp | +5,3 pp | ruído; **não alterada** |

  Também conferidas (perto de +8): `dev1_con_cicatriz_votiva` +6,6, `dev1_con_veu_de_incenso` +2,8, `dev1_zel_ninguem_mais` +4,4, `dev1_enl_consolo_roubado` +1,9 pp — todas sem bandeira de delta.
- Cartas com bandeira no relatório final: `dev1_con_veu_de_incenso` (dominante, 93%, +7.5 pp); `dev1_con_cajado_votivo` (dominante, 93%, +6.2 pp); `dev1_con_bencao_do_aco` (dominante, 54%, +11.2 pp); `dev1_zel_ciume_aberto` (dominante, 57%, +13.7 pp); `dev1_zel_ferro_antes_do_ferro` (dominante, 74%, +6.2 pp); `dev1_enl_nome_repetido` (dominante, 67%, +1.3 pp); `dev1_enl_nome_gravado` (dominante, 59%, +8.7 pp); `dev1_enl_luto_que_aquece` (dominante, 30%, +12.5 pp).
- Taxa de vitória por Postura não medida aqui (R8 é do conjunto das 5 Posturas).

## Limitações da arena

- O bot ordena pelo `dano_base` do principal; Vigília, Taunt, Marca, Torpor, Rachadura, gatilhos `ao_receber_dano`/`ao_aliado_sofrer`/`inicio_rodada`/`ao_derrubar` e cura condicional não pesam na decisão: o freio é o orçamento (`fx.budget_error`, todas dentro da faixa).
- Reações não são declaradas pelo bot; efeitos que dependem de aliado (`ao_aliado_sofrer`, Provocar entre vários alvos) não aparecem em luta solo — por isso nenhuma Carta tem Provocar como único ganho.
