import json, re, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
E = []
def e(m): E.append(m)
assert set(d) == {"title", "chapters"}, d.keys()
ids = set()
LIM = {"title": None}
words = 0; n = 0
NARR_BAD = re.compile(r"[/\_`*#{}\[\]<>|~→%$=+]|\d+d\d+|\.py\b|\.json\b|\.md\b")
EMOJI = re.compile("[\u2190-\u2bff\U0001F000-\U0001FFFF]")
def L(s, k, w):
    if not isinstance(s, str) or len(s) > k: e(f"{w}: len>{k}: {s!r}")
for ci, c in enumerate(d["chapters"], 1):
    if set(c) != {"id", "title", "color", "scenes"}: e(f"chapter keys {c.keys()}")
    if c["id"] != f"c{ci:02d}": e(f"chapter id {c['id']}")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", c["color"]): e(f"{c['id']} color")
    sc = c["scenes"]
    if sc[0]["visual"]["type"] != "title": e(f"{c['id']} not starting with title")
    lv = sc[-1]["visual"]
    if not (lv["type"] == "bullets" or (lv["type"] == "callout" and lv["kind"] == "key")): e(f"{c['id']} no recap")
    for si, s in enumerate(sc, 1):
        n += 1
        if set(s) != {"id", "title", "narration", "visual"}: e(f"scene keys {s.get('id')}")
        w = s["id"]
        if not re.fullmatch(r"c\d{2}s\d{2}", w) or w != f"{c['id']}s{si:02d}": e(f"bad id {w}")
        if w in ids: e(f"dup id {w}")
        ids.add(w)
        nw = len(s["narration"].split()); words += nw
        if not 40 <= nw <= 110: e(f"{w}: {nw} words")
        m = NARR_BAD.search(s["narration"])
        if m: e(f"{w}: narration symbol {m.group(0)!r}")
        if EMOJI.search(s["narration"]): e(f"{w}: emoji")
        v = s["visual"]; t = v["type"]
        if t == "title":
            if set(v) != {"type","heading","subheading"}: e(f"{w} title keys")
        elif t == "bullets":
            if not 3 <= len(v["items"]) <= 6: e(f"{w} bullets n")
            for i in v["items"]: L(i, 90, w)
        elif t == "graph":
            if v["direction"] not in ("LR","TB"): e(f"{w} dir")
            ns = [x["id"] for x in v["nodes"]]
            if not 3 <= len(ns) <= 14 or len(set(ns)) != len(ns): e(f"{w} nodes")
            for x in v["nodes"]:
                L(x["label"], 28, w)
                if x["group"] not in ("llm","python","data","io","infra","neutral"): e(f"{w} group")
            adj = {i: [] for i in ns}
            for ed in v["edges"]:
                if ed["from"] not in adj or ed["to"] not in adj: e(f"{w} edge ref"); continue
                if "label" in ed: L(ed["label"], 18, w)
                adj[ed["from"]].append(ed["to"])
            st = {}
            def dfs(u):
                st[u] = 1
                for x in adj[u]:
                    if st.get(x) == 1 or (not st.get(x) and not dfs(x)): return False
                st[u] = 2; return True
            if not all(st.get(i) or dfs(i) for i in ns): e(f"{w} cycle")
        elif t == "flow":
            if not 3 <= len(v["steps"]) <= 8: e(f"{w} steps")
            for x in v["steps"]: L(x["label"], 30, w); L(x["detail"], 80, w)
        elif t == "code":
            ls = v["code"].split("\n")
            if len(ls) > 16: e(f"{w} code lines")
            for x in ls: L(x, 80, w)
            if not v.get("file") or not v.get("language"): e(f"{w} code meta")
        elif t == "stats":
            if not 2 <= len(v["items"]) <= 6: e(f"{w} stats n")
            for x in v["items"]: L(x["value"], 10, w); L(x["label"], 40, w)
        elif t == "compare":
            for side in ("left","right"):
                if not v[side].get("title") or len(v[side]["items"]) > 5: e(f"{w} compare")
                for x in v[side]["items"]: L(x, 70, w)
        elif t == "table":
            if not 2 <= len(v["columns"]) <= 4 or len(v["rows"]) > 7: e(f"{w} table shape")
            for r in v["rows"]:
                if len(r) != len(v["columns"]): e(f"{w} row width")
                for x in r: L(x, 40, w)
        elif t == "callout":
            if v["kind"] not in ("info","warn","key"): e(f"{w} kind")
            L(v["text"], 220, w)
        elif t == "example":
            if not 3 <= len(v["lines"]) <= 8: e(f"{w} example n")
            for x in v["lines"]: L(x["label"], 28, w); L(x["value"], 60, w)
        else: e(f"{w} type {t}")
print(f"chapters={len(d['chapters'])} scenes={n} words={words} est_min={words/150:.1f}")
print("ERRORS:", len(E)); [print(" ", x) for x in E]
sys.exit(1 if E else 0)
