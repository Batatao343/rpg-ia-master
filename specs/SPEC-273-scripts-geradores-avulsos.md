# SPEC-273 — Aposentar geradores de uso único e unir os leitores de .env dos scripts

> **Status:** `draft` — **NÃO RECOMENDADA (decisão do dono 2026-10-18: não executar)**. Revisão independente 2026-10-18: UNSAFE — os dois geradores são passos obrigatórios da pipeline de autoria (ver §8).
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

- `scripts/gen_world_living_npcs.py` (186 linhas, último commit 2026-08-11) escreveu os
  36 NPCs da conflito-17, hoje curados em `data/codex` e no grafo.
- `scripts/gen_tiers_5_plus.py` (148 linhas, 2026-08-20) gerou as 80 Cartas tardias em `data/cards`.

Nenhum dos dois tem teste, CI, guia ou referência em CLAUDE/AGENTS; o único hit é uma
lista em `docs/descricao_projeto/fontes/exploracao/explore_06_qualidade.md`.
Diferente deles, `gen_classes_v2.py`, `gen_cards_v4.py`, `migrate_lore_nova.py`,
`migrate_bestiary_v4.py` e `import_visual_assets.py` são fonte documentada ou têm teste: ficam.

Também há dois leitores de `.env` escritos à mão: `_dotenv()` em
`scripts/release/checklist.py:340` e `load_env()` em `scripts/staging/s192.py:26`.
O projeto já depende de `python-dotenv`.

## 2. Requisitos

- **R1** — Confirmar que os dados gerados não são regerados por esses scripts: rodar cada
  um em diretório temporário (sem gravar no repo) **ou** checar se o docstring diz que é a
  fonte de verdade. Se algum for fonte de verdade, ele fica e vai para `docs/guias/AUTORIA.md`.
- **R2** — *(revisado)* **Nenhum dos dois sai.** Ambos são fonte (ver §8). Em vez de `git rm`,
  documentar a ordem da pipeline em `docs/guias/AUTORIA.md`:
  `gen_classes_v2.py` → `gen_cards_v4.py` → `gen_tiers_5_plus.py`; e `migrate_lore_nova.py` →
  `gen_world_living_npcs.py`.
- **R3** — *(revisado)* Premissa falsa: os dois leitores **já usam** `dotenv.dotenv_values`
  (`scripts/staging/s192.py:27-31`, `scripts/release/checklist.py:340-345`). O que existe é a mesma
  função de 5 linhas (merge `.env` + `.env.staging`, ignora vazio) duplicada. Opcional: mover para
  `scripts/staging/common.py` (que `s192.py` já importa) e importar de lá no checklist. Ganho ~5 linhas.

### Fora de escopo

`scripts/staging/*` de runbook (incident_drill, security_wave_smoke, voice_smoke…): são
ferramentas de operação citadas por runbooks da SPEC-197. Avaliar à parte com quem opera.

## 5. Critérios de aceite

- [ ] `uv run pytest` verde (inclui os testes de scripts de staging)
- [ ] `uv run python scripts/validate_content.py` sem erro
- [ ] `uv run python scripts/release/checklist.py --help` e `s192.py --help` funcionam

## 7. Riscos & compatibilidade

Risco **baixo**: perder a receita de geração. O histórico git guarda o script. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: UNSAFE as written — não recomendado apagar os geradores.**

Achados:
1. **`gen_tiers_5_plus.py` é passo obrigatório depois de `gen_classes_v2.py`/`gen_cards_v4.py`.** Ele
   pós-processa `data/classes.json` (`late_entropy_curve`, `branches.*.playstyle/tradeoff/preview_card_ids`)
   e carimba `tier/level_req/apex` em todas as Cartas de `data/cards/*.json` (`:103-144`). Nenhum dos
   geradores documentados no CLAUDE.md emite esses campos (`grep` = 0), e o runtime os lê
   (`progression.py:67,73,219`; `web/src/types.ts:55`). Rodar o caminho de autoria documentado sem ele
   quebra o nível 9–20 e os previews de subclasse. Docstring: "Autoria reproduzível".
2. **`gen_world_living_npcs.py` é passo obrigatório depois de `migrate_lore_nova.py`.** As 36 entidades
   `npc_mv_*` vivem só em `data/graph/entities.json` (72 hits; 0 em `entities_extra.json`), e o
   `migrate_lore_nova.py` "REGERA ... `entities.json` do zero" a partir de `lore_nova/`. Os `.md` sobrevivem
   (`curated: true`), mas as entidades somem do grafo até rodar o gerador de novo.
3. R3 partia de premissa falsa: `checklist.py:340` e `s192.py:26` já usam `dotenv.dotenv_values`.

Recomendação: trocar a spec por "documentar a ordem da pipeline em `docs/guias/AUTORIA.md`" (R2 revisado)
e, opcionalmente, deduplicar o leitor de `.env` em `scripts/staging/common.py`.
