# SPEC-296 — revisão sol (review)

> **Veredito:** `APPROVED`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-23 · **Commit revisado:** `4037737`

## Escopo

Branch `spec-296` (`f4d9748..4037737`, diff vs `main`): `services/ambient.py` (novo),
`agents/combat.py` (`_flee_alert_world`, `_ambient_for_combat`, fechamento do encontro),
`agents/storyteller.py` (pulso → `append_news`, `<AMBIENTE>`/`<OUVIU_DIZER>`),
`agents/npc.py`, `api.py::_world_block`, `state.py`, UI (`Hud.tsx::HeardNews`,
`heardNews.ts`, `ContextSurface.tsx`, `types.ts`) e os testes novos.
Fora: Etapa 5 (R1, staging `shadow` → `on`), que fica com o coordenador; smoke real §6.

Conferência por requisito:
- **R2:** um alerta por encontro. O registro roda só no ramo `combat_over`, uma vez, com o
  1º fugitivo (`fled` ou `status == "fugiu"`). Esse caminho cobre a fuga pelo orquestrador
  (`conflict_orchestrator.py:1306`) e pelo `_stalemate_guard` (`:1813`). Os desfechos
  `fled` (herói), `death` e `surrendered_enemy` não registram. `turn` = `world.turn_count`,
  `faction_id` vem do inimigo, e a simulação é excluída. O `world` de entrada não é mutado
  (`register_flee_alert` copia).
- **R3:** com `_ENCOUNTER_COOLDOWN` = 2 (+2 no early game) e `_ALERT_TTL` = 6, o reforço é
  alcançável. O alerta é consumido uma vez e o teste prova o `reason="reinforcements"`.
- **Regra de ouro:** `world.news` só recebe o rumor do pulso que entrou em
  `EVENTOS_DESTE_TURNO` (o schema `WorldPulse.rumor` já é "o que o JOGADOR percebe"). O
  `<OUVIU_DIZER>` traz a instrução "não invente detalhes além do texto". O hint do alerta
  usa o nome canônico da espécie (é o que o spawn precisa). Na UI (`world.threats`) e na
  narração do reforço, esse nome passa pelo `format_response → conceal_payload`
  (SPEC-293), então uma fação desconhecida não vaza. `active_threats` não expõe
  `faction_id`. As "Saídas" já aparecem ao jogador no `map_view` (destinos de viagem).
- **Saves antigos:** todo leitor usa `.get("news") or []`. Há round-trip save → load sem
  `news` e com `news` (`test_legacy_save_without_news_loads`).
- **Tamanho do prompt:** medi `<AMBIENTE>` nos 35 locais × 3 audiências. O máximo é
  369 chars (~100 tokens), dentro da estimativa de 80–150 da §7. `<OUVIU_DIZER>` = no
  máximo 3 rumores.
- **Letalidade:** o executor mediu 11/25 e 8/18 (0,44) contra o baseline 9/19 e 11/19, com 0
  `no_progress`. Isso fica dentro da meta M1 da SPEC-285 (≤ 0,564). Os encontros sobem
  (25 contra 19 no seed 1) e as mortes absolutas também (9 → 11), mas a taxa por combate
  cai. A amostra é pequena e o resultado é coerente com o risco previsto na §7.
- **UI:** React renderiza o texto escapado (sem `dangerouslySetInnerHTML`), a lista vai da
  mais nova para a mais antiga, o rótulo é "Dia N · Período · Local" e há estado vazio.
- **Guards:** nenhum `with_structured_output` novo. Nenhum segredo em log. Nada em
  `evals/`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/ambient.py:107` (`append_news`); `agents/storyteller.py:792` | O rumor é texto do LLM, persistido em `world.news` e reinjetado no prompt sem limite de tamanho. Só passa por `sanitize_meta_preamble`. Um rumor longo infla save, HUD e `<OUVIU_DIZER>`. | Truncar em `append_news`, por exemplo 280 chars com reticências, mais um teste. |
| P2-2 | P2 | `agents/npc.py:781`; `agents/storyteller.py:837` | `ambient_block` é chamado sem guarda no NPC e no storyteller. No combate há guarda (`_ambient_for_combat`). A função é pura e defensiva, mas uma exceção derrubaria o turno inteiro por um bloco opcional. | Usar o mesmo `try/except → ""` (ou um helper comum) nos três consumidores. |
| P2-3 | P2 | `agents/combat.py:862` | O desfecho `defeat` (herói inconsciente com inimigo restante) registra o alerta quando havia um fugitivo. A spec não proíbe, mas isso empilha reforço logo após uma derrota. | Opcional: excluir `defeat` ou registrar a decisão na spec. Medir no próximo playtest de combate. |
| P2-4 | P2 | `tests/test_flee_alert_wiring.py:93` | O R3 é provado chamando `check_encounter` direto. Falta o caminho completo combate → storyteller (viagem/descanso) → spawn de reforço. | Follow-up: teste que encadeia `combat_node` (fuga) → `storyteller_node` (descanso não seguro) com seed. |
| P2-5 | P2 | `web/src/components/Hud.tsx:236` | As classes `heard-news*` não têm CSS. A lista herda estilos genéricos. | Cosmético: estilo no CSS do HUD, se o dono quiser. |

Nenhum P0 ou P1.

## Correções aplicadas

Nenhuma (revisão só de leitura).

## Pendências

- P2-1/P2-2: correção pequena. O executor pode aplicar antes do pouso ou num follow-up da
  SPEC-298.
- P2-3/P2-4: decisão ou medição no próximo playtest de combate (coordenador).
- Etapa 5 (R1) e smoke real (§6): coordenador. Os checkboxes da §5 seguem abertos até lá.

## Comandos rodados

```text
git diff main...HEAD --stat → 15 arquivos, +877/-73
py.sh -m pytest tests/test_ambient.py tests/test_ambient_consumers.py tests/test_flee_alert_wiring.py → 20 passed
py.sh -m pytest -n auto -k "combat or encounter or storyteller or npc or light or weather or clima or luz or world_block" tests → 679 passed, 3 skipped
node --test web/tests/heardNews.test.mjs → 2 pass
npm run typecheck (web) → ok; eslint nos arquivos web alterados → ok
ruff check + ruff format --check nos .py alterados → ok
script ad hoc: ambient_block em 35 locais × 3 audiências → máx. 369 chars
```
