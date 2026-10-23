import {
  AgXToneMapping,
  Box3,
  Color,
  CubeCamera,
  DirectionalLight,
  Group,
  HalfFloatType,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  type Object3D,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Scene,
  ShaderMaterial,
  type Texture,
  TextureLoader,
  Vector3,
  WebGLRenderer,
  WebGLCubeRenderTarget,
} from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

import { contactShadow } from "./contactShadow";
import { media } from "./lib";

const ASPECT = 1200 / 1000;
const HALF_X = 36 / (2 * 85); // render_web.py: 85 mm lens, 36 mm horizontal sensor
const ELEVATION = (17 * Math.PI) / 180;
const START = (-35 * Math.PI) / 180;
const TARGET = new Vector3(0, 62, 0);

/** The marketing render's softboxes, in glTF's Y-up coordinates. */
function studio(): Scene {
  const scene = new Scene();
  scene.background = new Color().setRGB(0.92, 0.9, 0.86).multiplyScalar(1.1);
  const boxes: [number, number, number, number, number, number][] = [
    [700, 500, -650, 650, 450, 5.5],
    [500, 700, 700, 600, 500, 1.1],
    [900, 600, 0, 1100, -150, 2.6],
    [400, 800, 300, 600, -600, 2.2],
  ];
  for (const [w, h, x, y, z, intensity] of boxes) {
    const box = new Mesh(
      new PlaneGeometry(w, h),
      new MeshBasicMaterial({ color: new Color().setRGB(1, 0.97, 0.93).multiplyScalar(intensity) }),
    );
    box.position.set(x, y, z);
    box.lookAt(0, 72, 0);
    scene.add(box);
  }
  return scene;
}

/** Release GLB and generated geometry/materials, including a late load after unmount. */
function dispose(root: Object3D): void {
  root.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    const mesh = o as Mesh;
    mesh.geometry.dispose();
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) m.dispose();
  });
}

/** Scroll-driven PBR rendering; no animation loop runs while the page is idle. */
export class Turntable {
  readonly ready: Promise<void>;
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(20, ASPECT, 100, 2000);
  private readonly rig = new Group();
  private readonly observer: ResizeObserver;
  private environment: ReturnType<PMREMGenerator["fromScene"]> | undefined;
  private shadow: ReturnType<typeof contactShadow> | undefined;
  private occlusion: Texture | undefined;
  private reflection: ReturnType<PMREMGenerator["fromCubemap"]> | undefined;
  private progress = 0;
  private queued = 0;
  private destroyed = false;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.toneMapping = AgXToneMapping;
    this.renderer.toneMappingExposure = 2 ** 0.35;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFShadowMap;

    const room = studio();
    const pmrem = new PMREMGenerator(this.renderer);
    // PMREM's background cube is only one unit wide. A near plane of 1 clips
    // it out and silently removes the studio's broad background fill light.
    this.environment = pmrem.fromScene(room, 0, 0.1, 10000);
    this.scene.environment = this.environment.texture;
    pmrem.dispose();
    dispose(room);

    // PMREM supplies the broad studio light; the weak key shades local recesses.
    const key = new DirectionalLight(0xfff7ed, 0.15);
    key.position.set(-650, 650, 450);
    key.target.position.copy(TARGET);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    Object.assign(key.shadow.camera, { left: -180, right: 180, top: 180, bottom: -180, near: 100, far: 1600 });
    key.shadow.normalBias = 0.15;
    key.shadow.bias = -0.0001;
    key.shadow.radius = 4;
    this.rig.add(key, key.target);
    this.scene.add(this.rig);

    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(canvas);
    this.ready = this.load();
  }

  private async load(): Promise<void> {
    const [modelResult, textureResult] = await Promise.allSettled([
      new GLTFLoader().loadAsync(media("turntable.glb")),
      new TextureLoader().loadAsync(media("turntable-ao.webp")),
    ]);
    if (modelResult.status === "rejected" || textureResult.status === "rejected") {
      if (modelResult.status === "fulfilled") dispose(modelResult.value.scene);
      if (textureResult.status === "fulfilled") textureResult.value.dispose();
      throw new Error("Could not load turntable media");
    }
    const model = modelResult.value.scene;
    const occlusion = textureResult.value;
    if (this.destroyed) {
      dispose(model);
      occlusion.dispose();
      return;
    }
    occlusion.flipY = false;
    occlusion.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    this.occlusion = occlusion;
    const leds: Mesh[] = [];
    model.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      const mesh = o as Mesh;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const materials = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).map((material) => {
        if (material instanceof MeshStandardMaterial) {
          material.aoMap = occlusion;
          material.aoMapIntensity = 1;
          material.needsUpdate = true;
        }
        // Calibrate dark plastics against the Cycles reference: the environment's
        // specular contribution otherwise lifts charcoal and rubber to grey.
        if (
          material instanceof MeshStandardMaterial &&
          ["mk_charcoal", "mk_rubber", "mk_lens"].includes(material.name)
        ) {
          const dark = new MeshPhysicalMaterial({
            color: material.color.clone().multiplyScalar(material.name === "mk_charcoal" ? 0.75 : 1),
            roughness: Math.max(0.4, material.roughness),
            specularIntensity: 0.1,
            aoMap: occlusion,
            aoMapIntensity: 1,
            side: material.side,
          });
          dark.name = material.name;
          return dark;
        }
        if (material instanceof MeshStandardMaterial && (mesh.name === "top-cover" || mesh.name === "faceplate")) {
          const skin = material.clone();
          skin.aoMapIntensity = mesh.name === "top-cover" ? 0.35 : 0.55;
          // Separate fitted skins meet coplanar faces in the CAD export. Give
          // them a stable depth order instead of a flickering dotted seam.
          skin.polygonOffset = true;
          skin.polygonOffsetFactor = -1;
          skin.polygonOffsetUnits = -2;
          return skin;
        }
        return material;
      });
      mesh.material = Array.isArray(mesh.material) ? materials : (materials[0] ?? mesh.material);
      if (mesh.name.startsWith("mk_led")) leds.push(mesh);
    });
    model.updateMatrixWorld(true);
    this.shadow = contactShadow(this.renderer, model);
    this.scene.add(this.shadow.floor);
    for (const led of leds) {
      const bounds = new Box3().setFromObject(led);
      const size = bounds.getSize(new Vector3());
      const status = size.x < 3;
      const radius = size.x * (status ? 2.2 : 3.2);
      const halo = new Mesh(
        new PlaneGeometry(radius * 2, radius * 2),
        new ShaderMaterial({
          transparent: true,
          depthWrite: false,
          uniforms: { tint: { value: new Color(status ? "#e7f7ff" : "#fff0df").convertLinearToSRGB() } },
          vertexShader: `varying vec2 vUv;
            void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
          fragmentShader: `varying vec2 vUv; uniform vec3 tint;
            void main() {
              float r = length(vUv - 0.5) * 2.0;
              float a = exp(-r * r * 2.0) * (1.0 - smoothstep(0.6, 1.0, r));
              gl_FragColor = vec4(tint, a * 0.95);
            }`,
        }),
      );
      halo.position.copy(bounds.getCenter(new Vector3()));
      halo.position.z = bounds.max.z + 0.5;
      model.add(halo);
    }
    this.scene.add(model);
    this.reflectCaster(model);
    this.resize();
    this.render(); // ready only resolves after the first complete frame
  }

  /** The ball reflects the chassis above it and paper below it, rather than an
   * unobstructed studio sky. Capture once because the assembled model is static.
   */
  private reflectCaster(model: Object3D): void {
    const ball = model.getObjectByName("mk_ball") as Mesh | undefined;
    if (!ball || !(ball.material instanceof MeshStandardMaterial)) return;
    const cube = new WebGLCubeRenderTarget(128, { type: HalfFloatType });
    const probe = new CubeCamera(0.1, 2000, cube);
    new Box3().setFromObject(ball).getCenter(probe.position);
    const background = this.scene.background;
    this.scene.background = new Color("#f6f3ee");
    ball.visible = false;
    probe.update(this.renderer, this.scene);
    ball.visible = true;
    this.scene.background = background;
    const pmrem = new PMREMGenerator(this.renderer);
    this.reflection = pmrem.fromCubemap(cube.texture);
    ball.material.envMap = this.reflection.texture;
    ball.material.envMapIntensity = 0.65;
    ball.material.roughness = 0.2;
    ball.material.needsUpdate = true;
    pmrem.dispose();
    cube.dispose();
  }

  show(progress: number): void {
    this.progress = Math.max(0, Math.min(1, progress));
    this.requestFrame();
  }

  private resize(): void {
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (!w || !h || this.destroyed) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.fov = (2 * Math.atan(HALF_X / Math.min(this.camera.aspect, ASPECT)) * 180) / Math.PI;
    this.camera.updateProjectionMatrix();
    this.requestFrame();
  }

  private requestFrame(): void {
    if (this.queued || this.destroyed) return;
    this.queued = requestAnimationFrame(() => {
      this.queued = 0;
      this.render();
    });
  }

  private render(): void {
    if (this.destroyed) return;
    const az = START + this.progress * Math.PI * 2;
    this.camera.position.set(
      Math.sin(az) * 900 * Math.cos(ELEVATION),
      62 + 900 * Math.sin(ELEVATION),
      Math.cos(az) * 900 * Math.cos(ELEVATION),
    );
    this.camera.lookAt(TARGET);
    // Blender turns its camera and lights together; rotate the environment as well.
    this.rig.rotation.y = -az;
    this.scene.environmentRotation.y = -az;
    this.renderer.render(this.scene, this.camera);
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    cancelAnimationFrame(this.queued);
    this.observer.disconnect();
    this.scene.traverse((o) => {
      if (o instanceof DirectionalLight) o.shadow.dispose();
    });
    dispose(this.scene);
    this.environment?.dispose();
    this.shadow?.destroy();
    this.occlusion?.dispose();
    this.reflection?.dispose();
    this.renderer.dispose();
  }
}
