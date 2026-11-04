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
