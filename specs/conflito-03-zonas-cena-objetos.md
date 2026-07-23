# SPEC — Conflito v2 #03: Zonas, Cena Congelada e Objetos Interativos

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-01-virtudes-vitalidade` (`done` antes de iniciar)
> **Desbloqueia:** `conflito-04` (movimento por zona), `conflito-06` (Engajar/
> Desengajar/Esconder-se), `conflito-09` (fuga/perseguição usa zonas),
> `conflito-11` (preparação de encontro popula zonas/objetos)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

O combate hoje não tem posicionamento — é uma lista plana de participantes
(`combat.order`) sem distância, zona ou cobertura. `docs/valoria_conflict_migration_v2/
01_..._CONFLITOS.md` §6-7 introduz zonas abstratas nomeadas (não-grid) com três
eixos independentes — Distância (Próximo/Distante/Separado), Postura (Protegido/
Neutro/Exposto), Ocultação (Visível/Escondido) — mais Engajamento como relação
separada, e objetos interativos gerados pela LLM a partir da cena narrada com um
**catálogo fechado** de efeitos mecânicos.

Esta spec define a estrutura de dados da cena de conflito (zonas, ligações,
posições, objetos) e a regra de **cena congelada**: depois que o conflito começa,
nada pode ser acrescentado por interpretação livre.

## 2. Requisitos

- **R1** — `ConflictScene` (estrutura nova, não mais `combat` dict solto):
  `zones: List[{id, name, connections: List[zone_id]}]`, `positions: Dict[participant_id,
  {zone_id, distance_state, postura, ocultacao}]`, `objects: List[SceneObject]`,
  `frozen: bool` (True assim que o conflito começa).
- **R2** — Distância tem 3 estágios (Próximo/Distante/Separado); Postura 3
  (Protegido/Neutro/Exposto); Ocultação 2 (Visível/Escondido); Engajamento é lista
  separada `engaged_with: List[participant_id]` — dois personagens podem estar
  Próximos sem Engajados.
- **R3** — Mudança de distância: 1 estágio por Pré-Ação **ou** Pós-Ação; usando
  ambas no mesmo turno, atravessa 2 estágios.
- **R4** — Protegido/Exposto podem ser momentâneos (afeta só o próximo ataque
  aplicável, depois termina) ou sustentados (persiste enquanto a causa concreta
  existir — pilastra, correntes, cobertura, Guardar).
- **R5** — `SceneObject`: `{id, name, distance_state, zone_id, interactions:
  List[{label, cost ("pre_acao"|"pos_acao"|"acao"), effect: EffectSpec}],
  secret: bool, uses_remaining: Optional[int], destroyed: bool}`. O jogador vê
  `label`+`cost`, nunca `effect` (oculto até uso, salvo investigação prévia).
- **R6** — Catálogo fechado de `EffectSpec.kind` (compartilhado com `conflito-10`/
  `conflito-11`): `alter_terrain | block_route | unblock_route | damage |
  request_reaction | apply_condition | reposition | spawn_reinforcement |
  destroy_object | change_environment_condition`. Toda preparação de LLM que gerar
  um efeito fora deste catálogo é rejeitada na validação (não vira regra
  inventada).
- **R7** — Objeto secreto (`secret: True`) não aparece na lista visível até
  descoberto (via Procurar ou investigação prévia registrada).
- **R8** — Cena congelada: uma vez `frozen=True` (conflito iniciado), nenhuma
  chamada de LLM pode adicionar zona/objeto/participante fora dos gatilhos já
  preparados (reforços só entram via `spawn_reinforcement` com gatilho definido
  antes do início).

### Fora de escopo

Geração da cena pela LLM (`conflito-11`); resolução de dano/efeitos de ataque
(`conflito-04`/`05`); fuga/perseguição usando as zonas (`conflito-09`); Reações
disparadas por objeto (`conflito-06`).

## 3. Design técnico

**Arquivos novos:**
- `services/conflict_scene.py` — `ConflictScene` (Pydantic), `move_distance
  (scene, participant_id, direction, via: "pre"|"pos") -> Result`, `apply_object_interaction
  (scene, object_id, interaction_label, actor_id) -> EffectSpec`,
  `validate_effect_kind(effect) -> bool` (catálogo fechado), `freeze(scene)`.

**Arquivos alterados:**
- `state.py` — `GameState.combat` ganha `scene: Optional[ConflictScene]`
  (substitui gradualmente o `combat` dict solto de hoje — `round/active/order/
  idle_turns` continuam existindo em paralelo até `conflito-13` consolidar).

**Schema:**
```python
class SceneObject(TypedDict):
    id: str
    name: str
    distance_state: Literal["proximo", "distante", "separado"]
    zone_id: str
    interactions: List[Dict]  # {label, cost, effect}
    secret: bool
    uses_remaining: Optional[int]
    destroyed: bool

class EffectSpec(TypedDict):
    kind: Literal["alter_terrain","block_route","unblock_route","damage",
                  "request_reaction","apply_condition","reposition",
                  "spawn_reinforcement","destroy_object","change_environment_condition"]
    params: Dict
```

## 4. Plano passo a passo

### Etapa 1 — `ConflictScene` + zonas
1. **Testes** (`tests/test_conflito_zonas.py`): `test_move_distance_um_estagio`;
   `test_move_distance_dois_estagios_pre_e_pos`; `test_engajamento_independente_de_distancia`.
2. **Implementação:** `services/conflict_scene.py`.

### Etapa 2 — Postura e Ocultação
1. **Testes:** `test_protegido_momentaneo_expira_apos_um_ataque`;
   `test_protegido_sustentado_persiste_enquanto_causa_existir`.
2. **Implementação:** campos + lógica de expiração.

### Etapa 3 — Objetos interativos + catálogo fechado
1. **Testes:** `test_interacao_objeto_gera_effectspec_valido`;
   `test_effect_kind_fora_do_catalogo_e_rejeitado`; `test_objeto_secreto_nao_aparece_ate_descoberto`.
2. **Implementação:** `apply_object_interaction`/`validate_effect_kind`.

### Etapa 4 — Cena congelada
1. **Testes:** `test_freeze_bloqueia_novo_objeto_apos_inicio`;
   `test_reforco_so_entra_via_gatilho_preparado`.
2. **Implementação:** `freeze`/guard.

## 5. Critérios de aceite

- [ ] Zonas, distância, postura e ocultação funcionam como eixos independentes.
- [ ] Objeto interativo mostra só interação+custo ao jogador, efeito oculto até uso.
- [ ] Efeito mecânico fora do catálogo fechado é rejeitado na validação.
- [ ] Cena congelada impede acréscimo de elementos fora dos gatilhos preparados.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

N/A nesta spec (estrutura de dados pura). Smoke real da geração de zonas/objetos
pela LLM acontece em `conflito-11`.

## 7. Riscos & compatibilidade

- `combat` dict atual (`round/active/order/idle_turns`) e `ConflictScene` novo
  coexistem até `conflito-13` — documentar claramente qual campo é fonte de
  verdade de quê para não confundir sessões futuras.
- Catálogo fechado de `EffectSpec.kind` é compartilhado entre 3 specs
  (`conflito-03`/`10`/`11`) — definir aqui e só referenciar depois, nunca duplicar.
