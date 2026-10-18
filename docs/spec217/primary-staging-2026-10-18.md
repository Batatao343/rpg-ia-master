# SPEC-217 — Jev em `primary` no staging (2026-10-18)

**Decisão:** `primary` **fica LIGADO no staging**. Em 20 turnos reais não houve erro nem timeout. O Jev decidiu
18 dos 20 turnos. Houve 1 fallback sensato, e o router caiu de ≈ 1,5 s para ≈ 0,28 s (p50) nos turnos que o
Jev decidiu.

* **Aprovação do dono (2026-10-18, literal):** "já coloquei credito na OpenAi e pode ligar o primary no
  staging".
* **Escopo:** só staging (Vercel `rpg-ia-master-staging`, Supabase `uzeagzcyvxzrpjgrhaql`). Produção não
  existe e nada foi enviado ao GitHub.

## Como foi ligado

* **Tooling** (commit `c3bab62`, branch `staging-primary`):
  * `scripts/staging/vercel_env.py --jev-router primary --owner-approved-primary` envia três variáveis, só
    no target `production`:
    * `RPG_JEV_ROUTER_MODE=primary`;
    * `RPG_JEV_ROUTER_PRIMARY_APPROVED=1`;
    * `TYPESAFE_API_KEY` (secreta).
  * O preview nunca recebe nenhuma delas.
  * Sem `--owner-approved-primary`, o script recusa (`ValueError`, exit 1).
  * O default segue `off`. `off` e `shadow` apagam a variável de aprovação (`OPTIONAL_FLAGS`).
  * A citação do dono está no código (`OWNER_PRIMARY_APPROVAL`) e em teste
    (`test_jev_router_primary_requires_owner_flag_and_stays_out_of_preview`).
* **Deploy:** `vercel deploy --prod -e GIT_SHA=c3bab62…`, que gerou `rpg-ia-master-staging-gnlwq6evi-…vercel.app`.
  `/health` mostra `git_sha=c3bab62968ef…`, `hosted-supabase` e `hardened=true`.
* **Código do router:** é o mesmo da `main` `1c44409`, isto é, o porte R14 revisado pela Astra. O commit de
  tooling não toca o produto.
* **`e2e_session`:** verde. Cobre cookie/CSRF/captcha, 5 turnos SSE, retry com o mesmo `action_id` e logout.
  Evidência: [evidence/e2e_session_primary-2026-10-18.json](evidence/e2e_session_primary-2026-10-18.json).

## Medição (20 turnos SSE reais, narrador DeepSeek)

* **Driver:** `scripts/staging/jev_primary_measure.py`.
  * 2 usuários sintéticos, 2 jogos (Devoto do Abismo, nível 1).
  * Ações: inspeção de objetos (5), conversa com NPC (4), loja compra/venda (3), fabricação (2), tesouro/pegar
    (3), viagem (1), combate (2).
* **Junção:** linha `jev.primary` ↔ turno pelo `x-vercel-id`.
* **Latência do router:** `phase_ms.router` lido do `audit_trace` de cada jogo antes de apagá-lo.

| Medida | Valor |
|---|---|
| Turnos OK (HTTP 200, sem `error`) | **20/20** |
| Decididos pelo Jev | **18/20 = 90 %** dos turnos (18/19 = 94,7 % das chamadas) |
| Fallback para o CLASSIFY | 1: `target_low_confidence` em "Converso com a mulher na praça…". Sem NPC com esse rótulo em cena, o CLASSIFY mandou para a NPC presente. |
| Gate Python (sem chamada Jev) | 1 (viagem explícita) |
| Timeouts / erros / respostas inválidas / kill switch | 0 / 0 / 0 / 0 |
| Latência do Jev (`gru1` → TypeSafe) | p50 **259 ms**, p95 304 ms, máx. 304 ms (prazo de 1 s nunca atingido) |
| **Router, turnos decididos pelo Jev** | p50 **277 ms**, p95 323 ms (n = 18) |
| Router, turno em fallback (Jev + CLASSIFY) | 1.633 ms (n = 1) |
| Router, gate Python | 1 ms (n = 1) |
| Baseline do router com CLASSIFY (SPEC-214, gate real 17/10) | p50 1.473 ms, p95 2.023 ms |
| TTLT do turno (cliente, até `done`) | p50 **7.235 ms**, p95 14.806 ms, máx. 17.200 ms |
| Providers do turno | só `deepseek` (nenhum fallback de LLM) |

Rota dada pelo Jev × rótulo pretendido pelo driver:

| Rótulo | Rota | n |
|---|---|---:|
| story | storyteller | 5 |
| talk | npc_actor | 3 |
| loot_shop | loot | 3 |
| loot_craft | loot | 2 |
| loot_take | loot | 3 |
| combat | combat_agent | 2 |

**Coerência do loot.** A fonte do loot bateu com o resultado mecânico em todos os turnos:

* SHOP → "Não há mercador neste local" / "Ouro insuficiente";
* CRAFT → "Ninguém conhece uma receita";
* TREASURE → item + ouro.

**Narrações.** Revisadas à mão, com o texto fora do repo. Nenhum erro de roteamento visível:

* conversa → fala do NPC presente, com rótulo do falante;
* inspeção → narrador;
* combate → resolução de ataque.

As estranhezas vistas são de conteúdo e anteriores ao Jev:

* não há mercador nos locais iniciais;
* "Vendo a adaga velha" não casa com a "Adaga de Ferro" do inventário;
* a viagem explícita é decidida pelo gate Python.

## Chamadas e custo

* **Jev:** 22 chamadas na janela, sendo 19 dos 20 turnos e 3 do `e2e_session`, abaixo do teto de 40. O
  TypeSafe não informa custo; pela reserva de US$ 0,01 por chamada, isso dá ≈ US$ 0,22.
* **DeepSeek:** 25 turnos + 3 jogos novos, ≈ US$ 0,10. O custo exato está em `app.usage_events`.
* **Limpeza:** jogos e usuários sintéticos apagados (2 + 1 do e2e); `errors=[]`.

## Leitura e limites

* **[F]** O router economiza ≈ 1,2 s p50 por turno coberto (1.473 → 277 ms).
* **[F]** Nenhuma escalada para combate fora dos dois turnos de ataque explícito.
* **[H]** A amostra é pequena (20 turnos, 1 classe, 1 narrador). A TTLT p50 de 7,2 s não é comparável ao
  baseline de 10,5 s da SPEC-214, que usou outras ações e outros jogos. O ganho seguro é o do router.
* **[R]** Monitorar `jev.primary` com `outcome≠primary`. Se a taxa de fallback subir ou aparecer
  `timeout`/`error`, desligar com o kill switch ou com o rollback abaixo.

## Rollback

* **Imediato, sem deploy:** acionar o kill switch `decision_backend:jev` (SPEC-196,
  `scripts/admin_kill_switch.py`). O router volta ao CLASSIFY no mesmo turno.
* **Definitivo:**
  1. `python -m scripts.staging.vercel_env --jev-router off`, que apaga `RPG_JEV_ROUTER_MODE`,
     `RPG_JEV_ROUTER_PRIMARY_APPROVED` e `TYPESAFE_API_KEY`.
  2. `vercel deploy --prod -e GIT_SHA=<HEAD>`.
  3. Conferir `/health` e zero linhas `jev.*` nos logs.
* **Alternativa:** promover `rpg-ia-master-staging-bi7io32h1-…vercel.app` (`cae84b2`, `off`).

Evidência: [evidence/primary-staging-2026-10-18.json](evidence/primary-staging-2026-10-18.json) (SHA-256
`73940c24…f9746e`). Contém só as ações sintéticas do driver, rótulos, booleanos e latências: nenhum id,
e-mail, segredo ou narração.
