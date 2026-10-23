/**
 * The assembly guide in 3D: one WebGL renderer for the whole page. The prebuilt
 * assembly model is loaded once; a step only changes which parts show, their
 * visibility and where the new parts start. Frames are drawn on demand, never in an idle loop.
 *
 * Parts keep the low-poly library's original colours and photo textures, with ink outlines.
 */
import {
  BackSide,
  Box3,
  type BufferGeometry,
  Color,
  DirectionalLight,
  HemisphereLight,
  LineSegments,
  Matrix4,
  Mesh,
  type Object3D,
  PerspectiveCamera,
  Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";

import { media } from "../../lib";
import model from "./model.json";

type Vec = readonly [number, number, number];

interface StepData {
  id: string;
  adds: readonly string[];
  after: readonly string[];
  focus: readonly string[];
  camera: { position: Vec; target: Vec };
  move?: Readonly<Record<string, Vec>>;
  lid?: { pivot: Vec; tilt: number; drop: number; split: number };
}

const STEPS = model.steps as unknown as readonly StepData[];
const GROUPS: Readonly<Record<string, readonly string[]>> = model.groups;
const LINE_PX = 1.1; // outline width in CSS pixels
const EASE = (t: number): number => 1 - (1 - t) ** 3; // the part settles into place

/** Fat-line geometry from an exported (indexed, quantized) LINES primitive. */
function segments(src: BufferGeometry): LineSegmentsGeometry {
  const pos = src.getAttribute("position");
  const index = src.getIndex();
  const n = index ? index.count : pos.count;
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const v = index ? index.getX(i) : i;
    out.set([pos.getX(v), pos.getY(v), pos.getZ(v)], i * 3); // getX de-normalizes quantized values
  }
  return new LineSegmentsGeometry().setPositions(out);
}

/** Silhouette: the back faces pushed out a fixed number of pixels, drawn in ink. */
function hullMaterial(ink: Color, resolution: Vector2): ShaderMaterial {
  return new ShaderMaterial({
    side: BackSide,
    uniforms: {
      ink: { value: new Vector3(...ink.clone().convertLinearToSRGB().toArray()) },
      resolution: { value: resolution },
      width: { value: LINE_PX },
    },
    vertexShader: /* glsl */ `
      uniform vec2 resolution;
      uniform float width;
      void main() {
        vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        vec2 dir = (projectionMatrix * vec4(normalMatrix * normal, 0.0)).xy;
        if (dot(dir, dir) > 0.0) clip.xy += normalize(dir) * width * 2.0 / resolution * clip.w;
        gl_Position = clip;
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 ink;
      void main() { gl_FragColor = vec4(ink, 1.0); }`,
  });
}

export interface Projected {
  /** Where the focus parts are now and where they seat, in fractions of the canvas. */
  at: [number, number];
  seat: [number, number];
  /** 0 = lifted out, 1 = seated. */
  k: number;
}

export class AssemblyStage {
  readonly ready: Promise<void>;
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  // a tight depth range: crease lines under the 0.6 mm skins must lose the depth test
  private readonly camera = new PerspectiveCamera(20, 4 / 3, 100, 4000);
  private readonly controls: OrbitControls;
  private readonly resolution = new Vector2(1, 1);
  private readonly lines: LineMaterial;
  private readonly hull: ShaderMaterial;
  private readonly parts = new Map<string, Object3D>();
  private readonly bounds = new Map<string, Box3>();
  private readonly home = new Map<string, Matrix4>();
  private readonly observer: ResizeObserver;
  private step: StepData | undefined;
  private k = 1;
  private raf = 0;
  private glideRaf = 0;
  private frameQueued = 0;

  /** Called after every drawn frame, with the focus parts projected for the arrow and label. */
  onFrame: ((p: Projected) => void) | undefined;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const ink = new Color(model.colors.ink);
    this.hull = hullMaterial(ink, this.resolution);
    this.lines = new LineMaterial({ color: ink, linewidth: LINE_PX, worldUnits: false });
    this.scene.add(new HemisphereLight(0xffffff, 0xb9b2a8, 2));
    const sun = new DirectionalLight(0xffffff, 2);
    sun.position.fromArray(model.sun).negate().multiplyScalar(1000);
    this.scene.add(sun);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = false; // no damping: frames only while the pointer moves
    this.controls.rotateSpeed = 0.5;
    this.controls.enablePan = false; // keep the step centred
    this.controls.enableZoom = false; // the wheel scrolls the guide, not the model
    canvas.style.touchAction = "pan-y"; // a vertical swipe scrolls the page; a sideways drag turns
    this.controls.addEventListener("change", () => this.requestFrame());

    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(canvas);
    this.ready = this.load();
  }

  private async load(): Promise<void> {
    const gltf = await new GLTFLoader().loadAsync(media("assembly/assembly.glb"));
    gltf.scene.updateMatrixWorld(true);
    const creases: LineSegments[] = [];
    gltf.scene.traverse((o: Object3D) => {
      if (o instanceof LineSegments && o.userData.asm_lines) creases.push(o as LineSegments);
      const id = o.userData.asm_id as string | undefined;
      if (!id) return;
      o.matrixAutoUpdate = false;
      o.updateMatrix();
      this.home.set(id, o.matrix.clone());
      this.parts.set(id, o);
      const bounds = new Box3();
      const inverse = o.matrixWorld.clone().invert();
      const meshes: Mesh[] = [];
      o.traverse((child) => {
        if (!(child instanceof Mesh)) return;
        const mesh = child as Mesh;
        mesh.geometry.computeBoundingBox();
        const box = mesh.geometry.boundingBox;
        if (box) bounds.union(box.clone().applyMatrix4(inverse.clone().multiply(child.matrixWorld)));
        meshes.push(mesh);
      });
      this.bounds.set(id, bounds);
      for (const mesh of meshes) mesh.add(new Mesh(mesh.geometry, this.hull));
    });
    // Each part's crease lines (exported beside it) ride along as a child of the part.
    for (const src of creases) {
      const part = this.parts.get(src.userData.asm_lines as string);
      const home = part && this.home.get(part.userData.asm_id as string);
      src.removeFromParent();
      if (!part || !home) continue;
      const lines = new LineSegments2(segments(src.geometry), this.lines);
      src.updateMatrix();
      lines.matrixAutoUpdate = false;
      lines.matrix.copy(home).invert().multiply(src.matrix);
      part.add(lines);
    }
    this.scene.add(gltf.scene);
  }

  /**
   * Show a step at its start (parts lifted out) and frame it like the illustration's camera, either
   * at once or, with `glideMs`, by moving the camera there from wherever it is (the watch mode).
   */
  show(id: string, k = 0, glideMs = 0): void {
    const step = STEPS.find((s) => s.id === id);
    if (!step) return;
    this.step = step;
    const shown = new Set<string>();
    for (const g of step.after) for (const p of GROUPS[g] ?? []) shown.add(p);
    for (const g of step.adds) for (const p of GROUPS[g] ?? []) shown.add(p);
    cancelAnimationFrame(this.raf); // a step left mid-insertion must not keep moving its parts
    for (const [pid, mesh] of this.parts) {
      mesh.visible = shown.has(pid);
      // every part starts seated; setProgress below lifts only this step's new parts
      const home = this.home.get(pid);
      if (home) {
        mesh.matrix.copy(home);
        mesh.matrixWorldNeedsUpdate = true;
      }
    }
    if (glideMs > 0) this.glide(glideMs);
    else this.resetView();
    this.setProgress(k);
  }

  private glide(ms: number): void {
    const step = this.step;
    if (!step) return;
    cancelAnimationFrame(this.glideRaf);
    const fromPos = this.camera.position.clone();
    const fromTarget = this.controls.target.clone();
    const toPos = new Vector3(...step.camera.position);
    const toTarget = new Vector3(...step.camera.target);
    const start = performance.now();
    const tick = (now: number): void => {
      const t = Math.min(1, (now - start) / ms);
      const e = t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2; // ease in and out
      this.camera.position.lerpVectors(fromPos, toPos, e);
      this.controls.target.lerpVectors(fromTarget, toTarget, e);
      this.controls.update();
      this.requestFrame();
      if (t < 1) this.glideRaf = requestAnimationFrame(tick);
    };
    this.glideRaf = requestAnimationFrame(tick);
  }

  resetView(): void {
    if (!this.step) return;
    cancelAnimationFrame(this.glideRaf);
    this.camera.position.set(...this.step.camera.position);
    this.controls.target.set(...this.step.camera.target);
    this.controls.update();
    this.requestFrame();
  }

  /** Pose the new parts: 0 = lifted out, 1 = seated. */
  setProgress(k: number): void {
    this.k = k;
    const step = this.step;
    if (!step) return;
    const e = EASE(k);
    const m = new Matrix4();
    for (const g of step.adds) {
      for (const pid of GROUPS[g] ?? []) {
        const mesh = this.parts.get(pid);
        const home = this.home.get(pid);
        if (!mesh || !home) continue;
        this.pose(step, pid, e, m);
        mesh.matrix.multiplyMatrices(m, home);
        mesh.matrixWorldNeedsUpdate = true;
      }
    }
    this.requestFrame();
  }

  /** Play the insertion from the start, like the part being pushed home, after `delayMs`. */
  play(ms = 1400, delayMs = 0): void {
    cancelAnimationFrame(this.raf);
    const start = performance.now() + delayMs;
    const tick = (now: number): void => {
      const t = Math.min(1, Math.max(0, (now - start) / ms));
      this.setProgress(t);
      if (t < 1) this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  get progress(): number {
    return this.k;
  }

  destroy(): void {
    cancelAnimationFrame(this.raf);
    cancelAnimationFrame(this.glideRaf);
    cancelAnimationFrame(this.frameQueued);
    this.observer.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
  }

  /** Same motion as render_assembly.py: a straight slide, or the lid's drop-and-swing. */
  private pose(step: StepData, pid: string, e: number, out: Matrix4): void {
    if (step.lid) {
      const { pivot, tilt, drop, split } = step.lid;
      const a = tilt * (1 - Math.max(0, (e - split) / (1 - split)));
      const lift = drop * (1 - Math.min(1, e / split));
      const p = new Vector3(...pivot);
      out
        .makeTranslation(0, lift, 0)
        .multiply(new Matrix4().makeTranslation(p.x, p.y, p.z))
        .multiply(new Matrix4().makeRotationX(-a))
        .multiply(new Matrix4().makeTranslation(-p.x, -p.y, -p.z));
      return;
    }
    const v = step.move?.[pid];
    out.identity();
    if (v) out.makeTranslation(v[0] * (1 - e), v[1] * (1 - e), v[2] * (1 - e));
  }

  private resize(): void {
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    // fit the illustration's 4:3 framing inside any panel: wider panels keep its height, taller
    // ones its width
    const halfX = Math.tan((model.fovX * Math.PI) / 360);
    this.camera.aspect = w / h;
    const halfY = halfX / Math.min(this.camera.aspect, model.aspect);
    this.camera.fov = (2 * Math.atan(halfY) * 180) / Math.PI;
    this.camera.updateProjectionMatrix();
    this.resolution.set(w, h);
    this.lines.resolution.set(w, h);
    this.requestFrame();
  }

  private requestFrame(): void {
    if (this.frameQueued) return;
    this.frameQueued = requestAnimationFrame(() => {
      this.frameQueued = 0;
      this.renderer.render(this.scene, this.camera);
      if (this.onFrame) {
        const p = this.project();
        if (p) this.onFrame(p);
      }
    });
  }

  private project(): Projected | undefined {
    const step = this.step;
    if (!step || this.parts.size === 0) return undefined;
    const now = new Box3();
    const seat = new Box3();
    for (const pid of step.focus) {
      const mesh = this.parts.get(pid);
      const home = this.home.get(pid);
      if (!mesh || !home) continue;
      const bb = this.bounds.get(pid);
      if (!bb) continue;
      now.union(bb.clone().applyMatrix4(mesh.matrix));
      seat.union(bb.clone().applyMatrix4(home));
    }
    const frac = (b: Box3): [number, number] => {
      const v = b.getCenter(new Vector3()).project(this.camera);
      return [(v.x + 1) / 2, (1 - v.y) / 2];
    };
    return { at: frac(now), seat: frac(seat), k: this.k };
  }
}
