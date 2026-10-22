"""Marketing renders of the Mirae model (run after build_mirae.py, inside Blender).

    exec(open(r"D:/git/Mirae/cad/blender/render_marketing.py").read())

Renders the exact built geometry with Cycles: only materials, lights, a studio backdrop,
cameras and render-only detail on the purchased hardware (wheel hubs, caster ball, lens,
LED halos) are added. The printed parts are never modified.

Outputs (cad/renders/marketing/):
    hero.png                 3/4 front hero, 2560 x 1280 (2:1, downsizes to 1280 x 640)
    front.png side.png bottom.png   same lens + distance, so all three share one scale
    layout.json              projected pixel positions for the labels / dimension lines
Then run compose_views.py with the system Python to build views.png.
"""

import json
import math
import os

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

OUT = os.path.normpath(os.path.join(r"D:/git/Mirae/cad", "renders", "marketing"))
SAMPLES = globals().get("SAMPLES", 384)
SCALE = globals().get("SCALE", 1.0)  # resolution multiplier for quick tests

O = bpy.data.objects
PARTS = ["chassis", "battery-door", "pi-module", "top-cover", "faceplate", "sensor-mount"]
CENTER = Vector((0, 0, 72))


def collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    for ob in list(col.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)
    return col


def mat(name, color, rough=0.5, metal=0.0, coat=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def halo_mat(name, color, strength, radius):
    """Soft radial glow that fades to transparent (LED halo on the faceplate)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / radius,) * 3
    gr = nt.nodes.new("ShaderNodeTexGradient")
    gr.gradient_type = "SPHERICAL"
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation, pw.inputs[1].default_value = "POWER", 2.5
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], gr.inputs["Vector"])
    nt.links.new(gr.outputs["Fac"], pw.inputs[0])
    nt.links.new(pw.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def assign(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)


def mesh_obj(name, col, bm, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.location, ob.rotation_euler = loc, rot
    return ob


def cyl_bm(d, length, seg=96):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=seg, radius1=d / 2, radius2=d / 2, depth=length
    )
    return bm


def smooth(ob, angle=35):
    for p in ob.data.polygons:
        p.use_smooth = True
    if hasattr(ob.data, "set_sharp_from_angle"):
        ob.data.set_sharp_from_angle(angle=math.radians(angle))


# ---------------------------------------------------------------------------
def build_studio():
    sc = bpy.context.scene
    col = collection("Mirae_Studio")
    M = {
        "white": mat("mk_white", (0.88, 0.87, 0.84), rough=0.40),
        "face": mat("mk_face", (0.90, 0.89, 0.86), rough=0.33),
        "charcoal": mat("mk_charcoal", (0.018, 0.018, 0.02), rough=0.55),
        "black": mat("mk_black", (0.006, 0.006, 0.007), rough=0.25),
        "rubber": mat("mk_rubber", (0.012, 0.012, 0.012), rough=0.8),
        "hub": mat("mk_hub", (0.05, 0.05, 0.055), rough=0.45),
        "metal": mat("mk_metal", (0.62, 0.62, 0.64), rough=0.22, metal=1.0),
        "chrome": mat("mk_chrome", (0.9, 0.9, 0.92), rough=0.06, metal=1.0),
        "motor": mat("mk_motor", (0.35, 0.35, 0.37), rough=0.35, metal=1.0),
        "glass": mat("mk_lens", (0.005, 0.008, 0.015), rough=0.03, coat=1.0),
        "backdrop": mat("mk_backdrop", (0.36, 0.33, 0.30), rough=0.85),
        "led": mat("mk_led", (1, 0.85, 0.6), emit=(1.0, 0.72, 0.42), strength=40.0),
        "status": mat("mk_status", (1, 1, 1), emit=(0.85, 0.95, 1.0), strength=30.0),
    }
    for name, key in (
        ("chassis", "charcoal"),
        ("battery-door", "charcoal"),
        ("pi-module", "white"),
        ("top-cover", "white"),
        ("faceplate", "face"),
        ("sensor-mount", "black"),
    ):
        assign(O[name], M[key])
        smooth(O[name])

    # hide the plain hardware stand-ins that get render detail below, keep motors / caster body
    for ob in bpy.data.collections["Mirae_Reference"].objects:
        base = ob.name.split(".")[0]
        ob.hide_render = base not in (
            "ref_n20",
            "ref_encoder",
            "ref_caster_plate",
            "ref_caster_body",
        )
        if not ob.hide_render:
            assign(
                ob,
                M["motor"] if base in ("ref_n20", "ref_encoder", "ref_caster_body") else M["metal"],
            )

    # wheels: same 43 x 19 envelope and position as ref_wheel, with tyre radius + hub
    for ref in [o for o in O if o.name.startswith("ref_wheel")]:
        c = sum((ref.matrix_world @ v.co for v in ref.data.vertices), Vector()) / len(
            ref.data.vertices
        )
        s = 1 if c.x > 0 else -1
        tyre = mesh_obj("mk_tyre", col, cyl_bm(43.0, 19.0), c, (0, math.radians(90), 0))
        bev = tyre.modifiers.new("bev", "BEVEL")
        bev.width, bev.segments, bev.limit_method = 3.0, 6, "ANGLE"
        assign(tyre, M["rubber"])
        smooth(tyre, 60)
        hub = mesh_obj(
            "mk_hub", col, cyl_bm(26.0, 1.0), c + Vector((s * 9.3, 0, 0)), (0, math.radians(90), 0)
        )
        assign(hub, M["hub"])
        cap = mesh_obj(
            "mk_hubcap",
            col,
            cyl_bm(9.0, 1.4),
            c + Vector((s * 9.8, 0, 0)),
            (0, math.radians(90), 0),
        )
        assign(cap, M["metal"])
    # caster ball (same centre / diameter as the BCASTER-15-10K ball)
    cb = O["ref_caster_ball"]
    cc = sum((cb.matrix_world @ v.co for v in cb.data.vertices), Vector()) / len(cb.data.vertices)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=15.875 / 2)
    ball = mesh_obj("mk_ball", col, bm, (cc.x, cc.y, 15.875 / 2))
    assign(ball, M["chrome"])
    smooth(ball, 180)
    # camera lens behind the wall hole (Camera Module 3 housing front)
    ch = O["ref_cam_housing"]
    bb = [ch.matrix_world @ Vector(v) for v in ch.bound_box]
    lx = sum(v.x for v in bb) / 8
    lz = sum(v.z for v in bb) / 8
    ly = min(v.y for v in bb)
    lens = mesh_obj("mk_lens", col, cyl_bm(7.0, 1.0), (lx, ly + 0.5, lz), (math.radians(90), 0, 0))
    assign(lens, M["glass"])
    # LEDs: emissive dots + soft halos exactly on the faceplate LED positions
    for g in [o for o in O if o.name.startswith("ref_led_glow")]:
        c = sum((g.matrix_world @ v.co for v in g.data.vertices), Vector()) / len(g.data.vertices)
        d = max(g.dimensions.x, g.dimensions.z)
        status = d < 3.0
        dot = mesh_obj("mk_led", col, cyl_bm(d, 0.1, 48), c, (math.radians(90), 0, 0))
        assign(dot, M["status"] if status else M["led"])
        r = d * (2.2 if status else 3.2)
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=r)
        halo = mesh_obj("mk_halo", col, bm, c + Vector((0, -0.08, 0)), (math.radians(90), 0, 0))
        assign(
            halo,
            halo_mat(
                "mk_halo_" + ("s" if status else "e"),
                (0.85, 0.95, 1.0) if status else (1.0, 0.7, 0.4),
                6.0 if status else 9.0,
                r,
            ),
        )

    # cyclorama: floor sweeping up into a back wall (rotated to sit behind each camera)
    prof = [(-3000, 0)]
    R = 1600.0  # wide, soft sweep: reads as a gradient, not a horizon
    for k in range(41):
        a = math.radians(90 * k / 40)
        prof.append((400 + R * math.sin(a), R - R * math.cos(a)))
    prof.append((400 + R, 5000))
    bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-6000, 6000)]
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    cyc = mesh_obj("mk_cyclorama", col, bm)
    assign(cyc, M["backdrop"])
    smooth(cyc, 180)

    # light rig: emissive softboxes (scale independent), parented to an empty that turns with the shot
    rig = bpy.data.objects.new("mk_rig", None)
    col.objects.link(rig)
    boxes = [  # (size x, size y, location, strength) relative to a camera looking +Y from -Y
        ((700, 500), (-650, -450, 650), 5.5),  # key, front-left high
        ((500, 700), (700, -500, 600), 1.1),  # fill, right, high enough to keep the floor even
        ((900, 600), (0, 150, 1100), 2.6),  # top
        ((400, 800), (300, 600, 600), 2.2),  # rim, behind right
    ]
    for (sx, sy), loc, strength in boxes:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
        box = mesh_obj("mk_softbox", col, bm, loc)
        direction = (CENTER - Vector(loc)).normalized()
        box.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        em = mat(f"mk_softbox_{strength}", (0, 0, 0), emit=(1, 0.97, 0.93), strength=strength)
        assign(box, em)
        box.visible_camera = False
        box.visible_glossy = True
        box.parent = rig

    # world: soft warm grey, also the bottom-view background
    w = sc.world or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background") or w.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.30, 0.28, 0.26, 1)
    bg.inputs["Strength"].default_value = 0.35
    return col, cyc, rig


def setup_render(w, h):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "HIP"
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = d.type == "HIP"
    sc.cycles.device = "GPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = int(w * SCALE), int(h * SCALE)
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.render.image_settings.file_format = "PNG"


def camera(col, name, loc, target, lens, up=(0, 0, 1), shift_y=0.0):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width, cd.sensor_fit = lens, 36.0, "HORIZONTAL"
    cd.clip_start, cd.clip_end = 10.0, 20000.0
    cd.shift_y = shift_y
    cam = bpy.data.objects.new(name, cd)
    col.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = _look((Vector(target) - Vector(loc)).normalized(), Vector(up))
    return cam


def _look(d, up):
    z = -d
    x = up.cross(z).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_euler()


def project(cam, pts):
    sc = bpy.context.scene
    out = []
    for p in pts:
        v = world_to_camera_view(sc, cam, Vector(p))
        out.append((v.x * sc.render.resolution_x, (1 - v.y) * sc.render.resolution_y))
    return out


def render(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    col, cyc, rig = build_studio()
    for name in ("Mirae_Views",):
        vc = bpy.data.collections.get(name)
        if vc:
            for ob in vc.objects:
                ob.hide_render = True
    layout = {}

    # --- three matching views: one lens, one distance -> one scale --------------------------
    setup_render(1000, 1400)
    lens, dist = 135.0, 1100.0
    el = math.radians(3.0)
    shots = {
        "front": (
            Vector((0, -dist * math.cos(el), CENTER.z + dist * math.sin(el))),
            0.0,
            (0, 0, 1),
        ),
        "side": (
            Vector((-dist * math.cos(el), 0, CENTER.z + dist * math.sin(el))),
            -90.0,
            (0, 0, 1),
        ),
        "bottom": (Vector((0, 0, -dist)), None, (0, -1, 0)),
    }
    for name, (loc, rot_z, up) in shots.items():
        cam = camera(col, "mk_cam_" + name, loc, CENTER, lens, up=up, shift_y=-0.12)
        if rot_z is None:  # bottom: no floor, lights flipped under the robot
            cyc.hide_render = True
            rig.rotation_euler = (math.radians(180), 0, 0)
            bpy.context.scene.view_settings.exposure = 1.0
        else:
            bpy.context.scene.view_settings.exposure = 0.0
            cyc.hide_render = False
            cyc.rotation_euler = (0, 0, math.radians(rot_z))
            rig.rotation_euler = (0, 0, math.radians(rot_z))
        bpy.context.view_layer.update()
        render(cam, os.path.join(OUT, name + ".png"))
        if name == "front":
            layout[name] = {"dim": project(cam, [(-95, -105, 0), (95, -105, 0)]), "mm": 190}
        elif name == "side":
            layout[name] = {"dim": project(cam, [(-60, -105, 0), (-60, 105, 0)]), "mm": 210}
        else:
            layout[name] = {
                "caster": project(cam, [(0, -80, 0)])[0],
                "wheel": project(cam, [(70, 15, 0)])[0],
            }

    # --- hero: 3/4 front-left, 2:1 -------------------------------------------------------------
    setup_render(2560, 1280)
    bpy.context.scene.view_settings.exposure = 0.0
    cyc.hide_render = False
    az = math.radians(-35)  # camera azimuth around the robot (front = -Y)
    hd, he = 1200.0, math.radians(16)
    loc = Vector(
        (
            math.sin(az) * hd * math.cos(he),
            -math.cos(az) * hd * math.cos(he),
            60 + hd * math.sin(he),
        )
    )
    cyc.rotation_euler = (0, 0, az)
    rig.rotation_euler = (0, 0, az)
    hero = camera(col, "mk_cam_hero", loc, (0, -5, 58), 85.0)
    hero.data.shift_x = 0.0
    bpy.context.view_layer.update()
    render(hero, os.path.join(OUT, "hero.png"))

    with open(os.path.join(OUT, "layout.json"), "w") as f:
        json.dump(layout, f, indent=1)
    return layout


if globals().get("RUN", True):
    RESULT = main()
