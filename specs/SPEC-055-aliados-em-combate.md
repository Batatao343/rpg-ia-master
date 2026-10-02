# SPEC — Aliado presente entra no combate se está junto quando ele começa

> **Status:** `done`
> **Criada:** 2026-07-20 · **Atualizada:** 2026-08-02
> **Depende de:** Fase 4.5 (party + combate com aliados) `done` ·
> [npcs-3-camadas](SPEC-028-npcs-3-camadas-traits.md) `done` (gate `in_scene`) ·
> [npc-fallback-sem-alvo](SPEC-041-npc-fallback-sem-alvo.md) `done` (party in_scene)
> **Desbloqueia:** aliados com presença mecânica sentida (achado do playtest 2026-07-14)

---

## 1. Contexto & Objetivo

O playtest longo (`docs/playtest-longrun-2026-07-14.md`) registrou: **"Aliados sem
presença mecânica. Gorim/Korvus aparecem na prosa mas não existem pro gate de NPC
nem (aparentemente) pro combate."** O usuário definiu a regra desejada
(2026-07-20): **"os aliados devem aparecer no combate se estão juntos quando o
combate começa."**

### Achados da investigação (2026-07-20)

Investiguei o motor antes de propor. O que encontrei:

1. **O motor de combate JÁ inclui aliados corretamente** (Fase 4.5,
   [combat.py:418-424](../agents/combat.py#L418)): lê `state["party"]`, filtra
   `active_allies` (`active=True` ∧ `status=="ativo"` ∧ `hp>0`), rola iniciativa
   com o lado `ally` e resolve o turno deles (`resolve_ally_turn`). Um
   companheiro FORMAL e ativo **luta**. Não é bug do motor.

2. **A ÚNICA porta para `state["party"]` é o recrutamento formal**
   (`party.recruit`, [party.py:101](../party.py#L101)): gate determinístico
   `relationship >= 7` ∧ party < 3 ∧ fação não-hostil, disparado pela rota NPC
   com comando "junte-se a mim" (`detect_party_command`). NPC só vira combatente
   depois de passar por essa porta.

3. **Não existe ponte "NPC amigo em cena → combatente".** O combate só olha
   `state["party"]`. Um NPC aliado que está `in_scene` (conversando, viajando
   junto informalmente) mas nunca foi recrutado **não entra no combate**.

4. **No playtest, a party estava sempre VAZIA.** Os perfis combate/explorador/
   quester nunca recrutam (só `diplomatico` emite "se juntar"). Logo Gorim/Korvus
   eram **prosa sem lastro de estado** — o narrador inventou aliados que a
   mecânica nunca sancionou; nunca houve companheiro pra lutar.

**Conclusão:** o defeito é lacuna de coerência estado↔narração + gate de
recrutamento (rel≥7) mais lento que a prosa — não o motor. A correção alinhada ao
pedido do usuário: quando o combate começa, **qualquer aliado presente na cena**
(companheiro ativo — já ok; OU NPC amigo `in_scene`) entra no lado do herói. Um
NPC amigo em cena vira **aliado transitório** só para aquele combate (sem exigir
recrutamento formal permanente).

Princípio: **"Mecânica é Python"** — a decisão de quem é aliado presente é gate
determinístico (in_scene + amizade + fação), não julgamento do LLM.

## 2. Requisitos

- **R1 — Companheiro ativo presente luta (regressão, já funciona).** Fixar por
  teste: com `state["party"]` tendo aliado `active=True` presente, ao iniciar
  combate ele está na ordem de iniciativa no lado `ally`. (Trava o comportamento
  atual contra regressão.)
- **R2 — NPC amigo em cena vira aliado transitório no combate.** No início do
  combate (`is_combat_start`), NPCs do dict `npcs` que estão `in_scene` E são
  amigos (gate: `relationship >= LIMIAR_ALIADO_CENA` ∧ fação não-hostil ∧ não é
  o inimigo do encontro) são convertidos via `make_companion_from_npc` num
  combatente do lado `ally` **transitório** (flag `transient=True`), participando
  da iniciativa e agindo. `LIMIAR_ALIADO_CENA` < `RECRUIT_MIN_REL` (ex.: 5) — um
  amigo de cena luga contigo sem precisar do compromisso de recrutamento.
- **R3 — Transitório não vira party permanente.** O aliado transitório NÃO é
  persistido em `state["party"]` como companheiro fixo: some ao fim do combate
  (ou fica só enquanto `in_scene`). Recrutamento formal (rel≥7) segue a via
  própria para companheiro permanente. Evita que todo NPC amigo vire membro
  fixo do grupo.
- **R4 — Dano/morte do transitório reflete na cena.** Se o aliado transitório
  cai no combate, o NPC de origem no dict `npcs` marca ferido/morto de forma
  coerente (não ressuscita intacto no próximo turno de conversa). HP do
  companheiro transitório deriva de `combat_stats` do NPC ou template de
  arquétipo (já em `make_companion_from_npc`).
- **R5 — Sem aliado fantasma.** Se o narrador citar um aliado lutando, ele deve
  existir como combatente do lado herói (party ativa OU transitório). Invariante
  de telemetria `combat.phantom_ally` (warning): nome de aliado na narração de
  combate sem combatente correspondente do lado herói. Mede a lacuna que originou
  o achado.
- **R6 — Orçamento de inimigos considera o aliado transitório.** O spawn já
  escala por `n_allies` ([combat.py:142](../agents/combat.py#L142),
  `encounter_budget(level, danger, n_allies)`); incluir os transitórios na
  contagem para o combate não ficar trivial com muitos amigos em cena (teto de
  aliados transitórios, ex.: 2).

### Fora de escopo

- **Mudar o gate de recrutamento permanente** (rel≥7) — inalterado; transitório
  é caminho paralelo, não substitui.
- **IA de comportamento do aliado** — reusa `resolve_ally_turn`/behavior existente
  (Fase 4.5); nada novo.
- **Disciplinar o LLM a não inventar aliados** — atacado indiretamente por R2
  (agora o aliado citado provavelmente EXISTE) + medido por R5; não se tenta
  proibir a prosa.
- **Companheiros no HUD/telas de party** — sem mudança de UI (transitório é de
  combate; some depois).

## 3. Design técnico

**Arquivos alterados**
- `party.py`
  - `scene_allies(state) -> List[dict]`: NPCs `in_scene` amigos (gate R2) →
    lista de companheiros transitórios via `make_companion_from_npc`, marcados
    `{"transient": True, "origin_npc": <id>}`. Respeita teto (R6).
  - Constante `SCENE_ALLY_MIN_REL = 5` (< `RECRUIT_MIN_REL`).
- `agents/combat.py` (~l.418–424): `allies_active` passa a ser
  `party_mod.active_allies(state) + party_mod.scene_allies(state)` (transitórios
  só no `is_combat_start`, persistidos no `combat_meta`/party efêmera durante o
  combate). Contagem de aliados para `encounter_budget` inclui os transitórios
  (R6). Ao encerrar o combate: transitórios NÃO vão para `result["party"]`
  permanente; dano/morte reflete no NPC de origem em `result["npcs"]` (R4).
- `playtest/invariants.py`: `check_phantom_ally` (R5) — extrai nomes citados como
  aliados na narração de combate e confere contra o lado herói da ordem; warning.
- `playtest/profiles.py` (opcional): um perfil que RECRUTA e leva aliado pro
  combate, pra o harness exercitar R1/R2 (hoje só `diplomatico` recruta e não
  busca combate). Pode ser um ramo no `diplomatico` ou perfil novo `companheiro`.
- `state.py` — documentar flag efêmera `transient` no companheiro de combate
  (runtime-only, não persiste em party).
- `tests/test_aliados_combate.py` (novo).

**Assinaturas:**
```python
def scene_allies(state: Dict) -> List[Dict]: ...        # NPCs amigos in_scene → transitórios
SCENE_ALLY_MIN_REL = 5
MAX_SCENE_ALLIES = 2
```

**Gate de amigo-em-cena (R2), determinístico:**
```
in_scene(npc) ∧ relationship(npc) >= SCENE_ALLY_MIN_REL
            ∧ faction(npc) não hostil ao jogador
            ∧ npc não é combatente inimigo do encontro
```

## 4. Plano passo a passo

### Etapa 1 — Regressão do que já funciona + ponte de cena (testes primeiro)

1. **Testes** (`tests/test_aliados_combate.py`):
   - `test_companheiro_ativo_luta`: party com aliado ativo presente → está na
     ordem de iniciativa lado `ally` (trava R1).
   - `test_npc_amigo_em_cena_vira_aliado`: NPC `in_scene`, `relationship=6`,
     fação neutra → combate o inclui como transitório no lado herói.
   - `test_npc_hostil_ou_frio_nao_entra`: `relationship=3` OU fação hostil → NÃO
     entra.
   - `test_transitorio_nao_persiste_party`: após o combate, `state["party"]` não
     ganhou companheiro permanente; NPC segue no dict `npcs`.
   - `test_teto_aliados_transitorios`: 3 amigos em cena → no máx. `MAX_SCENE_ALLIES`
     entram.
2. **Implementação:** `party.scene_allies` + fiação em `combat.py` (R2/R3/R4/R6).
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Invariante anti-fantasma + perfil de harness

1. **Testes:** `test_phantom_ally_detecta` (aliado citado sem combatente → warning);
   `test_phantom_ally_silencia_com_aliado` (com transitório presente → sem
   violação).
2. **Implementação:** `check_phantom_ally` (R5) + perfil/ramo que recruta e
   combate (harness exercita a ponte).
3. **Verificação:** `uv run pytest` verde + harness mock do perfil mostra aliado
   no combate.

## 5. Critérios de aceite

- [x] Companheiro ativo presente entra na iniciativa (regressão travada)
- [x] NPC amigo `in_scene` vira aliado transitório no combate (teste)
- [x] NPC frio/hostil NÃO entra (teste de gate)
- [x] Transitório não vira party permanente; dano/morte reflete no NPC (testes)
- [x] Teto de aliados transitórios respeitado; `encounter_budget` conta os aliados
- [x] Invariante `combat.phantom_ally` detecta aliado citado sem combatente
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Guard de FallbackLLM: N/A (ponte é determinística; sem structured output novo)
- [x] Saves antigos continuam carregando (`transient` é efêmero; party intacta)

## 6. Smoke test com LLM real

1. API real: conversar com um NPC amigo (subir relação), mantê-lo em cena,
   provocar combate → o aliado aparece na iniciativa e age; o log de combate
   mostra a ação dele.
2. NPC morre no combate transitório → ao conversar depois, o estado reflete a
   perda (não volta intacto).
3. Recrutar formalmente (rel≥7) → o companheiro persiste na party entre combates
   (via já existente, não deve regredir).

## 7. Riscos & compatibilidade

- **Saves antigos:** party existente intacta; `transient` é flag efêmera de
  combate, não persistida. Sem migração.
- **MockLLM:** a ponte é determinística e independe do LLM; testável em mock.
  O gate usa `relationship`/`faction` do dict `npcs` (dados de estado, não LLM).
- **Balanceamento:** aliados transitórios facilitam o combate — mitigado por
  `SCENE_ALLY_MIN_REL` (só amigos reais), `MAX_SCENE_ALLIES` (teto) e
  `encounter_budget` contando-os (inimigos escalam junto). Cruza com
  [letalidade-early-game-v2](SPEC-056-letalidade-early-game-v2.md): mais aliados = menos
  letal; medir junto.
- **Coerência:** R4 (morte reflete no NPC) evita o "aliado imortal" que morre no
  combate e reaparece são na conversa seguinte.
- **Quota/latência:** nenhuma chamada de LLM nova; a ponte é pré-combate em Python.

## 8. Registro de execução (2026-08-02)

- A auditoria acrescentou o gate que impede o próprio NPC-alvo do encontro de
  virar aliado e travou por teste o reflexo de dano/morte no NPC de origem.
- O perfil `recrutador` foi corrigido para concentrar vínculo em um NPC, exercer
  o aliado transitório e depois o recrutamento formal. Run
  `20260802-171448-021987`: 30 turnos, 7 combates, 0 erros/violações; Tobias
  lutou como transitório no turno 2, entrou na party no turno 5 e continuou
  agindo/recebendo ferimentos nos conflitos seguintes.
- O MockLLM agora preserva alvo social explícito e `generate_new_npc` fixa o
  nome canônico pedido pelo router, eliminando troca de identidade válida no
  schema, mas errada no estado.
- Smoke real: Bors apareceu em `scene_allies`, iniciativa `heroes → enemy`,
  acertou o Bandido do Cais e foi citado pela narração real.
- Suíte integral: **1.320 passed, 1 skipped, 14 deselected**.
