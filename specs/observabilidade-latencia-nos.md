# SPEC — Observabilidade de latência por nó

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `fase-5.3-telemetria` (`done`)
> **Desbloqueia:** otimização orientada por evidência

---

## 1. Contexto & Objetivo

O harness media apenas a latência total do turno e dos providers. Para localizar
gargalos de grafo, precisa atribuir o intervalo observado entre updates aos nós
executados e agregar percentis sem instrumentar os agentes individualmente.

## 2. Requisitos

- **R1** — Cada `TurnRecord` guarda `node_latency_ms` por nó.
- **R2** — Streaming mede o tempo monotônico entre updates; wrappers sem stream
  registram a duração do `invoke` sob a rota observada.
- **R3** — O summary agrega count, média, p50, p95 e máximo por nó.
- **R4** — A instrumentação não muda ordem, estado ou quantidade de chamadas LLM.

### Fora de escopo

- Otimizações especulativas antes de dados; tracing distribuído externo.

## 3. Design técnico

Alterações restritas a `playtest/runner.py`, `playtest/telemetry.py` e relatório.
O relógio é `time.perf_counter()`. Se um chunk trouxer múltiplos nós, o intervalo
é atribuído ao primeiro e zero aos demais, preservando o total sem duplicação.

## 4. Plano passo a passo

1. Testar stream e fallback `invoke` com relógio controlado.
2. Implementar captura e serialização JSONL.
3. Implementar agregação e seção do relatório.
4. Rodar harness curto e suíte completa.

## 5. Critérios de aceite

- [x] JSONL contém latência por nó.
- [x] Summary contém percentis por nó.
- [x] Soma aproximada não duplica tempo de um turno.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Uma campanha curta real, se a cota permitir; o smoke offline valida integralmente
a instrumentação do grafo.

Smoke `20260813-001000-370465` gerou JSONL, summary e relatório com sete nós;
`combat_agent` p95 20 ms sob MockLLM.

## 7. Riscos & compatibilidade

A medição representa tempo observado entre emissões, incluindo overhead do grafo;
é adequada para comparação, não para profiling de CPU em nanossegundos.
