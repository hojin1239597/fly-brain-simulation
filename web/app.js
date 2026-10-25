import * as THREE from "three";

const COLORS = {
  OPTIC: "#8b97e8",
  AL: "#5ec8ff",
  LH: "#c9a6ff",
  KCab: "#3dff9a",
  KCg: "#1fa86a",
  PAM: "#ffc857",
  PPL: "#ff8a3d",
  MBON: "#d6ff4a",
  MB: "#9ad0a4",
  EB: "#ff7ad1",
  FB: "#ff5d8f",
  PB: "#ffd0e8",
  GNG: "#e07a5f",
  DN: "#f3f0e6",
  CENTRAL: "#6d7464",
};

const SIZES = {
  OPTIC: 0.02,
  CENTRAL: 0.016,
  AL: 0.022,
  LH: 0.024,
  KCab: 0.028,
  KCg: 0.028,
  PAM: 0.085,
  PPL: 0.1,
  MBON: 0.05,
  MB: 0.04,
  EB: 0.03,
  FB: 0.02,
  PB: 0.028,
  GNG: 0.018,
  DN: 0.026,
};

const ARENA = 3.05;
const $ = (id) => document.getElementById(id);

let meta = null;
let result = null;
let dose = [];
let disease = "parkinson";
let severity = 0.6;
let playing = true;
let speed = 1;
let last = 0;
const clouds = [];
const trail = [];

const bodyScene = new THREE.Scene();
const brainScene = new THREE.Scene();
const bodyCamera = new THREE.PerspectiveCamera(38, 1, 0.1, 80);
const brainCamera = new THREE.PerspectiveCamera(42, 1, 0.01, 20);
const bodyRenderer = new THREE.WebGLRenderer({ canvas: $("body-canvas"), antialias: true, preserveDrawingBuffer: true });
const brainRenderer = new THREE.WebGLRenderer({ canvas: $("brain-canvas"), antialias: true, preserveDrawingBuffer: true });
bodyRenderer.setClearColor(0x243028);
brainRenderer.setClearColor(0x101614);
bodyRenderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
brainRenderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));

const bodyOrbit = orbit($("body-canvas"), bodyCamera, new THREE.Vector3(0.1, 0, 0), 0.35, 0.68, 7.6, false);
const brainOrbit = orbit($("brain-canvas"), brainCamera, new THREE.Vector3(0, 0.02, 0), 0.5, 1.08, 1.72, true);

const arenaFly = makeFly(0.58);
const climbFly = makeFly(0.36);
bodyScene.add(arenaFly.root, climbFly.root);
buildArena();

function showError(error) {
  const banner = $("banner");
  banner.hidden = false;
  banner.textContent = error instanceof Error ? error.message : String(error);
}

function orbit(canvas, camera, target, theta, phi, dist, auto) {
  const state = { theta, phi, dist, drag: false, x: 0, y: 0, auto };
  canvas.addEventListener("pointerdown", (event) => {
    state.drag = true;
    state.x = event.clientX;
    state.y = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointerup", () => { state.drag = false; });
  canvas.addEventListener("pointermove", (event) => {
    if (!state.drag) return;
    state.theta -= (event.clientX - state.x) * 0.008;
    state.phi = Math.max(0.25, Math.min(1.45, state.phi + (event.clientY - state.y) * 0.008));
    state.x = event.clientX;
    state.y = event.clientY;
  });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    state.dist = Math.max(1.4, Math.min(24, state.dist + event.deltaY * 0.008));
  }, { passive: false });
  return {
    update(dt) {
      if (state.auto && !state.drag) state.theta += dt * 0.18;
      camera.position.set(
        target.x + state.dist * Math.sin(state.phi) * Math.sin(state.theta),
        target.y + state.dist * Math.cos(state.phi),
        target.z + state.dist * Math.sin(state.phi) * Math.cos(state.theta),
      );
      camera.lookAt(target);
    },
  };
}

function fit(renderer, camera, canvas) {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function makeFly(scale) {
  const root = new THREE.Group();
  const pose = new THREE.Group();
  root.add(pose);
  root.scale.setScalar(scale);
  const body = new THREE.MeshStandardMaterial({ color: 0xc4a574, roughness: 0.55 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x6e5434, roughness: 0.62 });
  const eye = new THREE.MeshStandardMaterial({ color: 0xc32618, roughness: 0.32, emissive: 0x5a100c, emissiveIntensity: 0.45 });
  const wingMat = new THREE.MeshStandardMaterial({
    color: 0xd5e4ea, transparent: true, opacity: 0.42, side: THREE.DoubleSide, roughness: 0.15,
  });

  const thorax = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 18), body);
  thorax.scale.set(1.05, 0.78, 0.72);
  pose.add(thorax);

  const abdomen = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 18), body);
  abdomen.scale.set(1.28, 0.7, 0.64);
  abdomen.position.set(-1.45, -0.02, 0);
  pose.add(abdomen);
  for (let i = 0; i < 4; i += 1) {
    const band = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 10), dark);
    band.scale.set(0.07, 0.72, 0.66);
    band.position.set(-0.95 - i * 0.32, -0.02, 0);
    pose.add(band);
  }

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.58, 22, 16), body);
  head.position.set(1.12, 0.06, 0);
  pose.add(head);
  for (const z of [0.42, -0.42]) {
    const eyeMesh = new THREE.Mesh(new THREE.SphereGeometry(0.4, 18, 12), eye);
    eyeMesh.scale.set(0.78, 1.2, 0.7);
    eyeMesh.position.set(1.22, 0.12, z);
    pose.add(eyeMesh);
  }
  const ant = new THREE.MeshStandardMaterial({ color: 0x241c14 });
  for (const z of [0.1, -0.1]) {
    const hair = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.012, 0.55, 6), ant);
    hair.position.set(1.7, 0.28, z);
    hair.rotation.z = -1.0;
    hair.rotation.y = z > 0 ? -0.25 : 0.25;
    pose.add(hair);
  }

  const wings = [];
  for (const side of [1, -1]) {
    const wing = new THREE.Mesh(new THREE.PlaneGeometry(1.85, 0.62), wingMat);
    wing.position.set(-0.2, 0.58, side * 0.62);
    wing.rotation.x = side * -0.7;
    wing.rotation.z = side * 0.18;
    pose.add(wing);
    wings.push(wing);
  }

  const joints = { abdomen: new THREE.Group(), wing_l: new THREE.Group(), wing_r: new THREE.Group() };
  joints.abdomen.position.set(-0.45, 0, 0);
  pose.add(joints.abdomen);
  abdomen.position.set(-1.0, -0.02, 0);
  joints.abdomen.attach(abdomen);
  pose.children.filter((child) => child !== joints.abdomen && child.position && child.position.x < -0.7).forEach((band) => {
    joints.abdomen.attach(band);
  });

  const legs = [];
  const names = ["fl", "fr", "ml", "mr", "hl", "hr"];
  const specs = [
    [0.48, 0.28, 1],
    [0.48, -0.28, -1],
    [0.02, 0.36, 1],
    [0.02, -0.36, -1],
    [-0.42, 0.26, 1],
    [-0.42, -0.26, -1],
  ];
  specs.forEach(([x, z, side], index) => {
    const hip = new THREE.Group();
    hip.position.set(x, -0.22, z);
    const knee = new THREE.Group();
    knee.position.set(side * 0.08, -0.38, 0);
    const upper = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.03, 0.42, 6), dark);
    upper.position.set(side * 0.04, -0.18, 0);
    upper.rotation.z = side * 0.25;
    const lower = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.02, 0.4, 6), dark);
    lower.position.set(side * 0.05, -0.2, 0);
    lower.rotation.z = side * 0.35;
    hip.add(upper);
    hip.add(knee);
    knee.add(lower);
    pose.add(hip);
    joints[`hip_${names[index]}`] = hip;
    joints[`knee_${names[index]}`] = knee;
    legs.push({ hip, knee, side });
  });
  wings.forEach((wing, index) => {
    const pivot = index === 0 ? joints.wing_l : joints.wing_r;
    pivot.position.copy(wing.position);
    pose.add(pivot);
    wing.position.set(-0.15, 0, (index === 0 ? 1 : -1) * 0.25);
    pivot.attach(wing);
  });
  return { root, pose, wings, legs, joints };
}

function buildArena() {
  bodyScene.add(new THREE.HemisphereLight(0xfff6e8, 0x3d4a34, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(4, 9, 5);
  bodyScene.add(sun);
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(ARENA, 64),
    new THREE.MeshStandardMaterial({ color: 0x3d4e38, roughness: 0.85 }),
  );
  floor.rotation.x = -Math.PI / 2;
  bodyScene.add(floor);
  const rim = new THREE.Mesh(
    new THREE.TorusGeometry(ARENA, 0.06, 8, 64),
    new THREE.MeshStandardMaterial({ color: 0x3c4a34 }),
  );
  rim.rotation.x = Math.PI / 2;
  bodyScene.add(rim);

  const tube = new THREE.Mesh(
    new THREE.CylinderGeometry(0.62, 0.62, 2.8, 24, 1, true),
    new THREE.MeshStandardMaterial({ color: 0xb7c8d4, transparent: true, opacity: 0.16, side: THREE.DoubleSide }),
  );
  tube.position.set(-2.15, 1.45, 2.35);
  bodyScene.add(tube);
  climbFly.root.position.set(-2.15, 0.2, 2.35);

  const trailLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: 0xdff25a }),
  );
  bodyScene.add(trailLine);
  bodyScene.userData.trail = trailLine;
}

async function loadBrain() {
  const buffer = await fetch("/flywire_points.bin").then((res) => res.arrayBuffer());
  const view = new DataView(buffer);
  const count = view.getUint32(0, true);
  const buckets = meta.groups.map(() => []);
  for (let i = 0; i < count; i += 1) {
    const offset = 4 + i * 7;
    const x = view.getInt16(offset, true) / 16000;
    const y = view.getInt16(offset + 2, true) / 16000;
    const z = view.getInt16(offset + 4, true) / 16000;
    const group = view.getUint8(offset + 6);
    if (!buckets[group]) continue;
    buckets[group].push(x, -y, -z);
  }
  const brain = new THREE.Group();
  meta.groups.forEach((group, index) => {
    const values = buckets[index];
    if (!values.length) return;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
    const material = new THREE.PointsMaterial({
      color: COLORS[group.id] || "#dddddd",
      size: SIZES[group.id] || 0.02,
      transparent: true,
      opacity: group.id === "OPTIC" ? 0.55 : 0.9,
      depthWrite: false,
      sizeAttenuation: true,
    });
    const points = new THREE.Points(geometry, material);
    brain.add(points);
    clouds.push({ id: group.id, points, material, base: SIZES[group.id] || 0.02, color: COLORS[group.id] });
  });
  brainScene.add(brain);
  $("brain-note").textContent = `${meta.neuron_count.toLocaleString("ko-KR")}개 신경의 실제 좌표. 옅고 붉은 점이 잃은 부분입니다.`;
}

function paintBrain(current) {
  const ids = meta.groups.map((group) => group.id);
  clouds.forEach((cloud) => {
    const index = ids.indexOf(cloud.id);
    const loss = current ? current.loss[index] : 1;
    const rate = current ? current.rates[index] : 0.15;
    const color = new THREE.Color(cloud.color);
    color.lerp(new THREE.Color("#ffffff"), Math.min(0.65, rate));
    color.lerp(new THREE.Color("#ff3b1f"), (1 - loss) * 0.88);
    cloud.material.color.copy(color);
    cloud.material.opacity = (cloud.id === "OPTIC" ? 0.16 : 0.08) + (cloud.id === "OPTIC" ? 0.5 : 0.88) * loss;
    cloud.material.size = cloud.base * (0.28 + 0.72 * loss);
  });
}

function applyJoints(model, joints) {
  if (!joints) return;
  model.joints.abdomen.rotation.z = joints.abdomen || 0;
  model.joints.wing_l.rotation.x = joints.wing_l || 0;
  model.joints.wing_r.rotation.x = joints.wing_r || 0;
  ["fl", "fr", "ml", "mr", "hl", "hr"].forEach((name) => {
    model.joints[`hip_${name}`].rotation.z = (joints[`hip_${name}`] || 0) * 1.8;
    model.joints[`knee_${name}`].rotation.z = ((joints[`knee_${name}`] || 0) - 0.25) * 1.4;
  });
}

function paintBody(current) {
  const fly = current.fly;
  const stand = 0.021;
  arenaFly.root.position.set(fly.x * ARENA, 0.16 + ((fly.z || stand) - stand) * 14, -fly.y * ARENA);
  if (fly.quat) arenaFly.root.quaternion.set(fly.quat[0], fly.quat[1], fly.quat[2], fly.quat[3]);
  else arenaFly.root.rotation.y = fly.heading;
  applyJoints(arenaFly, fly.joints);
  climbFly.root.position.set(-2.15, 0.18 + fly.climb * 2.15, 2.35);
  climbFly.root.rotation.set(0.15, Math.PI / 2, 0);
  applyJoints(climbFly, fly.climb_joints || fly.joints);
}

function remember(fly) {
  const point = new THREE.Vector3(fly.x * ARENA, 0.05, -fly.y * ARENA);
  const previous = trail[trail.length - 1];
  if (!previous || previous.distanceTo(point) > 0.03) trail.push(point);
  if (trail.length > 140) trail.shift();
  if (trail.length > 1 && bodyScene.userData.trail) {
    bodyScene.userData.trail.geometry.dispose();
    bodyScene.userData.trail.geometry = new THREE.BufferGeometry().setFromPoints(trail);
  }
}

function percent(value) {
  return `${Math.round(value * 100)}%`;
}

function renderReadout(current) {
  if (!current || !meta) return;
  $("phase").textContent = current.phase;
  $("body-live").textContent = `손상 ${percent(current.damage || 0)} · 속도 ${current.fly.speed.toFixed(2)} · 기어오르기 ${percent(current.fly.climb)}`;
  const ids = meta.groups.map((group) => group.id);
  const lossOf = (id) => current.loss[ids.indexOf(id)];
  const pam = meta.groups.find((group) => group.id === "PAM");
  const ppl = meta.groups.find((group) => group.id === "PPL");
  const left = Math.round(pam.count * lossOf("PAM") + ppl.count * lossOf("PPL"));
  $("loss-live").textContent = `도파민 신경 ${left.toLocaleString("ko-KR")} / ${(pam.count + ppl.count).toLocaleString("ko-KR")}`;
  document.querySelectorAll(".chip").forEach((chip) => {
    const index = ids.indexOf(chip.dataset.id);
    const loss = current.loss[index];
    chip.classList.toggle("hit", loss < 0.98);
    chip.querySelector("b").textContent = percent(loss);
  });
}

function doseValue(key) {
  if (!dose.length) return null;
  if (severity <= dose[0].severity) return dose[0][key];
  for (let index = 1; index < dose.length; index += 1) {
    const previous = dose[index - 1];
    const point = dose[index];
    if (severity <= point.severity) {
      const span = point.severity - previous.severity || 1;
      const mix = (severity - previous.severity) / span;
      return previous[key] * (1 - mix) + point[key] * mix;
    }
  }
  return dose[dose.length - 1][key];
}

function drawChart() {
  document.querySelectorAll(".charts canvas").forEach((canvas) => {
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.max(1, width * dpr);
    canvas.height = Math.max(1, height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const left = 36;
    const right = 12;
    const top = 12;
    const bottom = 26;
    const plotW = Math.max(1, width - left - right);
    const plotH = Math.max(1, height - top - bottom);
    ctx.strokeStyle = "#313a28";
    ctx.beginPath();
    ctx.moveTo(left, top);
    ctx.lineTo(left, top + plotH);
    ctx.lineTo(left + plotW, top + plotH);
    ctx.stroke();
    ctx.fillStyle = "#a7ae9b";
    ctx.font = "12px sans-serif";
    ctx.fillText("100%", 2, top + 10);
    ctx.fillText("0%", 14, top + plotH);
    ctx.fillText("손상 0", left, height - 6);
    ctx.fillText("손상 100%", left + plotW - 62, height - 6);
    if (!dose.length) return;
    const key = canvas.dataset.key;
    ctx.beginPath();
    dose.forEach((point, index) => {
      const x = left + point.severity * plotW;
      const y = top + (1 - point[key]) * plotH;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = canvas.dataset.color;
    ctx.lineWidth = 2;
    ctx.stroke();
    const marker = left + severity * plotW;
    const current = doseValue(key);
    ctx.fillStyle = canvas.dataset.color;
    ctx.beginPath();
    ctx.arc(marker, top + (1 - current) * plotH, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#f3f0e6";
    ctx.setLineDash([3, 4]);
    ctx.beginPath();
    ctx.moveTo(marker, top);
    ctx.lineTo(marker, top + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
  });
  document.querySelectorAll("[data-now]").forEach((node) => {
    const value = doseValue(node.dataset.now);
    node.textContent = value == null ? "" : `지금 슬라이더 ${Math.round(severity * 100)}%에서 ${percent(value)}`;
  });
}

function fillSummary() {
  if (!result) return;
  $("chain").innerHTML = result.chain.map((item) => `<li><span>${item.label}</span><b>${item.value}</b></li>`).join("");
  const rows = [
    ["버섯체 활동 감소", `${result.grade} ${percent(result.disease_score)}`],
    ["걸음", percent(result.locomotion)],
    ["기어오르기", percent(result.climbing)],
    [result.change_label, percent(result.change_value)],
  ];
  $("metrics").innerHTML = rows.map(([name, value]) => `<div><dt>${name}</dt><dd>${value}</dd></div>`).join("");
  $("story").textContent = result.story;
}

function showFrame(payload) {
  result = payload;
  fillSummary();
  paintBody(payload.frame);
  paintBrain(payload.frame);
  renderReadout(payload.frame);
  remember(payload.frame.fly);
}

async function postLive(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error("시뮬레이션을 받지 못했습니다.");
  return response.json();
}

let ticking = false;

async function pull() {
  if (!playing || ticking) return;
  ticking = true;
  const started = performance.now();
  try {
    const payload = await postLive("/api/live", { disease, severity, seconds: 0.1 * speed });
    showFrame(payload);
  } catch (error) {
    showError(error);
  } finally {
    ticking = false;
    const wait = Math.max(0, 100 - (performance.now() - started));
    window.setTimeout(pull, wait);
  }
}

function loadDose() {
  const asked = disease;
  fetch(`/api/dose?disease=${asked}`)
    .then((response) => response.json())
    .then((payload) => {
      if (asked !== disease || !payload.points) return;
      dose = payload.points;
      drawChart();
    })
    .catch(showError);
}

function draw(now) {
  requestAnimationFrame(draw);
  const dt = Math.min(0.05, (now - last) / 1000 || 0);
  last = now;
  fit(bodyRenderer, bodyCamera, $("body-canvas"));
  fit(brainRenderer, brainCamera, $("brain-canvas"));
  bodyOrbit.update(dt);
  brainOrbit.update(dt);
  bodyRenderer.render(bodyScene, bodyCamera);
  brainRenderer.render(brainScene, brainCamera);
}

function bind() {
  document.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () => {
      disease = card.dataset.disease;
      document.querySelectorAll(".card").forEach((other) => {
        const on = other === card;
        other.classList.toggle("active", on);
        other.setAttribute("aria-pressed", on ? "true" : "false");
      });
      loadDose();
    });
  });
  $("severity").addEventListener("input", (event) => {
    severity = Number(event.target.value) / 100;
    $("severity-out").textContent = `${event.target.value}%`;
    drawChart();
  });
  $("play").addEventListener("click", () => {
    playing = !playing;
    $("play").textContent = playing ? "일시정지" : "재생";
    if (playing) pull();
  });
  $("restart").addEventListener("click", async () => {
    trail.length = 0;
    playing = true;
    $("play").textContent = "일시정지";
    try {
      showFrame(await postLive("/api/reset", { disease, severity }));
    } catch (error) {
      showError(error);
    }
    pull();
  });
  $("speed").addEventListener("click", () => {
    speed = speed === 1 ? 2 : speed === 2 ? 4 : 1;
    $("speed").textContent = `${speed}×`;
  });
  window.addEventListener("resize", drawChart);
}

async function main() {
  bind();
  try {
    meta = await fetch("/api/meta").then((res) => res.json());
    $("legend").innerHTML = meta.groups.map((group) => (
      `<span class="chip" data-id="${group.id}"><i style="background:${COLORS[group.id]}"></i>${group.name} ${group.count.toLocaleString("ko-KR")}<b>100%</b></span>`
    )).join("");
    $("notes").innerHTML = meta.notes.map((note) => `<li>${note}</li>`).join("");
    $("cite").textContent = `${meta.dataset}. ${meta.citations.join(" ")} ${meta.transmitter_rule}.`;
    await loadBrain();
    paintBrain(null);
    loadDose();
    pull();
  } catch (error) {
    showError(error);
  }
  requestAnimationFrame(draw);
}

main();
