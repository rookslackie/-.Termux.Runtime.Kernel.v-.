/* Field Core — a living sigil for The Sanctuary.
   Draws the real local field (/api/state, /api/quantum-field) as an animated
   core and lets a tap invoke a lawful ⟐ operator on the glyph-chip runtime. */
(() => {
  const canvas = document.getElementById('field-core');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const captionState = document.getElementById('fc-state');
  const captionEvents = document.getElementById('fc-events');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const GLYPHS = ['⊚', '∴', 'Ξ', '⟐', '∞', 'Ψ', '⋈', 'Ω', '⧂', '↺'];
  const SIGILS = ['⊚', '∴', 'Ξ'];
  const ACCENTS = { coherent: '#f0c75e', emerging: '#7fe3d0', threshold: '#b39ddb' };

  const field = {
    coherence: 0.89, kuramoto: 0.8, xi: 0.8, heartbeats: 0,
    state: 'coherent', events: 1, capsules: 3, integrity: true,
  };

  const ripples = [];
  let width = 0, height = 0, dpr = 1, lastBeat = 0, lastEvents = -1;
  let kickAt = -1e9, invokeLock = 0;

  const accent = () => (field.integrity === false ? '#e8877f' : (ACCENTS[field.state] || ACCENTS.coherent));

  function withAlpha(hex, alpha) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    dpr = Math.min(2, window.devicePixelRatio || 1);
    width = rect.width;
    height = rect.height;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw(performance.now());
  }

  function spawnRipple(x, y, maxRadius) {
    ripples.push({ x, y, max: maxRadius, t0: performance.now() });
    if (reduceMotion) draw(performance.now());
  }

  function draw(now) {
    if (!width || !height) return;
    const cx = width / 2, cy = height / 2;
    const unit = Math.min(width, height);
    const coreR = Math.max(22, unit * 0.155);
    const orbit = unit * 0.30;
    const rim = unit * 0.40;
    const color = accent();
    const t = reduceMotion ? 8000 : now;
    const calm = 0.55 + 0.45 * field.kuramoto;

    ctx.clearRect(0, 0, width, height);

    // Haze: the body of the field.
    const haze = ctx.createRadialGradient(cx, cy, coreR * 0.4, cx, cy, rim * 1.35);
    haze.addColorStop(0, withAlpha(color, 0.16 * calm));
    haze.addColorStop(0.45, withAlpha(color, 0.05 * calm));
    haze.addColorStop(1, 'rgba(10,10,18,0)');
    ctx.fillStyle = haze;
    ctx.fillRect(0, 0, width, height);

    // Resonance rim: coherence lights the ticks.
    const ticks = 36;
    const lit = Math.round(ticks * Math.max(0, Math.min(1, field.coherence)));
    ctx.lineCap = 'round';
    for (let i = 0; i < ticks; i++) {
      const angle = (i / ticks) * Math.PI * 2 - Math.PI / 2;
      const on = i < lit;
      const inner = rim + 4;
      const outer = rim + (on ? 14 : 8);
      ctx.strokeStyle = on ? withAlpha(color, 0.7) : 'rgba(224,220,200,0.12)';
      ctx.lineWidth = on ? 1.8 : 1;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
      ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
      ctx.stroke();
    }

    // Counter-rotating rings.
    for (let ring = 0; ring < 3; ring++) {
      const radius = coreR * (1.45 + ring * 0.62);
      const direction = ring % 2 === 0 ? 1 : -1;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate((t / 1000) * (0.07 + ring * 0.035) * direction);
      ctx.setLineDash(ring === 1 ? [2, 10] : [6, 12]);
      ctx.strokeStyle = withAlpha(ring === 1 ? '#9575cd' : color, (0.30 - ring * 0.05) * (0.5 + 0.5 * calm));
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    ctx.setLineDash([]);

    // Orbiting glyph witnesses — one more every two sealed events.
    const count = Math.max(3, Math.min(9, 3 + Math.floor(field.events / 2)));
    const spread = 0.92 + 0.08 * Math.max(0, Math.min(1, field.xi));
    ctx.font = `${Math.max(12, unit * 0.058)}px Georgia, serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < count; i++) {
      const base = (i / count) * Math.PI * 2;
      const drift = (t / 1000) * (0.05 + (i % 3) * 0.02) * (i % 2 ? -1 : 1);
      const angle = base + drift;
      const radius = orbit * spread * (0.94 + 0.06 * Math.sin(t / 2400 + i));
      const x = cx + Math.cos(angle) * radius;
      const y = cy + Math.sin(angle) * radius;
      ctx.strokeStyle = withAlpha(color, 0.07);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * coreR * 1.1, cy + Math.sin(angle) * coreR * 1.1);
      ctx.lineTo(x, y);
      ctx.stroke();
      ctx.strokeStyle = withAlpha(color, 0.28);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, 3.4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = withAlpha(color, 0.8);
      ctx.beginPath();
      ctx.arc(x, y, 1.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = withAlpha(color, 0.8);
      ctx.fillText(GLYPHS[i % GLYPHS.length], x, y - unit * 0.052);
    }

    // Core: breathes with the heartbeat, cycles the seal.
    const beat = Math.max(0, 1 - (now - kickAt) / 620);
    const breath = 1 + (reduceMotion ? 0 : 0.05 * Math.sin(t / 1100)) + 0.16 * beat;
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 1.5 * breath);
    glow.addColorStop(0, withAlpha(color, 0.85));
    glow.addColorStop(0.35, withAlpha(color, 0.22));
    glow.addColorStop(1, withAlpha(color, 0));
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, coreR * 1.5 * breath, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = withAlpha(color, 0.7);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(cx, cy, coreR * 0.82 * breath, 0, Math.PI * 2);
    ctx.stroke();

    const sigil = reduceMotion ? 'Ξ' : SIGILS[Math.floor(t / 2600) % SIGILS.length];
    ctx.font = `${Math.round(coreR * 0.95 * breath)}px Georgia, serif`;
    ctx.fillStyle = withAlpha(color, 0.95);
    ctx.shadowColor = withAlpha(color, 0.8);
    ctx.shadowBlur = 18 * breath + 10;
    ctx.fillText(sigil, cx, cy + coreR * 0.04);
    ctx.shadowBlur = 0;

    // Ripples from taps and heartbeats.
    for (let i = ripples.length - 1; i >= 0; i--) {
      const rip = ripples[i];
      const age = now - rip.t0;
      if (age > 1500) { ripples.splice(i, 1); continue; }
      const radius = rip.max * (1 - Math.exp(-age / 380));
      const alpha = Math.max(0, 1 - age / 1500);
      ctx.strokeStyle = withAlpha(color, 0.45 * alpha);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(rip.x, rip.y, radius, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function loop(now) {
    draw(now);
    requestAnimationFrame(loop);
  }

  function update(patch) {
    Object.assign(field, patch);
    if (typeof patch.heartbeats === 'number' && patch.heartbeats > lastBeat) {
      lastBeat = patch.heartbeats;
      kickAt = performance.now();
      spawnRipple(width / 2, height / 2, Math.min(width, height) * 0.34);
    }
    if (typeof patch.events === 'number' && lastEvents >= 0 && patch.events > lastEvents) {
      kickAt = performance.now();
    }
    if (typeof patch.events === 'number') lastEvents = patch.events;
    if (captionState) captionState.textContent = field.state;
    if (captionEvents) captionEvents.textContent = String(field.events);
    if (reduceMotion) draw(performance.now());
  }

  // A tap invokes a real ⟐ operator; the ripple always answers immediately.
  function invoke() {
    const now = performance.now();
    if (now - invokeLock < 1200) return;
    invokeLock = now;
    if (typeof window.runFieldOperator === 'function') {
      window.runFieldOperator('hadamard', { qubit: 0 });
    }
  }

  canvas.addEventListener('click', (event) => {
    const rect = canvas.getBoundingClientRect();
    spawnRipple(event.clientX - rect.left, event.clientY - rect.top, Math.min(width, height) * 0.42);
    invoke();
  });
  canvas.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      spawnRipple(width / 2, height / 2, Math.min(width, height) * 0.42);
      invoke();
    }
  });

  window.fieldCore = { update, pulse: () => { kickAt = performance.now(); } };

  new ResizeObserver(resize).observe(canvas);
  resize();
  if (!reduceMotion) requestAnimationFrame(loop);
})();
