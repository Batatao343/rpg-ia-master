# SPEC-372 — revisão independente (ligações criatura → trama em Nova Arcádia)

> Nome do arquivo: `handoffs/SPEC-372-independent-review.md` (revisor Opus independente, não é o autor das ligações).
> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (`claude-opus-5-5`, `spec-reviewer`) · **Data:** 2026-11-03 · **Commit revisado:** `3a92ece8`

## Escopo

Commit `3a92ece8` (branch `spec-372`): `data/bestiario/fauna/nova_arcadia.yaml` (9 ligações em 8
criaturas), `data/world/fauna.json` regenerado, `data/world/rumor_seeds.json` (1 `sinal_rumor`
reescrito) e a tabela de justificativas da §9 da spec. Checklist §3.5 aplicado ligação a ligação.
Fontes lidas: campos **públicos** das 7 tramas (`title`, `pergunta`, `resumo_publico`, `locations`,
`portas[].hook_public`), a descrição do bestiário e todos os `sinais` das 8 criaturas. Os segredos
(`SECRET_SIGNATURES` e os grupos de `leak_phrases.json` de `corpos`, `praga`, `aco_lembra`,
`elaryin`, `pacto_valerius`) só foram lidos para conferir vazamento, não para julgar o encaixe.
Fora do escopo: motor, flag, avaliador (ver `SPEC-372-sol-review.md`).

## Ligação a ligação (checklist §3.5)

| Criatura → trama · `desde` | 1 Encaixe público | 2 `desde` | 3 Sinais sem segredo/núcleo | 4 Hub | 5 Disputa | Parecer |
|---|---|---|---|---|---|---|
| `mon_rosario_de_vertebras` → `tr_na_corpos_marcados` · tocada | ficha "onde os corpos sem Corvo acabam" (`fichas/nova_arcadia.yaml:220`) × resumo "certos corpos nunca chegam ao forno" | sintoma visível → `tocada` ok | rastro/som/rumor só descrevem a criatura no canal; nada de Silas Vane, Mãe Corva, venda ou destino dos corpos | Lama mantém 13 de 16 não-BOSS | 1 trama | OK |
| `mon_sangrado_da_clinica` → `tr_na_corpos_marcados` · investigada | ficha "doente da Praga sangrado numa clínica" × pergunta "o médico que os estuda" (campo público) e porta p2 "enfermeira da clínica" | consequência do tratamento → `investigada` ok | lanceta, cortes, "paciente que saiu curado volta pedindo desculpa": aponta a clínica (conteúdo da 360, já aprovado), não o laboratório nem a cepa (`praga`) nem o nome do médico | Ferro mantém 17 de 22 | 1 trama | OK |
| `mon_sorvedouro_do_codigo` → `tr_na_lista_de_fornalha` · tocada | ficha "patrulha os anéis de baixo atrás de magia não registrada" × resumo "no Lama e no Ferro quem tem o Éter escolhe entre se esconder e se inscrever" | sintoma visível → `tocada` ok | lacre com número de artigo, recitação; trama sem `secret_ids`; nada de Sylvenne/Sennar | território = locais da trama | 1 trama | OK |
| `mon_pavio_da_lista` → `tr_na_lista_de_fornalha` · investigada | ficha "mago da Lista de Fornalha rebitado e levado onde a máquina precisa de Éter" × resumo "nos livros da Legião, o nome é outro" | a criatura quase responde a `pergunta` (o registro manda o mago para a máquina); `investigada` é o mínimo correto | gaiola, grito, fivela da Legião; nada de núcleo | — | 1 trama | OK |
| `mon_enxerto_da_fornalha` → `tr_na_aco_que_lembra` · investigada | ficha "lâmina de Aço de Sangue que tem vontade" × resumo "o aço chia com vozes" e pergunta "sacramento da seita" | é a consequência mais próxima do segredo (`aco_lembra`: o aço lembra os mortos); `investigada` é o piso aceitável, `revelada` seria excesso de zelo | sinais falam de sangue, gemido e corte; nenhuma frase de `aco_lembra` ("lembra de fato os que morreram forjando"); o token `sangue` é do material público "Aço de Sangue" | — | 1 trama | OK |
| `mon_quebrado_de_vitrine` → `tr_na_a_colecao` · tocada | ficha "Elfo de estimação numa cadeira de exposição" × resumo "raridades vivas são exibidas em saraus" | sintoma público → `tocada` ok | sem Vespério Valante nem Oswin; o `rumor` reescrito ("jura que") mantém o sentido | Dourado mantém 8 de 9 | ver abaixo | OK |
| `mon_quebrado_de_vitrine` → `tr_na_po_de_sonho` · tocada | ficha "pele tratada com Pó de Fada" × resumo "o Pó de Fada tem selo e licença… os dois cobram" e porta p1 "quem tem a pele rachada como a dela" (`hook_public`) | sintoma → `tocada` ok | `cheiro` "pó adocicado de flor seca" sugere o Pó, que é público; nada de overdose, licença que esconde causa de morte ou Elaryin (`elaryin`) | — | 2ª trama com motivo explícito na porta p1 (pele rachada); a vitrine é também cliente do Pó | OK |
| `mon_escritura_rastejante` → `tr_na_a_colecao` · investigada | ficha "contrato vivo do Mercado com as assinaturas dos devedores" × resumo "contratos que nunca vencem decidem quem vira raridade" | mecanismo por trás da vitrine → `investigada` ok | "livro de dívidas" (antes "livro de contas") mantém o sentido; sem núcleo | — | 1 trama | OK |
| `mon_porca_da_queda` → `tr_na_po_de_sonho` · tocada | ficha "comeu o que os viciados do Beco dos Desdentados vomitam" × resumo "No Beco dos Desdentados vendem Pó de Sonho" | sintoma visível → `tocada` ok | vômito, viciado, chão que cede; nada de `elaryin` | porte de boi, não é o miúdo comum; Rato da Peste e outros 12 seguem livres no Lama | 1 trama | OK |

**Tramas sem criatura** (`tr_na_documento_da_legiao`, `tr_na_o_que_o_lorde_trocou`): concordo. Nenhuma
ficha de NA tem papel, adega ou cópia como tema; forçar a Traça do Sino Mudo pela porta do sétimo
sino seria ligação fraca. 5 de 7 tramas cobertas (≥ 4, D5).

**Teto (D4):** 8 de 33 não-BOSS (24 %). Por local, a criatura ligada leva ~29–35 % da massa do sorteio
quando todas as tramas abrem (`TRAMA_MULT` 2,0) e o pool dormente continua com 26 entradas em cada
um dos três anéis; nenhum papel de território some (conferido com `encounter_distribution`).

**Vazamento:** nenhum sinal das 8 criaturas contém frase de `SECRET_SIGNATURES` nem dos grupos de
`leak_phrases.json` dos segredos das tramas ligadas (varredura por frase, sem acento). A ligação não
é exposta ao jogador; o que ele vê são os sinais, já aprovados na 360, e o momento em que a criatura
passa a existir.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/fauna_lint_tramas.py:45` | A parte "segredo" do E22 só consulta `SECRET_SIGNATURES`, que tem 4 chaves (`arauto_identidade`, `pacto_valerius`, `rede_carmesim`, `rei_subterraneo`). Para 5 dos 6 `secret_ids` das tramas ligadas (`corpos`, `praga`, `aco_lembra`, `elaryin`, e `barril` da trama sem criatura) o E22 não confere nada; as frases desses segredos estão em `leak_phrases.json`, que a SPEC-350 já usa como assinatura (`content_validator._leak_groups`). Conferi à mão por frase: limpo hoje. | Follow-up: o E22 também testa as **frases** (fold) de `leak_phrases()[secret_id]`. Por token daria falso positivo (`para`, `sangue`), então por frase. |
| P2-2 | P2 | `specs/SPEC-372-fauna-tramas.md:287` | A justificativa do Rosário diz "no Lama sobram outros padrão (Porca, Coisa do Esgoto)", mas a Porca também ficou ligada (linha 295). O argumento continua de pé (13 de 16 livres), o texto se contradiz. | Trocar "Porca" por outra criatura livre do Lama (ex.: Roda de Mandíbulas, Rato da Peste). |
| P2-3 | P2 | `services/fauna_lint_tramas.py:51` | O token de nome do núcleo `conta` (de `npc_lorde_oswin_conta_de_ouro`) obrigou a reescrever dois sinais que não tinham nada a ver com Oswin. As reescritas mantêm o sentido, mas palavra comum vai seguir colidindo nas próximas regiões. | Follow-up: ignorar tokens de nome que são palavra comum do português (lista curta de exceções, como a `secret_word_exceptions` da 350) ou exigir o nome inteiro. |

Sem P0/P1. As 9 ligações estão aprovadas pelo checklist §3.5.

## Correções aplicadas

Nenhuma (revisão; o revisor só edita este arquivo).

## Pendências

- P2-1 e P2-3: follow-up de lint (onda 2 de tramas, antes de ligar criaturas fora de NA).
- P2-2: ajuste de texto na §9, pelo coordenador no pouso.

## Comandos rodados

```text
py.sh -c "plot_threads.threads_for_region('nova_arcadia') campos públicos + SECRET_SIGNATURES" → 7 tramas; só pacto_valerius tem assinatura
py.sh -c "sinais das 8 criaturas ligadas × leak_phrases() por frase e por token" → 0 frase; tokens só 'sangue'/'para' (falso positivo)
py.sh -c "encounter_distribution por anel, tramas dormentes × reveladas" → pool dormente 26 em cada anel; fatia ligada 0,29–0,35 aberta
py.sh -c "contagem não-BOSS por anel" → Lama 3/16, Ferro 5/22, Dourado 1/9 ligadas
```
