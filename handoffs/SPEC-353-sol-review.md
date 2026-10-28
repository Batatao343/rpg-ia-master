# SPEC-353 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, revisor independente) · **Data:** 2026-10-28 · **Commit revisado:** `7d8b34b7`

## Escopo

Branch `spec-353` (`git diff main...spec-353`, de `c5aa4d01` a `7d8b34b7`): `services/cards.py`,
`conflict_orchestrator.py`, `round_log.py`, `combat_preview.py`, `conflict_summary.py`, `card_text.py`,
`encounter_manifest.py`, `prose_guard.py`, `combat_targeting.py`, `enemy_decks.py`, `agents/combat.py`,
`agents/loot.py`, `api.py`, `observability/events.py` e os testes `tests/test_spec353_*` mais os três
testes antigos com expected alterado. Fiz conferências pontuais com os estados reais do smoke
(`docs/spec353/smoke/state-*.json`) e uma rodada de ponta a ponta do objeto de cena via `orch.run_round`.
Ficaram fora: o front (SPEC-354), a reexecução da arena (só li `docs/spec353/arena.md`) e o smoke real (§6).

Pontos verificados que estão OK:
- **Golden da 330 (foco 6):** `git diff main -- tests/spec330_equivalence.py tests/fixtures/` está vazio;
  `test_card_effects_grammar.py` passa; `final_blows`, `absorvido`, `condicoes_novas` e `sem_vitalidade`
  nascem no orquestrador (`_check_terminal(record=True)` só nos chamadores de turno, tick e auto-dano;
  `_annotate_absorbed` roda depois de `ct.resolve_turn`). Não há diff em `data/cards`, `config/flags.yaml`
  nem `evals/`.
- **Autoria (foco 2):** rodei `validate_attribution` sobre o `message` **verbatim** dos três estados reais,
  com a autoria que o motor registrou (d5: Sussurro Faminto acertou na Última Ação; k4: golpe final do
  Sangramento, golpe do herói errou; r6: Corte de Troca acertou). O resultado foi d5 → `V1`, k4 → `V3`,
  r6 → `V2`. As linhas de `authorship()` entram no `<fatos>`. O fallback determinístico
  (`final_blow_sentence`) diz o autor certo. O orçamento de 6 s está em `_fast_text(budget_s=…)` e o guard
  de FallbackLLM continua em `_fast_text_call`. Não há `with_structured_output` novo.
- **Ordem (foco 3):** `chrono_events` é a fonte única de `round_registry`, `mech_log` e `round_board`. Os
  expected alterados em 346/347 (`test_spec347_round_board` DoT com `ator_id=None`/`lado="efeito"`,
  `test_conflito_cartas`, `test_combat_preview`) seguem a spec e não ficaram mais fracos.
- **Custo e R14 (foco 4):** `test_r14_exact_sum_with_self_harm` fecha a conta exata em 40 casos e a linha
  `custo` aparece nas três superfícies.
- **Contrato 354 (foco 7):** `tipo`/`custo`/`queda`/`pressagio` estão presentes, `fora_de_combate` está em
  `INVALID_REASONS`, `prepared_slots=DECK_MAX` e `baralho{}` só com o Baralho `on` e `deck` não vazio. Em
  `off` nada muda. O registro sobrevive ao fim do conflito e é limpo na abertura.
- **Eventos novos:** registrados em `observability/events.py` e em `EVENTOS_DE_LOG.md`, sem texto nem
  segredo no payload.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/cards.py:530-535` | **R1 não funciona no caminho real.** `_in_scene_hand` só lê `state["combat"]["pilhas"]`, mas o motor chama `use_card` com o `round_state` do agente (`agents/combat.py:2490-2499`: `{"player", "_piles", "_deck_mode"}`, sem a chave `combat`). Reproduzi via `orch.run_round` com pilhas reais (`start_piles` + o objeto na mão) e o `round_state` de produção: o log sai `"Derrubar (Sino Rachado) não pôde ser jogada."` e não há ataque do herói. O item 1 (P1 do smoke) continua aberto; só a mensagem deixou de vazar o id. O teste unitário passa porque monta `{"combat": {"pilhas": …}}`, um formato que o motor nunca usa. | Ler também `state.get("_piles")`, algo como `piles = state.get("_piles") or ((state.get("combat") or {}).get("pilhas"))`. Acrescentar um teste de ponta a ponta: `orch.run_round` com `state={"player": h, "_piles": piles, "_deck_mode": "on"}` e o objeto na mão deve gerar um ataque com `card_id` = o id temporário e cobrar a frequência. O ideal é ter também um teste via `_combat_node`. |
| P2-1 | P2 | `tests/test_spec353_scene_card.py:67-69` | **O teste do contrato R2 não testa nada.** `bas_golpe`/`bas_guarda` não existem no catálogo (`cards.get_card` devolve `None`), então o laço cai em `continue` nas duas iterações. Também não cobre "a mão inicial dos 5 baralhos básicos + 1 objeto". Se este teste fosse real e usasse o formato de produção, teria pegado o P1-1. | Montar a mão com `card_piles.start_piles` para as 5 Posturas (ids reais `bas_dev_golpe` etc.) mais 1 objeto de cena, e chamar `use_card` com o formato `{"player", "_piles"}`. Pode haver um `assert` com o número de Cartas checadas para o teste nunca ficar vazio. |
| P2-2 | P2 | `services/combat_preview.py:172-192` | **R19/R21: `dano_*_apos_defesa` diverge do motor.** O cálculo subtrai `armor.protecao + cond_prot` sempre. O motor (`conflict_damage.py:276-312`) só aplica a armadura se ela for compatível (`is_fisico` ou `resist_tipos`) e não estiver Comprometida, tira 1 contra `perfurante` e ainda gasta Integridade (`reducoes_max`). Exemplos: uma Carta arcana contra alvo blindado mostra a prévia reduzida e o motor não reduz; um golpe perfurante absorve 1 a menos. O teste `test_preview_known_defense_only_public` só confere a aritmética `dano_min − 2` e não o motor, então o oráculo R21 "= dano real" com Proteção P não foi provado. | Restringir `defesa_conhecida` ao caso público e certo: armadura não Comprometida e dano físico (senão `None`, porque `resist_tipos` é oculto), com o ajuste de `perfurante`. Integridade/`reducoes_max` também é pública (`integridade_atual`), então incluir ou documentar. Fazer o oráculo R21 rodar o motor com o alvo blindado. |
| P2-3 | P2 | `tests/test_spec353_registry.py:147-162` | **R11 com textos parafraseados e autoria escrita à mão.** O teste usa frases curtas inventadas e um `_auth(...)` manual, não os textos nem o `last_out` reais. Conferi manualmente que os três textos verbatim são rejeitados, mas a prova não fica versionada, e o caminho `authorship(last_out)` → `validate_attribution` não é testado de ponta a ponta. | Copiar os três parágrafos verbatim (do `message` dos `state-*.json`) para o teste. Acrescentar um caso que monte o `last_out` com `final_blows` via `orch.run_round` (golpe final por DoT de aliado e herói que errou) e passe por `round_log.authorship` antes de `validate_attribution`. |
| P3-1 | P3 | `services/combat_preview.py:541` | A entrada `custo` do `round_board` usa a categoria crua (`ferimento critico`, sem acento), contra R34. | Usar `round_log._cat_pt`/`_region_phrase` como no registro. |
| P3-2 | P3 | `services/prose_guard.py:494` | O plural é feito com `label + "s"` e o numeral é sempre masculino: dá "Só dois Criaturas…", "Anão-Ecos", "Lobo Cinzentos". | Usar um numeral pelo gênero (duas/dois) e um plural simples por palavra (ou o plural do bestiário, se houver). Na falta disso, usar uma frase sem plural ("Só N do grupo avança…"). |
| P3-3 | P3 | `services/round_log.py:217` | R28 nunca dispara: `public_panel` não tem `virtudes`, então `corpo` é sempre `None` e "faltam N Ferimentos Críticos" não aparece. É seguro (não vaza nada), mas o requisito ficou morto. | Usar o mesmo gate de Corpo revelado da prévia (`combat_preview.py`, que lê o conhecimento revelado). Se isso não couber, registrar em §9 que R28 ficou só com a frase base. |
| P3-4 | P3 | `services/conflict_orchestrator.py:265`, `:446` | `_sem_vit_avisado` e `_taunt_resisted` são gravados **no ator** e vão para o save (`enemies`). `_taunt_resisted` também é posto em `_taunt_target` durante o forecast do presságio e só sai na rodada seguinte. Não afeta mecânica nem o golden (os testes passam), mas contraria o espírito de R40/R51 ("nunca gravado no ator"). Os dois também faltam em `NEW_KEYS` do guard. | Guardar em `combat_meta`/`out` (ex.: um set de avisados em `combat_meta`) ou, se ficar como está, pôr os dois nomes em `NEW_KEYS` de `test_spec353_golden_guard.py` e anotar a exceção em §9. |
| P3-5 | P3 | `tests/test_spec353_spawn_count.py` | Foco 8: só `hint_core`/`is_generic_hint` e `count_drift` têm teste unitário. Não há teste de que, com a dica "a criatura além das estacas", o spawn escolhe a espécie do scanner (não sai "Criatura Além das Estacas") e de que a narração de entrada ganha a frase de reconciliação no `_narrate_entrance`. | Acrescentar um teste de agente com `_install_llm` e `_scan(("Bandido", 2))` (como em `test_spec353_agent.py`) cobrindo o nome e a frase. |

## Correções aplicadas

(nenhuma ainda; o executor preenche depois)

## Pendências

- Antes do pouso: P1-1 e P2-1 (bloqueiam). P2-2 e P2-3 também devem ser fechados nesta spec, porque são
  oráculos que a spec exige (R21 e R11).
- P3: podem virar follow-up; se ficarem para depois, o executor registra em §9.
- O §9 "Etapa 0 (c)" segue aberta (o 6 do Penitente ainda não foi provado como Proteção). O smoke §6 fecha.

## Comandos rodados

```text
git diff main...HEAD --stat -- tests/spec330_equivalence.py tests/fixtures/ data/cards config/flags.yaml evals/ → vazio
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec353_*.py tests/test_card_effects_grammar.py tests/test_card_effects_review_spec330.py tests/test_conflict_summary_lifecycle.py tests/test_encounter_manifest.py tests/test_prose_guard.py tests/test_scene_cards*.py tests/test_spec346_{board_no_llm,loot_once,mech_log,outcome,saves,spawn_count_narration,spawn_hint,vigilia}.py tests/test_spec347_{forge_reasons,initiative_view,mech_log,round_board}.py tests/test_combat_preview.py tests/test_conflito_cartas.py → ~509 passed
scratch: cards.use_card com {"player","_piles"} (formato do motor) → recusa; com {"combat":{"pilhas"}} → ok
scratch: orch.run_round com objeto de cena na mão e round_state de produção → "Derrubar (Sino Rachado) não pôde ser jogada.", sem ataque do herói
scratch: validate_attribution(message verbatim, autoria do motor) → d5 V1, k4 V3, r6 V2
scratch: cards.get_card("bas_golpe"/"bas_guarda") → None
```
