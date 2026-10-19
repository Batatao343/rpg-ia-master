# SPEC-180 — Tela tática dedicada, ações básicas e informação de Cartas

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P0 (principal frontend)  
> **Depende de:** SPEC-179 `done`; SPEC-177 recomendado · **Desbloqueia:** SPEC-181/183.

## 1. Contexto & objetivo

`PlayScreen` e `styles.css` preservam a narrativa como palco central e inserem um dock que ocupa até 46vh; `SceneZones` é textual e aparece duplicado. Cartas ativas aparecem sem descrição mecânica suficiente, enquanto passivas/reação ficam fora do foco. A tela precisa assumir o combate como um modo de jogo de primeira classe, sem pedir ao jogador que adivinhe comandos no chat.

## 2. Requisitos

- **R1:** ao receber `combat.phase=entering|active`, alternar com transição curta para **BattleScreen**, com round, ordem de iniciativa, Vitalidade/Ferimentos, Entropia e estados de inimigos visíveis sem scroll principal; ao `ended`, abrir **CombatResult** e depois voltar à exploração.
- **R2:** dividir comandos em **Ações básicas** (`Ataque básico`, `Engajar`, `Desengajar`, `Guardar`, `Esconder-se`, `Procurar`, `Fugir`, `Passar`) e **Cartas (custam Entropia conforme ficha)**. Não rotular Entropia como stamina; Mana/Vigor só no fallback legado aplicável. Usar os `action_kind`/`maneuver` já suportados; adicionar apenas o que faltar de pré-condições.
- **R3:** alvos são selecionados por token no campo tático e espelhados no inspector; `target_id` canônico via ActionOptions, não por texto gerado. Alvos mortos/fugidos não podem ser selecionados; seleção troca quando o alvo some.
- **R4:** representar zonas e conexões como diagrama não-grid (existente em `scene.zones/positions`), com tokens nominados e barras, linha de engajamento, proximidade/distância, cobertura/postura e ocultação. Não inventar coordenadas de mapa canônicas.
- **R5:** Carta mostra **efeito mecânico**, custo efetivo de Entropia, alvo, frequência, prontidão, motivo de indisponibilidade e detalhes de Ruptura. Separar flavor e regras a partir de `efeito` validado. Para `dev_golpe_convite`: indicar **4 de dano base marcial, custo 0 E, uso livre**; não inferir que força avanço ou reduz defesa sem mecânica real.
- **R6:** painel permanente/compacto de **Passivas**, **Reação preparada** e gatilhos legíveis; reação é pré-seleção conforme motor atual, a menos que backend declare janela de interrupção real. Feedback de carta/reação consumida mostra porquê, custo e resultado.
- **R7:** log de batalha secundário, colapsável; narração apenas apoio dramático. Rodada e atualização visual ocorrem somente quando chega estado canônico; microanimação não é confirmação de sucesso.
- **R8:** mobile 320/390: campo tático ocupa viewport principal e ações em bandeja/abas acessíveis, sem texto e dock competindo por altura; foco, `Escape`, contraste, `prefers-reduced-motion` respeitados.

## 3. Design técnico

Novos componentes possíveis: `web/src/components/BattleScreen.tsx`, `BattlefieldZones.tsx`, `BasicActions.tsx`, `BattleInspector.tsx`, `CombatResult.tsx`, `PassiveEffects.tsx`, `CardDetails.tsx`. Reutilizar e reestruturar `CardHand`, `ReactionPrompt`, `WoundTrack`, `SceneZones`, `PlayScreen`, `Hud`, `styles.css`. Em `api.py`, enriquecer `_cards_block` com `rules_text`, `effect_summary` e `disabled_reason` produzidos determinísticamente em `services/cards.py`; não enviar dados ocultos de inimigos. Se custo for alterado por habilidade, usar `effective_cost` de `cards._entropy_cost`, não exclusivamente `custo_entropia` estático. Para ações que exigem alvo, registrar `target_id` obrigatório na UX e validar também no backend.

## 4. Etapas (testes primeiro)

1. F17/F18: fixture entrando em batalha mostra modo dedicado + botão Ataque básico **também** no jogo normal, nunca apenas no simulador.
2. F19/F20: tokens dos grupos corretos, card usado, último inimigo morre, tela de resultado aparece e volta à exploração.
3. Verificar condições da ação básica/Entropia, reação e passiva em fixtures de recursos zero, card gasto, alvo ausente.
4. Testar 320/390/768/1440, teclado, reduced motion e `axe` antes de estabilizar CSS.

## 5. Aceite

- [ ] Jogador conclui batalha fixture sem digitar texto livre; ação básica, carta, seleção de alvo, defesa e fuga encontram-se na tela.
- [ ] O campo mostra todos os atores do manifesto, posicionamento e relação de engajamento coerentes com API.
- [ ] Passivas e reações acessíveis e explicadas; custo/efeito não é só flavor.
- [ ] Vitória produz fecho e modo tático desaparece no momento correto.
- [ ] Zero controles ocultos por dock/scroll no mobile e regressões E2E/a11y verdes.

## 6. Riscos

Não construir grid espacial, pathfinding nem custos de stamina inexistentes. O motor de cartas já é deterministicamente resolvido; UI não simula dano próprio antes de receber decisão do servidor.
