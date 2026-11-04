# SPEC-377 — evidências

- `arena-antes.json` / `arena-depois.json`: `arena_spec355.py base --seeds 0:20` antes e depois do R15 (rendido deixa de ser alvo de Carta). Resultado idêntico: Devoto 60,2 %, Sangromante 65,0 %, Corruptor 51,9 %, Arcanista 55,8 %, Médico 45,8 % (todos na faixa 45–85 %). O bot da arena não usa rendição.
- Matriz de facção (R20): fixada em `tests/test_faction_visibility.py` (6 facções: 2 públicas, 4 secretas).
- Item 2 (Fôlego): `folego_divergencias.{py,json}` (Etapa 0: modos bruto/catálogo/`effective_card`; só 2 divergências, motivo (b) dot livre; modo (iii) limpo) e `lote-v2-{antes,depois}.json` (`cor_toque`, `toque_corrosivo`), conferidos pela revisão independente. Nada protegido muda; sem `/eval-publish`. (A chave `ref_custo_folego` dos JSONs guarda o resumo da referência; o script já grava `referencia`.)
