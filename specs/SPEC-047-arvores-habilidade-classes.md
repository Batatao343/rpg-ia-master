# SPEC — Árvores de Habilidade das 5 Classes (ativas + passivas + fora de combate)

> **Status:** `done` (2026-07-19 — autoria executada em **Fable**. Árvore de
> **101 habilidades** (41 ativas + 35 passivas + 25 utilitárias) gerada por
> `scripts/gen_classes_v2.py`. Motor: `ability_kind` no schema;
> `combat_mechanics.player_passives` funde passivas aprendidas às da classe em
> TODOS os callsites do jogador (inimigo segue em `class_passives`); 5 triggers
> novos vivos (`entropy_max_bonus` no `apply_choice` · `entropy_on_kill` no
> combat_node · `entropy_cost_reduction` e `charge_discount` com piso ·
> `carga_embrace` em dano/AC/ataque); utilitárias entram no prompt do storyteller
> via `services/context_builder.utility_context_block` (gate determinístico, LLM
> narra). HUD: selo ✦ passiva / ⚒ utilitária na ficha e no LevelUpModal;
> passiva/utilitária fora dos chips e do catálogo de combate. **918 offline
> verdes** (+20 `test_arvores_classes`) + smoke real 4/4 (storyteller REAL narrou
> "Avaliação de Preço" injetada no contexto). **Desvio consciente:** passivas
> autoradas SÓ com o vocabulário tipado da tabela §3.2 — sugestões do blueprint
> fora do vocabulário (ex.: "DoT dura +1 turno") foram trocadas por efeito
> tipado tematicamente equivalente, sem trigger ad-hoc novo.)
> **Criada:** 2026-07-17 · **Atualizada:** 2026-07-19
> **Depende de:** [refatoracao-sistema-classes](SPEC-048-refatoracao-sistema-classes.md) `approved`
> (define as 5 classes, Entropia/Carga, subclasses = branch derivada) · Fase 4.1
> (motor de árvore/ramo/elegibilidade) · 4.2 (passivas/`effects` tipados) — `done`
> **Desbloqueia:** playthrough completo das 5 classes; rebalanceamento
> **Fonte de design:** `VALORIA_spec_sistema_classes.md` (§3 — subclasses + "habilidades
> fora de combate" por classe). Números aqui são proposta inicial `[BALANCEAR]`.
>
> ### ⚠️ Autoria = modelo Fable (precedente da 4.1b)
> A Etapa de autoria (conteúdo criativo com identidade mecânica E narrativa,
> pesquisa de tom no Codex) segue a regra da 4.1b: rodar em **Fable**
> (claude-fable-5). Etapas de schema/motor/testes rodam em qualquer modelo.

---

## 1. Contexto & Objetivo

A spec-mãe ([refatoracao-sistema-classes](SPEC-048-refatoracao-sistema-classes.md)) define
**o sistema**: 5 classes, Entropia/Carga, gatilhos, subclasses como `branch`
derivado de `known_abilities`. O R8 dela pede a árvore, mas de forma resumida.
**Esta spec é o R8 expandido**: autora as árvores inteiras e — o pedido explícito
do usuário — dá a **cada subclasse habilidades passivas próprias, não só de
combate**, além de habilidades **fora de combate** (utilitárias).

Dois achados do motor que esta spec precisa resolver antes do conteúdo:

1. **Não existe passiva na árvore hoje.** `combat_mechanics.class_passives(player)`
   lê SÓ `CLASSES[classe]["passive_effects"]` (nível de classe). Passiva aprendida
   por subclasse não tem representação. → esta spec adiciona **habilidade do tipo
   passiva** no `player_abilities.json` e a função que funde as passivas aprendidas
   às da classe (`player_passives`).
2. **"Fora de combate" não existe como habilidade.** As capacidades utilitárias do
   doc (avaliar preço, detecção técnica, diagnóstico social…) hoje só existiriam
   como tempero narrativo via `class_themes`. → esta spec adiciona **habilidade do
   tipo utilitária**: uma capacidade determinística (o jogador TEM ou não tem) que
   entra no contexto do storyteller/router para a LLM **narrar** — a mecânica é o
   gate (conhece/não conhece), a narração é da LLM. Coerente com "mecânica é Python,
   LLM só narra".

Princípios (herdados da 4.1b): pesquisar o Codex antes de escrever para pegar o TOM
do mundo (pode ler `hidden`/`secret`, mas **nada de spoiler na saída**); zero
habilidade só-texto (todo efeito é campo que o motor resolve).

## 2. Requisitos

- **R1 — Tipagem de habilidade.** `player_abilities.json` ganha `ability_kind` ∈
  `{"active","passive","utility"}` (ausente/legado = `"active"`). `active` = ação
  de combate (como hoje); `passive` = efeito permanente ao aprender; `utility` =
  capacidade fora de combate.
- **R2 — Passivas na árvore funcionam.** `combat_mechanics.player_passives(player)`
  = `passive_effects` da classe **+** os `passive_effects` de toda habilidade
  `passive` em `known_abilities`. Os callsites de combate do JOGADOR passam a ler
  `player_passives`; inimigos seguem em `class_passives` (não têm passivas de árvore).
- **R3 — Cada subclasse tem ≥2 passivas.** Cada um dos 15 branches contém pelo menos
  **2 habilidades `passive`** com `passive_effects` tipado (efeito mecânico real,
  não prosa) — testável por assert.
- **R4 — Cada subclasse tem ≥1 utilitária.** Cada branch tem ≥1 habilidade
  `utility` (capacidade fora de combate) além das utilitárias de tronco.
- **R5 — Utilitárias de tronco (do doc).** Cada classe tem no **tronco comum** as 2
  habilidades "fora de combate" do documento-fonte (§3), como `utility`.
- **R6 — Cada subclasse tem ≥2 ativas de combate** encadeadas (`requires` dentro do
  ramo, tiers 2–4), com identidade mecânica distinta das outras duas subclasses da
  mesma classe.
- **R7 — Tudo em Entropia.** Nenhuma habilidade de jogador usa mana/stamina
  (`resource_type: "Entropia"` nas ativas; passivas/utilitárias `"Nenhum"`, `cost 0`).
- **R8 — Sem só-texto (herdado 4.1b R4).** Ativa: `damage_formula`≠"0" OU
  `conditions` OU `effects`. Passiva: `passive_effects` não-vazio e tipado.
  Utilitária: `out_of_combat` (descritor tipado, ver §3.4) não-vazio.
- **R9 — Ramo derivado + lock intactos.** Passivas/utilitárias com `branch` também
  entram no lock de ramo rival (`progression.eligible_abilities`) e na derivação
  (`player_branch`). Sem campo de estado novo.
- **R10 — HUD distingue tipos.** Passivas e utilitárias aparecem na ficha marcadas
  (◆ ramo já existe; adicionar selo de tipo), não como ação de combate clicável.
- **R11 — Anti-spoiler (herdado 4.1b R6).** Nome/descrição nunca revela fato só
  existente em chunk `hidden`/`secret`.
- **R12 — Guard-rail de volume por classe:** tronco (2 ativas iniciais + 2 utilitárias
  do doc + ≥1 passiva) + 3 branches (≥2 ativas + ≥2 passivas + ≥1 utilitária cada).
  ≈ 20 habilidades/classe, ≈ 100 no total. As 111 antigas saem (spec-mãe R10).

### Fora de escopo

- Motor de Entropia/Carga/gatilhos/consequências — é da **spec-mãe** (aqui só se
  AUTORAM habilidades que marcam `peak`/`cools`/`self_harm` que a spec-mãe lê).
- Tiers 5+ (nível 9–20) — fast-follow; aqui tiers 1–4 (jogável até ~nível 8).
- Rebalanceamento final de números.
- Inimigos/companheiros; economia; itens.

## 3. Design técnico

### 3.1. Schema de habilidade — campos novos

Sobre o schema atual (`name`, `category`, `cost`, `resource_type`,
`damage_formula`, `damage_type`, `conditions`, `save_stat`, `scaling_formula`,
`classes`, `branch`, `tier`, `level_req`, `requires`, `effects`):

```jsonc
"ability_kind": "active" | "passive" | "utility",   // ausente = "active"
"passive_effects": [ ... ],   // só passive — MESMO vocabulário de classes.json
"out_of_combat": { ... }      // só utility — descritor tipado (§3.4)
```

### 3.2. Passiva na árvore — `player_passives` (`combat_mechanics.py`)

```python
def learned_passives(player: Dict, *, abilities_db=None) -> List[Dict]:
    """passive_effects de toda habilidade ability_kind=='passive' em known_abilities."""

def player_passives(player: Dict, *, abilities_db=None) -> List[Dict]:
    """class_passives(player) + learned_passives(player). Usada nos callsites do
    JOGADOR (damage_bonus, condition_modifiers, iniciativa, retaliação, cura).
    Inimigo continua em class_passives (sem árvore)."""
```

Callsites a trocar de `class_passives(player)` → `player_passives(player)`:
`damage_bonus`, `condition_modifiers` (se lê passiva), iniciativa
(`initiative_attr`), retaliação (`melee_retaliate`), cura (`heal_bonus_low`),
AC (`unarmored_ac_con`, `party_active`). Enemy paths ficam.

**Vocabulário de `passive_effects` para as passivas novas** (triggers tipados —
reusa os existentes + adiciona os do sistema de Entropia/Carga):

| `trigger` | Efeito | Já existe? |
|---|---|---|
| `always` + `stat`/`delta` | bônus fixo (dano/AC/ataque/save) | sim (4.2) |
| `damage_type` | bônus condicional por tipo de dano | sim |
| `resist` + `name` | imune/resistente a condição | sim |
| `melee_retaliate` + `formula` | dano de retorno a quem bate cac | sim |
| `initiative_attr` | usa outro atributo na iniciativa | sim |
| `unarmored_ac_con` / `party_active` | AC condicional | sim |
| `heal_bonus_low` | +cura em alvo com pouca vida | sim |
| `entropy_max_bonus` + `delta` | +max_entropy permanente | **novo** |
| `entropy_on_kill` + `amount` | Entropia ao matar inimigo | **novo** |
| `entropy_cost_reduction` + `category`/`delta` | -custo de Entropia de uma categoria | **novo** |
| `charge_discount` + `delta` | reduz Carga ganha por ativação do gatilho | **novo** |
| `carga_embrace` + `per_tier`/`stat` | converte patamar de Carga em bônus (abraçar o Abismo) | **novo** |

Os 5 triggers novos são lidos pela mecânica (spec-mãe já toca esses pontos:
`entropy_config`/`try_pay_ability_cost`/`apply_entropy_trigger`/`abyss_tier`).
`entropy_max_bonus` aplica na criação/aprendizado; os demais no ponto do efeito.

### 3.3. Habilidade utilitária — como "funciona"

`utility` não tem resolução de combate. Ela é uma **capacidade conhecida** que:
1. Entra no **contexto do storyteller/router** (`services/context_builder` /
   prompt do storyteller) como "o herói é capaz de: <label>" — a LLM **narra** o
   uso; o gate (conhece/não conhece) é determinístico.
2. Opcionalmente arma um **hook leve determinístico** quando natural — ver `effect`
   em §3.4 (ex.: setar `world.treasure_hint`, revelar um chunk de codex, +1 num
   teste social). Sem hook = capacidade puramente narrada (ainda determinística no
   gate).
3. Aparece na ficha (HUD) com selo de utilitária.

Isto respeita "LLM só narra": o que o personagem PODE fazer é dado (Python); COMO
a cena descreve é narração.

### 3.4. `out_of_combat` — descritor tipado

```jsonc
"out_of_combat": {
  "label": "Avaliação de preço",
  "scope": "social" | "investigation" | "detection" | "engineering" | "medical",
  "prompt_hint": "sabe o custo/valor real de algo, mesmo quando escondido",
  "effect": null | {
    "kind": "reveal_hint" | "reveal_codex" | "skill_bonus" | "flag",
    "...": "params — ex.: {\"kind\":\"skill_bonus\",\"scope\":\"social\",\"delta\":2}"
  }
}
```

`scope`/`prompt_hint` alimentam o contexto do storyteller. `effect` (opcional) é o
hook determinístico. Validador exige `label`+`scope`+`prompt_hint`.

### 3.5. Blueprint de design (por classe → subclasse)

Identidades já fixadas pelo doc-fonte; a autoria enche as habilidades. `[BALANCEAR]`.

**Devoto do Abismo** (tank · ama · gatilho `on_damage_taken` · Carga=Insônia)
- *Tronco:* provocacao_do_abismo (ativa aggro), encaixe_do_golpe (ativa), **utility**
  `convite` (intimidação-convite + sente quem está perto do Abismo numa sala),
  **utility** `pararraios_social` (puxa medo coletivo, evita motim), **passive**
  postura_do_convite (aggro escala com Entropia — casa com a regra especial).
- *Consagrado:* marca ritual pré-combate (ativa buff), **passives**: marca_consagrada
  (redução de dano após ritual), fervor_silencioso; **utility** leitura de presságio.
- *Zeloso:* aggro por ciúme (ativa taunt em área), **passives**: ciume_do_abismo
  (retaliação a quem ataca aliado), possessao; **utility** farejar rival.
- *Enlutado:* golpe melancólico (ativa), **passives**: luto_que_pesa
  (`carga_embrace` — quanto mais Carga, +stat), intimidade_com_o_fim (resist medo);
  **utility** falar com quem o Abismo levou (lore/pistas).

**Sangromante** (dano cac · negocia · `on_self_harm` · Carga=Cicatriz)
- *Tronco:* corte_de_troca (ativa `self_harm`), esquiva_calculada (ativa),
  **utility** `avaliacao_de_preco`, **utility** `leitura_forense`, **passive**
  contrato_de_sangue (Entropia de sangue não vaza tão rápido — baseline).
- *Exposto:* golpe espetáculo (ativa `peak`), **passives**: cicatriz_credencial
  (`carga_embrace` — intimidação passiva por Cicatriz), pele_de_anúncio; **utility**
  presença que cala uma sala.
- *Avaro:* acúmulo (ativa que guarda Entropia), explosão única (ativa `peak`),
  **passives**: cofre_de_sangue (`entropy_max_bonus`), juros (mais vazamento se
  acertado); **utility** farejar dívida/segredo caro.
- *Silencioso:* corte exato (ativa consistente), **passives**: mão_firme
  (reduz `leak_frac`), economia_de_dor; **utility** ferir sem deixar marca (furtivo).

**Corruptor** (controle/DoT · trabalha junto · `on_decay_nearby` · Carga=Transformação)
- *Tronco:* toque_da_decadência (ativa DoT), semear (ativa), **utility**
  `investigacao_via_decadencia` (sente o podre/rachado/cedendo), **utility**
  `rede_de_pragas` (vermes/ratos/insetos viram informantes), **passive**
  parceria (DoT que você aplica dura +1 turno).
- *Biologia (decay flesh):* praga_de_esporos (ativa área DoT), **passives**:
  contágio (DoT se espalha), simbiose (`entropy_on_kill`); **utility** ler doença/veneno.
- *Alma (decay morale):* corroer_vontade (ativa debuff moral), **passives**:
  desespero_ambiente (inimigos perto: -save), eco_do_vazio; **utility** sentir
  mentira "apodrecendo" numa história.
- *Inorgânica (decay gear):* enferrujar (ativa corrói arma/armadura), **passives**:
  toque_corrosivo (ataques aplicam corrosão), pó_e_ferrugem; **utility** achar o
  ponto fraco de uma estrutura/mecanismo.

**Arcanista Cinzento** (dano/controle à dist. · manipula · `on_channel` · Carga=Dependência)
- *Tronco:* descarga_do_instrumento (ativa `cools`), vazão_controlada (ativa `cools`),
  **utility** `deteccao_tecnica` (detect magic — éter ativo/residual), **utility**
  `engenharia_de_campo` (conserta/desarma/reconfigura mecanismo), **passive**
  disciplina_da_caldeira (janela de vazão maior — baseline anti-overload).
- *Calibrado:* dano calibrado (ativa segura), **passives**: válvula_extra (menos
  risco de estouro), condensador (`entropy_cost_reduction`); **utility** calibrar
  aparelho alheio.
- *Descoberto:* toque cru (ativa alto dano `self_harm`), **passives**: pele_marcada
  (`carga_embrace` dano à mão nua), veias_de_éter; **utility** sentir éter pela pele
  (detecção sem instrumento).
- *Improvisador:* rig improvisado (ativa utilitária de combate: marcar/desarmar),
  **passives**: engenhoca (bônus de utilidade), peças_de_reposição; **utility**
  montar ferramenta na hora a partir de sucata.

**Médico de Campo** (suporte/cura · nega · `on_ally_suffer` · Carga=Recidiva)
- *Tronco:* sutura_de_campo (ativa cura), estabilizar (ativa), **utility**
  `diagnostico_social` (lê estresse/mentira/doença), **utility**
  `aritmetica_de_desastre` (numa cena de escala: recurso/mortos/ordem de agir),
  **passive** triagem (`heal_bonus_low` — a passiva de classe atual vira tronco).
- *Cirurgião de Trincheira:* intervenção imediata (ativa cura pesada), **passives**:
  mãos_rápidas (cura reativa +), sangue_frio (resist medo); **utility** milagre de
  campo improvisado.
- *Boticário:* dose preparada (ativa buff pré-luta), **passives**: composto_estável
  (buffs duram +), farmacopeia (pode mitigar Carga INTERNA de aliado — Insônia do
  Devoto, Dependência do Arcanista); **utility** destilar remédio do veneno local.
- *Cirurgião de Ferro:* prótese (ativa que dá +defesa a aliado), **passives**:
  aço_no_lugar (aliado com prótese resiste +), oficina (pode mitigar Carga FÍSICA de
  aliado — Cicatriz, transformação bio); **utility** forjar/consertar membro mecânico.

> A habilidade dedicada do Médico que **reduz Carga de aliado** (`reduce_ally_abyss`,
> spec-mãe R9) é uma ATIVA de tronco/Boticário — ex.: `purga_da_carga`.

## 4. Plano passo a passo (TDD — testes primeiro)

### Etapa 1 — Schema + motor (passiva na árvore + utilitária)
1. **Testes** (`tests/test_arvores_classes.py`):
   `test_ability_kind_default_active`; `test_player_passives_merges_learned`
   (aprender passiva soma `passive_effects` ao total; inimigo não);
   `test_learned_passive_affects_combat` (ex.: passiva `always +2 dano` muda o dano
   resolvido); `test_utility_in_storyteller_context` (utilitária conhecida aparece
   no context pack); `test_entropy_max_bonus_applies`.
2. **Impl:** `ability_kind`; `learned_passives`/`player_passives` + troca de
   callsites do jogador; leitura dos 5 triggers novos; injeção de `utility` no
   contexto do storyteller; validador aceita os 3 kinds.
3. **Verificação:** verde.

### Etapa 2 — Testes de conteúdo (antes da autoria)
1. **Testes:** `test_cada_subclasse_2_passivas` (R3); `test_cada_subclasse_1_utility`
   (R4); `test_tronco_tem_2_utility_do_doc` (R5); `test_cada_subclasse_2_ativas` (R6);
   `test_tudo_entropia` (R7 — nenhuma player ability em Mana/Estamina);
   `test_sem_so_texto` (R8 por kind); `test_requires_no_mesmo_ramo`;
   `test_starting_abilities_existem`. FALHAM contra o JSON atual (red).

### Etapa 3 — Autoria (Fable), classe a classe
Processo da 4.1b: pesquisa de tom no Codex (Grep, nunca Read inteiro) → escrever
tronco (ativas + 2 utilitárias do doc + passiva) → escrever os 3 branches (ativas
encadeadas + ≥2 passivas + ≥1 utilitária). Commit por classe. Seguir o blueprint §3.5.

### Etapa 4 — Passe de coerência + anti-spoiler
1. Nenhuma identidade de passiva duplicada entre as 3 subclasses de uma classe.
2. Anti-spoiler (R11): reler nome/descrição de toda habilidade nova.
3. Encoding UTF-8, sem mojibake.

### Etapa 5 — Frontend + suíte + smoke + docs
1. `Hud.tsx`/`types.ts`/`api.py`: selo de tipo (passiva/utilitária) na lista de
   habilidades; utilitárias visíveis fora de combate. `npm run build` verde.
2. `uv run pytest` verde. Smoke real (§6). Atualizar ESTADO_ATUAL/ROADMAP.

## 5. Critérios de aceite

- [x] `ability_kind` suportado; `player_passives` funde passivas aprendidas (motor).
- [x] Passiva aprendida muda o combate resolvido (teste + smoke: `juros_do_corpo` → "+1 passiva" no dano).
- [x] Utilitária conhecida entra no contexto do storyteller (teste + smoke real: narrador citou a capacidade).
- [x] Cada subclasse: ≥2 passivas + ≥1 utilitária + ≥2 ativas (R3/R4/R6 — asserts em `test_arvores_classes`).
- [x] Tronco de cada classe traz as 2 utilitárias "fora de combate" do doc (R5).
- [x] Zero habilidade de jogador em mana/stamina; zero só-texto (R7/R8 — por kind).
- [x] Lock de ramo rival vale para passiva/utilitária (R9 — `test_lock_de_ramo_vale_para_passiva`).
- [x] HUD marca passiva/utilitária (R10 — selo ✦/⚒ na ficha + LevelUpModal); `npm run build` verde.
- [x] `uv run pytest` verde (918 passed, 1 skipped).
- [x] Passe anti-spoiler registrado (grep: zero menção a segredos do Codex); autoria executada em Fable (claude-fable-5).

## 6. Smoke test com LLM real

1. Criar personagem de cada classe (ou ≥3 variadas); conferir que passivas e
   utilitárias do tronco aparecem na ficha e não são ação de combate.
2. Combate: aprender uma passiva no level up e ver o efeito no log (ex.: dano/AC).
3. Cena fora de combate: dar uma ação que use uma utilitária (ex.: "avalio o preço
   real disto") e conferir que o storyteller narra a capacidade (contexto injetado).
4. Médico: `purga_da_carga` reduz `abyss_charge` de um aliado da party (spec-mãe R9).

## 7. Riscos & compatibilidade

- **Passiva-na-árvore toca combate:** troca de `class_passives`→`player_passives`
  nos callsites do JOGADOR precisa de cuidado para não afetar inimigos — teste
  dedicado (`enemy` não ganha passiva de árvore).
- **Utilitária depende da LLM narrar:** o gate é determinístico, mas o "sabor" é da
  LLM — em MockLLM a narração é fixa; validar injeção de contexto por assert
  (contexto contém o label), não pela prosa.
- **Volume (~100 habilidades):** commit incremental por classe (como 4.1b).
- **Saves antigos:** cobertos pela migração da spec-mãe (R10) — `canonicalize`
  descarta ids inexistentes; `ability_kind` ausente = `active`.
- **Anti-spoiler:** pesquisa livre, filtro na saída (R11), passe manual na Etapa 4.
