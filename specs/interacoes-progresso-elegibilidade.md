# SPEC — Interações com progresso, elegibilidade e repetição útil

> **Status:** `in-progress` — implementação offline verde; aguarda matriz B real
> **Criada/Atualizada:** 2026-08-27
> **Depende de:** `npcs-3-camadas`, `aliados-em-combate`, `polish-prosa-v2` (`done`)
> **Supera:** smoke de recrutador que usava apenas `RECRUIT_MIN_REL`

## 1. Contexto & Objetivo

O recrutador da matriz A convidou o mesmo NPC 132 vezes. O harness usava limiar
fixo 7, enquanto o produto aplica modifier de trait e podia exigir 10. O detector
de prosa também contou o prefixo determinístico do NPC como abertura, inflando
warnings do diplomático e secret rusher. A solução é compartilhar decisão
canônica e medir progresso mecânico, sem ensinar o harness a raspar prosa.

## 2. Requisitos

- **R1 — Decisão tipada:** `recruitment_decision(state, npc)` retorna `ok`, código
  fechado, relação atual, limiar requerido interno e hint público sem revelar
  traits ocultos. `can_recruit` delega a ela por compatibilidade.
- **R2 — Resultado estruturado:** comandos NPC gravam `last_interaction_outcome`
  (`kind`, `subject_id`, `code`, `progressed`, `turn`) além da fala.
- **R3 — Perfil adaptativo:** recrutador consulta a decisão real, limita ações
  idênticas sem progresso, diversifica construção de confiança e troca de alvo/
  objetivo/local após tentativas finitas.
- **R4 — Diplomático:** mantém memória de perguntas/alvos e não repete ação
  idêntica quando o outcome não progride.
- **R5 — Segredos:** recusa esperada continua segura; `secret_rusher` não trata
  não-vazamento como falha do produto, mas varia alvo/pergunta após limite.
- **R6 — Detector semântico:** prefixos fechados (`🗣️ Nome:` etc.) são removidos
  antes de calcular abertura; denials determinísticos não são avaliados como
  estilo de prosa.
- **R7 — Episódios:** repetição gera um aviso no início do episódio e outro só
  após janela exponencial, não um warning a cada turno.
- **R8 — No-progress:** fingerprint de ação + outcome + ausência de delta produz
  `interaction.no_progress`; três repetições devem ser detectadas sem longrun.

### Fora de escopo

Revelar traits ocultos, garantir que todo NPC aceite recrutamento ou gerar diálogo
extra por LLM.

## 3. Design técnico

- `party.py`: `RecruitmentCode`, `RecruitmentDecision` e função canônica.
- `agents/npc.py`: persiste outcome estruturado para comandos determinísticos.
- `playtest/profiles.py`: máquinas de estado reiniciáveis por campanha; usam
  decisões de domínio, não constantes/texto.
- `services/prose_guard.py`: `semantic_opening` remove scaffold.
- `playtest/invariants.py`: tracker por campanha de episódios de repetição e
  progresso (sem singleton global de produto).

## 4. Plano TDD

1. Reproduzir NPC desconfiado: relação 7, limiar 10, 20 decisões; perfil não
   convida em loop e muda de estratégia em até três turnos.
2. Cobrir sentimental (limiar 5), party cheia, hostil, já recrutado e ausente.
3. Cobrir prefixos NPC com números variáveis e recusa idêntica; um episódio, não
   100 warnings.
4. Cobrir diplomático e secret rusher sem vazamento; suíte completa.

## 5. Critérios de aceite

- [x] Produto e harness usam a mesma decisão de recrutamento.
- [x] Nenhum perfil lê limiar duplicado nem raspa motivo da fala.
- [x] Relação 7/limiar 10 não causa convites indefinidos.
- [x] Traits ocultos não vazam no contrato público.
- [x] Três ações sem progresso são detectadas em teste unitário.
- [x] Scaffold NPC não conta como abertura semântica.
- [x] Suíte completa offline verde.
- [ ] Matriz B real confirma redução dos episódios repetidos sem vazamento.

## 6. Smoke real

Executar recrutador/diplomático/secret rusher por 30 turnos; confirmar adaptação,
zero vazamento e redução drástica de episódios repetidos.

## 7. Riscos

O harness não deve ganhar onisciência. Ele recebe apenas códigos que um cliente
real precisaria para reagir; limiar/trait permanecem internos ao motor.
