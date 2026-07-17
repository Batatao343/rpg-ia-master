# SPEC — Polish de prosa: anti-repetição, voz e menu de opções

> **Status:** `draft`
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** —
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achado H) — três tiques de prosa que corroem a
imersão em sessão longa:

1. **Aberturas repetitivas em combate:** "O ar fétido do pântano queima em suas
   narinas" abriu 3 turnos seguidos (combate t8–t11); estrutura de parágrafo
   idêntica turno após turno.
2. **Voz narrativa quebra na morte/downed:** o jogo inteiro é 2ª pessoa
   ("você"), mas as narrações de queda mudam pra 3ª ("o herói", "o viajante",
   "o explorador") — explorador t47, combate t13.
3. **Menu de opções inconsistente:** o fecho com opções concretas ("— Desce
   pra investigar? — Corre pro quartel? — Ou outra ação?") apareceu no quester
   t1 e é ótimo pra jogabilidade, mas some na maioria dos turnos.

Tudo é prompt/pós-processamento — zero mecânica nova.

## 2. Requisitos

- **R1** — Prompts de narração (storyteller e combate) recebem as **duas
  últimas aberturas de narração** (primeiras ~12 palavras de cada) com a
  instrução "NÃO comece com estrutura ou imagem parecida".
- **R2** — Prompts de narração de morte/downed exigem **2ª pessoa** ("você"),
  proibindo explicitamente "o herói/o viajante/o aventureiro". Vale pro
  texto determinístico do Saque também (revisar strings fixas em
  `agents/combat.py` — o memorial "Playtest-X, ... caiu em ..." é da crônica e
  pode ficar em 3ª, mas a NARRAÇÃO do turno não).
- **R3** — Storyteller fecha turnos de exploração/história com 2–3 opções
  concretas + "ou outra ação" quando NÃO há combate ativo (em combate as
  opções mecânicas já vêm dos chips `combat_suggestions`). Instrução de
  prompt com formato fixo (linhas iniciando com "—").
- **R4** — Verificação barata anti-repetição (determinística, pós-LLM): se a
  narração nova começa com as mesmas 6 palavras da anterior, logar
  `rpg.prose` warning (sem re-tentar — telemetria pra medir, não punir).
- **R5** — Invariante de playtest `narrative.repeated_opening` (`warning`):
  3 turnos consecutivos com abertura de 6 palavras iguais.

### Fora de escopo

- Re-tentar geração por estilo (custo/latência dobra — só medir por ora).
- Mudar comprimento/temperatura da narração.
- Tradução/idioma (spec beats-visibilidade-ptbr).

## 3. Design técnico

- **`agents/storyteller.py` / `agents/combat.py`** — R1: helper
  `ultimas_aberturas(messages, n=2) -> list[str]` (módulo novo
  `services/prose_guard.py` p/ reuso); injetar no prompt. R2/R3: cláusulas de
  prompt. R4: comparação pós-invoke + log.
- **`services/prose_guard.py`** (novo) — `opening(text, words=6) -> str`,
  `ultimas_aberturas(...)`, `repeats(a, b) -> bool`. Puro, sem LLM.
- **`playtest/invariants.py`** — R5 usando `prose_guard`.

## 4. Plano passo a passo

### Etapa 1 — prose_guard + injeção no prompt
1. **Testes** (`tests/test_prose_guard.py`): `test_opening_normaliza`
   (caixa/pontuação); `test_repeats`; `test_prompt_recebe_aberturas`
   (prompt do storyteller contém as aberturas anteriores — via mock).
2. **Implementação:** módulo + injeção nos 2 agentes.
3. `uv run pytest` verde.

### Etapa 2 — voz + menu
1. **Testes:** `test_prompt_morte_exige_segunda_pessoa` (cláusula presente);
   `test_prompt_exploracao_pede_opcoes` e
   `test_prompt_combate_nao_pede_opcoes`.
2. **Implementação:** cláusulas condicionais.
3. `uv run pytest` verde.

### Etapa 3 — telemetria/invariante
1. **Testes:** `test_invariante_repeated_opening` (fixture 3 aberturas iguais).
2. **Implementação:** R4 log + R5 check.
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [ ] R1–R5 com testes
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Smoke real (abaixo) sem regressão de qualidade percebida
- [ ] Saves antigos continuam carregando (nada de estado novo)

## 6. Smoke test com LLM real

1. 6+ turnos de combate real seguidos: aberturas distintas entre turnos
   consecutivos (olhar transcript).
2. Forçar downed: narração do turno em 2ª pessoa.
3. 3 turnos de exploração: fecho com opções concretas em ≥2 deles.

## 7. Riscos & compatibilidade

- Instrução demais no prompt pode engessar a prosa — cláusulas curtas, medir
  com `rpg.prose`/invariante ANTES de escalar pra re-tentativa.
- MockLLM devolve texto fixo → R4/R5 dispararão no mock; invariante fica
  `warning` (não quebra suíte) e o teste do harness mock ignora esse check
  (whitelist no runner, como já há p/ checks REAL-only, se necessário).
- Chips de combate (polish-sessao) seguem como única fonte de opção mecânica.
