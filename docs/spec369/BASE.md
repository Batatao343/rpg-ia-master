# SPEC-369 Fase A: base das metas (sementes 0-19; famílias 0-7)

Fonte única dos números: `docs/spec369/base-0-19.json`, gerado por `docs/spec369/metricas_369.py`
(`base`, `duracao`, `uso`, `posturas`, `emboscada --base`, `pressagio`, `familias`). Offline, MockLLM,
sem LLM por rodada. A Fase B mede com esta ferramenta congelada e não a edita (R1).

## R9(a): equivalência com a 368

- `base --seeds 0-19` **não** reproduz mais `docs/spec368/metricas-0-19.json` (`equivalencia_368`
  r9/r10 = false). **Causa:** o catálogo mudou depois de 03/11. A SPEC-371 incluiu as reações iniciais
  `arc1_ini_cinza_nos_olhos`, `dev1_ini_dor_devolvida` e `med1_ini_pinca_no_tendao` (992810fa e
  82ea73dd), e a ficha inicial passou a prepará-las.
- **Prova:** tirando essas 3 Cartas do catálogo em memória e do cache de heróis
  (`metricas_369.sem_cartas`), a mesma execução reproduz r9 e r10 da 368 **byte a byte**
  (`equivalencia_368_sem_cartas_pos_368` = true/true). A ferramenta é equivalente; quem mudou foi o produto.
- Pelo R9(a), **vale a base nova** (catálogo atual), que é a da tabela abaixo. Só o Arcanista e o Médico
  se moveram. Total: 1,921 → 1,915 Cartas por rodada; vitória 64,6 → 64,8 %; R10 de +10,1 % para +10,4 %.

## As 7 metas na base

| # | Meta | Limiar (D-369-3) | Base 0-19 | Passa? |
|---|---|---|---|---|
| 1 | Cartas por rodada (R13) | total ≥ 2,00; cada Postura ≥ 1,90 | **1,915**; Devoto 1,799 · Sangromante 1,792 · Corruptor 1,864 · Arcanista 1,876 · Médico 2,100 | não |
| 2 | Dominância (R14) | (a) 0 de onda nem assinatura básica (R14d) fora do Sangromante com uso > 60 %; (b) 0 `dominante` por Δ `lote-v2` fora do Sangromante | (a) `arc1_cal_pulso_medido` 1,0, `med1_fer_lente_de_protese` 1,0 e `bas_cor_mofo` 0,607 (assinatura básica); (b) **3 legadas**: `arc_cal_valvula` +10,0 · `dev_ombro_porta` +8,8 · `dev_reflexo_bastiao` +8,7 | não |
| 3 | Duração (R15) | p95 total ≤ 10; cada Postura ≤ 12; timeouts ≤ 1,0 % | p95 **12**; Médico p95 **19** e **4,4 %** de timeout; Devoto 11 | não |
| 4 | Presságio (R16, primária D-369-2) | `on-faixa` ≤ 95 % do dano de `on-cego` (`conhecida`, decks `on`); vitória 45-85 % | **103,4 %** (13,38 × 12,94); vitória 54,1 %; 4/20 sementes abaixo do cego | não |
| 5 | `draft.py` (R12) | ≥ 3/4 no lint (lote real) | 2/4 (fonte: 387/389); a régua não mede, é o §6 item 1 | não (§6) |
| 6 | Emboscada do Corruptor (R17) | realista com crédito D-369-6 ≥ 45,0 % | **50,7 %** (`realista_369`) | **sim** |
| 7 | Famílias (R20, D-369-7) | célula-alvo termina com `on` ∈ [45, 85] e \|Δ\| ≤ 10 pp | 5 células-alvo (lista abaixo) | não |

Guardas R19 na base: toda Postura em 45-85 % (Devoto 60,2 · Sangromante 65,0 · Corruptor 51,9 ·
Arcanista 55,8 · Médico 45,8), nenhuma subclasse padrão acima de 75 % fora de `EXCECOES_TETO`, Arcanista
`todas` ≥ 45 %. A vitória agregada da `base` é 64,8 %. Esses totais são a referência do R19(b)/(d).

### Meta 2: uso > 60 % por categoria (critério literal do dono: 15 Cartas; eram 14)

| Categoria | Uso > 60 % | `dominante` por Δ (`lote-v2`) |
|---|---|---|
| básica | golpes (fallback aceito, R14d): `bas_cor_golpe`, `bas_dev_golpe`, `bas_med_golpe` · **assinatura, entra na meta (a)**: `bas_cor_mofo` (0,607) | — |
| legada (travada pelo golden, D-369-4) | `arc_des_mao_nua`, `arc_descarga`, `arc_faisca`, `cor_bio_gangrena`, `med_fer_talas` | `arc_cal_valvula`, `dev_ombro_porta`, `dev_reflexo_bastiao` |
| onda | `arc1_cal_pulso_medido` (novo), `med1_fer_lente_de_protese` | — |
| Sangromante (exceção aceita, R4a) | `bas_san_corte_raso`, `san1_ava_penhor_de_carne`, `san1_exp_selo_de_dor`, `san_sil_exato` | — |

- `arc1_imp_bomba_estopim` **não** tem bandeira na base: Δ por substituição +5,0 pp (remoção +12,5; uso
  no lote 69 %). A 362 mediu +9,4 pp no protocolo v1, que é outro protocolo. O B4 (R14b), do jeito que
  está escrito, não tem alvo.
- Os 3 `dominante` por Δ são **legadas**, e nelas só o `custo_folego` pode mudar (e só se o D-369-4
  liberar). Com o D-369-4 em "não", a meta R14(b) é inalcançável sem mexer em legada. **Decisão do
  dono** (abaixo).
- As três são **reações** (`tipo: reacao`). O bot não as declara (uso 0,0 no lote), e o Δ é por
  **remoção** (`delta_base: "remocao"`, não há referência por substituição para reação). O
  `custo_folego` de uma reação que o motor dispara sozinho pode nem mover esse Δ.

## Decomposição do R8 (Presságio; dano médio recebido por conflito, 1.800 lutas por braço)

| Conhecimento / decks | `off` | `on-cego` | `on-368` | `on-faixa` | faixa ÷ cego | faixa vs `off` |
|---|---|---|---|---|---|---|
| desconhecida / off | 11,98 (64,8 %) | 13,22 (57,1 %) | 13,22 (57,1 %) | 13,47 (52,9 %) | 1,019 | +12,4 % |
| desconhecida / on | 11,85 (66,3 %) | 12,94 (59,7 %) | 12,94 (59,7 %) | 13,18 (55,3 %) | 1,018 | +11,2 % |
| conhecida / off | 11,98 (64,8 %) | 13,22 (57,1 %) | 13,22 (57,1 %) | 13,61 (52,2 %) | 1,029 | +13,6 % |
| **conhecida / on** | 11,85 (66,3 %) | 12,94 (59,7 %) | 12,94 (59,7 %) | 13,38 (54,1 %) | **1,034** | +13,0 % |

(vitória entre parênteses)

- O +10,4 % do `on` × `off` vem **todo do motor** (intenções congeladas): `on-cego` já carrega esse
  aumento.
- O `on-368` é **idêntico** ao `on-cego` em todos os blocos. O `_heed_omen` da 368 nunca consegue
  acrescentar a defesa, porque ela não cabe no Fôlego 2 junto com as duas jogadas.
- O leitor pré-registrado (R7) **piora** o dano em 2-3 % e a vitória em 4-6 pp. Trocar um golpe de 3
  por uma guarda de 2 alonga a luta (rodadas 4,76 → 5,15) mais do que protege. Com a regra congelada,
  a informação hoje não paga a defesa. A alavanca do R16 é de conteúdo (R18a/b: custo e valor das defesas).
- A secundária (texto da 329, `on-faixa` < `off`) está em +13,0 %. Ela só vale como critério se o dono
  escolher (D-369-2).

## Meta 3: duração (braço "teto 12" é só informativo)

| Postura | p95 | timeout | % rodadas com cura | cortadas pelo teto 12 | vitória com teto 12 |
|---|---|---|---|---|---|
| Devoto | 11 | 0,3 % | 0,0 | 4,2 % | 67,8 % |
| Sangromante | 8 | 0,0 % | 2,4 | 0,6 % | 71,9 % |
| Corruptor | 9 | 0,3 % | 0,0 | 2,2 % | 61,4 % |
| Arcanista | 8 | 0,0 % | 0,0 | 1,4 % | 61,4 % |
| **Médico** | **19** | **4,4 %** | **13,3** | 13,6 % | 48,1 % |

A hipótese do §1 se confirma: o Médico cura em 13,3 % das rodadas (as outras Posturas ficam entre 0 e
2,4 %) e é a única Postura fora da meta.

## Meta 6: emboscada realista (`total`, 0-19)

| Postura | realista | com contrapartida 355 | **com crédito D-369-6** |
|---|---|---|---|
| Devoto | 61,5 % | 61,5 % | 60,2 % |
| Sangromante | 61,9 % | 61,9 % | 62,8 % |
| Corruptor | 50,7 % | 50,7 % | **50,7 %** |
| Arcanista | 52,7 % | 52,7 % | 55,8 % |
| Médico | 46,1 % | 46,5 % | 46,5 % |

O Corruptor subiu de 44,2 % (355) para 50,7 % sem Carta nova: o catálogo mudou depois da 355
(SPEC-371, Membrana Reflexa preparada etc.). A meta 6 **já passa na base**. O R17, a Carta
`buff_iniciativa` do Corruptor, continua sendo requisito de desenho ("resposta à emboscada"), mas
deixou de ser necessário para o número. **Decisão do dono** (abaixo).

## Meta 7: células de família (D-369-7, 200 lutas por célula e modo; sementes 0-7, exceto `predador_apice` L3 com 0-19)

Definição aplicada: **alvo** = `off` ∈ [45, 85] e (`on` fora da faixa **ou** \|Δ\| > 10 pp);
**fora de escopo** = `off` já fora de 45-85 %.

| Célula | `off` | `on` | Δ pp | motivo |
|---|---|---|---|---|
| `abissal` L3 | 77,0 | **86,0** | +9,0 | `on` acima de 85 |
| `conjurador` L5 | 46,5 | **36,5** | −10,0 | `on` abaixo de 45 |
| `lider_matilha` L3 | 58,0 | 70,0 | **+12,0** | \|Δ\| > 10 (fica mais fácil) |
| `lider_matilha` L5 | 68,5 | 80,0 | **+11,5** | \|Δ\| > 10 (fica mais fácil) |
| `predador_apice` L3 ⚠ | 75,0 | 58,5 | **−16,5** | \|Δ\| > 10 |

- ⚠ **Amostra ampliada (gate R9c, item 4):** `predador_apice` tem só **2 criaturas** não-chefe, e com
  as sementes 0-7 a célula tinha 80 lutas por modo (76,2 → 63,7, Δ −12,5 pp). Por decisão do dono,
  **só essa célula** foi remedida com as sementes **0-19**, o que dá **200 lutas por modo**:
  `metricas_369.py familias --seeds 0-19 --only predador_apice --levels 3`. As sementes 8-19 são
  novas para a arena de famílias; a confirmação continua nas 260-267.
- Resultado: `off` 75,0 %, `on` 58,5 %, **Δ −16,5 pp** (erro-padrão do Δ ≈ 4,5 pp). **Continua na lista
  do R20.** O `on` está dentro de 45-85 %, mas \|Δ\| > 10. O registro de 80 lutas fica em
  `familias.cells["predador_apice|L3"].amostra_original_0_7`.

- Fora de escopo (o `off` já está fora): predador L5, morto-vivo L5, bruto L5, guardião L5, apex L5,
  emboscador L5 e abissal L5.
- A lista mudou em relação ao lote 2 de 27/10 (lá o candidato era só conjurador L5). `abissal` agora tem
  criaturas no bestiário, e o catálogo de inimigos e o bestiário mudaram desde então.
- Em `lider_matilha` o `on` deixa a luta **mais fácil** que o `off`, mas dentro de 45-85 %.

## Pedido de aprovação do oráculo (gate R9c): a Fase B (B3 em diante) só começa depois disto

O dono precisa confirmar ou trocar:

1. **D-369-2.** O critério da 329 passa a ser `on-faixa` ≤ 95 % do dano de `on-cego` (`conhecida`,
   decks `on`), e o `on` × `off` fica só registrado? Na base essa razão está em 103,4 %, e a Fase B só
   tem alavanca de conteúdo para mudar isso.
2. **D-369-3.** As metas em camadas valem? Há 4 pontos novos:
   - (0) o R13 exige toda Postura ≥ 1,90, e isso inclui o **Sangromante (1,792)**. Todas as Cartas dele
     estão travadas (R4a), e a alavanca compartilhada é limitada a +2 pp de vitória (R19b). Sem
     alavanca própria, o piso pode ser **inalcançável**. O Sangromante fica no piso de 1,90 ou vira
     exceção, como no R14?
   - (a2) o R14(a) também falha pela assinatura básica `bas_cor_mofo` (0,607), que entra na meta pelo R14(d).
   - (a) o R14(b) hoje só falha por **3 legadas** (`arc_cal_valvula`, `dev_ombro_porta`,
     `dev_reflexo_bastiao`). Elas ficam como "travadas pelo golden", fora da meta, ou o D-369-4 libera
     o `custo_folego` delas? As três são reações, com uso 0 pelo bot e Δ por remoção, e o
     `custo_folego` pode não mover esse Δ.
   - (b) o B4 (`bomba_estopim`) não tem alvo na base (+5,0 pp, sem bandeira). Ele sai do plano?
3. **D-369-1 e D-369-4.** Manter o Fôlego 2 e as legadas travadas? A Etapa 0 provou que um
   `custo_folego` explícito numa legada (teste com `arc_descarga` = 2, revertido) deixa o golden e o
   snapshot da 330 verdes.
4. **D-369-7.** A lista de 5 células acima é a lista do R20? Inclui as duas de `lider_matilha`, em que
   o `on` facilita. Sobre `predador_apice` L3 (80 lutas por modo, Δ com erro-padrão de ~7 pp), três
   opções: aceitar com 80, tirar da lista, ou medir **só essa célula** com mais sementes. A escolha
   precisa sair antes de ver o efeito da Fase B.
5. **R17.** A meta 6 já passa (50,7 %). A Carta `buff_iniciativa` do Corruptor continua no B2 por
   desenho, ou sai?
   Também sobre a meta (a) do R14: a guarda básica (`bas_*_guarda`) fica fora, como o golpe básico?
   Hoje nenhuma guarda passa de 60 % de uso, então a resposta não muda nenhum número (P3-6 da Astra).
6. **Pouso da Fase B.** A revisão Sol (Etapa 8) e o `/spec-land` exigem `tests/test_spec369_metas.py`
   com **0 xfailed** nos testes R13–R20 e R18 (a Fase C fica à parte). Um xfail por artefato ausente
   bloqueia o pouso.

Até a resposta, a Fase B pode fazer só o B1 (`draft.py`) e o B2 (Corruptor), que não dependem do
oráculo (R1).
