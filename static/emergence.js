/* Ξ.Emergence — live instrument for the Kuramoto field.
   Every pixel is drawn from /api/emergence/state; nothing is simulated here. */
(() => {
  const API = "/api/emergence";
  const GLYPHS = { converge: "⊚", perturb: "⟐", entrain: "⋈", seed: "∞", witness: "Ψ", quench: "∴", reset: "↺" };
  const OPERATORS = [
    ["converge", "Converge"], ["quench", "Quench"], ["perturb", "Perturb"],
    ["entrain", "Entrain"], ["seed", "Seed"], ["witness", "Witness"], ["reset", "Reset"],
  ];

  const $ = (id) => document.getElementById(id);
  const disc = $("em-disc"), order = $("em-order");
  const metricsBox = $("em-metrics"), actionsBox = $("em-actions");
  const statusEl = $("em-status"), eventsEl = $("em-events");

  const view = { nodes: [], topology: null, targetTheta: [], shownTheta: [], local: [], history: [], events: [], latest: null, nodeCount: 0, busy: false };

  // ── helpers ───────────────────────────────────────────────────────────
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const shortAngle = (a, b) => {
    let d = (a - b) % (Math.PI * 2);
    if (d > Math.PI) d -= Math.PI * 2;
    if (d < -Math.PI) d += Math.PI * 2;
    return d;
  };
  const fit = (canvas) => {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 300, h = canvas.clientHeight || 300;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  };
  const phaseColor = (local, alpha = 1) => {
    // violet (disordered) → cyan (forming) → gold (ordered)
    const t = clamp(local, 0, 1);
    const mix = (a, b, k) => a.map((x, i) => Math.round(x + (b[i] - x) * k));
    const violet = [149, 117, 205], cyan = [77, 208, 225], gold = [240, 199, 94];
    const c = t < 0.5 ? mix(violet, cyan, t / 0.5) : mix(cyan, gold, (t - 0.5) / 0.5);
    return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
  };

  // ── the phase disc ────────────────────────────────────────────────────
  function drawDisc() {
    const { ctx, w, h } = fit(disc);
    const cx = w / 2, cy = h / 2;
    const R0 = Math.min(w, h) * 0.42;
    ctx.clearRect(0, 0, w, h);

    // outer ring + phase ticks
    ctx.strokeStyle = "rgba(212,168,75,0.16)";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(cx, cy, R0, 0, Math.PI * 2); ctx.stroke();
    for (let k = 0; k < 24; k++) {
      const a = (k / 24) * Math.PI * 2;
      const long = k % 6 === 0;
      ctx.strokeStyle = long ? "rgba(212,168,75,0.28)" : "rgba(212,168,75,0.12)";
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * R0, cy + Math.sin(a) * R0);
      ctx.lineTo(cx + Math.cos(a) * (R0 - (long ? 9 : 4)), cy + Math.sin(a) * (R0 - (long ? 9 : 4)));
      ctx.stroke();
    }

    const n = view.shownTheta.length;
    if (!n) return;
    const pos = (i) => {
      const r = R0 * (0.40 + 0.60 * ((i * 0.6180339887) % 1));
      const a = view.shownTheta[i];
      return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
    };

    // coupled edges — alignment brightens the link
    if (view.topology) {
      ctx.lineWidth = 0.6;
      for (const e of view.topology.edges) {
        if (e.a >= n || e.b >= n) continue;
        const align = Math.max(0, Math.cos(view.shownTheta[e.a] - view.shownTheta[e.b]));
        if (align <= 0.02) continue;
        const [x1, y1] = pos(e.a), [x2, y2] = pos(e.b);
        ctx.strokeStyle = `rgba(77,208,225,${(align * 0.20).toFixed(3)})`;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
    }

    // mean field vector
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { mx += Math.cos(view.shownTheta[i]); my += Math.sin(view.shownTheta[i]); }
    const orderParam = Math.hypot(mx, my) / n;
    const mAngle = Math.atan2(my, mx);
    const armLen = R0 * orderParam;
    const grad = ctx.createLinearGradient(cx, cy, cx + Math.cos(mAngle) * armLen, cy + Math.sin(mAngle) * armLen);
    grad.addColorStop(0, "rgba(240,199,94,0.05)");
    grad.addColorStop(1, "rgba(240,199,94,0.85)");
    ctx.strokeStyle = grad;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(mAngle) * armLen, cy + Math.sin(mAngle) * armLen); ctx.stroke();
    ctx.beginPath(); ctx.arc(cx + Math.cos(mAngle) * armLen, cy + Math.sin(mAngle) * armLen, 3.2, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(240,199,94,0.9)"; ctx.fill();

    // oscillators
    for (let i = 0; i < n; i++) {
      const [x, y] = pos(i);
      const local = view.local[i] ?? 0.5;
      const r = 2.2 + local * 3.4;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = phaseColor(local, 0.92);
      ctx.shadowColor = phaseColor(local, 0.85);
      ctx.shadowBlur = 6 + local * 12;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  }

  // ── order parameter history ───────────────────────────────────────────
  function drawOrder() {
    const { ctx, w, h } = fit(order);
    ctx.clearRect(0, 0, w, h);
    const pad = 4;
    const y = (v) => pad + (1 - clamp(v, 0, 1)) * (h - pad * 2);
    const samples = view.history;
    if (samples.length < 2) return;

    // bands
    ctx.fillStyle = "rgba(240,199,94,0.05)";
    ctx.fillRect(pad, y(1), w - pad * 2, y(0.84) - y(1));
    ctx.fillStyle = "rgba(77,208,225,0.05)";
    ctx.fillRect(pad, y(0.62), w - pad * 2, y(0.40) - y(0.62));

    ctx.setLineDash([3, 4]);
    ctx.strokeStyle = "rgba(240,199,94,0.30)";
    ctx.beginPath(); ctx.moveTo(pad, y(0.84)); ctx.lineTo(w - pad, y(0.84)); ctx.stroke();
    ctx.strokeStyle = "rgba(149,117,205,0.35)";
    ctx.beginPath(); ctx.moveTo(pad, y(0.40)); ctx.lineTo(w - pad, y(0.40)); ctx.stroke();
    ctx.setLineDash([]);

    const t0 = samples[0].t, t1 = samples[samples.length - 1].t;
    const span = Math.max(t1 - t0, 1e-6);
    const x = (t) => pad + ((t - t0) / span) * (w - pad * 2);

    // fill
    ctx.beginPath();
    ctx.moveTo(x(samples[0].t), h - pad);
    samples.forEach((s) => ctx.lineTo(x(s.t), y(s.R)));
    ctx.lineTo(x(samples[samples.length - 1].t), h - pad);
    ctx.closePath();
    const fill = ctx.createLinearGradient(0, 0, 0, h);
    fill.addColorStop(0, "rgba(212,168,75,0.22)");
    fill.addColorStop(1, "rgba(212,168,75,0)");
    ctx.fillStyle = fill; ctx.fill();

    // line
    ctx.beginPath();
    samples.forEach((s, i) => (i ? ctx.lineTo(x(s.t), y(s.R)) : ctx.moveTo(x(s.t), y(s.R))));
    ctx.strokeStyle = "rgba(240,199,94,0.9)"; ctx.lineWidth = 1.4; ctx.stroke();

    // emergence markers
    for (const ev of view.events) {
      const t = parseFloat(String(ev.data?.at || "").replace("t=", ""));
      if (!Number.isFinite(t) || t < t0 || t > t1) continue;
      ctx.strokeStyle = ev.kind === "ignition" ? "rgba(240,199,94,0.8)" : "rgba(149,117,205,0.8)";
      ctx.beginPath(); ctx.moveTo(x(t), pad); ctx.lineTo(x(t), h - pad); ctx.stroke();
    }
  }

  // ── metrics ───────────────────────────────────────────────────────────
  function renderMetrics(m) {
    const chips = [
      ["order R", m.R.toFixed(4), m.R * 100],
      ["ξ density", m.xi.toFixed(4), m.xi * 100],
      ["entropy", m.entropy.toFixed(4), m.entropy * 100],
      ["coupling K", m.coupling.toFixed(3), (m.coupling / 4) * 100],
      ["oscillators", String(m.nodes), (m.nodes / 96) * 100],
      ["band", m.state, null],
    ];
    metricsBox.innerHTML = "";
    for (const [k, v, pct] of chips) {
      const el = document.createElement("div");
      el.className = "em-metric";
      const spark = pct === null ? "" : `<div class="spark"><i style="width:${clamp(pct, 0, 100).toFixed(1)}%"></i></div>`;
      el.innerHTML = `<div class="k">${k}</div><div class="v${pct === null ? " small" : ""}">${v}</div>${spark}`;
      metricsBox.appendChild(el);
    }
  }

  function renderEvents(items) {
    eventsEl.innerHTML = "";
    for (const ev of items) {
      const div = document.createElement("div");
      const isEmergence = ev.kind === "emergence";
      div.className = "em-event " + (isEmergence ? (ev.operator || "") : "");
      const glyph = isEmergence ? (GLYPHS[ev.operator] || "⊚") : (GLYPHS[ev.operator] || "Ξ");
      const label = isEmergence
        ? (ev.data?.message || ev.operator)
        : `${ev.operator} ← ${ev.actor}`;
      div.innerHTML = `<span class="g">${glyph}</span><strong>${escapeHtml(label)}</strong>
        <span class="meta">#${ev.sequence} · R ${(ev.metrics?.R ?? 0).toFixed(4)} · ${escapeHtml(ev.event_id.slice(0, 8))} · ${escapeHtml(ev.event_hash.slice(0, 12))}</span>`;
      eventsEl.appendChild(div);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ── data ──────────────────────────────────────────────────────────────
  async function load() {
    try {
      const r = await fetch(`${API}/state`);
      if (!r.ok) throw new Error(`field unavailable (${r.status})`);
      const s = await r.json();
      view.latest = s;
      view.targetTheta = s.theta;
      view.local = s.local;
      view.history = s.history || [];
      view.events = s.events || [];
      if (view.shownTheta.length !== s.theta.length) view.shownTheta = s.theta.slice();
      renderMetrics(s);
      renderEvents(view.events);
      const chain = s.integrity || {};
      statusEl.textContent = `local SQLite · ${chain.entries ?? 0} receipts · chain ${chain.ok ? "verified" : "INVALID"} · t=${s.t.toFixed(1)} · ${s.execution_class}`;
      statusEl.style.color = chain.ok ? "" : "var(--violet)";
      if (!view.topology || view.nodeCount !== s.nodes) {
        view.nodeCount = s.nodes;
        const t = await fetch(`${API}/topology`).then((x) => x.json());
        view.topology = t;
      }
    } catch (e) {
      statusEl.textContent = `field unreachable · ${e.message}`;
    }
  }

  async function act(operator, parameters = {}) {
    if (view.busy) return;
    view.busy = true;
    actionsBox.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      const r = await fetch(`${API}/operators`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operator, parameters, actor_id: "hunter",
          idempotency_key: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now() + Math.random()),
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "operator rejected");
      toast(`${GLYPHS[operator] || "Ξ"} ${operator} committed · R ${data.receipt.metrics.R.toFixed(4)}`);
      await load();
    } catch (e) {
      toast(`Ξ ${e.message}`);
    } finally {
      view.busy = false;
      actionsBox.querySelectorAll("button").forEach((b) => (b.disabled = false));
    }
  }

  function buildActions() {
    actionsBox.innerHTML = "";
    for (const [op, label] of OPERATORS) {
      const b = document.createElement("button");
      b.innerHTML = `<span class="g">${GLYPHS[op]}</span>${label}`;
      b.addEventListener("click", () => {
        const n = view.latest ? view.latest.nodes : 57;
        const params = op === "entrain"
          ? { a: Math.floor(Math.random() * n), b: Math.floor(Math.random() * n) }
          : op === "seed" ? { count: 1 } : op === "witness" ? { seed: Math.floor(Math.random() * 1e6) } : {};
        act(op, params);
      });
      actionsBox.appendChild(b);
    }
  }

  disc.addEventListener("click", (event) => {
    if (!view.latest) return;
    const rect = disc.getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 2;
    const angle = Math.atan2(event.clientY - rect.top - cy, event.clientX - rect.left - cx);
    let best = 0, bestD = Infinity;
    view.targetTheta.forEach((theta, i) => {
      const d = Math.abs(shortAngle(theta, angle));
      if (d < bestD) { bestD = d; best = i; }
    });
    act("perturb", { node: best, strength: 0.8 });
  });

  // ── animation ─────────────────────────────────────────────────────────
  let lastFrame = 0;
  function frame(now) {
    requestAnimationFrame(frame);
    if (document.hidden) return;
    if (now - lastFrame < 33) return;
    lastFrame = now;
    let moving = false;
    for (let i = 0; i < view.shownTheta.length; i++) {
      const target = view.targetTheta[i];
      if (target === undefined) continue;
      const d = shortAngle(target, view.shownTheta[i]);
      if (Math.abs(d) > 0.002) { view.shownTheta[i] += d * 0.18; moving = true; }
      else view.shownTheta[i] = target;
    }
    drawDisc();
    if (!moving) drawOrder();
  }

  buildActions();
  load().then(() => { drawOrder(); drawDisc(); });
  requestAnimationFrame(frame);
  setInterval(load, 900);
  setInterval(drawOrder, 900);
  window.addEventListener("resize", () => { drawDisc(); drawOrder(); });
})();
