# Pacote de prompts para gerar a próxima onda de SPECS — RPG IA Master

**Data:** 15/10/2026 · **Tipo:** prompts de investigação e AUTORIA de specs; não contém novas specs aprovadas nem implementações.

## Iniciar
1. Extraia o ZIP na raiz do checkout/repositório ou forneça a pasta ao coding agent. Não sobrescreva `specs/` com o material histórico.
2. Comece copiando **`prompts/00-orquestrador-*.md`** para seu Codex/Claude Code. Peça para ler os outros arquivos **sob demanda**, e não todos no contexto inicial.
3. O agente audita o HEAD, propõe ordem real e produz **uma spec draft por execução** via `specs/TEMPLATE.md`/`specs/index.yaml`; você aprova a spec, outro turno implementa.
4. **Prompts 01 e 05 são distintos de propósito**: primeiro auditoria de efeitos; só depois spec de implementação do plano de efeitos.
5. Visual: abrir `design-html/rpg-design-system-chat-first-v01.html` e `design-html/rpg-combate-experiencia-v03.html` localmente, e `referencias/ARSENAL_VISUAL_INTERATIVO.html`; comparar com `referencias/ARSENAL_VISUAL.md`.

## Prioridade e dependências
- **P0 / beta:** 00 inventário -> 01 auditoria UX -> 02 shell / 03 combate UX / 04 combate integridade -> 05 efeitos (após 01 e specs relevantes) -> 06 menus -> 07 interlocutor/voz -> 08 export observability -> 15 release gate. Algumas specs podem ser redigidas em paralelo, implementações devem respeitar dependências.
- **P1 / performance:** 09 mensuração -> 10 arquivista assíncrono e 11 hierarquia de memória.
- **P2 / consistência:** 12 conhecimento NPC/segredo -> 13 experimento Jev **só se justificado**.
- **Depois:** 14 mobile single-pane.

## Avisos de versão
Ao consultar `specs/index.yaml` em 15/10/2026, a numeração já chegava a **SPEC-198**; 176–180 (Jev) e 186–187 (voz) já estavam `done`. **NÃO reaproveitar nomes/IDs do velho ZIP de specs.** SPEC-180 tinha decisão de produção `NO_GO`, modo `off`; reabrir somente sob nova evidência. Fonte de verdade: HEAD, nunca este snapshot.

## Sobre o arsenal da outra conversa
A seleção **exata** do 'arsenal visual' citado em outra conversa **não foi encontrada nos arquivos recuperáveis desta sessão**. Para não atribuir escolhas que não foram vistas, incluí um **arsenal-base novo, pesquisado, com links e demos CSS/JS originais**, além de todas as referências/protótipos efetivamente disponíveis desta conversa. `referencias/PENDENCIA_ARSENAL_ORIGINAL.md` lista como mesclar a seleção original posteriormente; **não tratar o arsenal-base como se fosse uma cópia da outra conversa**.

## Conteúdo
`prompts/` — 16 missões autoexplicativas; `referencias/` — arsenal, links, guia de efeito, demo interativa, prompt de auditor; `design-html/` — 3 HTMLs prototipados; `previas/` — screenshots da conversa; `historico-nao-executar/` — rascunhos antigos para contextualização sem autorizar implementação; `orientacoes/` — governança e fluxos.

## Restrições de produto e de governança
Ler `DECISOES_PRODUTO.md`, `AGENTS.md`, `ESTADO_ATUAL.md` e políticas de eval/modelo existentes. Definir evals independentes **antes** de otimizar; não editar oráculo ao consertar produto; long-runs e providers reais opt-in. Este ZIP não contém credenciais, saves privados, efeitos copiados ou assets proprietários de jogos.
