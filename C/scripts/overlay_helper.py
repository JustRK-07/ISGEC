#!/usr/bin/env python3
"""overlay_helper.py — shared helpers for C/scripts/overlay.py.

Used to factor out the entity-level transform helpers from
A/scripts/overlay.py so they're independently importable.
"""


def prescale_entity(entity, sx, sy, ip_x=0.0, ip_y=0.0):
    """Bake INSERT position + xscale into each entity in a block.
    Converts block-local coords → STR-world coords by replicating
    `INSERT.pos + xscale * local`."""
    if sx == 1.0 and sy == 1.0 and ip_x == 0.0 and ip_y == 0.0:
        return
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = (ip_x + sx * entity.dxf.start[0],
                                ip_y + sy * entity.dxf.start[1], 0.0)
            entity.dxf.end = (ip_x + sx * entity.dxf.end[0],
                              ip_y + sy * entity.dxf.end[1], 0.0)
        elif t == "LWPOLYLINE":
            new_pts = [(ip_x + sx * v[0], ip_y + sy * v[1]) for v in entity.vertices()]
            entity.clear()
            for p in new_pts:
                entity.append_vertices(p)
        elif t in ("CIRCLE", "ARC"):
            entity.dxf.center = (ip_x + sx * entity.dxf.center[0],
                                 ip_y + sy * entity.dxf.center[1], 0.0)
            entity.dxf.radius = entity.dxf.radius * max(abs(sx), abs(sy))
        elif t == "ELLIPSE":
            entity.dxf.center = (ip_x + sx * entity.dxf.center[0],
                                 ip_y + sy * entity.dxf.center[1], 0.0)
            m = entity.dxf.major_axis
            entity.dxf.major_axis = (m[0] * sx, m[1] * sy, m[2])
        elif t == "POINT":
            entity.dxf.location = (ip_x + sx * entity.dxf.location[0],
                                    ip_y + sy * entity.dxf.location[1], 0.0)
        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = (ip_x + sx * entity.dxf.insert[0],
                                  ip_y + sy * entity.dxf.insert[1], 0.0)
        elif t == "SPLINE":
            try:
                cps = list(entity.control_points)
                entity.control_points = [(ip_x + sx * p[0], ip_y + sy * p[1]) for p in cps]
            except Exception:
                pass
        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    new_verts = []
                    for v in verts:
                        nx, ny = ip_x + sx * v[0], ip_y + sy * v[1]
                        if len(v) >= 3:
                            new_verts.append((nx, ny, v[2]))
                        else:
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception:
                    pass
        elif t == "DIMENSION":
            try:
                entity.dxf.insert = (ip_x + sx * entity.dxf.insert[0],
                                      ip_y + sy * entity.dxf.insert[1], 0.0)
            except Exception:
                pass
        elif t in ("SOLID", "TRACE", "3DFACE"):
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3",
                         "first_corner", "second_corner", "third_corner", "fourth_corner"):
                try:
                    v = getattr(entity.dxf, attr)
                    setattr(entity.dxf, attr, (ip_x + sx * v[0],
                                               ip_y + sy * v[1], v[2]))
                except Exception:
                    pass
    except Exception:
        pass


def transform_xy(x, y, ax, ay, bx, by):
    return (ax * x + bx, ay * y + by)


def transform_entity_inplace(entity, ax, ay, bx, by):
    """Apply the affine to an entity in place. INSERTs are intentionally
    NOT transformed (the caller pre-scales their block contents and snaps
    them to (0, 0, 0) with xscale=1 first)."""
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1], ax, ay, bx, by)
            entity.dxf.end = transform_xy(entity.dxf.end[0], entity.dxf.end[1], ax, ay, bx, by)
        elif t == "LWPOLYLINE":
            new_pts = [transform_xy(v[0], v[1], ax, ay, bx, by) for v in entity.vertices()]
            entity.clear()
            for p in new_pts:
                entity.append_vertices(p)
        elif t in ("CIRCLE", "ARC"):
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1], ax, ay, bx, by)
            r_scale = max(abs(ax), abs(ay))
            entity.dxf.radius = entity.dxf.radius * r_scale
        elif t == "ELLIPSE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1], ax, ay, bx, by)
            m = entity.dxf.major_axis
            entity.dxf.major_axis = (m[0] * ax, m[1] * ay, m[2])
        elif t == "POINT":
            entity.dxf.location = transform_xy(entity.dxf.location[0], entity.dxf.location[1], ax, ay, bx, by)
        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1], ax, ay, bx, by)
            try:
                if entity.dxf.hasattr("alignment_point") and entity.dxf.alignment_point:
                    entity.dxf.alignment_point = transform_xy(
                        entity.dxf.alignment_point[0], entity.dxf.alignment_point[1],
                        ax, ay, bx, by)
            except Exception:
                pass
            try:
                entity.dxf.height = entity.dxf.height * max(abs(ax), abs(ay))
            except Exception:
                pass
        elif t == "INSERT":
            pass  # leave at (0, 0) with xscale=1
        elif t == "SPLINE":
            try:
                cps = list(entity.control_points)
                entity.control_points = [transform_xy(p[0], p[1], ax, ay, bx, by) for p in cps]
            except Exception:
                pass
            try:
                fps = list(entity.fit_points)
                entity.fit_points = [transform_xy(p[0], p[1], ax, ay, bx, by) for p in fps]
            except Exception:
                pass
        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    new_verts = []
                    for v in verts:
                        nx, ny = transform_xy(v[0], v[1], ax, ay, bx, by)
                        if len(v) >= 3:
                            new_verts.append((nx, ny, v[2]))
                        else:
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception:
                    pass
        elif t == "DIMENSION":
            try:
                entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1], ax, ay, bx, by)
            except Exception:
                pass
        elif t in ("SOLID", "TRACE", "3DFACE"):
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3",
                         "first_corner", "second_corner", "third_corner", "fourth_corner"):
                try:
                    v = getattr(entity.dxf, attr)
                    setattr(entity.dxf, attr, transform_xy(v[0], v[1], ax, ay, bx, by))
                except Exception:
                    pass
    except Exception:
        pass
