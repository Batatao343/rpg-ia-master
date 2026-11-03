# SPEC-384 — revisão independente (spec `draft`)

> **Veredito:** `CHANGES_REQUIRED` (1 P1 de semântica no D1 e fatos [F] desatualizados; nenhum P0)
> **Revisor:** Opus (spec-reviewer, não é o autor) · **Data:** 2026-11-03 · **Commit revisado:** `2a6e0945` (main)

## Escopo

Revisão crítica da spec `specs/SPEC-384-poda-decisoes-dono-flags-perfis.md` (cardápio D1–D9), não de código
implementado. Conferi os fatos [F]/[H] no source, procurei consumidores escondidos, runbooks, choques com as
specs 376/378/381/383 e rodei a W1 de novo. Fora: W2 (evals/playtest), deploy, LLM real.

### Veredito por D

| D | Veredito | Resumo |
|---|---|---|
| D1 | **SAFE-WITH-CHANGES** | lista das 12 flags confere; R1.5 muda a semântica do CALENDAR sob `WORLD_ENGINE=shadow` (P1-1); falta consumidor escondido (P2-1/P2-2); fato do staging desatualizado (P1-2) |
| D2 | **SAFE** | só decisão; as 11 shadow conferem; dependência RUMORS_ADOPTED → RUMORS_PROPOSED confirmada (`services/rumor_adoption.py:36-47`) |
| D3 | **SAFE-WITH-CHANGES** | raio confere e a separação do "fugitivo voltou com reforços" está certa; faltou `test_spec325_flags.py:9-10`; a afirmação do `KeyError` está errada e mascara chamador que sobrar (P2-3/P2-4) |
| D4 | **SAFE** | nada é apagado; G3 confere (`agents/combat.py:2286, 2803`); 33 arquivos de teste citam `RPG_CARD_DECK` hoje (não 29) |
| D5 | **SAFE** (opção a) | tuplas idênticas confirmadas (`infrastructure/runtime.py:225-226`); manter é o certo |
| D6 | **SAFE** | só testes e docs importam `game_engine`; já existem testes de API para checkpoint/morte (`tests/test_bug_morte_checkpoint.py:139, 164, 224`); faltam 3 docs na lista (P2-6) |
| D7 | **SAFE** | sem chamador de produção; trava R7.3 já resolvida: a SPEC-376 exclui `set_deck` (`specs/SPEC-376-…md:42, 226, 244`); a 368 já pousou |
| D8 | **SAFE** (só art) | `/art/player/confirm` só tem testes e docs como consumidores; manter `/auth/logout` está certo, mas a evidência "bundle versionado" é falsa (P1-3) |
| D9 | **SAFE** | só `api.py:7139` e `observability/metrics.py:17` (+ o teste); 0 ocorrências em dashboards, alerts, grafana, prometheus, scripts e evals |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | spec R1.5; `services/world_calendar.py:36-47`; `tests/test_spec303_hook.py:113-117` | Para aposentar uma folha, a R1.5 manda `mode()` virar `"on" if mae=="on" else "off"`. O calendário **não** segue esse padrão: com `RPG_WORLD_ENGINE=shadow` ele devolve `shadow` e grava `world_sim.calendar_shadow`. Pela fórmula ele viraria `off`. Ou seja, muda o comportamento no modo `shadow` do motor, que ainda é o default de `vercel_env.py:266/530` com `--no-preset`. | No CALENDAR, aposentar = `mode()` devolve `world_engine.mode()` (repassa off/shadow/on). Acrescentar `calendar_shadow` à R0.5 (save aceito). Para LORE_QUESTS/WORLD_QUESTS/RUMORS a fórmula está certa, porque elas já rebaixam para `off` quando a mãe não está `on`. |
| P1-2 | P1 | spec R1.1, §1 item 3, §3.1 (OPENING_THREAD) | "Staging = `fae9a4e` (28/10)" está desatualizado. O smoke 4 rodou no staging `cc31a6c1` (02/11, cartas `on`), segundo `docs/spec364/achados-smoke4.md:5`. O `ESTADO_ATUAL` está atrasado. Isso afeta o R1.2(b), "smoke no deploy atual", e o G1 do D4. A conclusão sobre OPENING_THREAD continua de pé: `cc31a6c1` não tem `services/opening_threads.py`. | Trocar o fato por "staging = o SHA do último deploy registrado (conferir no Vercel/handoff do smoke)". O executor confere o SHA real antes de cada lote. |
| P1-3 | P1 | spec R8.1, R8.2, R8.3, §7 e auditoria §6.5 | O "bundle Android versionado no repo" **não é versionado**: `web/android/.gitignore:96` ignora `app/src/main/assets/public`. O `index-CUkFp7vO.js` é um build local de 15/10. A decisão de manter `/auth/logout` continua certa por outro motivo: **3** scripts de staging usam a rota (`e2e_session.py:285`, `measure.py:74`, `two_user_smoke.py:206`), não 2. | Reescrever a evidência: "build Android local/instalado (não versionado) + 3 scripts de staging + e2e fixture". Tirar o [F] de "versionado". |
| P2-1 | P2 | `tests/test_spec363_latency.py:79-80` | Faz `monkeypatch.setattr(latency_flags, "two_phase_on"/"replan_after_on", …)`. Se a R1.3 apagar essas funções ("vira constante ou some"), o teste quebra com `AttributeError`. Ele não aparece na linha das flags no §3.1. | Pôr na linha NPC_TWO_PHASE/REPLAN_AFTER. Preferir manter `two_phase_on()`/`replan_after_on()` como função que devolve `True`, ou ajustar o teste no mesmo commit. |
| P2-2 | P2 | `docs/spec302/world_engine_sim.py:186-199, 302-309, 356` | Simulador versionado que põe `RPG_CALENDAR=off` e `RPG_RUMORS=…` (há um `--calendar off`). O gate da SPEC-340 varre todo `.py` versionado, então a entrada no registro não pode sumir enquanto o script citar o nome. O arquivo não está no §3.3, que é a lista da W1. | Acrescentar ao §3.3 (D1 CALENDAR/RUMORS) e decidir: tirar o modo `off` do sim ou deixá-lo como no-op. |
| P2-3 | P2 | `tests/test_spec325_flags.py:9-10` | `assert len(cf.CAPS) == 8` e `len(set(ENV_VARS.values())) == 8` quebram quando o cap sai. A spec só lista `:13, 57-60`. Também `playtest/capabilities.py:39` deriva `KEYS` de `CAPS` e `tests/test_spec325_playtest.py:38` confere esse conjunto. | Incluir `:9-10` (vira 7) e citar `capabilities.py:39`/`test_spec325_playtest.py:38` no D3. |
| P2-4 | P2 | spec R3.2 (`docs/spec285/arena_lethality.py:249`); `services/combat_flags.py:50-55` | A spec diz que `combat_flags.mode("reinforcements")` levantaria `KeyError` sem o cap. Não levanta: cap desconhecido cai em `_DEFAULT_MODE.get(cap, "shadow")` e devolve **`shadow`** em silêncio. Um chamador que sobrar passa a rodar o ramo shadow sem nenhum erro. | Corrigir o texto. Acrescentar ao `test_spec384_reforcos.py` um grep/AST que garanta que não sobra `mode("reinforcements")`/`active("reinforcements")` em `.py` versionado, ou fazer `mode()` levantar com cap desconhecido (muda contrato; só se o dono quiser). |
| P2-5 | P2 | W1 (auditoria §6.2) | A W1 rodada hoje mostra `api.py` e `observability/metrics.py` presos pela branch **`spec-214`** (SPEC-214 `done`, último commit 17/10, 1 commit à frente). Com isso, D8/D9 nunca passariam. `spec-349-pre-sync` (68 commits) também é resto de outra rodada. | No Etapa 0, ignorar branches cuja spec está `done` (ou cujo patch já está na `main`, `git cherry`) e registrar a exclusão. Limpar as branches mortas fica com o dono/coordenador. |
| P2-6 | P2 | spec R6.1 | A lista de referências ao CLI não cita `docs/descricao_projeto/**` (guia interativo, explore_01), `docs/melhorias_workspace/02-linters-e-checks.md:14,70` nem `docs/spec223/README.md:14`. | Acrescentar à lista (só docs; o histórico pode ficar). |
| P2-7 | P2 | `specs/SPEC-381-refactor-api-routers.md:202-203` | A 381 mandou para a 384 também "`/game/map` vs `/data/map`". A 384 não trata esse par. As duas rotas estão vivas: o web usa `/game/map` (`web/src/api.ts:117`) e o `smoke_api.sh`/legado usam `/data/map` (`api.py:4080`). | Registrar no §2 "Fora de escopo" (as duas são rotas distintas com consumidor), para fechar o laço com a 381. |
| P2-8 | P2 | spec §7 "Perda do rollback" | As specs `done` 302:865, 303:698, 305:625, 307:614 e 313:792 documentam `RPG_X=off` como rollback. Nenhum runbook (`docs/spec197`, `docs/operacao`, `docs/guias`, `.github`, `.claude`) manda desligar essas flags. | Citar essas linhas no §7 e anotar no corpo de cada commit do D1 que aquele rollback documentado passa a ser `git revert`. |
| P2-9 | P2 | §3.1 contagens | Diferenças pequenas: COMPANION_SOUL tem 4 arquivos de teste com o nome literal (não 6); NPC_SELF tem 6 (não 7); CARD_DECK tem 33 (não 29). Os números de linha mudaram com o pouso da 368 (`set_deck` está em `services/cards.py:493`; o alias art está em `api.py:5053`; a métrica em `api.py:7139`). | Recontar na Etapa 0. Nenhuma decisão muda. |

Conferido e correto: os 12 nomes `on` e os 11 `shadow` em `config/flags.yaml` (todos `expires: 2027-01-25`);
`staging_flags.json` (RUMORS/LORE_QUESTS `on` explícitas; `world_engine: "on"`); `OPTIONAL_FLAGS`/`stale_names`
(`vercel_env.py:67-111, 222-224`) apagam do projeto o que falta no preset, então R1.4 com `REMOVED_NAMES` +
`kind: dev` é coerente com o gate (`scripts/flag_registry.py:111-122`: entrada órfã reprova); leitores montados em
runtime (`llm_setup.py:47`, `observability/logging_setup.py:134`) não tocam nenhuma flag do D1; 0 menções em
evals/fixtures/goldens/workflows/web para as flags do D1; `reforco_proprio` em `data/bestiario/fichas/*.yaml` é
intenção de inimigo (outra coisa: **não tocar** no D3); `combat_meta["reinforcement"]` em save de combate ativo
fica órfão e é ignorado (R0.5 ok); a SPEC-378 já exclui as flags do D1 (`specs/SPEC-378-…md:199-201`).

### W1 rodada de novo (03/11, main `2a6e0945`)

Interseção com a lista de arquivos da 384: `config/flags.yaml` (spec-371, spec-374) · `agents/combat.py`,
`playtest/invariants.py`, `web/src/types.ts` (spec-371) · `api.py`, `observability/metrics.py` (spec-214, morta;
ver P2-5). Com isso **D1 e D3 esperam** a 371 e a 374. D6 e D7 estão livres. D8 e D9 esperam a 381 de qualquer
jeito.

## Correções aplicadas

Nenhuma (revisão de spec; o autor aplica).

## Pendências

- O autor corrige P1-1..P1-3 e incorpora P2-1..P2-9 no corpo da spec antes de ela ir ao dono.
- Coordenador: atualizar o SHA do staging no `ESTADO_ATUAL` (P1-2); limpar as branches `spec-214` e
  `spec-349-pre-sync` com o dono (P2-5).

## Comandos rodados

```text
uv run --frozen python -c "yaml … kind=release default on/shadow" → 12 on + 11 shadow, iguais à spec
W1 (for-each-ref + diff main...b) ∩ arquivos da 384 → 6 arquivos (371, 374, 214)
git ls-files web/android … assets + git check-ignore → bundle ignorado (web/android/.gitignore:96)
git cat-file -e cc31a6c1:services/opening_threads.py → ausente (OPENING_THREAD segue inelegível)
pytest -n 0 test_flag_registry test_spec325_flags test_spec303_hook test_latency_metrics_compat → rc=0 (verde, 1 skip)
uv run --frozen python scripts/flag_registry.py check → rc=0
```
