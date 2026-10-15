/* ===== Biblioteca mínima do guia: grafos em camadas, passo-a-passo, quiz, tabs ===== */
const NS = 'http://www.w3.org/2000/svg';
const GROUP_LABEL = {llm: 'LLM (IA)', python: 'Python determinístico', data: 'Dados / memória', io: 'Entrada / saída', infra: 'Infraestrutura', neutral: 'Outro'};
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const el = (tag, attrs = {}, parent) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

const Graph = {
  /** Desenha um DAG em camadas (caminho mais longo) dentro de `host`. Arestas `back:true` são laços desenhados por fora. */
  render(host, spec) {
    const dir = spec.direction || 'LR';
    const lr = dir === 'LR';
    const nodes = spec.nodes;
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const edges = spec.edges.filter((e) => byId[e.from] && byId[e.to]);
    const fwd = edges.filter((e) => !e.back);
    const lvl = Object.fromEntries(nodes.map((n) => [n.id, n.layer ?? 0]));
    for (let k = 0; k < nodes.length; k++) {
      let ch = false;
      for (const e of fwd) if (lvl[e.to] < lvl[e.from] + 1) { lvl[e.to] = lvl[e.from] + 1; ch = true; }
      if (!ch) break;
    }
    const layers = [];
    nodes.forEach((n) => (layers[lvl[n.id]] ??= []).push(n.id));
    const L = layers.filter(Boolean);
    // barycentro: 2 passadas para reduzir cruzamentos
    const idx = {};
    const reindex = () => L.forEach((ly) => ly.forEach((id, i) => (idx[id] = i)));
    reindex();
    for (let pass = 0; pass < 2; pass++) {
      for (let li = 1; li < L.length; li++) {
        L[li].sort((a, b) => {
          const pa = fwd.filter((e) => e.to === a).map((e) => idx[e.from]);
          const pb = fwd.filter((e) => e.to === b).map((e) => idx[e.from]);
          const ma = pa.length ? pa.reduce((x, y) => x + y) / pa.length : idx[a];
          const mb = pb.length ? pb.reduce((x, y) => x + y) / pb.length : idx[b];
          return ma - mb;
        });
        reindex();
      }
    }
    const fs = spec.fontSize || 13;
    const wOf = (n) => Math.max(spec.minW || 110, Math.min(spec.maxW || 220, (n.label.length * fs * 0.6) + 34));
    const H = spec.nodeH || 44;
    const gapMain = spec.gapMain || (lr ? 70 : 56);
    const gapCross = spec.gapCross || (lr ? 18 : 22);
    const layerSize = L.map((ly) => Math.max(...ly.map((id) => (lr ? wOf(byId[id]) : H))));
    const crossSize = L.map((ly) => ly.reduce((a, id) => a + (lr ? H : wOf(byId[id])) + gapCross, -gapCross));
    const maxCross = Math.max(...crossSize);
    const pos = {};
    let main = 20;
    L.forEach((ly, li) => {
      let c = 20 + (maxCross - crossSize[li]) / 2;
      ly.forEach((id) => {
        const n = byId[id];
        const w = wOf(n);
        pos[id] = lr ? {x: main + (layerSize[li] - w) / 2, y: c, w, h: H} : {x: c, y: main, w, h: H};
        c += (lr ? H : w) + gapCross;
      });
      main += layerSize[li] + gapMain;
    });
    const W = lr ? main - gapMain + 20 : maxCross + 40;
    // LR largo demais para a tela → refaz de cima para baixo (legível em vez de minúsculo)
    if (lr && !spec.keepDir && host.clientWidth > 0 && host.clientWidth / W < 0.78) return Graph.render(host, {...spec, direction: 'TB', gapMain: 40, gapCross: 18});
    const HH = lr ? maxCross + 40 + (edges.some((e) => e.back) ? 50 : 0) : main - gapMain + 20 + (edges.some((e) => e.back) ? 40 : 0);
    host.innerHTML = '';
    const svg = el('svg', {viewBox: `0 0 ${W} ${HH}`, role: 'img', 'aria-label': spec.title || 'diagrama'}, host);
    svg.style.maxHeight = (spec.maxHeight || 620) + 'px';
    if (spec.minScale) svg.style.minWidth = Math.min(W * spec.minScale, 1400) + 'px';
    const defs = el('defs', {}, svg);
    const mk = el('marker', {id: 'arr' + host.id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse'}, defs);
    el('path', {d: 'M0,0 L10,5 L0,10 z', fill: cssVar('--gold')}, mk);
    const gE = el('g', {}, svg);
    const gN = el('g', {}, svg);
    const edgeEls = [];
    edges.forEach((e) => {
      const a = pos[e.from], b = pos[e.to];
      let d, lx, ly;
      if (e.back) {
        if (lr) {
          const x1 = a.x + a.w / 2, x2 = b.x + b.w / 2, y = maxCross + 40;
          d = `M${x1},${a.y + a.h} C${x1},${y + 20} ${x2},${y + 20} ${x2},${b.y + b.h}`;
          lx = (x1 + x2) / 2; ly = y + 12;
        } else {
          const y1 = a.y + a.h / 2, y2 = b.y + b.h / 2, x = W - 10;
          d = `M${a.x + a.w},${y1} C${x + 30},${y1} ${x + 30},${y2} ${b.x + b.w},${y2}`;
          lx = x + 4; ly = (y1 + y2) / 2;
        }
      } else if (lr) {
        const x1 = a.x + a.w, y1 = a.y + a.h / 2, x2 = b.x, y2 = b.y + b.h / 2, m = (x1 + x2) / 2;
        d = `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`; lx = x2 - 6; ly = y2 - 8;
      } else {
        const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = b.x + b.w / 2, y2 = b.y, m = (y1 + y2) / 2;
        d = `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}`; lx = x2 + 8; ly = y2 - 8;
      }
      const g = el('g', {class: 'gedge'}, gE);
      el('path', {d, stroke: e.color ? cssVar(e.color) || e.color : cssVar('--gold'), 'stroke-opacity': .6, 'marker-end': `url(#arr${host.id})`, 'stroke-dasharray': e.dashed ? '6 5' : ''}, g);
      if (e.label) {
        const t = el('text', {x: lx, y: ly, fill: cssVar('--muted'), 'text-anchor': e.back ? 'middle' : (lr ? 'end' : 'start')}, g);
        t.textContent = e.label;
      }
      edgeEls.push({e, g});
    });
    const nodeEls = {};
    nodes.forEach((n) => {
      const p = pos[n.id];
      const col = cssVar('--' + (n.group || 'neutral'));
      const g = el('g', {class: 'gnode', tabindex: 0, role: 'button', 'aria-label': n.label}, gN);
      el('rect', {x: p.x, y: p.y, width: p.w, height: p.h, rx: 10, fill: col, 'fill-opacity': .13, stroke: col, 'stroke-width': 1.8}, g);
      const lines = String(n.label).split('\n');
      lines.forEach((ln, i) => {
        const t = el('text', {x: p.x + p.w / 2, y: p.y + p.h / 2 + (i - (lines.length - 1) / 2) * (fs + 2) + fs * 0.35, 'text-anchor': 'middle', fill: cssVar('--text'), 'font-size': fs}, g);
        t.textContent = ln;
      });
      if (n.sub) {
        const t = el('text', {x: p.x + p.w / 2, y: p.y + p.h + 13, 'text-anchor': 'middle', fill: cssVar('--dim'), 'font-size': 10.5, 'font-family': cssVar('--fm')}, g);
        t.textContent = n.sub;
      }
      nodeEls[n.id] = g;
      const show = () => api.inspect(n.id);
      g.addEventListener('click', show);
      g.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); show(); } });
      g.addEventListener('mouseenter', () => { if (!api.locked) api.neighbors(n.id); });
      g.addEventListener('mouseleave', () => { if (!api.locked) api.reset(); });
    });
    const inspector = host.parentElement.querySelector('.inspector');
    const api = {
      locked: false,
      reset() { Object.values(nodeEls).forEach((g) => g.classList.remove('dim', 'hot')); edgeEls.forEach(({g}) => g.classList.remove('dim', 'hot')); },
      neighbors(id) {
        const near = new Set([id]);
        edges.forEach((e) => { if (e.from === id) near.add(e.to); if (e.to === id) near.add(e.from); });
        Object.entries(nodeEls).forEach(([k, g]) => g.classList.toggle('dim', !near.has(k)));
        edgeEls.forEach(({e, g}) => g.classList.toggle('dim', !(e.from === id || e.to === id)));
      },
      highlight(ids = [], path = []) {
        this.locked = ids.length > 0;
        const s = new Set(ids);
        Object.entries(nodeEls).forEach(([k, g]) => { g.classList.toggle('hot', s.has(k)); g.classList.toggle('dim', ids.length > 0 && !s.has(k)); });
        const ps = new Set(path.map((p) => p.join('>')));
        edgeEls.forEach(({e, g}) => { const on = ps.has(e.from + '>' + e.to); g.classList.toggle('hot', on); g.classList.toggle('dim', ids.length > 0 && !on); });
        if (!ids.length) this.reset();
      },
      inspect(id) {
        const n = byId[id];
        if (!inspector) return;
        const outs = edges.filter((e) => e.from === id).map((e) => byId[e.to].label.replace('\n', ' ') + (e.label ? ` <span class="pill">${esc(e.label)}</span>` : ''));
        const ins = edges.filter((e) => e.to === id).map((e) => byId[e.from].label.replace('\n', ' '));
        inspector.innerHTML = `<h5>${esc(n.label.replace('\n', ' '))} <span class="tag ${n.group || ''}">${GROUP_LABEL[n.group || 'neutral']}</span></h5>
          <div>${n.info || '<span class="hint">Sem detalhes adicionais.</span>'}</div>
          <div class="hint" style="margin-top:8px">${ins.length ? 'Recebe de: ' + ins.join(', ') + '. ' : ''}${outs.length ? 'Segue para: ' + outs.join(', ') + '.' : ''}</div>`;
      },
    };
    if (spec.legend !== false) {
      const groups = [...new Set(nodes.map((n) => n.group || 'neutral'))];
      const lg = document.createElement('div');
      lg.className = 'legend';
      lg.innerHTML = groups.map((g) => `<span><i style="background:${cssVar('--' + g)}"></i>${GROUP_LABEL[g]}</span>`).join('') + '<span style="margin-left:auto">clique num nó para detalhes · passe o mouse para ver vizinhos</span>';
      host.appendChild(lg);
    }
    return api;
  },
};

/** Monta um diagrama declarado em DIAGRAMS[nome] dentro de um <div class="diagram" data-graph="nome">. */
const GRAPHS = {};
function mountDiagrams() {
  document.querySelectorAll('[data-graph]').forEach((box) => {
    const name = box.dataset.graph;
    const spec = DIAGRAMS[name];
    if (!spec) return;
    box.innerHTML = `<div class="dtitle"><span>${esc(spec.title || '')}</span><button class="mini" data-reset>limpar destaque</button></div><div class="gh" id="g_${name}"></div><div class="inspector"><span class="hint">${esc(spec.hint || 'Clique em qualquer caixa para ver o que ela faz.')}</span></div>`;
    GRAPHS[name] = Graph.render(box.querySelector('.gh'), spec);
    box.querySelector('[data-reset]').onclick = () => GRAPHS[name].highlight([]);
  });
}

/** Passo-a-passo: STEPPERS[nome] = {graph?: nome, steps:[{t, h, hi?:[ids], path?:[[a,b]]}]} */
function mountSteppers() {
  document.querySelectorAll('[data-stepper]').forEach((box) => {
    const conf = STEPPERS[box.dataset.stepper];
    if (!conf) return;
    let i = 0;
    let timer = null;
    box.classList.add('stepper');
    box.innerHTML = `<div class="sbar"><button data-p>◀ anterior</button><button class="primary" data-n>próximo ▶</button><button data-a>▶▶ auto</button><span class="count"></span></div><div class="sbody"></div><div class="dots"></div>`;
    const body = box.querySelector('.sbody'), cnt = box.querySelector('.count'), dots = box.querySelector('.dots');
    dots.innerHTML = conf.steps.map((_, k) => `<i data-k="${k}" title="passo ${k + 1}"></i>`).join('');
    const show = (initial) => {
      const s = conf.steps[i];
      body.innerHTML = `<h5>${i + 1}. ${s.t}</h5><div>${s.h}</div>`;
      cnt.textContent = `passo ${i + 1} de ${conf.steps.length}`;
      dots.querySelectorAll('i').forEach((d, k) => d.classList.toggle('on', k <= i));
      if (!initial && conf.graph && GRAPHS[conf.graph]) {
        GRAPHS[conf.graph].highlight(s.hi || [], s.path || []);
        if (s.hi && s.hi.length === 1) GRAPHS[conf.graph].inspect(s.hi[0]);
      }
      if (conf.onStep) conf.onStep(i, s);
    };
    box.querySelector('[data-p]').onclick = () => { i = Math.max(0, i - 1); show(); };
    box.querySelector('[data-n]').onclick = () => { i = Math.min(conf.steps.length - 1, i + 1); show(); };
    box.querySelector('[data-a]').onclick = (ev) => {
      if (timer) { clearInterval(timer); timer = null; ev.target.textContent = '▶▶ auto'; return; }
      ev.target.textContent = '❚❚ pausar';
      timer = setInterval(() => { if (i >= conf.steps.length - 1) { clearInterval(timer); timer = null; ev.target.textContent = '▶▶ auto'; return; } i++; show(); }, 3200);
    };
    dots.onclick = (ev) => { if (ev.target.dataset.k) { i = +ev.target.dataset.k; show(); } };
    show(true);
  });
}

/** Quiz: <div class="quiz" data-quiz="nome"> */
function mountQuizzes() {
  document.querySelectorAll('[data-quiz]').forEach((box) => {
    const q = QUIZ[box.dataset.quiz];
    if (!q) return;
    box.innerHTML = `<div class="eyebrow">Teste rápido</div><div class="q">${q.q}</div><div class="opts">${q.o.map((o, k) => `<button data-k="${k}">${o}</button>`).join('')}</div><div class="exp">${q.e}</div>`;
    box.querySelectorAll('.opts button').forEach((b) => (b.onclick = () => {
      box.querySelectorAll('.opts button').forEach((x) => (x.disabled = true));
      b.classList.add(+b.dataset.k === q.a ? 'right' : 'wrong');
      box.querySelector(`[data-k="${q.a}"]`).classList.add('right');
      box.classList.add('done');
    }));
  });
}

/** Tabs simples: <div data-tabs> com botões [data-tab=x] e painéis [data-pane=x] */
function mountTabs() {
  document.querySelectorAll('[data-tabs]').forEach((box) => {
    const btns = box.querySelectorAll(':scope > .tabs > [data-tab]');
    const panes = box.querySelectorAll(':scope > [data-pane]');
    const go = (k) => { btns.forEach((b) => b.classList.toggle('on', b.dataset.tab === k)); panes.forEach((p) => p.classList.toggle('hidden', p.dataset.pane !== k)); };
    btns.forEach((b) => (b.onclick = () => go(b.dataset.tab)));
    if (btns[0]) go(btns[0].dataset.tab);
  });
}

/** Índice lateral com destaque da seção ativa + barra de progresso */
function mountToc() {
  const secs = [...document.querySelectorAll('section.chap')];
  const links = Object.fromEntries([...document.querySelectorAll('nav.toc a')].map((a) => [a.getAttribute('href').slice(1), a]));
  const bar = document.querySelector('.topbar .progress i');
  const onScroll = () => {
    const y = scrollY + 120;
    let cur = secs[0];
    for (const s of secs) if (s.offsetTop <= y) cur = s;
    Object.values(links).forEach((a) => a.classList.remove('active'));
    if (cur && links[cur.id]) links[cur.id].classList.add('active');
    const h = document.documentElement.scrollHeight - innerHeight;
    bar.style.width = (h > 0 ? (scrollY / h) * 100 : 0) + '%';
  };
  addEventListener('scroll', onScroll, {passive: true});
  onScroll();
  document.getElementById('tocBtn').onclick = () => document.body.classList.toggle('toc-open');
  document.querySelectorAll('nav.toc a').forEach((a) => (a.onclick = () => document.body.classList.remove('toc-open')));
  const themeBtn = document.getElementById('themeBtn');
  let saved = null;
  try { saved = localStorage.getItem('guia-theme'); } catch (e) {}
  if (saved) document.documentElement.dataset.theme = saved;
  themeBtn.onclick = () => {
    const cur = document.documentElement.dataset.theme || 'dark';
    const nxt = cur === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = nxt;
    try { localStorage.setItem('guia-theme', nxt); } catch (e) {}
    mountDiagrams(); // recolore SVGs
    mountSteppers();
  };
}

/** Filtro de tabela/lista: <input data-filter="#alvo"> esconde linhas que não casam */
function mountFilters() {
  document.querySelectorAll('[data-filter]').forEach((inp) => {
    const target = document.querySelector(inp.dataset.filter);
    inp.addEventListener('input', () => {
      const q = inp.value.trim().toLowerCase();
      target.querySelectorAll('[data-row]').forEach((r) => r.classList.toggle('hidden', q && !r.textContent.toLowerCase().includes(q)));
    });
  });
}
