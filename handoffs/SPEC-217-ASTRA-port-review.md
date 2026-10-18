# SPEC-217 — Revisão Astra independente do porte R14

**Veredito: `APPROVED`** (com duas correções aplicadas nesta revisão). Nenhuma chamada live e nenhuma ação
no staging. `primary` continua desligado; ativá-lo é decisão separada do dono, fora da conclusão da spec.

- Revisor: Astra (Opus), sem participação no porte nem no shadow.
- Objeto: `cae84b2` (porte R14) e `3e18035` (docs/evidência do shadow R15), branch `spec-217` sobre `main` `380c532`.
- Scripts da revisão (fora do worktree): `scratchpad/astra217port/diff_off.py`, `golden_old.py`.

## Checagens

| # | Ataque | Resultado |
|---|---|---|
| 1 | `off` idêntico byte a byte | (a) O golden de 15 cenários foi **regravado do router pré-porte** (`8df1770:agents/router.py`, com o `decide_route` de `off` que devolve `None`): 15/15 iguais ao fixture. (b) Diferencial próprio pré-porte × porte: **2.808 casos, 0 divergências** — 9 estados (base, pós-vitória, pós-morte, combate ativo, combate órfão, cena vazia, herói caído, última mensagem de IA, mensagem de sistema) × 24 ações (história, descanso, viagem, “vou ao”, taverna, ataque, “investo”, compra, venda, fabricação, pegar, NPC em cena, party, meta-pergunta ao narrador, descrição de cena, NPC morto, NPC fora de cena, injeção, vazio, hostil+descanso, fuga…) × 13 respostas do CLASSIFY (exceção, `AIMessage` de fallback, todas as rotas/alvos/fontes). `death_pending`/`archived`/`game_over` são barrados no `START` do grafo (`main.py`), antes do router. Com `off`, nenhuma thread, rede, import de `evals` ou telemetria (teste com `_pool` sentinela). |
| 2 | `primary` sem aprovação | Único caminho: `os.getenv("RPG_JEV_ROUTER_PRIMARY_APPROVED") == "1"` em `begin()`; `"yes"`/ausente → `approval_required`, zero chamada. `.env.example` só a cita comentada. `vercel_env.py` só oferece `off|shadow`, coloca a variável em `REMOVED_NAMES` (sempre apagada) e o `production` é montado de listas explícitas (sem passthrough do `.env`). Nenhum script/config/teste fora de monkeypatch a define. `PRIMARY_CALIBRATION=None` também bloqueia (`uncalibrated_threshold`). |
| 3 | Prazo de 1 s | `JevPending._result` espera no máximo `started + 1 s − agora`; o backend usa `timeout=total_timeout=1 s`, `max_retries=0`, HTTP em thread daemon com teto global de in-flight. Thread atrasada não é reaproveitada nem gera retry; o pool (4 workers) só serve a avaliação. Falhas → CLASSIFY: abstenção, baixa confiança, guards de combate/loot, alvo irrepresentável, timeout, erro, resposta inválida, kill switch `decision_backend:jev` e **chave ausente** (`configuration`, teste novo, sem rede). |
| 4 | Shadow não muda rota / não atrasa | Rota e alvo vêm sempre do CLASSIFY; `_finalize` da decisão Jev só alimenta a comparação (sem métrica/estado; teste de não mutação). **Defeito corrigido:** `observe()` esperava o Jev até o prazo quando o CLASSIFY terminava antes (ex.: CLASSIFY que falha rápido) — até ~1 s a mais no turno. Agora, se o Jev ainda não terminou, a comparação roda em callback ao fim dele e o turno segue sem espera (`wait_ms=0`); resposta após o prazo é registrada como `timeout` (o que o `primary` faria). Logs: rótulos, booleanos, latências e códigos fixos de erro; sem texto do jogador, nomes ou texto do provider (testado). O texto da ação vai ao TypeSafe por construção (aceito na spec). |
| 5 | Ordem dos gates | Combate ativo (`_combat_gate`) → turno de recuperação → descanso/viagem explícitos (SPEC-229) → `pre_classify` do interlocutor (SPEC-202, agora **antes** do Jev; no SPEC-180 vinha depois) → Jev → CLASSIFY. Testes cobrem viagem, meta-pergunta, combate ativo e, nesta revisão, descanso, descrição de cena e ação vazia: zero chamada Jev. |
| 6 | ID → nome | `target_name_for_id` percorre `npcs` → `party` → `enemies` na mesma ordem de `scene_view` (`setdefault`), e o teste de paridade com `map_target_to_id` da J2 cobre todos os atores visíveis. O Jev só pode escolher IDs da lista de opções (validado em `_validate_answer`). **Defeito corrigido:** se mesmo assim um ID não fosse nomeável, o `primary` seguia com alvo `None` (virava “Inimigos”/interlocutor por texto); agora cai para o CLASSIFY com `reason=target_unmapped` (teste novo). |
| 7 | Digests importam a política | `test_production_uses_the_frozen_policy_and_calibration` importa `jev_router_hybrid`/`spec238_loot` (os mesmos módulos que `jev_rollout._frozen()` usa) e recalcula `structure_digest` J1 `80225d16…10f5` e J1b `75635c89…2247`; τ rota/alvo/fonte = 0,50 = `PRIMARY_CALIBRATION`. A requisição de produção é comparada byte a byte ao `frozen_j1b_request` (sem features de local). |
| 8 | `vercel.json` | Passa a empacotar `evals/core` + `evals/experiments` + avaliadores (≈ 0,8 MB com `.pyc`), longe do teto de 500 MB (bundle ~315 MB, SPEC-192). Excluídos `evals/runs`, `evals/datasets`, `evals/experiments/data`; `.vercelignore` já tira `evals/runs`, `.env*`, `docs`, `tests`. Nenhum arquivo privado ignorado em `evals/` (holdout fica fora do repo). Os módulos importados só leem arquivos de dados dentro de funções de CLI (nunca no import nem no caminho de produção); `load_dotenv` só em `main()`. |
| 9 | Evidência do shadow | Recalculado do JSON: 58 turnos, 55 observações, 54 cobertas, 52 concordâncias de rota (96,3 %), confusão `loot→storyteller` ×2, 0 escalada para combate, `wait_ms` máx. 0, latência máx. 367 ms. 56 chamadas = 55 + 1 da sonda. Junção exata por `requestId`; a deduplicação (mesmo timestamp + mesmos campos, preferindo a cópia de `/game/action/stream`) só colapsa cópias idênticas do Fluid compute. JSON sem chave, e-mail, `game_id` ou nomes. A correção do item 4 não invalida a evidência: com `wait_ms=0` em todas as linhas, o caminho executado é o mesmo. |

## Correções desta revisão

- `services/jev_rollout.py`: shadow não bloqueante (callback ao fim do Jev; `timeout` se passou do prazo);
  `primary` com alvo não nomeável → fallback `target_unmapped`; `_event` aceita sobrescrever `reason`/`covered`.
- `tests/test_jev_router_port.py`: testes de shadow esperam o evento assíncrono; novos testes — shadow lento
  não atrasa (< 0,15 s), resposta tardia dentro do prazo ainda é comparada, alvo não mapeado, chave
  ausente, mais gates Python antes do Jev.

## Verificação

- Testes do porte: 31 passed (4 execuções repetidas, sem flake); afetados (`test_jev_rollout`,
  `test_router_interlocutor`, `test_spec196_finops`): 97 passed, 1 skipped.
- Suíte completa, ruff e `project_index check`: ver o commit desta revisão.

## Riscos remanescentes (não bloqueiam)

1. Léxico de verbos: “investo/acerto/atiro/encaro” seguem sem `attack` → fallback (latência, nunca erro).
   O shadow viu 1/55 (`combat_guard`). Mudar o léxico invalida digest e calibração.
2. Discordância `loot→storyteller` (2/54) no shadow: com `primary`, esses turnos iriam ao narrador em vez do
   loot. Não é escalada insegura; vale olhar antes de pedir `primary`.
3. Observação tardia do shadow roda em thread do pool; numa função serverless congelada após a resposta,
   ela pode se perder (sem efeito no jogo). Com SSE o turno continua aberto, então na prática é registrada.
4. Custo do Jev desconhecido (`unavailable`); nenhuma economia é alegada.

## Decisão pendente fora da spec

Ativar `primary` em qualquer ambiente exige aprovação explícita e separada do dono
(`RPG_JEV_ROUTER_PRIMARY_APPROVED=1`).
