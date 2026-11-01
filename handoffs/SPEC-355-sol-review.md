# SPEC-355 — revisão sol (review)

> **Veredito final:** `APPROVED_WITH_FOLLOWUPS` (re-revisão sobre `3deded66`; 3º passe sobre `aee8750e`; 1ª passada em `e78e7e80` foi `CHANGES_REQUIRED` pelo P1-1, agora corrigido)
> **Revisor:** Opus / Sol · **Data:** 2026-11-01 · **Commits revisados:** `e78e7e80` e depois `fbf675d0..3deded66` (branch `spec-355`, rebaseada em `main` `4d4e9182`)

## Escopo

`git diff main...spec-355` (11 commits, 49 arquivos): motor (R1–R4 em `services/conflict_orchestrator.py`,
`services/enemy_decks.py`, `agents/combat.py`), router (R5), conteúdo/ferramentas (R6–R10), balanço
(R11/R12/R17 + artefatos `docs/spec355/*`), guardas (R50–R53). Fora: smoke LLM real e R44 (são do
coordenador); arena não foi reexecutada (RAM) — só conferência dos JSON contra os relatórios.

**Integridade (R50/R51/R53): OK.** `git diff main...spec-355` vazio para `scripts/cards/sim.py`,
`docs/spec335/`, `docs/spec341/`, `data/cards/` (inclui `_orcamento.json`; nenhuma Carta de onda alterada),
`tests/spec330_equivalence.py`, `tests/fixtures/` (golden 330, snapshot de texto, `router_off_golden`),
`tests/test_spec341_balanco.py`, `config/flags.yaml`, `evals/`. Nenhum `with_structured_output`/prompt novo,
nenhum segredo em log. `arena_spec355.py` só importa o avaliador congelado (`arena_spec341 as B`) e
envolve `orch.run_round` no próprio processo.

**Expecteds alterados — justificados, não afrouxamento:**
- `tests/test_card_lint.py:416` — consequência direta do R9 (`intencao` sai de `REVELAR_PUBLICO_AVISO` por desenho).
- `tests/test_spec353_misc.py:67-75` — o R11 reexecuta o D6 da 353; o teste foi invertido e **endurecido**
  (agora exige `util in fora_do_conflito` e `util in player["deck"]`).
- `tests/test_spec346_router_fallback.py:10,68,82` — só a narração do fixture ganhou "bandido"/"goblin"; os
  desfechos (COMBAT/STORY) e os 12 casos seguros ficaram iguais. É o fechamento da P3-10 que o R5(a) pede.

**Motor — conferido e com teste que falha sem o fix:**
- R1: marca no chamador (`_tag_self_buffs`, fora de `_resolve_reaction_effect`); `test_tag_is_outside_resolve_reaction_effect` prova. Mutação (no-op em `_tag_self_buffs`) derruba o teste das duas ordens (2/2).
- R2: só `ataque`/`ataque_multiplo`, só com Provocação desta rodada, não rola se o alvo já é o provocador (rng intacto; arena solo inalterada), gasta 1 de duração por rolagem; teste da 339 verde sem mudar expected.
- R3: promessa só na cena (`scene["prenuncios"]`), gravada nos dois emissores (agente com presságio `on`, orquestrador com `!= on`, mutuamente exclusivos); fase antes da frustração testada.
- R4: comparação antes/depois no chamador; sem registro duplo (o caminho de Reação usa `record=False`).
- R5: (a)/(b)/(c) e bateria nova corretos; contexto de jogo segue bloqueando.
- R6: sem `--write` não grava (rodado: `exit=1`, `git status` limpo). R7/R8/R9/R10/R12/R17 ok.
- Números de `docs/spec355/RELATORIO*.md` batem com os JSON (recontei vitórias/lutas por célula); `arena-final == arena-a1`; `versoes` vazias; held-out com um único artefato por cenário.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_spec355_arena.py:30-36`; `specs/SPEC-355-cartas-pendencias-abertas.md:557` | O R45 manda o teste assertar "as faixas acima", que incluem o teto de 75 % **por subclasse (padrão)** com as exceções da 341 (avaro 75,2 / silencioso 76,6). O teste só checa o total por Postura. Nos artefatos: `arena-final.json` (0–19) tem **silencioso padrão 78,7 %** (pós-B era 76,2 %: o R11/R12 empurrou +2,5 pp), e `arena-confirmacao.json` tem avaro 77,6 % / silencioso 76,8 %. O 0–19 de 78,7 % não está nas pendências do §9 (só o held-out). Omissão do critério que falharia = afrouxamento por omissão no teste escrito por quem otimiza. | Adicionar a asserção de teto padrão por subclasse com um dicionário explícito `EXCECOES_TETO` (avaro, silencioso; valores dos artefatos) apontando §9, e registrar o silencioso 78,7 % (0–19, pós-R11/R12) nas pendências do dono. Sem mexer em número de Carta. |
| P2-1 | P2 | `services/conflict_orchestrator.py:2724-2729` | Quando a Provocação desvia, o registro sai contraditório: `pressagios_cumpridos` grava o `alvo_id` original e o log diz "cumpre o que o presságio anunciava." logo antes de "…muda de alvo." O resumo/IA pode narrar as duas coisas. | Chamar `_taunt_same_round` antes; se desviou, não anexar a linha "cumpre" (ou anexar com `alvo_id` novo e `desviado: true`). |
| P2-2 | P2 | `services/conflict_orchestrator.py:2672-2678` | O spec diz que a Provocação zerada "sai **depois** da ação do inimigo"; o código a remove (e loga "terminou") antes de a declaração resolver. Sem efeito mecânico visto (taunt só é lido na escolha de alvo), mas a ordem do registro fica "terminou" → ataque. Também: com Provocação antiga de outra fonte (B = alvo congelado) + nova (A), as duas perdem 1 de duração na mesma rolagem. | Adiar a remoção/linha para depois da ação (ou registrar o desvio no §9) e decrementar só as Provocações novas desta rodada. |
| P2-3 | P2 | `services/enemy_decks.py:450` | "Cumprida" é inferida por `plan(actor, rnd)`, não pela jogada efetiva. Se o plano manda a assinatura mas a declaração real não a joga (ex.: sem Fôlego/alvo), a promessa some calada no caminho `off` do presságio (no `on` o `_frustrate` existente cobre). | Conferir contra a declaração resolvida (ou registrar a limitação no §9). |
| P2-4 | P2 | `services/card_text.py:34-36` | Troca por substring sem fronteira de palavra: prosa comum ("fica sangrando", "enfraquecidos") vira "fica Sangrando"/"Enfraquecidos" no meio da frase. | Regex `\b(armadura_comprometida|enfraquecido|sangrando)\b` e, idealmente, só para as chaves com `_`. |
| P2-5 | P2 | `docs/spec355/RELATORIO-emboscada.md:16` | Diz que com R17 "os números não mudam", mas o Médico muda (`realista_com_contrapartida` 0,5321 vs 0,5352 em 0–19; 0,5617 vs 0,5609 em 20–99) — há Carta `buff_iniciativa` no `full_deck` do Médico em alguma célula. Observação lateral: o Médico vence **mais** emboscado (56,9 % vs 52,1 %), o que merece um olhar no wrapper da 346. | Corrigir a frase; anotar a anomalia do Médico no §9. |
| P2-6 | P2 | `tests/test_spec355_exemplos_fora.py:22-33` | `test_creation_pool_skips_exemplos` é vazio: `character_creator.build_player_sheet` não existe, então o teste nunca asserta nada. (O caminho real passa por `cards_for_class`, já coberto.) | Apagar o teste ou apontar para a função real de criação. |
| P2-7 | P2 | `scripts/gen_tiers_5_plus.py:305` | Em `--check` o gerador sai 1 hoje: `data/cards/basicas.json` e `data/cards/tiers_5_plus.json` divergem do que ele geraria. Não grava (R6 ok), mas o default nunca fica verde. | Registrar a divergência no §9 (pré-existente ou não) para quem for usar `--check` em CI. |
| P2-8 | P2 | `tests/test_spec355_arena.py:12`, `tests/test_spec355_guardas.py:31-39` | `EXCECOES_PISO` (Arcanista) é aceitável por R13/R18 (registrado para o dono), mas precisa de dono/spec de destino; e o guarda `git diff main` vira bloqueio permanente para qualquer spec futura que mude esses arquivos por protocolo (mesmo padrão da 353). | Comentar no teste a spec que deve remover a exceção; aceitar o padrão do guarda como está. |
| P2-9 | P2 | `tests/test_spec355_compra_utilitaria.py:63-70` | R52: `fora_do_conflito` e `scene["prenuncios"]` são campos persistidos novos; o teste de save antigo faz só `json.dumps/loads`, não `save_game_state`/`load_game_state`. | Um round-trip pela persistência real com combate em voo. |

## Correções aplicadas

Re-revisão (2026-11-01) de `fbf675d0..3deded66`. Os testes novos foram rodados contra o código de
`fbf675d0`, num worktree temporário depois removido, e **todos falham sem o fix** (5/5):
`test_diverted_attack_does_not_claim_the_original_promise`, `test_taunt_ends_after_the_enemy_action_in_the_log`,
`test_older_taunt_from_another_source_is_not_spent`, `test_promise_not_played_is_frustrated_by_the_effective_declaration`,
`test_condition_label_swap_respects_word_boundaries_and_prose`.

- **P1-1** `d08bc6ef`: `test_teto_padrao_por_subclasse` com `EXCECOES_TETO` medidas (silencioso 78,7 / todas 75,4 nas
  0-19; avaro 77,6 / silencioso 76,8 / todas 75,2 nas 20-99) e checagem de que a exceção é igual ao valor medido,
  sem folga. O §9 registra o silencioso 78,7 %. **Ok.**
- **P2-1/P2-2** `47612c06`: o desvio não loga "cumpre" e `pressagios_cumpridos` grava o alvo real. Gastam só as
  Provocações novas desta rodada (`fresh`, via shim para o `_taunt_target`), e o gasto e o "terminou" vêm depois de
  `_resolve_actor_turn` (`_spend_taunt`, nos dois caminhos). **Ok.**
- **P2-3** `dbb6e1b5`: a promessa fica `aguarda` quando o plano ainda manda jogar. `note_declaration` a cumpre pela
  `acao.card_id` efetiva, e `close_promises` (fim da rodada, antes da fase) frustra sem duplicar. **Ok.**
- **P2-4** `a2ad507c`: só chaves com `_` e fronteira de palavra. **Ok.**
- **P2-5** `d94533f0`/`3deded66`: o relatório foi corrigido (só o Médico mexe, por `med_dose_choque` no `full_deck`). Sobre a
  anomalia, **concordo** que é efeito do bot, não do wrapper: o wrapper só troca o `initiator` na rodada 0 (conferido
  em `arena_spec355.py:34-37`), e o ganho está concentrado em L3/L5, coerente com cura/Reação rendendo mais depois do
  dano. Fica bem a ressalva de que a mistura do Médico não é piso.
- **P2-6** `227ae164`: o teste de criação agora exercita a função real. **Ok.**
- **P2-7**: a divergência pré-existente está documentada no docstring do gerador e no §9. **Ok.**
- **P2-8** `d08bc6ef`: o guarda `git diff main` só vale na branch `spec-355`, e `EXCECOES_PISO` tem destino. **Ok.**
- **P2-9** `d94533f0`: round-trip por `persistence.save_game_state`/`load_game_state` com as chaves reais
  (`combat["scene"]["prenuncios"]`, `combat["pilhas"]["fora_do_conflito"]`), com e sem os campos. **Ok.**
- Integridade de novo: o diff de `main...3deded66` está vazio para avaliador, golden, orçamento, `data/cards/`,
  `flags.yaml` e `evals/`.

**Terceiro passe (2026-11-01), commits `cb8e62b9` e `aee8750e`:**

- **Expected da 295** (`tests/test_spec295_chefe_no_topo.py:224-232`): **preserva a intenção, não mascara
  regressão.** A Proteção natural vem do campo `protecao_natural` (`combat_mechanics.py:452`), não de condição.
  Tirar da conta só as condições com `source == "bst_defesa_instintiva"`, que é o id da Carta gravado em
  `conflict_orchestrator.py:1226`, mede exatamente "save antigo sem Proteção natural". Qualquer outra Proteção
  continua contando. Sugestão P2 (não bloqueia): assertar também que a condição filtrada é a da Reação, com
  `source_actor_id == "boss"`, para o filtro não esconder uma persistência indevida.
- **Bestiário:** as 7 trocas são coerentes com a lore. Conferi por Grep nome, descrição e ataques de cada criatura.
  - **Mudaram de arquétipo e de Carta:**
    - Devorador de Sol (lança e arco) → `tatico` + Bote Certeiro.
    - Pirata de Brekmar (cutelo e pistola, "briga suja") → `tatico` + Bote Certeiro.
    - Orc das Saídas Baixas ("embosca grupos pequenos") → `emboscador` + Golpe das Sombras.
    - Arpoador Osshari (arpão de leviatã) → `tatico` + Pancada Esmagadora. Encaixa como golpe pesado; só o tipo de
      dano (perfurante × esmagamento) é um detalhe de sabor.
  - **Conjuradores reais**, cujo ataque passou a `type: magic`:
    - Djinn, espírito elemental: Lâmina de Vento.
    - Gazer: Raio de Gelo.
    - Cultista "mago proibido": Extração Parcial.
  - O único consumidor mecânico de `attacks[].type` é `enemy_decks._is_melee_only`, e as 3 criaturas seguem
    `conjurador`, então o baralho delas não muda. A allowlist saiu e `validate_content.py` não acusa mais nada.
- **Arena:** `arena-bestiario-0-19.json` bate com o §9. As leituras padrão são idênticas às de `arena-final` em todas
  as Posturas e subclasses, só a elite muda (Devoto 64,2 → 61,5 %; Sangromante 61,0 → 59,8 %; Corruptor 45,6 → 46,7 %;
  Arcanista igual; Médico 52,1 → 51,2 %). Por isso `EXCECOES_TETO`, que trata do padrão, e `EXCECOES_PISO` (Arcanista
  44,4 %) continuam válidas sem regerar nada.
  Ressalva P2: `arena-final`, a confirmação 20–99 e a emboscada foram medidas com o Arpoador antigo. A leitura
  elite delas fica até ~5 pp otimista para o Devoto (elite 57,9 → 52,5 %). Não se regera nesta spec (R18), mas a
  próxima spec de balanço deve partir de uma base nova.

Testes do 3º passe, `-n 2`, todos com exit 0: `test_spec295_chefe_no_topo`, `test_spec355_*`, `test_enemy_decks`,
`test_spec353_misc`, `test_conflito_autoria_bestiario`, `test_import_bestiary_art`. `validate_content.py` sem erro.
**Veredito mantido: `APPROVED_WITH_FOLLOWUPS`.**

## Pendências

- P1-1 corrigido (ver acima). Resíduo aceito: `_taunt_same_round` aceita qualquer Provocação quando a fonte da condição nova é desconhecida (`"" in fresh_sources`, caso de Reação), o que é raro e só afeta a duração. Não bloqueia.
- Para o dono (já no §9, sem reajuste nesta spec): Arcanista 43,9 % held-out (< 45), Corruptor sem contrapartida de emboscada, avaro/silencioso acima do teto, Devoto +2,7 pp. Destino: spec nova de balanço com número novo.
- R44 não se aplica (nenhuma `versao` mudou; R14 não aplicado).

## Comandos rodados

```text
git diff main...spec-355 --stat -- <caminhos protegidos R50 + data/cards + flags + evals> → vazio
pytest -n 2 tests/test_spec355_*.py test_card_lint test_spec346_router_fallback test_spec353_misc test_spec341_balanco test_card_effects_grammar test_spec339*  → verde (exit 0)
pytest -n 2 test_card_acervo_reparo test_jev_router_port test_spec353_golden_guard test_card_piles test_enemy_decks test_spec346_* test_card_effects_review_spec330 test_round_multi_play → 387 passed
mutação R1 (`_tag_self_buffs` no-op, teste no scratchpad) → teste das duas ordens falha 2/2 (como deve)
py.sh scripts/gen_tiers_5_plus.py (sem --write) → exit 1, "mudaria basicas.json, tiers_5_plus.json", worktree limpo
script de conferência dos JSON da arena → bate com RELATORIO.md e RELATORIO-emboscada.md
mutação: os 5 testes novos rodados contra `fbf675d0` (worktree temporário) → 5 falhas (como devem)
pytest -n 2 test_spec355_* + card_lint + spec346_* + spec353 + 341 + grammar + 339 + decks/piles/multi_play/router/acervo em `3deded66` → exit 0
```
