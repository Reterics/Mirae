import { type Group, type Material, Mesh, Quaternion, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

import { media } from "../lib";
import type { EnvironmentCollider } from "./physics";

type Triple = [number, number, number];

/** media/house/colliders.json, exported from the same Blender scene as house.glb (glTF frame, metres). */
interface HouseManifest {
  model: string;
  spawn: { position: Triple; yaw: number };
  colliders: (
    | { name: string; surface: string; shape: "cuboid"; center: Triple; halfExtents: Triple }
    | { name: string; surface: string; shape: "cylinder"; center: Triple; halfHeight: number; radius: number }
    | { name: string; surface: string; shape: "convex"; points: Triple[] }
  )[];
}

// Ceiling-mounted parts: the orbit camera looks in from above and the key light shines down.
const HIDDEN = new Set(["Ceiling", "CeilingLight_Living", "CeilingLight_Bedroom", "Pendant_Dining"]);

/** Loads the flat and moves it so the manifest's spawn point sits at the origin, facing +Z. */
export async function loadHouse(): Promise<{ scene: Group; colliders: EnvironmentCollider[] }> {
  const response = await fetch(media("house/colliders.json"));
  if (!response.ok) throw new Error(`House colliders: HTTP ${String(response.status)}`);
  const manifest = (await response.json()) as HouseManifest;
  const gltf = await new GLTFLoader().loadAsync(media(`house/${manifest.model}`));
  const rotation = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), -manifest.spawn.yaw);
  const spawn = new Vector3(...manifest.spawn.position);
  const toSpawnFrame = (point: Triple): Vector3 => new Vector3(...point).sub(spawn).applyQuaternion(rotation);
  const scene = gltf.scene;
  scene.quaternion.copy(rotation);
  scene.position.copy(spawn).negate().applyQuaternion(rotation);
  scene.traverse((object) => {
    if (HIDDEN.has(object.name)) object.visible = false;
    if (object instanceof Mesh) {
      const material: Material | Material[] = (object as Mesh).material;
      const materials = Array.isArray(material) ? material : [material];
      object.castShadow = !materials.some((material) => material.transparent);
      object.receiveShadow = true;
    }
  });
  const colliders = manifest.colliders.map((part): EnvironmentCollider => {
    if (part.shape === "convex")
      return {
        shape: "convex",
        points: new Float32Array(part.points.flatMap((point) => toSpawnFrame(point).toArray())),
      };
    const center = toSpawnFrame(part.center);
    return part.shape === "cuboid"
      ? { shape: "cuboid", center, rotation, halfExtents: new Vector3(...part.halfExtents) }
      : { shape: "cylinder", center, rotation, halfHeight: part.halfHeight, radius: part.radius };
  });
  return { scene, colliders };
}
