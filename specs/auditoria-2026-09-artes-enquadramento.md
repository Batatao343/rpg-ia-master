# SPEC — Artes integrais, cards e visualização ampliada

> **Status:** `in-progress`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** Nenhuma
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

A auditoria em 1440×1000 e 390×844 mediu retratos 719×1079 em caixas 248×186: cover recorta aproximadamente metade da altura. A cascata CSS também zera a margem de card__art e reativa sua legenda; a figura ultrapassa o card em 16 px. Cenários usam banners baixos e retratos narrativos têm max-height com cover.

## 2. Requisitos

- **R1** — Raças, classes e retratos narrativos preservam toda a imagem (contain), com fundo coerente e sem distorção; nenhuma regeneração de arte.
- **R2** — Figura permanece dentro do card e nome é mostrado uma só vez, em desktop e 390 px.
- **R3** — Banner de cenário pode continuar panorâmico; deve oferecer visualização integral acessível em diálogo, assim como retratos. Escape fecha e devolve foco ao acionador; backdrop não bloqueia leitura após fechamento.
- **R4** — Falha de uma imagem não contamina a próxima: reset por asset_id/URL; SceneArtwork tem fallback sem imagem quebrada.
- **R5** — sizes corresponde ao espaço real (card versus narrativa); não carregar a resolução de painel para todo card. Sem novas dependências.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

web/src/styles.css: escopo específico para card__art, portrait e banner; evitar conflitos de especificidade. VisualArtwork.tsx e SceneArtwork.tsx: componente compartilhado de ampliação, controles de teclado e fallback. Prop de apresentação opcional: variant: "card" | "portrait" (default "portrait"); chamadas antigas seguem válidas. Imagens originais/catálogo permanecem imutáveis.

## 4. Plano passo a passo

1. Testes Python/Playwright opt-in em tests/test_frontend_visual_contracts.py: medir bounds, object-fit, proporção, legendas e overflow em 390/1440 px.
2. Corrigir CSS antes de adicionar ampliação; comparar a mesma raça/classe nas capturas.
3. Testar abertura/fechamento, teclado, erro de rede seguido de troca de asset; build e checklist React após editar componentes.
4. Executar suíte offline, build e smoke navegador real com API mock isolada.

## 5. Critérios de aceite

- [x] R1/R2: imagens integrais e cards sem transbordamento.
- [ ] R3/R4/R5: ampliação, acessibilidade, recuperação e resolução adequadas.
- [x] Build, suíte offline e smoke visual desktop/mobile verdes (lote CSS; repetir após R3–R5).

## 6. Smoke test com LLM real / integração aplicável

Não usa LLM nem altera contrato de provider. Smoke real desta spec é navegador local com arquivos reais e API mock, sem geração paga. Não depende da matriz B.

## 7. Riscos & compatibilidade

Mudar proporção aumenta altura dos cards; preservar navegação e leitura mobile. Sem migração de saves.

## Execução — 23/09

Primeiro lote: retratos com contain; cards com proporção 2:3; especificidade corrigida para margens e legenda. Banner panorâmico permanece intencionalmente cover, ainda sem ampliação. R3–R5 pendentes.

Regressão visual falhou nos dois viewports antes do ajuste e passou depois: `RPG_VISUAL_BROWSER=1 uv run pytest tests/test_frontend_visual_contracts.py` → **2 passed**, Chromium real. Smoke da aplicação com artes reais, API mock isolada e navegador em 1440/390 px confirmou enquadramento, limites do card e legenda única; console sem erros. Build verde; suíte completa **1743 passed, 18 skipped, 14 deselected**. Os dois testes visuais são opt-in e não estão incluídos nos 1743.

## Execução — 26/09 (prevalece sobre as pendências históricas)

Implementados diálogo compartilhado com Escape/retorno de foco, fallback por asset/URL, sizes por apresentação e cards sem botões aninhados. Gate visual Chromium 390/1440 e fluxo autenticado passaram. Falta a regressão explícita de falha de rede seguida de troca de asset/cenário; não encerrar R4 só pelo caminho feliz.
