"""Shared utilities for ThumbsUp tools.

This module consolidates helper functions that were previously duplicated
across multiple tool scripts (serial port detection, subprocess wrappers,
HITL log parsing, etc.).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Compiled regex for HITL status lines  (e.g. "HITL STATUS key=val ...")
# ---------------------------------------------------------------------------
HITL_STATUS_RE: re.Pattern[str] = re.compile(r"^HITL STATUS (.+)$")


# ---------------------------------------------------------------------------
# Serial port discovery
# ---------------------------------------------------------------------------

def find_pico_ports(product_hint: str | None = None) -> list[str]:
    """Return a list of serial ports that look like an RP2040 / Pico.

    Parameters
    ----------
    product_hint:
        Optional substring matched (case-insensitive) against the port's
        *product* and *description* fields.  Ports that don't match the
        hint are skipped.
    """
    if serial is None:
        raise RuntimeError("pyserial not installed. Try: pip install pyserial")

    ports = serial.tools.list_ports.comports()
    matches: list[str] = []
    for port in ports:
        if product_hint:
            product = (port.product or "").lower()
            description = (port.description or "").lower()
            if (product_hint.lower() not in product
                    and product_hint.lower() not in description):
                continue
        if ("2E8A" in port.hwid
                or "Pico" in port.description
                or "RP2040" in port.description):
            matches.append(port.device)
    return matches


def find_pico_port(product_hint: str | None = None) -> str | None:
    """Return the first serial port that looks like an RP2040 / Pico.

    When *product_hint* is ``None`` the function first checks for the
    well-known udev symlink ``/dev/ttyHITL_ROBOT`` before scanning.
    """
    if product_hint is None:
        hitl = Path("/dev/ttyHITL_ROBOT")
        if hitl.exists():
            return str(hitl)

    matches = find_pico_ports(product_hint)
    if matches:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------

def run_cmd(
    args: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run *args* via :func:`subprocess.run`, raising on non-zero exit.

    This is a thin convenience wrapper that always uses ``text=True`` and
    defers the ``check`` logic so we can include stderr/stdout in the
    exception message.
    """
    result = subprocess.run(
        args,
        capture_output=capture_output,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "unknown error"
        raise RuntimeError(f"command failed: {' '.join(args)}\n{detail}")
    return result


# ---------------------------------------------------------------------------
# HITL log helpers
# ---------------------------------------------------------------------------

def parse_kv_payload(payload: str) -> dict[str, str]:
    """Parse a space-separated ``key=value`` telemetry string."""
    out: dict[str, str] = {}
    for token in payload.strip().split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k] = v
    return out


def slugify(name: str) -> str:
    """Lowercase *name*, replace non-alnum runs with underscores."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
