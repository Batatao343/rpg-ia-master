# SPEC-376 — Etapa 0: deriva dos geradores (medida em 04/11, sobre `git archive main data`)

Procedimento (R5): diretório temporário fora de qualquer repo, `data/` copiado do `main`, cópias dos
scripts, `RPG_ROOT="$PWD"`, `python -I` do venv do checkout principal (sem `py.sh`/`uv run`). Snapshot
`git status --porcelain -- data/ scripts/` do checkout principal antes e depois: vazio nos dois. O
diretório temporário foi apagado ao fim. Contagens por item/campo vêm de um comparador JSON (`data.orig` x `data`).

## Medições (i), cada gerador sozinho

- **gen_cards_v4.py** (153 Cartas autorais): em `devoto/sangromante/corruptor/arcanista/medico.json`
  remove `tier`, `momento`, `level_req`, `raridade`, `apex` de **todas** as Cartas (30/31 por arquivo) e
  `reacao_inicial` (1, Corruptor); arquivos encolhem ~20 %. `virtude_sugeridas.json` muda de tamanho
  (1472 -> 1536 bytes), sem item novo.
- **gen_classes_v2.py** (grava ao ser importado): `classes.json` perde `late_entropy_curve` (5) e tem
  `branches` alterado (5); **recria `data/player_abilities.json`** (65 KB, removido da `main`).
- **gen_tiers_5_plus.py** (default `--check`): "mudaria" `basicas.json` e `tiers_5_plus.json` (deriva
  pré-existente, R12/fora de escopo). Nada gravado.
- **migrate_bestiary_v4.py** (sobrescreve): `bestiary.json` 373 criaturas, `virtudes` 246, `tactical_profile`
  286, `cartas` 285, `vitalidade`/`max_vitalidade`/`ferimento_espacos` 75, `resistances` 17, `immunities` 9;
  remove `appearance`/`substitui_generico` (3) e altera nome/descrição/ataques (3). `cards/bestiario.json`
  perde `momento` e `raridade` (40/40). **Destrutivo** (apaga curadoria das SPEC-335/349).

## Cadeia (ii): gen_classes_v2 -> gen_cards_v4 -> gen_tiers_5_plus --write

- `classes.json`: sem diferença (o `--write` devolve `late_entropy_curve` e o resto "da cadeia").
- 5 JSON de classe: a cadeia devolve `tier`, `level_req`, `apex`, mas **continua removendo os campos
  curados fora da cadeia**: `momento` (30/31 por arquivo, 153 no total), `raridade` (153) e
  `reacao_inicial` (1, Corruptor). Nenhuma Carta a mais ou a menos.
- `basicas.json` e `tiers_5_plus.json` mudam de tamanho/conteúdo (relatório do `--check`), `virtude_sugeridas.json`
  muda (+64 bytes).
- **Recria `data/player_abilities.json`** (65 KB; ausente na `main`).
- Testes que ficariam vermelhos (por leitura): `tests/test_cutover_audit.py:78` (arquivo recriado) e as
  asserções de `momento`/`raridade` em `tests/test_conflito_autoria_cartas.py`.

## Veredito (R6)

| Gerador | Veredito | Motivo |
|---|---|---|
| `gen_cards_v4.py` | **sai** (D1=a) | cadeia remove `momento`/`raridade`/`reacao_inicial` |
| `gen_classes_v2.py` | **sai** (D1=a) | cadeia recria `player_abilities.json`; sozinho remove `late_entropy_curve` |
| `gen_tiers_5_plus.py` | fica (R12) | `--check` seguro por default |
| `migrate_bestiary_v4.py` | fica, `--write` obrigatório (D3) | destrutivo comprovado (curadoria 335/349) |
