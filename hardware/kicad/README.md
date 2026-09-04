# ThumbsUp v1 KiCad project

Open `thumbsup.kicad_sch` in KiCad 10.  **Every `.kicad_sch` here is generated — edit
`../tools/sch/circuit.py` (connectivity) or `../tools/sch/layouts.py` (placement) and
rebuild.**

```bash
python3 -m venv hardware/tools/.venv
hardware/tools/.venv/bin/pip install -r hardware/tools/requirements.txt
hardware/tools/.venv/bin/python hardware/tools/sch/build.py --render
```

The build:

1. writes `thumbsup.kicad_sym` (AT32F421K8U7, FD6288Q with EP, HYG015N04LS1C2 with the PDFN pin
   numbering, SK6812MINI-C, a Pico W symbol whose ground pins are typed correctly) and
   `thumbsup.pretty` (SK6812MINI-C land pattern, Kelvin 2512 shunt, 30 A motor pads),
2. builds the SKiDL circuit, runs SKiDL ERC and writes `thumbsup.net`,
3. draws every sheet with explicit placement,
4. runs `kicad-cli sch erc` (summary printed, full report in `erc.json`),
5. exports `thumbsup_kicad.net` and checks that its (ref, pin) partition is identical to
   SKiDL's — the build fails if the drawing does not match the circuit,
6. with `--render`, writes one PNG per sheet into `preview/`.

| Sheet | File | Contents |
|---|---|---|
| Root | `thumbsup.kicad_sch` | sheet index |
| Pack | `thumbsup_pack.kicad_sch` | XT30, TVS, 1 mΩ shunt, reverse-polarity P-FET |
| Rails | `thumbsup_rails.kicad_sch` | AP63205 5 V, D3 to VSYS, 2× AP2112, monitors, power LED |
| Pico | `thumbsup_pico.kicad_sch` | Pico W, I2C pull-ups, ARM link, reset, NTC, expansion |
| Sense | `thumbsup_sense.kicad_sch` | INA226 ×4 with filters, LSM6DS3TR-C, ADXL375 |
| IO | `thumbsup_io.kicad_sch` | W25Q128, 74AHCT1G125, SK6812 ×2 |
| ESC L/R/W | `thumbsup_esc_{l,r,w}.kicad_sch` | AT32 + FD6288Q + sense networks (+ weapon enable on W) |
| Bridges | `thumbsup_esc_{l,r,w}_bridge.kicad_sch` | 3 half-bridges, bootstrap, shunt, bulk, motor pads |

Conventions: rails are power symbols, cross-sheet signals are global labels
(`L_HO1`, `MOTOR_W_A`, `I_L+`, `I_L_S+` …), sheet-local nets are plain labels.  Decoupling
capacitors are drawn in a strip per sheet with the IC they belong to in the title.  Kelvin
sense nets (`*_S+/-`) join the power nets only through `NT*` net-ties that must sit on the
shunt pads.  Parts with `(dnp yes)` (R201/R301/R401) are footprints only.  Every part carries
a hidden `Note` property with its placement intent.

`thumbsup.kicad_pcb` is an empty board — layout has not started.
