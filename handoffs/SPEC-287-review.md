# SPEC-287 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (subagente independente, não escreveu o código) · **Data:** 2026-10-19 · **Commit revisado:** `9c5e248` (sobre `main` `3bf6cb3`)

## Escopo

Branch `spec-287`, `git diff 3bf6cb3..9c5e248`: `encounter_budget.py`
(`ACTION_ECONOMY_STEP`, `action_economy_multiplier`, `floor_cost`, `fill_encounter`),
`agents/bestiary.py` (`apply_encounter_survival`, `_ready_v4`),
`scripts/migrate_bestiary_v4.py` + `data/bestiary.json` (13 criaturas com
`vitalidade_por_nivel_encontro`), `docs/spec285/arena_lethality.py` (seed global por
luta, `group_size` via `floor_cost`), `tests/test_spec287_encounter_scale.py`, spec e
`docs/spec287/README.md`. Fora: reexecução completa da arena de 10 seeds e dos
playtests (aceitos pela tabela do executor; reprodutibilidade conferida por amostra) e
a suíte completa (rodando em paralelo pelo coordenador).

## Verificação dos pontos pedidos

1. **`floor_cost`/`fill_encounter`** — correto. Chefe/Nomeado ficam fora da contagem
   de corpos e entram pelo custo linear (`encounter_budget.py:43-53`); o loop recalcula
   `spent = floor_cost(kept)` a cada reforço (`:149`), o teto de 4 reforços (`i < 4`) e a
   assinatura pública não mudaram. Em `agents/combat.py:377-393` a ordem continua
   clamp (linear) → fill; `report["cut_ids"]`/`joined_ids` (SPEC-203) são calculados
   pelos mesmos ids de antes, então o relatório de composição não muda de semântica.
2. **R2 é verdadeira, inclusive para composições mistas.** Com passo ≥ 0,
   `floor_cost ≥ soma linear` (multiplicador ≥ 1) e ambos crescem a cada corpo. Com 0 ou
   1 corpo não-chefe os dois custos são iguais; com ≥ 2 corpos a soma linear já é ≥ 4
   (custo mínimo 2), logo ≥ qualquer piso ≤ 4; com Chefe presente, 12 ≥ piso. Ex.:
   1 Padrão + reforço Lacaio = linear 5 / novo 11,25, os dois param. Portanto piso ≤ 4
   dá o mesmo número de corpos, e acima disso nunca mais corpos (o reforço é a mesma
   sequência determinística de `pick_encounter_enemy`). Conferido também
   numericamente: `group_size` da arena antes/depois idêntico nos níveis 1–4 e
   3/3/4/5 → 2 Lacaios nos níveis 5–8.
3. **`apply_encounter_survival`** — não muta o bestiário: `dict(db[...])` é cópia rasa,
   mas o helper só reescreve chaves de topo (`max_vitalidade`; `_ready_v4` grava
   `vitalidade/hp/max_hp/status`), e o teste confere `db[bid]` intacto. O Nível do
   Encontro vem de `prep.compute_encounter_level` (perigo do local/região, absoluto;
   `agents/combat.py:240`), nunca do nível da party. Caminhos de instância de Chefe:
   `template_by_id` (fonte canônica/encontro sistêmico com `enemy_id`) e cache-hit de
   `generate_new_enemy` (scanner) cobertos. Não cobertos: ver P2-1 e P2-2.
4. **Gerador idempotente**: `scripts/migrate_bestiary_v4.py` reexecutado → `data/bestiary.json`
   sem diff; só `data/cards/bestiario.json` apareceu modificado e era exclusivamente
   CRLF (`git diff --ignore-cr-at-eol --quiet` ok), restaurado. Lint de conteúdo
   `0 ERRO(S) · 0 AVISO(S)`.
5. **Arena**: `random.seed(str)` por luta (seed de `str` usa sha512, independe de
   `PYTHONHASHSEED`) só fixa o `random` global que o motor ainda consome; o `rng`
   explícito da luta segue `random.Random(seed)`. Duas execuções idênticas
   (`1 --levels 8 --bots cartas --categories lacaio,chefe`) deram 0,253/0,508 nas duas.
   `getattr(eb, "floor_cost", None)` cai na regra linear em commits antigos — ok.
6. **Desvio da §2** (Chefe fora do topo): bem sustentado — a cadeia já é falsa nos
   níveis 1–4, que não podem piorar (E4/M4); as sondas mostram que nem +36 Vit (0,49)
   nem duas ações (0,42) alcançam dois Elites (0,67–0,70). A decisão foi do
   coordenador sob a autorização do dono e ficou explicitamente fora de escopo; ver P2-4.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `agents/combat.py:386-388`; `world_utils.py:763` | O reforço do piso instancia a entrada crua do bestiário (`{**t, "id": ...}`) sem `apply_encounter_survival`. E o pool de `pick_encounter_enemy` exclui chefe por `"BOSS" in type`, não por categoria: `enemy_aranha_de_cristal` (chefe, `deserto_zhur`) e `enemy_garrick,_o_silenciador` (nomeado, `nova_arcadia`) saem como reforço em perigo 1–3 (confirmado por sondagem). Preexistente, mas agora também inconsistente com o R4 (no perigo 3 o Chefe-reforço perde +12 Vit). | Follow-up: filtrar o pool por `normalize_categoria(e) not in {"chefe","nomeado"}` (preferível — Chefe não deveria ser reforço) e/ou passar o `make_instance` por `apply_encounter_survival`. |
| P2-2 | P2 | `agents/bestiary.py:96-146`, `:327`; `api.py:3216` | Chefe gerado pela LLM (`materialize_enemy_concept`) não tem o campo e não ganha sobrevivência; o laboratório de combate copia `gamedata.BESTIARY` direto e usa a ficha base. Está dentro do escopo declarado no R4 (só `template_by_id` e cache-hit), mas cria assimetria entre Chefe curado e gerado. | Registrar; decidir em spec futura se `materialize_enemy_concept` com categoria chefe/nomeado grava o campo. Laboratório pode ficar como está (não tem Nível do Encontro). |
| P2-3 | P2 | `agents/bestiary.py:234-247` | Bônus sem teto: `ENCOUNTER_LEVEL_MAX = 10` daria +96 Vit. Hoje inalcançável (nenhum código de produção seta `world.encounter_type`, então o nível fica ≤ perigo 4 → ≤ +24). | Quando `encounter_type`/importância forem ligados, rever o `[BALANCEAR]` ou limitar os passos. |
| P2-4 | P2 | `specs/SPEC-287-encontros-escala-nivel-5-plus.md` §2 | A ordem `… < Chefe` pedida pelo dono foi trocada por decisão do coordenador. Justificativa sólida, mas é design. | Levar ao dono no ESTADO/ROADMAP como decisão a ratificar (séquito ou economia de ações do Chefe = spec própria). |
| P2-5 | P2 | `tests/test_spec287_encounter_scale.py:16-29` | Os testes de piso usam só reforço da mesma categoria; o caso misto (ex.: 1 Padrão inicial + reforços Lacaio) só está provado analiticamente acima. | Opcional: um caso parametrizado misto contra a regra linear. |

Sem P0/P1. Sem structured output novo, sem valor de LLM consumido, sem segredo em log,
sem toque em `evals/` protegido, sem schema/bump de save.

## Correções aplicadas

Nenhuma (revisão sem achados bloqueantes).

## Pendências

- P2-1 (reforço Chefe/sobrevivência) → follow-up de balanceamento (SPEC-049 ou spec nova).
- P2-4 → ratificação do dono.
- P2-2/P2-3/P2-5 → registrar; sem urgência.

## Comandos rodados

```text
git diff 3bf6cb3..HEAD --stat → 8 arquivos, +586/-81
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -o addopts="" -q tests/test_spec287_encounter_scale.py tests/test_encounter_manifest.py tests/test_encounter_identity_repro.py tests/test_letalidade_early.py tests/test_spec285_lethality.py → 166 passed
bash scripts/dev/py.sh scripts/migrate_bestiary_v4.py → bestiary.json sem diff; cards/bestiario.json só CRLF (restaurado)
bash scripts/dev/py.sh scripts/validate_content.py → 0 erros, 0 avisos
group_size antes/depois (script ad hoc) → níveis 1–4 idênticos; 5–8 Lacaio 3/3/4/5 → 2
pick_encounter_enemy sondado (nova_arcadia/deserto_zhur, perigo 1–4, 60 turnos) → garrick/aranha_de_cristal saem em perigo 1–3
arena_lethality.py 1 --levels 8 --bots cartas --categories lacaio,chefe (2×) → 0,253/0,508 idênticos
```
