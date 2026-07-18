# Sistema de Classes — Valoria

> Retrato do sistema em 2026-07-16. Fontes da verdade: `data/classes.json` (fichas),
> `data/class_themes.json` (gating narrativo), `data/player_abilities.json` (árvores,
> 111 habilidades), `progression.py` (XP/level up/subclasse). Specs de origem:
> `specs/fase-4.1-progressao.md` (motor) e `specs/fase-4.1b-arvores-valoria.md` (conteúdo).

---

## 1. Visão geral

O jogo tem **10 classes jogáveis**, todas 100% data-driven — nenhuma classe está
hard-coded em Python. Cada classe define:

- **Ficha base** (`base_stats`): HP/Mana/Stamina, defesa e os 6 atributos
  (`str/dex/con/int/wis/cha`, chaves curtas em runtime).
- **Passiva mecânica** (`passive` + `passive_effects` tipados que o motor resolve).
- **Ganhos por nível** (`level_gains`): quanto HP/Mana/Stamina sobem a cada level up.
- **2 habilidades iniciais** + equipamento inicial.
- **2 ramos de subclasse** (`branches`) ancorados na lore de Valoria.
- **Tema narrativo** (`class_themes.json`): o que a classe pode/não pode tentar.

Princípio central do projeto vale aqui também: **mecânica é Python, não LLM**. A IA
narra; números de passiva, custo, dano e level up resolvem em código determinístico
(`combat_mechanics.py`, `progression.py`).

---

## 2. A lore por trás das classes — os 4 pilares de Valoria

Valoria é um mundo **pós-queda**: a civilização caiu, o que existe é resto, ruína e
sobrevivente. Todo o design de classes e subclasses respira **4 pilares temáticos**
(definidos na spec 4.1b):

1. **Mundo vazio** — civilização caiu; sobreviver é ler, resistir ou explorar o que restou.
2. **O Abismo domina** — a ameaça de fundo é constante e maior que qualquer facção.
3. **Magia corrompe** — poder mágico cru cobra preço de quem o toca.
4. **Controle exige sacrifício OU tecnologia prévia** — as duas únicas formas seguras
   de canalizar magia: pagar com algo seu (sangue, vitalidade, carne) ou filtrá-la por
   instrumento da era anterior.

Cada **ramo** de subclasse é uma **postura diante desses pilares** — nunca um reskin.
Exemplo: o Arcanista Cinzento escolhe entre filtrar a magia por aparelho (tecnologia
prévia) ou tocar a fonte crua e pagar em carne (magia corrompe). O Cavaleiro escolhe
entre resistir ao vazio (muralha) ou eliminá-lo antes que chegue (lança).

Quando cabe, o ramo ganha cor de uma **facção/região do Codex** via `lore_ref`
(entidade real de `data/graph/entities.json` — é proibido inventar facção nova).
Regra anti-spoiler: nome/descrição de habilidade nunca revela fato `hidden`/`secret`
do lore.

---

## 3. As 10 classes

| Classe | Papel | Passiva | HP/Mana/Sta base | Atributos altos |
|---|---|---|---|---|
| **Cavaleiro da Vigília** | Tanque protetor | Muralha Humana: +2 AC com aliado da party ativo | 35 / 0 / 25 | STR 16, CON 16 |
| **Batedor das Fronteiras** | Explorador/dano à distância | Oportunista: +dano vs distraídos | 27 / 5 / 20 | DEX 18 |
| **Arcanista Cinzento** | Caster de controle | Mente Analítica: iniciativa por INT | 22 / 30 / 8 | INT 18 |
| **Sangromante** | Caster de risco | Sacrifício de Sangue: 2 HP = 1 Mana | 25 / 20 / 10 | CON 18, INT 16 |
| **Inquisidor da Cinza** | Tanque ofensivo | Fervor: imune a medo, +2 dano de fogo | 30 / 10 / 20 | STR 16, CHA 16 |
| **Pastor de Pragas** | Controle de área/atrito | Hospedeiro: 1d4 veneno em quem ataca melee | 28 / 25 / 12 | WIS 18, CON 16 |
| **Sombra da Corte** | Assassino social | Toque da Víbora: armas aplicam veneno fraco | 25 / 10 / 15 | DEX 16, CHA 16 |
| **Sapador da Fuligem** | Engenheiro/preparo | Demolidor: dano dobrado vs estruturas¹ | 26 / 0 / 25 | INT 16, STR/DEX 14 |
| **Médico de Campo** | Suporte sem magia | Triagem: +5 cura em alvo < 25% HP | 28 / 5 / 20 | INT 16, DEX 14 |
| **Guardião Selvagem** | Bruiser tribal | Pele Grossa: sem armadura, AC = 10+Dex+Con | 40 / 5 / 30 | STR 18, CON 16 |

¹ Única passiva puramente declarativa (motor não tem estruturas — caso documentado na spec 4.2 R5).
Todas as demais são `passive_effects` tipados que o combate resolve de verdade.

### Subclasses (2 ramos por classe, 20 no total)

Cada ramo tem: pilar temático declarado, identidade mecânica nomeável e, quase sempre,
âncora numa facção do Codex.

| Classe | Ramo A | Ramo B |
|---|---|---|
| Cavaleiro da Vigília | **Juramento da Muralha** — tanque puro: redução de dano, provocação (cidades-estado Vaelorn/Solvhen) | **Lança da Vigília** — dano focado: cargas, execução (Legião de Ferro) |
| Batedor das Fronteiras | **Leitor do Ermo** — atrito à distância: sangramento, marcas (bandos nômades) | **Fantasma da Fronteira** — emboscada: burst de abertura, evasão (Renegados do Ermo) |
| Arcanista Cinzento | **Mão Instrumentada** — controle de recurso: dreno de mana, campo de força (Clãs Tecnológicos de Skallgard) | **Toque Descoberto** — risco/retorno: dano alto com custo de corpo (cultos do Despertar) |
| Sangromante | **Dívida Medida** — sustain: drenar vida, pactos com prazo (cultistas da Destilação) | **Hemorragia Total** — burst all-in: dano máximo pago em HP |
| Inquisidor da Cinza | **Chama que Purga** — controle por medo: fogo punitivo, pira ritual (Filhos da Chama Azul) | **Discípulo da Fornalha** — fogo sustentado: queimaduras, autodano controlado (Encapuzados da Fornalha) |
| Pastor de Pragas | **Guardião do Ciclo** — atrito de área: esporos, dreno lento (Druidas do Ciclo Cinzento) | **Voz da Colmeia** — transformação: enxames hospedados, pago em carne (Hospedeiros de Xylos) |
| Sombra da Corte | **Lâmina Contratada** — execução single-target: venenos, golpe final (Mão Sombria) | **Olho do Corvo** — manipulação: chantagem que paralisa (Guilda dos Corvos) |
| Sapador da Fuligem | **Engenheiro de Cerco** — preparo e área: demolições, torretas (últimos anões do Reino) | **Alquimista da Sucata** — gambiarras: dano alto e instável (goblins-mineiros) |
| Médico de Campo | **Cirurgião de Trincheira** — cura pesada: triagem, milagres sem magia (Martelos Partidos) | **Boticário do Limiar** — química dual: corrosivos e panaceias com preço (Mercadores de Curiosidades) |
| Guardião Selvagem | **Raiz que Resta** — proteção territorial: casca, raízes que prendem (Floresta dos Sussurros) | **O Que Ela Virou** — feral: garras, instinto que cobra em sangue (druidas renegados) |

---

## 4. Árvore de habilidades e progressão

**Pool atual: 111 habilidades** em `data/player_abilities.json` (1 universal
`ataque_basico` + 11–13 por classe), distribuídas em:

- **Tiers:** 31 de tier 1 (tronco comum, sem ramo) · 60 de tier 2 · 20 de tier 3.
- **Recursos:** 61 usam Estamina · 39 Mana · 11 sem custo.
- **`level_req`:** de 1 a 6, com picos em 3 (35) e 4 (25) — a árvore abre cedo e o
  tier 3 fecha em nível 6.

### Como a subclasse acontece (`progression.py`)

Não existe campo "subclasse" no save — a subclasse é **derivada**: o `branch` da
primeira habilidade conhecida que tem ramo (`player_branch()`). Isso torna o sistema
à prova de save antigo. Consequência de design: **escolher a primeira habilidade de um
ramo tranca o ramo rival para sempre** naquela ficha (`eligible_abilities()` filtra o
ramo oposto).

Elegibilidade de habilidade = da classe (ou `all`) ∧ nível ≥ `level_req` ∧
`requires` ⊆ conhecidas ∧ não conhecida ∧ não é do ramo rival. Os `requires` formam
cadeia dentro do ramo (progressão linear com escolhas).

### XP e level up

- XP entra por **kill** (minion 50 / elite 200 / boss 1000), **beat de campanha**
  (150) e **quest** (200) — valores fixos, zero LLM.
- `XP_TABLE` segue a curva clássica de D&D 5e (300 para o nível 2 … 355.000 para o 20).
- Level up (`grant_xp`) processa multi-nível em sequência: sobe máximos pela curva
  `level_gains` da classe e enfileira **`pending_choices`** (habilidade nova ou +1
  atributo), consumidas via `apply_choice` com validação server-side (`/game/levelup`).

---

## 5. Gating narrativo (o que a classe PODE tentar)

`data/class_themes.json` define por classe `allowed` / `forbidden` / `style` — usado
pelo Ruler para julgar habilidades abertas (ação livre digitada pelo jogador).
Determinístico, sem LLM, funciona offline (`agents/class_themes.py`).

Exemplos: o Cavaleiro não lança magia arcana nem usa furtividade de armadura pesada;
o Sapador não usa magia nenhuma ("todo problema tem uma solução com pólvora"); o
Sangromante não tem cura sagrada nem etiqueta de corte.

Complementa isso a régua de poder por nível (`get_power_guideline`):
TIER 1 Iniciante (≤4) → TIER 2 Heroico (≤10) → TIER 3 Mestre (≤16) → TIER 4 Lenda.
O `style` de cada classe também alimenta o tom da narração.

---

## 6. Como o motor consome tudo isso

| Peça | Papel |
|---|---|
| `gamedata.py` | Carrega `classes.json`/`class_themes.json`/`player_abilities.json` → `CLASSES`, `CLASS_THEMES`, `ABILITIES`, `XP_TABLE` |
| `character_creator.py` | Cria a ficha a partir da classe (IA sugere nome/história; números vêm do JSON oficial) |
| `progression.py` | XP, level up, `pending_choices`, derivação de subclasse, elegibilidade, backfill de saves antigos |
| `combat_mechanics.py` | Resolve passivas (`passive_effects`), custos (Mana/Estamina), fórmulas de dano, condições, cooldowns |
| `agents/class_themes.py` | Gating de ação livre + régua de poder por nível |
| `api.py` / `game_engine.py` | Expõem criação, level up (`/game/levelup`) e ficha |

Interação com raças: raças/origens vivem em `data/origins.json` com traits mecânicos
próprios (Fase 2.5b) — classe e raça são eixos independentes da ficha.

---

## 7. Estado e pendências

**O que está sólido:**
- 10 classes completas, cada uma com identidade mecânica E narrativa distinta.
- 20 ramos, todos ancorados nos pilares de Valoria; 19/20 com `lore_ref` real no
  grafo (só Hemorragia Total é deliberadamente sem facção).
- Zero habilidade "só texto" (R4 da spec 4.1b): tudo resolve no motor ou tem
  `effects` tipado.
- Subclasse sem campo novo de estado — compatível com qualquer save.
- Tuning de nível 1 revisado no ciclo de produto (spec balanceamento-early-game).

**Pendências conhecidas:**
- Passiva do Sapador (dano vs estruturas) segue declarativa — motor não tem
  estruturas destrutíveis.
- Habilidades param em `level_req` 6 (tier 3): jogo suporta nível 20, árvore cobre
  até ~6. Expansão de tiers altos é conteúdo futuro (pós-Fase 8/10b).
- `get_power_guideline` (tiers de poder narrativo) e a árvore mecânica usam escalas
  diferentes de "tier" — atenção ao ler código.
