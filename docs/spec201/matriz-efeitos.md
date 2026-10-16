# SPEC-201 — Matriz de efeitos e interações (diagnóstico UX)

> Commit auditado: `afe98941a541dc5643b1f2f1f4ef3ba7563fcca6` (HEAD limpo em `web/src/**`; nada de produto foi alterado).
> Rótulos: **[F]** fato observado no source/captura/medição · **[H]** hipótese · **[R]** recomendação · **[D]** decisão do dono.
> Arsenal de referência: `referencias/ARSENAL_VISUAL.md` do pacote (**arsenal-base provisório, D7/Q2** — usado só como vocabulário; a seleção original do dono ainda não foi importada).
> Funções do arsenal: affordance · preparação · compromisso · consequência · revelação · transição.
> Capturas: `capturas/{1440x900,1280x800}/…png` (índice e comando em `capturas/INDEX.md`); dados brutos em `dados/*.json`; medições em `medicoes.md`; atrito em `atrito-sem-animacao.md`; tokens/estados em `gaps-design-system.md`.

## 0. Correções de premissa [F]

- **Não existe "tela de mapa".** O mapa é a aba `mapa` do `Hud` (`Hud.tsx:96`, componente `WorldMap.tsx`, com `onTravel`). Tratado como aba.
- **Não existe "tela de Bestiário".** Ele vive dentro do `CodexTab.tsx` (categoria `creatures`, tiers `codex-beast`).
- **Não existe estado "bloqueado/secreto" no Codex.** `CodexTab` só lista o que o servidor devolveu como descoberto; o estado `revealed/secret` é *ausente* por construção (ver R6 em `gaps-design-system.md`). A ordem de segurança é "nunca enviar", não "esconder no cliente".
- `EmberField` **não roda** com `prefers-reduced-motion: reduce` (retorna antes de agendar `requestAnimationFrame`, `EmberField.tsx:8-9`). A hipótese H do R10 ("pode seguir rodando JS") é **refutada** para o carregamento; porém a checagem é feita só na montagem (não reage a mudança de preferência nem a aba oculta) — ver M25.

## 1. Inventário de superfícies (R1)

Fonte: `App.tsx` (`Screen = bootstrap|auth|saves|create|simulator|play|account`, `App.tsx:46`) e `PlayScreen.tsx`.

| # | Superfície | Arquivo (linhas) | Estados de loading/erro/vazio | Captura |
|---|---|---|---|---|
| S01 | Bootstrap ("Abrindo as Crônicas…") | `App.tsx:766-772` (`role=status`, `aria-busy`) | só loading | — (efêmero) |
| S02 | Auth + Turnstile | `AuthScreen.tsx:22-150`, `TurnstileChallenge.tsx` | erro `role=alert` (`:128`), notice `role=status` (`:129`); botões `disabled={working}` sem texto de pendente | `auth-default`, `auth-error` |
| S03 | Conta | `AccountScreen.tsx:333-486` | loading/erro/vazio com `role=status/alert` | `account-default` (fixture sem `/account/*` → estado de erro) |
| S04 | Saves | `SaveScreen.tsx:16-96` | vazio → cai em Create; `busy` desabilita | `saves-default/hover/focus` |
| S05 | Criação (wizard 5 passos) | `CreateScreen.tsx:23,183-519` | prólogo loading `role=status` (`:449`) | `create-step1…step5`, `create-card-*` |
| S06 | Laboratório de combate | `CombatSimulatorScreen.tsx:36-162` | loading `role=status` (`:75`) | `simulator-default` |
| S07 | Play — topbar + `placesbar` | `PlayScreen.tsx:100-145` | — | `play-default` |
| S08 | StoryLog | `StoryLog.tsx:7-96` | `.thinking` `aria-live=polite` (`:42`) | `play-*` |
| S09 | SceneArtwork / VisualArtwork / ArtworkDialog | `SceneArtwork.tsx`, `VisualArtwork.tsx`, `ArtworkDialog.tsx` | fallback por `failedKey` | `play-default` |
| S10 | Composer + voz | `PlayScreen.tsx:196-241` | `role=status/alert` da voz (`:231`) | `play-composer-*` |
| S11 | Chips (manobras, lugares, sugestões) | `PlayScreen.tsx:129-145,180-195` | `disabled={busy}` | `combat-active` |
| S12 | Tactical dock: CardHand/ReactionPrompt/WoundTrack/SceneZones | `PlayScreen.tsx:147-176`, `CardHand.tsx`, `ReactionPrompt.tsx`, `WoundTrack.tsx`, `SceneZones.tsx` | vazio → `return null` | `combat-active`, `combat-card-*` |
| S13 | Hud + 8 abas `ficha|combate|personagens|mapa|faccoes|missoes|cronica|codex` | `Hud.tsx:96-628` | vazios por aba (`combat-empty`) | `hud-tab-*` |
| S14 | WorldMap (aba mapa) | `WorldMap.tsx:1-134` | `return null` se mapa não carregou | `hud-tab-mapa` |
| S15 | CodexTab (+Bestiário) | `CodexTab.tsx:17-191` | loading/vazio por categoria | `hud-tab-codex` |
| S16 | QuestsTab | `QuestsTab.tsx` | vazio | `hud-tab-missoes` |
| S17 | LevelUpModal | `LevelUpModal.tsx:25-158` | — | `overlay-levelup` |
| S18 | DeathModal | `DeathModal.tsx:1-69` | — | `overlay-death` |
| S19 | Game over / resultado do laboratório | `PlayScreen.tsx:252-285` | — | `overlay-gameover` |
| S20 | Banner de erro | `Banner.tsx` (6 s erro / 9 s aviso, `role=alert`) | — | `play-composer-error` |
| S21 | OnboardingHint | `OnboardingHint.tsx` | dispensável (localStorage) | `play-default` |
| S22 | ImageQuoteDialog / GeneratedPortrait / GeneratedArtCard / `image-offers` | `App.tsx:716-739`, `ImageQuoteDialog.tsx`, `GeneratedPortrait.tsx`, `GeneratedArtCard.tsx` | `role=status/alert` | barra "Cotar retrato" visível em `play-*` |
| S23 | EmberField + `.atmosphere` | `EmberField.tsx`, `styles.css:69-86` | — | todas |

## 2. Matriz de efeitos (R2/R11/R14)

Ordem: interação (hover/focus/press) → seleção → confirmação implícita → saída visível (resultado/erro) → transições. **Nenhuma transição cosmética é P0.** Prioridade P0–P3 como no arsenal-base. "opcional" = puramente cosmético.
Critérios de aceite não dependem de tempo de animação e valem sob `prefers-reduced-motion: reduce`.

| ID | tela | interação | problema atual [F/H] | efeito/interação proposto | propósito | prioridade | a11y | perf | risco de confusão | critério de aceite |
|---|---|---|---|---|---|---|---|---|---|---|
| M01 | Create (raça/classe/região) | clicar no cartão | **[F]** só o `<button class="card__name card__select">` é clicável = **4,5 % da área** do cartão (`dados/create-hitbox-*.json`: botão 213×27 em cartão 249×519); `elementFromPoint` no centro/canto devolve `div.visual-art__monogram`, fora de `button`; clique no centro mantém `aria-pressed=false`; ainda assim `.card` tem `cursor:pointer` e hover com `translateY(-1px)` (`styles.css:285-296`). Hipótese de "clique impreciso" **confirmada** | hitbox = cartão inteiro (botão estica por `::after{inset:0}` ou `onClick` no `article`) + halo de foco no cartão + indicador persistente de selecionado | affordance | P0 | `aria-pressed` + foco visível sem hover; ver M03 sobre `role=radiogroup` | CSS puro | baixo | clicar em qualquer ponto do cartão seleciona; selecionado visível (borda `--accent` + marcador textual) sob `reduce`; `elementFromPoint` no centro resolve para o controle |
| M02 | Create | semântica do grupo | **[F]** `role="radiogroup"` contendo `button[aria-pressed]` (`CreateScreen.tsx:225,235`): papel declara rádio mas os filhos são toggles; sem setas | alinhar papel (`radio` + setas ou grupo de toggles sem `radiogroup`) | affordance | P1 | Tab/setas coerentes com o papel | — | baixo | leitor/teclado tratam o grupo de forma consistente; axe sem violação |
| M03 | Create | avançar passo | **[F]** troca seca entre passos; stepper `.wizard__step` sem indicador deslizante; `aria-current=step` já existe (`:189`) | painel com transição curta de opacidade + indicador de passo (`layoutId`) | transição | P2 | foco vai ao título do passo; seleção preservada | opacity/transform | baixo | trocar de passo preserva seleções; foco no `h2` do passo; sem animação sob `reduce` |
| M04 | Create | prólogo carregando | **[F]** `.prologue__pulse` é pulso de opacidade infinito sem fase real (`styles.css:320`) | rótulo de fase honesto ("tecendo o prólogo…") sem barra falsa | compromisso | P2 | `role=status` já existe | CSS | baixo | texto de fase visível; sem animação sob `reduce` |
| M05 | Auth | enviar/erro | **[F]** botões só `disabled` (`AuthScreen.tsx:130`); captura `auth-error` mostra o `detail` cru do servidor ("bad") sem vínculo ao campo; sem `aria-busy` | estado `pending` com rótulo ("Entrando…"), mensagem humana, `aria-describedby` no campo | compromisso | P1 | `role=alert` já existe; vincular ao input | CSS | baixo | submit mostra pendente e reabilita com erro legível |
| M06 | Saves | abrir save | **[H]** `savecard__main` só muda borda/sombra 0.15 s (`styles.css:915`); clique entra em `busy` sem texto de pendente | hover/foco consistentes + rótulo "Abrindo…" no cartão clicado | compromisso | P1 | foco visível (ok, global `:140`) | CSS | baixo | cartão clicado mostra pendente; demais ficam `disabled` com explicação |
| M07 | Play/topbar | barra de ofertas de imagem | **[F]** `.image-offers` ("Cotar retrato") é bloco em fluxo **acima** do cabeçalho do jogo (`App.tsx:719-731`, `styles.css:1135`): empurra a topbar ~56 px e fica na primeira linha de toda captura `play-*` | mover para menu/aba de personagem (SPEC-209) e remover do fluxo do chat | affordance | P1 | alvo de teclado estável | nenhuma | médio (some o atalho) | topbar na mesma posição com/sem oferta; oferta acessível por menu |
| M08 | Play/composer | enviar ação | **[F]** botão vira "…" ao `busy` (`PlayScreen.tsx:227`) sem `aria-busy`; legenda de fase SSE só aparece no `.thinking` | estado `pending` do composer (rótulo + `aria-busy`) + fase SSE visível junto ao campo | compromisso | P0 | `aria-busy`, texto de fase | CSS | baixo | enviar bloqueia reenvio e mostra fase; erro reabilita o botão com texto |
| M09 | Play/StoryLog | nova narração | **[F]** todo bloco é `motion.article` com fade+`y 14`+`blur(3px)` 0,55 s (`StoryLog.tsx:69-73`), inclusive histórico recarregado; tempo de quadro com blur: 0–1 quadro >33 ms em 3×60 msgs com blur vs 0 sem blur — diferença dentro do ruído (`medicoes.md`) | animar só o bloco novo; histórico sem animação; sem `blur` em lista | consequência | P1 | 1 anúncio `aria-live` por turno (hoje **nenhum**: `section.story` sem `aria-live`) | evitar `filter` em lista | médio (leitura) | histórico carregado sem animação; novo turno anunciado 1× |
| M10 | Play/StoryLog | rolar até o fim | **[F]** `scrollTop = scrollHeight` a cada mudança de `entries/thinking` (`StoryLog.tsx:16-19`), mesmo se o jogador rolou para ler acima | não arrastar o scroll se o usuário subiu; chip "ir ao fim" | affordance | P1 | foco/scroll preservados | — | médio | rolar para cima durante streaming não é revertido |
| M11 | Play/StoryLog | custo do turno | **[F]** `✧` (`msg__cost-button`) é o único acesso ao custo; alvo pequeno | manter; garantir alvo ≥24 px e rótulo | affordance | P3 | `aria-expanded` já existe | — | baixo | alvo ≥24 px; painel acessível por foco |
| M12 | Play/composer | microfone | **[F]** estados gravando/transcrevendo/erro em `voice-status` com `role=status/alert` e timer (`PlayScreen.tsx:229-239`) | manter e padronizar com estados de M08 | compromisso | P1 | já `aria-live` | CSS | baixo | cada fase tem texto + ícone estável |
| M13 | Dock de combate | layout | **[F]** o `tactical-dock` (414 px) ocupa a **coluna do chat** e a narração fica com **99 px** de altura em 900 px (`dados/combat-card-states-1440x900.json`: `dockRect.h=414`, `storyRect.h=99`); texto da narração aparece atrás da mão (`capturas/1440x900/combat-active.webp`); a faixa Vitalidade/zonas é cortada pelos chips | levar mão/reação/zonas para a aba Combate (SPEC-205) e devolver a altura ao chat | transição | P0\* | ordem de foco: chat → aba | layout | alto | chat ≥50 % da altura em combate (\*P0 por ser correção de layout/legibilidade, não efeito) |
| M14 | Combate | armar carta + escolher alvo | **[F]** `<select>` de alvo + botão "Jogar Carta"; sem estado armado, sem `Esc`, sem mira por clique no inimigo (`CardHand.tsx:34-99`; `SceneZones` é lista textual) | arma → mira → executa por gesto (SPEC-205), `aria-pressed` no armado, `Esc` desarma | preparação | P0 | `Esc`/Enter, alvo focável | transform | médio | carta armada: `aria-pressed=true`, borda `--accent`; `Esc` desarma; igual sob `reduce` |
| M15 | Combate | custo/limite/indisponível | **[F]** custo só em `title="Custo de Entropia"` (`CardHand.tsx:58`); `title` inacessível em toque/teclado; motivo de `disabled` aparece como "Sem Entropia" mas sem custo-vs-saldo | painel/tooltip **focável** com custo real, frequência e razão | affordance | P0 | focável, não só hover | CSS | baixo | motivo do `disabled` por texto, sem `title` único |
| M16 | Combate | carta indisponível/gasta | **[F]** `.combat-card button:disabled{opacity:.45;cursor:default}` (`styles.css:948`): só opacidade, o cartão inteiro continua parecendo clicável | estado `is-spent`/`is-blocked` com texto + sem hover lift | affordance | P1 | texto ≠ cor | CSS | baixo | cartão `disabled` sem hover; razão visível |
| M17 | Combate | Ruptura | **[F]** toggle "Declarar Ruptura" muda para "Romper" (`CardHand.tsx:74-96`) sem preview do efeito | linha de resumo "o que a Ruptura faz" focável | preparação | P1 | `aria-pressed` ok | — | médio | estado declarado visível antes de confirmar |
| M18 | Combate | reação | **[F]** `ReactionPrompt` é `fieldset` permanente na mão ("Reação preparada para esta rodada"), `title` para gatilho (`ReactionPrompt.tsx:33`) | painel contextual **somente** quando há gatilho real; não bloqueante | consequência | P0 | região viva, `Passar` default | presença | médio | aparece só com gatilho do backend; conteúdo igual sob `reduce` |
| M19 | HUD | trocar aba | **[F]** `tablist` sem indicador deslizante e **sem setas**: `ArrowRight` no tab Ficha deixou a seleção inalterada (`dados/tablist-arrow-keys-*.json`); `role=tabpanel tabIndex=0` | indicador persistente (`layoutId`) + setas/Home/End (padrão WAI-ARIA tabs) | affordance | P0 | setas ←/→ | layout leve | baixo | aba ativa inequívoca sob `reduce`; setas movem seleção |
| M20 | HUD | auto-troca por combate | **[F]** `useEffect` força `combate` ao entrar em luta e `ficha` ao sair (`Hud.tsx:26-34`) sem aviso; o jogador perde a aba aberta | não forçar; badge/indicador na aba Combate; anunciar troca | confirmação implícita | P0 | `aria-live` na troca | — | médio | aba escolhida preservada; entrada em combate sinalizada sem tirar o foco |
| M21 | HUD | gaveta <900 px | **[F]** `.hud` vira gaveta `translateX(100%)` 0,3 s (`styles.css:812-820`); mobile fora de escopo | — (SPEC-216) | transição | P3 | — | — | — | fora de escopo |
| M22 | HUD/Mapa | viajar | **[F]** nós usam `cursor:default` (`styles.css:588,1124`) e `title=` com lore (`WorldMap.tsx:99-110`); tooltip como único detalhe; menor alvo 68×22 px | cursor/halo em nó viajável; painel focável com rota/tempo; fog também por texto | affordance | P1 | rótulo de fog ("Região inexplorada" já existe `:117`) | CSS/SVG | baixo | nó viajável tem cursor/halo; não viajável explica por quê |
| M23 | HUD/Mapa | fog / spoiler | **[F]** DOM mascara não visitados ("???"), **mas `/data/map` entrega nome e `lore_seed` de nós não visitados ao cliente** (`dados/sentinel.json`: sentinela só na resposta de `/data/map`; DOM e atributos limpos) | não efeito: servidor deve filtrar por `visited` antes de efeitos de revelação | revelação | P0 | — | — | **alto** (spoiler em rede) | sentinela ausente em DOM **e** rede (hoje só DOM) |
| M24 | HUD/Codex | abrir/descobrir | **[F]** sem estado revelado vs bloqueado; lista só o descoberto (`CodexTab.tsx`); sem transição de "novo registro" | marcador "novo" + revelação sutil ao descobrir; sem DOM do que não foi descoberto | revelação | P1 | `aria-label` genérico quando houver bloqueado | troca direta | **alto** | busca de sentinela no DOM e rede = 0 |
| M25 | Shell | `EmberField` | **[F]** canvas contínuo; medição ociosa 3 s: tarefa ≈210 ms vs ≈76 ms em `reduce` (≈+130 ms/3 s ≈ +4 % de uma thread; `medicoes.md`); checagem de `reduce` só na montagem; não pausa em aba oculta | pausar em `visibilitychange`/mudança de preferência | transição (atmosfera) | P3 · opcional | decorativo `aria-hidden` ✔ | −4 % CPU ocioso | baixo | 0 frames em `reduce`/aba oculta |
| M26 | Overlays | foco/Esc | **[F]** `LevelUpModal`/`DeathModal`/`simulation-result` são `div[role=dialog][aria-modal]` **sem** `autoFocus`, foco preso, `Esc` ou retorno de foco (grep: apenas `ArtworkDialog`/`ImageQuoteDialog` gerenciam); `DeathModal` sem `aria-labelledby` | foco ao título/primeira ação, retorno de foco, `Esc` quando seguro | compromisso | P0 | foco preso, retorno | — | baixo | abrir modal move foco para dentro; fechar devolve à origem |
| M27 | LevelUp | botão "Depois" | **[F]** `<button class="btn">` **sem variante**: `.btn` base não define fundo/cor (`styles.css:123-129`) → botão branco com texto quase invisível (`capturas/*/overlay-levelup.webp`) | usar `btn--ghost`/`btn--primary` | affordance | P0 | contraste | — | baixo | contraste ≥4,5:1 em todos os `.btn` |
| M28 | LevelUp | pulso do atalho | **[F]** `.iconbtn--levelup` com `lvl-pulse` infinito (`styles.css:870`) | pulso finito (3 ciclos) ou estático com selo | consequência | P2 · opcional | zera em `reduce` | CSS | baixo | sem animação infinita |
| M29 | Death | resultado da queda | **[F]** `motion.div` fade+`y`+`scale` 0,5 s (`DeathModal.tsx:23-28`); conteúdo informativo denso (ledger) | manter; garantir leitura sem animar | consequência | P2 | foco (M26) | — | baixo | todo dado do ledger visível em 1ª pintura sob `reduce` |
| M30 | Play | dano em Vitalidade | **[F]** `barhit` (brilho) e `combatblock.is-hit` com `shake` (`styles.css:522,547`); sem delta textual | manter brilho; chip de delta ("−6") | consequência | P0 | texto equivalente | CSS | baixo | delta visível sem animação; sem `shake` sob `reduce` |
| M31 | Play | fim de combate | **[F]** dock some de uma vez; HUD volta para `ficha` (M20) | cartão de resultado (ConflictSummary) com XP/loot na UI, não na prosa | consequência | P1 | `role=status` | — | médio | resultado visível ao fechar o dock |
| M32 | Telas | troca de screen | **[F]** `AnimatePresence mode="wait"` fade 0→1 entre telas (`App.tsx:766-860`); `play`↔`account` não preserva scroll/foco/rascunho (`input` é `useState` do `PlayScreen`, `:39`) | preservar rascunho/scroll; fade curto opcional | transição | P2 | foco restaurado | opacity | médio | rascunho do composer sobrevive a `account` |
| M33 | Sim./Create | altura | **[F]** laboratório e wizard passam de 900 px (botão "Voltar" cortado em `simulator-default.webp`); `account-shell-link` ("Conta"/"Sair") sobrepõe o topo do painel (`App.tsx:736-742`) | cabeçalho fixo fora do painel; rolagem interna | affordance | P1 | ordem de foco | — | baixo | nenhum controle sobreposto/cortado a 1280×800 |
| M34 | Arte | retrato/cena em geração | **[F]** estados de espera de arte têm `role=status`, mas visual próprio sem skeleton neutro (`GeneratedPortrait.tsx:51`) | skeleton neutro; arte nunca carrega número/regra | revelação | P2 | `alt` obrigatório | lazy | médio | imagem nunca é a única fonte de custo/dano/alvo |
| M35 | Banner | erro de ação | **[F]** banner fixo 6 s (`Banner.tsx:12`) cobre a topbar (`play-composer-error.webp`); "Consultar/Retomar" e "Descartar" (`.pending-operation`, `App.tsx:742`, `styles.css:364`, z-index 100 > overlay 60) aparecem sempre que há operação pendente — inclusive durante um turno normal em andamento (`play-composer-pending.webp`) — sobre o chat | erro inline junto ao composer; recuperação só quando há pendência real | saída visível | P1 | `role=alert` ✔ | — | médio | erro persiste até ação; pendência explica o que fará |
| M36 | Combate | entrada/saída do encontro | **[H]** troca de modo é corte seco (dock aparece/some com `fighting`) | título curto de encontro + retorno ao chat com resumo | transição | P2 | texto do título | opacity | médio | encontro anunciado 1× por `combat.active` |

\* M13 é P0 por ser correção de layout (legibilidade), não efeito; mantido na matriz por ser o maior problema evidenciado.

**Contagem:** 36 linhas (≥25). Todas com evidência e critério observável independente de tempo.

## 3. O que NÃO animar (R3)

1. **Parágrafos de narração longa** — histórico não anima; só o bloco novo (M09). Efeito em texto lido repetidamente cansa e custa `blur`.
2. **Listas do Codex/Crônica/Missões** — consulta; troca direta (arsenal: "troca direta; sem spoiler no DOM").
3. **Tooltips/painéis de custo** — informação precisa estar lá no 1º quadro (M15).
4. **Rolagem do chat** — nenhum `smooth` (hoje não há; manter assim).
5. **Cada controle/botão** — sem "dez animações por controle": hover/focus/press já resolvidos por CSS (M01).
6. **Números de dano/XP/ouro** — mudar o texto; sem contador rolante nem partículas.
7. **Tela de morte** — conteúdo denso e grave; sem tremor.
8. **Fog do mapa** — sem revelar nome antes da descoberta (M23).

## 4. Confirmações repetitivas removíveis (R14)

- **Combate: "Jogar Carta" + `Agir/Lutar`** — dois caminhos distintos para a mesma intenção; o botão "Jogar Carta" já confirma (`CardHand.tsx:84`). Substituir por arma→mira→executa sem "tem certeza?" (SPEC-205).
- **Ruptura**: "Declarar Ruptura" → "Romper" são duas ações para um gesto (M17); o estado declarado já é a confirmação visível.
- **Pendência de ação**: "Consultar / Retomar" + "Descartar" aparecem já durante um turno normal em andamento, quando ainda não há decisão a tomar (M35).
- **Level-up**: "Depois" + "Confirmar" — manter só quando há escolha adiável (subclasse não adia, `disabled={isSubclass}`).

## 5. Pontos de efeito previstos (R8) — `previsto`, sem proposta de implementação

| Superfície futura | Gatilho real | Função | Risco/observação | Prioridade provisória |
|---|---|---|---|---|
| Shell SPEC-204: troca de aba, split↔full, resize | seleção de aba; `combat.active`; largura | transição | rascunho/scroll/foco preservados (M20, M32); sem 3ª coluna [D] | P1 |
| Combate SPEC-205: arma→mira→executa | clique em carta; `valid_targets` | preparação/compromisso | feedback independe do LLM; sem confirmação repetida [D] | P0 |
| Combate: entrada/saída de encontro | `combat.active` true/false; `ConflictSummary` | transição/consequência | XP/números só na UI, não na prosa [D] | P1 |
| Combate: dano/status/reação | `ActionResponse`/`reactions` | consequência | texto equivalente; sem `shake` sob `reduce` | P0 |
| Menu Deck/Personagem SPEC-209 | preparar cartas fora de luta | preparação | só dados canônicos | P1 |
| Menu Mapa/viagem SPEC-210 | `onTravel`, fog | revelação/transição | tooltip sem spoiler; servidor filtra (M23) | P1 |
| Menu Codex/Bestiário/dossiês SPEC-211 | descoberta, fato vs rumor | revelação | arte secreta fora do DOM e da rede até a descoberta | P1 |

## 6. Arte contextual real vs informação mecânica (R13)

**(a) Onde arte real agrega atmosfera e pode ganhar revelação/transição** (fonte: `services/visual_catalog.py`; resolução por ID canônico e estado, nunca por nome):

| Onde | Componente | ID canônico da fonte | Regra de visibilidade | Efeito possível |
|---|---|---|---|---|
| Cena do local | `SceneArtwork` | `visual.scene.asset.asset_id` (`scene-<location_id>`; `subject_type: location`) | só local atual/visitado; fallback regional explícito | revelação suave na troca de local (opacity); sem parallax obrigatório |
| Primeira aparição de NPC | `StoryLog` → `VisualArtwork` (`visual.cue`) | `asset.subject_id` = id do NPC; ledger visual no save (schema v6) | NPC secreto/oculto nunca entra no catálogo público | revelação única por NPC, 0 repetição em reload |
| Raça/classe | `CreateScreen` cartões | `opts.visuals.races[id]`/`classes[id]` | catálogo público, sem estado de jogo | hover/seleção (M01); sem animação na imagem |
| Retrato do jogador | `GeneratedPortrait` | `portrait_generation_id` | só do dono; quote explícito (SPEC-188) | skeleton neutro (M34) |
| Cartas/criaturas/mapa | não há arte por carta hoje [F]; criaturas só texto no Codex | — | — | candidato futuro (SPEC-211), sempre atrás de descoberta |

**(b) Onde a imagem NÃO pode carregar informação mecânica** — custo, dano, alvo válido, estado de Ferimento, fog e disponibilidade. Essa informação tem **sempre** texto/token equivalente (`.combat-card__cost "2E"`, `.combat-card__state`, `WoundTrack`, rótulo "Região inexplorada"). Arte decorativa usa `alt` descritivo e nunca é a única indicação de `disabled`/selecionado.

## 7. Referências do pacote (R15)

Citadas como **comportamento**, nunca como estilo/regra; números, cartas e falas dos HTMLs de `design-html/` são mock [D]. Nenhuma proposta adiciona framework ou UI kit: `motion` ^12.42 + CSS existentes são o teto.

| Linhas | Referência | Uso |
|---|---|---|
| M01, M19 | `ARSENAL_VISUAL.md` "Focus halo…", "Seleção com indicador persistente (layoutId)" | vocabulário |
| M14, M15, M18 | "Linha de mira e alvo válido", "Feedback de custo/alcance", "Reação contextual sem bloqueio"; `design-html/rpg-combate-experiencia-v03.html` | comportamento de combate (mock) |
| M13, M20, M32 | "Transição split↔full"; `design-html/rpg-design-system-chat-first-v01.html` | shell chat-first (mock) |
| M09, M25 | `REFERENCIAS_LINKS.md` (MDN reduced-motion; Motion layout docs) | acessibilidade/implementação |
| M23, M24 | `ARSENAL_VISUAL.md` "Interfaces de consulta": "arte secreta não carregada no HTML antes da descoberta" | spoiler |

## 8. Auditoria de `motion` atual (R9, resumo; dados completos em `medicoes.md`)

`motion.*`: `StoryLog.tsx:69` (fade+y14+blur 0,55 s), `DeathModal.tsx:23` (fade+y16+scale 0,5 s), `LevelUpModal.tsx:44` (fade+y14+scale 0,35 s), `SceneArtwork.tsx:15` (`motion.img` em `AnimatePresence mode="wait"`), `App.tsx:766-860` (fade entre telas). Nenhum `layout`/`layoutId`. `MotionConfig reducedMotion="user"` (`App.tsx:714`) desliga transformações mas **não** `opacity` — por isso o fade permanece sob `reduce` (consistente com o bloco CSS que só zera `animation`/`transition`, não `motion` inline).
`@keyframes`: `pulse`, `throb` (×4 usos), `beacon` (×2), `shake`, `barhit`, `veilpulse`, `blink`, `prologue-pulse`, `lvl-pulse` (`styles.css:320-871`). Sob `reduce` o bloco global `styles.css:825-828` zera `animation` e comprime `transition-duration`; em captura `reduce` **nenhum** elemento mantém animação CSS (`movingInReduce: []`).
