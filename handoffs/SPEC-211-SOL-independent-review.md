# SPEC-211 — Revisão Sol independente

- **Revisor:** Sol (≡ Opus, contexto separado; não escreveu a implementação)
- **Data:** 2026-10-17 · base `main` 625540c + implementação não commitada na branch `spec-211`
- **Veredito:** **APPROVED_WITH_FOLLOWUPS** após 2 correções com teste. Spec fica `in-progress`
  apenas pela autoria separada do eval de leak (`handoffs/SPEC-211-eval-authoring.md`).

## 1. Governança
`uv run --frozen python -m evals.core.governance check --root .` → `eval governance valid: 9 dataset(s)`.
`web/e2e/fixtures.ts` e `web/e2e/effects.spec.ts` NÃO estão em `evals/protected-paths.txt`
(o protegido é `web/e2e/contracts`); `critical-journeys.yaml/.spec.ts` intactos. As edições
(rota `/game/codex/dossiers` na fixture e no cenário `codex.entry.reveal`) foram mantidas.

## 2. Ataque de vazamento
| Vetor | Resultado |
|---|---|
| Entidade hidden/secret (contagem, arte, id, relações, encontros, crônica, versão) | OK — tudo parte de `player_codex` (SPEC-206, fail-closed); `_events_about`/`chronicle_index` filtram por entidade visível; `version` global = max só dos visíveis; `test_oculto_e_inexistente_indistinguiveis` (payloads byte-idênticos). |
| Texto de segredo | OK — só `world_projection.revealed_facts` aceitos (via SPEC-206). |
| NPC `hidden_traits`/`memory`/`npc_secrets` | OK — dossiê não lê memória bruta; `appears_to_know` só `player_observation` perception/suspicion; allowlist `extra=forbid` + `FORBIDDEN_KEYS`. |
| Bestiário: chaves acima do tier | **DEFEITO corrigido** — `build_dossiers` omitia as chaves, mas a rota fazia `model_dump()` e o JSON saía com `description/type/max_hp/defense/attacks/behavior/loot/revealed_*: null` (viola R6 "ausência de chave"). Agora `model_dump(exclude_unset=True)`; testes `test_api_json_criatura_tier1_*`/`tier2_*` falhavam antes. |
| Cartas/resistências reveladas | **DEFEITO corrigido** — `_revealed_for` lia `bestiary_knowledge._load_all()` no escopo do dono LEGADO também em perfis com banco, onde esse escopo é compartilhado entre contas (um jogador veria o que outro revelou). Fora de `legacy` o dossiê agora não revela nada do overlay (não há escritor de produção por dono/jogo hoje). Teste `test_perfil_com_banco_nao_le_overlay_legado_compartilhado`. Tier ≥2 e exclusão de `variant_exclusive_cards` mantidas. |
| Tier 4 `behavior`/`loot` | Conforme R6/§3.2 (`behavior?/loot? (tier>=4)`, limiares de `BESTIARY_TIERS` inalterados). `behavior` (perfil tático) trafega mas não é renderizado — igual ao `/game/codex` existente. |
| Cross-owner (perfis DB) | OK — mesmo caminho de `/game/codex`: `load_game_state` escopado por `current_principal()`; 404 sem save; `Cache-Control: private, no-store` (+ middleware SPEC-221). GET sem CSRF (n/a). |
| Perfil legacy | Sem auth por design (SPEC-218 trata o default); sem regressão. |
| Fallback legado de Pessoas | Sem regressão e com melhoria (`_npcs_block` agora omite NPC de entidade hidden/secret não revelada). **Follow-up (pré-existente, fora do escopo):** o `GameResponse.npcs` ainda traz `last_memory` = `memory[-1]` bruto e `known_by_player` ausente conta como conhecido; o fallback do HUD renderiza isso. Recomendo spec curta para trocar `last_memory` por nota com proveniência (SPEC-206) quando a F07 migrar para o dossiê. |
| DOM (`title`/`data-*`/`aria-label`) | OK — só dados já visíveis (rótulo de certeza, tier_name, id/título de dossiê exibido). |
| XSS | OK — corpos via `mdLite` (escapa `&<>`) só em conteúdo de elemento; `fact`/`description` como texto. |

## 3. A11y / animação
- Nenhum `role="status"` em UI sempre montada; certeza tem texto ("Fato confirmado"...), não só cor.
- Teclado: setas/Home/End na lista, Enter (botão nativo), Esc volta sem fechar o painel; foco devolvido à linha.
- axe WCAG 2 A/AA (painel de contexto, save realista): **0 serious/critical** em split 50% e painel inteiro.
- R8/R9 (SPEC-208): `tabs.css` sem animação própria; chegada reaproveita `ArrivalLi`/`codex.entry.reveal`.

## 4. Evidência executada
- Save realista: API legacy real (`uvicorn` :8197, MockLLM), personagem nível 3 + 6 turnos (NPC + combate);
  dump `docs/spec211/evidence/dossiers_realistic_save.json` com `assert_no_private_fields == []` e
  `assert_no_player_leak == []`; capturas `split50-1440-codex-npc.png`, `full-1440-bestiario.png`,
  `full-1440-bestiario-after-reload.png` (dossiê aberto sobrevive a reload; combate ativo reabre na
  aba Combate por design da SPEC-204).
- Playwright completo (`--workers=1`, config temporária :4197, removida): ver §5.
- `uv run pytest` completo (sem pipe): exit 0 — 3289 passed, 184 skipped (sem `test_project_index`).
- `npm test` 107/107; `npm run build` verde; Ruff verde; `validate_content` 0 erros/0 avisos.

## 5. Playwright completo
**189 passed, 29 skipped, 3 failed** (221, chromium + chromium-motion, 22 min). As 3 falhas são as instáveis já conhecidas e alheias à SPEC-211: `account-lifecycle` (2, polling SPEC-190) e `voice-input` MediaRecorder nativo (SPEC-187). `dossiers.spec.ts`, `workspace-shell`, `critical-journeys` (F07 incluída) e `effects` (incl. `codex.entry.reveal` nos 2 projetos) verdes.

## 6. Observações não bloqueantes
- Codex mostra "Pessoas" (seção 204) e "Personagens (n)" (categoria) lado a lado — duplicação herdada da
  SPEC-204; consolidar quando F07 migrar para o dossiê.
- `encounters[]` parcial (primeiro contato + eventos canônicos públicos), sem `encounter_id` de combate por
  NPC — desvio documentado; refetch de URL assinada (R9) n/a para arte curada estática.
- Nome de NPC como chave do índice (`_npc_index`): dois NPCs homônimos compartilhariam relação/turnos;
  improvável, sem impacto de vazamento observado (ambos precisam ter passado pela projeção).
