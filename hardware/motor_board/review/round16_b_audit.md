# Round 16 — B audit (consistency, rev L after round 15)

Auditor B.  Package copied to `/tmp/r16b/`; `design/motor_board.py` → `237 refs (205 placed
components), 160 nets, 67 BOM lines` / `checks: OK`; `design/calcs.py` rerun.  The regenerated
`netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md` and `calcs.md` are byte-identical to the tree.

## Cross-file checks (clean)

* bom.csv: 67 lines, Σ Qty = 199; the 6 DNP (C110–C112, C114–C116) are in the netlist and not the CSV;
  205 placed = 199 + 6.  DESIGN §1, BOM.md and README agree (199 / 67 / 6 DNP).
* Every designator named in DESIGN, BOM.md, README, calcs.md, spice/README, datasheets/README exists in
  the netlist (MH1–MH4 are pinless parts in motor_board.py, so only absent from nets.md: expected).
* BOM.md "Parts to watch": every LCSC number matches bom.csv.  datasheets/README covers every
  non-generic BOM line.
* MCU pins/AFs: DESIGN §3.2–§3.4, the ADC table, §7.21 comparator inputs and §8 match mcu_pinmap.md
  (e.g. PB11 COMP6_INP/ADC12_IN14, PA4 ADC2_IN17, PB13 ADC3_IN5, PB7 TIM8_BKIN, PD2 W_ARM_S).
  16 analog inputs = 9 injected + 7 regular.
* Spot-checked IC pinouts against the PDFs: DRV8316C (all 41 pads vs Table 6-1), INA239 (1 CS, 2 MOSI,
  3 ALERT, 4 MISO, 5 SCLK …).  Test-pad list, J1 pin table, TP numbering in §9 match the netlist.
* SPI frames: every DRV8316 word in §8 has correct even parity (0x0603, 0x0606, 0x1019, 0x0A4E, 0x0D10,
  0x0F00, 0x1818, 0x087C, 0x097D) and so does 0x0C90 — **except the one below**.
* §5 / §3.2 / §1 ARM and hot-plug numbers match `spice/arm.out` and `spice/hotplug.out`.

## Findings

### B16-01 — MAJOR — per-drive coast exit word has the wrong parity (0x0C10 → must be 0x0D10)

DESIGN.md:683–684: "leave with CTRL4 **0x0C10**".  Frame = R/W(15) | addr(14:9) | P(8) | data(7:0),
even parity over all 16 bits (SLVSH07 SPI format: "Parity bit, P (bit B8) … is set such that the SDI input data word has
even number of 1s").  CTRL4 = 6h → 0x0C00 (2 ones); data 0x10 (1 one) → 3 ones → P must be 1 → **0x0D10**,
which is exactly the value the boot sequence already uses (DESIGN.md:611 "CTRL4 0x0D10").  0x0C10 has
odd parity: the DRV8316 flags SPI_PARITY (STAT2 bit 2) and ignores the write, so the chip stays in
"Hi-Z FETs" and the drive never comes back (the register check then sees 0x90 where it expects 0x10 →
drive row 2 loop → latch).  Fails safe, but it is the wrong word, and round 15 recorded this block as
"verified parity" (CHANGES.md:300).  Fix: "leave with CTRL1 0x0603 → CTRL4 **0x0D10** → CTRL1 0x0606".

### B16-02 — MINOR — the "rewrite" after a per-drive coast un-coasts the chip before PWM_MODE is restored

§8.1 drive row 2 (DESIGN.md:676): "Per-drive coast, fault recovery, rewrite, restart".  The only
rewrite sequence defined (DESIGN.md:611) writes CTRL4 0x0D10 (DRV_OFF bit 0) **before** CTRL2 0x087C
(3x PWM), and it assumes the shared DRV_OFF pin is high, which is not true for a per-drive event (the other
drive is running).  After an NPOR (the chip reset into 6x mode) this rewrite takes the chip out of Hi-Z in
6x mode and then changes PWM_MODE while the FETs operate — the very thing the per-drive coast paragraph
forbids (DESIGN.md:684–685, "TI: do not change PWM_MODE while the FETs operate").  State that a
per-drive rewrite writes CTRL4 as 0x0C90 (keeps the chip coasted), and the CTRL4 0x0D10 exit is the last
write, at restart.

### B16-03 — MINOR — a latched drive is un-coasted by the boot sequence after an MCU reset

The latch word keeps left/right latches across NRST/IWDG/BOR resets (DESIGN.md:635–638), and row 2
says a latched drive "stays coasted" (DESIGN.md:676).  But the boot order (DESIGN.md:595–596) runs the
§8 DRV8316 sequence unconditionally, which writes CTRL4 0x0D10 (DESIGN.md:611) to both chips, then
releases DRV_OFF for the healthy drive.  The latched drive is then active: at 0 % duty in 3x mode (INL
= +3V3) its low sides are on — braking, not coasted — and the register check expects 0x10 for it.  Add
to the boot order: a drive latched in the latch word gets CTRL4 0x0C90 (expected 0x90) before DRV_OFF
goes low.

### B16-04 — MINOR — locked-rotor trips: §9 expects row 6 (no latch), §8.1 row 5 latches

§8.1 row 5 (DESIGN.md:655): "~3 consecutive restarts have each ended in a comparator trip before
reaching the commanded speed → latch the weapon".  §9 step 6 (DESIGN.md:759–760): "repeated locked-rotor
trips → row 6 cool-down, no latch".  A locked drum with the limit raised past the comparator threshold
(the §9 step 4 set-up, DESIGN.md:737–738) never reaches commanded speed, so as the classifier is written it
matches row 5 and latches after ~3 restarts.  Either the §9 expectation is stale (should be "latches via
row 5: expected, clear it") or row 5 needs a discriminator.  Worth deciding explicitly: the same row
latches the weapon for the rest of a match on a drum jammed by an opponent if it desyncs into
comparator trips three times.

### B16-05 — MINOR — §8 fast-trip row points at the wrong §8.1 row

DESIGN.md:614: "nuisance trips would keep restarting the weapon (**§8.1 row 2**)".  Row 2 is the
supply/bus event; comparator trip → restart is **row 6** (DESIGN.md:656).  Dangling reference left from
the round-15 renumbering.

### B16-06 — MINOR — §7.21 still states the round-14 latch rule

DESIGN.md:582: "a comparator re-trip within ~200 µs of re-enable (a persistent short), latches the weapon
off".  After round 15 a single fast re-trip does *not* latch: row 4 needs it for the **second
consecutive** restart, measured from the first applied vector (DESIGN.md:654, "one fast re-trip alone can
be a badly synchronised restart"), and row 5 adds the standstill case.  Reword §7.21 to "two consecutive
fast re-trips, or ~3 restarts that trip before reaching speed (§8.1 rows 4–5)".

### B16-07 — MINOR — TH1 over-temperature has no row of its own; the §8 cross-reference lands on an nFAULT row

§8 weapon-safety row (DESIGN.md:617): "TH1 > ~100 °C → coast until < ~80 °C (row 9)".  Row 9's
evidence is "W_nFAULT stays low > ~10 ms" (DESIGN.md:659); TH1 only discriminates the cause there.  A
polled TH1 > 100 °C with W_nFAULT high (the normal case: TH1 is the FET NTC, U2's OTSD is a die limit)
matches no row, while the table does list other polled events (row 10 stall, row 11 strap test) and ends
in row 12 "Anything else → Unknown → latch".  Give the polled TH1 limit its own non-latching row (or say
in row 12 that it covers break events only), and point §8 at it.

### B16-08 — MINOR — rev labels stale after round 15

DESIGN.md:9 "rev L rounds 11–14"; README.md:7 "after fourteen adversarial review rounds".  CHANGES.md's
last section is "Round 15 … → rev L (text only)".  Should read rounds 11–15 / fifteen (same class as
B14-06).

## Notes

* N1 — DESIGN.md:611 lists the read-back set as "CTRL2/CTRL3/CTRL4/CTRL5/CTRL6/CTRL10" but then gives an
  expected value for CTRL1 (0x06, locked).  Add CTRL1 to the list (a lost lock is worth seeing).
* N2 — Row 0 (DESIGN.md:650) is a polled condition ("current ≈ 0 while the drum is driven"), not something
  evaluable ~0.5 ms after a break, when the bridge is already off; it works only because the BOVL restart
  (row 1) drives the drum again.  It holds until an operator clear, so its "driven" test should require a
  meaningful commanded current (a false positive costs the weapon for the match).
* N3 — If the CTRL4 DRV_OFF bit pulls nFAULT low (the bench-verify item, DESIGN.md:686), the coast itself
  raises an L_/R_nFAULT event (and a TIM8 break on the left) that matches no drive row (the drive table
  has no fall-through row).  Say what that event classifies as once the bench result is known.

## Counts

BLOCKER 0 · MAJOR 1 · MINOR 7 · NOTE 3.
