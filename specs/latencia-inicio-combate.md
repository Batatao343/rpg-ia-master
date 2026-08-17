# SPEC — Latência do início de combate

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `observabilidade-latencia-nos`

## 1. Contexto & objetivo

O início real concentra 27–35 s e usa uma chamada FAST para inventar geometria
antes de o motor Python congelar a cena. Mecânica não deve depender dessa chamada.

## 2. Requisitos

- **R1** — Cena base é construída deterministicamente em Python com zonas,
  posições e nível de encontro válidos.
- **R2** — Nenhum invoke FAST exclusivo de preparação ocorre no start.
- **R3** — Scanner/bestiário e narração existentes permanecem resilientes.
- **R4** — Cobertura de objetos/posições e todos os testes de conflito seguem verdes.

## 3. Design

`_prepare_scene` usa `fallback_safe_scene(ctx)` como construtor canônico. A LLM
continua identificando/narrando; números, zonas mínimas e posições são Python.

## 4. Aceite

- [x] Uma chamada FAST a menos por início.
- [x] Cena válida e congelada.
- [x] Longrun mostra preparação mecânica barata; smoke real geral segue verde.
- [x] `uv run pytest` verde.

## 5. Evidência

O contrato falha se `_prepare_scene` invocar LLM. No longrun 200t, o nó de
combate ficou em p95 127 ms no MockLLM; smoke real geral 2/2 confirmou o pipeline
sem erro e sem fallback determinístico.
