// SO-101 conveyor lab: replays recorded MuJoCo episodes exported by autolab/scripts/export_conveyor_replay.py.
// Robot: official SO-101 URDF + meshes via urdf-loader. Nothing here simulates physics.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import URDFLoader from './vendor/urdf-loader/URDFLoader.js';

const $ = (id) => document.getElementById(id);
const stage = $('stage');
const qMJ = (q) => new THREE.Quaternion(q[1], q[2], q[3], q[0]); // MuJoCo (w,x,y,z) -> three (x,y,z,w)
const fmt$ = (v) => (v < 0 ? '−$' : '$') + Math.abs(v).toFixed(2);

// ---------------------------------------------------------------- renderers / scene
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(2, devicePixelRatio));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
stage.prepend(renderer.domElement);
const camRenderer = new THREE.WebGLRenderer({ canvas: $('cam-3d'), antialias: true });
camRenderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = null;
const world = new THREE.Group();
world.rotation.x = -Math.PI / 2; // MuJoCo z-up -> three y-up
scene.add(world);
scene.add(new THREE.HemisphereLight(0xdfe9f2, 0x1a2430, 1.5));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(0.5, 1.2, 0.4);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
Object.assign(sun.shadow.camera, { left: -0.5, right: 0.5, top: 0.5, bottom: -0.5, near: 0.1, far: 3 });
scene.add(sun);

const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 10);
camera.position.set(0.78, 0.46, -0.30); // front-right of the cell, high enough to see the whole arm
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0.13, 0.08, -0.02);
controls.enableDamping = true;
controls.minDistance = 0.25;
controls.maxDistance = 2.0;

function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(1, h);
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(stage);

// ---------------------------------------------------------------- build the cell from scene.json
const mat = (rgba, extra = {}) => new THREE.MeshStandardMaterial({ color: new THREE.Color(rgba[0], rgba[1], rgba[2]), transparent: rgba[3] < 1, opacity: rgba[3], roughness: 0.7, ...extra });
let rollers = [], objects = new Map(), robot = null, beltCam = null;

function stripeTexture() {
  const c = document.createElement('canvas'); c.width = 64; c.height = 4;
  const g = c.getContext('2d'); g.fillStyle = '#9aa3ad'; g.fillRect(0, 0, 64, 4); g.fillStyle = '#4d555e'; g.fillRect(0, 0, 10, 4);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function geomMesh(g) {
  let geo;
  if (g.type === 'box') geo = new THREE.BoxGeometry(2 * g.size[0], 2 * g.size[1], 2 * g.size[2]);
  else if (g.type === 'cylinder' || g.type === 'capsule') { geo = new THREE.CylinderGeometry(g.size[0], g.size[0], 2 * g.size[1], 24); geo.rotateX(Math.PI / 2); }
  else return null;
  const m = new THREE.Mesh(geo, mat(g.rgba));
  m.position.set(...g.pos);
  m.quaternion.copy(qMJ(g.quat));
  m.castShadow = m.receiveShadow = true;
  return m;
}

function buildScene(sc) {
  const table = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.6), new THREE.MeshStandardMaterial({ color: 0x1d2a38, roughness: 0.95 }));
  table.position.set(0.15, 0, 0); table.receiveShadow = true; world.add(table);
  for (const g of sc.static) { const m = geomMesh(g); if (m) world.add(m); }
  const tex = stripeTexture();
  for (const r of sc.rollers) {
    const pivot = new THREE.Group(); pivot.position.set(...r.pos);
    const geo = new THREE.CylinderGeometry(r.radius, r.radius, 2 * r.half_len, 20); geo.rotateZ(Math.PI / 2);
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.5, metalness: 0.3 }));
    m.castShadow = m.receiveShadow = true; pivot.add(m); world.add(pivot); rollers.push(pivot);
  }
  const bc = sc.belt_cam;
  beltCam = new THREE.PerspectiveCamera(bc.fovy, bc.width / bc.height, 0.01, 3);
  beltCam.position.set(...bc.pos); beltCam.quaternion.copy(qMJ(bc.quat)); world.add(beltCam);
}

function loadRobot(sc) {
  return new Promise((resolve, reject) => {
    const loader = new URDFLoader();
    loader.load('./' + sc.robot.urdf, (r) => {
      r.traverse((c) => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
      world.add(r); robot = r; resolve(r);
    }, undefined, reject);
  });
}

// ---------------------------------------------------------------- playback
let ep = null, sc = null, playing = true, speed = 1, t = 0, lastNow = performance.now(), visible = true, raf = 0, ledgerShown = 0, ready = false;

function frameAt(time) {
  const f = ep.frames, i = Math.max(0, Math.min(f.length - 1, Math.floor(time * ep.fps)));
  const j = Math.min(f.length - 1, i + 1);
  const a = Math.min(1, Math.max(0, time * ep.fps - i));
  return [f[i], f[j], a];
}

function apply(time) {
  const [A, B, a] = frameAt(time);
  sc.robot.joints.forEach((name, k) => { if (robot && robot.joints[name]) robot.setJointValue(name, A.q[k] + (B.q[k] - A.q[k]) * a); });
  const rAng = A.r + (B.r - A.r) * a;
  for (const p of rollers) p.rotation.x = rAng;
  const nextById = new Map(B.o.map((o) => [o[0], o]));
  const seen = new Set();
  for (const o of A.o) {
    const m = objects.get(o[0]); if (!m) continue;
    const n = nextById.get(o[0]);
    const lerpOK = n && Math.hypot(n[1] - o[1], n[2] - o[2], n[3] - o[3]) < 0.05; // no interpolation across respawns
    m.position.set(o[1], o[2], o[3]);
    const q = qMJ([o[4], o[5], o[6], o[7]]);
    if (lerpOK) { m.position.lerp(new THREE.Vector3(n[1], n[2], n[3]), a); q.slerp(qMJ([n[4], n[5], n[6], n[7]]), a); }
    m.quaternion.copy(q); m.visible = true; seen.add(o[0]);
  }
  for (const [id, m] of objects) if (!seen.has(id)) m.visible = false;
  // HUD
  $('money').textContent = fmt$(A.m);
  const led = ep.ledger.filter((e) => e.t <= time);
  const c = (o, k) => led.filter((e) => e.outcome === o && e.kind === k).length;
  $('counts').innerHTML = `red in bin <b>${c('bin', 'red_square')}</b> · blue in bin <b>${c('bin', 'blue_circle')}</b> · red missed <b>${c('end', 'red_square')}</b> · blue passed <b>${c('end', 'blue_circle')}</b>`;
  const bs = $('belt-state'); bs.textContent = A.b ? 'belt RUNNING' : 'belt STOPPED · picking'; bs.className = A.b ? '' : 'stopped';
  $('time').textContent = time.toFixed(1) + ' s';
  $('scrub').value = String(Math.round(time * ep.fps));
  document.querySelectorAll('#ledger li').forEach((li) => li.classList.toggle('on', Number(li.dataset.t) <= time));
  if (led.length > ledgerShown) { for (const e of led.slice(ledgerShown)) flash(e); }
  ledgerShown = led.length;
  drawOverlay(time, A.tgt);
}

function flash(e) {
  const d = document.createElement('div');
  d.className = 'f ' + (e.amount > 0 ? 'pos' : e.amount < 0 ? 'neg' : 'zero');
  d.textContent = `${e.amount >= 0 ? '+' : '−'}$${Math.abs(e.amount).toFixed(2)}  ${e.kind.replace('_', ' ')} → ${e.outcome}`;
  $('flashes').append(d); setTimeout(() => d.remove(), 1900);
}

function lookAt(time) {
  const L = ep.looks; let lo = 0, hi = L.length - 1, best = null;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (L[mid].t <= time) { best = L[mid]; lo = mid + 1; } else hi = mid - 1; }
  return best;
}

function drawOverlay(time, tgt) {
  const cv = $('cam-overlay'), g = cv.getContext('2d');
  g.clearRect(0, 0, cv.width, cv.height);
  const look = lookAt(time);
  if (!look || time - look.t > 0.5) return; // detections are only shown while they are current
  g.lineWidth = 1.5; g.font = '600 10px ui-monospace, Menlo, monospace';
  for (const [kind, u, v, area, x, y] of look.d) {
    const col = kind === 'red_square' ? '#ff6b6b' : kind === 'blue_circle' ? '#6fa8ff' : '#ffe066';
    const r = Math.max(6, Math.sqrt(area) * 0.75);
    g.strokeStyle = col; g.fillStyle = col;
    g.strokeRect(u - r, v - r, 2 * r, 2 * r);
    g.fillText(kind === 'red_square' ? 'SQ' : kind === 'blue_circle' ? 'CI' : '?', u - r, v - r - 3);
    if (tgt && Math.hypot(tgt[0] - x, tgt[1] - y) < 0.01) { g.fillStyle = '#fff'; g.beginPath(); g.arc(u, v, 3, 0, 7); g.fill(); }
  }
}

function loop(now) {
  raf = requestAnimationFrame(loop);
  if (!ep || !sc) return;
  const dt = Math.min(0.1, (now - lastNow) / 1000); lastNow = now;
  if (playing) { t += dt * speed; if (t >= ep.seconds) { t = 0; ledgerShown = 0; } }
  apply(t);
  controls.update();
  renderer.render(scene, camera);
  camRenderer.render(scene, beltCam);
}

function setRunning(on) {
  if (!ready) return; // the town can report visibility before the recorded run has loaded
  if (on && !raf) { lastNow = performance.now(); raf = requestAnimationFrame(loop); }
  if (!on && raf) { cancelAnimationFrame(raf); raf = 0; }
}

// Pause when the town hides the lab frame (presents:visibility) or the tab is in the background.
window.addEventListener('message', (e) => {
  if (e.source !== window.parent || e.origin !== location.origin || !e.data || e.data.type !== 'presents:visibility') return;
  visible = !!e.data.visible; setRunning(visible && !document.hidden);
});
document.addEventListener('visibilitychange', () => setRunning(visible && !document.hidden));

$('back').addEventListener('click', () => {
  if (window.parent !== window) window.parent.postMessage({ type: 'presents:leave-terminal' }, location.origin);
  else location.href = '/hypernym/presents/#now';
});
$('play').addEventListener('click', () => { playing = !playing; $('play').textContent = playing ? '❚❚' : '▶'; $('play').setAttribute('aria-label', playing ? 'Pause' : 'Play'); });
$('scrub').addEventListener('input', (e) => { t = Number(e.target.value) / ep.fps; ledgerShown = ep.ledger.filter((x) => x.t <= t).length; });
$('speed').addEventListener('change', (e) => { speed = Number(e.target.value); });

function buildObjects(list) {
  // Item kinds come from each episode's seed, so the pool is rebuilt per episode.
  for (const m of objects.values()) { world.remove(m); m.geometry.dispose(); m.material.dispose(); }
  objects = new Map();
  for (const o of list) {
    let geo;
    if (o.type === 'box') geo = new THREE.BoxGeometry(2 * o.size[0], 2 * o.size[1], 2 * o.size[2]);
    else { geo = new THREE.CylinderGeometry(o.size[0], o.size[0], 2 * o.size[1], 28); geo.rotateX(Math.PI / 2); }
    const m = new THREE.Mesh(geo, mat(o.rgba, { roughness: 0.45 })); m.visible = false; m.castShadow = true; world.add(m); objects.set(o.id, m);
  }
}

async function loadEpisode(file) {
  const next = await (await fetch('./' + file)).json();
  buildObjects(next.objects);
  ep = next;
  t = 0; ledgerShown = 0;
  $('scrub').max = String(ep.frames.length - 1);
  $('badge').textContent = `SIMULATED · recorded MuJoCo run · seed ${ep.seed}`;
  $('ledger').innerHTML = ep.ledger.map((e) => `<li data-t="${e.t}"><span>${e.t.toFixed(1)}s</span><span>${e.kind.replace('_', ' ')} → ${e.outcome}</span><span class="${e.amount > 0 ? 'pos' : e.amount < 0 ? 'neg' : 'zero'}">${fmt$(e.amount)}</span></li>`).join('');
}

async function main() {
  try {
    const [index, scn] = await Promise.all([fetch('./data/episodes.json').then((r) => r.json()), fetch('./data/scene.json').then((r) => r.json())]);
    sc = scn; buildScene(sc);
    $('episode').innerHTML = index.episodes.map((e, i) => `<option value="${i}">seed ${e.seed} · ${fmt$(e.balance)}</option>`).join('');
    $('episode').addEventListener('change', (e) => loadEpisode(index.episodes[Number(e.target.value)].file));
    await Promise.all([loadRobot(sc), loadEpisode(index.episodes[0].file)]);
    $('loading').remove();
    resize();
    ready = true;
    setRunning(visible && !document.hidden);
  } catch (err) {
    $('loading').textContent = 'Could not load the lab: ' + err.message;
    console.error(err);
  }
}
main();
