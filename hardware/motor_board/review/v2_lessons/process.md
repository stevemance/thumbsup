# v2 lessons: process and tooling

Scope: how the first motor-board layout (worktree-routing, 2026-09-25 to 09-29) was done, which methods paid off, what
wasted time, and the workflow v2 should follow.  Design-specific lessons (which parts go where) are in the sibling memos.

Sources: `ROUTING_PLAN.md`, `kicad/gen/*`, `tail_log/` (47 accepted rounds), `git log` on worktree-routing, session
transcript 35ed3eaa (user messages and status reports), memory notes `hardware-routing-state` / `hardware-pcb-pipeline`.

## Timeline in numbers

| When (local) | Method | Open connections |
|---|---|---|
| 09-25 07:30-10:30 | Placement v2, 75 x 35 mm, adversarially reviewed for spacing and per-part rationale; **no routability metric** | - |
| 09-25 12:29 | Freerouting on everything (without telling the user) | 458 -> pass 1: 241 unrouted, 479 violations; stopped |
| 09-25 13:44-18:49 | route_blocks (hand geometry + grid A*), block by block, 4 layers | 329 -> 220; U2 region found fully enclosed |
| 09-25 19:11 | 4 -> 6 layers (user choice) | |
| 09-25 22:00-09-26 09:25 | Full rebuilds (`route_all.py`, 10-12 min, once 41 min), rip-up post-pass | 189 -> 89 |
| 09-26 09:25-09-27 10:42 | **Plateau** at 89-90: full rebuilds, Freerouting on the tail (>1000 violations on KiCad-clean copper), escape finders | 89 -> 90 |
| 09-27 11:43 | Freeze-and-edit tail loop (user asked "is there a way to move faster?") | 89 -> 60 in ~3.5 h |
| 09-27 15:55 | Board grown 75 -> 85 mm (grow.py) | 60 -> 59 |
| 09-27 16:00-20:25 | Tail rounds 17-24, L5 jumpers allowed | 59 -> 38 |
| 09-27 21:32 | MCU pin swaps (rev L1) | 38 -> 35 |
| 09-28 overnight | genvip / genfence / genmove / genl5 sweeps, rounds 26-47 | 35 -> 13 |
| 09-29 | density map, MCU block move (26 open), front end into band (48 open): both rejected | 13, restart ordered |

Roughly 30 h of routing effort; the last 13 opens never closed.  The user's own verdict question ("how many layers
would professionals use?") was answered with measurements: 311 signal connections, ~3.0 m minimum Manhattan length,
~1-2 signal layers' worth of demand, **688 vias (2.2 per signal connection)**, effectively only ~2.5 usable signal
layers.  The board was a 4-layer board lost to placement, pin assignment and routing method, not to density.

## Lessons

### 1. The router was sequential with no global negotiation, so order and early copper decided the outcome
**Evidence.** `router.py`: 0.05 mm grid A*, "one connection at a time ... the result becomes an obstacle for the next
request".  Rip-up was bolted on later and only over `soft` (router-made local) routes; hand blocks were protected.  A
trial pass on 09-25 routed 66 of 134 pairs and "every long U1-hub net failed" because local hookups had already sealed
the U1 field.  Region rip-up with 12 random re-route orders gave 24-27 open vs 14; re-laying U1's west fan-out
automatically went 38 -> 45 ("the hand-planned escapes are denser than the grid router reproduces").  Pads rasterised as
bounding boxes made the router conservative right where density mattered (0.5 mm-pitch QFN/LQFP).
**v2.** Route signals with a negotiated-congestion (PathFinder-style) router: every net routed every iteration, shared
cells allowed but penalised with history + present-congestion costs, iterate until no overuse.  Route all signal nets
in one global pass after power/critical copper is fixed; never grow the board by accreting nets one at a time.  Model
pads by true shape (at least rounded rect) before trusting the router near fine-pitch parts.

### 2. Incremental patching (the tail loop) was a good loop for the wrong phase
**Evidence.** Full rebuilds cost 10-12 min (8 min routing ~800 routes, 3 min fill + DRC); the plateau at 89-90 lasted
~25 h largely because each idea cost a rebuild.  The freeze-and-edit loop (`tail.py`, ~30 s per iteration, ops
move/rip/rip_ref/track/via/vip/route/drop/shift/copy_nets/swap_pin, every accepted round in `tail_log/NN_*.py`,
DRC 0 + parity 0 at every commit) closed 89 -> 13.  But from round 1 the board was no longer reproducible from
`route_all.py`; every fix was bolted onto copper laid under older, worse assumptions, and each fix consumed routing
resources for later ones (L4 3V3 fill split into islands by each L4 signal; ~63 GND pads needing own drop vias; L5
filling with long jumpers).
**v2.** Keep a fast edit loop, but use it for *placement* iteration and for final polish only.  The routing itself
should stay a function of (placement, pin map, rules): re-run globally (it must be fast enough: target < 2 min) after
any placement change.  Freeze only after a global pass reaches 0 open, then polish by hand.

### 3. Placement was reviewed for spacing and rationale, not for routability
**Evidence.** The user asked for an adversarially reviewed placement "rationalising every part" at <= 75 x 35 mm.
`PLACEMENT.md` / `placement_spec.py` mention "crossing" only for a few local fan-outs; no ratsnest, crossing count, or
cut-line congestion was measured.  Result: the left Hall front end stacked on top of U1 (its vias competing with U1's
fan-out field: "every via spot is in U1's fan-out field"), U10 on the L3 bus turn, J3 pin order reversed vs U10's
inputs, U6 in the far NW making W_INLx a 27-45 mm loop, C410 20 mm from U4 "since placement", R62 35 mm from D3.  Nine
of the last 17 opens trace directly to these placement choices.
**v2.** Placement is not done until it passes routability metrics: total HPWL / Manhattan ratsnest length, ratsnest
crossing count, per-cut-line demand vs capacity (tracks that fit across a line on the available signal layers), and a
"no part stacked on an IC's escape field" rule (keep the opposite side under a fine-pitch IC free for its via field).
Review placement against those numbers, not just spacing.

### 4. MCU pin assignment was fixed before placement and co-optimised only at the end
**Evidence.** Rev L pins were chosen in the design package.  Pin swaps (rev L1, 09-27) came only after ~20 h of
routing, recovered 3 opens directly, and were constrained by copper already laid ("PC6 has no via reach at all", the
W-group rotation was "net zero" because the new pins were already boxed in).  The rev L2 swap set was AF-checked but
never applied.
**v2.** Treat MCU pin mapping (within AF constraints from the ST pin database) and connector pin order as placement
variables.  Do a pin-assignment pass right after coarse placement: assign each peripheral function to the package side
facing its load, minimising crossings; re-check with the AF checker; push to schematic + DESIGN.md contract + CHANGES.md
immediately (see memory "firmware implications into docs").

### 5. Hand-laid buses reserved corridors early and later boxed everything in
**Evidence.** `route_blocks.py` (972 lines) hand-placed the 11-12 lane L3 east bus (y 27.8-31.3) and U1's fan-out
early.  They became the dominant blocker: "U1's field is sealed on L3", "U2's region is enclosed: the bus south, its
north group west, U4's columns east", U10 "under the bus's east-end columns", J2's pin row exactly on the bus band, the
grown band a corridor where "every pad that needs a via is blocked".  Hand escapes could not be re-derived by the
router, so they were effectively frozen.
**v2.** No hand-committed long buses before a global feasibility route exists.  Plan channels as *soft* reservations
(costs, not walls) in the congestion router; hand-draw only short, electrically critical geometry (gate/Kelvin loops,
buck loop, decoupling) and let long logic nets negotiate.  Any hand geometry that crosses a cut line must be justified
against that line's capacity.

### 6. Growing the board created a dead band instead of relief
**Evidence.** `grow.py` cut along a stepped line and shifted the east part +10 mm (46 tracks bridged, 8 re-routed):
60 -> 59 open.  The cut went through the weapon bridge (10 x 19 mm of dead space between cells C and B) and the new
band filled with stretched tracks and bus lanes, so no via fitted there.  The user noticed ("those extra 10mm are
just dead space in the middle") and later ruled "Growing before only resulted in low density space, so let's not do
that until we fully utilize the space."  The later MCU block move (blockmove.py) had the same failure: +13 opens,
because the strip it opened filled with bridges and the stacked front end moved with U1.
**v2.** Area changes and block moves happen at placement time, followed by a global re-route, never as geometric
surgery on routed copper.  Before any area change, show a density/congestion map and predict where the new area lands
relative to the congested cut lines.

### 7. Freerouting was tried three times and never earned its cost
**Evidence.** v1 board (Sept): "never converged and burned days".  09-25: started on all 458 items without flagging the
switch; the user interrupted ("Wait, what are you doing?"), pass 1 gave 241 unrouted / 479 violations at ~5 min per pass.
09-26 tail run with all 5,090 existing items locked: >1000 violations reported against KiCad-clean copper (its DSN rule
model differs from KiCad's), over half the tail unrouted per 20-min pass.  Known gotchas: fanout pass must be disabled,
an empty inner layer with a large area becomes a "power plane", concave outlines mis-computed.
**v2.** Do not use Freerouting as the primary router.  If used at all, only on a DSN whose rule export has been
validated round-trip on a small already-clean board (0 violations on import), with a pass budget and a stop criterion
agreed up front.  Never switch methods without telling the user.

### 8. Blind experiment sweeps had very low yield
**Evidence.** A 132-experiment batch (lift one blocker, re-route) came back empty except one unusable hit (R_VM at
0.127 mm); an earlier run of it was killed for low memory.  genl5/genmove/genfence/genvip sweeps yielded ~2-5 %; late
pace was "one fix per 30-60 minutes of experiments".
**v2.** Before sweeping, compute *why* a net fails (the cut line it cannot cross and that cut's demand vs capacity).  If
the cut is over capacity, no local experiment can succeed: change placement/pins/layers instead.  Budget sweeps:
if a batch yields < 10 %, stop sweeping and escalate.

### 9. Missing milestones let the tail absorb days; stop points were decided late
**Evidence.** The 09-25 estimate was "8-10 more hours" to completion; it took ~4 days and did not finish.  The plateau
(89-90 for ~25 h) and the 17 -> 13 end game (~1 day) had no pre-agreed exit.  The assistant asked for 8 layers
repeatedly; the user finally said "Do not ask for 8 layers again. Think critically about the board itself".  The
honest answer (4 layers is normal for this board) came only when asked.
**v2.** Milestones with numbers, checked against the plan: (a) placement metrics pass; (b) global route reaches <= 5 %
open with no overuse on critical cut lines; (c) 0 open.  If a milestone is missed by the time budget (e.g. 2x the
estimate) or open count is flat for 3 iterations, stop, diagnose at the placement level, and bring the user a
measured recommendation, not a list of layer upgrades.

### 10. Via usage was unbudgeted
**Evidence.** 688 vias, 2.2 per signal connection, 0.4/0.2 signal vias through all six layers; via-in-pad on boxed-in
pads; ~63 GND drop vias added late; viaspot.py repeatedly found "no legal 0.3 mm via within 1.5 mm".  On a through-via
board each via blocks every layer.
**v2.** Track a via budget per region (target <= 1 per signal connection overall) and via-site capacity under each IC
before routing.  Plan GND/rail drop vias with placement (each decap gets its via site reserved), not as a close-out.
Consider 0.3/0.15 vias in the logic area if the fab allows, decided at setup.

### 11. Fill and plane side effects were discovered one island at a time
**Evidence.** B/F tracks stranded GND fill islands (islands.py, fillonly.py, netcc.py written to find them); signals on
L4 split the "+3V3 fill" ("each one cost +3V3 islands"); L5 accumulated long jumpers until a "caution" note; DRC's
zone-to-zone items have no position.
**v2.** On 4 layers: L2 solid GND, no signal fills on inner layers; rails as routed trunks or dedicated pours decided at
setup.  Run an island/plane-integrity check (unanchored fills, plane slot lengths under signals) in the fast loop, not
only at DRC.

### 12. KiCad / pcbnew and environment gotchas (keep in the tooling README)
- `SaveBoard` re-nets a lone new via that overlaps a fill to the fill's net (GND).  Give each via its track in the same
  step, or add a tiny own-net anchor stub (tail_apply via/vip).
- After moving/shifting zones, `board.Zones()` returned bare SWIG objects; use index-based zone access.
- `gen_sch.py` re-rolls every symbol uuid, breaking footprint links: edit `.kicad_sch` in place for pin swaps, or make
  the generator uuid-stable (derive uuids from ref + pin).
- `route_all.py` diagnostic (per-failure re-route against an empty board) silently took a build from 10 to 41 min: make
  expensive diagnostics opt-in and print build time.
- Worktree guard: 56 "too complex to verify" and 10 "program computed at runtime" refusals in the transcript.  Use
  checked-in scripts with plain invocations (`python3 tool.py args`), absolute paths, no variables-as-programs or
  complex pipelines.
- Memory pressure: the machine had ~2.6 GB free of 15 GB with swap full (09-25); background batches were killed.
  Run at most 2 parallel pcbnew jobs, stream results to disk, make batches resumable.
- pcbnew scripts: `/usr/bin/python3 -X faulthandler -u` (silent segfaults); close KiCad first.
- plot.py at first did not draw In4 ("L5 looked empty in plots but it is not"): render every copper layer.

### 13. What worked and should be kept
- DRC 0 and netlist parity 0 as an invariant at every commit; one commit per accepted round with the open count in the
  message.  This made every regression and every rejected experiment cheap to reason about.
- Ops-based edit lists (`tail_edits.py`) and the round log: reproducible, reviewable, revertable.
- Experiment isolation (`TAIL_EXP`: own work dir per trial).
- Diagnostic tools: density.py (per-layer occupancy + ratsnest), viaspot.py with single-blocker search, netcc.py,
  islands.py, spot.py.  They turned "stuck" into specific causes; they came too late (density.py on the last day).
- Researching implications before acting (Hall pull-up VT- margin, thermal-via lanes, C410 hot-plug slew) and writing
  deviations into ROUTING_PLAN / FAB.md / DESIGN.md.  The user explicitly asked for this and it prevented bad fixes.
- Honest "tried and rejected, with numbers" entries; keep that discipline.

### 14. What the user values (from their messages)
- Wants the assistant to do the work autonomously ("keep going ... until you asymptote", "use your judgement") but
  to be told when the method changes ("Wait, what are you doing?") and to get a short status on request.
- Prefers a hand-routing / professional workflow over autorouter script development ("bias more towards more of a
  hand-routing approach vs autorouting script dev").  v2's better router must be pitched as tooling for that
  professional flow, kept small, with early results shown.
- Speed ("seems crazy to build everything every time"); research before deviations; no wasted area; no repeated
  asks for the same escalation; critical thinking grounded in measurements.
- Constraints for v2: board dimensions and the board-to-board header fixed; 4 layers; any part may move; no part
  removed without asking.

## Proposed v2 workflow

**0. Setup (half a day max).**  4-layer stack-up (F signals+power / L2 solid GND / L3 signals + rail trunks / B
signals+parts), rules and via sizes fixed, net classes.  Tooling: one uuid-stable schematic/pin-map path; pcbnew
scripts runnable with plain commands; render tool that shows all layers + ratsnest.

**1. Floorplan by function (not by part).**  Fix the power stage, connectors, header and mounting from the constraints.
Assign regions: each IC gets its escape field (both sides under fine-pitch parts reserved), each sensor front end sits
by its connector, weapon logic by U2, SPI peripherals on the MCU side that faces them.

**2. Pin assignment co-optimised with the floorplan.**  MCU AF-legal remap + connector pin order to minimise ratsnest
crossings.  Update design/pin map/DESIGN contract/CHANGES immediately; firmware notes stay facts only.

**3. Placement with metrics.**  Report per iteration: HPWL, ratsnest crossings, per-cut-line demand/capacity on the
signal layers, via-site capacity per IC, parts stacked on escape fields (must be 0), decap-to-pin distances.
Adversarial review uses these numbers plus the electrical rules (loops, Kelvin, analog separation).
Gate: every cut line <= ~70 % of capacity before routing starts.

**4. Critical copper by hand, short only.**  Power pours, gate/Kelvin loops, buck loop, decoupling with reserved via
sites, GND drops.  Nothing longer than a few mm that crosses a cut line.

**5. Global negotiated-congestion route of all signals** (fast: < 2 min; pads by true shape; layer/via costs; soft
channel preferences).  Output: open count, overuse map, via count.  If overuse persists on a cut line after N
iterations, go back to 1-3 (move parts / swap pins), never patch.

**6. Milestone check with the user** when (a) placement metrics pass, (b) the first global route is <= 5 % open, and
whenever progress is flat for 3 iterations or time exceeds 2x estimate.  Bring measurements and one recommendation.

**7. Freeze and polish.**  Only after 0 open: freeze, then a tail loop for cleanup (length, stitching, plane slots,
silk), DRC 0 + parity 0 per commit, round log kept.

**8. Close-out.**  Plane integrity and island check, via-in-pad list to FAB.md, JLC checks, deviations reviewed.
