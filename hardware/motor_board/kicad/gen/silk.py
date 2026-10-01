"""Silkscreen for JLC (tail_apply op "silk"):
- keep:   regex of parts that keep their silk (handled after assembly); every other part's silk graphics move to its Fab
          layer and its reference is hidden
- mark:   regex of orientation-sensitive parts (ICs, diodes, FETs): a filled 0.5 mm dot just outside pad 1 (pad 1 = pin 1 /
          cathode), on the part's side, clear of pads; JLC checks polarity against the silk
- labels: [(text, ref, pad, sides)] function labels (wire names, polarity) placed next to the pad, sides "F", "B" or "FB";
          a label replaces the part's reference (hidden) when hide_ref lists the part
Kept outlines are drawn at JLC's 0.15 mm minimum and any kept silk segment closer than EDGE to the board edge is dropped.
Text is 1.0 mm / 0.15 mm (JLC minimum), mirrored on the bottom; every text is placed at the first candidate spot that is
inside the board (EDGE), off every mask opening on its side (+0.15) and off the other silk placed so far."""
import math
import re

import pcbnew

TXT_H, TXT_W, LINE_W, EDGE, PAD_CLR, DOT_R = 1.0, 0.15, 0.15, 0.3, 0.15, 0.25
F = pcbnew.FromMM
t = pcbnew.ToMM


def _rect(bb, grow=0.0):
    return (t(bb.GetLeft()) - grow, t(bb.GetTop()) - grow, t(bb.GetRight()) + grow, t(bb.GetBottom()) + grow)


def _hit(a, c):
    return not (a[2] <= c[0] or c[2] <= a[0] or a[3] <= c[1] or c[3] <= a[1])


def _shape_boxes(g, grow=0.1):
    """thin boxes along a silk shape (a rectangle / circle outline does not block its inside)"""
    st = g.GetShape()
    if st == pcbnew.SHAPE_T_RECT:
        r = _rect(g.GetBoundingBox())
        return [(r[0] - grow, r[1] - grow, r[2] + grow, r[1] + grow), (r[0] - grow, r[3] - grow, r[2] + grow, r[3] + grow),
                (r[0] - grow, r[1] - grow, r[0] + grow, r[3] + grow), (r[2] - grow, r[1] - grow, r[2] + grow, r[3] + grow)]
    if st == pcbnew.SHAPE_T_CIRCLE and not g.IsSolidFill():
        c, rad = g.GetCenter(), t(g.GetRadius())
        out = []
        for k in range(16):
            a = 2 * math.pi * k / 16
            x, y = t(c.x) + rad * math.cos(a), t(c.y) + rad * math.sin(a)
            out.append((x - grow - 0.2, y - grow - 0.2, x + grow + 0.2, y + grow + 0.2))
        return out
    if st == pcbnew.SHAPE_T_SEGMENT:
        a, c = g.GetStart(), g.GetEnd()
        n = max(1, int(math.dist((t(a.x), t(a.y)), (t(c.x), t(c.y))) / 0.4))
        out = []
        for k in range(n + 1):
            x, y = t(a.x) + (t(c.x) - t(a.x)) * k / n, t(a.y) + (t(c.y) - t(a.y)) * k / n
            out.append((x - grow - 0.1, y - grow - 0.1, x + grow + 0.1, y + grow + 0.1))
        return out
    return [_rect(g.GetBoundingBox(), grow)]


def apply(b, e, log=print):
    keep = re.compile(e.get("keep", r"$^"))
    mark = re.compile(e.get("mark", r"$^"))
    hide_ref = set(e.get("hide_ref", []))
    ob = _rect(b.GetBoardEdgesBoundingBox())
    inner = (ob[0] + 0.05 + EDGE, ob[1] + 0.05 + EDGE, ob[2] - 0.05 - EDGE, ob[3] - 0.05 - EDGE)
    # mask openings per side (pads; THT pads on both)
    opening = {"F": [], "B": []}
    for f in b.GetFootprints():
        for p in f.Pads():
            r = _rect(p.GetBoundingBox(), PAD_CLR)
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                opening["F"].append(r); opening["B"].append(r)
            else:
                opening["B" if f.IsFlipped() else "F"].append(r)
    placed = {"F": [], "B": []}
    for f in b.GetFootprints():                      # M2 screw head (r ~1.9 mm) + margin: r 2.2 mm
        if re.fullmatch(r"MH\d+", f.GetReference()):
            c = f.GetPosition(); R = 2.2
            for side in ("F", "B"):
                placed[side].append((t(c.x) - R, t(c.y) - R, t(c.x) + R, t(c.y) + R))

    def free(r, side):
        return (inner[0] <= r[0] and inner[1] <= r[1] and r[2] <= inner[2] and r[3] <= inner[3]
                and not any(_hit(r, o) for o in opening[side]) and not any(_hit(r, o) for o in placed[side]))

    def place(item, side, around, prefer=None, maxgap=3.5):
        """move a text item to the first free spot around a box (x0,y0,x1,y1); returns True if placed"""
        for ang in (0, 90):
            item.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
            if _place(item, side, around, prefer, maxgap):
                return True
        item.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
        return False

    def _place(item, side, around, prefer, maxgap):
        cx, cy = (around[0] + around[2]) / 2, (around[1] + around[3]) / 2
        hw, hh = (around[2] - around[0]) / 2, (around[3] - around[1]) / 2
        item.SetPosition(pcbnew.VECTOR2I_MM(0, 0))
        tb = _rect(item.GetBoundingBox())
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        cands = []
        for gap in [g for g in (0.2, 0.4, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5) if g <= maxgap]:
            ks = range(24)
            if prefer is not None:                   # preferred side first (degrees, 0 = +x, 90 = +y)
                ks = sorted(ks, key=lambda k: abs((k * 15 - prefer + 180) % 360 - 180))
            for k in ks:                             # round the box, nearest-first ring by ring
                a = 2 * math.pi * k / 24
                ca, sa = math.cos(a), math.sin(a)
                # point on the box (inflated by gap + half the text) in direction a
                ex, ey = hw + gap + tw / 2, hh + gap + th / 2
                s = min(ex / abs(ca) if abs(ca) > 1e-6 else 1e9, ey / abs(sa) if abs(sa) > 1e-6 else 1e9)
                cands.append((cx + ca * s, cy + sa * s))
        for x, y in cands:
            item.SetPosition(pcbnew.VECTOR2I_MM(x, y))
            r = _rect(item.GetBoundingBox(), 0.1)
            if free(r, side):
                placed[side].append(r)
                return True
        return False

    def text_item(s, side):
        x = pcbnew.PCB_TEXT(b)
        x.SetText(s)
        x.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
        x.SetTextSize(pcbnew.VECTOR2I_MM(TXT_H, TXT_H)); x.SetTextThickness(F(TXT_W))
        if side == "B":
            x.SetMirrored(True)
        return x

    unplaced = []
    # 1) strip / keep footprint silk
    for f in b.GetFootprints():
        ref = f.GetReference()
        side = "B" if f.IsFlipped() else "F"
        if not keep.fullmatch(ref):
            f.Reference().SetVisible(False)
            for g in f.GraphicalItems():
                if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                    g.SetLayer(pcbnew.F_Fab if g.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab)
            continue
        for g in list(f.GraphicalItems()):
            if g.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS) or g.GetClass() != "PCB_SHAPE":
                continue
            g.SetWidth(max(g.GetWidth(), F(LINE_W)))
            r = _rect(g.GetBoundingBox())
            if r[0] < inner[0] or r[1] < inner[1] or r[2] > inner[2] or r[3] > inner[3]:
                g.SetLayer(pcbnew.F_Fab if g.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab)
            else:
                placed[side] += _shape_boxes(g)
    # 2) pin-1 / cathode dots
    for f in b.GetFootprints():
        ref = f.GetReference()
        if not mark.fullmatch(ref):
            continue
        side = "B" if f.IsFlipped() else "F"
        p1 = [p for p in f.Pads() if p.GetNumber() == "1"]
        if not p1:
            unplaced.append(f"dot {ref} (no pad 1)"); continue
        p1 = p1[0]
        c = f.GetPosition(); pc = p1.GetPosition()
        pr = _rect(p1.GetBoundingBox())
        hx, hy = (pr[2] - pr[0]) / 2, (pr[3] - pr[1]) / 2
        dx, dy = t(pc.x - c.x), t(pc.y - c.y)
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        done = False
        # outward along centre->pad 1 first, then 16 directions round the pad
        dirs = [(ux, uy)] + [(math.cos(2 * math.pi * k / 16), math.sin(2 * math.pi * k / 16)) for k in range(16)]
        dirs.sort(key=lambda v: -(v[0] * ux + v[1] * uy))          # prefer the outward side
        for extra in (0.3, 0.45, 0.65, 0.9, 1.2):
            for vx, vy in dirs:
                d = math.hypot(abs(vx) * hx, abs(vy) * hy) + extra + DOT_R
                x, y = t(pc.x) + vx * d, t(pc.y) + vy * d
                r = (x - DOT_R - 0.05, y - DOT_R - 0.05, x + DOT_R + 0.05, y + DOT_R + 0.05)
                if free(r, side):
                    s = pcbnew.PCB_SHAPE(b)
                    s.SetShape(pcbnew.SHAPE_T_CIRCLE)
                    s.SetCenter(pcbnew.VECTOR2I_MM(x, y)); s.SetEnd(pcbnew.VECTOR2I_MM(x + DOT_R, y))
                    s.SetFillMode(pcbnew.FILL_T_FILLED_SHAPE); s.SetWidth(F(0.1))
                    s.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
                    b.Add(s)
                    placed[side].append(r)
                    done = True
                    break
            if done:
                break
        if not done:                                   # smaller dot (0.3 mm) outward, before the inboard fallback
            for extra in (0.2, 0.3, 0.45):
                for vx, vy in dirs:
                    d = math.hypot(abs(vx) * hx, abs(vy) * hy) + extra + 0.15
                    x, y = t(pc.x) + vx * d, t(pc.y) + vy * d
                    r = (x - 0.2, y - 0.2, x + 0.2, y + 0.2)
                    if free(r, side):
                        s = pcbnew.PCB_SHAPE(b)
                        s.SetShape(pcbnew.SHAPE_T_CIRCLE)
                        s.SetCenter(pcbnew.VECTOR2I_MM(x, y)); s.SetEnd(pcbnew.VECTOR2I_MM(x + 0.1, y))
                        s.SetFillMode(pcbnew.FILL_T_FILLED_SHAPE); s.SetWidth(F(0.1))
                        s.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
                        b.Add(s); placed[side].append(r); done = True
                        break
                if done:
                    break
        if not done:                                   # fallback: inside the package outline, inboard of pad 1
            for frac in (0.3, 0.38, 0.45):             # on the pad-1 side of the body: never at the centre
                x, y = t(pc.x) + (t(c.x) - t(pc.x)) * frac, t(pc.y) + (t(c.y) - t(pc.y)) * frac
                r = (x - 0.17, y - 0.17, x + 0.17, y + 0.17)
                if not any(_hit(r, o) for o in opening[side]) and not any(_hit(r, o) for o in placed[side]):
                    s = pcbnew.PCB_SHAPE(b)
                    s.SetShape(pcbnew.SHAPE_T_CIRCLE)
                    s.SetCenter(pcbnew.VECTOR2I_MM(x, y)); s.SetEnd(pcbnew.VECTOR2I_MM(x + 0.1, y))
                    s.SetFillMode(pcbnew.FILL_T_FILLED_SHAPE); s.SetWidth(F(0.1))
                    s.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
                    b.Add(s); placed[side].append(r); done = True
                    break
        if not done:
            unplaced.append(f"dot {ref}")
    # 3) function labels
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for lab in e.get("labels", []):
        s, ref, pad, sides = lab[:4]
        prefer = lab[4] if len(lab) > 4 else None
        f = fps[ref]
        p = [q for q in f.Pads() if q.GetNumber() == str(pad)][0]
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        body = _rect(cy.BBox()) if cy.OutlineCount() and re.fullmatch(r"J\d+", ref) else None
        for side in sides:
            x = text_item(s, side)
            if body:                                   # never under the part's own body (connector housings)
                placed[side].append(body)
            ok = place(x, side, _rect(p.GetBoundingBox()), prefer)
            if body:
                placed[side].remove(body)
            if ok:
                b.Add(x)
            else:
                unplaced.append(f"label {s} @ {ref}.{pad} {side}")
    # 3b) free texts: (text, side, (x, y) board-local) placed at the nearest free spot round the point
    OXl, OYl = ob[0] + 0.05, ob[1] + 0.05
    for s, side, (px, py) in e.get("texts", []):
        x = text_item(s, side)
        cx, cy = OXl + px, OYl + py
        if place(x, side, (cx - 0.1, cy - 0.1, cx + 0.1, cy + 0.1), maxgap=3.5):
            b.Add(x)
        else:
            unplaced.append(f"text {s}")
            if __import__("os").environ.get("SILK_DEBUG"):
                x.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T)); x.SetPosition(pcbnew.VECTOR2I_MM(cx, cy))
                r = _rect(x.GetBoundingBox(), 0.1)
                log(f"  dbg {s} rect {[round(v - o, 2) for v, o in zip(r, (OXl, OYl, OXl, OYl))]} inner_ok "
                    f"{inner[0] <= r[0] and inner[1] <= r[1] and r[2] <= inner[2] and r[3] <= inner[3]}")
                for o in opening[side] + placed[side]:
                    if _hit(r, o):
                        log(f"    hit {[round(v - w, 2) for v, w in zip(o, (OXl, OYl, OXl, OYl))]}")
    # 4) kept references: hide where a label names the part, else re-place them clear
    for f in b.GetFootprints():
        ref = f.GetReference()
        if not keep.fullmatch(ref):
            continue
        r = f.Reference()
        if ref in hide_ref:
            r.SetVisible(False); continue
        r.SetVisible(True)
        r.SetTextSize(pcbnew.VECTOR2I_MM(TXT_H, TXT_H)); r.SetTextThickness(F(TXT_W))
        side = "B" if f.IsFlipped() else "F"
        cy = f.GetCourtyard(pcbnew.B_CrtYd if side == "B" else pcbnew.F_CrtYd)
        box = _rect(cy.BBox()) if cy.OutlineCount() else _rect(f.GetBoundingBox(False))
        if not place(r, side, box, maxgap=2.0):
            r.SetVisible(False)
            unplaced.append(f"ref {ref} (hidden: no clear spot)")
    for u in unplaced:
        log(f"silk: {u}")
    log(f"silk: done ({len(unplaced)} not placed)")
