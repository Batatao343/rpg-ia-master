# SPEC — Hardening de persistência, checkpoints e idempotência de turno

> **Status:** `done`
> **Criada:** 2026-08-11 · **Atualizada:** 2026-08-11
> **Depende de:** [checkpoints-morte](SPEC-060-checkpoints-morte.md) `done` · [streaming-turno-sse](SPEC-036-streaming-turno-sse.md) `done`
> **Desbloqueia:** Fase 10b e abertura segura para usuários externos

---

## 1. Contexto & Objetivo

A auditoria de 2026-08-11 confirmou que `*.checkpoint.json` entra na descoberta
de saves vivos, que a suíte offline grava em `saves/`/`data/saves_memory/` reais
e que a repetição automática SSE→POST pode aplicar a mesma ação duas vezes.
Também há escrita JSON não-atômica e rotas que ignoram falha de persistência.

O objetivo é tornar um turno local serializado, idempotente e durável, mantendo
compatibilidade com clientes que ainda não enviam `action_id`.

## 2. Requisitos

- **R1** — descoberta/listagem de saves ignora `*.checkpoint.json`.
- **R2** — excluir uma campanha remove save vivo, checkpoint e memória; um
  checkpoint órfão também pode ser removido pelo mesmo `game_id`.
- **R3** — save vivo e checkpoint usam escrita atômica no mesmo diretório.
- **R4** — falha de `save_game_state`/`save_checkpoint` vira erro explícito; a API
  não responde sucesso falso.
- **R5** — mutações do mesmo `game_id` são serializadas no processo.
- **R6** — `ActionRequest.action_id` opcional é persistido em ledger limitado;
  repetir o mesmo ID devolve o estado atual sem executar outro turno.
- **R7** — o worker SSE conclui e persiste mesmo se o consumidor desconectar;
  fallback POST reutiliza o mesmo `action_id`.
- **R8** — a suíte isola saves, checkpoints e memória de sessão em `tmp_path`.
- **R9** — `circuit_open`/`build_error` não contam como rede, falha de rede ou custo
  na telemetria da API.
- **R10** — criação valida classe, raça e região contra os catálogos canônicos.
- **R11** — CI valida Python, conteúdo e frontend; documentação descreve o sistema atual.

### Fora de escopo

- Limpeza automática dos diretórios atuais, pois saves reais e de teste estão misturados.
- Locks distribuídos, autenticação e Postgres — permanecem na Fase 10b.
- Novas features de gameplay ou arte.

## 3. Design técnico

- `persistence.py`: `_iter_live_save_files`, `_atomic_write_json`, exclusão composta
  e campo persistido `processed_action_ids`.
- `api.py`: locks por `game_id`, ledger idempotente, worker SSE dono do save,
  validação canônica e propagação de falha de escrita.
- `web/src/App.tsx`: um UUID por intenção, compartilhado por stream e fallback.
- `tests/conftest.py`: sandbox autouse para os dois diretórios de runtime.
- `tests/test_hardening_persistencia_sse.py`: regressões R1–R10.

## 4. Plano passo a passo

1. Escrever regressões de descoberta, exclusão, atomicidade e sandbox.
2. Implementar a fronteira de persistência e o ledger serializado.
3. Reestruturar SSE para persistir no worker e adicionar `action_id` no cliente.
4. Corrigir telemetria, DTOs, CI e documentação.
5. Rodar suíte completa, lint de conteúdo, build e smoke offline da API.

## 5. Critérios de aceite

- [x] Checkpoint nunca aparece em `/game/saves` nem como save mais recente.
- [x] Exclusão não deixa checkpoint/memória órfãos.
- [x] Escrita interrompida não substitui o JSON válido anterior.
- [x] Falha de persistência retorna 500 sanitizado.
- [x] Duas ações iguais com o mesmo `action_id` avançam apenas um turno.
- [x] SSE e fallback compartilham o ID e o worker salva sem depender do consumidor.
- [x] Suíte não escreve nos diretórios reais.
- [x] Telemetria não cobra skip local.
- [x] DTO rejeita opções de criação não canônicas.
- [x] `uv run pytest` verde — 1398 passed, 1 skipped, 14 deselected.
- [x] `uv run python scripts/validate_content.py` verde — 0 erro/0 aviso.
- [x] `npm run build` verde — 454 módulos.
- [x] Nenhum `with_structured_output` novo.
- [x] Saves antigos continuam carregando (`processed_action_ids=[]`).

## 6. Smoke test

Esta fatia não cria contrato LLM novo. O smoke obrigatório é offline: criar jogo,
executar ação por SSE com `action_id`, repetir via POST, confirmar um único avanço,
listar/excluir e confirmar ausência de checkpoint fantasma.

Executado pela suíte em `tests/test_hardening_persistencia_sse.py`: 10/10 verdes,
incluindo fechamento antecipado do consumidor SSE e duas mutações concorrentes.

## 7. Riscos & compatibilidade

- Clientes antigos sem `action_id` mantêm o comportamento anterior.
- O lock é process-local; múltiplos workers exigirão storage transacional na 10b.
- O ledger é limitado para não crescer indefinidamente no save.
