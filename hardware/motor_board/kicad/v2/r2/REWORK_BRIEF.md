# Power-first rework brief (2026-10-01, owner-approved) — for one area agent

Read r2/HAND_BRIEF.md first (stage pipeline, tools, shell rules); this brief overrides its "Current state" section.

## Why
The adversarial review found the signal routing walls off the power copper: with a full-board single-net pour
(`/usr/bin/python3 kicad/v2/r2/pourtest.py hR` from hardware/motor_board) 12 power nets fall apart into islands. The
owner approved a power-first rework: make every power net connectable, moving parts and ripping / re-routing the signals
that wall it off. Same parts, same netlist (no pin swaps, no part removal, no package changes).

## Base and deliverable
- Base stage: **hR** (chain h0..hY -> hF -> hR; hS = silk, always last). Build your stage `kicad/gen/<name>.py` on hR:
  `bash kicad/v2/r2/stage.sh <name> hR`. Do not edit any other stage or shared tool except to add your own files.
- Use `move`, `tr`, `via` (PV / RV / POFV), `route(...)`, `rip` / `rip_segs` (with `v2_pre.n_("NET")` full net names,
  layers F1 / L3 / L4), exactly as the existing stages do (see hF.py, hY.py, hZ.py for idioms).
- Re-route what you rip: by hand (`tr`/`via`) or with `route(...)` requests in your stage; if many nets need it, a
  router-flow stage on top of yours like h4M (`import os; os.environ["H4_BASE"]="<name>"; from h4 import *`,
  `H4_ORDER=rails,analog,long,local timeout 1800 bash kicad/v2/r2/stage.sh h4<X> <name>`).
- Deliverable: your stage module(s) applying cleanly on hR with **DRC 0 errors, parity 0, 0 signal/rail opens**
  (`python3 kicad/v2/r2/opens.py <stage>`), and **pourtest PASS for every net in your area**
  (`/usr/bin/python3 kicad/v2/r2/pourtest.py <stage> NET NET ...`), without making any other net's pourtest worse (run the
  full `pourtest.py <stage>` at the end and compare with hR's). Also run the silk stage on top to make sure nothing you
  moved breaks silk/DRC: `bash kicad/v2/r2/stage.sh hS_<name> <your final stage>` with a copy of hS.py named hS_<name>.py.
- Do not commit; the coordinator merges. Report: parts moved (ref, x, y, rot, side), POFVs added, nets ripped and how
  re-routed, pourtest before/after, any rule deviation, anything you could not fix and why.

## Rules (must hold)
- JLC rules = the project DRC (motor_board.kicad_dru / .kicad_pro). Track >= 0.15 / clearance 0.127 (logic); power-class
  clearance 0.15+; vias 0.4/0.2 (PV), 0.45/0.25 (RV), POFV 0.4/0.2 via-in-pad allowed (list each one).
- Non-GND vias >= 0.9 mm apart (L2 antipads must not merge); note any exception.
- Front power band: no L3/L4 signal tracks at y < 18.5 (x 27-44.5 and x < 14) / y < 16.3 (x 14-27 and x >= 44.5); the L3
  band at y < 16 is reserved for the VBAT pour.
- No L4 tracks within EP + 0.5 mm of U2/U3/U4; no L3 tracks within EP + 1.5 mm of U3/U4.
- Analog nets (MTEMP, TEMPJ, W_SOx, W_Vx, W_NTC, VBAT_SNS, INA_INx, CELLx) on L1/L3, away from phase / SW nodes.
- Hot parts on top. Parts may move/rotate/flip; never removed or changed. Courtyards must not overlap (DRC checks).
- Power copper: leave room for the pour: phase / VM / VBAT paths at least ~1.5-2 mm wide on L1 where current flows
  (calcs.md: drive phases 1-2 A rms, 8 A peak; weapon / pack much more). If you draw explicit power tracks instead of
  relying on the later pour, use >= 0.5 mm (drive VM / phases) and more where it fits.
- DESIGN.md section 6 (layout rules) is the contract; read the items for your area.
- Shell: write scripts to files (the guard rejects loops / heredocs with cd / $(..)); never `pkill -f`; always `timeout`.
  Scratch: /home/smance/.claude/jobs/35ed3eaa/tmp/<your stage name>/.
