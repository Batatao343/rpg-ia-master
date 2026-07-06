# SPEC — Fase 11 — LLM contract tests (provider real respeita contratos)

> **Status:** `draft`
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fases 2.6/2.8/4.x `done` (contratos que serão testados)
> **Desbloqueia:** releases com troca de provider/modelo sem regressão silenciosa

---

## 1. Contexto & Objetivo

A suíte offline força `RPG_FORCE_MOCK=1` — o MockLLM devolve instâncias
Pydantic válidas, então **bug de mapeamento de campo nunca quebra no mock**
(lição repetida em toda fase: 4 bugs no smoke da Fase 4, 3 na Fase 6, todos
invisíveis offline). Hoje a validação real é artesanal: smoke manual por spec
+ `tests/test_real_llm.py` (4 testes, ~7-10 requests). Cada troca de modelo
(`llm_setup.py`) ou de provider (`LLM_PROVIDER`) re-expõe o projeto aos mesmos
riscos sem checklist executável.

Esta spec transforma o smoke artesanal em **suíte de contrato**: testes
pytest marcados (`-m llm_contract`), skip automático sem chave, orçamento
explícito de requests por teste (soma ≤ 15, dentro do free tier de 20/dia por
modelo), 1 assert de CONTRATO por teste (schema/estrutura, não qualidade de
prosa). Fica fora do CI padrão (validate.yml roda offline); roda sob demanda
antes de release/troca de modelo.

Princípio: **LLM propõe, motor valida** — os contratos testados são exatamente
os pontos onde o motor confia no shape da resposta.

## 2. Requisitos

- **R1 — Marker + skip:** testes em `tests/test_contracts_llm.py` com
  `pytestmark = [pytest.mark.llm_contract, skipif(sem GOOGLE_API_KEY)]`;
  `pytest.ini`/`pyproject` registra o marker; suíte offline NÃO os coleta por
  default (`addopts` com `-m "not llm_contract"` OU manter skip + ignore no
  CI — decidir na implementação, documentar).
- **R2 — Orçamento:** constante `_BUDGET` por teste no docstring; soma total
  ≤ 15 requests; cada teste usa o tier mais barato que prova o contrato (FAST
  sempre que possível).
- **R3 — Contratos cobertos** (1 teste cada):
  1. **Router:** frase de combate inequívoca → `route == "COMBAT"`; frase de
     fala com NPC → `route == "NPC"` + `active_npc_name` preenchido.
  2. **Structured events (2.6):** turno com mudança de mundo óbvia → proposta
     parseia como `ProposedWorldEvent` e passa em `world_validators` OU turno
     banal → lista vazia (sem alucinação de evento).
  3. **Combat parse:** ação "ataco o lobo com a espada" → `CombatAction` com
     `action_type` válido e alvo casando inimigo em cena por id.
  4. **NPC não-onisciência:** npc_actor com contexto SEM um fato → resposta
     não contém o fato (usa fato sintético injetável, não lore real — verificável
     por substring).
  5. **Loot/trade intent (4.4):** "compro a poção" → `TradeIntent` com
     `intent="buy"` e item resolvido por id canônico.
  6. **Archivist:** resumo não perde entidade crítica (nome do player e local
     atual presentes no `narrative_summary` novo).
  7. **Fallback:** com `RPG_NO_MOCK=1` e chave inválida → turno completa com
     mensagem de fallback e estado íntegro (nenhum campo corrompido) — este é
     offline de fato (não gasta quota).
- **R4 — Structured output com guard:** cada teste que usa
  `with_structured_output` asserta `isinstance(resultado, Schema)` — se o
  provider devolver `AIMessage` (fallback), o teste FALHA com mensagem clara
  ("provider caiu no fallback — quota?") em vez de estourar atributo.
- **R5 — Relatório de custo:** fixture de sessão conta requests feitas
  (wrapper em `get_llm`) e imprime no teardown: `[CONTRACT] N requests
  consumidas` — visível no `-s`.
- **R6 — Doc:** seção curta em `ESTADO_ATUAL.md` (como rodar:
  `uv run pytest -m llm_contract -v -s`) e nota no `CLAUDE.md` § comandos.

### Fora de escopo

- Avaliação de QUALIDADE narrativa (LLM-as-judge) — só shape/contrato.
- Rodar contratos no CI (quota + flakiness de rede; CI continua offline).
- Providers além do configurado no `.env` (matriz multi-provider é manual).
- Substituir os smokes por spec — contrato cobre o transversal, smoke de
  feature nova continua obrigatório (workflow § spec-driven).

## 3. Design técnico

### Arquivos novos

- `tests/test_contracts_llm.py` — os 7 contratos.

### Arquivos alterados

- `pyproject.toml` (ou `pytest.ini`) — registra marker `llm_contract`.
- `tests/conftest.py` — **cuidado:** hoje força `RPG_FORCE_MOCK=1` para tudo;
  os testes de contrato precisam de opt-out (fixture que remove a env var
  quando o marker está presente — `request.node.get_closest_marker`).
- `ESTADO_ATUAL.md` / `CLAUDE.md` — como rodar.

### Esqueleto

```python
import pytest

pytestmark = pytest.mark.llm_contract

@pytest.fixture(autouse=True)
def _real_llm(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    # invalida caches de llm_setup se houver

def test_router_classifica_combate():  # _BUDGET: 1 request FAST
    state = _estado_minimo(acao="Desembainho a espada e ataco o goblin!")
    out = dm_router_node(state)
    assert out.get("route") == "COMBAT"
```

`tests/test_real_llm.py` atual: migrar os 4 testes existentes para o arquivo
novo com o marker (aposentar o `--ignore` hardcoded do `/qa` e do CI depois
que o marker excluir por default).

## 4. Plano passo a passo

### Etapa 1 — Infra de marker + opt-out do mock

1. **Testes:** `test_marker_excluido_da_suite_offline` (subprocess: `pytest
   --collect-only -q` default não coleta `llm_contract`);
   `test_optout_do_mock_dentro_do_marker` (fixture remove a env).
2. **Implementação:** marker + fixture + contador de requests.
3. **Verificação:** `/qa` verde (offline inalterada).

### Etapa 2 — Contratos 1-3 (router, eventos 2.6, combate)

1. **Testes:** os próprios contratos (só rodam com chave).
2. **Verificação:** `uv run pytest -m llm_contract -v -s` com chave real —
   anotar requests consumidas.

### Etapa 3 — Contratos 4-7 (NPC, trade, archivist, fallback)

1. Idem; contrato 7 roda offline (chave inválida proposital + `RPG_NO_MOCK=1`).
2. **Verificação:** suíte offline verde + contratos verdes com chave.

### Etapa 4 — Migrar test_real_llm.py + docs

1. Mover os 4 testes existentes para o marker; atualizar `/qa` skill e
   `validate.yml` (trocar `--ignore` por exclusão de marker, se adotada).
2. Docs (R6).

## 5. Critérios de aceite

- [ ] `uv run pytest` offline não coleta/roda nenhum contrato (zero rede)
- [ ] `uv run pytest -m llm_contract -v -s` com chave: 7 contratos, ≤15 requests, contador impresso
- [ ] Contrato falha LEGÍVEL quando provider cai no fallback (não AttributeError)
- [ ] Contrato 7 (fallback) roda sem chave e passa
- [ ] `test_real_llm.py` migrado (arquivo antigo removido)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM nos testes (isinstance — R4)
- [ ] Saves antigos continuam carregando (nada de runtime muda)

## 6. Smoke test com LLM real

A spec É o smoke. Execução única com chave real = critério de aceite 2.
Registrar no `CHANGELOG.md` a contagem de requests da primeira rodada verde.

## 7. Riscos & compatibilidade

- **Flakiness de LLM real:** contratos assertam shape, não texto — mas router
  pode errar classificação borderline; usar frases inequívocas e aceitar 1
  retry manual (documentado; sem retry automático para não estourar quota).
- **Quota:** 15 requests distribuídas entre FAST/SMART; rodar contratos e
  smoke de feature no MESMO dia pode estourar 20/dia — rodar em dias separados.
- **conftest global:** o opt-out do mock é o ponto delicado — testar que a
  suíte offline continua 100% mockada (contrato de isolamento na Etapa 1).
- **Saves antigos / MockLLM:** sem impacto.
