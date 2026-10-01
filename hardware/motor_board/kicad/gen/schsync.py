"""Sync a stage board to the (regenerated) schematic, tail_apply op "sync":
    dict(op="sync", place={"C117": (x, y, rot, "F"|"B")})
gen_sch.py gives every symbol a fresh UUID, so after a schematic regeneration every footprint's path (the board <->
schematic link the DRC parity check uses) is re-pointed by reference; value, fields (LCSC, MPN, Datasheet,
Description) and sheet name/file follow the schematic.  A part in the schematic but not on the board is loaded from its
library footprint, netted from the netlist and put at place[ref] (board-local mm).  A footprint on the board with no
symbol is reported (parts are never removed here).  Source: `kicad-cli sch export netlist` of the root sheet."""
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
sys.path.insert(0, str(HERE.parent / "lib_build"))
import kicadlib as K  # noqa: E402

SKIP_FIELDS = {"Reference", "Value", "Footprint", "Sheetname", "Sheetfile", "ki_keywords", "ki_fp_filters"}


def _netlist():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "n.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out),
                        str(PROJ / "motor_board.kicad_sch")], check=True, capture_output=True)
        tree = K.parse(out.read_text())
    comps = {}
    for c in K.children(K.child(tree, "components"), "comp"):
        ref = K.child(c, "ref")[1]
        fields = {}
        fl = K.child(c, "fields")
        if fl:
            for f in K.children(fl, "field"):
                name = K.child(f, "name")[1]
                fields[name] = f[2] if len(f) > 2 and isinstance(f[2], str) else ""
        sp = K.child(c, "sheetpath")
        comps[ref] = dict(value=K.child(c, "value")[1], footprint=K.child(c, "footprint")[1], fields=fields,
                          sheet_tstamps=K.child(sp, "tstamps")[1], tstamp=K.child(c, "tstamps")[1],
                          sheetname=K.child(sp, "names")[1].strip("/").split("/")[-1], pins={})
        for p in K.children(c, "property"):
            if K.child(p, "name")[1] == "Sheetfile":
                comps[ref]["sheetfile"] = K.child(p, "value")[1]
    for n in K.children(K.child(tree, "nets"), "net"):
        name = K.child(n, "name")[1]
        for nd in K.children(n, "node"):
            r, pin = K.child(nd, "ref")[1], K.child(nd, "pin")[1]
            if r in comps:
                comps[r]["pins"][pin] = name
    return comps


def _load_fp(fpid):
    lib, name = fpid.split(":", 1)
    for d in (PROJ, Path("/usr/share/kicad/footprints")):
        p = d / f"{lib}.pretty"
        if (p / f"{name}.kicad_mod").exists():
            return pcbnew.FootprintLoad(str(p), name)
    raise FileNotFoundError(fpid)


def apply(b, e, OX, OY, log=print):
    comps = _netlist()
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    nets = {str(k): v for k, v in b.GetNetsByName().items()}
    relinked = added = changed = 0
    for ref, c in sorted(comps.items()):
        f = fps.get(ref)
        if f is None:
            if ref not in e.get("place", {}):
                log(f"sync: {ref} is in the schematic but not on the board and has no place[] entry"); continue
            f = _load_fp(c["footprint"])
            f.SetFPID(pcbnew.LIB_ID(*c["footprint"].split(":", 1)))
            f.SetReference(ref)
            b.Add(f)
            x, y, rot, side = e["place"][ref]
            if side == "B":
                f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            f.SetPosition(pcbnew.VECTOR2I_MM(OX + x, OY + y))
            f.SetOrientationDegrees(rot)
            for pad in f.Pads():
                n = c["pins"].get(pad.GetNumber())
                if n:
                    if n not in nets:
                        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
                    pad.SetNet(nets[n])
            for fl in f.GetFields():
                if fl.GetName() != "Reference":
                    fl.SetVisible(False)
            added += 1
            log(f"sync: added {ref} {c['value']} at ({x}, {y}) r{rot} {side}")
        if f.GetValue() != c["value"]:
            log(f"sync: {ref} value {f.GetValue()} -> {c['value']}"); f.SetValue(c["value"]); changed += 1
        for k, v in c["fields"].items():
            if k in SKIP_FIELDS or (f.HasField(k) and f.GetFieldText(k) == v):
                continue
            log(f"sync: {ref} field {k} -> {v[:40]}")
            f.SetField(k, v)
            fl = f.GetField(k)
            if fl:
                fl.SetVisible(False)
        f.SetPath(pcbnew.KIID_PATH(c["sheet_tstamps"] + c["tstamp"]))
        f.SetSheetname(c["sheetname"]); f.SetSheetfile(c.get("sheetfile", c["sheetname"] + ".kicad_sch"))
        relinked += 1
    extra = sorted(set(fps) - set(comps))
    if extra:
        log(f"sync: on the board but not in the schematic (left alone): {extra}")
    log(f"sync: {relinked} relinked, {added} added, {changed} values changed")
