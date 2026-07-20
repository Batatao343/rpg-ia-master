# SPEC — Limpar `in_scene` de NPC em toda troca de local (fecha `recycled_npc`)

> **Status:** `approved`
> **Criada:** 2026-07-20 · **Atualizada:** 2026-07-20
> **Depende de:** [encontros-dedupe](encontros-dedupe.md) `done` (vínculo de local + invariante) ·
> [combate-lifecycle](combate-lifecycle.md) `done` (fuga aplica viagem no mesmo turno)
> **Desbloqueia:** telemetria de playtest limpa (menos ruído de warning nos runs longos)

---

## 1. Contexto & Objetivo

O playtest longo (`run_id 20260719-160014`) acusou **43 violações
`narrative.recycled_npc`** (warning) — a spec `encontros-dedupe` deveria ter
matado isso. Investigando o JSONL: as violações disparam em turnos de **combate**,
não de narração de encontro, e não há reintrodução de NPC visível na prosa. Não é
o "Sobrevivente moribundo em 3 locais" que a `encontros-dedupe` combateu — é
**flag zumbi**.

Causa-raiz: o reset de cena (`npc_layers.reset_scene`, que faz `in_scene=False`
em todos) só roda **no storyteller quando há viagem** ([storyteller.py:548](../agents/storyteller.py#L548)).
Mas há outra via de troca de local que NÃO reseta: a **fuga de combate** aplica
`apply_travel` em [combat.py:726](../agents/combat.py#L726) sem chamar
`reset_scene`. Resultado: um NPC gerado em `pm_profundezas` (`created_turn`,
`in_scene=True`) sobrevive à fuga do jogador para `nova_arcadia`, e o invariante
`check_recycled_npc` (`created_turn` + `in_scene` + `home != local`) dispara em
TODO turno seguinte até a cena ser resetada por acaso — daí as dezenas de
ocorrências.

Ponto importante (não é bug de gameplay): o **contexto do narrador já está
protegido** — `npc_layers.npcs_for_context` (encontros-dedupe R1) filtra por
`home_location_id`, então o NPC zumbi NÃO vaza pra prosa. O dano é só estado sujo
+ ruído de telemetria. Objetivo: fechar o buraco no ponto certo (toda troca de
local reseta a cena) e endurecer o invariante para medir vazamento REAL, não a
flag crua.

Princípio: **determinístico** — reset de cena é operação pura sobre o dict de
NPCs, sem LLM.

## 2. Requisitos

- **R1 — Fuga de combate reseta a cena.** Quando `combat_node` aplica
  `apply_travel` na fuga bem-sucedida ([combat.py:726](../agents/combat.py#L726)),
  também aplica `npc_layers.reset_scene(npcs)` ao dict de NPCs do resultado —
  igual ao storyteller faz na viagem. Nenhum NPC do local antigo continua
  `in_scene` no destino.
- **R2 — Qualquer troca de local reseta a cena (defesa central).** Garantir que
  toda via que muda `world.current_location_id` num turno zere `in_scene` dos
  NPCs do dict. As vias hoje: storyteller-viagem (já ok) e combate-fuga (R1). Se
  surgir outra, um helper único deve cobrir — preferir centralizar a lógica
  "mudou de local → reset_scene" em vez de espalhar. Membros de party vivem em
  `state["party"]` (não no dict `npcs`), então o reset não os afeta — a presença
  de aliado é preservada.
- **R3 — Invariante mede vazamento REAL, não flag crua.** `check_recycled_npc`
  passa a só reportar quando o NPC gerado fora do local de fato ENTRARIA no
  contexto do narrador — i.e., reusar o mesmo predicado de
  `npc_layers.npcs_for_context` (vínculo de local / in_scene / party) em vez de
  `in_scene and home != loc` cru. Defesa em profundidade: mesmo que uma flag
  zumbi escape do reset, o invariante só grita se ela realmente puder poluir a
  cena. Continua `warning`.
- **R4 — Regressão no harness.** Rodada mock longa (perfis que fogem/viajam em
  combate — `combate`, `fujao`, `explorador` × ≥50 turnos) mostra
  `narrative.recycled_npc` caindo de dezenas para ~0. Registrar o número.

### Fora de escopo

- **Dedupe de encontro / carrossel de template** — é a `encontros-dedupe`, já
  `done`; esta spec é só a flag zumbi na troca de local.
- **NPC que viaja junto / recrutamento** — já coberto (party em lista separada;
  re-home na reintrodução). Não mexer.
- **Mudar a severidade do invariante** — segue `warning` (não reprova run).
- **Comportamento do narrador / geração de NPC** — inalterado.

## 3. Design técnico

**Arquivos alterados**

- `agents/combat.py` (~l.720–730): no ramo de fuga com viagem, após
  `result["world"] = wu.apply_travel(base_world, dest)`, adicionar
  `result["npcs"] = npc_layers.reset_scene(state.get("npcs", {}))` (importar
  `from services import npc_layers`). Só quando houve viagem de fato.
- `playtest/invariants.py` (`check_recycled_npc`, l.335): trocar o predicado cru
  `npc.get("created_turn") is not None and in_scene and home and home != loc`
  por: NPC gerado (`created_turn`) que aparece no conjunto
  `npc_layers.npcs_for_context(state)` MAS cujo `home_location_id` != local
  atual. Reusa a função de contexto como fonte de verdade (se ela filtra, o
  invariante cala).
- (Opcional, R2) `services/npc_layers.py`: helper
  `reset_scene_on_location_change(prev_world, new_world, npcs)` que aplica
  `reset_scene` só se o `current_location_id` mudou — açúcar para os callsites
  não repetirem a condição. Só criar se reduzir duplicação real; senão, a
  chamada direta em combat.py basta.

**Assinaturas reusadas (já existem):**
```python
npc_layers.reset_scene(npcs: Dict[str, dict]) -> Dict[str, dict]  # in_scene=False p/ todos
npc_layers.npcs_for_context(state: Dict) -> List[str]             # gate de contexto do narrador
```

Nenhum schema muda. `in_scene` já é campo existente; o reset só o zera mais cedo.

## 4. Plano passo a passo

### Etapa 1 — Fuga reseta cena + invariante honesto (testes primeiro)

1. **Testes** (`tests/test_encontros_dedupe.py` / `test_combat_lifecycle.py`):
   - `test_fuga_reseta_in_scene`: estado com NPC gerado `in_scene=True` em
     `loc_A`; jogador foge (`combat_flee_attempt`) para `loc_B` → após
     `combat_node`, o NPC tem `in_scene=False`.
   - `test_recycled_npc_nao_dispara_com_gate`: NPC gerado com `home != loc` mas
     FILTRADO por `npcs_for_context` (não em cena) → invariante NÃO reporta.
   - `test_recycled_npc_dispara_no_vazamento_real`: NPC gerado que de fato entra
     no contexto fora do local → invariante ainda reporta (não perdeu poder).
2. **Implementação:** R1 (combat.py) + R3 (invariants.py).
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Regressão no harness

1. Rodar mock `--profile fujao`/`combate`/`explorador` × 50t; contar
   `narrative.recycled_npc`. Alvo: ~0 (era 43 no run longo).
2. Anexar o número aqui.

## 5. Critérios de aceite

- [ ] Fuga de combate com viagem zera `in_scene` dos NPCs (teste)
- [ ] `check_recycled_npc` só dispara em vazamento real de contexto (2 testes)
- [ ] Harness mock longo: `narrative.recycled_npc` cai de dezenas para ~0 (número
      registrado)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A (spec determinística, sem structured output novo)
- [ ] Saves antigos continuam carregando (nenhuma mudança de schema; `in_scene`
      já existe)

## 6. Smoke test com LLM real

1. Um turno de API real: entrar em combate num local, gerar/ver um NPC em cena,
   fugir para outro local → o estado do save mostra o NPC com `in_scene=false`
   (não zumbi).
2. Confirmar que um aliado de party continua presente após a fuga (party é lista
   separada — não deve sumir).

## 7. Riscos & compatibilidade

- **Saves antigos:** `in_scene` já é campo existente (ausente = `True` por
  legado, via `is_in_scene`). Zerar mais cedo é seguro; nenhuma migração.
- **MockLLM:** o reset é determinístico e independe do LLM; testável em mock. A
  regressão do harness roda em mock.
- **Risco de zerar cena legítima:** `reset_scene` na fuga é exatamente o
  comportamento desejado (você fugiu do local — a cena antiga ficou pra trás).
  Party não vive no dict `npcs`, então aliados não são afetados. Se algum fluxo
  quiser preservar um NPC específico ao viajar, ele já usa a via de
  re-home/party — fora do escopo.
- **Impacto em quota/latência:** nenhum (operação em memória, sem LLM).
