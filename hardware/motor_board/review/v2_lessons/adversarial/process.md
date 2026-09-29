# Adversarial review: the v2 process plan (process.md "Proposed v2 workflow", README §3)

Stance: skeptical EDA lead.  Evidence: `kicad/gen/router.py`, `route_all.py`, the four memos.

**Verdict.** The diagnosis is right: v1 was lost to placement, pins and layer allocation, not to density.  The fix is
aimed at the wrong layer.  Five of the six root causes are placement/pins/layers, yet the biggest new cost is a
detailed router.  The routability gate is right in intent but cannot be computed as written.  Keep steps 1-3.
Replace step 5 with a cheap *global* router plus a time-boxed detailed route.  Allow a few hand-finished opens.

## C1 (critical): PathFinder on router.py is a rewrite, and "< 2 min" is not credible

What router.py is today:

- A 0.05 mm grid: about 1.19 M cells per layer, about 4.8 M nodes on 4 layers.
- Pure-Python A* (`heapq`, tuple keys, `best`/`parent` dicts).
- An `owner` array with **one net per cell**.
- Legality is a boolean `free_t`/`free_v`, rebuilt for each request from a fresh `distance_transform_edt` of the
  other nets' copper, per layer.
- Measured: about 800 requests in 8 min, so about 0.6 s per connection.

PathFinder re-routes every net on every iteration with soft costs.  Here is what that needs:

- **Runtime.** 30-50 iterations × 311-800 connections × 0.6 s is **2-5 h per global run**.  "< 2 min" needs more
  than 100× (numba/C++, flat arrays).
- **Occupancy.** `owner` cannot hold two nets.  Negotiation needs per-cell counts and removable per-net copper.
- **Clearance vs congestion.** Clearance lives in a non-additive EDT.  Two tracks conflict when their dilated swaths
  touch, not when they share a cell, so "overuse" on a 0.05 mm grid is ill-defined.
  - Working routers use a track-pitch grid (0.3 mm for 0.15/0.15, one node = one legal track position).
  - Or they use gridless shape conflicts, which is most of Freerouting's code.
- **Vias.** The via is v1's binding resource, yet it has a flat `via_cost = 1.5` and no congestion term.  It needs
  an ~0.8-0.9 mm multi-layer exclusion disc that is shared and priced.
- **Multi-pin nets.** Requests are 2-point, with the topology pre-chosen in `blocks.json`, and own-net tracks are
  not goals.  Negotiation needs tree growth.
- **Pads.** Pads are rasterised as bounding boxes, and `MARGIN = 0.05` is added to every clearance.  That is a 33 %
  tax on 0.15 mm clearance, about 15 % of the lanes, exactly in the fine-pitch fields that decide closure.
- **Rules.** Net-class clearance only.  None of the custom `.kicad_dru` widths, net-ties, zone thermals or fill
  behaviour is modelled.

Realistic cost: **1-2 weeks** before it routes this board.  That is more than all of v1's routing, and it is the
"autorouter script dev" the user asked to avoid (process §14).

## C2 (critical): "capacity" is undefined, and the plan counts L3 as signal capacity that electrical.md forbids

A computable definition:

- **Capacity** of a cut segment on layer *k* = (length − blocked length) / (w + s), about 3.3 tracks/mm at
  0.15/0.15.
- The blocked length counts pads, pours, keep-outs, via fields, and bottom-part courtyards on L4.
- **Demand** = the MST edges that cross the segment.

The contradiction: process step 0 says "L3 signals + rail trunks".  Electrical.md B makes L3 **L4's reference**:
GND wherever L4 signals run, the front band a VBAT pour, and only "few slow lanes where no L4 signal runs above".

In the logic core that leaves about 1.5 signal layers, not 3.  A gate that counts L3 passes unroutable placements.
Capacity needs an L3/L4 exclusion term: an L3 lane consumes the L4 capacity above it.

Straight cut lines are arbitrary.  v1 died of a 2D via-site shortage around U1, which no single line captures.
Measure it with:

- **gcell global routing:** edge capacity per layer from the real blockage, and via capacity per tile from the legal
  via sites;
- **RUDY** as a zero-cost first screen.

Ratsnest crossings are a good objective for pin assignment, but a weak routability gate on 4 layers.

## M1 (major): the plan overfits to v1

- **"Never patch after the autoroute; re-place instead" will loop on a single stubborn net.**  Professionals finish
  the last 1-3 % by hand with push-and-shove.  Set a threshold instead: ≤ ~10 opens may be hand-finished if none
  lies on an over-capacity edge; anything beyond that goes back to placement.
- **The ban on hand-drawn long buses throws out v1's best hand work.**  v1's buses failed because they were drawn
  before any feasibility check.  A hand-designed U1 escape pattern co-designed with the pin map (critique §8) is
  the highest-value hand work on the board.  The rule "nothing longer than a few mm crossing a cut line" forbids
  it.  The same rule also contradicts the **gate/Kelvin pairs**, which run from U2 to the front-right cells and
  cross the power/logic boundary by construction.  Budget both in the line's capacity; don't ban them.
- **Freerouting never got a valid trial.**
  - 09-25 was stopped after **pass 1**, and pass 1 is always poor; Freerouting needs tens of passes.
  - 09-26's ">1000 violations on KiCad-clean copper" is a DSN rule-export mismatch, not router quality.
  - Both runs were on the placement all four memos call unroutable.

## M2 (major): no validation loop from the router to KiCad DRC

The plan needs three checks:

- **(a) A rule-equivalence test.** Route a known-dense patch (v1's U1 field), apply it, and require 0 DRC errors.
  Then shrink MARGIN until DRC breaks, and back off one step.
- **(b) Zone refill + DRC + island check on every run.** L4 signals will shred the L4 GND fill, as they did v1's
  3V3 fill.
- **(c)** Enforce the `.kicad_dru` class widths and net-ties on the router's output.

## M3 (major): no time-box or kill criteria for tool development

§9 time-boxes routing but not tooling, and v1 lost many of its ~30 h to tools that were later abandoned.  Each tool
effort needs a spike budget and a benchmark agreed in advance.  Tell the user before any method switch.

## M4 (major): DFM and assembly are left to close-out

These change placement, so they belong in step 0:

- **JLC 4-layer:** the via menu, a 0.3/0.15 surcharge, the via-in-pad price.  The via cost and the escape pattern
  depend on the answer.
- **Assembly:** two-sided assembly and its second setup (J1 forces bottom parts), and the bottom height limit.
- **Fab details:** panel rails, fiducials, part-to-edge distances, thermal-pad paste windowing, drop-via tenting
  under fine pitch, and mask dams at 0.5 mm pitch.
- **Test/debug access:** probe access and the SWD/Tag-Connect decision.

## M5 (major): the user checkpoints are in the wrong order

The part-size decisions (README §5, ~300 mm²) set the area budget, so ask them **before** the floorplan.  Add a
user checkpoint after pin assignment, because it changes the firmware contract.

## m1 (minor): cost-model gaps

- **Prose-only rules.** Several rules exist only as prose; without soft costs each one becomes a manual pass after
  routing:
  - no L4 signal over an L3 lane;
  - analog ≥ 1 mm from phase/SW/gate;
  - the INH lines away from the ADC pins;
  - a GND stitch via within 1 mm of every L1↔L4 via.
- **Gate/Kelvin pairs.** They are coupled pairs (same layer, adjacent, paired vias), not impedance-controlled.  No
  planned router handles pairs, so state that they stay hand-drawn.
- **Via-in-pad.** Give it a cost (price, wicking) or forbid it for signals.  In v1 it was an escape valve.

## m2 (minor): environment

15 GB RAM with swap full.  A 4.8 M-node search in Python dicts beside pcbnew will not fit.

---

## Alternative plan (prioritized, time-boxed)

**P0. Constraint freeze, ≤ ½ day, then a user checkpoint.**
- The part-size questions.
- The JLC 4-layer via, via-in-pad and stack-up quote.
- The assembly sides and height limit.
- One stack-up rule set: L3 = GND except the front VBAT band and the named slow lanes.  Write it into the
  `.kicad_dru`.

**P1. Floorplan + pin assignment, as planned, 1 day.**
Score by crossings and edge bearing, AF-checked.  Then a user checkpoint on the floorplan and the pin map.

**P2. Global router as the gate: ≤ 1 day to build, seconds to run.**
This is where PathFinder belongs:
- 0.5-1 mm gcells;
- per-layer edge capacity from the real blockage, with the L3/L4 exclusion;
- per-tile via capacity from the legal via sites left after the decap/GND drops;
- MST net topologies.

About 300 lines of numpy.

- **Gate:** 0 overflow, peak edge use ≤ 80 %, core mean ≤ 60-70 %, via demand ≤ 70 % of the sites under
  U1/U2/U3/U4.
- **Output:** corridors, a heat map, and a predicted via count (target ≈ 1.1 per connection).
- **Validation:** it must *predict* v1's failure on the v1 placement.

**P3. Hand-designed escapes and critical copper, 1 day.**
- The U1 via row 1.5-2 mm outside the body, matched to the pins and the P2 corridors.
- QFN fan-outs and thermal arrays, decap drops.
- Gate/Kelvin pairs, buck loop, pack pours.

Then re-run P2 with this copper frozen.

**P4. Detailed route, time-boxed.**
- **(a) Freerouting, 2 h.**
  - First the DSN round-trip on the P3 board: 0 violations on import, using clearance compensation and the class
    rules.
  - Fanout off, P3 copper locked.
  - Stop if the unrouted count has not fallen over 5 passes.
- **(b) router.py inside the P2 corridors.**  Confine each A* to its corridor plus one tile: about 50× less search,
  and most of the order dependence goes because the global router already negotiated the crossings.  Rip-up only
  among corridor-mates.  This reuses DRC-validated code for about 1 day of work.
- **(c) Both stall above ~10 opens:** the problem is in P1/P2, so go back with the heat map.

**P5. Hand finish, ≤ 10 local opens.**  The user in KiCad push-and-shove (their stated preference), or the tail
ops.  DRC 0 + parity 0 per commit.

**P6. Close-out.**  Refill, the island and antipad-chain checks, the JLC DFM upload, two-sided assembly outputs,
then a user review.

**Kill criteria:**
- P2 fails to predict v1's U1 failure within 1 day → fall back to RUDY + hand channel counts.
- P4 over its box → go to (c), never to a sweep.
- Any step at 2× its estimate → stop and report to the user with measurements.

## What will likely fail first as written

1. **Week one disappears into the router core** (occupancy, clearance-aware conflicts, speed).  Meanwhile the
   placement iterates unmeasured, because the gate's capacity has no definition.
2. **The first negotiated runs "converge" by using L3 lanes under L4 signals.**  The electrical review then
   rejects the result after routing.
3. **The U1/U2 fine-pitch escapes report overuse that is really bbox-pad and margin error.**  The plan's
   "never patch" rule then sends the team back into re-placement.
