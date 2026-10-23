import {
  DoubleSide,
  Mesh,
  MeshBasicMaterial,
  type Object3D,
  OrthographicCamera,
  PlaneGeometry,
  Scene,
  ShaderMaterial,
  WebGLRenderTarget,
  type WebGLRenderer,
} from "three";
import { HorizontalBlurShader } from "three/addons/shaders/HorizontalBlurShader.js";
import { VerticalBlurShader } from "three/addons/shaders/VerticalBlurShader.js";

/** Project the actual underside onto the floor once, with height-dependent density.
 * The robot never moves: only its camera does, so the texture stays valid at every angle.
 */
export function contactShadow(renderer: WebGLRenderer, model: Object3D): { floor: Mesh; destroy: () => void } {
  const size = 400;
  const shadow = new WebGLRenderTarget(512, 512);
  const scratch = new WebGLRenderTarget(512, 512, { depthBuffer: false });
  const scene = new Scene();
  scene.add(model.clone(true));
  const depth = new ShaderMaterial({
    side: DoubleSide,
    vertexShader: `varying float height;
      void main() {
        vec4 world = modelMatrix * vec4(position, 1.0);
        height = world.y;
        gl_Position = projectionMatrix * viewMatrix * world;
      }`,
    fragmentShader: `varying float height;
      void main() {
        float contact = pow(1.0 - clamp(height / 90.0, 0.0, 1.0), 1.3);
        gl_FragColor = vec4(0.0, 0.0, 0.0, contact * 0.95);
      }`,
  });
  scene.overrideMaterial = depth;
  const camera = new OrthographicCamera(-size / 2, size / 2, size / 2, -size / 2, 0.1, 150);
  camera.position.set(0, -1, 0);
  camera.up.set(0, 0, 1);
  camera.lookAt(0, 0, 0);

  const horizontal = new ShaderMaterial({
    ...HorizontalBlurShader,
    uniforms: { tDiffuse: { value: shadow.texture }, h: { value: 2.5 / 512 } },
    depthTest: false,
    depthWrite: false,
  });
  const vertical = new ShaderMaterial({
    ...VerticalBlurShader,
    uniforms: { tDiffuse: { value: scratch.texture }, v: { value: 2.5 / 512 } },
    depthTest: false,
    depthWrite: false,
  });
  const quad = new Mesh(new PlaneGeometry(2, 2), horizontal);
  const blur = new Scene();
  blur.add(quad);
  const flatCamera = new OrthographicCamera(-1, 1, 1, -1, 0, 2);
  flatCamera.position.z = 1;
  const previousTarget = renderer.getRenderTarget();
  const previousAlpha = renderer.getClearAlpha();
  renderer.setClearAlpha(0);
  renderer.setRenderTarget(shadow);
  renderer.render(scene, camera);
  for (let i = 0; i < 2; i++) {
    quad.material = horizontal;
    renderer.setRenderTarget(scratch);
    renderer.render(blur, flatCamera);
    quad.material = vertical;
    renderer.setRenderTarget(shadow);
    renderer.render(blur, flatCamera);
  }
  renderer.setRenderTarget(previousTarget);
  renderer.setClearAlpha(previousAlpha);
  depth.dispose();
  horizontal.dispose();
  vertical.dispose();
  quad.geometry.dispose();
  scratch.dispose();

  const floor = new Mesh(
    new PlaneGeometry(size, size),
    new MeshBasicMaterial({
      map: shadow.texture,
      transparent: true,
      depthWrite: false,
      side: DoubleSide,
      toneMapped: false,
    }),
  );
  floor.rotation.x = Math.PI / 2;
  floor.position.y = -0.15;
  return { floor, destroy: () => shadow.dispose() };
}
