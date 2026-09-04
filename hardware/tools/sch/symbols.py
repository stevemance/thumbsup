"""Custom KiCad symbols for parts that are not in the stock KiCad library.

Pin numbers are taken from the vendor datasheets in ``hardware/datasheets/pdf``:

* AT32F421K8U7 QFN-32 5x5: Artery DS_AT32F421 V2.0x, Figure 4 / pin table
  (QFN32 column). VSS is the exposed pad only (pin 33); pin 16 is PB2.
* FD6288Q QFN-24: Fortior FD6288 DS V1.6, Table 1-2.
* SK6812MINI-C: OPSCO datasheet pin table (1 DIN, 2 VDD, 3 DOUT, 4 GND); the
  matching land pattern is ``thumbsup.pretty/LED_SK6812MINI-C``.
* HYG015N04LS1C2 PDFN 5x6: Huayi DS p.1, leads 1-3 = S, 4 = G, tab = D.
* AP40P05 SOT-23: AllPower DS V1.1 p.1, G = 1, S = 2, D = 3 (= KiCad Q_PMOS_GSD).

Writes ``thumbsup.kicad_sym`` plus the project lib tables.  The library
version header must be one KiCad understands (20241209 = KiCad 9 format,
which KiCad 10 loads and upgrades).
"""

from __future__ import annotations

import re
from pathlib import Path

LIB_VERSION = "20241209"
GRID = 2.54

# (kind, name, number) ; None = gap row
AT32_LEFT = [
    ("power_in", "VDD", "1"),
    ("power_in", "VDD2", "17"),
    ("power_in", "VDDA", "5"),
    None,
    ("input", "NRST", "4"),
    ("input", "BOOT0", "31"),
    None,
    ("input", "PB4_DSHOT", "27"),
    ("bidirectional", "PA13_SWDIO", "23"),
    ("input", "PA14_SWCLK", "24"),
    ("bidirectional", "PB6_TLM_TX", "29"),
    None,
    ("input", "PA0_BEMFA", "6"),
    ("input", "PA4_BEMFB", "10"),
    ("input", "PA5_BEMFC", "11"),
    ("input", "PA1_VN", "7"),
    ("input", "PA3_I", "9"),
    ("input", "PA6_V", "12"),
    None,
    ("power_in", "EP_VSS", "33"),
]
AT32_RIGHT = [
    ("output", "PA10_AH", "20"),
    ("output", "PB1_AL", "15"),
    ("output", "PA9_BH", "19"),
    ("output", "PB0_BL", "14"),
    ("output", "PA8_CH", "18"),
    ("output", "PA7_CL", "13"),
    None,
    ("bidirectional", "PF0", "2"),
    ("bidirectional", "PF1", "3"),
    ("bidirectional", "PA2", "8"),
    ("bidirectional", "PA11", "21"),
    ("bidirectional", "PA12", "22"),
    ("bidirectional", "PA15", "25"),
    ("bidirectional", "PB2", "16"),
    ("bidirectional", "PB3", "26"),
    ("bidirectional", "PB5", "28"),
    ("bidirectional", "PB7", "30"),
    ("bidirectional", "PB8", "32"),
]

FD6288_LEFT = [
    ("input", "HIN1", "22"),
    ("input", "HIN2", "23"),
    ("input", "HIN3", "24"),
    None,
    ("input", "LIN1", "1"),
    ("input", "LIN2", "2"),
    ("input", "LIN3", "3"),
    None,
    ("power_in", "VCC", "4"),
    ("power_in", "COM", "6"),
    None,
    ("no_connect", "NC", "5"),
    ("no_connect", "NC", "7"),
    ("no_connect", "NC", "8"),
    ("no_connect", "NC", "21"),
    None,
    ("power_in", "EP", "25"),
]
FD6288_RIGHT = [
    ("passive", "VB1", "20"),
    ("output", "HO1", "19"),
    ("passive", "VS1", "18"),
    None,
    ("passive", "VB2", "17"),
    ("output", "HO2", "16"),
    ("passive", "VS2", "15"),
    None,
    ("passive", "VB3", "14"),
    ("output", "HO3", "13"),
    ("passive", "VS3", "12"),
    None,
    ("output", "LO1", "11"),
    ("output", "LO2", "10"),
    ("output", "LO3", "9"),
]


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _pin(kind: str, name: str, num: str, x: float, y: float, rot: int, length: float = 2.54) -> str:
    return (
        f"\t\t\t(pin {kind} line\n"
        f"\t\t\t\t(at {_f(x)} {_f(y)} {rot})\n"
        f"\t\t\t\t(length {_f(length)})\n"
        f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
        f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n'
        f"\t\t\t)"
    )


def _box_symbol(name: str, left: list, right: list, footprint: str, desc: str, half_w: float) -> str:
    rows = max(len(left), len(right))
    top = (rows - 1) / 2 * GRID
    top = round(top / GRID) * GRID + GRID  # keep on grid, one row of headroom
    pins = []
    for side, rot, x in ((left, 0, -(half_w + 2.54)), (right, 180, half_w + 2.54)):
        y = top
        for row in side:
            if row is not None:
                kind, pname, num = row
                pins.append(_pin(kind, pname, num, x, y, rot))
            y -= GRID
    body_top = top + GRID
    body_bot = top - rows * GRID
    return (
        f'\t(symbol "{name}"\n'
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
        f'\t\t(property "Reference" "U" (at {_f(-half_w)} {_f(body_top + 2.54)} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'\t\t(property "Value" "{name}" (at {_f(-half_w)} {_f(body_bot - 2.54)} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'\t\t(property "Footprint" "{footprint}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(property "ki_description" "{desc}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(symbol "{name}_0_1"\n'
        f"\t\t\t(rectangle (start {_f(-half_w)} {_f(body_top)}) (end {_f(half_w)} {_f(body_bot)})\n"
        "\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))\n"
        "\t\t)\n"
        f'\t\t(symbol "{name}_1_1"\n' + "\n".join(pins) + "\n\t\t)\n\t)"
    )


def _sk6812() -> str:
    name = "SK6812MINI-C"
    pins = [
        _pin("input", "DIN", "1", -7.62, 0, 0),
        _pin("power_in", "VDD", "2", 0, 7.62, 270),
        _pin("output", "DOUT", "3", 7.62, 0, 180),
        _pin("power_in", "GND", "4", 0, -7.62, 90),
    ]
    return (
        f'\t(symbol "{name}"\n'
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
        '\t\t(property "Reference" "D" (at -5.08 8.89 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'\t\t(property "Value" "{name}" (at -5.08 -8.89 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        '\t\t(property "Footprint" "thumbsup:LED_SK6812MINI-C" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t(property "ki_description" "Addressable RGB LED, 3.5x3.7 mm, 5 V" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(symbol "{name}_0_1"\n'
        "\t\t\t(rectangle (start -5.08 5.08) (end 5.08 -5.08)\n"
        "\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))\n"
        "\t\t)\n"
        f'\t\t(symbol "{name}_1_1"\n' + "\n".join(pins) + "\n\t\t)\n\t)"
    )


def _pico_symbol() -> str:
    """KiCad's RaspberryPi_Pico_W (a derived symbol) with GND/AGND typed as
    power inputs instead of power outputs — the stock symbol makes every
    ground on the board an ERC 'output to output' conflict."""
    import os

    libdir = os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
    text = (Path(libdir) / "MCU_Module.kicad_sym").read_text()
    i = text.index('(symbol "RaspberryPi_Pico"\n')
    depth, j = 0, i
    while True:
        c = text[j]
        if c == '"':
            j = text.index('"', j + 1)
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    block = text[i:j + 1].replace('"RaspberryPi_Pico"', '"PicoW"').replace('"RaspberryPi_Pico_', '"PicoW_')
    block = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "Pico W"', block, count=1)
    block = re.sub(r'\(property "Footprint" "[^"]*"', '(property "Footprint" "Module:RaspberryPi_Pico_W_SMD_HandSolder"', block, count=1)
    # retype the ground pins
    out, pos = [], 0
    while True:
        k = block.find("(pin ", pos)
        if k < 0:
            out.append(block[pos:])
            break
        depth, e = 0, k
        while True:
            c = block[e]
            if c == '"':
                e = block.index('"', e + 1)
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            e += 1
        pin = block[k:e + 1]
        if re.search(r'\(number "(3|8|13|18|23|28|33|38)"', pin):
            pin = re.sub(r"^\(pin \w+", "(pin power_in", pin)
        out.append(block[pos:k])
        out.append(pin)
        pos = e + 1
    return "\t" + "".join(out)


def _extract_symbol(lib_file: str, name: str) -> str:
    import os

    libdir = os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
    text = (Path(libdir) / lib_file).read_text()
    i = text.index(f'(symbol "{name}"\n')
    depth, j = 0, i
    while True:
        c = text[j]
        if c == '"':
            j = text.index('"', j + 1)
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[i:j + 1]


def _strip_pins(block: str) -> str:
    out, pos = [], 0
    while True:
        k = block.find("(pin ", pos)
        if k < 0:
            out.append(block[pos:])
            break
        depth, e = 0, k
        while True:
            c = block[e]
            if c == '"':
                e = block.index('"', e + 1)
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            e += 1
        out.append(block[pos:k])
        pos = e + 1
    return "".join(out)


def _hyg_fet() -> str:
    """HYG015N04LS1C2 in PDFN 5x6 (PQFN-8-EP footprint): leads 1-3 = S, 4 = G,
    tab 5 = D (Huayi DS p.1 'S S S G / D D D D').  Graphics borrowed from
    KiCad's Q_NMOS_GSD; the three source pins are stacked on the S position."""
    name = "HYG015N04LS1C2"
    block = _extract_symbol("Transistor_FET.kicad_sym", "Q_NMOS_GSD")
    block = block.replace('"Q_NMOS_GSD"', f'"{name}"').replace('"Q_NMOS_GSD_', f'"{name}_')
    block = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{name}"', block, count=1)
    block = re.sub(r'\(property "Footprint" "[^"]*"', '(property "Footprint" "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic"', block, count=1)
    block = _strip_pins(block)
    pins = [
        _pin("input", "G", "4", -5.08, 0, 0),
        _pin("passive", "S", "1", 2.54, -5.08, 90),
        _pin("passive", "S", "2", 2.54, -5.08, 90),
        _pin("passive", "S", "3", 2.54, -5.08, 90),
        _pin("passive", "D", "5", 2.54, 5.08, 270),
    ]
    # put the pins into the *_1_1 unit
    k = block.index(f'(symbol "{name}_1_1"')
    k = block.index("\n", k) + 1
    return "\t" + block[:k] + "\n".join(pins) + "\n" + block[k:]


def library_text() -> str:
    syms = [
        _hyg_fet(),
        _pico_symbol(),
        _box_symbol(
            "AT32F421K8U7",
            AT32_LEFT,
            AT32_RIGHT,
            "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.3x3.3mm",
            "Artery AT32F421 Cortex-M4 120 MHz, QFN-32 5x5 (EP 3.25 mm), AM32 AT32DEV_F421 pinout",
            15.24,
        ),
        _box_symbol(
            "FD6288Q",
            FD6288_LEFT,
            FD6288_RIGHT,
            "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm",
            "Fortior FD6288Q 3-phase 250 V gate driver, QFN-24 4x4 (EP size: verify vs DS drawing)",
            12.7,
        ),
        _sk6812(),
    ]
    return f"(kicad_symbol_lib\n\t(version {LIB_VERSION})\n\t(generator \"thumbsup_symbols\")\n" + "\n".join(syms) + "\n)\n"


def write_library(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    lib = out_dir / "thumbsup.kicad_sym"
    lib.write_text(library_text())
    (out_dir / "sym-lib-table").write_text(
        "(sym_lib_table\n  (version 7)\n"
        '  (lib (name "thumbsup")(type "KiCad")(uri "${KIPRJMOD}/thumbsup.kicad_sym")(options "")(descr "ThumbsUp custom symbols"))\n)\n'
    )
    (out_dir / "fp-lib-table").write_text(
        "(fp_lib_table\n  (version 7)\n"
        '  (lib (name "thumbsup")(type "KiCad")(uri "${KIPRJMOD}/thumbsup.pretty")(options "")(descr "ThumbsUp custom footprints"))\n)\n'
    )
    write_footprints(out_dir / "thumbsup.pretty")
    return lib


if __name__ == "__main__":
    print(write_library(Path(__file__).resolve().parents[2] / "kicad"))


# ---------------------------------------------------------------- footprints
def _fp(name: str, descr: str, body: str, attr: str = "smd") -> str:
    return (
        f'(footprint "{name}"\n\t(version 20241229)\n\t(generator "thumbsup_symbols")\n\t(layer "F.Cu")\n'
        f'\t(descr "{descr}")\n\t(attr {attr})\n'
        f'\t(property "Reference" "REF**" (at 0 -4 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
        f'\t(property "Value" "{name}" (at 0 4 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n'
        + body + "\n)\n"
    )


def _smd_pad(num: str, x: float, y: float, w: float, h: float) -> str:
    return f'\t(pad "{num}" smd rect (at {x} {y}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask"))'


def _tht_pad(num: str, x: float, y: float, d: float, drill: float, shape: str = "circle") -> str:
    return f'\t(pad "{num}" thru_hole {shape} (at {x} {y}) (size {d} {d}) (drill {drill}) (layers "*.Cu" "*.Mask"))'


def _line(x1, y1, x2, y2, layer="F.SilkS", w=0.12) -> str:
    return f'\t(fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) (layer "{layer}"))'


def _rect(x1, y1, x2, y2, layer, w=0.1) -> str:
    return f'\t(fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) (fill no) (layer "{layer}"))'


def fp_sk6812mini_c() -> str:
    """OPSCO SK6812MINI-C land pattern (DS §6): pad sizes and the 0.6 mm x-gap
    from the drawing.  Pin 1 (DIN) is bottom-right, the cut corner of the
    package.  Body 3.5 x 3.7 mm."""
    # x-gap 0.6, y-gap 0.5.  Left column pads: DOUT 1.5 wide (top), GND 2.4 wide (bottom).
    # Right column: VDD 2.2 wide (top), DIN 1.3 wide (bottom).
    pads = [
        _smd_pad("3", -(0.3 + 0.75), -(0.25 + 0.65), 1.5, 1.3),   # DOUT top-left
        _smd_pad("2", (0.3 + 1.1), -(0.25 + 0.6), 2.2, 1.2),      # VDD top-right
        _smd_pad("4", -(0.3 + 1.2), (0.25 + 0.4), 2.4, 0.8),      # GND bottom-left
        _smd_pad("1", (0.3 + 0.65), (0.25 + 0.45), 1.3, 0.9),     # DIN bottom-right
    ]
    body = "\n".join(pads + [
        _rect(-1.75, -1.85, 1.75, 1.85, "F.Fab"),
        _line(1.75, 1.35, 1.25, 1.85, "F.Fab"),  # cut corner at DIN
        _line(-2.0, -2.1, 2.0, -2.1), _line(-2.0, 2.1, 1.3, 2.1), _line(2.0, 2.1, 2.0, 1.4),
        _rect(-2.25, -2.35, 2.25, 2.35, "F.CrtYd", 0.05),
        '\t(fp_text user "1" (at 2.7 1.1 0) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))',
    ])
    return _fp("LED_SK6812MINI-C", "OPSCO SK6812MINI-C 3.5x3.7mm, pads per DS section 6, pin 1 DIN at cut corner", body)


def fp_shunt_2512_kelvin() -> str:
    """2512 metal-element shunt with wide pads plus a 0.5 mm sense stub on the
    inner edge of each pad for the Kelvin net-ties.  Pads sized for 2 mm wide
    terminations (TA-I RLP25 recommendation for R <= 4 mOhm: a 4.0, b 3.1, gap 1.3)."""
    pads = [
        _smd_pad("1", -2.2, 0, 3.1, 4.0),
        _smd_pad("2", 2.2, 0, 3.1, 4.0),
    ]
    body = "\n".join(pads + [
        _rect(-3.2, -1.6, 3.2, 1.6, "F.Fab"),
        _line(-3.9, -2.2, 3.9, -2.2), _line(-3.9, 2.2, 3.9, 2.2),
        _rect(-4.1, -2.4, 4.1, 2.4, "F.CrtYd", 0.05),
        '\t(fp_text user "KELVIN: sense traces leave the inner pad edges" (at 0 3.2 0) (layer "F.Fab") (effects (font (size 0.5 0.5) (thickness 0.08))))',
    ])
    return _fp("R_2512_Shunt_Kelvin", "2512 metal shunt, 3.1x4.0 pads 1.3 mm apart; route Kelvin sense from the inner pad edges", body)


def fp_motor_pads() -> str:
    """Three motor-phase solder terminals: 2.0 mm plated holes with 4.5 mm
    annular pads on 5.0 mm pitch plus 4x3 mm SMD lands on the top side so a
    16-18 AWG lead can be laid flat and soldered (20-30 A)."""
    pads = []
    for i, x in enumerate((-5.0, 0.0, 5.0)):
        pads.append(_tht_pad(str(i + 1), x, 0, 4.5, 2.0, "circle" if i else "roundrect"))
        pads.append(_smd_pad(str(i + 1), x, -4.0, 4.0, 3.0))
    body = "\n".join(pads + [
        _line(-8.0, -6.0, 8.0, -6.0), _line(-8.0, 2.8, 8.0, 2.8),
        _rect(-8.2, -6.2, 8.2, 3.0, "F.CrtYd", 0.05),
        '\t(fp_text user "A  B  C" (at 0 4.0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
    ])
    return _fp("MotorPads_1x03_P5.00mm", "Motor phase pads: 2.0 mm holes / 4.5 mm pads at 5 mm pitch + 4x3 mm top lands, 30 A", body, "through_hole")


def write_footprints(pretty: Path) -> None:
    pretty.mkdir(parents=True, exist_ok=True)
    for text in (fp_sk6812mini_c(), fp_shunt_2512_kelvin(), fp_motor_pads()):
        name = re.match(r'\(footprint "([^"]+)"', text).group(1)
        (pretty / f"{name}.kicad_mod").write_text(text)
