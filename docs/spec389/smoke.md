# Smoke: SPEC-389 §6 (LLM real)

Feito em 04/11/2026.

**Staging.** `hosted-supabase`, `/health` com `git_sha` `70c7ebc3` (389 na `main`), preset com cartas `on`. `post_deploy_smoke`, `vercel_smoke` e `e2e_session` passaram. Medição feita pelo coordenador às 06:51–06:58 UTC. Ela usou uma conta sintética com 1 jogo, apagado no fim (`users_exist_after: [false]`). `image_generation` foi ligado antes da 1ª amostra e desligado no fim (`list` → `false`). Não houve retrato pago.

**Local.** Itens 2–11 em [smoke-local.md](smoke-local.md) (agente Sonnet), com 9 de 10 ok e 3 P3 de texto (abaixo).

## Item 1: S7-1 (R1–R7), medição da oferta

Evidência: [offer-measure-20261104.json](offer-measure-20261104.json), que só contém hashes, sem cookie, id de jogo ou segredo.

| Amostras | Com oferta | Com `offer_view` | Causas de omissão | Instâncias Vercel | Jogo (API × navegador) |
|---|---|---|---|---|---|
| 6 API + 6 navegador (1440, 390, 1440, 1280, 1440, 390) | **12/12** | **12/12** (`missing: 0`) | nenhuma | 3 (`64403721` 4/4, `60a00558` 7/7, `3724f076` 1/1) | o mesmo `b3e050eb` / `game_ref 1d01a0ba…` dos dois lados |

- **Kill switch.** O `audit` registra o `on` às 06:48:48, antes da 1ª amostra.
- **R6/R7.** Depois da 389 não houve omissão por causa inesperada em nenhuma instância. As correções confirmadas no código explicam as quedas que os smokes 6 e 7 tinham visto:
  - o `None` de `peek_ceiling` deixou de ir para o cache de 60 s (`price_absent`);
  - o snapshot do kill switch passou a ter idade máxima.

  A hipótese "jogo diferente" (API × navegador) foi descartada: os dois lados leram o mesmo jogo.
- **Correções no script de medição feitas no smoke** (commit deste registro):
  - O navegador ia à home e não abria o jogo. O app não tem link direto, então entrou `--hero` (clique no herói da lista) com `expect_response("/game/state")`.
  - `PORTRAIT_MEASURE_SHOTS` grava um print quando a leitura falta, para diagnóstico.
  - O Playwright Python precisou de `python -m playwright install chromium-headless-shell` na máquina.

## Achados restantes (P3, smoke local)

1. **Nome do herói no registro do Voto.** O registro mostra "Goblin, provocado por Hi4, muda de alvo.", e deveria ser "provocado por você".
2. **Título da quest no recibo.** `turn_outcome.quests_completed` traz `title: "q368"`, que é o id. Precisa ser conferido com uma quest real.
3. **Pronome no Voto.** O texto do item 5 diz "Você está provocado: a próxima intenção dele mira Soldado". O sujeito é o herói, mas "dele" aponta para outro.

Os três seguem para correção na SPEC-390.
