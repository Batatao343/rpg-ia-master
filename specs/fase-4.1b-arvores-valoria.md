# SPEC — Fase 4.1b: Árvores de Valoria — subclasses e habilidades lore-driven

> **Status:** `done` (2026-07-04 — executada por Fable; smoke LLM real coberto pelo item 3 do smoke da 4.1)
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 4.1 Etapas 1–2a (schema da árvore + validadores) — o schema é
> definido lá; esta spec só produz CONTEÚDO válido contra ele
> **Desbloqueia:** Fase 4.1 Etapas 3–7 (elegibilidade, hooks, UI) · Fase 4.2 (buffs — consome `effects`)
>
> ### ⚠️ EXECUTOR OBRIGATÓRIO: modelo **Fable** (claude-fable-5)
>
> Esta spec é 90% autoria criativa: pesquisa de lore no Codex + design de 20 ramos
> temáticos + escrita de ~80 habilidades novas com identidade mecânica E narrativa.
> Não delegar a modelo menor nem a subagent com modelo menor. Se a sessão atual não
> estiver rodando Fable, PARAR e avisar o usuário antes de começar.

---

## 1. Contexto & Objetivo

A Fase 4.1 entrega o **motor** de progressão (XP, level up, escolha na árvore). Esta
spec entrega as **árvores em si**: para cada uma das 10 classes, uma árvore única com
**2 ramos** que funcionam como **subclasses** — cada ramo ancorado nos **conceitos
fundamentais de Valoria**, com identidade mecânica própria (não reskin um do outro).

**Os pilares temáticos do mundo (toda árvore respira isso):**

- **Mundo vazio** — civilização caiu; o que existe é resto, ruína, sobrevivente.
- **O Abismo domina** — a ameaça de fundo é constante e maior que qualquer fação.
- **Magia corrompe** — poder mágico cru cobra preço de quem o toca.
- **Controle exige sacrifício OU tecnologia prévia** — as duas únicas formas seguras
  de canalizar magia: pagar com algo seu (sangue, vitalidade, memória) ou filtrá-la
  por instrumento da era anterior.

Cada ramo é uma **postura diante desses pilares** (ex.: para um caster — sacrificar
para controlar vs instrumentar para controlar; para um marcial — resistir ao vazio
vs explorá-lo). Fação/região/tradição do Codex pode dar cor e nome, mas é tempero,
não requisito.

Hoje `player_abilities.json` tem 45 habilidades flat, sem dono, e várias são
"só texto" (buff que nunca vira número). Meta: escolher um ramo tem que **soar como
uma escolha que só existe em Valoria** e **mudar como o personagem joga**
(burst vs controle, sustain vs risco).

Princípios: mecânica é Python (habilidade descreve efeito em campos que o motor
resolve — nunca prosa solta); **pesquisar o Codex antes de escrever para pegar o TOM
do mundo** (pode pesquisar tudo, inclusive `hidden`/`secret` — mas NADA de spoiler
no resultado: nome/descrição de habilidade nunca revela segredo do lore).

## 2. Requisitos

- **R1** — Cada uma das 10 classes tem: **tronco comum** (3–4 habilidades, tier 1,
  sem ramo) + **2 ramos** (4–5 habilidades cada, tiers 2–3, com `requires` formando
  cadeia dentro do ramo). Total por classe: 11–14. Total geral: ~120 (reaproveitar
  as 45 existentes onde couberem — atribuindo `classes`/`branch`/`tier` — e escrever
  ~75–85 novas).
- **R2** — Todo ramo é ancorado em **pelo menos um pilar temático** de Valoria
  (mundo vazio / Abismo / magia corrompe / controle por sacrifício ou tecnologia):
  campo `theme` do ramo declara o pilar + a postura ("sacrifício", "instrumento",
  "resistir ao vazio"...). `lore_ref` (entidade do grafo) é **opcional** — usar
  quando uma fação/região der cor natural ao ramo; se presente, deve resolver em
  `data/graph/entities.json`. Proibido inventar fação/lugar novo com nome próprio.
- **R3** — Os 2 ramos de uma classe têm **identidades mecânicas distintas e
  nomeáveis** (ex.: "burst de dano com custo de HP" vs "controle e atrito"). A tabela
  de design (§3, apêndice A) declara a identidade de cada ramo ANTES da autoria das
  habilidades; habilidade que não sirva à identidade do ramo não entra.
- **R4** — Zero habilidade só-texto: toda habilidade tem OU efeito que o motor atual
  resolve (`damage_formula` ≠ "0", cura, DoT/condição em `conditions`, `save_stat`)
  OU `effects` tipado (schema da 4.1) que a Fase 4.2 tornará mecânico. Buff novo SEM
  `effects` tipado = reprovado na validação.
- **R5** — Nomes/descrições em PT-BR, tom do mundo (dark, pós-queda, mundo vazio,
  tecnologia suja + magia que cobra preço — coerente com o Codex), UTF-8. Descrição
  pode citar fação/região quando der cor natural, mas o obrigatório é RESPIRAR os
  pilares — magia nunca é gratuita, poder sempre tem custo ou instrumento.
- **R6** — **Anti-spoiler:** pesquisar pode incluir `hidden`/`secret` (para calibrar
  tom), mas nome/descrição/nome de ramo NUNCA revela fato que só existe em chunk
  `hidden`/`secret` (revelação de personagem, verdade oculta da história, existência
  de entidade secreta). Teste do jogador: quem só viu lore `public` não pode aprender
  nada novo sobre a TRAMA lendo a árvore.
- **R7** — Documento de design entregue como apêndice A DESTA spec (tabela por
  classe: ramos, âncora de lore, identidade mecânica, lista de habilidades) —
  preenchido durante a execução, vira registro permanente.
- **R8** — Validação automática: os testes de schema da 4.1 Etapa 2a passam
  (`classes`/`tier`/`level_req`/`requires` válidos, sem ciclo, ramo consistente) +
  testes desta spec (≥ 2 ramos/classe, ≥ 4 habilidades/ramo, `lore_ref` resolve no
  grafo de entidades, R4 verificado por assert).

### Fora de escopo

- Motor de elegibilidade/escolha/lock de ramo (Fase 4.1).
- Efeito mecânico de `effects` em combate (Fase 4.2 — aqui só se PREENCHE o campo).
- Classes novas; habilidades de inimigos (4.6); habilidades de companion (4.5).
- Rebalancear números das 45 habilidades legadas que ficarem no tronco.

## 3. Design técnico

### Processo obrigatório (por classe, nesta ordem)

1. **Pesquisa de lore** — Grep em `data/codex/**` e `data/graph/entities.json` pelos
   temas da classe (NUNCA Read inteiro de arquivo de lore — CLAUDE.md). Objetivo:
   pegar o TOM (vocabulário, imagens, como o mundo fala de magia/vazio/Abismo) e
   levantar cores opcionais (fação/região/tradição). Pode ler `hidden`/`secret` —
   filtro anti-spoiler é na SAÍDA (R6), não na pesquisa.
2. **Design dos ramos** — escolher 2 posturas que criem TENSÃO entre si diante dos
   pilares do mundo (duas respostas rivais à mesma pergunta — ex.: "como se controla
   o que corrompe?" → sacrifício vs instrumento); definir `theme` + identidade
   mecânica de cada; preencher a linha da classe no apêndice A.
3. **Autoria** — escrever as habilidades no JSON, encadeando `requires` dentro do
   ramo (tier 2 → tier 3).
4. **Validação** — rodar os testes de schema + desta spec antes de passar à próxima
   classe.

### Posturas candidatas por classe (ponto de partida — o design real sai da pesquisa)

Formato: pergunta do mundo que a classe encara → duas respostas rivais (= ramos).
Fações/regiões entre parênteses = cor OPCIONAL, não âncora obrigatória.

| Classe | Pergunta | Postura A vs Postura B |
|---|---|---|
| Cavaleiro da Vigília | O que se protege num mundo vazio? | Muralha: resistir, custe o que custar vs Lança: eliminar a ameaça antes que chegue (cor: Legião de Ferro) |
| Batedor das Fronteiras | Como se vive no vazio? | Ler o ermo (rastreio, atrito) vs Tornar-se parte dele (emboscada, isolamento) |
| Arcanista Cinzento | Como controlar o que corrompe? | Instrumento: tecnologia prévia filtra tudo (cor: Clãs Tecnológicos) vs Exposição calculada: tocar a fonte crua e pagar aos poucos |
| Sangromante | Quanto de si vale o poder? | Sacrifício medido (dívida, sustain) vs Hemorragia total (burst, all-in) |
| Inquisidor da Cinza | O fogo purifica ou consome? | Pureza: queimar a corrupção (medo, controle) vs Fornalha: virar o incêndio (dano sustentado, autodano) |
| Pastor de Pragas | Simbiose: quem hospeda quem? | Ciclo: praga como equilíbrio (DoT, atrito) vs Colmeia: entregar o corpo ao enxame (transformação, risco) |
| Sombra da Corte | O que mata mais: lâmina ou segredo? | Veneno/execução vs Informação/manipulação (cor: Mão Sombria, Guilda dos Corvos) |
| Sapador da Fuligem | O que a era anterior deixou? | Engenharia de cerco (preparo, área) vs Sucata viva (improviso, gambiarras voláteis) |
| Médico de Campo | Curar num mundo que não cura? | Triagem: manter vivo a qualquer custo vs Alquimia: o remédio que também é veneno |
| Guardião Selvagem | A natureza sobreviveu? | Guardar o que resta (proteção, terreno) vs Canalizar o que ela virou (feral, corrompido-controlado) |

### Formato (schema definido na 4.1 — repetido aqui por conveniência)

`classes.json`, por classe:

```json
"branches": {
  "fornalha": {
    "name": "Discípulo da Fornalha",
    "theme": "controle pela tecnologia prévia — virar o incêndio em vez de temê-lo",
    "lore_ref": "encapuzados_fornalha",
    "identity": "Dano de fogo sustentado + autodano controlado",
    "description": "..."
  },
  "chama_azul": { ... }
}
```

(`theme` obrigatório — pilar + postura; `lore_ref` opcional — quando presente,
resolve no grafo.)

`player_abilities.json`, por habilidade (campos novos sobre os existentes):

```json
"marca_da_fornalha": {
  "name": "Marca da Fornalha",
  "classes": ["Inquisidor da Cinza"],
  "branch": "fornalha",
  "tier": 2, "level_req": 3,
  "requires": ["<id tier anterior do ramo>"],
  "cost": 6, "resource_type": "Mana",
  "damage_formula": "2d6+cha_mod", "damage_type": "Fogo",
  "conditions": ["Queimadura (2 dano/turno, 3 turnos)"],
  "save_stat": "dex",
  "effects": [{"kind": "dot", "stat": null, "delta": 2, "duration": 3}]
}
```

(`branch: null` ou ausente = tronco comum. `effects` só quando o efeito não é
resolvível pelos campos atuais — buffs, controle.)

### Distribuição mecânica mínima por ramo (guard-rail anti-monotonia)

- ≥ 1 habilidade de dano direto com escala (`scaling_formula` ≠ "0")
- ≥ 1 habilidade com `save_stat` (interage com atributos do inimigo)
- ≥ 1 buff/controle/utilidade com `effects` tipado
- Custos usam o recurso da classe (stamina p/ marciais, mana p/ casters, misto ok)
- Tier 3 do ramo = habilidade "assinatura" (mais cara, efeito marcante)

## 4. Plano passo a passo

### Etapa 1 — Testes de conteúdo (antes da autoria)

1. **Testes** (`tests/test_fase41b.py`): `test_toda_classe_tem_2_ramos`;
   `test_ramo_tem_4_mais_habilidades`; `test_ramo_tem_theme` (não-vazio);
   `test_lore_ref_quando_presente_resolve_no_grafo`;
   `test_sem_habilidade_so_texto` (R4: damage=0 ∧ sem conditions ∧ sem effects →
   fail); `test_requires_dentro_do_mesmo_ramo_ou_tronco`; `test_distribuicao_minima_por_ramo`.
   (R6 anti-spoiler não é automatizável — vira item de revisão manual na Etapa 3.)
2. **Verificação:** testes existem e FALHAM contra o JSON atual (red).

### Etapa 2 — Autoria classe a classe (Fable)

Para cada classe, o processo do §3 (pesquisa → design → autoria → validação).
Commit por classe ou por par de classes (revisão incremental possível).

### Etapa 3 — Passe de coerência final

1. Reler apêndice A completo: 20 ramos, nenhuma identidade mecânica duplicada
   entre classes vizinhas (ex.: dois ramos "DoT de veneno" — diferenciar).
2. **Passe anti-spoiler (R6):** reler nome/descrição de TODO ramo e habilidade nova
   perguntando "isso revela algo que só existe em chunk `hidden`/`secret`?" —
   qualquer dúvida, reescrever mais vago.
3. `uv run pytest` completo verde (schema 4.1 + conteúdo 4.1b).
4. Conferir encoding (arquivo JSON legível em UTF-8, sem mojibake).

## 5. Critérios de aceite

- [ ] 10 classes × 2 ramos, todos com `theme` (pilar + postura); `lore_ref` presente
      resolve no grafo
- [ ] ~120 habilidades no total, zero só-texto (R4 automatizado)
- [ ] Apêndice A preenchido (registro de design permanente)
- [ ] Identidades mecânicas distintas dentro de cada classe (R3)
- [ ] Passe anti-spoiler feito (R6 — revisão manual registrada no apêndice A)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Executado pelo modelo Fable (anotar no apêndice A)

## 6. Smoke test com LLM real

Conteúdo puro — sem request novo próprio. Coberto pelo smoke da 4.1 (item 3:
habilidade nova escolhida no level up funciona em combate real via parser Gemini).
Adicional: 1 request de storyteller num local ligado a um ramo (ex.: Skallgard)
para conferir que a narração convive bem com o nome da habilidade.

## 7. Riscos & compatibilidade

- **Lore drift:** modelo inventar fato específico do mundo — mitigado pelo processo
  pesquisa-primeiro e por ancorar em PILAR temático (conceito não drifta como fato).
  Na dúvida, ficar no conceito e não citar entidade.
- **Vazamento de segredo:** R6 + passe anti-spoiler manual da Etapa 3 (pesquisa é
  livre; o filtro é na saída).
- **Volume:** ~120 entradas à mão — commit incremental por classe evita perder
  trabalho e permite revisão do usuário no meio.
- **`effects` órfão até a 4.2:** campo preenchido mas inerte — aceitável e
  deliberado (4.2 liga o motor; formato já definido na 4.1 evita retrabalho).
- **Saves antigos:** sem impacto além do já coberto pelo backfill da 4.1 (ids).

---

## Apêndice A — Registro de design

> Executor: **Claude Fable 5** (claude-fable-5), 2026-07-04.
> 111 habilidades (66 novas + 45 reatribuídas), 20 ramos, 10 troncos.
> Fontes de tom pesquisadas: `timeline/` (magia provém do caos do Abismo; custo
> corporal — "veias escurecem, mente se dissolve"; Destilação = transferir o custo),
> `factions/` (Fornalha/Chama Azul/Clãs/Druidas/Colmeia/Corvos/Mão/Anões/goblins/
> Martelos), `world_story/` (Éter denso de Aethelgard).

| Classe | Ramo | Theme (pilar + postura) | lore_ref | Identidade mecânica | Habilidades |
|---|---|---|---|---|---|
| Cavaleiro da Vigília | Juramento da Muralha | mundo vazio — resistir | cidades_estado_sobreviventes_vaelorn_solvhen | tank: AC, provocação, punição | muralha_de_escudos, golpe_do_escudo, provocacao_de_ferro, ultimo_bastiao |
| Cavaleiro da Vigília | Lança da Vigília | mundo vazio — eliminar antes | legiao_ferro | burst focado, quebra de linha, medo | carga_de_lanca, quebra_linha, decapitar, julgamento_da_vigilia |
| Batedor das Fronteiras | Leitor do Ermo | mundo vazio — ler o que restou | bandos_nomades | atrito: sangramento, marca, precisão | flecha_farpada, marca_do_cacador, tiro_certeiro, chuva_do_ermo |
| Batedor das Fronteiras | Fantasma da Fronteira | mundo vazio — virar parte dele | renegados_ermo | emboscada: burst, evasão, stun | emboscada, passo_do_ermo, golpe_do_silencio, apagar_se |
| Arcanista Cinzento | Mão Instrumentada | tecnologia prévia — filtrar tudo | clas_tecnologicos | recurso: dreno, dano calibrado | sifao_de_mana, condensador_de_eter, descarga_calibrada, poco_de_gravidade |
| Arcanista Cinzento | Toque Descoberto | magia corrompe — pagar aos poucos | cultos_despertar_dispersos | risco/retorno: autodano, controle | teleporte_instavel, chama_do_abismo, veias_negras, sussurro_de_controle |
| Sangromante | Dívida Medida | sacrifício — contabilizado | cultistas_destilacao | sustain: dreno, pactos com prazo | drenar_vida, pacto_medido, sangria_ritual, camara_de_cristal |
| Sangromante | Hemorragia Total | sacrifício — tudo de uma vez | — | burst all-in pago em HP | explosao_de_cadaver, erupcao_carmesim, ultimo_folego, apoteose_do_sangue |
| Inquisidor da Cinza | Chama que Purga | Abismo — queimar a corrupção | filhos_chama_azul | medo, fogo punitivo, pira | batismo_de_brasa, chama_do_juizo, interrogatorio_ardente, pira_da_pureza |
| Inquisidor da Cinza | Discípulo da Fornalha | tecnologia prévia — virar o incêndio | encapuzados_fornalha | fogo sustentado + autodano | lanca_chamas, aco_de_sangue, bafo_da_fundicao, coracao_de_forja |
| Pastor de Pragas | Guardião do Ciclo | Abismo — conter a podridão | druidas_ciclo_cinzento | DoT de área, root, dreno+cura | mortalha_de_esporos, seiva_cinzenta, enraizar, equilibrio_do_pantano |
| Pastor de Pragas | Voz da Colmeia | magia corrompe — simbiose extrema | colmeia_hospedeiros | transformação paga em carne | hospedar_enxame, erupcao_de_quitina, sentinelas_aladas, mente_partilhada |
| Sombra da Corte | Lâmina Contratada | mundo vazio — morte como serviço | mao_sombria | execução single-target, veneno | garrote, chuva_de_agulhas, veneno_do_contrato, golpe_de_misericordia |
| Sombra da Corte | Olho do Corvo | mundo vazio — informação > sangue | guilda_corvos | debuff, manipulação, medo | chantagem, rede_de_informantes, lamina_no_escuro, xeque_da_corte |
| Sapador da Fuligem | Engenheiro de Cerco | tecnologia prévia — o manual anão | ultimos_anoes_reino | preparo, área, torreta, escudo | granada_flashbang, escudo_de_energia, carga_de_demolicao, torreta_automatica |
| Sapador da Fuligem | Alquimista da Sucata | mundo vazio — improviso volátil | goblins_mineiros | gambiarras: dano alto instável | sobrecarga, bomba_de_pregos, mistura_instavel, obra_prima_de_refugo |
| Médico de Campo | Cirurgião de Trincheira | mundo vazio — vivo a qualquer custo | resistencia_operaria_martelos_partidos | cura pesada, stun químico | granada_de_cura, serra_de_campo, anestesia_bruta, milagre_de_campo |
| Médico de Campo | Boticário do Limiar | magia corrompe — remédio do veneno | mercadores_curiosidades | química dual: corrosivo, panaceia | injecao_de_furia, frasco_corrosivo, vapores_do_limiar, panaceia_negra |
| Guardião Selvagem | Raiz que Resta | mundo vazio — guardar o verde | floresta_sussurros | proteção territorial, root | pele_de_casca, prisao_de_raizes, chicote_espinhoso, coracao_da_floresta |
| Guardião Selvagem | O Que Ela Virou | magia corrompe — canalizar o corrompido | druidas_renegados | feral: garras, instinto, uivo | garras_negras, instinto_corrompido, uivo_do_vazio, forma_do_abismo |

Troncos novos: postura_vigilante (Cav), bencao_dos_fungos (Pas), diagnostico_frio
(Méd), passo_da_mata (Gua). Reatribuições notáveis: estocada_renal e quebra_joelhos
compartilhadas entre 2 classes; raio_de_ferrugem e lanca_chamas idem.

> Passe anti-spoiler (R6) executado em 2026-07-04 · Resultado: **ok** — nomes/
> descrições usam só material `public` (Batismo de Fogo, Fundições, Destilação,
> Colmeia, Éter, Abismo genérico); nenhuma referência aos 4 reveals protegidos
> (Arauto, Rei Subterrâneo, pacto, Rede Carmesim) nem a Thessrak/Urath.
