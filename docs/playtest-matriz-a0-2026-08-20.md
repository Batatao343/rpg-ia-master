# Diagnóstico da matriz A0 — 2026-08-20

Run: `20260820-134236-013629`  
Configuração: dez pares fixos, até 200 turnos, LLM real, teto de US$ 0,25 e
800 requests por campanha.

## Resultado

A0 foi reclassificada como execução de descoberta de capacidade, não como a
matriz A de aceite. Os pares normal e explorador completaram 200/200; os outros
oito foram interrompidos pelo teto entre 11 e 53 turnos. Foram observados 678
turnos, zero exceção do runner, uma violação `error` e 25 warnings.

| Par | Perfil | Nível | Turnos | Custo estimado | Achado principal |
|---:|---|---:|---:|---:|---|
| 1 | normal | 1 | 200 | US$ 0,14756 | 21 falsos warnings de NPC reciclado |
| 2 | explorador | 3 | 200 | US$ 0,15960 | 17 mortes e ciclo jogável com Vitalidade 0 |
| 3 | diplomático | 5 | 45 | US$ 0,25452 | teto por indisponibilidade das rotas |
| 4 | combate | 7 | 32 | US$ 0,28186 | `combat.no_progress` por Mimetismo Morto |
| 5 | comerciante | 9 | 34 | US$ 0,28928 | teto por indisponibilidade das rotas |
| 6 | quester | 11 | 47 | US$ 0,25386 | teto por indisponibilidade das rotas |
| 7 | recrutador | 13 | 53 | US$ 0,25192 | teto por indisponibilidade das rotas |
| 8 | fujão | 15 | 11 | US$ 0,28128 | teto por indisponibilidade das rotas |
| 9 | secret_rusher | 18 | 45 | US$ 0,25768 | teto por indisponibilidade das rotas |
| 10 | loot_abuser | 20 | 11 | US$ 0,27354 | teto por indisponibilidade das rotas |

## Achados transformados em specs

1. [Capacidade de provider antes do longrun](../specs/matriz-a-capacidade-provider.md):
   preflight dos três tiers, preset Groq-only, pacing e contrato para histórico
   estruturado terminado em `AIMessage`.
2. [Loop de Mimetismo Morto](../specs/combate-mimetismo-morto-loop.md): inimigo
   já oculto não pode escolher outra Carta de esconder.
3. [Fuga com Vitalidade zero](../specs/fuga-vitalidade-zero.md): a fuga é
   bloqueada e o conflito resolve o fluxo terminal.
4. [NPC reciclado e mortes](../specs/observabilidade-npc-mortes-longrun.md):
   menção memorial não significa presença e o relatório lista todas as mortes.

## Evidência após a correção

- Preflight real Groq-only verde em CLASSIFY, FAST e SMART.
- FAST/SMART usam 120b e caem apenas para o 20b do mesmo provider quando um tool
  call for rejeitado; não há MockLLM nem fallback determinístico na rota.
- Matriz offline curta `20260820-155100-829869`: 10×3, 30/30, zero erro e zero
  violação.
- Suíte completa: 1591 passed, 16 skipped, 14 deselected.

A próxima evidência é A1: os mesmos dez pares, 200 turnos cada, após essas
correções. Só A1 completa poderá virar o baseline da comparação com B.
