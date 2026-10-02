# SPEC — Capacidade de provider antes de longrun real

> **Status:** `done`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A `20260820-134236-013629`

## 1. Problema

O baseline tentou dez campanhas, mas só duas completaram. DeepSeek ficou sem
saldo, Gemini sem créditos, Anthropic rejeitou prefill e Groq excedeu 8.000 TPM;
o fallback caro levou oito campanhas ao cap entre 11 e 53 turnos. O harness
iniciou um experimento sabidamente incapaz de completar e o cap pôde ultrapassar
US$ 0,25 no turno final.

## 2. Requisitos

- **R1:** `matrix-suite --real` executa preflight estruturado nos três tiers antes
  de criar o manifesto; falha não inicia campanha.
- **R2:** presets explícitos isolam a capacidade usada pelo experimento:
  `groq-free` fixa CLASSIFY no 20b e FAST/SMART no 120b, com fallback
  intra-provider para o 20b; `deepseek-paid` fixa os três tiers em
  `deepseek-v4-flash`. Nenhum preset inclui MockLLM ou mistura contas/providers.
- **R3:** o harness pode espaçar sucessos Groq 120b por intervalo configurável,
  apenas em playtest real, para respeitar TPM sem alterar o motor de produção.
- **R4:** manifesto registra preset e intervalo; A↔B repete ambos.
- **R5:** cap continua obrigatório e o console mostra teto por campanha/agregado.
- **R6:** nenhuma imagem é gerada e nenhuma chave/erro sensível entra no relatório.
- **R7:** structured output OpenAI-compat cujo histórico termina em `AIMessage`
  recebe uma instrução humana neutra para impedir continuação textual sem tool call.

## 3. Aceite

- [x] Preflight fake cobre sucesso/falha nos três tiers.
- [x] Regressão prova que prefill por `AIMessage` termina em tool call estruturado.
- [x] Preset contém somente Groq e não usa MockLLM.
- [x] Preset `deepseek-paid` contém somente DeepSeek V4 Flash nos três tiers;
  preflight real CLASSIFY/FAST/SMART verde em 2026-08-20.
- [x] Pacer não atua no mock nem em outro modelo e espaça 120b no real.
- [x] Matrix curta offline e suíte completa verdes.
- [x] Matriz A real completou 10×200; falhas estruturadas foram recuperadas sem invocação terminal.

> **Evidência negativa A1:** `20260820-155300-494278` foi interrompida após o
> primeiro par revelar 707 falhas/796 tentativas e 146 turnos sem sucesso de
> rede. A proteção fail-closed agora impede repetição; capacidade externa segue
> necessária para cumprir o último aceite.
