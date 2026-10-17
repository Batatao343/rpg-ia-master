# SPEC-212 — Etapa 0 (autoria de eval) — handoff para o executor de produto

Autoria separada, anterior ao executor de produto (`EVAL_AUTHORING_REQUIRED`). Nenhum código de produto
foi alterado. Publicar exige aprovação do environment `eval-governance`. Review Sol da autoria ainda pendente.

## O que foi autorado

| Item | Arquivo |
|---|---|
| Jornada J-V1 (V01..V09, 1 sessão serial) | `web/e2e/vertical-journey.spec.ts` |
| Suporte: guardas R10, ledger de turnos/beacon, log rpg.turn, axe por aba, leitor de ZIP, PII, ponte p/ oráculo | `web/e2e/vertical-support.ts` |
| Manifesto (schema_version 2; V01–V09 `suite: vertical`, viewports 1440x900 e 1280x800) | `web/e2e/critical-journeys.yaml` |
| Oráculos da régua (console, turns/R11, secrets/R12, xp/R6, latency/R13, speaker/R2, roster/R3, gesture/R4, a11y/R15) + evaluator + baseline p50/p95 nearest-rank | `evals/evaluators/gameplay_gate.py` |
| Ponte CLI: trace do J-V1 em stdin -> veredito JSON (exit 1 com problemas) | `evals/gameplay_scan.py` |
| Adapter, runner, enum, registry: suíte `gameplay_gate`, 3 métricas bloqueantes + `vertical_journey_pass_rate` | `evals/core/{adapters,runner,schemas}.py`, `evals/metrics-registry.yaml`, `evals/eval-case.schema.json` |
| Corpus: 54 casos fixture-authored (good + bad por oráculo, inclui mutações: oráculo cego/paranoico é pego) | `evals/datasets/regression/gameplay_gate.jsonl` |
| Relatório F/V (`--suite vertical`: 9 passos x 2 viewports, todos `passed`) | `scripts/frontend_eval_report.py` |
| Testes | `tests/test_eval_gameplay_gate.py`, `tests/test_eval_frontend.py`, `tests/test_ci_eval_gates.py` |
| CI: `--suite gameplay_gate` + novo teste no job determinístico | `.github/workflows/eval-gates.yml` |

Evaluator **1.14.0** (era 1.13.0); `evals/manifest.lock.json` relocked com `python -m evals.core.governance lock`
(11 datasets); `check` verde. Decisão D-212-5 registrada na spec (218/219 `done` condicionam só o convite de testers).

## Como a jornada roda (provisionamento que o `scripts/beta_gameplay_gate.py` deve fazer)

Sem as 4 variáveis a jornada fica `skipped` (o gate deve tratar como `not_provisioned`, falha em `--strict`):

- `RPG_VJ_BASE_URL` — API real que serve `web/dist` (perfil `local`, `RPG_FORCE_MOCK=1`,
  **`RPG_CLIENT_LATENCY_REPORT=1`**; `scripts/audit_local_server.py` já seta o resto: rate limit 0, cache runtime isolado).
- `RPG_VJ_PYTHON` — python do projeto (uv): roda `python -m evals.gameplay_scan`.
- `RPG_VJ_SERVICE_KEY` — service key do GoTrue local (usuário sintético confirmado; só `127.0.0.1:55321`, apagado no teardown).
- `RPG_VJ_API_LOG` — arquivo do stdout/stderr da API (linhas JSON `"evt": "turn"` do `rpg.turn`).
- Config Playwright: projetos `desktop-1440` (1440x900) e `desktop-1280` (1280x800), `workers: 1`, sem `webServer` Vite.
  A jornada lê o viewport de `testInfo.project.use.viewport`. Trace por viewport em
  `RPG_VJ_ARTIFACT_DIR` (default `web/test-results/vertical/vertical-trace-<viewport>.json`).

Receita usada na autoria: API `scripts/audit_local_server.py --port 8203` (stdout em arquivo), config temporária com
`baseURL` 8203; F01–F40 com config temporária Vite 4203. Ambas apagadas.

## Resultado agora (stack real + MockLLM, 3 execuções em cada viewport durante a autoria)

| Passo | 1440x900 | 1280x800 | Observação |
|---|---|---|---|
| V01 criar personagem/abrir chat | pass | pass | wizard real, prólogo semeia "Mestre Aldric" |
| V02 narrador x NPC | pass | pass | pergunta -> narrador; fala dirigida -> `speaker.kind=npc`; sem seletor no DOM |
| V03 ameaça -> combate em split + manifesto | pass | pass | aba Combate em split; ids da UI = hostis do manifesto |
| V04 carta por gesto sem confirmação | pass | pass | carta com alvo = 2 cliques; nenhum diálogo |
| V05 vitória e derrota | pass | pass | vitória (`combat_result.outcome`), painel "Vitória", Continuar, exploração limpa; derrota -> DeathModal -> checkpoint |
| V06 XP estruturado + replay | pass | pass | chip `+N XP` = `turn_outcome.xp_delta`; replay devolve o mesmo `receipt_id` |
| V07 abas coerentes + axe | pass | pass | axe sem serious/critical nas 5 abas |
| V08 salvar/recarregar + reload mid-SSE | pass | pass | exatamente um turno; retry do mesmo `action_id` não cria turno |
| **V09 export + oráculos transversais** | **FAIL** | **FAIL** | export válido e sem PII; falha só por `latency:null_server_stream` (abaixo) |

## Lacunas de PRODUTO que o executor precisa resolver (a régua NÃO foi afrouxada)

1. **R13 — `rpg.turn` de turno `transport=stream` sai com `ttfmc_server_ms`/`ttlt_server_ms` nulos** (a linha é
   gravada no commit, antes de as marcas de stream fecharem; o `timings.jsonl` do export diz o mesmo,
   `timing_partial: true`). Spec R13 exige não nulos em stream. Corrigir (emitir a linha após `ttlt`, ou
   completar as marcas antes do log) — ou decisão do dono de mover a presença server-side para as métricas
   Prometheus `rpg_turn_*_seconds` (mudança de régua = nova Etapa 0). As marcas do cliente (beacon) estão
   presentes em 100% dos turnos, com ack <= ttfmc <= ttlt <= state.
2. **Dado sem seed.** Combate e desfecho são probabilísticos (`random.Random()` sem seed). A jornada é adaptativa
   (até 8 tentativas para abrir combate, até 14 rodadas, até 30 turnos para cair; contagens em annotation
   `attempts`) e falha explícita se o desfecho esperado não ocorrer. Para tornar a vitória/derrota **determinísticas**
   como a spec pede (R5), o produto precisa de uma seed de teste (ex.: `RPG_DICE_SEED`) com guarda fail-closed fora
   do perfil de teste. Hoje a flakiness residual é baixa nas campanhas escolhidas (Nova Arcádia/Devoto; Montanhas
   Afiadas/Arcanista), mas existe.
3. **Aliado transitório fora do manifesto (R3).** O NPC em cena (Mestre Aldric) aparece como participante na arena e
   nas Cartas de suporte, mas não consta em `encounter_view.participants` (manifesto SPEC-203 só lista os hostis).
   O oráculo `roster` compara só os hostis (`.tchip--enemy` x `role == hostile`); se o dono quiser que aliados
   também sejam manifesto, é decisão de produto + nova Etapa 0.
4. **UX (informativo):** o modal de nível (`LevelUpModal`) cobre o botão "Continuar" do painel de desfecho; a jornada
   resolve o modal antes (`settleLevelUp`). Carta de suporte `target_kind: self` com aliado em cena entra em mira
   (2 cliques) — correto para suporte, registrado como `card_target` no oráculo de gesto.
5. **Beacon de latência = `requestfailed ERR_ABORTED`** no Chromium (keepalive), mesmo com 204 recebido. É a única
   entrada da allowlist R10 (`VERTICAL_ALLOWLIST`, regex exato por URL+erro; o dataset prova que não tolera aborts
   em `/game/action*`). Remover quando o cliente deixar de reportar isso.

## Mapa para a Etapa 1 (`services/gameplay_oracles.py`, produto, TDD)

Nomes da spec §3.2 -> oráculo de régua equivalente (use-os como contrato; **não editar `evals/`**):
`no_duplicate_turns` = `turn_problems`, `no_unrevealed_secret` = `secret_problems` (strict: só `secret_revealed`
aceito desarma), `xp_not_in_prose` = `xp_problems`, `latency_present` = `latency_problems` (+ `latency_baseline`),
`speaker_matches` = `speaker_problems`, `roster_stable` = `roster_problems`. O orquestrador pode chamar
`python -m evals.gameplay_scan` ou reimplementar com teste de paridade contra `gameplay_gate.jsonl`.

## Armadilhas

- Hash do lock é de bytes: tudo em LF (`.gitattributes`). No Windows, normalize antes de relock
  (`python -m evals.core.governance lock --dataset ...` reescreve schemas/lock em CRLF).
- `innerText` aplica `text-transform: uppercase` nas abas: compare sem caixa.
- O chip de XP dura 4,5 s: só vale como "UI do turno" quando o recibo traz XP (`ui_checked`/`ui_xp` no trace).
- Beacon de latência e linha `rpg.turn` só existem com `RPG_CLIENT_LATENCY_REPORT=1` e log capturado.
