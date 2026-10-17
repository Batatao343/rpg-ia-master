# SPEC-212 — follow-up de eval da revisão Sol (não bloqueante)

Revisão independente (Sol ≡ Opus). Nenhum arquivo de régua foi editado pelo revisor.

## Item 1 — comentário da allowlist contradiz KI-3 (cosmético)

`web/e2e/vertical-support.ts` (`VERTICAL_ALLOWLIST`) diz que o beacon de latência "é enviado com keepalive".
O cliente usa `fetch` comum (`web/src/api.ts` `sendClientLatency`, sem `keepalive`), como registra KI-3; o
`ERR_ABORTED` vem do beacon fire-and-forget abortado por `page.reload()`/navegação da jornada. A regex
(`/telemetry/client-latency net::ERR_ABORTED$`) está correta e estreita (o dataset `gg.console.allowlist_is_narrow`
prova que `/game/action*` nunca é tolerado). Sugestão: corrigir só o comentário na próxima autoria + relock.

## Item 2 — BLOQUEANTE: corrida em V01 (`vertical-journey.spec.ts` ~l.242)

Gate `--strict` no commit `2f3aacb8badf` (árvore limpa): `ok: false`. desktop-1440 V01–V09 verdes;
desktop-1280 V01 falhou com `save recém-criado na lista` (undefined) e V02–V09 ficaram `skipped`, o que deixa
todos os oráculos `not_provisioned` (falta o trace 1280).

Causa (log da API do gate): a ordem foi `POST /game/prologue` → **`GET /game/saves` (da jornada)** →
`POST /game/new 200`. O produto monta a tela de jogo com o composer (`textbox "Sua ação"`, botão "Enviando…")
enquanto `/game/new` ainda está em voo ("o narrador tece o destino…") — estado de carregamento intencional.
`await composer().waitFor()` resolve nesse estado, e a jornada lê `/game/saves` antes de o jogo existir.
Passa quando `/game/new` é rápido (1440, execuções isoladas), falha sob carga (após F01–F40 no mesmo gate).

Correção sugerida (só na jornada, sem afrouxar oráculo): esperar a resposta de `/game/new` antes de seguir,
por exemplo `const created = page.waitForResponse(r => r.url().endsWith("/game/new") && r.request().method() === "POST");`
registrado antes do clique em "Começar a jornada", `expect((await created).ok()).toBeTruthy()`, e então
`await expect(composer()).toBeEnabled()`. Opcional: poll em `/game/saves` até conter `HERO`. Precisa de relock +
`eval-governance`. Artefatos da falha guardados fora do repo (scratchpad do coordenador:
`spec212-failed-gate/`: evidência JSON/MD, `gate-vertical.json`, `gate-api.log`, trace/screenshot).

## Item 3 — mutações
Mutações aplicadas pelo revisor no evaluator (removendo `duplicate:replay_new_turn`, removendo `\d+\s*xp` do
`_XP_IN_PROSE`, allowlist que aceita tudo) foram todas pegas por `tests/test_eval_gameplay_gate.py`
(corpus + blind/paranoid oracle). Revertidas.
