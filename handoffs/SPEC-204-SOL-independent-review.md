# SPEC-204 — parecer de revisão Sol independente

> **Revisor:** Sol (≡ Opus, contexto separado do executor) · **Data:** 2026-10-16
> **Escopo:** commit de implementação da SPEC-204 (shell chat + contexto, split e cinco abas).

Veredito Sol: APPROVED_WITH_FOLLOWUPS.

Verificado: nunca 3 regiões visíveis; rascunho/scroll/reação por game_id com Workspace keyed; logout/troca de dono limpam (clearOwner); workspaceStorage valida e usa try/catch; combate abre split sem roubar foco e mantém aba ao encerrar; modais com useModalFocus; tablists com setas/Home/End; sem dado novo exposto, sem mudança de API/save.

Correções aplicadas: StoryLog memo + onScrollPosition estável; capturas fora do repo e convertidas para WebP.

Achados menores: foco cai no body ao enviar (pré-existente); apagar save não chama forgetChatSession; nome 'Fechar ficha' mantido; clearOwner movido para após imports no rebase.

Smoke §6 verde (uvicorn+MockLLM, split, combate, divisor por teclado 70% persistido, 1024/390 sem overflow, 0 pageerror/console.error).
