# SPEC — Grounding de posse do inventário na memória

> **Status:** `done` ? aceite local e smoke real DeepSeek verdes em 2026-09-28.
> **Criada:** 2026-08-28 · **Atualizada:** 2026-09-17
> **Depende de:** `grounding-local-memoria-canonica` (`in-progress`)
> **Desbloqueia:** conclusão da matriz B de playtest real

---

## 1. Contexto & Objetivo

Na terceira tentativa da matriz B, o storyteller recusou corretamente “Diário da
Casa Vesper” e uma chave desconhecida, mas turnos depois o archivist registrou que
o viajante carregava esses objetos. A prosa rejeitada não pode se tornar estado
mecânico por meio da memória.

O motor deve manter a autoridade do inventário Python, lembrar recusas de item de
forma durável e colocar fatos/resumos antigos contraditórios em quarentena.

## 2. Requisitos

- **R1** — Itens recusados pelo storyteller entram num ledger persistido, único e limitado.
- **R2** — Alegação explícita de posse pelo jogador é recusada se citar item recusado ou item canônico ausente do inventário.
- **R3** — Se o item for obtido legitimamente depois, a posse passa a ser válida.
- **R4** — Alegações sobre posse de NPC não são confundidas com posse do jogador.
- **R5** — Resumo, ledger e memória vetorial legados contraditórios não entram no contexto.
- **R6** — O playtest emite erro observável ao surgir nova memória de posse fantasma.
- **R7** — Saves antigos carregam com ledger vazio.

### Fora de escopo

Extração genérica de entidades de qualquer frase e alteração das regras de loot.

## 3. Design técnico

- `state.py`/`persistence.py` — `rejected_item_claims: List[str]`, máximo 100.
- `agents/storyteller.py` — acumula nomes recusados no ledger.
- `services/memory_provenance.py` — detecta e sanitiza contradições de posse.
- `agents/archivist.py` — ancora o prompt no inventário e sanitiza fatos/resumo.
- `services/context_builder.py` — quarentena no contexto.
- `playtest/invariants.py` — `memory.inventory_grounding`.

## 4. Plano passo a passo

1. **Testes:** reproduzir o fato da campanha, posse válida, posse de NPC, roundtrip e invariante.
2. **Implementação:** ledger durável, validador, sanitização e prompt ancorado.
3. **Verificação:** testes focados, suíte completa e nova tentativa da matriz B.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

Sujeito e verbo afirmativo devem ser diretos. Negações e relato sobre posse de
NPC não são posse do jogador; uma oração coordenada com outro sujeito encerra
a lista de objetos atribuída ao player. Nomes são comparados com fronteiras de
palavra. Plano/gates no [adendo pré-matriz](SPEC-162-remediacao-local-contratos-pre-matriz.md).

- [x] O fato real “O viajante carrega: diário...” é recusado.
- [x] Item presente no inventário é aceito, mesmo se recusado anteriormente.
- [x] Contexto e resumo não propagam posse fantasma.
- [x] Invariante dedicado cobre regressão sem long run.
- [x] Saves antigos continuam carregando.
- [x] `uv run pytest` verde (17/09: 1681 passed, 16 skipped, 14 deselected).
- [x] Smoke real dirigido de inventário/memória confirma integração; B integral é gate global separado.

## 6. Smoke test com LLM real

Gate bloqueado por HTTP 402 DeepSeek; evidência histórica e retomada em
[fechamento local](../docs/fechamento-local-2026-09-17.md).

1. Repetir a matriz B com DeepSeek sem fallback determinístico.
2. Confirmar zero `memory.inventory_grounding` e ausência de posse fantasma no relatório.

## 7. Riscos & compatibilidade

- A detecção é deliberadamente estreita: apenas sujeito jogador + verbo explícito de posse.
- Ledger limitado evita crescimento do save; inventário atual sempre prevalece sobre recusa antiga.
- Não adiciona chamadas de LLM nem custo/latência de rede.


## Fechamento real ? 2026-09-28

Matriz real n?o registrou memory.inventory_grounding nem posse fantasma.
Evid?ncia consolidada: [matriz B](../docs/playtest-matriz-b-2026-09-28.md), `20260927-214549-731406` e `20260928-084057-102826`. A matriz global incompleta permanece responsabilidade exclusiva da SPEC-128.
