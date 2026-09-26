# SPEC — Contrato compartilhado de evidências narrativas

> **Status:** `in-progress`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** auditoria-2026-09-recompensas-recibos (para consequências econômicas)
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

Uma resposta simulada “Ari morreu. Você chegou a Brekmar” passou para apresentação com jogador vivo em Nova Arcádia. O arquivista rejeitou a morte em important_facts, mas a gravou em new_summary e chronicle_entry. Há validadores parciais distintos por consumidor.

## 2. Requisitos

- **R1** — Mensagem, resumo, crônica e memória compartilham validação das mesmas alegações críticas: morte, localização atual, posse, identidade, segredo e recompensa.
- **R2** — Alegações mecânicas tipadas são propostas; só consequências aceitas pelo Python podem ser afirmadas como confirmadas. Nunca promover texto livre por coocorrência de um evento não relacionado.
- **R3** — Negação, hipótese, fala de NPC e fatos históricos não viram afirmação atual. Corpus de positivos/negativos em pt-BR cobre cada categoria.
- **R4** — Texto incompatível fica fora de todos os derivados, com auditoria limitada e motivo. Contexto/RAG não perde todas as memórias válidas porque uma frase falhou.
- **R5** — Preservar atmosfera e criatividade. Não prometer validação semântica infalível nem usar outra chamada LLM para cada frase.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

Novo services/narrative_evidence.py com EvidenceSnapshot (game_id:str, timeline_epoch:int, turn:int, location_id:str, player_alive:bool, entity_ids:list[str], inventory:dict[str,int], accepted_event_ids:list[str]) e NarrativeCheck (text:str, rejections:list[dict[str,str]], evidence_ids:list[str]); construção somente de estado/eventos aceitos. Funções build_evidence(state:dict)->EvidenceSnapshot e validate_narrative(text:str, evidence:EvidenceSnapshot, *, channel:str)->NarrativeCheck. Integrar agentes/finalizer/archivist/context_builder de forma incremental. Eventuais novos campos Pydantic terão defaults e guard de FallbackLLM. Fonte do estado continua state.py; evidência é derivada, não segundo estado autoritativo.

## 4. Plano passo a passo

1. tests/test_narrative_evidence.py: reproduções da auditoria, negações, rumor e viagem futura; nenhum falso positivo nos controles.
2. Cobrir important_facts/new_summary/chronicle_entry separadamente, incluindo fallback plain-text.
3. Integrar contrato por rota, testando grafo → finalizer → save/load → contexto seguinte.
4. Contracts reais curtos opt-in após offline; matriz B apenas gate global posterior.

## 5. Critérios de aceite

- [ ] Todos os canais obedecem R1–R5, com corpus independente.
- [ ] Suites offline e contratos dirigidos reais executados; guard estruturado coberto.
- [ ] Saves antigos carregam sem inventar evidência.

## 6. Smoke test com LLM real / integração aplicável

3–5 turnos dirigidos com provider autorizado, separando STORY/NPC/LOOT e memória. Sem execução paga automática neste ciclo. Enquanto faltar, status permanece in-progress.

## 7. Riscos & compatibilidade

Regex é defesa auxiliar, não prova semântica universal. Não migrar arquitetura inteira nem remover liberdade narrativa. Alterações no template de resposta exigem compatibilidade Mock/Fallback e atualização da spec.

## Execução — 26/09 (prevalece sobre as pendências históricas)

EvidenceSnapshot e guard compartilhado integrados em mensagem, resumo, crônica e contexto; auditoria limitada/persistida. Corpus cobre morte, chegada, negação, rumor e pronome reflexivo. Pendente: unificar totalmente os guards antigos de memory_fact/contexto (que ainda podem descartar rumores), ampliar corpus de posse/identidade/segredo/recompensa e validar grafo/save/load dirigido. Smoke com provider real não executado. evidence_ids ainda não é atribuição por alegação; não tratar regex como certificação semântica.
