/* ===== Widgets interativos com as fórmulas reais do projeto ===== */
const $ = (s, r = document) => r.querySelector(s);
const d10 = () => 1 + Math.floor(Math.random() * 10);

/* ---------- Calculadora de ataque (conflict_resolution + conflict_damage) ---------- */
const GRAVIDADE = {0: [3, 6], 1: [4, 8], 2: [5, 10], 3: [6, 12], 4: [7, 14], 5: [8, 16]}; // leve até a, grave até b, crítico acima
const VIT_CORPO = {0: 6, 1: 8, 2: 10, 3: 12, 4: 14, 5: 16};
const ARMOR = {none: null, leve: {prot: 1, integ: 4, red: 1}, media: {prot: 2, integ: 6, red: 2}, pesada: {prot: 3, integ: 8, red: 3}};
const PHYS = ['cortante', 'perfurante', 'impactante'];

function mountAttack() {
  const box = $('#atk');
  if (!box) return;
  box.innerHTML = `
  <div class="calc">
    <div class="grid" style="gap:10px">
      <label class="f">Virtude do atacante (0–5) <input type="range" min="0" max="5" value="4" id="aV"><span class="mono" id="aVv"></span></label>
      <label class="f">Nível do herói (bônus de early-game) <input type="range" min="1" max="20" value="1" id="aL"><span class="mono" id="aLv"></span></label>
      <label class="f">Agilidade do alvo → Esquiva = 10 + Agilidade <input type="range" min="0" max="5" value="3" id="aA"><span class="mono" id="aAv"></span></label>
      <label class="f">Dano-base <select id="aD"><option value="3">3 — ataque básico (sem Carta)</option><option value="3">3 — arma leve</option><option value="4" selected>4 — marcial</option><option value="6">6 — versátil</option><option value="8">8 — pesada</option></select></label>
      <label class="f">Tipo de dano <select id="aT"><option>cortante</option><option>perfurante</option><option>impactante</option><option>ígneo</option><option>gélido</option><option>elétrico</option><option>abissal</option><option>arcano</option><option>corrosivo</option></select></label>
      <div class="row"><label class="f">Vantagem <select id="aAdv"><option value="0">nenhuma</option><option value="1">Vantagem (3d10, 2 maiores)</option><option value="-1">Desvantagem (3d10, 2 menores)</option></select></label>
        <label class="f">Luz/clima <select id="aEnv"><option value="0">neutro</option><option value="-1">escuro sem tocha (−1)</option><option value="-2">escuro + tempestade (−2)</option></select></label></div>
      <div class="row"><label class="f">Resistência do alvo <select id="aR"><option value="0">nenhuma</option><option value="-2">resistência (−2)</option><option value="-4">resistência maior (−4)</option><option value="2">vulnerabilidade (+2)</option><option value="4">vulnerab. maior (+4)</option><option value="imune">imune</option></select></label>
        <label class="f">Armadura do alvo <select id="aArm"><option value="none">nenhuma</option><option value="leve">leve (Prot 1, Integ 4)</option><option value="media">média (Prot 2, Integ 6)</option><option value="pesada">pesada (Prot 3, Integ 8)</option></select></label></div>
      <div class="row"><label class="f">Vitalidade atual do alvo <input type="number" id="aHP" value="12" min="0" max="60"></label>
        <label class="f">Corpo do alvo (0–5) <input type="number" id="aC" value="3" min="0" max="5"></label></div>
      <div class="row"><button class="primary" id="aRoll">🎲 Rolar ataque</button><button id="aCrit">forçar Crítico (dupla 5-5)</button></div>
    </div>
    <div>
      <div class="dice" id="aDice"></div>
      <div class="verdict" id="aVerdict">Role para ver o ataque resolvido passo a passo.</div>
      <div class="pipe" id="aPipe"></div>
      <p class="hint" style="font-size:13px;color:var(--dim)">Fórmulas de <code>conflict_resolution.py</code> e <code>conflict_damage.py</code>. Simplificação didática: Proteção só vale para dano físico e a Integridade converte até o limite de reduções por ataque; secundários de gélido/elétrico/abissal/arcano não são simulados.</p>
    </div>
  </div>`;
  const upd = () => { $('#aVv').textContent = '+' + $('#aV').value; $('#aLv').textContent = 'nível ' + $('#aL').value + ' → bônus +' + earlyBonus(+$('#aL').value); $('#aAv').textContent = 'Esquiva ' + (10 + +$('#aA').value); };
  ['#aV', '#aL', '#aA'].forEach((s) => $(s).addEventListener('input', upd));
  upd();
  $('#aRoll').onclick = () => rollAttack(false);
  $('#aCrit').onclick = () => rollAttack(true);
}
const earlyBonus = (lvl) => (lvl <= 2 ? 2 : lvl === 3 ? 1 : 0);

function rollAttack(forceCrit) {
  const adv = +$('#aAdv').value;
  let dice = forceCrit ? [5, 5] : adv === 0 ? [d10(), d10()] : [d10(), d10(), d10()];
  let kept = [...dice];
  if (dice.length === 3) kept = [...dice].sort((a, b) => (adv > 0 ? b - a : a - b)).slice(0, 2);
  const keptCopy = [...kept];
  $('#aDice').innerHTML = dice.map((v) => {
    const k = keptCopy.indexOf(v);
    const isKept = k >= 0;
    if (isKept) keptCopy.splice(k, 1);
    return `<div class="die roll ${isKept ? 'kept' : 'drop'}">${v}</div>`;
  }).join('');
  const V = +$('#aV').value, env = +$('#aEnv').value, esq = 10 + +$('#aA').value;
  const total = kept[0] + kept[1] + V + env;
  const dupla = kept[0] === kept[1];
  const mult = dupla ? (kept[0] === 10 ? 3 : 2) : 1;
  const hit = dupla || total >= esq;
  const lines = [];
  lines.push([`Dados mantidos ${kept.join(' + ')}`, kept[0] + kept[1]]);
  lines.push([`+ Virtude${env ? ' + ambiente' : ''}`, `${V}${env ? ' ' + env : ''} → total ${total}`]);
  lines.push([`vs Esquiva do alvo`, esq]);
  if (dupla) lines.push([kept[0] === 10 ? 'Dupla 10 = SUPERCRÍTICO' : `Dupla ${kept[0]} = CRÍTICO`, `×${mult} e acerta sempre`]);
  if (!hit) {
    $('#aVerdict').innerHTML = `<span style="color:var(--muted)">Errou.</span> ${total} < ${esq}`;
    $('#aPipe').innerHTML = lines.map(([a, b]) => `<div><span>${a}</span><b>${b}</b></div>`).join('');
    return;
  }
  const lvl = +$('#aL').value, type = $('#aT').value;
  let dano = (+$('#aD').value + earlyBonus(lvl)) * mult;
  lines.push([`1. Dano-base ${$('#aD').value} + early-game ${earlyBonus(lvl)}, ×${mult}`, dano]);
  const r = $('#aR').value;
  if (r === 'imune') { lines.push(['2. Imunidade', 'dano zerado']); finish(lines, 0, 0, null); return; }
  if (+r) { dano = Math.max(0, dano + +r); lines.push([`2. Resistência/vulnerabilidade ${+r > 0 ? '+' : ''}${r}`, dano]); }
  const arm = ARMOR[$('#aArm').value];
  let absorbed = false;
  if (arm && PHYS.includes(type) && dano > 0) {
    const prot = Math.max(0, arm.prot - (type === 'perfurante' ? 1 : 0));
    const before = dano; dano = Math.max(0, dano - prot); absorbed = before !== dano;
    lines.push([`3. Proteção ${prot}${type === 'perfurante' ? ' (perfurante −1)' : ''}`, dano]);
    const integCost = 1;
    const red = Math.min(arm.red, arm.integ, dano);
    if (red > 0) { dano -= red; lines.push([`4. Integridade converte ${red} em redução`, dano]); }
    if (type === 'impactante' && absorbed) lines.push(['   impactante gasta +1 de Integridade', '—']);
    void integCost;
  } else if (arm) lines.push(['3–4. Armadura não protege este tipo', dano]);
  if (type === 'ígneo' && dano >= 1) { dano += 2; lines.push(['5. Ígneo atravessou: +2', dano]); }
  const hp = +$('#aHP').value;
  const exc = Math.max(0, dano - hp), hpAfter = Math.max(0, hp - dano);
  lines.push([`6. Vitalidade ${hp} → ${hpAfter}`, `excedente ${exc}`]);
  const C = Math.max(0, Math.min(5, +$('#aC').value));
  let cat = null;
  if (exc > 0) { const [a, b] = GRAVIDADE[C]; cat = exc <= a ? 'leve' : exc <= b ? 'grave' : 'crítico'; lines.push([`7. Faixa de Gravidade do Corpo ${C} (leve ≤${GRAVIDADE[C][0]}, grave ≤${GRAVIDADE[C][1]})`, `Ferimento ${cat}`]); if (type === 'cortante') lines.push(['   cortante + ferido → Sangramento', '1 de dano, 1 turno']); }
  finish(lines, dano, exc, cat);
}
function finish(lines, dano, exc, cat) {
  $('#aVerdict').innerHTML = `Acertou: <b style="color:var(--gold)">${dano}</b> de dano${cat ? ` · <span style="color:var(--danger)">Ferimento ${cat}</span>` : exc === 0 ? ' · sem Ferimento' : ''}`;
  $('#aPipe').innerHTML = lines.map(([a, b]) => `<div><span>${a}</span><b>${b}</b></div>`).join('');
}

/* ---------- Simulador do RoutedLLM ---------- */
const ROUTES = {
  CLASSIFY: ['DeepSeek v4 flash', 'Groq gpt-oss-20b', 'Gemini flash-lite'],
  FAST: ['DeepSeek v4 flash', 'Groq gpt-oss-120b', 'MiniMax M2.5', 'Qwen plus', 'Gemini flash'],
  SMART: ['DeepSeek v4 flash', 'Groq gpt-oss-120b', 'Anthropic Claude Sonnet', 'Gemini pro'],
};
const OUTCOMES = {ok: 'responde OK', timeout: 'timeout / 429 / 5xx', perm: '402 sem saldo / 401 chave inválida', schema: 'JSON fora do schema (3x)', schema1: 'JSON inválido 1x, depois OK', text: 'JSON em texto (sem tool call)'};
function mountRouted() {
  const box = $('#routed');
  if (!box) return;
  box.innerHTML = `<div class="row" style="margin-bottom:10px"><span>Tier:</span>${Object.keys(ROUTES).map((t, i) => `<button data-tier="${t}" class="${i === 1 ? 'on' : ''}">${t}</button>`).join('')}</div><div id="rCands" class="grid" style="gap:8px"></div><div class="row" style="margin:12px 0"><button class="primary" id="rGo">▶ Simular invoke()</button><button id="rRand">aleatório</button></div><div class="seq" id="rLog"></div>`;
  let tier = 'FAST';
  const draw = () => {
    $('#rCands').innerHTML = ROUTES[tier].map((c, i) => `<div class="row card" style="padding:8px 12px"><b style="min-width:220px">${i + 1}. ${c}</b><select data-c="${i}">${Object.entries(OUTCOMES).map(([k, v]) => `<option value="${k}" ${i === ROUTES[tier].length - 1 || (i === 0 ? false : false) ? '' : ''}>${v}</option>`).join('')}</select></div>`).join('');
    const sels = box.querySelectorAll('#rCands select');
    if (sels[0]) sels[0].value = 'timeout';
  };
  box.querySelectorAll('[data-tier]').forEach((b) => (b.onclick = () => { tier = b.dataset.tier; box.querySelectorAll('[data-tier]').forEach((x) => x.classList.toggle('on', x === b)); draw(); }));
  draw();
  $('#rRand').onclick = () => box.querySelectorAll('#rCands select').forEach((s) => (s.value = Object.keys(OUTCOMES)[Math.floor(Math.random() * 6)]));
  $('#rGo').onclick = () => {
    const log = [];
    const outs = [...box.querySelectorAll('#rCands select')].map((s) => s.value);
    let ok = false;
    for (let i = 0; i < outs.length && !ok; i++) {
      const n = ROUTES[tier][i], o = outs[i];
      if (o === 'ok') { log.push([n, '✔ sucesso na 1ª geração → devolve o modelo Pydantic']); ok = true; }
      else if (o === 'timeout') log.push([n, '✖ erro de TRANSPORTE: não regenera no mesmo provider; troca de provider (max_retries=0)']);
      else if (o === 'perm') log.push([n, '✖ erro PERMANENTE: abre circuit breaker até a próxima campanha; troca de provider']);
      else if (o === 'schema') { log.push([n, '⟳ geração 1: falha de schema → regenera com mensagem dizendo qual contrato falhou']); log.push([n, '⟳ geração 2 e 3: ainda inválido → desiste deste provider']); }
      else if (o === 'schema1') { log.push([n, '⟳ geração 1 inválida → regenera no MESMO provider']); log.push([n, '✔ geração 2 válida']); ok = true; }
      else if (o === 'text') { log.push([n, '⚑ sem tool call, mas o texto tem um objeto JSON → recuperação local (recovery="local_json"), SEM nova request']); ok = true; }
    }
    if (!ok) log.push(['RoutedLLM', '∅ esgotou → AIMessage(""). O nó cai no caminho determinístico pelo guard isinstance — o jogador nunca vê erro de provider.']);
    $('#rLog').innerHTML = log.map(([a, b]) => `<div class="msg"><span>${a}</span><span>${b}</span></div>`).join('');
    [...$('#rLog').children].forEach((m, k) => setTimeout(() => m.classList.add('on'), 250 * k));
  };
}

/* ---------- Economia: preço (services/economy.py) ---------- */
const RARITY = {comum: 25, incomum: 100, raro: 400, 'épico': 1500, 'lendário': 6000};
function mountPrice() {
  const box = $('#price');
  if (!box) return;
  box.innerHTML = `<div class="calc"><div class="grid" style="gap:10px">
    <label class="f">Raridade (preço-base) <select id="pR">${Object.entries(RARITY).map(([k, v]) => `<option value="${v}">${k} — ${v}</option>`).join('')}</select></label>
    <label class="f">Oferta <select id="pS"><option value="0.6">o local PRODUZ o item (×0,6)</option><option value="1" selected>há produtor alcançável (×1,0)</option><option value="1.8">rotas até produtores bloqueadas (×1,8 — some da prateleira)</option></select></label>
    <label class="f">Multiplicador do mercador <input type="range" min="0.8" max="1.4" step="0.05" value="1" id="pM"><span class="mono" id="pMv"></span></label>
    <div class="row"><label><input type="checkbox" id="pH"> facção que controla o local é hostil (×1,5 na compra)</label></div>
    <div class="row"><label><input type="checkbox" id="pV"> estou VENDENDO (×0,5)</label></div></div>
    <div><div class="verdict" id="pOut"></div><div class="pipe" id="pPipe"></div><p style="font-size:13px;color:var(--dim)">Arredonda para múltiplo de 5. A IA nunca decide sinal nem valor do ouro: só interpreta "compro / vendo / quanto custa".</p></div></div>`;
  const calc = () => {
    const b = +$('#pR').value, s = +$('#pS').value, m = +$('#pM').value, h = $('#pH').checked && !$('#pV').checked, v = $('#pV').checked;
    $('#pMv').textContent = '×' + m.toFixed(2);
    let p = b * s * m * (h ? 1.5 : 1) * (v ? 0.5 : 1);
    const r5 = Math.max(5, Math.round(p / 5) * 5);
    $('#pOut').innerHTML = `Preço final: <b style="color:var(--gold)">${r5}</b> de ouro${s === 1.8 ? ' <span class="tag err">indisponível na prateleira</span>' : ''}`;
    $('#pPipe').innerHTML = [[`base`, b], [`× oferta`, s], [`× mercador`, m.toFixed(2)], [`× hostil`, h ? 1.5 : 1], [`× venda`, v ? 0.5 : 1], [`= bruto`, p.toFixed(1)], ['arredondado (5)', r5]].map(([a, c]) => `<div><span>${a}</span><b>${c}</b></div>`).join('');
  };
  box.querySelectorAll('select,input').forEach((i) => i.addEventListener('input', calc));
  calc();
}

/* ---------- Orçamento de encontro (encounter_budget.py) ---------- */
function mountBudget() {
  const box = $('#budget');
  if (!box) return;
  box.innerHTML = `<div class="calc"><div class="grid" style="gap:10px">
    <label class="f">Nível do herói <input type="range" min="1" max="20" value="1" id="bL"><span class="mono" id="bLv"></span></label>
    <label class="f">Perigo do local (1–4) <input type="range" min="1" max="4" value="4" id="bD"><span class="mono" id="bDv"></span></label>
    <label class="f">Aliados <input type="range" min="0" max="3" value="0" id="bA"><span class="mono" id="bAv"></span></label></div>
    <div><div class="verdict" id="bOut"></div><div class="pipe" id="bPipe"></div><p style="font-size:13px;color:var(--dim)">Custo por inimigo: lacaio 2, elite 5, chefe 12. Chefes nunca são cortados. No nível 1 no máximo 1 elite. O teto nasceu de um playtest: nível 1 em perigo 4 recebia 2 elites — sentença de morte.</p></div></div>`;
  const BASE = {1: 2, 2: 4, 3: 7, 4: 10};
  const calc = () => {
    const L = +$('#bL').value, D = +$('#bD').value, A = +$('#bA').value;
    $('#bLv').textContent = L; $('#bDv').textContent = D; $('#bAv').textContent = A;
    const raw = BASE[D] + L + 2 * A, cap = 5 + 3 * L + 2 * A, b = Math.min(raw, cap);
    $('#bOut').innerHTML = `Orçamento: <b style="color:var(--gold)">${b}</b> pontos ≈ ${Math.floor(b / 2)} lacaios ou ${Math.floor(b / 5)} elite(s)`;
    $('#bPipe').innerHTML = [[`base pelo perigo ${D}`, BASE[D]], ['+ nível', L], ['+ 2 × aliados', 2 * A], ['= bruto', raw], ['teto de sobrevivência 5 + 3·nível + 2·aliados', cap], ['= min(bruto, teto)', b]].map(([a, c]) => `<div><span>${a}</span><b>${c}</b></div>`).join('');
  };
  box.querySelectorAll('input').forEach((i) => i.addEventListener('input', calc));
  calc();
}

/* ---------- Pontuação de fatos no contexto ---------- */
function mountScore() {
  const box = $('#score');
  if (!box) return;
  const f = [['rel', 'Relevância (termos da consulta)', 0.35, 0.6], ['loc', 'Mesmo local', 0.25, 1], ['ent', 'Entidades em cena', 0.2, 0.5], ['imp', 'Impacto do tipo de evento', 0.1, 1], ['rec', 'Recência (1 − turnos/50)', 0.1, 0.8]];
  box.innerHTML = `<div class="calc"><div class="grid" style="gap:8px">${f.map(([k, l, w, v]) => `<label class="f">${l} <span class="pill">peso ${w}</span><input type="range" min="0" max="1" step="0.05" value="${v}" data-k="${k}" data-w="${w}"></label>`).join('')}</div>
  <div><div class="verdict" id="sOut"></div><div class="hbars" id="sBars"></div><h4>Orçamento de 3.500 tokens por seção</h4><div class="hbars" id="sBudget"></div></div></div>`;
  const budget = [['current_state', 25], ['active_location', 20], ['relations', 15], ['entities', 15], ['lore', 15], ['session_memory', 10]];
  $('#sBudget').innerHTML = budget.map(([n, p]) => `<div class="hb"><span>${n}</span><div class="bar"><i style="width:${p * 4}%"></i></div><span>${Math.round(3500 * p / 100)} tk</span></div>`).join('');
  const calc = () => {
    let s = 0;
    const parts = [...box.querySelectorAll('input')].map((i) => { const c = +i.value * +i.dataset.w; s += c; return [i.parentElement.firstChild.textContent.trim(), c]; });
    $('#sOut').innerHTML = `score = <b style="color:var(--gold)">${s.toFixed(3)}</b>`;
    $('#sBars').innerHTML = parts.map(([n, c]) => `<div class="hb"><span>${n}</span><div class="bar"><i style="width:${(c / 0.35) * 100}%"></i></div><span>${c.toFixed(3)}</span></div>`).join('');
  };
  box.querySelectorAll('input').forEach((i) => i.addEventListener('input', calc));
  calc();
}

/* ---------- Tabela de XP ---------- */
function mountXP() {
  const box = $('#xp');
  if (!box) return;
  const T = {2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000};
  const slots = (n) => (n <= 3 ? 4 : n <= 6 ? 5 : n <= 9 ? 6 : n <= 12 ? 7 : n <= 16 ? 8 : n <= 19 ? 9 : 10);
  const extra = (n) => [n === 3 ? 'subclasse (irreversível)' : '', [2, 4, 6, 8, 10].includes(n) ? '+1 Virtude' : '', [12, 16, 20].includes(n) ? 'Maestria' : '', n === 20 ? 'Ápice automático' : '', n < 20 ? 'Carta ou evolução A/B' : ''].filter(Boolean).join(' · ');
  box.innerHTML = `<div class="hbars">${Object.entries(T).map(([n, x]) => `<div class="hb" title="${extra(+n)}"><span>nível ${n} · ${slots(+n)} slots</span><div class="bar"><i style="width:${(x / 355000) * 100}%"></i></div><span>${x.toLocaleString('pt-BR')}</span></div>`).join('')}</div><p style="font-size:13px;color:var(--dim)">Passe o mouse para ver as escolhas de cada nível. XP: lacaio 50, elite 200, chefe 1.000, beat de campanha 150, quest 200 (+20 de ouro).</p>`;
}

/* ---------- Sequência SSE ---------- */
function mountSSE() {
  const box = $('#sse');
  if (!box) return;
  const ev = [['accepted', '{game_id} — a thread worker assumiu o turno (dona do lock e do save)'], ['phase', '{node:"campaign_manager", status:"done"} → "O mestre consulta os arcanos…"'], ['route', '{route:"storyteller"} → "O narrador tece o destino…"'], ['phase', '{node:"storyteller"}'], ['phase', '{node:"archivist"}'], [': ping', 'a cada 10 s sem evento (evita timeout de proxy)'], ['visual', 'cue de primeira aparição de NPC + cena do local'], ['narrative', '{chunk:"Você deixa as muralhas…", done:false} — pedaços de 80 caracteres'], ['narrative', '{chunk:"", done:true}'], ['state', 'GameResponse completo (HUD, mapa, combate, missões, crônica…)']];
  box.innerHTML = `<div class="row" style="margin-bottom:8px"><button class="primary" id="sseGo">▶ Reproduzir stream</button><span style="font-size:13px;color:var(--dim)">Se o stream cair, o cliente reenvia via POST com o MESMO action_id — o backend devolve o mesmo turno, nunca roda duas vezes.</span></div><div class="seq">${ev.map(([a, b]) => `<div class="msg"><span>${a}</span><span>${b}</span></div>`).join('')}</div>`;
  $('#sseGo').onclick = () => { const m = box.querySelectorAll('.msg'); m.forEach((x) => x.classList.remove('on')); m.forEach((x, k) => setTimeout(() => x.classList.add('on'), 420 * k)); };
}

/* ---------- Sequência claim/commit ---------- */
function mountClaim() {
  const box = $('#claim');
  if (!box) return;
  const ev = [['cliente', 'POST com action_id (obrigatório no perfil durável)'], ['receipt?', 'já existe recibo para essa operação? → devolve a resposta gravada (exactly-once)'], ['claim', 'TX curta: SELECT games FOR UPDATE → versão bate? jogo livre? INSERT operations ON CONFLICT → lease 180 s'], ['heartbeat', 'thread renova o lease a cada 45 s enquanto a IA pensa'], ['grafo', 'LangGraph roda FORA de qualquer transação'], ['commit_game', 'TX: fencing (lease_token) + versão otimista; UPDATE games version+1; eventos; checkpoint; turns; flush do outbox; receipt'], ['falha?', 'perdeu o lease → LeaseHeld; versão velha → StaleVersion (409); worker atrasado não publica'], ['retry', 'mesma chave e mesmo payload → recibo; payload diferente → 409 operation_request_mismatch']];
  box.innerHTML = `<div class="row" style="margin-bottom:8px"><button class="primary" id="clGo">▶ Reproduzir</button></div><div class="seq">${ev.map(([a, b]) => `<div class="msg"><span>${a}</span><span>${b}</span></div>`).join('')}</div>`;
  $('#clGo').onclick = () => { const m = box.querySelectorAll('.msg'); m.forEach((x) => x.classList.remove('on')); m.forEach((x, k) => setTimeout(() => x.classList.add('on'), 500 * k)); };
}

/* ---------- Visibilidade do RAG ---------- */
function mountVis() {
  const box = $('#vis');
  if (!box) return;
  const docs = [['Anel de Lama — descrição sensorial do bairro', 'public'], ['Velha Magda — curandeira do Anel de Lama', 'public'], ['Velha Magda — identidade secreta (Mão Sombria)', 'hidden'], ['O Aprendiz que destruiu Aethelgard foi o maior herói', 'secret'], ['Verme Primordial das Raízes do Mundo', 'hidden'], ['Rumores sobre Valerius', 'public'], ['Doc com visibilidade digitada errado: "publik"', '???']];
  const rank = {public: 0, hidden: 1, secret: 2};
  box.innerHTML = `<div class="row" style="margin-bottom:8px"><span>Quem consulta?</span><button data-v="0" class="on">narrador / NPC (public)</button><button data-v="1">planejador de campanha (vê hidden/secret no grafo)</button></div><div id="visList" class="grid" style="gap:6px"></div>`;
  const draw = (max) => { $('#visList').innerHTML = docs.map(([t, v]) => { const r = v in rank ? rank[v] : 2; const ok = max === 1 || r <= max; return `<div class="row card" style="padding:8px 12px;opacity:${ok ? 1 : 0.35}"><span class="tag ${v === 'public' ? 'ok' : v === 'hidden' ? 'warn' : 'err'}">${v}${v === '???' ? ' → tratado como secret' : ''}</span><span>${t}</span><span style="margin-left:auto">${ok ? '✔ entra' : '✖ filtrado'}</span></div>`; }).join(''); };
  box.querySelectorAll('[data-v]').forEach((b) => (b.onclick = () => { box.querySelectorAll('[data-v]').forEach((x) => x.classList.toggle('on', x === b)); draw(+b.dataset.v); }));
  draw(0);
}
