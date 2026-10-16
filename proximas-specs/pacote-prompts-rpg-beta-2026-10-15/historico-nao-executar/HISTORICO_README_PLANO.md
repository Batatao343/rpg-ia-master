# RPG IA Master — Plano de specs pós-playtest

**Data:** 2026-10-12  
**Base inspecionada:** `Batatao343/rpg-ia-master`, branch `main` (leitura estática)  
**Estado deste pacote:** propostas de specs, todas `draft`. **Não foram inseridas** no GitHub, **não estão registradas** em `specs/index.yaml` e **não constituem aprovação ou teste executado**.

## Diagnóstico prioritário

O jogo possui um motor tático de Cartas, Entropia, Vitalidade/Ferimentos, Reações e zonas, mas a área principal continua sendo um diário de chat com um dock tático abaixo. A API expõe parcialmente os estados necessários ao frontend. Há lacunas na identidade do interlocutor, no dossiê de NPCs, no manifesto de participantes de encontro, no estado final pós-combate e na semântica de feedback e recuperação de ações pendentes.

**Achados verificados:**
- `web/src/components/PlayScreen.tsx`: **Ataque básico** é botão explícito apenas no simulador, embora o backend aceite `action_kind=attack` também em campanhas normais. O painel inferior de combate ocupa até `46vh` (`web/src/styles.css`), sob a narrativa.
- `web/src/components/Hud.tsx` e `services/npc_layers.py`: Pessoas mostra `last_memory`; a API fornece exatamente a última entrada de memória, não um resumo.
- `web/src/components/CardHand.tsx`: só mostra Cartas `ativa`, com a descrição autoral e custo/frequência. A **Golpe do Convite** (`data/cards/devoto.json`) tem `dano_base: 4`, `custo_entropia: 0` e `frequencia: livre`, mas isso não está explicitado na descrição apresentada.
- `agents/combat.py`: o scanner interpreta inimigos presentes a partir de `messages[-2:]` e pode preparar elenco diferente do que o jogador havia entendido da cena. O log que orienta a narração também inclui linha `+XP`.
- `web/src/App.tsx`: o frontend já tenta SSE, mantém `action_id` idempotente e tem retomada, mas status `running` pode apresentar erro pedindo nova consulta.
- `services/prologue.py` e `CreateScreen.tsx`: prólogo confirmável **já existe**; falta um contrato de abertura inequívoca na narrativa efetivamente exibida.
- `specs/SPEC-149...`: identidade por ID e aliases já foi tratada, mas gênero/pronomes, vínculo entre speaker e NPC e cronologia relacional precisam de cobertura adicional.
- `specs/SPEC-143...`: tentativa anterior de fan-out concorrente **falhou no gate real**. Não reaplicar paralelismo como correção presumida.
- `specs/SPEC-172...`: F01–F16 passaram no teste E2E determinístico. Isso não atesta os cenários emergentes descritos no playtest.

## Prioridade e sequência sugeridas

| Spec proposta | Prioridade | Tema | Dependências propostas |
|---|---|---|---|
| SPEC-176 | P0 | Congelar novos evals e contrato JEV | nenhuma |
| SPEC-177 | P0 | Ações resilientes, latência e recuperação | 176 |
| SPEC-178 | P0 | Interlocutor, identidade e dossiê de pessoas | 176 |
| SPEC-179 | P0 | Elenco do encontro, transição, vitória e XP | 176 |
| SPEC-180 | P0 | Tela de combate tática e clareza das Cartas | 179; preferencialmente 177 |
| SPEC-181 | P1 | Shell de RPG com menus + design/motion | 180 |
| SPEC-182 | P1 | Abertura da aventura causal e localizada | 176 |
| SPEC-183 | P1 | Balanceamento, pressão tática e dano | 179, 180 |

A **SPEC-176 define e congela a régua**, sem otimizar o produto. As demais só modificam produto, sem alterar expected, evaluators, datasets, denominadores ou gates protegidos na mesma tarefa. Seguir `AGENTS.md`, `specs/TEMPLATE.md`, `specs/index.yaml` e `docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`. Nos ciclos de implementação, registrar IDs canônicos no índice, aprovar cada spec e usar revisão independente quando houver mudança de ownership, concorrência e semântica de eval.

## Wireframe de intenção (desktop)

**Exploração / diálogo**

```text
┌─────────────────── CRÔNICAS DE VALORIA ───────────────────────────────────┐
│ Jornada  Pessoas  Inventário  Mapa  Missões  Crônica        Dia · Local  │
├───────────────┬─────────────────────────────────────┬───────────────────┤
│ OBJETIVOS     │ CENA / ARTE                         │ CONTEXTO          │
│ Quest atual   ├─────────────────────────────────────┤ NPC selecionado  │
│ Rastros       │ CADERNO DE AVENTURA                  │ Perfil e fatos   │
│ Pistas        │ Texto narrado + falas identificadas  │ Ações locais     │
│               │                                     │                  │
├───────────────┴─────────────────────────────────────┴───────────────────┤
│ [AGIR NO MUNDO] [FALAR COM NPC ▾] [PERGUNTAR AO NARRADOR] [ação...]      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Combate**

```text
┌──────────────────── CONFRONTO • RODADA 03 ───────────────────────────────┐
│ Você: Vitalidade / Ferimentos / Entropia      Iniciativa e ameaças      │
├─────────────────────────────────────────────┬───────────────────────────┤
│          CAMPO TÁTICO POR ZONAS              │ ALVO SELECIONADO         │
│  [Ruínas] ─── [Estrada] ─── [Bosque]         │ Nome · Estado · Defesa   │
│  tokens de jogador / bandido / corvos        │ Passivas / Reações       │
│  proximidade, cobertura, engajamento         │ Última troca            │
├─────────────────────────────────────────────┴───────────────────────────┤
│ AÇÕES BÁSICAS    Ataque • Engajar • Guardar • Desengajar • Fugir • Passar│
│ CARTAS / ENTROPIA   [carta + efeito/custo] [carta] [carta]               │
│ REAÇÃO PREPARADA   [trigger, custo, ativação]   LOG MECÂNICO ▸           │
└─────────────────────────────────────────────────────────────────────────┘
```

O campo é **por zonas**, não um grid inventado: `services/conflict_scene.py` já define `zones`, `positions`, `distance_state`, `postura`, `ocultacao`, `engaged_with`. O layout deve representar esses dados sem alterar seu significado.

## Linguagem visual

Direção sugerida: *grimdark cartográfico e interface de jogo de tabuleiro premium*: superfícies de ardósia envelhecida, tinta osso, bronze escurecido; cores funcionais reservadas a perigo, recurso e seleção. Tipografia de leitura para prosa e interface legível para controles. Em vez de multiplicar bordas e ornamentos, dar hierarquia a cena, personagens, mapa e ações.

Efeitos vinculados a eventos canônicos: **entrada do combate** (sweep/vinheta breve), **iniciativa** (tokens iluminados), **carta usada** (deslocamento/materialização), **hit** (número e redução da Vitalidade), **ferimento** (alerta específico), **reação** (parry/defesa), **vitória** (pausa da cena + resultado). Implementar com `motion/react` e CSS já instalados; nunca depender da duração da animação para confirmar uma mutação. Respeitar `prefers-reduced-motion`, sem flashes constantes, áudios compulsórios ou ornamentos em cada contêiner.

## Escopo de validação

Retestar F01–F16, acrescentar novos casos F17+, smoke real dirigido e **JEV após identificar seu runner/contrato exato**. Não encontrei comando ou artefato com a sigla `JEV` na árvore de arquivos inspecionada, então **não afirmo ter executado JEV**. Também não executei pytest/Playwright/live provider: esta entrega é análise e especificação.

## Referências de código

- [Frontend principal](https://github.com/Batatao343/rpg-ia-master/tree/main/web/src)
- [API](https://github.com/Batatao343/rpg-ia-master/blob/main/api.py)
- [Agente de combate](https://github.com/Batatao343/rpg-ia-master/blob/main/agents/combat.py)
- [Camadas de NPCs](https://github.com/Batatao343/rpg-ia-master/blob/main/services/npc_layers.py)
- [Contrato da interface tática existente](https://github.com/Batatao343/rpg-ia-master/blob/main/specs/SPEC-077-conflito-16-frontend-combate-cartas.md)
- [Baseline de frontend](https://github.com/Batatao343/rpg-ia-master/blob/main/specs/SPEC-172-frontend-evals.md)
- [Experimento negativo de latência](https://github.com/Batatao343/rpg-ia-master/blob/main/docs/latencia-turno-r29-2026-08-28.md)
