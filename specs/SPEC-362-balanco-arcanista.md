# SPEC-362 — Balanço do Arcanista Cinzento pós-SPEC-355 (piso de 45 % com folga; exceções do Sangromante definitivas)

> **Status:** `in-progress`
> **Criada:** 2026-11-01 · **Atualizada:** 2026-11-01
> **Épico:** SPEC-327
> **Depende de:** SPEC-341 (`done`: protocolo de balanço, `arena_spec341.py` congelado, inventário de controle), SPEC-355 (código na `main`: R11 utilitárias fora da compra, R12 Cartas 2d6 fora do pool, R17 contrapartida de emboscada; `EXCECOES_PISO`/`EXCECOES_TETO` em `tests/test_spec355_arena.py`).
> **Desbloqueia:** remover a exceção de piso do Arcanista (`tests/test_spec355_arena.py:13`); fechar a pendência de balanço da SPEC-355 §9 antes de ligar as Cartas (`on`).
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` (mecânica e integridade da arena) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato com evidência · **[H]** hipótese a confirmar na Etapa 0 · **[D]** decisão (§8).

---

## 1. Contexto & Objetivo

[F] A SPEC-355 fechou com o **Arcanista Cinzento abaixo do piso de 45 %** na leitura total (padrão+elite):

| medição | Arcanista `todas` (total) | fonte |
|---|---|---|
| pós-B, sementes 0–19 | 46,5 % | `docs/spec355/RELATORIO.md:11` |
| A1 = final (R11+R12), 0–19 | 44,4 % | `docs/spec355/RELATORIO.md:11` |
| confirmação 20–99 (Arpoador antigo) | **43,9 %** | `docs/spec355/RELATORIO.md:11`, `:23` |
| 0–19 depois da correção do bestiário | **44,4 %** | `docs/spec355/arena-bestiario-0-19.json:414` |
| emboscada realista, 0–19 | 42,1 % | `specs/SPEC-355-cartas-pendencias-abertas.md:555` |

O teste de artefato da 355 deixa o Arcanista passar por uma exceção explícita, `EXCECOES_PISO = {"Arcanista Cinzento"}` (`tests/test_spec355_arena.py:11-13`). O comentário dessa linha diz que ela sai com a spec de balanço do Arcanista. É esta.

[F] A queda veio do bloco A1 da 355 (−2,1 pp; `docs/spec355/RELATORIO.md:11`), que mexeu em duas coisas ao mesmo tempo:

- **R11:** utilitárias saem da compra no conflito e vão para `fora_do_conflito` (`services/card_piles.py:175-188`);
- **R12:** as quatro Cartas 2d6 saem do pool. Uma delas é do Arcanista: `raio_cinza` (`data/cards/exemplos.json:223-236`, `dano` `2d6`, tier 1, `level_req` 1).

A 355 atribui a queda principalmente ao R11. [H] O mecanismo provável: utilitária tem efeito `kind: utilitaria`, sem efeito de combate (`data/cards/arcanista.json:57-71`), e o bot nunca a joga (`scripts/cards/sim.py:175-191` só joga cura, defesa, ataque e suporte). Na compra, ela era carta morta, mas alongava o monte e atrasava o reembaralho, e cada reembaralho põe 1 Fardo no monte (`services/card_piles.py:201-207`). Fora da compra, o monte encurta e os Fardos chegam antes. Ao mesmo tempo, a utilitária continua ocupando vaga no baralho da arena, porque `sim.full_deck` filtra por `cards._DECK_TIPOS`, que inclui `utilitaria` (`scripts/cards/sim.py:93-97`, `services/cards.py:437`). A parte que cabe ao R12 (`raio_cinza`) nunca foi medida em separado. A Etapa 0 separa as duas.

[F] A única recalibração que a 355 tentou foi 1 passo em 1 Carta (`arc1_imp_bomba_estopim` dano 4→5). Esse passo moveu só o L5, em ±1 luta, e foi revertido (`docs/spec355/RELATORIO.md:14-17`). A atribuição da 355 tem duas limitações (`docs/spec355/atribuicao-arcanista.json`):

- mede **só a leitura padrão** (`docs/spec341/arena_spec341.py:59-64`, `_padrao_level`), mas o critério é o total. Hoje a fraqueza está no elite: `todas` tem padrão 59,2 % e elite 29,6 %, e L5 elite fica em 14/80 (`arena-bestiario-0-19.json:405-416`);
- dá 0,0 para a maioria das Cartas de onda, porque elas não entram no baralho `todas` (corte por `DECK_MAX`, `sim.py:104-114`).

Os deltas positivos de onda são pequenos: `bomba_estopim` L5 +7,5, `truque` L5 +6,2, `carretel` L3 +5,1, `pulso_medido` L1 +3,8. Duas Cartas têm delta **negativo**, ou seja, o baralho vence mais sem elas: `arc1_des_garganta` (L3 −4,9) e `arc1_des_brasa` (L3 −2,5) (`atribuicao-arcanista.json:362-376`).

[F] A revisão Sol da 355 apontou um problema: a confirmação 20–99 e a emboscada foram medidas com o Arpoador Osshari **antigo**, e esses JSON não foram regerados (`SPEC-355 §9`, linha 571). Por isso esta spec **parte de uma base nova**, medida na `main` atual. Os números da 355 servem só de referência.

[F] Subclasses do Arcanista (total/padrão, 0–19, `arena-bestiario-0-19.json:418-510`):

| subclasse | total | padrão |
|---|---|---|
| calibrado | 55,4 % | 67,5 % |
| descoberto | **40,6 %** | 54,2 % |
| improvisador | 55,8 % | 68,8 % |

O braço `todas` (sub `""`) é um baralho próprio, que mistura as três subclasses (`services/cards.py:319`). Não é a média delas. O gate de piso lê só esse braço (`tests/test_spec355_arena.py:47-50`).

**Pedido do dono (01/11):** "melhora um pouco o Arcanista, o Sangromante pode deixar como está."

**Objetivo:**

- Arcanista `todas` no total **≥ 46,5 % nas sementes 0–19** (folga sobre 45) e **≥ 45,0 % na confirmação 20–99**;
- nenhuma subclasse do Arcanista acima de 75 % na leitura padrão;
- as outras quatro Posturas com células idênticas à base (seguem dentro de 45–85 %);
- tudo isso mexendo só em número e custo de **até 3 Cartas de onda do Arcanista**, com até 2 passos cada;
- `EXCECOES_PISO` some;
- as exceções de teto do Sangromante (`EXCECOES_TETO`) passam a ser registradas como **aceitas em definitivo** pelo dono.

Princípio: mecânica é Python. O avaliador, o orçamento e o golden ficam congelados, e as Cartas legadas não mudam.

## 2. Requisitos

### Integridade (valem para todas as etapas)

- **R1 — Avaliador congelado.** Saem desta spec byte-idênticos à `main`:
  - `scripts/cards/sim.py`;
  - `docs/spec335/arena_posturas.py`;
  - `docs/spec341/arena_spec341.py`;
  - `docs/spec355/arena_spec355.py`;
  - `data/cards/_orcamento.json`;
  - `tests/spec330_equivalence.py`;
  - `tests/fixtures/spec330_legacy_golden.json`;
  - `tests/fixtures/spec330_card_text_snapshot.json`;
  - `tests/test_card_sim.py`;
  - `tests/test_spec341_balanco.py`.

  Os limiares (`sim.py:48-54`), o `PROTOCOLO_LOTE`, a faixa 45–85 % (total por Postura) e o teto de 75 % (padrão por subclasse) também não mudam. Prova: `git diff --exit-code main -- <caminhos>` no pouso. Se uma mudança de protocolo parecer necessária, o executor para e registra a decisão para o dono, sem aplicar.
- **R2 — Legadas intactas.** Nenhuma das Cartas legadas muda. Prova: `git diff --exit-code main -- data/cards/{devoto,sangromante,corruptor,medico,arcanista,basicas,bestiario,exemplos,exemplos_extra,tiers_5_plus}.json`, e `tests/test_card_effects_grammar.py` e `tests/test_spec341_balanco.py::test_legadas_intactas` verdes sem regenerar nada. `raio_cinza` continua fora do pool (R12 da 355).
- **R3 — Sementes de ajuste × confirmação.** O ajuste usa só as sementes **0–19**. As sementes **20–99** rodam **uma vez**, depois do commit do pacote final. Ajustar o número de uma Carta até ela passar nas 20–99 é proibido. Se a confirmação falhar, o executor registra e devolve, sem reajustar.
- **R4 — Escopo do Sangromante e da 341.** Nenhuma Carta do Sangromante muda. Se alguma Carta alterada nesta spec tiver id presente em `docs/spec341/arena-final.json["versoes"]` ou `docs/spec341/arena-confirmacao.json["versoes"]`, o executor **para e devolve** (D17 da 355). Hoje nenhum id do Arcanista está nessas listas (`docs/spec341/arena-final.json:6-…`, só Sangromante, Giz e Dívida), então isso não deve acontecer. O teste do R14 trava a regra.

### Base nova (Etapa 0)

- **R5 — Base nova na `main` atual.** Rodar `bash scripts/dev/py.sh docs/spec355/arena_spec355.py base --seeds 0:20 --out docs/spec362/arena-base-0-19.json` (5 Posturas, todas as subclasses, níveis 1/3/5, padrão+elite).
  - Comparar célula a célula com `docs/spec355/arena-bestiario-0-19.json` e registrar o diff em `docs/spec362/RELATORIO.md`. Divergir **não** bloqueia (o catálogo ou o bestiário podem ter mudado depois da 355): a base nova vale e a causa provável da divergência vai para o relatório.
  - Se o Arcanista `todas` já estiver ≥ 46,5 % na base, nenhuma Carta muda. A spec segue direto para a confirmação (Etapa 5) e para os R12/R13.
  - **Não** rodar a base nas 20–99. A held-out fica limpa até a confirmação (R3).
- **R6 — Decomposição R11 × R12 (diagnóstico).** Novo `docs/spec362/arena_spec362.py`, subcomando `decompor`. Mede o Arcanista (`todas` e as 3 subclasses), sementes 0–19, em três braços, **no mesmo processo** e com monkeypatch restaurado no `finally`. Nenhum arquivo muda.
  - (a) catálogo atual;
  - (b) com `raio_cinza` de volta ao pool: `cards.EXEMPLO_FORA_DO_POOL` sem esse id;
  - (c) com as utilitárias do Arcanista de volta à compra: `card_piles.start_piles` com o comportamento anterior ao R11, só para Cartas de `classe == "Arcanista Cinzento"`.

  O resultado vai para `docs/spec362/decomposicao-0-19.json` e para uma tabela no relatório. É ferramenta de diagnóstico e não vira critério nem alavanca. O braço (c) é a medição da alternativa do R11, que se aplica só por decisão do dono (D4).
- **R7 — Atribuição na leitura total.** Subcomando `atribuicao` do `arena_spec362.py`, que **importa** `arena_posturas.run_arm`, `sim.full_deck` e `sim.fight` sem modificá-los. Para cada Carta (de onda e legada; as legadas só para informação) presente em `sim.full_deck("Arcanista Cinzento", L, sub)` com L ∈ {1, 3, 5} e sub ∈ {`""`, `calibrado`, `descoberto`, `improvisador`}:
  - tirar a Carta do catálogo como em `sim.build_arms` (`sim.py:319-331`), remontar o baralho e medir a taxa **total** (padrão+elite) e a padrão, sementes 0–19;
  - gravar `{card_id: {sub: {"L1": Δpp, "L3": Δpp, "L5": Δpp, "total": Δpp, "padrao": Δpp, "no_baralho": [níveis]}}}` em `docs/spec362/atribuicao-0-19.json`.

  Uso por Carta (na mão × jogada) vem de `seen` em `sim.full_deck_decl` (`sim.py:134-142`), passado pelo `fight` (`sim.py:214`). Com a atribuição, o relatório lista as Cartas de onda candidatas: as que **estão no baralho `todas`** em ao menos um nível, ordenadas por Δ total. O relatório também destaca as Cartas com Δ negativo (o baralho vence mais sem elas), que são as mais baratas de corrigir com buff.

### Pacote do Arcanista

- **R8 — Alavancas permitidas.** Só número e custo, no mesmo objeto, em Cartas de onda do Arcanista (`data/cards/posturas/arcanista_cinzento_{tronco,calibrado,descoberto,improvisador}.json`):
  - **+1** em `dano_base` ou `valor` de um efeito;
  - **−1** em `custo_folego` ou `custo_entropia` (mínimo 0);
  - um degrau de `frequencia` no sentido mais livre (`cena` → `turno` → `livre`).

  "Passo" = uma dessas mudanças. Cada Carta recebe **no máximo 2 passos**, iguais ou diferentes, e o pacote tem **no máximo 3 Cartas**.

  **Não** valem: `tier`, `level_req`, `patamar` e `raridade`, porque mudam quem entra no baralho da arena (341 R4); `kind`, palavras-chave e efeitos novos ou removidos; e `duracao` de `taunt`/`marca`, que o inventário `ONDA_CONTROLE` da 341 trava (`arc1_imp_parafuso`/`arame` em 2 por desenho, `specs/SPEC-341-balanco-sangromante.md:152-153`).
- **R9 — Toda Carta alterada:**
  - tem `versao` = (versão na `main`) + 1, uma única subida mesmo com 2 passos (`docs/guias/CARTAS.md:70`, `:99`);
  - fica dentro da faixa do orçamento: `fx.budget_error(card) is None`. Buff pode estourar o **teto** da faixa (`services/card_effects.py:1688-1699`). Passo que estoura o orçamento é inválido e não conta;
  - passa em `card_lint` sem avisos e em `bash scripts/dev/py.sh scripts/validate_content.py` com 0 erros;
  - mantém `descricao` e `momento` coerentes. Se a `descricao` mudar, entra `nota_voz` em `data/cards/_ondas.yaml`.
- **R10 — Escolha e ordem.**
  1. As Cartas saem do R7, entre as de onda do Arcanista presentes no baralho `todas` (é o braço do gate). Primeiro as de maior uso com Δ total ≤ 0, que são cartas jogadas e fracas. Depois, as de maior Δ total positivo.
  2. Desempate: a Carta que também está no baralho do `descoberto` (40,6 %, a subclasse mais fraca).
  3. Aplicar **um passo por vez** e remedir só o Arcanista (`todas` + 3 subclasses) nas sementes 0–19, anotando o Δ de cada passo no relatório.
  4. Parar no primeiro pacote que cumpre o R11. Passo que não move o `todas` (|Δ| < 1 luta em 480) é revertido e conta no limite de passos daquela Carta.

  [H] As candidatas pelos dados da 355 são `arc1_des_garganta` (`arcanista_cinzento_descoberto.json:160-187`, `silenciado` 1, Fôlego 1, Entropia 1, `livre`), `arc1_des_brasa` (`:131`), `arc1_imp_bomba_estopim` (`arcanista_cinzento_improvisador.json:185`), `arc1_imp_truque` (`:220`), `arc1_imp_carretel` (`:68`) e `arc1_cal_pulso_medido` (`arcanista_cinzento_calibrado.json:34`). O R7 confirma ou descarta cada uma.
- **R11 — Metas do pacote (sementes 0–19, base do R5):**
  - Arcanista `todas` com total ≥ **46,5 %** (D1);
  - toda subclasse do Arcanista com padrão ≤ **75,0 %** e total ≤ 85 %;
  - nenhuma subclasse do Arcanista **cai** mais de 2,0 pp no total em relação à base;
  - as outras quatro Posturas com células **idênticas** à base do R5. Por construção, nenhuma Carta delas muda; se alguma célula mudar, é bug e o executor para.

  Se 3 Cartas × 2 passos não chegarem a 46,5 % sem violar o resto, há dois casos:
  - **(a) pacote parcial com `todas` entre 45,0 e 46,5 %:** segue para a confirmação e o relatório registra que a folga não foi atingida (D1);
  - **(b) `todas` < 45,0 %:** o executor **para** antes da confirmação e devolve ao coordenador a curva medida (Δ por passo), o resultado do braço (c) do R6 e a lista de legadas que o R7 aponta. Não aplica a alternativa das utilitárias (D4) nem mexe em legada.

### Confirmação e guardas

- **R12 — Confirmação uma vez (20–99).** Depois do commit do pacote, uma única rodada grava `docs/spec362/arena-confirmacao.json`:
  - `arena_spec341.py posturas --seeds 20:100 --classes "Arcanista Cinzento"` (as 4 chaves `todas`/`calibrado`/`descoberto`/`improvisador`);
  - `arena_spec341.py cartas --seeds 20:100 --ids <alteradas>`, que dá a bandeira por Carta.

  Critérios:
  - Arcanista `todas` com total ≥ **45,0 %**;
  - subclasses com padrão ≤ 75,0 %;
  - nenhuma Carta alterada com bandeira `dominante` (Δ > +8 pp com uso > 60 %, `sim.py:50-51`).

  Falhou = registro em §9 e devolução ao dono, sem reajuste. Nesse caso a exceção de piso **fica** (R13), com o comentário atualizado. As outras Posturas não rodam nas 20–99: as células delas são idênticas por construção (R11), e a 355 já as confirmou.
- **R13 — Fim do `EXCECOES_PISO`.** Com o R12 aprovado:
  - em `tests/test_spec355_arena.py`, `EXCECOES_PISO` sai;
  - o piso do Arcanista passa a ser lido do artefato que substitui o da 355. Um mapa `SUPERADO_POR = {"Arcanista Cinzento": "docs/spec362"}` faz `test_faixas_por_postura` checar o `todas.total` do Arcanista em `docs/spec362/arena-final.json` e `arena-confirmacao.json`, em vez dos JSON congelados da 355 (43,9/44,4 %, que não são regerados).

  Só remover a linha quebraria o teste sobre artefatos que não mudam mais. Por ser mudança em teste de artefato, ela vai em **commit separado** (`test(arena): Arcanista floor read from SPEC-362 artifact`), feito pelo coordenador ou por outro agente com revisão Sol, **nunca pelo executor** (D17 da 355).
- **R14 — Sangromante: exceções definitivas.**
  - Nenhuma Carta do Sangromante muda (pedido do dono).
  - Em `tests/test_spec355_arena.py:14-26`, `EXCECOES_TETO` mantém **os mesmos valores**. Só o comentário muda, para citar "aceitas como definitivas pelo dono em 01/11 (SPEC-362 §8 D5)".
  - `tests/test_spec341_balanco.py` fica intocado (R1).
  - `san1_sil_corte_sem_aviso` continua em `versao` 2 e `dominante` aceito (341, aceite de 27/10). O R14 da 355 **não** é reaplicado.

  O comentário vai no mesmo commit separado do R13.
- **R15 — Teste de artefato desta spec.** `tests/test_spec362_arcanista.py`:
  - `test_versoes_batem_com_catalogo`: `versoes` de `arena-final.json` e `arena-confirmacao.json` iguais ao catálogo;
  - `test_pacote_dentro_do_limite`: ≤ 3 ids alterados, todos de onda do Arcanista, `versao` = `main` + 1, `card_lint` sem issue, `fx.budget_error is None`;
  - `test_alteradas_fora_da_341`: nenhum id alterado em `docs/spec341/arena-*.json["versoes"]` (R4);
  - `test_arcanista_piso_e_teto`: `todas.total` ≥ 0,465 em `arena-final.json` (ou ≥ 0,45 se o relatório declarar o caso R11(a), via chave `"folga_atingida": false` no JSON) e ≥ 0,45 em `arena-confirmacao.json`; padrão ≤ 0,75 em toda subclasse do Arcanista nos dois arquivos;
  - `test_outras_posturas_identicas_a_base`: as células de Devoto, Sangromante, Corruptor e Médico em `arena-final.json` são iguais às de `arena-base-0-19.json`;
  - `test_legadas_e_avaliador_sem_diff`: `git diff --quiet main -- <caminhos do R1/R2>`, só na branch `spec-362` (mesma guarda de `tests/test_spec355_guardas.py`).

### Fora de escopo

- Qualquer Carta do Sangromante, incluindo `san1_sil_corte_sem_aviso` (pedido do dono, R14).
- Carta legada, inclusive `raio_cinza` de volta ao pool (R12 da 355). O R6(b) só mede.
- **Aplicar** a alternativa "utilitárias de volta à compra só para o Arcanista". O R6(c) mede; aplicar é decisão do dono (D4).
- Subir o `descoberto` (40,6 % no total) ao piso. O gate é por Postura (`todas`). A subclasse fica registrada como observação e entra só pelo desempate do R10 (D3).
- Emboscada realista do Arcanista (42,1 % na 355) como critério: só medição informativa no relatório (D6).
- Utilitárias ocupando vaga no `full_deck` da arena (`sim.py:93-97`): é propriedade do avaliador, e o lugar dela é a SPEC-358 (arena por substituição) ou uma spec de avaliador.
- Corruptor perto do piso (45,6–46,7 %) e Devoto +2,7 pp: só registrar se a base nova mostrar mudança.
- Ligar as Cartas (`on`): coordenador.

## 3. Design técnico

### 3.1 Arquivos novos

- `docs/spec362/arena_spec362.py`, que **só importa** (`sim`, `arena_posturas`, `arena_spec341`, `services.cards`, `services.card_piles`):
  - `decompor --seeds 0:20 --out …`: R6, três braços, monkeypatch com `try/finally`;
  - `atribuicao --seeds 0:20 --out …`: R7, leave-one-out em total e padrão por sub, com `no_baralho` e uso;
  - `passo --seeds 0:20 --out …`: mede o Arcanista (`todas` + 3 subs) com o catálogo atual. É um atalho de `arena_spec341.posturas(range, {"Arcanista Cinzento": [...]})` que anexa `versoes` das Cartas alteradas.

  O script é escrito e commitado **antes** de qualquer mudança de Carta. Depois, só ganha subcomando novo com justificativa no relatório.
- `docs/spec362/arena-base-0-19.json` (R5), `decomposicao-0-19.json` (R6), `atribuicao-0-19.json` (R7), `passos-0-19.json` (um registro por passo do R10), `arena-final.json` (0–19, 5 Posturas, `versoes`, `folga_atingida`), `arena-confirmacao.json` (R12) e `RELATORIO.md`.
- `tests/test_spec362_arcanista.py` (R15).

### 3.2 Arquivos alterados

- `data/cards/posturas/arcanista_cinzento_*.json`: ≤ 3 objetos no total, ≤ 2 passos cada, `versao` + 1.
- `data/cards/_ondas.yaml`: `nota_voz`, só se alguma `descricao` mudar.
- `tests/test_spec355_arena.py`: **commit separado, não do executor** (R13/R14). Sai `EXCECOES_PISO`, entra `SUPERADO_POR`, e o comentário de `EXCECOES_TETO` é atualizado com os valores intocados.
- `specs/SPEC-355-cartas-pendencias-abertas.md` §9: uma linha apontando que a pendência do Arcanista foi tratada na SPEC-362 (feita pelo coordenador no pouso).

### 3.3 Formatos

Passo numa Carta (ids reais; números ilustrativos, o R7 decide):

```json
{
  "id": "arc1_des_garganta",
  "custo_folego": 0,
  "custo_entropia": 1,
  "efeitos": [{"kind": "aplicar_condicao", "condicao": "silenciado", "duracao": 1}],
  "versao": 2
}
```

`arena-final.json` usa as mesmas chaves de `docs/spec355/arena-final.json`, mais `base` e `folga_atingida`:

```json
{"seeds": [0, 20], "versoes": {"arc1_des_garganta": 2}, "folga_atingida": true,
 "base": "docs/spec362/arena-base-0-19.json",
 "posturas": {"Arcanista Cinzento": {"todas": {"celulas": {"L1 padrao": [0, 80]}, "total": 0.0, "padrao": 0.0, "elite": 0.0}}}}
```

### 3.4 Assinaturas

- `arena_spec362.decompor(seeds: range) -> dict[str, dict]`: chaves `atual`, `com_raio_cinza` e `utilitarias_na_compra`; cada uma no formato de `arena_spec341.posturas`.
- `arena_spec362.atribuicao(seeds: range) -> dict[str, dict[str, dict[str, float | list[int]]]]`.
- `test_spec362_arcanista.SUBCLASSES = ("todas", "calibrado", "descoberto", "improvisador")`.

## 4. Plano passo a passo

Custo de máquina: a arena do Arcanista nas 0–19 são 4 braços × 6 células × 80 = 1.920 lutas. A de 5 Posturas é cerca de 5×, e as 20–99 cerca de 4×. Rodar em série, um processo por vez, com `run_in_background` e timeout explícito. Medir a RAM antes (CLAUDE.md), e nunca rodar em paralelo com a suíte.

### Etapa 0 — Base e diagnóstico (sem mudar Carta)

1. Escrever e commitar `docs/spec362/arena_spec362.py`.
2. R5: `arena_spec355.py base --seeds 0:20` → `arena-base-0-19.json`; diff contra `docs/spec355/arena-bestiario-0-19.json` no relatório. Se o Arcanista `todas` ≥ 46,5 %, pular para a Etapa 4.
3. R6: `decompor` → `decomposicao-0-19.json`, com a tabela (a)/(b)/(c) no relatório.
4. R7: `atribuicao` → `atribuicao-0-19.json`, com a lista de candidatas no relatório.
5. **Verificação:** `git diff --exit-code main -- <caminhos do R1>` vazio.

### Etapa 1 — Testes primeiro

1. `tests/test_spec362_arcanista.py` (R15). Os testes de artefato e de pacote falham pelo motivo certo (JSON ausente, pacote vazio). `test_alteradas_fora_da_341` e `test_legadas_e_avaliador_sem_diff` passam.
2. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_spec362_arcanista.py -q -n 2`.

### Etapa 2 — Pacote (R8–R11)

1. Um passo por vez, na ordem do R10. Depois de cada passo: `card_lint`, `fx.budget_error`, `passo --seeds 0:20`, e o Δ anotado em `passos-0-19.json` e no relatório.
2. Parar no primeiro pacote que cumpre o R11, ou no caso R11(a)/(b). Em (b): hand-back ao coordenador **sem** seguir.
3. `arena_spec355.py base --seeds 0:20 --versoes <alteradas>` → `arena-final.json` (5 Posturas; as outras devem ser idênticas à base).
4. **Verificação:** `tests/test_spec362_arcanista.py` (exceto confirmação), `tests/test_card_lint.py`, `tests/test_card_acervo_reparo.py`, `tests/test_card_effects_grammar.py`, `tests/test_spec341_balanco.py`, `tests/test_spec355_arena.py` (ainda com `EXCECOES_PISO`) e `validate_content` com 0 erros, todos com `-n 2`.
5. Commit do pacote **antes** da Etapa 3.

### Etapa 3 — Confirmação (R12), uma vez

1. `arena_spec341.py posturas --seeds 20:100 --classes "Arcanista Cinzento"` e `cartas --seeds 20:100 --ids <alteradas>` → `arena-confirmacao.json`, com `versoes`.
2. Emboscada informativa (D6): `arena_spec355.py emboscada --seeds 0:20 --classes "Arcanista Cinzento" --base docs/spec362/arena-final.json`. Só o número vai para o relatório.
3. `RELATORIO.md` completo: base × final (0–19), confirmação, Δ por passo, decomposição, Cartas alteradas (id, campo, de → para, `versao`) e o veredito da bandeira de cada alterada.
4. **Verificação:** `tests/test_spec362_arcanista.py` inteiro verde, ou registro do R12 falho e hand-back.

### Etapa 4 — Testes da 355 (commit separado, coordenador ou outro agente)

1. Com o R12 aprovado: `tests/test_spec355_arena.py` sem `EXCECOES_PISO`, com `SUPERADO_POR` (R13) e o comentário de `EXCECOES_TETO` (R14). Se o R12 falhou: só o comentário de `EXCECOES_PISO` muda, citando a 362 e o número medido.
2. **Verificação:** `tests/test_spec355_arena.py` e `tests/test_spec362_arcanista.py` verdes com `-n 2`.

### Etapa 5 — Revisão

1. `spec-reviewer` (Sol) confere:
   - R1, R2 e R3 pela ordem dos commits: script → pacote → confirmação;
   - que nenhum passo ficou acima de 2 por Carta;
   - que o orçamento não estourou;
   - que as outras Posturas estão idênticas;
   - que o commit da Etapa 4 não é do executor.
2. Handoff em `handoffs/SPEC-362-sol-review.md`.

## 5. Critérios de aceite

- [ ] R1/R2: diff vazio no avaliador, no orçamento, no golden, no snapshot, em `test_card_sim.py`, em `test_spec341_balanco.py` e nas legadas; `test_card_effects_grammar` verde.
- [ ] R5: base nova 0–19 gravada e diff contra a 355 registrado.
- [ ] R6/R7: decomposição R11 × R12 × utilitárias e atribuição na leitura total gravadas.
- [ ] R8–R10: ≤ 3 Cartas de onda do Arcanista, ≤ 2 passos cada, só alavancas do R8, `versao` + 1, lint e orçamento limpos.
- [ ] R11: Arcanista `todas` ≥ 46,5 % nas 0–19 (ou o caso (a) registrado); subclasses ≤ 75 % na padrão; outras Posturas idênticas à base.
- [ ] R12 (nova regra do dono, 02/11): confirmação 100–179 rodada uma vez deu `todas` 44,4 % (< 45,0): FALHOU, devolvido ao dono; 20–99 informativa 46,1 %; bandeira `dominante` não medida.
- [ ] R13: `EXCECOES_PISO` NÃO removido (confirmação 100–179 falhou).
- [ ] R14: nenhuma Carta do Sangromante alterada; `EXCECOES_TETO` com os mesmos valores e o comentário de aceite definitivo.
- [ ] R15: `tests/test_spec362_arcanista.py` verde.
- [ ] Revisão Sol sem P0/P1 aberto (`handoffs/SPEC-362-sol-review.md`).
- [ ] `uv run pytest` verde (suíte completa, 1× no pouso, pelo coordenador).
- [ ] Saves antigos carregam: saves guardam só ids, e o motor lê a `versao` do catálogo.
- [ ] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo).

## 6. Smoke test real

Não há LLM no caminho: o balanço é determinístico. O smoke real é a **arena com as sementes 20–99** sobre o catálogo final e o motor da `main` (Etapa 3). O executor cola a saída resumida no hand-back:

1. `bash scripts/dev/py.sh docs/spec341/arena_spec341.py posturas --seeds 20:100 --classes "Arcanista Cinzento"` → `todas` com total ≥ 45,0 %; as três subclasses ≤ 75,0 % na padrão.
2. `bash scripts/dev/py.sh docs/spec341/arena_spec341.py cartas --seeds 20:100 --ids <alteradas>` → nenhuma bandeira `dominante`.
3. Um `orch.run_round` com cada Carta alterada, pelo caminho real (como em `tests/test_spec339_duracao_condicoes.py`): o `mech_log` mostra o número novo, e `card_effects.render_card_text` (`services/card_effects.py:1528`) bate com ele.
4. Coordenador, junto do smoke final das Cartas (SPEC-355 item 17): com as flags `on`, um conflito com um Arcanista em que uma Carta alterada aparece na mão. O texto da Carta na tela mostra o número novo, e a mão não tem utilitária.

Se 1–2 falharem: **não** reajustar com essas sementes (R3). Registrar e devolver.

## 7. Riscos & compatibilidade

- **Overfitting às sementes 0–19.** O `todas` tem 480 lutas, com erro padrão de cerca de 2,3 pp. Ir de 44,4 % a 46,5 % são cerca de 10 vitórias, e uma parte disso pode ser ruído. As defesas são a held-out (≈ 1.920 lutas, erro padrão de cerca de 1,1 pp, rodada uma vez) com critério duro de 45,0 % (não 46,5) e o teto de passos. O custo é a spec poder fechar sem a folga (caso R11(a)), o que é aceitável.
- **Buff que sobe uma subclasse e não o `todas`.** Os baralhos são diferentes (`cards.py:319`, `sim.py:104-114`). Por isso o R10 só escolhe Cartas presentes no baralho `todas`, e o R11 trava o teto das subclasses.
- **Teto do orçamento.** Buff em Carta de onda pode passar do máximo da faixa (`card_effects.py:1688-1699`). O passo é inválido, o R9 bloqueia, e escolhe-se outro passo ou outra Carta.
- **Base nova diferente da 355.** SPEC-359 (bestiário onda 2) ou SPEC-358 (avaliador) podem pousar antes. O R5 mede na `main` do dia, e o relatório registra o commit. Se o avaliador mudar no meio da execução, a spec para e remede a partir da Etapa 0.
- **Alternativa das utilitárias (D4).** Ela devolve à mão de conflito cartas que não se jogam, que é o defeito que o R11 da 355 corrigiu ("mão sem Aguentar", SPEC-355 §6.1). O ganho de arena viria de atrasar o Fardo, não de poder de Carta. Por isso fica só medida.
- **Teste da 355 sobre artefato congelado.** Remover `EXCECOES_PISO` sem `SUPERADO_POR` quebraria o teste com os 43,9/44,4 % que não são regerados. O R13 resolve com leitura do artefato novo, em commit separado (integridade de eval).
- **Saves e flags.** As Cartas estão atrás de flag `off` em produção e staging. Saves guardam id; sem migração.
- **MockLLM/FallbackLLM e quota:** nenhum impacto.

## 8. Decisões

### Do dono

- **01/11 — "melhora um pouco o Arcanista, o Sangromante pode deixar como está".** A spec nasce `approved`. As decisões abaixo seguem a recomendação e são **revogáveis**.
- **Regras herdadas (341/355):** mecânica é Python; avaliador, orçamento e golden da 330 congelados; Carta legada não muda; 0–19 para ajuste e 20–99 para confirmação uma vez; `test_spec341_balanco.py` intocado (se uma versão da 341 subir: D17, parar e devolver).

### Do autor (valem como aprovadas; revogáveis pelo dono)

- **D1 — Meta com folga: `todas` ≥ 46,5 % nas 0–19 e ≥ 45,0 % nas 20–99.** O pedido era "46–47 %". 46,5 % fica no meio, a cerca de 1 erro padrão do piso. Na held-out vale o piso, porque exigir folga também lá convida a reajuste. Pacote máximo entre 45 e 46,5 nas 0–19: segue e registra (R11(a)).
- **D2 — Até 3 Cartas de onda, até 2 passos cada, só número e custo (R8).** Mais largo que o 1 passo da 341/355, por pedido do dono. A 355 mostrou que 1 passo em 1 Carta não move o `todas` (`docs/spec355/RELATORIO.md:14-17`).
- **D3 — `descoberto` (40,6 % no total) fica fora da meta.** O critério da 355 é por Postura (`todas`). O R10 favorece Cartas que também ajudam o descoberto, e o relatório registra o número final dele. Subir o descoberto ao piso pede spec própria.
- **D4 — Utilitárias de volta à compra só para o Arcanista: medir (R6c), não aplicar.** É uma regra por classe que reabre o defeito corrigido na 355 (carta injogável na mão). O ganho medido viria do atraso do Fardo e da ordem do monte, não de poder. Se o pacote de onda falhar (caso R11(b)), o dono escolhe entre: (a) aceitar a exceção de piso como definitiva, (b) abrir uma spec com Carta nova ou passo em legada pelo protocolo D7 da 339, ou (c) aplicar esta alternativa, já com o número medido.
- **D5 — Exceções de teto do Sangromante aceitas como definitivas.** `EXCECOES_TETO` (`tests/test_spec355_arena.py:16-26`: `todas` 0,754/0,752, `silencioso` 0,787/0,768, `avaro` 0,776) e as da 341 (`tests/test_spec341_balanco.py:233-237`) ficam como estão, com o comentário atualizado (R14). `san1_sil_corte_sem_aviso` segue `dominante` aceito. Sem próxima onda de balanço do Sangromante pendente.
- **D6 — Emboscada realista só informativa.** O Arcanista tem Cartas `buff_iniciativa` (contrapartida do R17 da 355 já vale). O número vai para o relatório sem critério.
- **D7 — `EXCECOES_PISO` sai em commit separado de outro agente, com `SUPERADO_POR` (R13).** É o mesmo precedente do R44/D17 da 355: quem otimiza não edita o gate.

### Do dono, via coordenador (02/11) - substitui a decisão anterior de manter a exceção

Objetivo: Arcanista `todas` >= 45 % na confirmação, sem `EXCECOES_PISO`. 20-99 já vista: ajuste só em 0-19 (mira >= 48 %), confirmação nova UMA vez nas sementes 100-179, 20-99 só informativa. Alavancas: (a) `raio_cinza` de volta ao pool (R12 da 355 o tirou por higiene - fixture 2d6 pela via legada -, não por dominância); (b) passos extras em Cartas de onda. Se a 100-179 falhar: parar e devolver, sem 2ª confirmação.

Execução: `raio_cinza` fora de `EXEMPLO_FORA_DO_POOL` (`services/cards.py`; carta legada intacta) + `pulso_medido` custo_folego 1->0: 0-19 = 48,1 %. **100-179 = 44,4 % (FALHOU)**; 20-99 informativa = 46,1 %. Regra 4: parado. `EXCECOES_PISO` permanece (comentário 44,8 % da decisão anterior está desatualizado: números atuais acima).

### Para o dono confirmar (não bloqueiam a execução)

1. D1: a folga de 46,5 % nas 0–19 com piso de 45 % na held-out está boa, ou o dono quer exigir 46,5 % também nas 20–99?
2. D3: o descoberto em ~40 % no total incomoda? Se sim, fica uma spec própria depois desta.
3. D4: só se o pacote falhar. Escolher (a), (b) ou (c).

## 9. Registro de implementação

Pacote: `arc1_imp_bomba_estopim` (frequencia cena->turno, dano_base 4->5), `arc1_imp_truque` (protecao 2->3), `arc1_cal_pulso_medido` (dano_base 3->4), todas versao 2. Base 44,4 -> 46,5 % (0-19); confirmacao 20-99 44,8 % (R12 reinterpretado, ver §8). Decomposicao: raio_cinza fora do pool explica a queda; utilitarias na compra pioram (42,3 %). Detalhes: `docs/spec362/RELATORIO.md`. Desvios: atribuicao so com Cartas de onda; teste R15 exige lint sem erros (avisos preexistem); bandeira por Carta na 20-99 nao medida; piso da confirmacao no teste = 0,448 (excecao).
