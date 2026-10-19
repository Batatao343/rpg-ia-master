# SPEC-179 — Elenco canônico do encontro e encerramento visível do combate

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P0  
> **Depende de:** SPEC-176 `done` · **Desbloqueia:** SPEC-180/183 · **Revisão:** Sol (estado multi-agente).

## 1. Contexto & objetivo

O scanner de `agents/combat.py` extrai grupos de inimigos de apenas `messages[-2:]`, potencialmente perdendo bandidos previamente apresentados quando corvos surgem na prosa. Ao fim do combate a UI só vê `combat.active=false`; o `conflict_summary` canônico não tem um bloco de resultado projetado para o jogador. O texto narrativo ainda recebe linhas de XP no log mecânico.

## 2. Requisitos

- **R1:** preparar antes da luta um `EncounterManifest` por `encounter_id`, com atores estáveis (`participant_id`, identidade/template, grupo, função `hostile|ally|neutral|hazard|summon`, quantidade e estado), posição inicial e fonte canônica. Scanner pode propor, mas não sobrescrever silenciosamente participantes já estabelecidos.
- **R2:** bandido, corvo e Halveth ficam em entidades/grupos distintos; um grupo só sai da luta após evento explícito `dead`, `fled`, `surrendered`, `disengaged`, `not_present` validado. Ajustes de budget geram evento de composição justificado; não apagam inimigo da ficção.
- **R3:** `combat` expõe `phase = entering|active|resolving|ended` e `battle_id`; transições são determinísticas e idempotentes, inclusive no reload e após kill do último inimigo.
- **R4:** quando termina, API envia `CombatResultView` derivado do `conflict_summary`: resultado `victory|defeat|fled|other`, participantes derrotados/fugitivos, resumo público, ferimentos, recompensa/XP em bloco **meta UI**, marcador único do evento. O frontend sempre tem uma tela/painel de conclusão independente de uma LLM responder.
- **R5:** XP é entregue apenas no campo de progressão/notificação de UI, nunca no prompt/log fornecido à prosa; sanitizar artefatos históricos e validar ausência de padrões `+NN XP` em `message`/`presentation_history` narrativos.
- **R6:** na vitória, renderizar fecho narrativo curto baseado em resultado canônico, depois tela de resultado e botão **Continuar aventura** que fecha modo combate, sem consumir ação narrativa. Em derrota, prevalece death flow existente.
- **R7:** evitar duplicar XP, loot, kill ou evento de fim em replay de mesma ação; roundtrip save/reload consistente.

## 3. Design técnico

Arquivos: `agents/combat.py`, `services/encounter_preparation.py`, `services/conflict_summary.py`, `services/conflict_scene.py`, `services/actor_lifecycle.py` se aplicável, `api.py`, `state.py`, `persistence.py`, `web/src/types.ts`. O manifest deve ser registrado antes de `run_round` e usado como fonte para criação/adição de atores. `CombatResultView` não deve vazar inimigos/segredos que não foram percebidos. O `combat.active` deve seguir derivado do motor; `phase` é projeção de lifecycle, não controle arbitrário do cliente.

Exemplo de saída: `{battle_id, phase:'ended', outcome:'victory', actors:[{id,role,final_status}], aftermath_text, rewards:{xp_delta,items}, ended_event_id}`. Antes da resolução, `rewards` não está acessível.

## 4. Etapas (testes primeiro)

1. Fixture Halveth + 2 bandidos hostis + corvos como criaturas/hazard; validar IDs/grupos antes e depois da descrição de corvos.
2. Fixtures de kill do último inimigo, fuga, rendição, derrota e replay com perda de SSE; zero ator inexplicavelmente sumido.
3. Implementar manifest e evento de mudanças do elenco, salvamento e view de resultado.
4. Remover linhas meta do prompt de narração e exibir recompensa separadamente.
5. Executar testes `test_combat_lifecycle`, `test_conflict_summary_lifecycle`, playtest invariants e F08/F19/F20.

## 5. Aceite

- [ ] Elenco autorizado da cena corresponde ao elenco de entrada no combate salvo mudanças explicitadas por evento.
- [ ] Mortes/fugas/rendição permanecem consistentes no save e na narrativa.
- [ ] Em todo término o jogador vê resultado e pode voltar à exploração sem outra mensagem.
- [ ] Sem XP em prosa; XP correto na ficha/notificação e concedido exatamente uma vez.
- [ ] Regressões de combate, load/replay e E2E verdes.

## 6. Riscos

Não forçar que todo NPC mencionado participe de combate: distinguir presente, distante, neutro e hostil. Encontro com corvos pode ser excelente emergentemente, mas não pode reclassificar/apagar bandidos sem decisão canônica. Preservar motor determinístico e política de orçamento de encontro.
