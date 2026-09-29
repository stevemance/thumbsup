"""Write a pinsolve result into design/motor_board.py's MCU_PINS (U1 pin -> net and the alternate function it relies
on).  python3 apply_pins.py out/pinsolve_180.json   (then run design/motor_board.py: it re-checks every AF)."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]
sol = json.load(open(sys.argv[1]))["pins"]
ns = {"n": "http://dummy.com"}
root = ET.parse(MB / "ref" / "STM32G474RxTx_pins.xml").getroot()
PIN = {p.get("Position"): (p.get("Name"), p.get("Type"), {s.get("Name") for s in p.findall("n:Signal", ns)})
       for p in root.findall("n:Pin", ns)}
POWER = {"1": ("VBAT", "+3V3"), "15": ("VSS", "GND"), "16": ("VDD", "+3V3"), "27": ("VSSA", "GND"),
         "28": ("VREF+", "+3V3A"), "29": ("VDDA", "+3V3A"), "31": ("VSS", "GND"), "32": ("VDD", "+3V3"),
         "47": ("VSS", "GND"), "48": ("VDD", "+3V3"), "63": ("VSS", "GND"), "64": ("VDD", "+3V3")}


def af_for(net, pin, tag):
    sigs = PIN[pin][2]
    pick = lambda rx: sorted(s for s in sigs if re.fullmatch(rx, s))[0]
    if net == "SWDIO":
        return "SYS_JTMS-SWDIO"
    if net == "SWCLK":
        return "SYS_JTCK-SWCLK"
    if tag in ("fixed", "gpio"):
        return ""
    if tag == "bk":
        return "TIM1_BKIN" if "TIM1_BKIN" in sigs else "TIM1_BKIN2"
    m = re.fullmatch(r"bk(\d+)", tag)
    if m:
        return f"TIM{m.group(1)}_BKIN" if f"TIM{m.group(1)}_BKIN" in sigs else f"TIM{m.group(1)}_BKIN2"
    m = re.fullmatch(r"k(\d)", tag)
    if m:
        return f"TIM1_CH{m.group(1)}N" if "_INL" in net else f"TIM1_CH{m.group(1)}"
    m = re.fullmatch(r"t(\d+)k(\d)", tag)
    if m:
        return f"TIM{m.group(1)}_CH{m.group(2)}"
    m = re.fullmatch(r"(both|a1|a2)c(\d)", tag)
    if m:
        return f"COMP{m.group(2)}_INP"
    if tag == "op5":
        return "OPAMP5_VINP"
    m = re.fullmatch(r"adc(\d)|a(\d)", tag)
    if m:
        return pick(fr"ADC{m.group(1) or m.group(2)}_IN\d+")
    m = re.fullmatch(r"s(\d)", tag)
    if m:
        return f"SPI{m.group(1)}_" + net.split("_")[1]
    if re.fullmatch(r"U?S?ART\d|LPUART\d|UART\d|USART\d", tag):
        return f"{tag}_" + ("TX" if net.endswith("TX") else "RX")
    raise SystemExit(f"unknown tag {tag} for {net}")


rows = {}
by_pin = {d["pin"]: (n, d["tag"]) for n, d in sol.items()}
for pin in map(str, range(1, 65)):
    name = PIN[pin][0].split("-OSC")[0]
    if pin in POWER:
        rows[pin] = (POWER[pin][0], POWER[pin][1], "")
    elif pin in by_pin:
        n, tag = by_pin[pin]
        rows[pin] = (name, n, af_for(n, pin, tag))
    else:
        rows[pin] = (name, "NC", "")
lines = ["MCU_PINS = {", "    # pin: (name, net, required alternate function or '' for GPIO/analog-only)",
         "    # co-assigned with the v2 placement (kicad/v2/pinsolve.py, 2026-09-29); U1 at (43.5, 26.25), rotated 180"]
items = [f'"{p}": ("{a}", "{b}", "{c}")' for p, (a, b, c) in rows.items()]
for i in range(0, 64, 3):
    lines.append("    " + ", ".join(items[i:i + 3]) + ",")
lines.append("}")
new = "\n".join(lines) + "\n"
mb = (MB / "design" / "motor_board.py").read_text()
a = mb.index("MCU_PINS = {")
b = mb.index("\n}\n", a) + 3
(MB / "design" / "motor_board.py").write_text(mb[:a] + new + mb[b:])
for p, r in rows.items():
    print(p, r)
