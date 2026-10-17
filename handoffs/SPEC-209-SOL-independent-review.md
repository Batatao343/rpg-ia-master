# SPEC-209 — revisão independente Sol (Opus, contexto separado)

- **Data:** 2026-10-17 · **Base:** `main` 625540c + implementação não commitada na branch `spec-209`
- **Revisor:** Sol (≡ Opus), não autor da implementação.
- **Veredito:** **APPROVED_WITH_FIXES** — 3 defeitos corrigidos nesta revisão; status `in-progress` só pela autoria de eval separada.

## Verificações pedidas

1. **`web/e2e/fixtures.ts` e o lock de governança.** Não faz parte do lock: `uv run --frozen python -m evals.core.governance check --root .`
   → `eval governance valid: 9 dataset(s)` antes e depois. A edição (mock de `POST /game/cards/prepare`) fica.
2. **Segurança/integridade da rota `POST /game/cards/prepare`.**
   - Ownership/CSRF: o middleware `_session_boundary` cobre todo `/game*` nos perfis DB (principal + CSRF em métodos não-GET);
     `load_game_state` resolve pelo owner, igual a `/game/equip`.
   - Operação/idempotência/lease/fencing: `_begin_state_mutation` → claim com `base_version`; `operation_scope`; `_commit_state_mutation`
     (CAS por versão). Turno em andamento: legacy serializa por `_game_lock(game_id)`; DB conflita no claim (409 `operation_in_progress`).
     Gate de operação falha pendente (`pending_operation`) também vale, por compartilhar o kind.
   - Save intocado em erro: toda rejeição levanta antes do commit; `set_prepared` roda numa cópia rasa (`with_location`) e o estado só
     recebe `probe["player"]` no sucesso. `_location` nunca chega ao save (teste dedicado).
   - Não preparar carta que não possui / limite: decididos só no servidor (`set_prepared`: subconjunto de `known_cards`, `prepare_slots_for_level`).
   - **Defeito corrigido:** a rota não estava na janela do rate limit (equip/levelup estão). Adicionada + `test_prepare_entra_no_rate_limit`.
3. **Reuso de `kind="equip"`.** Seguro: o recibo é indexado por (owner, operation_id, game_id, kind, request_hash) e os payloads
   (`item_id/unequip_slot` × `prepared`) geram hashes distintos — reusar o mesmo `action_id` em outra rota dá 409
   `operation_request_mismatch`, e o replay da mesma requisição devolve o recibo original. Única perda: a auditoria de operações
   rotula preparo como `equip`. Sem migration (evita aplicar DDL em staging por rótulo). Teste `infra_local`
   `test_prepare_cards_shares_equip_kind_without_key_collision` adicionado (skip offline; roda no audit-local).
4. **Restrição `apex` ativa.** Consistente com a §8 item 4 (default: ativar) e com R4. `can_reorganize` usa `world.danger_level`,
   que o motor mantém sincronizado ao perigo efetivo (SPEC-233) na viagem/decay; divergência residual é a mesma do motor.

## Defeitos corrigidos
- Rate limit da rota (acima).
- **R13 "atualizando…" ausente:** deck mostra "· atualizando…" no cabeçalho enquanto salva ou com turno em andamento e bloqueia novo
  preparo nesse intervalo; ficha mostra o mesmo com turno em andamento. Node + Playwright (servidor atrasado).
- **GET pós-preparação falho virava "Não foi possível preparar"** apesar do save gravado: agora aplica `cards/prepared_slots` da resposta.
- Cosmético: contagem colada ao rótulo ("PREPARAÇÃO1/2") por flex do `.hud__label`.

## Critérios restantes concluídos
- axe sem serious/critical em 320 e 768 (Combate, Personagem/Ficha, Jornada); 390/1440 já cobertos.
- Split 50% em 1440: no máximo uma região rolável com overflow no painel, nas duas abas (deck forçado a transbordar).
- Evidência: `docs/spec209/evidence/{1440-split50-combate,1440-split50-personagem,390-combate,390-personagem}.png`.

## Execução
- `uv run pytest` completo (`--ignore=tests/test_project_index.py`): exit 0, ≈3.240 passed, 185 skipped, 0 falhas.
- `npm test` 107/107; `npm run build` verde; Playwright Chromium `--workers=1` (config temporária porta 4195, removida):
  deck-character + workspace-shell + combat-gesture + combat-outcome + critical-journeys = 65 passed.
- Ruff nos .py tocados verde; governança de eval válida.

## Follow-ups (fora do aceite)
- `reaction.present`, `passive.trigger`, `encounter.enter/exit` (adiados da SPEC-208) não implementados — dependem de janela de reação
  emitida pelo backend; registrar em spec de contrato de reação.
- Autoria das jornadas F (`handoffs/SPEC-209-eval-authoring.md`) — único item para `done`.
- Opcional: kind dedicado `prepare_cards` numa próxima migration de operações, se a auditoria precisar distinguir.
