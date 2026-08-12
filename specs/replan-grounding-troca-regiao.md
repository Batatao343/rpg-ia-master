# SPEC — Replanejamento e grounding na troca de região

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `balanceamento-early-game` e campaign manager (`done`)
> **Desbloqueia:** exploração livre sem transplante de arcos

---

## 1. Contexto & Objetivo

Ao viajar de Nova Arcádia para Brekmar com todos os beats ainda pendentes, o
campaign manager não replanejou e continuou propondo objetivos da região antiga.
A exceção criada para preservar twists acabou permitindo beats geograficamente
órfãos.

## 2. Requisitos

- **R1** — Toda troca entre regiões deve exigir replanejamento, mesmo com zero beats concluídos.
- **R2** — Viagem dentro da mesma região não deve replanejar apenas por mudança de local.
- **R3** — O `campaign_plan.location` persistido deve ser ancorado no local canônico atual, nunca no texto livre do LLM.
- **R4** — O invariante deve detectar plano regional obsoleto após o turno de tolerância da própria viagem.

### Fora de escopo

Gerar novos mapas ou validar cada substantivo citado na prosa de um beat.

## 3. Design técnico

- **`agents/campaign_manager.py`** — política de replan e âncora canônica.
- **`playtest/invariants.py`** — auditoria de plano obsoleto.
- **`tests/test_replan_grounding_regional.py`** — troca inter/intrarregional e resposta LLM divergente.

## 4. Plano passo a passo

1. **Testes:** expressar os três casos de replan e a âncora canônica.
2. **Implementação:** simplificar a decisão determinística e sobrescrever somente o campo de localização.
3. **Verificação:** testes de campaign manager e invariantes verdes.

## 5. Critérios de aceite

- [x] Mudança de região sempre replana no turno seguinte.
- [x] Movimento local preserva o arco.
- [x] Planos novos são ancorados no local atual.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard existente de structured output preservado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Viajar com todos os beats pendentes para outra região.
2. Executar uma ação local e confirmar novo plano ancorado no destino.

Executado no smoke real `20260812-172526-505951`: Nova Arcádia → Brekmar
replanejou, inclusive com fallback estruturado DeepSeek → Groq.

## 7. Riscos & compatibilidade

O replan adiciona requests SMART apenas quando o jogador cruza uma região, evento deliberadamente raro.
