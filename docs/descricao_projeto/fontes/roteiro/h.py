"""Helpers para montar o roteiro (um único ponto de verdade -> JSON + MD)."""


def T(h, s):
    return {"type": "title", "heading": h, "subheading": s}


def B(h, *items):
    return {"type": "bullets", "heading": h, "items": list(items)}


def G(h, d, nodes, edges):
    return {
        "type": "graph", "heading": h, "direction": d,
        "nodes": [{"id": i, "label": l, "group": g} for (i, l, g) in nodes],
        "edges": [
            ({"from": e[0], "to": e[1], "label": e[2]} if len(e) > 2 else {"from": e[0], "to": e[1]})
            for e in edges
        ],
    }


def F(h, *steps):
    return {"type": "flow", "heading": h, "steps": [{"label": a, "detail": b} for (a, b) in steps]}


def C(h, file, lang, code):
    return {"type": "code", "heading": h, "file": file, "language": lang, "code": code.strip("\n")}


def S(h, *items):
    return {"type": "stats", "heading": h, "items": [{"value": v, "label": l} for (v, l) in items]}


def CMP(h, lt, li, rt, ri):
    return {"type": "compare", "heading": h, "left": {"title": lt, "items": li}, "right": {"title": rt, "items": ri}}


def TB(h, cols, rows):
    return {"type": "table", "heading": h, "columns": cols, "rows": rows}


def CO(kind, h, text):
    return {"type": "callout", "kind": kind, "heading": h, "text": text}


def EX(h, *lines):
    return {"type": "example", "heading": h, "lines": [{"label": a, "value": b} for (a, b) in lines]}


def sc(title, narration, visual):
    return {"title": title, "narration": " ".join(narration.split()), "visual": visual}


def ch(title, color, scenes):
    return {"title": title, "color": color, "scenes": scenes}
