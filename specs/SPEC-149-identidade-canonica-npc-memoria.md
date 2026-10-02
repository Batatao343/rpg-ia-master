# SPEC — Identidade canônica de NPC na sessão e memória

> **Status:** `done` ? aceite local e smoke real DeepSeek verdes em 2026-09-28.
> **Criada:** 2026-08-31 · **Atualizada:** 2026-09-17
> **Depende de:** `encontros-dedupe`, `grounding-local-memoria-canonica`
> **Desbloqueia:** reinício da matriz B real

---

## 1. Contexto & Objetivo

Na matriz B `20260831-161803-462254`, Skriit Mil-olhos foi criado como goblin
pequeno, mas o archivist persistiu que ele era um homem alto. A mesma sessão
também passou a conter duas chaves para o mesmo `id` de NPC após reintrodução:
`Skriit Mil-olhos` e `npc_skriit_mil_olhos`.

Uma entidade deve ter uma única ficha mecânica por sessão, e fatos de memória
não podem contrariar seus traços identitários canônicos.

## 2. Requisitos

- **R1** — Referências por chave, nome ou ID resolvem a mesma ficha ignorando acento/pontuação e prefixos técnicos.
- **R2** — Reintrodução de NPC de cache atualiza a ficha existente; nunca cria segunda chave para o mesmo `id`.
- **R3** — Load/save coalesce duplicatas legadas sem perder estado dinâmico recente.
- **R4** — Fato/resumo que troca espécie ou porte explícito do NPC é recusado e auditado.
- **R5** — Contexto não devolve memória vetorial/ledger legado com identidade contraditória.
- **R6** — Prompt do archivist recebe âncoras de aparência dos NPCs presentes.
- **R7** — Playtest acusa nova duplicata mecânica ou memória de identidade divergente.

### Fora de escopo

Reconhecimento semântico genérico de toda característica de personalidade e
alterações legítimas de roupa, ferimentos ou envelhecimento.

## 3. Design técnico

- `services/entity_identity.py`: resolução/coalescência de NPCs runtime.
- `agents/storyteller.py`: segundo lookup após a fábrica/cache.
- `agents/npc.py`/`party.py`: ator e recrutamento resolvem nome/chave/ID antes
  de consultar/criar ficha ou verificar participação no grupo.
- `persistence.py`: normalização de saves antigos e escritos novos.
- `services/memory_provenance.py`: `npc_identity_contradiction` e sanitização.
- `agents/archivist.py`/`services/context_builder.py`: âncora e quarentena.
- `playtest/invariants.py`: `entity.npc_duplicate_identity` e `memory.npc_identity_grounding`.

## 4. Plano passo a passo

1. Escrever regressões com a ficha/fato exatos de Skriit.
2. Implementar identidade runtime e coalescência migration-safe.
3. Implementar grounding de memória/resumo/contexto e invariantes.
4. Rodar testes focados, suíte completa e reiniciar B desde o par 1.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

Aliases viram metadados persistidos. Coalescência une componentes transitivos,
inclusive uma ficha-ponte entre dois grupos anteriores, sem perder os nomes/IDs
descartados. As seis permutações de três fichas são testadas com roundtrip e
idempotência; identidade antiga e dinâmica recente permanecem separadas.
Gates no [adendo pré-matriz](SPEC-162-remediacao-local-contratos-pre-matriz.md).

- [x] Reintroduzir `npc_skriit_mil_olhos` mantém uma única chave/ficha.
- [x] “Skriit (homem alto...)” é recusado; “Skriit, goblin pequeno...” passa.
- [x] Duplicata legada é coalescida no roundtrip.
- [x] Contexto não expõe fato contraditório.
- [x] Invariantes curtas cobrem ambos os defeitos.
- [x] `uv run pytest` verde (17/09: 1681 passed, 16 skipped, 14 deselected).
- [x] Smoke real dirigido de reintrodução por alias confirma integração; B integral é gate global separado.

## 6. Smoke test com LLM real

Reiniciar a matriz B; o perfil explorador deve atravessar reintroduções sem
duplicata e sem `memory.npc_identity_grounding`.

## 7. Riscos & compatibilidade

A detecção semântica é estreita a espécie/porte explícitos. A coalescência
preserva identidade da ficha com `created_turn` mais antigo quando ambas têm
datas confiáveis; sem essas datas, mantém a primeira identidade. O estado
dinâmico segue a ocorrência mais recente. Isso não infere qual aparência é
verdadeira quando não há evidência de origem. A invariante compara todos os
aliases, inclusive nome igual com IDs distintos. Testes locais passaram;
o [gate real](../docs/fechamento-local-2026-09-17.md) permanece bloqueado por saldo.


## Fechamento real ? 2026-09-28

Reintrodu??o real resolveu Mulher de unhas pretas para Mulher de xale pu?do, sem duplicata ou memory.npc_identity_grounding.
Evid?ncia consolidada: [matriz B](../docs/playtest-matriz-b-2026-09-28.md), `20260927-214549-731406` e `20260928-084057-102826`. A matriz global incompleta permanece responsabilidade exclusiva da SPEC-128.
