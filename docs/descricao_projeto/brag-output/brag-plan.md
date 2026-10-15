# /brag — rpg-ia-master

**O que é:** um RPG de texto dark fantasy em que uma IA é o mestre do jogo — mas cada dado, dano e moeda é resolvido em código determinístico.
**Para quem:** quem gosta de RPG de mesa e quem constrói produtos com IA (o post é para LinkedIn).
**Diferencial:** "a IA narra, o Python decide" — a IA não consegue trapacear.
**Claim mais forte:** o mestre de IA não pode roubar nos dados.
**Gancho visual:** os retratos pintados de Valoria saindo do escuro.
**UI real mostrada:** wizard de criação (cards de classe com arte), prólogo "Dívidas de Sangue", tela de jogo com digitação e narração, mão de Cartas no combate — capturados do app rodando (modo simulado, sem custo).
**Tom:** cinematic, dark fantasy (Cinzel + EB Garamond, bronze sobre ardósia, sangue só para perigo — as cores do próprio `styles.css`).
**Legenda de compartilhamento:** "Construí um mestre de RPG com IA que não pode roubar nos dados."

## Storyboard (25 s, 1920×1080, 30 fps, sem narração)

| # | Tempo | Cena | Texto na tela | Som |
|---|---|---|---|---|
| 1 | 0,0–3,2 | Retrato do Arcanista Cinzento sai do escuro, push-in lento, brasas | "E se o mestre do jogo fosse uma IA…" | trilha entra |
| 2 | 3,2–6,4 | Fundo preto, dois d10 rolam e param em 7 e 10 | "…que não pode roubar nos dados?" | dados rolando |
| 3 | 6,4–10,4 | Seis retratos de raças deslizam em fila; título | "CRÔNICAS DE VALORIA" · "Um RPG de texto dark fantasy narrado por IA" | cartas deslizando, impacto suave |
| 4 | 10,4–14,4 | Wizard real (cards de classe) → painel do prólogo entra | "Escolha quem você é." · "A IA escreve seu prólogo." | carta |
| 5 | 14,4–18,6 | Gravação real: digitando uma ação, a narração aparece | "Escreva qualquer ação. O mundo responde." | teclado ao fundo |
| 6 | 18,6–22,2 | Combate real: mão de Cartas; chip de rolagem 2d10 + Virtude 17 vs Esquiva 13 → ACERTO | "A IA narra. O Python rola os dados." | carta + dados |
| 7 | 22,2–25,0 | Fechamento com brasas | "rpg-ia-master" · "A IA narra. O Python decide." · crédito da trilha | final da trilha |

Transições: saída do conteúdo antigo → mergulho no escuro → entrada do novo (sem crossfade sujo), com um brilho dourado varrendo nas viradas maiores.

## Áudio
- Trilha: últimos 25 s de "Crossing the Chasm" (Kevin MacLeod, incompetech.com, CC BY 4.0) — o final da música coincide com o fim do vídeo.
- Efeitos: dados, cartas, teclado e impacto suave do kit do /brag (Kenney, CC0), mixados baixo, sob a música.

## Números usados
O exemplo de ataque (2d10 = 13, + Força 4 = 17 contra Esquiva 13) é o ataque real executado na exploração do código (Devoto nível 1 contra Rato da Peste).
