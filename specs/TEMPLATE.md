# SPEC — <Título curto da feature/fase>

> **Status:** `draft` | `approved` | `in-progress` | `done`
> **Criada:** YYYY-MM-DD · **Atualizada:** YYYY-MM-DD
> **Depende de:** <specs anteriores que precisam estar `done`>
> **Desbloqueia:** <specs/features que dependem desta>

---

## 1. Contexto & Objetivo

Por que esta spec existe. Qual problema resolve. 2-4 parágrafos no máximo.
Referência ao princípio de arquitetura relevante (ver `ROADMAP.md` § Princípios).

## 2. Requisitos

Numerados, testáveis. Cada requisito deve poder virar assert.

- **R1** — ...
- **R2** — ...

### Fora de escopo

Lista explícita do que esta spec NÃO cobre (anti-scope-creep).

## 3. Design técnico

Detalhe suficiente para uma sessão futura de IA implementar **sem reler o roadmap**:

- **Arquivos novos** — caminho + responsabilidade
- **Arquivos alterados** — o que muda em cada um
- **Schemas** — Pydantic/TypedDict completos (campos, tipos, defaults)
- **Assinaturas** — funções públicas com tipos
- **Formatos de dados** — JSON/frontmatter com exemplo real (usar IDs canônicos do projeto, não inventados)

## 4. Plano passo a passo

Etapas ordenadas e testáveis. **Testes primeiro** (TDD): cada etapa nomeia os
testes a escrever ANTES do código e o que cada um asserta.

### Etapa N — <nome>

1. **Testes** (`tests/test_<...>.py`): `test_x` asserta ...; `test_y` asserta ...
2. **Implementação:** ...
3. **Verificação:** `uv run pytest` verde.

## 5. Critérios de aceite

Checklist objetivo. A spec só vira `done` com todos marcados.

- [ ] ...
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM em todo `with_structured_output` novo (try/except ou isinstance)
- [ ] Saves antigos continuam carregando

## 6. Smoke test com LLM real

Checklist manual curto (3-5 requests, dentro da quota Gemini de 20/dia/modelo).
MockLLM esconde bugs de mapeamento de campo — este passo é obrigatório antes de `done`.

1. ...
2. ...

## 7. Riscos & compatibilidade

- Compatibilidade com saves antigos: ...
- Comportamento no MockLLM / FallbackLLM: ...
- Impacto em quota/latência: ...
