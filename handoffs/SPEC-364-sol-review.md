# SPEC-364 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (re-revisão de `4c05ca40`: só P3 abertos; ver § Re-revisão)
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

Ver §9 da spec ("Correções da revisão Sol") e os commits `fix|test` posteriores a 50fb8f12.

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

## Re-revisão (2026-11-02, `50fb8f12..4c05ca40`)

**Veredito da re-revisão:** `CHANGES_REQUIRED`, só com P3 (nenhum P0/P1/P2 aberto). São 3 correções pequenas
de teste/registro; nada no motor. Pela regra "zero pendência" do dono, voltam à Terra; se o coordenador aceitar
P3-8..P3-10 como follow-up registrado, a spec pode pousar.

### Achados originais

| ID | Situação | Evidência |
|---|---|---|
| P1-1 | **Fechado** | `tests/test_spec364_flee_surfaces.py` semeia a perseguição (`alcancado`, `distante`, `afastado`, `quase_livre`), faz a fuga pela API e dá `pytest.fail` se nenhuma semente produzir o desfecho (não é mais vácuo). O contador envolve `get_llm` de 8 módulos (o `agents.combat` importa no topo, então o patch pega) e exige `calls == []` nas rodadas que não encerram a luta. O teste vácuo saiu de `test_spec346_board_no_llm.py`. A sonda antiga não se aplica mais (o laço removido era o objeto dela); o caso (a) alcançado → avança agora é afirmado com `pressionado → afastado` no `mech_log`, na mensagem e no Livro, e passa. |
| P2-1 | **Fechado** (ressalva em P3-9) | Mesmo arquivo: `mech_log`, mensagem e `/game/history` com a mesma trilha nos casos (a)–(c), regex de R3 em todas as superfícies, voz de R16, Carta de Cena disparando. (d) só afirma conflito encerrado e ausência de ids; (e) é unidade. `round_board` só é varrido por ids (o §9 justifica: é lista estruturada sem trilha). |
| P2-2 | **Fechado** | `agents/combat.py:3412-3413` grava `_last = {de, sacrificio}`; `_flee_roll_payload` devolve payload sem dado; `_flee_line` (`services/combat_preview.py:328-330`) escreve "Fuga · sacrifício aceito · escapou (afastado → livre)". `out["fuga"]` só é lido por `_flee_line` (conferido), então `total: None` não quebra ninguém. Teste `test_force_escape_has_no_stale_roll`. |
| P2-3 | **Fechado** | `fall_partition` inclui `inconscientes` (`services/round_log.py:602`); teste com nocaute antigo. Efeito colateral aceitável: no fallback determinístico o inconsciente antigo vira "já tinha tombado" (`round_log.py:806-808`), o que é verdade ("tombar" = cair). |
| P2-4 | **Parcial** → P3-8 | `tests/test_spec364_death_api.py` prova pela API mensagem, Livro, `death_context.killer`, crônica ("Smoke4A tombou em combate" íntegro) e `mech_log`, nos dois caminhos. Falta o "inimigo caído em rodada anterior" de R21, e o motivo registrado no §9 está, ao que tudo indica, errado (ver P3-8). |
| P2-5 | **Fechado** (ressalva em P3-10) | `test_no_internal_ids_or_hero_name_in_history_r29` com 2 fugas, Cartas de Cena, item livre longo, `quase_livre`/`alcancado` e a regra de voz. |
| P3-1 | **Fechado** (ressalva em P3-11) | `_V6_FALL_RE` com plurais, `cai/tomba morto` tratado como presente, verbo sem sujeito herdando o nome; 4 positivos novos e os 12 benignos seguem verdes. |
| P3-2 | **Fechado** | Prefixo "Na rodada final" sempre que há `last_out` (`round_log.py:638`). |
| P3-3 | **Fechado** | `_BUY_ASK_RE`/`_SELL_ASK_RE` (`agents/loot.py:177-202`): pergunta de compra cota o estoque; item que o mercador não tem → "não está à venda aqui". 2 testes novos. |
| P3-4 | **Fechado** | Saldo no singular só em 1000 milli (`AccountScreen.tsx:362`). |
| P3-5 | **Fechado** | Teste renomeado `test_settle_above_ceiling_capped`; R17 provado pela evidência do §6.3 (decisão do coordenador). |
| P3-6 | **Fechado** | `assert first != blow`. |
| P3-7 | **Fechado** | Fixture com o `A_end.message` bruto do staging; V6 rejeita o real e aceita o corrigido. |

### Achados novos

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-8 | P3 | `specs/SPEC-364-cartas-smoke4.md` §9 ("Limite honesto") e `tests/test_spec364_death_api.py:25-45` | O §9 afirma que "o inimigo morto em rodada anterior sai de `state["enemies"]` antes do resumo seguinte", o que deixaria R10/V6 **inertes em produção**. Reproduzi o sintoma com uma sonda (clone morto semeado → `build_summary` recebe só `[Smoke4A, Goblin 1]`, `mortos == []`), mas a causa é o **seed**: `add_second_enemy` cria um clone que não está no manifesto, e `em.reconcile_roster` (`agents/combat.py:2342`; `services/encounter_manifest.py:595-602`) corta todo "intruder" antes da rodada. Um inimigo que morre de verdade está no manifesto e continua em `enemies` (o nó só esvazia a lista quando `combat_over`, `agents/combat.py:3028`). Ou seja, o teste de R21 não tem o 2º inimigo caído, e o registro no §9 desinforma o coordenador. | Semear o 2º inimigo **também** em `combat["encounter"]["participants"]` (mesmo `participant_id`/`species_label`, status `morto`) e afirmar pela API que o resumo e os fatos contam a queda antiga no passado ("Antes do fim, … já tinha morrido"; texto ao jogador sem "<nome> tomba"). Corrigir o §9: o corte vem do manifesto no seed, não do motor. |
| P3-9 | P3 | `tests/test_spec364_flee_surfaces.py:117-123` | O caso (d) "escapa" não confere trilha em nenhuma superfície, só que o conflito fechou e que não há ids. R2(d) pede o mesmo `de → para` (`quase livre → livre`) onde ele aparece (`mech_log` "Fuga · … · escapou (quase livre → livre)"). | Afirmar `"quase livre → livre" in surf["mech_log"]` quando houver linha `Fuga ·`. |
| P3-10 | P3 | `tests/test_spec363_ids.py:201-202` | O passo "Quero ver o mercado" não verifica que a consulta aconteceu: o texto entra no blob sem asserção, então se o roteador não for à loja o item livre longo nunca é exibido e o teste passa igual. | `assert "Pelo que você carrega" in texts[-1]` (ou o nome curto "Faca de esfolar de osso de baleia") e `"Haldor usa" not in texts[-1]`. |
| P3-11 | P3 | `services/conflict_summary.py:534-543` | A herança de sujeito do V6 gera falso positivo com sujeito posposto: "Ao lado do Goblin, tomba o Minotauro." (o Minotauro caiu na rodada final, frase correta) dispara V6, porque a 1ª oração cita o Goblin e a 2ª começa pelo verbo. Custa prosa boa (fallback), não correção. | Só herdar o nome quando a oração com verbo não tem outro sujeito nominal depois do verbo (ex.: `bare` e nada além de complemento sem nome de participante); acrescentar a frase ao corpus benigno. |

### Comandos rodados (re-revisão)

```text
git diff 50fb8f12..HEAD --stat → 17 arquivos, +474/−57
pytest -n 2 test_spec364_* (13 arquivos) + test_spec346_board_no_llm + test_spec363_ids + test_spec363_outcome_text + test_remediacao_comerciante_real + test_card_effects_grammar → 189 passed, 2 skipped (Postgres)
sonda temporária (clone morto semeado, spy em build_summary; arquivo removido) → participantes sem o clone; causa = reconcile_roster (intruso fora do manifesto)
tsc -p web/tsconfig.json --noEmit → 0 erros
ruff check (arquivos alterados) → All checks passed
```
