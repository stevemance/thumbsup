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
        "run": "#f58518",
        "forward": "#54a24b",
        "turn": "#e45756",
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

