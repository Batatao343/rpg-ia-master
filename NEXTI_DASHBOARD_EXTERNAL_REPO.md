# Dashboard Nexti em Repositório Separado

Conforme solicitado, o dashboard foi removido deste repositório (`rpg-ia-master`) e recriado do zero em um novo repositório local:

- Caminho: `/workspace/nexti-dashboard`
- Arquivos principais:
  - `/workspace/nexti-dashboard/index.html`
  - `/workspace/nexti-dashboard/README.md`

## Estado do novo repositório
- Inicializado com `git init`
- Commit inicial criado: `Initial commit: Nexti dashboard standalone`

## Como executar
```bash
cd /workspace/nexti-dashboard
python -m http.server 8000
```
Abrir: `http://localhost:8000`
