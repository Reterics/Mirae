"""Lifestyle marketing renders: the exact Mirae model in a furnished living room.

    python cad/blender/fetch_assets.py          # once: CC0 assets from Poly Haven
    exec(open(r"D:/git/Mirae/cad/blender/render_lifestyle.py").read())   # in Blender

Reuses the materials and hardware detail from render_marketing.py, then builds a room
around the untouched model: Poly Haven HDRI, laminate floor and real furniture models
(sofa, coffee table, plant, books, cushions), plaster walls, a window whose sun casts a
pane-patterned light patch on the floor where the robot stands, a rim light, and shallow
depth of field. The printed parts are never modified.

Outputs (cad/renders/marketing/):
    home_hero.png     2560 x 1280  (2:1, GitHub social preview / README / web hero)
    home_square.png   2048 x 2048  (1:1 social)
    home_portrait.png 1638 x 2048  (4:5 social)
    home_side.png     2560 x 1440  (16:9, side profile)
    cutout.png        2048 x 2048  transparent PNG with contact shadow (store / crowdfunding)
"""

import math
import os

import bmesh
import bpy
from mathutils import Vector

ASSETS = r"D:/git/Mirae/cad/renders/assets"
HDRI = os.path.join(ASSETS, "hdri", "photo_studio_loft_hall_4k.hdr")
FLOOR = os.path.join(ASSETS, "laminate_floor_02", "laminate_floor_02_{}_2k.jpg")
MODELS = os.path.join(ASSETS, "models")
HDRI_ROT = globals().get("HDRI_ROT", 200.0)
SHOTS = globals().get("SHOTS", ("home_hero", "home_square", "home_portrait", "home_side", "cutout"))

WALL_Y, WALL_X = 1900.0, 1700.0  # room corner behind the robot
SUN_DIR = Vector((0.50, 0.70, -0.52)).normalized()  # window at front-left, light travels back-right

_g = {
    "__name__": "mk",
    "RUN": False,
    "SAMPLES": globals().get("SAMPLES", 512),
    "SCALE": globals().get("SCALE", 1.0),
}
exec(open(r"D:/git/Mirae/cad/blender/render_marketing.py").read(), _g)
OUT = _g["OUT"]
mesh_obj, assign, mat, smooth, cyl_bm = (
    _g["mesh_obj"],
    _g["assign"],
    _g["mat"],
    _g["smooth"],
    _g["cyl_bm"],
)


def node_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree


def floor_mat():
    m, nt = node_mat("mk_floor")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / 1400.0,) * 3  # ~1.4 m per texture tile
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(90))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    texs = {}
    for key in ("diff", "rough", "nor_gl"):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(FLOOR.format(key), check_existing=True)
        if key != "diff":
            t.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
        texs[key] = t
    nt.links.new(texs["diff"].outputs["Color"], bsdf.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value, rr.inputs["To Max"].default_value = 0.22, 0.55
    nt.links.new(texs["rough"].outputs["Color"], rr.inputs["Value"])
    nt.links.new(rr.outputs[0], bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.6
    nt.links.new(texs["nor_gl"].outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def plaster_mat():
    m, nt = node_mat("mk_plaster")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.80, 0.77, 0.72, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.05
    nz.inputs["Detail"].default_value = 10.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def box(name, col, size, loc, m, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    ob = mesh_obj(name, col, bm, loc)
    if bevel:
        mod = ob.modifiers.new("bev", "BEVEL")
        mod.width, mod.segments = bevel, 3
    assign(ob, m)
    return ob


def import_model(col, name, loc, rot_z=0.0, scale=1.0):
    """Import a Poly Haven glTF (already in mm via the scene unit scale) and place it."""
    d = os.path.join(MODELS, name)
    path = next(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".gltf"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new("mk_" + name, None)
    col.objects.link(root)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        if o.parent is None:
            o.parent = root
    root.location, root.rotation_euler, root.scale = loc, (0, 0, math.radians(rot_z)), (scale,) * 3
    return root


def build_home():
    col, cyc, rig = _g["build_studio"]()
    cyc.hide_render = True
    for ch in rig.children:
        ch.hide_render = True
    sc = bpy.context.scene
    room = _g["collection"]("Mirae_Home")

    # world: interior HDRI, kept low so the window sun carries the image
    w = sc.world
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(HDRI_ROT))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.55
    nt.links.new(bg.outputs[0], out.inputs[0])

    # floor, walls, skirting
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6000)
    floor = mesh_obj("mk_floor", room, bm)
    assign(floor, floor_mat())
    plaster = plaster_mat()
    skirt = mat("mk_skirting", (0.86, 0.85, 0.82), rough=0.4)
    box("mk_wall", room, (8000, 40, 2800), (0, WALL_Y + 20, 1400), plaster)
    box("mk_wall", room, (40, 8000, 2800), (WALL_X + 20, 0, 1400), plaster)
    box("mk_skirt", room, (8000, 16, 90), (0, WALL_Y - 8, 45), skirt, 2.0)
    box("mk_skirt", room, (16, 8000, 90), (WALL_X - 8, 0, 45), skirt, 2.0)

    # real furniture (Poly Haven, CC0); positions picked for the hero / square / portrait framing
    import_model(room, "modern_arm_chair_01", (-620, WALL_Y - 620, 0), 18.0)
    import_model(room, "mid_century_lounge_chair", (WALL_X - 600, 1250, 0), -120.0)
    import_model(room, "modern_coffee_table_01", (650, 820, 0), 90.0)
    import_model(room, "book_encyclopedia_set_01", (520, 760, 390), 8.0)
    import_model(room, "potted_plant_02", (WALL_X - 380, WALL_Y - 380, 0), 30.0)

    # window: an off-camera wall with 2x2 panes between the sun and the room, so the sun
    # lands as a pane-patterned patch around the robot
    q = SUN_DIR.to_track_quat("-Z", "Y")
    pane_w, pane_h, mull = 560.0, 760.0, 70.0
    # put the centre of one pane (not the mullion cross) on the robot
    c = (
        Vector((0, -40, 60))
        - SUN_DIR * 2600
        - q @ Vector(((pane_w + mull) / 2, (pane_h + mull) / 2, 0))
    )
    occ_m = mat("mk_occluder", (0.1, 0.1, 0.1))
    W2, H2 = pane_w + mull * 1.5, pane_h + mull * 1.5
    parts = [
        ((9000, 9000), (0, H2 + 4500)),
        ((9000, 9000), (0, -H2 - 4500)),
        ((9000, 2 * H2), (-W2 - 4500, 0)),
        ((9000, 2 * H2), (W2 + 4500, 0)),
        ((mull, 2 * H2), (0, 0)),
        ((2 * W2, mull), (0, 0)),
    ]
    for (sx, sy), (ox, oy) in parts:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(ox, oy, 0), verts=bm.verts)
        ob = mesh_obj("mk_window_wall", room, bm, c)
        ob.rotation_euler = q.to_euler()
        assign(ob, occ_m)
        ob.visible_camera = ob.visible_glossy = ob.visible_transmission = False

    sun_d = bpy.data.lights.new("mk_sun", "SUN")
    sun_d.energy, sun_d.angle = 7.0, math.radians(1.2)
    sun_d.color = (1.0, 0.83, 0.64)
    sun = bpy.data.objects.new("mk_sun", sun_d)
    room.objects.link(sun)
    sun.rotation_euler = q.to_euler()

    # rim light behind-right so the white shell edge separates from the background
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(bm, vec=(500, 700, 1), verts=bm.verts)
    rim = mesh_obj("mk_rim", room, bm, (520, 420, 380))
    rim.rotation_euler = (
        (Vector((0, 0, 80)) - rim.location).normalized().to_track_quat("-Z", "Y").to_euler()
    )
    assign(rim, mat("mk_rim_mat", (0, 0, 0), emit=(1.0, 0.95, 0.9), strength=5.0))
    rim.visible_camera = rim.visible_glossy = False
    return col, room, rig


def shot(col, name, w, h, loc, target, lens, fstop, focus, shift=(0.0, 0.0)):
    """shift: lens shift as a fraction of the frame width (negative x moves the subject right)."""
    _g["setup_render"](w, h)
    sc = bpy.context.scene
    sc.view_settings.exposure = 0.0
    sc.render.film_transparent = False
    cam = _g["camera"](col, "mk_cam_" + name, loc, target, lens)
    cam.data.shift_x, cam.data.shift_y = shift
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (Vector(focus) - Vector(loc)).length
    cam.data.dof.aperture_fstop = fstop / 1000.0  # scene is in mm, Cycles' aperture assumes metres
    bpy.context.view_layer.update()
    path = os.path.join(OUT, name + ".png")
    _g["render"](cam, path)
    return path


def cutout(col, room, rig):
    """Transparent PNG of the robot with its contact shadow, studio-lit."""
    for ob in room.objects:
        ob.hide_render = True
    for ch in rig.children:
        ch.hide_render = False
    rig.rotation_euler = (0, 0, math.radians(-35))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=3000)
    catcher = mesh_obj("mk_catcher", col, bm)
    catcher.is_shadow_catcher = True
    sc = bpy.context.scene
    w = sc.world.node_tree.nodes.get("Background")
    w.inputs["Strength"].default_value = 0.8
    _g["setup_render"](2048, 2048)
    sc.render.film_transparent = True
    sc.view_settings.exposure = 0.0
    az, hd, he = math.radians(-35), 720.0, math.radians(16)
    loc = (
        math.sin(az) * hd * math.cos(he),
        -math.cos(az) * hd * math.cos(he),
        60 + hd * math.sin(he),
    )
    cam = _g["camera"](col, "mk_cam_cutout", loc, (0, -5, 66), 85.0)
    bpy.context.view_layer.update()
    path = os.path.join(OUT, "cutout.png")
    _g["render"](cam, path)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    col, room, rig = build_home()
    fstop = globals().get("FSTOP", 3.5)
    focus = (0, -105, 90)
    plan = {
        # robot on the right third (lens shift), wall + chair softly blurred on the left for a headline
        "home_hero": (2560, 1280, (-520, -1020, 240), (-40, 40, 150), 42.0, focus, (-0.17, 0.0)),
        "home_square": (2048, 2048, (-520, -1020, 240), (-40, 40, 190), 55.0, focus, (0.0, 0.0)),
        "home_portrait": (1638, 2048, (-480, -960, 230), (-30, 40, 210), 55.0, focus, (0.0, 0.0)),
        "home_side": (2560, 1440, (-1150, -380, 200), (0, 40, 100), 85.0, (-80, 0, 85), (0.0, 0.0)),
    }
    out = []
    for name, (w, h, loc, target, lens, foc, shift) in plan.items():
        if name in SHOTS:
            out.append(shot(col, name, w, h, loc, target, lens, fstop, foc, shift))
    if "cutout" in SHOTS:
        out.append(cutout(col, room, rig))
    return out


if globals().get("RUN", True):
    RESULT = main()
