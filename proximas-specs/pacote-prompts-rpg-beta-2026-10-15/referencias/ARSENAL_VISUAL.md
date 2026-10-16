# Arsenal visual base — matriz para design system do RPG chat-first

**Status:** curadoria pesquisada nesta sessão, **não a seleção literal da outra conversa**. Escolher por função e restrição de UX. Efeitos devem ser uma linguagem visual compartilhada, não um parque temático de animações.

## Gramática de movimento
1. **Affordance:** apontar/clicar/focar claramente (hover, focus ring, press, hitbox).
2. **Preparação:** estado armado/seleção/alvo elegível sem alterar mundo.
3. **Compromisso:** ação realmente enviada; estado pending, erro e rollback se necessário.
4. **Consequência:** impacto, vida, status, posição, evento e narrativa.
5. **Revelação:** conhecimento descoberto, não spoiler.
6. **Transição:** chat↔combate / split↔full / aba↔aba sem perder foco/scroll.

## Catálogo por jornada

| Efeito | Onde / gatilho | Por que | Faixa de prioridade | Referência técnica | Reduced motion / risco |
|---|---|---|---|---|---|
| Focus halo e hover lift contido | classe, raça, card, itens de menu | confirmar clicável | P0 | Motion `whileHover` / CSS | foco visível sem hover; não mover layout |
| Seleção com indicador persistente | raça/classe, aba, carta | deixar estado inequívoco | P0 | Motion shared `layoutId` | underline/borda estática |
| Transição split↔full com shared layout | minimizar/expandir chat/contexto | orientação espacial | P0 | Motion `layout` | instantânea sem mover conteúdo |
| Cartas sobem ao selecionar | combate, deck | preparar ação | P0 | Motion transform | borda/ícone de seleção |
| Linha de mira e alvo válido | carta com alvo | prevenir misclick | P0 | SVG/CSS, pointer states | foco e rótulo do alvo |
| Feedback de custo/alcance | carta hover/foco | informar decisão | P0 | CSS/React state | estado textual e contrastes |
| Lançamento curto de carta | execução confirmada pelo server | consequência | P0 | Motion keyframes, transform | pulse mínimo / status text |
| Dano e status como microfeedback | acerto, bloqueio, ferimento | comunicar mecânica | P0 | Motion presence | texto/chip atualiza sem float |
| Reação contextual sem bloqueio | trigger real do backend | decisão oportuna | P0 | toast/panel presence | mesmo conteúdo estático |
| Entrada de encontro | ameaça identificada pelo chat | mudança de modo sem susto | P0 | overlay curto, shared layout | corte instantâneo com título |
| Vitória/fuga e retorno ao chat | estado terminal | fechamento natural | P0 | fade + narrative event | cena estática com log |
| Feedback de stream (thinking ≠ progresso falso) | turno em curso | reduzir sensação de travamento | P0 | skeleton/activity, SSE states | label de pending |
| Estados microfone | gravando/transcrevendo/erro | status inequívoco | P0 | CSS pulse controlado | texto e ícone estáveis |
| Acordeão no dossiê NPC | clique em fatos/rumores | leitura sem parede de logs | P1 | Motion layout | abre sem animação |
| Descoberta bestiário | criatura identificada | sensação de descoberta | P1 | reveal/mask sutil | troca direta; sem spoiler no DOM |
| Marcador e caminho no mapa | explorar/selecionar local | orientar geografia | P1 | SVG line / motion | marcador estático |
| Efeito de tinta/folha no Codex | página nova/registro | atmosfera temática | P2 | CSS masked reveal | fade/instant |
| Parallax muito leve de arte de cena | cenário estático | profundidade | P2 | transform limitado | desativado |
| Glare/specular em cartas raras | detalhes cosméticos | valor percebido | P2 | CSS pointer transform | totalmente opcional |
| Tremor global/screen shake | golpe excepcional | sensação de impacto | P3 | Motion transform, ≤ ocorrência rara | **off** por padrão se reduzir movimento |
| Partículas/shader/CRT | só tela especial após pesquisa | atmosfera | P3 | Canvas/WebGL apenas se justificar | fallback estático, custo pesado |

## Interfaces de consulta
- **Codex:** retrato e nome consistentes; fatos confirmados x rumores com ícones/cópia, não só cor; impressão de livro/arquivo sem sacrificar legibilidade.
- **Personagem:** escolha de raça/classe deve responder hover, pressionar e state selected mesmo via teclado; preview de efeitos mecânicos canônicos e imagem vinculada ao personagem.
- **Combate fora da batalha:** carta reordenável/preparável se backend permitir; drag pode enriquecer, mas clique/teclado são fundamentais.
- **Bestiário:** entradas descobertas e silhouette desconhecida; arte secreta não carregada no HTML antes da descoberta.
- **Mapa:** fog-of-war e caminhos conhecidos; não antecipar criaturas/tesouros via tooltips/metadados.

## Contratos de desempenho
- Estado mecânico não fica aguardando a animação terminar. Preferir opacity/transform; evitar blur animado gigante em telas longas.
- Evitar motion constante no chat e fundo que distraia leitura. Tempo não é hard-coded nesta curadoria; agente mede e propõe budgets com a11y.
- Animação deve funcionar e degradar sem Internet ou biblioteca opcional, e parar com aba em background.
- Testar `prefers-reduced-motion`, resize, escala de fontes, teclado, focus e hot reload.
- Não adicionar `GSAP` só por um efeito; o repo já usa `motion`. Dependências novas demandam justificativa + licença + bundle impact.
- **Não copiar gráficos originais nem estilos exatos de jogos de terceiros**; links são estudo de comportamento.

## Ordem de aplicação sugerida
Primeiro interações que corrigem uso (hover, alvo, seleção), depois transição (abas/split/combate), depois revelação e atmosfera. Priorizar a jornada beta inteira, não um efeito bonito isolado.
