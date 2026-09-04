"""Explicit-placement KiCad schematic drawing on top of kicad-sch-api.

Connectivity comes from the SKiDL parts/nets in ``circuit.py``; this module
only adds geometry.  Everything you do not route by hand is finished
automatically by ``Sheet.finish()``:

* pins on a power net get a power symbol,
* pins on a net that also appears on another sheet get a global label,
* pins on a sheet-local net get a local label,
* unconnected pins get a no-connect flag.

Coordinates are millimetres on KiCad's 1.27 mm grid; ``G`` = 2.54 mm.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import kicad_sch_api as ksa

GRID = 1.27
G = 2.54
STUB = 2.54
REV = "v1.1"
DATE = "2026-09-03"

# power net -> symbol to use for it
POWER_SYMBOLS = {
    "GND": "power:GND",
    "+5V": "power:+5V",
    "+5V_PICO": "power:+5V",
    "+3V3_A": "power:+3V3",
    "+3V3_MCU": "power:+3V3",
    "+VDRV": "power:+5V",
    "VBAT": "power:+BATT",
    "VBAT_PACK": "power:+BATT",
    "W_VCC": "power:+5V",
    "+3V3_PICO": "power:+3V3",
    "VBAT_LINK": "power:+BATT",
}
GLOBAL_SHAPE = {"output": "output", "input": "input", "power_in": "passive", "power_out": "passive"}


def snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 2)


@dataclass
class PinGeom:
    part: object
    num: str
    name: str
    etype: str
    x: float
    y: float
    dx: int
    dy: int

    @property
    def pt(self):
        return (self.x, self.y)

    def out(self, n: float = STUB):
        return (snap(self.x + self.dx * n), snap(self.y + self.dy * n))

    @property
    def net(self):
        pin = self.part[self.num]
        return pin.net if pin.is_connected() else None


def _rot(x: float, y: float, deg: int):
    c, s = round(math.cos(math.radians(deg))), round(math.sin(math.radians(deg)))
    return (x * c + y * s, -x * s + y * c)


class Sheet:
    def __init__(self, design, key: str, title: str, path: Path, cross: set, paper: str = "A3", sid: int = 1):
        self.design = design
        self.key = key
        self.sid = sid
        self.path = Path(path)
        self.cross = cross  # net names that appear on more than one sheet
        self.sch = ksa.create_schematic(title)
        self.sch.set_paper_size(paper)
        self.cache = ksa.get_symbol_cache()
        self.comps: dict[str, object] = {}
        self.pins: dict[tuple[str, str], PinGeom] = {}
        self.covered: set[tuple[str, str]] = set()
        self.segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self.pwr_n = 0
        self.global_labels: list[tuple[str, float, float, int, str]] = []
        self.geom: dict[str, tuple] = {}  # ref -> (kind, x, y, rot, lib_id)
        self.extra_pts: set = set()  # power-symbol / flag pins that may sit mid-wire
        self.seen_segs: set = set()
        self.label_ends: set = set()  # (x, y) of label / power-symbol anchor points
        self.title = title

    # ------------------------------------------------------------ parts
    def lib_id(self, part) -> str:
        return f"{part.lib.filename.split('/')[-1].replace('.kicad_sym', '') if hasattr(part.lib, 'filename') and part.lib.filename else part.lib.name}:{part.name}"

    def place(self, part, x: float, y: float, rot: int = 0):
        lib_id = self.lib_id(part)
        x, y = snap(x), snap(y)
        props = {k: v for k, v in part.fields.items() if k not in ("Reference", "Value", "Footprint", "Datasheet")}
        comp = self.sch.components.add(lib_id=lib_id, reference=part.ref, value=str(part.value), position=(x, y), rotation=rot, footprint=part.footprint or "", **props)
        self.comps[part.ref] = comp
        sym = self.cache.get_symbol(lib_id)
        self.geom[part.ref] = ("part", x, y, rot, lib_id)
        for sp in sym.pins:
            lx, ly = sp.position.x, sp.position.y
            ex, ey = -round(math.cos(math.radians(sp.rotation))), -round(math.sin(math.radians(sp.rotation)))
            px, py = _rot(lx, -ly, rot)
            dx, dy = _rot(ex, -ey, rot)
            self.pins[(part.ref, str(sp.number))] = PinGeom(part, str(sp.number), sp.name, str(sp.pin_type).split(".")[-1].lower(), snap(x + px), snap(y + py), int(dx), int(dy))
        return comp

    def place_pin_at(self, part, pin_num, pt, rot: int = 0):
        """Place ``part`` so that its pin ``pin_num`` connection point lands on ``pt``."""
        lib_id = self.lib_id(part)
        sym = self.cache.get_symbol(lib_id)
        sp = next(p for p in sym.pins if str(p.number) == str(pin_num) or p.name == str(pin_num))
        px, py = _rot(sp.position.x, -sp.position.y, rot)
        return self.place(part, pt[0] - px, pt[1] - py, rot)

    def pin(self, part, num) -> PinGeom:
        try:
            return self.pins[(part.ref, str(num))]
        except KeyError:
            # look up by name
            for (ref, n), pg in self.pins.items():
                if ref == part.ref and pg.name == str(num):
                    return pg
            raise

    # ------------------------------------------------------------ wires
    def _seg(self, a, b):
        a = (snap(a[0]), snap(a[1]))
        b = (snap(b[0]), snap(b[1]))
        if a == b:
            return
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError(f"non-orthogonal segment {a}->{b} on {self.key}")
        key = (min(a, b), max(a, b))
        if key in self.seen_segs:
            return
        self.seen_segs.add(key)
        self.sch.add_wire(start=a, end=b)
        self.segments.append((a, b))

    def _cover(self, pin: PinGeom):
        for (ref, num), pg in self.pins.items():
            if ref == pin.part.ref and (pg.x, pg.y) == (pin.x, pin.y):
                self.covered.add((ref, num))

    def _resolve(self, p):
        if isinstance(p, PinGeom):
            self._cover(p)
            return p.out(), p.pt
        return (snap(p[0]), snap(p[1])), None

    def wire(self, *pts, style: str = "auto"):
        """Manhattan wire through pins/points. Pins get a stub first."""
        assert len(pts) >= 2
        resolved = [self._resolve(p) for p in pts]
        # stubs
        for (o, pinpt) in resolved:
            if pinpt is not None:
                self._seg(pinpt, o)
        chain = [o for (o, _) in resolved]
        for i in range(len(chain) - 1):
            a, b = chain[i], chain[i + 1]
            if a[0] == b[0] or a[1] == b[1]:
                self._seg(a, b)
                continue
            pa, pb = pts[i], pts[i + 1]
            s = style
            if s == "auto":
                ah = isinstance(pa, PinGeom) and pa.dx != 0
                bh = isinstance(pb, PinGeom) and pb.dx != 0
                av = isinstance(pa, PinGeom) and pa.dy != 0
                bv = isinstance(pb, PinGeom) and pb.dy != 0
                if ah and bh:
                    s = "zh"
                elif av and bv:
                    s = "zv"
                elif ah or bv:
                    s = "hv"
                else:
                    s = "vh"
            if s == "hv":
                self._seg(a, (b[0], a[1]))
                self._seg((b[0], a[1]), b)
            elif s == "vh":
                self._seg(a, (a[0], b[1]))
                self._seg((a[0], b[1]), b)
            elif s == "zh":
                mx = snap((a[0] + b[0]) / 2)
                self._seg(a, (mx, a[1]))
                self._seg((mx, a[1]), (mx, b[1]))
                self._seg((mx, b[1]), b)
            elif s == "zv":
                my = snap((a[1] + b[1]) / 2)
                self._seg(a, (a[0], my))
                self._seg((a[0], my), (b[0], my))
                self._seg((b[0], my), b)
            else:
                raise ValueError(style)

    def stub(self, pin: PinGeom, n: float = STUB):
        self._cover(pin)
        self._seg(pin.pt, pin.out(n))
        return pin.out(n)

    # ------------------------------------------------------------ labels / power
    def _label_rot(self, dx: int, dy: int) -> int:
        if dx < 0:
            return 180
        if dx > 0:
            return 0
        if dy < 0:
            return 90
        return 270

    def _stagger(self, pin: PinGeom, stub: float) -> float:
        """Use a longer stub when the neighbouring pin (2.54 mm away, same exit
        direction) already has a label at the short length, so texts do not overprint."""
        if not stub:
            return stub
        for k in (-1, 1):
            nb = (snap(pin.x + pin.dy * k * G), snap(pin.y + pin.dx * k * G))  # perpendicular neighbour
            nb_end = (snap(nb[0] + pin.dx * stub), snap(nb[1] + pin.dy * stub))
            if nb_end in self.label_ends:
                return stub * 2
        return stub

    def label(self, pin: PinGeom, text: str | None = None, glob: bool | None = None, stub: float = STUB):
        net = pin.net
        name = text or (net.name if net is not None else None)
        if name is None:
            raise ValueError(f"{pin.part.ref}.{pin.num} has no net")
        stub = self._stagger(pin, stub)
        end = self.stub(pin, stub) if stub else pin.pt
        self.label_ends.add(end)
        if not stub:
            self._cover(pin)
        if glob is None:
            glob = name in self.cross
        rot = self._label_rot(pin.dx, pin.dy)
        if glob:
            self.global_labels.append((name, end[0], end[1], rot, GLOBAL_SHAPE.get(pin.etype, "bidirectional")))
        else:
            self.sch.add_label(text=name, position=end, rotation=rot)

    def label_at(self, pt, name: str, rot: int = 0, glob: bool | None = None):
        pt = (snap(pt[0]), snap(pt[1]))
        if glob is None:
            glob = name in self.cross
        if glob:
            self.global_labels.append((name, pt[0], pt[1], rot, "bidirectional"))
        else:
            self.sch.add_label(text=name, position=pt, rotation=rot)

    def power(self, pin: PinGeom, name: str | None = None, stub: float = STUB):
        net = pin.net
        name = name or net.name
        stub = self._stagger(pin, stub)
        end = self.stub(pin, stub)
        self.label_ends.add(end)
        self.power_at(end, name, up=(name != "GND"), came_from=(pin.dx, pin.dy))

    def power_at(self, pt, name: str, up: bool = True, came_from=(0, 1)):
        """Put a power symbol at ``pt``.  A wire arriving sideways gets a symbol
        rotated to point away from the part (no jog: a jog lands on the
        neighbouring pin of any 2.54 mm pitch part)."""
        pt = (snap(pt[0]), snap(pt[1]))
        dx, dy = came_from
        rot = 0
        if dx < 0:
            rot = 90 if up else 270
        elif dx > 0:
            rot = 270 if up else 90
        elif (up and dy > 0) or (not up and dy < 0):
            rot = 180  # rail symbol hanging downwards / GND pointing up
        self.pwr_n += 1
        ref = f"#PWR{self.sid:02d}{self.pwr_n:03d}"
        self.sch.components.add(lib_id=POWER_SYMBOLS[name], reference=ref, value=name, position=pt, rotation=rot)
        self.geom[ref] = ("power", pt[0], pt[1], rot, POWER_SYMBOLS[name])
        self.extra_pts.add(pt)

    def flag(self, pt, came_from=(0, 1)):
        """PWR_FLAG on a wire end."""
        pt = (snap(pt[0]), snap(pt[1]))
        self.pwr_n += 1
        ref = f"#FLG{self.sid:02d}{self.pwr_n:03d}"
        self.sch.components.add(lib_id="power:PWR_FLAG", reference=ref, value="PWR_FLAG", position=pt, rotation=0)
        self.geom[ref] = ("flag", pt[0], pt[1], 0, "power:PWR_FLAG")
        self.extra_pts.add(pt)

    def nc(self, pin: PinGeom):
        self._cover(pin)
        self.sch.no_connects.add(position=pin.pt)

    def text(self, x, y, s: str, size: float = 1.5, bold: bool = False):
        self.sch.add_text(text=s, position=(snap(x), snap(y)), size=size, bold=bold)

    # ------------------------------------------------------------ finish
    def finish(self):
        for (ref, num), pg in self.pins.items():
            if (ref, num) in self.covered:
                continue
            net = pg.net
            if net is None:
                self.nc(pg)
            elif net.name in POWER_SYMBOLS:
                self.power(pg)
            else:
                self.label(pg)
        self._junctions()
        self.sch.set_title_block(title=self.title, rev=REV, date=DATE, company="ThumbsUp")
        self.sch.save(str(self.path))
        self._postprocess()

    def _junctions(self):
        pts: dict[tuple[float, float], int] = {}
        for a, b in self.segments:
            for p in (a, b):
                pts[p] = pts.get(p, 0) + 1
        pinpts = {(pg.x, pg.y) for pg in self.pins.values()} | self.extra_pts
        for p in self.extra_pts:
            pts.setdefault(p, 0)
        for p, n in pts.items():
            through = 0
            for a, b in self.segments:
                if p in (a, b):
                    continue
                if a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1]):
                    through += 2
                elif a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]):
                    through += 2
            deg = n + through + (1 if p in pinpts else 0)
            if deg >= 3:
                self.sch.junctions.add(position=p)

    def _postprocess(self):
        """Fix what kicad-sch-api gets wrong: global labels are not written,
        properties sit on the symbol origin and extra fields are visible,
        text/labels lack justification."""
        txt = self.path.read_text()
        txt = _rewrite_symbols(txt, self)
        txt = _fix_labels_and_text(txt)
        if self.global_labels:
            body = "".join(_global_label(*g) for g in self.global_labels)
            i = txt.rstrip().rfind(")")
            txt = txt[:i] + body + txt[i:]
        self.path.write_text(txt)


TWO_PIN = ("Device:R", "Device:C", "Device:L", "Device:LED", "Device:D_Schottky", "Device:D_Zener", "Device:C_Polarized", "Device:Thermistor_NTC", "Switch:SW_Push")


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _prop(name: str, value: str, x: float, y: float, rot: int = 0, justify: str | None = "left", hide: bool = False) -> str:
    eff = "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
    if justify:
        eff += f"\t\t\t\t(justify {justify})\n"
    if hide:
        eff += "\t\t\t\t(hide yes)\n"
    eff += "\t\t\t)\n"
    return f'\t\t(property "{name}" "{value}"\n\t\t\t(at {_fmt(x)} {_fmt(y)} {rot})\n' + eff + "\t\t)\n"


def _balanced(text: str, start: int) -> int:
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced")


def _rewrite_symbols(txt: str, sheet: "Sheet") -> str:
    out = []
    pos = 0
    key = "\n\t(symbol\n\t\t(lib_id \""
    while True:
        i = txt.find(key, pos)
        if i < 0:
            out.append(txt[pos:])
            break
        j = _balanced(txt, i + 1)
        out.append(txt[pos:i + 1])
        out.append(_rewrite_symbol_block(txt[i + 1:j], sheet))
        pos = j
    return "".join(out)


def _rewrite_symbol_block(block: str, sheet: "Sheet") -> str:
    m = re.search(r'\(property "Reference" "([^"]+)"', block)
    if not m:
        return block
    ref = m.group(1)
    if ref not in sheet.geom:
        return block
    kind, x, y, rot, lib_id = sheet.geom[ref]
    # collect existing properties (name, value) then strip them
    props = []
    pos = 0
    stripped = []
    while True:
        i = block.find("\t\t(property \"", pos)
        if i < 0:
            stripped.append(block[pos:])
            break
        j = _balanced(block, i)
        pm = re.match(r'\t\t\(property "((?:[^"\\]|\\.)*)" "((?:[^"\\]|\\.)*)"', block[i:j])
        props.append((pm.group(1), pm.group(2)))
        stripped.append(block[pos:i])
        pos = j
        if block[pos:pos + 1] == "\n":
            pos += 1
    body = "".join(stripped)
    values = dict(props)
    new = ""
    if kind == "power":
        up = "GND" not in lib_id
        new += _prop("Reference", ref, x, y, 0, None, hide=True)
        if rot in (0, 180):
            dy = -5.08 if up else 3.81
            if rot == 180:
                dy = -dy
            new += _prop("Value", values.get("Value", ""), x, y + dy, 0, None)
        else:
            points_left = (rot == 90) if up else (rot == 270)
            d = 5.08 if up else 3.81
            if points_left:
                new += _prop("Value", values.get("Value", ""), x - d, y, 0, "right")
            else:
                new += _prop("Value", values.get("Value", ""), x + d, y, 0, "left")
    elif kind == "flag":
        new += _prop("Reference", ref, x, y, 0, None, hide=True)
        new += _prop("Value", "PWR_FLAG", x, y - 6.35, 0, None)
    else:
        sym = sheet.cache.get_symbol(lib_id)
        bx0, by0, bx1, by1 = sym.bounding_box
        corners = [_rot(px, -py, rot) for px, py in ((bx0, by0), (bx1, by0), (bx0, by1), (bx1, by1))]
        left = x + min(c[0] for c in corners)
        right = x + max(c[0] for c in corners)
        top = y + min(c[1] for c in corners)
        pins = [pg for (r, _), pg in sheet.pins.items() if r == ref]
        vertical = len(pins) == 2 and pins[0].x == pins[1].x
        if lib_id in TWO_PIN and vertical:
            new += _prop("Reference", ref, x + 1.905, y - 1.27, 0, "left")
            new += _prop("Value", values.get("Value", ""), x + 1.905, y + 1.27, 0, "left")
        elif lib_id in TWO_PIN:
            new += _prop("Reference", ref, x, y - 2.54, 0, None)
            new += _prop("Value", values.get("Value", ""), x, y + 2.54, 0, None)
        elif lib_id.startswith("Transistor_FET"):
            new += _prop("Reference", ref, right + 0.635, y - 2.54 if rot == 0 else top - 1.27, 0, "left")
            new += _prop("Value", values.get("Value", ""), right + 0.635, y if rot == 0 else top + 1.27, 0, "left")
        else:
            new += _prop("Reference", ref, left, top - 3.81, 0, "left")
            new += _prop("Value", values.get("Value", ""), left, top - 1.27, 0, "left")
    dnp = False
    for name, val in props:
        if name in ("Reference", "Value"):
            continue
        if name == "DNP":
            dnp = True
            continue
        new += _prop(name, val, x, y, 0, None, hide=True)
    note = sheet.design.notes.get(ref) if kind == "part" else None
    if note:
        new += _prop("Note", note.replace('"', "'"), x, y, 0, None, hide=True)
    if dnp:
        body = body.replace("(dnp no)", "(dnp yes)", 1)
    # insert the new properties right after the (uuid ...) line
    k = body.find("\t\t(uuid ")
    k = body.find("\n", k) + 1
    return body[:k] + new + body[k:]


def _fix_labels_and_text(txt: str) -> str:
    def lab(m):
        rot = int(float(m.group(2)))
        j = "right bottom" if rot in (180, 270) else "left bottom"
        return m.group(1) + f"(justify {j})"
    txt = re.sub(r'(\(label "(?:[^"\\]|\\.)*"\n\t\t\(at [-\d.]+ [-\d.]+ ([\d.]+)\)\n\t\t\(effects\n\t\t\t\(font\n\t\t\t\t\(size [\d.]+ [\d.]+\)\n\t\t\t\)\n\t\t\t)\(justify [a-z ]+\)', lab, txt)
    txt = re.sub(r'(\(text "(?:[^"\\]|\\.)*"\n\t\t\(exclude_from_sim no\)\n\t\t\(at [-\d.]+ [-\d.]+ [\d.]+\)\n\t\t\(effects\n\t\t\t\(font\n(?:\t\t\t\t[^\n]*\n)*?\t\t\t\)\n)', lambda m: m.group(1) + "\t\t\t(justify left bottom)\n", txt)
    return txt


def _global_label(name: str, x: float, y: float, rot: int, shape: str) -> str:
    import uuid as _uuid

    j = "right" if rot in (180, 270) else "left"
    return (
        f'\t(global_label "{name}"\n\t\t(shape {shape})\n\t\t(at {_fmt(x)} {_fmt(y)} {rot})\n'
        f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {j})\n\t\t)\n"
        f'\t\t(uuid "{_uuid.uuid4()}")\n'
        f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n\t\t\t(at {_fmt(x)} {_fmt(y)} 0)\n'
        f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t)\n"
    )


class Root:
    """Root sheet: sheet symbols laid out in a grid plus a description block."""

    def __init__(self, title: str, path: Path, paper: str = "A3"):
        self.sch = ksa.create_schematic(title)
        self.sch.set_paper_size(paper)
        self.path = Path(path)
        self.title = title

    def sheet(self, name: str, filename: str, x: float, y: float, w: float = 38.1, h: float = 15.24):
        self.sch.add_sheet(name=name, filename=filename, position=(snap(x), snap(y)), size=(snap(w), snap(h)))

    def text(self, x, y, s: str, size: float = 1.5, bold: bool = False):
        self.sch.add_text(text=s, position=(snap(x), snap(y)), size=size, bold=bold)

    def finish(self):
        self.sch.set_title_block(title=self.title, rev=REV, date=DATE, company="ThumbsUp")
        self.sch.save(str(self.path))
        self.path.write_text(_fix_labels_and_text(self.path.read_text()))
