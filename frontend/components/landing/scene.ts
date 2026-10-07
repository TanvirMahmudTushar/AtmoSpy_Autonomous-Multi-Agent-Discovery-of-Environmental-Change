import * as THREE from "three";
import { AGENTS, AGENT_BY_ID, type AgentId } from "./agents";

/**
 * The landing-page "mission crew" diorama: a floating voxel island where each
 * pipeline agent acts out its job on a loop. Plain three.js, no assets — every
 * mesh is built from boxes so it matches the pixel/voxel look of the app.
 */

export interface DioramaHandle {
  getStatus(id: AgentId): string;
  select(id: AgentId | null): void;
  dispose(): void;
}

interface DioramaOptions {
  onSelect(id: AgentId | null): void;
}

type V2 = { x: number; z: number };

const PIXEL_FONT = '"Press Start 2P", monospace';

// ---------------------------------------------------------------- helpers

const matCache = new Map<string, THREE.MeshLambertMaterial>();

function mat(color: string, emissive = "#000000", emissiveIntensity = 1): THREE.MeshLambertMaterial {
  const key = `${color}|${emissive}|${emissiveIntensity}`;
  let m = matCache.get(key);
  if (!m) {
    m = new THREE.MeshLambertMaterial({ color, emissive, emissiveIntensity });
    matCache.set(key, m);
  }
  return m;
}

function box(
  w: number,
  h: number,
  d: number,
  material: THREE.Material,
  x = 0,
  y = 0,
  z = 0,
  parent?: THREE.Object3D,
): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  parent?.add(m);
  return m;
}

function damp(current: number, target: number, rate: number, dt: number): number {
  return current + (target - current) * Math.min(1, rate * dt);
}

function angleTo(from: V2, to: V2): number {
  return Math.atan2(to.x - from.x, to.z - from.z);
}

function makeCanvasSprite(
  width: number,
  height: number,
  draw: (ctx: CanvasRenderingContext2D) => void,
  worldWidth: number,
): { sprite: THREE.Sprite; redraw: (draw?: (ctx: CanvasRenderingContext2D) => void) => void } {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.minFilter = THREE.LinearFilter;
  let painter = draw;
  const redraw = (next?: (ctx: CanvasRenderingContext2D) => void) => {
    if (next) painter = next;
    ctx.clearRect(0, 0, width, height);
    painter(ctx);
    tex.needsUpdate = true;
  };
  redraw();
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sprite.scale.set(worldWidth, (worldWidth * height) / width, 1);
  sprite.renderOrder = 10;
  return { sprite, redraw };
}

function drawTag(ctx: CanvasRenderingContext2D, text: string, color: string) {
  const w = ctx.canvas.width;
  const h = ctx.canvas.height;
  ctx.fillStyle = "rgba(7, 11, 20, 0.82)";
  ctx.fillRect(6, 6, w - 12, h - 12);
  ctx.strokeStyle = color;
  ctx.lineWidth = 4;
  ctx.strokeRect(6, 6, w - 12, h - 12);
  ctx.fillStyle = "#eef3fb";
  ctx.font = `20px ${PIXEL_FONT}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, w / 2, h / 2 + 2);
}

// ---------------------------------------------------------------- agent rig

interface Rig {
  id: AgentId;
  root: THREE.Group;
  body: THREE.Group;
  head: THREE.Group;
  armL: THREE.Group;
  armR: THREE.Group;
  legL: THREE.Group;
  legR: THREE.Group;
  hand: THREE.Group;
  walkPhase: number;
}

interface Pose {
  armL?: number;
  armR?: number;
  armLz?: number;
  armRz?: number;
  headX?: number;
  headY?: number;
  crouch?: number;
}

function makeRig(id: AgentId): Rig {
  const color = AGENT_BY_ID[id].color;
  const suit = mat(color);
  const white = mat("#e9eef5");
  const dark = mat("#26314a");
  const visor = mat("#0b1222", color, 0.7);
  const glow = mat(color, color, 1);

  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);

  const legL = new THREE.Group();
  legL.position.set(-0.13, 0.45, 0);
  box(0.2, 0.45, 0.24, dark, 0, -0.225, 0, legL);
  body.add(legL);
  const legR = new THREE.Group();
  legR.position.set(0.13, 0.45, 0);
  box(0.2, 0.45, 0.24, dark, 0, -0.225, 0, legR);
  body.add(legR);

  box(0.54, 0.56, 0.34, suit, 0, 0.73, 0, body);
  box(0.56, 0.08, 0.36, white, 0, 0.5, 0, body);
  box(0.4, 0.42, 0.16, white, 0, 0.76, -0.25, body);
  box(0.12, 0.12, 0.02, glow, 0.12, 0.85, 0.175, body);

  const makeArm = (side: number) => {
    const arm = new THREE.Group();
    arm.position.set(0.36 * side, 0.96, 0);
    box(0.17, 0.5, 0.19, suit, 0, -0.22, 0, arm);
    box(0.18, 0.12, 0.2, white, 0, -0.47, 0, arm);
    body.add(arm);
    return arm;
  };
  const armL = makeArm(-1);
  const armR = makeArm(1);
  const hand = new THREE.Group();
  hand.position.set(0, -0.52, 0.02);
  armR.add(hand);

  const head = new THREE.Group();
  head.position.set(0, 1.01, 0);
  body.add(head);
  box(0.52, 0.48, 0.48, white, 0, 0.25, 0, head);
  box(0.4, 0.22, 0.02, visor, 0, 0.27, 0.245, head);
  box(0.04, 0.22, 0.04, dark, 0.16, 0.6, 0, head);
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 6), glow);
  tip.position.set(0.16, 0.74, 0);
  head.add(tip);

  root.traverse((o) => (o.userData.agentId = id));
  return { id, root, body, head, armL, armR, legL, legR, hand, walkPhase: 0 };
}

/** Ease limbs toward a pose. Anything not set relaxes to neutral. */
function pose(rig: Rig, p: Pose, dt: number) {
  const r = 12;
  rig.armL.rotation.x = damp(rig.armL.rotation.x, p.armL ?? 0, r, dt);
  rig.armR.rotation.x = damp(rig.armR.rotation.x, p.armR ?? 0, r, dt);
  rig.armL.rotation.z = damp(rig.armL.rotation.z, p.armLz ?? 0, r, dt);
  rig.armR.rotation.z = damp(rig.armR.rotation.z, p.armRz ?? 0, r, dt);
  rig.head.rotation.x = damp(rig.head.rotation.x, p.headX ?? 0, r, dt);
  rig.head.rotation.y = damp(rig.head.rotation.y, p.headY ?? 0, r, dt);
  rig.body.position.y = damp(rig.body.position.y, -(p.crouch ?? 0), r, dt);
  rig.legL.rotation.x = damp(rig.legL.rotation.x, 0, r, dt);
  rig.legR.rotation.x = damp(rig.legR.rotation.x, 0, r, dt);
}

/** Walk-cycle overlay; call after pose(). `carrying` keeps the arms forward. */
function walkCycle(rig: Rig, dt: number, carrying: boolean) {
  rig.walkPhase += dt * 10;
  const s = Math.sin(rig.walkPhase);
  rig.legL.rotation.x = s * 0.6;
  rig.legR.rotation.x = -s * 0.6;
  if (!carrying) {
    rig.armL.rotation.x = -s * 0.5;
    rig.armR.rotation.x = s * 0.5;
  }
  rig.body.position.y = Math.abs(s) * 0.06;
}

function face(rig: Rig, angle: number, dt: number) {
  const h = rig.root.rotation.y;
  const d = Math.atan2(Math.sin(angle - h), Math.cos(angle - h));
  rig.root.rotation.y = h + d * Math.min(1, dt * 8);
}

/** Step toward a target on the ground. Returns true on arrival. */
function moveTo(rig: Rig, target: V2, dt: number, speed = 1.6): boolean {
  const p = rig.root.position;
  const dx = target.x - p.x;
  const dz = target.z - p.z;
  const dist = Math.hypot(dx, dz);
  if (dist < 0.04) return true;
  const step = Math.min(dist, speed * dt);
  p.x += (dx / dist) * step;
  p.z += (dz / dist) * step;
  face(rig, Math.atan2(dx, dz), dt);
  return false;
}

// ---------------------------------------------------------------- scene

export function createDiorama(container: HTMLDivElement, opts: DioramaOptions): DioramaHandle {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.style.display = "block";
  renderer.domElement.style.touchAction = "pan-y";
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);

  // --- lights
  const hemi = new THREE.HemisphereLight("#ffffff", "#444444", 1);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight("#ffffff", 1);
  sun.position.set(6, 12, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 40 });
  sun.shadow.bias = -0.0015;
  scene.add(sun);
  const screenLight = new THREE.PointLight("#38bdf8", 0, 6, 1.5);
  screenLight.position.set(0.5, 1.4, -3.3);
  scene.add(screenLight);

  // --- island
  const world = new THREE.Group();
  scene.add(world);
  const grass = mat("#6aa84f");
  box(12, 0.5, 12, grass, 0, -0.25, 0, world);
  box(12.02, 0.18, 12.02, mat("#4f8a3a"), 0, -0.58, 0, world);
  const dirt = mat("#8a5a34");
  const dirtDark = mat("#6b4428");
  box(11, 1, 11, dirt, 0, -1.15, 0, world);
  box(9, 1, 9, dirtDark, 0, -2.15, 0, world);
  box(6, 1, 6, dirt, 0, -3.15, 0, world);
  box(3, 1, 3, dirtDark, 0.5, -4.15, -0.5, world);
  box(1, 1, 1, mat("#7a7f8c"), 4.6, -1.4, 5.1, world);
  box(1, 1, 1, mat("#7a7f8c"), -5.1, -1.6, -2, world);

  // stepping-stone path dish → terminal
  const stone = mat("#b9b3a3");
  for (let i = 0; i < 6; i++) box(0.5, 0.06, 0.5, stone, -3.2 + i * 0.7, 0.02, -2.6 + (i % 2) * 0.1, world);

  // trees
  const trunk = mat("#6b4428");
  const leaves = mat("#3f7d43");
  const leavesLight = mat("#57a05a");
  const trees: THREE.Group[] = [];
  for (const [x, z, s] of [
    [-5.2, -5.2, 1],
    [5.2, -5.2, 0.9],
    [-5.2, 5.2, 1.1],
    [5.3, 0.4, 0.8],
    [-2.6, -5.3, 0.7],
  ] as const) {
    const t = new THREE.Group();
    t.position.set(x, 0, z);
    t.scale.setScalar(s);
    box(0.3, 0.9, 0.3, trunk, 0, 0.45, 0, t);
    box(1.1, 0.9, 1.1, leaves, 0, 1.3, 0, t);
    box(0.7, 0.6, 0.7, leavesLight, 0, 2.0, 0, t);
    world.add(t);
    trees.push(t);
  }

  // crop rows
  const cropA = mat("#9bcf53");
  const cropB = mat("#e0b23d");
  for (let r = 0; r < 3; r++) {
    box(0.5, 0.05, 2.6, mat("#6b4428"), -3.2 + r * 0.7, 0.02, 1.3, world);
    for (let c = 0; c < 5; c++) {
      const h = 0.2 + ((r * 5 + c) % 3) * 0.08;
      box(0.22, h, 0.22, (r + c) % 2 ? cropA : cropB, -3.2 + r * 0.7, h / 2 + 0.04, 0.3 + c * 0.5, world);
    }
  }

  // --- satellite dish
  const dish = new THREE.Group();
  dish.position.set(-4, 0, -3.6);
  world.add(dish);
  const metal = mat("#c5cdd8");
  box(0.9, 0.3, 0.9, mat("#7a8699"), 0, 0.15, 0, dish);
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 1, 8), metal);
  pole.position.y = 0.8;
  pole.castShadow = true;
  dish.add(pole);
  const dishYaw = new THREE.Group();
  dishYaw.position.y = 1.3;
  dish.add(dishYaw);
  const dishTilt = new THREE.Group();
  dishTilt.rotation.x = 0.7;
  dishYaw.add(dishTilt);
  const bowl = new THREE.Mesh(
    new THREE.ConeGeometry(0.85, 0.35, 18, 1, true),
    new THREE.MeshLambertMaterial({ color: "#e9eef5", side: THREE.DoubleSide }),
  );
  bowl.rotation.x = Math.PI;
  bowl.position.y = 0.15;
  bowl.castShadow = true;
  dishTilt.add(bowl);
  box(0.04, 0.6, 0.04, metal, 0, 0.45, 0, dishTilt);
  const receiverMat = new THREE.MeshBasicMaterial({ color: "#38bdf8" });
  const receiver = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 8), receiverMat);
  receiver.position.y = 0.78;
  dishTilt.add(receiver);

  // --- terminal desk, monitor, hologram bars
  const deskMat = mat("#8b6a48");
  box(2.4, 0.08, 1, deskMat, 0.5, 0.74, -4, world);
  box(0.1, 0.7, 0.9, deskMat, -0.6, 0.35, -4, world);
  box(0.1, 0.7, 0.9, deskMat, 1.6, 0.35, -4, world);
  box(1.4, 0.9, 0.1, mat("#1b2335"), 0.5, 1.3, -4.25, world);
  box(0.12, 0.3, 0.12, mat("#1b2335"), 0.5, 0.9, -4.3, world);
  box(0.8, 0.04, 0.26, mat("#3a465f"), 0.75, 0.8, -3.75, world);

  const screenCanvas = document.createElement("canvas");
  screenCanvas.width = 128;
  screenCanvas.height = 80;
  const screenCtx = screenCanvas.getContext("2d")!;
  const screenTex = new THREE.CanvasTexture(screenCanvas);
  screenTex.colorSpace = THREE.SRGBColorSpace;
  screenTex.magFilter = THREE.NearestFilter;
  const screenMat = new THREE.MeshBasicMaterial({ map: screenTex });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(1.28, 0.78), screenMat);
  screen.position.set(0.5, 1.3, -4.195);
  world.add(screen);
  const screenSeries: number[] = Array.from({ length: 24 }, (_, i) => 0.4 + i * 0.01 + Math.random() * 0.15);
  let screenFlash = 0;
  function drawScreen() {
    const c = screenCtx;
    c.fillStyle = screenFlash > 0 ? "#12324a" : "#07131f";
    c.fillRect(0, 0, 128, 80);
    c.fillStyle = "#1f3b52";
    for (let y = 12; y < 80; y += 12) c.fillRect(6, y, 116, 1);
    c.strokeStyle = "#34d399";
    c.lineWidth = 2;
    c.beginPath();
    screenSeries.forEach((v, i) => {
      const x = 6 + (i / (screenSeries.length - 1)) * 116;
      const y = 74 - v * 64;
      if (i === 0) c.moveTo(x, y);
      else c.lineTo(x, y);
    });
    c.stroke();
    c.fillStyle = "#eda100";
    c.fillRect(6, 4, 30 + Math.random() * 40, 3);
    screenTex.needsUpdate = true;
  }
  drawScreen();

  const holo = new THREE.Group();
  holo.position.set(0.5, 2.05, -4.1);
  world.add(holo);
  const holoBase = new THREE.Mesh(
    new THREE.BoxGeometry(1.5, 0.03, 0.4),
    new THREE.MeshBasicMaterial({ color: "#38bdf8", transparent: true, opacity: 0.35 }),
  );
  holo.add(holoBase);
  const barColors = ["#2a78d6", "#1baf7a", "#eda100", "#eb6834", "#e87ba4"];
  const bars = barColors.map((c, i) => {
    const b = new THREE.Mesh(
      new THREE.BoxGeometry(0.2, 1, 0.2),
      new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.85 }),
    );
    b.position.x = -0.56 + i * 0.28;
    holo.add(b);
    return b;
  });
  let barBump = 0;

  // --- printer
  box(0.8, 0.55, 0.65, mat("#d6dbe3"), 2.6, 0.275, -4, world);
  box(0.5, 0.05, 0.1, mat("#26314a"), 2.6, 0.5, -3.7, world);
  const printerLed = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 0.02), new THREE.MeshBasicMaterial({ color: "#34d399" }));
  printerLed.position.set(2.9, 0.4, -3.67);
  world.add(printerLed);
  const paperMat = mat("#ffffff");
  const printedPaper = box(0.36, 0.02, 0.46, paperMat, 2.6, 0.57, -3.9, world);
  printedPaper.visible = false;

  // --- filing cabinet + findings counter
  const cabinet = new THREE.Group();
  cabinet.position.set(-1.6, 0, 4.5);
  world.add(cabinet);
  box(0.9, 1.3, 0.7, mat("#7a8699"), 0, 0.65, 0, cabinet);
  for (let i = 0; i < 3; i++) {
    for (const zf of [-1, 1]) {
      box(0.8, 0.02, 0.02, mat("#4a5568"), 0, 0.42 + i * 0.4, 0.36 * zf, cabinet);
      box(0.2, 0.05, 0.03, mat("#e9eef5"), 0, 0.3 + i * 0.4, 0.36 * zf, cabinet);
    }
  }
  let findingsCount = 0;
  const counter = makeCanvasSprite(320, 72, (c) => drawTag(c, "FINDINGS 0", "#a78bfa"), 2.2);
  counter.sprite.position.set(-1.6, 2.0, 4.5);
  world.add(counter.sprite);
  const bumpCounter = () => {
    findingsCount += 1;
    counter.redraw((c) => drawTag(c, `FINDINGS ${findingsCount}`, "#a78bfa"));
  };

  // --- whiteboard
  const board = new THREE.Group();
  board.position.set(-4.9, 0, 1.1);
  board.rotation.y = Math.PI / 2;
  world.add(board);
  const boardFrame = mat("#5b6478");
  box(0.08, 1.0, 0.08, boardFrame, -1.1, 0.5, 0, board);
  box(0.08, 1.0, 0.08, boardFrame, 1.1, 0.5, 0, board);
  box(2.6, 1.55, 0.06, boardFrame, 0, 1.6, -0.02, board);
  box(2.45, 1.4, 0.04, mat("#f7f7f2"), 0, 1.6, 0.01, board);
  box(2.0, 0.03, 0.01, mat("#26314a"), 0, 1.05, 0.04, board);
  box(0.03, 1.1, 0.01, mat("#26314a"), -1.0, 1.58, 0.04, board);
  const TREND_SEGMENTS = 80;
  const TREND_RADIAL = 5;
  let trendMesh: THREE.Mesh | null = null;
  let trendCurve: THREE.CatmullRomCurve3 | null = null;
  function newTrendLine() {
    if (trendMesh) {
      board.remove(trendMesh);
      trendMesh.geometry.dispose();
      (trendMesh.material as THREE.Material).dispose();
    }
    const rising = Math.random() > 0.3;
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 11; i++) {
      const u = i / 11;
      const base = rising ? u : 1 - u;
      pts.push(new THREE.Vector3(-1 + u * 2, 1.15 + base * 0.8 + (Math.random() - 0.5) * 0.18, 0.06));
    }
    trendCurve = new THREE.CatmullRomCurve3(pts);
    trendMesh = new THREE.Mesh(
      new THREE.TubeGeometry(trendCurve, TREND_SEGMENTS, 0.028, TREND_RADIAL, false),
      new THREE.MeshBasicMaterial({ color: rising ? "#e34948" : "#2a78d6" }),
    );
    trendMesh.geometry.setDrawRange(0, 0);
    board.add(trendMesh);
  }
  newTrendLine();

  // --- telescope
  const scope = new THREE.Group();
  scope.position.set(4.2, 0, 3.6);
  world.add(scope);
  const tripod = mat("#3a465f");
  for (let i = 0; i < 3; i++) {
    const leg = box(0.05, 1.1, 0.05, tripod, 0, 0.5, 0, scope);
    const a = (i / 3) * Math.PI * 2;
    leg.position.set(Math.sin(a) * 0.22, 0.5, Math.cos(a) * 0.22);
    leg.rotation.set(Math.cos(a) * 0.3, 0, -Math.sin(a) * 0.3);
  }
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.1, 1.4, 12), mat("#e9eef5"));
  tube.position.y = 1.25;
  tube.rotation.z = -0.9;
  tube.castShadow = true;
  scope.add(tube);
  const lens = new THREE.Mesh(new THREE.CircleGeometry(0.13, 12), new THREE.MeshBasicMaterial({ color: "#38bdf8" }));
  lens.position.set(0, 0.71, 0);
  lens.rotation.x = -Math.PI / 2;
  tube.add(lens);

  // --- satellite on a tilted orbit ring around the island, so it reads as
  // "in orbit" even under an orthographic camera that hides height.
  const orbit = new THREE.Group();
  orbit.position.set(0, 0.8, 0);
  orbit.rotation.set(0.26, 0, -0.2);
  scene.add(orbit);
  const ORBIT_R = 8.2;
  const orbitRing = new THREE.Mesh(
    new THREE.TorusGeometry(ORBIT_R, 0.025, 4, 160),
    new THREE.MeshBasicMaterial({ color: "#38bdf8", transparent: true, opacity: 0.3 }),
  );
  orbitRing.rotation.x = Math.PI / 2;
  orbit.add(orbitRing);
  const satellite = new THREE.Group();
  satellite.scale.setScalar(1.2);
  orbit.add(satellite);
  box(0.5, 0.5, 0.7, mat("#d9a441"), 0, 0, 0, satellite);
  const panel = mat("#2a4f9c", "#1e3a8a", 0.4);
  box(1.3, 0.04, 0.5, panel, 0.95, 0, 0, satellite);
  box(1.3, 0.04, 0.5, panel, -0.95, 0, 0, satellite);
  box(0.06, 0.3, 0.06, metal, 0, -0.35, 0, satellite);
  const satBlink = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 6), new THREE.MeshBasicMaterial({ color: "#e34948" }));
  satBlink.position.set(0, 0.3, 0);
  satellite.add(satBlink);
  satellite.traverse((o) => (o.castShadow = false));

  // --- clouds
  const cloudMat = new THREE.MeshLambertMaterial({ color: "#ffffff", transparent: true, opacity: 0.9 });
  const clouds = [
    [-6, 5.2, -2, 1],
    [2, 5.8, 3, 0.8],
    [7, 4.8, -5, 1.2],
  ].map(([x, y, z, s]) => {
    const g = new THREE.Group();
    box(1.4, 0.5, 0.9, cloudMat, 0, 0, 0, g);
    box(0.9, 0.5, 0.7, cloudMat, 0.6, 0.3, 0.1, g);
    box(0.8, 0.4, 0.8, cloudMat, -0.6, 0.15, -0.1, g);
    g.children.forEach((c) => (c.castShadow = false));
    g.position.set(x, y, z);
    g.scale.setScalar(s);
    scene.add(g);
    return g;
  });

  // --- effects: data packets + ripples
  interface Fx {
    mesh: THREE.Mesh;
    life: number;
    from?: THREE.Vector3;
    to?: THREE.Vector3;
  }
  const packetGeo = new THREE.BoxGeometry(0.14, 0.14, 0.14);
  const packetMat = new THREE.MeshBasicMaterial({ color: "#38bdf8" });
  const packets: Fx[] = [];
  const ripples: Fx[] = [];
  const rippleGeo = new THREE.RingGeometry(0.16, 0.24, 28);
  function spawnRipple(x: number, z: number, color: string) {
    const m = new THREE.Mesh(
      rippleGeo,
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1, side: THREE.DoubleSide }),
    );
    m.rotation.x = -Math.PI / 2;
    m.position.set(x, 0.03, z);
    world.add(m);
    ripples.push({ mesh: m, life: 1 });
  }

  // --- crew
  const tagSprites: THREE.Sprite[] = [];
  const rigs = Object.fromEntries(
    AGENTS.map((a) => {
      const rig = makeRig(a.id);
      const tag = makeCanvasSprite(256, 64, (c) => drawTag(c, a.tag, a.color), 1.9);
      tag.sprite.position.y = 2.15;
      tag.sprite.userData.redraw = () => tag.redraw();
      tagSprites.push(tag.sprite);
      rig.root.add(tag.sprite);
      world.add(rig.root);
      return [a.id, rig];
    }),
  ) as Record<AgentId, Rig>;

  // Re-render the pixel-font tags once the web font is actually available.
  const tagRedraws: (() => void)[] = [];
  scene.traverse((o) => {
    if (o instanceof THREE.Sprite && o.userData.redraw) tagRedraws.push(o.userData.redraw);
  });
  tagRedraws.push(() => counter.redraw());
  document.fonts
    ?.load(`20px ${PIXEL_FONT}`)
    .then(() => {
      tagRedraws.forEach((r) => r());
      if (reducedMotion) render();
    })
    .catch(() => {});

  // Held props
  const dataCube = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, 0.3), mat("#38bdf8", "#38bdf8", 0.8));
  dataCube.position.set(0, 0.85, 0.38);
  dataCube.visible = false;
  rigs.data.root.add(dataCube);

  const heldPaper = box(0.36, 0.03, 0.46, paperMat, 0, 0.82, 0.34, rigs.report.root);
  heldPaper.visible = false;

  const probe = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.02, 0.8, 6), mat("#c5cdd8"));
  probe.position.set(0, -0.3, 0.05);
  rigs.spatial.hand.add(probe);
  const probeTip = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), new THREE.MeshBasicMaterial({ color: "#38bdf8" }));
  probeTip.position.y = -0.4;
  probe.add(probeTip);

  const marker = box(0.06, 0.16, 0.06, mat("#e34948"), 0, -0.05, 0.05, rigs.trend.hand);
  marker.castShadow = false;

  const doubt = makeCanvasSprite(
    64,
    64,
    (c) => {
      c.fillStyle = "#ffffff";
      c.beginPath();
      c.arc(32, 30, 26, 0, Math.PI * 2);
      c.fill();
      c.fillStyle = "#e34948";
      c.font = `bold 34px ${PIXEL_FONT}`;
      c.textAlign = "center";
      c.textBaseline = "middle";
      c.fillText("?", 34, 33);
    },
    0.55,
  );
  doubt.sprite.position.y = 2.6;
  doubt.sprite.visible = false;
  rigs.skeptic.root.add(doubt.sprite);
  tagRedraws.push(() => doubt.redraw());

  // Selection ring
  const selectRing = new THREE.Mesh(
    new THREE.RingGeometry(0.42, 0.52, 32),
    new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.9, side: THREE.DoubleSide }),
  );
  selectRing.rotation.x = -Math.PI / 2;
  selectRing.visible = false;
  world.add(selectRing);
  let selected: AgentId | null = null;

  // ---------------------------------------------------------------- behaviours

  const status: Record<AgentId, string> = {
    data: "",
    stats: "",
    trend: "",
    spatial: "",
    skeptic: "",
    report: "",
  };

  // Starting spots
  rigs.data.root.position.set(-3.1, 0, -2.7);
  rigs.stats.root.position.set(1.0, 0, -3.05);
  rigs.stats.root.rotation.y = Math.PI;
  rigs.trend.root.position.set(-4.2, 0, 1.6);
  rigs.spatial.root.position.set(1.5, 0, 0.5);
  rigs.skeptic.root.position.set(3.35, 0, 3.6);
  rigs.skeptic.root.rotation.y = Math.PI / 2;
  rigs.report.root.position.set(2.6, 0, -3.1);
  rigs.report.root.rotation.y = Math.PI;

  const DISH_SPOT: V2 = { x: -3.1, z: -2.7 };
  const DROP_SPOT: V2 = { x: -0.2, z: -3.15 };
  const PRINTER_SPOT: V2 = { x: 2.6, z: -3.1 };
  const ARCHIVE_SPOT: V2 = { x: -1.6, z: 3.65 };
  const PROBE_SITES: V2[] = [
    { x: 1.5, z: 0.5 },
    { x: 3.6, z: -1.6 },
    { x: 3.9, z: 1.3 },
    { x: 0.6, z: 2.4 },
    { x: 2.3, z: -0.9 },
    { x: 1.8, z: 2.0 },
  ];

  let pendingReports = 0;

  const dataBot = { state: "toDish" as "toDish" | "load" | "toTerm" | "drop", timer: 0 };
  function updateData(dt: number) {
    const rig = rigs.data;
    const pos = { x: rig.root.position.x, z: rig.root.position.z };
    switch (dataBot.state) {
      case "toDish":
        status.data = "Heading to the dish for the next NASA download";
        pose(rig, {}, dt);
        if (moveTo(rig, DISH_SPOT, dt)) {
          dataBot.state = "load";
          dataBot.timer = 0;
        } else walkCycle(rig, dt, false);
        break;
      case "load": {
        status.data = "Downloading a NASA POWER time series";
        dataBot.timer += dt;
        face(rig, angleTo(pos, { x: -4, z: -3.6 }), dt);
        pose(rig, { armL: -1.3, armR: -1.3, headX: -0.3 }, dt);
        const k = Math.min(1, dataBot.timer / 1.2);
        dataCube.visible = true;
        dataCube.scale.setScalar(0.2 + 0.8 * k);
        dataCube.rotation.y += dt * 4;
        if (dataBot.timer > 1.4) dataBot.state = "toTerm";
        break;
      }
      case "toTerm":
        status.data = "Carrying fresh data to the lab";
        pose(rig, { armL: -1.1, armR: -1.1 }, dt);
        dataCube.rotation.y += dt * 2;
        if (moveTo(rig, DROP_SPOT, dt, 1.4)) {
          dataBot.state = "drop";
          dataBot.timer = 0;
        } else walkCycle(rig, dt, true);
        break;
      case "drop": {
        status.data = "Uploading the data to the analysis terminal";
        dataBot.timer += dt;
        face(rig, Math.PI * 0.85, dt);
        pose(rig, { armL: -1.5, armR: -1.5 }, dt);
        const k = Math.min(1, dataBot.timer / 0.7);
        dataCube.scale.setScalar(1 - k);
        if (dataBot.timer > 0.7 && dataCube.visible) {
          dataCube.visible = false;
          screenFlash = 0.4;
          barBump = 1;
          pendingReports = Math.min(pendingReports + 1, 3);
          screenSeries.push(Math.min(1, screenSeries[screenSeries.length - 1] + (Math.random() - 0.35) * 0.12));
          screenSeries.shift();
          drawScreen();
        }
        if (dataBot.timer > 1.1) dataBot.state = "toDish";
        break;
      }
    }
  }

  let statsLookTimer = 0;
  function updateStats(dt: number, t: number) {
    const rig = rigs.stats;
    statsLookTimer += dt;
    const looking = statsLookTimer % 7 > 5.5;
    face(rig, Math.PI, dt);
    pose(
      rig,
      looking
        ? { armL: -1.2, armR: -0.2, headX: -0.5, headY: 0.2 }
        : {
            armL: -1.25 + Math.sin(t * 22) * 0.12,
            armR: -1.25 + Math.sin(t * 22 + Math.PI) * 0.12,
            headX: 0.15,
          },
      dt,
    );
    status.stats = looking
      ? "Checking the p-value against the confidence band"
      : barBump > 0.3
        ? "New data in. Running Mann-Kendall and Sen's slope"
        : "Fitting an OLS trend line";
    barBump = Math.max(0, barBump - dt * 0.6);
    bars.forEach((b, i) => {
      const h = 0.25 + 0.45 * Math.abs(Math.sin(t * 0.8 + i * 1.3)) + barBump * (0.2 + i * 0.08);
      b.scale.y = h;
      b.position.y = h / 2 + 0.02;
    });
    holo.position.y = 2.05 + Math.sin(t * 1.5) * 0.04;
  }

  const trendBot = { state: "draw" as "draw" | "admire" | "erase", progress: 0, timer: 0 };
  const penLocal = new THREE.Vector3();
  function updateTrend(dt: number, t: number) {
    const rig = rigs.trend;
    const mesh = trendMesh!;
    const curve = trendCurve!;
    const pen = board.localToWorld(curve.getPointAt(Math.min(1, Math.max(0, trendBot.progress)), penLocal));
    const standAt: V2 = { x: -4.15, z: pen.z - 0.3 };
    switch (trendBot.state) {
      case "draw": {
        status.trend = "Plotting the long-term trend";
        trendBot.progress = Math.min(1, trendBot.progress + dt / 6);
        const arrived = moveTo(rig, standAt, dt, 1.2);
        if (arrived || Math.hypot(rig.root.position.z - standAt.z, rig.root.position.x - standAt.x) < 0.3) {
          face(rig, -Math.PI / 2, dt);
        }
        pose(rig, { armR: -1.45 - (pen.y - 1.1) * 0.9 + Math.sin(t * 12) * 0.05, armL: -0.1, headY: 0.2 }, dt);
        mesh.geometry.setDrawRange(0, Math.round(trendBot.progress * TREND_SEGMENTS) * TREND_RADIAL * 6);
        if (trendBot.progress >= 1) {
          trendBot.state = "admire";
          trendBot.timer = 0;
        }
        break;
      }
      case "admire":
        status.trend = "Trend found. Flagging a possible changepoint";
        trendBot.timer += dt;
        face(rig, Math.PI / 4, dt);
        pose(rig, { armL: -2.9, armR: -2.9, armLz: -0.2, armRz: 0.2 }, dt);
        rig.body.position.y = Math.abs(Math.sin(trendBot.timer * 8)) * 0.15;
        if (trendBot.timer > 2.2) {
          trendBot.state = "erase";
          trendBot.timer = 0;
        }
        break;
      case "erase":
        status.trend = "Wiping the board for the next variable";
        trendBot.timer += dt;
        face(rig, -Math.PI / 2, dt);
        pose(rig, { armR: -1.9, armRz: Math.sin(trendBot.timer * 14) * 0.5 }, dt);
        trendBot.progress = Math.max(0, 1 - trendBot.timer / 1.2);
        mesh.geometry.setDrawRange(0, Math.round(trendBot.progress * TREND_SEGMENTS) * TREND_RADIAL * 6);
        if (trendBot.timer > 1.3) {
          newTrendLine();
          trendBot.state = "draw";
          trendBot.progress = 0;
        }
        break;
    }
  }

  const spatialBot = { state: "walk" as "walk" | "probe", site: 1, timer: 0, probed: false };
  function updateSpatial(dt: number) {
    const rig = rigs.spatial;
    switch (spatialBot.state) {
      case "walk":
        status.spatial = "Walking to the next grid cell";
        pose(rig, { armR: -0.2 }, dt);
        if (moveTo(rig, PROBE_SITES[spatialBot.site], dt, 1.3)) {
          spatialBot.state = "probe";
          spatialBot.timer = 0;
          spatialBot.probed = false;
        } else walkCycle(rig, dt, false);
        break;
      case "probe": {
        spatialBot.timer += dt;
        const tt = spatialBot.timer;
        status.spatial = "Sampling soil moisture in this cell";
        if (tt < 0.6) pose(rig, { armR: -0.9, headX: 0.4 }, dt);
        else pose(rig, { armR: -0.35, headX: 0.5, crouch: 0.15 }, dt);
        if (tt > 0.7 && !spatialBot.probed) {
          spatialBot.probed = true;
          const fwd = rig.root.rotation.y;
          const px = rig.root.position.x + Math.sin(fwd) * 0.45 + Math.cos(fwd) * 0.3;
          const pz = rig.root.position.z + Math.cos(fwd) * 0.45 - Math.sin(fwd) * 0.3;
          spawnRipple(px, pz, Math.random() > 0.5 ? "#38bdf8" : "#eb6834");
        }
        if (tt > 1.8) {
          spatialBot.state = "walk";
          spatialBot.site = (spatialBot.site + 1) % PROBE_SITES.length;
        }
        break;
      }
    }
  }

  let skepticTimer = 0;
  function updateSkeptic(dt: number, t: number) {
    const rig = rigs.skeptic;
    skepticTimer += dt;
    const cycle = skepticTimer % 7.5;
    if (cycle < 4.5) {
      status.skeptic = "Looking for a second line of evidence";
      doubt.sprite.visible = false;
      face(rig, Math.PI / 2, dt);
      pose(rig, { armL: -1.1, armR: -0.9, headX: 0.35 + Math.sin(t * 1.5) * 0.05 }, dt);
    } else {
      status.skeptic = "Not convinced. Is the effect big enough to matter?";
      doubt.sprite.visible = true;
      doubt.sprite.position.y = 2.6 + Math.sin(t * 6) * 0.06;
      face(rig, Math.PI / 4, dt);
      pose(rig, { armL: -1.4, armR: -1.4, armLz: -0.9, armRz: 0.9, headY: Math.sin(t * 9) * 0.45 }, dt);
    }
  }

  const reportBot = { state: "wait" as "wait" | "pick" | "toArchive" | "file" | "back", timer: 0 };
  function updateReport(dt: number, t: number) {
    const rig = rigs.report;
    switch (reportBot.state) {
      case "wait":
        status.report = "Waiting for a checked result to file";
        face(rig, Math.PI, dt);
        pose(rig, { headY: Math.sin(t * 0.7) * 0.5 }, dt);
        if (pendingReports > 0) {
          pendingReports -= 1;
          reportBot.state = "pick";
          reportBot.timer = 0;
          printedPaper.visible = true;
        }
        break;
      case "pick": {
        status.report = "Printing the finding report";
        reportBot.timer += dt;
        face(rig, Math.PI, dt);
        printedPaper.position.z = -3.9 + Math.min(1, reportBot.timer / 0.8) * 0.3;
        pose(rig, { armL: -1.2, armR: -1.2, headX: 0.3 }, dt);
        if (reportBot.timer > 1.1) {
          printedPaper.visible = false;
          printedPaper.position.z = -3.9;
          heldPaper.visible = true;
          reportBot.state = "toArchive";
        }
        break;
      }
      case "toArchive":
        status.report = "Filing the finding with its citations";
        pose(rig, { armL: -1.0, armR: -1.0 }, dt);
        if (moveTo(rig, ARCHIVE_SPOT, dt, 1.5)) {
          reportBot.state = "file";
          reportBot.timer = 0;
        } else walkCycle(rig, dt, true);
        break;
      case "file":
        status.report = "Saved as a scientific finding";
        reportBot.timer += dt;
        face(rig, 0, dt);
        pose(rig, { armL: -1.6, armR: -1.6 }, dt);
        if (reportBot.timer > 0.5 && heldPaper.visible) {
          heldPaper.visible = false;
          bumpCounter();
          spawnRipple(-1.6, 4.0, "#a78bfa");
        }
        if (reportBot.timer > 0.9) reportBot.state = "back";
        break;
      case "back":
        status.report = "Heading back to the printer";
        pose(rig, {}, dt);
        if (moveTo(rig, PRINTER_SPOT, dt, 1.6)) reportBot.state = "wait";
        else walkCycle(rig, dt, false);
        break;
    }
  }

  // ---------------------------------------------------------------- world tick

  const satPos = new THREE.Vector3();
  const receiverPos = new THREE.Vector3();
  let packetTimer = 0;
  let screenTimer = 0;

  function update(dt: number, t: number) {
    world.position.y = Math.sin(t * 0.6) * 0.08;

    // satellite orbit + downlink
    const a = t * 0.22;
    satellite.position.set(Math.cos(a) * ORBIT_R, 0, Math.sin(a) * ORBIT_R);
    satellite.rotation.y = -a;
    satBlink.visible = Math.sin(t * 6) > 0;
    satellite.getWorldPosition(satPos);
    dishYaw.rotation.y = damp(dishYaw.rotation.y, Math.atan2(satPos.x + 4, satPos.z + 3.6), 2, dt);

    receiver.getWorldPosition(receiverPos);
    packetTimer -= dt;
    if (packetTimer <= 0) {
      packetTimer = 0.7;
      const m = new THREE.Mesh(packetGeo, packetMat);
      scene.add(m);
      packets.push({ mesh: m, life: 1, from: satPos.clone(), to: receiverPos.clone() });
    }
    for (let i = packets.length - 1; i >= 0; i--) {
      const p = packets[i];
      p.life -= dt / 1.3;
      if (p.life <= 0) {
        scene.remove(p.mesh);
        packets.splice(i, 1);
        receiverMat.color.set("#ffffff");
        continue;
      }
      p.mesh.position.lerpVectors(p.from!, p.to!, 1 - p.life);
      p.mesh.rotation.x += dt * 3;
      p.mesh.rotation.y += dt * 2;
    }
    receiverMat.color.lerp(new THREE.Color("#38bdf8"), Math.min(1, dt * 4));

    for (let i = ripples.length - 1; i >= 0; i--) {
      const r = ripples[i];
      r.life -= dt / 1.4;
      if (r.life <= 0) {
        world.remove(r.mesh);
        (r.mesh.material as THREE.Material).dispose();
        ripples.splice(i, 1);
        continue;
      }
      r.mesh.scale.setScalar(1 + (1 - r.life) * 5);
      (r.mesh.material as THREE.MeshBasicMaterial).opacity = r.life;
    }

    screenTimer += dt;
    if (screenTimer > 0.3) {
      screenTimer = 0;
      screenFlash = Math.max(0, screenFlash - 0.3);
      drawScreen();
    }
    printerLed.visible = reportBot.state !== "pick" || Math.sin(t * 20) > 0;

    clouds.forEach((c, i) => {
      c.position.x += dt * (0.25 + i * 0.08);
      if (c.position.x > 10) c.position.x = -10;
    });
    trees.forEach((tr, i) => (tr.rotation.z = Math.sin(t * 1.2 + i) * 0.02));

    updateData(dt);
    updateStats(dt, t);
    updateTrend(dt, t);
    updateSpatial(dt);
    updateSkeptic(dt, t);
    updateReport(dt, t);

    if (selected) {
      const r = rigs[selected].root.position;
      selectRing.visible = true;
      selectRing.position.set(r.x, 0.04, r.z);
      selectRing.scale.setScalar(1 + Math.sin(t * 5) * 0.08);
    } else selectRing.visible = false;
  }

  // ---------------------------------------------------------------- theme

  function applyTheme() {
    const light = document.documentElement.getAttribute("data-theme") === "light";
    if (light) {
      hemi.color.set("#fff6dc");
      hemi.groundColor.set("#8a6a3c");
      hemi.intensity = 1.6;
      sun.color.set("#fff1d0");
      sun.intensity = 2.2;
      screenLight.intensity = 0;
      cloudMat.opacity = 0.95;
    } else {
      hemi.color.set("#7d93d6");
      hemi.groundColor.set("#1a1f33");
      hemi.intensity = 1.1;
      sun.color.set("#b9cdfc");
      sun.intensity = 1.3;
      screenLight.intensity = 6;
      cloudMat.opacity = 0.35;
    }
  }
  applyTheme();
  const themeObserver = new MutationObserver(() => {
    applyTheme();
    if (reducedMotion) render();
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---------------------------------------------------------------- camera + input

  let userAz = 0;
  let pointerAz = 0;
  let autoAz = 0;
  // World units that must stay in frame: the island is ~17 wide on screen,
  // so the narrow limit crops the far corners slightly on phones.
  const VIEW_W = 16.5;
  const VIEW_H = 11.4;

  function layoutCamera() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    renderer.domElement.style.width = `${w}px`;
    renderer.domElement.style.height = `${h}px`;
    // On phones the tags pile on top of each other; the chips below the
    // canvas name the agents instead.
    tagSprites.forEach((sp) => (sp.visible = w >= 520));
    const aspect = w / h;
    let halfH = VIEW_H / 2;
    if (aspect * halfH * 2 < VIEW_W) halfH = VIEW_W / aspect / 2;
    camera.left = -halfH * aspect;
    camera.right = halfH * aspect;
    camera.top = halfH;
    camera.bottom = -halfH;
    camera.updateProjectionMatrix();
  }
  function placeCamera() {
    const az = Math.PI / 4 + autoAz + userAz + pointerAz;
    camera.position.set(Math.sin(az) * 18, 10.4, Math.cos(az) * 18);
    camera.lookAt(0, 0.6, 0);
  }

  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  function agentAt(e: PointerEvent): AgentId | null {
    const rect = renderer.domElement.getBoundingClientRect();
    ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(
      AGENTS.map((a) => rigs[a.id].root),
      true,
    );
    for (const h of hits) {
      if (h.object instanceof THREE.Sprite) continue;
      const id = h.object.userData.agentId as AgentId | undefined;
      if (id) return id;
    }
    return null;
  }

  let dragging = false;
  let dragStartX = 0;
  let dragLastX = 0;
  const onDown = (e: PointerEvent) => {
    dragging = true;
    dragStartX = dragLastX = e.clientX;
  };
  const onMove = (e: PointerEvent) => {
    const rect = renderer.domElement.getBoundingClientRect();
    if (dragging && e.pointerType === "mouse") {
      userAz -= (e.clientX - dragLastX) * 0.006;
      dragLastX = e.clientX;
      if (reducedMotion) {
        placeCamera();
        render();
      }
    } else if (e.pointerType === "mouse") {
      pointerAz = (((e.clientX - rect.left) / rect.width) * 2 - 1) * -0.06;
    }
    renderer.domElement.style.cursor = dragging && Math.abs(e.clientX - dragStartX) > 4 ? "grabbing" : agentAt(e) ? "pointer" : "grab";
  };
  const onUp = (e: PointerEvent) => {
    const wasClick = Math.abs(e.clientX - dragStartX) < 5;
    dragging = false;
    if (wasClick) setSelected(agentAt(e), true);
  };
  const onLeave = () => {
    dragging = false;
    pointerAz = 0;
  };
  renderer.domElement.addEventListener("pointerdown", onDown);
  renderer.domElement.addEventListener("pointermove", onMove);
  renderer.domElement.addEventListener("pointerup", onUp);
  renderer.domElement.addEventListener("pointerleave", onLeave);

  function setSelected(id: AgentId | null, notify: boolean) {
    selected = id;
    if (reducedMotion) {
      update(0, simTime);
      render();
    }
    if (notify) opts.onSelect(id);
  }

  // ---------------------------------------------------------------- loop

  function render() {
    renderer.render(scene, camera);
  }

  let raf = 0;
  let last = 0;
  let simTime = 0;
  let onScreen = true;

  function tick(now: number) {
    raf = requestAnimationFrame(tick);
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    simTime += dt;
    autoAz = Math.sin(simTime * 0.08) * 0.3;
    update(dt, simTime);
    placeCamera();
    render();
  }
  function start() {
    if (raf || reducedMotion || !onScreen || document.hidden) return;
    last = performance.now();
    raf = requestAnimationFrame(tick);
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }

  layoutCamera();
  if (reducedMotion) {
    // Settle the crew into a representative mid-task frame, then hold still.
    for (let i = 0; i < 240; i++) update(1 / 60, (simTime += 1 / 60));
    placeCamera();
    render();
  } else {
    placeCamera();
    start();
  }

  const resizeObserver = new ResizeObserver(() => {
    layoutCamera();
    render();
  });
  resizeObserver.observe(container);

  const io = new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting;
    if (onScreen) start();
    else stop();
  });
  io.observe(container);

  const onVisibility = () => (document.hidden ? stop() : start());
  document.addEventListener("visibilitychange", onVisibility);

  return {
    getStatus: (id) => status[id],
    select: (id) => setSelected(id, false),
    dispose() {
      stop();
      resizeObserver.disconnect();
      io.disconnect();
      themeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerup", onUp);
      renderer.domElement.removeEventListener("pointerleave", onLeave);
      const geos = new Set<THREE.BufferGeometry>();
      const mats = new Set<THREE.Material>();
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Sprite) {
          geos.add(o.geometry);
          (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => mats.add(m));
        }
      });
      mats.forEach((m) => {
        const map = (m as THREE.MeshBasicMaterial).map;
        map?.dispose();
        m.dispose();
      });
      geos.forEach((g) => g.dispose());
      [packetGeo, rippleGeo].forEach((g) => g.dispose());
      packetMat.dispose();
      matCache.clear();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
