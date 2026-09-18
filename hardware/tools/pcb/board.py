#!/usr/bin/env python3
"""Board construction helpers on the pcbnew Python API (KiCad 10, system python3).

Usage from build_pcb.py.  Everything here is deterministic: the board is rebuilt
from the KiCad netlist exported by tools/sch/build.py plus the placement and
copper described in code, so it is regenerable like the schematic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KICAD = ROOT / "hardware" / "kicad"
sys.path.insert(0, str(HERE.parent / "sch"))
from sexp import child, find_all, parse  # noqa: E402

FP_DIRS = [Path("/usr/share/kicad/footprints"), KICAD]


def mm(v: float) -> int:
    return pcbnew.FromMM(v)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def load_netlist(path: Path):
    """[(ref, value, footprint 'Lib:Name', {pin: net})] and {net: [(ref, pin)]}"""
    tree = parse(path.read_text())
    comps = {}
    for c in find_all(tree, "comp"):
        ref = child(c, "ref")[1]
        comps[ref] = {
            "value": child(c, "value")[1],
            "footprint": child(c, "footprint")[1] if child(c, "footprint") else "",
            "pins": {},
            "fields": {child(f, "name")[1]: f[-1] for f in (child(c, "fields") or [])[1:] if isinstance(f, list) and isinstance(f[-1], str)},
            "dnp": any(isinstance(p, list) and p[0] == "property" and child(p, "name") and child(p, "name")[1] == "dnp" for p in c),
        }
    nets = {}
    for n in find_all(tree, "net"):
        name = child(n, "name")[1]
        nodes = [(child(nd, "ref")[1], child(nd, "pin")[1]) for nd in n if isinstance(nd, list) and nd[0] == "node"]
        nets[name] = nodes
        for ref, pin in nodes:
            comps[ref]["pins"][pin] = name
    return comps, nets


def load_footprint(fpid: str) -> pcbnew.FOOTPRINT:
    lib, name = fpid.split(":", 1)
    for d in FP_DIRS:
        p = d / f"{lib}.pretty"
        if p.is_dir():
            fp = pcbnew.FootprintLoad(str(p), name)
            if fp is not None:
                return fp
    raise FileNotFoundError(fpid)


class Board:
    def __init__(self):
        self.b = pcbnew.BOARD()
        self.b.SetCopperLayerCount(4)
        self.nets: dict[str, pcbnew.NETINFO_ITEM] = {}
        self.fps: dict[str, pcbnew.FOOTPRINT] = {}

    # ------------------------------------------------------------ netlist
    def populate(self, netlist: Path):
        comps, nets = load_netlist(netlist)
        for name in nets:
            ni = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(ni)
            self.nets[name] = ni
        for ref, c in comps.items():
            if not c["footprint"]:
                continue
            fp = load_footprint(c["footprint"])
            fp.SetReference(ref)
            fp.SetValue(c["value"])
            for k, v in c["fields"].items():
                if k in ("LCSC", "Note"):
                    fp.SetField(k, v)
            if c["dnp"]:
                fp.SetDNP(True)
            for f in fp.GetFields():
                if f.GetName() != "Reference":
                    f.SetVisible(False)          # Value / LCSC / Note stay in the file, off the silk
            r = fp.Reference()
            r.SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
            r.SetTextThickness(mm(0.1))
            for pad in fp.Pads():
                net = c["pins"].get(pad.GetNumber())
                if net:
                    pad.SetNet(self.nets[net])
            self.b.Add(fp)
            self.fps[ref] = fp
        return comps, nets

    # ------------------------------------------------------------ placement
    def place(self, ref: str, x: float, y: float, rot: float = 0.0, back: bool = False):
        fp = self.fps[ref]
        if back != fp.IsFlipped():
            fp.Flip(fp.GetPosition(), False)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        return fp

    def pad_pos(self, ref: str, pad: str) -> tuple[float, float]:
        for p in self.fps[ref].Pads():
            if p.GetNumber() == pad:
                v = p.GetPosition()
                return pcbnew.ToMM(v.x), pcbnew.ToMM(v.y)
        raise KeyError((ref, pad))

    # ------------------------------------------------------------ geometry
    def outline(self, points: list[tuple[float, float]], width: float = 0.1):
        for i in range(len(points)):
            a, b_ = points[i], points[(i + 1) % len(points)]
            seg = pcbnew.PCB_SHAPE(self.b)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(pt(*a))
            seg.SetEnd(pt(*b_))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(mm(width))
            self.b.Add(seg)

    def outline_arc_rect(self, x0, y0, x1, y1, r: float):
        """Rounded rectangle outline on Edge.Cuts."""
        def seg(a, b_):
            s = pcbnew.PCB_SHAPE(self.b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pt(*a)); s.SetEnd(pt(*b_)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); self.b.Add(s)

        def arc(cx, cy, start, end):
            a = pcbnew.PCB_SHAPE(self.b)
            a.SetShape(pcbnew.SHAPE_T_ARC)
            a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(mm(0.1))
            a.SetCenter(pt(cx, cy)); a.SetStart(pt(*start)); a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(-90, pcbnew.DEGREES_T), False)
            self.b.Add(a)

        seg((x0 + r, y0), (x1 - r, y0)); seg((x1, y0 + r), (x1, y1 - r)); seg((x1 - r, y1), (x0 + r, y1)); seg((x0, y1 - r), (x0, y0 + r))
        arc(x1 - r, y0 + r, (x1 - r, y0), (x1, y0 + r))
        arc(x1 - r, y1 - r, (x1, y1 - r), (x1 - r, y1))
        arc(x0 + r, y1 - r, (x0 + r, y1), (x0, y1 - r))
        arc(x0 + r, y0 + r, (x0, y0 + r), (x0 + r, y0))

    def track(self, net: str, a, b_, width: float, layer=pcbnew.F_Cu):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(pt(*a)); t.SetEnd(pt(*b_)); t.SetWidth(mm(width)); t.SetLayer(layer); t.SetNet(self.nets[net])
        self.b.Add(t)
        return t

    def via(self, net: str, x, y, drill: float = 0.3, size: float = 0.6):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pt(x, y)); v.SetDrill(mm(drill)); v.SetWidth(mm(size)); v.SetNet(self.nets[net])
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        self.b.Add(v)
        return v

    def zone(self, net: str, layer, points, priority: int = 0, clearance: float = 0.25, min_width: float = 0.25, thermal: bool = False, name: str = ""):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer)
        z.SetNet(self.nets[net])
        z.SetAssignedPriority(priority)
        z.SetLocalClearance(mm(clearance))
        z.SetMinThickness(mm(min_width))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
        z.SetZoneName(name)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in points:
            ol.Append(mm(x), mm(y))
        self.b.Add(z)
        return z

    def keepout(self, layers, points, name: str = "", tracks=True, vias=True, pads=False, copper=True):
        z = pcbnew.ZONE(self.b)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias); z.SetDoNotAllowPads(pads); z.SetDoNotAllowZoneFills(copper)
        z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for l in layers:
            ls.addLayer(l)
        z.SetLayerSet(ls)
        z.SetZoneName(name)
        ol = z.Outline(); ol.NewOutline()
        for x, y in points:
            ol.Append(mm(x), mm(y))
        self.b.Add(z)
        return z

    def text(self, s: str, x, y, layer=pcbnew.F_SilkS, size: float = 1.0, rot: float = 0):
        t = pcbnew.PCB_TEXT(self.b)
        t.SetText(s); t.SetPosition(pt(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(size * 0.15))
        t.SetTextAngleDegrees(rot)
        self.b.Add(t)
        return t

    # ------------------------------------------------------------ rules
    def design_rules(self):
        ds = self.b.GetDesignSettings()
        ds.m_MinClearance = mm(0.1)    # JLC 1 oz outer, 4-layer: 0.09/0.09 mm
        ds.m_TrackMinWidth = mm(0.1)
        ds.m_ViasMinSize = mm(0.4)
        ds.m_MinThroughDrill = mm(0.2)
        ds.m_ViasMinAnnularWidth = mm(0.1)
        ds.m_CopperEdgeClearance = mm(0.3)
        ds.m_SolderMaskMinWidth = mm(0.0)
        ds.SetBoardThickness(mm(1.6))

    def fill_zones(self):
        filler = pcbnew.ZONE_FILLER(self.b)
        filler.Fill(self.b.Zones())

    def save(self, path: Path):
        pcbnew.SaveBoard(str(path), self.b)
