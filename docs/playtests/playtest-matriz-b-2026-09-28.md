# Playtest real — matriz B (2026-09-27 a 2026-09-28)

## Estado final aceito

A matriz B executou **1.951/2.000 turnos válidos** com DeepSeek
`deepseek-v4-flash`, sem fallback. As campanhas 1–9 terminaram com 200 turnos,
zero erros, zero violações `error` e zero invocações LLM terminais. A campanha
10 parou no turno 151 por HTTP 402 `Insufficient Balance`. Faltaram 49 turnos
observados, mas o aceite exige repetir o par 10 inteiro desde o turno zero; a
Em 28/09, o usuário dispensou a repetição integral depois de informar que os
US$ 5 adicionados foram consumidos. A amostra de 1.951 turnos foi aceita com
essa limitação e a SPEC-128 foi encerrada como `done`.

Artefatos:

- `playtest_runs/20260927-214549-731406`: campanhas 1–8 completas; tentativa da
  campanha 9 interrompida no startup por uma falha transitória de conexão.
- `playtest_runs/20260928-084057-102826`: campanha 9 completa e campanha 10
  interrompida no turno 151 pelo saldo do provider.

## Resultado por perfil

| # | Perfil | Turnos | Erros | Error | Warning | Requests | Custo estimado |
|---|---|---:|---:|---:|---:|---:|---:|
| 01 | normal | 200 | 0 | 0 | 0 | 507 | US$ 0,14196 |
| 02 | explorador | 200 | 0 | 0 | 0 | 470 | US$ 0,13160 |
| 03 | diplomático | 200 | 0 | 0 | 0 | 526 | US$ 0,14728 |
| 04 | combate | 200 | 0 | 0 | 0 | 328 | US$ 0,09184 |
| 05 | comerciante | 200 | 0 | 0 | 2 | 514 | US$ 0,14392 |
| 06 | quester | 200 | 0 | 0 | 6 | 555 | US$ 0,15540 |
| 07 | recrutador | 200 | 0 | 0 | 1 | 40 | US$ 0,01120 |
| 08 | fujão | 200 | 0 | 0 | 1 | 140 | US$ 0,03920 |
| 09 | secret rusher | 200 | 0 | 0 | 0 | 611 | US$ 0,17108 |
| 10 | loot abuser | 151/200 | 1 provider | 0 | 4 | 506 | US$ 0,14168 |

Total observado nos dois runs, incluindo tentativas de provider que falharam:
**4.201 requests** e **US$ 1,17628 estimados**. O custo do contrato real curto
da auditoria não é incluído porque esse teste não registra tokens/custo.

## Evidência dos contratos funcionais

- Lifecycle, queda e checkpoint: múltiplos `player_downed` foram restaurados e
  retomaram o jogo sem falsa morte, cauda de transição ou violação de fase.
- Interações: diplomático 5→0 warnings, recrutador 132→1 e secret rusher 53→0
  em relação à matriz A; zero vazamento de segredo.
- Memória: zero `memory.location_grounding`, `memory.inventory_grounding` e
  `memory.npc_identity_grounding`. Uma reintrodução real resolveu “Mulher de
  unhas pretas” para o NPC existente “Mulher de xale puído”.
- Replan e structured output: falhas estruturadas recuperáveis não produziram
  `None` opaco; zero recorrência dos erros de replan/viagem da matriz A.
- Narrativa e recompensas: STORY/NPC/LOOT/memória atravessaram os runs sem
  alegação crítica inválida. O contrato opt-in DeepSeek concluiu beat elegível,
  concedeu exatamente 150 XP e produziu `last_turn_outcome` consistente.

Os 14 warnings da B parcial são todos `narrative.repeated_opening`. O total caiu
de 193 na matriz A para 14 até aqui. Houve aumentos pequenos em alguns perfis,
mas nenhuma nova categoria funcional ou violação `error`.

## Achados adicionais

1. **Telemetria de custo subestima o débito real.** O harness estimou US$ 1,17628,
   enquanto o usuário informou consumo dos US$ 5 recém-adicionados. A estimativa
   não deve ser usada como proteção financeira até ser reconciliada com o
   faturamento do provider.
2. **Prefixo NPC pode ser duplicado.** No turno 86 do `secret_rusher`, o wrapper
   exibiu o nome do Arauto e o texto do provider já começou com o mesmo prefixo,
   produzindo nome/aspas duplicados.
3. **Há uma lacuna de observabilidade de repetição NPC.** O console detectou oito
   aberturas repetidas do Arauto, mas o summary do perfil registrou zero
   `warning_violations`. O detector de fala e a invariante agregada não compartilham
   o mesmo canal.
4. **Repetição narrativa residual.** Comerciante (2), quester (6), recrutador (1),
   fujão (1) e loot abuser parcial (4) ainda repetiram aberturas. O total caiu
   cerca de 93% frente à matriz A, mas os casos restantes merecem polish.

## Comando de certificação estrita futura

Após restaurar saldo efetivo para a chave usada pelo processo:

```powershell
uv run python -m playtest matrix-suite --label B --turns 200 --real `
  --max-requests 800 --max-cost 0.25 --start-index 10 `
  --routes-profile deepseek-paid
```

O comando reinicia apenas o par 10 com o mesmo seed canônico `6209`; não é
correto somar os 151 turnos abortados a uma nova campanha para formar 200.

## Gate offline

Su?te offline final: **1807 passed, 35 skipped, 15 deselected**. Os 12 erros da primeira tentativa foram bloqueios de filesystem do sandbox em FAISS/WebP; a repeti??o fora do sandbox passou integralmente.
