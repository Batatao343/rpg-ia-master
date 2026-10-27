# SPEC-335 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Claude Opus 5.5, spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `bb8a8ce0`

## Escopo

Branch `spec-335`, `main...bb8a8ce0` (1 commit, 19 arquivos): Lote 0 (reparo R5 das 308
legadas: `data/cards/{arcanista,bestiario,corruptor,devoto,exemplos,exemplos_extra,medico,sangromante,tiers_5_plus}.json`),
Lote 1 (36 Cartas do Arcanista em `data/cards/posturas/arcanista_cinzento_*.json` +
`data/cards/_ondas.yaml`), `services/card_lint.py` (`GENERICAS`), testes
(`tests/test_card_acervo_reparo.py` novo, `tests/test_card_lint.py`, `tests/test_mecanica_orfa.py`),
`docs/cartas/PAINEL.md`, cabeçalho e andamento da spec. Conferido contra R1 (só Arcanista),
R3, R4, R5, R7, R8 e os desvios declarados no hand-back. Fora: Lotes 2–6, R6, smoke real.

### O que está correto (conferido de forma independente)

- **Lote 0 = zero mudança mecânica.** Script próprio comparou `main` × HEAD carta a carta
  nos 9 arquivos legados, excluindo só `descricao/contrapartida/raridade/momento`: **0 campos
  mecânicos alterados, 0 ids a mais ou a menos, 0 chaves de topo alteradas**. Nenhuma fixture
  de golden/snapshot mudou no diff; `test_card_effects_grammar.py` (snapshot do texto das 308)
  e `test_card_effects_review_spec330.py` passam sem regerar.
- 35 `descricao` vazias preenchidas (só as vazias; nenhuma `descricao` existente fora de
  `tiers_5_plus` foi reescrita). As 80 de `tiers_5_plus` têm `descricao`/`contrapartida`
  únicas e com sabor; `check_voice` passa nas 308 exceto `arc_imp_maquina` (nome com 5
  palavras — pré-existente, não tocado aqui).
- **Roda das Posturas** no Lote 1: nenhuma Carta com Sacrifício, `taunt` ou condição de
  provocar; `marca` (Vantagem contra o alvo) não é provocar. Primários bem cobertos (29 `dano`
  com área/Chamado, 7 `comprar`, 3 `descartar`, Vazão, Ressoar, Guardar).
- **Voz** do Lote 1: nomes ≤ 4 palavras, sem dígito na `descricao`, `descricao` ≤ 140; lint e
  orçamento verdes (`test_lote1_passa_no_lint_contra_o_acervo`).
- **`momento` do Arcanista** (legadas + onda 1) distinto: 0 duplicata exata, similaridade
  máxima 0,54 (< `LIMIAR_MOMENTO` 0,60).
- Nada em `evals/`; nenhum segredo; nenhum caminho de LLM tocado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/cards/_ondas.yaml:5`; `scripts/cards/promote.py:114` | `revisor_voz: dono (amostra de 20%, revisão posterior)` registra o dono como revisor sem ele ter revisado — atestado falso. O guard do `promote.py` recusa só a string literal `pendente`; o valor escolhido contorna o guard. Viola R8 ("revisão de voz do dono **antes** de entrar no pool"): as 36 Cartas já estão no catálogo (`cards.all_cards()`), sem gate de runtime por onda. | Escolher um dos dois, com o coordenador: **(a, conforme R8)** tirar as 36 do pool para `data/cards/_rascunhos/onda1_arcanista.json` e só rodar `promote.py --revisor-voz dono` quando o dono responder sobre a amostra; ou **(b)** campo separado e honesto: `revisor_voz: null` + `voz_status: pendente-dono` (+ `voz_revisada_em`), aceito pelo `promote.py` só com bandeira explícita `--voz-pendente`, e `validate_content`/checklist de release acusando onda com `voz_status != aprovada`. Em ambos, endurecer o guard do `promote.py` (recusar valor que contenha `pendente`/`posterior`, ou exigir valor de uma lista fechada). Mudança no `promote.py` é ferramenta da 336: fazer em commit separado e registrar. |
| P1-2 | P1 | spec §4.1 linha 63 (desvio 2); relatório de sim não versionado | A arena aprovou o lote com parâmetros escolhidos pelo executor (nível de entrada, 20 sementes), diferentes do default que o `promote.py` usaria sem `--sim-report` (`[1,3,5]`, 4 sementes). O relatório **não foi commitado** e não reproduz: (i) default, estado pré-promoção: **11 bandeiras `dominante`** (`arc1_cal_estilhaco` +8,3 pp, `arc1_cal_impacto`, `arc1_cal_quadrante`, `arc1_des_palma`, `arc1_des_raio_livre`, `arc1_des_fenda`, `arc1_des_caldeira_sem_fundo`, `arc1_imp_bomba_estopim`, `arc1_imp_arame`, `arc1_imp_terceiro_dia`, `arc1_imp_ultima_gambiarra`); (ii) por `level_req`, 20 sementes, uma Carta por vez: 2 (`arc1_des_dedos` +8,8 pp, `arc1_imp_gambiarra` +8,7 pp); (iii) por `level_req` agrupado, 20 sementes: 1 (`arc1_cal_pulso_medido` uso 60,7 %). O hand-back cita −15/−11 pp; eu obtive −13,8/−10,0 no melhor palpite da configuração. O código do evaluator não mudou, mas mudar níveis/sementes até não haver bandeira é mudar o denominador na mesma tarefa que otimiza o produto (AGENTS.md § integridade). Agravante declarado no desvio 1: o poder das Cartas de golpe foi posto em efeitos secundários **que a arena não mede** para passar sem bandeira. | Versionar o relatório e o comando exato (ex.: `docs/cartas/sim/onda1-arcanista.json` + linha no PAINEL). Protocolo da arena: ou o default do `sim.py`/`promote.py`, ou um protocolo novo (níveis por `level_req`, N sementes, `MIN_LUTAS`) **definido pela 336/coordenador**, não pelo executor do lote, e aplicado igual a todos os lotes. Rodar o lote no protocolo fixado e, para cada bandeira, ajustar a Carta ou justificar por escrito como falso-positivo de amostra (`vezes_na_mao` 6–8 nas raras/abissais). Abrir follow-up na 336: a arena medir efeitos secundários (área, Chamado, Rachadura) e o suporte `custo_folego: 0`; até lá o orçamento (`fx.budget_error`, verde) é o único freio dessas Cartas — dizer isso no PAINEL. |
| P1-3 | P1 | `data/cards/posturas/arcanista_cinzento_calibrado.json:5` (`arc1_cal_leitura`), `…_improvisador.json:39` (`arc1_imp_gambiarra`) e mais 8 | **R3 violado:** comum = "≤ 1 efeito + ≤ 1 palavra-chave". 10 das 18 comuns têm 2 efeitos (`arc1_cal_leitura`, `arc1_cal_estilhaco`, `arc1_des_faisca`, `arc1_des_dedos`, `arc1_des_palma`, `arc1_des_corrente`, `arc1_imp_parafuso`) e `arc1_imp_gambiarra` tem **3** (proteção + ganhar Fôlego + descartar). Nenhum lint aplica R3, e o campo `raridade` nem alimenta o orçamento (`fx.raridade` deriva do `patamar`; `lendario/mitico` → faixa `epica`, não `abissal`). | Reduzir as comuns a 1 efeito (o "dano + dano com Chamado" pode virar 1 efeito com `chamado`, se a gramática permitir; senão subir para incomum/`avancado` e rebalancear a distribuição 50/30/15/5) e passar `arc1_imp_gambiarra` a incomum com ≤ 2 efeitos. Adicionar `check_raridade` ao `card_lint` (comum ≤ 1 efeito e ≤ 1 palavra-chave; incomum ≤ 2; abissal exige `exaurir` + custo explícito em Entropia/Vitalidade; `raridade` coerente com o `patamar`), com teste. |
| P1-4 | P1 | spec §4.1 linha 58 (`[x] Lote 0`) | R4/R5 marcados como feitos, mas os `momento` de modelo das outras 4 Posturas não são distintos: duplicatas exatas (Sangromante ~12, Corruptor ~14, Médico ~9, Devoto ~6, fora as básicas sem `momento`) e pares com similaridade ≥ `LIMIAR_MOMENTO` (0,60): Devoto 20, Sangromante 32, Corruptor 31, Médico 27, Inimigo 10, virtudes 8. Pela R4 essas Cartas seriam "rejeitadas". | Não marcar o Lote 0 como completo: escrever "momento das 4 Posturas = placeholder; reescrito no lote de cada Postura (2–5)". Adicionar teste por Postura (0 duplicata exata e 0 par ≥ `LIMIAR_MOMENTO`) com uma lista de exceções explícita das Posturas ainda sem lote, que encolhe a cada lote (o Arcanista já entra sem exceção). |
| P2-1 | P2 | `tests/test_card_lint.py:333-337` | Contagem fixa 359 vai quebrar na SPEC-332 (88 `inf_*`) e em cada lote — o teste vira atrito, não garantia. | Manter `set(cards.all_cards()) == ids` (o objetivo real do teste) e trocar a contagem por composição: `legadas = set(eq.legacy_cards())`, `ondas = {cid for o in promote.load_ondas() for cid in o["cartas"]}`; afirmar `legadas \| ondas <= ids` e que `ids - legadas - ondas` é só básicas e prefixos de origem conhecidos (`bas_`, `inf_`, …), cada grupo com o tamanho declarado no seu dono (`_ondas.yaml`, arquivo da 332). |
| P2-2 | P2 | `tests/test_mecanica_orfa.py:850-890` | Cobertura é real, mas desigual: `comprar`/`descartar` passam por `resolve_turn` com Carta sintética (bom); `revelar`/`mover_alvo_zona` chamam `fx.apply_effect` direto (sem o caminho de Carta); `vigilia` chama `fx.add_vigilia` direto — não prova que uma Carta com `kind: vigilia` principal chega lá. `_reuse_test` replica à mão a fixture autouse de `test_card_effects_piles` (acoplamento frágil). Não é afrouxamento: as chaves entram no inventário porque passaram a existir Cartas ativas com esses principais. | Agora há Carta real para cada kind (`arc1_imp_remendo_cobre`, `arc1_imp_olho_latao`, `arc1_imp_carretel`, `arc1_cal_compasso`, `arc1_des_corrente`): registrar via `_play_active(kind, alvo)` como os demais `card:ativa:*`, com o observável (modificador `vigilia`, `out["revelacoes"]`, `distance_state`, pilhas com `RPG_CARD_DECK=on`). |
| P2-3 | P2 | `scripts/gen_tiers_5_plus.py:149` | Rodar o gerador sobrescreve o reparo das 80 (`descricao`/`contrapartida` genéricas, sem `raridade`/`momento`). O lint pega a `descricao` (`GENERICAS`), mas não a `contrapartida`. | Fazer o gerador preservar por id os campos de texto existentes (merge: só gera o que falta) ou recusar escrever sem `--force` quando o arquivo tem texto diferente do modelo; incluir a frase-modelo da `contrapartida` ("Consome Entropia e respeita a frequência") em `GENERICAS`/checagem própria. |
| P2-4 | P2 | `data/cards/_orcamento.json:3-12`; `services/card_effects.py:1545` | Dois vocabulários de raridade: o campo `raridade` (comum/incomum/rara/abissal) e a faixa do orçamento derivada do `patamar` (… `epica`, `apice`). `arc1_des_caldeira_sem_fundo`/`arc1_imp_ultima_gambiarra` declaram `abissal` e são orçadas como `epica`. | Registrar como decisão na spec (o orçamento segue o `patamar`; `raridade` é rótulo de complexidade) ou unificar na 336; o `check_raridade` do P1-3 cobre a coerência. |
| P2-5 | P2 | spec §4.1 linha 63 (desvio 3) | Defensivas com delta negativo grande no default (`arc1_cal_segunda_medicao` −25 pp, `arc1_cal_rede` −18,8 pp, `arc1_imp_bomba_estopim` −25 pp). Pela R4 da 336 só delta **positivo** (> +8 pp) vira bandeira, então não é bandeira — mas é sinal de carta fraca ou de bot cego para defesa. | Anotar no PAINEL como "a revisar" e abrir follow-up na 336 (bandeira `fraca` para delta ≤ −10 pp com amostra suficiente, e bot que joga defesa antes de estar ferido). Não mexer no evaluator nesta spec. |

## Correções aplicadas

Nenhuma ainda (revisão inicial).

## Pendências

- P1-1 depende de decisão do coordenador/dono (tirar do pool vs. `voz_status: pendente-dono`); a amostra de 7 ids está pronta para o dono.
- Follow-ups da 336 (P1-2 arena de efeitos secundários; P2-5 bandeira `fraca`) — dono: coordenador, spec de destino: SPEC-336 (ou nova).
- `arc_imp_maquina` (nome com 5 palavras, pré-existente) — renomear no Lote 0 se o snapshot permitir, ou deixar para o lote do Arcanista.

## Comandos rodados

```text
git diff main...HEAD --stat → 19 arquivos, +2575/−414
scratchpad/eqcheck.py (main × HEAD, campos mecânicos das legadas) → 0 diferenças
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_card_acervo_reparo.py tests/test_card_draft.py tests/test_card_effects_grammar.py tests/test_card_effects_piles.py tests/test_card_effects_review_spec330.py tests/test_card_lint.py tests/test_card_piles.py tests/test_card_sim.py tests/test_cards_prepare_api.py tests/test_mecanica_orfa.py tests/test_log_event_registry.py tests/test_no_silent_except.py → 330 passed, exit 0
bash scripts/dev/py.sh scripts/validate_content.py → 0 erros, 0 avisos
bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/posturas/arcanista_cinzento_{calibrado,descoberto,improvisador}.json (default) → 11 `dominante`
scratchpad/simcheck.py (pré-promoção; default | level_req×20 sementes) → 11 | 2 `dominante`
scratchpad/simcheck2.py (pré-promoção; level_req agrupado ×20 sementes) → 1 `dominante`
scratchpad/audit.py (R3/R7/roda no Lote 1) → 10 comuns com > 1 efeito; roda e voz OK
scratchpad/mom.py (similaridade de `momento` por Postura) → Arcanista OK; outras 4 com 20–32 pares ≥ 0,60
```
