"""Print the project's current design rules / net classes and the board's stackup section."""
import json
import re
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "motor_board"
p = json.loads((P / "motor_board.kicad_pro").read_text())
ds = p["board"]["design_settings"]
print("rules", json.dumps(ds["rules"]))
print("track_widths", ds["track_widths"], "vias", ds["via_dimensions"])
print("net_settings keys", list(p["net_settings"]))
print("classes", [c["name"] for c in p["net_settings"]["classes"]])
print("default", json.dumps(p["net_settings"]["classes"][0]))
print("patterns", p["net_settings"].get("netclass_patterns"))
pcb = (P / "motor_board.kicad_pcb").read_text()
m = re.search(r"\n\t\t\(stackup.*?\n\t\t\)\n", pcb, re.S)
print(m.group(0)[:2500] if m else "no stackup")
print("zones", pcb.count("\n\t(zone"))
