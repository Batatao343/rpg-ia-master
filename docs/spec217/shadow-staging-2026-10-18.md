# SPEC-217 R14 + R15 — porte desligado e shadow no staging (2026-10-18)

**Resultado:** critério do shadow (R15) **atendido**. Em 55 turnos reais em que o router chamou o Jev, a
política congelada cobriu 54. Nesses 54, ela concordou com a rota efetiva do CLASSIFY em 52 (**96,3 %**,
mínimo exigido 95 %). Houve **zero** escalada para combate. O staging **voltou para `off`**. `primary`
continua desligado e depende de aprovação separada do dono.

## Porte (R14)

Commit `cae84b2` (branch `spec-217`):

* **Política:** `services/jev_rollout.py` **importa** a política congelada (não copia). São as funções de
  `evals/experiments/jev_router_hybrid.py` + `spec238_loot.py`, variante
  `plain+target+guard@0.50+lootsrc+lguard@0.50`, com features de local OFF e léxico de verbos inalterado.
  Os digests J1 `sha256:80225d16…10f5` e J1b `sha256:75635c89…2247` são recalculados em teste a partir do
  código importado.
* **Calibração:** `PRIMARY_CALIBRATION = ("SPEC-217-J2-20261018T134801Z", 0.50)`. Um teste verifica que o
  τ de rota, alvo e fonte é o mesmo 0,50.
* **Ordem no router:** o Jev roda **depois de todos os gates Python**. O `pre_classify` (SPEC-202) também
  passou a vir antes dele. Prazo de 1 s, sem retry, cliente HTTP compartilhado. Abstenção, confiança baixa,
  guarda de combate ou loot, alvo irrepresentável, erro, timeout ou kill switch levam ao CLASSIFY no mesmo
  turno.
* **Router:** `dm_router_node` foi dividido em `_classify` + `_finalize`. Uma decisão coberta do Jev passa
  pelo **mesmo** pós-processamento do CLASSIFY: interlocutor (SPEC-202), `combat_target_ref`,
  `loot_source` e retomada pós-combate. O ID de alvo do Jev vira o nome que o router grava (chave de
  `npcs`, nome do membro da party ou nome do inimigo). A paridade com o `map_target_to_id` da J2 é testada.
* **`off`:** idêntico byte a byte ao router anterior ao porte. Há um teste com payloads dourados gravados
  do código pré-porte em 15 cenários. Nenhuma thread, rede ou telemetria.
* **`primary`:** exige, além da calibração, `RPG_JEV_ROUTER_PRIMARY_APPROVED=1`, que é aprovação exclusiva
  do dono. `scripts/staging/vercel_env.py` só oferece `off|shadow` e **sempre apaga** essa variável.
* **`shadow`:** o Jev roda em paralelo ao CLASSIFY, com o mesmo prazo de 1 s. O log `jev.shadow` traz só
  rótulos, booleanos e latências: rota efetiva × rota que o `primary` daria, concordância de alvo e fonte,
  motivo de fallback e `wait_ms`. Nunca traz texto do jogador nem nomes.
* **Empacotamento:** a função Vercel passa a levar `evals/core` + `evals/experiments`. Continuam fora os
  diretórios `runs`, `datasets` e `experiments/data`.

## Execução do shadow

* Staging `rpg-ia-master-staging` (Vercel Hobby `gru1`, `hosted-supabase`, RLS por request). Supabase
  `uzeagzcyvxzrpjgrhaql`.
* Deploy de `cae84b2` com `--jev-router-mode shadow`, ou seja, `RPG_JEV_ROUTER_MODE=shadow` e
  `TYPESAFE_API_KEY` secreta, só no target production. `/health` mostrou o mesmo sha.
* Driver: `scripts/staging/jev_shadow_measure.py`. Foram 5 usuários sintéticos com 5 jogos novos (Devoto do
  Abismo, nível 1) e **58 turnos SSE reais**, narrador DeepSeek. As ações eram variadas: conversa (15),
  exploração/observação (20), compra/venda/troca (7), pegar/vasculhar (6), fabricar (4), viagem (1) e
  combate (5, no fim de cada jogo). Antes houve uma sonda de 2 turnos para validar o formato do log.
* Junção: cada turno guarda o `x-vercel-id` e casa exatamente com o `requestId` da linha `jev.shadow`.
  * No Fluid compute, 5 linhas apareceram em duplicata, também sob a requisição concorrente do cron
    `/internal/cron/jobs`, com o mesmo timestamp e os mesmos campos. Elas foram deduplicadas e são uma
    chamada só.
  * 3 turnos não chamaram o Jev, porque gates Python decidiram:
    * "Observo ao redor com cuidado." → descrição de cena (SPEC-202);
    * "Viajo para…" e "Descanso…" → viagem/descanso explícitos.
* Ao final: `--jev-router-mode off`, que apagou `RPG_JEV_ROUTER_MODE` e `TYPESAFE_API_KEY`, seguido de
  redeploy do mesmo `cae84b2` (`bi7io32h1`).
  * `/health` mostrou o sha.
  * `e2e_session` verde.
  * Zero linhas `jev.*` nos logs após o redeploy.
* Limpeza: 5+1 jogos e 5+1 usuários sintéticos apagados. A varredura achou 0 restantes.

## Resultados (n = 55 observações, 54 cobertas)

| Medida | Valor |
|---|---|
| Cobertura (o Jev decidiria) | 54/55 = **98,2 %** (1 fallback: `combat_guard` em "Investo contra a criatura…", em que o CLASSIFY deu combate, que é o caso p04 da J2) |
| **Concordância de rota (cobertos)** | **52/54 = 96,3 %** (critério ≥ 95 %) |
| Concordância de alvo (npc/combate cobertos) | 17/17 |
| Concordância de fonte do loot | 17/17 |
| Escalada para combate (Jev combate, CLASSIFY não) | **0** |
| Timeouts / erros / respostas inválidas | 0 / 0 / 0 |
| Latência do Jev (servidor `gru1` → TypeSafe) | p50 **251 ms**, p95 292 ms, máx. 367 ms |
| Espera adicionada ao turno (`wait_ms`) | p50 0, p95 0, máx. 0 ms (o Jev termina antes do CLASSIFY) |

Confusão (rota efetiva CLASSIFY → rota que o `primary` daria):

| | storyteller | npc_actor | loot | combat_agent |
|---|---:|---:|---:|---:|
| **storyteller** | 18 | | | |
| **npc_actor** | | 13 | | |
| **loot** | 2 | | 17 | |
| **combat_agent** | | | | 4 |

As duas divergências seguem o mesmo padrão. O **CLASSIFY** mandou ações de observação para `loot`:
"Inspeciono a carroça abandonada." e "Examino um objeto estranho na banca.". O Jev deu `storyteller` com
confiança 1,0, que é o rótulo pretendido pelo driver.

Contra os rótulos pretendidos pelas ações sintéticas, nos 54 turnos cobertos, o CLASSIFY acertou 50 e o
`primary` hipotético acertou 52. Esses rótulos são do driver, não de um oráculo. As 2 falhas comuns às duas
rotas são perguntas sem NPC nomeado ("Pergunto à pessoa mais próxima…", "Olá! Você sabe…"). O
pós-processamento do interlocutor (SPEC-202) leva as duas a `storyteller`, nos dois braços.

## Chamadas e custo

* **Jev:** 56 chamadas (55 no shadow + 1 na sonda), abaixo do teto autorizado de 60. O TypeSafe não
  informa custo (`unavailable`). Pela reserva de US$ 0,01 por chamada, isso dá ≈ US$ 0,56.
* **DeepSeek (narrador e demais nós):** 60 turnos + 6 jogos novos + `e2e_session` (5 turnos). O gasto de
  texto do dia ficou bem abaixo do cap de 5 BRL. O custo exato está no ledger `app.usage_events` do staging.

## Leitura e limites

* **[F]** No ambiente real, o Jev custa ≈ 250 ms e não atrasa o turno em `shadow`. Em `primary`, nos 98 %
  de turnos cobertos, ele substituiria o CLASSIFY (≈ 1,5 s p50 no staging, segundo a SPEC-214).
* **[F]** Os riscos da revisão Astra J2 se confirmaram na direção esperada:
  * o léxico de verbos sem "investo" gerou 1 fallback (latência, não erro);
  * o prazo de 1 s nunca foi atingido (máx. 367 ms).
* **[H]** A amostra é sintética, pequena e com um só narrador e classe. A concordância mede o CLASSIFY, não
  a verdade; as 2 divergências favorecem o Jev.
* **[R]** Pedir `primary` ao dono só depois da revisão Astra do commit do porte (R14). Se aprovado, ligar
  primeiro no staging, com o kill switch `decision_backend:jev` pronto.

Evidência: [evidence/shadow-staging-2026-10-18.json](evidence/shadow-staging-2026-10-18.json) (SHA-256
`3a7ec5af…1217`). Contém só ações sintéticas deste driver, rótulos, booleanos e latências: nenhum id,
e-mail ou segredo.
