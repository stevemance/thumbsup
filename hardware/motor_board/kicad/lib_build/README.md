# Motor-board parts library (build + verification)

`out/motor_board.kicad_sym` and `out/motor_board.pretty/` are the project library for the KiCad
project in `../motor_board/` (install by copying them there; the project already registers both as
project libraries through `${KIPRJMOD}`).

```
python3 build_lib.py      # writes out/ from parts.py
python3 check_lib.py      # must print "0 errors"
python3 test_check_lib.py # after changing check_lib/build_lib: every planted error must be caught
```

## What is in it

- **28 symbols**, one per purchased part, with Footprint, LCSC, MPN and Datasheet filled in:
  - 5 drawn from the datasheet pin tables: DRV8316CRRGFR, DRV8323RHRGZR, BQ76907RGRR,
    LM74502DDFR, TPS22945DCKR;
  - 23 copied from KiCad 10 stock symbols (pin numbers and types kept; some pins renamed to the
    datasheet names).
- Plain resistors and capacitors (and the NTC TH1) are **not** in it: use stock `Device:R`,
  `Device:C`, `Device:Thermistor_NTC`, with the value, footprint and `LCSC` field from
  `design/bom.csv`.
- **5 custom footprints**:
  - `TI_RGF0040E…` (DRV8316C, TI SLVSH07 p.92–94);
  - `R_2512_HoLR_1-4mR` (RS1–RS3, HoLR p.3);
  - `R_2512_JIERR_RE_small_electrode` (RS4, JIERR p.5);
  - `BOOMELE_1.27-2x10P_SMD` (J1, vendor drawing);
  - `SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB` (J2/J3, vendor drawing).

  Every other footprint is KiCad stock.
- **3D models:** the custom footprints have none (stock ones do).

## How it was verified

- **Adversarial review:** three rounds with independent reviewers, results in `review/`.
  - Symbols were checked against datasheet pin tables, including gate units and diode/MOSFET/
    capacitor polarity.
  - Footprints were measured from the manufacturer drawings (rendered at 300–400 dpi).
  - The tooling was audited by planting errors.
  - Round 1 caught a real blocker: the RGF0040E pads were 0.3 mm inboard and shorted to the
    exposed pad.
  - Round 2 moved RS4 to JIERR's recommended land.
- **`check_lib.py`** checks the library against `design/netlist.csv`, `design/bom.csv`,
  `../../BOM.md` and the footprints:
  - pins by number and name, pads, fields, LCSC codes from two sources, part numbers;
  - gate units, hidden power pins, pad layers and paste, copper gaps, courtyard;
  - the manufacturer-drawing dimensions (`parts.DRAWING`), JLC's own footprints (`ref/easyeda/`,
    including the mounting tabs);
  - fab flags, and an ERC preview.
- **`test_check_lib.py`** plants 29 realistic errors and requires every one to fail the check.

## Notes for schematic capture and ordering

- **PWR_FLAG:** ERC will want a PWR_FLAG on the nets fed from off-board or through a series
  part: VBAT, BAT_IN, GND, +5V, +3V3A, BMS_BAT, L_VM/R_VM, L_VSRC/R_VSRC. `check_lib.py` lists them.
- **SN74LVC3G17 (U9/U10):** unit B is gate **3** and unit C is gate **2**. Place the units by pin
  name, not by unit letter.
- **LED D3 (KT-0603R):** the vendor calls the anode pin 1, KiCad's pad 1 is the cathode (the net
  mapping is right). Check the cathode mark in JLC's placement preview.
- **JLC placement rotations:** Q1–Q8 and U3/U4 are drawn turned relative to JLC's footprints, so
  expect rotation corrections (jlcpcb-tools handles them).
- **J1 (BOOMELE 2×10):** the part has no pin-1 feature. The compute board's socket footprint must
  be the exact mirror of this numbering: odd pins in one column, pin 1 at the top of the x < 0
  column.
- **J2/J3:** pin 1 follows JST SM06B, because the XUNPU drawing does not mark it. Confirm against a
  mating SHR-06V-S cable.
- **RS4 (LCSC C46961745):** the part number and photos say small electrode, but LCSC lists
  ±50 ppm/°C, which JIERR gives for the large electrode. Either version solders on this land.
