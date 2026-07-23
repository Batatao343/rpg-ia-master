# SPEC — Conflito v2 #12: Integração de Loot e Resumo Canônico Pós-Conflito

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-07-morte-rendicao-captura`, `conflito-08-comportamento-tatico-companheiros`,
> `conflito-09-fuga-perseguicao` (todas `done` antes de iniciar — precisa de
> todos os desfechos possíveis de conflito)
> **Desbloqueia:** `conflito-13` (cutover final)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Loot já existe e funciona (`agents/loot.py`, `services/economy.py`) e **não
precisa ser recriado** — só integrado ao novo resultado de conflito
(`docs/valoria_conflict_migration_v2/02_..._MIGRACAO.md` §4.7: "Loot continua fora
da LLM... deve receber o estado final do conflito e concluir sua resolução antes
da retomada narrativa"). Hoje `combat_node` seta `next: "loot"` só em vitória
(`agents/combat.py:596`), com `loot_source` implícito `TREASURE`.

`01_..._CONFLITOS.md` §35 exige que, depois do combate/perseguição/loot
concluídos (sem LLM), a LLM receba um **resumo canônico** — não os detalhes
mecânicos brutos — e retome a narrativa sem poder reverter nenhum fato.

## 2. Requisitos

- **R1** — `loot_node` passa a receber o estado final do `ConflictScene`/
  `ChaseState` já resolvidos (não mais só "combate venceu" implícito) —
  `loot_source` continua determinístico, mas a origem de raridade/quantidade pode
  refletir o Nível do Encontro (`conflito-11`) no lugar do `danger_level` bruto
  atual, mantendo `economy.roll_loot` como está sempre que possível (reaproveitar,
  não recriar).
- **R2** — Resumo canônico (`ConflictSummary`) contém: participantes,
  sobreviventes, mortos, inconscientes, rendidos, fugitivos, capturados,
  Ferimentos, Cicatrizes a gerar (`conflito-07`), recursos gastos, Cartas
  descobertas, resistências descobertas (`conflito-08`), objetos utilizados,
  mudanças permanentes no cenário, companheiros separados (`conflito-09`),
  decisões morais, fatos de relação, loot obtido, estado final da party.
- **R3** — A LLM (storyteller/archivist) continua a narrativa **só** a partir
  desses fatos — não pode reverter morte→fuga, libertar capturado, restaurar
  cenário destruído, sem um novo acontecimento posterior explícito (doc 03,
  Cenário 52).
- **R4** — Combate/perseguição/loot são concluídos **inteiramente sem LLM**; só
  depois disso o resumo é montado e entregue.

### Fora de escopo

Mudanças na lógica interna de `economy.py` (preço/estoque/craft) — fora de
escopo, já funciona; regras de quando um objeto vira loot (`conflito-03`/`11` já
cobrem objetos de cena, este spec só cobre o **resumo**, não a geração).

## 3. Design técnico

**Arquivos novos:**
- `services/conflict_summary.py` — `ConflictSummary` (Pydantic, campos de R2),
  `build_summary(scene, chase_state, death_outcomes, loot_result) ->
  ConflictSummary`.

**Arquivos alterados:**
- `agents/loot.py` — consumo do `ConflictSummary`/`ConflictScene` no lugar do
  estado de combate simplificado atual; `loot_source` deriva de contexto mais rico
  mas a função `roll_loot` de `services/economy.py` **não muda**.
- `agents/archivist.py` — recebe `ConflictSummary` como fonte de fatos a
  persistir (memória curto/longo prazo), no lugar de inferir do log de combate
  bruto.

**Schema:**
```python
class ConflictSummary(TypedDict):
    participantes: List[str]
    sobreviventes: List[str]
    mortos: List[str]
    inconscientes: List[str]
    rendidos: List[str]
    fugitivos: List[str]
    capturados: List[str]
    ferimentos: Dict[str, List[Dict]]
    cicatrizes_a_gerar: List[str]
    recursos_gastos: Dict[str, int]
    cartas_descobertas: List[str]
    resistencias_descobertas: List[str]
    objetos_utilizados: List[str]
    mudancas_permanentes_cenario: List[str]
    companheiros_separados: List[Dict]
    decisoes_morais: List[str]
    fatos_de_relacao: List[str]
    loot_obtido: List[Dict]
    estado_final_party: Dict
```

## 4. Plano passo a passo

### Etapa 1 — `ConflictSummary` + `build_summary`
1. **Testes** (`tests/test_conflito_resumo.py`): `test_build_summary_cobre_todos_os_campos`;
   `test_summary_reflete_mortos_rendidos_fugitivos_corretamente`.
2. **Implementação:** `services/conflict_summary.py`.

### Etapa 2 — Integração com `loot_node`
1. **Testes:** `test_loot_recebe_conflict_scene_resolvido`; `test_roll_loot_nao_muda_assinatura`
   (garante que `economy.py` não foi tocado desnecessariamente).
2. **Implementação:** `agents/loot.py`.

### Etapa 3 — Entrega à narrativa (archivist/storyteller)
1. **Testes:** `test_narrativa_nao_pode_reverter_fato_do_resumo` (teste de
   contrato/validação, não de LLM real); `test_archivist_persiste_fatos_do_resumo`.
2. **Implementação:** `agents/archivist.py`.

## 5. Critérios de aceite

- [ ] Combate/perseguição/loot resolvem 100% sem LLM antes do resumo existir.
- [ ] Resumo canônico cobre todos os campos de R2.
- [ ] `economy.py`/`roll_loot` continuam funcionando sem reescrita desnecessária.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

1. Conflito real com 1 morto, 1 rendido, 1 fugitivo, loot obtido — confirmar a
   narração pós-combate cita os fatos corretos e não inventa desfecho diferente.
2. Confirmar `archivist` persiste os fatos de relação corretamente na memória de
   sessão.

## 7. Riscos & compatibilidade

- Risco principal é reescrever `economy.py` sem necessidade — a spec explicitamente
  proíbe isso (doc de escopo: "loot atual deve ser integrado, não recriado").
- `ConflictSummary` é o contrato entre motor determinístico e LLM — qualquer
  campo faltante aqui vira um "fato perdido" na narrativa; revisar contra a lista
  completa do doc 01 §35 antes de fechar `done`.
