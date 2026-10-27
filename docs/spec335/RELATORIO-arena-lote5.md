# SPEC-335 — arena do Lote 5 (Médico de Campo, onda 1)

> Gerado a partir de `docs/spec335/sim-lote5-*.json`. Reproduzir: `bash docs/spec335/rodar-protocolo-lote5.sh` (o `sim.py` sai com 1 quando há bandeira; o script não aborta por isso) e `bash scripts/dev/py.sh docs/spec335/confirmar_lote5.py`.

**Protocolo** (`--protocolo lote`, igual aos Lotes 1–4): cada Carta isolada (as irmãs do lote fora do catálogo), ao `level_req`, encontro padrão, 20 sementes = 80 lutas por braço, braços pareados. 1 luta = 1,25 pp; ±9 pp é ruído.

| Carta | uso na mão | delta de vitória | lutas | bandeiras |
|---|---|---|---|---|
| `med1_tri_remendo_rapido` | 19% (36/189) | +5.0 pp | 80 | — |
| `med1_tri_maca_erguida` | 68% (120/177) | +5.0 pp | 80 | dominante |
| `med1_tri_ordem_curta` | 56% (83/149) | +2.5 pp | 80 | — |
| `med1_tri_no_desfeito` | 55% (83/151) | +3.7 pp | 80 | — |
| `med1_tri_sedativo_seco` | 59% (83/140) | +3.7 pp | 80 | — |
| `med1_tri_pancada_de_cabo` | 42% (58/137) | +7.5 pp | 80 | — |
| `med1_tri_respiro_forcado` | 0% (0/177) | -1.2 pp | 80 | uso_nao_medido |
| `med1_tri_sutura_sob_fogo` | 17% (30/172) | +6.2 pp | 80 | — |
| `med1_tri_golpe_e_pulso` | 58% (92/159) | +16.3 pp | 80 | dominante |
| `med1_tri_sedar_e_remendar` | 28% (28/99) | -3.7 pp | 80 | — |
| `med1_tri_hospital_de_lona` | 24% (20/84) | +5.0 pp | 80 | — |
| `med1_tri_pulso_emprestado` | 20% (11/56) | +10.0 pp | 80 | dominante |
| `med1_bot_emplasto_espesso` | 65% (121/187) | +2.5 pp | 80 | dominante |
| `med1_bot_sal_na_sombra` | 56% (82/147) | +2.5 pp | 80 | — |
| `med1_bot_po_nos_olhos` | 54% (82/151) | -2.5 pp | 80 | — |
| `med1_bot_visco_de_raiz` | 57% (82/145) | +0.0 pp | 80 | — |
| `med1_bot_gota_de_veneno` | 62% (82/132) | +1.3 pp | 80 | dominante |
| `med1_bot_giz_vermelho` | 87% (164/188) | -1.2 pp | 80 | dominante |
| `med1_bot_frasco_aos_pes` | 0% (0/183) | -3.7 pp | 80 | uso_nao_medido |
| `med1_bot_antidoto_de_cinza` | 32% (46/145) | -1.2 pp | 80 | — |
| `med1_bot_agulha_envenenada` | 59% (88/149) | +22.5 pp | 80 | dominante |
| `med1_bot_amargo_forte` | 47% (36/77) | +2.5 pp | 80 | — |
| `med1_bot_fumigacao_geral` | 21% (15/71) | +1.2 pp | 80 | — |
| `med1_bot_elixir_imperfeito` | 18% (12/67) | +5.0 pp | 80 | — |
| `med1_fer_tala_rigida` | 90% (165/184) | +0.0 pp | 80 | dominante |
| `med1_fer_lente_de_protese` | 56% (83/149) | +3.7 pp | 80 | — |
| `med1_fer_pistao_de_campo` | 39% (57/145) | +0.0 pp | 80 | — |
| `med1_fer_cravo_na_junta` | 56% (83/147) | +3.7 pp | 80 | — |
| `med1_fer_garra_de_protese` | 54% (97/180) | +3.7 pp | 80 | — |
| `med1_fer_placa_no_peito` | 0% (0/189) | +1.2 pp | 80 | uso_nao_medido |
| `med1_fer_cotovelo_de_aco` | 82% (133/162) | +22.5 pp | 80 | dominante |
| `med1_fer_armadura_de_campo` | 32% (55/170) | +6.2 pp | 80 | — |
| `med1_fer_pinca_de_aco` | 80% (121/151) | +20.0 pp | 80 | dominante |
| `med1_fer_braco_de_colosso` | 36% (30/83) | +6.2 pp | 80 | — |
| `med1_fer_ancora_de_ferro` | 33% (29/89) | +8.8 pp | 80 | dominante |
| `med1_fer_cirurgia_no_ferro` | 26% (19/73) | +7.5 pp | 80 | — |

## Taxa de vitória da POSTURA, antes x depois (pedido do coordenador)

`bash scripts/dev/py.sh docs/spec335/arena_postura_medico.py 20` (mesmo bot e mesma arena de `docs/spec336/arena_folego_full.py`: baralho COMPLETO da Postura, `sim.full_deck` + `sim.fight`, Fôlego 2, mão 5; L1/L3/L5 x padrão/elite x 4 criaturas x 20 sementes = 480 lutas por linha). "Antes" = as 36 Cartas fora do catálogo; "depois" = catálogo completo. Só o Médico muda.

| Baralho | antes | depois | L5 padrão | L5 elite |
|---|---|---|---|---|
| todas as subclasses (como o alerta da 328) | 46,5 % | **63,5 %** | 14 % → 72 % | 5 % → 35 % |
| `cirurgiao_trincheira` | 50,6 % | 58,8 % | 24 % → 42 % | 9 % → 14 % |
| `boticario` | 48,7 % | 54,0 % | 11 % → 49 % | 7 % → 14 % |
| `cirurgiao_ferro` | 51,9 % | 59,0 % | 14 % → 64 % | 5 % → 23 % |

Só **padrão** (o critério "45–75 %" da §5): antes 54,6 % (todas) / 60,8 / 55,8 / 57,5 % (trincheira / boticário / ferro); depois **74,6 / 67,1 / 64,2 / 73,3 %** (a linha "todas" fica na borda de 75 %, e é ela que mistura as três subclasses; o jogador real tem uma). Nenhuma Postura sai da faixa e nenhuma subclasse piora em média; a queda do alerta ("9–16 % em L5") some em L5 padrão (11–24 % → 42–72 %). **Elite em L5 continua fraco** (14–35 %), o que o `off` da 328 já era; é do encontro, não das Cartas. Caem levemente: `boticario` L1/L3 padrão (-3/-7 lutas em 80, ruído de 1 luta = 1,25 pp, mas consistente) e `cirurgiao_ferro` L1 elite (62 → 46 em 80): os comuns de controle e reação não são decisivos para o bot, que gasta o Fôlego em golpes.

**Por que L5 sobe tanto.** O baralho do Médico no L4–L5 antes do lote era 9 básicas + `estabilizar`, `antitoxina`, `nevoa`, `purga`, `dose_choque`, `ancora`...: quase nenhuma Carta que fere ou cura de verdade (o braço "sem" vence 21–26 % em L4). Os incomuns híbridos (golpe que também cura/protege/envenena) trazem dano ao baralho; o resto da subida vem de cura primária e proteção, que o bot joga abaixo de 50 %/75 % da Vitalidade.

## Leitura (honesta)

- **Bandeiras de uso são artefato do bot** (joga todo golpe/efeito barato da mão por ordem de `dano_base`): `dominante` em `med1_tri_maca_erguida` (68 %), `med1_bot_emplasto_espesso` (65 %), `med1_bot_gota_de_veneno` (62 %), `med1_bot_giz_vermelho` (87 %) e `med1_fer_tala_rigida` (90 %) com delta de -1,2 a +5,0 pp: são Cartas baratas de suporte que o bot joga com a sobra de Fôlego; **não mexi no poder para sumi-las**. Reações saem `uso_nao_medido` (o bot não as declara): `tri_respiro_forcado`, `bot_frasco_aos_pes`, `fer_placa_no_peito`.
- **Deltas de 4 Cartas passam de +15 pp e são do braço base fino, não só da Carta.** `golpe_e_pulso`, `agulha_envenenada`, `cotovelo_de_aco` e `pinca_de_aco` entram em L4, onde o baralho do Médico vence 21–26 % (não tem golpe). Confirmei com **sementes 20–99 (320 lutas por braço)**, `sim-lote5-confirmacao-sementes20-99.json`, com **dois controles sintéticos de só dano** (sem sustento, mesmo custo, `level_req` 4): `dano 4` = **+10,0 pp** e `dano 5` = **+16,2 pp**. As quatro Cartas: +15,0 / +16,6 / +20,0 / +17,5 pp, ou seja, 0 a 10 pp acima do controle de dano equivalente (a diferença é o sustento, pequeno por desenho). Antes da confirmação eu **tirei poder**: `golpe_e_pulso` de dano 4 marcial para dano 3 leve (+25,6 → +15,0 pp), `cotovelo_de_aco` de 5 para 4 (+23,8 → +20,0) e `agulha_envenenada` com o DoT de 3 para 2 rodadas (+19,7 → +16,6). Registrado e aceito: o Médico precisa de dano no baralho para ser viável, e é isso que o delta mede.
- **Deltas perto de +8 pp, conferidos com 320 lutas**: `tri_pancada_de_cabo` +7,5 → **+3,1 pp**; `tri_pulso_emprestado` +10,0 → **+1,6 pp** (uso 8 %); `fer_ancora_de_ferro` +8,8 → **+2,5 pp**; `fer_cirurgia_no_ferro` +7,5 → **+4,1 pp**. Eram ruído do braço. `tri_sutura_sob_fogo` (+6,2) fica abaixo do limiar.
- **Cura em luta solo vale.** Toda Carta de cura é `cura` primário sem `alvo`, que cai no escolhido ou em si mesmo; `purga_condicao`, `reduzir_carga_aliado` e a `protecao` idem. Cura em aliado só vale com aliados: `estabilizar` aparece **só** em `tri_hospital_de_lona`, junto de `cura`; sozinho seria Carta morta em solo. O bot cura abaixo de 50 %; o baralho do Médico ganha 8 Cartas de `cura` primária.
- **Fôlego 0 em 11 comuns de controle/buff** (`ordem_curta`, `no_desfeito`, `sedativo_seco`, `sal_na_sombra`, `po_nos_olhos`, `visco_de_raiz`, `gota_de_veneno`, `giz_vermelho`, `tala_rigida`, `lente_de_protese`, `cravo_na_junta`): uma vez por cena (ou por turno), pagas só em Entropia, para o Fôlego (o recurso escasso) ficar para golpe e cura. O orçamento da faixa comum/Fôlego 0 (`[0, 7]`) as cobre.
- Cartas de controle (Torpor, Vantagem, Marca, Cego, Enredado, Exposto, Desarme, Medo, empurrão) e `reduzir_carga_aliado` não são medidas pela arena (o bot não pondera esses efeitos): o freio é o orçamento (`fx.budget_error`, todas dentro da faixa).

## Verificação no motor real (fora da arena)

Cada uma das 36 Cartas foi jogada por `ct.resolve_turn` (alvo aliado e alvo si mesmo, "luta solo") e as 3 reações por `_resolve_reaction_effect`: o efeito aplicado confere com o texto gerado. Achados do próprio lote, corrigidos antes do lint final:

- **Condição de estatística repetida na mesma Carta é engolida.** `protecao`, `buff_defesa`, `buff_acerto`, `buff_dano`, `vantagem`, `dot` e `marca` criam a condição com o NOME da Carta; um segundo no mesmo alvo vira "condição renovada" e some. `fer_braco_de_colosso` (acerto + dano) e `fer_ancora_de_ferro` (proteção + defesa) perdiam o 2º efeito; viraram dano + Vigília e proteção + Vigília + Torpor. `tests/test_card_acervo_reparo.py` recusa mais de uma dessas por Carta.
- **Efeito principal de kind legado ignora `alvo`**: `alvo: aliados` só vale em efeito extra (o principal vai para o alvo escolhido). Nenhuma Carta do lote usa área no principal; o teste recusa.
- **Reações de Médico**: só entraram as que valem sozinho (`cura` em si, `buff_defesa` em si, `Medo` no atacante); `aliado_cai`/`ao_aliado_ser_atacado` (legadas) só disparam com aliado.
- **`reduzir_carga_aliado` gasta 2 de Entropia a mais** (custo interno do motor, mesmo sem Carga a tirar); as descrições de `bot_sal_na_sombra` e das raras dizem que a Entropia do Médico paga a conta. Em luta solo ele purga a Carga do próprio Médico.

## Limitações da arena

- O bot ordena pelo `dano_base` do principal; Rachadura, Torpor, Marca, condições, DoT e cura condicional não pesam na decisão. Reações não são declaradas. O baralho é o "completo" do `sim.full_deck` (ordenado por tier e id), que não é uma escolha do jogador: o delta de uma Carta mede "esta Carta no lugar da mais fraca", não o melhor baralho possível.
- Taxa de vitória por Postura fora de L1/L3/L5 e de padrão/elite não foi medida.
