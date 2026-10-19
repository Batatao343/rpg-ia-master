---
name: estado
description: Regenera o bloco "Decisões recentes" do ESTADO_ATUAL.md a partir dos cabeçalhos das specs, sincroniza specs/index.yaml e confere o teto de 8 KB. Use em "/estado", "atualiza o ESTADO", após pousar specs ou ao fim de uma onda.
---

# /estado

ESTADO_ATUAL.md é **substituído, nunca anexado** (≤ 8 KB). Rode na raiz do checkout:

```bash
. scripts/dev/env.sh
uv run --frozen python scripts/spec_index.py build
uv run --frozen python scripts/spec_index.py recent --days 7 --write ESTADO_ATUAL.md
uv run --frozen python scripts/spec_index.py summary
uv run --frozen python scripts/spec_index.py estado-size
```

Depois, à mão e **substituindo** linhas (nunca criando novas):
- "Estado em 10 linhas": sha da `main`, contagem da suíte (última execução real),
  linha de specs = saída do `summary`, sha do staging se mudou.
- "Próximos 3 passos" / "Bloqueios no dono": remova o que fechou.
- "Notas da onda em curso": só o coordenador escreve (≤ 6 linhas por frente). Ao abrir
  onda nova, mova as notas para `CHANGELOG.md` (`## AAAA-MM-DD`) e esvazie a seção.

`estado-size` vermelho → mova detalhe para `CHANGELOG.md`/`docs/historico/`.
Mostre o `git diff --stat` e deixe o commit para o `/wrap-up` ou o coordenador.
