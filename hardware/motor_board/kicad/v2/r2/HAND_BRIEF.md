# Hand-routing brief (v2 motor board, 4 layers) — for agents working one cluster

Worktree: /home/smance/projects/thumbsup/.claude/worktrees/layout-v2 (branch layout-v2). Board: kicad/motor_board,
85 x 35 mm, JLC041611-1080 4-layer: L1 = F.Cu (top), L2 = In1.Cu solid GND (no tracks), L3 = In2.Cu (named
"L3.PWR_GND" in these boards), L4 = B.Cu (bottom).  Coordinates are board-local mm (KiCad x - 100, y - 70).

## Stage pipeline (kicad/gen)
- A stage is a python module kicad/gen/<name>.py that appends edits to v2_pre.EDITS:
  `tr(net, layer, pts, w=0.15)`, `via(net, (x,y), PV|POFV|RV, "note")`, `route(net, a, b, layers, margin=..)` (grid
  router; a/b = P("U9", 3) | ("via", x, y) | ("pt", x, y, layer)), `EDITS.append(dict(op="move", ref=, x=, y=, rot=,
  side="F"|"B"))`, rips: `dict(op="rip_segs", tracks=[(net, layer, a, b)], vias=[(net, c)])`, `dict(op="rip",
  box=(x0,y0,x1,y1), nets=[...], layers=[...], reroute=False)`.  Layers: F1 / L3 / L4 constants from v2_pre.
- Run a stage on a base stage:  `bash kicad/v2/r2/stage.sh <name> <base>`  (~8 s without router requests), then
  `python3 kicad/v2/r2/opens.py <name>` (counts) and `python3 kicad/v2/r2/errs.py <name> [net,net]` (DRC errors with
  positions + the opens of the listed nets).  The DRC uses the project's JLC rule file (motor_board.kicad_dru).
- Router flow on top of your stage (measure the whole board): create kicad/gen/h4<X>.py containing
  `import os; os.environ["H4_BASE"] = "<your stage>"; from h4 import *` and run
  `H4_ORDER=rails,analog,long,local timeout 1800 bash kicad/v2/r2/stage.sh h4<X> <your stage>` (~3 min).
- Geometry tools: `/usr/bin/python3 kicad/v2/r2/view.py dump <board> <out.json>` (board = kicad/gen/out/exp/<stage>/
  proj/motor_board.kicad_pcb); `python3 kicad/v2/r2/segs.py <dump> x0 y0 x1 y1 [F,L3,B] [net,..]` (copper listing);
  `python3 kicad/v2/r2/probe.py <dump> "via:NET:x,y" "F:NET:x,y;x,y" "L3:..." "B:..." "scan:NET:x0,y0,x1,y1:0.1"`
  (clearance check of proposed copper / map of legal via spots); `uv run --no-project --with matplotlib python
  kicad/v2/r2/view.py plot <dump> x0 y0 x1 y1 out.png F|L3|B <drc.json>` (picture; read it with the Read tool).
- Shell: the worktree guard rejects loops/heredocs/`$(..)` in Bash calls — write small scripts to files instead.
  Never `pkill -f` a pattern that matches your own command line.

## Current state
- Base for your work: stage **h3** (kicad/gen/h3.py on h1 on h0): hand-placed MCU escapes, the L3 weapon bus
  (INHB 26.95 / INHA 28.05 / INHC 28.45 / INLB_M 29.35 / INLA_M 29.65 east of x 48; under the MCU's east pins INHA 26.65,
  INHC 27.0, INLB_M 28.85, INLA_M 29.15), U6 behind U2 (61.75, 30.25, rot 270, B), the east-pin L1 lanes (NRST y 27.75,
  W_ARM_S y 28.5, W_EN y 29.0 from the MCU east pins to x 54-57), J1 escapes (SWCLK L3 y 31.0 x 44.6-51.9, SWDIO L4 under
  R18 and y 34.55 behind J1), the rear L1 lanes from the MCU rear pins (MB_RX 33.72, MB_TX 34.0, R_S2 34.28, R_S1 34.56,
  x 38-46), and a replay of the earlier router's copper for 24 untouched nets.  **h4** = router flow on h3: 33
  signal/rail opens, DRC 0.  Do not change h1/h3/h4; build your own stage on h3.
- Sensor pins (rev L4): L_S1 = U1.51, L_S2 = U1.56 (rear row), L_S3 = U1.30 (front row); R_S1 = U1.57, R_S2 = U1.58
  (rear), R_S3 = U1.24 (front).  MTEMP: R_MTEMP = U1.5 (east, y 28.0), L_MTEMP = U1.6 (east, y 27.5).

## Rules (must hold)
- DRC 0 errors with the project rule file (JLC limits).  Track 0.15 / clearance 0.127 min; vias 0.4/0.2 (PV) or
  0.45/0.25 (RV); via-in-pad allowed as POFV 0.40/0.20 (paid option already ordered) — list every POFV you add.
- Non-GND vias >= 0.9 mm apart centre-to-centre (L2 antipads must not merge); note any exception you need.
- Front power band: no L3/L4 signal tracks at y < 18.5 (x < 14 and 27-44.5) / y < 16.3 (x 14-27 and x >= 44.5).
- No L4 tracks within 0.5 mm of the U2/U3/U4 exposed pads; no L3 tracks within 1.5 mm of U3/U4's exposed pads.
- Analog nets (MTEMP, TEMPJ, W_SOx, W_Vx, W_NTC, VBAT_SNS) on L1/L3; on L3 keep L4 free right over them where you can;
  a short L4 hop onto a bottom-side pad is fine.
- Parts may be moved/rotated/flipped (never removed or changed).  Keep each part's function local where it matters
  (decoupling caps at their pins).  Test pads (TPx) can go anywhere reachable on top.
- Stay inside your cluster's region; if you must touch copper outside it, say exactly what and why.
- Long commands: always `timeout`; never leave a job running without knowing it finished.

## Deliverable
Your stage module (kicad/gen/<name>.py) applying cleanly on h3 with DRC 0, plus a short report: which opens you closed
(measured with your h4<X> run vs the 33 baseline), parts moved (ref, new x/y/rot/side), POFVs added, rule
deviations, what is still open in your cluster and why.  Do not commit; the coordinator merges and commits.
