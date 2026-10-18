# SPEC-265 — Remover o recurso legado mana/stamina do jogador

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Astra` (≡ Opus) · **REVIEW_REQUIRED:** `true` — muda o shape da resposta da API e o HUD
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A refatoração de classes (SPEC-048) trocou mana+stamina do jogador por **Entropia**. A
conflito-01 levou o save para v4 e arquivou as fichas antigas. O resto do caminho
mana/stamina continua vivo de ponta a ponta, só que nunca recebe valor:

- `state.py:129-131`: `max_mana`/`max_stamina` em `PlayerStats`
- `world_utils.py:290-294`: o descanso recompõe `mana`/`stamina` se a chave existir
- `api.py:1520-1523`: a view do jogador devolve `mana/max_mana/stamina/max_stamina` (sempre 0)
- `web/src/types.ts:76-78`, `web/src/components/Hud.tsx:40-46` (barras "Mana"/"Vigor"
  "para saves antigos sem Entropia"), `Hud.tsx:496` (tipo `kind`), `web/src/styles.css:41,521`
- `playtest/invariants.py:48-49`: checa limites de mana/stamina

Saves pré-v4 não carregam como jogo ativo (archive). As barras legadas nunca aparecem.

## 2. Requisitos

- **R1** — Remover os campos de mana/stamina do jogador em `state.py`, `world_utils.apply_rest`,
  na view da API, em `types.ts`, no HUD (barras, `kind`, CSS) e nos invariantes do playtest.
- **R2** — **Não tocar** em `persistence._MIGRATIONS`: as migrações v0→v4 que leem/apagam
  mana/stamina continuam iguais (save antigo precisa migrar).
- **R3** — Não tocar em mana/stamina de **inimigos** se algum dado/bestiário ainda usar
  (verificar com `git grep -n "mana\|stamina" services/ data/bestiary.json`, só grep).
- **R4** — `CreateScreen.tsx:38` (`stamina_bonus` → "Vigor") só sai se `data/origins.json`
  não tiver mais `stamina_bonus` (grep); senão fica.
- **R5** — Testes: apagar as fixtures inertes de mana/stamina em `tests/test_fase0.py:70-79,114`,
  `test_mvp.py:38-39,159-165,260`, `test_fase2.py:111`, `test_fase32.py:36,53`, `test_fase43.py:18,180`.
  **Manter** `test_mvp.py:166` (garante que `mana` não volta à ficha).

### Fora de escopo

Mudar o schema do save (sem bump de `SCHEMA_VERSION`); mudar Entropia/Carga.

## 3. Design técnico

Só remoção. A resposta de `/game/state` perde 4 chaves que sempre valiam 0. O cliente
web é o único consumidor (o app Android usa o mesmo bundle).

## 4. Plano passo a passo

1. **Testes:** ajustar as fixtures (R5); acrescentar a `test_mvp.py` uma assert de que a view
   da API não tem `max_mana`.
2. **Implementação:** R1 na ordem backend → playtest → web.
3. **Verificação:** suíte + build web + e2e.

## 5. Critérios de aceite

- [ ] `git grep -n "max_mana\|max_stamina"` só encontra migrações, testes de ausência e docs
- [ ] `uv run pytest` verde
- [ ] `cd web && npm test && npm run build` verdes; Playwright `npm run test:e2e` verde
- [ ] Jornadas F01–F24 do frontend eval (`scripts/frontend_eval_report.py --check`) verdes;
      a régua de evals não é editada (se algum dataset citar mana, parar e pedir autoria)
- [ ] Um save v4 real carrega e mostra o HUD só com Vitalidade/Entropia/Carga

## 6. Smoke

`uv run uvicorn api:app` com MockLLM: criar personagem, descansar, conferir o HUD em 390 px e 1440 px.

## 7. Riscos & compatibilidade

Risco **médio**: muda o contrato JSON. Um cliente Android antigo instalado ignora chave
ausente (`?? 0`). Rollback: `git revert` (sem migração de dados envolvida).
