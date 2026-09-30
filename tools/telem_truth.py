"""Weapon ESC telemetry ground-truth check (HITL rig).

Arms the weapon, sweeps throttle with the HITL WEAPON override, and compares
the robot's AM32 telemetry against independent measurements:
  eRPM        vs the motor's phase-voltage frequency (ADALM2000 CH2 across two
              weapon phases, see tools/m2k_phase_worker.py)
  voltage     vs the PSU (also swept 12.6/11.1/10.5 V while spinning)
  current     vs PSU current above the armed baseline (the rig ESC has no sensor)
  temperature plausibility only
plus decode statistics from HITL EDTSTATS / TELEMSTATS.

usage: python3 tools/telem_truth.py [tag] [steps, e.g. 10,20,30,50,70,100,-50,0]
Pass criteria used in Sep 2026: eRPM within +/-1%, decode ok% = 100 at every
step, voltage within one 0.25 V step of the PSU, rpm 0 when stopped."""
import sys, time, re, statistics, subprocess, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import serial
import hitl_orchestrator as H
S = Path(__file__).parent
TOOLS = Path(__file__).resolve().parent
tag = sys.argv[1] if len(sys.argv) > 1 else "telem_sweep"
out = Path(__file__).resolve().parent.parent / "hitl_logs" / tag; out.mkdir(parents=True, exist_ok=True)
POLE_PAIRS = 7
STEPS = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "10,20,30,50,70,100,-50,0").split(",")]
ST = re.compile(r"HITL STATUS .*?weapon=(\S+) speed=(-?\d+) target=(-?\d+) thr=(\d+).* telem=(\d) age_ms=(\S+)(?: rpm=(\d+) erpm=(\d+) v=([0-9.]+) i=([0-9.]+) temp=(\d+))?")
EDT = re.compile(r"HITL EDTSTATS (.*)")
TS = re.compile(r"TELEMSTATS .*")
def psu(kind):
    r = subprocess.run(["labctl", "psu", "measure", "--channel", "1", "--kind", kind], capture_output=True, text=True)
    try: return float(r.stdout.strip().splitlines()[-1])
    except Exception: return None
rp, gp = H.resolve_robot_port(), H.resolve_gamepad_port()
H.picotool_reboot_application(H.get_usb_serial_for_tty(rp)); H.wait_for_tty_reenumerate(rp, 15)
H.picotool_reboot_application(H.get_usb_serial_for_tty(gp)); H.wait_for_tty_reenumerate(gp, 15)
rows = []
try:
  with serial.Serial(rp, 115200, timeout=0.05) as rs, serial.Serial(gp, 115200, timeout=0.05) as gs:
    R = H.SerialLogger(rs, out / "robot.log", "ROBOT"); G = H.SerialLogger(gs, out / "gamepad.log", "GAMEPAD")
    W = lambda pred, t=3.0: H.wait_for_robot_condition(R, timeout_s=t, predicate=pred, pump_logs=[G])
    def collect(t, cmds=()):
        st, edt, ts = [], [], []
        for c in cmds: R.send_line(c)
        end = time.monotonic() + t
        while time.monotonic() < end:
            G.read_line(); l = R.read_line()
            if not l: time.sleep(0.002); continue
            m = ST.search(l)
            if m: st.append(m.groups()); continue
            m = EDT.search(l)
            if m: edt.append(dict(kv.split("=",1) for kv in m.group(1).split())); continue
            if TS.search(l): ts.append(l)
        return st, edt, ts
    def edt_now():
        _, e, _ = collect(0.4, ["HITL EDTSTATS"]); return e[-1] if e else None
    m2k = subprocess.Popen([str(TOOLS / "m2k_phase_worker.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    assert m2k.stdout.readline().startswith("READY")
    def phase_freq():
        m2k.stdin.write(f"CAP {out}/ph.npy\n"); m2k.stdin.flush()
        l = m2k.stdout.readline().split()
        return (float(l[1]), float(l[2]), float(l[4])) if l and l[0] == "DONE" else (None, None, None)
    time.sleep(2); G.send_line("RESET"); W(lambda s: "t_ms" in s, 12)
    R.send_line("HITL BATTERY 12500"); W(lambda s: s.get("batt_mv") == "12500")
    H.ensure_robot_ready(R, G, timeout_s=40.0); W(lambda s: s.get("failsafe") == "0", 5)
    R.send_line("HITL STATUSRATE 50")
    H.labctl_psu_set(1, 12.6, 5.0); collect(1.5)
    i_base_disarmed = statistics.mean([psu("current") for _ in range(3)])
    G.send_line("BTN B 1"); time.sleep(0.15); G.send_line("BTN B 0")
    t_arm = time.monotonic()
    W(lambda s: s.get("weapon") == "ARMED", 10); arm_s = time.monotonic() - t_arm
    e0 = edt_now()
    st, _, _ = collect(5.0)
    e1 = edt_now()
    i_base = statistics.mean([psu("current") for _ in range(3)])
    idle_v = [float(x[8]) for x in st if x[8] is not None]
    K = ["sent","ok","no_start","bitcount","gcr","crc","erpm","stopped","temp","volt","curr","dbg","stress","event","e00","discarded_words"]
    delta = lambda a, b: {k: int(b[k]) - int(a[k]) for k in K}
    print(f"ARM took {arm_s:.2f}s; idle 5s EDT delta {delta(e0, e1)}")
    print(f"idle field ages: rpm={e1['rpm']} rpm_age={e1['rpm_age']} v={e1['v']} v_age={e1['v_age']} t={e1['t']} t_age={e1['t_age']} edt_active={e1['edt_active']}")
    print(f"idle v values: {sorted(set(idle_v))[:6]}  psu_v={psu('voltage')}  I_base disarmed={i_base_disarmed:.3f} armed={i_base:.3f}", flush=True)
    for pct in STEPS:
        collect(0.2, [f"HITL WEAPON {pct}"])
        collect(3.0 if pct else 2.5)
        ea = edt_now(); t0 = time.monotonic()
        st, _, ts = collect(2.0, ["HITL TELEMSTATS"])
        eb = edt_now(); dt = time.monotonic() - t0
        f, vpp, snr = phase_freq()
        pv, pi = psu("voltage"), psu("current")
        rpm = [int(x[6]) for x in st if x[6]]; erpm = [int(x[7]) for x in st if x[7]]
        v = [float(x[8]) for x in st if x[8]]; cur = [float(x[9]) for x in st if x[9]]; tmp = [int(x[10]) for x in st if x[10]]
        true_erpm = f * 60 if (f and vpp and vpp > 1.0) else 0.0
        row = dict(pct=pct, thr=st[-1][3] if st else None,
                   rpm_med=statistics.median(rpm) if rpm else None, erpm_med=statistics.median(erpm) if erpm else None,
                   erpm_min=min(erpm) if erpm else None, erpm_max=max(erpm) if erpm else None,
                   true_erpm=round(true_erpm), phase_vpp=vpp, phase_snr=snr,
                   v_med=statistics.median(v) if v else None, psu_v=pv,
                   i_med=statistics.median(cur) if cur else None, psu_i=pi, psu_i_delta=round(pi - i_base, 3) if pi is not None else None,
                   temp=statistics.median(tmp) if tmp else None,
                   rates_hz={k: round(v / dt, 1) for k, v in delta(ea, eb).items() if v} if ea and eb else None,
                   telemstats=ts[-1][:220] if ts else None)
        if row["erpm_med"] and true_erpm: row["erpm_err_pct"] = round(100 * (row["erpm_med"] - true_erpm) / true_erpm, 2)
        rows.append(row); print(json.dumps(row), flush=True)
    collect(0.2, ["HITL WEAPON 30"]); collect(3.0)
    for vset in (12.6, 11.1, 10.5, 12.6):
        H.labctl_psu_set(1, vset, 5.0); collect(3.0)
        _, e, _ = collect(0.4, ["HITL EDTSTATS"])
        print(f"VSWEEP set={vset} psu={psu('voltage')} esc_v={e[-1]['v'] if e else None} v_age={e[-1]['v_age'] if e else None}", flush=True)
    collect(0.2, ["HITL WEAPON OFF"]); collect(3.0)
    _, e, _ = collect(0.4, ["HITL EDTSTATS"])
    print(f"after stop: rpm={e[-1]['rpm']} rpm_age={e[-1]['rpm_age']} stopped={e[-1]['stopped']}", flush=True)
    G.send_line("BTN B 1"); time.sleep(0.15); G.send_line("BTN B 0"); collect(1.0)
    m2k.stdin.write("QUIT\n"); m2k.stdin.flush()
finally:
    H.labctl_psu_off(1)
    json.dump(rows, open(out / "rows.json", "w"), indent=1)
