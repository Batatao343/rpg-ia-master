# Arte visual curada (Fase 8A)

O jogo publica apenas derivados WebP do catálogo `data/visual_assets.json`.
Os PNGs originais e o ZIP do handoff são fontes locais: não entram no Git e
não são servidos pela API.

## Pacote importado

- Pacote: `VALORIA_GAME_ART_HANDOFF`
- Recebido e verificado em: 2026-08-12
- SHA-256 do ZIP: `8f1574b336a9fe8db5fe128d50b0f66b7a5a84fb57063848aa9de014e0709bd1`
- Integridade: 68/68 PNGs conferidos; nenhuma divergência
- Disponível no handoff: 14 imagens de 6 raças, 5 classes, 36 locais e 13
  NPCs públicos. Os NPCs secretos Thessavar e Víbora foram excluídos na origem.
- Importado pelo jogo: uma capa para cada uma das 6 raças, 5 classes, 22
  locais canônicos e 12 NPCs canônicos. Vrethis permanece registrado como fonte
  não mapeada porque ainda não existe no grafo do jogo.

Todos os 35 nós do mapa têm arte exata (22) ou fallback regional explícito
(13). Um fallback conserva `location_id` e nome do lugar atual, mas responde
`scope=regional`, portanto nunca se apresenta como ilustração exata.

## Reimportar

Use Python 3.13 pelo `uv`:

```powershell
$env:Path="$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv run python scripts/import_visual_assets.py --source-root C:\caminho\VALORIA_GAME_ART_HANDOFF
uv run python scripts/import_visual_assets.py --source-root C:\caminho\VALORIA_GAME_ART_HANDOFF --check
uv run python scripts/validate_content.py
```

O import valida `approved + public + SHA-256`, orientação e confinamento de
caminho antes de promover o lote. Ele remove metadata, gera thumbnail/display
com dimensões explícitas e impõe 120 KiB para thumbnails, 300 KiB para retratos
e 400 KiB para cenas. Nomes carregam os primeiros 12 caracteres do hash da
fonte. `--check` reconstrói em temporário e não escreve. Derivados desconhecidos
são preservados por padrão; `--prune` autoriza removê-los.

Para trocar uma arte, obtenha um manifesto novo aprovado, ajuste somente a
matriz de IDs em `scripts/import_visual_assets.py`, reimporte e rode os gates.
Nunca associe por semelhança de nome nem publique `hidden/secret`.

## Placeholder de sistema

`assets/visual/system/aguardando-arte-source.png` é a composição neutra
autorizada para uma futura lacuna de raça/classe. Foi gerada pelo gerador de
imagem integrado do Codex em 2026-08-12, 1024×1536, SHA-256
`6e22252aa9b9610cee908358e6978028e84ff7401ecf79d55c79f1605132e51f`.
O prompt e a proveniência completos ficam no README da mesma pasta. O handoff
atual tem arte aprovada para todas as raças e classes, então o placeholder não
é publicado nem usado por nenhuma delas.

NPCs de runtime e entidades ainda sem retrato usam monograma CSS determinístico
com nome/papel. Isso é deliberado: nunca se empresta o rosto de outro NPC.
