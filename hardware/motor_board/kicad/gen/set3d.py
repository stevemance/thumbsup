"""Set 3D model references on a board's footprints (by footprint name): /usr/bin/python3 set3d.py <in.kicad_pcb> [out]
Stock footprints whose stock model is not shipped with KiCad 10 use project models (kicad/motor_board/3dmodels, built by
gen3d.py / lib_build/model_rgf0040e.py); project footprints use the models their library now carries."""
import sys

import pcbnew

P = "${KIPRJMOD}/3dmodels/"
K = "${KICAD10_3DMODEL_DIR}/"
MODELS = {
    "SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm": P + "SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm.step",
    "SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm": P + "SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm.step",
    "QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm": P + "QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm.step",
    "Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm": P + "Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm.step",
    "SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB": K + "Connector_JST.3dshapes/JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal.step",
    "DHWQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm": P + "DHWQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm.step",
    "BOOMELE_1.27-2x10P_SMD": K + "Connector_PinHeader_1.27mm.3dshapes/PinHeader_2x10_P1.27mm_Vertical_SMD.step",
    "R_2512_HoLR_1-4mR": K + "Resistor_SMD.3dshapes/R_2512_6332Metric.step",
    "R_2512_JIERR_RE_small_electrode": K + "Resistor_SMD.3dshapes/R_2512_6332Metric.step",
    "TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm": P + "TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm.step",
}
src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else src
b = pcbnew.LoadBoard(src)
n = 0
for f in b.GetFootprints():
    name = str(f.GetFPID().GetLibItemName())
    if name not in MODELS:
        continue
    ms = f.Models()
    ms.clear()
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = MODELS[name]
    ms.push_back(m)
    n += 1
pcbnew.SaveBoard(dst, b)
print(f"set 3D models on {n} footprints")
