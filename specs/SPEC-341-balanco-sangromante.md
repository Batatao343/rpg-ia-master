# SPEC-341 — Balanço de poder das Cartas pós-SPEC-339 (Sangromante avaro/silencioso, dominantes novas, controles de duração)

> **Status:** `approved`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-339 (`done`: tick de duração corrigido, viés de ordem do `full_deck` removido), SPEC-335 (Lotes 0–6 na `main`, `off`), SPEC-336 (esteira: lint, `versao`, `_ondas.yaml`), SPEC-330 (golden das 308 legadas).
> **Desbloqueia:** fechar o critério aberto da SPEC-335 ("nenhuma Postura fora de 45–75 % na arena padrão"); o passo "arena por Postura" que o ESTADO pede antes de ligar as Cartas (`on`).
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` (mecânica e integridade da arena) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato com evidência · **[H]** hipótese a confirmar na Etapa 0 · **[D?]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

[F] A arena por Postura refeita na SPEC-339, com o baralho sem viés de ordem e o motor corrigido, deixa **só o Sangromante** acima do teto de 75 % na leitura "padrão" (`docs/spec339/RELATORIO-arena.md:22-25`):

| Sangromante | padrão (critério 45–75 %) | total (padrão+elite) |
|---|---|---|
| todas as subclasses | **77,9** | 65,6 |
| exposto | 70,4 | 58,3 |
| avaro | **78,7** | 66,0 |
| silencioso | **79,6** | 66,2 |

Nota de leitura: o "77,9 %" é a leitura **padrão** (leitura A da 335, a do critério), não a total (`docs/spec339/arena-depois.json:2194-2196`: `total 0.656`, `padrao 0.779`). A meta de 45–85 % aprovada pelo dono vale para a arena de **baralhos de inimigo** da 332, outra métrica. O critério desta spec é o da 335: 45–75 % na leitura padrão.

[F] De onde vem a diferença entre as subclasses, por célula (`arena-depois.json:2198-2290`, vitórias em 80 lutas):

| subclasse | L1 padrão | L3 padrão | L5 padrão |
|---|---|---|---|
| exposto | 69 | 62 | **38** |
| avaro | 73 | 64 | **52** |
| silencioso | 71 | 63 | **57** |

O L1 é alto nas três (86–91 %), e é ele que segura a média. A diferença entre o exposto e as outras duas aparece no **L5**, quando entram as Cartas de `level_req` 4. Pelo protocolo, avaro precisa perder 10 vitórias em 240 (189 → ≤ 180) e silencioso precisa perder 11 (191 → ≤ 180).

[F] Nenhuma Carta de onda do avaro ou do silencioso, sozinha, explica o excesso. No protocolo de lote, os deltas das Cartas que entram na arena (`level_req` ≤ 5) ficam todos dentro do ruído (≤ +5,0 pp; `arena-depois.json:334-498`, `:662-769`; ruído de ~4 pp segundo `RELATORIO-arena.md:128`). O excesso é **cumulativo**. Por isso esta spec começa por um diagnóstico de atribuição em nível de Postura (Etapa 0), e não por nerf às cegas.

Junto com isso, três pendências da 339 dependem do motor corrigido:

- **Duas bandeiras `dominante` novas** (`RELATORIO-arena.md:101`):
  - `cor1_alm_culpa_antiga` (onda, Corruptor/alma): +11,2 pp sobre uma base de 12,5 %, em `arena-depois.json:919-932`;
  - `san_exp_espetaculo` (**legada**): +8,3 pp em 48 lutas por braço, com 4 sementes e protocolo default, em `arena-depois.json:1922-1935`.
- **Os 9 ids ex-`CONTROLE_DURACAO_PENDENTES`** saíram da lista sem revisão de número (`RELATORIO-arena.md:125-127`; a lista já não existe: `tests/test_card_lint.py:441`).
- **Giz Vermelho**, escrito com `duracao: 2` só para escapar do lint provisório (`docs/spec335/RELATORIO-arena-lote5.md:75`), passou de +5,0 para +7,5 pp com o motor corrigido (`arena-antes.json:1762-1774` → `arena-depois.json:1758-1769`). O limiar de `dominante` é +8 pp.

**Objetivo:**

- levar Sangromante avaro e silencioso para ≤ 75 % na leitura padrão, sem derrubar o exposto;
- tratar as 2 dominantes;
- rever os 9 ids e as Cartas de onda que ficaram com `duracao: 2` como contorno.

Tudo isso mexendo **só em Cartas de onda** (335/336). As 308 legadas ficam intactas: o golden é protegido (`evals/protected-paths.txt:14`). O protocolo e os limiares da arena também não mudam. Princípio: **mecânica é Python**. O freio de poder é número de Carta dentro do orçamento (`services/card_effects.py:1676-1686`), medido por um avaliador congelado.

## 2. Requisitos

### Integridade (valem para todas as etapas)

- **R1 — Avaliador congelado.** `scripts/cards/sim.py` e `docs/spec335/arena_posturas.py` saem desta spec byte-idênticos. Também não mudam:
  - os limiares de `sim.py:48-54`;
  - `PROTOCOLO_LOTE` (`sim.py:391`, travado por `tests/test_card_sim.py:344-348`);
  - a faixa 45–75 %, o orçamento (`data/cards/_orcamento.json`) e `evals/`.

  Prova: `git diff --exit-code main -- scripts/cards/sim.py docs/spec335/arena_posturas.py data/cards/_orcamento.json tests/test_card_sim.py` no pouso. Se alguma mudança de protocolo parecer necessária, o executor para e registra uma decisão **separada** para o dono, sem aplicar.
- **R2 — Legadas intactas.** Nenhum objeto das 308 legadas muda: `git diff --exit-code main -- data/cards/{devoto,sangromante,corruptor,medico,arcanista,basicas,bestiario,exemplos,exemplos_extra,tiers_5_plus}.json tests/fixtures/spec330_legacy_golden.json`, e `tests/test_card_effects_grammar.py` verde. Uma mudança em legada que pareça indispensável vira uma **proposta** em `docs/spec341/proposta-legadas.md` (id, mudança, evidência e o protocolo R11 da SPEC-339 para o golden) e uma decisão do dono. Não é aplicada.
- **R3 — Sementes de ajuste × sementes de confirmação.** O ajuste usa só as sementes 0–19 (o protocolo) e o diagnóstico da Etapa 0. As sementes **20–99** são de confirmação (held-out). Elas rodam **uma vez** no pacote final, e se a confirmação falhar o executor **para** e devolve ao coordenador. Iterar o número de uma Carta até ela passar nas 20–99 é proibido.
- **R4 — Alavancas permitidas.** Só número e custo dentro do mesmo objeto:
  - `dano_base`, `valor` de efeito;
  - `custo_folego`, `custo_entropia`;
  - `frequencia` (`livre` → `turno` → `cena`);
  - valor de `sacrificio`;
  - `duracao`.

  **Não** valem `tier`, `level_req`, `patamar` nem `raridade`. Essas alavancas mudam **quem entra** no baralho da arena (ordenado por `tier`, `sim.py:104-109`; 2 cópias por `patamar` comum, `sim.py:111`, `services/cards.py:415`). O poder sairia da medição em vez de cair. Exceção só por decisão do dono (D4).
- **R5 — Toda Carta alterada:**
  - ganha `versao` + 1 (`docs/guias/CARTAS.md:70`, `:99`; a convenção praticada é editar o objeto no lugar, como `san1_sil_olho_no_pulso` v2 e `arc1_tro_lance_calculado` v2);
  - passa no orçamento, isto é, não fica abaixo do piso da faixa (`card_effects.py:1681`);
  - passa em `card_lint` sem avisos e em `bash scripts/dev/py.sh scripts/validate_content.py` com 0 erros;
  - mantém `descricao` e `momento` coerentes com o efeito novo.

  Se a `descricao` mudar, a voz entra na amostra da onda, com `nota_voz` explicando a mudança.

### Diagnóstico (Etapa 0)

- **R6 — Reprodução do baseline.** `arena_posturas.run_arm` com as sementes 0–19, L1/L3/L5 e padrão+elite reproduz **exatamente** as células do Sangromante, Corruptor/alma e Médico/boticário de `docs/spec339/arena-depois.json`. Se divergir, a spec para: o catálogo ou o motor mudou desde a 339.
- **R7 — Atribuição por leave-one-out.** Para avaro, silencioso e exposto (este como controle), e para cada Carta do baralho da arena em L1/L3/L5, com Cartas de onda e **legadas** (as legadas só para informação):
  - tirar a Carta do catálogo, remontar o baralho (`sim.full_deck`) e medir a taxa padrão com as sementes 0–19;
  - gravar Δ pp por Carta e por nível em `docs/spec341/atribuicao.json` e a tabela ordenada em `docs/spec341/RELATORIO.md`.

  O script **importa** `run_arm`, `full_deck` e `fight` sem modificá-los. A atribuição é uma ferramenta de diagnóstico e não vira critério.
- **R8 — Confirmação das bandeiras com sementes 20–99.** Rodar, com o protocolo de lote, sementes `range(20, 100)` e os mesmos parâmetros do resto, para:
  - `cor1_alm_culpa_antiga`;
  - `san_exp_espetaculo`, com o protocolo default de legado: níveis 1,3,5, padrão, 4 criaturas, como `docs/spec339/arena_spec339.py:71`;
  - os 9 ids do R11;
  - `med1_bot_giz_vermelho` e `neu1_ka_divida_gravada`.

  Uma bandeira que não se confirma (delta ≤ +8 pp ou sem `dominante`) é registrada como **ruído**, e a Carta não muda. É o precedente da 335: `docs/spec335/RELATORIO-arena-lote3.md` (3 de 4 eram ruído) e `RELATORIO-arena-lote6.md` (1 de 13 era real).

### Sangromante avaro e silencioso

- **R9 — Teto.** Com o pacote final, as taxas da leitura padrão (sementes 0–19, protocolo da 339) são:
  - avaro ≤ 75,0 % e silencioso ≤ 75,0 %;
  - Sangromante/todas ≤ 75,0 %;
  - na confirmação com as sementes 20–99, os mesmos três ≤ 75,0 % (D2).
- **R10 — Exposto e pisos preservados.**
  - Exposto na leitura padrão ≥ 65,0 % e queda ≤ 5,0 pp em relação a 70,4 % (sementes 0–19), e ≥ 65,0 % nas 20–99 (D3).
  - Nenhuma subclasse do Sangromante abaixo de 45 % na leitura **total** (padrão+elite). Hoje a menor é 58,3 %.
  - As outras Posturas mudam só pelo que esta spec mexer nelas: Corruptor/alma e Médico/boticário, R12/R14. As demais saem com células idênticas às da 339, porque nenhuma Carta delas muda.
- **R11 — Pacote mínimo.**
  - Só Cartas de onda de `data/cards/posturas/sangromante_avaro.json` e `sangromante_silencioso.json`, escolhidas pelo R7 (maior Δ positivo entre as que entram na arena).
  - **≤ 3 Cartas por subclasse** e **1 passo por Carta**: −1 de `dano_base`/`valor`, +1 de Fôlego ou Entropia, ou um degrau de `frequencia`.
  - O tronco (`sangromante_tronco.json`) e o exposto ficam de fora: mexer neles derruba o exposto.
  - Se o pacote mínimo não bastar, o executor para e devolve ao coordenador a curva medida (Δ por passo) e a lista de legadas que o R7 aponta (R2), em vez de empilhar nerfs.

  [H] Candidatas pelas evidências atuais, que o R7 confirma ou descarta:
  - `san1_sil_corte_sem_aviso`: `dano_base` 6, Fôlego 1, `level_req` 4, uso 70 % (`sangromante_silencioso.json:191-223`; `arena-depois.json:742-755`);
  - `san1_ava_cobranca_adiada`: 8 de dano por Fôlego, `level_req` 4 (`sangromante_avaro.json:241-274`);
  - `san1_ava_penhor_de_carne`: `dano_base` 5 com Fôlego 1, uso 68 % (`:277-308`);
  - `san1_ava_moeda_guardada`: +5,0 pp (`:5-36`; `arena-depois.json:334-345`).

  As de `level_req` 4 explicam o L5, onde está a diferença para o exposto.

### Dominantes novas

- **R12 — `cor1_alm_culpa_antiga`** (`data/cards/posturas/corruptor_alma.json:220-253`: Marca do Abismo 2 + `desmoralizado` 2, Fôlego 1, Entropia 2, `cena`, `level_req` 4).
  - Se o R8 **não** confirmar: nada muda.
  - Se confirmar: vale D5. A recomendação é **aceitar e registrar** como "dominante aceita", porque alma é a subclasse mais fraca (53,3 % na padrão, 43,3 % no total) e a Carta resgata um baralho que sem ela vence 12,5 % em L4.
  - Se o dono preferir o nerf: `desmoralizado` com `duracao` 2 → 1 (`versao` 2), com Corruptor/alma ≥ 50 % na leitura padrão nas duas faixas de sementes.
- **R13 — `san_exp_espetaculo` (legada).** Não muda (R2). A Carta é só `taunt` 2 + `auto_dano` 2 (`data/cards/sangromante.json:181-206`), e o bot de arena joga solo, sem a quem redirecionar (`RELATORIO-arena.md:120-122`). O delta, se for real, vem do `auto_dano` alimentando a mecânica de classe, não do Provocar. O executor:
  1. confirma pelo R8;
  2. se confirmar, escreve a proposta em `docs/spec341/proposta-legadas.md`, com a hipótese de causa testada (luta com e sem `auto_dano`, `rng` igual);
  3. deixa a decisão para o dono (D6).

### Controle de duração sob o motor corrigido

- **R14 — Inventário fechado das Cartas de onda com `taunt`/`marca`.** Um teste lista todas as Cartas de onda com `kind` `taunt` ou `marca` e confere a `duracao` efetiva contra a tabela abaixo. Uma Carta nova com `taunt`/`marca` fora da tabela falha até ser classificada.

  | id | arquivo | controle | `duracao` hoje | origem | proposta |
  |---|---|---|---|---|---|
  | `dev1_zel_ciume_aberto` | `devoto_zeloso.json:224` | taunt | 1 | ex-pendente | manter 1 |
  | `dev1_zel_corpo_entre` | `devoto_zeloso.json:335` | taunt | 1 | ex-pendente | manter 1 |
  | `dev1_zel_ninguem_mais` | `devoto_zeloso.json:375` | taunt | 1 | ex-pendente | manter 1 |
  | `san1_exp_veia_a_mostra` | `sangromante_exposto.json:39` | taunt | 1 | ex-pendente | manter 1 |
  | `san1_exp_plateia_cega` | `sangromante_exposto.json:270` | taunt | 1 | ex-pendente | manter 1 |
  | `san1_exp_teatro_de_facas` | `sangromante_exposto.json:342` | taunt | 1 | ex-pendente | manter 1 |
  | `san1_sil_marca_de_unha` | `sangromante_silencioso.json:161` | marca | 1 | ex-pendente | manter 1 (pode entrar no R11) |
  | `san1_sil_cirurgia_sem_testemunha` | `sangromante_silencioso.json:330` | marca | 1 | ex-pendente | manter 1 |
  | `san1_ava_livro_de_dividas` | `sangromante_avaro.json:143` | marca | 1 | ex-pendente | manter 1 (pode entrar no R11) |
  | `med1_bot_giz_vermelho` | `medico_boticario.json:153` | marca | **2** | contorno do lint (Lote 5) | **1**, `versao` 2 (D7) |
  | `neu1_ka_divida_gravada` | `valoria_neutras.json:756` | marca | **2** | escrita sob o lint (Lote 6) | **1**, `versao` 2 (D7) |
  | `arc1_imp_parafuso` | `arcanista_cinzento_improvisador.json:5` | marca | 2 | Lote 1, antes do lint (desenho) | manter 2 |
  | `arc1_imp_arame` | `arcanista_cinzento_improvisador.json:253` | marca | 2 | Lote 1, antes do lint (desenho) | manter 2 |

- **R15 — Os 9 ex-pendentes valem no motor real.**
  - Um teste parametrizado joga cada Carta pelo caminho real (`orch.run_round`, as duas ordens de iniciativa, com aliado e 2 inimigos, `rng` forçado como em `tests/test_spec339_duracao_condicoes.py`).
  - `taunt`: exatamente 1 declaração inimiga posterior mira o jogador.
  - `marca`: o próximo ataque do aplicador tem a Vantagem da Marca, e a Vantagem não existe no ataque seguinte.

  Com o bot solo, Provocar não aparece na taxa de vitória (6 dos 9 são `taunt`). Por isso a prova de "vale" é este teste, e a arena só confere que nenhuma das 9 vira `dominante` nas sementes 20–99 (R8).
- **R16 — Giz Vermelho e Dívida Gravada voltam a `duracao` 1** (D7), com teste de motor (R15) provando que a Marca de `duracao` 1 cobre o próximo ataque do aplicador. Arena:
  - Giz no protocolo de lote;
  - Dívida Gravada como variante de 2 baralhos, como no Lote 6 (`docs/spec335/RELATORIO-arena-lote6.md`);
  - delta ≤ +8 pp nas duas faixas de sementes;
  - Médico/boticário segue entre 45 e 75 % na leitura padrão.

### Relatório

- **R17 — `docs/spec341/RELATORIO.md`** traz:
  - a tabela antes/depois por subclasse, nas duas faixas de sementes;
  - o top 10 da atribuição por subclasse;
  - as Cartas alteradas (id, campo, de → para, `versao`);
  - o veredito de cada bandeira (real/ruído, ação);
  - o veredito dos 13 ids do R14;
  - a lista de propostas para legadas, se houver.

  Os dados brutos ficam em `docs/spec341/arena-final.json` (0–19) e `docs/spec341/arena-confirmacao.json` (20–99). Cada JSON leva `versoes: {id: versao}` das Cartas alteradas.
- **R18 — Guarda contra artefato velho** (D8). `tests/test_spec341_balanco.py` lê `docs/spec341/arena-final.json` e `arena-confirmacao.json` e:
  - asserta os tetos e pisos do R9/R10 **com os números da 335/339, sem limite novo**;
  - asserta que as `versoes` gravadas batem com as do catálogo atual.

  Assim, mudar de novo uma dessas Cartas sem refazer a arena quebra o teste.

### Fora de escopo

- Mudar qualquer Carta legada (R2). Só proposta.
- Mudar o protocolo da arena, o bot (`full_deck_decl`), os limiares de bandeira, a faixa 45–75 %, o orçamento ou o golden. Se for preciso, é decisão separada.
- Devoto/consagrado em 75,0 % (no limite, dentro da faixa) e Corruptor/alma baixo no total (43,3 %): só registrar.
- Buffs de Postura fraca (Corruptor, Arcanista): a faixa está cumprida na leitura padrão.
- Texto do `taunt` ("pode" em vez de "precisa", P2-5 da 335) e escolha de alvo do `taunt` em efeito extra: SPEC-336.
- Bot com aliado para medir Provocar na taxa de vitória: follow-up da 336 (P2-11 da 335).
- Ligar as Cartas (`on`) e o e2e: coordenador, depois desta spec.

## 3. Design técnico

### 3.1 Arquivos novos

- `docs/spec341/arena_spec341.py`, um orquestrador que **só importa** (R1):
  - `atribuicao --sub <sub> --levels 1,3,5 --seeds 0:20`: R7, sobre `sim.full_deck` com a Carta tirada do catálogo como em `sim.build_arms` (`sim.py:319-331`), restaurando o catálogo no `finally`;
  - `posturas --seeds A:B [--classes ...]`: chama `arena_posturas.run_arm(cls, range(A, B), [1,3,5], ["padrao","elite"], 4, sub)` (`docs/spec335/arena_posturas.py:38-52`) e grava as mesmas chaves da 339 (`total`, `padrao`, `elite`, `celulas`);
  - `cartas --seeds A:B --ids ...`: chama `sim.simulate_batch([card], [level_req], ["padrao"], 4, list(range(A, B)))`, com os parâmetros do `PROTOCOLO_LOTE` e só as sementes trocadas, como `docs/spec335/confirmar_tronco_lote6.py:4-11`, `:62`. Para legada, níveis `[1,3,5]` (R8);
  - `report`: gera `RELATORIO.md`.

  Ele é escrito e commitado **antes** de qualquer mudança de Carta (Etapa 0), e o revisor confere que nenhum commit posterior o altera, exceto o `report`.
- `tests/test_spec341_balanco.py` (R14, R15, R16, R18, R2).
- `docs/spec341/{atribuicao.json, arena-final.json, arena-confirmacao.json, RELATORIO.md}` e, se houver, `proposta-legadas.md`.

### 3.2 Arquivos alterados

- `data/cards/posturas/sangromante_avaro.json` e `sangromante_silencioso.json`: ≤ 3 objetos cada (R11), com `versao` + 1.
- `data/cards/posturas/medico_boticario.json` (`med1_bot_giz_vermelho`) e `data/cards/valoria_neutras.json` (`neu1_ka_divida_gravada`): `duracao` 2 → 1, `versao` 2 (D7).
- `data/cards/posturas/corruptor_alma.json`: só se D5 = nerf.
- `data/cards/_ondas.yaml`: `nota_voz` da onda, se alguma `descricao` mudar (R5).
- Não tocar: `tests/test_card_sim.py:360` fixa `san1_exp_selo_de_dor` em `versao` 1, e o exposto está fora do R11. Se a Carta mudar por decisão, o teste aponta o achado.

### 3.3 Formato (exemplo com ids reais; números ilustrativos, o R7 decide)

```json
{
  "id": "san1_sil_corte_sem_aviso",
  "custo_folego": 1,
  "efeitos": [
    {"kind": "dano", "categoria_arma": "leve", "dano_base": 5},
    {"kind": "sangria", "valor": 1}
  ],
  "versao": 2
}
```

`arena-final.json` (mesmas chaves de `docs/spec339/arena-depois.json` em `posturas`, mais):

```json
{"seeds": [0, 20], "versoes": {"san1_sil_corte_sem_aviso": 2, "med1_bot_giz_vermelho": 2},
 "posturas": {"Sangromante": {"avaro": {"celulas": {"L1 padrao": [0, 80]}, "padrao": 0.0, "total": 0.0, "elite": 0.0}}}}
```

### 3.4 Assinaturas

- `arena_spec341.leave_one_out(cls: str, sub: str, levels: list[int], seeds: range) -> dict[str, dict[str, float]]`, que devolve `{card_id: {"L1": Δpp, "L3": Δpp, "L5": Δpp, "padrao": Δpp}}`.
- `arena_spec341.posturas(seeds: range, classes: dict[str, list[str]]) -> dict`.
- `test_spec341_balanco.ONDA_CONTROLE: dict[str, tuple[str, int]]`, com id → (controle, `duracao` esperada), igual à tabela do R14.

## 4. Plano passo a passo

Custo de máquina: cada `posturas` com as sementes 20–99 é cerca de 4× a rodada da 339. Rodar só as classes afetadas (Sangromante, Corruptor/alma, Médico/boticário), em um processo, com `run_in_background` e timeout explícito. Nunca em paralelo com a suíte. Medir a RAM antes (CLAUDE.md).

### Etapa 0 — Diagnóstico (sem mudar Carta)

1. Escrever e commitar `docs/spec341/arena_spec341.py` (§3.1).
2. R6: reproduzir as células da 339 e anotar em `RELATORIO.md`. Se divergir, parar.
3. R7: rodar a atribuição para avaro, silencioso e exposto, e gravar `atribuicao.json`.
4. R8: confirmar com as sementes 20–99 as 2 dominantes, os 9 ids, Giz e Dívida Gravada.
5. **Verificação:** `git diff --exit-code main -- scripts/cards/sim.py docs/spec335/arena_posturas.py`. Hand-back parcial ao coordenador **só se** o R6 divergir ou o R8 confirmar `san_exp_espetaculo` (proposta R13).

### Etapa 1 — Testes primeiro (TDD)

`tests/test_spec341_balanco.py`:

1. `test_inventario_controle_de_onda_fechado`: toda Carta de onda com `taunt`/`marca` está em `ONDA_CONTROLE`, e a `duracao` efetiva (ausente = 1) bate com a tabela. **Falha** até Giz e Dívida irem para 1.
2. `test_controle_d1_de_onda_vale_no_turno_seguinte[id-ordem]`: R15 para os 9 + Giz + Dívida, pelo `orch.run_round` real. O `taunt` desvia exatamente 1 declaração e a `marca` cobre só o próximo ataque do aplicador. Deve passar já para os 9 e falhar para Giz e Dívida na parte "não existe no ataque seguinte".
3. `test_cartas_alteradas_sobem_versao_e_passam_no_lint`: para cada id em `ALTERADAS` (preenchido na Etapa 2), `versao` > a da `main`, `card_lint.lint_card` sem issue e `fx.budget_error` `None`.
4. `test_legadas_intactas`: o hash dos objetos das 308 legadas é igual ao do golden (reaproveitar `tests/spec330_equivalence.py`, sem regenerar nada).
5. `test_arena_final_dentro_da_faixa` e `test_arena_confirmacao_dentro_da_faixa` (R9, R10, R18): leem os JSON; falham enquanto eles não existirem ou estiverem fora.
6. `test_arena_versoes_batem_com_catalogo` (R18).
7. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_spec341_balanco.py -q -n 2`. Os testes 1, 2 (Giz/Dívida), 3, 5 e 6 falham pelo motivo certo, e o 4 passa.

### Etapa 2 — Controles de duração (R16)

1. Giz Vermelho e Dívida Gravada: `duracao` 1, `versao` 2.
2. **Verificação:** testes 1 e 2 verdes; `tests/test_card_lint.py`, `tests/test_card_acervo_reparo.py` e `tests/test_spec339_duracao_condicoes.py` verdes com `-n 2`; `validate_content` com 0 erros.

### Etapa 3 — Pacote do Sangromante (R11)

1. Escolher pelo `atribuicao.json` as Cartas e o passo de cada uma. Aplicar uma Carta por vez, remedindo **só** a subclasse com as sementes 0–19, e anotar o Δ de cada passo em `RELATORIO.md`.
2. Parar no primeiro pacote que cumpre o R9 nas sementes 0–19 com o exposto no R10. Se, com 3 Cartas por subclasse, não chegar: parar e devolver (R11).
3. **Verificação:** teste 3 verde; lint e `validate_content` limpos.

### Etapa 4 — Dominante do Corruptor (só se o R8 confirmar e D5 = nerf)

1. `desmoralizado` com `duracao` 1 e `versao` 2; remedir Corruptor/alma.

### Etapa 5 — Arena final e confirmação

1. `posturas --seeds 0:20` para as 5 Posturas, gravado em `arena-final.json`. As Posturas sem Carta alterada devem sair idênticas à 339 (R10).
2. `posturas --seeds 20:100` só para Sangromante, Corruptor/alma e Médico/boticário, e `cartas --seeds 20:100` para as alteradas, gravado em `arena-confirmacao.json`. Uma vez só (R3).
3. `report`, gerando `RELATORIO.md`.
4. **Verificação:** testes 5 e 6 verdes; `tests/test_card_sim.py`, `tests/test_card_effects_grammar.py`, `tests/test_balance_classes.py` e `tests/test_balance_classes_v4_runtime.py` verdes com `-n 2` (R17 da 339: se algum falhar, registrar e parar, sem mudar limite); e o diff do R1/R2 vazio.

### Etapa 6 — Revisão

1. `spec-reviewer` (Sol) confere:
   - o R1, o R2 e o R3, pela ordem dos commits: script antes das Cartas e confirmação depois do pacote;
   - o veredito das bandeiras;
   - o R15 lido no log do `run_round`.
2. Handoff em `handoffs/SPEC-341-sol-review.md`.

## 5. Critérios de aceite

- [ ] R1/R2: diff vazio em `sim.py`, `arena_posturas.py`, `_orcamento.json`, `tests/test_card_sim.py`, nos JSON legados e no golden; `test_card_effects_grammar` verde.
- [ ] R3: `arena-confirmacao.json` gerado uma vez, depois do commit do pacote (o histórico prova).
- [ ] R6: baseline da 339 reproduzido célula a célula.
- [ ] R7: `atribuicao.json` e a tabela no relatório.
- [ ] R9: avaro, silencioso e Sangromante/todas ≤ 75,0 % na leitura padrão, nas sementes 0–19 **e** 20–99.
- [ ] R10: exposto ≥ 65,0 % (queda ≤ 5 pp nas 0–19) nas duas faixas; nenhuma subclasse do Sangromante < 45 % no total; Posturas sem Carta alterada idênticas à 339.
- [ ] R11: ≤ 3 Cartas por subclasse, 1 passo cada, só alavancas do R4, `versao` + 1, lint e orçamento limpos.
- [ ] R12/R13: veredito das 2 dominantes registrado (ruído, aceita ou nerf conforme D5); `san_exp_espetaculo` intocada e, se confirmada, com proposta escrita.
- [ ] R14–R16: inventário fechado verde; os 9 + Giz + Dívida valem no `run_round` real nas duas ordens; Giz e Dívida em `duracao` 1, com delta ≤ +8 pp nas duas faixas; Médico/boticário entre 45 e 75 %.
- [ ] R17/R18: relatório completo; testes de artefato verdes.
- [ ] Revisão Sol `APPROVED`.
- [ ] `uv run pytest` verde (suíte completa, 1× no pouso, pelo coordenador).
- [ ] Saves antigos carregam: saves guardam só ids e o motor lê a maior `versao`.
- [ ] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo).

## 6. Smoke test real

Não há LLM no caminho: o balanço é determinístico, MockLLM. O smoke real é a **arena com as sementes 20–99** sobre o catálogo final e o motor da `main`. A Etapa 5.2 é o smoke, e o executor cola a saída resumida no hand-back:

1. `bash scripts/dev/py.sh docs/spec341/arena_spec341.py posturas --seeds 20:100 --classes Sangromante` → avaro, silencioso e todas ≤ 75,0 %; exposto ≥ 65,0 % na leitura padrão.
2. `... cartas --seeds 20:100 --ids <alteradas> med1_bot_giz_vermelho neu1_ka_divida_gravada cor1_alm_culpa_antiga` → nenhuma bandeira `dominante` nova entre as alteradas; veredito de `culpa_antiga` conforme D5.
3. `... posturas --seeds 20:100 --classes Corruptor:alma "Médico de Campo:boticario"` → as duas entre 45 e 75 % na leitura padrão.
4. Um `orch.run_round` com Giz Vermelho v2 e um com uma Carta alterada do Sangromante: o log mostra o efeito novo, e `render_card_text` bate com o número novo.

Se 1–3 falharem: **não** reajustar com essas sementes (R3). Parar e devolver ao coordenador.

## 7. Riscos & compatibilidade

- **Overfitting às sementes 0–19.** Com 240 lutas por subclasse, o erro padrão é de ~2,7 pp, e ajustar até "passar" no limite pode ser ruído. O R3 (held-out 20–99, uma vez) e o R11 (1 passo por Carta, pacote mínimo) são a defesa. O custo é a spec poder parar sem fechar, o que é o comportamento correto.
- **Atribuição não aditiva.** O leave-one-out mede cada Carta sozinha, e a soma dos Δ não é o efeito do pacote. Por isso a Etapa 3 remede a cada passo.
- **O excesso pode estar nas legadas.** Se o R7 mostrar que as maiores contribuições do avaro/silencioso são legadas (`san_ava_*`/`san_sil_*`), o pacote só de onda pode não bastar sem esvaziar as Cartas novas. Nesse caso, o R11 manda parar e o dono decide (D4/D6).
- **Saves e flags.** As Cartas de onda estão atrás de flag `off` em produção e staging (ESTADO). Saves guardam só o id, e a `versao` maior vale ao carregar. Sem migração.
- **Golden.** Não muda (R2). Se mudar, é bug do executor e bloqueia.
- **`test_card_sim.py:360`** depende de `san1_exp_selo_de_dor` v1: o exposto fica fora do pacote.
- **Custo de máquina.** As sementes 20–99 levam cerca de 4× o tempo. Rodar uma por vez, em background, sem `-n auto` e fora da janela da suíte do coordenador.
- **MockLLM/FallbackLLM e quota:** nenhum impacto.

## 8. Decisões que o dono precisa tomar

- **D1 — Métrica do teto:** a leitura **padrão** (critério da 335/339, onde o Sangromante está em 77,9 %) ou a total (65,6 %, já dentro da faixa)? **Recomendação: padrão.** É o critério escrito na 335 e a leitura usada em todas as rodadas. Trocar de métrica agora seria mudar o avaliador para passar.
- **D2 — Confirmação held-out:** exigir ≤ 75 % também nas sementes 20–99 (uma rodada, sem reajuste)? **Recomendação: sim.** Sem isso, o ajuste fica sujeito a overfitting às 20 sementes do protocolo. Alternativa mais branda: 20–99 ≤ 76,5 % (cerca de 1 erro padrão com 960 lutas).
- **D3 — O que é "não derrubar o exposto":** **recomendação: ≥ 65,0 % na leitura padrão e queda ≤ 5 pp nas sementes 0–19.** Na prática, o exposto não é tocado (R11), então a guarda só pega efeito colateral.
- **D4 — Alavancas:** só número e custo (R4), sem `tier`/`level_req`/`patamar`/`raridade`, e no máximo 3 Cartas por subclasse? **Recomendação: sim.** As alavancas excluídas mudam a composição do baralho da arena e escondem poder em vez de tirá-lo. Se o pacote não bastar, o dono decide no hand-back entre (a) mais Cartas ou mais passos, ou (b) uma proposta sobre legadas.
- **D5 — `cor1_alm_culpa_antiga`, se o R8 confirmar a bandeira:** aceitar e registrar, ou dar o nerf (`desmoralizado` 2 → 1)? **Recomendação: aceitar e registrar.** Alma é a subclasse mais fraca (53,3 % padrão, 43,3 % total), e a Carta tira um baralho de 12,5 % do buraco. O precedente é a Bênção do Aço, aceita perto do limiar na 335. Se a bandeira não se confirmar, nada muda.
- **D6 — `san_exp_espetaculo` (legada):** **recomendação: não mexer nesta spec.** Confirmar com as sementes 20–99. Se for real, abrir uma spec própria, com o protocolo de golden R11 da SPEC-339, porque a causa provável é `auto_dano` × mecânica de classe e não a Carta.
- **D7 — Giz Vermelho e Dívida Gravada de `duracao` 2 para 1 (`versao` 2):** **recomendação: sim.** O 2 foi contorno de um bug que a 339 corrigiu. Com o motor certo, Giz subiu para +7,5 pp, perto do limiar de 8. Os 9 ex-pendentes ficam em 1, e `arc1_imp_parafuso`/`arame` (`duracao` 2 por desenho, Lote 1) não mudam.
- **D8 — Teste de artefato (R18)** que lê os JSON da arena e trava as `versoes` alteradas? **Recomendação: sim, só com o escopo das Cartas desta spec.** Ele usa os limites existentes (45–75 % e o piso do exposto desta spec) e falha se alguém mudar essas Cartas sem refazer a arena. Custo: a esteira da 336 precisa refazer a arena ao mexer nelas, o que é desejável.

**Decisões do dono (27/10, "aprovo!!"):** todas as recomendações D1–D8.
