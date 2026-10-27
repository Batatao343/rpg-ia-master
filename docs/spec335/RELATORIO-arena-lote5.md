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
| `med1_tri_golpe_e_pulso` | 36% (56/157) | +6.2 pp | 80 | — |
| `med1_tri_sedar_e_remendar` | 28% (28/99) | -3.7 pp | 80 | — |
| `med1_tri_hospital_de_lona` | 24% (20/84) | +5.0 pp | 80 | — |
| `med1_tri_pulso_emprestado` | 20% (11/56) | +10.0 pp | 80 | dominante |
| `med1_bot_emplasto_espesso` | 65% (121/187) | +2.5 pp | 80 | dominante |
| `med1_bot_sal_na_sombra` | 56% (82/147) | +2.5 pp | 80 | — |
| `med1_bot_po_nos_olhos` | 54% (82/151) | -2.5 pp | 80 | — |
| `med1_bot_visco_de_raiz` | 57% (82/145) | +0.0 pp | 80 | — |
| `med1_bot_gota_de_veneno` | 62% (82/132) | +1.3 pp | 80 | dominante |
| `med1_bot_giz_vermelho` | 58% (82/141) | +0.0 pp | 80 | — |
| `med1_bot_frasco_aos_pes` | 0% (0/183) | -3.7 pp | 80 | uso_nao_medido |
| `med1_bot_antidoto_de_cinza` | 32% (46/145) | -1.2 pp | 80 | — |
| `med1_bot_agulha_envenenada` | 39% (55/141) | +17.5 pp | 80 | dominante |
| `med1_bot_amargo_forte` | 47% (36/77) | +2.5 pp | 80 | — |
| `med1_bot_fumigacao_geral` | 21% (15/71) | +1.2 pp | 80 | — |
| `med1_bot_elixir_imperfeito` | 18% (12/67) | +5.0 pp | 80 | — |
| `med1_fer_tala_rigida` | 52% (83/160) | +1.2 pp | 80 | — |
| `med1_fer_lente_de_protese` | 56% (83/149) | +3.7 pp | 80 | — |
| `med1_fer_pistao_de_campo` | 39% (57/145) | +0.0 pp | 80 | — |
| `med1_fer_cravo_na_junta` | 56% (83/147) | +3.7 pp | 80 | — |
| `med1_fer_garra_de_protese` | 54% (97/180) | +3.7 pp | 80 | — |
| `med1_fer_placa_no_peito` | 0% (0/189) | +1.2 pp | 80 | uso_nao_medido |
| `med1_fer_cotovelo_de_aco` | 46% (71/156) | +11.2 pp | 80 | dominante |
| `med1_fer_armadura_de_campo` | 32% (55/170) | +6.2 pp | 80 | — |
| `med1_fer_pinca_de_aco` | 47% (71/152) | +8.7 pp | 80 | dominante |
| `med1_fer_braco_de_colosso` | 36% (30/83) | +6.2 pp | 80 | — |
| `med1_fer_ancora_de_ferro` | 33% (29/89) | +8.8 pp | 80 | dominante |
| `med1_fer_cirurgia_no_ferro` | 26% (19/73) | +7.5 pp | 80 | — |

## Taxa de vitória da POSTURA, antes x depois (pedido do coordenador)

`bash scripts/dev/py.sh docs/spec335/arena_postura_medico.py 20` (mesmo bot e mesma arena de `docs/spec336/arena_folego_full.py`: baralho COMPLETO da Postura, `sim.full_deck` + `sim.fight`, Fôlego 2, mão 5; L1/L3/L5 x padrão/elite x 4 criaturas x 20 sementes = 480 lutas por linha). "Antes" = as 36 Cartas fora do catálogo; "depois" = catálogo completo. Só o Médico muda. **Medida de novo depois da revisão Sol** (híbridos, Giz e Tala em `cena`).

| Baralho | total antes → depois | só padrão antes → depois | L5 padrão | L5 elite |
|---|---|---|---|---|
| todas as subclasses (não é baralho de jogador) | 46,5 % → 63,1 % | 54,6 % → 75,0 % | 14 % → 66 % | 5 % → 26 % |
| `cirurgiao_trincheira` | 50,6 % → 56,7 % | 60,8 % → **64,2 %** | 24 % → 34 % | 9 % → 10 % |
| `boticario` | 48,7 % → 53,5 % | 55,8 % → **63,7 %** | 11 % → 42 % | 7 % → 9 % |
| `cirurgiao_ferro` | 51,9 % → 54,4 % | 57,5 % → **67,1 %** | 14 % → 42 % | 5 % → 11 % |

**Alvo da revisão (≤ 70 % só padrão por subclasse): cumprido** (64,2 / 63,7 / 67,1 %; antes da revisão o Ferro estava em 73,3 %). Nenhuma subclasse piora no total. Elite em L5 continua fraco (9–26 %), o que o `off` da 328 já era; é do encontro. Limitação (Sol, P2-3, follow-up 336): dentro do mesmo tier o `full_deck` escolhe pela ordem alfabética do id, então "antes x depois" mede "o lote preenche o baralho", não "o melhor baralho possível".

## Leitura (honesta)

- **Bandeiras de uso são artefato do bot** (joga todo golpe/efeito barato da mão por ordem de `dano_base`): `dominante` em suportes baratos com delta de -1 a +5 pp; não mexi no poder para sumi-las. Reações saem `uso_nao_medido` (o bot não as declara): `tri_respiro_forcado`, `bot_frasco_aos_pes`, `fer_placa_no_peito`.
- **Os 4 híbridos de golpe eram fortes de verdade e passaram para `cena`** (P1-1 da revisão; precedente da Bênção do Aço, Lote 3). A versão `turno` ficava 7,5 a 16,3 pp acima do controle de só dano da mesma subclasse (a explicação "braço base fino" que eu dera antes foi refutada: o controle de dano 3 sobe só +0,3/+5,6 pp). `agulha_envenenada` também perdeu 1 rodada de DoT (2 → 1). Com **sementes 20–99 (320 lutas por braço)**, `sim-lote5-confirmacao-sementes20-99.json`, controles de só dano na MESMA subclasse e mesmo dano:

| Carta | delta | controle (`turno`, só dano) | sobra |
|---|---|---|---|
| `tri_golpe_e_pulso` (dano 3 leve) | +4,1 | +5,6 | -1,5 |
| `bot_agulha_envenenada` (dano 3 leve, DoT 1) | +6,2 | +0,3 | +5,9 (delta ≤ +8) |
| `fer_cotovelo_de_aco` (dano 4 marcial) | +4,1 | +10,0 | -5,9 |
| `fer_pinca_de_aco` (dano 4 marcial) | +5,9 | +10,0 | -4,1 |

  O protocolo (sementes 0–19) ainda mostra `agulha` +17,5, `cotovelo` +11,2 e `pinca` +8,7 pp: com 80 lutas o braço base oscila (±9 pp); a confirmação com 320 lutas é a que vale.
- **Outros deltas altos no protocolo, conferidos com 320 lutas**: `tri_pulso_emprestado` +10,0 → **+1,6**; `fer_ancora_de_ferro` +8,8 → **+2,5**; `fer_cirurgia_no_ferro` +4,1; `tri_pancada_de_cabo` +3,1.
- **Cura em luta solo vale.** Toda Carta de cura é `cura` primário sem `alvo`, que cai no escolhido ou em si mesmo; `purga_condicao`, `reduzir_carga_aliado` e a `protecao` idem. Cura em aliado só vale com aliados: `estabilizar` aparece **só** em `tri_hospital_de_lona`, junto de `cura`. O bot cura abaixo de 50 %; o baralho do Médico ganha 8 Cartas de `cura` primária.
- **Fôlego 0 só com `cena`** (P2-1): 11 comuns de controle/buff pagas só em Entropia, uma vez por cena; `tala_rigida` e `giz_vermelho` (eram `turno`, 90 % e 87 % de uso: efeito grátis todo turno) passaram para `cena`. A Entropia quase não pesa (o jogador a ganha ao sofrer dano), então o freio é a frequência e o orçamento, não a Entropia. Teste novo recusa Fôlego 0 fora de `cena`.
- **Giz Vermelho com `duracao: 2`** (P1-2, só a parte do lote): controle com `duracao` 1 expira no tick do início do turno do inimigo (bug de motor anterior, spec própria). Lint provisório `controle_duracao` recusa `taunt`/`marca` com duracao < 2 em Carta de onda; as 9 Cartas dos Lotes 2–3 que violam ficam numa lista provisória (`CONTROLE_DURACAO_PENDENTES`), não alteradas.
- Cartas de controle (Torpor, Vantagem, Marca, Cego, Enredado, Exposto, Desarme, Medo, empurrão) e `reduzir_carga_aliado` não são medidas pela arena: o freio é o orçamento (`fx.budget_error`, todas dentro da faixa).

## Verificação no motor real (fora da arena)

Cada uma das 36 Cartas foi jogada por `ct.resolve_turn` (alvo aliado e alvo si mesmo, "luta solo") e as 3 reações por `_resolve_reaction_effect`: o efeito aplicado confere com o texto gerado. Achados do próprio lote, corrigidos antes do lint final:

- **Condição de estatística repetida na mesma Carta é engolida.** `protecao`, `buff_defesa`, `buff_acerto`, `buff_dano`, `vantagem`, `dot` e `marca` criam a condição com o NOME da Carta; um segundo no mesmo alvo vira "condição renovada" e some. `fer_braco_de_colosso` (acerto + dano) e `fer_ancora_de_ferro` (proteção + defesa) perdiam o 2º efeito; viraram dano + Vigília e proteção + Vigília + Torpor. `tests/test_card_acervo_reparo.py` recusa mais de uma dessas por Carta.
- **Efeito principal de kind legado ignora `alvo`**: `alvo: aliados` só vale em efeito extra (o principal vai para o alvo escolhido). Nenhuma Carta do lote usa área no principal; o teste recusa.
- **Reações de Médico**: só entraram as que valem sozinho (`cura` em si, `buff_defesa` em si, `Medo` no atacante); `aliado_cai`/`ao_aliado_ser_atacado` (legadas) só disparam com aliado.
- **`reduzir_carga_aliado` gasta 2 de Entropia a mais** (custo interno do motor, mesmo sem Carga a tirar). Correção de motor (P2-2) **tentada e revertida**: não cobrar sem Carga muda o resultado de `med_bot_purga` legada no teste de equivalência das 308 (`test_equivalencia_das_308_cartas_legadas_contra_o_motor_anterior`), o que a condição do coordenador proíbe. Fica para a 325/336 junto do texto gerado ("custa 2 de Entropia", que também mexeria no snapshot da 330). A `descricao` de `bot_sal_na_sombra` diz que a Entropia do Médico paga a conta, haja Carga ou não. Em luta solo ele purga a Carga do próprio Médico.

## Limitações da arena

- O bot ordena pelo `dano_base` do principal; Rachadura, Torpor, Marca, condições, DoT e cura condicional não pesam na decisão. Reações não são declaradas. O baralho é o "completo" do `sim.full_deck` (ordenado por tier e id), que não é uma escolha do jogador: o delta de uma Carta mede "esta Carta no lugar da mais fraca", não o melhor baralho possível.
- Taxa de vitória por Postura fora de L1/L3/L5 e de padrão/elite não foi medida.
