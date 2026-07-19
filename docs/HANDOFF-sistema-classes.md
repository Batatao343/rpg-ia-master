# HANDOFF — Épico do Sistema de Classes (Cinco Posturas diante do Abismo)

> ✅ **ÉPICO 100% CONCLUÍDO em 2026-07-19** — as DUAS specs `done`:
> [refatoracao-sistema-classes](../specs/refatoracao-sistema-classes.md) (motor:
> 5 Posturas + Entropia/Carga; etapas 1–8) e
> [arvores-habilidade-classes](../specs/arvores-habilidade-classes.md) (árvore
> rica: 101 habilidades com passivas/utilitárias, autoria em Fable).
> 918 offline verdes + 2 smokes reais 4/4. Referência viva:
> [CLASSES.md](CLASSES.md) (mecânica) e [CLASSES_NARRATIVA.md](CLASSES_NARRATIVA.md).
> O texto abaixo é o plano original de retomada — registro histórico.
>
> Documento auto-contido (histórico) para retomar. Fonte da verdade do design:
> [specs/refatoracao-sistema-classes.md](../specs/refatoracao-sistema-classes.md)
> (motor/dados) e [specs/arvores-habilidade-classes.md](../specs/arvores-habilidade-classes.md)
> (árvore rica — passivas/utilitárias, autoria em **Fable**).
> Criado: 2026-07-18. Suíte no ponto de partida: **881 offline verdes**.

---

## TL;DR — onde parou

- **Etapa 1/8 `done` e commitada** (`c9d3da4`): recurso **Entropia** existe e
  funciona. `PlayerStats` tem `entropy`/`max_entropy`/`abyss_charge`;
  `combat_mechanics._resource_field("Entropia")→"entropy"` (o `spend_resources`
  já deduz); `world_utils.apply_rest` recompõe Entropia **integral** e não mexe
  na Carga. Testes: `tests/test_classes_refactor.py` (5).
- **Etapa 2/8 PRONTA mas NÃO aplicada**: o gerador `scripts/gen_classes_v2.py`
  produz `data/classes.json` + `data/player_abilities.json` das **5 classes ×
  3 subclasses + 41 habilidades**, com todos os blocos tipados
  (`entropy_trigger`/`special_rule`/`abyss`/`branches`/`level_gains`). Já foi
  rodado e **validado** (starting_abilities existem, branches casam). Foi
  **revertido do working tree** porque o rollout derruba 41 testes (ver abaixo).
- **Falta**: aplicar a Etapa 2 + migrar/reescrever os 41 testes + Etapas
  **3, 4, 6, 7, 8**. Etapa 5 (árvore RICA ~100 hab com passivas/utilitárias) é a
  **spec #2** e deve ser autorada em **Fable**.

Nada do épico está no working tree agora — a suíte está verde no estado da
Etapa 1. Retomar = rodar o gerador de novo e seguir o plano.

---

## Como retomar (comandos)

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"   # uv fora do PATH
cd "c:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master"
uv run pytest                                # confirmar 881 verdes (estado etapa 1)

# aplicar a Etapa 2 (gera classes.json + player_abilities.json das 5 Posturas):
$env:RPG_ROOT = "c:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master"
uv run python scripts/gen_classes_v2.py      # imprime "abilities: 41 | classes: 5 | validação OK"

uv run pytest -p no:cacheprovider            # verá ~41 falhas (inventário abaixo)
```

> **Gotchas do ambiente** (todos já conhecidos, ver ESTADO_ATUAL):
> - `uv` fica em `%APPDATA%\Python\Python314\Scripts` (fora do PATH).
> - `data/bestiary.json` e `data/npc_database.json` são cache runtime — a suíte/
>   smokes os sujam. **`git checkout -- data/bestiary.json data/npc_database.json`
>   antes de cada commit.**
> - `git add` mostra warnings LF→CRLF — benignos.
> - Smoke com LLM real: **autorizado** pelo usuário ("pode fazer em tudo").
>   DeepSeek é o primário; ~$0.03/smoke. RAG vivo (Jina no `.env`).
> - Suíte offline roda em ~15-25s; use `-p no:cacheprovider`.

---

## As 5 classes (resumo — detalhe em `scripts/gen_classes_v2.py` e §3.3 da spec)

| Classe | Papel · Postura | HP/Entropia/Def | Gatilho (`kind`) | Regra especial | Carga | Attr |
|---|---|---|---|---|---|---|
| **Devoto do Abismo** | tank · ama | 38/14/16 | `on_damage_taken` | taunt escala c/ Entropia | **insonia** | str |
| **Sangromante** | dano cac · negocia | 26/16/12 | `on_self_harm` | `blood_leak` (Entropia de sangue vaza) | **cicatriz** | dex |
| **Corruptor** | DoT · trabalha junto | 28/18/13 | `on_decay_nearby` | domínio define decadência | **transformacao** | wis |
| **Arcanista Cinzento** | dist · manipula | 22/20/11 | `on_channel` | `boiler` (estoura sem vazão) | **dependencia** | int |
| **Médico de Campo** | suporte · nega | 28/16/14 | `on_ally_suffer` | `heal_abyss` (reduz Carga alheia) | **recidiva** (oculta) | int |

`level_gains.entropy`: Devoto 2 · Sangromante 3 · Corruptor 4 · Arcanista 6 · Médico 3.
Branches (subclasses = branch derivado de `known_abilities`): Devoto
consagrado/zeloso/enlutado · Sangromante exposto/avaro/silencioso · Corruptor
biologia/alma/inorganica · Arcanista calibrado/descoberto/improvisador · Médico
cirurgiao_trincheira/boticario/cirurgiao_ferro.

---

## Inventário das 41 falhas do rollout (o que fazer com cada cluster)

Rodar `uv run python scripts/gen_classes_v2.py` e depois `pytest` produz:

| Arquivo | Falhas | Natureza | Ação |
|---|---|---|---|
| `test_fase42.py` | 14 | buffs/passivas tipadas 4.2 (hp_as_mana do Sangromante, party_active AC do Cavaleiro, etc.) | **REESCREVER** contra os gatilhos de Entropia + consequências de Carga (etapas 3/4). Passivas antigas não existem mais. |
| `test_fase41.py` | 7 | progressão/XP/árvore — ids de habilidade e branches antigos em fixtures | Atualizar fixtures p/ classes+habilidades novas |
| `test_fase41b.py` | 6 | árvores de Valoria (20 ramos antigos) | Reescrever p/ os 15 branches novos (5×3) OU arquivar (a árvore rica é spec #2/Fable) |
| `test_combat_heal.py` | 5 | habilidades de cura antigas | Apontar p/ `sutura_de_campo`/`intervencao_imediata` (Médico) |
| `test_polish_sessao.py` | 3 | `combat_suggestions` (chips) usa ids/recurso antigos | Fixture com habilidade nova (resource_type Entropia) |
| `test_onboarding.py` | 2 | anti-drift onboarding↔classes (onboarding.json tem 10 classes) | **Reescrever bloco `classes` de `onboarding.json` p/ as 5** (Etapa 2) |
| `test_mvp.py` · `test_fase51.py` · `test_fase45.py` · `test_balance_early.py` | 1 cada | nome de classe antigo incidental em fixture | Trocar por classe nova (ex.: "Devoto do Abismo") |

**Também precisam de atenção (não quebram, mas referenciam classe antiga):**
- `playtest/runner.py` — `_DEFAULT_CHAR["class_name"] = "Batedor das Fronteiras"`
  → trocar por uma das 5 (sugestão: **Arcanista Cinzento**, cobre dist/dano).
- `playtest/profiles.py` — conferir classes dos perfis.
- `combat_mechanics.py` — referências a passivas antigas (class_passives) por nome.

---

## Plano restante (segue o §4 da spec — TDD, testes primeiro)

- **Etapa 2 (dados) — aplicar:** rodar o gerador; reescrever `class_themes.json`
  e o bloco `classes` de `data/onboarding.json` p/ as 5 (o gerador NÃO faz esses
  dois); atualizar `character_creator.CLASS_ATTR_MAP` + preencher Entropia na
  ficha (`entropy`/`max_entropy` de `base_stats.entropy` escalando como HP;
  `abyss_charge=0`; mana/stamina→0). **Nota:** as edições de
  `character_creator.py` (CLASS_ATTR_MAP 5 classes + bloco de Entropia) foram
  feitas e revertidas nesta sessão — refazer (estão descritas em §3.8 da spec).
  Testes: `test_five_classes_load`, `test_each_class_three_branches`,
  `test_base_stats_have_entropy`, `test_onboarding_matches_classes`,
  `test_class_attr_map_covers_five`.
- **Etapa 3 (gatilhos + Carga):** `combat_mechanics.entropy_config`,
  `apply_entropy_trigger`, `abyss_tier` + pontos de acionamento no loop de
  combate (§3.4 da spec: on_damage_taken, on_self_harm, on_decay_nearby,
  on_channel, on_ally_suffer). Contador transitório `player["_entropy_trigger_turn"]`.
- **Etapa 4 (regras especiais + consequências):** taunt_scales / blood_leak /
  boiler / heal_abyss (§3.5) + Insônia/Cicatriz/Transformação/Dependência/
  Recidiva (§3.6) + `reduce_ally_abyss` (§3.7, só Médico). **É aqui que
  `test_fase42` é reescrito** — as passivas antigas viram gatilhos/consequências.
- **Etapa 5 (árvore rica):** spec #2 `arvores-habilidade-classes` — passivas na
  árvore + utilitárias. **Autorar em Fable.** O gerador atual já dá um conjunto
  MÍNIMO jogável (41 ativas); a 5 expande p/ ~100 com passivas/utilitárias.
- **Etapa 6 (migração):** `persistence._MIGRATIONS` — mapa old→new (tabela §3.10),
  backfill `entropy`/`max_entropy`/`abyss_charge`, `canonicalize_known_abilities`
  descarta habilidades inexistentes. Arquivar `docs/CLASSES*.md`. Atualizar
  `playtest/runner._DEFAULT_CHAR` + `profiles.py`.
  Teste `test_no_old_class_in_active_data` (grep-assert: nenhuma das 10 antigas
  em classes.json/class_themes.json/onboarding.json).
- **Etapa 7 (frontend):** `web/src` `types.ts` + `api.py` `/game/state` expõe
  `entropy`/`max_entropy`/`abyss_charge`/`abyss_tier` (oculto p/ Médico) +
  `Hud.tsx` barra Entropia + chip Carga. `cd web && npm run build`.
- **Etapa 8:** `uv run pytest` verde + smoke real (§6 da spec: criar Sangromante,
  auto-dano soma Entropia+Carga, descanso recompõe Entropia sem baixar Carga,
  Devoto apanha→Insônia; save de classe antiga migra) + docs.

---

## Tabela de migração (Etapa 6) — old → new

| Classe antiga | Nova |
|---|---|
| Cavaleiro da Vigília · Inquisidor da Cinza | Devoto do Abismo |
| Sombra da Corte · Sangromante | Sangromante |
| Pastor de Pragas · Guardião Selvagem | Corruptor |
| Arcanista Cinzento · Batedor das Fronteiras | Arcanista Cinzento |
| Médico de Campo · Sapador da Fuligem | Médico de Campo |

---

## Riscos / decisões já tomadas

- **MockLLM esconde mapeamento de campo** — `character_creator` (SMART) precisa
  de smoke real (entropy/abyss no save). Vale a regra do projeto.
- **Números são `[BALANCEAR]`** — proposta jogável, não final (§8 da spec).
- **Ordem de autoria:** 4 classes não-Médico primeiro, Médico por último
  (depende de Carga alheia viva) — §8.4.
- **Coupling 2↔5:** `starting_abilities` de classes.json PRECISAM existir em
  player_abilities.json. O gerador já garante isso (gera os dois juntos). Não
  editar um sem o outro.
