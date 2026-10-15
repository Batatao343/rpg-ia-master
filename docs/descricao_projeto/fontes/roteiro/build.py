import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1, p2, p3, p4, p5

OUT = sys.argv[1]
TITLE = "Crônicas de Valoria por dentro: como funciona o rpg-ia-master"

chapters = p1.CHAPTERS + p2.CHAPTERS + p3.CHAPTERS + p4.CHAPTERS + p5.CHAPTERS
errs, warns = [], []
doc = {"title": TITLE, "chapters": []}
for ci, c in enumerate(chapters, 1):
    cid = f"c{ci:02d}"
    scenes = []
    for si, s in enumerate(c["scenes"], 1):
        scenes.append({"id": f"{cid}s{si:02d}", **s})
    doc["chapters"].append({"id": cid, "title": c["title"], "color": c["color"], "scenes": scenes})

BAD = re.compile(r"[/\\_`*#{}\[\]<>|~→%$=+]|\d+d\d+")
EMOJI = re.compile("[←-⯿\U0001F000-\U0001FFFF]")


def chk(cond, msg):
    if not cond:
        errs.append(msg)


def L(s, n, where):
    chk(isinstance(s, str) and len(s) <= n, f"{where}: len {len(s) if isinstance(s,str) else s} > {n}: {s!r}")


total_words = 0
nscenes = 0
for c in doc["chapters"]:
    chk(re.fullmatch(r"#[0-9A-Fa-f]{6}", c["color"]), f"{c['id']} color")
    sc = c["scenes"]
    chk(sc[0]["visual"]["type"] == "title", f"{c['id']} first not title")
    last = sc[-1]["visual"]
    chk(last["type"] == "bullets" or (last["type"] == "callout" and last["kind"] == "key"), f"{c['id']} last not recap")
    for s in sc:
        nscenes += 1
        w = len(s["narration"].split())
        total_words += w
        where = s["id"]
        chk(40 <= w <= 110, f"{where}: narration words {w}")
        m = BAD.search(s["narration"])
        chk(not m, f"{where}: bad char in narration {m.group(0) if m else ''}")
        chk(not EMOJI.search(s["narration"]), f"{where}: emoji")
        L(s["title"], 40, where + " title")
        v = s["visual"]; t = v["type"]
        if len(v.get("heading", "")) > 60:
            warns.append(f"{where}: long heading {len(v['heading'])}")
        if t == "title":
            L(v["heading"], 60, where); L(v["subheading"], 90, where)
        elif t == "bullets":
            chk(3 <= len(v["items"]) <= 6, f"{where}: bullets count {len(v['items'])}")
            for it in v["items"]: L(it, 90, where + " bullet")
        elif t == "graph":
            ids = [n["id"] for n in v["nodes"]]
            chk(3 <= len(ids) <= 14, f"{where}: nodes {len(ids)}")
            chk(len(set(ids)) == len(ids), f"{where}: dup node ids")
            chk(v["direction"] in ("LR", "TB"), where)
            for n in v["nodes"]:
                L(n["label"], 28, where + " node")
                chk(n["group"] in ("llm", "python", "data", "io", "infra", "neutral"), f"{where}: group {n['group']}")
            adj = {i: [] for i in ids}
            for e in v["edges"]:
                chk(e["from"] in adj and e["to"] in adj, f"{where}: edge ref {e}")
                if "label" in e: L(e["label"], 18, where + " edge")
                if e["from"] in adj and e["to"] in adj: adj[e["from"]].append(e["to"])
            state = {}
            def dfs(u):
                state[u] = 1
                for x in adj[u]:
                    if state.get(x) == 1: return False
                    if not state.get(x) and not dfs(x): return False
                state[u] = 2; return True
            chk(all(state.get(i) or dfs(i) for i in ids), f"{where}: graph has cycle")
        elif t == "flow":
            chk(3 <= len(v["steps"]) <= 8, f"{where}: steps {len(v['steps'])}")
            for st in v["steps"]: L(st["label"], 30, where + " step"); L(st["detail"], 80, where + " detail")
        elif t == "code":
            lines = v["code"].split("\n")
            chk(len(lines) <= 16, f"{where}: code lines {len(lines)}")
            for ln in lines: L(ln, 80, where + " codeline")
            chk(v["language"] in ("python", "ts", "json", "bash", "sql"), where)
        elif t == "stats":
            chk(2 <= len(v["items"]) <= 6, f"{where}: stats {len(v['items'])}")
            for it in v["items"]: L(it["value"], 10, where + " statv"); L(it["label"], 40, where + " statl")
        elif t == "compare":
            for side in ("left", "right"):
                chk(len(v[side]["items"]) <= 5, f"{where}: compare {side} count")
                for it in v[side]["items"]: L(it, 70, where + " cmp")
        elif t == "table":
            chk(2 <= len(v["columns"]) <= 4, f"{where}: cols")
            chk(len(v["rows"]) <= 7, f"{where}: rows {len(v['rows'])}")
            for r in v["rows"]:
                chk(len(r) == len(v["columns"]), f"{where}: row width {r}")
                for cell in r: L(cell, 40, where + " cell")
        elif t == "callout":
            chk(v["kind"] in ("info", "warn", "key"), where); L(v["text"], 220, where + " callout")
        elif t == "example":
            chk(3 <= len(v["lines"]) <= 8, f"{where}: example lines")
            for ln in v["lines"]: L(ln["label"], 28, where + " exl"); L(ln["value"], 60, where + " exv")
        else:
            errs.append(f"{where}: unknown type {t}")

chk(doc["chapters"][0]["scenes"][0]["visual"]["type"] == "title", "first scene")
print("chapters", len(doc["chapters"]), "scenes", nscenes, "words", total_words, "min", round(total_words / 150, 1))
for w in warns: print("WARN", w)
for e in errs: print("ERR", e)
if errs:
    sys.exit(1)

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "roteiro.json"), "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)


def vis_md(v):
    t = v["type"]; o = []
    if t == "title":
        o.append(f"Cartão de abertura — **{v['heading']}** / _{v['subheading']}_")
    elif t == "bullets":
        o.append(f"Lista — **{v['heading']}**"); o += [f"  - {i}" for i in v["items"]]
    elif t == "graph":
        o.append(f"Grafo ({v['direction']}) — **{v['heading']}**")
        lab = {n["id"]: n["label"] for n in v["nodes"]}
        o.append("  - Nós: " + "; ".join(f"{n['label']} [{n['group']}]" for n in v["nodes"]))
        o += [f"  - {lab[e['from']]} → {lab[e['to']]}" + (f" ({e['label']})" if e.get("label") else "") for e in v["edges"]]
    elif t == "flow":
        o.append(f"Fluxo numerado — **{v['heading']}**")
        o += [f"  {i}. **{s['label']}** — {s['detail']}" for i, s in enumerate(v["steps"], 1)]
    elif t == "code":
        o.append(f"Código — **{v['heading']}** (`{v['file']}`)")
        o.append(f"\n```{v['language']}\n{v['code']}\n```")
    elif t == "stats":
        o.append(f"Painel de números — **{v['heading']}**")
        o += [f"  - **{i['value']}** — {i['label']}" for i in v["items"]]
    elif t == "compare":
        o.append(f"Comparação — **{v['heading']}**")
        o.append(f"  - _{v['left']['title']}_: " + " · ".join(v["left"]["items"]))
        o.append(f"  - _{v['right']['title']}_: " + " · ".join(v["right"]["items"]))
    elif t == "table":
        o.append(f"Tabela — **{v['heading']}**\n")
        o.append("| " + " | ".join(v["columns"]) + " |")
        o.append("|" + "---|" * len(v["columns"]))
        o += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in v["rows"]]
    elif t == "callout":
        o.append(f"Destaque ({v['kind']}) — **{v['heading']}**: {v['text']}")
    elif t == "example":
        o.append(f"Exemplo passo a passo — **{v['heading']}**")
        o += [f"  - {l['label']}: `{l['value']}`" for l in v["lines"]]
    return "\n".join(o)


md = [f"# {TITLE}", "",
      "Roteiro de vídeo longo, pedagógico, sobre o projeto rpg-ia-master. Fonte única: o mesmo conteúdo está estruturado em `roteiro.json` (consumido pelo Remotion). Narração em pt-BR para TTS (voz Microsoft Maria).", "",
      "## Sumário", ""]
for c in doc["chapters"]:
    md.append(f"- **{c['id']}** {c['title']} ({len(c['scenes'])} cenas, cor `{c['color']}`)")
md.append("")
for c in doc["chapters"]:
    cw = sum(len(s["narration"].split()) for s in c["scenes"])
    md += [f"## {c['id'].upper()} — {c['title']}", "", f"_Cor do capítulo: `{c['color']}` · {len(c['scenes'])} cenas · {cw} palavras (~{cw/150:.1f} min)_", ""]
    for s in c["scenes"]:
        md += [f"### {s['id']} — {s['title']}", "", f"**Narração:** {s['narration']}", "", "**Visual:** " + vis_md(s["visual"]), ""]
md += ["## Estimativa de duração", "",
       f"- Capítulos: {len(doc['chapters'])}",
       f"- Cenas: {nscenes}",
       f"- Palavras de narração: {total_words}",
       f"- Ritmo de referência: ~150 palavras por minuto",
       f"- Duração estimada da narração: ~{total_words/150:.0f} minutos ({total_words/150/60:.2f} h), sem contar pausas e transições entre cenas.", ""]
with open(os.path.join(OUT, "roteiro.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print("written")
