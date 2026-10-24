import RAPIER from "@dimforge/rapier3d-compat";
import { Euler, Quaternion, Vector3 } from "three";

import type { DriveCommand } from "./drive";

export interface RobotGeometry {
  wheelX: number;
  axleZ: number;
  radius: number;
  wheelHalfWidth: number;
  casterZ: number;
  casterRadius: number;
}

export interface PhysicsSettings {
  slope: number;
  crossSlope: number;
  friction: number;
  torque: number;
  comHeight: number;
  comForward: number;
}

export const DEFAULT_SETTINGS: PhysicsSettings = {
  slope: 0,
  crossSlope: 0,
  friction: 0.7,
  torque: 196,
  comHeight: 60,
  comForward: 36,
};

/** A fixed obstacle or floor piece, already in the spawn frame (robot at the origin, facing +Z). */
export type EnvironmentCollider =
  | { shape: "cuboid"; center: Vector3; rotation: Quaternion; halfExtents: Vector3 }
  | { shape: "cylinder"; center: Vector3; rotation: Quaternion; halfHeight: number; radius: number }
  | { shape: "convex"; points: Float32Array };

export const FIXED_DT = 1 / 120;
// N20E-12-100 (HESTORE 100.429.00): 100 rpm at 12 V.
const MAX_WHEEL_SPEED = (100 * 2 * Math.PI) / 60;
export const TOTAL_MASS = 1.727;
const WHEEL_MASS = 0.0194;
// GG-KUB-30-B's Ø30 steel ball (maintainer); its housing is part of the body.
const BALL_MASS = 0.111;

/** SI units. Explicit wheel joints and a freely rotating caster; no scripted robot position. */
export class RobotPhysics {
  readonly world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  readonly body: RAPIER.RigidBody;
  readonly wheels: RAPIER.RigidBody[] = [];
  readonly caster: RAPIER.RigidBody;
  readonly joints: RAPIER.RevoluteImpulseJoint[] = [];
  readonly groundRotation: Quaternion;
  readonly wheelColliders: RAPIER.Collider[] = [];
  readonly ground: RAPIER.Collider[] = [];
  readonly casterCollider: RAPIER.Collider;
  private readonly commands = [0, 0];

  constructor(
    readonly geometry: RobotGeometry,
    readonly settings: PhysicsSettings,
    environment: readonly EnvironmentCollider[],
  ) {
    this.world.timestep = FIXED_DT;
    this.world.integrationParameters.numSolverIterations = 24;
    this.world.integrationParameters.numInternalPgsIterations = 4;
    this.world.integrationParameters.lengthUnit = 0.1;
    this.groundRotation = new Quaternion().setFromEuler(
      new Euler((-settings.slope * Math.PI) / 180, 0, (settings.crossSlope * Math.PI) / 180),
    );
    const groundBody = this.world.createRigidBody(RAPIER.RigidBodyDesc.fixed().setRotation(this.groundRotation));
    for (const part of environment) {
      let desc: RAPIER.ColliderDesc | null;
      if (part.shape === "convex") desc = RAPIER.ColliderDesc.convexHull(part.points);
      else {
        desc =
          part.shape === "cuboid"
            ? RAPIER.ColliderDesc.cuboid(part.halfExtents.x, part.halfExtents.y, part.halfExtents.z)
            : RAPIER.ColliderDesc.cylinder(part.halfHeight, part.radius);
        desc.setTranslation(part.center.x, part.center.y, part.center.z).setRotation(part.rotation);
      }
      if (!desc) throw new Error("Degenerate convex collider in the environment.");
      this.ground.push(this.world.createCollider(desc.setFriction(settings.friction).setRestitution(0), groundBody));
    }
    const spawn = new Vector3(0, 0.002, 0).applyQuaternion(this.groundRotation);
    this.body = this.world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(spawn.x, spawn.y, spawn.z)
        .setRotation(this.groundRotation)
        .setCanSleep(false)
        .setCcdEnabled(true),
    );
    const bodyMass = TOTAL_MASS - 2 * WHEEL_MASS - BALL_MASS;
    const com = {
      x: 0,
      y:
        ((TOTAL_MASS * settings.comHeight) / 1000 -
          2 * WHEEL_MASS * geometry.radius -
          BALL_MASS * geometry.casterRadius) /
        bodyMass,
      z:
        (TOTAL_MASS * (geometry.axleZ + settings.comForward / 1000) -
          2 * WHEEL_MASS * geometry.axleZ -
          BALL_MASS * geometry.casterZ) /
        bodyMass,
    };
    // Equivalent-box inertia is an explicit approximation until measured/CAD tensors are available.
    this.body.setAdditionalMassProperties(
      bodyMass,
      com,
      {
        x: (bodyMass * (0.145 ** 2 + 0.21 ** 2)) / 12,
        y: (bodyMass * (0.19 ** 2 + 0.21 ** 2)) / 12,
        z: (bodyMass * (0.19 ** 2 + 0.145 ** 2)) / 12,
      },
      { x: 0, y: 0, z: 0, w: 1 },
      true,
    );
    for (const [x, y, z, height] of [
      [0.083, 0.012, 0.092, 0.036],
      [0.074, 0.043, 0.078, 0.091],
    ] as const) {
      this.world.createCollider(
        RAPIER.ColliderDesc.cuboid(x, y, z).setTranslation(0, height, 0).setDensity(0).setFriction(settings.friction),
        this.body,
      );
    }
    for (const x of [geometry.wheelX, -geometry.wheelX]) {
      const local = new Vector3(x, geometry.radius, geometry.axleZ);
      const at = local.clone().applyQuaternion(this.groundRotation).add(spawn);
      const wheel = this.world.createRigidBody(
        RAPIER.RigidBodyDesc.dynamic()
          .setTranslation(at.x, at.y, at.z)
          .setRotation(this.groundRotation)
          .setCanSleep(false)
          .setCcdEnabled(true),
      );
      const rotation = new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), Math.PI / 2);
      this.wheelColliders.push(
        this.world.createCollider(
          RAPIER.ColliderDesc.cylinder(geometry.wheelHalfWidth, geometry.radius)
            .setRotation(rotation)
            .setMass(WHEEL_MASS)
            .setFriction(settings.friction)
            .setRestitution(0),
          wheel,
        ),
      );
      const joint = this.world.createImpulseJoint(
        RAPIER.JointData.revolute(local, { x: 0, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }),
        this.body,
        wheel,
        true,
      ) as RAPIER.RevoluteImpulseJoint;
      joint.setContactsEnabled(false);
      joint.configureMotorModel(RAPIER.MotorModel.ForceBased);
      joint.setMotorMaxForce(settings.torque / 1000);
      this.joints.push(joint);
      this.wheels.push(wheel);
    }
    const casterLocal = new Vector3(0, geometry.casterRadius, geometry.casterZ);
    const casterAt = casterLocal.clone().applyQuaternion(this.groundRotation).add(spawn);
    this.caster = this.world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(casterAt.x, casterAt.y, casterAt.z)
        .setRotation(this.groundRotation)
        .setCcdEnabled(true),
    );
    this.casterCollider = this.world.createCollider(
      RAPIER.ColliderDesc.ball(geometry.casterRadius)
        .setMass(BALL_MASS)
        .setFriction(settings.friction)
        .setRestitution(0),
      this.caster,
    );
    this.world
      .createImpulseJoint(RAPIER.JointData.spherical(casterLocal, { x: 0, y: 0, z: 0 }), this.body, this.caster, true)
      .setContactsEnabled(false);
  }

  step(drive: DriveCommand): void {
    const targets = [drive.left, drive.right];
    this.joints.forEach((joint, i) => {
      const current = this.commands[i] ?? 0;
      const target = targets[i] ?? 0;
      const next = current + Math.max(-FIXED_DT * 3, Math.min(FIXED_DT * 3, target - current));
      this.commands[i] = next;
      joint.configureMotorVelocity(next * MAX_WHEEL_SPEED, 0.15);
    });
    this.world.step();
  }

  contact(collider: RAPIER.Collider): boolean {
    return this.ground.some((ground) => {
      let touching = false;
      this.world.contactPair(ground, collider, (manifold) => {
        if (manifold.numSolverContacts() > 0) touching = true;
      });
      return touching;
    });
  }

  dispose(): void {
    this.world.free();
  }
}

export async function initPhysics(): Promise<void> {
  await RAPIER.init();
}
