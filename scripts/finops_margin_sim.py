"""SPEC-196 margin simulation over REAL repo baselines (offline, non-commercial).

No SKU or price is published in the repo; the gross prices below are SIMULATION INPUTS.
Cost per turn comes from measured playtests (see BASELINES); fees from the SPEC-195/189
channel assumptions. Output: docs/spec196/margin-simulation.md

  uv run python scripts/finops_margin_sim.py            # writes the report
  uv run python scripts/finops_margin_sim.py --print    # stdout only
"""
from __future__ import annotations

import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))

import argparse
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from services.finops import TARGET_MARGIN, estimate_fee, FeeRate
from services.shard_pricing import _ratio_units

OUT = Path(__file__).resolve().parents[1] / "docs/spec196/margin-simulation.md"

# --- measured cost per turn (USD) --------------------------------------------------------
# Sources: ESTADO_ATUAL (matriz B 28/09: US$1,17628 / 1.951 turnos, estimado e SUBCONTADO);
# playtest comerciante real 20/08 (US$0,162860 / 200 turnos); run 13x30 DeepSeek
# (~US$0,00080/turno); playtest/pricing.py (deepseek-v4-flash 1200 in + 400 out x ~2,7 invokes).
BASELINES = (
    ("matriz B 28/09 (subcontado)", Decimal("1.17628") / Decimal("1951")),
    ("13x30 DeepSeek v4", Decimal("0.00080")),
    ("comerciante real 20/08", Decimal("0.162860") / Decimal("200")),
)
IMAGE_COST_USD = Decimal("0.05")  # ASSUMPTION: gpt-image-2 1024x1536 ~1.6k output tokens @ $30/M
FX = Decimal("5.40")  # ASSUMPTION (BRL/USD); real value comes from the published pricing_version
FX_BUFFER = Decimal("0.10")
UNIT_BRL = Decimal("0.001")  # ASSUMPTION: BRL budget per shard_milli (1 shard = R$1,00)
CHANNELS = (
    ("stripe", FeeRate(Decimal("0.0399"), Decimal("0.39")),
     "Stripe BR cartao 3,99% + R$0,39 (assumido; confirmar contra a conta)"),
    ("google_play", FeeRate(Decimal("0.15"), Decimal("0")),
     "Google Play 15% (confirmar tier de servico pendente SPEC-198)"),
)
GROSS_PRICES = (Decimal("9.90"), Decimal("19.90"), Decimal("39.90"), Decimal("79.90"))


@dataclass(frozen=True)
class Line:
    channel: str
    gross: Decimal
    fee: Decimal
    budget: Decimal
    grant_milli: int
    turns_per_pack: Decimal
    cost_per_turn_usd: Decimal
    consumption_cost_brl: Decimal
    cm: Decimal
    margin_pct: Decimal
    headroom: Decimal
    meets: bool


def simulate(gross: Decimal, fee_rate: FeeRate, channel: str, cost_turn_usd: Decimal,
             drift: Decimal = Decimal(1)) -> Line:
    fee = estimate_fee(gross, fee_rate)
    target = (gross * TARGET_MARGIN).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    budget = gross - fee - target
    grant = _ratio_units(budget, UNIT_BRL, ceiling=False)
    allocated = UNIT_BRL * grant
    debit_per_turn = cost_turn_usd * FX * (1 + FX_BUFFER)  # what the wallet debits per turn
    turns = allocated / debit_per_turn
    actual_cost = turns * cost_turn_usd * FX * drift  # real cost if every shard is consumed
    cm = gross - fee - actual_cost
    pct = cm / gross
    headroom = (gross - fee - gross * TARGET_MARGIN) / (actual_cost / drift)
    return Line(channel, gross, fee, allocated, grant, turns, cost_turn_usd, actual_cost, cm,
                pct, headroom, pct >= TARGET_MARGIN)


def render() -> str:
    out = [
        "# SPEC-196 — Simulacao de margem (baseline real)", "",
        "> Gerado por `scripts/finops_margin_sim.py`. **Nao e oferta comercial**: nenhum SKU/preco",
        "> esta publicado; precos brutos sao entradas de simulacao. Imposto fora desta versao",
        "> (`tax_rate = 0`). Infra fixa (Vercel/Supabase) fica FORA das margens por SKU.", "",
        "## Premissas", "",
        f"- FX {FX} BRL/USD, buffer de FX {FX_BUFFER:.0%} no debito (premissa; real vem da `pricing_version`).",
        f"- Unidade de orcamento: R$ {UNIT_BRL} por shard_milli (1 shard = R$ 1,00) (premissa).",
        f"- Meta de margem de contribuicao: {TARGET_MARGIN:.0%} por SKU/canal/pricing_version.",
        f"- Imagem: ~US$ {IMAGE_COST_USD} por retrato (premissa; substituir pelo 1o uso real em staging).",
        "- Taxas por canal:",
    ]
    out += [f"  - `{c}`: {note}" for c, _, note in CHANNELS]
    out += ["", "## Custo por turno (medido)", "", "| Baseline | USD/turno |", "|---|---|"]
    out += [f"| {name} | {cost:.6f} |" for name, cost in BASELINES]
    out += ["", "Fontes: `ESTADO_ATUAL.md` (matriz B, comerciante real 20/08, 13x30),",
            "`playtest/pricing.py` (heuristica 1200 in/400 out). A matriz B esta SUBCONTADA",
            "(achado de 28/09); por isso o cenario de estresse x3 e o que decide o guard.", ""]
    failures = 0
    for name, cost in BASELINES:
        out += [f"## Cenario: {name} ({cost:.6f} USD/turno)", "",
                "| Canal | Preco | Taxa canal | Orcamento var. | Turnos/pacote | Custo real (todos consumidos) | "
                "Margem R$ | Margem % | Folga de custo | >=5%? |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for channel, fee_rate, _ in CHANNELS:
            for gross in GROSS_PRICES:
                ln = simulate(gross, fee_rate, channel, cost)
                failures += not ln.meets
                out.append(
                    f"| {channel} | R$ {ln.gross} | R$ {ln.fee} | R$ {ln.budget:.2f} | "
                    f"{ln.turns_per_pack:.0f} | R$ {ln.consumption_cost_brl:.2f} | "
                    f"R$ {ln.cm:.2f} | {ln.margin_pct:.1%} | {ln.headroom:.2f}x | "
                    f"{'sim' if ln.meets else '**NAO**'} |")
        out.append("")
    ref_name, ref_cost = BASELINES[-1]
    out += [f"## Deriva de custo do provider (baseline `{ref_name}`, pacote R$ 19,90)", "",
            "O debito usa o custo do rate card; se o provider encarecer sem o card ser atualizado,",
            "a margem cai mesmo com o buffer. 'Deriva' = custo real / custo do card.", "",
            "| Canal | Deriva | Margem R$ | Margem % | >=5%? |", "|---|---|---|---|---|"]
    for channel, fee_rate, _ in CHANNELS:
        for drift in (Decimal("1"), Decimal("1.05"), Decimal("1.10"), Decimal("1.25"), Decimal("2"), Decimal("3")):
            ln = simulate(Decimal("19.90"), fee_rate, channel, ref_cost, drift)
            failures += not ln.meets
            out.append(f"| {channel} | {drift}x | R$ {ln.cm:.2f} | {ln.margin_pct:.1%} | "
                       f"{'sim' if ln.meets else '**NAO**'} |")
    out.append("")
    img_cost_brl = IMAGE_COST_USD * FX * (1 + FX_BUFFER)
    out += ["## Imagem (retrato)", "",
            f"Debito por imagem: US$ {IMAGE_COST_USD} x FX {FX} x (1+{FX_BUFFER}) = R$ {img_cost_brl:.2f} "
            f"(= {img_cost_brl / UNIT_BRL:.0f} shard_milli). O guard de imagem (kill switch + rate card",
            "fresco, 7 dias) impede nova venda de efeito caro com cartao stale.", "",
            "## Leitura", "",
            "- Escopo: dimensionamento de PRECO por compra no desenho (preco - taxa - meta), assumindo",
            "  ZERO reembolso/disputa. O relatorio real (`services/finops.py`) usa receita LIQUIDA",
            "  (bruto - reembolso - disputa) e a margem % e a meta de 5% sao calculadas sobre ela;",
            "  taxas ja pagas e custo de uso nao sao devolvidos pelo canal. Esta simulacao NAO",
            "  prova margem de producao: so mostra a folga do preco antes de publicar a versao.",
            "- O pacote e dimensionado em ORCAMENTO, nao em turnos: a margem % e independente do custo",
            "  por turno e so o numero de turnos/pacote muda. A unica protecao contra deriva de custo",
            "  e o buffer de FX (10%): 'folga' ~1,10x. Acima disso, com todos os shards consumidos, a",
            "  margem cai abaixo de 5% => rate card fresco/alertas/kill switches sao o guard real",
            "  (SPEC-196 R3/R4/R5).",
            "- A folga cai com a taxa do canal: Google Play (15%) tem folga menor que Stripe; preco baixo",
            "  sofre mais com a taxa fixa de R$0,39 do Stripe.",
            f"- Linhas abaixo da meta nesta simulacao (inclui cenarios de deriva): **{failures}**. Cada",
            "  uma indica SKU/canal cujo preco deve subir (ou pacote reduzir) antes de publicar a",
            "  `pricing_version`.",
            "- Quebra (shards nao consumidos) so melhora a margem real; nao e creditada aqui.", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.print:
        print(text)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
