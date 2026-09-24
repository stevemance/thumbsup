"""Minimal KiCad s-expression helpers for the motor-board parts library.

Only what build_lib.py and check_lib.py need: parse a .kicad_sym / .kicad_mod into nested lists,
pull symbols, pins and pads out of them, and write text back.
"""
import re
from pathlib import Path

STOCK_SYM = Path("/usr/share/kicad/symbols")
STOCK_FP = Path("/usr/share/kicad/footprints")

_TOKEN = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')


def parse(text):
    """Parse an s-expression into nested lists; strings keep their quotes stripped, atoms stay str."""
    stack, cur = [], []
    pos = 0
    while True:
        m = _TOKEN.match(text, pos)
        if not m:
            break
        tok = m.group(1)
        pos = m.end()
        if tok == "(":
            stack.append(cur)
            cur = []
        elif tok == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif tok.startswith('"'):
            cur.append(Str(tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            cur.append(tok)
    return cur[0] if len(cur) == 1 else cur


class Str(str):
    """A quoted string atom (so it is written back with quotes)."""


def dump(node, indent=0):
    if isinstance(node, list):
        if not node:
            return "()"
        head = dump(node[0])
        simple = all(not isinstance(x, list) for x in node)
        if simple:
            return "(" + " ".join(dump(x) for x in node) + ")"
        inner = [dump(x, indent + 1) for x in node[1:]]
        pad = "\t" * (indent + 1)
        return "(" + head + "".join("\n" + pad + s if s.startswith("(") else " " + s for s in inner) + "\n" + "\t" * indent + ")"
    if isinstance(node, Str):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(node)


def children(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def child(node, key):
    c = children(node, key)
    return c[0] if c else None


def load_symbol_lib(path):
    return parse(Path(path).read_text())


def symbols(lib):
    """Top-level symbols of a library: name -> node."""
    return {s[1]: s for s in children(lib, "symbol")}


def resolve(lib, name):
    """A symbol with 'extends' merged into its parent (KiCad derived symbols)."""
    syms = symbols(lib)
    s = syms[name]
    ext = child(s, "extends")
    if not ext:
        return s
    parent = resolve(lib, ext[1])
    return parent, s


def sym_pins(sym):
    """All pins of a symbol (any unit/body style): list of dict(number, name, type, unit)."""
    out = []

    def walk(node, unit):
        for c in node:
            if not isinstance(c, list) or not c:
                continue
            if c[0] == "symbol" and isinstance(c[1], str) and re.search(r"_(\d+)_(\d+)$", c[1]):
                u = int(re.search(r"_(\d+)_(\d+)$", c[1]).group(1))
                walk(c, u)
            elif c[0] == "pin":
                name = child(c, "name")[1]
                number = child(c, "number")[1]
                out.append(dict(number=str(number), name=str(name), type=c[1], unit=unit,
                                hidden="hide" in [x for x in c if isinstance(x, str)] or bool(child(c, "hide"))))

    walk(sym, 0)
    return out


def sym_props(sym):
    return {p[1]: p[2] for p in children(sym, "property")}


def load_footprint(path):
    return parse(Path(path).read_text())


def fp_pads(fp):
    """Pads of a footprint: list of dict(number, type, shape, at=(x,y,rot), size=(w,h), layers)."""
    out = []
    for p in children(fp, "pad"):
        at = child(p, "at")
        size = child(p, "size")
        out.append(dict(number=str(p[1]), type=p[2], shape=p[3],
                        at=tuple(float(v) for v in at[1:]) if at else None,
                        size=tuple(float(v) for v in size[1:3]) if size else None,
                        layers=[str(x) for x in (child(p, "layers") or [None])[1:]]))
    return out


def stock_footprint_path(libname, fpname):
    return STOCK_FP / f"{libname}.pretty" / f"{fpname}.kicad_mod"
