#!/usr/bin/env python3
"""
Generate a Markdown + PDF report for a HITL run directory produced by tools/hitl_orchestrator.py.

This script is intentionally standalone and is invoked by the orchestrator via the repo's
Python venv (./.venv/bin/python3) so we can rely on matplotlib without requiring system-wide
packages.
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


HITL_STATUS_RE = re.compile(r"^HITL STATUS (.+)$")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def parse_kv_payload(payload: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in payload.strip().split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k] = v
    return out


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_int(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(str(s).strip())
    except ValueError:
        return None


def safe_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(str(s).strip())
    except ValueError:
        return None


@dataclass
class StatusSeries:
    t_s: list[float]
    dl_us: list[int]
    dr_us: list[int]
    failsafe: list[int]
    armed: list[int]
    conn: list[int]
    ry: list[int]
    rpm: list[int | None]


def parse_robot_status_series(robot_serial_log: Path) -> StatusSeries | None:
    if not robot_serial_log.exists():
        return None

    t_s: list[float] = []
    dl_us: list[int] = []
    dr_us: list[int] = []
    failsafe: list[int] = []
    armed: list[int] = []
    conn: list[int] = []
    ry: list[int] = []
    rpm: list[int | None] = []

    for line in robot_serial_log.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        try:
            ts = float(parts[0].strip())
        except ValueError:
            continue
        payload = parts[3].strip()
        m = HITL_STATUS_RE.match(payload)
        if not m:
            continue
        kv = parse_kv_payload(m.group(1))
        dl = safe_int(kv.get("dl_us"))
        dr = safe_int(kv.get("dr_us"))
        fs = safe_int(kv.get("failsafe"))
        ar = safe_int(kv.get("armed"))
        co = safe_int(kv.get("conn"))
        ryy = safe_int(kv.get("ry"))

        if dl is None or dr is None:
            continue

        t_s.append(ts)
        dl_us.append(dl)
        dr_us.append(dr)
        failsafe.append(0 if fs is None else fs)
        armed.append(0 if ar is None else ar)
        conn.append(0 if co is None else co)
        ry.append(0 if ryy is None else ryy)
        rpm.append(safe_int(kv.get("rpm")))

    if not t_s:
        return None
    return StatusSeries(
        t_s=t_s,
        dl_us=dl_us,
        dr_us=dr_us,
        failsafe=failsafe,
        armed=armed,
        conn=conn,
        ry=ry,
        rpm=rpm,
    )


def contiguous_spans(t: list[float], flags: list[int], wanted: int = 1) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    if not t:
        return spans
    start: float | None = None
    last_t = t[0]
    for ti, fi in zip(t, flags):
        if fi == wanted and start is None:
            start = ti
        if fi != wanted and start is not None:
            spans.append((start, last_t))
            start = None
        last_t = ti
    if start is not None:
        spans.append((start, last_t))
    return spans


def plot_psu_current(samples_path: Path, title: str, out_png: Path, *, pdf=None) -> bool:
    if not samples_path.exists():
        return False

    # Import matplotlib lazily so this script can still run if invoked outside the venv.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    samples = load_json(samples_path)
    points = [(s.get("t_s"), s.get("phase"), s.get("current_a")) for s in samples]
    points = [(t, p, i) for (t, p, i) in points if isinstance(t, (int, float)) and isinstance(p, str) and i is not None]
    if not points:
        return False

    t = [float(x[0]) for x in points]
    phase = [str(x[1]) for x in points]
    curr = [float(x[2]) for x in points]

    # Phase coloring.
    palette = {
        "baseline": "#4c78a8",
        "step_up": "#f58518",
        "step_down": "#54a24b",
        "run": "#f58518",
        "drive_run": "#54a24b",
        "disarmed_cmd": "#b279a2",
        "estop": "#e45756",
        "forward": "#54a24b",
        "turn": "#e45756",
        "left_only": "#eeca3b",
        "right_only": "#ff9da6",
        "stop_left": "#b279a2",
        "stop_right": "#72b7b2",
        "stop1": "#b279a2",
        "stop2": "#72b7b2",
    }

    fig, ax = plt.subplots(figsize=(10.5, 4.0), constrained_layout=True)
    ax.plot(t, curr, color="#111111", linewidth=1.2, marker="o", markersize=3, label="current (A)")
    ax.set_title(title)
    ax.set_xlabel("t (s)")
    ax.set_ylabel("current (A)")
    ax.grid(True, alpha=0.3)

    # Shade contiguous phase spans.
    last_phase = phase[0]
    span_start = t[0]
    for ti, ph in zip(t[1:], phase[1:]):
        if ph != last_phase:
            ax.axvspan(span_start, ti, color=palette.get(last_phase, "#cccccc"), alpha=0.10, linewidth=0)
            span_start = ti
            last_phase = ph
    ax.axvspan(span_start, t[-1], color=palette.get(last_phase, "#cccccc"), alpha=0.10, linewidth=0)

    # Add a compact legend for phases that appeared.
    seen = sorted(set(phase), key=lambda p: phase.index(p))
    handles = []
    labels = []
    for ph in seen:
        c = palette.get(ph, "#cccccc")
        h = plt.Line2D([0], [0], color=c, linewidth=6, alpha=0.6)
        handles.append(h)
        labels.append(ph)
    if handles:
        ax.legend(handles, labels, title="phase", loc="upper right", framealpha=0.9)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    return True


def plot_drive_pwm(series: StatusSeries, title: str, out_png: Path, *, pdf=None) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not series.t_s:
        return False

    # Only emit if there's meaningful motion.
    motion = max(max(abs(v - 1500) for v in series.dl_us), max(abs(v - 1500) for v in series.dr_us))
    if motion < 15:
        return False

    fig, ax = plt.subplots(figsize=(10.5, 4.2), constrained_layout=True)
    ax.plot(series.t_s, series.dl_us, label="dl_us (left)", linewidth=1.2)
    ax.plot(series.t_s, series.dr_us, label="dr_us (right)", linewidth=1.2)
    ax.axhline(1500, color="#666666", linewidth=1, linestyle="--", alpha=0.7)
    ax.set_title(title)
    ax.set_xlabel("t (s)")
    ax.set_ylabel("pulse (us)")
    ax.grid(True, alpha=0.25)

    # Shade failsafe windows.
    for a, b in contiguous_spans(series.t_s, series.failsafe, wanted=1):
        ax.axvspan(a, b, color="#e45756", alpha=0.10, linewidth=0)

    ax.legend(loc="upper right", framealpha=0.9)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    return True


@dataclass
class WeaponSeries:
    t_s: list[float]
    speed: list[int]
    target: list[int]
    thr: list[int]
    rpm: list[int | None]


def parse_weapon_status_series(robot_serial_log: Path) -> WeaponSeries | None:
    if not robot_serial_log.exists():
        return None

    t_s: list[float] = []
    speed: list[int] = []
    target: list[int] = []
    thr: list[int] = []
    rpm: list[int | None] = []

    for line in robot_serial_log.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        try:
            ts = float(parts[0].strip())
        except ValueError:
            continue
        payload = parts[3].strip()
        m = HITL_STATUS_RE.match(payload)
        if not m:
            continue
        kv = parse_kv_payload(m.group(1))

        sp = safe_int(kv.get("speed"))
        tg = safe_int(kv.get("target"))
        th = safe_int(kv.get("thr"))
        if sp is None or tg is None or th is None:
            continue

        t_s.append(ts)
        speed.append(sp)
        target.append(tg)
        thr.append(th)
        rpm.append(safe_int(kv.get("rpm")))

    if not t_s:
        return None
    return WeaponSeries(t_s=t_s, speed=speed, target=target, thr=thr, rpm=rpm)


def plot_weapon_latency(step_dir: Path, title: str, out_png: Path, *, pdf=None, cycle_idx: int = 0) -> bool:
    """Plot 1 - Command vs RPM Time Series for a single cycle."""
    result_path = step_dir / "weapon_latency_result.json"
    if not result_path.exists():
        return False

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    result = load_json(result_path)
    if not isinstance(result, dict):
        return False

    cycles = result.get("cycles") or []
    if cycle_idx >= len(cycles):
        return False

    cycle = cycles[cycle_idx]
    ts_list = cycle.get("time_series") or []
    if not ts_list:
        return False

    timestamps = cycle.get("timestamps") or {}
    latency = cycle.get("latency_ms") or {}

    # Extract time series relative to command sent.
    t0 = timestamps.get("host_cmd_sent_s") or 0.0
    t_rel = [pt.get("t_s", 0) - t0 for pt in ts_list]
    targets = [pt.get("target", 0) for pt in ts_list]
    speeds = [pt.get("speed", 0) for pt in ts_list]
    thrs = [pt.get("thr", 0) for pt in ts_list]
    rpms = [pt.get("rpm_filtered", pt.get("rpm", 0)) for pt in ts_list]

    fig, ax = plt.subplots(figsize=(11.0, 5.0), constrained_layout=True)
    ax.step(t_rel, targets, where="post", color="#2ca02c", linewidth=1.4, alpha=0.85, label="target (%)")
    ax.step(t_rel, speeds, where="post", color="#1f77b4", linewidth=1.1, alpha=0.7, label="speed (%)")
    ax.set_xlabel("time relative to command (s)")
    ax.set_ylabel("weapon (%)")
    ax.set_ylim(-2, 105)
    ax.set_title(f"{title} (cycle {cycle_idx + 1}, axis={cycle.get('axis_value', '?')})")
    ax.grid(True, alpha=0.25)

    # Right Y axis for RPM.
    ax2 = ax.twinx()
    ax2.plot(t_rel, rpms, color="#d62728", linewidth=1.3, alpha=0.9, label="RPM (filtered)")
    ax2.set_ylabel("RPM")
    ax2.grid(False)

    # Vertical dashed lines for latency events.
    event_colors = {
        "host_emu_hid_sent_s": ("#9467bd", "emu_sent"),
        "host_robot_ry_event_s": ("#8c564b", "ry_change"),
        "host_robot_rpm_event_s": ("#e377c2", "rpm_seen"),
    }
    for key, (color, label) in event_colors.items():
        val = timestamps.get(key)
        if val is not None:
            x = float(val) - t0
            ax.axvline(x, color=color, linewidth=1.2, linestyle="--", alpha=0.85)
            ax.text(x, 100, label, rotation=90, va="top", ha="right", fontsize=7, color=color)

    # Command down line.
    cmd_down_s = timestamps.get("host_cmd_down_s")
    if cmd_down_s is not None:
        ax.axvline(float(cmd_down_s) - t0, color="#7f7f7f", linewidth=1.2, linestyle="--", alpha=0.7)
        ax.text(float(cmd_down_s) - t0, 100, "cmd_zero", rotation=90, va="top", ha="right", fontsize=7, color="#7f7f7f")

    # Annotation box with latency breakdown.
    parts: list[str] = []
    for k in ["total_host", "total_fw", "emu_internal", "bt_link_approx",
              "fw_input_to_target", "fw_target_to_dshot", "fw_dshot_to_rpm"]:
        v = latency.get(k)
        if v is not None:
            parts.append(f"{k}: {v:.1f}ms")
    if parts:
        ax.text(0.02, 0.98, "\n".join(parts), transform=ax.transAxes, fontsize=7,
                va="top", ha="left", family="monospace",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    # Combined legend.
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower right", framealpha=0.9, fontsize=8)

    # Optional: PSU current overlay — clip to this cycle's time range.
    psu_path = step_dir / "psu_current_samples.json"
    if psu_path.exists():
        try:
            psu = load_json(psu_path)
            t_min = t_rel[0] + t0 if t_rel else t0
            t_max = t_rel[-1] + t0 if t_rel else t0
            psu_clipped = [(s.get("t_mid_s", s.get("t_s", 0)) - t0, float(s["current_a"]))
                           for s in psu
                           if isinstance(s.get("current_a"), (int, float))
                           and t_min <= s.get("t_mid_s", s.get("t_s", 0)) <= t_max]
            if psu_clipped:
                psu_t, psu_i = zip(*psu_clipped)
                ax3 = ax.twinx()
                ax3.spines["right"].set_position(("axes", 1.08))
                ax3.plot(psu_t, psu_i, color="#bcbd22", linewidth=0.8, alpha=0.4, label="PSU I (A)")
                ax3.set_ylabel("PSU current (A)", fontsize=7)
                ax3.tick_params(labelsize=6)
        except Exception:
            pass

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    return True


def plot_weapon_latency_cycles(step_dir: Path, title: str, out_png: Path, *, pdf=None) -> bool:
    """Plot 2 - Latency Breakdown: grouped bar chart across all cycles."""
    result_path = step_dir / "weapon_latency_result.json"
    if not result_path.exists():
        return False

    result = load_json(result_path)
    cycles = result.get("cycles") if isinstance(result, dict) else None
    if not isinstance(cycles, list) or not cycles:
        return False

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    xs: list[int] = []
    bt_vals: list[float] = []
    ramp_vals: list[float] = []
    motor_vals: list[float] = []
    axis_vals: list[int] = []

    for c in cycles:
        if not isinstance(c, dict):
            continue
        idx = safe_int(c.get("cycle"))
        if idx is None:
            continue
        lat = c.get("latency_ms") or {}
        bt = safe_float(lat.get("bt_link_approx"))
        ramp = safe_float(lat.get("fw_target_to_dshot"))
        motor = safe_float(lat.get("fw_dshot_to_rpm"))
        if ramp is None or motor is None:
            continue
        xs.append(idx)
        bt_vals.append(bt if bt is not None else 0.0)
        ramp_vals.append(ramp)
        motor_vals.append(motor)
        axis_vals.append(safe_int(c.get("axis_value")) or 0)

    if not xs:
        return False

    fig, ax = plt.subplots(figsize=(10.5, 4.5), constrained_layout=True)
    x_arr = np.arange(len(xs))
    width = 0.55

    # Stacked bars: BT+Input | Ramp | Motor+Telem.
    bars_bt = ax.bar(x_arr, bt_vals, width, label="BT link + input", color="#9467bd", alpha=0.85)
    bars_ramp = ax.bar(x_arr, ramp_vals, width, bottom=bt_vals, label="Ramp (target→DShot)", color="#ff7f0e", alpha=0.85)
    bottoms = [b + r for b, r in zip(bt_vals, ramp_vals)]
    bars_motor = ax.bar(x_arr, motor_vals, width, bottom=bottoms, label="Motor+Telem (DShot→RPM)", color="#d62728", alpha=0.85)

    # Annotate total on top of each bar.
    for i in range(len(xs)):
        total = bt_vals[i] + ramp_vals[i] + motor_vals[i]
        ax.text(x_arr[i], total + 2, f"{total:.0f}ms", ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x_arr)
    ax.set_xticklabels([f"C{x}\n(RY={a})" for x, a in zip(xs, axis_vals)], fontsize=7)
    ax.set_ylabel("latency (ms)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper right", framealpha=0.9, fontsize=8)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    return True


def plot_weapon_latency_stats(step_dir: Path, title: str, out_png: Path, *, pdf=None) -> bool:
    """Plot 3 - Box plot of latency segments across all cycles + summary table."""
    result_path = step_dir / "weapon_latency_result.json"
    if not result_path.exists():
        return False

    result = load_json(result_path)
    cycles = result.get("cycles") if isinstance(result, dict) else None
    if not isinstance(cycles, list) or len(cycles) < 2:
        return False

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Collect per-segment data.
    segments: dict[str, list[float]] = {
        "BT link": [],
        "Ramp": [],
        "Motor+Telem": [],
        "Total (FW)": [],
        "Total (Host)": [],
    }
    for c in cycles:
        lat = c.get("latency_ms") or {}
        bt = safe_float(lat.get("bt_link_approx"))
        ramp = safe_float(lat.get("fw_target_to_dshot"))
        motor = safe_float(lat.get("fw_dshot_to_rpm"))
        fw_total = safe_float(lat.get("total_fw"))
        host_total = safe_float(lat.get("total_host"))
        if bt is not None:
            segments["BT link"].append(bt)
        if ramp is not None:
            segments["Ramp"].append(ramp)
        if motor is not None:
            segments["Motor+Telem"].append(motor)
        if fw_total is not None:
            segments["Total (FW)"].append(fw_total)
        if host_total is not None:
            segments["Total (Host)"].append(host_total)

    # Filter out empty segments.
    labels = [k for k, v in segments.items() if v]
    data = [segments[k] for k in labels]
    if not data:
        return False

    fig, ax = plt.subplots(figsize=(10.5, 5.0), constrained_layout=True)
    bp = ax.boxplot(data, labels=labels, patch_artist=True, showmeans=True)
    colors = ["#9467bd", "#ff7f0e", "#d62728", "#2ca02c", "#1f77b4"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)

    ax.set_ylabel("latency (ms)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)

    # Add summary text.
    import statistics
    summary_lines: list[str] = []
    for lbl, vals in zip(labels, data):
        if not vals:
            continue
        med = statistics.median(vals)
        mn = min(vals)
        mx = max(vals)
        avg = statistics.mean(vals)
        summary_lines.append(f"{lbl}: med={med:.1f} mean={avg:.1f} min={mn:.1f} max={mx:.1f}")
    if summary_lines:
        ax.text(0.02, 0.98, "\n".join(summary_lines), transform=ax.transAxes, fontsize=7,
                va="top", ha="left", family="monospace",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    return True


def plot_latency_drift(step_dir: Path, title: str, out_png: Path, *, pdf=None) -> bool:
    """Plot per-cycle total_fw latency with linear regression trend line."""
    result_path = step_dir / "weapon_latency_result.json"
    if not result_path.exists():
        return False

    result = load_json(result_path)
    if not isinstance(result, dict):
        return False

    drift = result.get("drift")
    if not isinstance(drift, dict) or "slope_ms_per_cycle" not in drift:
        return False

    cycles = result.get("cycles")
    if not isinstance(cycles, list) or len(cycles) < 2:
        return False

    # Extract per-cycle total_fw values.
    ys: list[float] = []
    for c in cycles:
        lat = c.get("latency_ms") or {}
        val = safe_float(lat.get("total_fw"))
        if val is not None:
            ys.append(val)
    if len(ys) < 2:
        return False

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = list(range(1, len(ys) + 1))
    slope = drift["slope_ms_per_cycle"]
    max_latency_ms = drift.get("max_latency_ms")
    check_drift = drift.get("check_drift", False)
    drift_ok = drift.get("drift_ok", True)

    # Compute regression line points using 0-indexed xs for slope calculation.
    import statistics
    mean_x = statistics.mean(range(len(ys)))
    mean_y = statistics.mean(ys)
    reg_ys = [mean_y + slope * (i - mean_x) for i in range(len(ys))]

    fig, ax = plt.subplots(figsize=(10.5, 5.0), constrained_layout=True)
    ax.scatter(xs, ys, color="#1f77b4", s=40, zorder=3, label="Per-cycle FW latency")
    ax.plot(xs, reg_ys, color="#d62728", linewidth=1.5, linestyle="--",
            label=f"Trend: {slope:+.4f} ms/cycle")

    if max_latency_ms is not None:
        ax.axhline(y=max_latency_ms, color="#ff7f0e", linewidth=1.0, linestyle=":",
                    label=f"Max threshold: {max_latency_ms:.0f} ms")

    ax.set_xlabel("Cycle #")
    ax.set_ylabel("Total FW latency (ms)")
    status_str = ""
    if check_drift:
        status_str = " [PASS]" if drift_ok else " [FAIL]"
    ax.set_title(f"{title}{status_str}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=8)

    # Annotate half-split info.
    first_half = drift.get("first_half_mean_ms")
    second_half = drift.get("second_half_mean_ms")
    half_delta = drift.get("half_delta_ms")
    if first_half is not None and second_half is not None:
        info = (f"1st half mean: {first_half:.1f} ms\n"
                f"2nd half mean: {second_half:.1f} ms\n"
                f"Delta: {half_delta:+.1f} ms")
        ax.text(0.98, 0.98, info, transform=ax.transAxes, fontsize=7,
                va="top", ha="right", family="monospace",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    return True


def make_summary_page(report: dict[str, Any], *, pdf) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(11.0, 8.5), constrained_layout=True)
    ax = fig.add_subplot(111)
    ax.axis("off")

    ok = bool(report.get("ok"))
    suite = report.get("suite")
    run_id = report.get("run_id")
    run_dir = report.get("run_dir")
    started_at = report.get("started_at")
    git_meta = report.get("git") or {}

    lines: list[str] = []
    lines.append("ThumbsUp HITL Report")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Suite: {suite}")
    lines.append(f"Result: {'PASS' if ok else 'FAIL'}")
    lines.append(f"Run ID: {run_id}")
    lines.append(f"Run Dir: {run_dir}")
    lines.append(f"Started At: {started_at}")
    if isinstance(git_meta, dict) and git_meta:
        commit = git_meta.get("commit")
        branch = git_meta.get("branch")
        dirty = git_meta.get("dirty")
        lines.append(f"Git: {branch}@{commit} dirty={dirty}")
    lines.append("")
    lines.append("Steps:")
    for r in report.get("results") or []:
        name = r.get("name")
        rok = r.get("ok")
        detail = r.get("detail")
        lines.append(f"- {name}: {'PASS' if rok else 'FAIL'} ({detail})")

    text = "\n".join(lines)
    ax.text(
        0.02,
        0.98,
        text,
        va="top",
        ha="left",
        family="monospace",
        fontsize=10,
    )

    pdf.savefig(fig)
    plt.close(fig)


def write_markdown(run_dir: Path, report: dict[str, Any], step_sections: list[str]) -> None:
    ok = bool(report.get("ok"))
    suite = report.get("suite")
    run_id = report.get("run_id")

    md: list[str] = []
    md.append(f"# ThumbsUp HITL Report")
    md.append("")
    md.append(f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`")
    md.append(f"- Suite: `{suite}`")
    md.append(f"- Result: `{'PASS' if ok else 'FAIL'}`")
    md.append(f"- Run ID: `{run_id}`")
    md.append(f"- Run Dir: `{run_dir}`")
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append("```json")
    md.append(json.dumps(report, indent=2, sort_keys=True))
    md.append("```")
    md.append("")
    md.append("## Steps")
    md.append("")
    md.extend(step_sections)
    md.append("")
    md.append("## Artifacts Index")
    md.append("")
    md.append("This directory contains the full raw logs used to generate this report. Key files:")
    md.append("")
    md.append(f"- `orchestrator_report.json`")
    md.append(f"- `report.pdf`")
    md.append(f"- `report_gen.log`")
    md.append(f"- `steps/` (per-step serial logs + JSON results)")
    md.append(f"- `plots/` (generated plots)")
    md.append("")

    (run_dir / "report.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate HITL report (md/pdf/plots) from a run directory")
    ap.add_argument("--run-dir", required=True, help="Run directory produced by tools/hitl_orchestrator.py")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    report_path = run_dir / "orchestrator_report.json"
    if not report_path.exists():
        raise SystemExit(f"missing {report_path}")

    report = load_json(report_path)
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Generate PDF + plots.
    from matplotlib.backends.backend_pdf import PdfPages

    pdf_path = run_dir / "report.pdf"
    step_sections: list[str] = []

    with PdfPages(pdf_path) as pdf:
        make_summary_page(report, pdf=pdf)

        for r in report.get("results") or []:
            name = r.get("name") or "step"
            step_ok = bool(r.get("ok"))
            artifacts_dir = r.get("artifacts_dir")
            step_dir = Path(artifacts_dir) if artifacts_dir else None

            step_sections.append(f"### {name}")
            step_sections.append("")
            step_sections.append(f"- Result: `{'PASS' if step_ok else 'FAIL'}`")
            step_sections.append(f"- Detail: `{r.get('detail')}`")
            if step_dir is not None:
                step_sections.append(f"- Artifacts: `{step_dir.relative_to(run_dir) if step_dir.is_relative_to(run_dir) else step_dir}`")
            step_sections.append("")

            if step_dir is None or not step_dir.exists():
                continue

            # List artifacts in markdown (flat list, no nesting).
            files = sorted([p for p in step_dir.rglob("*") if p.is_file()])
            if files:
                step_sections.append("Files:")
                step_sections.append("")
                for p in files:
                    rel = p.relative_to(run_dir) if p.is_relative_to(run_dir) else p
                    step_sections.append(f"- `{rel}`")
                step_sections.append("")

            # Include known JSON result files (small).
            for json_name in [
                "drive_spin_result.json",
                "weapon_spin_result.json",
                "weapon_latency_result.json",
                "estop_drive_result.json",
                "weapon_disarmed_guard_result.json",
                "estop_weapon_result.json",
                "drive_e2e_result.json",
                "disconnect_failsafe_result.json",
                "psu_snapshot.json",
            ]:
                jp = step_dir / json_name
                if not jp.exists():
                    continue
                step_sections.append(f"{json_name}:")
                step_sections.append("")
                step_sections.append("```json")
                step_sections.append(jp.read_text(encoding="utf-8"))
                step_sections.append("```")
                step_sections.append("")

            # Plots: PSU current.
            psu_samples = step_dir / "psu_current_samples.json"
            if psu_samples.exists():
                out_png = plots_dir / f"{slugify(name)}_psu_current.png"
                if plot_psu_current(psu_samples, f"{name} - PSU Current", out_png, pdf=pdf):
                    step_sections.append(f"![{name} PSU current]({out_png.relative_to(run_dir)})")
                    step_sections.append("")

            # Plots: weapon latency (v2: RPM-based with firmware timestamps).
            if (step_dir / "weapon_latency_result.json").exists():
                # One time-series plot per cycle.
                lat_data = load_json(step_dir / "weapon_latency_result.json")
                n_cycles = len(lat_data.get("cycles", [])) if isinstance(lat_data, dict) else 0
                for ci in range(n_cycles):
                    suffix = f"_c{ci + 1}" if n_cycles > 1 else ""
                    out_png = plots_dir / f"{slugify(name)}_weapon_latency{suffix}.png"
                    if plot_weapon_latency(step_dir, f"{name} - Weapon Latency", out_png, pdf=pdf, cycle_idx=ci):
                        step_sections.append(f"![{name} weapon latency cycle {ci + 1}]({out_png.relative_to(run_dir)})")
                        step_sections.append("")
                out_png = plots_dir / f"{slugify(name)}_weapon_latency_cycles.png"
                if plot_weapon_latency_cycles(step_dir, f"{name} - Latency Breakdown", out_png, pdf=pdf):
                    step_sections.append(f"![{name} weapon latency cycles]({out_png.relative_to(run_dir)})")
                    step_sections.append("")
                out_png = plots_dir / f"{slugify(name)}_weapon_latency_stats.png"
                if plot_weapon_latency_stats(step_dir, f"{name} - Latency Stats", out_png, pdf=pdf):
                    step_sections.append(f"![{name} weapon latency stats]({out_png.relative_to(run_dir)})")
                    step_sections.append("")
                out_png = plots_dir / f"{slugify(name)}_weapon_latency_drift.png"
                if plot_latency_drift(step_dir, f"{name} - Latency Drift", out_png, pdf=pdf):
                    step_sections.append(f"![{name} weapon latency drift]({out_png.relative_to(run_dir)})")
                    step_sections.append("")

                # Latency markdown summary.
                try:
                    lat_result = load_json(step_dir / "weapon_latency_result.json")
                    if isinstance(lat_result, dict) and lat_result.get("summary"):
                        summary = lat_result["summary"]
                        step_sections.append("**Latency Summary:**")
                        step_sections.append("")
                        for seg_name in ["total_host_ms", "total_fw_ms", "bt_link_approx_ms",
                                         "fw_ramp_ms", "fw_motor_telem_ms"]:
                            seg = summary.get(seg_name)
                            if isinstance(seg, dict):
                                step_sections.append(
                                    f"- {seg_name}: median={seg.get('median', '?')}ms "
                                    f"(min={seg.get('min', '?')}, max={seg.get('max', '?')}, "
                                    f"n={seg.get('samples', '?')})"
                                )
                        step_sections.append("")
                        step_sections.append(
                            f"> Note: Competition firmware uses WEAPON_DSHOT_TELEMETRY_MS=50ms "
                            f"decode polling, adding up to 50ms to fw_motor_telem."
                        )
                        step_sections.append("")

                    # Drift summary.
                    if isinstance(lat_result, dict) and isinstance(lat_result.get("drift"), dict):
                        drift = lat_result["drift"]
                        if "slope_ms_per_cycle" in drift:
                            drift_ok = drift.get("drift_ok", True)
                            check_drift = drift.get("check_drift", False)
                            status = ""
                            if check_drift:
                                status = " PASS" if drift_ok else " FAIL"
                            step_sections.append("**Drift Analysis:**")
                            step_sections.append("")
                            step_sections.append(
                                f"- Slope: {drift['slope_ms_per_cycle']:.4f} ms/cycle")
                            first_h = drift.get("first_half_mean_ms")
                            second_h = drift.get("second_half_mean_ms")
                            delta_h = drift.get("half_delta_ms")
                            if first_h is not None and second_h is not None:
                                step_sections.append(
                                    f"- First half mean: {first_h:.1f} ms, "
                                    f"Second half mean: {second_h:.1f} ms "
                                    f"(delta: {delta_h:+.1f} ms)")
                            max_c = drift.get("max_cycle_ms")
                            if max_c is not None:
                                step_sections.append(
                                    f"- Max single cycle: {max_c:.1f} ms")
                            if check_drift:
                                step_sections.append(
                                    f"- Drift check:{status}")
                                if not drift_ok:
                                    for reason in drift.get("drift_fail_reasons", []):
                                        step_sections.append(f"  - {reason}")
                            step_sections.append("")
                except Exception:
                    pass

            # Plots: drive PWM.
            robot_log = step_dir / "robot_serial.log"
            series = parse_robot_status_series(robot_log)
            if series is not None:
                out_png = plots_dir / f"{slugify(name)}_drive_pwm.png"
                if plot_drive_pwm(series, f"{name} - Drive PWM", out_png, pdf=pdf):
                    step_sections.append(f"![{name} drive PWM]({out_png.relative_to(run_dir)})")
                    step_sections.append("")

    write_markdown(run_dir, report, step_sections)


if __name__ == "__main__":
    main()
