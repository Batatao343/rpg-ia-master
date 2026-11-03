# SPEC-374 — dry-run do `migrate_lore_nova.py` (R16)

Rodado numa **cópia** temporária (`lore_nova/`, `data/codex`, `data/graph`, `data/codex_overrides.yaml`),
com o cwd na cópia; nunca no worktree. Mesmo procedimento do teste
`tests/test_spec374_migrate.py::test_migrate_nao_apaga_curados`.

## Antes da correção (estado herdado da 366)

- `.md` apagados e não regerados: **17** — os 14 `npcs/segredos/npc_tr_*_segredo.md` (SPEC-350 R10)
  e os 3 `npcs/segredos/npc_mv_{irena_prego_frio,mara_do_setimo_sino,teo_chamine}_segredo.md`.
  Eram escritos à mão (não saem de `lore_nova/`) e não tinham `curated: true`. A hipótese [H] da spec
  se confirmou: a lista bate exatamente.
- Ids que saíam de `entities.json`: **36**, todos `npc_mv_*` (NPCs do mundo vivo, docs públicos
  curados em `data/codex/npcs/mundo_vivo/`, que não vêm de `lore_nova/`). Os `npc_tr_*` já estavam em
  `entities_extra.json`.
- `entities.json` 603 -> 567 ids; `entities_extra.json` 348 ids.

## Correção aplicada

1. `curated: true` no frontmatter dos 17 docs de segredo acima (lista do dry-run, não glob).
2. Os 36 `npc_mv_*` saem de `entities.json` e vão para `entities_extra.json` (mesmo shape; é o que o
   migrate produziria). `entities.json` 567, `entities_extra.json` 384.
3. Regra nova no validador (`validate_curated_secrets`): `npc_secret` cujo `related_entities` aponta
   para entidade só de `entities_extra.json` sem `curated: true` = ERRO.
4. `docs/guias/AUTORIA.md` (Fluxo A): o doc de segredo de entidade curada também leva `curated: true`.

## Depois da correção (mesma cópia)

- `.md` antes 1056 / depois 1056; sumiram 0; novos 0.
- ids de `entities.json` antes 567 / depois 567; sumiram 0; novos 0.
- Rodar 2x seguidas não muda nenhum byte (`test_migrate_idempotente`).
- `validate_content.py`: 0 ERRO(S).

O migrate real num worktree descartável (smoke §6.2) fica para o coordenador.
