"""
Minimal self-contained ctypes wrapper around libngspice.so (the ngspice shared
library that KiCad ships).  No ngspice binary is required.

Usage:
    from ngspice_shared import NgSpice
    ng = NgSpice()
    ng.load_netlist(netlist_string)
    ng.run("dc vbat -13 13 0.1")       # or "op", "tran 1n 100u"
    v = ng.vector("v(out)")            # numpy array
    names = ng.vectors()               # list of vector names in the current plot

Every run creates a new plot in ngspice; vector() reads from the current plot
unless plot= is given.
"""
import ctypes as ct
import os
import sys

import numpy as np

_LIB_CANDIDATES = [
    os.environ.get("NGSPICE_LIB", ""),
    "/usr/lib/x86_64-linux-gnu/libngspice.so.0",
    "libngspice.so.0",
    "libngspice.so",
]


class NgComplex(ct.Structure):
    _fields_ = [("cx_real", ct.c_double), ("cx_imag", ct.c_double)]


class VectorInfo(ct.Structure):
    _fields_ = [
        ("v_name", ct.c_char_p),
        ("v_type", ct.c_int),
        ("v_flags", ct.c_short),
        ("v_realdata", ct.POINTER(ct.c_double)),
        ("v_compdata", ct.POINTER(NgComplex)),
        ("v_length", ct.c_int),
    ]


# Callback prototypes (see ngspice manual, chapter "Shared ngspice API")
SendChar = ct.CFUNCTYPE(ct.c_int, ct.c_char_p, ct.c_int, ct.c_void_p)
SendStat = ct.CFUNCTYPE(ct.c_int, ct.c_char_p, ct.c_int, ct.c_void_p)
ControlledExit = ct.CFUNCTYPE(ct.c_int, ct.c_int, ct.c_bool, ct.c_bool, ct.c_int, ct.c_void_p)
SendData = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_int, ct.c_int, ct.c_void_p)
SendInitData = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_int, ct.c_void_p)
BGThreadRunning = ct.CFUNCTYPE(ct.c_int, ct.c_bool, ct.c_int, ct.c_void_p)

VF_COMPLEX = 1 << 1


class NgSpiceError(RuntimeError):
    pass


class NgSpice:
    def __init__(self, verbose=False, libpath=None):
        self.verbose = verbose
        self.stdout_lines = []
        self.stderr_lines = []
        self._lib = None
        for cand in ([libpath] if libpath else []) + _LIB_CANDIDATES:
            if not cand:
                continue
            try:
                self._lib = ct.CDLL(cand, mode=ct.RTLD_GLOBAL)
                self.libpath = cand
                break
            except OSError:
                continue
        if self._lib is None:
            raise NgSpiceError("could not load libngspice; tried %r" % _LIB_CANDIDATES)

        lib = self._lib
        lib.ngSpice_Init.restype = ct.c_int
        lib.ngSpice_Init.argtypes = [SendChar, SendStat, ControlledExit, SendData,
                                     SendInitData, BGThreadRunning, ct.c_void_p]
        lib.ngSpice_Command.restype = ct.c_int
        lib.ngSpice_Command.argtypes = [ct.c_char_p]
        lib.ngSpice_Circ.restype = ct.c_int
        lib.ngSpice_Circ.argtypes = [ct.POINTER(ct.c_char_p)]
        lib.ngGet_Vec_Info.restype = ct.POINTER(VectorInfo)
        lib.ngGet_Vec_Info.argtypes = [ct.c_char_p]
        lib.ngSpice_CurPlot.restype = ct.c_char_p
        lib.ngSpice_CurPlot.argtypes = []
        lib.ngSpice_AllPlots.restype = ct.POINTER(ct.c_char_p)
        lib.ngSpice_AllPlots.argtypes = []
        lib.ngSpice_AllVecs.restype = ct.POINTER(ct.c_char_p)
        lib.ngSpice_AllVecs.argtypes = [ct.c_char_p]
        lib.ngSpice_running.restype = ct.c_bool
        lib.ngSpice_running.argtypes = []

        # Keep references to the callbacks so they are not garbage collected.
        self._cb_char = SendChar(self._on_char)
        self._cb_stat = SendStat(self._on_stat)
        self._cb_exit = ControlledExit(self._on_exit)
        self._cb_data = SendData(self._on_data)
        self._cb_init = SendInitData(self._on_init)
        self._cb_bg = BGThreadRunning(self._on_bg)
        rc = lib.ngSpice_Init(self._cb_char, self._cb_stat, self._cb_exit,
                              self._cb_data, self._cb_init, self._cb_bg, None)
        if rc != 0:
            raise NgSpiceError("ngSpice_Init returned %d" % rc)

    # ---- callbacks -------------------------------------------------------
    def _on_char(self, msg, ident, user):
        s = msg.decode(errors="replace")
        if s.startswith("stderr"):
            self.stderr_lines.append(s[6:].strip())
            if self.verbose or "Error" in s or "error" in s:
                print("[ngspice] " + s, file=sys.stderr)
        else:
            self.stdout_lines.append(s[6:].strip() if s.startswith("stdout") else s)
            if self.verbose:
                print("[ngspice] " + s)
        return 0

    def _on_stat(self, msg, ident, user):
        return 0

    def _on_exit(self, status, immediate, quit_, ident, user):
        # Never let ngspice kill the host process.
        return 0

    def _on_data(self, pvecvalues, count, ident, user):
        return 0

    def _on_init(self, pvecinfo, ident, user):
        return 0

    def _on_bg(self, running, ident, user):
        return 0

    # ---- public API ------------------------------------------------------
    def command(self, cmd):
        rc = self._lib.ngSpice_Command(cmd.encode())
        if rc != 0:
            raise NgSpiceError("ngSpice_Command(%r) returned %d" % (cmd, rc))
        return rc

    def load_netlist(self, netlist):
        """Load a complete netlist (first line = title, must contain .end)."""
        self.stdout_lines.clear()
        self.stderr_lines.clear()
        lines = [ln for ln in netlist.strip("\n").splitlines()]
        if not any(ln.strip().lower() == ".end" for ln in lines):
            lines.append(".end")
        arr = (ct.c_char_p * (len(lines) + 1))()
        for i, ln in enumerate(lines):
            arr[i] = ln.encode()
        arr[len(lines)] = None
        rc = self._lib.ngSpice_Circ(arr)
        if rc != 0:
            raise NgSpiceError("ngSpice_Circ failed (rc=%d):\n%s" % (rc, "\n".join(self.stderr_lines)))
        errs = [l for l in self.stderr_lines if "error" in l.lower()]
        if errs:
            raise NgSpiceError("netlist errors:\n" + "\n".join(errs))

    def run(self, analysis):
        """analysis e.g. 'op', 'dc vbat -13 13 0.1', 'tran 1n 100u'.  Runs in the
        foreground (blocking) and returns the resulting plot name."""
        self.command(analysis)
        errs = [l for l in self.stderr_lines if "error" in l.lower()]
        if errs:
            raise NgSpiceError("analysis errors:\n" + "\n".join(errs))
        return self.current_plot()

    def current_plot(self):
        p = self._lib.ngSpice_CurPlot()
        return p.decode() if p else None

    def plots(self):
        arr = self._lib.ngSpice_AllPlots()
        out = []
        i = 0
        while arr and arr[i]:
            out.append(arr[i].decode())
            i += 1
        return out

    def vectors(self, plot=None):
        plot = plot or self.current_plot()
        arr = self._lib.ngSpice_AllVecs(plot.encode())
        out = []
        i = 0
        while arr and arr[i]:
            out.append(arr[i].decode())
            i += 1
        return out

    def vector(self, name, plot=None):
        """Return vector as numpy array (float64 or complex128)."""
        plot = plot or self.current_plot()
        full = name if "." in name.split("(")[0] else "%s.%s" % (plot, name)
        p = self._lib.ngGet_Vec_Info(full.encode())
        if not p:
            p = self._lib.ngGet_Vec_Info(name.encode())
        if not p:
            raise NgSpiceError("vector %r not found; available: %s" % (name, self.vectors(plot)))
        vi = p.contents
        n = vi.v_length
        if vi.v_flags & VF_COMPLEX and vi.v_compdata:
            buf = np.ctypeslib.as_array(vi.v_compdata, shape=(n,))
            return (buf["cx_real"] + 1j * buf["cx_imag"]).copy()
        return np.ctypeslib.as_array(vi.v_realdata, shape=(n,)).copy()

    def destroy(self):
        try:
            self.command("destroy all")
        except NgSpiceError:
            pass


if __name__ == "__main__":
    # Self-test: resistor divider.
    ng = NgSpice(verbose=False)
    ng.load_netlist("""selftest divider
v1 in 0 dc 10
r1 in out 1k
r2 out 0 1k
.end""")
    ng.run("op")
    print("plot:", ng.current_plot(), "vectors:", ng.vectors())
    print("v(out) =", ng.vector("v(out)"))
    ng.run("dc v1 0 10 5")
    print("dc sweep v(out) =", ng.vector("v(out)"), "sweep =", ng.vector("v-sweep"))
