"""hQ: final-review fixes on hX (silk hS follows):
- RS4.2 (VBAT, the pack shunt's load side): 3 vias in its pad straight into the L3 VBAT band, so the 22 A pack current no
  longer leaves the shunt only through a 1.7 mm L1 neck (review pours-1); filled + capped (POFV list in FAB.md).
- DNP parts (C110-C112, C114-C116): no paste on their pads, so the stencil prints no solder on the empty lands (jlc-assembly-3).
- Tombstoning (critic-1): small two-terminal parts (0402 / 0603 R, C, LED) whose GND pad sits in a GND pour while the other
  pad is on a trace get a thermal-relief GND pad (2 x 0.25 mm spokes, 0.25 mm gap) so both pads heat alike at reflow.
  Decoupling / bypass caps (other pad on a supply rail) stay solid: their loop inductance matters more."""
import pcbnew

import v2_pre
from v2_pre import EDITS, via, POFV, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
F = pcbnew.FromMM

for y in (2.2, 3.2, 4.2):
    via("VBAT", (36.45, y), RV, "RS4.2 (VBAT) -> L3 band, via in pad")

RAILS = {"+3V3", "+3V3A", "+5V", "VBAT", "BMS_BAT", "BMS_REG", "L_VM", "R_VM", "L_AVDD", "R_AVDD", "U2_DVDD", "U2_VCP",
         "L_VCP", "R_VCP", "PSW_CAP", "BUCK_CB", "L_CPH", "L_CPL", "R_CPH", "R_CPL", "U2_CPH", "U2_CPL", "VBAT_SW", "BAT_IN"}
SMALL = ("_0402_", "_0603_")
# GND pads whose fill reaches them only through a gap too narrow for 2 spokes (DRC starved_thermal / unconnected), and R49
# (its solid L4 pad is the only bridge between two L4 GND fill pieces): solid
SOLID = {"R49", "C82", "C41", "C43", "C44", "C45", "C49", "C81", "C91", "C92", "R14", "R23", "R25", "R32", "R40", "R45"}


def fix(b, ctx):
    n_dnp = n_th = 0
    for f in b.GetFootprints():
        if f.IsDNP():
            for p in f.Pads():
                ls = p.GetLayerSet()
                ls.RemoveLayer(pcbnew.F_Paste); ls.RemoveLayer(pcbnew.B_Paste)
                p.SetLayerSet(ls)
            n_dnp += 1
            continue
        fp = str(f.GetFPID().GetLibItemName())
        ref = f.GetReference()
        if not any(s in fp for s in SMALL) or ref.rstrip("0123456789") not in ("R", "C", "D"):
            continue
        pads = list(f.Pads())
        if len(pads) != 2:
            continue
        nets = [p.GetNetname().split("/")[-1] for p in pads]
        if nets.count("GND") != 1:
            continue
        other = [n for n in nets if n != "GND"][0]
        if (ref.startswith("C") and other in RAILS) or ref in SOLID:
            continue                                   # bypass cap: keep the GND pad solid
        g = pads[nets.index("GND")]
        g.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        g.SetLocalThermalSpokeWidthOverride(F(0.25))
        g.SetThermalGap(F(0.25))
        n_th += 1
    print(f"hQ: paste removed on {n_dnp} DNP parts; thermal-relief GND pad on {n_th} small parts")


EDITS.append(dict(op="py", fn=fix))
