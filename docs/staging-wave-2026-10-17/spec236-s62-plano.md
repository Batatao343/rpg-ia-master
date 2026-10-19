# SPEC-236 §6.2 — teto diário cross-day em 2 dias reais de staging

> Autorização do dono (19/10): medir §6.2 em 2 dias reais de staging. Dia 1 executado em 19/10; **dia 2 NÃO
> executado** — roteiro abaixo, comandos prontos.

## O que §6.2 prova

`services/daily_spend_cap._manually_reenabled` (R3): um re-enable humano só protege o **mesmo dia-de-teto**
do trip que ele respondeu. Bug original: trip de ONTEM + re-enable HOJE + gasto de hoje > teto → `image_generation`
seguia ligado (`manual_override`). Correto: o cron finops de hoje desliga a imagem de novo (override não vaza).

Dia-de-teto = meia-noite em UTC−3 (`RPG_DAILY_SPEND_TZ_OFFSET_HOURS`, default −3, sem horário de verão):
19/10 = `2026-10-19T03:00Z` → `2026-10-20T03:00Z`.

## Dia 1 — 19/10 (executado)

Evidências em `docs/staging-wave-2026-10-17/evidence/spec236_s62_day1_*.json`.

1. `snapshot --label day1_before`: dia-de-teto 2026-10-19, switches do teto ligados.
2. `spend --label day1_spend --turns 3`: usuário sintético + jogo + 3 turnos reais (DeepSeek/Jina). Gasto
   do dia que conta = US$ 0,00717 ≈ R$ 0,036. O usuário e o jogo ficam vivos até depois do trip (apagar o jogo
   apaga em cascata os `usage_events` dele e o gasto some do teto — ver "Achados" abaixo).
3. `vercel_env.py ... --daily-cap-brl 0.01` + deploy (teto temporário R$ 0,01).
4. `finops --label day1_trip --expect-cap-brl 0.01 --expect-trip`: `POST /internal/cron/finops` real →
   `daily_cap_exceeded=true`, `image_generation` e `stt_fallback_expensive` desligados por `system:finops`
   (linhas imutáveis em `app.kill_switch_audit`). **Trip registrado: `2026-10-19T12:12:37Z` (09:12 BRT), dia-de-teto
   2026-10-19, motivo `daily spend cap exceeded: 0.04 > 0.01 BRL`, `daily_cap_manual_override` vazio.**
5. Restauração: `vercel_env.py` sem `--daily-cap-brl` (volta a 5) + deploy; re-enable humano dos 2 switches
   (`admin_kill_switch.py on ... --apply`, ator `staging-1910`); `cleanup` do usuário e do jogo do spend;
   `finops --label day1_restored --expect-cap-brl 5` (teto 5 confirmado no deploy, nada desligado); `e2e_session` verde.
   Estado final do dia 1: deploy `4c4167b` (= main, runtime idêntico ao `563331b` anterior), teto R$ 5, cap de texto
   ligado, Jev `primary`, `image_generation`/`stt_fallback_expensive` ligados (re-enable humano `staging-1910`).

Por que re-ligar no dia 1 e não deixar desligado até o dia 2: o pedido era deixar o staging como estava.
Isso não enfraquece o teste: no dia 2 a linha mais recente do audit será um re-enable humano de 20/10 e
existirá um trip do sistema de 19/10 em `rows[1:]` — exatamente a condição que o código antigo aceitava como
override (`any trip anterior`) e que R3 recusa (trip precisa estar no mesmo dia-de-teto). O re-enable de 19/10
também é de outro dia, então não muda o resultado.

## Dia 2 — 20/10 (NÃO executado) — roteiro

**Horário mínimo:** `2026-10-20 00:00` em Brasília (= `2026-10-20T03:00Z`). Recomendado a partir de
**00:10 BRT**, para não cair na virada do dia (o cron finops agendado roda a cada hora cheia e, com o teto 5,
não dispara nada). Qualquer horário de 20/10 BRT serve; o roteiro inteiro leva ~20 min (2 deploys).

Pré-requisitos: frente "staging" com o worktree `rpg-staging` (branch `staging-1910`), `.env.staging` e
`.vercel` ligados ao repo principal (hardlink/junction), sem outro trabalho mexendo no staging ao mesmo tempo.
Jev `primary` continua ligado em todos os pushes (flags abaixo). Custo esperado: < US$ 0,02.

```bash
cd "C:/Users/guilh/AppData/Local/Temp/claude/rpg-staging"
export PATH="$APPDATA/Python/Python314/Scripts:$PATH" PYTHONUTF8=1 \
  UV_PROJECT_ENVIRONMENT="C:/Users/guilh/OneDrive/Área de Trabalho/rpg-ia-master/.venv"
SHA=$(git -C "C:/Users/guilh/OneDrive/Área de Trabalho/rpg-ia-master" rev-parse main)
DEPLOY='from scripts.staging import s192; import sys; r=s192.vercel(["deploy","--prod","--yes","-e","GIT_SHA="+sys.argv[1]], s192.load_env()); print(r.returncode, r.stdout[-300:]); sys.exit(r.returncode)'

# 0) Pré-check: dia-de-teto = 2026-10-20; audit deve mostrar o trip system:finops de 19/10 e NENHUM trip de 20/10.
uv run --frozen python -m scripts.staging.spec236_daily_cap snapshot --label day2_before

# 1) Gasto real de hoje (> R$ 0,01). Usuário fica vivo até o passo 6.
uv run --frozen python -m scripts.staging.spec236_daily_cap spend --label day2_spend --turns 3

# 2) Re-enable MANUAL hoje (20/10). Escreve linhas humanas no audit, posteriores ao trip de ontem.
for K in image_generation stt_fallback_expensive; do
  uv run --frozen python scripts/admin_kill_switch.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging \
    on $K --actor staging-1910 --reason "SPEC-236 6.2 dia 2: re-enable manual apos trip de 19/10" --apply
done

# 3) Teto baixo temporário + deploy (gasto do passo 1 já passa de R$ 0,01).
uv run --frozen python -m scripts.staging.vercel_env --jev-router-mode primary --owner-approved-primary --daily-cap-brl 0.01
uv run --frozen python -c "$DEPLOY" "$SHA"

# 4) O TESTE: cron finops real. Esperado: daily_cap_exceeded=true, daily_cap_switched_off contém
#    image_generation (e stt_fallback_expensive), daily_cap_manual_override VAZIO, switch image=false.
#    O script sai !=0 se o override vazar.
uv run --frozen python -m scripts.staging.spec236_daily_cap finops --label day2_cross_day \
  --expect-cap-brl 0.01 --expect-trip

# 5) Restaurar: teto 5 + deploy; re-ligar os 2 switches (humano).
uv run --frozen python -m scripts.staging.vercel_env --jev-router-mode primary --owner-approved-primary
uv run --frozen python -c "$DEPLOY" "$SHA"
for K in image_generation stt_fallback_expensive; do
  uv run --frozen python scripts/admin_kill_switch.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging \
    on $K --actor staging-1910 --reason "SPEC-236 6.2 dia 2: restauracao pos-teste" --apply
done

# 6) Limpeza + checagens finais.
uv run --frozen python -m scripts.staging.spec236_daily_cap cleanup --label day2_cleanup
uv run --frozen python -m scripts.staging.spec236_daily_cap snapshot --label day2_restored
curl -s https://rpg-ia-master-staging.vercel.app/health      # git_sha = $SHA
uv run --frozen python -m scripts.staging.e2e_session         # ok=true
```

**Critério de verde (§6.2):** `spec236_s62_day2_cross_day.json` com `ok=true`, `finops.summary.daily_cap_switched_off`
contendo `image_generation`, `daily_cap_manual_override` vazio, e `after.audit_recent` mostrando, em ordem:
trip `system:finops` de 19/10 → re-enable humano de 20/10 → novo trip `system:finops` de 20/10.
Com isso o item "Smoke real §6" da SPEC-236 fecha e a spec pode ir a `done` (coordenador).

**Se der errado:** se o passo 4 mostrar `image_generation` em `daily_cap_manual_override`, o override vazou
(regressão de R3) — restaurar (passo 5) e abrir bug. Se `daily_cap_exceeded=false`, conferir que o deploy pegou o
teto (`--expect-cap-brl` falha) e que o gasto do passo 1 está no dia-de-teto de 20/10.

## Achados (dia 1)

`app.usage_events` tem FK `ON DELETE CASCADE` para `app.games` e `app.operations` (e é `PRIVATE_TABLES` na exclusão
de conta). Apagar a campanha apaga os eventos de uso dela, e o gasto do dia
deixa de contar no teto diário e no FinOps. Visto no staging: o retrato da Tarefa A (US$ 0,011) sumiu do gasto
do dia assim que a campanha foi apagada. Em produção, um jogador que apaga a campanha no mesmo dia "devolve" o
gasto ao teto (e o relatório de margem perde o custo). A SPEC-222 R7 declara retenção de 13 meses para
`usage_events`, o que o cascade contradiz. Registrado para decisão do dono (provável spec de follow-up:
`usage_events` sem cascade/anonimizado na exclusão).

Segundo achado: `app.games` não tem FK para `auth.users`; apagar um usuário pelo Admin API (como os smokes fazem)
deixa o jogo órfão. Havia 13 jogos órfãos de smokes antigos no staging em 19/10 (não mexidos). Os smokes desta
frente apagam os próprios jogos (`spec236_daily_cap cleanup`, `e2e_session`). A exclusão de conta do produto
(SPEC-190) apaga os jogos explicitamente, então o efeito é só de higiene do staging.
