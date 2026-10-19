# SPEC-178 — Interlocutor explícito, identidade canônica e dossiê de pessoas

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P0  
> **Depende de:** SPEC-176 `done` · **Risco:** estado persistente/cross-domain; revisão Sol recomendada.

## 1. Contexto & objetivo

A interface trata narrador e NPC como texto enviado ao mesmo campo; o roteador infere destino por LLM e nome, e a aba Pessoas imprime a última lembrança. O caso Halveth/Ressa, mudanças de pronome e memória de expulsão seguida de contratação sem explicação mostram que o interlocutor, a identidade e a cronologia das relações precisam ser vínculos explícitos.

## 2. Requisitos

- **R1:** a UI oferece modos claros **Agir**, **Falar com [NPC da cena]** e **Perguntar ao Narrador**. Para seleção explícita, a LLM não pode mudar `recipient_id`. Entrada livre conserva roteamento de compatibilidade; ambiguidades expõem uma sugestão não invasiva de destinatário.
- **R2:** em diálogo, cada evento e cada mensagem renderizada carregam `speaker_id` canônico e nome visível derivado do mesmo registro. `Ressa` jamais aparece com avatar/etiqueta de Halveth por associação a rota anterior.
- **R3:** pergunta metajogo ao narrador não passa por diálogo NPC nem avança relógio, quests ou relação. Responde somente com conhecimento público/visível ao protagonista; não revela informações ocultas da sessão.
- **R4:** registro de identidade de NPC contém campos explícitos, p.ex. `canonical_id`, `display_name`, `pronouns/gender_presentation` (se conhecidos), `species`, `role`, `aliases`, cada um com proveniência e política de atualização. Identidades preexistentes não mudam silenciosamente em novo turno/save/load.
- **R5:** aba Pessoas vira **dossiê**: descrição pública, onde foi visto, relação, fatos conhecidos, histórico resumido de encontros e o que se sabe que ele sabe de nós. Fatos trazem `fact_id`, `source_event_id/turn` e marcador de confiabilidade. Ocultar fatos secretos e nunca inferir conhecimento de NPC apenas porque o narrador conhece.
- **R6:** contradição aparente de comportamento (expulsou da torre, depois contratou) exige evento/causa de reconciliação ou é retida para revisão da narrativa; registrar mudança legítima de atitude sem reescrever evento passado.
- **R7:** saves legados sem gênero/pronomes exibem `não determinado`; não preencher com chute de IA. Comportamento temporal de memória deve sobreviver roundtrip.

## 3. Design técnico

API: acrescentar campo opcional `recipient_npc_id` à ação, validado em `npc_layers.npcs_in_scene`/resolver canônico; o nome público vem do ID, não do texto da resposta. Adicionar endpoint separado read-only `POST /game/clarify` para perguntas ao narrador, que não execute `campaign_manager`/`archivist`/turno, e que monte apenas contexto público (se isso exigir migração de persistência ou autenticação, planejar na implementação). Retornar `speaker` estruturado em resposta e histórico (`services/presentation_history.py`). Novo `NpcDossierView` derivado de fatos/eventos válidos em `services/npc_layers.py` e memória/proveniência existente; manter `last_memory` como compat temporária. Atualizar `agents/router.py`, `agents/npc.py`, `services/entity_identity.py`, `api.py`, `web/src/types.ts`, `PlayScreen.tsx`, `Hud.tsx`, `StoryLog.tsx`.

**Contrato exemplo:** `NpcDossierView = { id, name, pronouns_known, role, relationship, in_scene, last_seen, known_facts:[{id,text,source_event_id,turn}], interactions:[{turn,location,summary,outcome}], known_about_player:[{id,text,source_event_id}] }`. Campos sobre conhecimento só contêm o que jogador testemunhou ou aprendeu legitimamente; `unknown` não equivale a falso.

## 4. Etapas (testes primeiro)

1. Fixtures com dois NPCs na cena (Halveth/Ressa), nomes/aliases conflitantes, pergunta ao narrador, múltiplas visitas, save/reload e fato secreto.
2. Implementar `recipient_npc_id` e `speaker` no contrato, regressão do router e do histórico.
3. Implementar políticas de identidade, migração e view de dossiê com proveniência.
4. Implementar modos de entrada e página Pessoas; testar trocas de aba/salvamento e mobile.

## 5. Aceite

- [ ] Seleção explícita de destinatário tem 100% de correspondência ao ID; erro controlado quando NPC não está mais em cena.
- [ ] Sem troca inadvertida de nome, gênero/pronomes ou memória canônica em 30 turnos dirigidos e reload.
- [ ] Expulsão e contratação coexistem como eventos quando há mudança causal registrada; nunca se apaga retrospectivamente um fato.
- [ ] Dossiê contém resumo verificável de pelo menos 3 interações, não só a última fala.
- [ ] Narrator Q&A é read-only, sem vazamento de spoiler/segredo.
- [ ] Evals da SPEC-176, F07/F21/F22, suíte e smoke real dirigido verdes.

## 6. Riscos

Conhecimento pode ser falso na ficção: o dossiê distingue alegação, rumor e fato confirmado. "Imutável" aplica-se a identidade de fonte e histórico de eventos, não à opinião/relação que pode evoluir legitimamente.
