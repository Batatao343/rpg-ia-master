# SPEC-205 — Combate por gesto: carta, mira e alvo direto

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-199 `done` (resultado fora da prosa), SPEC-203 `done` (identidade estável de elenco), SPEC-204 `done` (aba Combate), SPEC-232 `done` (efeitos reais de Carta/Reação + alvo default de carta) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-208, SPEC-209, SPEC-212, SPEC-216 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 03
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — jornadas frontend novas (carta com alvo, carta sem alvo, ataque básico, cancelar, alvo inválido, idempotência) em `web/e2e/critical-journeys.yaml`; autoria em tarefa separada, sem editar evaluator/expected/dataset protegido na implementação.

Rótulos: **[F]** fato observado no source (HEAD 6b94f66) · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

Hoje jogar uma carta exige: escolher a carta, abrir um `<select>` de alvo no cabeçalho da mão e clicar "Jogar Carta"; o ataque básico nem existe como botão no jogo real. O objetivo é a regra de produto **uma ação por gesto**: cartas com alvo entram em modo mira e o clique no alvo válido executa; cartas sem alvo e ações básicas executam num clique; Esc ou clique fora cancela; teclado completo; nenhuma confirmação redundante. O jogador vê, antes de agir, o custo real, a frequência/limite, os alvos válidos (ou por que não há), e o servidor continua sendo a única autoridade dos números.

Isto **evolui o contrato de UI da SPEC-077** (mão, Reação, zonas, Ferimentos, conhecimento progressivo do inimigo), sem reabri-la, e reaproveita o laboratório da SPEC-090 e as reações da SPEC-081. A UI vive na aba **Combate** do shell (SPEC-204); esta spec não decide o shell. Referência de comportamento: `design-html/rpg-combate-experiencia-v03.html` do pacote (números, cartas extras, retratos e falas são mock; as regras vêm do repo). Material `historico-nao-executar/HISTORICO_SPEC-180*` é só contexto histórico (IDs colidem com specs reais).

### Fatos auditados

- **[F]** `api.py` `ActionRequest` (~l.876): `card_id`, `target_id`, `ruptura`, `reaction_card_id`, `action_kind` (`attack|maneuver|pass|flee`), `maneuver` (`engajar|desengajar|guardar|esconder|procurar`), `action_id` (UUID canônico). `_apply_action_options` (~l.3167) converte isso em `state["combat_declaration"]`; sem `target_id`, usa o **primeiro inimigo ativo**.
- **[F]** A projeção de combate (~l.1421-1508) devolve `enemies[]` (`id`, `name`, `vitalidade/max`, `esquiva`, `protecao`, `integridade_*`, `recursos_visiveis`, `conditions`, `revealed_cards`, `revealed_resistances`), `cards` via `_cards_block(player, prepared_only=True)`, `scene` (`zones`, `positions` com `engaged_with`, `distance`, `posture`, `concealment`), `chase`, `reactions`, `last_player_action`. `_cards_block` (~l.1198) calcula `cost`, `frequency`, `spent`, `ready`, `target_kind` (`self|enemy`), `has_rupture`, `rupture_ready`, `trigger`. **Não existe** lista de alvos válidos nem motivo de indisponibilidade; `ready` é um booleano agregado (preparada + não gasta + custo ≤ Entropia).
- **[F]** `services/cards.py::can_use_card` é a consulta pura da economia; `conflict_turn.py` revalida no uso (`use_card`/`use_ruptura`) e `conflict_scene.occlusion_attack_modifier` bloqueia alvo sem posição conhecida (`can_target`). Cartas de dados (`data/cards/*.json`) **não têm campo de alcance**; "alcance/zona" só existe via engajamento, distância e ocultação da cena.
- **[F]** `web/src/components/CardHand.tsx`: `<select>` de alvo só aparece com >1 inimigo; botão "Jogar Carta"/"Romper"; sem mira por clique, sem Esc/teclado, sem tooltip de limites; filtra `type === "ativa"`. `ReactionPrompt.tsx` é um `fieldset` com botões; `SceneZones.tsx` é lista textual (inimigos não clicáveis); `PlayScreen.tsx` mostra `TACTICAL_MANEUVERS` (Engajar, Guardar, Esconder-se, Procurar, Fugir) e só inclui o chip **"Ataque básico" quando `simulation`** (l.69). No jogo real o ataque básico só sai por texto livre (parse LLM).
- **[F]** `agents/combat.py::_default_card_target` (l.330) só é usado no caminho de parse de texto. Em `_apply_action_options`, cartas vindas da UI com `target_id` ausente recebem o primeiro inimigo; `conflict_turn._resolve_support_card` usa `actors_by_id.get(step.target_id) or actor`.
- **[H]** Combinando os dois fatos acima, uma carta de suporte (`target_kind: "self"`, ex.: cura/proteção) jogada da UI pode ter como alvo o primeiro inimigo em vez do jogador. Deve ser **reproduzido por teste antes de qualquer correção** (R12); se confirmado, é bug de borda a corrigir nesta spec.
- **[F]** `types.ts`: `CardView`, `EnemyView`, `ConflictSceneView`, `CombatBlock` existem; sem `valid_targets`, sem intenção inimiga, sem evento de resultado de combate.

## 2. Requisitos

**Gesto e fluxo**
- **R1** — [D] Carta ativa com alvo: clicar/Enter na carta entra em **modo mira** (carta marcada, alvos válidos destacados, inválidos esmaecidos com motivo); clicar num alvo válido executa a ação com `card_id` + `target_id`, sem botão adicional.
- **R2** — [D] Carta sem alvo (efeito sobre si/cena) e **Ataque básico** executam com **um clique**. Ataque básico com um único alvo válido executa direto; com vários, entra em mira como carta com alvo.
- **R3** — [D] Esc, clique fora da arena ou clicar de novo na carta selecionada cancela a mira sem enviar nada; trocar de carta durante a mira substitui a seleção.
- **R4** — [D] Nenhuma confirmação extra ("Tem certeza?") em ações reversíveis ou de rotina. Apenas ação genuinamente irreversível pode confirmar, com a consequência explicada; a lista inicial é **vazia** e qualquer inclusão passa pelo dono (seção 8, P3). Fugir e Ruptura não confirmam.
- **R5** — [D] Ruptura vira modificador de mira: toggle "Ruptura" ligado antes do alvo, visível na carta; executa no mesmo gesto do alvo.
- **R6** — [D] Teclado completo: Tab/setas percorrem mão, ações básicas, reações e alvos; Enter/Espaço seleciona/executa; Esc cancela; atalhos numéricos 1-9 para a mão são opcionais [R]. Foco visível, `aria-pressed` na carta em mira, `aria-live` anuncia "Mirando X: escolha um alvo" e o resultado. Funciona com `prefers-reduced-motion`.

**Contrato aditivo de validade (Python)**
- **R7** — [D][R] `combat.cards[]` ganha `valid_targets: string[]` e `invalid_reason: string | null` (por carta), e `combat.basic_actions[]` (`attack`, `pass`, `flee`, manobras) com a mesma forma. Alvos incluem inimigos **e aliados/o próprio herói** conforme `target_kind` da carta. Campos **aditivos**: clientes antigos continuam válidos.
- **R8** — [R] `invalid_reason` é enum fechado: `not_prepared | spent_frequency | no_entropy | cooldown | no_valid_target | target_dead | target_hidden | out_of_zone | not_your_turn | combat_inactive`. Cada motivo vem de uma consulta pura em Python reutilizando `cards.can_use_card`, `conflict_scene` (engajamento/distância/ocultação) e estado do alvo; **nenhum cálculo de regra no frontend**. `out_of_zone` só é emitido onde a cena já impõe restrição (não há campo de alcance nas cartas).
- **R9** — [D] O servidor **continua revalidando tudo** no uso (`use_card`, ocultação, alvo morto). Se o cliente enviar alvo fora de `valid_targets` (estado velho), a resposta é rejeição estruturada sem consumir Entropia/frequência, e a UI mostra o motivo e refaz a mira com o estado novo.
- **R10** — Cartas `target_kind: "self"` nunca recebem inimigo como alvo vindo da UI: o servidor normaliza para o jogador (ver H da seção 1 e R12).

**Informação visível**
- **R11** — Inimigos e aliados são alvos clicáveis em uma arena por zonas (evolução de `SceneZones`), mostrando: nome estável (`species_label` de `combat.encounter_view.participants[]` da SPEC-203 R1/R7, chaveado por `participant_id` = `enemy.id`; os ids em `valid_targets` são esses mesmos `participant_id`/`"player"`/id de aliado), Vitalidade atual/max **vinda do servidor**, Ferimentos/condições, intenção revelada (somente o que `bestiary_knowledge.public_panel` já expõe; hoje `revealed_cards`/`revealed_resistances`), passivas e reações visíveis, quem age agora e posição/engajamento. Nada oculto vaza: não revelar carta/resistência não revelada. Inimigos mortos saem da lista de alvos.
- **R12** — Teste de reprodução: carta de suporte da UI sem `target_id` (jogada em combate com inimigo vivo) deve resolver sobre o jogador. Se falhar hoje, corrigir em `_apply_action_options` (alvo derivado de `target_kind`, não do "primeiro inimigo"); se passar, manter o teste como regressão.
- **R13** — Tooltip/painel de carta ao hover **e** ao foco: custo real (`cost`, com Dependência aplicada, `base_cost` quando diferir), frequência e limite restante (`spent`), gatilho de reação, efeito (`description`), motivo de indisponibilidade em texto. Números só do payload; nunca inventados.

**Estado, feedback e idempotência**
- **R14** — [D] **Proibido estado otimista para números**: HP, Entropia, dano e frequência só mudam depois da resposta. Permitido otimismo só de afeto visual (carta "em envio", alvo "travado", spinner), nunca de valor. Durante `busy` a mira fica bloqueada.
- **R15** — Feedback de resultado vem do servidor: dano/cura/falha/Ferimento e a projeção pública **`turn_outcome`** da SPEC-199 R4 (`xp_delta`, `level_delta`, `level_after`, `source == "combat"`) aparecem como toasts/chips na arena e nos números, não na prosa. Ao término, o desfecho usa `combat_result` da SPEC-203 R7 (`outcome`, `participants[].final_status`); o painel de desfecho em si é da SPEC-203 R8 — esta spec só o hospeda na aba Combate. Se `turn_outcome`/`combat_result` faltarem (servidor antigo, `{}`), a UI degrada para o `last_player_action` existente sem inventar XP.
- **R16** — Idempotência: cada gesto gera um `action_id` UUID novo; reenvio após timeout/rede reutiliza o **mesmo** `action_id` e resulta em exatamente um turno (comportamento da SPEC-086, não alterar). Duplo clique/Enter repetido não envia duas ações (trava até resposta).
- **R17** — Estados terminais: combate encerrado (`active:false`), game over, `death_pending`, simulação finalizada e fuga bem-sucedida desligam a mira, limpam seleção e mostram o desfecho; reação disponível é oferecida no mesmo padrão de um clique (substitui o `fieldset` atual, mantendo `reaction_card_id` no payload).
- **R19** — Layout: a mão preparada, as ações básicas e o alvo em mira ficam sempre visíveis dentro da aba Combate em 1440×900 e em `split` 50/50 (nenhuma carta coberta pelo log, toast ou painel; assert de bounding box sem interseção). Nenhum efeito de impacto (shake, flash, zoom) desloca ou oculta carta/alvo durante a decisão; efeitos finais são da SPEC-208.
- **R18** — Rascunho do chat e histórico não são afetados pelo gesto (draft pertence ao shell da SPEC-204).

### Fora de escopo
- Shell, abas e split 50/50 (SPEC-204); manifesto/identidade do encontro e evento XP em si (SPEC-203/199); deck, Maestria e preparação fora de combate (SPEC-209); design system e efeitos de impacto/animação finais (SPEC-208); mobile (SPEC-216).
- Nova mecânica, rebalanceamento, alcance como regra nova de cartas, mudanças no motor `conflict_orchestrator`/`conflict_turn`, novo `action_kind`.
- Estado otimista de números; streaming de combate; chamada LLM nova em combate; Jev.
- Editar evaluator/expected/dataset protegido de `evals/`.

## 3. Design técnico

**Arquivos novos**
- `services/combat_targeting.py` — consulta pura, sem LLM: `valid_targets_for_card(state, card_id) -> TargetingResult`, `basic_action_targeting(state, kind, maneuver=None)`. Reutiliza `cards.can_use_card`, `conflict_scene.is_engaged/is_hidden_from/occlusion_attack_modifier`, estado do alvo. Mesma função usada pela projeção e (R9) pela validação de borda.
- `web/src/combat/useTargeting.ts` — hook/máquina de estados `idle → aiming(card|basic, ruptura) → submitting → idle`; Esc/click-out; teclado; sem números locais.
- `web/src/components/combat/Arena.tsx` (substitui o uso de `SceneZones` na aba Combate), `TargetChip.tsx`, `CardTooltip.tsx`; `CardHand.tsx` e `ReactionPrompt.tsx` evoluem (cartas viram seletores de mira; reação em um clique). Nomes finais ajustáveis pelo executor se SPEC-204 já tiver convenção de pasta.
- `tests/test_combat_targeting.py`, `web/e2e/combat-gesture.spec.ts`.

**Arquivos alterados**
- `api.py`: `_cards_block` ganha `valid_targets`/`invalid_reason`; projeção ganha `basic_actions`; `_apply_action_options` rejeita alvo inválido (R9) e normaliza alvo de carta `self` (R10/R12). `ActionRequest` **não muda** (aditivo só na resposta).
- `web/src/types.ts`: `CardView.valid_targets?: string[]`, `CardView.invalid_reason?: InvalidReason | null`, `CombatBlock.basic_actions?: BasicActionView[]`; todos opcionais para tolerar servidor antigo.
- `web/src/components/PlayScreen.tsx`: remove o chip "Ataque básico" condicionado a `simulation` e o `TACTICAL_MANEUVERS` solto; o Combate da SPEC-204 hospeda a arena. A simulação (SPEC-090/`CombatSimulatorScreen`) passa a usar o mesmo componente.

**Contratos de dados**
```json
// combat.cards[i] (campos novos)
{"id":"golpe_do_convite","ready":true,"target_kind":"enemy",
 "valid_targets":["lobo_1","lobo_2"],"invalid_reason":null}
// carta indisponível
{"id":"muralha_viva","ready":false,"valid_targets":[],"invalid_reason":"no_entropy"}
// combat.basic_actions[i]
{"kind":"attack","valid_targets":["lobo_1"],"invalid_reason":null,"cost":0}
{"kind":"maneuver","maneuver":"guardar","valid_targets":[],"invalid_reason":null,"cost":0}
```
Rejeição de borda (R9): HTTP 409 com `detail.code = "invalid_target"` + `invalid_reason`, sem mudança de estado. [H] Código/forma exatos seguem o padrão de erros estruturados já usado em `api.py`; o executor confirma antes de fixar.

**State ownership**
- Servidor: Vitalidade, Entropia, frequência, `valid_targets`, intenção revelada, resultado, XP. UI: apenas `aiming/selectedCard/ruptura/hoverTarget/pendingActionId` (efêmero, não persistido, descartado ao trocar de `game_id`).
- Saves: **sem mudança de schema**; `valid_targets` é derivado a cada resposta.

**Degradação/fallback**
- Servidor sem os campos novos: UI cai para `ready`/`target_kind` e primeiro alvo vivo (comportamento atual) sem quebrar.
- Falha de rede no gesto: seleção mantida, botão "Tentar de novo" com o mesmo `action_id` (R16).
- Reduced motion: mira indicada por contorno/rótulo, não por movimento.

## 4. Plano passo a passo (TDD)

### Etapa 1 — Reproduções e `combat_targeting` (Python)
1. **Testes** (`tests/test_combat_targeting.py`): `test_support_card_from_ui_targets_player` (H/R12, vermelho se bug); `test_attack_card_lists_alive_enemies_only`; `test_dead_target_excluded`; `test_hidden_target_reason`; `test_no_entropy_reason`; `test_spent_frequency_reason`; `test_not_prepared_reason`; `test_basic_attack_single_target`; `test_unknown_reason_never_emitted` (enum fechado); `test_targeting_matches_server_revalidation` (todo alvo em `valid_targets` é aceito pelo motor; fora dele é rejeitado).
2. **Implementação:** `services/combat_targeting.py`; ligar em `_cards_block`/projeção; rejeição estruturada e normalização `self`.
3. **Verificação:** `uv run pytest tests/test_combat_targeting.py tests/test_conflito16_frontend.py` verde, depois suíte completa.

### Etapa 2 — Idempotência e contrato
1. **Testes:** `test_action_retry_same_action_id_single_turn_card`; `test_invalid_target_rejected_without_spending`; `test_old_client_payload_still_valid` (campos novos ignorados).
2. **Implementação:** ajustes mínimos em `api.py`.

### Etapa 3 — Máquina de mira e componentes (frontend)
1. **Testes unitários** (vitest/Node conforme `web/` já usa): `useTargeting` transitions (idle→aiming→submitting, Esc, troca de carta, `busy`), sem número otimista (snapshot dos valores antes/depois da resposta).
2. **Implementação:** hook, `Arena`, `TargetChip`, `CardTooltip`, evolução de `CardHand`/`ReactionPrompt`; remoção do `<select>` e do botão "Jogar Carta".

### Etapa 4 — Playwright dos fluxos
`web/e2e/combat-gesture.spec.ts` contra a API determinística: carta com alvo (2 cliques), carta sem alvo (1), ataque básico em jogo real (1), cancelar com Esc e clique fora, alvo inválido com motivo, Entropia insuficiente, alvo morto, reação em um clique, combate encerrado/fuga, teclado puro, idempotência pós-timeout, 390/1440 sem overflow, Axe sem violação serious/critical. Medir **cliques até a ação correta**, **cliques falhos** e **tempo até a ação correta** (ms do primeiro foco na aba ao request enviado, script Playwright determinístico) e registrar; meta inicial [R]: carta com alvo ≤ 2 cliques e 0 cliques falhos no roteiro.

Nota de integridade: `combat-gesture.spec.ts` é teste de implementação do executor (não governado); as jornadas F-numeradas que contam para `frontend_eval_report.py` (em `web/e2e/critical-journeys.{yaml,spec.ts}`, `evals/metrics-registry.yaml`, `evals/manifest.lock.json`) são autoradas e travadas na tarefa de eval separada, antes da implementação, e o executor não as edita.

### Etapa 5 — Handoff de evals e fechamento
Registrar handoff `EVAL_AUTHORING_REQUIRED` (jornadas novas) sem tocar `evals/`. `ESTADO_ATUAL.md`/`ROADMAP.md` conforme AGENTS.md.

## 5. Critérios de aceite

- [ ] Carta com alvo executa em 2 gestos (carta, alvo); sem alvo e ataque básico em 1; Esc/click-out cancelam sem request.
- [ ] Ataque básico disponível no jogo real (não só na simulação), sem texto livre.
- [ ] `valid_targets`/`invalid_reason` por carta e `basic_actions` calculados em Python; testes cobrem todos os motivos do enum.
- [ ] Servidor rejeita alvo inválido sem consumir recurso; todo alvo anunciado é aceito pelo motor.
- [ ] Reprodução H resolvida (alvo de suporte = jogador) e travada por teste.
- [ ] Zero estado otimista de HP/Entropia/dano/frequência (teste de UI).
- [ ] Resultado e XP exibidos a partir de eventos do servidor (SPEC-199); degradação sem o evento testada.
- [ ] Teclado completo + `aria-live` + foco visível; Axe sem serious/critical em 390 e 1440.
- [ ] Mão/alvo nunca encobertos por log/toast em 1440×900 e split 50/50 (R19).
- [ ] Ids de alvo = `participant_id` do manifesto SPEC-203; XP lido de `turn_outcome` (SPEC-199), nunca da prosa.
- [ ] `action_id` reutilizado no retry gera um único turno; duplo clique não duplica.
- [ ] Servidor antigo/cliente antigo: campos opcionais, sem quebra.
- [ ] `uv run pytest` verde; `npm run build` verde; Playwright do combate verde; sem edição em `evals/`.
- [ ] Revisão Sol independente registrada.

## 6. Smoke

Offline (MockLLM, padrão): campanha de combate determinística, jogar uma carta com alvo, uma sem alvo, ataque básico, cancelar com Esc, tentar carta sem Entropia, reconectar e repetir ação com mesmo `action_id`; conferir que HP muda só após a resposta. Provider real **opt-in**, fora do gate: no máximo 1 combate curto (≤ 20 requests, ≤ US$ 0,10), apenas para ver prosa sem XP e NPC/inimigo estáveis; autorização explícita antes.

## 7. Riscos & compatibilidade

- **Saves:** nenhuma mudança de schema; nenhuma migração. `valid_targets` é derivado.
- **Paridade de regras:** risco de divergência entre `combat_targeting` e o motor; mitigado por teste de equivalência (R9) e revalidação no servidor.
- **Conflito de merge:** `PlayScreen.tsx`, `styles.css` e `App.tsx` são tocados também pela SPEC-204 e pela SPEC-197 (`in-progress`, não editada aqui); implementar só após 204 `done` e rebasear.
- **Cartas de reação/passivas:** `can_use_card` só aceita `ativa`; reações seguem pelo gatilho do motor, a UI só escolhe a reação preparada (comportamento SPEC-077/081).
- **Informação oculta:** a arena nunca deriva intenção de dados privados do inimigo; só `public_panel`.
- **Latência:** o cálculo de alvos é puro e O(cartas × inimigos); sem LLM, sem I/O.

## 8. Pontos de decisão do dono

- **P1 — Ataque básico com um único alvo executa direto?** Default recomendado: **sim** (1 clique).
- **P2 — Atalhos numéricos 1-9 na mão?** Default: sim, opcionais e desativáveis; teclado por Tab/Enter é obrigatório.
- **P3 — Existe alguma ação a confirmar?** Default: **nenhuma** na primeira entrega; Fugir e Ruptura não confirmam. Qualquer exceção volta ao dono com a consequência explicada.
- **P4 — Alvo de carta de suporte: aliado clicável ou só o próprio herói?** Default: herói e aliados presentes em cena (a lista vem de `valid_targets`); sem aliado, 1 clique em si.

## 9. Evidência requerida

- Saída de `uv run pytest` (suíte completa) e de `tests/test_combat_targeting.py`; build web; relatório Playwright com 390/1440, Axe e timings de cliques (até ação correta, cliques falhos).
- Resultado do teste de reprodução H (falhou/passou antes da correção) anexado.
- Captura/JSON de uma jogada real offline mostrando HP só após resposta.
- Handoff de evals (jornadas novas) e parecer de revisão Sol em `handoffs/`.
