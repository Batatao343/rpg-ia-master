# SPEC-335 — arena do Lote 4 (Corruptor, onda 1)

> Gerado a partir de `docs/spec335/sim-lote4-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote4.sh` (o `sim.py` sai com 1 quando há bandeira; o script não aborta por isso).

**Protocolo** (`--protocolo lote`, `sim.py` corrigido do Lote 2): cada Carta isolada (as irmãs do lote fora do catálogo), ao `level_req`, encontro padrão, 20 sementes = 80 lutas por braço, braços pareados. 1 luta = 1,25 pp; ±9 pp é ruído.

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `cor1_bio_mofo_quente` | 31% (35/113) | +0.0 pp | 80 | — |
| `cor1_bio_febre_lenta` | 12% (14/114) | +1.2 pp | 80 | — |
| `cor1_bio_raiz_na_pele` | 70% (78/112) | -1.3 pp | 80 | dominante |
| `cor1_bio_ler_a_carne` | 12% (14/113) | +1.2 pp | 80 | — |
| `cor1_bio_mordida_do_bolor` | 70% (78/111) | +1.2 pp | 80 | dominante |
| `cor1_bio_pele_podre` | 0% (0/113) | +1.2 pp | 80 | uso_nao_medido |
| `cor1_bio_nariz_de_coveiro` | 9% (10/113) | +0.0 pp | 80 | — |
| `cor1_bio_carne_tenra` | 20% (26/131) | -2.5 pp | 80 | — |
| `cor1_bio_golpe_de_mofo` | 47% (34/72) | +2.5 pp | 80 | — |
| `cor1_bio_colheita_podre` | 20% (15/73) | -1.2 pp | 80 | — |
| `cor1_bio_metastase_viva` | 29% (19/66) | -3.7 pp | 80 | — |
| `cor1_bio_banquete_de_vermes` | 74% (46/62) | +7.5 pp | 80 | dominante |
| `cor1_alm_semente_de_culpa` | 26% (31/120) | +5.0 pp | 80 | — |
| `cor1_alm_sussurro_rouco` | 26% (31/120) | +3.8 pp | 80 | — |
| `cor1_alm_voz_que_falta` | 26% (31/121) | +5.0 pp | 80 | — |
| `cor1_alm_rosto_do_pavor` | 26% (31/120) | +3.8 pp | 80 | — |
| `cor1_alm_pe_no_vazio` | 26% (31/120) | +5.0 pp | 80 | — |
| `cor1_alm_ler_a_culpa` | 26% (31/120) | +3.8 pp | 80 | — |
| `cor1_alm_duvida_reflexa` | 0% (0/118) | +1.3 pp | 80 | uso_nao_medido |
| `cor1_alm_culpa_antiga` | 41% (57/138) | +2.5 pp | 80 | — |
| `cor1_alm_cerco_de_vozes` | 40% (30/74) | -6.2 pp | 80 | — |
| `cor1_alm_lembranca_errada` | 72% (51/71) | -1.3 pp | 80 | dominante |
| `cor1_alm_corredor_sem_eco` | 11% (7/66) | -5.0 pp | 80 | — |
| `cor1_alm_nome_apagado` | 11% (7/64) | +2.5 pp | 80 | — |
| `cor1_ino_ponto_fraco` | 18% (42/229) | -3.7 pp | 80 | — |
| `cor1_ino_junta_emperrada` | 28% (33/119) | +0.0 pp | 80 | — |
| `cor1_ino_estalo_de_viga` | 56% (67/119) | +1.3 pp | 80 | — |
| `cor1_ino_ler_o_metal` | 18% (42/229) | -3.7 pp | 80 | — |
| `cor1_ino_estilhaco_de_ferro` | 0% (0/126) | -3.7 pp | 80 | uso_nao_medido |
| `cor1_ino_carapaca_de_ferrugem` | 25% (32/129) | -2.5 pp | 80 | — |
| `cor1_ino_oxido_no_gume` | 25% (33/131) | +0.0 pp | 80 | — |
| `cor1_ino_peso_morto` | 25% (33/133) | +0.0 pp | 80 | — |
| `cor1_ino_estrutura_cansada` | 46% (31/67) | -6.2 pp | 80 | — |
| `cor1_ino_dobra_forcada` | 19% (13/69) | -3.7 pp | 80 | — |
| `cor1_ino_colapso_programado` | 51% (32/63) | +1.3 pp | 80 | — |
| `cor1_ino_geometria_da_ruina` | 5% (3/65) | +3.7 pp | 80 | em_branco |

**Leitura (honesta)**

- Nenhuma Carta passa de +8 pp. A maior é `cor1_bio_banquete_de_vermes` a **+7,5 pp** (80 lutas): conferida com **sementes 20–99 (320 lutas por braço)**, `sim-lote4-confirmacao-sementes20-99.json`: **−1,2 pp** (0,766 sem / 0,753 com). Era ruído; Carta não alterada. As comuns de Alma a +3,8/+5,0 pp (`cor1_alm_semente_de_culpa` conferida: **+0,9 pp** em 320 lutas) compartilham o mesmo braço base e o mesmo uso (26 %, 31/120): é o ruído do braço, não poder da Carta.
- Bandeiras de **uso** são artefato do bot (joga todo golpe/efeito barato da mão por ordem de `dano_base`), como registrado na revisão Sol do Lote 2; **não mexi no poder para sumi-las**: `dominante` em `cor1_bio_raiz_na_pele` (70 %, delta −1,3 pp), `cor1_bio_mordida_do_bolor` (70 %, +1,2 pp), `cor1_bio_banquete_de_vermes` (74 %, ver acima) e `cor1_alm_lembranca_errada` (72 %, −1,3 pp); `em_branco` em `cor1_ino_geometria_da_ruina` (5 %, 3/65 na mão: rara de Fôlego 2; o bot não pondera Rachadura/Enredado, e o delta é +3,7 pp). Reações saem `uso_nao_medido` (o bot não as declara): `cor1_bio_pele_podre`, `cor1_alm_duvida_reflexa`, `cor1_ino_estilhaco_de_ferro`.
- O braço base do Corruptor já vence muito nos níveis baixos (0,70 a 0,78 em nível 1; 0,28 a 0,74 nos níveis 4 a 15): deltas pequenos refletem a Postura forte no encontro padrão, e não Cartas fracas. Taxa de vitória por Postura não medida aqui (R8 é do conjunto das 5 Posturas).
- Cartas de controle (Rachadura, Torpor, Marca, Medo, Enredado, Silêncio, DoT) não são medidas pela arena (o bot não pondera esses efeitos): o freio é o orçamento (`fx.budget_error`, todas dentro da faixa). `Chamado` (`cor1_alm_corredor_sem_eco`, `cor1_ino_dobra_forcada`) só vale com Entropia ≥ k, que o encontro padrão não garante no nível de entrada.

## Verificação no motor real (fora da arena)

Cada uma das 36 Cartas foi jogada por `ct.resolve_turn` (suporte em si mesmo, hostis no inimigo, Mira +40) e as 3 reações por `_resolve_reaction_effect`: o efeito aplicado confere com o texto gerado. Achado do próprio lote: a Marca do Abismo é **consumida pelo dano da mesma Carta** (a versão inicial de `cor1_alm_corredor_sem_eco` tinha dano `chamado` depois da Marca e a comia no ato); a Carta virou Marca + Medo + Torpor (Chamado), e `tests/test_card_acervo_reparo.py` recusa dano depois de Marca na mesma Carta.

## Limitações da arena

- O bot ordena pelo `dano_base` do principal; Rachadura, Torpor, Marca, condições, DoT e cura condicional não pesam na decisão. Reações não são declaradas.
