# SPEC-198 - Rascunho da ficha da loja (Google Play)

> RASCUNHO para o usuario aprovar. Nome publico, desenvolvedor, e-mail e URLs dependem de `docs/spec197/external-inputs.md`
> (itens 6, 7, 11, 12). Nada aqui foi enviado ao Play Console.

## Metadados

| Campo | pt-BR (padrao) | en-US |
|---|---|---|
| Titulo (max 30) | `Valoria - RPG de Texto com IA` (29) | `Valoria: AI Text RPG` (20) |
| Descricao curta (max 80) | `RPG sombrio de texto: sua jornada em Valoria, narrada por IA, no seu ritmo.` | `A dark text RPG: your journey through Valoria, narrated by AI, at your pace.` |
| Categoria | Jogos > Role Playing (alternativa: Aventura) | idem |
| Tags sugeridas | RPG, texto, fantasia sombria, narrativa, IA | idem |
| E-mail de contato | `suporte@<dominio>` (obrigatorio) | idem |
| Site / Privacidade | `<URL publicada /privacidade>` (obrigatoria, https, sem PDF) | idem |
| Preco | App gratuito, com compras no app (consumiveis: Estilhas) | idem |

> Titulo: nao usar emojis, preco, "melhor", "gratis" ou "#1" (politica de metadados). Nome final decidido pelo usuario.

## Descricao completa (pt-BR)

Valoria e um RPG de texto de fantasia sombria. Voce cria um personagem, escolhe uma das cinco Posturas diante do Abismo e
percorre um mundo vivo - cidades, ruinas, faccoes e segredos - em campanhas narradas por inteligencia artificial.

O QUE VOCE FAZ
- Escreva (ou fale) o que seu personagem faz; o mundo responde com narrativa original a cada turno.
- Combate tatico por Cartas, com Reacoes, Ferimentos e consequencias reais. A matematica e do jogo, nao da IA.
- Explore um mapa de 35 locais, converse com NPCs que lembram de voce, recrute aliados e siga missoes.
- Sua cronica e salva por capitulo: continue de onde parou, em qualquer dispositivo da sua conta.
- Entrada por voz opcional: o audio nao e armazenado em nossos servidores; e enviado ao provedor de transcricao, sujeito a retencao dele.

CONTA E COMPRAS
- Crie uma conta com e-mail. Exporte ou exclua seus dados no proprio app.
- Estilhas sao a moeda opcional para recursos como imagens geradas por IA. O jogo base nao exige compra.
- Compras sao feitas pelo Google Play.

AVISOS
- Conteudo gerado por IA: as historias sao ficcao e podem conter violencia de fantasia.
- Requer conexao com a internet.

## Descricao completa (en-US)

Valoria is a dark-fantasy text RPG. Create a character, choose one of five Postures before the Abyss, and travel a living
world of cities, ruins, factions and secrets in campaigns narrated by artificial intelligence.

WHAT YOU DO
- Type (or speak) what your character does; the world answers with original narration every turn.
- Tactical Card combat with Reactions, Wounds and real consequences. The math is the game's, not the AI's.
- Explore a 35-location map, talk to NPCs who remember you, recruit allies and follow quests.
- Your chronicle is saved chapter by chapter: continue anywhere with your account.
- Optional voice input: audio is not stored on our servers; it is sent to the transcription provider and subject to that provider's retention.

ACCOUNT AND PURCHASES
- Sign up with email. Export or delete your data inside the app.
- Shards are the optional currency for features such as AI-generated images. The base game requires no purchase.
- Purchases go through Google Play.

NOTICES
- AI-generated content: stories are fiction and may include fantasy violence.
- Internet connection required.

## Questionario de classificacao de conteudo (IARC) - rascunho de respostas

Categoria do app: **Jogo**. Respostas propostas (o usuario confirma; as respostas tem de refletir o app real, nao o desejado):

| Pergunta IARC | Resposta proposta | Justificativa |
|---|---|---|
| Violencia | Sim - violencia de fantasia, nao realista, contra criaturas/NPCs; texto, sem imagens graficas de gore | combate/morte narrados em texto; arte estilizada |
| Sangue/gore | Sim, leve/descritivo em texto (Sangromante, ferimentos) - revisar contra a arte curada | classe tematica |
| Conteudo sexual / nudez | Nao | nao ha conteudo sexual; ver risco de IA abaixo |
| Linguagem impropria | Possivel, leve - conteudo gerado por IA | narrador sem filtro absoluto |
| Substancias controladas | Referencias fantasiosas (pocoes/venenos); sem drogas reais | revisar |
| Jogos de azar simulados / apostas | Nao | sem cassino |
| Interacao entre usuarios / chat | Nao - single player; sem UGC compartilhado | confirmar |
| Compartilha localizacao | Nao | |
| Compras digitais | Sim | Estilhas (consumiveis) |
| Conteudo gerado por usuario / IA generativa | Sim - texto livre do jogador e narracao/imagens por IA | declarar; ha moderacao basica? (confirmar - risco R-IA) |

Faixa esperada: **12+ / PEGI 12 / ClassInd 14** (confirmar o resultado oficial; a IARC calcula). Se o narrador de IA puder produzir
conteudo mais forte, o resultado sobe - nao subestimar. A politica de **conteudo gerado por IA** do Google exige mecanismo de
denuncia/feedback no app: **lacuna a verificar antes da producao** (hoje so ha suporte por e-mail).

## Politica de contas

Google exige **exclusao de conta no app E URL web** para exclusao. No app existe (SPEC-190); a URL web de solicitacao de exclusao
deve apontar para a pagina de suporte/privacidade (`<URL>`). Registrar no formulario Data Safety.

## Plano de capturas de tela

Requisitos: 2-8 capturas de celular, PNG/JPEG 24 bits sem alfa, lado 320-3840 px, proporcao max 2:1 (usar 1080x2400 ou 9:16).
Plano de 6 (pt-BR; repetir em en-US depois):
1. Tela inicial / continuar jornada (arte e marca)
2. Criacao de personagem (cartas de raca/classe)
3. Narracao de turno com arte do local
4. Combate tatico (mao de Cartas + Reacao)
5. Mapa / fog of war
6. Ficha do personagem / cronica
Legenda curta por imagem (sobreposicao opcional, sem texto enganoso).

**Estado (15/10):** 3 capturas de TRABALHO (login, home, narracao) feitas no emulador `rpg34` contra o staging com usuario sintetico
(removido; HTTP 200, `exists=False`) em `screenshots/draft_*.jpg` (540x1200, comprimidas). **Nao servem para a loja:** o staging usa
`RPG_FORCE_MOCK=1` (narracao simulada com texto quebrado: "Voce descreva o cenario...") e a UI mostra botoes de cotacao
("COTAR RETRATO") que sao de operacao. Alem disso, o cabecalho da home sobrepoe "CONTA - 0 ESTILHAS" e "ENCERRAR SESSAO" em 390 px
(bug visual, corrigir antes das capturas finais). Capturas finais: producao/staging com LLM real + `scripts/android/store_screenshots.mjs`
(ajustar passos de combate/mapa; os cliques genericos de Ficha/Mapa/Cronica nao abriram painel). Criar usuario sintetico e limpar depois.

## Feature graphic (obrigatorio)

1024 x 500 px, PNG/JPEG sem alfa. Conteudo: arte de Nova Arcadia (de `web/public/art`, ja curada) escurecida com gradiente,
titulo "VALORIA" em fonte serifada dourada (a mesma da UI) e subtitulo "RPG de texto narrado por IA". Sem screenshots de UI,
sem precos, texto dentro da zona central 80%. Icone da loja: 512x512 PNG (a partir do brasao do app).
