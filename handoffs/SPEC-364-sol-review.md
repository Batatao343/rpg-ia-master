# SPEC-364 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / Sol (spec-reviewer) · **Data:** 2026-11-02 · **Commit revisado:** `a6ab7d61`

## Escopo

`git diff main...spec-364` (11 commits, 44 arquivos): `agents/combat.py`, `agents/loot.py`, `api.py`,
`inventory.py`, `services/{chase,combat_preview,conflict_summary,creature_art,economy,round_log}.py`, front
(`TargetChip`, `ImageQuoteDialog`, `CombateTab`, `AccountScreen`, `StoryLog`, `PlayMenu`, `PlayScreen`, `App`,
`lib/estilhas.ts`, `lib/portraitOrder.ts`, `types.ts`), testes novos `test_spec364_*`, e2e `spec364-*`, e a spec
(R1–R29, §9). Confrontado com `specs/SPEC-364-cartas-smoke4.md` e `docs/spec364/achados-smoke4.md`.
Fora: smoke §6 (coordenador); e2e Playwright não rodados por mim (custo de RAM).

O que está correto: R1/R3 (o `de` agora vem de `previous_track`, depois de retomar/reiniciar a perseguição;
`TRACK_LABEL` com `alcancado`; rótulo desconhecido → ""), R4–R9 (catálogo antes do regex de modo, pergunta nunca
transaciona, duas seções, `short_name` só na exibição, mercador no contexto e no fallback), R11, R12 (V6 com
partição compartilhada), R14/R15 (scene_logs e status por `_voce` antes do dedupe), R18–R20 (`preco_milli`
string, coerência com o inteiro cotado, "até", plural, atalho em milli), R22 (bug real do fallback do cliente
corrigido), R23a (JSON e SSE com `play_index == 1`, save intacto), R25 (nenhum `with_structured_output` novo; R4/R6
cortam CLASSIFY), R26/R27 (sem diff em golden 330, `web/e2e/contracts`, `config/flags.yaml`, orquestrador,
`scene_cards`, `evals/`), R28 (campos opcionais; `tsc` verde). Nenhum segredo em log; nenhum writer persistente
novo (só campos aditivos de view).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_spec346_board_no_llm.py:352-379` | O teste de R24 é **vácuo**: só afirma algo `if found:` e o cenário nunca acontece. Sondei os 40 seeds com o mesmo laço: `last_mech_log` sai vazio em todas as rodadas (a declaração `{"kind": "flee"}` + "Fugir" não produz fuga nesse fixture), `found is None` e o teste passa sem asserção. Os warnings `combat.narrate_failed: AssertionError` no mesmo laço indicam que algum caminho chamou o stub de `_no_llm` e o erro foi engolido, então nem "0 LLM" está provado. Também falta a Carta de Cena de condição pedida em R24. | Semear o estado direto (perseguição já `alcancado` em `combat_meta["chase"]` + rng controlado) para forçar alcançado → avança; `assert found`; fazer o stub contar chamadas e afirmar `== 0` (não depender de exceção que o nó engole); incluir a Carta de Cena de condição. |
| P2-1 | P2 | `tests/test_spec364_flee_trail.py:48-115` | R2 exige o mesmo `de → para` em **5 superfícies** (`mech_log`, registro, `round_board`, mensagem, `/game/history`) nos 5 casos. Os testes só cobrem `_flee_roll_payload`, `_flee_line` e os logs de `_attempt_flee` (unidade). `round_board`, mensagem do turno e `/game/history` não são exercitados em nenhum caso; `test_force_escape_trail` não confere payload nem linha. | Um teste por `_combat_node` (ou TestClient) com estado semeado por caso (a)–(e), afirmando a mesma string nas 5 superfícies e o regex de R3 sobre todas. |
| P2-2 | P2 | `agents/combat.py:3402-3405` | Sacrifício aceito (`force_escape`) com perseguição **retomada** espalha o `_last` da rodada anterior (`total`/`difficulty`/`sucesso` velhos) e só troca o `de`; `_flee_roll_payload` então publica no `mech_log` o dado da rodada passada como se fosse desta, com veredito "escapou" (ex.: "Fuga · total 9 vs 12 · escapou (afastado → livre)"). Pré-existente, mas R2(e) trouxe esse caminho para o escopo e R1 mexeu nele. | No `force_escape`, gravar `_last = {"de": previous_track, "sacrificio": True}` (sem total) e, em `_flee_roll_payload`/`_flee_line`, emitir a linha de fuga sem dado para o sacrifício (ou nenhuma), com o mesmo `de → livre` do Livro. Cobrir em P2-1 (e). |
| P2-3 | P2 | `services/round_log.py:602` e `:638` | `fall_partition` só considera `mortos`/`caidos`; `inconscientes` nunca entra em `earlier`. Quando há qualquer queda anterior, `outcome_facts` rotula **todo** inconsciente como "Na rodada final, X perdeu os sentidos.", mesmo quem foi nocauteado rodadas antes. É um fato temporal falso entregue ao LLM (a classe exata do achado 4), e V6 não o pega. | Incluir `inconscientes` em `fall_partition` (e no `skip` do fallback) **ou** só prefixar "Na rodada final" para nomes em `now_names`, mantendo o formato antigo para os demais. Teste com nocaute na rodada 2 e vitória na 4. |
| P2-4 | P2 | `tests/test_spec364_death_digit_name.py` (arquivo) | R21 pede teste de **API** (TestClient, estado semeado) com asserções em mensagem, registro, `mech_log`, `death_context`, crônica e `/game/history`. O entregue é unidade (`_narrate_outcome`, `round_registry`, `outcome_facts`, `_killer_identity`); `death_context`, crônica, `/game/history` e `mech_log` ficam sem prova. O §9 registra o desvio, mas o critério de aceite R21 continua aberto e o achado 8 do smoke era justamente "sem teste ponta a ponta". | Semear o herói com Vitalidade 0 e Ferimentos a 1 espaço do Crítico final + rng fixo (ou `final_blows` forçado num seam de teste) e afirmar pela API; se for inviável, a spec precisa rebaixar R21 explicitamente (decisão do coordenador) em vez de marcá-lo verde. |
| P2-5 | P2 | `tests/test_spec363_ids.py:15-25` | R29 pede que `test_no_internal_ids_in_history` passe a **incluir** 2 fugas seguidas, Carta de Cena de Carga, consulta do mercado com item livre longo e a regra de voz de R16, e que o padrão ganhe `alcancado`/`quase_livre`. Só `\balcancado\b` foi acrescentado ao detector; nenhum cenário novo, sem `quase_livre`, sem a regra de voz. | Estender o cenário do teste com os três eventos e acrescentar `quase_livre` e a checagem "não começa com o nome do herói nem contém `<nome>:`". |
| P3-1 | P3 | `services/conflict_summary.py:442`, `:510` | V6 só vê verbos de queda no singular presente (`tombam`, `caem`, `morrem` passam) e `morto` conta como marca de passado, então "o Goblin cai morto ao seu lado" é aceito, que é o mesmo erro do smoke. A divisão por vírgula também deixa passar "o Goblin, ferido, tomba". | Acrescentar plurais a `_FALL_RE` (no uso do V6); tirar `morto` das marcas quando colado ao verbo no presente (`cai morto`, `tomba morto`); avaliar oração por vírgula só se o nome e o verbo não estiverem em orações vizinhas. Somar esses casos ao corpus (positivos) sem quebrar os 12 benignos. |
| P3-2 | P3 | `services/round_log.py:638-647` | R10/§3.3 dizem que as quedas da rodada final saem como "Na rodada final, …". O prefixo só aparece quando existe alguma queda anterior; sem ela, o fato fica "X morreu." como antes. Não é um bug (preserva os fatos da 363), mas é um desvio da letra da spec. | Registrar no §9 como decisão de execução (ou aplicar o prefixo sempre que `last_out` existir). |
| P3-3 | P3 | `agents/loot.py:185` | `_shop_question_quote` dá prioridade ao inventário: "Me vende uma tocha?" com uma Tocha na mochila responde o preço que o mercador **paga** ("o mercador paga N"), não o preço de compra. Não transaciona, mas responde à pergunta errada. | Com marcador de compra (`me vende`, `vende`, `comprar`, `custa`, `quanto custa`), resolver primeiro pelo estoque (`_resolve_item_ref(..., "buy")`); inventário só para `vender`/`vale`/`paga`. Adicionar o caso ao `test_question_never_trades_item`. |
| P3-4 | P3 | `web/src/components/AccountScreen.tsx:362` | R19 manda aplicar o plural aos textos de saldo de `AccountScreen`; o saldo principal continua `shards(...) <span>Estilhas</span>` (saldo de exatamente 1000 milli mostra "1 Estilhas"). A linha de consumo por categoria (`:426`) também mantém "Estilhas" fixo. | Usar `estilhasLabel` (ou o mesmo teste de `=== 1000n`) no rótulo do saldo; a linha agregada pode ficar como está, registrada. |
| P3-5 | P3 | `tests/test_spec364_portrait_debit.py:17-41` | R17 (único oráculo de "débito = liquidado ≤ teto, reserva 0") não rodou: os 2 testes dependem de `RPG_TEST_DATABASE_URL`, que não existe localmente **nem no CI** (nenhum workflow define Postgres). Como o motor de cobrança não mudou e o §6.3 confere débito e reserva no staging, aceito como follow-up, não como bloqueio. Além disso, `test_settle_above_ceiling_rejected` afirma o limite no teto (anomalia financeira), não recusa: o nome mente. | Renomear para `test_settle_above_ceiling_capped`; rodar os 2 testes com Supabase local antes de marcar R17 (ou registrar no §6 o débito/reserva do staging como a prova); anotar no §9 que essa família de testes não roda no CI. |
| P3-6 | P3 | `tests/test_spec364_death_digit_name.py:116` | `assert blow != first or blow` é tautológico (passa sempre que `blow` não é vazio). A asserção útil é a seguinte (`blow == species_label_for(ENEMIES[0])`). | Remover a linha ou trocar por `assert first != blow` com um cenário em que o 1º ativo não é o autor. |
| P3-7 | P3 | `tests/fixtures/spec364_smoke.py` | R13 pede o texto **real** do staging; a fixture usa uma reconstrução com a frase citada (registrado no §9). | Coordenador: colar o `A_end.message` bruto do `scratchpad/smoke4/stg/stg_log.jsonl` (sem segredos) e manter o teste. |

Avaliação de R17 sem Postgres (pergunta do coordenador): **aceitável como follow-up**, não como critério cumprido.
O código da liquidação não foi tocado, a regra já é coberta pela SPEC-352 e o §6.3 mede débito e reserva no
staging. Mas o checkbox de R17 só deve ser marcado com os 2 testes rodados num Postgres ou com a evidência do §6.3
anotada como a prova (P3-5).

## Correções aplicadas

(nenhuma ainda; o executor preenche por commit)

## Pendências

- P1-1, P2-1..P2-5: obrigatórios antes do pouso (executor Terra, nesta spec).
- P3-1..P3-7: zero pendência por decisão do dono → corrigir nesta spec; P3-5/P3-7 dependem do coordenador
  (Postgres local ou evidência do §6.3; texto bruto do smoke).
- Smoke §6 (coordenador).

## Comandos rodados

```text
git diff main...HEAD --stat → 44 arquivos, +1919/−147
pytest -q tests/test_spec364_*.py tests/test_spec346_board_no_llm.py tests/test_spec363_ids.py tests/test_remediacao_comerciante_real.py → 98 passed, 2 skipped (RPG_TEST_DATABASE_URL)
sonda temporária do laço de R24 (40 seeds, arquivo removido) → found=None; last_mech_log vazio; warnings combat.narrate_failed
node --test web/tests/spec364-estilhas.test.mjs web/tests/spec347-components.test.mjs → 17 pass
tsc -p web/tsconfig.json --noEmit → 0 erros
ruff check (arquivos Python alterados) → All checks passed
git diff main...HEAD -- evals/ tests/fixtures/spec330_legacy_golden.json web/e2e/contracts config/flags.yaml services/conflict_orchestrator.py services/scene_cards.py → vazio
```
