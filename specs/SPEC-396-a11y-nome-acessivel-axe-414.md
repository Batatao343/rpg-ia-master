# SPEC-396 — A11y: nome acessível contém o texto visível (destrava axe-core 4.14, PR #55)

> **Status:** `draft` (reservada 04/11; corpo a escrever)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Origem:** PR #55 do Dependabot (lote npm: `@axe-core/playwright` 4.10.2→4.14.0, `typescript-eslint` 8.72.1, `vite` 8.3.5). Com o 4.14, a regra `label-content-name-mismatch` (WCAG 2.5.3 *Label in Name*) passa a valer: 87 falhas no e2e completo (04/11), **todas** dessa regra; 354 passam. Exemplos: `effects.spec.ts` (ctrl.pending, mira, card.arm, tab.indicator, map.marker), `combat-gesture.spec.ts`, `critical-journeys.spec.ts` F06/F35.
> **Escopo:** corrigir os `aria-label` que não contêm o texto visível (ou trocar por `aria-labelledby`/texto visível) e pousar o bump do PR #55 junto, com o pin `tests/test_eval_frontend.py` (`^4.14.0`). Sem desligar a regra.
> **Depende de:** nada · **Desbloqueia:** PR #55
> **Risco:** `médio` (UI pública; sem mudança de comportamento de jogo)
> **Evidência:** e2e completo com axe 4.14: 0 violação `label-content-name-mismatch`.

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
