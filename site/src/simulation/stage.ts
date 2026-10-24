import {
  AgXToneMapping,
  Box3,
  BufferGeometry,
  Color,
  DirectionalLight,
  Group,
  HemisphereLight,
  Line,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshStandardMaterial,
  type Object3D,
  OrthographicCamera,
  PCFShadowMap,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

import model from "../assembly/viewer/model.json";
import { media } from "../lib";
import type { DriveCommand } from "./drive";
import { loadHouse } from "./house";
import { type EnvironmentCollider, FIXED_DT, initPhysics, RobotPhysics, type PhysicsSettings } from "./physics";

// The key light follows the robot so its shadow frustum (±1.5 m) stays around it in the flat.
const KEY_OFFSET = new Vector3(-0.5, 1.5, 0.8);

export interface Telemetry {
  speed: number;
  acceleration: number;
  pitch: number;
  roll: number;
  contacts: readonly boolean[];
  wheelbase: number;
}

interface Highlight {
  material: MeshStandardMaterial;
  color: Color;
  emissive: Color;
  intensity: number;
  component: string;
}

function release(root: Object3D): void {
  root.traverse((object) => {
    if (object instanceof Mesh || object instanceof LineSegments || object instanceof Line) {
      const mesh = object as Mesh;
      mesh.geometry.dispose();
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        if (material instanceof MeshStandardMaterial) {
          material.map?.dispose();
          material.normalMap?.dispose();
          material.roughnessMap?.dispose();
          material.metalnessMap?.dispose();
        }
        material.dispose();
      }
    }
  });
}

/** A physics viewport and independent inset canvases, inside opaque HUD cards. */
export class SimulationStage {
  readonly ready: Promise<void>;
  private readonly renderer: WebGLRenderer;
  private readonly insetRenderers = new Map<
    HTMLCanvasElement,
    { renderer: WebGLRenderer; width: number; height: number }
  >();
  private readonly scene = new Scene();
  private readonly hudScene = new Scene();
  private readonly camera = new PerspectiveCamera(42, 1, 0.005, 30);
  private readonly hudCamera = new OrthographicCamera(-0.125, 0.125, 0.14, -0.14, 0.001, 2);
  private readonly firstPersonCamera = new PerspectiveCamera(41, 16 / 10, 0.002, 20);
  private readonly cameraMount = new Vector3();
  private readonly controls: OrbitControls;
  private readonly robot = new Group();
  private readonly terrain = new Group();
  private readonly key = new DirectionalLight(0xffffff, 3);
  private environment: readonly EnvironmentCollider[] = [];
  private readonly highlights: Highlight[] = [];
  private readonly wheelVisuals: { object: Object3D; side: number }[] = [];
  private readonly observer: ResizeObserver;
  private readonly parts = new Map<string, Object3D>();
  private physics: RobotPhysics | undefined;
  private drive: DriveCommand = { left: 0, right: 0 };
  private settings: PhysicsSettings;
  private paused = false;
  private showSupport = true;
  private peripherals = { camera: false, sensor: false };
  private raf = 0;
  private destroyed = false;
  private previousTime = 0;
  private accumulator = 0;
  private lastTelemetry = 0;
  private previousVelocity = new Vector3();
  private elapsedTelemetry = 0;
  private previousPosition = new Vector3();
  private support: Line | undefined;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    settings: PhysicsSettings,
    private readonly onTelemetry: (data: Telemetry) => void,
  ) {
    this.settings = settings;
    this.renderer = new WebGLRenderer({ canvas, antialias: true });
    this.renderer.toneMapping = AgXToneMapping;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFShadowMap;
    this.scene.background = new Color(0xeae6df);
    this.hudScene.background = new Color(0xf6f3ee);
    for (const scene of [this.scene, this.hudScene]) {
      scene.add(new HemisphereLight(0xffffff, 0x8f8272, 2.8));
      const key = scene === this.scene ? this.key : new DirectionalLight(0xffffff, 3);
      key.position.copy(KEY_OFFSET);
      if (scene === this.scene) {
        key.castShadow = true;
        key.shadow.mapSize.set(2048, 2048);
        Object.assign(key.shadow.camera, { left: -1.5, right: 1.5, top: 1.5, bottom: -1.5, near: 0.01, far: 8 });
        key.shadow.normalBias = 0.0005;
        key.shadow.bias = -0.0001;
        scene.add(key.target);
      }
      scene.add(key);
    }
    this.scene.add(this.terrain, this.robot);
    this.camera.position.set(0.43, 0.31, 0.51);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.set(0, 0.055, 0);
    this.controls.minDistance = 0.25;
    this.controls.maxDistance = 2.5;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.enableDamping = true;
    this.controls.update();
    this.hudCamera.position.set(0, 0.7, 0);
    this.hudCamera.up.set(0, 0, 1);
    this.hudCamera.lookAt(0, 0, 0);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(canvas);
    this.resize();
    this.ready = this.load();
  }

  private async load(): Promise<void> {
    const [gltf, exterior, house] = await Promise.all([
      new GLTFLoader().loadAsync(media("assembly/assembly.glb")),
      new GLTFLoader().loadAsync(media("turntable.glb")),
      loadHouse(),
      initPhysics(),
    ]);
    if (this.destroyed) {
      release(gltf.scene);
      release(exterior.scene);
      release(house.scene);
      return;
    }
    this.terrain.add(house.scene);
    this.environment = house.colliders;
    gltf.scene.updateMatrixWorld(true);
    const lines: Object3D[] = [];
    gltf.scene.traverse((object) => {
      if (object instanceof LineSegments) lines.push(object);
      const id: unknown = object.userData.asm_id;
      if (typeof id === "string") this.parts.set(id, object);
      if (object instanceof Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });
    for (const line of lines) {
      line.removeFromParent();
      release(line);
    }
    const groupIds: Readonly<Record<string, readonly string[]>> = model.groups;
    const groupBounds = (name: string): Box3 => {
      const box = new Box3();
      for (const id of groupIds[name] ?? []) {
        const part = this.parts.get(id);
        if (part) box.expandByObject(part);
      }
      return box;
    };
    // Dimensions and component positions come from the shipped GLB, in millimetres.
    const tyres = [...this.parts.values()].filter((object) => String(object.userData.source).startsWith("mk_tyre"));
    const tyre = tyres[0];
    const ball = [...this.parts.values()].find((object) => object.userData.source === "ref_caster_ball");
    if (!tyre || !ball) {
      release(gltf.scene);
      throw new Error("The robot model is missing its wheels or caster.");
    }
    const wheelBox = new Box3().setFromObject(tyre);
    const wheelCenter = wheelBox.getCenter(new Vector3()).multiplyScalar(0.001);
    const wheelSize = wheelBox.getSize(new Vector3()).multiplyScalar(0.001);
    const ballBox = new Box3().setFromObject(ball);
    const ballCenter = ballBox.getCenter(new Vector3()).multiplyScalar(0.001);
    const geometry = {
      wheelX: Math.abs(wheelCenter.x),
      axleZ: wheelCenter.z,
      radius: wheelSize.y / 2,
      wheelHalfWidth: wheelSize.x / 2,
      casterZ: ballCenter.z,
      casterRadius: ballCenter.y,
    };
    const lens = [...this.parts.values()].find((object) => object.userData.source === "cm_cam_lens");
    if (!lens) throw new Error("The robot model is missing its camera lens.");
    const lensBounds = new Box3().setFromObject(lens);
    this.cameraMount.copy(lensBounds.getCenter(new Vector3())).multiplyScalar(0.001);
    this.cameraMount.z = lensBounds.max.z * 0.001 + 0.001;
    const hud = gltf.scene.clone(true);
    hud.scale.setScalar(0.001);
    const componentById = new Map<string, string>();
    for (const name of ["motors", "wheels", "camera", "tof"])
      for (const id of groupIds[name] ?? []) componentById.set(id, name);
    hud.traverse((object) => {
      const id: unknown = object.userData.asm_id;
      if (typeof id !== "string") return;
      const covering = ["shell", "lid", "faceplate", "hat", "pi"].some((name) => groupIds[name]?.includes(id));
      if (covering) object.visible = false;
      const component = componentById.get(id);
      const side = object.position.x > 0 ? "left" : "right";
      object.traverse((child) => {
        if (!(child instanceof Mesh)) return;
        const mesh = child as Mesh;
        const materials = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).map((source) => {
          const material = source.clone();
          if (material instanceof MeshStandardMaterial) {
            if (groupIds.base?.includes(id)) {
              material.transparent = true;
              material.opacity = 0.18;
              material.depthWrite = false;
            }
            if (component)
              this.highlights.push({
                material,
                color: material.color.clone(),
                emissive: material.emissive.clone(),
                intensity: material.emissiveIntensity,
                component: component === "motors" || component === "wheels" ? side : component,
              });
          }
          return material;
        });
        mesh.material = materials.length === 1 && materials[0] ? materials[0] : materials;
      });
    });
    this.hudScene.add(hud);
    // Arrow anchors use the actual motor group bounds, split by side.
    const motorBounds = groupBounds("motors");
    const motorZ = motorBounds.getCenter(new Vector3()).z * 0.001;
    this.canvas.parentElement?.style.setProperty("--motor-y", `${(0.5 - motorZ / 0.28) * 100}%`);
    const exteriorWheels: Object3D[] = [];
    exterior.scene.traverse((object) => {
      if (/^mk_(hub|hubcap|tyre)(\.|$)/.test(object.name)) exteriorWheels.push(object);
      if (object instanceof Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });
    for (const object of exteriorWheels) {
      const side = object.position.x > 0 ? 0 : 1;
      const center = new Vector3((side === 0 ? 1 : -1) * geometry.wheelX, geometry.radius, geometry.axleZ);
      const pivot = new Group();
      pivot.position.copy(center);
      const original = object.position.clone().multiplyScalar(0.001);
      object.removeFromParent();
      object.position.copy(original.sub(center));
      object.scale.multiplyScalar(0.001);
      pivot.add(object);
      this.scene.add(pivot);
      this.wheelVisuals.push({ object: pivot, side });
    }
    exterior.scene.scale.setScalar(0.001);
    this.robot.add(exterior.scene);
    const points = [
      new Vector3(geometry.wheelX, 0.001, geometry.axleZ),
      new Vector3(-geometry.wheelX, 0.001, geometry.axleZ),
      new Vector3(0, 0.001, geometry.casterZ),
      new Vector3(geometry.wheelX, 0.001, geometry.axleZ),
    ];
    this.support = new Line(
      new BufferGeometry().setFromPoints(points),
      new LineBasicMaterial({ color: 0x9a5418, transparent: true, opacity: 0.65, depthTest: false }),
    );
    this.support.renderOrder = 9;
    this.robot.add(this.support);
    this.physics = new RobotPhysics(geometry, this.settings, this.environment);
    this.terrain.quaternion.copy(this.physics.groundRotation);
    this.raf = requestAnimationFrame(this.frame);
  }

  setInput(drive: DriveCommand, camera: boolean, sensor: boolean): void {
    this.drive = drive;
    this.peripherals = { camera, sensor };
  }
  setPaused(value: boolean): void {
    this.paused = value;
    this.accumulator = 0;
    this.previousVelocity.set(0, 0, 0);
    this.elapsedTelemetry = 0;
  }
  setSupportVisible(value: boolean): void {
    this.showSupport = value;
  }
  reset(settings: PhysicsSettings = this.settings): void {
    this.settings = settings;
    if (!this.physics) return;
    const geometry = this.physics.geometry;
    this.physics.dispose();
    this.physics = new RobotPhysics(geometry, settings, this.environment);
    this.terrain.quaternion.copy(this.physics.groundRotation);
    this.accumulator = 0;
    this.previousVelocity.set(0, 0, 0);
    this.elapsedTelemetry = 0;
  }
  stepOnce(): void {
    if (this.paused) {
      this.physics?.step(this.drive);
      this.elapsedTelemetry += FIXED_DT;
    }
  }

  private readonly frame = (now: number): void => {
    if (this.destroyed || !this.physics) return;
    const physics = this.physics;
    const elapsed = this.previousTime ? Math.min((now - this.previousTime) / 1000, 0.05) : 0;
    this.previousTime = now;
    if (!this.paused && !document.hidden) {
      this.accumulator += elapsed;
      while (this.accumulator >= FIXED_DT) {
        physics.step(this.drive);
        this.accumulator -= FIXED_DT;
        this.elapsedTelemetry += FIXED_DT;
      }
    }
    const position = physics.body.translation();
    this.robot.position.copy(position);
    this.robot.quaternion.copy(physics.body.rotation());
    for (const visual of this.wheelVisuals) {
      const wheel = physics.wheels[visual.side];
      if (wheel) {
        visual.object.position.copy(wheel.translation());
        visual.object.quaternion.copy(wheel.rotation());
      }
    }
    const delta = this.robot.position.clone().sub(this.previousPosition);
    this.camera.position.add(delta);
    this.controls.target.add(delta);
    this.previousPosition.copy(this.robot.position);
    this.controls.update();
    this.key.position.copy(this.robot.position).add(KEY_OFFSET);
    this.key.target.position.copy(this.robot.position);
    if (this.support) this.support.visible = this.showSupport;
    this.firstPersonCamera.position
      .copy(this.cameraMount)
      .applyQuaternion(this.robot.quaternion)
      .add(this.robot.position);
    this.firstPersonCamera.up.set(0, 1, 0).applyQuaternion(this.robot.quaternion);
    this.firstPersonCamera.lookAt(
      new Vector3(0, 0, 1).applyQuaternion(this.robot.quaternion).add(this.firstPersonCamera.position),
    );
    for (const h of this.highlights) {
      const active =
        h.component === "left"
          ? this.drive.left !== 0
          : h.component === "right"
            ? this.drive.right !== 0
            : h.component === "camera"
              ? this.peripherals.camera
              : this.peripherals.sensor;
      h.material.color.copy(active ? new Color(0xe8964a) : h.color);
      h.material.emissive.copy(active ? new Color(0xa85008) : h.emissive);
      h.material.emissiveIntensity = active ? 0.75 : h.intensity;
    }
    if (now - this.lastTelemetry > 100) {
      const velocity = new Vector3().copy(physics.body.linvel());
      const forward = new Vector3(0, 0, 1).applyQuaternion(this.robot.quaternion);
      const side = new Vector3(1, 0, 0).applyQuaternion(this.robot.quaternion);
      this.onTelemetry({
        speed: velocity.length(),
        acceleration:
          this.elapsedTelemetry > 0
            ? velocity.clone().sub(this.previousVelocity).dot(forward) / this.elapsedTelemetry
            : 0,
        pitch: (Math.asin(Math.max(-1, Math.min(1, forward.y))) * 180) / Math.PI,
        roll: (Math.asin(Math.max(-1, Math.min(1, side.y))) * 180) / Math.PI,
        contacts: [
          ...physics.wheelColliders.map((collider) => physics.contact(collider)),
          physics.contact(physics.casterCollider),
        ],
        wheelbase: (physics.geometry.casterZ - physics.geometry.axleZ) * 1000,
      });
      this.previousVelocity.copy(velocity);
      this.elapsedTelemetry = 0;
      this.lastTelemetry = now;
    }
    this.render();
    this.raf = requestAnimationFrame(this.frame);
  };

  private render(): void {
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    this.renderer.setScissorTest(false);
    this.renderer.setViewport(0, 0, width, height);
    this.renderer.render(this.scene, this.camera);
    for (const [selector, scene, camera] of [
      [".component-hud", this.hudScene, this.hudCamera],
      [".first-person-hud", this.scene, this.firstPersonCamera],
    ] as const) {
      const card = this.canvas.parentElement?.querySelector<HTMLDetailsElement>(selector);
      const area = card?.querySelector<HTMLElement>(".hud-render-area");
      const canvas = area?.querySelector("canvas");
      if (!card?.open || !area || !canvas) continue;
      let inset = this.insetRenderers.get(canvas);
      if (!inset) {
        const renderer = new WebGLRenderer({ canvas, antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.toneMapping = AgXToneMapping;
        inset = { renderer, width: 0, height: 0 };
        this.insetRenderers.set(canvas, inset);
      }
      const width = area.clientWidth;
      const height = area.clientHeight;
      if (inset.width !== width || inset.height !== height) {
        inset.renderer.setSize(width, height, false);
        inset.width = width;
        inset.height = height;
      }
      if (camera instanceof PerspectiveCamera) {
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      }
      const supportVisible = this.support?.visible;
      if (this.support && scene === this.scene) this.support.visible = false;
      inset.renderer.render(scene, camera);
      if (this.support && supportVisible !== undefined) this.support.visible = supportVisible;
    }
  }

  private resize(): void {
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  dispose(): void {
    this.destroyed = true;
    cancelAnimationFrame(this.raf);
    this.observer.disconnect();
    this.controls.dispose();
    this.physics?.dispose();
    for (const inset of this.insetRenderers.values()) inset.renderer.dispose();
    this.insetRenderers.clear();
    release(this.scene);
    release(this.hudScene);
    this.renderer.dispose();
  }
}
