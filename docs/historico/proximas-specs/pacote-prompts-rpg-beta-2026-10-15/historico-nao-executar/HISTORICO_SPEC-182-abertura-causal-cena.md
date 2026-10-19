# SPEC-182 — Contrato causal de abertura da aventura

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P1  
> **Depende de:** SPEC-176 `done` · **Reusa:** `services/prologue.py` e etapa de confirmação já existentes.

## 1. Contexto & objetivo

O prólogo personalizado já é aprovado na criação do personagem, mas o `opening_scene_brief` pode limitar-se a ambientação/gancho genéricos. No playtest, não ficou claro por que o personagem estava caminhando na pradaria ou como se deparou com saqueadores. A abertura deve constituir uma cena causal e localizada, não apenas uma descrição estilizada.

## 2. Requisitos

- **R1:** a abertura contém lugar/sublocal identificável, momento do dia, **motivo para o personagem estar ali**, o que percebeu antes do encontro, atores presentes, distâncias/perigo observáveis, uma escolha inicial com consequências aparentes.
- **R2:** esses elementos viram `OpeningSceneState` estruturado, validado contra região/local atual e NPCs iniciados; a LLM narra o estado, mas não troca local/participantes por conveniência literária.
- **R3:** a cena inicial distingue fato estabelecido, rumor e desconhecido; não revela segredos só para criar gancho.
- **R4:** a tela de confirmação existente exibe sinopse sem spoilers e o contexto essencial "onde/por quê/o que está acontecendo"; o primeiro turno mostra continuidade sem repetir texto integralmente.
- **R5:** fallback determinístico contém causa e situação explícita, não apenas "um detalhe perturbador e um gancho".

## 3. Design técnico

Evoluir `StartScenario`/`scenario_to_state_seed` em `services/prologue.py`, estado inicial de `api.py`, validador do `services/world_validators.py` e componente `web/src/components/CreateScreen.tsx`. Campos sugeridos: `location_id`, `sublocation_id?`, `arrival_reason`, `initial_activity`, `inciting_event`, `visible_actor_ids`, `initial_threats`, `initial_choices`. Persistir somente fatos públicos aprovados e reconciliados; incluir referência em `campaign_plan` para narrativa inicial.

## 4. Etapas (testes primeiro)

1. Fixture pradaria + saqueadores verifica onde, motivação, observação e primeiro ponto de decisão.
2. Criar modelos e validações; migrar saves sem cenário.
3. Ajustar fallback/narração e confirmação visual.
4. Testar regressões com criação clássica e personalização; 3–5 prólogos reais sob orçamento aprovado.

## 5. Aceite

- [ ] Em toda abertura fixture o jogador responde "onde estou?", "por que cheguei?" e "quem/que ameaça vi?" usando informações visíveis.
- [ ] Sem troca de local, atores ou conhecimento secreto na primeira cena.
- [ ] Criação/saves legados preservados; regressões de prólogo e F02 verdes.

## 6. Riscos

Não forçar toda abertura a ter combate: exploração e oportunidade pacífica devem permanecer válidas. A estrutura informa a causalidade, não roteiriza escolhas.
