# SPEC-199 — XP e números de recompensa fora da prosa do narrador

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-226 `done` (quantidade de XP correta antes de projetar o evento) · SPEC-144 e SPEC-077 `done` são evoluídas, não reabertas. R12 (cura no inimigo) foi transferido para a SPEC-232 (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-203, SPEC-205, SPEC-212 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 04 (parte a)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false` — escopo limitado (um nó + projeção aditiva + chip de UI), sem mudança de regra de XP nem de schema de save
> **EVAL_AUTHORING_REQUIRED:** `true` — eval narrativo "prosa sem números mecânicos de recompensa" (autoria em tarefa separada, ver seção 9)

---

## 1. Contexto & Objetivo

No playtest o jogador viu "+N XP" dentro do texto do narrador. A decisão de produto fechada [D] (`DECISOES_PRODUTO.md`) é: **"O chat recebe desfecho; UI recebe XP e números."** Esta spec elimina o vazamento de números de recompensa para a prosa e cria a superfície estruturada (campo na API + chip/toast) por onde o XP passa a chegar. Não muda quanto XP é dado nem quando.

Fatos observados no HEAD `6b94f66`:

- [F] `agents/combat.py` (~l.922-929): após os kills, `pg.grant_xp` roda e então `logs.append(f"+{xp} XP" + (f" — NÍVEL {n}!" ...))`. Os `logs` são a única entrada mecânica do narrador: `_narrate(player, enemies, logs, ...)` embute-os em `<log_mecanico>` (l.561-585); logo o LLM pode (e vai) ecoar "+N XP" na prosa.
- [F] **Os fallbacks imprimem `logs` literalmente**: o fallback de `_narrate` (l.598-601, após o `except`) devolve `"⚔️ " + "\n".join(f"• {l}" for l in logs)`; `_narrate_fall` imprime `logs[-4:]` (l.553-558); o ramo `is_simulation` imprime todos os logs (laboratório, SPEC-090). Com a linha de XP em `logs`, o fallback mostra "• +N XP" como narração.
- [F] Há um **segundo vazamento, independente do combate**: `services/turn_outcome.py::render_player_message` (SPEC-144) anexa ao texto do jogador `\n\n[RESULTADO] +N ouro · +N XP · +qty item_id · N missão(ões)...`. `format_response` (`api.py` ~l.1071) usa `player_facing_message(state)` = `last_turn_outcome.player_message`; portanto **todo turno com XP (combate, beat, quest, armadilha) mostra "+N XP" na mensagem do chat**, mesmo depois de corrigir o combate. `tests/test_matriz_a_contratos.py` e `tests/test_pre_matrix_contracts.py` referenciam `[RESULTADO]`.
- [F] `last_turn_outcome` (`xp_delta`, `level_delta`, `gold_delta`, `items_gained`, `quests_completed`, `receipt_id`, `event_ids`) já é calculado em `agents/turn_finalizer.py`/`finalize_outcome` por delta de estado, é persistido em `persistence.py` (~l.594) e **não é projetado** em `GameResponse` (`api.py` l.1028-1059) nem existe em `web/src/types.ts` (`GameResponse`, l.462-489).
- [F] Outras fontes de número na mensagem: `agents/loot.py` (`[SISTEMA] +Nx item | Ouro ±N (total T)` em compra/venda l.225-231; `[SISTEMA] +N de ouro` no saque l.278-282, via `_player_facing_message`, l.132-135). XP de beat (`agents/storyteller.py` l.802-812) e de quest (`services/event_processor.py` l.318-329) só chegam à mensagem pelo recibo `[RESULTADO]`, não por log.
- [F] XP/nível já têm superfície no HUD (`web/src/components/Hud.tsx` l.153, `player_stats.xp`/`xp_next_level`) e level-up pendente já é projetado (`pending_choices`, `level_up` em `api.py` l.1127-1128, `_levelup_block` l.1291) e consumido por `LevelUpModal`. Falta o **evento de ganho** (delta do turno).
- [F] POST e SSE convergem em `_run_turn_collected` → `format_response`; o SSE emite o mesmo objeto no evento `state` (`api.py` ~l.3462). Replay por `action_id` devolve `format_response(state)` do save (`api.py` ~l.3331). Um campo derivado de estado persistido herda paridade e idempotência.
- [F] Precedente de campo estruturado público alimentado por estado: `last_economy_action` (`state.py` l.463).

Objetivo: (1) nenhum número de recompensa (XP, nível ganho, ouro/itens/quests do recibo) na prosa do narrador nem em seus fallbacks; (2) campo estruturado `turn_outcome` na projeção da API e em `types.ts`; (3) a UI exibe o ganho como chip/toast mecânico, sem redesenhar layout (layout é SPEC-204/205).

## 2. Requisitos

- **R1** — [R] O nó de combate não insere XP/nível em `logs` nem em qualquer texto enviado a `_narrate`/`_narrate_fall`. Teste causal: após vitória com XP>0, o prompt montado para `_narrate` não contém `XP`, `NÍVEL` nem o valor de `xp_for_kills`, e o fallback de `_narrate` também não.
- **R2** — [R] O XP continua aplicado por `pg.grant_xp` (valor e level-up inalterados — não mudar regra) e refletido em `last_turn_outcome.xp_delta`/`level_delta` pelo finalizer existente. Exatamente um `grant_xp` por conjunto de kills.
- **R3** — [R] `render_player_message` (SPEC-144) deixa de anexar `[RESULTADO] ...`. O texto do jogador é a prosa guardada, sem bloco numérico. A remoção de frases "nada novo foi obtido" quando há ganho (`_NEGATIVE_REWARD`/`_NEGATIVE_ITEM`) **permanece**. `last_turn_outcome.player_message` segue como campo canônico da prosa.
- **R4** — [R] Nova projeção pública `turn_outcome` em `GameResponse` (aditivo, default `{}`), com whitelist: `receipt_id`, `turn`, `xp_delta`, `level_delta`, `level_after`, `gold_delta`, `items_gained` (lista `{id, name, qty}` com nome de exibição resolvido em Python, nunca só `item_id` cru), `quests_completed` (lista `{id, title}`), `source` (`"combat"|"loot"|"story"|"quest"|"mixed"|"none"`, derivado de rota/deltas, nunca do LLM). Não expor `event_ids`, `transition_readiness` nem hashes internos.
- **R5** — [R] Paridade POST/SSE: o evento SSE `state` carrega o mesmo `turn_outcome` (mesmo `model_dump`); nenhum evento SSE novo é obrigatório. Os chunks `narrative` do SSE nunca contêm o recibo (consequência de R3).
- **R6** — [R] Idempotência: reenvio com o mesmo `action_id` devolve o mesmo `turn_outcome` (mesmo `receipt_id`) sem novo grant de XP; `GET /game/state` após reload devolve o `turn_outcome` do último turno persistido, e o cliente só anima o chip quando o `receipt_id` é novo para a sessão de UI (R8).
- **R7** — [R] Persistência: sem mudança de schema de save (dado já existe em `last_turn_outcome`). Save pré-SPEC-199 sem `last_turn_outcome` carrega e projeta `turn_outcome == {}`; save cujo `player_message` já contém `[RESULTADO]` é re-sanitizado na projeção (`strip_receipt`), para o histórico não vazar após o upgrade. O save não é reescrito.
- **R8** — [R] UI: `web/src/types.ts` ganha `TurnOutcome` e `GameResponse.turn_outcome?`. Componente mínimo de chip/toast (tokens e classes existentes; sem nova biblioteca nem novo layout) mostra `+N XP`, `Nível N!` quando `level_delta>0`, `+N ouro`, itens e missões concluídas, por tempo curto, `aria-live="polite"`, respeitando `prefers-reduced-motion`. Mostra só quando `receipt_id` é novo (ref/estado de sessão, não localStorage). Chip de nível não substitui o `LevelUpModal` quando há `pending_choices`.
- **R9** — [R] Fallbacks determinísticos sem números de recompensa: `_narrate_fall` e o fallback de `_narrate` não contêm XP/nível/ouro/itens-quantidade. Linhas de dano em `logs` permanecem nesta spec (decisão D-A, seção 8).
- **R10** — [R] Inventário de vazamentos entregue na etapa 1 em `docs/spec199/README.md`: todo ponto que concatena número mecânico de recompensa na mensagem (`combat`, `loot` compra/venda/saque, `storyteller` beat/armadilha, `event_processor` quest), classificado "corrigido aqui" ou "adiado + spec sugerida". Corrigido aqui: combate + recibo `[RESULTADO]`. Linhas `[SISTEMA]` do `loot` seguem D-B.
- **R11** — [R] Modo simulação (`combat_simulation`) não concede XP (já `not is_simulation`) e o `turn_outcome` fica `{}`.
- **R12** — [MOVIDO PARA SPEC-232, ja na main; nao implementado aqui] Bug confirmado por leitura de código (coordenador, 2026-10-15): carta benéfica (`efeito.kind` em `_default_card_target`, ex.: `cura`) jogada pela UI sem `target_id` recebe o 1º inimigo ativo em `api.py::_apply_action_options` (~l.3178); `agents/combat.py` (~l.843) só troca alvo inválido, e o inimigo é válido — a cura vai para o inimigo (`services/conflict_turn.py::_resolve_support_card`). Correção aqui: o default de alvo para `kind=card` usa `_default_card_target(card, primeiro_inimigo)` também na borda da API; teste de reprodução primeiro (carta de cura sem alvo → Vitalidade do jogador sobe, do inimigo não). Isto antecipa o R12 de reprodução da SPEC-205, que passa a apenas verificar a regressão.

> **Nota de escopo (revisão 2026-10-15):** R12 é um bug de alvo de carta, não de XP; entra
> aqui por ser pequeno, já reproduzido em leitura de código e bloquear o playtest de combate.
> Se o dono preferir spec própria, mover R12/Etapa 5b para um fix isolado antes da SPEC-205.
> **Transferido para a SPEC-232 (ordem final 2026-10-15):** R12 e a Etapa 5b saem desta spec e são executados na SPEC-232, que já corrige `_default_card_target` (BUG-02-20) e precede a SPEC-205. Esta spec fica só com XP/resultado fora da prosa; ignorar R12, Etapa 5b e o critério de aceite correspondente.

### Fora de escopo

- Mudar fórmula de XP, curva de nível, level-up ou `pending_choices`.
- Manifesto de encontro, identidade de inimigos, retorno ao chat/desfecho (SPEC-203); gesto de alvo e feedback tático de dano (SPEC-205); layout/abas (SPEC-204); design system de efeitos (SPEC-208).
- Reescrever as linhas `[SISTEMA]` de compra/venda/saque do `loot` (D-B).
- Streaming real de tokens e qualquer provider real.
- Edição de evaluator/dataset protegido de `evals/` (eval novo é handoff separado).

## 3. Design técnico

### Arquivos alterados

- `agents/combat.py` — remover `logs.append(f"+{xp} XP"...)`; manter `level_up_events` em `pending_world_events`; auditar `_narrate`, `_narrate_fall` e o fallback de `_narrate` para que nada de recompensa chegue a eles. Sem alteração em `grant_xp`.
- `services/turn_outcome.py` — `render_player_message` sem `[RESULTADO]`; `finalize_outcome` registra também `level_after`, `items_gained_named` (via `inventory.item_display`/`make_entry`) e `source`. Funções puras novas `public_outcome(outcome) -> PublicOutcome` (whitelist R4) e `strip_receipt(text) -> str` (R7).
- `api.py` — `GameResponse.turn_outcome: Dict[str, Any] = {}`; `format_response` preenche com `public_outcome(state.get("last_turn_outcome") or {})` (vazio em simulação) e aplica `strip_receipt` ao texto. `/game/state` herda via `format_response`.
- `web/src/types.ts` — `TurnOutcome` + `turn_outcome?` em `GameResponse`.
- `web/src/components/OutcomeToast.tsx` (novo, ~60 linhas), montado em `PlayScreen.tsx`; CSS mínimo em `web/src/styles.css` com variáveis existentes.
- `tests/test_matriz_a_contratos.py`, `tests/test_pre_matrix_contracts.py` — atualizar asserts que esperam `[RESULTADO]` na mensagem para o campo `turn_outcome` (testes de produto; confirmar que não são dataset/evaluator protegido de `evals/` antes de editar).

### Schemas

```python
# services/turn_outcome.py
class PublicOutcome(TypedDict, total=False):
    receipt_id: str
    turn: int
    xp_delta: int
    level_delta: int
    level_after: int
    gold_delta: int
    items_gained: list[dict]      # [{"id": str, "name": str, "qty": int}]
    quests_completed: list[dict]  # [{"id": str, "title": str}]
    source: str                   # combat|loot|story|quest|mixed|none

def public_outcome(outcome: dict) -> PublicOutcome: ...
def strip_receipt(text: str) -> str: ...
```

```ts
export interface TurnOutcome {
  receipt_id: string; turn: number;
  xp_delta: number; level_delta: number; level_after?: number;
  gold_delta: number;
  items_gained: { id: string; name: string; qty: number }[];
  quests_completed: { id: string; title: string }[];
  source: "combat" | "loot" | "story" | "quest" | "mixed" | "none";
}
```

### State ownership

- Python (combate/finalizer) é dono dos números; `last_turn_outcome` (persistido) é a fonte; a API só projeta com whitelist. O LLM não vê nem produz o campo. O cliente exibe e guarda em memória de sessão o último `receipt_id`.
- `source`: derivado da rota do turno, de `last_economy_action` e dos deltas — nunca de texto. [H] a rota final pode não estar disponível ao finalizer (a rota fiel é capturada por stream no playtest); nesse caso usar `"mixed"` com mais de um tipo de delta e `"none"` sem delta, registrando a limitação sem bloquear.

### Degradação / fallback

- LLM falhou/`FallbackLLM`: texto determinístico sem números de recompensa; `turn_outcome` continua presente (vem de delta de estado).
- `turn_outcome` ausente (save/cliente antigo): chip não aparece; HUD segue mostrando XP total.
- Cliente antigo ignora o campo novo (aditivo).

## 4. Plano passo a passo

### Etapa 1 — Inventário e reprodução (testes primeiro)

1. **Testes** (`tests/test_combat_xp_outside_prose.py`, MockLLM, offline): `test_repro_xp_in_prompt` captura o `SystemMessage` passado ao LLM em `_narrate` via fake LLM e asserta ausência de `XP`/`NÍVEL`; `test_repro_fallback_prints_xp` força fallback e asserta ausência de `XP`; `test_repro_receipt_in_message` asserta que a mensagem de `format_response` após kill não contém `[RESULTADO]` nem `\+\d+\s*XP`. Os três falham no HEAD (repro dos fatos [F]).
2. Gerar o inventário R10 (grep dos pontos de concatenação, incl. `playtest/` e `evals/` que leiam `[RESULTADO]`/`XP`) em `docs/spec199/README.md`.

### Etapa 2 — Combate

1. **Testes:** `test_combat_logs_have_no_reward_lines`; `test_xp_still_granted_once` (XP sobe exatamente `xp_for_kills(dead)`); `test_level_up_event_still_emitted` (evento `level_up` em `pending_world_events` e `pending_choices` preenchido); `test_fall_and_fallback_prose_have_no_reward_numbers`.
2. **Implementação:** remover o `logs.append` de XP.
3. **Verificação:** testes da etapa verdes.

### Etapa 3 — Recibo e projeção

1. **Testes:** `test_render_player_message_has_no_receipt`; `test_negative_reward_phrase_still_stripped_when_gain`; `test_public_outcome_whitelist` (sem `event_ids`/`transition_readiness`); `test_public_outcome_names_items`; `test_strip_receipt_legacy_message`; `test_response_turn_outcome_empty_for_legacy_save`.
2. **Implementação:** `turn_outcome.py`, `api.py`; atualizar os dois testes de contrato legados.
3. **Verificação:** `uv run pytest tests/test_combat_xp_outside_prose.py tests/test_matriz_a_contratos.py tests/test_pre_matrix_contracts.py` verde.

### Etapa 4 — Paridade, idempotência, persistência

1. **Testes** (TestClient, `RPG_FORCE_MOCK=1`, perfil legacy): `test_post_and_sse_turn_outcome_parity` (mesma ação em dois jogos semeados iguais → `turn_outcome` idêntico; evento SSE `state` contém o campo; chunks `narrative` concatenados sem `[RESULTADO]`/`XP`); `test_action_id_replay_same_receipt_no_double_xp` (dois POST com o mesmo `action_id` → mesmo `receipt_id`, `player.xp` aumentou uma vez); `test_save_reload_keeps_outcome` (salvar após kill, `load_game_state`, `format_response` → mesmo `turn_outcome`); `test_simulation_has_no_outcome`.
2. **Verificação:** verde; `tests/test_streaming.py` e `tests/test_hardening_persistencia_sse.py` seguem verdes.

### Etapa 5 — UI

1. **Testes** (Node, padrão dos testes de cliente existentes em `web/`): `OutcomeToast` formata `+N XP`/`Nível N!`/itens; não renderiza com `receipt_id` repetido nem com campos zerados; `aria-live` presente. Passe de browser opcional a 390 e 1440 px sem overflow (sem provider).
2. **Implementação:** `types.ts`, `OutcomeToast.tsx`, montagem em `PlayScreen.tsx`, CSS mínimo.
3. **Verificação:** `cd web && npm run build` e testes Node verdes.

### Etapa 5b — Alvo default de carta benéfica (R12)

1. **Testes** (`tests/test_combat_xp_outside_prose.py` ou `tests/test_card_default_target_api.py`):
   `test_repro_cura_sem_alvo_vai_para_inimigo` (vermelho no HEAD): combate ativo, POST
   `/game/action` com `card_id` de carta `efeito.kind="cura"` e sem `target_id` → Vitalidade
   do jogador sobe e a do inimigo não; `test_carta_ofensiva_sem_alvo_segue_primeiro_inimigo`
   (regressão: carta de dano sem alvo continua indo ao 1º inimigo ativo);
   `test_target_explicito_respeitado` (`target_id` explícito nunca é sobrescrito).
2. **Implementação:** em `api.py::_apply_action_options`, para `req.card_id` sem
   `req.target_id`, usar `_default_card_target(cards.get_card(card_id) or {}, primeiro_inimigo)`
   (importado de `agents/combat.py` ou movido para `services/` — sem duplicar o set `friendly`).
3. **Verificação:** testes verdes; `tests/test_combat_lifecycle.py` verde.

### Etapa 6 — Fechamento

`uv run pytest` completo; `uv run ruff check .`; `uv run python scripts/validate_content.py`; atualizar `ESTADO_ATUAL.md`/`ROADMAP.md`; registrar o handoff do eval (seção 9). O implementador não toca `evals/`.

## 5. Critérios de aceite

- [x] Prompt de `_narrate`, `_narrate_fall` e fallbacks não contêm XP, nível ganho, ouro nem itens-quantidade de recompensa (R1, R9).
- [x] Mensagem do chat (POST e chunks SSE) não contém `[RESULTADO]` nem `+N XP` em turno com ganho (R3, R5).
- [x] `GameResponse.turn_outcome` presente em POST, SSE `state` e `/game/state`, idêntico entre POST e SSE (R4, R5).
- [x] Replay com mesmo `action_id`: um único grant de XP, mesmo `receipt_id` (R6).
- [x] Round-trip de save com `last_turn_outcome`, e save legado sem o campo / com `[RESULTADO]` no texto (R7).
- [x] Chip mostra XP/nível/ouro/itens/missões uma vez por `receipt_id`, `aria-live`, sem nova biblioteca e sem alterar layout (R8).
- [x] Nenhuma mudança de regra de XP; testes de progressão existentes intocados e verdes.
- [x] Carta benéfica sem `target_id` pela API afeta o jogador; carta ofensiva sem alvo segue o 1º
      inimigo ativo; `target_id` explícito preservado (R12, Etapa 5b).
- [x] **Contrato compartilhado:** `turn_outcome` (`PublicOutcome`) é o único "evento de
      recompensa/XP" para SPEC-203 (`combat_result.xp_event_ref = receipt_id`), SPEC-205,
      SPEC-209 e SPEC-212; nenhuma delas cria campo paralelo de XP.
- [x] `docs/spec199/README.md` com inventário R10 e D-B resolvido.
- [x] `uv run pytest` verde (suíte completa offline); `npm run build` verde; Ruff verde.
- [x] Saves antigos continuam carregando.
- [x] Nenhum `with_structured_output` novo (sem guard adicional).

## 6. Smoke test

Offline por padrão (MockLLM, `RPG_FORCE_MOCK=1`):

1. `uv run python -m playtest run --all --turns 30` (ou perfis `combate` e `quester`): zero erro/violação; `playtest transcript <run_id>` e grep: nenhuma narração com `\+\d+ XP` ou `[RESULTADO]`.
2. `bash scripts/smoke_api.sh` e um POST/SSE de ação de combate com vitória: `turn_outcome.xp_delta > 0`, prosa limpa.
3. Browser local (opcional): vitória → chip `+N XP` uma vez; reload não repete o chip.

Provider real: **não requerido** (mudança de montagem de texto/projeção). Se o dono quiser validar a prosa no DeepSeek: opt-in com teto de 20 requests / US$ 0,20 e 1 combate dirigido; o aceite não depende disso.

## 7. Riscos & compatibilidade

- **Saves:** sem mudança de schema. Mensagens já salvas podem conter `[RESULTADO]`: tratado por `strip_receipt` na projeção; `messages` LangChain não são mutadas.
- **SPEC-144:** evolui o contrato de apresentação (recibo vira campo). Risco de regressão do achado original ("nada foi obtido" + ganho): mitigado por R3 e `test_negative_reward_phrase_still_stripped_when_gain`.
- **Playtest/evals existentes:** invariantes ou perfis que leiam `[RESULTADO]`/`XP` na mensagem migram para `turn_outcome`; se algum estiver em dataset/evaluator protegido, **não editar**: registrar handoff (seção 9).
- **Memória/archivist:** sem o recibo/XP na prosa o archivist não grava "+N XP" como fato (efeito desejado); conferir que `conflict_summary`/`summary_facts` não dependem de `logs` com XP.
- **Cliente em cache:** campo aditivo; bundle antigo ignora.
- **Custo/latência:** zero chamadas LLM novas.
- **MockLLM:** esconde bugs de mapeamento; sem structured output novo aqui, e os testes de prompt capturam o prompt em vez de depender de strings do mock.

## 8. Pontos de decisão do dono

- **D-A (dano nos fallbacks/`_narrate_fall`):** a decisão fechada cobre XP/recompensa; dano ainda aparece em bullets do fallback de queda e no modo laboratório. **Default recomendado:** manter aqui; SPEC-205 decide o formato de feedback tático de dano na UI.
- **D-B (linhas `[SISTEMA]` do `loot`: compra/venda/saque):** ledger mecânico visível no chat. **Default recomendado:** não alterar aqui (testes e o perfil comerciante dependem do texto; precisa de superfície de transação na UI); abrir spec sucessora "recibo de economia na UI" após SPEC-205. Se o dono preferir fechar tudo agora, estender R3/R8 ao `loot` (custo: uma etapa extra).
- **D-C (persistência do chip):** toast efêmero por `receipt_id` em sessão de UI. **Default recomendado:** sem histórico de recompensas persistido nesta spec; export/Crônica (SPEC-207) pode ler `last_turn_outcome`.

## 9. Evidência requerida

- Saída de `uv run pytest` completa (passed/skipped) mais os arquivos novos isolados; `npm run build` e testes Node.
- Repro antes/depois da etapa 1 (três testes vermelhos no HEAD, verdes depois) e `docs/spec199/README.md` com inventário R10, D-B resolvido e diff dos testes legados de `[RESULTADO]`.
- run_id de playtest offline com grep limpo; screenshots 390/1440 do chip (opcional).
- **Handoff de eval (EVAL_AUTHORING_REQUIRED, tarefa separada, fora desta implementação):** eval determinístico "narrative-no-mechanical-numbers" (fixtures de turno com XP/ouro/itens; asserta prosa visível sem `+N XP`, `[RESULTADO]`, `Nível N` nem quantidade de ouro de recompensa, e `turn_outcome` correto). Autoria por quem não implementa esta spec, com dataset congelado e registro na governança de `evals/`.
