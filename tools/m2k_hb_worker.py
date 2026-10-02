#!/opt/labctl/venv/bin/python3
"""ADALM2000 worker for tools/hitl_drive_hb.py (runs under the labctl venv, which has libm2k).

Rig wiring (M2K GND to both Pico GNDs):
  DIO0 emulator GP15 (HID-send marker)   DIO1 robot GP15 (report-rx marker)
  DIO2 robot GP0 left IN1                DIO3 robot GP1 left IN2
  DIO4 robot GP4 weapon DShot            DIO5 robot GP2 right IN1
  DIO6 robot GP3 right IN2               DIO7 robot GP6 DRV8874 nSLEEP
  CH1 (+1/-1) across the left motor (OUT1/OUT2), CH2 (+2/-2) across the right.

Analog and digital are started together (mixed-signal acquisition), but the
analog samples still lag the digital ones by ~5-6 ms, varying per capture; the
analyses that need both locate events in each domain separately.

Protocol (one command per stdin line, one reply line each, replies are JSON
after the keyword):
  CAP <rate_hz> <n_samples> <out.npz>
      starts a free-running capture, prints 'ARMED', then blocks until the n
      samples are in, saves them and prints 'DONE {...summary}'.  The caller
      applies its stimulus between ARMED and DONE.
  AN <out.npz> <json-args>
      analyses a saved capture, prints 'RESULT {...}'.  args["kind"]:
        "summary"  per-DIO duty/frequency/edges and per-channel analog stats
        "drive"    per-motor signed drive duty, brake and coast fractions in
                   bins of args["bin_us"] (default 1000), plus marker edges
        "coast"    windows where a motor's IN1 and IN2 are both low for at
                   least args["min_ms"]; back-EMF at the window start (see
                   an_coast for how the analog lag is handled)
        "levels"   per-channel PWM rail levels (gain/offset calibration)
        "analog"   per-channel mean voltage in bins of args["bin_us"]
        "phases"   per-motor median voltage in each H-bridge state
  QUIT
"""
import json
import sys

import libm2k
import numpy as np

MOTORS = {"L": {"in1": 2, "in2": 3, "ch": 0}, "R": {"in1": 5, "in2": 6, "ch": 1}}

ctx = libm2k.m2kOpen()
if ctx is None:
    print("ERR no M2K", flush=True)
    sys.exit(1)
ctx.calibrateADC()
ctx.setTimeout(20000)
ain = ctx.getAnalogIn()
ain.reset()
dig = ctx.getDigital()
dig.reset()
for ch in (0, 1):
    ain.enableChannel(ch, True)
    ain.setRange(ch, libm2k.PLUS_MINUS_25V)
atrig = ain.getTrigger()
for ch in (0, 1):
    atrig.setAnalogMode(ch, libm2k.ALWAYS)
for ch in range(8):
    dig.setDirection(ch, libm2k.DIO_INPUT)
    dig.enableChannel(ch, True)
dtrig = dig.getTrigger()
for ch in range(16):
    dtrig.setDigitalCondition(ch, libm2k.NO_TRIGGER_DIGITAL)
print("READY", flush=True)


def reply(kind, obj):
    print(kind + " " + json.dumps(obj, separators=(",", ":")), flush=True)


def capture(rate, n, path):
    ain.setSampleRate(rate)
    dig.setSampleRateIn(rate)
    ctx.startMixedSignalAcquisition(n)
    print("ARMED", flush=True)
    try:
        a = np.asarray(ain.getSamples(n), dtype=np.float32)
        d = np.asarray(dig.getSamples(n), dtype=np.uint16)
    finally:
        ctx.stopMixedSignalAcquisition()
    rate_actual = float(ain.getSampleRate())
    np.savez(path, a=a, d=d, rate=rate_actual)
    return {"path": path, "n": int(len(d)), "rate": rate_actual,
            "a_mean": [round(float(x.mean()), 3) for x in a]}


def bit(d, ch):
    return ((d >> ch) & 1).astype(np.int8)


def edges(v, rate):
    dv = np.diff(v)
    return {"rise_s": (np.flatnonzero(dv == 1) / rate).round(6).tolist(),
            "fall_s": (np.flatnonzero(dv == -1) / rate).round(6).tolist()}


def an_summary(a, d, rate, args):
    out = {"dio": {}, "analog": []}
    for ch in range(8):
        v = bit(d, ch)
        rises = int((np.diff(v) == 1).sum())
        out["dio"][str(ch)] = {"duty": round(float(v.mean()), 4), "rises": rises,
                               "freq_hz": round(rises * rate / len(v), 1)}
    for x in a:
        out["analog"].append({"mean": round(float(x.mean()), 3), "min": round(float(x.min()), 3),
                              "max": round(float(x.max()), 3)})
    return out


def an_drive(a, d, rate, args):
    bin_n = max(1, int(round(args.get("bin_us", 1000) * rate / 1e6)))
    out = {"bin_s": bin_n / rate, "markers": {}}
    for name, m in MOTORS.items():
        i1, i2 = bit(d, m["in1"]), bit(d, m["in2"])
        n = len(i1) // bin_n * bin_n
        fwd = ((i1 == 1) & (i2 == 0))[:n].reshape(-1, bin_n).mean(1)
        rev = ((i1 == 0) & (i2 == 1))[:n].reshape(-1, bin_n).mean(1)
        brk = ((i1 == 1) & (i2 == 1))[:n].reshape(-1, bin_n).mean(1)
        cst = ((i1 == 0) & (i2 == 0))[:n].reshape(-1, bin_n).mean(1)
        out[name] = {"drive": (fwd - rev).round(4).tolist(), "brake": brk.round(4).tolist(),
                     "coast": cst.round(4).tolist()}
    for ch in (0, 1, 7):
        out["markers"][str(ch)] = edges(bit(d, ch), rate)
    return out


def _jumps(x, thr):
    return np.flatnonzero(np.abs(np.diff(x)) > thr)


def an_coast(a, d, rate, args):
    """Back-EMF in coast windows (both IN low >= min_ms).

    The M2K's analog samples lag its digital samples by a few ms, and the lag
    differs between captures, so each window is located in the analog trace
    itself: the digital window (exact length) is slid over a lag range and
    placed where it contains the fewest PWM switching edges, or for a window
    taken from 100% duty (no PWM edges), where the voltage steps down into it
    and back up out of it.  Brush-commutation spikes are suppressed with 0.25 ms
    bin medians; a line fitted to them is extrapolated back to the window start
    (the wheel slows while coasting)."""
    min_n = int(args.get("min_ms", 2.0) * rate / 1000)
    skip_n = int(args.get("skip_ms", 0.3) * rate / 1000)
    tail_n = int(args.get("tail_ms", 0.3) * rate / 1000)
    lag_lo = int(args.get("lag_min_ms", 2.0) * rate / 1000)
    lag_hi = int(args.get("lag_max_ms", 9.0) * rate / 1000)
    vb = float(args.get("vb", 12.0))
    thr = 0.3 * vb
    bin_n = max(1, int(0.00025 * rate))
    out = {}
    for name, m in MOTORS.items():
        i1, i2, x = bit(d, m["in1"]), bit(d, m["in2"]), a[m["ch"]]
        both_low = ((i1 == 0) & (i2 == 0)).astype(np.int8)
        padded = np.concatenate(([0], both_low, [0]))
        starts = np.flatnonzero(np.diff(padded) == 1)
        ends = np.flatnonzero(np.diff(padded) == -1)
        jumps = _jumps(x, thr)
        wins = []
        for s, e in zip(starts, ends):
            if e - s < min_n or s == 0 or e >= len(both_low):
                continue
            pre = slice(max(0, s - int(0.002 * rate)), s)
            fwd = float(((i1[pre] == 1) & (i2[pre] == 0)).mean())
            rev = float(((i1[pre] == 0) & (i2[pre] == 1)).mean())
            pwm_edges = int((np.diff(i1[pre]) != 0).sum() + (np.diff(i2[pre]) != 0).sum())
            lags = np.arange(lag_lo, lag_hi)
            lags = lags[e + lags + int(0.001 * rate) < len(x)]
            if len(lags) == 0:
                continue
            if pwm_edges > 4:
                # count of analog switching edges inside each candidate window
                cs = np.searchsorted(jumps, s + lags)
                ce = np.searchsorted(jumps, e + lags)
                score = ce - cs
                best = score.min()
                cand = lags[score == best]
                lag = int(cand[len(cand) // 2])
                method = "edges"
            else:
                c = np.concatenate(([0.0], np.cumsum(x, dtype=np.float64)))
                q = int(0.0005 * rate)
                g = int(0.0002 * rate)

                def mean(lo, hi):
                    return (c[hi] - c[lo]) / (hi - lo)
                sign = 1.0 if fwd >= rev else -1.0
                sc = []
                for L in lags:
                    ws, we = s + L, e + L
                    sc.append(sign * (mean(ws - q, ws) - mean(ws + g, ws + g + q)
                                      + mean(we + g, we + g + q) - mean(we - g - q, we - g)))
                lag = int(lags[int(np.argmax(sc))])
                best = None
                method = "step"
            ws, we = s + lag, e + lag
            seg = x[ws + skip_n: we - tail_n]
            nb = len(seg) // bin_n
            if nb < 3:
                continue
            med = np.median(seg[: nb * bin_n].reshape(nb, bin_n), axis=1)
            t = (skip_n + (np.arange(nb) + 0.5) * bin_n) / rate
            k, b = np.polyfit(t, med, 1)
            drv = x[max(0, ws - int(0.002 * rate)): ws]
            wins.append({"t_s": round(s / rate, 6), "len_ms": round((e - s) * 1000 / rate, 3),
                         "lag_ms": round(lag * 1000 / rate, 3), "lag_method": method,
                         "edges_in_window": None if best is None else int(best),
                         "drive_frac": round(fwd - rev, 4),
                         "emf0_v": round(float(b), 4), "slope_v_per_ms": round(float(k) / 1000, 4),
                         "emf_mean_v": round(float(med.mean()), 4),
                         "emf_end_v": round(float(np.median(med[-4:])), 4),
                         "driven_mean_v": round(float(drv.mean()), 4) if len(drv) else None})
        out[name] = wins
    return out


def an_levels(a, d, rate, args):
    """PWM rail levels per channel (no digital alignment needed): median of the
    samples in the top and bottom clusters, and the overall median."""
    out = []
    for x in a:
        lo, hi = np.percentile(x, 0.5), np.percentile(x, 99.5)
        span = hi - lo
        res = {"median": round(float(np.median(x)), 4)}
        if span > 2.0:
            res["high"] = round(float(np.median(x[x > hi - 0.25 * span])), 4)
            res["low"] = round(float(np.median(x[x < lo + 0.25 * span])), 4)
        out.append(res)
    return out


def an_analog(a, d, rate, args):
    bin_n = max(1, int(round(args.get("bin_us", 1000) * rate / 1e6)))
    n = a.shape[1] // bin_n * bin_n
    return {"bin_s": bin_n / rate,
            "ch": [x[:n].reshape(-1, bin_n).mean(1).round(4).tolist() for x in a]}


def an_phases(a, d, rate, args):
    """Median motor voltage in each H-bridge state (calibration: brake = 0 V,
    drive = supply minus FET drops)."""
    out = {}
    for name, m in MOTORS.items():
        i1, i2, x = bit(d, m["in1"]), bit(d, m["in2"]), a[m["ch"]]
        res = {"mean": round(float(x.mean()), 4)}
        for state, mask in (("fwd", (i1 == 1) & (i2 == 0)), ("rev", (i1 == 0) & (i2 == 1)),
                            ("brake", (i1 == 1) & (i2 == 1)), ("coast", (i1 == 0) & (i2 == 0))):
            # Drop samples next to a transition (ringing, M2K bandwidth).
            ok = mask.copy()
            ok[1:] &= mask[:-1]
            ok[:-1] &= mask[1:]
            res[state] = round(float(np.median(x[ok])), 4) if ok.sum() > 20 else None
            res[state + "_frac"] = round(float(mask.mean()), 4)
        out[name] = res
    return out


ANALYSES = {"phases": an_phases, "levels": an_levels, "summary": an_summary, "drive": an_drive, "coast": an_coast, "analog": an_analog}

for line in sys.stdin:
    parts = line.split(None, 2)
    if not parts:
        continue
    try:
        if parts[0] == "QUIT":
            break
        if parts[0] == "CAP":
            reply("DONE", capture(int(float(parts[1])), int(parts[2].split()[0]), parts[2].split()[1]))
        elif parts[0] == "AN":
            path, rest = parts[1], parts[2] if len(parts) > 2 else "{}"
            args = json.loads(rest)
            z = np.load(path)
            reply("RESULT", ANALYSES[args.get("kind", "summary")](z["a"], z["d"], float(z["rate"]), args))
        else:
            print("ERR unknown command", flush=True)
    except Exception as e:  # report and keep serving
        print("ERR " + repr(e).replace("\n", " "), flush=True)
libm2k.contextClose(ctx)
