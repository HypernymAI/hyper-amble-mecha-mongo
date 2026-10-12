// Presents mind — what Amble remembers about this link, live from MongoDB Atlas.
//
// Rendered only when the hello says this link may chat. The socket is the one
// intake.js opened (passed in as `intake`); every request is
// {type: 'presents_mind', k} or {type: 'presents_dream', k} and the server
// derives the scope from the link, so a visitor only ever sees their own
// link's memories. The server answers one message at a time per socket, so
// at most one mind request is in flight and replies arrive in order. Polls
// every POLL_MS while the panel is open and the tab visible, and once right
// after each chat reply. All text goes in through textContent.

export const POLL_MS = 4000;
const SVG = 'http://www.w3.org/2000/svg';

export function sparkPoints(scores, width, height, pad = 4) {
  const n = scores.length;
  if (!n) return [];
  const step = n > 1 ? (width - pad * 2) / (n - 1) : 0;
  return scores.map((s, i) => {
    const v = Math.max(0, Math.min(10, Number(s.score) || 0));
    return [+(pad + (n > 1 ? i * step : (width - pad * 2) / 2)).toFixed(1), +(height - pad - (v / 10) * (height - pad * 2)).toFixed(1)];
  });
}

export function when(iso, now = Date.now()) {
  const t = Date.parse(iso || '');
  if (Number.isNaN(t)) return '';
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 45) return 'just now';
  if (s < 3600) return Math.round(s / 60) + 'm ago';
  if (s < 86400) return Math.round(s / 3600) + 'h ago';
  return new Date(t).toLocaleDateString(undefined, {month: 'short', day: 'numeric'});
}

const fmt = v => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(1) : '–');

export function mountMind({document, intake, setTimeoutImpl = globalThis.setTimeout, clearTimeoutImpl = globalThis.clearTimeout}) {
  if (!intake) return null;
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const state = {disposed: false, open: false, built: false, inflight: false, timer: 0, seen: null, last: '', nodes: null, failures: 0};

  function build() {
    const panel = el('aside', 'mind-panel'); panel.id = 'mind-panel'; panel.hidden = true; panel.setAttribute('aria-label', 'Amble’s mind');
    const head = el('header', 'mind-head');
    const titles = el('div', 'mind-titles');
    titles.append(el('h2', 'mind-title', 'Amble’s mind'), el('p', 'mind-sub', 'stored in MongoDB Atlas'));
    const close = el('button', 'mind-close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Close Amble’s mind');
    head.append(titles, close);
    const stats = el('dl', 'mind-stats');
    const statNodes = {};
    for (const key of ['turns', 'memories', 'lessons', 'dreams']) {
      const box = el('div', 'mind-stat'); const v = el('dd', null, '0'); box.append(v, el('dt', null, key)); stats.append(box); statNodes[key] = v;
    }
    const dreaming = el('p', 'mind-dreaming'); dreaming.hidden = true;
    dreaming.append(el('span', 'mind-orb'), el('span', null, 'Dreaming… turning this visit into memories and lessons'));
    const offline = el('p', 'mind-offline', 'Memory is offline right now.'); offline.hidden = true;
    const body = el('div', 'mind-body');
    const section = (title, hint) => { const s = el('section', 'mind-section'); const h = el('h3', null, title); if (hint) h.append(el('span', 'mind-hint', hint)); s.append(h); body.append(s); return s; };
    const improve = section('Self-improvement', 'reply scores 0–10');
    const spark = document.createElementNS(SVG, 'svg'); spark.setAttribute('class', 'mind-spark'); spark.setAttribute('viewBox', '0 0 260 56'); spark.setAttribute('role', 'img');
    const delta = el('p', 'mind-delta'); const critique = el('p', 'mind-critique');
    improve.append(spark, delta, critique);
    const less = section('Lessons Amble wrote itself'); const lessList = el('ul', 'mind-list mind-lessons'); less.append(lessList);
    const mems = section('Memories'); const memList = el('ul', 'mind-list mind-memories'); mems.append(memList);
    const drs = section('Dreams'); const dreamList = el('ul', 'mind-list mind-dreams'); drs.append(dreamList);
    const foot = el('footer', 'mind-foot');
    const dream = el('button', 'mind-dream', 'Dream now'); dream.type = 'button';
    const status = el('span', 'mind-status'); status.setAttribute('role', 'status');
    foot.append(dream, status);
    const live = el('p', 'visually-hidden'); live.setAttribute('aria-live', 'polite');
    panel.append(head, stats, dreaming, offline, body, foot, live);
    document.body.append(panel);

    const toggle = el('button', 'mind-toggle'); toggle.type = 'button'; toggle.id = 'mind-toggle';
    toggle.setAttribute('aria-controls', 'mind-panel'); toggle.setAttribute('aria-expanded', 'false');
    toggle.append(el('span', 'mind-toggle-dot'), el('span', 'mind-toggle-label', 'Mind'));
    toggle.setAttribute('aria-label', 'Amble’s mind');
    const actions = document.querySelector('.studio-actions');
    if (actions) actions.prepend(toggle); else document.body.append(toggle);

    toggle.addEventListener('click', () => { const next = !state.open; state.userClosed = !next; setOpen(next); });
    close.addEventListener('click', () => { state.userClosed = true; setOpen(false); try { toggle.focus(); } catch (_) {} });
    dream.addEventListener('click', dreamNow);
    state.nodes = {panel, toggle, statNodes, dreaming, offline, spark, delta, critique, memList, lessList, dreamList, dream, status, live};
    state.built = true;
  }

  function render(mind) {
    const n = state.nodes;
    const key = JSON.stringify(mind);
    if (key === state.last) return;
    state.last = key;
    const enabled = mind.enabled !== false;
    n.offline.hidden = enabled;
    const stats = mind.stats || {};
    for (const k in n.statNodes) n.statNodes[k].textContent = String(Number(stats[k]) || 0);
    n.dreaming.hidden = !mind.dreaming;
    n.panel.classList.toggle('is-dreaming', !!mind.dreaming);
    n.toggle.classList.toggle('is-dreaming', !!mind.dreaming);
    n.dream.disabled = !enabled || !!mind.dreaming;

    // Memories: highlight ids not seen on the previous render (never on the first).
    const memories = Array.isArray(mind.memories) ? mind.memories : [];
    const fresh = [];
    n.memList.replaceChildren(...memories.map(m => {
      const li = el('li', 'mind-item');
      const meta = el('div', 'mind-meta');
      const kind = el('span', 'mind-kind', m.kind || 'fact'); kind.dataset.kind = m.kind || 'fact';
      meta.append(kind, el('time', 'mind-when', when(m.when)));
      if (m.origin && m.origin !== 'dream') meta.append(el('span', 'mind-origin', m.origin));
      li.append(meta, el('p', 'mind-text', m.text || ''));
      if (state.seen && !state.seen.has(m.id)) { li.classList.add('is-fresh'); fresh.push(m.text || ''); }
      return li;
    }));
    if (!memories.length) n.memList.append(el('li', 'mind-empty', 'Nothing yet. Chat a little and Amble will remember.'));
    state.seen = new Set(memories.map(m => m.id));
    if (fresh.length) n.live.textContent = (fresh.length === 1 ? 'New memory: ' : `${fresh.length} new memories: `) + fresh.join('; ');

    const lessons = Array.isArray(mind.lessons) ? mind.lessons : [];
    n.lessList.replaceChildren(...lessons.map(l => {
      const li = el('li', 'mind-item mind-lesson' + (l.active === false ? ' is-retired' : ''));
      const meta = el('div', 'mind-meta');
      meta.append(el('span', 'mind-kind', l.active === false ? 'retired' : 'active'), el('time', 'mind-when', when(l.when)));
      meta.firstChild.dataset.kind = l.active === false ? 'retired' : 'active';
      li.append(meta, el('p', 'mind-text', l.text || ''));
      return li;
    }));
    if (!lessons.length) n.lessList.append(el('li', 'mind-empty', 'No lessons yet. Amble writes them while it dreams.'));

    const dreams = Array.isArray(mind.dreams) ? mind.dreams : [];
    n.dreamList.replaceChildren(...dreams.map(d => {
      const li = el('li', 'mind-dream-row');
      li.append(el('time', 'mind-when', when(d.when)),
        el('span', null, `${Number(d.turns) || 0} turns → ${Number(d.memories) || 0} memories · ${Number(d.lessons) || 0} lessons` + (Number(d.retired) ? ` · ${Number(d.retired)} retired` : '')));
      return li;
    }));
    if (!dreams.length) n.dreamList.append(el('li', 'mind-empty', 'No dreams yet.'));

    renderScores(Array.isArray(mind.scores) ? mind.scores : [], mind.improvement || {});
  }

  function renderScores(scores, imp) {
    const n = state.nodes, W = 260, H = 56;
    const nodes = [];
    for (const y of [10, 5, 0]) {
      const line = document.createElementNS(SVG, 'line');
      const yy = (H - 4 - (y / 10) * (H - 8)).toFixed(1);
      line.setAttribute('x1', '0'); line.setAttribute('x2', String(W)); line.setAttribute('y1', yy); line.setAttribute('y2', yy);
      line.setAttribute('class', 'mind-grid'); nodes.push(line);
    }
    const pts = sparkPoints(scores, W, H);
    if (pts.length > 1) {
      const path = document.createElementNS(SVG, 'polyline');
      path.setAttribute('points', pts.map(p => p.join(',')).join(' ')); path.setAttribute('class', 'mind-line'); nodes.push(path);
    }
    pts.forEach((p, i) => {
      const c = document.createElementNS(SVG, 'circle');
      c.setAttribute('cx', String(p[0])); c.setAttribute('cy', String(p[1])); c.setAttribute('r', i === pts.length - 1 ? '3.2' : '2.2');
      c.setAttribute('class', 'mind-dot' + (i === pts.length - 1 ? ' is-last' : ''));
      const t = document.createElementNS(SVG, 'title'); t.textContent = `${Number(scores[i].score) || 0}/10 — ${scores[i].critique || ''}`; c.append(t);
      nodes.push(c);
    });
    n.spark.replaceChildren(...nodes);
    n.spark.setAttribute('aria-label', scores.length ? `Reply scores: ${scores.map(s => Number(s.score) || 0).join(', ')}` : 'No reply scores yet');
    n.delta.replaceChildren();
    if (imp.before_avg != null || imp.after_avg != null) {
      const up = imp.before_avg != null && imp.after_avg != null ? imp.after_avg - imp.before_avg : null;
      n.delta.append(el('span', 'mind-avg', `avg before lessons ${fmt(imp.before_avg)}`), el('span', 'mind-arrow', ' → '),
        el('span', 'mind-avg is-after', `with lessons ${fmt(imp.after_avg)}`));
      if (up != null) { const b = el('span', 'mind-up' + (up < 0 ? ' is-down' : ''), (up >= 0 ? '+' : '') + up.toFixed(1)); n.delta.append(' ', b); }
    } else n.delta.textContent = scores.length ? `${scores.length} replies scored · lessons not yet in play` : 'Each reply is scored by a judge; lessons should lift the line.';
    const lastCrit = scores.length ? scores[scores.length - 1].critique : '';
    n.critique.textContent = lastCrit ? '“' + lastCrit + '”' : '';
    n.critique.hidden = !lastCrit;
  }

  async function refresh() {
    if (state.disposed || state.inflight || !state.built) return;
    state.inflight = true;
    let reply = null;
    try { reply = await intake.send('presents_mind', {}, 'presents_mind_reply'); } catch (_) { reply = null; }
    state.inflight = false;
    if (state.disposed) return;
    if (reply?.ok && reply.mind && typeof reply.mind === 'object') { state.failures = 0; render(reply.mind); }
    else if (reply && reply.ok === false && ['link', 'origin', 'type'].includes(reply.error)) { stopPolling(); state.nodes.status.textContent = 'Not available on this link.'; state.dead = true; }
    else state.failures++;
  }

  function schedule() {
    clearTimeoutImpl(state.timer); state.timer = 0;
    if (state.disposed || state.dead || !state.open || document.hidden) return;
    state.timer = setTimeoutImpl(async () => { await refresh(); schedule(); }, state.failures > 2 ? POLL_MS * 3 : POLL_MS);
  }
  function stopPolling() { clearTimeoutImpl(state.timer); state.timer = 0; }

  async function dreamNow() {
    const {dream, status} = state.nodes;
    dream.disabled = true; status.textContent = 'Asking Amble to dream…';
    let reply = null;
    try { reply = await intake.send('presents_dream', {}, 'presents_mind_reply'); } catch (_) {}
    if (state.disposed) return;
    status.textContent = reply?.ok ? (reply.started ? 'Dreaming started.' : 'Already dreaming, or nothing new to dream about.') : 'Amble could not dream right now.';
    state.last = '';
    await refresh();
    if (!state.nodes.dreaming.hidden) dream.disabled = true; else dream.disabled = false;
    setTimeoutImpl(() => { if (!state.disposed) status.textContent = ''; }, 6000);
  }

  function setOpen(open) {
    if (!state.built || (state.dead && open)) return;
    state.open = !!open;
    state.nodes.panel.hidden = !state.open;
    state.nodes.toggle.setAttribute('aria-expanded', String(state.open));
    document.body.classList.toggle('mind-open', state.open);
    if (state.open) { refresh().then(schedule); } else stopPolling();
  }

  const onVisibility = () => { if (document.hidden) stopPolling(); else if (state.open) refresh().then(schedule); };
  document.addEventListener('visibilitychange', onVisibility);
  // A chat reply carries `reply`; refresh right after it so new turns show.
  const offReply = intake.on('presents_reply', message => {
    if (state.open && message && typeof message.reply === 'string') setTimeoutImpl(() => refresh(), 50);
  });

  const hello = intake.hello().then(reply => {
    if (state.disposed || !reply?.ok || reply.chat !== true) return;
    build();
    if (state.pendingView) api.view(state.pendingView);
  }).catch(() => {});

  const api = {
    ready: hello,
    open: () => state.open,
    setOpen,
    refresh,
    // Opens itself alongside the chat in the theatre on wide screens.
    view(name) {
      if (!state.built) { state.pendingView = name; return; }
      const wide = !(globalThis.matchMedia?.('(max-width:900px)').matches);
      if (name === 'theatre' && wide && !state.userClosed) setOpen(true);
    },
    dispose() {
      state.disposed = true; stopPolling();
      document.removeEventListener('visibilitychange', onVisibility);
      try { offReply?.(); } catch (_) {}
    },
  };
  return api;
}
