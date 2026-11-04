# SPEC-369 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Sol · **Data:** 2026-11-04 · **Commit revisado:** `8fe4e0dd`

## Escopo

Fase B, blocos B1 (R12, `draft.py` + D-369-5) e B2 (R17, Carta de iniciativa do Corruptor),
branch `spec-369`, `main...HEAD` = `37296877` (B1), `35a77627` (B2) e `8fe4e0dd` (ajuste da
régua, autor da Fase A). Arquivos: `scripts/cards/draft.py`, `services/card_budget_fit.py`,
`scripts/bestiario/gerar_mecanica.py`, `data/cards/posturas/corruptor_tronco.json`,
`data/cards/_ondas.yaml`, `tests/test_card_draft_orcamento.py`, `tests/test_card_acervo_reparo.py`,
`tests/test_spec369_regua.py` e §9 da spec. Ficaram fora: B3 em diante (gate R9c) e a Fase C.
Não rodei de novo a medição `emboscada`/`posturas`, porque a RAM livre estava em 2,4 GB. O
resultado declarado bate com a análise: a passiva tem `level_req` 1, então o crédito D-369-6
anula a emboscada em todos os níveis, e o `realista_369` do Corruptor fica igual ao total da
base (51,9).

### Conferência

- **R1.** B1 e B2 não tocam arquivo da Fase A. `8fe4e0dd` só altera `tests/test_spec369_regua.py`
  e §9, num commit próprio de autor de régua, e o executor parou e devolveu antes, como o R1
  manda. A prova não ficou mais fraca. O estado da base continua afirmado, agora com
  `sem_cartas(ini)`. O teste também passou a exigir que toda Carta `buff_iniciativa` do Corruptor
  seja `passiva`, fique fora do crédito da 355 e seja creditada pelo D-369-6 no seu
  `level_req`, e os casos do Devoto e do Sangromante não mudaram. Falta só o `<sha-A>` (P2-1).
- **R2.** `git diff --exit-code 1869254c HEAD` (merge-base = `main` de partida) dá vazio em
  todos os caminhos do R2 e também em `evals/`, `agents/combat.py` e
  `services/conflict_orchestrator.py`. Contra a `main` atual aparecem `agents/combat.py` e
  `evals/protected-paths.txt`, mas a mudança veio da `main` (SPEC-372), não da branch.
- **R12(a)**: `_triagem` importa `card_lint.check_budget` e `check_raridade` sem copiar código.
  **(b)**: `_diagnostico_orcamento` põe `power_score`, `faixa` e `direcao` no JSON do pedido de
  reparo (o teste confere `79.5` e `[4.0, 13.0]`). **(c)**: `fit_orcamento` roda com
  `MAX_PASSOS_AJUSTE = 6` sobre uma cópia e só mexe em números (`custo_folego` 0..3 e
  `dano_base` do maior dano). A Carta ajustada leva `ajuste_orcamento`, e a que falha segue em
  `rejeitadas`, que vira `_rejeitadas_vocabulario`, com o motivo. **(d)**: o guard
  `isinstance(res, LoteRascunho)` do reparo ficou como estava (`draft.py:385`), e
  `test_reparo_fallback_llm` cobre o caso.
- **D-369-5**: há equivalência real. O teste copia o `_fit_orcamento` antigo congelado e compara
  com o novo em todas as Cartas de `data/cards/inimigos`, com 4 variações de dano (> 200 casos).
  O desvio do `primary_effect` (só roda se existe `efeito`) é neutro no bestiário, onde
  `efeito` sempre existe, e só evita um `KeyError` no rascunho.
- **R17**: a Carta segue o §3.3. É `passiva`, comum, `level_req` 1, Fôlego 0, `livre`, com
  `buff_iniciativa` 2 e descrição sem número. `lint_card` e `budget_error` ficam limpos,
  `validate_content` dá 0 erros, e iniciativa não está no "Nunca" do Corruptor (SPEC-335:29).
  A `nota_voz` segue o precedente das ondas de 27/10 e da 371. O produto honra a Carta: o
  `_has_vigilia` (`agents/combat.py:1933-1938`) lê o catálogo, e o teste usa as funções reais,
  sem mock. A mudança em `test_tronco_cartas_por_postura` (4 Cartas do Corruptor e a passiva
  isenta da regra "Fôlego 0 → `cena`") se justifica, porque a regra vale para ativas de
  tronco e o §3.3 prescreve `livre`.
- **R19 (B2)**: a passiva não entra no `full_deck`, por isso as Posturas não se movem. O
  Sangromante fica em +0,0.
- **Qualidade**: nenhuma função nova passa de 60 linhas. `draft.py` tem 454 linhas e
  `gerar_mecanica.py` diminuiu. `dup_helpers` não achou nada, e `ruff` passou limpo.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `specs/SPEC-369-cartas-balanco-metas-epico.md:451` | O `<sha-A>` registrado (`8985c4c0`) ficou velho. Depois dele, `81f06c22` (BASE.md, na `main`) e `8fe4e0dd` (régua) mudaram arquivos da Fase A, e a prova do R1/Etapa 8 (`git diff --exit-code <sha-A> -- <arquivos da Fase A>`) falha. | Atualizar o `<sha-A>` para o sha de `8fe4e0dd` após o rebase do pouso e listar os dois commits como de autor da régua. |
| P3-1 | P3 | `scripts/cards/draft.py:374` | O cabeçalho do pedido de reparo ainda diz "REJEITADAS pelo vocabulário", mas agora o motivo pode ser orçamento ou raridade. O LLM recebe uma instrução que contradiz a `direcao`. | Trocar por "rejeitadas pelo vocabulário, orçamento ou raridade; no orçamento, siga `direcao`". |
| P3-2 | P3 | `scripts/cards/draft.py:359` | O motivo "não coube em 6 passos" aparece mesmo com 0 passos possíveis. Exemplo: Carta abaixo da faixa com Fôlego 0, já que o ajuste só reduz poder (verificado com `power_score -0.5`, faixa `[0, 7]`). | Separar os casos: `passos == []` vira "ajuste não aplicável (abaixo da faixa)". |
| P3-3 | P3 | `tests/test_card_draft_orcamento.py:84` | `if len(llm.calls) == 2:` deixa o teste passar sem afirmar nada se o reparo não for chamado. Hoje ele é chamado (conferido). | Afirmar `len(llm.calls) == 2` sem condição. |
| P3-4 | P3 | `specs/SPEC-369-cartas-balanco-metas-epico.md:222` | No §3.1, a assinatura é `fit_orcamento(card, max_passos=6) -> tuple[dict, list[str]]`. A implementada é `(card, max_passos=40, passos=None) -> dict`. O §9 registra o que foi feito, mas não marca isso como desvio do desenho. A mudança se justifica, porque o padrão 40 preserva a equivalência com o bestiário. | Anotar o desvio no §3.1 ou no §9. |
| P3-5 | P3 | `specs/SPEC-369-cartas-balanco-metas-epico.md:507` | O Médico aparece com 45,8 na base e 46,7 "na repetição", sem causa registrada. O R19(d) do B3 em diante depende de uma base estável. | Antes do B3, isolar a causa (mudança de catálogo na `main` desde o sha-A ou não-determinismo) e registrar no §9. |

## Correções aplicadas

Nenhuma até agora (revisão inicial).

## Pendências

- P2-1 é do coordenador, no pouso da Fase B (é edição só da §9).
- P3-1 a P3-4 podem ir com o B3 ou num commit curto do executor B1.
- P3-5 é pré-requisito do B3 (coordenador/executor B3).

## Comandos rodados

```text
bash scripts/dev/pt.sh -n 0 tests/test_card_draft_orcamento.py tests/test_card_draft.py tests/test_spec387_draft.py tests/test_card_acervo_reparo.py tests/test_spec369_regua.py tests/test_mecanica_orfa.py → 189 passed
bash scripts/dev/pt.sh -n 0 tests/test_spec369_metas.py tests/test_size_budget.py → 4 passed, 15 xfailed
git diff --exit-code 1869254c HEAD -- <caminhos R2> evals agents/combat.py services/conflict_orchestrator.py → vazio
git diff --stat 8985c4c0 HEAD -- docs/spec369 tests/test_spec369_*.py → BASE.md (81f06c22, main) + test_spec369_regua.py (8fe4e0dd)
scripts/validate_content.py → 0 erros, 29 avisos (bestiário, preexistentes)
scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome repetido
ruff check (arquivos alterados) → All checks passed
```

(Os testes rodaram em série, `-n 0`, porque a RAM livre estava em 2,4 GB.)

## Rodada 2 (2026-11-04, commit revisado `130cc04f`)

> **Veredito:** `APPROVED` (escopo B1/B2; P2-1 fica com o coordenador no pouso, e P3-5 foi para o autor da régua em `b14c66c1`, que a Astra revisa)

- P3-1 fechado: `draft.py:377`. O cabeçalho agora diz "vocabulário, orçamento ou raridade; veja os motivos".
- P3-2 fechado: `draft.py:359-362`. Quando `passos == []`, o motivo é "sem passo possível", separado de "não coube em 6 passos". O teste novo `test_ajuste_sem_passo_possivel_tem_motivo_proprio` afirma os dois lados.
- P3-3 fechado: `test_reparo_aumenta_quando_abaixo` afirma `len(llm.calls) == 2` sem condicional.
- P3-4 fechado: o §3.1 registra a assinatura real e por que o desvio se justifica.
- Nada fora do escopo: o commit toca só `draft.py`, o teste do B1 e a spec.

```text
bash scripts/dev/pt.sh tests/test_card_draft_orcamento.py tests/test_card_draft.py tests/test_spec387_draft.py → 27 passed (-n 2)
ruff check + ruff format --check (draft.py, teste) → limpos
```

## Fase B (B3/B5/B6 + D-369-10) — 2026-11-04, commit revisado `1baa675b`

> **Veredito:** `CHANGES_REQUIRED` (2 achados P1, 4 achados P3)

Commits de produto revisados: `c2d05130` (B3), `f58016b8` (B5, só §9), `00448b33` (B6), `d986c92b` (artefatos) e `540deb81` (passo da D-369-10). Commits de régua: `8ef607c0` e `7a75a389`.

### Conferência

1. **R1/R2: ok.**
   - `git diff 7a75a389 HEAD -- <arquivos da Fase A>` dá vazio.
   - No intervalo `ef850520..HEAD`, os arquivos da Fase A só foram tocados por commits `test(cards)` de régua: `06bd8f39`, `33b08981`, `6ed6815d`, `8ef607c0` e `7a75a389`.
   - Nenhum commit de produto toca régua.
   - Os caminhos do R2, `evals/`, `agents/combat.py` e `conflict_orchestrator.py` dão `git diff --exit-code` vazio contra `ef850520`.
   - Os limiares mudaram depois da Fase B (`7a75a389`), mas por decisão escrita do dono (D-369-10), num commit separado de autor de régua. Os limites registrados são os números da Fase B e não podem piorar. Aceito.
2. **R18: limite estourado no processo** (P1-2, abaixo). O R18 diz que "passo que não move a métrica-alvo é revertido e **conta no limite**". Uma sondagem em árvore descartável é exatamente isso: um passo medido e revertido. A spec não abre exceção para ela. Pela regra, então, as sondagens contam.
   - **Heróis:** há 5 Cartas mantidas e 3 do B5 revertidas (8), mais 3 Cartas só sondadas: `bas_med_pressao`, `arc1_cal_pulso_medido` e `bas_cor_mofo`. Isso dá **11 Cartas, acima do teto de 8**. O `bas_cor_mofo` recebeu 3 tentativas, acima de 2.
   - **Famílias:** além das 2 Cartas registradas, foram sondadas outras: `abissal` +3, `conjurador` +3 e `predador_apice` +5. O teto é de 2 Cartas por família.
   - O B5 também mediu 3 Cartas num só braço, quando a regra é um passo por vez. Isso foi declarado.
   - O pacote que fica no produto respeita os limites. O problema é a busca (*forking paths*) sobre as sementes 0–19 e um `passos-0-19.json` que não registra a busca inteira. Por isso o `test_r18` passa.
3. **Passos mantidos: ok, com ressalvas P3.** Os 6 passos do B3 e o da D-369-10 têm `metricas_antes`/`depois` e `guarda_r19`. Os 4 do B6 têm `resultado` por célula, mas não têm `guarda_r19` por passo. Os parciais do B6 se justificam: movem a célula mais de 1 luta, não pioram outra célula mais de 5 pp, o lint barra o `dano_base` abaixo da arma, e a D-369-10 item 3 os aceita como limite.
4. **`mon_automato_fundicao` (agilidade 4→3): quebra um teste** (P1-1).
   - `tests/test_spec349_curadoria_legado.py::test_snapshot_bate_com_bestiario_original_nos_campos_de_slot` falha (`virtudes` {agilidade 3} != snapshot {agilidade 4}, `tests/fixtures/spec349_legado_snapshot.json:1757`). É uma criatura `valoria/unico` de Nova Arcádia, e os campos de slot dela eram invariantes da 349.
   - Os outros testes passaram: golden e snapshot da 330, `test_spec285_lethality`, `test_spec349_{mecanica,bestiary_lint,onda_nova_arcadia}` e `test_conflito_autoria_bestiario`.
   - Efeito no jogo real: o elite fica mais fácil (esquiva 14→13) para **todas** as Posturas, em todo encontro de Nova Arcádia, não só para o Médico. Isso está coberto pela D-369-10 ("um passo num único inimigo"). Convém ver se a SPEC-394 (recalibrar criaturas derivadas) mede essa criatura, para não haver conflito de calibração.
5. **Básicas a Fôlego 0: ok.**
   - A UI e o custo exibido vêm de `custo_folego`, então não precisam de mudança.
   - `budget_error` é `None` nas 3 básicas e em `bas_med_golpe`.
   - As descrições não mudaram e não têm número.
   - Nenhum texto do produto afirma "básica custa 1 Fôlego".
   - A mudança em `tests/test_card_piles.py` está justificada (R18b) e ficou mais forte, porque fixa o conjunto exato das Cartas a 0.
   - O `card_lint.lint_card` ainda acusa `momento` ausente nas básicas e nas Cartas de inimigo, e `tier` ausente nas Cartas de inimigo. Esses erros já existiam: o lint de onda não se aplica a esse acervo. Ficam como P3 de registro, porque o R18 pede "card_lint sem aviso".
6. **R17 (51,9 % × 60,6 %): os dois números estão certos, cada um no seu momento.** Com `level_req` 1, a passiva anula a emboscada em todos os níveis, então o `realista_369` do Corruptor é igual ao total `posturas` dele.
   - Na B2, esse total era 51,9 %.
   - No passo 5 do B3, `bas_cor_guarda` foi a Fôlego 0 e o total do Corruptor subiu de 51,9 para 60,6 %.
   - O valor que vale é **60,6 %**, o do estado final, e a correção no §9 está certa.
7. **Conteúdo: ok.** `validate_content` dá 0 erros (29 avisos de bestiário que já existiam). Os textos não mudaram, então a voz continua a mesma.
8. **Metas: ok.** `test_spec369_metas.py` dá 8 passed e 7 xfailed, e os 7 são todos do R22 (falta `confirmacao.json`).

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/bestiary.json:8997` × `tests/fixtures/spec349_legado_snapshot.json:1757` | O passo da D-369-10 deixa vermelho `test_spec349_curadoria_legado::test_snapshot_bate_com_bestiario_original_nos_campos_de_slot`, e a suíte do pouso falharia. | Num commit próprio, atualizar o fixture (`agilidade` 3) **ou** criar uma exceção nominal no teste, citando a D-369-10. Registrar no §9. Rodar `tests/test_spec349_*`. |
| P1-2 | P1 | `docs/spec369/passos-0-19.json`; §9 :640-642, :652, :673 | As sondagens revertidas não estão no registro. Pelo R18 elas contam no limite: são 11 Cartas de herói contra o teto de 8, 3 tentativas em `bas_cor_mofo` contra o teto de 2, e mais de 2 Cartas por família em 3 famílias. O `test_r18` passa só porque o registro está incompleto. | (a) Registrar cada sondagem em `passos-0-19.json` (`mantido: false`, `sondagem: true`, sem métrica inventada: só o que foi medido). (b) No §5, marcar o R18 como "pacote final dentro, processo fora". (c) Levar ao dono como D-369-11: aceitar o estouro e usar a Fase C (260–339, held-out) como a guarda contra overfit, ou reverter. Não editar a régua para isso. |
| P3-1 | P3 | `docs/spec369/passos-0-19.json` (2º passo de `bas_med_golpe`) | O passo registra `versao: [1, 2]`, mas o arquivo tem `versao` 3. O §9:628 diz "mesma versão". | Corrigir para `[2, 3]` e alinhar o texto do §9. |
| P3-2 | P3 | `passos-0-19.json` (B6) | Os passos do B6 não registram `guarda_r19`. A medição final mostra as Posturas iguais às do fim do B3, então a guarda vale no fim, mas não está provada passo a passo. | Anotar `guarda_r19` (ou "n/a: a arena de Posturas não usa Cartas de família", com prova). |
| P3-3 | P3 | §9 :686 | Falta registrar que o passo da criatura vale no jogo inteiro (todas as Posturas, Nova Arcádia) e se a SPEC-394 a mede. | Uma linha no §9 e no RELATORIO. |
| P3-4 | P3 | R18 ("card_lint sem aviso") | Os erros de `momento`/`tier` nas básicas e nas Cartas de inimigo já existiam e não vêm deste diff. | Registrar a isenção no §9, porque o lint de onda não vale para básicas e inimigos. |

### Comandos rodados

```text
git diff --stat 7a75a389 HEAD -- docs/spec369/{metricas_369,bot_pressagio}.py docs/spec369/{base-0-19.json,BASE.md} tests/test_spec369_*.py → vazio
git diff --exit-code ef850520 HEAD -- <R2> evals agents/combat.py services/conflict_orchestrator.py → vazio
pt.sh -n 0 tests/test_spec349_curadoria_legado.py → 1 failed, 4 passed (P1-1)
pt.sh -n 0 card_lint, card_piles, conflito_autoria_bestiario, mecanica_orfa, scene_cards, spec285_lethality, spec349_{bestiary_lint,mecanica,onda_nova_arcadia}, spec369_{metas,regua}, spec377_folego, card_acervo_reparo, card_effects_grammar → 983 passed, 7 xfailed (R22)
pt.sh -n 0 spec341_balanco, spec35{3,5}_*, spec362, spec363/364/367/387 golden guards, card_sim → 78 passed, 10 skipped
scripts/validate_content.py → 0 erros
```

(Rodei em série, `-n 0`, porque a RAM livre estava em 1,4 GB, com processos de outra sessão. Não reproduzi medição da arena.)

## Fase B — rodada 2 (2026-11-04, commit revisado `7d7a88cb`)

> **Veredito:** `APPROVED`. Fechado com D-369-11 e D-369-12 (§8, `46930fe7`). A Fase C é a guarda contra overfit; se ela reprovar, a decisão volta ao dono.

- **P1-1 fechado** (`3b57ed9b`). O fixture mudou em uma linha só: a `agilidade` de `mon_automato_fundicao` passou de 4 para 3, dentro do bloco dessa criatura. Fora essa linha, `tests/fixtures/` não muda contra `ef850520`, então o snapshot continua exato para as outras 123 criaturas. Prefiro isso a uma exceção nominal no teste, que o deixaria mais frouxo.
- **P1-2 fechado** por decisão do dono (D-369-12). O `passos-0-19.json` passou a ter 36 sondagens (`sondagem: true`, `mantido: false`). A Carta vai em `sondagem_carta`, por isso o `test_r18` conta só o pacote final. O processo fora do limite agora fica visível no artefato e no §9 ("pacote final dentro, processo fora"). Aceito.
- **P3-1 fechado.** As versões de `bas_med_golpe` estão em `[1, 2]` e `[2, 3]`.
- **P3-2 aceito.** Cada passo do B6 declara que não houve medição da guarda R19 depois dele, e que ela foi medida no estado final. Os totais de Posturas depois do B6 e da D-369-10 são idênticos aos de antes do B6. Os estados intermediários só aplicam subconjuntos das mesmas Cartas de família, e a Fase C remede tudo. Por isso a falta de medição por passo não esconde risco.
- **P3-3 e P3-4 fechados.** O §9 registra que a criatura muda em todo o jogo, e que os erros de `momento`/`tier` nas básicas e Cartas de inimigo são isentos do lint e já existiam (o gate é `validate_content`).

```text
pt.sh (-n 2) tests/test_spec349_*.py tests/test_spec369_*.py tests/test_card_piles.py tests/test_card_acervo_reparo.py → 782 passed, 7 xfailed (R22)
git diff --stat ef850520 HEAD -- tests/fixtures/ → 1 linha (spec349_legado_snapshot.json)
```
