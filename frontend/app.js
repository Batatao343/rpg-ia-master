/* Crônicas — cliente do RPG. Vanilla, fala com a API FastAPI na mesma origem. */
(() => {
  "use strict";

  const LS_KEY = "cronicas_game_id";
  const $ = (id) => document.getElementById(id);

  const state = { gameId: null, level: 1, busy: false, simNoticed: false };

  // ---------- helpers de rede ----------
  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  }

  // ---------- banner ----------
  let bannerTimer = null;
  function banner(msg, kind = "error") {
    const el = $("banner");
    el.textContent = msg;
    el.classList.toggle("is-warn", kind === "warn");
    el.hidden = false;
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(() => (el.hidden = true), kind === "warn" ? 9000 : 6000);
  }

  const FALLBACK_HINTS = ["erro ai", "indisponível", "narrador está indisponível", "transação falhou"];
  function looksDegraded(text) {
    const t = (text || "").toLowerCase();
    return FALLBACK_HINTS.some((h) => t.includes(h));
  }

  // ---------- render: mensagens ----------
  function addMessage(text, { role = "narrator", type = "STORY" } = {}) {
    const log = $("log");
    const wrap = document.createElement("article");
    wrap.className = "msg msg--" + (role === "player" ? "player" : type.toLowerCase());

    const roleEl = document.createElement("p");
    roleEl.className = "msg__role";
    roleEl.textContent = role === "player" ? "Você" : type === "NPC" ? "Diálogo" : type === "COMBAT" ? "Combate" : type === "LOOT" ? "Espólio" : "Narrador";

    const body = document.createElement("div");
    body.className = "msg__body";
    body.innerHTML = mdLite(text);

    wrap.append(roleEl, body);
    log.appendChild(wrap);
    scrollStory();
  }

  // markdown mínimo e seguro: escapa HTML, depois aplica **negrito** e *itálico*
  function mdLite(text) {
    const esc = String(text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return esc
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*(?!\s)([^*]+?)\*/g, "$1<em>$2</em>");
  }

  function scrollStory() {
    const s = document.querySelector(".story");
    if (s) s.scrollTop = s.scrollHeight;
  }

  function thinking(on) {
    $("thinking").hidden = !on;
    if (on) scrollStory();
  }

  // ---------- render: HUD ----------
  function setBar(fillId, cur, max, lowKindEl) {
    const pct = max > 0 ? Math.max(0, Math.min(100, (cur / max) * 100)) : 0;
    $(fillId).style.width = pct + "%";
    if (lowKindEl) lowKindEl.classList.toggle("is-low", pct <= 30);
  }

  function renderState(r) {
    const p = r.player_stats || {};
    $("h-name").textContent = p.name || "Herói";
    $("h-sub").textContent = [p.class_name, p.race].filter(Boolean).join(" · ") || "—";

    $("h-hp").textContent = `${p.hp ?? 0}/${p.max_hp ?? 0}`;
    setBar("h-hp-fill", p.hp, p.max_hp, document.querySelector('.bar[data-kind="hp"]'));
    $("h-mana").textContent = `${p.mana ?? 0}/${p.max_mana ?? 0}`;
    setBar("h-mana-fill", p.mana, p.max_mana);
    $("h-stam").textContent = `${p.stamina ?? 0}/${p.max_stamina ?? 0}`;
    setBar("h-stam-fill", p.stamina, p.max_stamina);

    $("h-level").textContent = p.level ?? 1;
    $("h-xp").textContent = p.xp ?? 0;
    $("h-gold").textContent = p.gold ?? 0;
    $("h-def").textContent = p.defense ?? 0;

    // inventário
    const inv = $("h-inv");
    inv.innerHTML = "";
    const items = r.inventory || [];
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "empty"; li.textContent = "Vazio";
      inv.appendChild(li);
    } else {
      for (const it of items) {
        const li = document.createElement("li");
        li.textContent = prettyItem(it);
        inv.appendChild(li);
      }
    }

    renderCombat(r.combat || {});
    renderQuest(r.quest || {});

    $("h-summary").textContent = r.narrative_summary || "A aventura começa.";
    $("t-location").textContent = r.current_location || "—";

    const w = r.world || {};
    if (w.period) $("t-clock").textContent = `Dia ${w.day} · ${w.period}`;

    // morte
    if ((p.hp ?? 1) <= 0) $("overlay-death").hidden = false;
  }

  function renderCombat(c) {
    const block = $("combatblock");
    const enemies = c.enemies || [];
    if (!c.active || !enemies.length) { block.hidden = true; return; }
    block.hidden = false;

    $("h-combat-round").textContent = c.round ? `· Round ${c.round}` : "";

    // inimigos com barra de HP + condições
    const ul = $("h-enemies");
    ul.innerHTML = "";
    enemies.forEach((e) => {
      const li = document.createElement("li");
      li.className = "enemy";
      const pct = e.max_hp > 0 ? Math.max(0, Math.min(100, (e.hp / e.max_hp) * 100)) : 0;
      const top = document.createElement("div");
      top.className = "enemy__top";
      top.innerHTML = `<span>${escapeHtml(e.name)}</span><span class="muted">${e.hp}/${e.max_hp}</span>`;
      const track = document.createElement("div");
      track.className = "enemy__track";
      const fill = document.createElement("div");
      fill.className = "enemy__fill";
      fill.style.width = pct + "%";
      track.appendChild(fill);
      li.append(top, track);
      if ((e.conditions || []).length) li.appendChild(condChips(e.conditions));
      ul.appendChild(li);
    });

    // iniciativa
    const order = c.order || [];
    $("h-init-label").hidden = order.length === 0;
    const ol = $("h-initiative");
    ol.innerHTML = "";
    order.forEach((o) => {
      const li = document.createElement("li");
      li.className = "init " + (o.side === "hero" ? "init--hero" : "init--enemy");
      li.textContent = `${o.init} · ${o.name}`;
      ol.appendChild(li);
    });

    // condições do player
    const pconds = c.player_conditions || [];
    $("h-pcond-block").hidden = pconds.length === 0;
    const pul = $("h-pconds");
    pul.innerHTML = "";
    if (pconds.length) pul.appendChild(condChips(pconds, true));

    // cooldowns de habilidade
    const cds = c.cooldowns || {};
    const keys = Object.keys(cds);
    $("h-cd-block").hidden = keys.length === 0;
    const cdRow = $("h-cooldowns");
    cdRow.innerHTML = "";
    keys.forEach((k) => {
      const chip = document.createElement("span");
      chip.className = "cond-chip";
      chip.textContent = `${prettyItem(k)} (${cds[k]})`;
      cdRow.appendChild(chip);
    });
  }

  function condChips(conds, asChildren) {
    const wrap = document.createElement(asChildren ? "li" : "div");
    wrap.className = "conds__row";
    conds.forEach((cd) => {
      const chip = document.createElement("span");
      chip.className = "cond-chip" + (cd.dot > 0 ? " is-dot" : "");
      const dot = cd.dot > 0 ? ` ${cd.dot}/t` : "";
      chip.textContent = `${cd.name}${dot} (${cd.duration})`;
      wrap.appendChild(chip);
    });
    return wrap;
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderQuest(q) {
    const block = $("questblock");
    const beats = q.beats || [];
    if (!q.objective && !beats.length) { block.hidden = true; return; }
    block.hidden = false;

    const done = beats.filter((b) => b.status === "done").length;
    const total = q.total || beats.length;
    const progress = total ? ` (${Math.min(done, total)}/${total})` : "";
    $("h-quest-obj").textContent = (q.objective || "Avance a trama.") + progress;

    const ol = $("h-quest-beats");
    ol.innerHTML = "";
    beats.forEach((b, i) => {
      const li = document.createElement("li");
      const isDone = b.status === "done";
      const isCurrent = !isDone && i === (q.current_step ?? 0);
      li.className = "quest__beat" + (isDone ? " is-done" : isCurrent ? " is-current" : "");
      li.textContent = b.description || "";
      ol.appendChild(li);
    });
  }

  function prettyItem(id) {
    return String(id).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // ---------- fluxo de telas ----------
  function showPlay() {
    $("screen-create").hidden = true;
    $("screen-play").hidden = false;
  }
  function showCreate() {
    $("screen-play").hidden = true;
    $("overlay-death").hidden = true;
    $("screen-create").hidden = false;
  }

  // ---------- carregar opções de criação ----------
  async function loadOptions() {
    try {
      const o = await api("/data/options");
      fillSelect("f-race", o.races);
      fillSelect("f-class", o.classes);
      fillSelect("f-region", o.regions);
    } catch (e) {
      banner("Não consegui carregar as opções. A API está rodando? (" + e.message + ")");
    }
  }
  function fillSelect(id, values) {
    const sel = $(id);
    sel.innerHTML = "";
    (values || []).forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
  }

  // ---------- nível segmentado ----------
  function initLevel() {
    $("f-level").addEventListener("click", (e) => {
      const b = e.target.closest(".seg");
      if (!b) return;
      document.querySelectorAll("#f-level .seg").forEach((s) => s.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      state.level = parseInt(b.dataset.level, 10) || 1;
    });
  }

  // ---------- criar personagem ----------
  async function createCharacter(e) {
    e.preventDefault();
    if (state.busy) return;
    const f = $("form-create");
    const payload = {
      name: f.name.value.trim() || "Herói",
      race: f.race.value,
      class_name: f.class_name.value,
      region: f.region.value,
      level: state.level,
      backstory: f.backstory.value.trim(),
    };
    setBusy(true, "btn-create", "Forjando…");
    showPlay();
    $("log").innerHTML = "";
    thinking(true);
    try {
      const r = await api("/game/new", { method: "POST", body: JSON.stringify(payload) });
      onTurn(r, { opening: true });
    } catch (err) {
      showCreate();
      banner("Falha ao criar personagem: " + err.message);
    } finally {
      thinking(false);
      setBusy(false, "btn-create", "Começar a jornada");
    }
  }

  // ---------- agir ----------
  async function sendAction(e) {
    e.preventDefault();
    if (state.busy) return;
    const input = $("action-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    addMessage(text, { role: "player" });
    setBusy(true, "btn-send", "…");
    thinking(true);
    try {
      const r = await api("/game/action", {
        method: "POST",
        body: JSON.stringify({ input_text: text, game_id: state.gameId }),
      });
      onTurn(r);
    } catch (err) {
      banner("O destino tropeçou: " + err.message);
    } finally {
      thinking(false);
      setBusy(false, "btn-send", "Agir");
      input.focus();
    }
  }

  // ---------- resultado de um turno ----------
  function onTurn(r, { opening = false } = {}) {
    state.gameId = r.game_id || state.gameId;
    if (state.gameId) localStorage.setItem(LS_KEY, state.gameId);
    addMessage(r.message, { role: "narrator", type: r.message_type || "STORY" });
    renderState(r);
    if (r.simulated && !state.simNoticed) {
      state.simNoticed = true;
      banner("Modo simulado: história fictícia para testar a interface. Adicione GOOGLE_API_KEY no .env para a IA real.", "warn");
    } else if (!r.simulated && looksDegraded(r.message)) {
      banner("Modo degradado: defina GOOGLE_API_KEY no .env para o narrador responder de verdade.", "warn");
    }
  }

  function setBusy(on, btnId, label) {
    state.busy = on;
    const b = $(btnId);
    if (b) { b.disabled = on; if (label) b.textContent = label; }
  }

  // ---------- continuar jornada anterior ----------
  async function tryOfferContinue() {
    const saved = localStorage.getItem(LS_KEY);
    if (!saved) return;
    try {
      const r = await api("/game/state?game_id=" + encodeURIComponent(saved));
      const btn = $("btn-continue");
      btn.hidden = false;
      btn.addEventListener("click", () => {
        state.gameId = saved;
        showPlay();
        $("log").innerHTML = "";
        addMessage(r.message || "Você retoma sua jornada.", { role: "narrator", type: r.message_type || "STORY" });
        renderState(r);
      });
    } catch (_) {
      localStorage.removeItem(LS_KEY); // save sumiu
    }
  }

  // ---------- bind UI ----------
  function init() {
    loadOptions();
    initLevel();
    tryOfferContinue();

    $("form-create").addEventListener("submit", createCharacter);
    $("form-action").addEventListener("submit", sendAction);
    $("btn-new").addEventListener("click", () => { showCreate(); });
    $("btn-restart").addEventListener("click", () => { showCreate(); });
    $("btn-hud").addEventListener("click", () => $("hud").classList.toggle("is-open"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
