# SPEC-NNN — Bestiário de Valoria, onda <N>: <Região>

> Spec-filha da SPEC-349 (esteira do bestiário). Referencia §3 da 349 e `docs/guias/BESTIARIO.md`;
> preenche só o variável. Autor de prosa: **Opus** (Fable só por pedido explícito do dono).
> Uma onda = uma spec (D8). Status: `draft`.

## 1. Região e habitat

- `region_id`: `<regiao>` · onda <N> · ordem D9 da 349.
- Nós de habitat (com `region_id == <regiao>` em `data/world_map.json`): `<no1>`, `<no2>`, ... Cada nó tem >= 5 criaturas.
- Âncoras de lore (arquivo:linha, verificadas no source): `lore_nova/<arq>.txt:<n>`, ...

## 2. Demônios da onda

- Obrigatório de lugar fixo (se houver): `npc_<demonio>` (`lore_nova/npcs.txt:<n>`).
- Demônios da onda (crias de anatomias diferentes entre regiões, R29): `npc_<x>`, `npc_<y>`, ...
- Nenhuma cria revela o pacto de Valerius (SPEC-348 R16-R18) nem é o demônio em si (P7).

## 3. Slots genéricos (tirados de `curadoria_legado.yaml`)

| Id do slot | Destino | Conceito |
|---|---|---|
| `enemy_...` | reinventar / adotar | ... |

## 4. Cotas (D12) e ajustes justificados

20-25 novas; >= 4 por família; lacaio >= 6, padrão >= 6, elite >= 4, chefe 1-2; >= 8 papéis e >= 7 arquétipos.
Ajuste de cota (justificar): ...

## 5. Etapas

1. Tabuleiro (`vagas:`) verde em `scripts/bestiario/lint.py --vagas`.
2. Conceitos 2× em `docs/spec349/conceitos-<regiao>.md`.
3. Fichas + docs (`gerar_docs.py`) + revisão de unicidade em `handoffs/SPEC-349-independent-review.md`.
4. Mecânica (`data/bestiario/mecanica/<regiao>.yaml`, `gerar_mecanica.py`) e `fases` dos chefes.
5. Arena (`calibrar.py`, `arena.py --regiao <regiao>`): 45-85 % em `off` e `on`; slots com |delta| <= 8 pp.
6. Rumores (`scripts/build_rumor_seeds.py`), `validate_content.py` com 0 ERRO, `painel.py`, `_esteira.yaml`.

## 6. Smoke real (<= 5 requests) e arena

- Jogo novo em `<nó>`, ação "ataco o/a `<criatura nova>`": spawn resolve no id novo.
- `RPG_ENEMY_DECKS=on`, 3 rodadas: o telegrafo vem 1 rodada antes e a assinatura é jogada.
- Relatório da arena: `docs/spec349/arena-<regiao>.md`.
