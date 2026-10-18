# SPEC-265 — Remover o recurso legado mana/stamina do jogador

> **Status:** `done` (revisão Sol APPROVED, [handoff](../handoffs/SPEC-265-SOL-review.md)) · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (tokens CSS, fixtures e2e, `mana_bonus`, fallback do HUD; ver §8)
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

- **R1** — Remover os campos de mana/stamina do jogador em `state.py` (`PlayerStats`, linhas
  128-131; **não** em `EnemyStats`:194-195), `world_utils.apply_rest`, na view da API, em
  `types.ts`, no HUD (barras, `kind`, regras `.bar[data-kind=...]`) e nos invariantes do playtest.
  - **R1a** *(revisão)* — **Manter os tokens `--mana`/`--stamina`** em `web/src/styles.css:40-41`:
    `web/tests/design.test.mjs:54-60` ("tokens legados não foram renomeados nem removidos") falha se
    eles saírem. Remover só as regras `.bar[data-kind="mana"|"stamina"]` (`:520-521`). Apagar o
    token exige editar esse guard de design de propósito, fora desta spec.
  - **R1b** *(revisão)* — `web/e2e/fixtures.ts:19` monta `player_stats` com `mana/max_mana/stamina/
    max_stamina` num literal tipado `GameResponse`; com o tipo encolhido o `tsc`/Playwright acusa
    propriedade excedente. Tirar as 4 chaves da fixture.
  - **R1c** *(revisão)* — HUD: hoje, com `max_entropy == 0`, o ramo `else` desenha Mana/Vigor 0/0.
    Definir o novo comportamento explicitamente (proposta: desenhar a barra de Entropia 0/0, sem
    ramo) e cobrir com teste de componente; não deixar o HUD sem barra de recurso.
  - **R1d** *(revisão)* — `invariants.bounds()` também roda para party e inimigos. Hoje nenhum
    deles tem `max_mana`/`max_stamina` (bestiário tem só `mana`/`stamina`, sem teto; grep em
    `party.py`, `services/`, `agents/` vazio), então tirar as tuplas não perde cobertura. Registrar
    o grep no PR.
- **R2** — **Não tocar** em `persistence._MIGRATIONS`: as migrações v0→v4 que leem/apagam
  mana/stamina continuam iguais (save antigo precisa migrar).
- **R3** — Não tocar em mana/stamina de **inimigos** se algum dado/bestiário ainda usar
  (verificar com `git grep -n "mana\|stamina" services/ data/bestiary.json`, só grep).
- **R4** — `CreateScreen.tsx:37-38` (`mana_bonus` → "Mana", `stamina_bonus` → "Vigor") **ficam**:
  `data/origins.json:31,37,88` ainda declara `mana_bonus: 10` e `stamina_bonus: 5`. Que esses
  bônus de origem não fazem nada no motor v4 é um achado à parte (spec de conteúdo de origens),
  fora desta poda.
- **R5** — Testes: apagar as fixtures inertes de mana/stamina **do jogador** em `tests/test_fase0.py:70-79,114`,
  `test_mvp.py:38-39,159-165,260`, `test_fase2.py:111`, `test_fase32.py:36,53`, `test_fase43.py:18,180`.
  **Manter** `test_mvp.py:166` (garante que `mana` não volta à ficha) e
  `test_classes_refactor.py:77-79,135-136` (asserts de ausência).
  *(revisão)* A lista original omite ~10 arquivos com mana/stamina em fixtures: `test_aliados_combate`,
  `test_bug_contabilidade_recompensas`, `test_classes_refactor:335`, `test_combat_lifecycle`,
  `test_contracts_llm`, `test_fase64`, `test_fase65`, `test_fixes_playtest`, `test_polish_sessao`,
  `test_routing_tiers`. Muitas dessas chaves são de **inimigo** (`"stamina": 0, "mana": 0, "attack_mod"`)
  e devem ficar (R3). Dicts de jogador com chave extra não quebram nada: limpar é opcional.

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

- [ ] `git grep -n "max_mana\|max_stamina"` só encontra migrações, testes de ausência, fixtures
      opcionais de teste e docs
- [ ] `cd web && npm test` verde **sem** editar `design.test.mjs` (tokens preservados, R1a)
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

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

Verificado: nenhum consumidor de `mana/max_mana/stamina/max_stamina` do jogador em `evals/`
(datasets, adapters, registry, locks), `scripts/` (fora do gerador de classes) nem em `web/android`;
o app Android usa o mesmo bundle e só desenha Mana/Vigor quando `max_entropy == 0`. `persistence._MIGRATIONS`
fica intacto (R2). `combat_mechanics` não lê mana do jogador (o único hit é o nome de trigger `hp_as_mana`).

Achados que mudaram a spec:
1. `web/tests/design.test.mjs:54-60` trava os tokens `--mana`/`--stamina`: removê-los quebra `npm test` → R1a.
2. `web/e2e/fixtures.ts:19` tem as 4 chaves num literal `GameResponse`: excesso de propriedade após o
   encolhimento do tipo → R1b.
3. O HUD hoje cai para Mana/Vigor 0/0 quando `max_entropy` é 0; a spec não dizia o que fica no lugar → R1c.
4. `data/origins.json` tem `mana_bonus` **e** `stamina_bonus`: os dois chips do `CreateScreen` ficam (R4 corrigido).
5. `EnemyStats` (`state.py:194-195`) e 19 criaturas do bestiário mantêm `mana`/`stamina`; a lista de
   fixtures de teste do R5 omitia ~10 arquivos, a maioria com chaves de inimigo que devem ficar.

## 9. Execução 2026-10-18

Implementado (R1–R5 revisados): removidos `max_mana/max_stamina` e `mana/stamina` do jogador em `state.py` (`EnemyStats` intacto), `world_utils.apply_rest`, view `/game/state` (`format_response`: perde `mana`, `max_mana`, `stamina`, `max_stamina`, sempre 0), `playtest/invariants.bounds`, `web/src/types.ts`, HUD (R1c: sempre desenha a barra de Entropia, 0/0 se não houver; o chip de Carga segue gated por `max_entropy>0`), regras CSS `.bar[data-kind=mana|stamina]`, fixture `web/e2e/fixtures.ts`. Mantidos: tokens `--mana/--stamina` (R1a), `persistence._MIGRATIONS` (R2), inimigos/bestiário (R3), chips `mana_bonus/stamina_bonus` da criação (R4). Testes: `test_fase0` ajustado; `test_cards_prepare_api` assevera a ausência das 4 chaves na view; demais fixtures de jogador com chaves extras ficam (opcional). Nenhum arquivo protegido de eval editado (nenhum dataset/jornada cita mana).

Verificado: pytest completo, ruff, `npm test` 126/126, `npm run build`, Playwright chromium (critical-journeys F01–F35 incl. HUD, deck-character, combat-gesture, workspace-shell). **Status `in-progress`**: REVIEW_REQUIRED (Astra/Sol) pendente; mudança de contrato da API documentada acima; falta teste de componente do HUD 0/0 (sem harness de componente — coberto só por tsc/e2e) e smoke manual 390/1440 px.
