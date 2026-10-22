"""Parametric builder for the Mirae robot enclosure (v3: low rounded-trapezoid companion).

Run inside Blender (Text Editor or via MCP):
    exec(open(r"D:/git/Mirae/cad/blender/build_mirae.py").read())

One run: build -> manifold, interference, overhang, bed-fit and centre-of-mass checks
-> export STLs -> save .blend. Set EXPORT = False in the exec globals to only rebuild,
and RENDER = True to also render the front / side / bottom views.

Units: 1 Blender unit = 1 mm (scene scale_length = 0.001).
Assembly coordinates: Z = 0 is the ground, -Y is FRONT (face, caster), +Y is REAR,
+X is the viewer's right when looking at the face.

Printable parts (collection "Mirae"), every one fits a 220 x 220 bed in one piece:
    chassis       - charcoal base: wheel wells, N20 mounts, caster inserts, battery bay,
                    driver pocket, power board standoffs, sensor slot, USB-C + switch
    battery-door  - underside hatch with vents, 4x M3 countersunk
    pi-module     - white upper shell: Pi 5 tray, face-module slot, speaker, vents,
                    magnet columns, lid lip
    top-cover     - sloped lid with soft fillet, magnet-held, mic port
    faceplate     - V1 blank face, 2 diffused LED points + status light
    sensor-mount  - camera + VL53L1X carrier, slides into the base front slot

Vendor dimensions (HESTORE): BCASTER-15-10K ball caster 48.3 x 32.5 x 20 mm, M4 holes 39 mm;
N20-3PI-WHL wheel 42 x 18 mm (modelled as a 43 x 19 envelope); N20E motor 26 x 12 x 10 mm,
3 mm shaft; TB6612FNG-M 20.5 x 20.5 mm. Values marked MEASURE are not in a vendor spec.
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Parameters (mm)
# ---------------------------------------------------------------------------
P = dict(
    # footprint: rounded trapezoid, wide front, narrower rear
    L=210.0,
    WF=190.0,
    WR=164.0,
    plan_r=22.0,
    bed_xy=215.0,  # Ender-class 220 x 220 bed minus margin
    wall=2.5,
    clearance=0.35,  # sliding / press fits, PLA and PETG
    # heights
    ground_clear=20.0,  # = caster height (BCASTER-15-10K)
    floor_t=3.0,
    seam_z=58.0,  # base / upper shell split
    rim_front=138.0,
    rim_rear=116.0,  # sloped rim plane (rear value is at y = +L/2)
    # wall lean in degrees (inward going up), per edge: front, right, rear, left
    base_lean=(0.0, 6.0, 15.0, 6.0),
    shell_lean=(0.0, 6.0, 25.0, 6.0),
    seam_chamfer=0.8,
    bed_chamfer=1.5,
    rim_chamfer=0.6,
    shell_floor_t=2.5,
    # lid
    lid_t=7.0,
    lid_fillet=4.0,
    lip_inset=1.6,
    lip_h=2.5,
    magnet_d=6.2,
    magnet_depth=3.2,  # 6x3 mm neodymium discs
    mic_hole_d=2.0,
    mic_y=-85.0,
    mic_board=(14.0, 14.0, 3.0),  # INMP441, MEASURE
    # fasteners
    insert_d=4.2,
    insert_depth=8.0,
    screw_clear_d=3.4,
    boss_d=9.0,  # M3
    m4_insert_d=5.6,
    m4_insert_depth=8.0,  # caster
    part_bed_chamfer=0.4,
    # drive
    wheel_d=43.0,
    wheel_w=19.0,
    wheel_gap=1.5,
    axle_y=15.0,  # slightly behind centre
    motor_w=12.0,
    motor_h=10.0,
    motor_len=26.0,
    encoder=(8.0, 15.0, 15.0),  # length, width, height behind the motor, MEASURE
    motor_plate_t=2.0,
    gearbox_slot_w=4.5,
    cradle_h=7.0,
    # front caster
    caster_y=-80.0,
    caster_size=(48.3, 32.5, 20.0),
    caster_hole_spacing=39.0,
    caster_ball_d=15.875,
    # battery, loaded from below through a hatch, between caster and axle
    battery=(77.0, 41.0, 21.0),  # 2x18650 holder, MEASURE
    battery_y=-30.0,
    door_t=2.5,
    door_margin=8.0,
    # TB6612FNG-M pocket between the motors
    driver=(20.5, 20.5, 10.0),
    driver_y=15.0,
    # 5 V / 5 A buck + charger/BMS board
    power=(60.0, 35.0, 15.0),
    power_y=62.0,  # MEASURE
    usb_slot=(10.0, 4.5),
    switch_d=7.0,
    io_z=35.0,  # MEASURE
    # sensor cluster (base front, viewer's right)
    plate_w=104.0,
    plate_t=3.0,
    cam_x=14.0,
    cam_lens_z=42.0,
    cam_board=(25.0, 24.0),
    cam_hole_dx=21.0,
    cam_hole_dy=12.5,
    cam_hole_top=2.0,
    cam_lens_top=9.46,
    cam_depth=10.0,
    cam_housing=11.0,
    cam_wall_hole_d=9.0,  # Camera Module 3
    tof_x=38.0,
    tof_z=40.0,
    tof_board=(18.0, 13.0),
    tof_aperture=(7.0, 4.0),
    tof_hole_spacing=12.7,  # MEASURE
    pilot_d=1.8,
    fpc_slot=(20.0, 6.0),
    fpc_y=-90.0,
    # face module interface (top-open slide-in slot, retained by the lid)
    face_panel_w=100.0,
    face_panel_bottom=66.0,
    face_panel_r=10.0,
    face_panel_t=2.1,
    face_flange_w=108.0,
    face_flange_bottom=62.0,
    face_flange_t=2.3,
    face_inset=0.4,
    face_rail_t=3.0,
    face_open_w=92.0,
    face_open_bottom=70.0,
    face_open_r=3.0,
    face_top_gap=0.2,
    face_module_env=(86.0, 15.0, 57.0),
    # V1 lights (thin-skin diffusion; led_skin=0 gives through-holes for light pipes)
    led_d=3.1,
    led_dx=36.0,
    led_z=108.0,
    status_d=2.2,
    status_pos=(40.0, 76.0),
    led_skin=0.6,
    # speaker (left), vents (right), exhaust (rear)
    speaker_d=40.0,
    speaker_depth=5.0,
    speaker_y=35.0,
    speaker_z=86.0,  # MEASURE
    amp_board=(19.0, 17.0, 5.0),
    amp_pos=(-30.0, 60.0),  # MAX98357
    grille_hole_d=2.6,
    grille_rings=(0.0, 5.0, 10.0, 15.0),
    exhaust_slots=7,
    exhaust_slot=(3.0, 14.0),
    exhaust_pitch=7.0,
    exhaust_z=96.0,
    # Raspberry Pi 5
    pi_hole_x=58.0,
    pi_hole_y=49.0,
    pi_hole_d=2.7,
    pi_standoff_h=3.0,
    pi_center=(0.0, 10.0),
    pi_case=(94.0, 63.0, 25.0),  # passive aluminium case, MEASURE
    # rough masses (g) for the centre-of-mass check
    mass=dict(
        pi=140, battery=110, motor=12, wheel=10, speaker=35, power=25, driver=5, camera=5, amp=3
    ),
    print_density=1.24 * 0.8,  # g/cm3 x fill factor for thin-walled parts
)

SEGC = 10  # segments per plan corner
SEG = 48
ROOT = (
    os.path.dirname(os.path.abspath(__file__))
    if "__file__" in globals()
    else r"D:/git/Mirae/cad/blender"
)

L2 = P["L"] / 2
YF, YR = -L2, L2
Z_B = P["ground_clear"]
FLOOR_TOP = Z_B + P["floor_t"]
Z_S = P["seam_z"]
TRAY_TOP = Z_S + P["shell_floor_t"]
RIM0 = P["rim_front"]  # rim plane height at y = YF
SLOPE = (P["rim_rear"] - P["rim_front"]) / (YR - YF)  # dz/dy of the rim plane
N_RIM = Vector((0, -SLOPE, 1)).normalized()
ROT_N = Matrix.Rotation(math.atan(SLOPE), 4, "X")  # local Z -> rim plane normal
FRONT_IN = YF + P["wall"]  # front wall is vertical
AXLE_Z = P["wheel_d"] / 2


def rim_z(y, above=0.0):
    return RIM0 + above + SLOPE * (y - YF)


# ---------------------------------------------------------------------------
# Body outline: rounded trapezoid whose edges lean inward with height
# ---------------------------------------------------------------------------
POLY = [(-P["WF"] / 2, YF), (P["WF"] / 2, YF), (P["WR"] / 2, YR), (-P["WR"] / 2, YR)]  # CCW
EDGES = []
for _i in range(4):
    _a, _b = Vector(POLY[_i]), Vector(POLY[(_i + 1) % 4])
    _d = (_b - _a).normalized()
    _n = Vector((_d.y, -_d.x))
    EDGES.append((_n, _n.dot(_a)))


def edge_off(z):
    out = []
    for i in range(4):
        tb = math.tan(math.radians(P["base_lean"][i]))
        ts = math.tan(math.radians(P["shell_lean"][i]))
        out.append(tb * (z - Z_B) if z <= Z_S else tb * (Z_S - Z_B) + ts * (z - Z_S))
    return out


def core(z, extra):
    """Polygon with every edge moved inward by its lean offset + extra (vertex i joins edges i-1, i)."""
    off = edge_off(z)
    lines = [(n, c - off[i] - extra) for i, (n, c) in enumerate(EDGES)]
    verts = []
    for i in range(4):
        (n1, c1), (n2, c2) = lines[i - 1], lines[i]
        det = n1.x * n2.y - n1.y * n2.x
        verts.append(Vector(((c1 * n2.y - c2 * n1.y) / det, (n1.x * c2 - n2.x * c1) / det)))
    return verts


def ring_pts(z, inset, z_out=None):
    """Outline at height z, offset inward by `inset`, as 3D points (placed at z_out if given)."""
    R = P["plan_r"]
    C = core(z, R)
    pts = []
    for i in range(4):
        a0 = math.atan2(EDGES[i - 1][0].y, EDGES[i - 1][0].x)
        a1 = math.atan2(EDGES[i][0].y, EDGES[i][0].x)
        while a1 < a0:
            a1 += 2 * math.pi
        for k in range(SEGC + 1):
            a = a0 + (a1 - a0) * k / SEGC
            pts.append(
                (
                    C[i].x + (R - inset) * math.cos(a),
                    C[i].y + (R - inset) * math.sin(a),
                    z if z_out is None else z_out,
                )
            )
    return pts


def sec_pts(inset, above=0.0):
    """Upper-shell outline (offset by `inset`) cut by the rim plane raised by `above`."""
    za, zb = Z_S, Z_S + 100.0
    out = []
    for (xa, ya, _), (xb, yb, _) in zip(ring_pts(za, inset), ring_pts(zb, inset)):
        kx, ky = (xb - xa) / (zb - za), (yb - ya) / (zb - za)
        z = (RIM0 + above + SLOPE * (ya - ky * za - YF)) / (1 - SLOPE * ky)
        out.append((xa + kx * (z - za), ya + ky * (z - za), z))
    return out


def edge_x(i, y, z, inset):
    n, c = EDGES[i]
    cc = c - edge_off(z)[i] - inset
    return (cc - n.y * y) / n.x


def edge_y(i, x, z, inset):
    n, c = EDGES[i]
    cc = c - edge_off(z)[i] - inset
    return (cc - n.x * x) / n.y


# ---------------------------------------------------------------------------
# Mesh helpers
# ---------------------------------------------------------------------------
def _collection(name, parent=None, clear=True):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    elif clear:
        for ob in list(col.objects):
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if me and me.users == 0 and isinstance(me, bpy.types.Mesh):
                bpy.data.meshes.remove(me)
    return col


def _object(name, bm, col, matrix=None):
    if matrix is not None:
        bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def loft_rings(name, col, rings, matrix=None):
    """Closed solid through rings of 3D points (all rings the same length)."""
    bm = bmesh.new()
    loops = [[bm.verts.new(p) for p in r] for r in rings]
    bm.faces.new(loops[0][::-1])
    bm.faces.new(loops[-1])
    n = len(loops[0])
    for a, b in zip(loops, loops[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return _object(name, bm, col, matrix)


def ring_solid(name, col, outer, inner):
    """Closed band between outer and inner ring stacks (lip, groove)."""
    bm = bmesh.new()
    lo = [[bm.verts.new(p) for p in r] for r in outer]
    li = [[bm.verts.new(p) for p in r] for r in inner]
    n = len(lo[0])
    for i in range(n):
        j = (i + 1) % n
        for a, b in zip(lo, lo[1:]):
            bm.faces.new((a[i], a[j], b[j], b[i]))
        for a, b in zip(li, li[1:]):
            bm.faces.new((a[j], a[i], b[i], b[j]))
        bm.faces.new((lo[0][j], lo[0][i], li[0][i], li[0][j]))
        bm.faces.new((lo[-1][i], lo[-1][j], li[-1][j], li[-1][i]))
    return _object(name, bm, col)


def rrect_pts(w, d, r, inset=0.0, seg=12):
    w, d, r = w - 2 * inset, d - 2 * inset, r - inset
    r = max(min(r, w / 2 - 0.01, d / 2 - 0.01), 0.0)
    pts = []
    for x, y, a0 in (
        (w / 2 - r, d / 2 - r, 0),
        (-w / 2 + r, d / 2 - r, 90),
        (-w / 2 + r, -d / 2 + r, 180),
        (w / 2 - r, -d / 2 + r, 270),
    ):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    return pts


def loft(name, col, w, d, r, rings, cx=0.0, cy=0.0, seg=12, matrix=None):
    """Rounded-rect solid through (z, inset) rings."""
    bm = bmesh.new()
    loops = [
        [bm.verts.new((cx + x, cy + y, z)) for x, y in rrect_pts(w, d, r, i, seg)] for z, i in rings
    ]
    bm.faces.new(loops[0][::-1])
    bm.faces.new(loops[-1])
    n = len(loops[0])
    for a, b in zip(loops, loops[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    return _object(name, bm, col, matrix)


def rrect_prism(name, col, w, d, h, r, z0, cx=0.0, cy=0.0, seg=12):
    return loft(name, col, w, d, r, [(z0, 0.0), (z0 + h, 0.0)], cx, cy, seg)


def box(name, col, sx, sy, sz, cx, cy, cz):
    return rrect_prism(name, col, sx, sy, sz, 0.0, cz - sz / 2, cx, cy, seg=1)


def u_pts(w, h, r, inset=0.0, seg=12):
    """Outline with rounded bottom corners and a square top, bottom edge at y=0."""
    w, r = w - 2 * inset, r - inset
    y0, y1 = inset, h - inset
    pts = [(w / 2, y1), (-w / 2, y1)]
    for x, a0 in ((-w / 2 + r, 180), (w / 2 - r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((x + r * math.cos(a), y0 + r + r * math.sin(a)))
    return pts


def u_loft(name, col, w, h, r, rings, matrix=None, seg=12):
    bm = bmesh.new()
    loops = [[bm.verts.new((x, y, z)) for x, y in u_pts(w, h, r, i, seg)] for z, i in rings]
    bm.faces.new(loops[0][::-1])
    bm.faces.new(loops[-1])
    n = len(loops[0])
    for a, b in zip(loops, loops[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    return _object(name, bm, col, matrix)


def _YZ(z0):
    """Place a u_loft in the front wall: rings are world Y values, local y is height above z0.
    (x, y, z) -> (-x, z, y + z0), det +1."""
    return Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, z0), (0, 0, 0, 1)))


_AX = {
    "Z": Matrix.Identity(4),
    "X": Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))),  # (x,y,z)->(z,x,y)
    "Y": Matrix.Rotation(math.radians(90), 4, "X"),
}  # (x,y,z)->(x,-z,y)


def cyl(name, col, d, length, loc, axis="Z", d2=None, seg=SEG):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=seg,
        radius1=d / 2,
        radius2=(d2 if d2 is not None else d) / 2,
        depth=length,
    )
    return _object(name, bm, col, Matrix.Translation(Vector(loc)) @ _AX[axis])


def cyl_n(name, col, d, length, pt, along):
    """Cylinder on the rim-plane normal through pt, centre shifted `along` the normal."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=SEG, radius1=d / 2, radius2=d / 2, depth=length
    )
    return _object(
        name, bm, col, Matrix.Translation(Vector(pt)) @ ROT_N @ Matrix.Translation((0, 0, along))
    )


def slot(name, col, a, b, r, length, loc, axis):
    """Rounded-rect through-cut. axis X: a along Y, b along Z. axis Y: a along X, b along Z."""
    bm = bmesh.new()
    pts = rrect_pts(a, b, r, seg=8)
    lo = [bm.verts.new((x, y, -length / 2)) for x, y in pts]
    hi = [bm.verts.new((x, y, length / 2)) for x, y in pts]
    bm.faces.new(lo[::-1])
    bm.faces.new(hi)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    m = (
        _AX["X"]
        if axis == "X"
        else Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    )
    return _object(name, bm, col, Matrix.Translation(Vector(loc)) @ m)


def boolean(target, tools, op):
    """Apply one MANIFOLD boolean of `target` against tool objects, then delete the tools."""
    if not tools:
        return
    tmp = bpy.data.collections.new("_bool_tmp")
    bpy.context.scene.collection.children.link(tmp)
    for t in tools:
        for c in list(t.users_collection):
            c.objects.unlink(t)
        tmp.objects.link(t)
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = op
    mod.solver = "MANIFOLD"
    mod.operand_type = "COLLECTION"
    mod.collection = tmp
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    new_me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.remove(mod)
    old = target.data
    new_me.name = old.name
    target.data = new_me
    bpy.data.meshes.remove(old)
    for t in tools:
        me = t.data
        bpy.data.objects.remove(t, do_unlink=True)
        bpy.data.meshes.remove(me)
    bpy.data.collections.remove(tmp)


def slide_slot(col, add, x_wall, y_c, z_lo, z_hi, half_w, depth, rib_t=3.0, finger=4.0):
    """Vertical slide-in slot against the (vertical) front wall at y = x_wall."""
    h = z_hi - z_lo
    zc = (z_lo + z_hi) / 2
    for s in (-1, 1):
        along = y_c + s * (half_w + rib_t / 2)
        across = x_wall + (depth + rib_t) / 2 - 0.25
        add.append(box("rib", col, rib_t, depth + rib_t + 0.5, h, along, across, zc))
        add.append(
            box(
                "finger",
                col,
                finger + 0.5,
                rib_t,
                h,
                y_c + s * (half_w - finger / 2 + 0.25),
                x_wall + depth + rib_t / 2,
                zc,
            )
        )


def grille(col, cut, x_wall, y_c, z_c):
    for rr in P["grille_rings"]:
        n = 1 if rr == 0 else int(round(2 * math.pi * rr / (P["grille_hole_d"] + 2.2)))
        for k in range(n):
            a = 2 * math.pi * k / n + (math.pi / n if (rr / 5) % 2 else 0)
            cut.append(
                cyl(
                    "grille",
                    col,
                    P["grille_hole_d"],
                    14.0,
                    (x_wall, y_c + rr * math.cos(a), z_c + rr * math.sin(a)),
                    "X",
                    seg=16,
                )
            )


def base_env(col, name="env"):
    bc, sc = P["bed_chamfer"], P["seam_chamfer"]
    return loft_rings(
        name,
        col,
        [ring_pts(Z_B, bc), ring_pts(Z_B + bc, 0), ring_pts(Z_S - sc, 0), ring_pts(Z_S, sc)],
    )


def shell_env(col, name="env"):
    sc, rc = P["seam_chamfer"], P["rim_chamfer"]
    return loft_rings(
        name, col, [ring_pts(Z_S, sc), ring_pts(Z_S + sc, 0), sec_pts(0, -rc), sec_pts(rc)]
    )


# ---------------------------------------------------------------------------
# Derived drive geometry
# ---------------------------------------------------------------------------
WR_ = P["wheel_d"] / 2
_ay = P["axle_y"]
# the wheel must clear the leaning, angled inner side wall over its whole box
WHEEL_OUT = (
    min(
        edge_x(1, y, z, P["wall"])
        for y in (_ay - WR_, _ay + WR_)
        for z in (FLOOR_TOP, P["wheel_d"])
    )
    - P["wheel_gap"]
)
WHEEL_IN = WHEEL_OUT - P["wheel_w"]
WHEEL_X = (WHEEL_IN + WHEEL_OUT) / 2
PLATE_X = WHEEL_IN - P["wheel_gap"]
MOTOR_FACE = PLATE_X - P["motor_plate_t"]
MOTOR_BACK = MOTOR_FACE - P["motor_len"]
ENC_BACK = MOTOR_BACK - P["encoder"][0]
assert P["driver"][0] / 2 + 3.0 < ENC_BACK, "motors collide with the driver pocket"


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------
def build_chassis(col):
    ft, c = P["floor_t"], P["clearance"]
    ob = base_env(col, "chassis")
    cav = loft_rings(
        "cav",
        col,
        [
            ring_pts(FLOOR_TOP, P["wall"]),
            ring_pts(Z_S, P["wall"]),
            ring_pts(Z_S, P["wall"], z_out=Z_S + 2.0),
        ],
    )
    boolean(ob, [cav], "DIFFERENCE")
    add, cut = [], []
    ay = P["axle_y"]
    h_in = Z_S - FLOOR_TOP

    # join bosses (M3 inserts) for the upper shell
    join_pts = [(-55.0, -60.0), (55.0, -60.0), (-50.0, 50.0), (50.0, 50.0)]
    for x, y in join_pts:
        add.append(cyl("boss", col, P["boss_d"], h_in + 0.5, (x, y, FLOOR_TOP + h_in / 2 - 0.25)))
        cut.append(
            cyl(
                "insert",
                col,
                P["insert_d"],
                P["insert_depth"] + 1,
                (x, y, Z_S - P["insert_depth"] / 2 + 0.5),
            )
        )

    # drive: wheel wells, motor plates with open-top U slot, cradles, floor openings
    rail_y = P["motor_w"] / 2 + c + P["wall"] / 2
    plate_h = P["wheel_d"] + 3 - FLOOR_TOP
    el, ew, eh = P["encoder"]
    for s in (-1, 1):
        cut.append(
            box(
                "well",
                col,
                P["wheel_w"] + 2 * P["wheel_gap"],
                2 * WR_ + 4,
                ft * 3,
                s * WHEEL_X,
                ay,
                Z_B + ft / 2,
            )
        )
        px = s * (PLATE_X - P["motor_plate_t"] / 2)
        add.append(
            box(
                "mplate",
                col,
                P["motor_plate_t"],
                2 * WR_ + 3,
                plate_h + 0.5,
                px,
                ay,
                FLOOR_TOP + plate_h / 2 - 0.25,
            )
        )
        cut.append(
            box(
                "uslot",
                col,
                P["motor_plate_t"] * 3,
                P["gearbox_slot_w"],
                60.0,
                px,
                ay,
                AXLE_Z + 30.0,
            )
        )
        cut.append(
            cyl("uslot_r", col, P["gearbox_slot_w"], P["motor_plate_t"] * 3, (px, ay, AXLE_Z), "X")
        )
        mx = s * (MOTOR_FACE + MOTOR_BACK) / 2
        for ry in (-rail_y, rail_y):
            add.append(
                box(
                    "rail",
                    col,
                    P["motor_len"],
                    P["wall"],
                    P["cradle_h"] + 0.5,
                    mx,
                    ay + ry,
                    FLOOR_TOP + P["cradle_h"] / 2 - 0.25,
                )
            )
        # the motor hangs 3.5 mm below the floor (axle 21.5 vs caster 20): open the floor under it
        cut.append(
            box(
                "mslot",
                col,
                P["motor_len"] + 1.0,
                P["motor_w"] + 2 * c,
                ft * 3,
                mx,
                ay,
                Z_B + ft / 2,
            )
        )
        cut.append(
            box(
                "eslot",
                col,
                el + 1.5,
                ew + 2 * c,
                ft * 3,
                s * (MOTOR_BACK - el / 2),
                ay,
                Z_B + ft / 2,
            )
        )
        for zx in (MOTOR_FACE - 5.0, MOTOR_BACK + 5.0):
            for zy in (-1, 1):
                cut.append(
                    box(
                        "zip", col, 4.0, 2.0, ft * 3, s * zx, ay + zy * (rail_y + 3.0), Z_B + ft / 2
                    )
                )

    # front caster: M4 heat-set inserts from below
    for cx in (-P["caster_hole_spacing"] / 2, P["caster_hole_spacing"] / 2):
        add.append(cyl("cboss", col, 10.0, 9.5, (cx, P["caster_y"], FLOOR_TOP + 4.5)))
        cut.append(
            cyl(
                "cinsert",
                col,
                P["m4_insert_d"],
                P["m4_insert_depth"] + 1,
                (cx, P["caster_y"], Z_B + P["m4_insert_depth"] / 2 - 0.5),
            )
        )

    # battery bay: loads from below, ribs hold it, door screws into 4 M3 inserts
    bw, bd, bh = P["battery"]
    by_ = P["battery_y"]
    ow_, od_ = bw + 2 * c + 1.0, bd + 2 * c + 1.0
    cut.append(rrect_prism("bat_open", col, ow_, od_, ft * 3, 2.0, Z_B - ft, 0, by_))
    rib_h = bh + 1.0
    for s in (-1, 1):
        add.append(
            box(
                "bat_rib",
                col,
                2.0,
                od_ + 4.0,
                rib_h + 0.5,
                s * (ow_ / 2 + 1.0),
                by_,
                FLOOR_TOP + rib_h / 2 - 0.25,
            )
        )
        add.append(
            box(
                "bat_rib",
                col,
                ow_ + 4.0,
                2.0,
                rib_h + 0.5,
                0,
                by_ + s * (od_ / 2 + 1.0),
                FLOOR_TOP + rib_h / 2 - 0.25,
            )
        )
    door_pts = door_screws()
    for x, y in door_pts:
        add.append(cyl("dboss", col, P["boss_d"], 7.5, (x, y, FLOOR_TOP + 3.5)))
        cut.append(cyl("dinsert", col, P["insert_d"], 7.0, (x, y, Z_B + 3.0)))

    # TB6612FNG-M slide-in pocket between the motors
    dw, dd, dh = P["driver"]
    for s in (-1, 1):
        add.append(
            box(
                "drv_rail",
                col,
                2.0,
                dd,
                6.5,
                s * (dw / 2 + c + 1.0),
                P["driver_y"],
                FLOOR_TOP + 3.0,
            )
        )
    add.append(
        box(
            "drv_stop",
            col,
            dw + 2 * c + 4.0,
            2.0,
            6.5,
            0,
            P["driver_y"] + dd / 2 + c + 1.0,
            FLOOR_TOP + 3.0,
        )
    )

    # power board standoffs (rear)
    pw, pd, ph = P["power"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (pw / 2 - 3.5), P["power_y"] + sy * (pd / 2 - 3.5)
            add.append(cyl("pso", col, 5.0, 4.5, (x, y, FLOOR_TOP + 1.75)))
            cut.append(cyl("pso_hole", col, 2.2, 5.0, (x, y, FLOOR_TOP + 2.5)))

    # sensor slot on the front wall + camera / ToF openings
    slide_slot(
        col, add, FRONT_IN, 0.0, FLOOR_TOP, Z_S - 0.3, P["plate_w"] / 2 + c, P["plate_t"] + c
    )
    fy = YF + P["wall"] / 2
    cut.append(
        cyl(
            "lens", col, P["cam_wall_hole_d"], P["wall"] * 3, (P["cam_x"], fy, P["cam_lens_z"]), "Y"
        )
    )
    aw, ah = P["tof_aperture"]
    cut.append(
        slot("tof", col, aw + 1.0, ah + 1.0, 1.5, P["wall"] * 3, (P["tof_x"], fy, P["tof_z"]), "Y")
    )

    # rear I/O next to the power board (rear wall leans: cut long)
    uw, uh = P["usb_slot"]
    iz = P["io_z"]
    cut.append(
        slot(
            "usb",
            col,
            uw,
            uh,
            uh / 2 - 0.01,
            12.0,
            (25.0, edge_y(2, 25.0, iz, P["wall"] / 2), iz),
            "Y",
        )
    )
    cut.append(
        cyl(
            "switch",
            col,
            P["switch_d"],
            12.0,
            (-25.0, edge_y(2, -25.0, iz, P["wall"] / 2), iz),
            "Y",
        )
    )

    boolean(ob, add, "UNION")
    boolean(ob, [base_env(col)], "INTERSECT")
    boolean(ob, cut, "DIFFERENCE")
    return ob, join_pts


def door_screws():
    bw, bd, _ = P["battery"]
    c = P["clearance"]
    hx = (bw + 2 * c + 1.0) / 2 + 2.0 + 3.0
    hy = (bd + 2 * c + 1.0) / 2 + 2.0 + 3.0
    return [(sx * hx, P["battery_y"] + sy * hy) for sx in (-1, 1) for sy in (-1, 1)]


def build_battery_door(col):
    bw, bd, _ = P["battery"]
    t = P["door_t"]
    pts = door_screws()
    dw = 2 * abs(pts[0][0]) + 2 * P["door_margin"] - 6.0
    dd = 2 * abs(pts[0][1] - P["battery_y"]) + 2 * P["door_margin"] - 6.0
    bc = P["part_bed_chamfer"]
    ob = loft(
        "battery-door",
        col,
        dw,
        dd,
        6.0,
        [(Z_B - t, bc), (Z_B - t + bc, 0), (Z_B, 0)],
        0,
        P["battery_y"],
    )
    cut = []
    for x, y in pts:
        cut.append(cyl("hole", col, P["screw_clear_d"], t * 3, (x, y, Z_B - t / 2)))
        cut.append(cyl("csk", col, 6.6, 1.7, (x, y, Z_B - t + 0.84), d2=3.4))
    for i in range(9):
        cut.append(
            rrect_prism(
                "vent",
                col,
                2.5,
                18.0,
                t * 3,
                1.24,
                Z_B - 2 * t,
                (i - 4) * 5.0,
                P["battery_y"] + 2.0,
            )
        )
    boolean(ob, cut, "DIFFERENCE")
    return ob


def column_center(i, z):
    R = P["plan_r"]
    u = (EDGES[i - 1][0] + EDGES[i][0]).normalized()
    return core(z, R)[i] + u * (R - P["wall"] - P["boss_d"] / 2 + 1.0)


def build_pi_module(col, join_pts):
    ft, c = P["shell_floor_t"], P["clearance"]
    ob = shell_env(col, "pi-module")
    cav = loft_rings("cav", col, [ring_pts(TRAY_TOP, P["wall"]), sec_pts(P["wall"], 10.0)])
    boolean(ob, [cav], "DIFFERENCE")
    add, cut = [], []

    # leaning corner columns with magnet pockets on the rim-plane normal
    col_top = []
    for i in range(4):
        z_hi = RIM0 + 10.0
        rings = []
        for z in (TRAY_TOP - 0.5, z_hi):
            cc = column_center(i, z)
            rings.append(
                [
                    (
                        cc.x + P["boss_d"] / 2 * math.cos(2 * math.pi * k / 32),
                        cc.y + P["boss_d"] / 2 * math.sin(2 * math.pi * k / 32),
                        z,
                    )
                    for k in range(32)
                ]
            )
        add.append(loft_rings("column", col, rings))
        z = RIM0
        for _ in range(6):
            cc = column_center(i, z)
            z = rim_z(cc.y)
        col_top.append(Vector((cc.x, cc.y, z)))
        cut.append(
            cyl_n(
                "magnet",
                col,
                P["magnet_d"],
                P["magnet_depth"] + 1,
                col_top[-1],
                -P["magnet_depth"] / 2 + 0.5,
            )
        )

    # tray: screws into the base, Pi standoffs, cable + camera FPC slots
    for x, y in join_pts:
        cut.append(cyl("join", col, P["screw_clear_d"], ft * 3, (x, y, Z_S + ft / 2)))
    px, py = P["pi_center"]
    sh = P["pi_standoff_h"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = px + sx * P["pi_hole_x"] / 2, py + sy * P["pi_hole_y"] / 2
            add.append(cyl("pi_so", col, 6.0, sh + 0.5, (x, y, TRAY_TOP + sh / 2 - 0.25)))
            cut.append(cyl("pi", col, P["pi_hole_d"], ft + sh + 2, (x, y, Z_S + (ft + sh) / 2)))
    for sx in (-1, 1):
        cut.append(rrect_prism("cable", col, 10.0, 26.0, ft * 3, 3.0, Z_S - ft, sx * 55.0, -30.0))
    fw_, fd_ = P["fpc_slot"]
    cut.append(rrect_prism("fpc", col, fw_, fd_, ft * 3, 2.0, Z_S - ft, P["cam_x"], P["fpc_y"]))

    # face module interface: notch for the panel, flange slot, rail frame (top-open)
    flange_front = FRONT_IN
    flange_back = (
        FRONT_IN + P["face_inset"] + P["face_panel_t"] - P["wall"] + P["face_flange_t"] + c
    )
    rail_back = flange_back + P["face_rail_t"]
    fw = P["face_flange_w"] + 2 * c
    h_in = RIM0 - TRAY_TOP
    add.append(
        box(
            "rail_frame",
            col,
            fw + 3.0,
            rail_back - flange_front + 0.1,
            h_in + 1.0,
            0,
            (flange_front - 0.1 + rail_back) / 2,
            TRAY_TOP + h_in / 2,
        )
    )
    top = RIM0 + 20.0
    nb = P["face_panel_bottom"] - c
    cut.append(
        u_loft(
            "notch",
            col,
            P["face_panel_w"] + 2 * c,
            top - nb,
            P["face_panel_r"] + c,
            [(YF - 1.0, 0), (flange_front + 0.1, 0)],
            matrix=_YZ(nb),
        )
    )
    fb = P["face_flange_bottom"] - 0.25
    cut.append(
        u_loft(
            "flange_slot",
            col,
            fw,
            top - fb,
            P["face_panel_r"] + 4 + c,
            [(flange_front, 0), (flange_back, 0)],
            matrix=_YZ(fb),
        )
    )
    ob_ = P["face_open_bottom"]
    cut.append(
        u_loft(
            "face_open",
            col,
            P["face_open_w"],
            top - ob_,
            P["face_open_r"],
            [(flange_front - 1.0, 0), (rail_back + 1.0, 0)],
            matrix=_YZ(ob_),
        )
    )

    # speaker (left): vertical slide-in slot just inside the leaning wall; vents (right)
    ys, zs, sr = P["speaker_y"], P["speaker_z"], P["speaker_d"] / 2
    depth = P["speaker_depth"] + c
    x_face = (
        max(edge_x(3, y, zs + sr, P["wall"]) for y in (ys - sr, ys + sr)) + 0.3
    )  # speaker front face
    x_out = edge_x(3, ys, TRAY_TOP, P["wall"]) - 1.0  # reach into the wall
    rib_t, finger = 3.0, 4.0
    sup_h = zs - sr - TRAY_TOP
    z_top = zs + sr * 0.6
    add.append(
        box(
            "spk_support",
            col,
            x_face + depth - x_out,
            P["speaker_d"] + 6.0,
            sup_h + 0.5,
            (x_face + depth + x_out) / 2,
            ys,
            TRAY_TOP + sup_h / 2 - 0.25,
        )
    )
    for s in (-1, 1):
        x1 = x_face + depth + rib_t
        add.append(
            box(
                "spk_rib",
                col,
                x1 - x_out,
                rib_t,
                z_top - TRAY_TOP + 0.5,
                (x1 + x_out) / 2,
                ys + s * (sr + c + rib_t / 2),
                (TRAY_TOP + z_top) / 2 - 0.25,
            )
        )
        add.append(
            box(
                "spk_finger",
                col,
                rib_t,
                finger + 0.5,
                z_top - TRAY_TOP + 0.5,
                x_face + depth + rib_t / 2,
                ys + s * (sr + c - finger / 2 + 0.25),
                (TRAY_TOP + z_top) / 2 - 0.25,
            )
        )
    grille(col, cut, edge_x(3, ys, zs, P["wall"] / 2), ys, zs)
    grille(col, cut, edge_x(1, ys, zs, P["wall"] / 2), ys, zs)

    # rear exhaust slots high on the sloped back
    ew, eh = P["exhaust_slot"]
    n = P["exhaust_slots"]
    ez = P["exhaust_z"]
    for i in range(n):
        ex = (i - (n - 1) / 2) * P["exhaust_pitch"]
        cut.append(
            slot(
                "exhaust",
                col,
                ew,
                eh,
                ew / 2 - 0.01,
                14.0,
                (ex, edge_y(2, ex, ez, P["wall"] / 2), ez),
                "Y",
            )
        )

    boolean(ob, add, "UNION")
    boolean(ob, [shell_env(col)], "INTERSECT")
    # lid lip on the rim (removed across the face slot by the slot cuts)
    li, lt = P["lip_inset"], P["wall"] - P["lip_inset"] + 0.3
    boolean(
        ob,
        [
            ring_solid(
                "lip",
                col,
                [sec_pts(li, -0.5), sec_pts(li, P["lip_h"])],
                [sec_pts(li + lt, -0.5), sec_pts(li + lt, P["lip_h"])],
            )
        ],
        "UNION",
    )
    boolean(ob, cut, "DIFFERENCE")
    return ob, col_top


def build_top_cover(col, col_top):
    t, f = P["lid_t"], P["lid_fillet"]
    rings = [sec_pts(0, 0.0)]  # no bed chamfer: on a sloped lid it turns into an overhang
    for k in range(9):
        a = math.radians(90 * k / 8)
        rings.append(sec_pts(f * (1 - math.cos(a)), t - f + f * math.sin(a)))
    ob = loft_rings("top-cover", col, rings)
    c = P["clearance"]
    li, lt = P["lip_inset"], P["wall"] - P["lip_inset"] + 0.3
    gi, gt = li - c, lt + 2 * c
    cut = [
        ring_solid(
            "groove",
            col,
            [sec_pts(gi, -1.0), sec_pts(gi, P["lip_h"] + 0.3)],
            [sec_pts(gi + gt, -1.0), sec_pts(gi + gt, P["lip_h"] + 0.3)],
        )
    ]
    for pt in col_top:
        cut.append(
            cyl_n(
                "magnet", col, P["magnet_d"], P["magnet_depth"] + 1, pt, P["magnet_depth"] / 2 - 0.5
            )
        )
    my = P["mic_y"]
    cut.append(cyl_n("mic", col, P["mic_hole_d"], t * 3, (0, my, rim_z(my)), t / 2))
    boolean(ob, cut, "DIFFERENCE")
    return ob


def build_faceplate(col):
    """Flange (back, on the bed) + visible panel. Local z=0 is the back face,
    local y is height above the flange bottom."""
    pt, ft_ = P["face_panel_t"], P["face_flange_t"]
    back_y = YF + P["face_inset"] + pt + ft_
    top = rim_z(back_y + P["clearance"]) - P["face_top_gap"]
    fb, pb = P["face_flange_bottom"], P["face_panel_bottom"]
    bc = P["part_bed_chamfer"]
    ob = u_loft(
        "faceplate",
        col,
        P["face_flange_w"],
        top - fb,
        P["face_panel_r"] + 4,
        [(0, bc), (bc, 0), (ft_, 0)],
    )
    panel = u_loft(
        "panel",
        col,
        P["face_panel_w"],
        top - pb,
        P["face_panel_r"],
        [(ft_ - 0.5, 0), (ft_ + pt, 0)],
    )
    panel.data.transform(Matrix.Translation((0, pb - fb, 0)))
    boolean(ob, [panel], "UNION")
    depth = ft_ + pt - P["led_skin"]
    cut = []
    for x, z, d in (
        (-P["led_dx"] / 2, P["led_z"], P["led_d"]),
        (P["led_dx"] / 2, P["led_z"], P["led_d"]),
        (P["status_pos"][0], P["status_pos"][1], P["status_d"]),
    ):
        cut.append(cyl("led", col, d, depth + 1.0, (x, z - fb, depth / 2 - 0.5)))
    boolean(ob, cut, "DIFFERENCE")
    ob.data.transform(Matrix.Translation((0, back_y, fb)) @ _AX["Y"])
    return ob


# flat-local -> front-wall placement: local +Z points into the robot, local +Y is world +Z,
# local +X is world -X (det +1)
_FRONT = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def build_sensor_mount(col):
    t = P["plate_t"]
    ph = (Z_S - 0.3) - FLOOR_TOP - 0.5
    pz = FLOOR_TOP + 0.25 + ph / 2
    bc = P["part_bed_chamfer"]
    ob = loft("sensor-mount", col, P["plate_w"], ph, 3.0, [(0, bc), (bc, 0), (t, 0)])
    add, cut = [], []
    cx = -P["cam_x"]  # local X is mirrored
    lens_z = P["cam_lens_z"] - pz
    top = lens_z + P["cam_lens_top"]
    hs = P["cam_housing"]
    cut.append(rrect_prism("cam_win", col, hs, hs, t * 3, 2.0, -t, cx, lens_z))
    so_len = P["cam_depth"] - t - P["clearance"]
    for hx in (-P["cam_hole_dx"] / 2, P["cam_hole_dx"] / 2):
        for hy in (top - P["cam_hole_top"], top - P["cam_hole_top"] - P["cam_hole_dy"]):
            add.append(cyl("cam_so", col, 4.0, so_len + 0.5, (cx + hx, hy, t + so_len / 2 - 0.25)))
            cut.append(
                cyl("cam_pilot", col, P["pilot_d"], so_len + t, (cx + hx, hy, t + so_len / 2))
            )
    tx, tz = -P["tof_x"], P["tof_z"] - pz
    aw, ah = P["tof_aperture"]
    cut.append(box("tof_win", col, aw, ah, t * 3, tx, tz, t / 2))
    for hx in (-P["tof_hole_spacing"] / 2, P["tof_hole_spacing"] / 2):
        cut.append(cyl("tof_pilot", col, P["pilot_d"], t * 3, (tx + hx, tz, t / 2)))
    boolean(ob, add, "UNION")
    boolean(ob, cut, "DIFFERENCE")
    ob.data.transform(Matrix.Translation((0, FRONT_IN + P["clearance"] / 2, pz)) @ _FRONT)
    return ob


# ---------------------------------------------------------------------------
# Reference hardware (interference check, CoM, renders)
# ---------------------------------------------------------------------------
def build_reference(col, join_pts):
    e = 0.05
    ay = P["axle_y"]
    refs, render = [], []
    # wheels (rendered)
    for s in (-1, 1):
        w = cyl(
            "ref_wheel", col, P["wheel_d"], P["wheel_w"] - 2 * e, (s * WHEEL_X, ay, AXLE_Z), "X"
        )
        refs.append(w)
        render.append(w)
        refs.append(
            box(
                "ref_n20",
                col,
                P["motor_len"] - 2 * e,
                P["motor_w"] - 2 * e,
                P["motor_h"] - 2 * e,
                s * (MOTOR_FACE + MOTOR_BACK) / 2,
                ay,
                AXLE_Z,
            )
        )
        el, ew, eh = P["encoder"]
        refs.append(
            box(
                "ref_encoder",
                col,
                el - 2 * e,
                ew - 2 * e,
                eh - 2 * e,
                s * (MOTOR_BACK - el / 2),
                ay,
                AXLE_Z,
            )
        )
        render += refs[-2:]
    # caster (rendered): plate + housing + ball
    cw, cd, ch = P["caster_size"]
    cy = P["caster_y"]
    for ob in (
        box("ref_caster_plate", col, cw, cd, 3.0 - e, 0, cy, Z_B - 1.5),
        cyl(
            "ref_caster_body",
            col,
            22.0,
            ch - 3.0 - P["caster_ball_d"] / 2,
            (0, cy, (Z_B - 3.0 + P["caster_ball_d"] / 2) / 2),
        ),
        cyl(
            "ref_caster_ball",
            col,
            P["caster_ball_d"] - 0.2,
            P["caster_ball_d"] / 2 - 0.3,
            (0, cy, P["caster_ball_d"] / 4),
        ),
    ):
        refs.append(ob)
        render.append(ob)
    # electronics envelopes
    bw, bd, bh = P["battery"]
    refs.append(box("ref_battery", col, bw, bd, bh - 2 * e, 0, P["battery_y"], Z_B + bh / 2))
    dw, dd, dh = P["driver"]
    refs.append(box("ref_driver", col, dw, dd, dh, 0, P["driver_y"], FLOOR_TOP + dh / 2 + 0.05))
    pw, pd, ph = P["power"]
    refs.append(box("ref_power", col, pw, pd, ph, 0, P["power_y"], FLOOR_TOP + 4.0 + ph / 2 + 0.05))
    cx_, cy_, cz_ = P["pi_case"]
    px, py = P["pi_center"]
    refs.append(
        box(
            "ref_pi5_case",
            col,
            cx_,
            cy_,
            cz_ - 2 * e,
            px,
            py,
            TRAY_TOP + P["pi_standoff_h"] + cz_ / 2,
        )
    )
    ys, zs, sr = P["speaker_y"], P["speaker_z"], P["speaker_d"] / 2
    x_face = max(edge_x(3, y, zs + sr, P["wall"]) for y in (ys - sr, ys + sr)) + 0.3
    refs.append(
        cyl(
            "ref_speaker",
            col,
            P["speaker_d"] - 2 * e,
            P["speaker_depth"] - 2 * e,
            (x_face + P["speaker_depth"] / 2, ys, zs),
            "X",
        )
    )
    refs.append(
        cyl(
            "ref_speaker_magnet", col, 22.0, 10.0, (x_face + P["speaker_depth"] + 5.05, ys, zs), "X"
        )
    )
    aw_, ad_, ah_ = P["amp_board"]
    refs.append(
        box(
            "ref_amp",
            col,
            aw_,
            ad_,
            ah_,
            P["amp_pos"][0],
            P["amp_pos"][1],
            TRAY_TOP + ah_ / 2 + 0.05,
        )
    )
    ex, ey, ez = P["face_module_env"]
    plate_back = YF + P["face_inset"] + P["face_panel_t"] + P["face_flange_t"]
    refs.append(
        box(
            "ref_face_module",
            col,
            ex,
            ey,
            ez,
            0,
            plate_back + ey / 2 + 0.1,
            P["face_open_bottom"] + 2.0 + ez / 2,
        )
    )
    mw, md, mh = P["mic_board"]
    my = P["mic_y"]
    refs.append(box("ref_mic", col, mw, md, mh, 0, my, rim_z(my + md / 2) - mh / 2 - 0.3))
    hs, dep = P["cam_housing"] - 1.0, P["cam_depth"]
    refs.append(
        box(
            "ref_cam_housing",
            col,
            hs,
            dep - 0.2,
            hs,
            P["cam_x"],
            FRONT_IN + dep / 2 + 0.05,
            P["cam_lens_z"],
        )
    )
    bw2, bh2 = P["cam_board"]
    refs.append(
        box(
            "ref_cam_pcb",
            col,
            bw2,
            1.0,
            bh2,
            P["cam_x"],
            FRONT_IN + dep + 0.6,
            P["cam_lens_z"] + P["cam_lens_top"] - bh2 / 2,
        )
    )
    tw, th = P["tof_board"]
    refs.append(
        box(
            "ref_tof",
            col,
            tw,
            2.5,
            th,
            P["tof_x"],
            FRONT_IN + P["plate_t"] + P["clearance"] + 1.35,
            P["tof_z"],
        )
    )
    # screws driven from inside: head + vertical tool path up to the rim
    for x, y in join_pts:
        refs.append(cyl("ref_join_head", col, 6.0, 3.0, (x, y, TRAY_TOP + 1.55)))
        top = rim_z(y) - 1.0
        refs.append(
            cyl("ref_join_tool", col, 6.0, top - TRAY_TOP - 3.2, (x, y, (TRAY_TOP + 3.1 + top) / 2))
        )
    for ob in refs:
        ob.display_type = "WIRE"
        ob.hide_render = True
    for ob in render:
        ob.display_type = "SOLID"
        ob.hide_render = False
    for ob in render:
        ob.color = (
            (0.03, 0.03, 0.03, 1)
            if "wheel" in ob.name
            else (0.30, 0.30, 0.32, 1)
            if ("n20" in ob.name or "encoder" in ob.name)
            else (0.55, 0.56, 0.58, 1)
        )
    # lit-LED markers on the faceplate front (preview / render only)
    fy = YF + P["face_inset"] - 0.06
    for x, z, d, colr in (
        (-P["led_dx"] / 2, P["led_z"], P["led_d"], (1.0, 0.85, 0.55, 1)),
        (P["led_dx"] / 2, P["led_z"], P["led_d"], (1.0, 0.85, 0.55, 1)),
        (P["status_pos"][0], P["status_pos"][1], P["status_d"], (1.0, 0.95, 0.85, 1)),
    ):
        ob = cyl("ref_led_glow", col, d, 0.1, (x, fy, z), "Y", seg=24)
        ob.color = colr
        refs.append(ob)
    return refs


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bm.free()
    d = ob.dimensions
    return {
        "non_manifold_edges": nm,
        "dims_mm": [round(d.x, 1), round(d.y, 1), round(d.z, 1)],
        "volume_cm3": round(vol / 1000, 1),
    }


def centroid(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    v_tot, acc = 0.0, Vector()
    for f in bm.faces:
        a, b, c = (v.co for v in f.verts)
        v = a.dot(b.cross(c)) / 6.0
        v_tot += v
        acc += v * (a + b + c) / 4.0
    bm.free()
    return acc / v_tot, abs(v_tot)


def com_check(parts, refs):
    m = P["mass"]
    items = []
    for ob in parts:
        c, v = centroid(ob)
        items.append((v / 1000 * P["print_density"], c))
    pick = {
        "ref_pi5_case": m["pi"],
        "ref_battery": m["battery"],
        "ref_n20": m["motor"],
        "ref_wheel": m["wheel"],
        "ref_speaker": m["speaker"],
        "ref_power": m["power"],
        "ref_driver": m["driver"],
        "ref_cam_pcb": m["camera"],
        "ref_amp": m["amp"],
    }
    for ob in refs:
        key = ob.name.split(".")[0]
        if key in pick:
            items.append((pick[key], centroid(ob)[0]))
    mt = sum(w for w, _ in items)
    com = sum((c * w for w, c in items), Vector()) / mt
    # support triangle: caster ball + the two wheel contact points
    tri = [
        Vector((0, P["caster_y"])),
        Vector((WHEEL_X, P["axle_y"])),
        Vector((-WHEEL_X, P["axle_y"])),
    ]
    p = com.to_2d()
    sign = 1.0 if (tri[1] - tri[0]).cross(tri[2] - tri[0]) > 0 else -1.0
    margins = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        margins.append(sign * (b - a).normalized().cross(p - a))  # >0 inside, distance to the edge
    return {
        "mass_g": round(mt),
        "com_mm": [round(x, 1) for x in com],
        "min_margin_to_tip_edge_mm": round(min(margins), 1),
    }


def overhangs(ob, max_angle=45.0, min_size=10.0):
    """Downward faces steeper than max_angle from vertical, in print orientation, grouped into
    regions; regions under min_size (small holes) ignored. Flat regions are bridges/ceilings."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.transform(bm, matrix=PRINT_ROT[ob.name] @ ob.matrix_world, verts=bm.verts)
    bm.normal_update()
    zmin = min(v.co.z for v in bm.verts)
    lim = -math.sin(math.radians(max_angle)) - 0.01
    bad = {f for f in bm.faces if f.normal.z < lim and f.calc_center_median().z > zmin + 0.05}
    regions, seen = [], set()
    for f in bad:
        if f in seen:
            continue
        stack, reg = [f], []
        seen.add(f)
        while stack:
            cur = stack.pop()
            reg.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb in bad and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        vs = [v.co for cur in reg for v in cur.verts]
        ext = [max(v[i] for v in vs) - min(v[i] for v in vs) for i in range(3)]
        if max(ext[0], ext[1]) < min_size:
            continue
        regions.append(
            {
                "flat": all(cur.normal.z < -0.99 for cur in reg),
                "xy_extent": [round(ext[0], 1), round(ext[1], 1)],
                "z": round(min(v.z for v in vs) - zmin, 1),
                "area": round(sum(cur.calc_area() for cur in reg), 1),
            }
        )
    bm.free()
    return regions


def intersect_volume(a, b):
    me = a.data.copy()
    tmp = bpy.data.objects.new("_ix", me)
    bpy.context.scene.collection.objects.link(tmp)
    mod = tmp.modifiers.new("ix", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "INTERSECT", "MANIFOLD", b
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = tmp.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    vol = abs(bm.calc_volume())
    bm.free()
    ev.to_mesh_clear()
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.meshes.remove(me)
    return vol


def interference(parts, refs, tol=1.0):
    hits = {}
    items = [r for r in refs if not r.name.startswith("ref_led")] + parts
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            v = intersect_volume(a, b)
            if v > tol:
                hits[f"{a.name} x {b.name}"] = round(v, 1)
    return hits


_RX90 = Matrix.Rotation(math.radians(90), 4, "X")
PRINT_ROT = {
    "chassis": Matrix.Identity(4),
    "battery-door": Matrix.Identity(4),  # outer face on the bed
    "pi-module": Matrix.Identity(4),
    "top-cover": Matrix.Rotation(-math.atan(SLOPE), 4, "X"),  # sloped bottom flat on the bed
    "faceplate": Matrix.Rotation(math.radians(-90), 4, "X"),  # back (flange) on the bed
    "sensor-mount": _RX90,  # front on the bed
}


def print_mesh(ob):
    me = ob.data.copy()
    me.transform(ob.matrix_world)
    me.transform(PRINT_ROT[ob.name])
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs))))
    return me, (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def bed_fit(parts):
    out = {}
    for ob in parts:
        me, size = print_mesh(ob)
        bpy.data.meshes.remove(me)
        out[ob.name] = {
            "print_size_mm": [round(s, 1) for s in size],
            "fits": size[0] <= P["bed_xy"] and size[1] <= P["bed_xy"],
        }
    return out


def export_stl(parts, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    tmp_col = _collection("_export_tmp")
    written = {}
    for ob in parts:
        me, _ = print_mesh(ob)
        tmp = bpy.data.objects.new(ob.name + "_print", me)
        tmp_col.objects.link(tmp)
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        tmp.select_set(True)
        bpy.context.view_layer.objects.active = tmp
        path = os.path.normpath(os.path.join(out_dir, ob.name + ".stl"))
        bpy.ops.wm.stl_export(
            filepath=path,
            export_selected_objects=True,
            global_scale=1.0,
            use_scene_unit=False,
            apply_modifiers=True,
        )
        written[ob.name] = path
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.meshes.remove(me)
    bpy.data.collections.remove(tmp_col)
    return written


# ---------------------------------------------------------------------------
# Three-view render (front / side / bottom), one pass, same scale
# ---------------------------------------------------------------------------
def render_views(out_dir, labels):
    import numpy as np

    sc = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    vcol = _collection("Mirae_Views")
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "OBJECT"
    sh.show_cavity, sh.show_object_outline = True, True
    sh.show_shadows = False
    sc.render.resolution_x = sc.render.resolution_y = 1000
    sc.render.film_transparent = False
    sc.world.color = (0.80, 0.79, 0.77)
    sh.background_type = "WORLD"
    views = [  # name, camera location, rotation, label location, label rotation
        ("front", (0, -600, 70), (90, 0, 0), (0, -300, -40), (90, 0, 0)),
        ("side", (-600, 0, 70), (90, 0, -90), (-300, 0, -40), (90, 0, -90)),
        ("bottom", (0, 0, -600), (180, 0, 0), (0, 128, -5), (180, 0, 0)),
    ]
    files = []
    for name, loc, rot, lloc, lrot in views:
        cam_data = bpy.data.cameras.new("cam_" + name)
        cam_data.type, cam_data.ortho_scale = "ORTHO", 280.0
        cam_data.clip_start, cam_data.clip_end = 1.0, 2000.0
        cam = bpy.data.objects.new("cam_" + name, cam_data)
        vcol.objects.link(cam)
        cam.location, cam.rotation_euler = loc, [math.radians(a) for a in rot]
        txt = bpy.data.curves.new("lbl_" + name, "FONT")
        txt.body, txt.size, txt.align_x = labels[name], 9.0, "CENTER"
        tob = bpy.data.objects.new("lbl_" + name, txt)
        vcol.objects.link(tob)
        tob.location, tob.rotation_euler = lloc, [math.radians(a) for a in lrot]
        tob.color = (0.25, 0.25, 0.25, 1)
    for name, *_ in views:
        sc.camera = bpy.data.objects["cam_" + name]
        path = os.path.join(out_dir, f"mirae_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        files.append(path)
    imgs = [bpy.data.images.load(f, check_existing=False) for f in files]
    w, h = imgs[0].size
    arrs = [np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4) for im in imgs]
    sep = np.ones((h, 6, 4), dtype=np.float32) * np.array([0.55, 0.55, 0.55, 1.0], dtype=np.float32)
    combo = np.concatenate([arrs[0], sep, arrs[1], sep, arrs[2]], axis=1)
    out = bpy.data.images.new("mirae_views", combo.shape[1], combo.shape[0], alpha=True)
    out.pixels.foreach_set(combo.ravel())
    out.filepath_raw = os.path.join(out_dir, "mirae_views.png")
    out.file_format = "PNG"
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)
    return files + [os.path.join(out_dir, "mirae_views.png")]


COLORS = {
    "chassis": (0.10, 0.10, 0.11, 1),  # charcoal
    "battery-door": (0.10, 0.10, 0.11, 1),
    "pi-module": (0.93, 0.92, 0.89, 1),  # warm white
    "top-cover": (0.93, 0.92, 0.89, 1),
    "faceplate": (0.96, 0.95, 0.93, 1),
    "sensor-mount": (0.04, 0.04, 0.04, 1),
}


def build():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"
    parts_col = _collection("Mirae")
    ref_col = _collection("Mirae_Reference")
    chassis, join_pts = build_chassis(parts_col)
    pi_mod, col_top = build_pi_module(parts_col, join_pts)
    parts = [
        chassis,
        build_battery_door(parts_col),
        pi_mod,
        build_top_cover(parts_col, col_top),
        build_faceplate(parts_col),
        build_sensor_mount(parts_col),
    ]
    refs = build_reference(ref_col, join_pts)
    for ob in parts:
        ob.color = COLORS[ob.name]
    return parts, refs


EXPORT = globals().get("EXPORT", True)
RENDER = globals().get("RENDER", False)

if __name__ == "__main__" or True:
    PARTS, REFS = build()
    REPORT = {ob.name: check(ob) for ob in PARTS}
    REPORT["_interference"] = interference(PARTS, REFS)
    REPORT["_overhangs"] = {ob.name: overhangs(ob) for ob in PARTS}
    REPORT["_bed_fit"] = bed_fit(PARTS)
    REPORT["_com"] = com_check(PARTS, REFS)
    ok = (
        all(REPORT[o.name]["non_manifold_edges"] == 0 for o in PARTS)
        and not REPORT["_interference"]
        and all(v["fits"] for v in REPORT["_bed_fit"].values())
        and REPORT["_com"]["min_margin_to_tip_edge_mm"] > 5.0
    )
    if EXPORT and ok:
        REPORT["_exported"] = export_stl(PARTS, os.path.join(ROOT, "..", "stl"))
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "robot.blend"))
    hmax = max(v.co.z for v in PARTS[3].data.vertices)
    REPORT["_derived"] = {
        "footprint_mm": [P["WF"], P["L"]],
        "height_mm": round(hmax, 1),
        "caster_height_required": Z_B,
        "axle_z": AXLE_Z,
        "axle_y": P["axle_y"],
        "wheel_x": round(WHEEL_X, 1),
        "track_mm": round(2 * WHEEL_X, 1),
        "wheelbase_mm": round(P["axle_y"] - P["caster_y"], 1),
        "motor_gap_mm": round(2 * ENC_BACK, 1),
        "export_gate_ok": ok,
    }
    if RENDER:
        REPORT["_renders"] = render_views(
            os.path.join(ROOT, "..", "renders"),
            {
                "front": f"FRONT   {P['WF']:.0f} mm wide",
                "side": f"SIDE   {P['L']:.0f} mm long  x  {hmax:.0f} mm tall",
                "bottom": "BOTTOM   front caster + 2 rear-centre wheels",
            },
        )
