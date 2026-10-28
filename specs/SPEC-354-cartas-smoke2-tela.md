# SPEC-354 — Cartas: a tela do combate depois do 2º smoke real (Livro reaberto, barra fixa, dobra, registro, retrato, toasts e nomes)

> **Status:** `in-progress` (dono em autonomia até 08:30 de 28/10; decisões em §8)
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Épico:** SPEC-327
> **Depende de:** SPEC-347 (`in-progress`, código na `main`: `RoundBoard`/`round_board`, retrato, `resetBookScroll`, regra de medição) · SPEC-342 (linha de base `off` win32) · SPEC-322 (tokens) · SPEC-346 (`round_board` com DoT e curas, já na `main`).
> **Corre em paralelo com:** SPEC-353 (motor/backend do mesmo smoke) e SPEC-352 (retrato pago; mexe em `api.py::_enemy_portrait`). Fronteira em "Fora de escopo" e D-354-8.
> **Desbloqueia:** ligar `RPG_CARD_DECK=on` no staging sem os defeitos de tela do 2º smoke.
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` (Playwright e `node --test` são testes de produto, fora de `evals/protected-paths.txt`).
> **Precisa de backend:** mínimo, só de view: (a) `_enemy_portrait` sem o portão da flag (R6); (b) o registro da última rodada sobrevive ao fim do conflito na view (R4.1, ver D-354-4). Todo o resto é front.

Rótulos: **[F]** fato no source (worktree `rpg-spec-354`, `main` em `1b769c9f`) · **[H]** hipótese com evidência, que o 1º teste da etapa confirma ou derruba · **[R]** recomendação · **[D]** decisão (§8).
Insumo: [docs/spec354/achados-smoke2.md](../docs/spec354/achados-smoke2.md) (itens 1–8) e os prints em `docs/spec354/smoke/`. Cada item foi conferido no print e no source.

---

## 1. Contexto & Objetivo

[F] O 2º smoke real do combate por cartas (28/10, `main` em `7c084cfc`, SPEC-346/347 pousadas, DeepSeek, flags de cartas `on`, 390×844 e 1440×900) achou oito defeitos de **tela**. Os de motor e de API (nome de inimigo, regras) estão na SPEC-353. Esta spec cuida só do que o jogador vê: o Livro que reabre no prólogo, controles sob a barra fixa no celular, a mão abaixo da dobra no desktop, o pós-combate pobre no painel, o registro da rodada confuso, o retrato que some sem a flag, toasts que cobrem o texto e um id cru (`npc_ketil`) na Arena.

[F] O item 1 é reincidente: a SPEC-347 R11 corrigiu uma hipótese (memória de rolagem da mesma aba) que **não era o caminho do smoke**. A própria 347 registrou que não conseguiu escrever o teste vermelho (`SPEC-347 §9`, "R11 (Livro reaberto): a hipótese não foi reproduzida"). O smoke reabriu o save pelo caminho real: carregar a página, ir para a lista de saves e escolher o save (`App.tsx:184-189` → `handleContinueSave`, `App.tsx:746-772`). Por isso esta spec **exige** um e2e com dados de um save real, vermelho antes da correção.

Objetivo: o tabuleiro e o Livro ficam legíveis e tocáveis a 390 e a 1440 sem rolar para achar o que importa, e nada novo cobre texto ou controle. Princípio: *mecânica é Python*. O front só mostra o que a API manda, e a única mudança de backend é de view.

## 2. Requisitos

**Regra de medição (herdada da SPEC-347 §2).** O teste mede **sem rolar antes**: nada de `scrollIntoViewIfNeeded`, `hover` ou `click` do Playwright no elemento medido. Para agir, usar o atalho de teclado (desktop) ou `locator.dispatchEvent("click")` (celular). "Visível e livre" quer dizer que o centro do controle devolve o próprio controle (ou um filho) em `document.elementFromPoint`, e que a caixa fica inteira dentro do viewport e da área visível do painel que rola (`.ws-panel` ou `.story`). Helper: `web/e2e/spec347-helpers.ts::measure` (`:6`). Larguras: 390×844 com `isMobile`/`hasTouch` e 1440×900.

### Etapa 1 — o Livro reabre na última narração (item 1, P2)

- **R1 — Reabrir um save mostra o fim do Livro.**
  [F] Caminho do smoke: a página carrega, `bootstrapSession` busca os saves e abre a lista (`App.tsx:184-189`). O jogador escolhe o save. `handleContinueSave` chama `resetBookScroll(gid)` (`App.tsx:757`), monta a tela com o log vazio (`:758`) e depois carrega o histórico inteiro de uma vez (`:766`, `setLog` em `:735`). Numa página recém-carregada, a memória de rolagem (`chatSessionStore.ts:9-23`) já está vazia. Então o conserto da 347 (`resetBookScroll`) não muda nada nesse caminho.
  [F] No `StoryLog`, a rolagem até o fim acontece **uma vez**, quando `entries` muda (`StoryLog.tsx:48-58`), e só se `position.current.atBottom` for verdadeiro. Qualquer evento `scroll` grava `atBottom` de novo a partir da geometria do momento (`:60-66`). O `.story` tem `overflow-anchor: none` (`styles.css:1280`): quando algo acima do ponto de leitura cresce, o navegador não compensa.
  [F] Medido no smoke: `.story` com `scrollTop` 130 de 3146 (1440) e 0 de 4203 (390). Os dois estão no prólogo (print `5067793-Haldor-a1-1440-0-inicio.png`).
  [H1] (1440) O `scrollTop = scrollHeight` roda antes de a altura final existir: as imagens das entradas (`msg__visual`, `StoryLog.tsx:154-156`), a arte de cena (`ChatSurface.tsx:92-93`), a troca de fonte e a passagem para "lado a lado" quando o conflito é detectado na montagem (`Workspace.tsx:153-158`) aumentam a altura depois. O evento `scroll` da rolagem programática chega um quadro depois. Se o conteúdo já cresceu nesse intervalo, `onScroll` grava `atBottom: false`, e o efeito de `:54` para de seguir o fim.
  [H2] (390) Na montagem em combate, o celular abre a superfície de Combate (`Workspace.tsx:157`), e o chat fica `hidden` (`ChatSurface.tsx:64`). O histórico chega com o `.story` sem altura. O retorno ao chat restaura a posição (`StoryLog.tsx:41-45`) a partir de um `position` que pode ter sido gravado com geometria errada.
  - R1.1 — **Teste de reprodução primeiro, com save real.** Novo `web/e2e/spec354-livro.spec.ts`:
    - Fixture **gravada de um save real**: `web/e2e/fixtures/spec354/save-haldor.json`, com as respostas reais de `GET /game/saves`, `GET /game/state?game_id=…` e todas as páginas de `GET /game/history` (com `visual` das entradas, quando houver) do save do smoke (Haldor, Skallgard, em combate, ≥ 20 entradas). O executor grava as respostas da API local legacy com um script descartável (fora do repo) e confere que não há segredo nem e-mail. As imagens vêm de `web/public/art/**` reais, servidas pela rota do Playwright com 300 ms de atraso, para reproduzir o carregamento tardio.
    - `reabrir_save_real_1440` e `reabrir_save_real_390`: `page.goto("/")` → lista de saves → clicar no save **por `dispatchEvent`** → esperar o fim do histórico (última `.msg` no DOM) → esperar 1,5 s (imagens carregadas) → **sem rolar**: `scrollHeight − scrollTop − clientHeight ≤ 48` no `.story`, e o retângulo da última `.msg` intersecta a área visível do `.story`. A 390, o teste toca primeiro na aba "Crônica" da `MobileTabBar` (o combate abre por padrão).
    - Os dois testes têm de **falhar antes da correção**. O executor registra a saída vermelha na §9 (valores de `scrollTop`/`scrollHeight`). Se não falharem, ele aumenta a fidelidade da fixture (atraso das imagens, fontes, estado de combate, mais páginas de histórico) até reproduzir. Se mesmo assim não reproduzir, ele **para**, registra a tentativa na §9 e devolve ao coordenador. Não vale corrigir às cegas de novo.
    - Ele confirma ou derruba H1/H2 e registra na §9 a causa real.
  - R1.2 — **Correção: o Livro "gruda no fim" ao abrir (D-354-1).** Quando o `StoryLog` recebe o histórico (de 0 para N entradas) ou volta a ficar visível com `atBottom` verdadeiro, ele entra no modo "preso ao fim": um `ResizeObserver` no `.log` e no `.story` refaz `scrollTop = scrollHeight` a cada mudança de tamanho. O modo termina no 1º gesto do jogador (roda, toque, teclado ou ponteiro, que `markGesture` já registra em `StoryLog.tsx:34-35,96`). Enquanto o modo durar, um evento `scroll` sem gesto recente **não** grava `atBottom: false`. Sem `ResizeObserver` (navegador antigo), cai no comportamento de hoje.
  - R1.3 — A regra da SPEC-204 R7 continua: se o jogador subiu no Livro, a narração nova não o puxa para o fim, e a sua própria ação puxa. **Teste:** os e2e do Livro que já existem (`web/e2e/livro.spec.ts`) seguem verdes, e um teste novo `subir_e_receber_narracao_nao_puxa` (1440, fixture comum) rola o Livro para cima com a roda (gesto), recebe uma narração e confere que `scrollTop` não mudou.

### Etapa 2 — celular: nada sob a barra fixa (item 2, P2)

- **R2 — "Desfazer fila" e a nota de "Sem matar" ficam à vista acima da barra fixa.**
  [F] No celular, `.play-queue__end` é `sticky` acima da tab bar (`workspace.css:382`) e fica sobre o que vem antes dela no fluxo. A fila põe, nesta ordem, os itens, o "Desfazer fila" de linha (`PlayQueue.tsx:75-79`; visível só em ≤ 640 px por `workspace.css:435`) e a nota de "Sem matar" (`PlayQueue.tsx:80`). Esses dois ficam logo acima da barra.
  [F] Ao enfileirar, `add` devolve o foco para a carta da mão (`DeckCombat.tsx:139`). `focus()` sem `preventScroll` rola o painel até a mão. Nada rola a fila para a vista. A 347 só rola a **mira** (`DeckCombat.tsx:109-111`, com `scroll-margin-block-end` em `workspace.css:415`). Resultado: com 2 cartas na fila, "Desfazer fila" e a nota ficam sob a barra (print `4780731-Haldor-r2-390-3-fila.png`).
  - R2.1 — Em ≤ 640 px, quando muda o tamanho da fila ou o estado de "Sem matar", o último elemento visível da fila (a nota, se existir; senão "Desfazer fila") rola para a vista com `block: "nearest"`. Ele usa `scroll-margin-block-end` igual à altura da barra fixa mais a tab bar (mesma conta de `workspace.css:415`). A rolagem só acontece com o painel visível e nunca com carta armada (aí a barra não é fixa, `workspace.css:419`).
  - R2.2 — O foco que volta para a carta (`DeckCombat.tsx:139`) usa `focus({ preventScroll: true })`, para não desfazer R2.1.
  - R2.3 — O painel que rola (`.ws-panel`) ganha, só no celular e só com o tabuleiro (`:has(.deck-combat)` ou classe no contêiner), `scroll-padding-block-end` igual à altura da barra fixa. Assim o fim do conteúdo sempre pode subir acima da barra.
  - R2.4 — **Teste** `web/e2e/spec354-mobile.spec.ts::fila_cheia_sem_sobreposicao_390` (`hasTouch`, "Sem matar" disponível): enfileirar 2 cartas por `dispatchEvent` e ligar "Sem matar". Sem nenhuma rolagem do teste, "Desfazer fila" e `.play-queue__spare` ficam visíveis e livres (regra de medição). A barra continua numa linha (o R2.4 da 347 segue verde).

### Etapa 3 — desktop: a mão sem rolar com registro e dois inimigos (itens 3 e 5, P2/P3)

- **R3 — A 1440, a 1ª carta da mão fica inteira à vista no topo do painel.**
  [F] Ordem do tabuleiro: faixa de cena → `RoundBoard` → Arena → mão (`DeckCombat.tsx:173-177`). No print `5692211-Mirela-v1-1440-top.png`, com 5 entradas no registro, 2 inimigos (presságio, "Revelado") e o jogador com uma carta revelada, "Sua mão" começa em y ≈ 868 de 900. A primeira carta fica fora da dobra.
  [F] Somam altura: a faixa de cena em duas linhas (o relógio quebra); o `RoundBoard` em duas colunas (`workspace.css:462-466`), com linhas que quebram por falta de largura; a linha de iniciativa da Arena; e os chips em duas colunas (`workspace.css:441`, `minmax(14rem, 1fr)`).
  - R3.1 — O `RoundBoard` fica em **uma coluna** em toda largura (sai o `grid-template-columns` de `workspace.css:463`). Cada entrada ocupa uma linha a 1440: o alvo e o chip não quebram (`white-space: nowrap` no alvo, com reticências no nome do ator quando faltar espaço). Isso também resolve a ordem de leitura do item 5 (R5.1).
  - R3.2 — No desktop, o `RoundBoard` mostra as **últimas 4 jogadas** e "Ver a rodada inteira (N)" (`details`) quando há mais (D-354-2). Hoje o desktop mostra todas (`RoundBoard.tsx:23`). Os efeitos (R5.2) contam à parte e mostram no máximo 2 linhas, com o resto dentro do mesmo `details`.
  - R3.3 — Se R3.1 e R3.2 não bastarem para o teste R3.4, o executor aplica nesta ordem, medindo a cada passo, e registra na §9 o que usou: (a) a linha "Na última rodada, … agiram primeiro." passa a ser o subtítulo do `RoundBoard`, só no modo Baralho (`Arena.tsx` com `compact`); (b) a faixa de cena fica numa linha a ≥ 1200 px (relógio com `nowrap` e reticências no nome da cena); (c) chips de inimigo com `minmax(12rem, 1fr)` em `.arena--compact`. A ordem do tabuleiro **não** muda (D-354-2).
  - R3.4 — **Teste** `web/e2e/spec354-desktop.spec.ts::mao_sem_rolar_1440_registro_dois_inimigos`: fixture com 3 zonas, jogador com 1 carta revelada e condição, 2 inimigos com presságio, 2 condições e "Revelado" cada, presságio de cena, `registro_rodada` com 6 entradas (4 jogadas, 1 dano contínuo, 1 queda) e mão de 5 cartas. Com `.ws-panel.scrollTop === 0`, a 1ª `.deck-card` fica inteira dentro da área visível do painel e livre. O `arena_tres_zonas_1440` da 347 continua verde.

### Etapa 4 — registro da rodada honesto (item 5, P3)

- **R5 — O registro separa jogadas de efeitos e não atribui ao jogador o que ele sofreu.**
  [F] O dano contínuo sai como entrada com `ator_id` = **quem sofre**, `lado` = lado de quem sofre e `rotulo: "Dano contínuo"` (`services/combat_preview.py:347-362`). Ele é intercalado no início do turno de quem sofre (`:372-377`). O `Row` põe o ícone de herói por `lado === "heroi"` e escreve "Você" por `ator_id === "player"` (`RoundBoard.tsx:11`). Então o DoT que o jogador sofre parece um ataque dele.
  [F] Um ataque que acerta sem dano (porque só aplica condição) sai com `dano: null` e `efeito: null` (`combat_preview.py:319-320`). O chip vira só "Acerto" (`web/src/combat/deck.ts:184-187`).
  [F] Queda de inimigo e presságio cumprido não geram entrada no `round_board` (`combat_preview.py:282-399`). Eles só aparecem na prosa do Livro (print `6282120`: "Criatura Além das Estacas cumpre o que o presságio anunciava").
  - R5.1 — Uma coluna, na ordem cronológica (R3.1).
  - R5.2 — O `RoundBoard` tem duas listas: "Jogadas" (entradas de turno e reação) e, abaixo, "Efeitos da rodada" (dano contínuo, quedas e presságios cumpridos), só quando houver efeitos (D-354-3). O tipo da entrada vem de `tipo` quando a API mandar (contrato em §3, produzido pela SPEC-353). Sem `tipo`, o front infere: `rotulo === "Dano contínuo" && carta_id === null && resultado === "efeito"` → `dano_continuo`; o resto → `jogada`.
  - R5.3 — Linha de efeito: sem ícone de herói e sem "Você" como ator. Texto: "{quem sofre} sofre {condição} · −{n} Vitalidade" (para o jogador: "Você sofre {condição} · −{n} Vitalidade"); "{nome} cai ({desfecho})" para `queda`; "Presságio cumprido: {texto}" para `pressagio`.
  - R5.4 — Chip de acerto sem dano: com `efeito` → "Acerto · {efeito}"; sem `efeito` → "Acerto · sem dano". Nunca só "Acerto". O `efeito` do ataque que aplica condição é produzido pela SPEC-353 (contrato em §3); até lá, aparece "Acerto · sem dano".
  - R5.5 — **Testes** `node --test` (`web/tests/spec354-roundboard.test.mjs`, SSR): DoT no jogador não renderiza o ícone de herói nem "Você" como ator, e fica em "Efeitos da rodada"; `tipo: "queda"` e `tipo: "pressagio"` renderizam o texto literal; acerto com `dano: null` e sem `efeito` → "Acerto · sem dano"; com `efeito: "Sangrando"` → "Acerto · Sangrando"; sem efeitos, não existe a lista "Efeitos da rodada"; entradas antigas sem `tipo` continuam renderizando.

### Etapa 5 — pós-combate no painel (item 4, P3)

- **R4 — Depois do conflito, o painel de Combate mostra o resumo final e o registro da última rodada.**
  [F] Com o combate encerrado, o painel mostra só o `CombatOutcomePanel`, o Espólio e a nota (`CombateTab.tsx:282-291`). O tabuleiro (e com ele o `RoundBoard`) só existe com `live` (`:292`). No fim do conflito, o motor apaga as pilhas (`agents/combat.py:2694-2696`), e a view só põe `registro_rodada` quando existem pilhas (`api.py:3020-3025`). Por isso o registro da rodada que encerrou a luta não chega ao front.
  [F] O resumo final é a última narração do Livro (SPEC-346). O painel de contexto não recebe o log: o `Workspace` passa `log` só ao `ChatSurface` (`Workspace.tsx:338-359`). Print `4857228-Haldor-v3-390-top.png`: só "Vitória" e o Espólio.
  - R4.1 — **View mínima (D-354-4):** no turno em que o conflito acaba, a view do combate traz `registro_rodada` com o registro da rodada final, mesmo sem pilhas. O executor primeiro confirma, com um teste de `_combat_block` sobre o estado depois do turno final, se `meta["last_round_board"]` sobrevive ao fim (`store_mech_log` grava em `combat_preview.py:248`). Se sobrevive, a mudança é só em `api.py:3024`: ler `last_round_board` também sem pilhas, enquanto `combat_result` for o do conflito que acabou de terminar. Se não sobrevive, a mudança é da SPEC-353 (o motor teria de guardar), e esta spec só consome o campo quando existir.
  - R4.2 — Abaixo do `CombatOutcomePanel`, o painel mostra "A última rodada" com o `RoundBoard` (mesmo componente, título "O que se jogou na rodada final") quando houver `registro_rodada`.
  - R4.3 — Acima do registro, "O desfecho" mostra o texto da última narração do Livro depois do resultado (a entrada de narrador mais recente), com no máximo 6 linhas (`line-clamp`) e o botão "Ler na Crônica", que leva à superfície do chat. O `Workspace` passa `lastNarration?: string` ao `ContextSurface` e daí ao `CombateTab`. Sem narração (ainda em fluxo, ou erro), a seção não aparece.
  - R4.4 — Ordem no painel encerrado: `CombatOutcomePanel` → "O desfecho" → "A última rodada" → Espólio. O R8 da 347 (o desfecho rola para a vista uma vez por resultado) continua.
  - R4.5 — **Testes:** `tests/test_spec354_final_round_view.py` (com `RPG_CARD_DECK=on`, depois do turno que encerra o conflito, a view tem `registro_rodada`, e com o Baralho `off` não tem). Playwright `web/e2e/spec354-pos-combate.spec.ts::pos_combate_mostra_desfecho_e_rodada` a 390 e 1440: a fixture de vitória traz `registro_rodada` e uma narração final; o painel mostra o texto literal "O desfecho", o trecho da narração, "A última rodada" e o `RoundBoard`; "Ler na Crônica" (≥ 44 px no toque) leva ao chat; "Continuar" segue visível e livre.

### Etapa 6 — retrato sempre (item 6, P3)

- **R6 — Todo inimigo do tabuleiro mostra a arte curada ou o ícone da família, com a flag ligada ou não.**
  [F] `_enemy_portrait` devolve `None` quando `RPG_CREATURE_ART` não está `on` e não há arte curada (`api.py:2802-2803`). Sem `retrato`, o chip não mostra nada (`TargetChip.tsx:75,101`). Isso diverge da D-347-H ("sem imagem: marcador com o ícone da família").
  [F] `portrait_for` já resolve tudo sem a flag: arte curada → registro → família → marcador (`services/creature_art.py:175-224`). A oferta `gerar` só sai com a flag `on` (`:214`).
  - R6.1 — **Backend mínimo:** `_enemy_portrait` deixa de ter o portão de `:2802-2803` e sempre devolve `portrait_for(...)`. Com a flag `off`, ele passa `registry=None` (o `EmptyRegistry`) e nenhum preço, de modo que nunca há `gerar` nem leitura de registro. Com `on`, segue igual ao que estiver na `main` (inclusive o que a SPEC-352 mudar: o executor faz rebase e mantém a lógica de registro/preço da 352, tirando só o portão; ver D-354-8).
  - R6.2 — O retrato aparece nos **dois modos** (Baralho `on` e `off`), porque a regra é "sempre" (D-354-5). O `TargetChip` não muda: ele já mostra o retrato quando a chave existe.
  - R6.3 — **Testes:** `tests/test_spec354_portrait_always.py`: com `RPG_CREATURE_ART=off` e sem arte curada, todo inimigo da view tem `retrato.estado == "marcador"`, `icone == FAMILY_ICON[familia]`, `src is None`, `gerar is None`; nada é lido do registro (registro falso que falha se for chamado); com arte curada `creature_family`, `estado == "pronto"`. O teste da 347 que afirmava "sem a flag, nenhuma chave `retrato` (exceto arte curada)" (`tests/test_spec347_creature_art.py`) é atualizado nesta mesma tarefa, e a mudança é registrada na §9 (é teste de produto, não eval protegido). Playwright `spec354-desktop.spec.ts::retrato_marcador_sem_flag` (1440 e 390): os dois chips de inimigo têm `.tchip__portrait` com o ícone, e o R3.4 continua verde com os retratos.

### Etapa 7 — toasts e alvos de toque no desktop (item 7, P3)

- **R7 — Os ganhos não cobrem o texto do Livro.**
  [F] No desktop, o `OutcomeToast` é `position: absolute` dentro da coluna do chat, logo acima do composer (`workspace.css:398-399`; montado em `ChatSurface.tsx:95`). Ele cobre as últimas linhas do Livro, justamente as mais novas (print `6282120-Haldor-k4-1440-4-pos-combate.png`).
  [F] Na vitória, o `CombatOutcomePanel` já lista os mesmos ganhos (`rewardLines(result, outcome)`, `CombatOutcomePanel.tsx:14`).
  - R7.1 — Quando o turno traz um `combat_result` novo e o painel de Combate está visível (modo lado a lado ou painel com a aba Combate), o toast desse turno não aparece: os ganhos já estão no desfecho (D-354-6). O recibo é marcado como visto, para não reaparecer depois.
  - R7.2 — No desktop, o toast deixa de sobrepor: ele entra **no fluxo**, numa faixa entre o `.story` e o composer, que só ocupa altura enquanto há chips. Com o Livro preso ao fim (R1.2), a última linha continua à vista.
  - R7.3 — **Teste** `spec354-desktop.spec.ts::toast_nao_cobre_livro_1440`: um turno comum com ganhos (sem `combat_result`) → enquanto o toast está visível, o retângulo de cada `.outcome-chip` não intersecta nenhum `.msg` dentro da área visível do `.story`. E `vitoria_sem_toast_duplicado_1440`: na vitória com o painel de Combate visível, nenhum `.outcome-chip` aparece, e o desfecho lista os ganhos.
- **R8 — Alvos de 44 px no cabeçalho com toque no desktop.**
  [F] O piso de toque já cobre `.play .iconbtn, .play .btn, .play .tab` em `pointer: coarse` (`workspace.css:286-294`). O smoke mediu 37–38 px a 1440 com ponteiro **fino**, o que é esperado.
  - R8.1 — **Teste** `spec354-desktop.spec.ts::cabecalho_44_coarse_1440` com `isMobile: true, hasTouch: true` a 1440×900. Primeiro ele afirma `matchMedia("(pointer: coarse)").matches === true` (se a emulação não der `coarse`, o teste falha com essa mensagem, em vez de passar à toa). Depois mede ≥ 43,5 px de altura e de largura em todo botão de `.topbar`, `.ws-bar` e `.ws-tabs`, incluindo o fechar (×) do painel. O que ficar abaixo entra na regra de `workspace.css:288-292`. Se tudo já passar, a §9 registra "sem mudança de CSS; teste de regressão".

### Etapa 8 — nunca um id cru na tela (item 8, P2)

- **R9 — O front sempre mostra um nome exibível.**
  [F] Aliado na Arena usa `name: p.participant_name` (`web/src/combat/Arena.tsx:53-58`). A API devolve o próprio id quando não acha o nome (`api.py:2877`, `participant_names.get(str(participant_id), str(participant_id))`; o mesmo em `engaged_names`, `:2885`). Resultado: "npc_ketil" na Arena, na rodada 0 (print `4661367-Haldor-t1-390-combate.png`). O conserto da API é da SPEC-353 (item 7 dela). Este requisito é a defesa no front, que vale mesmo depois daquele conserto.
  - R9.1 — Nova `displayName(raw, id, ctx)` em `web/src/combat/displayName.ts`. Um texto "parece id" quando casa `/^[a-z][a-z0-9]*(_[a-z0-9]+)+$/` ou é igual ao `participant_id`. Nesse caso, a função procura, nesta ordem: o nome do membro do grupo (`party`) pelo id; o nome do NPC conhecido em `data.npcs` pelo `entity_id`/id; o `species_label` de `encounter_view.participants`. Se nada servir, ela humaniza: tira o prefixo (`npc_`, `enemy_`, `ally_`, `bst_`), o sufixo numérico (`_2`, `_r1`), troca `_` por espaço e põe maiúscula ("npc_ketil" → "Ketil"; "enemy_goblin_2" → "Goblin 2"). Nome que não parece id passa intacto.
  - R9.2 — Aplicada em `buildParticipants` (nome de jogador, inimigo e aliado, e `engagedNames`), nas linhas do `RoundBoard` (`ator_nome`, `alvo_nome`), no presságio (`omenView`/`pressagioLine`, via `nameOf`) e no `nameOf` do `CombateTab` (`CombateTab.tsx:105`).
  - R9.3 — **Testes** `node --test` (`web/tests/spec354-display-name.test.mjs`): os exemplos de R9.1; "Ketil" passa intacto; "Saqueador de Marfim" passa intacto; um id com NPC conhecido devolve o nome do NPC. Playwright `spec354-mobile.spec.ts::sem_id_cru_na_arena_390`: fixture com aliado `participant_name: "npc_ketil"` → a Arena mostra "Ketil", e nenhum nó de texto do `.ws-combat` casa com `/\b(npc|enemy|ally|bst)_[a-z0-9_]+\b/`.

### Transversais

- **R10 — Linha de base `off` da 342 verde em win32.** `web/e2e/deck-342-baseline.spec.ts` (`maxDiffPixelRatio` 0,01) roda antes e depois de cada etapa. Mudanças esperadas no `off`: o Livro preso ao fim (R1), o toast no fluxo (R7) e o retrato (R6, só se a fixture da baseline trouxer `retrato`; hoje não traz). Se algum snapshot mudar, a regeração vai num commit **só** com os snapshots (`test(e2e): regenerate SPEC-342 off baseline for SPEC-354 R…`), com os diffs salvos em `docs/spec354/baseline-diff/` e conferidos pelo revisor (mesmo rito da SPEC-347 R15.2/R15.3). Diferença fora dessas regiões é defeito.
- **R11 — Só tokens da 322.** CSS novo ou alterado usa só `var(--…)` existentes: nada de hex/rgb/oklch literal, raio literal ou token novo. O CSS novo vai num bloco `/* SPEC-354 */` no fim de `workspace.css`, que já é coberto por `web/tests/deck-tokens-342.test.mjs` (`:10`, do `.deck-combat {` até o fim). Se algo for para `styles.css` (Livro/toast), o teste passa a cobrir também esse bloco. `npm run lint` fica verde.
- **R12 — Alvos ≥ 44 px em `pointer: coarse`** para todo controle novo ou movido: "Ver a rodada inteira (N)" no desktop com toque, "Ler na Crônica", "Desfazer fila" depois de R2, e os do cabeçalho (R8). Critério da 321/342: ≥ 43,5 px.

### Fora de escopo

- Tudo de motor e de API da SPEC-353, inclusive: o conserto do nome na API (`api.py:2855-2885`, item 7 da 353); **produzir** as entradas `queda`/`pressagio` e o `efeito` do ataque que aplica condição no `round_board` (esta spec só define o contrato em §3 e as renderiza); a semântica do relógio ou da iniciativa.
- O fluxo pago do retrato (SPEC-352): cotação, registro, worker, botão "Gerar retrato" ligado. Aqui só sai o portão da flag do marcador.
- Mudar a ordem do tabuleiro (faixa → registro → Arena → mão). Reordenar é decisão de produto (D-354-2).
- Retrato de jogador e aliados. Animação nova. Toast no celular (o achado é só no desktop).
- Ligar flags no staging (ato do coordenador depois do `done`).

## 3. Design técnico

**Arquivos alterados (front)**

| Arquivo | Mudança | Req. |
|---|---|---|
| `web/src/components/StoryLog.tsx` | modo "preso ao fim" (`ResizeObserver` em `.log` e `.story`; termina no 1º gesto); `onScroll` não grava `atBottom: false` sem gesto enquanto preso | R1.2, R1.3 |
| `web/src/hooks/useStickToBottom.ts` (**novo**, opcional) | o mesmo modo, extraído e testável em `node --test` | R1.2 |
| `web/src/components/combat/DeckCombat.tsx` | rolagem da cauda da fila (R2.1); `focus({preventScroll: true})` em `add` (`:139`) | R2 |
| `web/src/components/combat/PlayQueue.tsx` | `data-queue-tail` no último elemento visível (nota ou "Desfazer fila") | R2.1 |
| `web/src/components/combat/RoundBoard.tsx` | uma coluna; "Jogadas" + "Efeitos da rodada"; últimas 4 no desktop; `title` opcional ("rodada final"); `displayName` | R3, R4.2, R5, R9 |
| `web/src/combat/deck.ts` | `roundLogView` com `tipo` inferido e chip "Acerto · {efeito}" / "Acerto · sem dano" | R5.2–R5.4 |
| `web/src/combat/displayName.ts` (**novo**) | `displayName`, `looksLikeId`, `humanizeId` | R9 |
| `web/src/combat/Arena.tsx` | `displayName` em `buildParticipants`; subtítulo de iniciativa no Baralho (se R3.3a) | R3.3, R9 |
| `web/src/workspace/tabs/CombateTab.tsx` | "O desfecho" e "A última rodada" no painel encerrado; `nameOf` com `displayName` | R4, R9 |
| `web/src/workspace/ContextSurface.tsx`, `web/src/workspace/Workspace.tsx` | `lastNarration` do log até o `CombateTab`; "Ler na Crônica" chama `showChat` | R4.3 |
| `web/src/workspace/ChatSurface.tsx`, `web/src/components/OutcomeToast.tsx` | toast no fluxo depois do `StoryLog` (desktop); `suppress` quando o desfecho está visível | R7 |
| `web/src/types.ts` | `RoundLogEntry.tipo?`; `CombateTab`/`ContextSurface` props | R4, R5 |
| `web/src/workspace.css` | bloco `/* SPEC-354 */`: `scroll-margin`/`scroll-padding` da fila no celular, `RoundBoard` uma coluna, efeitos, desfecho, toast no fluxo, piso de toque se R8 pedir | todos |

**Arquivos alterados (backend, só view)**

- `api.py::_enemy_portrait` (`:2796-2818`): sem o portão de `:2802-2803`; com a flag `off`, `registry=None`, sem preço (R6.1).
- `api.py::_combat_block` (`:3020-3025`): `registro_rodada` também sem pilhas, no turno do fim do conflito, se R4.1 confirmar que `last_round_board` sobrevive (D-354-4).

**Contrato pedido à SPEC-353** (o front daqui aceita a ausência e não quebra):

```ts
// RoundLogEntry ganha um campo opcional; entradas antigas seguem válidas.
interface RoundLogEntry {
  // …campos atuais (types.ts:1186-1193)…
  tipo?: "jogada" | "dano_continuo" | "queda" | "pressagio";
  // queda:     ator_id/ator_nome = quem caiu; efeito = "abatido" | "desacordado" | "rendido" | "fugiu"
  // pressagio: ator_id/ator_nome = quem cumpriu; efeito = texto público do presságio
  // jogada que só aplica condição: resultado "acerto", dano null, efeito = nome da condição ("Sangrando")
}
```

**Assinaturas**

```ts
export function looksLikeId(text: string, id?: string): boolean;
export function humanizeId(id: string): string;                      // "npc_ketil" → "Ketil"; "enemy_goblin_2" → "Goblin 2"
export function displayName(raw: string | null | undefined, id: string, ctx: {
  party?: PartyMember[]; npcs?: GameResponse["npcs"]; labels?: Map<string, string>;
}): string;
export function roundEntryKind(e: RoundLogEntry): "jogada" | "dano_continuo" | "queda" | "pressagio";
// RoundBoard: { entries; round; compact; title?: string }   (title = "O que se jogou na rodada final" no pós-combate)
// CombateTab/ContextSurface: lastNarration?: string; onShowChat?: () => void
// OutcomeToast: { outcome; suppress?: boolean }
```

**Microcopy (literal; os testes assertam)**

| Onde | Texto |
|---|---|
| Registro, efeitos | Efeitos da rodada |
| Registro, DoT | {nome} sofre {condição} · −{n} Vitalidade · (jogador) Você sofre {condição} · −{n} Vitalidade |
| Registro, queda | {nome} cai ({desfecho}) |
| Registro, presságio | Presságio cumprido: {texto} |
| Registro, acerto sem dano | Acerto · {efeito} · ou · Acerto · sem dano |
| Registro, ver mais (desktop e celular) | Ver a rodada inteira ({n}) |
| Pós-combate, resumo | O desfecho |
| Pós-combate, botão | Ler na Crônica |
| Pós-combate, registro | A última rodada · título: O que se jogou na rodada final |

**Exemplo (ids do smoke; o executor confere os ids reais em `data/cards/` e `data/bestiary.json`)**

```json
"registro_rodada": [
  {"ator_id": "player", "ator_nome": "Haldor", "lado": "heroi", "carta_id": "golpe_do_penitente",
   "carta_nome": "Golpe do Penitente", "alvo_id": "enemy_bandido_1", "alvo_nome": "Bandido",
   "origem": "turno", "rotulo": null, "resultado": "acerto", "dano": 6, "efeito": null, "tipo": "jogada"},
  {"ator_id": "player", "ator_nome": "Haldor", "lado": "heroi", "carta_id": null,
   "carta_nome": "Sangrando", "alvo_id": null, "alvo_nome": null, "origem": "turno",
   "rotulo": "Dano contínuo", "resultado": "efeito", "dano": 1, "efeito": "−1 Vitalidade"},
  {"ator_id": "enemy_bandido_1", "ator_nome": "Bandido", "lado": "inimigo", "carta_id": null,
   "carta_nome": null, "alvo_id": null, "alvo_nome": null, "origem": "turno", "rotulo": null,
   "resultado": "efeito", "dano": null, "efeito": "abatido", "tipo": "queda"}
]
```

A 2ª entrada não tem `tipo` (formato de hoje): o front infere `dano_continuo` e renderiza "Você sofre Sangrando · −1 Vitalidade" em "Efeitos da rodada".

## 4. Plano passo a passo

Web: `cd web && npm test` (`node --test`) e `npm run test:e2e -- <spec> --workers=1`. Python: `bash scripts/dev/py.sh -m pytest <arquivos> -q` (no máximo `-n 2`). Fixtures: `web/e2e/deck-342-helpers.ts::armDeck` ganha `roundLog` com `tipo`, `allies` (com `participant_name` cru) e `victory` (com `combat_result`, `registro_rodada` e narração final). A linha de base `deck-342-baseline.spec.ts` roda antes da Etapa 1 (para provar o verde de partida) e no fim de cada etapa.

### Etapa 1 — Livro (R1)

1. **Testes primeiro.** Gravar `web/e2e/fixtures/spec354/save-haldor.json` (R1.1). `spec354-livro.spec.ts::reabrir_save_real_1440` e `reabrir_save_real_390` → **vermelhos**, saída registrada na §9. `subir_e_receber_narracao_nao_puxa` (verde antes e depois). Se houver `useStickToBottom`, o `node --test` dele (preso ao fim segue a mudança de tamanho; gesto solta; `scroll` sem gesto não solta).
2. **Implementação:** R1.2.
3. **Verificação:** os dois vermelhos ficam verdes; `livro.spec.ts`, `spec347-board-only.spec.ts` e a linha de base.

### Etapa 2 — barra fixa no celular (R2)

1. **Testes primeiro.** `spec354-mobile.spec.ts::fila_cheia_sem_sobreposicao_390` (vermelho antes).
2. **Implementação:** R2.1–R2.3.
3. **Verificação:** o teste, `spec347-mobile.spec.ts` (barra numa linha, mira livre) e `spec345-mobile390.spec.ts`.

### Etapa 3 — registro e dobra no desktop (R3, R5)

1. **Testes primeiro.** `web/tests/spec354-roundboard.test.mjs` (R5.5); `spec354-desktop.spec.ts::mao_sem_rolar_1440_registro_dois_inimigos` (vermelho antes).
2. **Implementação:** R5.1–R5.4 → R3.1 → R3.2 → medir → R3.3 (a→c, só o necessário).
3. **Verificação:** os testes acima, `spec347-desktop.spec.ts` (`arena_tres_zonas_1440`, `registro_acima_da_arena`) e os SSR do `RoundBoard` da 347 (ajustar só o que a D-354-2 muda, com a mudança registrada na §9).

### Etapa 4 — pós-combate (R4)

1. **Testes primeiro.** `tests/test_spec354_final_round_view.py` (primeiro o diagnóstico: `last_round_board` sobrevive ao fim?). `spec354-pos-combate.spec.ts`.
2. **Implementação:** R4.1 (view, se o diagnóstico permitir; senão registrar na §9 e consumir quando a 353 entregar) → `lastNarration` → R4.2–R4.4.
3. **Verificação:** o escopo, `desfecho_abre_no_topo` (347 R8.2) e os testes do Espólio da 342.

### Etapa 5 — retrato (R6)

1. **Testes primeiro.** `tests/test_spec354_portrait_always.py` (vermelho antes); atualizar o caso de `tests/test_spec347_creature_art.py` que fixava a ausência de `retrato` sem a flag.
2. **Implementação:** R6.1 (rebase sobre a 352 se ela já tiver pousado).
3. **Verificação:** `tests/test_spec347_creature_art.py`, `tests/test_spec352_*` (se existirem), `spec347-retrato.spec.ts` e `retrato_marcador_sem_flag`.

### Etapa 6 — toasts, toque e nomes (R7, R8, R9)

1. **Testes primeiro.** `toast_nao_cobre_livro_1440`, `vitoria_sem_toast_duplicado_1440`, `cabecalho_44_coarse_1440`, `spec354-display-name.test.mjs`, `sem_id_cru_na_arena_390`.
2. **Implementação:** R7.1–R7.2, R8 (se preciso), R9.
3. **Verificação:** o escopo, os testes do `OutcomeToast` da SPEC-199/342 (`B-1`) e a linha de base.

### Etapa 7 — prints e smoke

1. `web/e2e/spec354-prints.spec.ts` (`test.skip` sem `RPG_SPEC354_PRINTS=1`) grava em `docs/spec354/depois/` os mesmos cenários de `smoke/`: `1440-reaberto`, `390-reaberto`, `390-fila`, `1440-registro-dois-inimigos`, `390-pos-combate`, `1440-pos-combate`, `390-arena-aliado`.
2. Smoke real (§6).

## 5. Critérios de aceite

- [ ] R1–R12 com teste nomeado verde (`node --test`, Playwright `--workers=1`, pytest do escopo).
- [ ] `reabrir_save_real_1440` e `reabrir_save_real_390` **vermelhos antes** e verdes depois, com fixture de save real e o vermelho (valores) registrado na §9, junto da causa real (H1/H2 confirmada ou outra).
- [ ] Medição por `elementFromPoint` sem rolar antes, a 390 e a 1440 (R2.4, R3.4, R4.5, R7.3).
- [ ] A 1440, com `RoundBoard` (6 entradas) e 2 inimigos, a 1ª carta da mão fica inteira à vista com `scrollTop === 0` (R3.4).
- [ ] Nenhum id cru em `.ws-combat` (R9.3). Marcador de família sem a flag (R6.3).
- [ ] Alvos ≥ 44 px em `pointer: coarse`, inclusive a 1440 com `coarse` afirmado no teste (R8, R12).
- [ ] Linha de base win32 da 342 verde; regerada só se R10 permitir, em commit próprio, com diffs em `docs/spec354/baseline-diff/` conferidos pelo revisor.
- [ ] Só tokens da 322: `deck-tokens-342.test.mjs` (estendido se houver CSS em `styles.css`) e `npm run lint` verdes (R11).
- [ ] `npm run build` e `npm test` verdes. `uv run pytest` verde (suíte completa: coordenador, no pouso).
- [ ] Saves antigos carregam: `registro_rodada` sem `tipo` renderiza; view sem `retrato`/`registro_rodada` não quebra.
- [ ] Prints "depois" em `docs/spec354/depois/` (Etapa 7).
- [ ] Smoke real (§6) executado e registrado.

## 6. Smoke test com LLM real

O mesmo roteiro do 2º smoke: API local legacy, DeepSeek, preset com `RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_SCENE_CARDS`, `RPG_COMBAT_NONLETHAL` e `RPG_CARD_REWARDS` `on`, e `RPG_CREATURE_ART` **`off`**. Se a SPEC-353 já tiver pousado, ela entra junto. São ~10–14 requests de turno.

1. A 1440: jogar um conflito com 2 inimigos e aliado (Skallgard, como Haldor) até a rodada 2 → a mão aparece sem rolar; o registro fica em uma coluna, com o dano contínuo em "Efeitos da rodada"; os chips mostram o ícone da família; nenhum id cru.
2. A 390: enfileirar 2 cartas e ligar "Sem matar" → "Desfazer fila" e a nota à vista acima da barra, sem rolar.
3. Vencer → a 1440, sem toast sobre o Livro e o desfecho com os ganhos; a 390, a aba Combate mostra "O desfecho" (trecho da narração final) e "A última rodada".
4. Recarregar a página → lista de saves → reabrir o save, a 1440 e a 390 → o Livro abre na última narração (medir `scrollTop`/`scrollHeight` como no smoke).
5. Com o emulador de toque a 1440: medir as abas e os botões do cabeçalho (≥ 44 px).
6. Comparar `docs/spec354/depois/` com `smoke/` e anotar na §9.

## 7. Riscos & compatibilidade

- **Saves:** nada novo no save. `tipo` e `registro_rodada` pós-combate são só view e opcionais; entrada antiga sem `tipo` é inferida.
- **Livro preso ao fim:** pode brigar com quem rola logo ao abrir. O modo termina no 1º gesto (roda, toque, tecla, ponteiro), e a regra da SPEC-204 R7 tem teste (R1.3). Sem `ResizeObserver`, o comportamento é o de hoje.
- **Rolagem automática da fila (R2):** só no celular, só com o painel visível, só com `block: "nearest"`, e nunca com carta armada. É o mesmo padrão da mira (347 R1.2).
- **Retrato nos dois modos (R6.2):** o chip fica 56–72 px mais largo também no `off`. A baseline da 342 não traz `retrato` na fixture e não muda. O impacto real no `off` é visual e intencional (D-354-5).
- **Conflito com a SPEC-352:** as duas mexem em `api.py::_enemy_portrait`. Quem pousar por último faz o rebase e mantém a lógica de registro/preço da 352, tirando só o portão da flag (D-354-8).
- **Conflito com a SPEC-353:** a 353 mexe no `round_board` (contrato `tipo`/`efeito`) e no nome da API. O front daqui aceita a ausência de tudo isso. Se a 353 escolher outros nomes de campo, o executor ajusta `roundEntryKind` e registra na §9.
- **MockLLM/FallbackLLM:** nenhuma chamada de LLM nova. **Latência/quota:** zero request novo por turno. `portrait_for` sem a flag só lê o catálogo curado em memória.

## 8. Decisões

**Do dono:**

- **D-354-A — Corrigir os 8 itens do 2º smoke**, com status `approved` na criação (autonomia até 08:30 de 28/10).
- **D-354-B — Item 1 só fecha com e2e que reabre um save real e falha antes do conserto.** Sem reprodução, o executor para e devolve (R1.1).
- **D-354-C — Item 6: ícone da família sempre que não houver imagem, com `RPG_CREATURE_ART` ligada ou não.**

**Do autor (recomendadas e adotadas; o dono pode reverter):**

- **D-354-1 — Livro "preso ao fim" até o 1º gesto**, em vez de rolar uma vez quando o histórico chega. Alternativa: rolar de novo depois de `load` das imagens e de `document.fonts.ready`. Rejeitada porque não cobre a troca para "lado a lado" nem fontes ou imagens que cheguem depois desses eventos.
- **D-354-2 — Ordem do tabuleiro mantida; o registro encolhe.** No desktop, o `RoundBoard` mostra as últimas 4 jogadas + "Ver a rodada inteira (N)" (revisa a 347 R14.3 "no desktop, todas"). Alternativa: pôr a mão antes do registro. Rejeitada porque a 347 fez do registro a superfície principal da rodada (D-347-C).
- **D-354-3 — Efeitos (DoT, quedas, presságio cumprido) numa lista própria abaixo das jogadas**, e não intercalados. Perde-se a posição exata do tique no tempo. Em troca, o registro deixa de parecer que o jogador atacou quando ele sofreu dano. Se o dono preferir a ordem exata, a alternativa é manter o tique no lugar, com estilo de efeito e sem ícone de herói.
- **D-354-4 — Registro da rodada final: view mínima nesta spec**, se `last_round_board` sobreviver ao fim do conflito (3 linhas em `api.py`). Se exigir guardar no motor, fica com a SPEC-353, e o front consome quando existir.
- **D-354-5 — O retrato (arte ou marcador) aparece também no modo `off`.** "Sempre" vale para os dois modos. Alternativa: só no Baralho, para não mexer no `off`.
- **D-354-6 — Na vitória com o painel de Combate visível, o toast some** (os ganhos já estão no desfecho). Nos outros turnos, o toast vai para o fluxo, entre o Livro e o composer.
- **D-354-7 — `displayName` humaniza id como último recurso** ("npc_ketil" → "Ketil"). É melhor um nome aproximado que um id. O nome certo é responsabilidade da API (SPEC-353).
- **D-354-8 — Fronteira:** backend aqui só em `_enemy_portrait` (sem o portão) e, se D-354-4 permitir, em `_combat_block` (registro final). Nome na API, `tipo`/`efeito` no `round_board` e motor são da SPEC-353. O fluxo pago é da SPEC-352.

**O que o dono ainda pode querer decidir** (nada bloqueia a execução; os defaults acima valem):

1. D-354-3: efeitos numa lista separada (default) ou intercalados no tempo.
2. D-354-5: retrato também no `off` (default) ou só no Baralho.
3. D-354-2: últimas 4 jogadas no desktop (default) ou outro número.
4. Coordenador: avisar o autor da SPEC-353 do contrato `tipo`/`efeito` em §3 (o front daqui já aceita a ausência).

## 9. Notas de implementação

**Executor (28/10, Sonnet), o que ficou feito e o que não.**

- **R1 (Livro reabre no prólogo) — NÃO reproduzido; nenhuma correção feita (D-354-B).** `web/e2e/spec354-livro.spec.ts` + `fixtures/spec354/save-real.json` (gravação de `/game/saves`, `/game/state`, `/game/history` de um save real local, Batatof, 51 entradas; o save do smoke, Haldor, não existe nesta máquina). Reabre pela lista de saves (`page.goto("/")` → clique) a 1440 e a 390 (aba Crônica), com 4 imagens de cena de 300 ms, combate ativo na montagem (`SPEC354_COMBAT=1`), API lenta 700 ms e CPU 4× (`SPEC354_SLOW=1`): sempre `gap` 0 (ex.: scrollTop 24347 de 24768; 390: 30397 de 30885). H1 e H2 não se confirmaram nesse ambiente. Os testes ficam como regressão (verdes). Falta o save real do smoke (ou o `GET /game/history` dele) para reproduzir.
- **R2:** `data-queue-tail` + `scrollIntoView({block:"nearest"})` da cauda da fila só no celular/sem carta armada, `focus({preventScroll:true})`, `scroll-padding`. Teste `fila_cheia_sem_sobreposicao_390` a 390×480 (celular baixo; a 844 a fixture não estoura a barra): vermelho sem o fix, verde com.
- **R3/R5:** `RoundBoard` em uma coluna, 4 últimas jogadas + "Ver a rodada inteira (N)" (desktop também; o SSR da 347 foi ajustado), "Efeitos da rodada" (até 2 + resto no details), `roundEntryKind` infere `tipo`, chip "Acerto · sem dano". R3.3 precisou só do **(c)**: `minmax(12rem)` nos chips (a (a) e a (b) não foram necessárias): a 1ª carta fica em y 747–864 de 900. **Desvio:** `arena_tres_zonas_1440` (347) passou de ≥224 px para ≥192 px por causa do 12rem.
- **R4:** `_combat_block` devolve `registro_rodada` sem pilhas quando o conflito acabou (`last_round_board` sobrevive ao fim; as pilhas é que são apagadas; `tests/test_spec354_final_round_view.py`). Painel: "O desfecho" (última narração, `line-clamp` 6, "Ler na Crônica") e "A última rodada". Testes `combat-outcome` e `M05` (strict mode: o texto agora aparece também no painel) foram escopados à região "Narrativa".
- **R6:** `_enemy_portrait` sem o portão da flag (rebase com a 352: não houve conflito, 352 não pousou até aqui). `test_spec347_creature_art.py` atualizado (antes afirmava "sem chave `retrato`"). O e2e `retrato_marcador_sem_flag` não foi escrito: o `TargetChip` não mudou (a 347 já cobre marcador/imagem no front) e a mudança é só de view (pytest).
- **R7:** `OutcomeToast` agora no fluxo (desktop), entre o Livro e o composer; `suppress` com `combat_result` e Combate à vista. **R8:** já passava (`cabecalho_44_coarse_1440` é regressão; sem mudança de CSS). **R9:** `displayName` (+ aplicado em Arena, RoundBoard, `nameOf`); tipos de `PartyMember`/`NpcView` não têm id, então o casamento é por nome humanizado.
- **Não feito:** R1.2 (sem reprodução), `subir_e_receber_narracao_nao_puxa` é fraco (injeta DOM, não passa pelo React); `spec354-prints` e o smoke real (§6); R1.3 de verdade. Baseline 342: verde, sem regeração.
