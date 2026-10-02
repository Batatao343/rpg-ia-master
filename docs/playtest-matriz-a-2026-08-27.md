# Playtest real — matriz A pareada (2026-08-20 a 2026-08-27)

## Escopo e validade

A baseline A reúne dez campanhas independentes, todas com DeepSeek real, sem
MockLLM ou fallback determinístico, 200 turnos por campanha. Os pares preservam
perfil, classe, nível e seed definidos por `matrix-suite`.

| Par | Run | Perfil | Turnos | Erros | Violações error | Warnings | p50/p95 ms |
|---|---|---|---:|---:|---:|---:|---:|
| 01 | `20260820-200416-642340` | normal, nível 1 | 200 | 0 | 0 | 0 | 9.674 / 20.300 |
| 02 | `20260820-200416-642340` | explorador, nível 3 | 200 | 0 | 0 | 0 | 8.486 / 18.767 |
| 03 | `20260820-200416-642340` | diplomático, nível 5 | 200 | 0 | 0 | 5 | 15.898 / 22.085 |
| 04 | `20260820-200416-642340` | combate, nível 7 | 200 | 0 | 7 | 0 | 11.305 / 19.771 |
| 05 | `20260821-001914-212655` | comerciante, nível 9 | 200 | 0 | 0 | 0 | 10.918 / 21.533 |
| 06 | `20260821-001914-212655` | quester, nível 11 | 200 | 0 | 5 | 1 | 13.229 / 20.637 |
| 07 | `20260821-001914-212655` | recrutador, nível 13 | 200 | 0 | 0 | 132 | 4.475 / 15.959 |
| 08 | `20260821-092129-358859` | fujão, nível 15 | 200 | 0 | 0 | 0 | 11.335 / 19.790 |
| 09 | `20260821-092129-358859` | secret rusher, nível 18 | 200 | 0 | 0 | 53 | 14.656 / 20.095 |
| 10 | `20260827-114435-548287` | loot abuser, nível 20 | 200 | 0 | 0 | 2 | 7.370 / 12.904 |

Total: **2.000/2.000 turnos**, zero erro de turno, 12 violações `error`, 193
warnings, 5.224 tentativas LLM, 5.205 sucessos, 19 falhas recuperadas, 36 mortes
e custo observado de **US$ 1,46272**.

A tentativa incompleta `20260821-092129-358859/matrix_10_6209` foi excluída:
parou no turno 75 após três `CampaignPlanModel=None`. O replay integral e válido
do par 10 é o run `20260827-114435-548287`.

## Achados e recorrência

### A1 — ciclo de vida do ator, não “HP zero”

O perfil combate produziu sete `player.zero_vitality_outside_terminal`; o
quester, uma. O contrato canônico de Ferimentos permite Vitalidade zero sem
morte, mas `fuga-vitalidade-zero` criou uma invariante incompatível. A falha real
é outra: após `post_combat_consciousness` marcar o protagonista inconsciente, o
grafo ainda aceita viagem, conversa, loot e novo conflito. A correção precisa
centralizar elegibilidade de ação por fase de vida, nunca usar Vitalidade como
atalho para morte.

Spec definitiva: `SPEC-141-contrato-canonico-ciclo-vida-acoes.md`. Ela supera os requisitos
R1–R3 de `SPEC-131-fuga-vitalidade-zero.md`, preservando o contrato de
`SPEC-083-fix-vitalidade-ferimentos-terminal.md`.

### A2 — recompensa consolidada depois da fala

O quester registrou quatro `narrative.reward_contradiction` (turnos 39, 42, 80
e 94). Em todos, o storyteller negou recompensa e só depois o archivist aplicou
`quest_completed`, ouro e XP. O patch anterior cobria apenas delta concedido
dentro do storyteller; não cobria mutação canônica tardia.

Spec definitiva: `SPEC-144-resultado-canonico-turno-apresentacao.md`, que amplia e
substitui a cobertura parcial de `SPEC-095-feedback-ledger-recompensas.md`.

### A3 — interação sem progresso e elegibilidade divergente

O recrutador gerou 132 warnings. O perfil convidava ao atingir o limiar fixo 7,
mas `party.can_recruit` elevava o limiar real até 10 por traits ocultos; assim,
repetia o mesmo convite e a mesma recusa por mais de cem turnos. Diplomático e
secret rusher somaram 58 warnings; parte mede scaffold determinístico do NPC,
não a abertura semântica da prosa.

Spec definitiva: `SPEC-142-interacoes-progresso-elegibilidade.md`, com uma decisão
tipada compartilhada pelo produto e pelo harness, máquina de estados adaptativa
e telemetria episódica.

### A4 — structured output sem evidência diagnóstica

Houve 19 falhas LLM recuperadas, principalmente `CampaignPlanModel=None`. Uma
tentativa excluída encerrou a matriz após três respostas inválidas consecutivas.
O retry atual pede regeneração às cegas porque `include_raw=False` elimina a
resposta e a causa do parse.

Spec definitiva: `SPEC-145-structured-output-evidencia-recuperacao.md`, que supera o
retry genérico de `SPEC-136-structured-output-retry-provider.md` sem relaxar fail-closed.

## Gate A→correções→B

A matriz B só pode começar depois das quatro specs implementadas, testes curtos
das reproduções exatas e suíte offline completa verde. B repete os mesmos dez
pares, 200 turnos, seeds, classes, níveis, preset e limites. Qualquer regressão
nova em B interrompe o ciclo para decisão do usuário.
